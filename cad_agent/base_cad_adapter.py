"""Closed, context-free Base-CAD binding and identity kernel."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import re

from cad_agent.drawing_contracts import canonical_json_sha256


BASE_CAD_BINDING_SCHEMA_VERSION = "base-cad-binding-1.0"

_BINDING_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "source_bundle_sha256",
        "source_custody_sha256",
        "source_fusion_sha256",
        "base_source",
        "inspection_id",
        "inspection_sha256",
        "target_drawing_sha256",
        "eligible_component_ids",
        "transform_policy",
        "state",
    }
)
_BASE_SOURCE_FIELDS = frozenset({"source_id", "sha256", "revision"})
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_TRANSFORM_POLICY = "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY"


class BaseCadAdapterError(ValueError):
    """Raised when a Base-CAD binding is malformed or unsafe."""


def _fail(message: str) -> None:
    raise BaseCadAdapterError(message)


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{context} must be a mapping")
    if any(type(key) is not str for key in value):
        _fail(f"{context} keys must be strings")
    return dict(value)


def _closed(value: object, expected: frozenset[str], context: str) -> dict[str, object]:
    result = _mapping(value, context)
    unknown = set(result) - expected
    missing = expected - set(result)
    if unknown:
        _fail(f"{context} contains unknown fields: {sorted(unknown)}")
    if missing:
        _fail(f"{context} is missing fields: {sorted(missing)}")
    return result


def _identifier(value: object, context: str) -> str:
    if type(value) is not str or not _IDENTIFIER_PATTERN.fullmatch(value):
        _fail(f"{context} must be a safe identifier")
    return value


def _sha256(value: object, context: str) -> str:
    if type(value) is not str or not _SHA256_PATTERN.fullmatch(value):
        _fail(f"{context} must be a lowercase SHA-256")
    return value


def _validate_binding(payload: object) -> dict[str, object]:
    result = _closed(payload, _BINDING_FIELDS, "binding")
    if result["schema_version"] != BASE_CAD_BINDING_SCHEMA_VERSION:
        _fail("binding.schema_version is unsupported")
    _identifier(result["run_id"], "binding.run_id")
    for field in (
        "source_bundle_sha256",
        "source_custody_sha256",
        "source_fusion_sha256",
        "inspection_sha256",
        "target_drawing_sha256",
    ):
        _sha256(result[field], f"binding.{field}")

    base_source = _closed(result["base_source"], _BASE_SOURCE_FIELDS, "binding.base_source")
    _identifier(base_source["source_id"], "binding.base_source.source_id")
    _sha256(base_source["sha256"], "binding.base_source.sha256")
    _identifier(base_source["revision"], "binding.base_source.revision")
    _identifier(result["inspection_id"], "binding.inspection_id")

    component_ids = result["eligible_component_ids"]
    if type(component_ids) is not list or not component_ids:
        _fail("binding.eligible_component_ids must be a non-empty list")
    normalized_ids = [_identifier(item, "binding.eligible_component_ids") for item in component_ids]
    if len(set(normalized_ids)) != len(normalized_ids):
        _fail("binding.eligible_component_ids must be duplicate-free")
    if result["transform_policy"] != _TRANSFORM_POLICY:
        _fail("binding.transform_policy is unsupported")
    if result["state"] != "READY_FOR_SELECTION":
        _fail("binding.state is not ready for selection")

    result["base_source"] = base_source
    result["eligible_component_ids"] = sorted(normalized_ids)
    return deepcopy(result)


def validate_base_cad_binding(payload: object) -> dict[str, object]:
    """Validate and return a detached normalized Base-CAD binding."""
    return _validate_binding(payload)


def base_cad_binding_sha256(payload: object) -> str:
    """Hash only the validated normalized binding through the canonical owner."""
    return canonical_json_sha256(_validate_binding(payload))


__all__ = [
    "BASE_CAD_BINDING_SCHEMA_VERSION",
    "BaseCadAdapterError",
    "base_cad_binding_sha256",
    "validate_base_cad_binding",
]
