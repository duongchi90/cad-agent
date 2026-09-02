"""Thin, provenance-bound CAD query adapter.

This module adds the smallest Phase 1A read surface on top of the existing
DARA, R3, R4, and typed CAD-read owners.  Selectors are resolved from sealed
provenance before any live entity lookup, so a query never needs a whole
drawing enumeration and cannot silently drift to another candidate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import json
import ntpath

from cad_agent import candidate_revision as _candidate_revision
from cad_agent import component_view_registry as _registry
from cad_agent import drawing_artifact_reference as _dara
from cad_agent.drawing_contracts import canonical_json_sha256


DRAWING_OBSERVATION_SCHEMA_VERSION = "drawing-observation-1.0"
ENTITY_QUERY_SCHEMA_VERSION = "entity-query-1.0"
ENTITY_QUERY_RESULT_SCHEMA_VERSION = "entity-query-result-1.0"

MAX_QUERY_HANDLES = 64
MAX_QUERY_COMPONENTS = 32
MAX_QUERY_VIEWS = 16
MAX_RESULT_BYTES = 64 * 1024

_OBSERVATION_FIELDS = frozenset(
    {"schema_version", "binding", "structural_summary", "live_session", "observation_sha256"}
)
_OBSERVATION_BINDING_FIELDS = frozenset(
    {
        "drawing_reference_id",
        "drawing_reference_sha256",
        "artifact_sha256",
        "registry_snapshot_sha256",
        "candidate_revision_sha256",
        "candidate_state_sha256",
    }
)
_SUMMARY_FIELDS = frozenset(
    {
        "component_count",
        "view_count",
        "link_count",
        "candidate_binding_count",
        "components_by_type",
        "views_by_role",
        "layout_ids",
        "whole_drawing_entity_count_status",
    }
)
_LIVE_SESSION_FIELDS = frozenset({"status", "active_document_path", "variables"})
_LIVE_VARIABLES = (
    "DWGPREFIX",
    "DWGNAME",
    "CTAB",
    "CVPORT",
    "TILEMODE",
    "INSUNITS",
)
_QUERY_FIELDS = frozenset(
    {"schema_version", "handles", "component_ids", "view_ids", "detail"}
)
_RESULT_FIELDS = frozenset(
    {"schema_version", "binding", "normalized_query", "entities", "result_sha256"}
)
_ENTITY_BASE_FIELDS = ("handle", "type", "layer")
_ENTITY_GEOMETRY_FIELDS = (
    "start",
    "end",
    "center",
    "radius",
    "start_angle_deg",
    "end_angle_deg",
    "insert",
    "content",
    "height",
    "rotation_deg",
    "attributes",
)
_ENTITY_FIELDS = frozenset((*_ENTITY_BASE_FIELDS, *_ENTITY_GEOMETRY_FIELDS))


class DrawingQueryError(ValueError):
    """Categorical refusal at the bounded drawing-query boundary."""


def _fail(code: str) -> None:
    raise DrawingQueryError(code)


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _closed(value: object, fields: frozenset[str], code: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail(code)
    return deepcopy(dict(value))


def _sha(value: object, code: str) -> str:
    if not _is_sha256(value):
        _fail(code)
    return value


def _normalize_path(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return ntpath.normcase(ntpath.normpath(value))


def _normalize_ids(
    value: object, *, limit: int, code: str
) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(code)
    values = list(value)
    if len(values) > limit or any(type(item) is not str or not item for item in values):
        _fail(code)
    folded = [item.casefold() for item in values]
    if len(folded) != len(set(folded)):
        _fail(code)
    return sorted(values, key=lambda item: (item.casefold(), item))


def validate_entity_query(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate and normalize the closed, bounded selector contract."""

    query = _closed(payload, _QUERY_FIELDS, "QUERY_SCHEMA_INVALID")
    if query["schema_version"] != ENTITY_QUERY_SCHEMA_VERSION:
        _fail("QUERY_SCHEMA_INVALID")
    handles = _normalize_ids(
        query["handles"], limit=MAX_QUERY_HANDLES, code="QUERY_HANDLES_INVALID"
    )
    components = _normalize_ids(
        query["component_ids"],
        limit=MAX_QUERY_COMPONENTS,
        code="QUERY_COMPONENT_IDS_INVALID",
    )
    views = _normalize_ids(
        query["view_ids"], limit=MAX_QUERY_VIEWS, code="QUERY_VIEW_IDS_INVALID"
    )
    detail = query["detail"]
    if detail not in {"SUMMARY", "GEOMETRY"}:
        _fail("QUERY_DETAIL_INVALID")
    if not handles and not components and not views:
        _fail("QUERY_SELECTOR_REQUIRED")
    return {
        "schema_version": ENTITY_QUERY_SCHEMA_VERSION,
        "handles": handles,
        "component_ids": components,
        "view_ids": views,
        "detail": detail,
    }


def _validate_live_session(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("OBSERVATION_LIVE_SESSION_INVALID")
    status = value.get("status")
    if status == "NOT_OBSERVED":
        if set(value) != {"status"}:
            _fail("OBSERVATION_LIVE_SESSION_INVALID")
        return {"status": status}
    if status != "OBSERVED" or set(value) != _LIVE_SESSION_FIELDS:
        _fail("OBSERVATION_LIVE_SESSION_INVALID")
    path = _normalize_path(value.get("active_document_path"), "OBSERVATION_LIVE_SESSION_INVALID")
    variables = value.get("variables")
    if not isinstance(variables, Mapping):
        _fail("OBSERVATION_LIVE_SESSION_INVALID")
    if not set(variables).issubset(set(_LIVE_VARIABLES)):
        _fail("OBSERVATION_LIVE_SESSION_INVALID")
    return {
        "status": status,
        "active_document_path": path,
        "variables": deepcopy(dict(variables)),
    }


def _validate_binding(value: object) -> dict[str, object]:
    binding = _closed(value, _OBSERVATION_BINDING_FIELDS, "OBSERVATION_BINDING_INVALID")
    for field, item in binding.items():
        if field.endswith("sha256"):
            _sha(item, "OBSERVATION_BINDING_INVALID")
        elif type(item) is not str or not item:
            _fail("OBSERVATION_BINDING_INVALID")
    return binding


def _validate_counts(value: object, code: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        _fail(code)
    result: dict[str, int] = {}
    for key, count in value.items():
        if type(key) is not str or not key or type(count) is not int or count < 0:
            _fail(code)
        result[key] = count
    return result


def _validate_summary(value: object) -> dict[str, object]:
    summary = _closed(value, _SUMMARY_FIELDS, "OBSERVATION_SUMMARY_INVALID")
    for field in (
        "component_count",
        "view_count",
        "link_count",
        "candidate_binding_count",
    ):
        if type(summary[field]) is not int or summary[field] < 0:
            _fail("OBSERVATION_SUMMARY_INVALID")
    _validate_counts(summary["components_by_type"], "OBSERVATION_SUMMARY_INVALID")
    _validate_counts(summary["views_by_role"], "OBSERVATION_SUMMARY_INVALID")
    layout_ids = summary["layout_ids"]
    if (
        isinstance(layout_ids, (str, bytes))
        or not isinstance(layout_ids, list)
        or any(type(item) is not str or not item for item in layout_ids)
        or layout_ids != sorted(set(layout_ids))
    ):
        _fail("OBSERVATION_SUMMARY_INVALID")
    if summary["whole_drawing_entity_count_status"] != "NOT_ENUMERATED":
        _fail("OBSERVATION_SUMMARY_INVALID")
    return summary


def _observation_hash_payload(value: Mapping[str, object]) -> dict[str, object]:
    return {
        field: deepcopy(value[field])
        for field in ("schema_version", "binding", "structural_summary", "live_session")
    }


def validate_drawing_observation(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate a deterministic observation and its integrity hash."""

    observation = _closed(payload, _OBSERVATION_FIELDS, "OBSERVATION_SCHEMA_INVALID")
    if observation["schema_version"] != DRAWING_OBSERVATION_SCHEMA_VERSION:
        _fail("OBSERVATION_SCHEMA_INVALID")
    _validate_binding(observation["binding"])
    _validate_summary(observation["structural_summary"])
    _validate_live_session(observation["live_session"])
    supplied = _sha(observation["observation_sha256"], "OBSERVATION_HASH_MISMATCH")
    try:
        expected = canonical_json_sha256(_observation_hash_payload(observation))
    except (TypeError, ValueError) as error:
        raise DrawingQueryError("OBSERVATION_HASH_MISMATCH") from error
    if supplied != expected:
        _fail("OBSERVATION_HASH_MISMATCH")
    return deepcopy(observation)


def _validate_bound_inputs(
    *,
    reference: Mapping[str, object],
    current_observation: Mapping[str, object],
    artifact_bytes: bytes,
    parent_reference: Mapping[str, object] | None,
    accepted_transition_evidence_sha256: str | None,
    registry: Mapping[str, object],
    registry_upstream_context: object,
    candidate_state: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    if not isinstance(artifact_bytes, bytes):
        _fail("ARTIFACT_BYTES_INVALID")
    try:
        sealed_reference = _dara.validate_drawing_artifact_reference(
            reference,
            expected_artifact_role="R3_CANDIDATE",
            parent_reference=parent_reference,
            accepted_transition_evidence_sha256=accepted_transition_evidence_sha256,
        )
        sealed_observation = _dara.validate_drawing_artifact_current_observation(
            current_observation
        )
        _dara.require_current_drawing_artifact_reference(
            reference=sealed_reference,
            observation=sealed_observation,
            artifact_bytes=artifact_bytes,
            parent_reference=parent_reference,
            accepted_transition_evidence_sha256=accepted_transition_evidence_sha256,
        )
    except Exception as error:
        if "STALE" in str(error):
            raise DrawingQueryError("DRAWING_ARTIFACT_STALE") from error
        raise DrawingQueryError("DRAWING_BINDING_INVALID") from error

    try:
        sealed_registry = _registry.validate_component_view_registry(
            registry, upstream_context=registry_upstream_context
        )
    except Exception as error:
        raise DrawingQueryError("REGISTRY_BINDING_MISMATCH") from error
    provenance = _registry.component_view_registry_provenance_evidence(
        sealed_registry, upstream_context=registry_upstream_context
    )
    reference_provenance = sealed_reference["r3_provenance_binding"]
    if (
        not isinstance(reference_provenance, Mapping)
        or reference_provenance.get("registry_snapshot_sha256")
        != sealed_registry["registry_snapshot_sha256"]
        or reference_provenance.get("provenance_sha256") != provenance["provenance_sha256"]
    ):
        _fail("REGISTRY_BINDING_MISMATCH")

    if (
        isinstance(candidate_state, Mapping)
        and "current_candidate_revision_sha256" in candidate_state
        and candidate_state["current_candidate_revision_sha256"] is None
    ):
        _fail("CANDIDATE_NOT_CURRENT")
    try:
        sealed_state = _candidate_revision.validate_candidate_revision_state(candidate_state)
    except Exception as error:
        raise DrawingQueryError("CANDIDATE_STATE_INVALID") from error
    selected_sha = sealed_state["current_candidate_revision_sha256"]
    if selected_sha is None:
        _fail("CANDIDATE_NOT_CURRENT")
    selected = next(
        (
            item
            for item in sealed_state["candidate_revisions"]
            if item["candidate_revision_sha256"] == selected_sha
        ),
        None,
    )
    if not isinstance(selected, Mapping):
        _fail("CANDIDATE_NOT_CURRENT")
    if selected["upstream_bindings"] != sealed_registry["upstream_bindings"]:
        _fail("REGISTRY_BINDING_MISMATCH")
    artifacts = selected.get("candidate_artifacts")
    if not isinstance(artifacts, Mapping):
        _fail("CANDIDATE_REFERENCE_MISMATCH")
    for field in ("reference_id", "reference_sha256", "artifact_sha256"):
        if artifacts.get(field) != sealed_reference[field]:
            _fail("CANDIDATE_REFERENCE_MISMATCH")
    if artifacts.get("accepted_transition_evidence_sha256") != accepted_transition_evidence_sha256:
        _fail("CANDIDATE_TRANSITION_MISMATCH")
    mutation = selected.get("mutation_evidence")
    if (
        not isinstance(mutation, Mapping)
        or mutation.get("accepted_transition_evidence_sha256")
        != accepted_transition_evidence_sha256
    ):
        _fail("MUTATION_TRANSITION_MISMATCH")
    if selected.get("run_id") != sealed_reference["run_id"]:
        _fail("CANDIDATE_SCOPE_MISMATCH")
    return sealed_reference, sealed_observation, sealed_registry, {
        "candidate_revision_id": selected["revision_id"],
        "candidate_revision_sha256": selected["candidate_revision_sha256"],
        "candidate_state_sha256": sealed_state["state_sha256"],
    }


def _binding_record(
    reference: Mapping[str, object],
    registry: Mapping[str, object],
    candidate: Mapping[str, object],
) -> dict[str, object]:
    return {
        "drawing_reference_id": reference["reference_id"],
        "drawing_reference_sha256": reference["reference_sha256"],
        "artifact_sha256": reference["artifact_sha256"],
        "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
        "candidate_revision_sha256": candidate["candidate_revision_sha256"],
        "candidate_state_sha256": candidate["candidate_state_sha256"],
    }


def _live_session(client: object, expected_path: str) -> dict[str, object]:
    if client is None:
        _fail("LIVE_CLIENT_REQUIRED")
    names = list(_LIVE_VARIABLES)
    try:
        variables = client.drawing_get_variables(names)
    except Exception as error:
        raise DrawingQueryError("DRAWING_IDENTITY_UNAVAILABLE") from error
    if not isinstance(variables, Mapping):
        _fail("DRAWING_IDENTITY_INVALID")
    prefix = variables.get("DWGPREFIX")
    name = variables.get("DWGNAME")
    if type(prefix) is not str or type(name) is not str or not prefix or not name:
        _fail("DRAWING_IDENTITY_INVALID")
    actual = ntpath.normcase(ntpath.normpath(ntpath.join(prefix, name)))
    if actual != expected_path:
        _fail("ACTIVE_DOCUMENT_MISMATCH")
    return {
        "status": "OBSERVED",
        "active_document_path": actual,
        "variables": {
            key: deepcopy(variables[key])
            for key in names
            if key in variables
        },
    }


def _structural_summary(registry: Mapping[str, object]) -> dict[str, object]:
    components = registry["components"]
    views = registry["views"]
    links = registry["links"]
    by_type: dict[str, int] = {}
    view_roles: dict[str, int] = {}
    layout_ids: set[str] = set()
    handles: set[str] = set()
    for component in components:
        kind = str(component["component_type"])
        by_type[kind] = by_type.get(kind, 0) + 1
        for binding in component["candidate_entity_bindings"]:
            handles.add(str(binding["entity_handle"]).casefold())
    for view in views:
        role = str(view["view_role"])
        view_roles[role] = view_roles.get(role, 0) + 1
        for layout in view["layout_bindings"]:
            layout_ids.add(str(layout["layout_id"]))
        for binding in view["candidate_entity_bindings"]:
            handles.add(str(binding["entity_handle"]).casefold())
    return {
        "component_count": len(components),
        "view_count": len(views),
        "link_count": len(links),
        "candidate_binding_count": len(handles),
        "components_by_type": dict(sorted(by_type.items())),
        "views_by_role": dict(sorted(view_roles.items())),
        "layout_ids": sorted(layout_ids),
        "whole_drawing_entity_count_status": "NOT_ENUMERATED",
    }


def observe_drawing(
    *,
    reference: Mapping[str, object],
    current_observation: Mapping[str, object],
    artifact_bytes: bytes,
    parent_reference: Mapping[str, object] | None,
    accepted_transition_evidence_sha256: str | None,
    registry: Mapping[str, object],
    registry_upstream_context: object,
    candidate_state: Mapping[str, object],
    client: object = None,
    expected_active_document_path: str | None = None,
) -> dict[str, object]:
    """Return a provenance-bound structural summary without entity enumeration."""

    sealed_reference, _, sealed_registry, candidate = _validate_bound_inputs(
        reference=reference,
        current_observation=current_observation,
        artifact_bytes=artifact_bytes,
        parent_reference=parent_reference,
        accepted_transition_evidence_sha256=accepted_transition_evidence_sha256,
        registry=registry,
        registry_upstream_context=registry_upstream_context,
        candidate_state=candidate_state,
    )
    if client is None:
        if expected_active_document_path is not None:
            _fail("OFFLINE_PATH_NOT_ALLOWED")
        live = {"status": "NOT_OBSERVED"}
    else:
        expected = _normalize_path(
            expected_active_document_path, "DRAWING_PATH_REQUIRED"
        )
        live = _live_session(client, expected)
    payload = {
        "schema_version": DRAWING_OBSERVATION_SCHEMA_VERSION,
        "binding": _binding_record(sealed_reference, sealed_registry, candidate),
        "structural_summary": _structural_summary(sealed_registry),
        "live_session": live,
    }
    payload["observation_sha256"] = canonical_json_sha256(payload)
    return validate_drawing_observation(payload)


def _selector_handles(
    query: Mapping[str, object], registry: Mapping[str, object]
) -> tuple[list[str], set[str]]:
    requested = list(query["handles"])
    bound: set[str] = set()
    component_ids = set(query["component_ids"])
    view_ids = set(query["view_ids"])
    components = {str(item["component_id"]): item for item in registry["components"]}
    views = {str(item["view_id"]): item for item in registry["views"]}
    candidate_id = registry["upstream_bindings"]["candidate_id"]
    for component_id in query["component_ids"]:
        component = components.get(component_id)
        if component is None:
            _fail("COMPONENT_SELECTOR_NOT_FOUND")
        for binding in component["candidate_entity_bindings"]:
            if (
                binding["target_namespace"] == "CANDIDATE"
                and binding["candidate_id"] == candidate_id
            ):
                requested.append(str(binding["entity_handle"]))
                bound.add(str(binding["entity_handle"]).casefold())
    for view_id in query["view_ids"]:
        view = views.get(view_id)
        if view is None:
            _fail("VIEW_SELECTOR_NOT_FOUND")
        for binding in view["candidate_entity_bindings"]:
            if (
                binding["target_namespace"] == "CANDIDATE"
                and binding["candidate_id"] == candidate_id
            ):
                requested.append(str(binding["entity_handle"]))
                bound.add(str(binding["entity_handle"]).casefold())
    unique: dict[str, str] = {}
    for handle in requested:
        unique.setdefault(handle.casefold(), handle)
    if len(unique) > MAX_QUERY_HANDLES:
        _fail("QUERY_RESOLUTION_UNBOUNDED")
    return sorted(unique.values(), key=lambda item: (item.casefold(), item)), bound


def _entity_record(
    raw: Mapping[str, object], requested_handle: str, detail: str
) -> dict[str, object]:
    if type(raw.get("handle")) is not str or raw["handle"].casefold() != requested_handle.casefold():
        _fail("ENTITY_IDENTITY_MISMATCH")
    if any(type(raw.get(field)) is not str or not raw[field] for field in ("type", "layer")):
        _fail("ENTITY_GET_INVALID")
    result: dict[str, object] = {
        field: deepcopy(raw[field]) for field in _ENTITY_BASE_FIELDS
    }
    if detail == "GEOMETRY":
        for field in _ENTITY_GEOMETRY_FIELDS:
            if field in raw:
                result[field] = deepcopy(raw[field])
    return result


def _validate_entity(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("RESULT_ENTITY_INVALID")
    keys = set(value)
    if keys == {"handle", "status"}:
        if type(value["handle"]) is not str or not value["handle"] or value["status"] != "NOT_FOUND":
            _fail("RESULT_ENTITY_INVALID")
        return deepcopy(dict(value))
    if not {"handle", "type", "layer"}.issubset(keys) or not keys.issubset(_ENTITY_FIELDS):
        _fail("RESULT_ENTITY_INVALID")
    if any(type(value.get(field)) is not str or not value[field] for field in _ENTITY_BASE_FIELDS):
        _fail("RESULT_ENTITY_INVALID")
    return deepcopy(dict(value))


def _result_hash_payload(value: Mapping[str, object]) -> dict[str, object]:
    return {
        field: deepcopy(value[field])
        for field in ("schema_version", "binding", "normalized_query", "entities")
    }


def validate_entity_query_result(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate a query result and its binding/integrity hash."""

    result = _closed(payload, _RESULT_FIELDS, "RESULT_SCHEMA_INVALID")
    if result["schema_version"] != ENTITY_QUERY_RESULT_SCHEMA_VERSION:
        _fail("RESULT_SCHEMA_INVALID")
    _validate_binding(result["binding"])
    normalized = validate_entity_query(result["normalized_query"])
    if normalized != result["normalized_query"]:
        _fail("RESULT_QUERY_NOT_CANONICAL")
    entities = result["entities"]
    if not isinstance(entities, list) or len(entities) > MAX_QUERY_HANDLES:
        _fail("RESULT_ENTITIES_INVALID")
    checked = [_validate_entity(item) for item in entities]
    if checked != entities:
        _fail("RESULT_ENTITIES_INVALID")
    supplied = _sha(result["result_sha256"], "RESULT_HASH_MISMATCH")
    try:
        expected = canonical_json_sha256(_result_hash_payload(result))
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise DrawingQueryError("RESULT_HASH_MISMATCH") from error
    if supplied != expected:
        _fail("RESULT_HASH_MISMATCH")
    if len(encoded) > MAX_RESULT_BYTES:
        _fail("RESULT_OVERSIZED")
    return deepcopy(result)


def query_entities(
    *,
    reference: Mapping[str, object],
    current_observation: Mapping[str, object],
    artifact_bytes: bytes,
    parent_reference: Mapping[str, object] | None,
    accepted_transition_evidence_sha256: str | None,
    registry: Mapping[str, object],
    registry_upstream_context: object,
    candidate_state: Mapping[str, object],
    client: object,
    expected_active_document_path: str,
    query: Mapping[str, object],
) -> dict[str, object]:
    """Resolve bounded selectors and read only the resulting entity handles."""

    normalized_query = validate_entity_query(query)
    sealed_reference, _, sealed_registry, candidate = _validate_bound_inputs(
        reference=reference,
        current_observation=current_observation,
        artifact_bytes=artifact_bytes,
        parent_reference=parent_reference,
        accepted_transition_evidence_sha256=accepted_transition_evidence_sha256,
        registry=registry,
        registry_upstream_context=registry_upstream_context,
        candidate_state=candidate_state,
    )
    expected_path = _normalize_path(expected_active_document_path, "DRAWING_PATH_REQUIRED")
    _live_session(client, expected_path)
    handles, registry_bound = _selector_handles(normalized_query, sealed_registry)
    entities: list[dict[str, object]] = []
    for handle in handles:
        try:
            raw = client.entity_get(handle)
        except KeyError as error:
            if handle.casefold() in registry_bound:
                raise DrawingQueryError("REGISTRY_ENTITY_BINDING_NOT_OBSERVED") from error
            entities.append({"handle": handle, "status": "NOT_FOUND"})
            continue
        except Exception as error:
            raise DrawingQueryError("ENTITY_GET_FAILED") from error
        if not isinstance(raw, Mapping):
            if handle.casefold() in registry_bound:
                _fail("REGISTRY_ENTITY_BINDING_NOT_OBSERVED")
            _fail("ENTITY_GET_INVALID")
        entities.append(_entity_record(raw, handle, normalized_query["detail"]))
    payload = {
        "schema_version": ENTITY_QUERY_RESULT_SCHEMA_VERSION,
        "binding": _binding_record(sealed_reference, sealed_registry, candidate),
        "normalized_query": normalized_query,
        "entities": entities,
    }
    payload["result_sha256"] = canonical_json_sha256(payload)
    return validate_entity_query_result(payload)


__all__ = [
    "DRAWING_OBSERVATION_SCHEMA_VERSION",
    "ENTITY_QUERY_RESULT_SCHEMA_VERSION",
    "ENTITY_QUERY_SCHEMA_VERSION",
    "DrawingQueryError",
    "MAX_QUERY_COMPONENTS",
    "MAX_QUERY_HANDLES",
    "MAX_QUERY_VIEWS",
    "MAX_RESULT_BYTES",
    "observe_drawing",
    "query_entities",
    "validate_drawing_observation",
    "validate_entity_query",
    "validate_entity_query_result",
]
