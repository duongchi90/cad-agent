from __future__ import annotations

from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path

import pytest

from cad_agent.candidate_revision import (
    build_candidate_revision,
    build_candidate_revision_state,
)


_FIXTURE_MODULE = Path(__file__).with_name("test_cad_agent_candidate_revision.py")
_DRAWING_PATH = r"C:\temp\cad-agent-mech1a-candidate\candidate.dwg"
_FOREIGN_DRAWING_PATH = r"C:\temp\cad-agent-mech1a-candidate\foreign.dwg"


def _module():
    try:
        return importlib.import_module("cad_agent.drawing_query")
    except ModuleNotFoundError as error:
        raise AssertionError("MECH-1A drawing query adapter is not implemented") from error


def _fixture_module():
    spec = importlib.util.spec_from_file_location("mech1a_candidate_fixtures", _FIXTURE_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bound() -> dict[str, object]:
    fixtures = _fixture_module()
    material = fixtures._accepted_r3_material()
    candidate = build_candidate_revision(**fixtures._valid_args(material=material))
    state = build_candidate_revision_state(
        candidate_revisions=[candidate],
        current_candidate_revision_sha256=candidate["candidate_revision_sha256"],
    )
    return {
        "reference": material["child_reference"],
        "current_observation": material["child_observation"],
        "artifact_bytes": material["child_bytes"],
        "parent_reference": material["parent_reference"],
        "accepted_transition_evidence_sha256": material[
            "accepted_transition_evidence_sha256"
        ],
        "registry": material["registry"],
        "registry_upstream_context": material["context"],
        "candidate_state": state,
    }


class _RecordingClient:
    def __init__(self, drawing_path: str = _DRAWING_PATH) -> None:
        self.drawing_path = drawing_path
        self.variable_calls: list[list[str]] = []
        self.entity_get_calls: list[str] = []
        self.entity_list_calls = 0
        self.entities: dict[str, dict[str, object]] = {
            "10": {
                "handle": "10",
                "type": "LINE",
                "layer": "SHAFT",
                "start": (0.0, 0.0),
                "end": (100.0, 0.0),
            },
            "30": {
                "handle": "30",
                "type": "CIRCLE",
                "layer": "HOLE",
                "center": (20.0, 5.0),
                "radius": 2.0,
            },
            "C3D4": {
                "handle": "C3D4",
                "type": "INSERT",
                "layer": "BODY",
            },
        }

    def drawing_get_variables(self, names: list[str]) -> dict[str, object]:
        self.variable_calls.append(list(names))
        path = Path(self.drawing_path)
        return {"DWGPREFIX": str(path.parent) + "\\", "DWGNAME": path.name}

    def entity_list(self, layer: str | None = None) -> list[dict[str, object]]:
        self.entity_list_calls += 1
        del layer
        return list(self.entities.values())

    def entity_get(self, entity_id: str) -> dict[str, object]:
        self.entity_get_calls.append(entity_id)
        if entity_id not in self.entities:
            raise KeyError(entity_id)
        return dict(self.entities[entity_id])


def _live_query(**overrides: object) -> dict[str, object]:
    query: dict[str, object] = {
        "schema_version": "entity-query-1.0",
        "handles": ["10"],
        "component_ids": [],
        "view_ids": [],
        "detail": "GEOMETRY",
    }
    query.update(overrides)
    return query


def test_public_surface_and_offline_observation_are_bounded() -> None:
    module = _module()
    assert module.DRAWING_OBSERVATION_SCHEMA_VERSION == "drawing-observation-1.0"
    assert module.ENTITY_QUERY_SCHEMA_VERSION == "entity-query-1.0"
    assert module.ENTITY_QUERY_RESULT_SCHEMA_VERSION == "entity-query-result-1.0"
    assert issubclass(module.DrawingQueryError, ValueError)

    observation = module.observe_drawing(**_bound(), client=None)

    assert observation["schema_version"] == "drawing-observation-1.0"
    assert observation["live_session"] == {"status": "NOT_OBSERVED"}
    assert observation["structural_summary"]["whole_drawing_entity_count_status"] == (
        "NOT_ENUMERATED"
    )
    assert observation["structural_summary"]["candidate_binding_count"] == 1
    assert len(observation["observation_sha256"]) == 64


def test_observation_is_deterministic_and_validated() -> None:
    module = _module()
    first = module.observe_drawing(**_bound(), client=None)
    second = module.observe_drawing(**_bound(), client=None)

    assert first == second
    assert module.validate_drawing_observation(first) == first

    tampered = deepcopy(first)
    tampered["structural_summary"]["candidate_binding_count"] = 99
    with pytest.raises(module.DrawingQueryError, match="OBSERVATION_HASH_MISMATCH"):
        module.validate_drawing_observation(tampered)

    extra = deepcopy(first)
    extra["unexpected"] = True
    with pytest.raises(module.DrawingQueryError, match="OBSERVATION_SCHEMA_INVALID"):
        module.validate_drawing_observation(extra)


def test_exact_handle_query_uses_only_bounded_entity_get_calls() -> None:
    module = _module()
    client = _RecordingClient()
    result = module.query_entities(
        client=client,
        **_bound(),
        expected_active_document_path=_DRAWING_PATH,
        query=_live_query(handles=["30", "10"]),
    )

    assert client.entity_list_calls == 0
    assert client.entity_get_calls == ["10", "30"]
    assert result["normalized_query"]["handles"] == ["10", "30"]
    assert [item["handle"] for item in result["entities"]] == ["10", "30"]
    assert result["entities"][0]["start"] == (0.0, 0.0)
    assert len(result["result_sha256"]) == 64
    assert module.validate_entity_query_result(result) == result


def test_component_selector_resolves_only_registry_bound_handle() -> None:
    module = _module()
    bound = _bound()
    component_id = bound["registry"]["components"][0]["component_id"]
    client = _RecordingClient()

    result = module.query_entities(
        client=client,
        **bound,
        expected_active_document_path=_DRAWING_PATH,
        query=_live_query(handles=[], component_ids=[component_id]),
    )

    assert client.entity_list_calls == 0
    assert client.entity_get_calls == ["C3D4"]
    assert result["entities"] == [
        {"handle": "C3D4", "type": "INSERT", "layer": "BODY"}
    ]


def test_missing_direct_handle_is_categorical_not_found_without_scan() -> None:
    module = _module()
    client = _RecordingClient()
    result = module.query_entities(
        client=client,
        **_bound(),
        expected_active_document_path=_DRAWING_PATH,
        query=_live_query(handles=["DEADBEef"]),
    )

    assert client.entity_list_calls == 0
    assert client.entity_get_calls == ["DEADBEef"]
    assert result["entities"] == [{"handle": "DEADBEef", "status": "NOT_FOUND"}]


def test_stale_binding_rejects_before_any_live_read() -> None:
    module = _module()
    bound = _bound()
    client = _RecordingClient()
    bound["artifact_bytes"] = b"stale-bytes"

    with pytest.raises(module.DrawingQueryError, match="DRAWING_ARTIFACT_STALE"):
        module.query_entities(
            client=client,
            **bound,
            expected_active_document_path=_DRAWING_PATH,
            query=_live_query(),
        )

    assert client.variable_calls == []
    assert client.entity_get_calls == []
    assert client.entity_list_calls == 0


def test_wrong_active_document_rejects_before_entity_get() -> None:
    module = _module()
    client = _RecordingClient(_FOREIGN_DRAWING_PATH)

    with pytest.raises(module.DrawingQueryError, match="ACTIVE_DOCUMENT_MISMATCH"):
        module.query_entities(
            client=client,
            **_bound(),
            expected_active_document_path=_DRAWING_PATH,
            query=_live_query(),
        )

    assert client.entity_get_calls == []
    assert client.entity_list_calls == 0


def test_live_identity_allowlist_is_code_owned() -> None:
    module = _module()
    client = _RecordingClient()
    module.query_entities(
        client=client,
        **_bound(),
        expected_active_document_path=_DRAWING_PATH,
        query=_live_query(),
    )

    assert client.variable_calls == [
        ["DWGPREFIX", "DWGNAME", "CTAB", "CVPORT", "TILEMODE", "INSUNITS"]
    ]


def test_query_rejects_extra_fields_and_unbounded_selectors() -> None:
    module = _module()
    for bad in (
        {**_live_query(), "raw_lisp": "(command)"},
        {**_live_query(), "handles": [str(index) for index in range(65)]},
        {**_live_query(), "detail": "ALL"},
    ):
        with pytest.raises(module.DrawingQueryError):
            module.validate_entity_query(bad)


def test_query_rejects_stale_or_missing_candidate_state() -> None:
    module = _module()
    bound = _bound()
    stale = deepcopy(bound)
    stale["candidate_state"]["current_candidate_revision_sha256"] = None
    with pytest.raises(module.DrawingQueryError, match="CANDIDATE_NOT_CURRENT"):
        module.observe_drawing(**stale, client=None)

    foreign = deepcopy(bound)
    foreign["registry"] = deepcopy(bound["registry"])
    foreign["registry"]["upstream_bindings"]["candidate_id"] = "foreign"
    with pytest.raises(module.DrawingQueryError, match="REGISTRY_BINDING_MISMATCH"):
        module.observe_drawing(**foreign, client=None)


def test_registry_bound_missing_entity_fails_closed() -> None:
    module = _module()
    bound = _bound()
    component_id = bound["registry"]["components"][0]["component_id"]
    client = _RecordingClient()
    del client.entities["C3D4"]

    with pytest.raises(
        module.DrawingQueryError, match="REGISTRY_ENTITY_BINDING_NOT_OBSERVED"
    ):
        module.query_entities(
            client=client,
            **bound,
            expected_active_document_path=_DRAWING_PATH,
            query=_live_query(handles=[], component_ids=[component_id]),
        )

    assert client.entity_list_calls == 0


def test_query_result_rejects_tampering() -> None:
    module = _module()
    client = _RecordingClient()
    result = module.query_entities(
        client=client,
        **_bound(),
        expected_active_document_path=_DRAWING_PATH,
        query=_live_query(),
    )
    tampered = deepcopy(result)
    tampered["entities"][0]["layer"] = "FOREIGN"

    with pytest.raises(module.DrawingQueryError, match="RESULT_HASH_MISMATCH"):
        module.validate_entity_query_result(tampered)


def test_production_adapter_has_no_unbounded_or_mutating_owner_calls() -> None:
    module = _module()
    source = Path(module.__file__).read_text(encoding="utf-8")
    forbidden = (
        ".entity_list(",
        ".drawing_open(",
        ".drawing_close(",
        ".drawing_save(",
        ".entity_erase(",
        ".entity_create_",
        "subprocess",
        "os.system",
        "eval(",
        "exec(",
        "raw_lisp",
    )
    assert not [marker for marker in forbidden if marker in source]
