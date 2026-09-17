from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

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


def _external_artifacts_for_test(tmp_path: Path) -> dict[str, object]:
    from PIL import Image, ImageDraw

    from cad_agent.live import write_build_evidence
    from cad_agent.source_verified_geometry import (
        materialize_verified_external_visual_lines,
    )
    from cad_agent.source_support_verifier import (
        verify_external_visual_proposal_source_support,
    )
    from cad_agent.source_fusion_proposal import (
        compile_external_visual_object_proposal,
    )
    from dxf_builder_lib.builder import build_dxf

    source_sha256 = "1" * 64
    image = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(image)
    line_specs = [
        ("main_vertical", [10, 5], [10, 50]),
        ("mirror_top", [20, 10], [50, 10]),
        ("mirror_right", [50, 12], [50, 40]),
        ("mirror_bottom", [20, 40], [50, 40]),
        ("mirror_left", [20, 12], [20, 38]),
        ("lower_slope", [10, 50], [20, 40]),
    ]
    for _primitive_id, start, end in line_specs:
        draw.line((*start, *end), fill=0, width=1)
    render_stream = io.BytesIO()
    image.save(render_stream, format="PNG")
    render_bytes = render_stream.getvalue()
    binding = {
        "source_sha256": source_sha256,
        "page_index": 0,
        "source_render_sha256": hashlib.sha256(render_bytes).hexdigest(),
        "roi_bbox_px": [0, 0, 63, 63],
    }
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {
                "id": primitive_id,
                "type": "LINE",
                "start_px": start,
                "end_px": end,
            }
            for primitive_id, start, end in line_specs
        ],
        "object_groups": [
            {
                "group_id": "six-line-probe",
                "proposed_label": "UNCLASSIFIED_BOUNDARY",
                "primitive_hypothesis_ids": [
                    primitive_id for primitive_id, _start, _end in line_specs
                ],
            }
        ],
        "excluded_memberships": [],
    }
    request = compile_external_visual_object_proposal(
        proposal=proposal,
        expected_binding=binding,
        expected_calibration_binding={
            "unit": "mm",
            "pixel_to_unit_scale": 1.0,
            "origin_px": [0.0, 64.0],
            "method": "manual_override",
            "reference_note": "test exact source-bound calibration",
            "status": "verified",
            "source_sha256": source_sha256,
        },
    )
    result = verify_external_visual_proposal_source_support(
        verification_request=request,
        source_render_bytes=render_bytes,
    )
    from primitive_ir_lib.models import Calibration

    primitive_doc = materialize_verified_external_visual_lines(
        verification_request=request,
        verification_result=result,
        source_render_bytes=render_bytes,
        calibration=Calibration(
            unit="mm",
            pixel_to_unit_scale=1.0,
            origin_px=(0.0, 64.0),
            method="manual_override",
            reference_note="test exact source-bound calibration",
            status="verified",
            source_sha256=source_sha256,
        ),
        source_file_name="source.png",
        image_width_px=64,
        image_height_px=64,
    )
    primitive_path = tmp_path / "external-primitive.json"
    primitive_path.write_text(
        json.dumps(primitive_doc.to_dict(), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    candidate_path = tmp_path / "external-candidate" / "candidate.dxf"
    candidate_path.parent.mkdir()
    build = build_dxf(
        primitive_doc,
        str(candidate_path),
        semantic_doc=None,
        build_components=False,
        build_dimensions=False,
    )
    build_evidence_path = candidate_path.with_name("build-evidence.json")
    write_build_evidence(build_evidence_path, build)
    return {
        "primitive_path": primitive_path,
        "candidate_path": candidate_path,
        "build_evidence_path": build_evidence_path,
        "verification_request": request,
        "verification_result": result,
        "source_render_bytes": render_bytes,
    }


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


def _external_geometry_packet_for_test() -> dict[str, object]:
    evidence = {
        "source_sha256": (
            "13d822cf828cccc6cd21b19ec3c410f0ea89aef440aeca4c96248e86c08b5b38"
        ),
        "primitive_ir_sha256": (
            "82042917095aa5400b13e2098b4aadf35dd6414b869ac88087b3ad17a1f60814"
        ),
        "verification_request_sha256": (
            "cf36fb0a271df58f4fb435d76c2dd14328026fd0ccc09f10993d355eef9c4417"
        ),
        "verification_result_sha256": (
            "6300f84c5194290cee0818358f6cf7f7247bf87e3ad202eecc0682e5dcd413b7"
        ),
        "candidate_sha256": (
            "497b5e8653842413927fa979f8be51c0f71b23239bc7d2da2cd15dd633dc6499"
        ),
        "build_evidence_sha256": (
            "053d93bcdfda4a18a4628837eb24f6fc8a8b14b1fd11303faaaa9e435885ceb5"
        ),
    }
    primitive_specs = [
        ("main_vertical", "30", (1905.0, 216.0), (1905.0, 519.0)),
        ("mirror_top", "31", (1912.0, 347.0), (1942.0, 347.0)),
        ("mirror_right", "32", (1942.0, 350.0), (1942.0, 387.0)),
        ("mirror_bottom", "33", (1912.0, 387.0), (1942.0, 387.0)),
        ("mirror_left", "34", (1912.0, 351.0), (1912.0, 386.0)),
        ("lower_slope", "35", (1905.0, 510.0), (1898.0, 519.0)),
    ]
    pilot_id = "external-geometry-ai-p1"
    candidate_id = f"{pilot_id}:{evidence['candidate_sha256']}"
    primitives = []
    for primitive_id, handle, start, end in primitive_specs:
        raw = {
            "id": primitive_id,
            "type": "line",
            "geometry": {
                "start": {"x": start[0], "y": start[1]},
                "end": {"x": end[0], "y": end[1]},
            },
        }
        primitive = SimpleNamespace(
            to_dict=lambda raw=raw: deepcopy(raw),
        )
        primitives.append(
            provenance._external_primitive_projection(
                pilot_id=pilot_id,
                source_sha256=evidence["source_sha256"],
                candidate_sha256=evidence["candidate_sha256"],
                relative_path="candidate.dxf",
                primitive=primitive,
                written_geometry=raw["geometry"],
                handle=handle,
                layer="UNCLASSIFIED",
            )
        )

    primitives.sort(key=lambda item: str(item["primitive_id"]))
    packet = {
        "schema_version": "external-geometry-provenance-1.0",
        "provenance_mode": "EXTERNAL_GEOMETRY_ONLY",
        "pilot_id": pilot_id,
        "candidate_id": candidate_id,
        "candidate_path_binding_sha256": "a" * 64,
        "source_sha256": evidence["source_sha256"],
        "source_render_sha256": (
            "b03477a1f9cd5df4f8ee6125f8faed1bf35586cb4f891c30bf2351929833b9d0"
        ),
        "primitive_ir_sha256": evidence["primitive_ir_sha256"],
        "verification_request_sha256": evidence["verification_request_sha256"],
        "verification_result_sha256": evidence["verification_result_sha256"],
        "candidate_sha256": evidence["candidate_sha256"],
        "build_evidence_sha256": evidence["build_evidence_sha256"],
        "primitive_projections": primitives,
        "provenance_sha256": "",
    }
    packet["provenance_sha256"] = provenance.canonical_json_sha256(
        provenance._external_packet_without_checksum(packet)
    )
    return provenance.validate_external_geometry_provenance(packet)


def test_external_geometry_only_candidate_reaches_existing_r3_without_semantic_authority(
    tmp_path: Path,
) -> None:
    """A verified primitive-only candidate must not require fabricated pilot semantics."""

    artifacts = _external_artifacts_for_test(tmp_path)
    inputs = provenance.build_external_geometry_r3_inputs(
        pilot_id="external-geometry-ai-p1",
        primitive_ir_path=artifacts["primitive_path"],
        candidate_path=artifacts["candidate_path"],
        build_evidence_path=artifacts["build_evidence_path"],
        verification_request=artifacts["verification_request"],
        verification_result=artifacts["verification_result"],
        source_render_bytes=artifacts["source_render_bytes"],
    )
    normalized = inputs["upstream_context"]["external_geometry_provenance"]

    assert normalized["schema_version"] == (
        "external-geometry-provenance-1.0"
    )
    assert normalized["provenance_mode"] == "EXTERNAL_GEOMETRY_ONLY"
    assert normalized["source_sha256"] == "1" * 64
    assert normalized["candidate_sha256"] == hashlib.sha256(
        artifacts["candidate_path"].read_bytes()
    ).hexdigest()
    assert all(
        item["source"] == "geometry_external_ai"
        for item in normalized["primitive_projections"]
    )

    registry = r3.build_component_view_registry(**inputs)
    assert registry["schema_version"] == "component-view-registry-1.1"
    assert registry["upstream_bindings"]["provenance_mode"] == (
        "EXTERNAL_GEOMETRY_ONLY"
    )
    assert len(registry["components"]) == 1
    component = registry["components"][0]
    assert component["origin_class"] == "RECONSTRUCTED_NEW"
    assert component["semantic_projection_refs"] == []
    assert len(component["candidate_entity_bindings"]) == 6
    assert all(
        binding["candidate_id"] == normalized["candidate_id"]
        for binding in component["candidate_entity_bindings"]
    )
    assert r3.validate_component_view_registry(
        registry, upstream_context=inputs["upstream_context"]
    ) == registry


@pytest.mark.parametrize(
    "field",
    [
        "candidate_sha256",
        "build_evidence_sha256",
        "verification_request_sha256",
        "verification_result_sha256",
    ],
)
def test_external_geometry_provenance_rejects_tampered_identity(field: str) -> None:
    packet = _external_geometry_packet_for_test()
    packet[field] = "f" * 64

    expected_error = (
        "EXTERNAL_CANDIDATE_ID_MISMATCH"
        if field == "candidate_sha256"
        else "EXTERNAL_PROVENANCE_HASH_MISMATCH"
    )
    with pytest.raises(
        provenance.GeneratedPilotProvenanceError,
        match=expected_error,
    ):
        provenance.validate_external_geometry_provenance(packet)


def test_external_geometry_provenance_rejects_injected_semantic_features() -> None:
    packet = _external_geometry_packet_for_test()
    packet["feature_projections"] = []

    with pytest.raises(
        provenance.GeneratedPilotProvenanceError,
        match="EXTERNAL_PROVENANCE_SCHEMA_INVALID",
    ):
        provenance.validate_external_geometry_provenance(packet)


def test_external_geometry_provenance_issuer_rederives_identity(
    tmp_path: Path,
) -> None:
    artifacts = _external_artifacts_for_test(tmp_path)

    packet = provenance.build_external_geometry_provenance(
        pilot_id="external-geometry-ai-p1",
        primitive_ir_path=artifacts["primitive_path"],
        candidate_path=artifacts["candidate_path"],
        build_evidence_path=artifacts["build_evidence_path"],
        verification_request=artifacts["verification_request"],
        verification_result=artifacts["verification_result"],
        source_render_bytes=artifacts["source_render_bytes"],
    )

    candidate_sha256 = hashlib.sha256(
        artifacts["candidate_path"].read_bytes()
    ).hexdigest()
    primitive_ir_sha256 = hashlib.sha256(
        artifacts["primitive_path"].read_bytes()
    ).hexdigest()
    assert packet["candidate_sha256"] == candidate_sha256
    assert packet["primitive_ir_sha256"] == primitive_ir_sha256
    assert packet["candidate_id"] == (
        "external-geometry-ai-p1:" + candidate_sha256
    )
    assert packet["source_render_sha256"] == hashlib.sha256(
        artifacts["source_render_bytes"]
    ).hexdigest()
    assert packet["verification_request_sha256"] == artifacts[
        "verification_request"
    ]["verification_request_sha256"]
    assert packet["verification_result_sha256"] == provenance.canonical_json_sha256(
        artifacts["verification_result"]
    )


def test_external_geometry_provenance_rejects_unbacked_request_identity(
    tmp_path: Path,
) -> None:
    artifacts = _external_artifacts_for_test(tmp_path)
    tampered_request = deepcopy(artifacts["verification_request"])
    tampered_request["verification_request_sha256"] = "e" * 64

    with pytest.raises(
        provenance.GeneratedPilotProvenanceError,
        match="EXTERNAL_ARTIFACT_CHAIN_INVALID",
    ):
        provenance.build_external_geometry_provenance(
            pilot_id="external-geometry-ai-p1",
            primitive_ir_path=artifacts["primitive_path"],
            candidate_path=artifacts["candidate_path"],
            build_evidence_path=artifacts["build_evidence_path"],
            verification_request=tampered_request,
            verification_result=artifacts["verification_result"],
            source_render_bytes=artifacts["source_render_bytes"],
        )


def test_external_geometry_r3_rejects_detached_issuer_bypass() -> None:
    packet = _external_geometry_packet_for_test()
    packet.update(
        {
            "source_render_sha256": "e" * 64,
            "primitive_ir_sha256": "f" * 64,
            "verification_request_sha256": "1" * 64,
            "verification_result_sha256": "2" * 64,
            "build_evidence_sha256": "3" * 64,
        }
    )
    packet["provenance_sha256"] = provenance.canonical_json_sha256(
        provenance._external_packet_without_checksum(packet)
    )

    with pytest.raises(TypeError):
        provenance.build_external_geometry_r3_inputs(packet)


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


def test_source_bound_compile_plan_has_reuse_first_handoff_to_external_r3() -> None:
    """A P1 compile plan must have a thin handoff into the existing artifact chain."""

    from cad_agent.mechanical_pilot import compile_source_bound_simple_shaft_proposal

    source_sha256 = "0c3db3046e9842dfcb6075ea2f6209dfe0afcc26f5e6d428dcd3ab2d72ac4ffa"
    render_sha256 = "7fa3ce10bda49c40064995dca67c46a31d87d988e695e6394b2d79286546edbc"
    binding = {
        "source_sha256": source_sha256,
        "page_index": 0,
        "roi_bbox_px": [0, 0, 263, 108],
        "source_render_sha256": render_sha256,
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 1.0,
            "origin_px": [0.0, 0.0],
            "method": "manual_override",
            "reference_note": "Exact PH008 table is authoritative; dimensions are not pixel-derived",
            "status": "verified",
            "source_sha256": source_sha256,
        },
        "profile_id": "simple-stepped-shaft-p1-v1",
    }
    plan = compile_source_bound_simple_shaft_proposal(
        {
            "schema_version": "p1-source-bound-proposal-1.0",
            "proposal_source": "external_ai",
            **binding,
            "dimensions_mm": {
                "shaft_diameter_a": 20.6375,
                "shaft_diameter_b": 12.7,
                "segment_length_a": 5.55625,
                "segment_length_b": 49.2125,
                "hole_diameter": 3.175,
                "hole_axial_position": 51.59375,
            },
            "evidence_refs": {
                "item_url": "https://catalog.lexcocable.com/item/gs-hardware-structural-hardware-clevis-pins-headed/clevis-pin-headed/ph008",
                "item_artifact_sha256": source_sha256,
                "drawing_url": "https://catalog.lexcocable.com/Asset/PH008dimensions.jpg",
                "drawing_sha256": render_sha256,
                "variant_binding": "PH008 item identity + PH008 dimension table + linked manufacturer drawing",
            },
        },
        expected_binding=binding,
    )

    handoff = getattr(
        provenance,
        "build_external_geometry_r3_inputs_from_compile_plan",
        None,
    )
    assert callable(handoff), (
        "P1 compile plan has no reuse-first handoff into the existing "
        "verified PrimitiveIR/candidate/build-evidence chain"
    )
