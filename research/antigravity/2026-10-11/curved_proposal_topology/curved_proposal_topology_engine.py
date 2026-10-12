"""External Visual Object Proposal Curved Topology Engine.

Research Reference Engine comparing Strategies A-D for Topic 27:
EXTERNAL_VISUAL_OBJECT_PROPOSAL_CURVED_TOPOLOGY_V1.
"""

from __future__ import annotations

import copy
import math
import re
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_fusion_proposal import (
    compile_external_visual_object_proposal as prod_compile_proposal,
)

_SCHEMA_VERSION = "external-visual-object-proposal-1.0"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_VIEW_ROLES = {"SIDE", "FRONT", "TOP", "REAR"}

_BINDING_FIELDS = {
    "source_sha256",
    "page_index",
    "source_render_sha256",
    "roi_bbox_px",
}
_PROPOSAL_FIELDS = {
    "schema_version",
    "proposal_source",
    *_BINDING_FIELDS,
    "view_role_proposal",
    "primitive_hypotheses",
    "object_groups",
    "excluded_memberships",
}
_TOPOLOGY_FIELDS = {
    "kind",
    "ordered_primitive_hypothesis_ids",
    "closure",
    "endpoint_tolerance_px",
}
_GROUP_FIELDS = {"group_id", "proposed_label", "primitive_hypothesis_ids"}
_GROUP_FIELDS_WITH_TOPOLOGY = {*_GROUP_FIELDS, "topology_hypothesis"}
_EXCLUSION_FIELDS = {"primitive_hypothesis_id", "excluded_group_id"}


def _fail(code: str) -> None:
    raise ValueError(code)


def _closed(value: object, fields: set[str], code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(code)
    if set(value) != fields or any(not isinstance(key, str) for key in value):
        _fail(code)
    return value


def _identifier(value: object, code: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _sha256(value: object, code: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _nonnegative_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(code)
    return value


def _nonnegative_float(value: object, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(code)
    try:
        val = float(value)
    except (ValueError, OverflowError):
        _fail(code)
    if not math.isfinite(val) or val < 0:
        _fail(code)
    return val


def _point(value: object, *, roi: list[int]) -> list[float]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            for item in value
        )
    ):
        _fail("PRIMITIVE_HYPOTHESIS_INVALID")
    x, y = float(value[0]), float(value[1])
    if not (roi[0] <= x <= roi[2] and roi[1] <= y <= roi[3]):
        _fail("PRIMITIVE_HYPOTHESIS_OUTSIDE_ROI")
    return [x, y]


def _binding(value: object, code: str) -> dict[str, object]:
    record = _closed(value, _BINDING_FIELDS, code)
    roi = record["roi_bbox_px"]
    if (
        not isinstance(roi, list)
        or len(roi) != 4
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in roi)
        or roi[0] >= roi[2]
        or roi[1] >= roi[3]
    ):
        _fail(code)
    return {
        "source_sha256": _sha256(record["source_sha256"], code),
        "page_index": _nonnegative_int(record["page_index"], code),
        "source_render_sha256": _sha256(record["source_render_sha256"], code),
        "roi_bbox_px": list(roi),
    }


def _get_primitive_endpoints(prim: Mapping[str, object]) -> List[Tuple[float, float]]:
    """Return all discrete endpoints of a primitive (1 for circle, 2 for line/arc)."""
    ptype = prim["type"]
    if ptype == "LINE":
        s = prim["start_px"]
        e = prim["end_px"]
        return [(float(s[0]), float(s[1])), (float(e[0]), float(e[1]))]
    elif ptype == "ARC":
        c = prim["center_px"]
        r = float(prim["radius_px"])
        t1 = math.radians(float(prim["start_angle_deg"]))
        t2 = math.radians(float(prim["end_angle_deg"]))
        # Pixel coordinates: x = cx + r*cos(t), y = cy + r*sin(t)
        p1 = (float(c[0]) + r * math.cos(t1), float(c[1]) + r * math.sin(t1))
        p2 = (float(c[0]) + r * math.cos(t2), float(c[1]) + r * math.sin(t2))
        return [p1, p2]
    elif ptype == "CIRCLE":
        # A circle has no open endpoints (it is continuous)
        return []
    return []


def _primitives_connect(
    first: Mapping[str, object],
    second: Mapping[str, object],
    *,
    tolerance: float,
) -> bool:
    """Determine whether two primitives connect within a tolerance distance."""
    # If either is a full circle, it cannot connect endpoint-to-endpoint
    if first["type"] == "CIRCLE" or second["type"] == "CIRCLE":
        return False

    first_pts = _get_primitive_endpoints(first)
    second_pts = _get_primitive_endpoints(second)
    if not first_pts or not second_pts:
        return False

    limit_sq = tolerance * tolerance
    for p1 in first_pts:
        for p2 in second_pts:
            dx = p1[0] - p2[0]
            dy = p1[1] - p2[1]
            if dx * dx + dy * dy <= limit_sq:
                return True
    return False


# ==============================================================================
# Polymorphic Primitive Hypotheses Compiler
# ==============================================================================

def compile_curved_primitives(
    value: object,
    *,
    roi: list[int],
) -> list[dict[str, object]]:
    """Compile and normalize LINE, CIRCLE, and ARC primitive hypotheses."""
    if not isinstance(value, list) or not value or len(value) > 256:
        _fail("PRIMITIVE_HYPOTHESES_INVALID")

    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for item in value:
        if not isinstance(item, Mapping):
            _fail("PRIMITIVE_HYPOTHESIS_INVALID")
        primitive_id = _identifier(item.get("id"), "PRIMITIVE_HYPOTHESIS_INVALID")
        if primitive_id in seen_ids:
            _fail("DUPLICATE_PRIMITIVE_HYPOTHESIS")
        seen_ids.add(primitive_id)

        ptype = item.get("type")
        if ptype == "LINE":
            req_keys = {"id", "type", "start_px", "end_px"}
            if set(item) != req_keys:
                _fail("PRIMITIVE_HYPOTHESIS_INVALID")
            start = _point(item["start_px"], roi=roi)
            end = _point(item["end_px"], roi=roi)
            if start == end:
                _fail("PRIMITIVE_HYPOTHESIS_INVALID")
            normalized.append({
                "id": primitive_id,
                "type": "LINE",
                "start_px": start,
                "end_px": end,
            })
        elif ptype == "CIRCLE":
            req_keys = {"id", "type", "center_px", "radius_px"}
            if set(item) != req_keys:
                _fail("PRIMITIVE_HYPOTHESIS_INVALID")
            center = _point(item["center_px"], roi=roi)
            radius = _nonnegative_float(item["radius_px"], "PRIMITIVE_HYPOTHESIS_INVALID")
            if radius <= 0.0 or not math.isfinite(radius):
                _fail("PRIMITIVE_HYPOTHESIS_INVALID")
            normalized.append({
                "id": primitive_id,
                "type": "CIRCLE",
                "center_px": center,
                "radius_px": radius,
            })
        elif ptype == "ARC":
            req_keys = {"id", "type", "center_px", "radius_px", "start_angle_deg", "end_angle_deg"}
            if set(item) != req_keys:
                _fail("PRIMITIVE_HYPOTHESIS_INVALID")
            center = _point(item["center_px"], roi=roi)
            radius = _nonnegative_float(item["radius_px"], "PRIMITIVE_HYPOTHESIS_INVALID")
            if radius <= 0.0 or not math.isfinite(radius):
                _fail("PRIMITIVE_HYPOTHESIS_INVALID")
            start_ang = _nonnegative_float(item["start_angle_deg"], "PRIMITIVE_HYPOTHESIS_INVALID")
            end_ang = _nonnegative_float(item["end_angle_deg"], "PRIMITIVE_HYPOTHESIS_INVALID")
            if start_ang == end_ang:
                _fail("PRIMITIVE_HYPOTHESIS_INVALID")
            normalized.append({
                "id": primitive_id,
                "type": "ARC",
                "center_px": center,
                "radius_px": radius,
                "start_angle_deg": start_ang,
                "end_angle_deg": end_ang,
            })
        else:
            _fail("PRIMITIVE_HYPOTHESIS_INVALID")

    return normalized


# ==============================================================================
# Curved & Hybrid Topology Compiler
# ==============================================================================

def compile_curved_topology(
    value: object,
    *,
    member_ids: list[str],
    primitives_by_id: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Compile and validate boundary chain topology across lines, circles, and arcs."""
    record = _closed(value, _TOPOLOGY_FIELDS, "GROUP_TOPOLOGY_INVALID")
    if record["kind"] != "BOUNDARY_CHAIN":
        _fail("GROUP_TOPOLOGY_INVALID")
    closure = record["closure"]
    if closure not in {"OPEN", "CLOSED", "UNRESOLVED"}:
        _fail("GROUP_TOPOLOGY_INVALID")

    tol = _nonnegative_float(record["endpoint_tolerance_px"], "GROUP_TOPOLOGY_INVALID")
    if tol > 64.0:
        _fail("GROUP_TOPOLOGY_INVALID")

    ordered = record["ordered_primitive_hypothesis_ids"]
    if not isinstance(ordered, list) or not ordered:
        _fail("GROUP_TOPOLOGY_INVALID")

    ordered_ids: list[str] = []
    seen: set[str] = set()
    for item in ordered:
        item_id = _identifier(item, "GROUP_TOPOLOGY_INVALID")
        if item_id in seen:
            _fail("GROUP_TOPOLOGY_INVALID")
        seen.add(item_id)
        ordered_ids.append(item_id)

    if set(ordered_ids) != set(member_ids):
        _fail("GROUP_TOPOLOGY_INVALID")

    # Single-primitive topology
    if len(ordered_ids) == 1:
        prim = primitives_by_id[ordered_ids[0]]
        if prim["type"] == "CIRCLE":
            # A circle is inherently a closed loop
            if closure == "OPEN":
                _fail("GROUP_TOPOLOGY_INVALID")
        else:
            # A single line or open arc CANNOT be a closed boundary chain
            if closure == "CLOSED":
                _fail("GROUP_TOPOLOGY_INVALID")
        return {
            "kind": "BOUNDARY_CHAIN",
            "ordered_primitive_hypothesis_ids": ordered_ids,
            "closure": closure,
            "endpoint_tolerance_px": tol,
        }

    # Multi-primitive topology: consecutive connectivity
    for first_id, second_id in zip(ordered_ids, ordered_ids[1:]):
        first_prim = primitives_by_id[first_id]
        second_prim = primitives_by_id[second_id]
        if not _primitives_connect(first_prim, second_prim, tolerance=tol):
            _fail("GROUP_TOPOLOGY_DISCONNECTED")

    # If CLOSED, wrap-around connectivity (last connects to first)
    if closure == "CLOSED":
        last_prim = primitives_by_id[ordered_ids[-1]]
        first_prim = primitives_by_id[ordered_ids[0]]
        if not _primitives_connect(last_prim, first_prim, tolerance=tol):
            _fail("GROUP_TOPOLOGY_DISCONNECTED")

    return {
        "kind": "BOUNDARY_CHAIN",
        "ordered_primitive_hypothesis_ids": ordered_ids,
        "closure": closure,
        "endpoint_tolerance_px": tol,
    }


def compile_curved_groups(
    value: object,
    *,
    primitives_by_id: Mapping[str, Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[str, set[str]]]:
    if not isinstance(value, list) or not value or len(value) > 128:
        _fail("GROUP_MEMBERSHIP_INVALID")

    primitive_ids = set(primitives_by_id)
    normalized: list[dict[str, object]] = []
    memberships: dict[str, set[str]] = {}

    for raw in value:
        if not isinstance(raw, Mapping):
            _fail("GROUP_MEMBERSHIP_INVALID")
        raw_fields = set(raw)
        if raw_fields != _GROUP_FIELDS and raw_fields != _GROUP_FIELDS_WITH_TOPOLOGY:
            _fail("GROUP_MEMBERSHIP_INVALID")
        record = raw
        group_id = _identifier(record["group_id"], "GROUP_MEMBERSHIP_INVALID")
        if group_id in memberships:
            _fail("GROUP_MEMBERSHIP_INVALID")
        label = _identifier(record["proposed_label"], "GROUP_MEMBERSHIP_INVALID")
        members = record["primitive_hypothesis_ids"]
        if not isinstance(members, list) or not members or len(members) > 256:
            _fail("GROUP_MEMBERSHIP_INVALID")
        member_ids: list[str] = []
        seen_members: set[str] = set()
        for member in members:
            member_id = _identifier(member, "GROUP_MEMBERSHIP_INVALID")
            if member_id not in primitive_ids or member_id in seen_members:
                _fail("GROUP_MEMBERSHIP_INVALID")
            seen_members.add(member_id)
            member_ids.append(member_id)
        memberships[group_id] = set(member_ids)
        normalized_group: dict[str, object] = {
            "group_id": group_id,
            "proposed_label": label,
            "primitive_hypothesis_ids": member_ids,
        }
        if "topology_hypothesis" in record:
            normalized_group["topology_hypothesis"] = compile_curved_topology(
                record["topology_hypothesis"],
                member_ids=member_ids,
                primitives_by_id=primitives_by_id,
            )
        normalized.append(normalized_group)

    return normalized, memberships


# ==============================================================================
# Strategy Comparators
# ==============================================================================

class StrategyA_ProductionBaseline:
    """Current Production Baseline in cad_agent/source_fusion_proposal.py."""

    @staticmethod
    def compile_proposal(
        proposal: Dict[str, Any],
        expected_binding: Dict[str, Any],
    ) -> Dict[str, Any]:
        return prod_compile_proposal(proposal=proposal, expected_binding=expected_binding)


class StrategyB_NaiveTypeExpansion:
    """Allows CIRCLE/ARC primitive definitions, but fails on hybrid boundary connectivity."""

    @staticmethod
    def compile_proposal(
        proposal: Dict[str, Any],
        expected_binding: Dict[str, Any],
    ) -> Dict[str, Any]:
        record = _closed(proposal, _PROPOSAL_FIELDS, "PROPOSAL_FIELDS_INVALID")
        if record["schema_version"] != _SCHEMA_VERSION:
            _fail("PROPOSAL_SCHEMA_INVALID")
        if record["proposal_source"] != "external_ai":
            _fail("PROPOSAL_SOURCE_INVALID")
        trusted_binding = _binding(expected_binding, "EXPECTED_BINDING_INVALID")
        prims = compile_curved_primitives(record["primitive_hypotheses"], roi=trusted_binding["roi_bbox_px"])
        prims_by_id = {str(item["id"]): item for item in prims}
        
        # Naive: attempts line-only connectivity using start_px / end_px
        for g in record.get("object_groups", []):
            if "topology_hypothesis" in g:
                top = g["topology_hypothesis"]
                ordered = top.get("ordered_primitive_hypothesis_ids", [])
                for f_id, s_id in zip(ordered, ordered[1:]):
                    f = prims_by_id[f_id]
                    s = prims_by_id[s_id]
                    if f["type"] != "LINE" or s["type"] != "LINE":
                        # Crashes on non-line primitives
                        _fail("GROUP_TOPOLOGY_INVALID")
        return {"status": "COMPILED_STRATEGY_B"}


class StrategyC_DisjointPartitioner:
    """Allows lines in chains and circles in non-topological groups; rejects hybrid line-arc chains."""

    @staticmethod
    def compile_proposal(
        proposal: Dict[str, Any],
        expected_binding: Dict[str, Any],
    ) -> Dict[str, Any]:
        record = _closed(proposal, _PROPOSAL_FIELDS, "PROPOSAL_FIELDS_INVALID")
        if record["schema_version"] != _SCHEMA_VERSION:
            _fail("PROPOSAL_SCHEMA_INVALID")
        trusted_binding = _binding(expected_binding, "EXPECTED_BINDING_INVALID")
        prims = compile_curved_primitives(record["primitive_hypotheses"], roi=trusted_binding["roi_bbox_px"])
        prims_by_id = {str(item["id"]): item for item in prims}

        for g in record.get("object_groups", []):
            if "topology_hypothesis" in g:
                top = g["topology_hypothesis"]
                ordered = top.get("ordered_primitive_hypothesis_ids", [])
                # Reject any hybrid chain containing arcs or circles
                types = {prims_by_id[pid]["type"] for pid in ordered}
                if "ARC" in types or "CIRCLE" in types:
                    _fail("GROUP_TOPOLOGY_INVALID")
        return {"status": "COMPILED_STRATEGY_C"}


class StrategyD_UnifiedCurvedTopologyOracle:
    """Selected Oracle: Full curved primitive hypotheses and hybrid contour topology compiler."""

    @staticmethod
    def compile_proposal(
        proposal: Dict[str, Any],
        expected_binding: Dict[str, Any],
    ) -> Dict[str, Any]:
        record = _closed(proposal, _PROPOSAL_FIELDS, "PROPOSAL_FIELDS_INVALID")
        if record["schema_version"] != _SCHEMA_VERSION:
            _fail("PROPOSAL_SCHEMA_INVALID")
        if record["proposal_source"] != "external_ai":
            _fail("PROPOSAL_SOURCE_INVALID")

        supplied_binding = _binding(
            {field: record[field] for field in _BINDING_FIELDS},
            "PROPOSAL_BINDING_INVALID",
        )
        trusted_binding = _binding(expected_binding, "EXPECTED_BINDING_INVALID")
        if supplied_binding != trusted_binding:
            _fail("BINDING_MISMATCH")

        view_role = record["view_role_proposal"]
        if not isinstance(view_role, str) or view_role not in _VIEW_ROLES:
            _fail("VIEW_ROLE_INVALID")

        primitives = compile_curved_primitives(
            record["primitive_hypotheses"],
            roi=trusted_binding["roi_bbox_px"],
        )
        primitives_by_id = {str(item["id"]): item for item in primitives}
        groups, memberships = compile_curved_groups(
            record["object_groups"],
            primitives_by_id=primitives_by_id,
        )

        # Exclusions validation
        exclusions: list[dict[str, str]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for raw in record["excluded_memberships"]:
            exc = _closed(raw, _EXCLUSION_FIELDS, "EXCLUSION_INVALID")
            pid = _identifier(exc["primitive_hypothesis_id"], "EXCLUSION_INVALID")
            gid = _identifier(exc["excluded_group_id"], "EXCLUSION_INVALID")
            if pid not in primitives_by_id or gid not in memberships:
                _fail("EXCLUSION_INVALID")
            pair = (pid, gid)
            if pair in seen_pairs:
                _fail("EXCLUSION_INVALID")
            seen_pairs.add(pair)
            if pid in memberships[gid]:
                _fail("EXCLUSION_CONTRADICTION")
            exclusions.append({
                "primitive_hypothesis_id": pid,
                "excluded_group_id": gid,
            })

        return {
            "kind": "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST",
            "status": "PROPOSAL_ONLY",
            "exact_source_binding": copy.deepcopy(trusted_binding),
            "proposal_source": "external_ai",
            "view_role_proposal": view_role,
            "primitive_hypotheses": copy.deepcopy(primitives),
            "object_groups": copy.deepcopy(groups),
            "excluded_memberships": exclusions,
        }
