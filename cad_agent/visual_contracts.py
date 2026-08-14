"""Strict, pure-Python Visual Supervisor contract validation."""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from .drawing_contracts import canonical_json_sha256

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CAPTURED_AT_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


class VisualContractError(ValueError):
    """Raised when a Visual Supervisor contract is malformed or unsafe."""


def _fail(contract: str, message: str) -> None:
    raise VisualContractError(f"{contract}: {message}")


def _keys(
    payload: Mapping[str, object],
    *,
    contract: str,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    if any(not isinstance(key, str) for key in payload):
        _fail(contract, "properties must use string keys")
    allowed = required | (optional or set())
    missing = sorted(required - set(payload))
    unexpected = sorted(set(payload) - allowed)
    if missing:
        _fail(contract, f"missing required properties: {', '.join(missing)}")
    if unexpected:
        _fail(contract, f"Unexpected properties: {', '.join(unexpected)}")


def _object(value: object, *, contract: str, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(contract, f"{path} must be an object")
    return value


def _string(value: object, *, contract: str, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(contract, f"{path} must be a non-empty string")
    return value


def _nullable_non_empty_string(value: object, *, contract: str, path: str) -> str | None:
    if value is None:
        return None
    return _string(value, contract=contract, path=path)


def _identifier(value: object, *, contract: str, path: str) -> str:
    text = _string(value, contract=contract, path=path)
    if _ID_RE.fullmatch(text) is None:
        _fail(contract, f"{path} has invalid identifier format")
    return text


def _nullable_identifier(value: object, *, contract: str, path: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, contract=contract, path=path)


def _sha256(value: object, *, contract: str, path: str) -> str:
    text = _string(value, contract=contract, path=path)
    if _HASH_RE.fullmatch(text) is None:
        _fail(contract, f"{path} must be a lowercase SHA-256")
    return text


def _finite_number(value: object, *, contract: str, path: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(contract, f"{path} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        _fail(contract, f"{path} must be finite")
    return value


def _non_negative_integer(value: object, *, contract: str, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(contract, f"{path} must be a non-negative integer")
    return value


def _positive_integer(value: object, *, contract: str, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail(contract, f"{path} must be a positive integer")
    return value


def _bool(value: object, *, contract: str, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(contract, f"{path} must be boolean")
    return value


def _string_list(value: object, *, contract: str, path: str, min_items: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < min_items:
        _fail(contract, f"{path} must contain at least {min_items} items")
    for index, item in enumerate(value):
        _string(item, contract=contract, path=f"{path}[{index}]")
    return value


def _validate_reference(
    value: object,
    *,
    contract: str,
    path: str,
    allow_entity_handle: bool = False,
) -> None:
    reference = _object(value, contract=contract, path=path)
    _keys(
        reference,
        contract=contract,
        required={"type", "id"},
        optional={"entity_handle"} if allow_entity_handle else None,
    )
    if reference["type"] not in {"DATUM", "ENTITY", "FEATURE", "DIMENSION"}:
        _fail(contract, f"{path}.type is invalid")
    _identifier(reference["id"], contract=contract, path=f"{path}.id")
    if "entity_handle" in reference:
        if reference["type"] != "DATUM":
            _fail(contract, f"{path}.entity_handle is only valid for DATUM references")
        _identifier(reference["entity_handle"], contract=contract, path=f"{path}.entity_handle")


def _validate_bbox(value: object, *, contract: str, path: str) -> None:
    if not isinstance(value, list) or len(value) != 4:
        _fail(contract, f"{path} must contain exactly four numbers")
    for index, item in enumerate(value):
        _finite_number(item, contract=contract, path=f"{path}[{index}]")


def _validate_wcs_bbox(value: object, *, contract: str, path: str) -> list[float | int]:
    _validate_bbox(value, contract=contract, path=path)
    assert isinstance(value, list)
    xmin, ymin, xmax, ymax = value
    if xmax <= xmin or ymax <= ymin:
        _fail(contract, f"{path} must be a non-degenerate [xmin, ymin, xmax, ymax] bbox")
    return value


def _validate_point(value: object, *, contract: str, path: str) -> None:
    if not isinstance(value, list) or len(value) != 2:
        _fail(contract, f"{path} must contain exactly two numbers")
    for index, item in enumerate(value):
        _finite_number(item, contract=contract, path=f"{path}[{index}]")


def _validate_segment(value: object, *, contract: str, path: str) -> None:
    if not isinstance(value, list) or len(value) != 2:
        _fail(contract, f"{path} must contain exactly two points")
    for index, point in enumerate(value):
        _validate_point(point, contract=contract, path=f"{path}[{index}]")


def _validate_nullable_number(value: object, *, contract: str, path: str) -> None:
    if value is not None:
        _finite_number(value, contract=contract, path=path)


def _validate_dimension_observer_evidence(
    dimension: dict[str, Any], *, contract: str, path: str
) -> None:
    if "raw_text_candidates" in dimension:
        _string_list(
            dimension["raw_text_candidates"],
            contract=contract,
            path=f"{path}.raw_text_candidates",
        )
    if "ocr_evidence" in dimension:
        ocr_evidence = dimension["ocr_evidence"]
        if not isinstance(ocr_evidence, list):
            _fail(contract, f"{path}.ocr_evidence must be a list")
        for index, raw_candidate in enumerate(ocr_evidence):
            candidate_path = f"{path}.ocr_evidence[{index}]"
            candidate = _object(raw_candidate, contract=contract, path=candidate_path)
            _keys(
                candidate,
                contract=contract,
                required={"id", "content", "bbox", "rotation_deg", "confidence", "source"},
            )
            _identifier(candidate["id"], contract=contract, path=f"{candidate_path}.id")
            if not isinstance(candidate["content"], str):
                _fail(contract, f"{candidate_path}.content must be a string")
            _validate_bbox(candidate["bbox"], contract=contract, path=f"{candidate_path}.bbox")
            rotation = _finite_number(
                candidate["rotation_deg"],
                contract=contract,
                path=f"{candidate_path}.rotation_deg",
            )
            if rotation not in {-90.0, 0.0, 90.0}:
                _fail(contract, f"{candidate_path}.rotation_deg is invalid")
            confidence = _finite_number(
                candidate["confidence"],
                contract=contract,
                path=f"{candidate_path}.confidence",
            )
            if not 0.0 <= confidence <= 1.0:
                _fail(contract, f"{candidate_path}.confidence must be between 0 and 1")
            _string(candidate["source"], contract=contract, path=f"{candidate_path}.source")
    if "symbol_text" in dimension:
        _nullable_non_empty_string(
            dimension["symbol_text"],
            contract=contract,
            path=f"{path}.symbol_text",
        )

    if "tolerance" in dimension:
        tolerance = _object(dimension["tolerance"], contract=contract, path=f"{path}.tolerance")
        _keys(
            tolerance,
            contract=contract,
            required={"mode", "upper", "lower", "unit"},
        )
        if tolerance["mode"] not in {"NONE", "SYMMETRIC", "LIMITS", "PLUS_MINUS"}:
            _fail(contract, f"{path}.tolerance.mode is invalid")
        _validate_nullable_number(
            tolerance["upper"], contract=contract, path=f"{path}.tolerance.upper"
        )
        _validate_nullable_number(
            tolerance["lower"], contract=contract, path=f"{path}.tolerance.lower"
        )
        _nullable_non_empty_string(
            tolerance["unit"], contract=contract, path=f"{path}.tolerance.unit"
        )

    if "extension_geometry" in dimension:
        geometry = _object(
            dimension["extension_geometry"],
            contract=contract,
            path=f"{path}.extension_geometry",
        )
        _keys(
            geometry,
            contract=contract,
            required={"dimension_line", "extension_lines", "arrow_points"},
            optional={"leader_lines"},
        )
        if geometry["dimension_line"] is not None:
            _validate_segment(
                geometry["dimension_line"],
                contract=contract,
                path=f"{path}.extension_geometry.dimension_line",
            )
        extension_lines = geometry["extension_lines"]
        if not isinstance(extension_lines, list):
            _fail(contract, f"{path}.extension_geometry.extension_lines must be a list")
        for index, segment in enumerate(extension_lines):
            _validate_segment(
                segment,
                contract=contract,
                path=f"{path}.extension_geometry.extension_lines[{index}]",
            )
        arrow_points = geometry["arrow_points"]
        if not isinstance(arrow_points, list):
            _fail(contract, f"{path}.extension_geometry.arrow_points must be a list")
        for index, point in enumerate(arrow_points):
            _validate_point(
                point,
                contract=contract,
                path=f"{path}.extension_geometry.arrow_points[{index}]",
            )
        if "leader_lines" in geometry:
            leader_lines = geometry["leader_lines"]
            if not isinstance(leader_lines, list):
                _fail(contract, f"{path}.extension_geometry.leader_lines must be a list")
            for index, segment in enumerate(leader_lines):
                _validate_segment(
                    segment,
                    contract=contract,
                    path=f"{path}.extension_geometry.leader_lines[{index}]",
                )

    if "attachment_candidates" in dimension:
        candidates = dimension["attachment_candidates"]
        if not isinstance(candidates, list):
            _fail(contract, f"{path}.attachment_candidates must be a list")
        for index, raw_candidate in enumerate(candidates):
            candidate_path = f"{path}.attachment_candidates[{index}]"
            candidate = _object(raw_candidate, contract=contract, path=candidate_path)
            _keys(
                candidate,
                contract=contract,
                required={"from_ref", "to_ref", "confidence", "evidence"},
            )
            _validate_reference(
                candidate["from_ref"], contract=contract, path=f"{candidate_path}.from_ref"
            )
            _validate_reference(
                candidate["to_ref"], contract=contract, path=f"{candidate_path}.to_ref"
            )
            confidence = _finite_number(
                candidate["confidence"], contract=contract, path=f"{candidate_path}.confidence"
            )
            if not 0.0 <= confidence <= 1.0:
                _fail(contract, f"{candidate_path}.confidence must be between 0 and 1")
            _string_list(candidate["evidence"], contract=contract, path=f"{candidate_path}.evidence")

    if "provenance" in dimension:
        provenance = _object(dimension["provenance"], contract=contract, path=f"{path}.provenance")
        _keys(
            provenance,
            contract=contract,
            required={"observer_version", "ocr_engine", "observation_sha256"},
            optional={"ocr_rotations_deg"},
        )
        _string(
            provenance["observer_version"],
            contract=contract,
            path=f"{path}.provenance.observer_version",
        )
        _string(
            provenance["ocr_engine"],
            contract=contract,
            path=f"{path}.provenance.ocr_engine",
        )
        _sha256(
            provenance["observation_sha256"],
            contract=contract,
            path=f"{path}.provenance.observation_sha256",
        )
        if "ocr_rotations_deg" in provenance:
            rotations = provenance["ocr_rotations_deg"]
            if rotations != [0.0, 90.0, -90.0]:
                _fail(contract, f"{path}.provenance.ocr_rotations_deg is invalid")


_DIMENSION_ROLES = {"DRIVING", "REFERENCE", "DERIVED", "AMBIGUOUS", "CONFLICT"}
_DIMENSION_STATUSES = {"CONFIRMED", "UNRESOLVED", "CONFLICT"}
_ALIGNMENT_STATUSES = {"ALIGNED", "FAILED"}
_COMPARISON_TRENDS = {"BASELINE", "IMPROVED", "REGRESSED", "UNCHANGED"}


def _validate_dimension_register(payload: dict[str, Any]) -> None:
    contract = "dimension_register"
    required = {
        "schema_version",
        "run_id",
        "source_sha256",
        "page_id",
        "view_id",
        "coverage",
        "summary",
        "dimensions",
    }
    _keys(payload, contract=contract, required=required)
    if payload["schema_version"] != "dimension-register-1.0":
        _fail(contract, "schema_version must be 'dimension-register-1.0'")
    _identifier(payload["run_id"], contract=contract, path="run_id")
    _sha256(payload["source_sha256"], contract=contract, path="source_sha256")
    _identifier(payload["page_id"], contract=contract, path="page_id")
    _identifier(payload["view_id"], contract=contract, path="view_id")

    coverage = _object(payload["coverage"], contract=contract, path="coverage")
    _keys(
        coverage,
        contract=contract,
        required={"clusters_detected", "clusters_processed", "page_coverage_percent"},
    )
    detected = _non_negative_integer(
        coverage["clusters_detected"], contract=contract, path="coverage.clusters_detected"
    )
    processed = _non_negative_integer(
        coverage["clusters_processed"], contract=contract, path="coverage.clusters_processed"
    )
    if processed > detected:
        _fail(contract, "coverage.clusters_processed cannot exceed clusters_detected")
    percentage = _finite_number(
        coverage["page_coverage_percent"], contract=contract, path="coverage.page_coverage_percent"
    )
    if not 0.0 <= percentage <= 100.0:
        _fail(contract, "coverage.page_coverage_percent must be between 0 and 100")

    summary = _object(payload["summary"], contract=contract, path="summary")
    _keys(summary, contract=contract, required={"confirmed", "unresolved", "conflicts"})
    for key in ("confirmed", "unresolved", "conflicts"):
        _non_negative_integer(summary[key], contract=contract, path=f"summary.{key}")

    dimensions = payload["dimensions"]
    if not isinstance(dimensions, list):
        _fail(contract, "dimensions must be a list")
    disposition_counts = {"CONFIRMED": 0, "UNRESOLVED": 0, "CONFLICT": 0}
    for index, raw_dimension in enumerate(dimensions):
        path = f"dimensions[{index}]"
        dimension = _object(raw_dimension, contract=contract, path=path)
        _keys(
            dimension,
            contract=contract,
            required={
                "id",
                "display_text",
                "value",
                "unit",
                "kind",
                "role",
                "status",
                "critical",
                "source_evidence",
                "text_confidence",
                "attachment_confidence",
                "blocker_scope",
            },
            optional={
                "from_ref",
                "to_ref",
                "raw_text_candidates",
                "ocr_evidence",
                "symbol_text",
                "tolerance",
                "extension_geometry",
                "attachment_candidates",
                "provenance",
            },
        )
        _identifier(dimension["id"], contract=contract, path=f"{path}.id")
        role = dimension["role"]
        status = dimension["status"]
        if role not in _DIMENSION_ROLES:
            _fail(contract, f"{path}.role is invalid")
        if status not in _DIMENSION_STATUSES:
            _fail(contract, f"{path}.status is invalid")
        if not isinstance(dimension["display_text"], str):
            _fail(contract, f"{path}.display_text must be a string")
        if status == "CONFIRMED" and dimension["display_text"] == "":
            _fail(contract, f"{path}.display_text is required for CONFIRMED dimensions")
        if dimension["unit"] is not None:
            _string(dimension["unit"], contract=contract, path=f"{path}.unit")
        elif status == "CONFIRMED":
            _fail(contract, f"{path}.unit is required for CONFIRMED dimensions")
        _string(dimension["kind"], contract=contract, path=f"{path}.kind")
        if dimension["value"] is None:
            if status == "CONFIRMED":
                _fail(contract, f"{path}.value is required for CONFIRMED dimensions")
        else:
            _finite_number(dimension["value"], contract=contract, path=f"{path}.value")
        if role == "CONFLICT" and status != "CONFLICT":
            _fail(contract, f"{path}.CONFLICT role requires CONFLICT status")
        if role == "AMBIGUOUS" and status == "CONFIRMED":
            _fail(contract, f"{path}.AMBIGUOUS role cannot be CONFIRMED")
        if role == "DRIVING" and status == "CONFIRMED":
            for reference_key in ("from_ref", "to_ref"):
                if reference_key not in dimension:
                    _fail(contract, f"{path} requires {reference_key}")
        for reference_key in ("from_ref", "to_ref"):
            if reference_key in dimension:
                _validate_reference(
                    dimension[reference_key],
                    contract=contract,
                    path=f"{path}.{reference_key}",
                    allow_entity_handle=True,
                )
        _bool(dimension["critical"], contract=contract, path=f"{path}.critical")
        source_evidence = _object(dimension["source_evidence"], contract=contract, path=f"{path}.source_evidence")
        _keys(source_evidence, contract=contract, required={"crop_id", "bbox", "crop_sha256"})
        _identifier(source_evidence["crop_id"], contract=contract, path=f"{path}.source_evidence.crop_id")
        _validate_bbox(source_evidence["bbox"], contract=contract, path=f"{path}.source_evidence.bbox")
        _sha256(source_evidence["crop_sha256"], contract=contract, path=f"{path}.source_evidence.crop_sha256")
        for confidence_key in ("text_confidence", "attachment_confidence"):
            confidence = _finite_number(dimension[confidence_key], contract=contract, path=f"{path}.{confidence_key}")
            if not 0.0 <= confidence <= 1.0:
                _fail(contract, f"{path}.{confidence_key} must be between 0 and 1")
        blocker_scope = _string_list(
            dimension["blocker_scope"], contract=contract, path=f"{path}.blocker_scope", min_items=0
        )
        for blocker_index, region_id in enumerate(blocker_scope):
            _identifier(region_id, contract=contract, path=f"{path}.blocker_scope[{blocker_index}]")
        if dimension["critical"] and status in {"UNRESOLVED", "CONFLICT"} and not blocker_scope:
            _fail(contract, f"{path}.blocker_scope is required for a critical unresolved/conflicting dimension")
        _validate_dimension_observer_evidence(dimension, contract=contract, path=path)
        disposition_counts[status] += 1

    for key, expected in (("confirmed", "CONFIRMED"), ("unresolved", "UNRESOLVED"), ("conflicts", "CONFLICT")):
        if summary[key] != disposition_counts[expected]:
            _fail(contract, f"summary.{key} does not match dimension dispositions")


def require_dimension_gate_ready(register: Mapping[str, object]) -> None:
    validated = validate_visual_contract(register, contract="dimension_register")
    coverage = validated["coverage"]
    if coverage["clusters_processed"] != coverage["clusters_detected"]:
        raise VisualContractError("dimension_register: not all detected clusters have dispositions")
    if coverage["page_coverage_percent"] != 100.0:
        raise VisualContractError("dimension_register: page coverage must be 100 percent")
    for dimension in validated["dimensions"]:
        if dimension["critical"] and dimension["status"] in {"UNRESOLVED", "CONFLICT"}:
            raise VisualContractError(
                f"dimension_register: critical dimension {dimension['id']} blocks {dimension['blocker_scope']}"
            )


_GEOMETRY_METRICS = (
    "silhouette_iou",
    "chamfer_distance_normalized",
    "hausdorff_p95_normalized",
    "centroid_offset_x_ratio",
    "centroid_offset_y_ratio",
    "width_ratio_error",
    "height_ratio_error",
    "missing_edge_ratio",
    "extra_edge_ratio",
    "connected_component_difference",
)

_VISUAL_VERDICTS = {"PASS", "FAIL", "NEEDS_HUMAN"}
_SEVERITIES = {"INFO", "MINOR", "MAJOR", "CRITICAL"}
_FINDING_CATEGORIES = {
    "MISSING_FEATURE",
    "EXTRA_FEATURE",
    "TOPOLOGY_MISMATCH",
    "POSITION_MISMATCH",
    "PROPORTION_MISMATCH",
    "SHAPE_MISMATCH",
    "DIMENSION_MISMATCH",
    "ANNOTATION_LAYOUT_MISMATCH",
    "SOURCE_TECHNICAL_CONFLICT",
}
_ALLOWED_REPAIR_OPERATIONS = {
    "MOVE_COMPONENT",
    "ALIGN_COMPONENT",
    "REPLACE_POLYLINE_SEGMENT",
    "ADJUST_ARC",
    "ADJUST_SPLINE_CONTROL_REGION",
    "ADD_MISSING_FEATURE",
    "REMOVE_EXTRA_FEATURE",
    "REPLACE_WITH_APPROVED_BLOCK",
    "CREATE_NATIVE_DIMENSION",
    "REPAIR_NATIVE_DIMENSION",
}
_REGION_STATUSES = {"PENDING", "CHECKING", "FAILED", "NEEDS_REVIEW", "VERIFIED", "STALE"}
_GATE_STATUSES = {"PASS", "FAIL", "NOT_RUN"}
_CRITICALITIES = {"CRITICAL", "NORMAL"}
_PUBLISH_POLICY = "AUTO_PUBLISH_AFTER_ALL_GATES"
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/].+")
_CAPTURE_CLASSES = {"GLOBAL", "REGION", "DETAIL"}
_CAPTURE_MARGIN_BY_CLASS = {"GLOBAL": 0.05, "REGION": 0.10, "DETAIL": 0.05}
_CAPTURE_VIEW_DIRECTION = "TOP"
_CAPTURE_UCS = "WORLD"
_CAPTURE_VISUAL_STYLE = "2D_WIREFRAME"
_CAPTURE_BBOX_REL_TOL = 1e-6
_CAPTURE_BBOX_ABS_TOL = 1e-7


def _validate_geometry_comparison(payload: dict[str, Any]) -> None:
    contract = "geometry_comparison"
    required = {
        "schema_version",
        "comparison_id",
        "run_id",
        "region_id",
        "reference_package_sha256",
        "cad_render_sha256",
        "mutation_sha256",
        "alignment",
        "metrics",
        "trend",
        "previous_comparison_sha256",
    }
    _keys(payload, contract=contract, required=required)
    if payload["schema_version"] != "geometry-comparison-1.0":
        _fail(contract, "schema_version must be 'geometry-comparison-1.0'")
    for key in ("comparison_id", "run_id", "region_id"):
        _identifier(payload[key], contract=contract, path=key)
    for key in ("reference_package_sha256", "cad_render_sha256", "mutation_sha256"):
        _sha256(payload[key], contract=contract, path=key)

    alignment = _object(payload["alignment"], contract=contract, path="alignment")
    _keys(
        alignment,
        contract=contract,
        required={"status", "method", "anchor_ids", "transform_sha256"},
    )
    status = alignment["status"]
    if status not in _ALIGNMENT_STATUSES:
        _fail(contract, "alignment.status is invalid")
    _string(alignment["method"], contract=contract, path="alignment.method")
    anchor_ids = _string_list(alignment["anchor_ids"], contract=contract, path="alignment.anchor_ids")
    for index, anchor_id in enumerate(anchor_ids):
        _identifier(anchor_id, contract=contract, path=f"alignment.anchor_ids[{index}]")
    if status == "ALIGNED" and len(set(anchor_ids)) < 2:
        _fail(contract, "alignment.anchor_ids requires at least two unique anchors when aligned")
    _sha256(alignment["transform_sha256"], contract=contract, path="alignment.transform_sha256")

    metrics = _object(payload["metrics"], contract=contract, path="metrics")
    if status == "ALIGNED":
        _keys(metrics, contract=contract, required=set(_GEOMETRY_METRICS))
    else:
        _keys(metrics, contract=contract, required=set(), optional=set())
    for metric_name in _GEOMETRY_METRICS:
        if metric_name not in metrics:
            continue
        path = f"metrics.{metric_name}"
        value = _finite_number(metrics[metric_name], contract=contract, path=path)
        if metric_name == "silhouette_iou":
            if not 0.0 <= value <= 1.0:
                _fail(contract, f"{path} must be between 0 and 1")
        elif value < 0:
            _fail(contract, f"{path} must be non-negative")
        if metric_name == "connected_component_difference" and not isinstance(value, int):
            _fail(contract, f"{path} must be an integer")

    trend = payload["trend"]
    if trend not in _COMPARISON_TRENDS:
        _fail(contract, "trend is invalid")
    previous_hash = payload["previous_comparison_sha256"]
    if trend == "BASELINE":
        if previous_hash is not None:
            _fail(contract, "previous_comparison_sha256 must be null for BASELINE")
    else:
        _sha256(previous_hash, contract=contract, path="previous_comparison_sha256")
    if status == "FAILED" and trend != "BASELINE":
        _fail(contract, "FAILED alignment requires BASELINE trend")


def _validate_visual_review(payload: dict[str, Any]) -> None:
    contract = "visual_review"
    required = {
        "schema_version",
        "review_id",
        "run_id",
        "region_id",
        "iteration",
        "reference_package_sha256",
        "cad_render_sha256",
        "mutation_sha256",
        "geometry_comparison_sha256",
        "verdict",
        "severity",
        "confidence",
        "findings",
        "repair_intent",
    }
    _keys(payload, contract=contract, required=required)
    if payload["schema_version"] != "visual-review-1.0":
        _fail(contract, "schema_version must be 'visual-review-1.0'")
    for key in ("review_id", "run_id", "region_id"):
        _identifier(payload[key], contract=contract, path=key)
    iteration = _non_negative_integer(payload["iteration"], contract=contract, path="iteration")
    if iteration < 1:
        _fail(contract, "iteration must be at least 1")
    for key in (
        "reference_package_sha256",
        "cad_render_sha256",
        "mutation_sha256",
        "geometry_comparison_sha256",
    ):
        _sha256(payload[key], contract=contract, path=key)
    verdict = payload["verdict"]
    if verdict not in _VISUAL_VERDICTS:
        _fail(contract, "verdict is invalid")
    if payload["severity"] not in _SEVERITIES:
        _fail(contract, "severity is invalid")
    if verdict == "PASS" and payload["severity"] != "INFO":
        _fail(contract, "PASS verdict requires INFO severity")
    if verdict == "FAIL" and payload["severity"] not in {"MAJOR", "CRITICAL"}:
        _fail(contract, "FAIL verdict requires MAJOR or CRITICAL severity")
    confidence = _finite_number(payload["confidence"], contract=contract, path="confidence")
    if not 0.0 <= confidence <= 1.0:
        _fail(contract, "confidence must be between 0 and 1")

    findings = payload["findings"]
    if not isinstance(findings, list):
        _fail(contract, "findings must be a list")
    major_or_critical = False
    for index, raw_finding in enumerate(findings):
        path = f"findings[{index}]"
        finding = _object(raw_finding, contract=contract, path=path)
        _keys(
            finding,
            contract=contract,
            required={"finding_id", "category", "feature", "severity", "description", "evidence_refs"},
        )
        _identifier(finding["finding_id"], contract=contract, path=f"{path}.finding_id")
        if finding["category"] not in _FINDING_CATEGORIES:
            _fail(contract, f"{path}.category is invalid")
        _identifier(finding["feature"], contract=contract, path=f"{path}.feature")
        finding_severity = finding["severity"]
        if finding_severity not in _SEVERITIES:
            _fail(contract, f"{path}.severity is invalid")
        major_or_critical = major_or_critical or finding_severity in {"MAJOR", "CRITICAL"}
        _string(finding["description"], contract=contract, path=f"{path}.description")
        evidence_refs = _string_list(
            finding["evidence_refs"], contract=contract, path=f"{path}.evidence_refs", min_items=1
        )
        for evidence_index, evidence_ref in enumerate(evidence_refs):
            _string(evidence_ref, contract=contract, path=f"{path}.evidence_refs[{evidence_index}]")

    repair_intent = _object(payload["repair_intent"], contract=contract, path="repair_intent")
    _keys(
        repair_intent,
        contract=contract,
        required={"change", "preserve", "required_measurements", "requested_next_evidence"},
    )
    change = _string_list(repair_intent["change"], contract=contract, path="repair_intent.change")
    preserve = _string_list(repair_intent["preserve"], contract=contract, path="repair_intent.preserve")
    required_measurements = _string_list(
        repair_intent["required_measurements"],
        contract=contract,
        path="repair_intent.required_measurements",
    )
    requested_next_evidence = _string_list(
        repair_intent["requested_next_evidence"],
        contract=contract,
        path="repair_intent.requested_next_evidence",
    )
    del required_measurements
    if verdict == "PASS":
        if findings:
            _fail(contract, "PASS verdict requires empty findings")
        if change:
            _fail(contract, "PASS verdict requires empty repair_intent.change")
    elif verdict == "FAIL":
        if not major_or_critical:
            _fail(contract, "FAIL verdict requires a MAJOR or CRITICAL finding")
        if not change:
            _fail(contract, "FAIL verdict requires non-empty repair_intent.change")
        if not preserve:
            _fail(contract, "FAIL verdict requires non-empty repair_intent.preserve")
    elif not findings and not requested_next_evidence:
        _fail(contract, "NEEDS_HUMAN verdict requires a finding or requested next evidence")


def _validate_repair_plan(payload: dict[str, Any]) -> None:
    contract = "repair_plan"
    required = {
        "schema_version",
        "repair_id",
        "source_review_id",
        "run_id",
        "target_drawing_sha256",
        "operations",
        "affected_regions",
        "expected_improvements",
        "must_not_worsen",
        "rollback_candidate_sha256",
    }
    _keys(payload, contract=contract, required=required)
    if payload["schema_version"] != "repair-plan-1.0":
        _fail(contract, "schema_version must be 'repair-plan-1.0'")
    for key in ("repair_id", "source_review_id", "run_id"):
        _identifier(payload[key], contract=contract, path=key)
    for key in ("target_drawing_sha256", "rollback_candidate_sha256"):
        _sha256(payload[key], contract=contract, path=key)

    operations = payload["operations"]
    if not isinstance(operations, list) or not operations:
        _fail(contract, "operations must be a non-empty list")
    for index, raw_operation in enumerate(operations):
        path = f"operations[{index}]"
        operation = _object(raw_operation, contract=contract, path=path)
        _keys(
            operation,
            contract=contract,
            required={"operation", "target", "preserve_anchors", "constraint_refs"},
        )
        if operation["operation"] not in _ALLOWED_REPAIR_OPERATIONS:
            _fail(contract, f"{path}.operation is not allowed")
        target = _object(operation["target"], contract=contract, path=f"{path}.target")
        _keys(target, contract=contract, required={"stable_entity_id", "feature"})
        _string(target["stable_entity_id"], contract=contract, path=f"{path}.target.stable_entity_id")
        _identifier(target["feature"], contract=contract, path=f"{path}.target.feature")
        preserve_anchors = _string_list(
            operation["preserve_anchors"],
            contract=contract,
            path=f"{path}.preserve_anchors",
            min_items=1,
        )
        for anchor_index, anchor_id in enumerate(preserve_anchors):
            _identifier(anchor_id, contract=contract, path=f"{path}.preserve_anchors[{anchor_index}]")
        constraint_refs = _string_list(
            operation["constraint_refs"],
            contract=contract,
            path=f"{path}.constraint_refs",
        )
        for constraint_index, constraint_ref in enumerate(constraint_refs):
            _identifier(constraint_ref, contract=contract, path=f"{path}.constraint_refs[{constraint_index}]")

    affected_regions = _string_list(
        payload["affected_regions"], contract=contract, path="affected_regions", min_items=1
    )
    for index, region_id in enumerate(affected_regions):
        _identifier(region_id, contract=contract, path=f"affected_regions[{index}]")
    for key in ("expected_improvements", "must_not_worsen"):
        _string_list(payload[key], contract=contract, path=key, min_items=1)


def _validate_region_verification_register(payload: dict[str, Any]) -> None:
    contract = "region_verification_register"
    required = {
        "schema_version",
        "run_id",
        "region_id",
        "view_id",
        "criticality",
        "source_crop",
        "cad_evidence",
        "expected_features",
        "dimension_refs",
        "entity_refs",
        "geometry",
        "visual",
        "engineering",
        "unresolved_critical_items",
        "status",
    }
    _keys(payload, contract=contract, required=required)
    if payload["schema_version"] != "region-verification-register-1.0":
        _fail(contract, "schema_version must be 'region-verification-register-1.0'")
    for key in ("run_id", "region_id", "view_id"):
        _identifier(payload[key], contract=contract, path=key)
    if payload["criticality"] not in _CRITICALITIES:
        _fail(contract, "criticality is invalid")

    source_crop = _object(payload["source_crop"], contract=contract, path="source_crop")
    _keys(source_crop, contract=contract, required={"source_sha256", "crop_sha256", "bbox"})
    for key in ("source_sha256", "crop_sha256"):
        _sha256(source_crop[key], contract=contract, path=f"source_crop.{key}")
    _validate_bbox(source_crop["bbox"], contract=contract, path="source_crop.bbox")

    cad_evidence = _object(payload["cad_evidence"], contract=contract, path="cad_evidence")
    _keys(
        cad_evidence,
        contract=contract,
        required={"drawing_sha256", "render_sha256", "mutation_sha256", "latest_mutation_sha256"},
    )
    for key in ("drawing_sha256", "render_sha256", "mutation_sha256", "latest_mutation_sha256"):
        _sha256(cad_evidence[key], contract=contract, path=f"cad_evidence.{key}")

    _string_list(payload["expected_features"], contract=contract, path="expected_features")
    dimension_refs = _string_list(payload["dimension_refs"], contract=contract, path="dimension_refs")
    for index, dimension_ref in enumerate(dimension_refs):
        _identifier(dimension_ref, contract=contract, path=f"dimension_refs[{index}]")
    _string_list(payload["entity_refs"], contract=contract, path="entity_refs")

    for gate in ("geometry", "visual", "engineering"):
        gate_payload = _object(payload[gate], contract=contract, path=gate)
        hash_key = {
            "geometry": "comparison_sha256",
            "visual": "review_sha256",
            "engineering": "measurement_sha256",
        }[gate]
        _keys(gate_payload, contract=contract, required={"status", hash_key})
        if gate_payload["status"] not in _GATE_STATUSES:
            _fail(contract, f"{gate}.status is invalid")
        _sha256(gate_payload[hash_key], contract=contract, path=f"{gate}.{hash_key}")

    unresolved = _string_list(
        payload["unresolved_critical_items"],
        contract=contract,
        path="unresolved_critical_items",
    )
    for index, item in enumerate(unresolved):
        _identifier(item, contract=contract, path=f"unresolved_critical_items[{index}]")
    status = payload["status"]
    if status not in _REGION_STATUSES:
        _fail(contract, "status is invalid")
    if status == "VERIFIED":
        if cad_evidence["mutation_sha256"] != cad_evidence["latest_mutation_sha256"]:
            _fail(contract, "VERIFIED region has stale render evidence")
        for gate in ("geometry", "visual", "engineering"):
            if payload[gate]["status"] != "PASS":
                _fail(contract, f"VERIFIED region requires {gate} gate PASS")
        if unresolved:
            _fail(contract, "VERIFIED region has unresolved critical items")


def require_region_verified(region: Mapping[str, object]) -> None:
    validated = validate_visual_contract(region, contract="region_verification_register")
    if validated["status"] != "VERIFIED":
        raise VisualContractError("region_verification_register: status must be VERIFIED")
    evidence = validated["cad_evidence"]
    if evidence["mutation_sha256"] != evidence["latest_mutation_sha256"]:
        raise VisualContractError("region_verification_register: render evidence is stale")
    for gate in ("geometry", "visual", "engineering"):
        if validated[gate]["status"] != "PASS":
            raise VisualContractError(f"region_verification_register: {gate} gate must PASS")
    if validated["unresolved_critical_items"]:
        raise VisualContractError("region_verification_register: unresolved critical items remain")


def _normalize_visual_review_scope(payload: Mapping[str, object], *, contract: str) -> dict[str, object]:
    _keys(
        payload,
        contract=contract,
        required={
            "schema_version",
            "scope_id",
            "run_id",
            "registry_snapshot_sha256",
            "candidate_revision_sha256",
            "candidate_state_sha256",
            "regions",
        },
    )
    if payload["schema_version"] != "visual-review-scope-1.0":
        _fail(contract, "schema_version must be 'visual-review-scope-1.0'")
    normalized: dict[str, object] = {"schema_version": payload["schema_version"]}
    for key in ("scope_id", "run_id"):
        normalized[key] = _identifier(payload[key], contract=contract, path=key)
    for key in (
        "registry_snapshot_sha256",
        "candidate_revision_sha256",
        "candidate_state_sha256",
    ):
        normalized[key] = _sha256(payload[key], contract=contract, path=key)

    regions = payload["regions"]
    if not isinstance(regions, list) or not regions:
        _fail(contract, "regions must contain at least one item")

    normalized_regions: list[dict[str, object]] = []
    region_ids: set[str] = set()
    for index, value in enumerate(regions):
        path = f"regions[{index}]"
        region = _object(value, contract=contract, path=path)
        _keys(
            region,
            contract=contract,
            required={"region_id", "view_id", "sheet_id", "layout_id", "criticality"},
        )
        region_id = _identifier(region["region_id"], contract=contract, path=f"{path}.region_id")
        if region_id in region_ids:
            _fail(contract, f"duplicate region_id: {region_id}")
        region_ids.add(region_id)
        normalized_region: dict[str, object] = {"region_id": region_id}
        for key in ("view_id", "sheet_id", "layout_id"):
            normalized_region[key] = _identifier(
                region[key], contract=contract, path=f"{path}.{key}"
            )
        if not isinstance(region["criticality"], str) or region["criticality"] not in _CRITICALITIES:
            _fail(contract, f"{path}.criticality is invalid")
        normalized_region["criticality"] = region["criticality"]
        normalized_regions.append(normalized_region)

    normalized["regions"] = sorted(normalized_regions, key=lambda item: item["region_id"])
    return normalized


def _validate_visual_review_scope(
    payload: dict[str, Any], *, server_scope: Mapping[str, object] | None = None
) -> None:
    contract = "visual_review_scope"
    if server_scope is None:
        _fail(contract, "server_scope is required for server-owned validation")
    normalized_payload = _normalize_visual_review_scope(payload, contract=contract)
    normalized_server_scope = _normalize_visual_review_scope(server_scope, contract=contract)
    if normalized_payload != normalized_server_scope:
        _fail(contract, "payload does not match the server-owned scope")
    payload.clear()
    payload.update(normalized_payload)


def _normalize_capture_record(
    value: object,
    *,
    contract: str,
    path: str,
) -> dict[str, object]:
    capture = _object(value, contract=contract, path=path)
    _keys(
        capture,
        contract=contract,
        required={
            "capture_id",
            "capture_class",
            "parent_region_id",
            "region_id",
            "view_id",
            "sheet_id",
            "layout_id",
            "zoom_mode",
            "wcs_bbox",
            "margin_ratio",
            "view_direction",
            "ucs",
            "visual_style",
        },
    )
    normalized: dict[str, object] = {
        "capture_id": _identifier(capture["capture_id"], contract=contract, path=f"{path}.capture_id")
    }
    capture_class = _string(capture["capture_class"], contract=contract, path=f"{path}.capture_class")
    if capture_class not in _CAPTURE_CLASSES:
        _fail(contract, f"{path}.capture_class is invalid")
    normalized["capture_class"] = capture_class
    normalized["parent_region_id"] = _nullable_identifier(
        capture["parent_region_id"], contract=contract, path=f"{path}.parent_region_id"
    )
    normalized["region_id"] = _nullable_identifier(
        capture["region_id"], contract=contract, path=f"{path}.region_id"
    )
    for key in ("view_id", "sheet_id", "layout_id"):
        normalized[key] = _identifier(capture[key], contract=contract, path=f"{path}.{key}")

    zoom_mode = _string(capture["zoom_mode"], contract=contract, path=f"{path}.zoom_mode")
    expected_margin = _CAPTURE_MARGIN_BY_CLASS[capture_class]
    margin = _finite_number(capture["margin_ratio"], contract=contract, path=f"{path}.margin_ratio")
    if margin != expected_margin:
        _fail(contract, f"{path}.margin_ratio must equal canonical {capture_class} margin {expected_margin}")

    view_direction = _string(
        capture["view_direction"], contract=contract, path=f"{path}.view_direction"
    )
    ucs = _string(capture["ucs"], contract=contract, path=f"{path}.ucs")
    visual_style = _string(
        capture["visual_style"], contract=contract, path=f"{path}.visual_style"
    )
    if view_direction != _CAPTURE_VIEW_DIRECTION:
        _fail(contract, f"{path}.view_direction must be {_CAPTURE_VIEW_DIRECTION}")
    if ucs != _CAPTURE_UCS:
        _fail(contract, f"{path}.ucs must be {_CAPTURE_UCS}")
    if visual_style != _CAPTURE_VISUAL_STYLE:
        _fail(contract, f"{path}.visual_style must be {_CAPTURE_VISUAL_STYLE}")

    if capture_class == "GLOBAL":
        if zoom_mode != "EXTENTS" or capture["wcs_bbox"] is not None:
            _fail(contract, f"{path} GLOBAL capture requires EXTENTS and null wcs_bbox")
        if normalized["region_id"] is not None or normalized["parent_region_id"] is not None:
            _fail(contract, f"{path} GLOBAL capture cannot carry region identity")
        bbox: object = None
    else:
        if zoom_mode != "WINDOW":
            _fail(contract, f"{path} {capture_class} capture requires WINDOW zoom_mode")
        bbox = list(_validate_wcs_bbox(capture["wcs_bbox"], contract=contract, path=f"{path}.wcs_bbox"))
        if normalized["region_id"] is None:
            _fail(contract, f"{path}.region_id is required for {capture_class}")
        if capture_class == "REGION" and normalized["parent_region_id"] is not None:
            _fail(contract, f"{path}.parent_region_id must be null for REGION")
        if capture_class == "DETAIL" and normalized["parent_region_id"] is None:
            _fail(contract, f"{path}.parent_region_id is required for DETAIL")

    normalized.update(
        {
            "zoom_mode": zoom_mode,
            "wcs_bbox": bbox,
            "margin_ratio": margin,
            "view_direction": view_direction,
            "ucs": ucs,
            "visual_style": visual_style,
        }
    )
    return normalized


def _normalize_visual_capture_plan_payload(
    payload: Mapping[str, object], *, contract: str
) -> dict[str, object]:
    _keys(
        payload,
        contract=contract,
        required={
            "schema_version",
            "plan_id",
            "run_id",
            "scope_id",
            "registry_snapshot_sha256",
            "candidate_revision_sha256",
            "candidate_state_sha256",
            "latest_mutation_sha256",
            "captures",
        },
    )
    if payload["schema_version"] != "visual-capture-plan-1.0":
        _fail(contract, "schema_version must be 'visual-capture-plan-1.0'")
    normalized: dict[str, object] = {"schema_version": payload["schema_version"]}
    for key in ("plan_id", "run_id", "scope_id"):
        normalized[key] = _identifier(payload[key], contract=contract, path=key)
    for key in (
        "registry_snapshot_sha256",
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "latest_mutation_sha256",
    ):
        normalized[key] = _sha256(payload[key], contract=contract, path=key)
    captures = payload["captures"]
    if not isinstance(captures, list) or not captures:
        _fail(contract, "captures must contain at least one item")
    normalized_captures: list[dict[str, object]] = []
    capture_ids: set[str] = set()
    for index, raw_capture in enumerate(captures):
        capture = _normalize_capture_record(raw_capture, contract=contract, path=f"captures[{index}]")
        capture_id = str(capture["capture_id"])
        if capture_id in capture_ids:
            _fail(contract, f"duplicate capture_id: {capture_id}")
        capture_ids.add(capture_id)
        normalized_captures.append(capture)
    normalized["captures"] = normalized_captures
    return normalized


def _bbox_contains(parent: list[object], child: list[object]) -> bool:
    parent_min_x, parent_min_y, parent_max_x, parent_max_y = map(float, parent)
    child_min_x, child_min_y, child_max_x, child_max_y = map(float, child)

    def not_below(value: float, lower: float) -> bool:
        return value > lower or math.isclose(
            value,
            lower,
            rel_tol=_CAPTURE_BBOX_REL_TOL,
            abs_tol=_CAPTURE_BBOX_ABS_TOL,
        )

    def not_above(value: float, upper: float) -> bool:
        return value < upper or math.isclose(
            value,
            upper,
            rel_tol=_CAPTURE_BBOX_REL_TOL,
            abs_tol=_CAPTURE_BBOX_ABS_TOL,
        )

    return (
        not_below(child_min_x, parent_min_x)
        and not_below(child_min_y, parent_min_y)
        and not_above(child_max_x, parent_max_x)
        and not_above(child_max_y, parent_max_y)
    )


def _validate_visual_capture_plan(
    payload: dict[str, Any], *, server_scope: Mapping[str, object] | None = None
) -> None:
    contract = "visual_capture_plan"
    if server_scope is None:
        _fail(contract, "server_scope is required for server-owned validation")
    normalized = _normalize_visual_capture_plan_payload(payload, contract=contract)
    scope = _normalize_visual_review_scope(server_scope, contract=contract)
    for key in (
        "run_id",
        "scope_id",
        "registry_snapshot_sha256",
        "candidate_revision_sha256",
        "candidate_state_sha256",
    ):
        if normalized[key] != scope[key]:
            _fail(contract, f"{key} does not match the server-owned scope")

    scope_regions = scope["regions"]
    assert isinstance(scope_regions, list)
    region_by_id = {str(region["region_id"]): region for region in scope_regions}
    required_views = {
        (str(region["view_id"]), str(region["sheet_id"]), str(region["layout_id"]))
        for region in scope_regions
    }
    global_counts = {identity: 0 for identity in required_views}
    region_counts = {region_id: 0 for region_id in region_by_id}
    captures = normalized["captures"]
    assert isinstance(captures, list)
    region_capture_by_id = {
        str(capture["region_id"]): capture
        for capture in captures
        if capture["capture_class"] == "REGION"
    }
    seen_groups: set[tuple[str, str, str]] = set()

    for capture in captures:
        capture_class = capture["capture_class"]
        identity = (
            str(capture["view_id"]),
            str(capture["sheet_id"]),
            str(capture["layout_id"]),
        )
        if capture_class == "GLOBAL":
            if identity not in global_counts:
                _fail(contract, "GLOBAL capture is outside the server-owned scope")
            global_counts[identity] += 1
            seen_groups.add(identity)
            continue
        region_id = str(capture["region_id"])
        region = region_by_id.get(region_id)
        if region is None:
            _fail(contract, "region_id is outside the server-owned scope")
        expected_identity = (
            str(region["view_id"]),
            str(region["sheet_id"]),
            str(region["layout_id"]),
        )
        if identity != expected_identity:
            _fail(contract, "view_id/sheet_id/layout_id do not match the server-owned scope")
        if identity not in seen_groups:
            _fail(contract, "the first capture for each server-owned group must be GLOBAL")
        if capture_class == "REGION":
            region_counts[region_id] += 1
        else:
            parent_region_id = capture["parent_region_id"]
            if parent_region_id != region_id or parent_region_id not in region_by_id:
                _fail(contract, "parent_region_id must identify the accepted parent REGION")
            parent_capture = region_capture_by_id.get(str(parent_region_id))
            if parent_capture is None:
                _fail(contract, "DETAIL parent REGION capture is missing")
            parent_bbox = parent_capture["wcs_bbox"]
            detail_bbox = capture["wcs_bbox"]
            assert isinstance(parent_bbox, list)
            assert isinstance(detail_bbox, list)
            if not _bbox_contains(parent_bbox, detail_bbox):
                _fail(contract, "DETAIL bbox must be bounded by its parent REGION bbox")

    if any(count != 1 for count in global_counts.values()):
        _fail(contract, "exactly one GLOBAL capture is required per server-owned view/sheet/layout")
    if any(count != 1 for count in region_counts.values()):
        _fail(contract, "exactly one REGION capture is required per server-owned region")
    payload.clear()
    payload.update(normalized)


def _bbox_matches(expected: list[object], observed: list[object]) -> bool:
    return all(
        math.isclose(
            float(expected_value),
            float(observed_value),
            rel_tol=_CAPTURE_BBOX_REL_TOL,
            abs_tol=_CAPTURE_BBOX_ABS_TOL,
        )
        for expected_value, observed_value in zip(expected, observed, strict=True)
    )


def _validate_visual_capture_receipt(
    payload: dict[str, Any], *, server_plan: Mapping[str, object] | None = None
) -> None:
    contract = "visual_capture_receipt"
    if server_plan is None:
        _fail(contract, "server_scope is required for server-owned validation")
    plan = _normalize_visual_capture_plan_payload(server_plan, contract=contract)
    _keys(
        payload,
        contract=contract,
        required={
            "schema_version",
            "receipt_id",
            "capture_id",
            "run_id",
            "scope_id",
            "region_id",
            "view_id",
            "sheet_id",
            "layout_id",
            "candidate_revision_sha256",
            "candidate_state_sha256",
            "latest_mutation_sha256",
            "visual_capture_plan_sha256",
            "capture_class",
            "zoom_mode",
            "requested_wcs_bbox",
            "observed_wcs_bbox",
            "view_center",
            "view_width",
            "view_height",
            "view_direction",
            "ucs",
            "visual_style",
            "artifact_sha256",
            "artifact_width",
            "artifact_height",
            "captured_at_utc",
            "transient_state_restored",
        },
    )
    if payload["schema_version"] != "visual-capture-receipt-1.0":
        _fail(contract, "schema_version must be 'visual-capture-receipt-1.0'")
    _identifier(payload["receipt_id"], contract=contract, path="receipt_id")
    capture_id = _identifier(payload["capture_id"], contract=contract, path="capture_id")
    captures = plan["captures"]
    assert isinstance(captures, list)
    matched = [capture for capture in captures if capture["capture_id"] == capture_id]
    if len(matched) != 1:
        _fail(contract, "capture_id does not identify exactly one accepted plan capture")
    capture = matched[0]

    for key in ("run_id", "scope_id"):
        _identifier(payload[key], contract=contract, path=key)
        if payload[key] != plan[key]:
            _fail(contract, f"{key} does not match the server-owned plan")
    for key in (
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "latest_mutation_sha256",
    ):
        _sha256(payload[key], contract=contract, path=key)
        if payload[key] != plan[key]:
            _fail(contract, f"{key} does not match the server-owned plan")
    plan_sha = _sha256(
        payload["visual_capture_plan_sha256"],
        contract=contract,
        path="visual_capture_plan_sha256",
    )
    expected_plan_sha = canonical_json_sha256(plan)
    if plan_sha != expected_plan_sha:
        _fail(contract, "visual_capture_plan_sha256 does not match the server-owned plan sha")

    region_id = _nullable_identifier(payload["region_id"], contract=contract, path="region_id")
    if region_id != capture["region_id"]:
        _fail(contract, "region_id does not match the accepted capture")
    for key in (
        "view_id",
        "sheet_id",
        "layout_id",
        "capture_class",
        "zoom_mode",
        "view_direction",
        "ucs",
        "visual_style",
    ):
        _string(payload[key], contract=contract, path=key)
        if payload[key] != capture[key]:
            _fail(contract, f"{key} does not match the accepted capture")

    expected_bbox = capture["wcs_bbox"]
    requested_bbox = payload["requested_wcs_bbox"]
    observed_bbox = payload["observed_wcs_bbox"]
    if capture["capture_class"] == "GLOBAL":
        if requested_bbox is not None or observed_bbox is not None:
            _fail(contract, "GLOBAL requested_wcs_bbox and observed_wcs_bbox must be null")
    else:
        requested = list(
            _validate_wcs_bbox(requested_bbox, contract=contract, path="requested_wcs_bbox")
        )
        observed = list(
            _validate_wcs_bbox(observed_bbox, contract=contract, path="observed_wcs_bbox")
        )
        assert isinstance(expected_bbox, list)
        if requested != expected_bbox:
            _fail(contract, "requested_wcs_bbox does not match the accepted plan")
        if not _bbox_matches(expected_bbox, observed):
            _fail(contract, "observed_wcs_bbox is outside the accepted camera tolerance")

    _validate_point(payload["view_center"], contract=contract, path="view_center")
    view_width = _finite_number(payload["view_width"], contract=contract, path="view_width")
    view_height = _finite_number(payload["view_height"], contract=contract, path="view_height")
    if view_width <= 0:
        _fail(contract, "view_width must be positive")
    if view_height <= 0:
        _fail(contract, "view_height must be positive")

    if capture["capture_class"] != "GLOBAL":
        assert isinstance(expected_bbox, list)
        min_x, min_y, max_x, max_y = map(float, expected_bbox)
        margin = float(capture["margin_ratio"])
        expected_center = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
        actual_center = payload["view_center"]
        assert isinstance(actual_center, list)
        if any(
            not math.isclose(
                float(actual),
                expected,
                rel_tol=_CAPTURE_BBOX_REL_TOL,
                abs_tol=_CAPTURE_BBOX_ABS_TOL,
            )
            for actual, expected in zip(actual_center, expected_center, strict=True)
        ):
            _fail(contract, "view_center does not match the accepted bbox center")
        expected_width = (max_x - min_x) * (1.0 + 2.0 * margin)
        expected_height = (max_y - min_y) * (1.0 + 2.0 * margin)
        if not math.isclose(
            float(view_width),
            expected_width,
            rel_tol=_CAPTURE_BBOX_REL_TOL,
            abs_tol=_CAPTURE_BBOX_ABS_TOL,
        ):
            _fail(contract, "view_width does not match the accepted bbox margin policy")
        if not math.isclose(
            float(view_height),
            expected_height,
            rel_tol=_CAPTURE_BBOX_REL_TOL,
            abs_tol=_CAPTURE_BBOX_ABS_TOL,
        ):
            _fail(contract, "view_height does not match the accepted bbox margin policy")

    _sha256(payload["artifact_sha256"], contract=contract, path="artifact_sha256")
    _positive_integer(payload["artifact_width"], contract=contract, path="artifact_width")
    _positive_integer(payload["artifact_height"], contract=contract, path="artifact_height")
    captured_at = _string(payload["captured_at_utc"], contract=contract, path="captured_at_utc")
    if _CAPTURED_AT_UTC_RE.fullmatch(captured_at) is None:
        _fail(contract, "captured_at_utc must be RFC3339 UTC")
    if payload["transient_state_restored"] is not True:
        _fail(contract, "transient_state_restored must be true")


def _normalize_windows_path(value: object, *, contract: str, path: str) -> str:
    text = _string(value, contract=contract, path=path)
    if _WINDOWS_ABSOLUTE_PATH_RE.fullmatch(text) is None:
        _fail(contract, f"{path} must be an absolute Windows path with a drive letter")
    if any(character in text for character in "*?[]"):
        _fail(contract, f"{path} must not contain wildcard characters")
    segments = re.split(r"[\\/]", text)
    if ".." in segments:
        _fail(contract, f"{path} must not contain directory traversal")
    normalized = text.replace("/", "\\")
    while "\\\\" in normalized:
        normalized = normalized.replace("\\\\", "\\")
    if len(normalized) > 3:
        normalized = normalized.rstrip("\\")
    return normalized.casefold()


def _validate_auto_publish_authorization(payload: dict[str, Any]) -> None:
    contract = "auto_publish_authorization"
    required = {
        "schema_version",
        "authorization_id",
        "run_id",
        "policy",
        "target_path",
        "expected_initial_sha256",
        "allowed_backup_root",
        "single_use",
        "expires_after_run",
        "consumed",
        "authorized_by",
        "approval_reference",
        "status",
    }
    _keys(payload, contract=contract, required=required)
    if payload["schema_version"] != "auto-publish-authorization-1.0":
        _fail(contract, "schema_version must be 'auto-publish-authorization-1.0'")
    for key in ("authorization_id", "run_id", "authorized_by", "approval_reference"):
        _identifier(payload[key], contract=contract, path=key)
    if payload["policy"] != _PUBLISH_POLICY:
        _fail(contract, "policy is invalid")
    target_path = _normalize_windows_path(payload["target_path"], contract=contract, path="target_path")
    backup_root = _normalize_windows_path(
        payload["allowed_backup_root"], contract=contract, path="allowed_backup_root"
    )
    if target_path == backup_root:
        _fail(contract, "target_path and allowed_backup_root must differ")
    _sha256(payload["expected_initial_sha256"], contract=contract, path="expected_initial_sha256")
    if payload["single_use"] is not True:
        _fail(contract, "single_use must be true")
    if payload["expires_after_run"] is not True:
        _fail(contract, "expires_after_run must be true")
    _bool(payload["consumed"], contract=contract, path="consumed")
    if payload["status"] != "APPROVED":
        _fail(contract, "status must be APPROVED")


def require_auto_publish_authorized(
    authorization: Mapping[str, object],
    *,
    run_id: str,
    target_path: str,
    target_sha256: str,
) -> None:
    validated = validate_visual_contract(authorization, contract="auto_publish_authorization")
    if validated["consumed"]:
        raise VisualContractError("auto_publish_authorization: consumed authorization cannot be used")
    if validated["run_id"] != run_id:
        raise VisualContractError("auto_publish_authorization: run ID mismatch")
    contract = "auto_publish_authorization"
    actual_path = _normalize_windows_path(target_path, contract=contract, path="target_path")
    authorized_path = _normalize_windows_path(
        validated["target_path"], contract=contract, path="target_path"
    )
    if actual_path != authorized_path:
        raise VisualContractError("auto_publish_authorization: target path mismatch")
    _sha256(target_sha256, contract=contract, path="target_sha256")
    if target_sha256 != validated["expected_initial_sha256"]:
        raise VisualContractError("auto_publish_authorization: target SHA mismatch")


def _validate_visual_run_manifest(payload: dict[str, Any]) -> None:
    contract = "visual_run_manifest"
    required = {
        "schema_version",
        "run_id",
        "state",
        "authority",
        "source",
        "drawing",
        "evidence_root",
        "latest_mutation_sha256",
    }
    _keys(payload, contract=contract, required=required)
    if payload["schema_version"] != "visual-run-manifest-1.0":
        _fail(contract, "schema_version must be 'visual-run-manifest-1.0'")
    _identifier(payload["run_id"], contract=contract, path="run_id")
    states = {
        "CREATED",
        "SOURCE_NORMALIZED",
        "DIMENSIONS_OBSERVED",
        "DIMENSION_GATE_READY",
        "DRAFT_GENERATED",
        "REGIONS_CHECKING",
        "REPAIRING",
        "LOCAL_VISUAL_VERIFIED",
        "GLOBAL_VERIFIED",
        "PUBLISHING",
        "POST_SAVE_VERIFYING",
        "PUBLISHED",
        "NEEDS_HUMAN",
        "DIMENSION_CONFLICT",
        "NO_VISUAL_IMPROVEMENT",
        "EXECUTION_FAILED",
        "PUBLISH_REFUSED",
        "ROLLED_BACK",
    }
    if payload["state"] not in states:
        _fail(contract, "state is invalid")
    if payload["authority"] not in {"DISPOSABLE_REVIEW", "AUTHORITATIVE_CANDIDATE"}:
        _fail(contract, "authority is invalid")
    source = _object(payload["source"], contract=contract, path="source")
    _keys(source, contract=contract, required={"source_type", "source_sha256", "page_ids"})
    if source["source_type"] not in {"IMAGE", "PDF"}:
        _fail(contract, "source.source_type must be IMAGE or PDF")
    _sha256(source["source_sha256"], contract=contract, path="source.source_sha256")
    _string_list(source["page_ids"], contract=contract, path="source.page_ids", min_items=1)
    drawing = _object(payload["drawing"], contract=contract, path="drawing")
    _keys(drawing, contract=contract, required={"absolute_path", "initial_sha256"})
    _string(drawing["absolute_path"], contract=contract, path="drawing.absolute_path")
    _sha256(drawing["initial_sha256"], contract=contract, path="drawing.initial_sha256")
    _string(payload["evidence_root"], contract=contract, path="evidence_root")
    _sha256(payload["latest_mutation_sha256"], contract=contract, path="latest_mutation_sha256")


_VALIDATORS: dict[str, Callable[[dict[str, Any]], None]] = {
    "visual_run_manifest": _validate_visual_run_manifest,
    "dimension_register": _validate_dimension_register,
    "geometry_comparison": _validate_geometry_comparison,
    "visual_review": _validate_visual_review,
    "repair_plan": _validate_repair_plan,
    "region_verification_register": _validate_region_verification_register,
    "visual_review_scope": _validate_visual_review_scope,
    "visual_capture_plan": _validate_visual_capture_plan,
    "visual_capture_receipt": _validate_visual_capture_receipt,
    "auto_publish_authorization": _validate_auto_publish_authorization,
}
SUPPORTED_VISUAL_CONTRACTS = tuple(sorted(_VALIDATORS))

__all__ = [
    "SUPPORTED_VISUAL_CONTRACTS",
    "VisualContractError",
    "read_visual_contract",
    "require_auto_publish_authorized",
    "require_dimension_gate_ready",
    "require_region_verified",
    "validate_visual_contract",
]


def validate_visual_contract(
    payload: Mapping[str, object],
    *,
    contract: str,
    server_scope: Mapping[str, object] | None = None,
) -> dict[str, object]:
    key = contract.replace("-", "_")
    validator = _VALIDATORS.get(key)
    if validator is None:
        raise VisualContractError(f"unsupported contract kind: {contract}")
    if not isinstance(payload, Mapping):
        raise VisualContractError(f"{contract}: root must be an object")
    copied = copy.deepcopy(dict(payload))
    if key in {"visual_review_scope", "visual_capture_plan", "visual_capture_receipt"}:
        if server_scope is None or not isinstance(server_scope, Mapping):
            raise VisualContractError(
                f"{key}: server_scope is required for server-owned validation"
            )
        if key == "visual_review_scope":
            _validate_visual_review_scope(copied, server_scope=server_scope)
        elif key == "visual_capture_plan":
            _validate_visual_capture_plan(copied, server_scope=server_scope)
        else:
            _validate_visual_capture_receipt(copied, server_plan=server_scope)
    else:
        validator(copied)
    return copied


def read_visual_contract(path: Path, *, contract: str) -> dict[str, object]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VisualContractError(f"Cannot read {contract}: {source}") from exc
    if not isinstance(payload, dict):
        raise VisualContractError(f"{contract}: root must be an object")
    return validate_visual_contract(payload, contract=contract)
