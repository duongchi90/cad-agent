"""Source Fusion Native Curved Delta Composition Reference Engine.

Research Reference Engine comparing Strategies A-D for Topic 29:
SOURCE_FUSION_NATIVE_CURVED_DELTA_COMPOSITION_V1.
"""

from __future__ import annotations

import copy
import math
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_fusion_proposal import (
    _apply_alignment_to_target_line,
    _finite_point,
    _line_pair_residual,
    _native_lines,
    _nonnegative_tolerance,
    _proposal_without_match,
    _same_residual,
    _target_to_base_alignment,
    _TARGET_BASE_SCALE_TOLERANCE,
    compose_verified_native_line_delta as prod_compose_line_delta,
)
from primitive_ir_lib.geometry_alignment import AnchorPair
from primitive_ir_lib.models import (
    ArcGeometry,
    Calibration,
    CircleGeometry,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _fail(code: str) -> None:
    raise ValueError(code)


def _identifier(value: object, code: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        _fail(code)
    return value


# ==============================================================================
# Curved Residual and Alignment Helpers
# ==============================================================================

def apply_alignment_to_point(pt: Sequence[float], matrix: Sequence[Sequence[float]]) -> List[float]:
    """Transform a 2D point by a 2x3 affine matrix."""
    x, y = float(pt[0]), float(pt[1])
    tx = matrix[0][0] * x + matrix[0][1] * y + matrix[0][2]
    ty = matrix[1][0] * x + matrix[1][1] * y + matrix[1][2]
    return [round(tx, 6), round(ty, 6)]


def get_matrix_rotation_deg(matrix: Sequence[Sequence[float]]) -> float:
    """Extract rotation angle in degrees from a 2x3 similarity matrix."""
    return math.degrees(math.atan2(matrix[1][0], matrix[0][0])) % 360.0


def apply_alignment_to_target_circle(
    circle: Mapping[str, Any], matrix: Sequence[Sequence[float]]
) -> Dict[str, Any]:
    c = apply_alignment_to_point(circle["center"], matrix)
    return {
        "primitive_id": circle["primitive_id"],
        "type": "circle",
        "center": c,
        "radius": float(circle["radius"]),
    }


def apply_alignment_to_target_arc(
    arc: Mapping[str, Any], matrix: Sequence[Sequence[float]]
) -> Dict[str, Any]:
    c = apply_alignment_to_point(arc["center"], matrix)
    rot_deg = get_matrix_rotation_deg(matrix)
    s_deg = (float(arc["start_angle_deg"]) + rot_deg) % 360.0
    e_deg = (float(arc["end_angle_deg"]) + rot_deg) % 360.0
    return {
        "primitive_id": arc["primitive_id"],
        "type": "arc",
        "center": c,
        "radius": float(arc["radius"]),
        "start_angle_deg": round(s_deg, 3),
        "end_angle_deg": round(e_deg, 3),
    }


def compute_circle_pair_residual(base: Mapping[str, Any], target: Mapping[str, Any]) -> float:
    """Exact spatial residual between base circle and target circle."""
    c_base = base["center"]
    c_target = target["center"]
    center_dist = math.hypot(c_base[0] - c_target[0], c_base[1] - c_target[1])
    radius_diff = abs(float(base["radius"]) - float(target["radius"]))
    return max(center_dist, radius_diff)


def compute_arc_pair_residual(base: Mapping[str, Any], target: Mapping[str, Any]) -> float:
    """Exact spatial residual between base arc and target arc including endpoints."""
    c_base = base["center"]
    c_target = target["center"]
    center_dist = math.hypot(c_base[0] - c_target[0], c_base[1] - c_target[1])
    radius_diff = abs(float(base["radius"]) - float(target["radius"]))

    r_b = float(base["radius"])
    r_t = float(target["radius"])

    # Base endpoints
    b_s_rad = math.radians(float(base["start_angle_deg"]))
    b_e_rad = math.radians(float(base["end_angle_deg"]))
    b_p1 = (c_base[0] + r_b * math.cos(b_s_rad), c_base[1] + r_b * math.sin(b_s_rad))
    b_p2 = (c_base[0] + r_b * math.cos(b_e_rad), c_base[1] + r_b * math.sin(b_e_rad))

    # Target endpoints
    t_s_rad = math.radians(float(target["start_angle_deg"]))
    t_e_rad = math.radians(float(target["end_angle_deg"]))
    t_p1 = (c_target[0] + r_t * math.cos(t_s_rad), c_target[1] + r_t * math.sin(t_s_rad))
    t_p2 = (c_target[0] + r_t * math.cos(t_e_rad), c_target[1] + r_t * math.sin(t_e_rad))

    ep_dist = max(
        math.hypot(b_p1[0] - t_p1[0], b_p1[1] - t_p1[1]),
        math.hypot(b_p2[0] - t_p2[0], b_p2[1] - t_p2[1]),
    )
    return max(center_dist, radius_diff, ep_dist)


# ==============================================================================
# Strategies A - D
# ==============================================================================

class StrategyA_ProductionBaseline:
    """Production Baseline in cad_agent/source_fusion_proposal.py (line-only)."""

    @staticmethod
    def compose_delta(**kwargs: Any) -> Dict[str, Any]:
        return prod_compose_line_delta(**kwargs)


class StrategyB_CenterPointOnlyMatching:
    """Matches circles and arcs based purely on center distance, ignoring radius."""

    @staticmethod
    def compose_delta(
        *,
        base_observations: Sequence[Mapping[str, Any]],
        target_primitives: Sequence[Mapping[str, Any]],
        max_residual: float,
        keep_tolerance: float,
    ) -> Dict[str, Any]:
        matches = []
        used_base = set()
        for target in target_primitives:
            c_target = target["center"]
            candidates = []
            for base in base_observations:
                c_base = base["center"]
                dist = math.hypot(c_base[0] - c_target[0], c_base[1] - c_target[1])
                candidates.append((dist, base))
            candidates.sort(key=lambda x: x[0])
            if not candidates or candidates[0][0] > max_residual:
                continue
            best_dist, best_base = candidates[0]
            base_id = best_base["observation_id"]
            if base_id in used_base:
                continue
            used_base.add(base_id)
            status = "KEEP" if best_dist <= keep_tolerance else "MUTATE"
            matches.append({
                "base_id": base_id,
                "target_id": target["primitive_id"],
                "residual": round(best_dist, 3),
                "status": status,
            })
        return {"status": "SUCCESS", "matches": matches}


class StrategyC_UncoupledTypeMatchers:
    """Separate matchers for lines, circles, and arcs without unified validation."""

    @staticmethod
    def compose_delta(
        *,
        base_observations: Sequence[Mapping[str, Any]],
        target_primitives: Sequence[Mapping[str, Any]],
        max_residual: float,
        keep_tolerance: float,
    ) -> Dict[str, Any]:
        matches = []
        used_base = set()
        for target in target_primitives:
            ttype = target.get("type", "circle")
            candidates = []
            for base in base_observations:
                if base.get("type", "circle") != ttype:
                    continue
                if ttype == "circle":
                    res = compute_circle_pair_residual(base, target)
                elif ttype == "arc":
                    res = compute_arc_pair_residual(base, target)
                else:
                    res = 0.0
                candidates.append((res, base))
            if not candidates:
                continue
            candidates.sort(key=lambda x: x[0])
            best_res, best_base = candidates[0]
            if best_res > max_residual:
                continue
            base_id = best_base["observation_id"]
            if base_id in used_base:
                continue
            used_base.add(base_id)
            status = "KEEP" if best_res <= keep_tolerance else "MUTATE"
            matches.append({
                "base_id": base_id,
                "target_id": target["primitive_id"],
                "residual": round(best_res, 3),
                "status": status,
            })
        return {"status": "SUCCESS", "matches": matches}


class StrategyD_UnifiedGeometricDeltaComposerOracle:
    """Selected Oracle: Unified polymorphic correspondence and delta composition for Line, Circle, Arc."""

    @staticmethod
    def compose_delta(
        *,
        base_observations: Sequence[Mapping[str, Any]],
        verified_target_document: PrimitiveIRDocument,
        alignment_anchors: Sequence[Any],
        max_correspondence_residual: float,
        keep_tolerance: float,
        max_alignment_residual: float = 2.0,
    ) -> Dict[str, Any]:
        if not isinstance(verified_target_document, PrimitiveIRDocument):
            _fail("VERIFIED_TARGET_DOCUMENT_INVALID")
        if not verified_target_document.primitives:
            _fail("VERIFIED_TARGET_DOCUMENT_EMPTY")

        max_residual = _nonnegative_tolerance(
            max_correspondence_residual, "GEOMETRY_TOLERANCE_INVALID"
        )
        keep_limit = _nonnegative_tolerance(keep_tolerance, "GEOMETRY_TOLERANCE_INVALID")
        if keep_limit > max_residual:
            _fail("GEOMETRY_TOLERANCE_INVALID")

        # Estimate target-to-base alignment
        target_unit = verified_target_document.calibration.unit
        alignment_record, matrix = _target_to_base_alignment(
            alignment_anchors,
            max_residual=max_alignment_residual,
            coordinate_unit=target_unit,
        )

        # Normalize and align target primitives
        aligned_targets: List[Dict[str, Any]] = []
        for prim in verified_target_document.primitives:
            pid = prim.id
            ptype = prim.type
            if ptype == "line":
                raw_line = {
                    "primitive_id": pid,
                    "start": [prim.geometry.start.x, prim.geometry.start.y],
                    "end": [prim.geometry.end.x, prim.geometry.end.y],
                }
                aligned = _apply_alignment_to_target_line(raw_line, matrix)
                aligned_targets.append({
                    "primitive_id": pid,
                    "type": "line",
                    "start": aligned["start"],
                    "end": aligned["end"],
                })
            elif ptype == "circle":
                raw_circle = {
                    "primitive_id": pid,
                    "center": [prim.geometry.center.x, prim.geometry.center.y],
                    "radius": prim.geometry.radius,
                }
                aligned_targets.append(apply_alignment_to_target_circle(raw_circle, matrix))
            elif ptype == "arc":
                raw_arc = {
                    "primitive_id": pid,
                    "center": [prim.geometry.center.x, prim.geometry.center.y],
                    "radius": prim.geometry.radius,
                    "start_angle_deg": prim.geometry.start_angle_deg,
                    "end_angle_deg": prim.geometry.end_angle_deg,
                }
                aligned_targets.append(apply_alignment_to_target_arc(raw_arc, matrix))

        geometry_tolerance = {
            "unit": target_unit,
            "max_correspondence_residual": max_residual,
            "keep_tolerance": keep_limit,
        }

        # Pair matching
        matches: List[Tuple[Dict[str, Any], Dict[str, Any], float]] = []
        used_base_ids = set()
        matched_target_ids = set()

        base_by_type: Dict[str, List[Mapping[str, Any]]] = {}
        for b in base_observations:
            base_by_type.setdefault(b.get("type", "line"), []).append(b)

        for target in aligned_targets:
            ttype = target["type"]
            candidate_costs: List[Tuple[float, Mapping[str, Any]]] = []
            matching_bases = base_by_type.get(ttype, [])

            for base in matching_bases:
                if ttype == "line":
                    res = _line_pair_residual(base, target)
                elif ttype == "circle":
                    res = compute_circle_pair_residual(base, target)
                elif ttype == "arc":
                    res = compute_arc_pair_residual(base, target)
                else:
                    continue

                candidate_costs.append((res, base))

            if not candidate_costs:
                continue

            candidate_costs.sort(key=lambda item: item[0])
            best_residual, best_base = candidate_costs[0]

            if best_residual > max_residual:
                # Target primitive is unmatched within tolerance (candidate for ADD)
                continue

            # Ambiguity check
            if len(candidate_costs) > 1 and _same_residual(best_residual, candidate_costs[1][0]):
                return _proposal_without_match("AMBIGUOUS", geometry_tolerance, alignment_record)

            base_id = str(best_base["observation_id"])
            if base_id in used_base_ids:
                return _proposal_without_match("AMBIGUOUS", geometry_tolerance, alignment_record)

            used_base_ids.add(base_id)
            matched_target_ids.add(target["primitive_id"])
            matches.append((best_base, target, best_residual))

        # Build correspondence and deltas
        correspondence: List[Dict[str, Any]] = []
        deltas: List[Dict[str, Any]] = []

        for base, target, residual in sorted(matches, key=lambda pair: str(pair[0]["observation_id"])):
            btype = base.get("type", "line")
            changed = residual > keep_limit
            action = "MUTATE" if changed else "KEEP"

            corr_item = {
                "base_observation_id": base["observation_id"],
                "target_primitive_id": target["primitive_id"],
                "type": btype,
                "residual": round(residual, 4),
                "action": action,
            }
            correspondence.append(corr_item)

            if changed:
                delta_item: Dict[str, Any] = {
                    "base_observation_id": base["observation_id"],
                    "target_primitive_id": target["primitive_id"],
                    "type": btype,
                    "action": "MUTATE",
                    "residual": round(residual, 4),
                }
                if btype == "line":
                    delta_item["before"] = {"start": base["start"], "end": base["end"]}
                    delta_item["after"] = {"start": target["start"], "end": target["end"]}
                elif btype == "circle":
                    delta_item["before"] = {"center": base["center"], "radius": base["radius"]}
                    delta_item["after"] = {"center": target["center"], "radius": target["radius"]}
                elif btype == "arc":
                    delta_item["before"] = {
                        "center": base["center"],
                        "radius": base["radius"],
                        "start_angle_deg": base["start_angle_deg"],
                        "end_angle_deg": base["end_angle_deg"],
                    }
                    delta_item["after"] = {
                        "center": target["center"],
                        "radius": target["radius"],
                        "start_angle_deg": target["start_angle_deg"],
                        "end_angle_deg": target["end_angle_deg"],
                    }
                deltas.append(delta_item)

        # Record ADD proposals for unmatched targets
        for target in aligned_targets:
            if target["primitive_id"] not in matched_target_ids:
                add_item: Dict[str, Any] = {
                    "target_primitive_id": target["primitive_id"],
                    "type": target["type"],
                    "action": "ADD",
                }
                if target["type"] == "line":
                    add_item["geometry"] = {"start": target["start"], "end": target["end"]}
                elif target["type"] == "circle":
                    add_item["geometry"] = {"center": target["center"], "radius": target["radius"]}
                elif target["type"] == "arc":
                    add_item["geometry"] = {
                        "center": target["center"],
                        "radius": target["radius"],
                        "start_angle_deg": target["start_angle_deg"],
                        "end_angle_deg": target["end_angle_deg"],
                    }
                deltas.append(add_item)

        # Unmatched base observations (candidate REMOVE)
        unmatched_base = [
            base["observation_id"]
            for base in base_observations
            if str(base["observation_id"]) not in used_base_ids
        ]

        result = {
            "status": "DELTA_COMPOSED" if deltas else "NO_DELTA_IDENTICAL",
            "geometry_tolerance": geometry_tolerance,
            "alignment": alignment_record,
            "correspondence": correspondence,
            "deltas": deltas,
            "unmatched_base_observation_ids": sorted(unmatched_base),
        }
        result["result_sha256"] = canonical_json_sha256(result)
        return result
