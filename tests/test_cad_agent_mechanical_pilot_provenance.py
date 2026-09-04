from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from cad_agent import component_view_registry as r3
from cad_agent import drawing_query
from cad_agent import mechanical_pilot_provenance as provenance
from cad_agent.candidate_revision import CandidateRevisionError, validate_candidate_revision
from cad_agent.mechanical_pilot import build_simple_shaft_pilot


FIXTURE = Path(__file__).parent / "fixtures" / "phase3_synthetic_simple_shaft_v1.json"
SCOPE = {
    "run_id": "run-generated-pilot-001",
    "project_id": "project-generated-pilot",
    "drawing_id": "drawing-generated-pilot",
}


def _pilot(tmp_path: Path):
    return build_simple_shaft_pilot(FIXTURE, tmp_path / "generated_candidate.dxf")


def _primitive_bound_pilot(tmp_path: Path):
    helper_path = Path(__file__).with_name("test_cad_agent_phase4_pilot_binding.py")
    spec = importlib.util.spec_from_file_location("phase4_pilot_test_helpers", helper_path)
    if spec is None or spec.loader is None:
        raise AssertionError("phase4 helper module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    primitive_path = tmp_path / "page_01.json"
    module._write_primitive(primitive_path)
    from cad_agent.mechanical_pilot import bind_simple_shaft_pilot_from_primitive

    return bind_simple_shaft_pilot_from_primitive(
        primitive_path, tmp_path / "primitive-candidate" / "candidate.dxf"
    )


def test_generated_pilot_packet_is_exact_and_replayable(tmp_path: Path) -> None:
    result = _pilot(tmp_path)

    packet = provenance.build_generated_pilot_provenance(result)
    replay = provenance.validate_generated_pilot_provenance(packet)

    assert packet == replay
    assert packet["schema_version"] == "generated-mechanical-pilot-provenance-1.0"
    assert packet["pilot_id"] == "synthetic-simple-stepped-shaft-v1"
    assert packet["candidate_id"] == (
        f"synthetic-simple-stepped-shaft-v1:{result.candidate_sha256}"
    )
    assert packet["source_sha256"] == (
        "1c86ce46261a3689d00bc18157087e418df0872ac0a6a4635c157f2b85677b8d"
    )
    assert packet["candidate_sha256"] == result.candidate_sha256
    assert len(packet["candidate_path_binding_sha256"]) == 64
    assert [item["primitive_id"] for item in packet["primitive_projections"]] == [
        "hole-axial-001",
        "shaft-profile-001:bottom-main",
        "shaft-profile-001:bottom-step",
        "shaft-profile-001:left-cap",
        "shaft-profile-001:right-cap",
        "shaft-profile-001:step-fall",
        "shaft-profile-001:step-rise",
        "shaft-profile-001:top-main",
        "shaft-profile-001:top-step",
    ]
    assert packet["feature_projections"] == sorted(
        packet["feature_projections"], key=lambda item: item["feature_id"]
    )
    assert len(packet["provenance_sha256"]) == 64


def test_generated_pilot_packet_rejects_tampering_and_unknown_fields(
    tmp_path: Path,
) -> None:
    packet = provenance.build_generated_pilot_provenance(_pilot(tmp_path))

    extra = deepcopy(packet)
    extra["unexpected"] = True
    with pytest.raises(provenance.GeneratedPilotProvenanceError, match="SCHEMA"):
        provenance.validate_generated_pilot_provenance(extra)

    foreign = deepcopy(packet)
    foreign["primitive_projections"][0]["entity_handle"] = "DEAD"
    with pytest.raises(provenance.GeneratedPilotProvenanceError, match="HASH"):
        provenance.validate_generated_pilot_provenance(foreign)


def test_generated_pilot_rejects_in_memory_ir_not_bound_to_source(
    tmp_path: Path,
) -> None:
    result = _pilot(tmp_path)
    primitive = result.primitive_doc.primitives[0]
    primitive.geometry.start.x += 1.0

    with pytest.raises(
        provenance.GeneratedPilotProvenanceError,
        match="SOURCE_BINDING|PILOT_SOURCE",
    ):
        provenance.build_generated_pilot_provenance(result)


def test_generated_pilot_rejects_candidate_file_drift_before_composition(
    tmp_path: Path,
) -> None:
    result = _pilot(tmp_path)
    result.candidate_path.write_bytes(result.candidate_path.read_bytes() + b"\n")

    with pytest.raises(
        provenance.GeneratedPilotProvenanceError,
        match="CANDIDATE_ARTIFACT_HASH_MISMATCH",
    ):
        provenance.compose_generated_pilot_query_binding(result, **SCOPE)


def test_generated_pilot_rejects_build_evidence_file_drift_before_composition(
    tmp_path: Path,
) -> None:
    result = _pilot(tmp_path)
    payload = json.loads(result.build_evidence_path.read_text(encoding="utf-8"))
    payload["build_result"]["entity_count"] += 1
    result.build_evidence_path.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(
        provenance.GeneratedPilotProvenanceError,
        match="BUILD_EVIDENCE_MISMATCH",
    ):
        provenance.compose_generated_pilot_query_binding(result, **SCOPE)


def test_generated_pilot_rejects_source_replacement_during_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source-pilot.json"
    source_path.write_bytes(FIXTURE.read_bytes())
    result = build_simple_shaft_pilot(
        source_path, tmp_path / "source-candidate" / "candidate.dxf"
    )
    original_loader = provenance.load_pilot_definition

    def replace_before_load(path: Path) -> dict[str, object]:
        path.write_bytes(path.read_bytes() + b" ")
        return original_loader(path)

    monkeypatch.setattr(provenance, "load_pilot_definition", replace_before_load)
    with pytest.raises(
        provenance.GeneratedPilotProvenanceError,
        match="SOURCE_ARTIFACT_DRIFT",
    ):
        provenance.compose_generated_pilot_query_binding(result, **SCOPE)


def test_generated_pilot_rejects_build_evidence_replacement_during_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _pilot(tmp_path)
    original_loader = provenance.load_build_evidence

    def replace_before_load(path: Path, dxf: Path):
        path.write_bytes(path.read_bytes() + b" ")
        return original_loader(path, dxf)

    monkeypatch.setattr(provenance, "load_build_evidence", replace_before_load)
    with pytest.raises(
        provenance.GeneratedPilotProvenanceError,
        match="BUILD_EVIDENCE_DRIFT",
    ):
        provenance.compose_generated_pilot_query_binding(result, **SCOPE)


def test_generated_pilot_reuses_primitive_bound_phase4_owner(tmp_path: Path) -> None:
    result = _primitive_bound_pilot(tmp_path)

    packet = provenance.build_generated_pilot_provenance(result)

    assert packet["pilot_id"] == "synthetic-simple-stepped-shaft-v1"
    assert packet["source_sha256"] == result.source_sha256
    assert len(packet["primitive_projections"]) == result.build.entity_count


def test_generated_r3_registry_accepts_only_explicit_generated_mode(
    tmp_path: Path,
) -> None:
    result = _pilot(tmp_path)
    inputs = provenance.build_generated_pilot_r3_inputs(result)

    registry = r3.build_component_view_registry(**inputs)

    assert registry["schema_version"] == "component-view-registry-1.1"
    assert registry["upstream_bindings"]["provenance_mode"] == (
        "GENERATED_MECHANICAL_PILOT"
    )
    assert registry["upstream_bindings"]["candidate_path_binding_sha256"] == (
        inputs["upstream_context"]["mechanical_pilot_provenance"][
            "candidate_path_binding_sha256"
        ]
    )
    assert [component["origin_class"] for component in registry["components"]] == [
        "RECONSTRUCTED_NEW",
        "RECONSTRUCTED_NEW",
    ]
    assert r3.validate_component_view_registry(
        registry, upstream_context=inputs["upstream_context"]
    ) == registry
    assert r3.component_view_registry_provenance_evidence(
        registry, upstream_context=inputs["upstream_context"]
    )["registry_snapshot_sha256"] == registry["registry_snapshot_sha256"]


def test_generated_r3_rejects_foreign_handle_and_mixed_base_context(
    tmp_path: Path,
) -> None:
    result = _pilot(tmp_path)
    inputs = provenance.build_generated_pilot_r3_inputs(result)

    foreign = deepcopy(inputs["components"])
    foreign[0]["candidate_entity_bindings"][0]["entity_handle"] = "DEAD"
    with pytest.raises(r3.ComponentViewRegistryError, match="CANDIDATE|BINDING|FOREIGN"):
        r3.build_component_view_registry(
            upstream_context=inputs["upstream_context"], components=foreign
        )

    mixed_context = deepcopy(inputs["upstream_context"])
    mixed_context["reuse_handoff"] = {}
    with pytest.raises(r3.ComponentViewRegistryError, match="UPSTREAM|MIXED"):
        r3.build_component_view_registry(
            upstream_context=mixed_context, components=inputs["components"]
        )


@pytest.mark.parametrize("tampered_field", ["source", "semantic", "build"])
def test_generated_r3_rejects_tampered_upstream_checksums(
    tmp_path: Path, tampered_field: str
) -> None:
    result = _pilot(tmp_path)
    inputs = provenance.build_generated_pilot_r3_inputs(result)
    tampered_context = deepcopy(inputs["upstream_context"])
    packet = tampered_context["mechanical_pilot_provenance"]
    if tampered_field == "source":
        packet["source_sha256"] = "0" * 64
    elif tampered_field == "semantic":
        packet["feature_projections"][0]["semantic_projection_ref"] = "0" * 64
    else:
        packet["build_evidence_sha256"] = "0" * 64

    with pytest.raises(r3.ComponentViewRegistryError, match="PROVENANCE"):
        r3.build_component_view_registry(
            upstream_context=tampered_context,
            components=inputs["components"],
        )


def test_generated_r3_rejects_non_generated_origin_class(tmp_path: Path) -> None:
    result = _pilot(tmp_path)
    inputs = provenance.build_generated_pilot_r3_inputs(result)
    components = deepcopy(inputs["components"])
    components[0]["origin_class"] = "REUSED_UNCHANGED"

    with pytest.raises(r3.ComponentViewRegistryError, match="GENERATED_ORIGIN"):
        r3.build_component_view_registry(
            upstream_context=inputs["upstream_context"],
            components=components,
        )


class _BoundClient:
    def __init__(self, path: str, handles: list[str]) -> None:
        self.path = path
        self.handles = handles
        self.calls: list[str] = []

    def drawing_get_variables(self, names: list[str]) -> dict[str, object]:
        assert names
        drawing = Path(self.path)
        return {"DWGPREFIX": str(drawing.parent) + "\\", "DWGNAME": drawing.name}

    def entity_get(self, handle: str) -> dict[str, object]:
        self.calls.append(handle)
        if handle not in self.handles:
            raise KeyError(handle)
        return {"handle": handle, "type": "LINE", "layer": "MECHANICAL_SHAFT_STEP"}


def test_generated_composition_produces_current_r4_and_bounded_query(
    tmp_path: Path,
) -> None:
    result = _pilot(tmp_path)
    binding = provenance.compose_generated_pilot_query_binding(result, **SCOPE)
    assert binding["expected_active_document_path"] == str(
        result.candidate_path.resolve()
    )

    revision = binding["candidate_revision"]
    assert revision["candidate_kind"] == "ROOT_PRE_REPAIR"
    assert binding["candidate_state"]["current_candidate_revision_sha256"] == revision[
        "candidate_revision_sha256"
    ]
    assert validate_candidate_revision(
        revision,
        registry=binding["registry"],
        base_cad_handoff=None,
        baseline_context=binding["baseline_context"],
        parent_candidate=None,
        change_impact=binding["change_impact"],
        mutation_evidence=binding["mutation_evidence"],
        schema_version="candidate-revision-1.1",
        candidate_kind="ROOT_PRE_REPAIR",
    ) == revision

    shaft = next(
        component
        for component in binding["registry"]["components"]
        if component["component_type"] == "shaft_step"
    )
    handles = [
        item["entity_handle"] for item in shaft["candidate_entity_bindings"]
    ]
    client = _BoundClient(str(result.candidate_path), handles)
    query = drawing_query.query_entities(
        client=client,
        reference=binding["reference"],
        current_observation=binding["current_observation"],
        artifact_bytes=binding["artifact_bytes"],
        parent_reference=None,
        accepted_transition_evidence_sha256=None,
        registry=binding["registry"],
        registry_upstream_context=binding["registry_upstream_context"],
        candidate_state=binding["candidate_state"],
        expected_active_document_path=str(result.candidate_path),
        query={
            "schema_version": "entity-query-1.0",
            "handles": [],
            "component_ids": [shaft["component_id"]],
            "view_ids": [],
            "detail": "SUMMARY",
        },
    )
    assert [item["handle"] for item in query["entities"]] == sorted(handles)
    assert client.calls == sorted(handles)

    stale_client = _BoundClient(str(result.candidate_path), handles)
    with pytest.raises(drawing_query.DrawingQueryError, match="STALE"):
        drawing_query.query_entities(
            client=stale_client,
            reference=binding["reference"],
            current_observation=binding["current_observation"],
            artifact_bytes=binding["artifact_bytes"] + b"\n",
            parent_reference=None,
            accepted_transition_evidence_sha256=None,
            registry=binding["registry"],
            registry_upstream_context=binding["registry_upstream_context"],
            candidate_state=binding["candidate_state"],
            expected_active_document_path=str(result.candidate_path),
            query={
                "schema_version": "entity-query-1.0",
                "handles": [],
                "component_ids": [shaft["component_id"]],
                "view_ids": [],
                "detail": "SUMMARY",
            },
        )
    assert stale_client.calls == []

    foreign_client = _BoundClient(str(tmp_path / "foreign.dxf"), handles)
    with pytest.raises(drawing_query.DrawingQueryError, match="ACTIVE_DOCUMENT"):
        drawing_query.query_entities(
            client=foreign_client,
            reference=binding["reference"],
            current_observation=binding["current_observation"],
            artifact_bytes=binding["artifact_bytes"],
            parent_reference=None,
            accepted_transition_evidence_sha256=None,
            registry=binding["registry"],
            registry_upstream_context=binding["registry_upstream_context"],
            candidate_state=binding["candidate_state"],
            expected_active_document_path=binding["expected_active_document_path"],
            query={
                "schema_version": "entity-query-1.0",
                "handles": [],
                "component_ids": [shaft["component_id"]],
                "view_ids": [],
                "detail": "SUMMARY",
            },
        )
    assert foreign_client.calls == []


def test_generated_r4_requires_no_fake_handoff_and_rejects_supplied_one(
    tmp_path: Path,
) -> None:
    result = _pilot(tmp_path)
    binding = provenance.compose_generated_pilot_query_binding(result, **SCOPE)
    with pytest.raises(CandidateRevisionError, match="GENERATED|HANDOFF|R2"):
        validate_candidate_revision(
            binding["candidate_revision"],
            registry=binding["registry"],
            base_cad_handoff={"fake": True},
            baseline_context=binding["baseline_context"],
            parent_candidate=None,
            change_impact=binding["change_impact"],
            mutation_evidence=binding["mutation_evidence"],
            schema_version="candidate-revision-1.1",
            candidate_kind="ROOT_PRE_REPAIR",
        )
