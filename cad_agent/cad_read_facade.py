"""Bounded, provenance-bound read access over existing CAD read owners."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import json
import ntpath
from typing import Protocol

from cad_agent import candidate_revision as _candidate_revision
from cad_agent import drawing_artifact_reference as _dara
from cad_agent.drawing_contracts import canonical_json_sha256


CAD_READ_FACADE_SCHEMA_VERSION = "cad-read-facade-1.0"
MAX_QUERY_RESULT_COUNT = 100
MAX_QUERY_RESULT_BYTES = 64 * 1024
MAX_SUMMARY_SAMPLE_COUNT = 20

_BASE_FIELDS = frozenset({"handle", "type", "layer"})
_GEOMETRY_FIELDS = frozenset(
    {
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
    }
)
_ALLOWED_PROJECTION_FIELDS = _BASE_FIELDS | _GEOMETRY_FIELDS
_OBSERVE_RESULT_FIELDS = frozenset(
    {"schema_version", "operation", "binding", "summary", "query_id", "result_sha256"}
)
_OBSERVE_BINDING_FIELDS = frozenset(
    {
        "run_id",
        "project_id",
        "drawing_id",
        "drawing_reference_id",
        "drawing_reference_sha256",
        "artifact_sha256",
        "candidate_revision_id",
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "drawing_path",
        "current_observation_id",
        "current_observation_sha256",
    }
)
_OBSERVE_SUMMARY_FIELDS = frozenset(
    {"entity_count", "by_type", "by_layer", "sample_entities"}
)


class CadReadFacadeError(ValueError):
    """Categorical refusal at the bounded CAD-read façade."""


class CadReadClient(Protocol):
    """Existing typed CAD-read owner surface consumed by the façade."""

    def drawing_get_variables(self, names: list[str]) -> Mapping[str, object]: ...

    def entity_list(self, layer: str | None = None) -> list[Mapping[str, object]]: ...

    def entity_get(self, entity_id: str) -> Mapping[str, object]: ...


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_observe_drawing_result(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate and copy an observation emitted by this read façade.

    This checks the façade result contract and its canonical integrity hash. It
    does not establish drawing currentness independently; that remains owned by
    ``observe_drawing`` and the DARA/candidate inputs it consumes.
    """

    if not isinstance(payload, Mapping) or set(payload) != _OBSERVE_RESULT_FIELDS:
        _fail("RESULT_SCHEMA_INVALID")
    if (
        payload.get("schema_version") != CAD_READ_FACADE_SCHEMA_VERSION
        or payload.get("operation") != "observe_drawing"
    ):
        _fail("RESULT_SCHEMA_INVALID")
    binding = payload.get("binding")
    if not isinstance(binding, Mapping) or set(binding) != _OBSERVE_BINDING_FIELDS:
        _fail("RESULT_BINDING_INVALID")
    for field, value in binding.items():
        if type(value) is not str or not value:
            _fail("RESULT_BINDING_INVALID")
        if field.endswith("_sha256") and not _is_sha256(value):
            _fail("RESULT_BINDING_INVALID")

    summary = payload.get("summary")
    if not isinstance(summary, Mapping) or set(summary) != _OBSERVE_SUMMARY_FIELDS:
        _fail("RESULT_SUMMARY_INVALID")
    entity_count = summary.get("entity_count")
    if type(entity_count) is not int or entity_count < 0:
        _fail("RESULT_SUMMARY_INVALID")
    for field in ("by_type", "by_layer"):
        counts = summary.get(field)
        if not isinstance(counts, Mapping):
            _fail("RESULT_SUMMARY_INVALID")
        for key, count in counts.items():
            if type(key) is not str or not key or type(count) is not int or count < 0:
                _fail("RESULT_SUMMARY_INVALID")
    samples = summary.get("sample_entities")
    if (
        not isinstance(samples, list)
        or len(samples) > MAX_SUMMARY_SAMPLE_COUNT
        or any(
            not isinstance(item, Mapping)
            or set(item) != {"handle", "type", "layer"}
            or any(type(item.get(field)) is not str or not item[field] for field in ("handle", "type", "layer"))
            for item in samples
        )
    ):
        _fail("RESULT_SUMMARY_INVALID")

    result_sha256 = payload.get("result_sha256")
    query_id = payload.get("query_id")
    if not _is_sha256(result_sha256):
        _fail("RESULT_HASH_MISMATCH")
    hash_payload = {
        field: deepcopy(payload[field])
        for field in ("schema_version", "operation", "binding", "summary")
    }
    try:
        expected_sha256 = canonical_json_sha256(hash_payload)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as error:
        raise CadReadFacadeError("RESULT_HASH_MISMATCH") from error
    if result_sha256 != expected_sha256:
        _fail("RESULT_HASH_MISMATCH")
    if query_id != "cad-query-" + result_sha256:
        _fail("RESULT_ID_MISMATCH")
    if len(encoded) > MAX_QUERY_RESULT_BYTES:
        _fail("RESULT_OVERSIZED")
    return deepcopy(dict(payload))


def _fail(code: str) -> None:
    raise CadReadFacadeError(code)


def _string(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return value


def _normalize_limit(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_QUERY_RESULT_COUNT:
        _fail("LIMIT_INVALID")
    return value


def _normalize_projection(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("PROJECTION_INVALID")
    fields = list(value)
    if not fields or any(type(field) is not str for field in fields):
        _fail("PROJECTION_INVALID")
    if len(set(fields)) != len(fields):
        _fail("PROJECTION_INVALID")
    if not set(fields).issubset(_ALLOWED_PROJECTION_FIELDS):
        _fail("PROJECTION_UNSUPPORTED")
    return fields


def _normalize_filter(value: object, code: str) -> str | None:
    if value is None:
        return None
    return _string(value, code)


def _normalize_drawing_path(value: object) -> str:
    path = _string(value, "DRAWING_PATH_INVALID")
    return ntpath.normcase(ntpath.normpath(path))


def _validate_client_drawing(client: CadReadClient, expected_path: str) -> None:
    try:
        variables = client.drawing_get_variables(["DWGPREFIX", "DWGNAME"])
    except Exception as error:
        raise CadReadFacadeError("DRAWING_IDENTITY_UNAVAILABLE") from error
    if not isinstance(variables, Mapping):
        _fail("DRAWING_IDENTITY_INVALID")
    prefix = variables.get("DWGPREFIX")
    name = variables.get("DWGNAME")
    if type(prefix) is not str or type(name) is not str or not prefix or not name:
        _fail("DRAWING_IDENTITY_INVALID")
    active_path = ntpath.normcase(ntpath.normpath(ntpath.join(prefix, name)))
    if active_path != expected_path:
        _fail("DRAWING_IDENTITY_MISMATCH")


def _validated_binding(
    *,
    client: CadReadClient,
    drawing_reference: Mapping[str, object],
    drawing_observation: Mapping[str, object],
    artifact_bytes: bytes,
    candidate_state: Mapping[str, object],
    drawing_path: str,
    parent_reference: Mapping[str, object] | None,
    accepted_transition_evidence_sha256: str | None,
) -> dict[str, object]:
    if not isinstance(artifact_bytes, bytes):
        _fail("ARTIFACT_BYTES_INVALID")
    normalized_path = _normalize_drawing_path(drawing_path)
    try:
        reference = _dara.validate_drawing_artifact_reference(
            drawing_reference,
            expected_artifact_role="R3_CANDIDATE",
            parent_reference=parent_reference,
            accepted_transition_evidence_sha256=accepted_transition_evidence_sha256,
        )
        observation = _dara.validate_drawing_artifact_current_observation(
            drawing_observation
        )
        _dara.require_current_drawing_artifact_reference(
            reference=reference,
            observation=observation,
            artifact_bytes=artifact_bytes,
            parent_reference=parent_reference,
            accepted_transition_evidence_sha256=accepted_transition_evidence_sha256,
        )
        state = _candidate_revision.validate_candidate_revision_state(candidate_state)
    except CadReadFacadeError:
        raise
    except Exception as error:
        code = "DRAWING_ARTIFACT_STALE" if "STALE" in str(error) else "READ_BINDING_INVALID"
        raise CadReadFacadeError(code) from error

    selected_sha = state["current_candidate_revision_sha256"]
    if selected_sha is None:
        _fail("CANDIDATE_NOT_CURRENT")
    selected = next(
        (
            item
            for item in state["candidate_revisions"]
            if item["candidate_revision_sha256"] == selected_sha
        ),
        None,
    )
    if not isinstance(selected, Mapping):
        _fail("CANDIDATE_NOT_CURRENT")
    artifacts = selected.get("candidate_artifacts")
    if not isinstance(artifacts, Mapping):
        _fail("CANDIDATE_REFERENCE_MISMATCH")
    if any(
        artifacts.get(field) != reference[field]
        for field in ("reference_id", "reference_sha256", "artifact_sha256")
    ):
        _fail("CANDIDATE_REFERENCE_MISMATCH")
    if (
        artifacts.get("accepted_transition_evidence_sha256")
        != accepted_transition_evidence_sha256
    ):
        _fail("CANDIDATE_TRANSITION_MISMATCH")
    mutation = selected.get("mutation_evidence")
    if (
        not isinstance(mutation, Mapping)
        or mutation.get("accepted_transition_evidence_sha256")
        != accepted_transition_evidence_sha256
    ):
        _fail("MUTATION_TRANSITION_MISMATCH")
    if selected.get("run_id") != reference["run_id"]:
        _fail("CANDIDATE_SCOPE_MISMATCH")
    _validate_client_drawing(client, normalized_path)
    return {
        "run_id": reference["run_id"],
        "project_id": reference["project_id"],
        "drawing_id": reference["drawing_id"],
        "drawing_reference_id": reference["reference_id"],
        "drawing_reference_sha256": reference["reference_sha256"],
        "artifact_sha256": reference["artifact_sha256"],
        "candidate_revision_id": selected["revision_id"],
        "candidate_revision_sha256": selected["candidate_revision_sha256"],
        "candidate_state_sha256": state["state_sha256"],
        "drawing_path": normalized_path,
        "current_observation_id": observation["lookup_id"],
        "current_observation_sha256": observation["lookup_sha256"],
    }


def _read_entity_index(
    client: CadReadClient, layer: str | None, expected_path: str
) -> list[dict[str, str]]:
    try:
        raw_entities = client.entity_list(layer=layer)
    except Exception as error:
        raise CadReadFacadeError("ENTITY_LIST_FAILED") from error
    _validate_client_drawing(client, expected_path)
    if not isinstance(raw_entities, list):
        _fail("ENTITY_LIST_INVALID")
    entities: list[dict[str, str]] = []
    for raw in raw_entities:
        if not isinstance(raw, Mapping):
            _fail("ENTITY_LIST_INVALID")
        item = {
            "handle": _string(raw.get("handle"), "ENTITY_LIST_INVALID"),
            "type": _string(raw.get("type"), "ENTITY_LIST_INVALID"),
            "layer": _string(raw.get("layer"), "ENTITY_LIST_INVALID"),
        }
        entities.append(item)
    entities.sort(key=lambda item: (item["handle"].casefold(), item["handle"]))
    return entities


def _project_entity(
    client: CadReadClient,
    index: Mapping[str, str],
    projection: Sequence[str],
    expected_path: str,
) -> dict[str, object]:
    raw: Mapping[str, object] = index
    if any(field not in _BASE_FIELDS for field in projection):
        _validate_client_drawing(client, expected_path)
        try:
            detailed = client.entity_get(index["handle"])
        except Exception as error:
            raise CadReadFacadeError("ENTITY_GET_FAILED") from error
        if not isinstance(detailed, Mapping):
            _fail("ENTITY_GET_INVALID")
        if any(detailed.get(field) != index[field] for field in _BASE_FIELDS):
            _fail("ENTITY_IDENTITY_MISMATCH")
        _validate_client_drawing(client, expected_path)
        raw = detailed
    result: dict[str, object] = {}
    for field in projection:
        if field not in raw:
            _fail("ENTITY_FIELD_UNAVAILABLE")
        result[field] = deepcopy(raw[field])
    return result


def _finish_result(payload: dict[str, object]) -> dict[str, object]:
    try:
        result_sha256 = canonical_json_sha256(payload)
        result = {
            **payload,
            "query_id": "cad-query-" + result_sha256,
            "result_sha256": result_sha256,
        }
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as error:
        raise CadReadFacadeError("RESULT_INVALID") from error
    if len(encoded) > MAX_QUERY_RESULT_BYTES:
        _fail("RESULT_OVERSIZED")
    return result


def _finish_bound_result(
    *, client: CadReadClient, expected_path: str, payload: dict[str, object]
) -> dict[str, object]:
    """Re-check the active drawing immediately before finalizing a read result."""

    _validate_client_drawing(client, expected_path)
    return _finish_result(payload)


def observe_drawing(
    *,
    client: CadReadClient,
    drawing_reference: Mapping[str, object],
    drawing_observation: Mapping[str, object],
    artifact_bytes: bytes,
    candidate_state: Mapping[str, object],
    drawing_path: str,
    parent_reference: Mapping[str, object] | None = None,
    accepted_transition_evidence_sha256: str | None = None,
) -> dict[str, object]:
    """Return a bounded structural summary for the exact current candidate."""

    binding = _validated_binding(
        client=client,
        drawing_reference=drawing_reference,
        drawing_observation=drawing_observation,
        artifact_bytes=artifact_bytes,
        candidate_state=candidate_state,
        drawing_path=drawing_path,
        parent_reference=parent_reference,
        accepted_transition_evidence_sha256=accepted_transition_evidence_sha256,
    )
    entities = _read_entity_index(client, None, binding["drawing_path"])
    by_type: dict[str, int] = {}
    by_layer: dict[str, int] = {}
    for entity in entities:
        by_type[entity["type"]] = by_type.get(entity["type"], 0) + 1
        by_layer[entity["layer"]] = by_layer.get(entity["layer"], 0) + 1
    payload = {
        "schema_version": CAD_READ_FACADE_SCHEMA_VERSION,
        "operation": "observe_drawing",
        "binding": binding,
        "summary": {
            "entity_count": len(entities),
            "by_type": dict(sorted(by_type.items())),
            "by_layer": dict(sorted(by_layer.items())),
            "sample_entities": deepcopy(entities[:MAX_SUMMARY_SAMPLE_COUNT]),
        },
    }
    return _finish_bound_result(
        client=client,
        expected_path=binding["drawing_path"],
        payload=payload,
    )


def query_entities(
    *,
    client: CadReadClient,
    drawing_reference: Mapping[str, object],
    drawing_observation: Mapping[str, object],
    artifact_bytes: bytes,
    candidate_state: Mapping[str, object],
    drawing_path: str,
    parent_reference: Mapping[str, object] | None = None,
    accepted_transition_evidence_sha256: str | None = None,
    entity_type: str | None = None,
    layer: str | None = None,
    projection: Sequence[str] = ("handle", "type", "layer"),
    limit: int = 100,
) -> dict[str, object]:
    """Read a deterministic, filtered, field-whitelisted entity slice."""

    normalized_limit = _normalize_limit(limit)
    normalized_projection = _normalize_projection(projection)
    normalized_type = _normalize_filter(entity_type, "ENTITY_TYPE_INVALID")
    normalized_layer = _normalize_filter(layer, "LAYER_INVALID")
    binding = _validated_binding(
        client=client,
        drawing_reference=drawing_reference,
        drawing_observation=drawing_observation,
        artifact_bytes=artifact_bytes,
        candidate_state=candidate_state,
        drawing_path=drawing_path,
        parent_reference=parent_reference,
        accepted_transition_evidence_sha256=accepted_transition_evidence_sha256,
    )
    indexed = _read_entity_index(client, normalized_layer, binding["drawing_path"])
    matches = [
        item
        for item in indexed
        if (normalized_type is None or item["type"] == normalized_type)
        and (normalized_layer is None or item["layer"] == normalized_layer)
    ]
    selected = matches[:normalized_limit]
    payload = {
        "schema_version": CAD_READ_FACADE_SCHEMA_VERSION,
        "operation": "query_entities",
        "binding": binding,
        "filters": {"entity_type": normalized_type, "layer": normalized_layer},
        "projection": normalized_projection,
        "limit": normalized_limit,
        "total_count": len(matches),
        "returned_count": len(selected),
        "truncated": len(matches) > normalized_limit,
        "entities": [
            _project_entity(
                client, entity, normalized_projection, binding["drawing_path"]
            )
            for entity in selected
        ],
    }
    return _finish_bound_result(
        client=client,
        expected_path=binding["drawing_path"],
        payload=payload,
    )


__all__ = [
    "CAD_READ_FACADE_SCHEMA_VERSION",
    "CadReadClient",
    "MAX_QUERY_RESULT_BYTES",
    "MAX_QUERY_RESULT_COUNT",
    "CadReadFacadeError",
    "observe_drawing",
    "query_entities",
    "validate_observe_drawing_result",
]
