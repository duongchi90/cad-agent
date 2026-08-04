"""Strict, pure-Python Visual Supervisor contract validation."""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


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


def _identifier(value: object, *, contract: str, path: str) -> str:
    text = _string(value, contract=contract, path=path)
    if _ID_RE.fullmatch(text) is None:
        _fail(contract, f"{path} has invalid identifier format")
    return text


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


def _validate_reference(value: object, *, contract: str, path: str) -> None:
    reference = _object(value, contract=contract, path=path)
    _keys(reference, contract=contract, required={"type", "id"})
    if reference["type"] not in {"DATUM", "ENTITY", "FEATURE", "DIMENSION"}:
        _fail(contract, f"{path}.type is invalid")
    _identifier(reference["id"], contract=contract, path=f"{path}.id")


def _validate_bbox(value: object, *, contract: str, path: str) -> None:
    if not isinstance(value, list) or len(value) != 4:
        _fail(contract, f"{path} must contain exactly four numbers")
    for index, item in enumerate(value):
        _finite_number(item, contract=contract, path=f"{path}[{index}]")


_DIMENSION_ROLES = {"DRIVING", "REFERENCE", "DERIVED", "AMBIGUOUS", "CONFLICT"}
_DIMENSION_STATUSES = {"CONFIRMED", "UNRESOLVED", "CONFLICT"}


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
    if not isinstance(dimensions, list) or not dimensions:
        _fail(contract, "dimensions must be a non-empty list")
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
            optional={"from_ref", "to_ref"},
        )
        _identifier(dimension["id"], contract=contract, path=f"{path}.id")
        _string(dimension["display_text"], contract=contract, path=f"{path}.display_text")
        _finite_number(dimension["value"], contract=contract, path=f"{path}.value")
        _string(dimension["unit"], contract=contract, path=f"{path}.unit")
        _string(dimension["kind"], contract=contract, path=f"{path}.kind")
        role = dimension["role"]
        status = dimension["status"]
        if role not in _DIMENSION_ROLES:
            _fail(contract, f"{path}.role is invalid")
        if status not in _DIMENSION_STATUSES:
            _fail(contract, f"{path}.status is invalid")
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
                _validate_reference(dimension[reference_key], contract=contract, path=f"{path}.{reference_key}")
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
}


def validate_visual_contract(
    payload: Mapping[str, object],
    *,
    contract: str,
) -> dict[str, object]:
    key = contract.replace("-", "_")
    validator = _VALIDATORS.get(key)
    if validator is None:
        raise VisualContractError(f"unsupported contract kind: {contract}")
    if not isinstance(payload, Mapping):
        raise VisualContractError(f"{contract}: root must be an object")
    copied = copy.deepcopy(dict(payload))
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
