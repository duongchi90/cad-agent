"""Compile-only boundary for external visual/object proposals.

This module is intentionally pre-fusion: proposal data is not accepted semantic
or PrimitiveIR evidence and this seam has no CAD or source mutation side effect.
"""

from __future__ import annotations

import copy as _copy
import re as _re
from collections.abc import Mapping as _Mapping

from cad_agent.drawing_contracts import canonical_json_sha256 as _canonical_json_sha256


__all__ = ["compile_external_visual_object_proposal"]


_SCHEMA_VERSION = "external-visual-object-proposal-1.0"
_SHA256_RE = _re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = _re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
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
_PRIMITIVE_FIELDS = {"id", "type", "start_px", "end_px"}
_GROUP_FIELDS = {"group_id", "proposed_label", "primitive_hypothesis_ids"}
_GROUP_FIELDS_WITH_TOPOLOGY = {*_GROUP_FIELDS, "topology_hypothesis"}
_TOPOLOGY_FIELDS = {
    "kind",
    "ordered_primitive_hypothesis_ids",
    "closure",
    "endpoint_tolerance_px",
}
_EXCLUSION_FIELDS = {"primitive_hypothesis_id", "excluded_group_id"}


def _fail(code: str) -> None:
    raise ValueError(code)


def _closed(value: object, fields: set[str], code: str) -> _Mapping[str, object]:
    if not isinstance(value, _Mapping):
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


def _roi(value: object, code: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 4:
        _fail(code)
    normalized = [_nonnegative_int(item, code) for item in value]
    x0, y0, x1, y1 = normalized
    if x0 >= x1 or y0 >= y1:
        _fail(code)
    return normalized


def _binding(value: object, code: str) -> dict[str, object]:
    record = _closed(value, _BINDING_FIELDS, code)
    return {
        "source_sha256": _sha256(record["source_sha256"], code),
        "page_index": _nonnegative_int(record["page_index"], code),
        "source_render_sha256": _sha256(record["source_render_sha256"], code),
        "roi_bbox_px": _roi(record["roi_bbox_px"], code),
    }


def _point(value: object, *, roi: list[int]) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        _fail("PRIMITIVE_HYPOTHESIS_INVALID")
    point = [_nonnegative_int(item, "PRIMITIVE_HYPOTHESIS_INVALID") for item in value]
    x, y = point
    x0, y0, x1, y1 = roi
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        _fail("PRIMITIVE_OUTSIDE_ROI")
    return point


def _primitives(value: object, *, roi: list[int]) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value or len(value) > 256:
        _fail("PRIMITIVE_HYPOTHESIS_INVALID")

    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for raw in value:
        record = _closed(raw, _PRIMITIVE_FIELDS, "PRIMITIVE_HYPOTHESIS_INVALID")
        primitive_id = _identifier(record["id"], "PRIMITIVE_HYPOTHESIS_INVALID")
        if primitive_id in seen_ids:
            _fail("DUPLICATE_PRIMITIVE_HYPOTHESIS")
        seen_ids.add(primitive_id)
        if record["type"] != "LINE":
            _fail("PRIMITIVE_HYPOTHESIS_INVALID")
        start = _point(record["start_px"], roi=roi)
        end = _point(record["end_px"], roi=roi)
        if start == end:
            _fail("PRIMITIVE_HYPOTHESIS_INVALID")
        normalized.append(
            {
                "id": primitive_id,
                "type": "LINE",
                "start_px": start,
                "end_px": end,
            }
        )
    return normalized


def _topology(value: object, *, member_ids: list[str]) -> dict[str, object]:
    record = _closed(value, _TOPOLOGY_FIELDS, "GROUP_TOPOLOGY_INVALID")
    if record["kind"] != "BOUNDARY_CHAIN":
        _fail("GROUP_TOPOLOGY_INVALID")
    closure = record["closure"]
    if closure not in {"OPEN", "CLOSED", "UNRESOLVED"}:
        _fail("GROUP_TOPOLOGY_INVALID")
    tolerance = _nonnegative_int(record["endpoint_tolerance_px"], "GROUP_TOPOLOGY_INVALID")
    if tolerance > 64:
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
    return {
        "kind": "BOUNDARY_CHAIN",
        "ordered_primitive_hypothesis_ids": ordered_ids,
        "closure": closure,
        "endpoint_tolerance_px": tolerance,
    }


def _groups(
    value: object,
    *,
    primitive_ids: set[str],
) -> tuple[list[dict[str, object]], dict[str, set[str]]]:
    if not isinstance(value, list) or not value or len(value) > 128:
        _fail("GROUP_MEMBERSHIP_INVALID")

    normalized: list[dict[str, object]] = []
    memberships: dict[str, set[str]] = {}
    for raw in value:
        if not isinstance(raw, _Mapping):
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
            normalized_group["topology_hypothesis"] = _topology(
                record["topology_hypothesis"],
                member_ids=member_ids,
            )
        normalized.append(normalized_group)
    return normalized, memberships


def _exclusions(
    value: object,
    *,
    primitive_ids: set[str],
    memberships: dict[str, set[str]],
) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > 256:
        _fail("EXCLUSION_INVALID")

    normalized: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for raw in value:
        record = _closed(raw, _EXCLUSION_FIELDS, "EXCLUSION_INVALID")
        primitive_id = _identifier(record["primitive_hypothesis_id"], "EXCLUSION_INVALID")
        group_id = _identifier(record["excluded_group_id"], "EXCLUSION_INVALID")
        if primitive_id not in primitive_ids or group_id not in memberships:
            _fail("EXCLUSION_INVALID")
        pair = (primitive_id, group_id)
        if pair in seen_pairs:
            _fail("EXCLUSION_INVALID")
        seen_pairs.add(pair)
        if primitive_id in memberships[group_id]:
            _fail("EXCLUSION_CONTRADICTION")
        normalized.append(
            {
                "primitive_hypothesis_id": primitive_id,
                "excluded_group_id": group_id,
            }
        )
    return normalized


def compile_external_visual_object_proposal(
    *,
    proposal: object,
    expected_binding: object,
) -> dict[str, object]:
    """Compile an external-AI visual proposal into a verification-only request.

    The result deliberately carries no semantic authority and materializes no
    PrimitiveIR or CAD mutation. Source support and grouping remain checks that
    a downstream deterministic verifier must prove.
    """

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

    primitives = _primitives(record["primitive_hypotheses"], roi=trusted_binding["roi_bbox_px"])
    primitive_ids = {str(item["id"]) for item in primitives}
    groups, memberships = _groups(record["object_groups"], primitive_ids=primitive_ids)
    exclusions = _exclusions(
        record["excluded_memberships"],
        primitive_ids=primitive_ids,
        memberships=memberships,
    )

    request: dict[str, object] = {
        "kind": "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST",
        "status": "PROPOSAL_ONLY",
        "exact_source_binding": _copy.deepcopy(trusted_binding),
        "proposal_source": "external_ai",
        "view_role_proposal": view_role,
        "primitive_hypotheses": _copy.deepcopy(primitives),
        "object_groups": _copy.deepcopy(groups),
        "excluded_memberships": _copy.deepcopy(exclusions),
        "checks_required": [
            "EXACT_SOURCE_BINDING",
            "PER_PRIMITIVE_SOURCE_SUPPORT",
            "GROUP_TOPOLOGY",
            "EXCLUSION_CONSISTENCY",
        ],
        "semantic_label_authority": "NONE",
        "primitive_ir_materialized": False,
        "semantic_observation_materialized": False,
        "cad_mutation": False,
    }
    request["verification_request_sha256"] = _canonical_json_sha256(request)
    return request
