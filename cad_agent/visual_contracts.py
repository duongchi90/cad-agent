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


def _string_list(value: object, *, contract: str, path: str, min_items: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < min_items:
        _fail(contract, f"{path} must contain at least {min_items} items")
    for index, item in enumerate(value):
        _string(item, contract=contract, path=f"{path}[{index}]")
    return value


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
