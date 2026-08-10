"""Deterministic Component/View Registry core."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import re

from cad_agent import base_cad_adapter as _base_cad
from cad_agent import drawing_artifact_reference as _dara
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
_INPUT_VIEW_FIELDS = frozenset(
    {
        "view_role",
        "component_ids",
        "source_projection_refs",
        "semantic_projection_refs",
        "candidate_entity_bindings",
        "layout_bindings",
    }
)
_OUTPUT_VIEW_FIELDS = frozenset({"view_id", *_INPUT_VIEW_FIELDS})
_LAYOUT_BINDING_FIELDS = frozenset(
    {
        "layout_id",
        "display_name",
        "legacy_uuid",
        "relative_path",
        "captured_at_utc",
    }
)
_LINK_FIELDS = frozenset(
    {
        "link_id",
        "relation_type",
        "source_id",
        "target_id",
        "evidence_refs",
    }
)
_RELATION_TYPES = frozenset(
    {
        "COMPONENT_HAS_VIEW",
        "VIEWS_SHARE_COMPONENT",
        "VIEWS_SHARE_PARAMETER_EVIDENCE",
        "VIEW_PRESENTED_ON_LAYOUT",
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


def _closed(
    value: object, fields: frozenset[str], code: str
) -> dict[str, object]:
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


def _sha_list_allow_empty(value: object, code: str) -> list[str]:
    if type(value) is not list:
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
        key = _sha256(
            record.get("observation_key"), "SOURCE_PROJECTION_INVALID"
        )
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
        key = _sha256(
            record.get("observation_key"), "SEMANTIC_PROJECTION_INVALID"
        )
        raw_primitive_keys = record.get("primitive_observation_keys")
        if type(raw_primitive_keys) is not list or not raw_primitive_keys:
            _fail("SEMANTIC_PROJECTION_INVALID")
        membership: list[str] = []
        for raw_key in raw_primitive_keys:
            primitive_key = _sha256(
                raw_key, "SEMANTIC_PROJECTION_INVALID"
            )
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
    context = _closed(
        upstream_context, _CONTEXT_FIELDS, "UPSTREAM_CONTEXT_INVALID"
    )
    try:
        fusion = _source_fusion.validate_source_fusion_packet(
            context["source_fusion"]
        )
        fusion_sha256 = _source_fusion.source_fusion_sha256(fusion)
    except Exception as exc:
        raise ComponentViewRegistryError("SOURCE_FUSION_INVALID") from exc
    if fusion.get("status") != "READY":
        _fail("SOURCE_FUSION_NOT_READY")
    supplied_fusion_sha256 = _sha256(
        context["source_fusion_sha256"], "SOURCE_FUSION_HASH_INVALID"
    )
    if supplied_fusion_sha256 != fusion_sha256:
        _fail("SOURCE_FUSION_HASH_MISMATCH")

    try:
        handoff = _base_cad.validate_base_cad_reuse_handoff(
            context["reuse_handoff"]
        )
        handoff_sha256 = _base_cad.base_cad_reuse_handoff_sha256(handoff)
    except Exception as exc:
        raise ComponentViewRegistryError("REUSE_HANDOFF_INVALID") from exc
    supplied_handoff_sha256 = _sha256(
        context["reuse_handoff_sha256"], "REUSE_HANDOFF_HASH_INVALID"
    )
    if supplied_handoff_sha256 != handoff_sha256:
        _fail("REUSE_HANDOFF_HASH_MISMATCH")
    if handoff["source_bundle_sha256"] != fusion["source_bundle_sha256"]:
        _fail("R1_R2_LINEAGE_MISMATCH")
    if handoff["source_custody_sha256"] != fusion["source_custody_sha256"]:
        _fail("R1_R2_LINEAGE_MISMATCH")
    if handoff["source_fusion_sha256"] != fusion_sha256:
        _fail("R1_R2_LINEAGE_MISMATCH")

    candidate = _closed(
        context["candidate"], _CANDIDATE_FIELDS, "CANDIDATE_INVALID"
    )
    candidate_id = _identifier(
        candidate["candidate_id"], "CANDIDATE_INVALID"
    )
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
        raise ComponentViewRegistryError(
            "REUSE_CURRENTNESS_INVALID"
        ) from exc
    supplied_evaluation = _mapping(
        context["reuse_evaluation"], "REUSE_CURRENTNESS_INVALID"
    )
    if supplied_evaluation != evaluation:
        _fail("REUSE_CURRENTNESS_MISMATCH")
    if evaluation.get("state") != "CURRENT":
        _fail("REUSE_STALE")

    base_source = _closed(
        handoff["base_source"], _BASE_SOURCE_FIELDS, "BASE_SOURCE_INVALID"
    )
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
        binding = _closed(
            raw, _BINDING_FIELDS, "CANDIDATE_BINDING_INVALID"
        )
        if binding["target_namespace"] != "CANDIDATE":
            _fail("CANDIDATE_NAMESPACE_INVALID")
        accepted_candidate_id = _identifier(
            binding["candidate_id"], "CANDIDATE_BINDING_INVALID"
        )
        if accepted_candidate_id != candidate_id:
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
                "block_name": _text(
                    binding["block_name"], "CANDIDATE_BINDING_INVALID"
                ),
                "legacy_uuid": _text(
                    binding["legacy_uuid"], "CANDIDATE_BINDING_INVALID"
                ),
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
    component_type = _identifier(
        component["component_type"], "COMPONENT_TYPE_INVALID"
    )
    origin_class = component["origin_class"]
    if origin_class not in _ORIGIN_CLASSES:
        _fail("ORIGIN_CLASS_INVALID")

    source_refs = _sha_list(
        component["source_projection_refs"], "SOURCE_PROJECTION_REFS_INVALID"
    )
    semantic_refs = _sha_list(
        component["semantic_projection_refs"],
        "SEMANTIC_PROJECTION_REFS_INVALID",
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


def _ensure_component_target_owners(
    components: list[dict[str, object]],
) -> None:
    target_owners: dict[str, str] = {}
    for component in components:
        component_id = str(component["component_id"])
        for binding in component["candidate_entity_bindings"]:
            handle = str(binding["entity_handle"]).casefold()
            owner = target_owners.get(handle)
            if owner is not None and owner != component_id:
                _fail("DUPLICATE_TARGET_OWNER")
            target_owners[handle] = component_id


def _normalize_components(
    components: object,
    *,
    state: dict[str, object],
) -> list[dict[str, object]]:
    if type(components) is not list or not components:
        _fail("COMPONENTS_INVALID")
    normalized = [
        _normalize_input_component(component, state=state)
        for component in components
    ]
    ids = [str(component["component_id"]) for component in normalized]
    if len(ids) != len(set(ids)):
        _fail("DUPLICATE_COMPONENT")
    _ensure_component_target_owners(normalized)
    normalized.sort(key=lambda component: str(component["component_id"]))
    return normalized


def _validate_source_refs(
    refs: list[str],
    *,
    primitive_index: dict[str, str],
) -> list[str]:
    fingerprints: list[str] = []
    for ref in refs:
        fingerprint = primitive_index.get(ref)
        if fingerprint is None:
            _fail("FOREIGN_SOURCE_PROJECTION")
        fingerprints.append(fingerprint)
    return fingerprints


def _validate_semantic_refs(
    refs: list[str],
    *,
    semantic_index: dict[str, str],
) -> list[str]:
    fingerprints: list[str] = []
    for ref in refs:
        fingerprint = semantic_index.get(ref)
        if fingerprint is None:
            _fail("FOREIGN_SEMANTIC_PROJECTION")
        fingerprints.append(fingerprint)
    return fingerprints


def _view_candidate_bindings(
    value: object,
    *,
    candidate_id: str,
    components: list[dict[str, object]],
) -> list[dict[str, object]]:
    if type(value) is not list:
        _fail("VIEW_CANDIDATE_BINDINGS_INVALID")
    accepted = [
        binding
        for component in components
        for binding in component["candidate_entity_bindings"]
    ]
    normalized: list[dict[str, object]] = []
    for raw in value:
        binding = _closed(
            raw, _BINDING_FIELDS, "VIEW_CANDIDATE_BINDING_INVALID"
        )
        if binding["target_namespace"] != "CANDIDATE":
            _fail("VIEW_CANDIDATE_BINDING_INVALID")
        bound_candidate = _identifier(
            binding["candidate_id"], "VIEW_CANDIDATE_BINDING_INVALID"
        )
        if bound_candidate != candidate_id:
            _fail("VIEW_CANDIDATE_BINDING_INVALID")
        record = {
            "target_namespace": "CANDIDATE",
            "candidate_id": candidate_id,
            "entity_handle": _identifier(
                binding["entity_handle"], "VIEW_CANDIDATE_BINDING_INVALID"
            ),
            "block_name": _text(
                binding["block_name"], "VIEW_CANDIDATE_BINDING_INVALID"
            ),
            "legacy_uuid": _text(
                binding["legacy_uuid"], "VIEW_CANDIDATE_BINDING_INVALID"
            ),
            "relative_path": _text(
                binding["relative_path"], "VIEW_CANDIDATE_BINDING_INVALID"
            ),
            "captured_at_utc": _text(
                binding["captured_at_utc"], "VIEW_CANDIDATE_BINDING_INVALID"
            ),
        }
        if any(record == previous for previous in normalized):
            _fail("DUPLICATE_VIEW_CANDIDATE_BINDING")
        if not any(record == candidate for candidate in accepted):
            _fail("FOREIGN_VIEW_CANDIDATE_BINDING")
        normalized.append(record)

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


def _layout_bindings(value: object) -> list[dict[str, object]]:
    if type(value) is not list:
        _fail("LAYOUT_BINDINGS_INVALID")
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for raw in value:
        binding = _closed(
            raw, _LAYOUT_BINDING_FIELDS, "LAYOUT_BINDING_FIELDS_INVALID"
        )
        layout_id = _identifier(
            binding["layout_id"], "LAYOUT_BINDING_INVALID"
        )
        if layout_id in seen_ids:
            _fail("DUPLICATE_LAYOUT_BINDING")
        seen_ids.add(layout_id)
        normalized.append(
            {
                "layout_id": layout_id,
                "display_name": _text(
                    binding["display_name"], "LAYOUT_BINDING_INVALID"
                ),
                "legacy_uuid": _text(
                    binding["legacy_uuid"], "LAYOUT_BINDING_INVALID"
                ),
                "relative_path": _text(
                    binding["relative_path"], "LAYOUT_BINDING_INVALID"
                ),
                "captured_at_utc": _text(
                    binding["captured_at_utc"], "LAYOUT_BINDING_INVALID"
                ),
            }
        )
    normalized.sort(
        key=lambda item: (
            item["layout_id"],
            item["display_name"],
            item["legacy_uuid"],
            item["relative_path"],
            item["captured_at_utc"],
        )
    )
    return normalized


def _view_identity(
    *,
    view_role: str,
    component_ids: list[str],
    source_fingerprints: list[str],
    semantic_fingerprints: list[str],
) -> str:
    material = {
        "identity_kind": "r3-logical-view-v1",
        "schema_version": COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION,
        "view_role": view_role,
        "component_ids": sorted(component_ids),
        "source_membership": sorted(source_fingerprints),
        "semantic_membership": sorted(semantic_fingerprints),
    }
    return canonical_json_sha256(material)


def _normalize_input_view(
    value: object,
    *,
    state: dict[str, object],
    components: list[dict[str, object]],
) -> dict[str, object]:
    view = _closed(value, _INPUT_VIEW_FIELDS, "VIEW_FIELDS_INVALID")
    view_role = _identifier(view["view_role"], "VIEW_ROLE_INVALID")
    component_ids = _sha_list(
        view["component_ids"], "VIEW_COMPONENT_IDS_INVALID"
    )
    accepted_component_ids = {
        str(component["component_id"]) for component in components
    }
    if any(
        component_id not in accepted_component_ids
        for component_id in component_ids
    ):
        _fail("FOREIGN_VIEW_COMPONENT")

    source_refs = _sha_list(
        view["source_projection_refs"], "VIEW_SOURCE_REFS_INVALID"
    )
    semantic_refs = _sha_list(
        view["semantic_projection_refs"], "VIEW_SEMANTIC_REFS_INVALID"
    )
    source_fingerprints = _validate_source_refs(
        source_refs, primitive_index=state["primitive_index"]
    )
    semantic_fingerprints = _validate_semantic_refs(
        semantic_refs, semantic_index=state["semantic_index"]
    )
    candidate_bindings = _view_candidate_bindings(
        view["candidate_entity_bindings"],
        candidate_id=state["upstream_bindings"]["candidate_id"],
        components=components,
    )
    layouts = _layout_bindings(view["layout_bindings"])
    view_id = _view_identity(
        view_role=view_role,
        component_ids=component_ids,
        source_fingerprints=source_fingerprints,
        semantic_fingerprints=semantic_fingerprints,
    )
    return {
        "view_id": view_id,
        "view_role": view_role,
        "component_ids": component_ids,
        "source_projection_refs": source_refs,
        "semantic_projection_refs": semantic_refs,
        "candidate_entity_bindings": candidate_bindings,
        "layout_bindings": layouts,
    }


def _ensure_layout_consistency(
    views: list[dict[str, object]],
) -> None:
    layouts_by_id: dict[str, dict[str, object]] = {}
    for view in views:
        for layout in view["layout_bindings"]:
            layout_id = str(layout["layout_id"])
            previous = layouts_by_id.get(layout_id)
            if previous is not None and previous != layout:
                _fail("LAYOUT_BINDING_CONFLICT")
            layouts_by_id[layout_id] = layout


def _normalize_views(
    views: object,
    *,
    state: dict[str, object],
    components: list[dict[str, object]],
) -> list[dict[str, object]]:
    if type(views) not in (list, tuple):
        _fail("VIEWS_INVALID")
    normalized = [
        _normalize_input_view(view, state=state, components=components)
        for view in views
    ]
    ids = [str(view["view_id"]) for view in normalized]
    if len(ids) != len(set(ids)):
        _fail("DUPLICATE_VIEW")
    _ensure_layout_consistency(normalized)
    normalized.sort(key=lambda view: str(view["view_id"]))
    return normalized


def _expected_component_view_ids(
    components: list[dict[str, object]],
    views: list[dict[str, object]],
) -> dict[str, list[str]]:
    result = {
        str(component["component_id"]): [] for component in components
    }
    for view in views:
        view_id = str(view["view_id"])
        for component_id in view["component_ids"]:
            result[str(component_id)].append(view_id)
    for ids in result.values():
        ids.sort()
    return result


def _apply_component_view_ids(
    components: list[dict[str, object]],
    views: list[dict[str, object]],
) -> None:
    expected = _expected_component_view_ids(components, views)
    for component in components:
        component["view_ids"] = expected[str(component["component_id"])]


def _link_identity(
    *,
    relation_type: str,
    source_id: str,
    target_id: str,
    evidence_refs: list[str],
) -> str:
    material = {
        "identity_kind": "r3-explicit-link-v1",
        "schema_version": COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION,
        "relation_type": relation_type,
        "source_id": source_id,
        "target_id": target_id,
        "evidence_refs": sorted(evidence_refs),
    }
    return canonical_json_sha256(material)


def _make_link(
    relation_type: str,
    source_id: str,
    target_id: str,
    evidence_refs: list[str] | None = None,
) -> dict[str, object]:
    evidence = sorted(evidence_refs or [])
    return {
        "link_id": _link_identity(
            relation_type=relation_type,
            source_id=source_id,
            target_id=target_id,
            evidence_refs=evidence,
        ),
        "relation_type": relation_type,
        "source_id": source_id,
        "target_id": target_id,
        "evidence_refs": evidence,
    }


def _derive_links(
    views: list[dict[str, object]],
) -> list[dict[str, object]]:
    links: list[dict[str, object]] = []
    for view in views:
        view_id = str(view["view_id"])
        for component_id in view["component_ids"]:
            links.append(
                _make_link(
                    "COMPONENT_HAS_VIEW",
                    str(component_id),
                    view_id,
                )
            )
        for layout in view["layout_bindings"]:
            links.append(
                _make_link(
                    "VIEW_PRESENTED_ON_LAYOUT",
                    view_id,
                    str(layout["layout_id"]),
                )
            )

    for index, left in enumerate(views):
        left_id = str(left["view_id"])
        for right in views[index + 1 :]:
            right_id = str(right["view_id"])
            source_id, target_id = sorted((left_id, right_id))
            if set(left["component_ids"]) & set(right["component_ids"]):
                links.append(
                    _make_link(
                        "VIEWS_SHARE_COMPONENT",
                        source_id,
                        target_id,
                    )
                )
            shared_evidence = sorted(
                set(left["semantic_projection_refs"])
                & set(right["semantic_projection_refs"])
            )
            if shared_evidence:
                links.append(
                    _make_link(
                        "VIEWS_SHARE_PARAMETER_EVIDENCE",
                        source_id,
                        target_id,
                        shared_evidence,
                    )
                )

    links.sort(
        key=lambda link: (
            str(link["relation_type"]),
            str(link["source_id"]),
            str(link["target_id"]),
            tuple(link["evidence_refs"]),
            str(link["link_id"]),
        )
    )
    return links


def _snapshot_material(
    *,
    upstream_bindings: dict[str, object],
    components: list[dict[str, object]],
    views: list[dict[str, object]],
    links: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION,
        "upstream_bindings": deepcopy(upstream_bindings),
        "components": deepcopy(components),
        "views": deepcopy(views),
        "links": deepcopy(links),
    }


def build_component_view_registry(
    *,
    upstream_context: object,
    components: object,
    views: object = (),
) -> dict[str, object]:
    """Build a detached deterministic registry snapshot."""
    state = _upstream_context(upstream_context)
    normalized_components = _normalize_components(components, state=state)
    normalized_views = _normalize_views(
        views,
        state=state,
        components=normalized_components,
    )
    _apply_component_view_ids(normalized_components, normalized_views)
    links = _derive_links(normalized_views)
    material = _snapshot_material(
        upstream_bindings=state["upstream_bindings"],
        components=normalized_components,
        views=normalized_views,
        links=links,
    )
    result = deepcopy(material)
    result["registry_snapshot_sha256"] = canonical_json_sha256(material)
    return result


def _validate_output_component(
    value: object,
    *,
    state: dict[str, object],
) -> dict[str, object]:
    component = _closed(
        value, _OUTPUT_COMPONENT_FIELDS, "COMPONENT_FIELDS_INVALID"
    )
    supplied_view_ids = _sha_list_allow_empty(
        component["view_ids"], "COMPONENT_VIEW_IDS_INVALID"
    )
    input_component = {
        "component_type": component["component_type"],
        "origin_class": component["origin_class"],
        "source_projection_refs": component["source_projection_refs"],
        "semantic_projection_refs": component["semantic_projection_refs"],
        "base_cad_provenance_ref": component["base_cad_provenance_ref"],
        "candidate_entity_bindings": component["candidate_entity_bindings"],
    }
    normalized = _normalize_input_component(input_component, state=state)
    supplied_id = _sha256(
        component["component_id"], "COMPONENT_ID_INVALID"
    )
    if supplied_id != normalized["component_id"]:
        _fail("COMPONENT_ID_MISMATCH")
    normalized["view_ids"] = supplied_view_ids
    return normalized


def _validate_output_view(
    value: object,
    *,
    state: dict[str, object],
    components: list[dict[str, object]],
) -> dict[str, object]:
    view = _closed(value, _OUTPUT_VIEW_FIELDS, "VIEW_FIELDS_INVALID")
    input_view = {field: view[field] for field in _INPUT_VIEW_FIELDS}
    normalized = _normalize_input_view(
        input_view,
        state=state,
        components=components,
    )
    supplied_id = _sha256(view["view_id"], "VIEW_ID_INVALID")
    if supplied_id != normalized["view_id"]:
        _fail("VIEW_ID_MISMATCH")
    return normalized


def _normalize_output_views(
    value: object,
    *,
    state: dict[str, object],
    components: list[dict[str, object]],
) -> list[dict[str, object]]:
    if type(value) is not list:
        _fail("VIEWS_INVALID")
    normalized = [
        _validate_output_view(view, state=state, components=components)
        for view in value
    ]
    ids = [str(view["view_id"]) for view in normalized]
    if len(ids) != len(set(ids)):
        _fail("DUPLICATE_VIEW")
    _ensure_layout_consistency(normalized)
    normalized.sort(key=lambda view: str(view["view_id"]))
    return normalized


def _normalize_output_link(
    value: object,
    *,
    component_ids: set[str],
    view_ids: set[str],
    layout_ids: set[str],
    semantic_index: dict[str, str],
) -> dict[str, object]:
    link = _closed(value, _LINK_FIELDS, "LINK_FIELDS_INVALID")
    relation_type = _identifier(
        link["relation_type"], "LINK_RELATION_INVALID"
    )
    if relation_type not in _RELATION_TYPES:
        _fail("LINK_RELATION_INVALID")
    evidence_refs = _sha_list_allow_empty(
        link["evidence_refs"], "LINK_EVIDENCE_INVALID"
    )

    if relation_type == "COMPONENT_HAS_VIEW":
        source_id = _sha256(link["source_id"], "LINK_SOURCE_INVALID")
        target_id = _sha256(link["target_id"], "LINK_TARGET_INVALID")
        if source_id not in component_ids or target_id not in view_ids:
            _fail("DANGLING_LINK")
        if evidence_refs:
            _fail("LINK_EVIDENCE_INVALID")
    elif relation_type in {
        "VIEWS_SHARE_COMPONENT",
        "VIEWS_SHARE_PARAMETER_EVIDENCE",
    }:
        source_id = _sha256(link["source_id"], "LINK_SOURCE_INVALID")
        target_id = _sha256(link["target_id"], "LINK_TARGET_INVALID")
        if source_id not in view_ids or target_id not in view_ids:
            _fail("DANGLING_LINK")
        if source_id == target_id:
            _fail("SELF_LINK_INVALID")
        if source_id > target_id:
            _fail("LINK_DIRECTION_INVALID")
        if relation_type == "VIEWS_SHARE_PARAMETER_EVIDENCE":
            if not evidence_refs:
                _fail("LINK_EVIDENCE_INVALID")
            _validate_semantic_refs(
                evidence_refs, semantic_index=semantic_index
            )
        elif evidence_refs:
            _fail("LINK_EVIDENCE_INVALID")
    else:
        source_id = _sha256(link["source_id"], "LINK_SOURCE_INVALID")
        target_id = _identifier(link["target_id"], "LINK_TARGET_INVALID")
        if source_id not in view_ids or target_id not in layout_ids:
            _fail("DANGLING_LINK")
        if evidence_refs:
            _fail("LINK_EVIDENCE_INVALID")

    supplied_id = _sha256(link["link_id"], "LINK_ID_INVALID")
    expected_id = _link_identity(
        relation_type=relation_type,
        source_id=source_id,
        target_id=target_id,
        evidence_refs=evidence_refs,
    )
    if supplied_id != expected_id:
        _fail("LINK_ID_MISMATCH")
    return {
        "link_id": expected_id,
        "relation_type": relation_type,
        "source_id": source_id,
        "target_id": target_id,
        "evidence_refs": evidence_refs,
    }


def _normalize_output_links(
    value: object,
    *,
    components: list[dict[str, object]],
    views: list[dict[str, object]],
    state: dict[str, object],
) -> list[dict[str, object]]:
    if type(value) is not list:
        _fail("LINKS_INVALID")
    component_ids = {
        str(component["component_id"]) for component in components
    }
    view_ids = {str(view["view_id"]) for view in views}
    layout_ids = {
        str(layout["layout_id"])
        for view in views
        for layout in view["layout_bindings"]
    }
    normalized = [
        _normalize_output_link(
            link,
            component_ids=component_ids,
            view_ids=view_ids,
            layout_ids=layout_ids,
            semantic_index=state["semantic_index"],
        )
        for link in value
    ]
    ids = [str(link["link_id"]) for link in normalized]
    if len(ids) != len(set(ids)):
        _fail("DUPLICATE_LINK")
    normalized.sort(
        key=lambda link: (
            str(link["relation_type"]),
            str(link["source_id"]),
            str(link["target_id"]),
            tuple(link["evidence_refs"]),
            str(link["link_id"]),
        )
    )
    return normalized


def validate_component_view_registry(
    payload: object, *, upstream_context: object
) -> dict[str, object]:
    """Validate and detach a registry snapshot."""
    state = _upstream_context(upstream_context)
    registry = _closed(payload, _ROOT_FIELDS, "REGISTRY_FIELDS_INVALID")
    if registry["schema_version"] != COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION:
        _fail("REGISTRY_SCHEMA_INVALID")

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
        _validate_output_component(component, state=state)
        for component in raw_components
    ]
    ids = [str(component["component_id"]) for component in components]
    if len(ids) != len(set(ids)):
        _fail("DUPLICATE_COMPONENT")
    _ensure_component_target_owners(components)
    components.sort(key=lambda component: str(component["component_id"]))

    views = _normalize_output_views(
        registry["views"],
        state=state,
        components=components,
    )
    expected_membership = _expected_component_view_ids(components, views)
    for component in components:
        component_id = str(component["component_id"])
        if component["view_ids"] != expected_membership[component_id]:
            _fail("COMPONENT_VIEW_IDS_MISMATCH")

    expected_links = _derive_links(views)
    supplied_links = _normalize_output_links(
        registry["links"],
        components=components,
        views=views,
        state=state,
    )
    if supplied_links != expected_links:
        _fail("LINK_GRAPH_MISMATCH")

    material = _snapshot_material(
        upstream_bindings=state["upstream_bindings"],
        components=components,
        views=views,
        links=expected_links,
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


def _task3_dara_error(error: _dara.DrawingArtifactReferenceError) -> None:
    code = str(error)
    if code == "FOREIGN_REFERENCE":
        code = "REPLAY_MISMATCH"
    _fail(code)


def _task3_record_bindings(
    registry: dict[str, object],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    component_bindings = [
        {
            "component_id": str(component["component_id"]),
            "record_sha256": canonical_json_sha256(component),
        }
        for component in registry["components"]
    ]
    view_bindings = [
        {
            "view_id": str(view["view_id"]),
            "record_sha256": canonical_json_sha256(view),
        }
        for view in registry["views"]
    ]
    return component_bindings, view_bindings


def _task3_provenance_material(
    registry: dict[str, object],
) -> dict[str, object]:
    component_bindings, view_bindings = _task3_record_bindings(registry)
    return {
        "identity_kind": "r3-component-view-registry-provenance-v1",
        "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
        "component_bindings": component_bindings,
        "view_bindings": view_bindings,
    }


def finalize_component_view_correspondence(
    *,
    registry: object,
    upstream_context: object,
    parent_reference: object,
    parent_observation: object,
    parent_artifact_bytes: object,
    child_reference: object,
    child_observation: object,
    child_artifact_bytes: object,
    accepted_transition_evidence_sha256: object,
) -> dict[str, object]:
    """Finalize R3 correspondence against an immutable, current parent/child pair."""
    if parent_reference is None:
        _fail("MISSING_PARENT")
    if child_reference is None:
        _fail("MISSING_CHILD")

    try:
        normalized_registry = validate_component_view_registry(
            registry,
            upstream_context=upstream_context,
        )
    except ComponentViewRegistryError:
        _fail("CORRESPONDENCE_MISMATCH")

    try:
        normalized_parent = _dara.validate_drawing_artifact_reference(
            parent_reference,
            expected_artifact_role="R3_CANDIDATE",
        )
        normalized_child = _dara.validate_drawing_artifact_reference(
            child_reference,
            expected_artifact_role="R3_CANDIDATE",
            parent_reference=parent_reference,
            accepted_transition_evidence_sha256=(
                accepted_transition_evidence_sha256
            ),
        )
    except _dara.DrawingArtifactReferenceError as error:
        _task3_dara_error(error)
        raise AssertionError("unreachable")

    provenance_material = _task3_provenance_material(normalized_registry)
    component_bindings = provenance_material["component_bindings"]
    view_bindings = provenance_material["view_bindings"]
    provenance_sha256 = canonical_json_sha256(provenance_material)
    expected_binding = {
        "registry_snapshot_sha256": normalized_registry[
            "registry_snapshot_sha256"
        ],
        "provenance_sha256": provenance_sha256,
    }
    for reference in (normalized_parent, normalized_child):
        if reference["r3_provenance_binding"] != expected_binding:
            _fail("PROVENANCE_MISMATCH")

    try:
        _dara.require_current_drawing_artifact_reference(
            reference=parent_reference,
            observation=parent_observation,
            artifact_bytes=parent_artifact_bytes,
        )
        _dara.require_current_drawing_artifact_reference(
            reference=child_reference,
            observation=child_observation,
            artifact_bytes=child_artifact_bytes,
            parent_reference=parent_reference,
            accepted_transition_evidence_sha256=(
                accepted_transition_evidence_sha256
            ),
        )
    except _dara.DrawingArtifactReferenceError as error:
        _task3_dara_error(error)
        raise AssertionError("unreachable")

    return {
        "parent_reference_id": normalized_parent["reference_id"],
        "parent_reference_sha256": normalized_parent["reference_sha256"],
        "child_reference_id": normalized_child["reference_id"],
        "child_reference_sha256": normalized_child["reference_sha256"],
        "registry_snapshot_sha256": normalized_registry[
            "registry_snapshot_sha256"
        ],
        "provenance_sha256": provenance_sha256,
        "component_bindings": deepcopy(component_bindings),
        "view_bindings": deepcopy(view_bindings),
    }


def _seed_ids(
    value: object,
    *,
    code: str,
) -> list[str]:
    if type(value) not in (list, tuple):
        _fail(code)
    normalized = [_sha256(item, code) for item in value]
    if len(normalized) != len(set(normalized)):
        _fail(code)
    return sorted(normalized)


def _link_nodes(
    link: dict[str, object],
) -> tuple[tuple[str, str], tuple[str, str]]:
    relation_type = str(link["relation_type"])
    if relation_type == "COMPONENT_HAS_VIEW":
        return (
            ("component", str(link["source_id"])),
            ("view", str(link["target_id"])),
        )
    if relation_type == "VIEW_PRESENTED_ON_LAYOUT":
        return (
            ("view", str(link["source_id"])),
            ("layout", str(link["target_id"])),
        )
    return (
        ("view", str(link["source_id"])),
        ("view", str(link["target_id"])),
    )


def project_linked_view_impacts(
    *,
    registry: object,
    component_ids: object = (),
    view_ids: object = (),
    upstream_context: object,
) -> dict[str, object]:
    """Project deterministic linked impacts from explicit registry seeds."""
    normalized = validate_component_view_registry(
        registry, upstream_context=upstream_context
    )
    component_seeds = _seed_ids(
        component_ids, code="IMPACT_COMPONENT_IDS_INVALID"
    )
    view_seeds = _seed_ids(view_ids, code="IMPACT_VIEW_IDS_INVALID")
    if not component_seeds and not view_seeds:
        _fail("IMPACT_SEEDS_REQUIRED")

    components_by_id = {
        str(component["component_id"]): component
        for component in normalized["components"]
    }
    views_by_id = {
        str(view["view_id"]): view for view in normalized["views"]
    }
    layouts_by_id: dict[str, dict[str, object]] = {}
    for view in normalized["views"]:
        for layout in view["layout_bindings"]:
            layouts_by_id[str(layout["layout_id"])] = layout

    if any(seed not in components_by_id for seed in component_seeds):
        _fail("UNKNOWN_IMPACT_COMPONENT")
    if any(seed not in views_by_id for seed in view_seeds):
        _fail("UNKNOWN_IMPACT_VIEW")

    reached: set[tuple[str, str]] = {
        ("component", seed) for seed in component_seeds
    }
    reached.update(("view", seed) for seed in view_seeds)
    reached_links: set[str] = set()

    changed = True
    while changed:
        changed = False
        for link in normalized["links"]:
            left, right = _link_nodes(link)
            if left in reached or right in reached:
                link_id = str(link["link_id"])
                if link_id not in reached_links:
                    reached_links.add(link_id)
                    changed = True
                if left not in reached:
                    reached.add(left)
                    changed = True
                if right not in reached:
                    reached.add(right)
                    changed = True

    impacted_components = sorted(
        node_id for kind, node_id in reached if kind == "component"
    )
    impacted_views = sorted(
        node_id for kind, node_id in reached if kind == "view"
    )
    impacted_layout_ids = {
        node_id for kind, node_id in reached if kind == "layout"
    }
    impacted_layouts = sorted(
        (
            deepcopy(layout)
            for layout_id, layout in layouts_by_id.items()
            if layout_id in impacted_layout_ids
        ),
        key=lambda layout: str(layout["layout_id"]),
    )
    return {
        "component_ids": impacted_components,
        "view_ids": impacted_views,
        "layout_bindings": impacted_layouts,
        "link_ids": sorted(reached_links),
    }


__all__ = [
    "COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION",
    "ComponentViewRegistryError",
    "build_component_view_registry",
    "validate_component_view_registry",
    "component_view_registry_sha256",
    "project_linked_view_impacts",
]
