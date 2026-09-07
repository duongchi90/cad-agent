from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import importlib.util
from pathlib import Path

import pytest

from cad_agent import component_view_registry as r3
from cad_agent.drawing_contracts import canonical_json_sha256


SIGNATURE = "a" * 64
SOURCE_AUDIT_SHA256 = "b" * 64
CANDIDATE_AUDIT_SHA256 = "c" * 64


def _api():
    spec = importlib.util.find_spec("cad_agent.native_dwg_provenance")
    assert spec is not None, "native DWG provenance module contract is missing"
    return importlib.import_module("cad_agent.native_dwg_provenance")


def _readback(
    path: Path,
    data: bytes,
    *,
    count: int = 16_785,
    signature: str = SIGNATURE,
) -> dict[str, object]:
    record: dict[str, object] = {
        "schema_version": "native-dwg-readback-1.0",
        "artifact_path": str(path),
        "artifact_sha256": hashlib.sha256(data).hexdigest(),
        "entity_count": count,
        "entity_signature_sha256": signature,
        "observation_sha256": "",
    }
    record["observation_sha256"] = canonical_json_sha256(
        {
            key: record[key]
            for key in record
            if key != "observation_sha256"
        }
    )
    return record


def _fixture(tmp_path: Path) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "BVTL.dwg"
    candidate_path = tmp_path / "BVTL_candidate.dxf"
    source_bytes = b"native source bytes"
    candidate_bytes = b"editable full drawing bytes"
    source_path.write_bytes(source_bytes)
    candidate_path.write_bytes(candidate_bytes)
    return {
        "source_path": source_path,
        "candidate_path": candidate_path,
        "source_bytes": source_bytes,
        "candidate_bytes": candidate_bytes,
        "source_readback": _readback(source_path, source_bytes),
        "candidate_readback": _readback(candidate_path, candidate_bytes),
        "source_setup_audit_sha256": SOURCE_AUDIT_SHA256,
        "candidate_setup_audit_sha256": CANDIDATE_AUDIT_SHA256,
    }


def _build(module, fixture: dict[str, object]) -> dict[str, object]:
    return module.build_native_dwg_provenance(
        source_path=fixture["source_path"],
        candidate_path=fixture["candidate_path"],
        source_readback=fixture["source_readback"],
        candidate_readback=fixture["candidate_readback"],
        source_setup_audit_sha256=fixture["source_setup_audit_sha256"],
        candidate_setup_audit_sha256=fixture["candidate_setup_audit_sha256"],
    )


def test_native_module_exposes_closed_packet_contract() -> None:
    module = _api()
    assert module.NATIVE_DWG_PROVENANCE_SCHEMA_VERSION == (
        "native-dwg-full-drawing-provenance-1.0"
    )
    assert module.NATIVE_DWG_PROVENANCE_MODE == "NATIVE_DWG_FULL_DRAWING"
    assert issubclass(module.NativeDwgProvenanceError, ValueError)


def test_native_packet_is_deterministic_and_replayable(tmp_path: Path) -> None:
    module = _api()
    fixture = _fixture(tmp_path)
    first = _build(module, fixture)
    second = _build(module, fixture)

    assert first == second
    assert module.validate_native_dwg_provenance(first) == first
    assert first["scope"] == "FULL_DRAWING"
    assert first["source_format"] == "DWG"
    assert first["candidate_format"] == "DXF"
    assert first["calibration_mode"] == "NOT_APPLICABLE_NATIVE_CAD"
    assert first["candidate_id"] == (
        "native-dwg-full-drawing:" + fixture["candidate_readback"]["artifact_sha256"]
    )


def test_native_packet_rejects_source_or_candidate_hash_drift(
    tmp_path: Path,
) -> None:
    module = _api()
    fixture = _fixture(tmp_path)
    fixture["source_path"].write_bytes(b"replaced source bytes")
    with pytest.raises(
        module.NativeDwgProvenanceError,
        match="SOURCE_ARTIFACT_HASH_MISMATCH",
    ):
        _build(module, fixture)

    fixture = _fixture(tmp_path / "candidate-drift")
    fixture["candidate_path"].write_bytes(b"replaced candidate bytes")
    with pytest.raises(
        module.NativeDwgProvenanceError,
        match="CANDIDATE_ARTIFACT_HASH_MISMATCH",
    ):
        _build(module, fixture)


@pytest.mark.parametrize(
    ("field", "expected_code"),
    [
        ("entity_count", "ENTITY_COUNT_MISMATCH"),
        ("entity_signature_sha256", "ENTITY_SIGNATURE_MISMATCH"),
    ],
)
def test_native_packet_rejects_source_candidate_measurement_mismatch(
    tmp_path: Path,
    field: str,
    expected_code: str,
) -> None:
    module = _api()
    fixture = _fixture(tmp_path)
    changed = deepcopy(fixture["candidate_readback"])
    changed[field] = (
        changed[field] + 1
        if field == "entity_count"
        else "d" * 64
    )
    changed["observation_sha256"] = canonical_json_sha256(
        {
            key: changed[key]
            for key in changed
            if key != "observation_sha256"
        }
    )
    fixture["candidate_readback"] = changed
    with pytest.raises(
        module.NativeDwgProvenanceError,
        match=expected_code,
    ):
        _build(module, fixture)


def test_native_packet_rejects_unknown_fields_and_wrong_formats(
    tmp_path: Path,
) -> None:
    module = _api()
    packet = _build(module, _fixture(tmp_path))

    unknown = deepcopy(packet)
    unknown["unexpected"] = True
    with pytest.raises(
        module.NativeDwgProvenanceError,
        match="PROVENANCE_SCHEMA_INVALID",
    ):
        module.validate_native_dwg_provenance(unknown)

    wrong_format = deepcopy(packet)
    wrong_format["candidate_format"] = "DWG"
    with pytest.raises(
        module.NativeDwgProvenanceError,
        match="PROVENANCE_SCHEMA_INVALID",
    ):
        module.validate_native_dwg_provenance(wrong_format)


def test_native_packet_rejects_readback_observation_hash_drift(
    tmp_path: Path,
) -> None:
    module = _api()
    fixture = _fixture(tmp_path)
    changed = deepcopy(fixture["candidate_readback"])
    changed["observation_sha256"] = "e" * 64
    fixture["candidate_readback"] = changed
    with pytest.raises(
        module.NativeDwgProvenanceError,
        match="READBACK_HASH_MISMATCH",
    ):
        _build(module, fixture)


def test_native_r3_inputs_are_closed_and_do_not_invent_components(
    tmp_path: Path,
) -> None:
    module = _api()
    packet = _build(module, _fixture(tmp_path))
    inputs = module.build_native_dwg_r3_inputs(packet)

    assert set(inputs) == {"upstream_context", "components", "views"}
    assert inputs["components"] == []
    assert inputs["views"] == []
    assert inputs["upstream_context"]["provenance_mode"] == (
        "NATIVE_DWG_FULL_DRAWING"
    )
    assert "mechanical_pilot_provenance" not in inputs["upstream_context"]
    assert "source_fusion" not in inputs["upstream_context"]


def test_native_r3_registry_seals_one_drawing_binding_and_no_components(
    tmp_path: Path,
) -> None:
    module = _api()
    packet = _build(module, _fixture(tmp_path))
    inputs = module.build_native_dwg_r3_inputs(packet)
    registry = r3.build_component_view_registry(**inputs)

    assert registry["schema_version"] == (
        "component-view-registry-native-dwg-1.0"
    )
    assert set(registry) == {
        "schema_version",
        "upstream_bindings",
        "drawing_binding",
        "components",
        "views",
        "links",
        "registry_snapshot_sha256",
    }
    assert registry["components"] == []
    assert registry["views"] == []
    assert registry["links"] == []
    assert registry["drawing_binding"]["candidate_id"] == packet["candidate_id"]
    assert r3.validate_component_view_registry(
        registry,
        upstream_context=inputs["upstream_context"],
    ) == registry
    evidence = r3.component_view_registry_provenance_evidence(
        registry,
        upstream_context=inputs["upstream_context"],
    )
    assert evidence["drawing_binding"] == registry["drawing_binding"]


def test_native_r3_rejects_mixed_fields_and_nonempty_collections(
    tmp_path: Path,
) -> None:
    module = _api()
    packet = _build(module, _fixture(tmp_path))
    inputs = module.build_native_dwg_r3_inputs(packet)

    mixed_context = deepcopy(inputs["upstream_context"])
    mixed_context["source_fusion"] = {}
    with pytest.raises(
        r3.ComponentViewRegistryError,
        match="UPSTREAM_CONTEXT_INVALID",
    ):
        r3.build_component_view_registry(
            upstream_context=mixed_context,
            components=[],
            views=[],
        )

    with pytest.raises(
        r3.ComponentViewRegistryError,
        match="NATIVE_DWG_COMPONENTS_FORBIDDEN",
    ):
        r3.build_component_view_registry(
            upstream_context=inputs["upstream_context"],
            components=[{}],
            views=[],
        )

    with pytest.raises(
        r3.ComponentViewRegistryError,
        match="NATIVE_DWG_VIEWS_FORBIDDEN",
    ):
        r3.build_component_view_registry(
            upstream_context=inputs["upstream_context"],
            components=[],
            views=[{}],
        )


def test_native_r3_rejects_tampered_packet_and_nonempty_impact(
    tmp_path: Path,
) -> None:
    module = _api()
    packet = _build(module, _fixture(tmp_path))
    tampered = deepcopy(packet)
    tampered["candidate_sha256"] = "f" * 64
    inputs = module.build_native_dwg_r3_inputs(packet)
    tampered_context = deepcopy(inputs["upstream_context"])
    tampered_context["native_dwg_provenance"] = tampered
    with pytest.raises(
        r3.ComponentViewRegistryError,
        match="NATIVE_DWG_PROVENANCE_INVALID",
    ):
        r3.build_component_view_registry(
            upstream_context=tampered_context,
            components=[],
            views=[],
        )

    registry = r3.build_component_view_registry(**inputs)
    with pytest.raises(
        r3.ComponentViewRegistryError,
        match="NATIVE_DWG_IMPACT_FORBIDDEN",
    ):
        r3.project_linked_view_impacts(
            registry=registry,
            component_ids=["a" * 64],
            view_ids=[],
            upstream_context=inputs["upstream_context"],
        )


def test_native_composition_produces_current_dara_r3_r4_binding(
    tmp_path: Path,
) -> None:
    module = _api()
    fixture = _fixture(tmp_path)
    binding = module.compose_native_dwg_query_binding(
        source_path=fixture["source_path"],
        candidate_path=fixture["candidate_path"],
        source_readback=fixture["source_readback"],
        candidate_readback=fixture["candidate_readback"],
        source_setup_audit_sha256=fixture["source_setup_audit_sha256"],
        candidate_setup_audit_sha256=fixture["candidate_setup_audit_sha256"],
        run_id="run-native-001",
        project_id="project-native-001",
        drawing_id="drawing-native-001",
    )

    assert binding["reference"]["artifact_role"] == "R3_CANDIDATE"
    assert binding["registry"]["schema_version"] == (
        "component-view-registry-native-dwg-1.0"
    )
    assert binding["candidate_revision"]["candidate_kind"] == "ROOT_PRE_REPAIR"
    assert binding["candidate_state"]["current_candidate_revision_sha256"]
    assert binding["expected_active_document_path"] == str(
        fixture["candidate_path"].resolve()
    )
    assert binding["base_cad_handoff"] is None
