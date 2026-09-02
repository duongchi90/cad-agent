from __future__ import annotations

from copy import deepcopy
import importlib.util
from importlib import import_module
from pathlib import Path

import pytest

from cad_agent.candidate_revision import (
    build_candidate_revision,
    build_candidate_revision_state,
)
from cad_agent.drawing_contracts import canonical_json_sha256


_FIXTURE_MODULE = Path(__file__).with_name("test_cad_agent_candidate_revision.py")
_DRAWING_PATH = r"C:\temp\cad-agent-phase1-candidate\candidate.dwg"
_FOREIGN_DRAWING_PATH = r"C:\temp\cad-agent-phase1-candidate\foreign.dwg"


def _facade():
    try:
        return import_module("cad_agent.cad_read_facade")
    except ModuleNotFoundError as error:
        raise AssertionError("Phase 1 CAD read facade is not implemented") from error


def _candidate_fixtures() -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("phase1_candidate_fixtures", _FIXTURE_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    material = module._accepted_r3_material()
    candidate = build_candidate_revision(**module._valid_args(material=material))
    state = build_candidate_revision_state(
        candidate_revisions=[candidate],
        current_candidate_revision_sha256=candidate["candidate_revision_sha256"],
    )
    return {
        "drawing_reference": material["child_reference"],
        "drawing_observation": material["child_observation"],
        "artifact_bytes": material["child_bytes"],
        "parent_reference": material["parent_reference"],
        "accepted_transition_evidence_sha256": material[
            "accepted_transition_evidence_sha256"
        ],
        "candidate_state": state,
        "candidate": candidate,
    }


class _BoundFakeCadClient:
    def __init__(
        self,
        drawing_path: str = _DRAWING_PATH,
        fail_entity_get: bool = False,
    ) -> None:
        self._entities: dict[str, dict[str, object]] = {}
        self.fail_entity_get = fail_entity_get
        self._drawing_path = drawing_path

    def drawing_get_variables(self, names: list[str]) -> dict[str, object]:
        del names
        path = Path(self._drawing_path)
        return {"DWGPREFIX": str(path.parent) + "\\", "DWGNAME": path.name}

    def preload_entity(
        self,
        handle: str,
        entity_type: str,
        layer: str,
        geometry: dict[str, object],
    ) -> None:
        self._entities[handle] = {
            "handle": handle,
            "type": entity_type,
            "layer": layer,
            **geometry,
        }

    def entity_list(self, layer: str | None = None) -> list[dict[str, object]]:
        return [
            {
                "handle": entity["handle"],
                "type": entity["type"],
                "layer": entity["layer"],
            }
            for entity in self._entities.values()
            if layer is None or layer == entity["layer"]
        ]

    def entity_get(self, entity_id: str) -> dict[str, object]:
        if self.fail_entity_get:
            raise RuntimeError("entity get unavailable")
        return dict(self._entities[entity_id])


def _client(drawing_path: str = _DRAWING_PATH) -> _BoundFakeCadClient:
    client = _BoundFakeCadClient(drawing_path)
    client.preload_entity(
        "10",
        "LINE",
        "SHAFT",
        {"start": (0.0, 0.0), "end": (100.0, 0.0)},
    )
    client.preload_entity(
        "20",
        "LINE",
        "SHAFT",
        {"start": (0.0, 10.0), "end": (100.0, 10.0)},
    )
    client.preload_entity("30", "CIRCLE", "HOLE", {"center": (20.0, 5.0), "radius": 2.0})
    return client


class _MutationGuardedClient(_BoundFakeCadClient):
    def _forbid(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("CAD read facade invoked a mutation owner")

    drawing_close = _forbid
    drawing_save = _forbid
    drawing_save_as_dxf = _forbid
    block_update_attribute = _forbid
    entity_create_line = _forbid
    entity_create_circle = _forbid
    entity_create_arc = _forbid
    annotation_create_text = _forbid
    entity_erase = _forbid


def _bound_kwargs() -> dict[str, object]:
    fixtures = _candidate_fixtures()
    fixtures.pop("candidate")
    fixtures["drawing_path"] = _DRAWING_PATH
    return fixtures


def test_observe_drawing_returns_exact_bound_identity_and_deterministic_summary() -> None:
    bound = _bound_kwargs()
    first = _facade().observe_drawing(client=_client(), **bound)
    second = _facade().observe_drawing(client=_client(), **bound)

    assert first == second
    assert first["operation"] == "observe_drawing"
    assert first["binding"]["drawing_id"] == bound["drawing_reference"]["drawing_id"]
    assert first["binding"]["artifact_sha256"] == bound["drawing_reference"]["artifact_sha256"]
    assert first["binding"]["candidate_revision_sha256"] == bound["candidate_state"][
        "current_candidate_revision_sha256"
    ]
    assert first["binding"]["candidate_state_sha256"] == bound["candidate_state"]["state_sha256"]
    assert first["binding"]["drawing_path"] == _DRAWING_PATH.casefold()
    assert first["summary"]["entity_count"] == 3
    assert first["summary"]["by_type"] == {"CIRCLE": 1, "LINE": 2}
    assert first["summary"]["by_layer"] == {"HOLE": 1, "SHAFT": 2}
    assert len(first["result_sha256"]) == 64


def test_validate_observe_drawing_result_accepts_owner_output_and_returns_copy() -> None:
    bound = _bound_kwargs()
    payload = _facade().observe_drawing(client=_client(), **bound)

    validated = _facade().validate_observe_drawing_result(payload)

    assert validated == payload
    assert validated is not payload
    assert validated["binding"] is not payload["binding"]


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("operation", "query_entities", "RESULT_SCHEMA_INVALID"),
        ("query_id", "cad-query-wrong", "RESULT_ID_MISMATCH"),
        ("result_sha256", "0" * 64, "RESULT_HASH_MISMATCH"),
    ],
)
def test_validate_observe_drawing_result_rejects_tampered_owner_output(
    field: str, value: object, error: str
) -> None:
    payload = _facade().observe_drawing(client=_client(), **_bound_kwargs())
    tampered = deepcopy(payload)
    tampered[field] = value

    with pytest.raises(_facade().CadReadFacadeError, match=error):
        _facade().validate_observe_drawing_result(tampered)


def test_validate_observe_drawing_result_rejects_extra_root_field() -> None:
    payload = _facade().observe_drawing(client=_client(), **_bound_kwargs())
    tampered = deepcopy(payload)
    tampered["unexpected"] = True

    with pytest.raises(_facade().CadReadFacadeError, match="RESULT_SCHEMA_INVALID"):
        _facade().validate_observe_drawing_result(tampered)


def test_validate_observe_drawing_result_rejects_malformed_binding_sha() -> None:
    payload = _facade().observe_drawing(client=_client(), **_bound_kwargs())
    tampered = deepcopy(payload)
    tampered["binding"]["artifact_sha256"] = "not-a-sha"

    with pytest.raises(_facade().CadReadFacadeError, match="RESULT_BINDING_INVALID"):
        _facade().validate_observe_drawing_result(tampered)


def test_validate_observe_drawing_result_rejects_oversized_summary_sample() -> None:
    payload = _facade().observe_drawing(client=_client(), **_bound_kwargs())
    tampered = deepcopy(payload)
    tampered["summary"]["sample_entities"] = [
        {"handle": str(index), "type": "LINE", "layer": "SHAFT"}
        for index in range(21)
    ]

    with pytest.raises(_facade().CadReadFacadeError, match="RESULT_SUMMARY_INVALID"):
        _facade().validate_observe_drawing_result(tampered)


def test_query_entities_filters_projects_and_bounds_results() -> None:
    bound = _bound_kwargs()
    result = _facade().query_entities(
        client=_client(),
        **bound,
        entity_type="LINE",
        layer="SHAFT",
        projection=("handle", "type", "layer", "start", "end"),
        limit=1,
    )

    assert result["operation"] == "query_entities"
    assert result["total_count"] == 2
    assert result["returned_count"] == 1
    assert result["truncated"] is True
    assert result["entities"] == [
        {
            "handle": "10",
            "type": "LINE",
            "layer": "SHAFT",
            "start": (0.0, 0.0),
            "end": (100.0, 0.0),
        }
    ]
    assert result["filters"] == {"entity_type": "LINE", "layer": "SHAFT"}
    assert result["projection"] == ["handle", "type", "layer", "start", "end"]


def test_query_rejects_stale_artifact_before_reading_entities() -> None:
    bound = _bound_kwargs()
    stale = deepcopy(bound)
    stale["artifact_bytes"] = b"stale-candidate-bytes"

    with pytest.raises(_facade().CadReadFacadeError, match="DRAWING_ARTIFACT_STALE"):
        _facade().query_entities(client=_client(), **stale)


def test_query_rejects_non_current_candidate_state() -> None:
    bound = _bound_kwargs()
    stale = deepcopy(bound)
    stale["state"] = build_candidate_revision_state(
        candidate_revisions=[_candidate_fixtures()["candidate"]],
        current_candidate_revision_sha256=None,
    )
    stale["candidate_state"] = stale.pop("state")

    with pytest.raises(_facade().CadReadFacadeError, match="CANDIDATE_NOT_CURRENT"):
        _facade().query_entities(client=_client(), **stale)


def test_query_rejects_candidate_with_unbound_transition_evidence() -> None:
    spec = importlib.util.spec_from_file_location(
        "phase1_transition_fixtures", _FIXTURE_MODULE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    material = module._accepted_r3_material()
    args = module._valid_args(material=material, tag="unbound-transition")
    args["mutation_evidence"]["accepted_transition_evidence_sha256"] = "f" * 64
    args["mutation_evidence"]["evidence_sha256"] = canonical_json_sha256(
        {
            key: value
            for key, value in args["mutation_evidence"].items()
            if key != "evidence_sha256"
        }
    )
    candidate = build_candidate_revision(**args)
    bound = _bound_kwargs()
    bound["candidate_state"] = build_candidate_revision_state(
        candidate_revisions=[candidate],
        current_candidate_revision_sha256=candidate["candidate_revision_sha256"],
    )

    with pytest.raises(
        _facade().CadReadFacadeError, match="CANDIDATE_TRANSITION_MISMATCH"
    ):
        _facade().query_entities(client=_client(), **bound)


def test_query_rejects_candidate_with_conflicting_mutation_evidence() -> None:
    bound = _bound_kwargs()
    candidate = deepcopy(_candidate_fixtures()["candidate"])
    mutation = candidate["mutation_evidence"]
    mutation["accepted_transition_evidence_sha256"] = "f" * 64
    mutation["evidence_sha256"] = canonical_json_sha256(
        {
            key: value for key, value in mutation.items() if key != "evidence_sha256"
        }
    )
    candidate["revision_id"] = "candidate:" + canonical_json_sha256(
        {
            key: value
            for key, value in candidate.items()
            if key not in {"revision_id", "candidate_revision_sha256"}
        }
    )
    candidate["candidate_revision_sha256"] = canonical_json_sha256(
        {
            key: value
            for key, value in candidate.items()
            if key != "candidate_revision_sha256"
        }
    )
    bound["candidate_state"] = build_candidate_revision_state(
        candidate_revisions=[candidate],
        current_candidate_revision_sha256=candidate["candidate_revision_sha256"],
    )

    with pytest.raises(
        _facade().CadReadFacadeError, match="MUTATION_TRANSITION_MISMATCH"
    ):
        _facade().query_entities(client=_client(), **bound)


def test_query_rejects_foreign_client_drawing() -> None:
    with pytest.raises(_facade().CadReadFacadeError, match="DRAWING_IDENTITY_MISMATCH"):
        _facade().query_entities(
            client=_client(_FOREIGN_DRAWING_PATH), **_bound_kwargs()
        )


def test_query_rejects_active_drawing_change_during_read_epoch() -> None:
    class _FlippingClient(_BoundFakeCadClient):
        def __init__(self) -> None:
            super().__init__()
            self._identity_reads = 0

        def drawing_get_variables(self, names: list[str]) -> dict[str, object]:
            self._identity_reads += 1
            path = (
                _DRAWING_PATH
                if self._identity_reads == 1
                else _FOREIGN_DRAWING_PATH
            )
            return _BoundFakeCadClient(path).drawing_get_variables(names)

    client = _FlippingClient()
    client.preload_entity(
        "10", "LINE", "SHAFT", {"start": (0.0, 0.0), "end": (1.0, 0.0)}
    )

    with pytest.raises(_facade().CadReadFacadeError, match="DRAWING_IDENTITY_MISMATCH"):
        _facade().query_entities(client=client, **_bound_kwargs())


@pytest.mark.parametrize("operation", ("observe_drawing", "query_entities"))
def test_read_rejects_active_drawing_change_after_payload_assembly(
    operation: str,
) -> None:
    class _LateFlippingClient(_BoundFakeCadClient):
        def __init__(self) -> None:
            super().__init__()
            self._identity_reads = 0

        def drawing_get_variables(self, names: list[str]) -> dict[str, object]:
            self._identity_reads += 1
            path = (
                _DRAWING_PATH
                if self._identity_reads <= 2
                else _FOREIGN_DRAWING_PATH
            )
            return _BoundFakeCadClient(path).drawing_get_variables(names)

    client = _LateFlippingClient()
    client.preload_entity(
        "10", "LINE", "SHAFT", {"start": (0.0, 0.0), "end": (1.0, 0.0)}
    )
    bound = _bound_kwargs()

    with pytest.raises(_facade().CadReadFacadeError, match="DRAWING_IDENTITY_MISMATCH"):
        if operation == "observe_drawing":
            _facade().observe_drawing(client=client, **bound)
        else:
            _facade().query_entities(client=client, **bound)


def test_query_enforces_layer_filter_when_owner_ignores_filter() -> None:
    class _NoncompliantLayerClient(_BoundFakeCadClient):
        def entity_list(self, layer: str | None = None) -> list[dict[str, object]]:
            del layer
            return super().entity_list()

    client = _NoncompliantLayerClient()
    client.preload_entity(
        "10", "LINE", "SHAFT", {"start": (0.0, 0.0), "end": (1.0, 0.0)}
    )
    client.preload_entity("30", "CIRCLE", "HOLE", {"center": (1.0, 1.0), "radius": 1.0})
    result = _facade().query_entities(
        client=client,
        **_bound_kwargs(),
        layer="SHAFT",
    )

    assert result["returned_count"] == 1
    assert all(entity["layer"] == "SHAFT" for entity in result["entities"])


def test_query_rejects_detail_identity_drift() -> None:
    bound = _bound_kwargs()

    class _ForeignDetailClient(_BoundFakeCadClient):
        def entity_get(self, entity_id: str) -> dict[str, object]:
            result = super().entity_get(entity_id)
            result["layer"] = "FOREIGN"
            return result

    client = _ForeignDetailClient(fail_entity_get=False)
    client.preload_entity("10", "LINE", "SHAFT", {"start": (0.0, 0.0), "end": (1.0, 0.0)})

    with pytest.raises(_facade().CadReadFacadeError, match="ENTITY_IDENTITY_MISMATCH"):
        _facade().query_entities(
            client=client,
            **bound,
            entity_type="LINE",
            projection=("handle", "type", "layer", "start", "end"),
        )


def test_query_rejects_missing_projected_field() -> None:
    bound = _bound_kwargs()

    with pytest.raises(_facade().CadReadFacadeError, match="ENTITY_FIELD_UNAVAILABLE"):
        _facade().query_entities(
            client=_client(),
            **bound,
            entity_type="LINE",
            projection=("handle", "type", "layer", "content"),
        )


def test_read_facade_does_not_call_mutation_owners() -> None:
    bound = _bound_kwargs()
    client = _MutationGuardedClient(fail_entity_get=False)
    client.preload_entity("10", "LINE", "SHAFT", {"start": (0.0, 0.0), "end": (1.0, 0.0)})

    result = _facade().query_entities(client=client, **bound)

    assert result["returned_count"] == 1


@pytest.mark.parametrize(
    ("projection", "limit", "error"),
    [
        (("handle", "raw_lisp"), 10, "PROJECTION_UNSUPPORTED"),
        (("handle",), 0, "LIMIT_INVALID"),
        (("handle",), 101, "LIMIT_INVALID"),
    ],
)
def test_query_rejects_unbounded_or_unsupported_requests(
    projection: tuple[str, ...], limit: int, error: str
) -> None:
    with pytest.raises(_facade().CadReadFacadeError, match=error):
        _facade().query_entities(
            client=_client(),
            **_bound_kwargs(),
            projection=projection,
            limit=limit,
        )
