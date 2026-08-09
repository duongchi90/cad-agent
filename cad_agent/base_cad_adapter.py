"""Closed, context-free Base-CAD binding and identity kernel."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import importlib
import math
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
BASE_CAD_REUSE_HANDOFF_SCHEMA_VERSION = "base-cad-reuse-handoff-1.0"
_HANDOFF_FIELDS = frozenset(
    {
        "schema_version", "run_id", "source_bundle_sha256", "source_custody_sha256",
        "source_fusion_sha256", "base_cad_binding_sha256", "inspection_sha256",
        "extraction_plan_sha256", "base_source", "candidate_input_sha256",
        "candidate_output_sha256", "live_preflight_evidence_sha256", "components",
        "source_handle_to_candidate_handle",
    }
)
_HANDOFF_SOURCE_FIELDS = frozenset({"source_id", "sha256", "revision"})
_HANDOFF_COMPONENT_FIELDS = frozenset(
    {
        "logical_component_id", "source_handle", "source_layer", "source_block",
        "source_sha256", "source_revision", "candidate_handle", "transform", "provenance",
    }
)
_HANDOFF_TRANSFORM_FIELDS = frozenset({"rotation_degrees", "translation", "uniform_scale"})
_HANDOFF_POINT_FIELDS = frozenset({"x", "y", "z"})
_HANDOFF_MAP_FIELDS = frozenset({"source_handle", "candidate_handle"})


def _s3a_contract():
    return importlib.import_module("mcp_integration_lib.exact_base_xref")


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


def _handoff_number(value: object, context: str) -> int | float:
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        _fail(f"{context} must be a finite JSON number")
    if type(value) is float and value == 0.0:
        return 0.0
    return value


def _handoff_text(value: object, context: str) -> str:
    if type(value) is not str or not value or len(value) > 512:
        _fail(f"{context} must be a bounded non-empty string")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        _fail(f"{context} contains a control character")
    return value


def _validate_handoff_transform(value: object, context: str) -> dict[str, object]:
    result = _closed(value, _HANDOFF_TRANSFORM_FIELDS, context)
    result["rotation_degrees"] = _handoff_number(
        result["rotation_degrees"], f"{context}.rotation_degrees"
    )
    point = _closed(
        result["translation"], _HANDOFF_POINT_FIELDS, f"{context}.translation"
    )
    for axis in ("x", "y", "z"):
        point[axis] = _handoff_number(point[axis], f"{context}.translation.{axis}")
    result["uniform_scale"] = _handoff_number(
        result["uniform_scale"], f"{context}.uniform_scale"
    )
    result["translation"] = point
    return result


def _validate_reuse_handoff(payload: object) -> dict[str, object]:
    result = _closed(payload, _HANDOFF_FIELDS, "reuse handoff")
    if result["schema_version"] != BASE_CAD_REUSE_HANDOFF_SCHEMA_VERSION:
        _fail("reuse handoff.schema_version is unsupported")
    _identifier(result["run_id"], "reuse handoff.run_id")
    for field in (
        "source_bundle_sha256", "source_custody_sha256", "source_fusion_sha256",
        "base_cad_binding_sha256", "inspection_sha256", "extraction_plan_sha256",
        "candidate_input_sha256", "candidate_output_sha256", "live_preflight_evidence_sha256",
    ):
        _sha256(result[field], f"reuse handoff.{field}")

    source = _closed(result["base_source"], _HANDOFF_SOURCE_FIELDS, "reuse handoff.base_source")
    _identifier(source["source_id"], "reuse handoff.base_source.source_id")
    _sha256(source["sha256"], "reuse handoff.base_source.sha256")
    _identifier(source["revision"], "reuse handoff.base_source.revision")

    components = result["components"]
    if type(components) is not list or not components:
        _fail("reuse handoff.components must be a non-empty list")
    normalized_components = []
    seen_ids: set[str] = set()
    components_by_source: dict[str, dict[str, object]] = {}
    candidates_by_handle: set[str] = set()
    layer_block_pairs: set[tuple[str, str]] = set()
    for index, item in enumerate(components):
        context = f"reuse handoff.components[{index}]"
        component = _closed(item, _HANDOFF_COMPONENT_FIELDS, context)
        logical_id = _identifier(component["logical_component_id"], f"{context}.logical_component_id")
        source_handle = _identifier(component["source_handle"], f"{context}.source_handle")
        logical_key = logical_id.casefold()
        source_key = source_handle.casefold()
        if logical_key in seen_ids or source_key in components_by_source:
            _fail("reuse handoff components must have unique logical IDs and source handles")
        seen_ids.add(logical_key)
        component["source_layer"] = _handoff_text(
            component["source_layer"], f"{context}.source_layer"
        )
        component["source_block"] = _handoff_text(
            component["source_block"], f"{context}.source_block"
        )
        layer_block_key = (
            component["source_layer"].casefold(), component["source_block"].casefold()
        )
        if layer_block_key in layer_block_pairs:
            _fail("reuse handoff components must have unique source layer/block pairs")
        layer_block_pairs.add(layer_block_key)
        candidate_handle = _identifier(component["candidate_handle"], f"{context}.candidate_handle")
        candidate_key = candidate_handle.casefold()
        if candidate_key in candidates_by_handle:
            _fail("reuse handoff components must have unique candidate handles")
        candidates_by_handle.add(candidate_key)
        _sha256(component["source_sha256"], f"{context}.source_sha256")
        _identifier(component["source_revision"], f"{context}.source_revision")
        if component["source_sha256"] != source["sha256"]:
            _fail(f"{context}.source_sha256 does not match reuse handoff.base_source")
        if component["source_revision"] != source["revision"]:
            _fail(f"{context}.source_revision does not match reuse handoff.base_source")
        if component["provenance"] != "REUSED_FROM_BASE_CAD":
            _fail(f"{context}.provenance is unsupported")
        component["transform"] = _validate_handoff_transform(component["transform"], f"{context}.transform")
        components_by_source[source_key] = component
        normalized_components.append(component)
    normalized_components.sort(key=lambda item: item["logical_component_id"])

    mappings = result["source_handle_to_candidate_handle"]
    if type(mappings) is not list or len(mappings) != len(normalized_components):
        _fail("reuse handoff handle mapping must cover every component")
    normalized_mappings_by_source: dict[str, dict[str, str]] = {}
    mapped_candidates: set[str] = set()
    for index, item in enumerate(mappings):
        mapping = _closed(item, _HANDOFF_MAP_FIELDS, f"reuse handoff mapping[{index}]")
        mapping_source = _identifier(
            mapping["source_handle"], f"reuse handoff mapping[{index}].source_handle"
        )
        mapping_candidate = _identifier(
            mapping["candidate_handle"], f"reuse handoff mapping[{index}].candidate_handle"
        )
        source_key = mapping_source.casefold()
        candidate_key = mapping_candidate.casefold()
        component = components_by_source.get(source_key)
        if component is None or source_key in normalized_mappings_by_source:
            _fail("reuse handoff handle mappings must be unique and cover components")
        if component["candidate_handle"].casefold() != candidate_key:
            _fail("reuse handoff mapping does not match component candidate handle")
        if candidate_key in mapped_candidates:
            _fail("reuse handoff candidate mappings must be one-to-one")
        mapped_candidates.add(candidate_key)
        normalized_mappings_by_source[source_key] = {
            "source_handle": component["source_handle"],
            "candidate_handle": component["candidate_handle"],
        }
    if set(normalized_mappings_by_source) != set(components_by_source):
        _fail("reuse handoff handle mapping does not match components")
    normalized_mappings = sorted(
        normalized_mappings_by_source.values(), key=lambda item: item["source_handle"].casefold()
    )
    result["base_source"] = source
    result["components"] = normalized_components
    result["source_handle_to_candidate_handle"] = normalized_mappings
    return deepcopy(result)


def validate_base_cad_reuse_handoff(payload: object) -> dict[str, object]:
    """Validate and return a detached deterministic frozen reuse handoff."""
    return _validate_reuse_handoff(payload)


def base_cad_reuse_handoff_sha256(payload: object) -> str:
    """Hash only a validated handoff through the canonical JSON owner."""
    return canonical_json_sha256(_validate_reuse_handoff(payload))


def evaluate_frozen_base_cad_reuse(
    *, handoff: object, current_live_inspection: object
) -> dict[str, object]:
    """Classify frozen reuse against validated S3A inspection evidence."""
    normalized = _validate_reuse_handoff(handoff)
    try:
        current_inspection = _s3a_contract().validate_xref_inspection(current_live_inspection)
    except Exception as exc:
        raise BaseCadAdapterError("current live S3A inspection is invalid") from exc

    current = current_inspection["base_source"]
    current_components = {
        item["source_handle"].casefold(): item for item in current_inspection["components"]
    }
    for component in normalized["components"]:
        live_component = current_components.get(component["source_handle"].casefold())
        if live_component is None:
            _fail("reuse handoff component is absent from current live S3A inspection")
        if (
            live_component["source_layer"] != component["source_layer"]
            or live_component["source_block"] != component["source_block"]
        ):
            _fail("reuse handoff component layer/block does not match current S3A inspection")

    previous = normalized["base_source"]
    reason_codes = []
    if current["source_id"] != previous["source_id"]:
        reason_codes.append("SOURCE_ID_CHANGED")
    if current["sha256"] != previous["sha256"]:
        reason_codes.append("SOURCE_SHA256_CHANGED")
    if current["revision"] != previous["revision"]:
        reason_codes.append("SOURCE_REVISION_CHANGED")
    reason_codes.sort()
    state = "CURRENT" if not reason_codes else "STALE_REEXTRACTION_REQUIRED"
    affected = [] if state == "CURRENT" else sorted(
        item["logical_component_id"] for item in normalized["components"]
    )
    return {
        "state": state,
        "prior_handoff_sha256": base_cad_reuse_handoff_sha256(normalized),
        "affected_component_ids": affected,
        "previous_source": deepcopy(previous),
        "current_source": deepcopy(current),
    }


def build_proposed_base_cad_extraction(
    *,
    plan_id: str,
    inspection: object,
    selections: object,
    impacted_views: object | None = None,
) -> dict[str, object]:
    """Build an S3A-owned proposed extraction plan without approving or executing it."""
    try:
        exact_base_xref = _s3a_contract()
        validated_inspection = exact_base_xref.validate_xref_inspection(inspection)
        return deepcopy(
            exact_base_xref.build_extraction_plan(
                plan_id=plan_id,
                inspection=validated_inspection,
                selections=selections,
                impacted_views=impacted_views,
                approval_status="PROPOSED",
                approval_reference=None,
            )
        )
    except BaseCadAdapterError:
        raise
    except Exception as exc:
        raise BaseCadAdapterError("proposed extraction plan is invalid") from exc


def require_approved_base_cad_extraction_match(
    *,
    approved_plan: object,
    proposed_plan: object,
    inspection: object,
) -> dict[str, object]:
    """Require an explicit S3A-approved plan matching the prior proposal exactly."""
    try:
        exact_base_xref = _s3a_contract()
        validated_inspection = exact_base_xref.validate_xref_inspection(inspection)
        proposed = exact_base_xref.validate_extraction_plan(
            proposed_plan, inspection=validated_inspection
        )
        approved = exact_base_xref.validate_extraction_plan(
            approved_plan, inspection=validated_inspection
        )
    except Exception as exc:
        raise BaseCadAdapterError("approved extraction plan is invalid") from exc

    if approved["approval"]["status"] != "APPROVED":
        raise BaseCadAdapterError("approved extraction plan lacks explicit approval")
    if approved["approval"]["reference"] is None:
        raise BaseCadAdapterError("approved extraction plan lacks approval reference")

    proposed_identity = {key: value for key, value in proposed.items() if key != "approval"}
    approved_identity = {key: value for key, value in approved.items() if key != "approval"}
    if approved_identity != proposed_identity:
        raise BaseCadAdapterError("approved extraction plan does not match proposal")
    return deepcopy(approved)


__all__ = [
    "BASE_CAD_BINDING_SCHEMA_VERSION",
    "BASE_CAD_REUSE_HANDOFF_SCHEMA_VERSION",
    "BaseCadAdapterError",
    "base_cad_binding_sha256",
    "base_cad_reuse_handoff_sha256",
    "build_proposed_base_cad_extraction",
    "evaluate_frozen_base_cad_reuse",
    "require_approved_base_cad_extraction_match",
    "validate_base_cad_reuse_handoff",
    "validate_base_cad_binding",
]
