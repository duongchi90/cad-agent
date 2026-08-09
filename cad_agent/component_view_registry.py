"""Deterministic Task-1 Component/View Registry core."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import re

from cad_agent import base_cad_adapter as _base_cad
from cad_agent import source_fusion as _source_fusion
from cad_agent.drawing_contracts import canonical_json_sha256


COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION = "component-view-registry-1.0"

_CONTEXT_FIELDS = frozenset(
    {
        "source_fusion",
        "source_fusion_sha256",
        "reuse_handoff",
        "reuse_handoff_sha256",
        "reuse_evaluation",
        "current_live_inspection",
        "candidate",
    }
)
_CANDIDATE_FIELDS = frozenset({"candidate_id", "candidate_drawing_sha256"})
_INPUT_COMPONENT_FIELDS = frozenset(
    {
        "component_type",
        "origin_class",
        "source_projection_refs",
        "semantic_projection_refs",
        "base_cad_provenance_ref",
        "candidate_entity_bindings",
    }
)
_REQUIRED_INPUT_COMPONENT_FIELDS = frozenset(
    {
        "component_type",
        "origin_class",
        "source_projection_refs",
        "semantic_projection_refs",
        "candidate_entity_bindings",
    }
)
_OUTPUT_COMPONENT_FIELDS = frozenset(
    {
        "component_id",
        "component_type",
        "origin_class",
        "source_projection_refs",
        "semantic_projection_refs",
        "base_cad_provenance_ref",
        "view_ids",
        "candidate_entity_bindings",
    }
)
_BINDING_FIELDS = frozenset(
    {
        "target_namespace",
        "candidate_id",
        "entity_handle",
        "block_name",
        "legacy_uuid",
        "relative_path",
        "captured_at_utc",
    }
)
_ROOT_FIELDS = frozenset(
    {
        "schema_version",
        "upstream_bindings",
        "components",
        "views",
        "links",
        "registry_snapshot_sha256",
    }
)
_UPSTREAM_BINDING_FIELDS = frozenset(
    {
        "source_bundle_sha256",
        "source_custody_sha256",
        "source_fusion_sha256",
        "reuse_handoff_sha256",
        "candidate_id",
        "candidate_drawing_sha256",
        "base_source",
    }
)
_BASE_SOURCE_FIELDS = frozenset({"source_id", "sha256", "revision"})
_ORIGIN_CLASSES = frozenset(
    {
        "REUSED_UNCHANGED",
        "RECONSTRUCTED_CHANGED",
        "RECONSTRUCTED_NEW",
        "MIXED_UNRESOLVED",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class ComponentViewRegistryError(ValueError):
    """Raised when registry evidence is malformed, foreign, or stale."""


def _fail(code: str) -> None:
    raise ComponentViewRegistryError(code)


def _mapping(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(code)
    if any(type(key) is not str for key in value):
        _fail(code)
    return dict(value)


def _closed(value: object, fields: frozenset[str], code: str) -> dict[str, object]:
    result = _mapping(value, code)
    if set(result) != fields:
        _fail(code)
    return result


def _closed_optional(
    value: object,
    *,
    required: frozenset[str],
    allowed: frozenset[str],
    code: str,
) -> dict[str, object]:
    result = _mapping(value, code)
    keys = set(result)
    if not required.issubset(keys) or not keys.issubset(allowed):
        _fail(code)
    return result


def _identifier(value: object, code: str) -> str:
    if type(value) is not str or _IDENTIFIER_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _sha256(value: object, code: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _text(value: object, code: str) -> str:
    if type(value) is not str or not value or len(value) > 1024:
        _fail(code)
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        _fail(code)
    return value


def _sha_list(value: object, code: str) -> list[str]:
    if type(value) is not list or not value:
        _fail(code)
    normalized = [_sha256(item, code) for item in value]
    if len(normalized) != len(set(normalized)):
        _fail(code)
    return sorted(normalized)


def _stable_binding_material(binding: object) -> dict[str, object]:
    record = _mapping(binding, "SOURCE_PROJECTION_INVALID")
    kind = record.get("provenance_kind")
    common = {
        "provenance_kind": kind,
        "source_id": record.get("source_id"),
        "observed_source_sha256": record.get("observed_source_sha256"),
        "numeric_policy_version": record.get("numeric_policy_version"),
    }
    if kind == "PDF_RENDER":
        common.update(
            {
                "pdf_page_index": record.get("pdf_page_index"),
                "box_kind": record.get("box_kind"),
                "selected_box": deepcopy(record.get("selected_box")),
                "rotation": record.get("rotation"),
                "user_unit": deepcopy(record.get("user_unit")),
            }
        )
    elif kind != "DIRECT_IMAGE":
        _fail("SOURCE_PROJECTION_INVALID")
    return common


def _stable_content(value: object) -> dict[str, object]:
    content = _mapping(value, "SOURCE_PROJECTION_INVALID")
    return {
        key: deepcopy(item)
        for key, item in content.items()
        if key not in {"confidence", "primitive_observation_keys"}
    }


def _projection_indexes(
    fusion: dict[str, object],
) -> tuple[dict[str, str], dict[str, str]]:
    primitive_records = fusion["primitive_observations"]
    semantic_records = fusion["semantic_observations"]
    if type(primitive_records) is not list or type(semantic_records) is not list:
        _fail("SOURCE_FUSION_INVALID")

    primitive_fingerprints: dict[str, str] = {}
    for value in primitive_records:
        record = _mapping(value, "SOURCE_PROJECTION_INVALID")
        key = _sha256(record.get("observation_key"), "SOURCE_PROJECTION_INVALID")
        material = {
            "identity_kind": "r3-stable-primitive-membership-v1",
            "numeric_policy_version": record.get("numeric_policy_version"),
            "source": _stable_binding_material(record.get("source_binding")),
            "content": _stable_content(record.get("content")),
            "occurrence_count": record.get("occurrence_count"),
        }
        primitive_fingerprints[key] = canonical_json_sha256(material)

    semantic_fingerprints: dict[str, str] = {}
    for value in semantic_records:
        record = _mapping(value, "SEMANTIC_PROJECTION_INVALID")
        key = _sha256(record.get("observation_key"), "SEMANTIC_PROJECTION_INVALID")
        raw_primitive_keys = record.get("primitive_observation_keys")
        if type(raw_primitive_keys) is not list or not raw_primitive_keys:
            _fail("SEMANTIC_PROJECTION_INVALID")
        membership: list[str] = []
        for raw_key in raw_primitive_keys:
            primitive_key = _sha256(raw_key, "SEMANTIC_PROJECTION_INVALID")
            fingerprint = primitive_fingerprints.get(primitive_key)
            if fingerprint is None:
                _fail("SEMANTIC_PROJECTION_INVALID")
            membership.append(fingerprint)
        material = {
            "identity_kind": "r3-stable-semantic-membership-v1",
            "numeric_policy_version": record.get("numeric_policy_version"),
            "content": _stable_content(record.get("content")),
            "primitive_membership": sorted(membership),
        }
        semantic_fingerprints[key] = canonical_json_sha256(material)

    return primitive_fingerprints, semantic_fingerprints


def _upstream_context(upstream_context: object) -> dict[str, object]:
    context = _closed(upstream_context, _CONTEXT_FIELDS, "UPSTREAM_CONTEXT_INVALID")
    try:
        fusion = _source_fusion.validate_source_fusion_packet(context["source_fusion"])
        fusion_sha256 = _source_fusion.source_fusion_sha256(fusion)
    except Exception as exc:
        raise ComponentViewRegistryError("SOURCE_FUSION_INVALID") from exc
    if fusion.get("status") != "READY":
        _fail("SOURCE_FUSION_NOT_READY")
    if _sha256(context["source_fusion_sha256"], "SOURCE_FUSION_HASH_INVALID") != fusion_sha256:
        _fail("SOURCE_FUSION_HASH_MISMATCH")

    try:
        handoff = _base_cad.validate_base_cad_reuse_handoff(context["reuse_handoff"])
        handoff_sha256 = _base_cad.base_cad_reuse_handoff_sha256(handoff)
    except Exception as exc:
        raise ComponentViewRegistryError("REUSE_HANDOFF_INVALID") from exc
    if _sha256(context["reuse_handoff_sha256"], "REUSE_HANDOFF_HASH_INVALID") != handoff_sha256:
        _fail("REUSE_HANDOFF_HASH_MISMATCH")
    if handoff["source_bundle_sha256"] != fusion["source_bundle_sha256"]:
        _fail("R1_R2_LINEAGE_MISMATCH")
    if handoff["source_custody_sha256"] != fusion["source_custody_sha256"]:
        _fail("R1_R2_LINEAGE_MISMATCH")
    if handoff["source_fusion_sha256"] != fusion_sha256:
        _fail("R1_R2_LINEAGE_MISMATCH")

    candidate = _closed(context["candidate"], _CANDIDATE_FIELDS, "CANDIDATE_INVALID")
    candidate_id = _identifier(candidate["candidate_id"], "CANDIDATE_INVALID")
    candidate_sha256 = _sha256(
        candidate["candidate_drawing_sha256"], "CANDIDATE_INVALID"
    )
    if candidate_sha256 != handoff["candidate_output_sha256"]:
        _fail("CANDIDATE_OUTPUT_MISMATCH")

    try:
        evaluation = _base_cad.evaluate_frozen_base_cad_reuse(
            handoff=handoff,
            current_live_inspection=context["current_live_inspection"],
        )
    except Exception as exc:
        raise ComponentViewRegistryError("REUSE_CURRENTNESS_INVALID") from exc
    supplied_evaluation = _mapping(
        context["reuse_evaluation"], "REUSE_CURRENTNESS_INVALID"
    )
    if supplied_evaluation != evaluation:
        _fail("REUSE_CURRENTNESS_MISMATCH")
    if evaluation.get("state") != "CURRENT":
        _fail("REUSE_STALE")

    base_source = _closed(handoff["base_source"], _BASE_SOURCE_FIELDS, "BASE_SOURCE_INVALID")
    upstream_bindings = {
        "source_bundle_sha256": fusion["source_bundle_sha256"],
        "source_custody_sha256": fusion["source_custody_sha256"],
        "source_fusion_sha256": fusion_sha256,
        "reuse_handoff_sha256": handoff_sha256,
        "candidate_id": candidate_id,
        "candidate_drawing_sha256": candidate_sha256,
        "base_source": deepcopy(base_source),
    }
    primitive_index, semantic_index = _projection_indexes(fusion)
    return {
        "fusion": fusion,
        "handoff": handoff,
        "upstream_bindings": upstream_bindings,
        "primitive_index": primitive_index,
        "semantic_index": semantic_index,
    }


def _base_reference(
    value: object,
    *,
    handoff: dict[str, object],
    required: bool,
) -> dict[str, object] | None:
    if value is None:
        if required:
            _fail("BASE_PROVENANCE_REQUIRED")
        return None
    candidate = _mapping(value, "BASE_PROVENANCE_INVALID")
    for accepted in handoff["components"]:
        if candidate == accepted:
            return deepcopy(accepted)
    _fail("BASE_PROVENANCE_MISMATCH")


def _candidate_bindings(
    value: object,
    *,
    candidate_id: str,
    origin_class: str,
    base_reference: dict[str, object] | None,
) -> list[dict[str, object]]:
    if type(value) is not list:
        _fail("CANDIDATE_BINDINGS_INVALID")
    normalized: list[dict[str, object]] = []
    seen_handles: set[str] = set()
    for raw in value:
        binding = _closed(raw, _BINDING_FIELDS, "CANDIDATE_BINDING_INVALID")
        if binding["target_namespace"] != "CANDIDATE":
            _fail("CANDIDATE_NAMESPACE_INVALID")
        if _identifier(binding["candidate_id"], "CANDIDATE_BINDING_INVALID") != candidate_id:
            _fail("CANDIDATE_ID_MISMATCH")
        entity_handle = _identifier(
            binding["entity_handle"], "CANDIDATE_BINDING_INVALID"
        )
        if entity_handle.casefold() in seen_handles:
            _fail("DUPLICATE_CANDIDATE_BINDING")
        seen_handles.add(entity_handle.casefold())
        normalized.append(
            {
                "target_namespace": "CANDIDATE",
                "candidate_id": candidate_id,
                "entity_handle": entity_handle,
                "block_name": _text(binding["block_name"], "CANDIDATE_BINDING_INVALID"),
                "legacy_uuid": _text(binding["legacy_uuid"], "CANDIDATE_BINDING_INVALID"),
                "relative_path": _text(
                    binding["relative_path"], "CANDIDATE_BINDING_INVALID"
                ),
                "captured_at_utc": _text(
                    binding["captured_at_utc"], "CANDIDATE_BINDING_INVALID"
                ),
            }
        )

    if origin_class == "REUSED_UNCHANGED":
        if base_reference is None or len(normalized) != 1:
            _fail("REUSED_BINDING_INVALID")
        binding = normalized[0]
        if binding["entity_handle"].casefold() != str(
            base_reference["candidate_handle"]
        ).casefold():
            _fail("CANDIDATE_BINDING_MISMATCH")
        if binding["block_name"] != base_reference["source_block"]:
            _fail("CANDIDATE_BINDING_MISMATCH")
        if binding["entity_handle"].casefold() == str(
            base_reference["source_handle"]
        ).casefold():
            _fail("SOURCE_TARGET_CONFUSION")
    elif normalized:
        _fail("UNPROVEN_CANDIDATE_BINDING")

    normalized.sort(
        key=lambda item: (
            item["candidate_id"],
            item["entity_handle"].casefold(),
            item["block_name"],
            item["legacy_uuid"],
            item["relative_path"],
            item["captured_at_utc"],
        )
    )
    return normalized


def _component_identity(
    *,
    component_type: str,
    origin_class: str,
    source_refs: list[str],
    semantic_refs: list[str],
    primitive_index: dict[str, str],
    semantic_index: dict[str, str],
    base_source: dict[str, object] | None,
) -> str:
    source_membership: list[str] = []
    for ref in source_refs:
        fingerprint = primitive_index.get(ref)
        if fingerprint is None:
            _fail("FOREIGN_SOURCE_PROJECTION")
        source_membership.append(fingerprint)

    semantic_membership: list[str] = []
    for ref in semantic_refs:
        fingerprint = semantic_index.get(ref)
        if fingerprint is None:
            _fail("FOREIGN_SEMANTIC_PROJECTION")
        semantic_membership.append(fingerprint)

    material: dict[str, object] = {
        "identity_kind": "r3-component-v1",
        "schema_version": COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION,
        "component_type": component_type,
        "origin_class": origin_class,
        "source_membership": sorted(source_membership),
        "semantic_membership": sorted(semantic_membership),
    }
    if base_source is not None:
        material["base_source"] = deepcopy(base_source)
    return canonical_json_sha256(material)


def _normalize_input_component(
    value: object,
    *,
    state: dict[str, object],
) -> dict[str, object]:
    component = _closed_optional(
        value,
        required=_REQUIRED_INPUT_COMPONENT_FIELDS,
        allowed=_INPUT_COMPONENT_FIELDS,
        code="COMPONENT_FIELDS_INVALID",
    )
    component_type = _identifier(component["component_type"], "COMPONENT_TYPE_INVALID")
    origin_class = component["origin_class"]
    if origin_class not in _ORIGIN_CLASSES:
        _fail("ORIGIN_CLASS_INVALID")

    source_refs = _sha_list(
        component["source_projection_refs"], "SOURCE_PROJECTION_REFS_INVALID"
    )
    semantic_refs = _sha_list(
        component["semantic_projection_refs"], "SEMANTIC_PROJECTION_REFS_INVALID"
    )

    raw_base_reference = component.get("base_cad_provenance_ref")
    base_reference = _base_reference(
        raw_base_reference,
        handoff=state["handoff"],
        required=origin_class == "REUSED_UNCHANGED",
    )
    if origin_class == "RECONSTRUCTED_NEW" and base_reference is not None:
        _fail("RECONSTRUCTED_NEW_PROVENANCE_INVALID")

    candidate_id = state["upstream_bindings"]["candidate_id"]
    bindings = _candidate_bindings(
        component["candidate_entity_bindings"],
        candidate_id=candidate_id,
        origin_class=origin_class,
        base_reference=base_reference,
    )

    identity_base_source = (
        state["upstream_bindings"]["base_source"]
        if base_reference is not None
        else None
    )
    component_id = _component_identity(
        component_type=component_type,
        origin_class=origin_class,
        source_refs=source_refs,
        semantic_refs=semantic_refs,
        primitive_index=state["primitive_index"],
        semantic_index=state["semantic_index"],
        base_source=identity_base_source,
    )
    return {
        "component_id": component_id,
        "component_type": component_type,
        "origin_class": origin_class,
        "source_projection_refs": source_refs,
        "semantic_projection_refs": semantic_refs,
        "base_cad_provenance_ref": base_reference,
        "view_ids": [],
        "candidate_entity_bindings": bindings,
    }


def _normalize_components(
    components: object,
    *,
    state: dict[str, object],
) -> list[dict[str, object]]:
    if type(components) is not list or not components:
        _fail("COMPONENTS_INVALID")
    normalized = [
        _normalize_input_component(component, state=state) for component in components
    ]
    ids = [str(component["component_id"]) for component in normalized]
    if len(ids) != len(set(ids)):
        _fail("DUPLICATE_COMPONENT")
    target_owners: dict[str, str] = {}
    for component in normalized:
        component_id = str(component["component_id"])
        for binding in component["candidate_entity_bindings"]:
            handle = str(binding["entity_handle"]).casefold()
            owner = target_owners.get(handle)
            if owner is not None and owner != component_id:
                _fail("DUPLICATE_TARGET_OWNER")
            target_owners[handle] = component_id
    normalized.sort(key=lambda component: str(component["component_id"]))
    return normalized


def _snapshot_material(
    *,
    upstream_bindings: dict[str, object],
    components: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION,
        "upstream_bindings": deepcopy(upstream_bindings),
        "components": deepcopy(components),
        "views": [],
        "links": [],
    }


def build_component_view_registry(
    *, upstream_context: object, components: object
) -> dict[str, object]:
    """Build a detached deterministic Task-1 registry snapshot."""
    state = _upstream_context(upstream_context)
    normalized_components = _normalize_components(components, state=state)
    material = _snapshot_material(
        upstream_bindings=state["upstream_bindings"],
        components=normalized_components,
    )
    result = deepcopy(material)
    result["registry_snapshot_sha256"] = canonical_json_sha256(material)
    return result


def _validate_output_component(
    value: object,
    *,
    state: dict[str, object],
) -> dict[str, object]:
    component = _closed(value, _OUTPUT_COMPONENT_FIELDS, "COMPONENT_FIELDS_INVALID")
    if component["view_ids"] != []:
        _fail("TASK1_VIEW_IDS_INVALID")
    input_component = {
        "component_type": component["component_type"],
        "origin_class": component["origin_class"],
        "source_projection_refs": component["source_projection_refs"],
        "semantic_projection_refs": component["semantic_projection_refs"],
        "base_cad_provenance_ref": component["base_cad_provenance_ref"],
        "candidate_entity_bindings": component["candidate_entity_bindings"],
    }
    normalized = _normalize_input_component(input_component, state=state)
    supplied_id = _sha256(component["component_id"], "COMPONENT_ID_INVALID")
    if supplied_id != normalized["component_id"]:
        _fail("COMPONENT_ID_MISMATCH")
    return normalized


def validate_component_view_registry(
    payload: object, *, upstream_context: object
) -> dict[str, object]:
    """Validate and detach a Task-1 registry snapshot."""
    state = _upstream_context(upstream_context)
    registry = _closed(payload, _ROOT_FIELDS, "REGISTRY_FIELDS_INVALID")
    if registry["schema_version"] != COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION:
        _fail("REGISTRY_SCHEMA_INVALID")
    if registry["views"] != []:
        _fail("TASK1_VIEWS_INVALID")
    if registry["links"] != []:
        _fail("TASK1_LINKS_INVALID")

    upstream_bindings = _closed(
        registry["upstream_bindings"],
        _UPSTREAM_BINDING_FIELDS,
        "UPSTREAM_BINDINGS_INVALID",
    )
    if upstream_bindings != state["upstream_bindings"]:
        _fail("UPSTREAM_BINDINGS_MISMATCH")

    raw_components = registry["components"]
    if type(raw_components) is not list or not raw_components:
        _fail("COMPONENTS_INVALID")
    components = [
        _validate_output_component(component, state=state) for component in raw_components
    ]
    ids = [str(component["component_id"]) for component in components]
    if len(ids) != len(set(ids)):
        _fail("DUPLICATE_COMPONENT")
    components.sort(key=lambda component: str(component["component_id"]))

    material = _snapshot_material(
        upstream_bindings=state["upstream_bindings"],
        components=components,
    )
    supplied_snapshot = _sha256(
        registry["registry_snapshot_sha256"], "REGISTRY_SNAPSHOT_INVALID"
    )
    expected_snapshot = canonical_json_sha256(material)
    if supplied_snapshot != expected_snapshot:
        _fail("REGISTRY_SNAPSHOT_MISMATCH")

    result = deepcopy(material)
    result["registry_snapshot_sha256"] = expected_snapshot
    return result


def component_view_registry_sha256(
    payload: object, *, upstream_context: object
) -> str:
    """Return the canonical seal of a validated registry snapshot."""
    normalized = validate_component_view_registry(
        payload, upstream_context=upstream_context
    )
    return str(normalized["registry_snapshot_sha256"])


__all__ = [
    "COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION",
    "ComponentViewRegistryError",
    "build_component_view_registry",
    "validate_component_view_registry",
    "component_view_registry_sha256",
]
