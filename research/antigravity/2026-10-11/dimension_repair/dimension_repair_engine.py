"""
dimension_repair_engine.py — Reference implementations and benchmarks for
Headless Linear Dimension & Associativity Repair in DXF Builder (Repair #1).

Contract context:
In dxf_builder_lib/reviewer.py, Reviewer #1 performs comprehensive headless
validation on native DIMENSION entities:
- dimension count matches build_result.dimension_count
- DIMENSION entity handle exists in doc.entitydb
- DXF entity type is DIMENSION
- entity.dxf.layer matches expected written dimension layer
- entity.get_measurement() matches written measurement and approved value
- linear_dimension_matches_feature() proves WCS defpoint2/defpoint3 match
  the referenced ModelSpace LINE primitive.

However, dxf_builder_lib/repair.py currently only implements:
- repair_dxf() for raw primitives (LINE, CIRCLE, ARC, TEXT)
- repair_insert_components() for INSERT components
And has NO dimension repair capability.

This module provides:
- DimensionRepairResult dataclass
- Strategy A: Current Production Baseline (repair_dxf skips dimensions)
- Strategy B: Blind DB Wipe / Unassociated Reconstruction (fails feature binding)
- Strategy C: In-Place Property Patch (fails on handle loss or defpoint corruption)
- Strategy D: Full Ground-Truth Handle Reconstruction with Line Feature Associativity (Selected)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

try:
    import ezdxf
    _HAS_EZDXF = True
except ImportError:
    _HAS_EZDXF = False

from dxf_builder_lib.builder import BuildResult
from dxf_builder_lib.repair import repair_dxf


@dataclass
class DimensionRepairResult:
    """Repair #1 outcome for DIMENSION entities."""
    repaired_count: int = 0
    skipped_count: int = 0
    repaired_validation_ids: List[str] = field(default_factory=list)
    skipped_validation_ids: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)


def extract_validation_id_from_mismatch(mismatch_msg: str) -> Optional[str]:
    """Extract cross-validation ID from a dimension mismatch string.

    Reviewer #1 dimension messages have the form:
    '<validation_id>: <error message>'
    or
    'DIMENSION count mismatch: expected <n>, actual <m>'
    """
    cleaned = mismatch_msg.strip()
    if cleaned.startswith("DIMENSION count mismatch:"):
        return None
    if ":" in cleaned:
        candidate = cleaned.split(":", 1)[0].strip()
        if candidate:
            return candidate
    return None


def repair_dimensions_strategy_a(
    build_result: BuildResult,
    dimension_mismatches: List[str],
) -> DimensionRepairResult:
    """Strategy A: Current Production Behavior.

    Attempts to invoke existing repair_dxf().
    Because build_result.handle_by_primitive_id and
    written_geometry_by_primitive_id do NOT contain dimension validation IDs,
    repair_dxf() skips every dimension mismatch without making any repairs.
    """
    if not _HAS_EZDXF:
        raise ImportError("ezdxf is required for repair operations")

    if not dimension_mismatches:
        return DimensionRepairResult()

    raw_result = repair_dxf(build_result, dimension_mismatches)
    return DimensionRepairResult(
        repaired_count=raw_result.repaired_count,
        skipped_count=raw_result.skipped_count,
        repaired_validation_ids=raw_result.repaired_primitive_ids,
        skipped_validation_ids=raw_result.skipped_primitive_ids,
        details=[f"Strategy A: {d}" for d in raw_result.details],
    )


def repair_dimensions_strategy_b(
    build_result: BuildResult,
    dimension_mismatches: List[str],
) -> DimensionRepairResult:
    """Strategy B: Blind DB Wipe / Unassociated Reconstruction.

    Deletes corrupted dimension entities, but creates naive replacement dimensions
    without associating with the underlying LINE primitive endpoints (dummy defpoints).
    Fails reviewer linear_dimension_matches_feature() checks.
    """
    if not _HAS_EZDXF:
        raise ImportError("ezdxf is required for repair operations")

    result = DimensionRepairResult()
    if not dimension_mismatches:
        return result

    affected_ids: Set[str] = set()
    for msg in dimension_mismatches:
        vid = extract_validation_id_from_mismatch(msg)
        if vid:
            affected_ids.add(vid)
        elif msg.startswith("DIMENSION count mismatch:"):
            affected_ids.update(build_result.dimension_handle_by_cross_validation_id.keys())

    doc = ezdxf.readfile(build_result.output_path)
    msp = doc.modelspace()
    db = doc.entitydb

    for vid in sorted(affected_ids):
        handle = build_result.dimension_handle_by_cross_validation_id.get(vid)
        expected = build_result.written_dimension_by_cross_validation_id.get(vid)
        if expected is None:
            result.skipped_validation_ids.append(vid)
            result.skipped_count += 1
            result.details.append(f"{vid}: BỎ QUA - thiếu written_dimension evidence")
            continue

        if handle and db.get(handle) is not None:
            msp.delete_entity(db.get(handle))

        # Naive linear dim with arbitrary defpoints, unassociated to underlying line
        measurement = float(expected.get("measurement", 50.0))
        dummy_p1 = (0.0, 0.0)
        dummy_p2 = (measurement, 0.0)
        dummy_base = (measurement / 2.0, 10.0)

        layer = expected.get("layer", "DIMENSIONS")
        if layer not in doc.layers:
            doc.layers.new(name=layer, dxfattribs={"color": 7})

        dim_override = msp.add_linear_dim(
            base=dummy_base,
            p1=dummy_p1,
            p2=dummy_p2,
            dxfattribs={"layer": layer},
        )
        dim_override.render()
        new_dim = dim_override.dimension
        build_result.dimension_handle_by_cross_validation_id[vid] = new_dim.dxf.handle
        result.repaired_validation_ids.append(vid)
        result.repaired_count += 1
        result.details.append(f"{vid}: Blind recreated without line associativity")

    build_result.dimension_count = sum(1 for e in msp if e.dxftype() == "DIMENSION")
    doc.saveas(build_result.output_path)
    return result


def repair_dimensions_strategy_c(
    build_result: BuildResult,
    dimension_mismatches: List[str],
) -> DimensionRepairResult:
    """Strategy C: In-Place Entity Patch.

    Attempts to patch existing entity attributes (layer) in place without
    re-creating the entity or reconstructing defpoints.
    Fails when:
    - Entity handle is missing or deleted from entitydb.
    - Defpoints / measurement geometry are corrupted.
    - Dimension block representation is out of sync.
    """
    if not _HAS_EZDXF:
        raise ImportError("ezdxf is required for repair operations")

    result = DimensionRepairResult()
    if not dimension_mismatches:
        return result

    affected_ids: Set[str] = set()
    for msg in dimension_mismatches:
        vid = extract_validation_id_from_mismatch(msg)
        if vid:
            affected_ids.add(vid)

    doc = ezdxf.readfile(build_result.output_path)
    db = doc.entitydb

    for vid in sorted(affected_ids):
        handle = build_result.dimension_handle_by_cross_validation_id.get(vid)
        expected = build_result.written_dimension_by_cross_validation_id.get(vid)
        if expected is None or handle is None:
            result.skipped_validation_ids.append(vid)
            result.skipped_count += 1
            result.details.append(f"{vid}: BỎ QUA - thiếu handle hoặc written_dimension")
            continue

        entity = db.get(handle)
        if entity is None or entity.dxftype() != "DIMENSION":
            result.skipped_validation_ids.append(vid)
            result.skipped_count += 1
            result.details.append(f"{vid}: BỎ QUA - handle không tồn tại hoặc không phải DIMENSION")
            continue

        # In-place patch layer only
        target_layer = expected.get("layer", "DIMENSIONS")
        if target_layer not in doc.layers:
            doc.layers.new(name=target_layer, dxfattribs={"color": 7})
        entity.dxf.layer = target_layer

        result.repaired_validation_ids.append(vid)
        result.repaired_count += 1
        result.details.append(f"{vid}: In-place patched layer to '{target_layer}'")

    doc.saveas(build_result.output_path)
    return result


def repair_dimensions_strategy_d(
    build_result: BuildResult,
    dimension_mismatches: List[str],
) -> DimensionRepairResult:
    """Strategy D: Full Ground-Truth Handle Reconstruction with Line Feature Associativity (Selected).

    Execution Contract:
    1. Parse validation IDs from dimension mismatches (including count mismatch).
    2. Retrieve ground-truth written_dimension from build_result.written_dimension_by_cross_validation_id.
    3. Retrieve underlying feature LINE geometry from build_result.written_geometry_by_primitive_id.
    4. Validate finite coordinates and non-zero length. Fail-safe skip on invalid/missing geometry.
    5. Delete stale/corrupted DIMENSION entity by handle (if present in entitydb).
    6. Reconstruct linear dimension with exact outward normal offset, basepoint, and defpoint2/defpoint3.
    7. Render dimension block via ezdxf override.render().
    8. Update build_result.dimension_handle_by_cross_validation_id with new valid handle.
    9. Synchronize build_result.dimension_count.
    10. Save DXF back to build_result.output_path.
    """
    if not _HAS_EZDXF:
        raise ImportError("ezdxf is required for repair operations")

    result = DimensionRepairResult()
    if not dimension_mismatches:
        return result

    doc = ezdxf.readfile(build_result.output_path)
    msp = doc.modelspace()
    db = doc.entitydb

    # Step 1: Collect affected validation IDs
    affected_ids: Set[str] = set()
    for msg in dimension_mismatches:
        vid = extract_validation_id_from_mismatch(msg)
        if vid:
            affected_ids.add(vid)
        elif msg.startswith("DIMENSION count mismatch:"):
            # If total count mismatched, find which tracked dimensions are missing in DB
            for candidate_vid, cand_handle in build_result.dimension_handle_by_cross_validation_id.items():
                if cand_handle not in db or db.get(cand_handle) is None:
                    affected_ids.add(candidate_vid)

    def _ensure_layer(name: str) -> None:
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs={"color": 7})

    for vid in sorted(affected_ids):
        expected = build_result.written_dimension_by_cross_validation_id.get(vid)
        old_handle = build_result.dimension_handle_by_cross_validation_id.get(vid)

        if expected is None:
            result.skipped_validation_ids.append(vid)
            result.skipped_count += 1
            result.details.append(
                f"{vid}: BỎ QUA repair — không tìm được written_dimension trong BuildResult"
            )
            continue

        feature_id = expected.get("geometry_primitive_id")
        if not feature_id:
            result.skipped_validation_ids.append(vid)
            result.skipped_count += 1
            result.details.append(
                f"{vid}: BỎ QUA repair — thiếu geometry_primitive_id trong written_dimension"
            )
            continue

        line_geom = build_result.written_geometry_by_primitive_id.get(feature_id)
        if line_geom is None or line_geom.get("type") != "line":
            result.skipped_validation_ids.append(vid)
            result.skipped_count += 1
            result.details.append(
                f"{vid}: BỎ QUA repair — primitive '{feature_id}' không tồn tại hoặc không phải kiểu 'line'"
            )
            continue

        start = line_geom.get("start")
        end = line_geom.get("end")
        if not isinstance(start, (tuple, list)) or not isinstance(end, (tuple, list)) or len(start) < 2 or len(end) < 2:
            result.skipped_validation_ids.append(vid)
            result.skipped_count += 1
            result.details.append(f"{vid}: BỎ QUA repair — toạ độ start/end không hợp lệ")
            continue

        if not (math.isfinite(start[0]) and math.isfinite(start[1]) and math.isfinite(end[0]) and math.isfinite(end[1])):
            result.skipped_validation_ids.append(vid)
            result.skipped_count += 1
            result.details.append(f"{vid}: BỎ QUA repair — toạ độ chứa NaN hoặc Inf")
            continue

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            result.skipped_validation_ids.append(vid)
            result.skipped_count += 1
            result.details.append(f"{vid}: BỎ QUA repair — đoạn thẳng có độ dài bằng 0")
            continue

        # Step 5: Delete old entity by handle if still present
        if old_handle:
            old_entity = db.get(old_handle)
            if old_entity is not None and old_entity in msp:
                msp.delete_entity(old_entity)

        # Step 6: Compute placement geometry matching builder.py normal convention
        offset = max(length * 0.08, 5.0)
        normal_x, normal_y = -dy / length, dx / length
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        base = (midpoint[0] + normal_x * offset, midpoint[1] + normal_y * offset)
        angle = math.degrees(math.atan2(dy, dx))

        layer = expected.get("layer", "DIMENSIONS")
        _ensure_layer(layer)

        # Step 7: Add linear dimension & render
        p1 = (start[0], start[1])
        p2 = (end[0], end[1])
        override = msp.add_linear_dim(
            base=base,
            p1=p1,
            p2=p2,
            location=base,
            angle=angle,
            dxfattribs={"layer": layer},
        )
        override.render()
        new_dim = override.dimension
        new_handle = new_dim.dxf.handle

        # Step 8: Update handle tracking in BuildResult
        build_result.dimension_handle_by_cross_validation_id[vid] = new_handle

        result.repaired_validation_ids.append(vid)
        result.repaired_count += 1
        result.details.append(
            f"{vid}: đã xoá handle cũ '{old_handle}' và vẽ lại DIMENSION -> handle mới '{new_handle}', "
            f"layer='{layer}', feature_line='{feature_id}', measurement={length:.4f}"
        )

    # Step 9: Synchronize dimension count
    build_result.dimension_count = sum(1 for e in msp if e.dxftype() == "DIMENSION")
    doc.saveas(build_result.output_path)
    return result


# Default alias for production adoption
repair_dimensions = repair_dimensions_strategy_d
