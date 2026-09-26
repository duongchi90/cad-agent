"""Proposal-only external visual compilation and native-line composition.

Geometry proposals remain non-semantic and this seam has no CAD or source
mutation side effect.
"""

from __future__ import annotations

import copy as _copy
import math as _math
import re as _re
from collections.abc import Mapping as _Mapping

from cad_agent.drawing_contracts import canonical_json_sha256 as _canonical_json_sha256
from primitive_ir_lib.models import (
    PrimitiveIRDocument as _PrimitiveIRDocument,
    SourceDocument as _SourceDocument,
)


__all__ = [
    "compile_external_visual_object_proposal",
    "compose_verified_native_line_delta",
]


_SCHEMA_VERSION = "external-visual-object-proposal-1.0"
_SHA256_RE = _re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = _re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_VIEW_ROLES = {"SIDE", "FRONT", "TOP", "REAR"}
# Calibration already puts target geometry in native units; alignment must not
# rescale physical dimensions. Allow only floating-point fit noise around 1:1.
_TARGET_BASE_SCALE_TOLERANCE = 1e-6

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
_CALIBRATION_FIELDS = {
    "unit",
    "pixel_to_unit_scale",
    "origin_px",
    "method",
    "reference_note",
    "status",
    "source_sha256",
}
_MAX_NATIVE_LINE_OBSERVATIONS = 512
_MAX_VERIFIED_TARGET_LINES = 256


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


def _normalize_calibration_binding(
    value: object,
    *,
    source_sha256: str,
    code: str = "EXPECTED_CALIBRATION_BINDING_INVALID",
) -> dict[str, object]:
    if not isinstance(value, _Mapping):
        _fail(code)
    required_fields = _CALIBRATION_FIELDS - {"reference_note"}
    if set(value) != required_fields and set(value) != _CALIBRATION_FIELDS:
        _fail(code)
    record = value
    unit = record["unit"]
    if unit not in {"mm", "cm", "m"}:
        _fail(code)
    scale = record["pixel_to_unit_scale"]
    if (
        isinstance(scale, bool)
        or not isinstance(scale, (int, float))
        or not _math.isfinite(float(scale))
        or scale <= 0
    ):
        _fail(code)
    origin = record["origin_px"]
    if (
        not isinstance(origin, (list, tuple))
        or len(origin) != 2
        or any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not _math.isfinite(float(item))
            for item in origin
        )
    ):
        _fail(code)
    method = record["method"]
    if method not in {"known_dimension_reference", "title_block_scale", "manual_override"}:
        _fail(code)
    reference_note = record.get("reference_note")
    if reference_note is not None and not isinstance(reference_note, str):
        _fail(code)
    if record["status"] != "verified":
        _fail("EXTERNAL_GEOMETRY_CALIBRATION_UNVERIFIED")
    if record["source_sha256"] != source_sha256:
        _fail("EXTERNAL_GEOMETRY_CALIBRATION_SOURCE_MISMATCH")
    return {
        "unit": unit,
        "pixel_to_unit_scale": float(scale),
        "origin_px": [float(origin[0]), float(origin[1])],
        "method": method,
        "reference_note": reference_note,
        "status": "verified",
        "source_sha256": source_sha256,
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


def _lines_connect(
    first: _Mapping[str, object],
    second: _Mapping[str, object],
    *,
    tolerance: int,
) -> bool:
    first_points = (first["start_px"], first["end_px"])
    second_points = (second["start_px"], second["end_px"])
    limit_squared = tolerance * tolerance
    for first_point in first_points:
        for second_point in second_points:
            if not isinstance(first_point, list) or not isinstance(second_point, list):
                _fail("GROUP_TOPOLOGY_INVALID")
            dx = first_point[0] - second_point[0]
            dy = first_point[1] - second_point[1]
            if dx * dx + dy * dy <= limit_squared:
                return True
    return False


def _topology(
    value: object,
    *,
    member_ids: list[str],
    primitives_by_id: _Mapping[str, _Mapping[str, object]],
) -> dict[str, object]:
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

    for first_id, second_id in zip(ordered_ids, ordered_ids[1:]):
        if not _lines_connect(
            primitives_by_id[first_id],
            primitives_by_id[second_id],
            tolerance=tolerance,
        ):
            _fail("GROUP_TOPOLOGY_DISCONNECTED")
    if closure == "CLOSED" and len(ordered_ids) > 1:
        if not _lines_connect(
            primitives_by_id[ordered_ids[-1]],
            primitives_by_id[ordered_ids[0]],
            tolerance=tolerance,
        ):
            _fail("GROUP_TOPOLOGY_DISCONNECTED")

    return {
        "kind": "BOUNDARY_CHAIN",
        "ordered_primitive_hypothesis_ids": ordered_ids,
        "closure": closure,
        "endpoint_tolerance_px": tolerance,
    }


def _groups(
    value: object,
    *,
    primitives_by_id: _Mapping[str, _Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[str, set[str]]]:
    if not isinstance(value, list) or not value or len(value) > 128:
        _fail("GROUP_MEMBERSHIP_INVALID")

    primitive_ids = set(primitives_by_id)
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
                primitives_by_id=primitives_by_id,
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
    expected_calibration_binding: object | None = None,
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
    primitives_by_id = {str(item["id"]): item for item in primitives}
    primitive_ids = set(primitives_by_id)
    groups, memberships = _groups(record["object_groups"], primitives_by_id=primitives_by_id)
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
    if expected_calibration_binding is not None:
        request["exact_calibration_binding"] = _normalize_calibration_binding(
            expected_calibration_binding,
            source_sha256=trusted_binding["source_sha256"],
        )
    request["verification_request_sha256"] = _canonical_json_sha256(request)
    return request


def _finite_point(value: object, code: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        _fail(code)
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        _fail(code)
    try:
        point = [float(value[0]), float(value[1])]
    except OverflowError:
        _fail(code)
    if not all(_math.isfinite(item) for item in point):
        _fail(code)
    return point


def _native_lines(value: object) -> list[dict[str, object]]:
    if (
        not isinstance(value, list)
        or not value
        or len(value) > _MAX_NATIVE_LINE_OBSERVATIONS
    ):
        _fail("NATIVE_LINE_OBSERVATIONS_INVALID")

    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for item in value:
        record = _closed(
            item,
            {"observation_id", "start", "end"},
            "NATIVE_LINE_OBSERVATION_INVALID",
        )
        observation_id = _identifier(
            record["observation_id"], "NATIVE_LINE_OBSERVATION_INVALID"
        )
        if observation_id in seen_ids:
            _fail("DUPLICATE_NATIVE_LINE_OBSERVATION")
        seen_ids.add(observation_id)
        start = _finite_point(record["start"], "NATIVE_LINE_OBSERVATION_INVALID")
        end = _finite_point(record["end"], "NATIVE_LINE_OBSERVATION_INVALID")
        if start == end:
            _fail("NATIVE_LINE_OBSERVATION_INVALID")
        normalized.append(
            {"observation_id": observation_id, "start": start, "end": end}
        )
    return normalized


def _stable_target_document(value: _PrimitiveIRDocument) -> dict[str, object]:
    try:
        record = _copy.deepcopy(value.to_dict())
        for primitive in record["primitives"]:
            primitive["trace"].pop("extracted_at", None)
        return record
    except (AttributeError, KeyError, TypeError):
        _fail("VERIFIED_TARGET_DOCUMENT_INVALID")


def _verified_target_lines(
    value: object,
    *,
    verification_request: object,
    verification_result: object,
    source_render_bytes: object,
    calibration: object,
) -> list[dict[str, object]]:
    if (
        not isinstance(value, _PrimitiveIRDocument)
        or not isinstance(value.source_document, _SourceDocument)
        or not isinstance(value.primitives, list)
        or not value.primitives
        or len(value.primitives) > _MAX_VERIFIED_TARGET_LINES
    ):
        _fail("VERIFIED_TARGET_DOCUMENT_INVALID")

    # Re-run the existing source-support/calibration owner from exact bytes;
    # trace-shaped fields alone are not evidence of verification.
    from cad_agent.source_verified_geometry import (
        materialize_verified_external_visual_lines,
    )

    source = value.source_document
    reproduced = materialize_verified_external_visual_lines(
        verification_request=verification_request,
        verification_result=verification_result,
        source_render_bytes=source_render_bytes,
        calibration=calibration,
        source_file_name=source.file_name,
        image_width_px=source.image_width_px,
        image_height_px=source.image_height_px,
    )
    if _stable_target_document(value) != _stable_target_document(reproduced):
        _fail("VERIFIED_TARGET_EVIDENCE_MISMATCH")

    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for primitive in reproduced.primitives:
        primitive_id = _identifier(primitive.id, "VERIFIED_TARGET_LINE_INVALID")
        if primitive_id in seen_ids:
            _fail("DUPLICATE_VERIFIED_TARGET_LINE")
        seen_ids.add(primitive_id)
        start = _finite_point(
            [primitive.geometry.start.x, primitive.geometry.start.y],
            "VERIFIED_TARGET_LINE_INVALID",
        )
        end = _finite_point(
            [primitive.geometry.end.x, primitive.geometry.end.y],
            "VERIFIED_TARGET_LINE_INVALID",
        )
        if start == end:
            _fail("VERIFIED_TARGET_LINE_INVALID")
        normalized.append(
            {"primitive_id": primitive_id, "start": start, "end": end}
        )
    return normalized


def _line_pair_residual(first: _Mapping[str, object], second: _Mapping[str, object]) -> float:
    first_start, first_end = first["start"], first["end"]
    second_start, second_end = second["start"], second["end"]
    direct = max(_math.dist(first_start, second_start), _math.dist(first_end, second_end))
    reverse = max(_math.dist(first_start, second_end), _math.dist(first_end, second_start))
    residual = min(direct, reverse)
    if not _math.isfinite(residual):
        _fail("LINE_GEOMETRY_OUT_OF_RANGE")
    return residual


def _aligned_target_line(
    base: _Mapping[str, object], target: _Mapping[str, object]
) -> dict[str, list[float]]:
    start, end = target["start"], target["end"]
    direct = max(_math.dist(base["start"], start), _math.dist(base["end"], end))
    reverse = max(_math.dist(base["start"], end), _math.dist(base["end"], start))
    return {"start": start, "end": end} if direct <= reverse else {"start": end, "end": start}


def _nonnegative_tolerance(value: object, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(code)
    try:
        tolerance = float(value)
    except OverflowError:
        _fail(code)
    if not _math.isfinite(tolerance) or tolerance < 0:
        _fail(code)
    return tolerance


def _target_to_base_alignment(
    value: object, *, max_residual: float, coordinate_unit: str
) -> tuple[dict[str, object], tuple[tuple[float, ...], ...]]:
    from primitive_ir_lib.geometry_alignment import (
        AnchorPair as _AnchorPair,
        estimate_similarity_alignment as _estimate_similarity_alignment,
    )

    if (
        not isinstance(value, (list, tuple))
        or not 2 <= len(value) <= 32
        or any(not isinstance(anchor, _AnchorPair) for anchor in value)
    ):
        _fail("TARGET_BASE_ALIGNMENT_UNPROVEN")

    alignment = _estimate_similarity_alignment(
        value,
        max_residual_px=max_residual,
    )
    matrix = alignment.matrix
    if (
        alignment.status != "ALIGNED"
        or alignment.method != "VERIFIED_ANCHOR_SIMILARITY"
        or matrix is None
        or len(matrix) != 2
        or any(len(row) != 3 for row in matrix)
        or not all(_math.isfinite(float(item)) for row in matrix for item in row)
    ):
        _fail("TARGET_BASE_ALIGNMENT_UNPROVEN")

    uniform_scale = _math.hypot(float(matrix[0][0]), float(matrix[1][0]))
    if (
        not _math.isfinite(uniform_scale)
        or abs(uniform_scale - 1.0) > _TARGET_BASE_SCALE_TOLERANCE
    ):
        _fail("TARGET_BASE_ALIGNMENT_SCALE_UNPROVEN")

    anchors_by_id = {anchor.anchor_id: anchor for anchor in value}
    selected_anchors = []
    for anchor_id in alignment.anchor_ids:
        anchor = anchors_by_id[anchor_id]
        selected_anchors.append(
            {
                "anchor_id": anchor_id,
                "base": _finite_point(anchor.reference_px, "TARGET_BASE_ALIGNMENT_UNPROVEN"),
                "target": _finite_point(anchor.cad_px, "TARGET_BASE_ALIGNMENT_UNPROVEN"),
                "authority": anchor.authority,
                "confidence": float(anchor.confidence),
            }
        )
    return (
        {
            "status": alignment.status,
            "method": alignment.method,
            "coordinate_unit": coordinate_unit,
            "anchor_pairs": selected_anchors,
            "matrix": [list(row) for row in matrix],
            "uniform_scale": uniform_scale,
            "scale_tolerance": _TARGET_BASE_SCALE_TOLERANCE,
            "residual_rms": float(alignment.residual_rms_px),
            "max_residual": max_residual,
        },
        matrix,
    )


def _apply_alignment_to_target_line(
    line: _Mapping[str, object], matrix: tuple[tuple[float, ...], ...]
) -> dict[str, object]:
    def transform(value: object) -> list[float]:
        x, y = _finite_point(value, "TARGET_BASE_ALIGNMENT_UNPROVEN")
        try:
            point = [
                matrix[0][0] * x + matrix[0][1] * y + matrix[0][2],
                matrix[1][0] * x + matrix[1][1] * y + matrix[1][2],
            ]
        except OverflowError:
            _fail("TARGET_BASE_ALIGNMENT_UNPROVEN")
        if not all(_math.isfinite(item) for item in point):
            _fail("TARGET_BASE_ALIGNMENT_UNPROVEN")
        return point

    return {
        "primitive_id": line["primitive_id"],
        "start": transform(line["start"]),
        "end": transform(line["end"]),
    }


def _same_residual(first: float, second: float) -> bool:
    # Treat only floating-point representation noise as a geometric tie.
    return first == second or abs(first - second) <= 4 * max(
        _math.ulp(first), _math.ulp(second)
    )


def _proposal_without_match(
    status: str,
    geometry_tolerance: dict[str, object],
    target_to_base_alignment: dict[str, object],
) -> dict[str, object]:
    return {
        "status": "PROPOSAL_ONLY",
        "correspondence_status": status,
        "base_target_correspondence": [],
        "geometry_tolerance": geometry_tolerance,
        "target_to_base_alignment": target_to_base_alignment,
        "bounded_native_line_deltas": [],
        "semantic_label_authority": "NONE",
        "cad_mutation": False,
    }


def compose_verified_native_line_delta(
    *,
    base_native_line_observations: object,
    verified_target_document: object,
    verification_request: object,
    verification_result: object,
    source_render_bytes: object,
    calibration: object,
    base_coordinate_unit: object,
    max_correspondence_residual: object,
    keep_tolerance: object,
    target_to_base_alignment_anchors: object,
    max_alignment_residual: object,
) -> dict[str, object]:
    """Compose a geometry-only, proposal-only correspondence for bounded LINEs.

    Opaque IDs are carried into the result but never participate in matching.
    The existing anchor-similarity owner first maps target coordinates into the
    base frame; ambiguous or colliding matches then fail closed without deltas.
    """

    base_lines = _native_lines(base_native_line_observations)
    target_lines = _verified_target_lines(
        verified_target_document,
        verification_request=verification_request,
        verification_result=verification_result,
        source_render_bytes=source_render_bytes,
        calibration=calibration,
    )
    max_residual = _nonnegative_tolerance(
        max_correspondence_residual, "GEOMETRY_TOLERANCE_INVALID"
    )
    keep_limit = _nonnegative_tolerance(keep_tolerance, "GEOMETRY_TOLERANCE_INVALID")
    if keep_limit > max_residual:
        _fail("GEOMETRY_TOLERANCE_INVALID")
    target_calibration = verified_target_document.calibration
    if base_coordinate_unit != target_calibration.unit:
        _fail("GEOMETRY_UNIT_MISMATCH")
    alignment_limit = _nonnegative_tolerance(
        max_alignment_residual, "TARGET_BASE_ALIGNMENT_UNPROVEN"
    )
    alignment_record, alignment_matrix = _target_to_base_alignment(
        target_to_base_alignment_anchors,
        max_residual=alignment_limit,
        coordinate_unit=target_calibration.unit,
    )
    target_lines = [
        _apply_alignment_to_target_line(line, alignment_matrix) for line in target_lines
    ]
    geometry_tolerance = {
        "unit": target_calibration.unit,
        "max_correspondence_residual": max_residual,
        "keep_tolerance": keep_limit,
    }
    matches: list[tuple[dict[str, object], dict[str, object], float]] = []
    used_base_ids: set[str] = set()
    for target in target_lines:
        costs = [(_line_pair_residual(base, target), base) for base in base_lines]
        costs.sort(key=lambda item: item[0])
        best_residual, best_base = costs[0]
        if best_residual > max_residual:
            return _proposal_without_match(
                "NO_SUPPORTED_DELTA", geometry_tolerance, alignment_record
            )
        if len(costs) > 1 and _same_residual(best_residual, costs[1][0]):
            return _proposal_without_match("AMBIGUOUS", geometry_tolerance, alignment_record)
        base_id = str(best_base["observation_id"])
        if base_id in used_base_ids:
            return _proposal_without_match("AMBIGUOUS", geometry_tolerance, alignment_record)
        used_base_ids.add(base_id)
        matches.append((best_base, target, best_residual))

    correspondence: list[dict[str, object]] = []
    deltas: list[dict[str, object]] = []
    for base, target, residual in sorted(matches, key=lambda pair: str(pair[0]["observation_id"])):
        before = {"start": base["start"], "end": base["end"]}
        after = _aligned_target_line(base, target)
        changed = residual > keep_limit
        correspondence.append(
            {
                "base_observation_id": str(base["observation_id"]),
                "target_primitive_id": str(target["primitive_id"]),
                "disposition": "CHANGE" if changed else "KEEP",
                "residual": residual,
            }
        )
        if changed:
            deltas.append(
                {
                    "base_observation_id": str(base["observation_id"]),
                    "target_primitive_id": str(target["primitive_id"]),
                    "before": before,
                    "after": after,
                }
            )
    return {
        "status": "PROPOSAL_ONLY",
        "correspondence_status": "UNIQUE",
        "base_target_correspondence": correspondence,
        "geometry_tolerance": geometry_tolerance,
        "target_to_base_alignment": alignment_record,
        "bounded_native_line_deltas": deltas,
        "semantic_label_authority": "NONE",
        "cad_mutation": False,
    }
