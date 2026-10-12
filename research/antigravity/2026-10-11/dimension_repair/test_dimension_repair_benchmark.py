"""
test_dimension_repair_benchmark.py — Multi-Strategy Benchmark for
Headless Linear Dimension & Associativity Repair in DXF Builder.

Evaluates Strategies A, B, C, D across 8 benchmark scenarios:
- S1: Deleted dimension entity handle
- S2: Corrupted measurement / altered defpoints
- S3: Corrupted layer name
- S4: Endpoint mismatch with underlying LINE feature
- S5: Multi-dimension compound corruption (3 simultaneous faults)
- S6: Selective repair (uncorrupted dimension handle preserved untouched)
- S7: Tilted / diagonal 45-degree dimension repair
- S8: Dimension block out-of-sync / re-render recovery
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from primitive_ir_lib.models import (
    Calibration, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace,
)
from dxf_builder_lib.builder import NativeLinearDimensionSpec, build_dxf
from dxf_builder_lib.reviewer import review_dxf

try:
    import ezdxf
    _HAS_EZDXF = True
except ImportError:
    _HAS_EZDXF = False

from dimension_repair_engine import (
    repair_dimensions_strategy_a,
    repair_dimensions_strategy_b,
    repair_dimensions_strategy_c,
    repair_dimensions_strategy_d,
)


def _build_test_dxf(tmp_dir: str, specs_data: list[tuple[str, str, tuple, tuple, float]]):
    """Build a DXF with lines and dimensions from specs_data: (dim_id, line_id, start, end, approved)"""
    prims = []
    specs = []
    for dim_id, line_id, start, end, approved in specs_data:
        prims.append(
            Primitive(
                id=line_id, type="line", source="geo", confidence=1.0,
                trace=Trace(bbox_px=(0, 0, 10, 10)),
                geometry=LineGeometry(start=Point2D(start[0], start[1]), end=Point2D(end[0], end[1])),
            )
        )
        specs.append(
            NativeLinearDimensionSpec(
                id=dim_id,
                geometry_primitive_id=line_id,
                approved_value_mm=approved,
                source_ref=f"REF-{dim_id}",
            )
        )
    doc = PrimitiveIRDocument(
        source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=500, image_height_px=500),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=prims,
    )
    dxf_path = os.path.join(tmp_dir, "benchmark.dxf")
    built = build_dxf(doc, dxf_path, build_dimensions=True, dimension_specs=specs)
    return built, dxf_path


def test_scenario_1_deleted_dimension_entity():
    """S1: Deleted dimension entity in DXF."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        built, path = _build_test_dxf(tmp, [("D1", "L1", (0, 0), (80, 0), 80.0)])
        doc = ezdxf.readfile(path)
        doc.modelspace().delete_entity(doc.entitydb.get(built.dimension_handle_by_cross_validation_id["D1"]))
        doc.saveas(path)

        rev = review_dxf(built)
        assert not rev.passed

        rep_a = repair_dimensions_strategy_a(built, rev.dimension_mismatches)
        assert rep_a.repaired_count == 0

        # Strategy C fails because entity is missing
        rep_c = repair_dimensions_strategy_c(built, rev.dimension_mismatches)
        assert rep_c.repaired_count == 0

        # Strategy D succeeds
        rep_d = repair_dimensions_strategy_d(built, rev.dimension_mismatches)
        assert rep_d.repaired_count == 1
        assert review_dxf(built).passed is True


def test_scenario_2_corrupted_measurement():
    """S2: Defpoint altered causing measurement drift on an offset line."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        built, path = _build_test_dxf(tmp, [("D1", "L1", (50, 100), (170, 100), 120.0)])
        doc = ezdxf.readfile(path)
        ent = doc.entitydb.get(built.dimension_handle_by_cross_validation_id["D1"])
        ent.dxf.defpoint3 = (200, 100, 0)
        doc.saveas(path)

        rev = review_dxf(built)
        assert not rev.passed

        # Strategy B creates unassociated dimension at (0,0)-(120,0), fails feature binding to L1 at (50,100)
        rep_b = repair_dimensions_strategy_b(built, rev.dimension_mismatches)
        assert rep_b.repaired_count == 1
        rev_b = review_dxf(built)
        assert not rev_b.passed  # Fails feature binding to L1

        # Strategy D recreates properly with exact feature line associativity
        rev_mismatches = rev_b.dimension_mismatches
        rep_d = repair_dimensions_strategy_d(built, rev_mismatches)
        assert rep_d.repaired_count == 1
        assert review_dxf(built).passed is True


def test_scenario_3_corrupted_layer():
    """S3: Corrupted layer name."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        built, path = _build_test_dxf(tmp, [("D1", "L1", (0, 0), (60, 0), 60.0)])
        doc = ezdxf.readfile(path)
        ent = doc.entitydb.get(built.dimension_handle_by_cross_validation_id["D1"])
        ent.dxf.layer = "WRONG_LAYER"
        doc.saveas(path)

        rev = review_dxf(built)
        assert not rev.passed

        rep_a = repair_dimensions_strategy_a(built, rev.dimension_mismatches)
        assert rep_a.repaired_count == 0

        # Strategy D succeeds
        rep_d = repair_dimensions_strategy_d(built, rev.dimension_mismatches)
        assert rep_d.repaired_count == 1
        assert review_dxf(built).passed is True


def test_scenario_4_endpoint_mismatch_with_line_feature():
    """S4: Dimension defpoint2 shifted away from line start."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        built, path = _build_test_dxf(tmp, [("D1", "L1", (10, 20), (90, 20), 80.0)])
        doc = ezdxf.readfile(path)
        ent = doc.entitydb.get(built.dimension_handle_by_cross_validation_id["D1"])
        ent.dxf.defpoint2 = (15, 20, 0)
        doc.saveas(path)

        rev = review_dxf(built)
        assert not rev.passed

        # Strategy C patches layer in-place but cannot fix defpoints; review remains FAIL
        repair_dimensions_strategy_c(built, rev.dimension_mismatches)
        rev_c = review_dxf(built)
        assert not rev_c.passed  # Still fails feature binding

        # Strategy D fully reconstructs defpoints; review PASSES
        rep_d = repair_dimensions_strategy_d(built, rev_c.dimension_mismatches)
        assert rep_d.repaired_count == 1
        assert review_dxf(built).passed is True


def test_scenario_5_compound_multi_dimension_corruption():
    """S5: 3 simultaneous dimension corruptions (deleted, wrong layer, wrong defpoints)."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        built, path = _build_test_dxf(
            tmp,
            [
                ("D1", "L1", (0, 0), (50, 0), 50.0),
                ("D2", "L2", (0, 100), (80, 100), 80.0),
                ("D3", "L3", (0, 200), (100, 200), 100.0),
            ],
        )
        doc = ezdxf.readfile(path)
        # D1: delete entity
        doc.modelspace().delete_entity(doc.entitydb.get(built.dimension_handle_by_cross_validation_id["D1"]))
        # D2: tamper layer
        doc.entitydb.get(built.dimension_handle_by_cross_validation_id["D2"]).dxf.layer = "BAD_LAYER"
        # D3: tamper defpoint3
        doc.entitydb.get(built.dimension_handle_by_cross_validation_id["D3"]).dxf.defpoint3 = (150, 200, 0)
        doc.saveas(path)

        rev = review_dxf(built)
        assert not rev.passed
        assert len(rev.dimension_mismatches) >= 3

        rep_d = repair_dimensions_strategy_d(built, rev.dimension_mismatches)
        assert rep_d.repaired_count == 3
        assert set(rep_d.repaired_validation_ids) == {"D1", "D2", "D3"}
        assert review_dxf(built).passed is True


def test_scenario_6_selective_repair_preserves_uncorrupted():
    """S6: 2 dimensions; only D2 is tampered; D1 must remain untouched with original handle."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        built, path = _build_test_dxf(
            tmp,
            [
                ("D1", "L1", (0, 0), (40, 0), 40.0),
                ("D2", "L2", (0, 50), (90, 50), 90.0),
            ],
        )
        d1_handle_before = built.dimension_handle_by_cross_validation_id["D1"]

        # Tamper only D2
        doc = ezdxf.readfile(path)
        doc.entitydb.get(built.dimension_handle_by_cross_validation_id["D2"]).dxf.layer = "TAMPERED"
        doc.saveas(path)

        rev = review_dxf(built)
        assert not rev.passed

        rep_d = repair_dimensions_strategy_d(built, rev.dimension_mismatches)
        assert rep_d.repaired_count == 1
        assert rep_d.repaired_validation_ids == ["D2"]
        # D1 handle is strictly preserved
        assert built.dimension_handle_by_cross_validation_id["D1"] == d1_handle_before

        assert review_dxf(built).passed is True


def test_scenario_7_diagonal_45_degree_dimension_repair():
    """S7: 45-degree angled dimension repair."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        built, path = _build_test_dxf(
            tmp,
            [("D_DIAG", "L_DIAG", (0, 0), (100, 100), 141.421356)],
        )
        doc = ezdxf.readfile(path)
        doc.modelspace().delete_entity(doc.entitydb.get(built.dimension_handle_by_cross_validation_id["D_DIAG"]))
        doc.saveas(path)

        rev = review_dxf(built)
        assert not rev.passed

        rep_d = repair_dimensions_strategy_d(built, rev.dimension_mismatches)
        assert rep_d.repaired_count == 1
        assert review_dxf(built, tolerance_mm=0.01).passed is True


def test_scenario_8_render_recovery():
    """S8: Stale dimension handle rebound and rendered properly."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        built, path = _build_test_dxf(tmp, [("D1", "L1", (0, 0), (75, 0), 75.0)])
        # Corrupt the handle pointer in build_result to a nonexistent handle
        built.dimension_handle_by_cross_validation_id["D1"] = "NONEXISTENT_HANDLE_999"

        rev = review_dxf(built)
        assert not rev.passed
        assert any("NONEXISTENT_HANDLE_999" in m for m in rev.dimension_mismatches)

        rep_d = repair_dimensions_strategy_d(built, rev.dimension_mismatches)
        assert rep_d.repaired_count == 1
        assert built.dimension_handle_by_cross_validation_id["D1"] != "NONEXISTENT_HANDLE_999"

        assert review_dxf(built).passed is True
