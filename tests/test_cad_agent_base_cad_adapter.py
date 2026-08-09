from __future__ import annotations

from copy import deepcopy
import importlib
import json
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256


_FIELDS = {
    "schema_version", "run_id", "source_bundle_sha256", "source_custody_sha256",
    "source_fusion_sha256", "base_source", "inspection_id", "inspection_sha256",
    "target_drawing_sha256", "eligible_component_ids", "transform_policy", "state",
}
_BASE_SOURCE_FIELDS = {"source_id", "sha256", "revision"}


def _module():
    return importlib.import_module("cad_agent.base_cad_adapter")


def _binding() -> dict[str, object]:
    return {
        "schema_version": "base-cad-binding-1.0",
        "run_id": "run-R2-171-001",
        "source_bundle_sha256": "1" * 64,
        "source_custody_sha256": "2" * 64,
        "source_fusion_sha256": "3" * 64,
        "base_source": {"source_id": "base-cad-001", "sha256": "4" * 64, "revision": "rev-A"},
        "inspection_id": "inspection-001",
        "inspection_sha256": "5" * 64,
        "target_drawing_sha256": "6" * 64,
        "eligible_component_ids": ["component-B", "component-A"],
        "transform_policy": "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY",
        "state": "READY_FOR_SELECTION",
    }


def test_fixture_is_closed_and_canonical_hashable() -> None:
    payload = _binding()
    assert set(payload) == _FIELDS
    assert set(payload["base_source"]) == _BASE_SOURCE_FIELDS
    assert canonical_json_sha256(payload) == canonical_json_sha256(deepcopy(payload))


def test_offline_kernel_surface_is_exact_and_builder_locked() -> None:
    module = _module()
    assert module.BASE_CAD_BINDING_SCHEMA_VERSION == "base-cad-binding-1.0"
    assert issubclass(module.BaseCadAdapterError, ValueError)
    assert callable(module.validate_base_cad_binding)
    assert callable(module.base_cad_binding_sha256)
    assert not hasattr(module, "build_base_cad_binding")


def test_validation_returns_detached_sorted_normalized_copy() -> None:
    module = _module()
    payload = _binding()
    normalized = module.validate_base_cad_binding(payload)
    assert normalized is not payload
    assert normalized["base_source"] is not payload["base_source"]
    assert normalized["eligible_component_ids"] == ["component-A", "component-B"]
    payload["base_source"]["revision"] = "mutated"
    payload["eligible_component_ids"].append("component-C")
    assert normalized["base_source"]["revision"] == "rev-A"
    assert normalized["eligible_component_ids"] == ["component-A", "component-B"]


@pytest.mark.parametrize("payload", [None, [], "binding", 42, True])
def test_non_mapping_root_fails_closed(payload: object) -> None:
    module = _module()
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize("field", ["inspection_sha256", "base_source.revision"])
def test_missing_fields_fail_closed(field: str) -> None:
    module = _module()
    payload = _binding()
    if "." in field:
        del payload["base_source"][field.split(".", 1)[1]]
    else:
        del payload[field]
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "base-cad-binding-2.0"),
        ("source_bundle_sha256", "A" * 64),
        ("run_id", "bad id"),
        ("base_source.source_id", "../source"),
        ("eligible_component_ids", ["component-A", "component-A"]),
        ("state", "STALE_SOURCE"),
        ("transform_policy", "ARBITRARY_MATRIX"),
    ],
)
def test_invalid_authority_or_identity_fails_closed(field: str, value: object) -> None:
    module = _module()
    payload = _binding()
    if "." in field:
        payload["base_source"][field.split(".", 1)[1]] = value
    else:
        payload[field] = value
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize(
    "forbidden",
    ["path", "relative_path", "approval", "verdict", "repair", "publication",
     "source_handle", "candidate_handle", "units", "ucs", "wcs", "renderer",
     "transport", "registry_id", "revision_store"],
)
def test_private_live_and_downstream_authority_fields_fail_closed(forbidden: str) -> None:
    module = _module()
    payload = _binding()
    payload[forbidden] = "forbidden"
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


def test_component_permutations_have_one_hash_identity() -> None:
    module = _module()
    first = _binding()
    second = _binding()
    second["eligible_component_ids"] = list(reversed(second["eligible_component_ids"]))
    assert module.validate_base_cad_binding(first) == module.validate_base_cad_binding(second)
    assert module.base_cad_binding_sha256(first) == module.base_cad_binding_sha256(second)


def test_authoritative_mutations_change_hash_and_stale_state_rejects() -> None:
    module = _module()
    baseline = _binding()
    changed = _binding()
    changed["base_source"]["revision"] = "rev-B"
    assert module.base_cad_binding_sha256(changed) != module.base_cad_binding_sha256(baseline)
    stale = deepcopy(changed)
    stale["state"] = "SOURCE_DRIFTED"
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(stale)


def test_hash_uses_existing_canonical_owner_and_no_second_hash_or_live_owner() -> None:
    module = _module()
    assert module.base_cad_binding_sha256(_binding()) == canonical_json_sha256(
        module.validate_base_cad_binding(_binding())
    )
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "canonical_json_sha256" in source
    for forbidden in (
        "hashlib", "json.dumps", "cad_agent.source_bundle", "cad_agent.source_integrity",
        "cad_agent.source_fusion", "mcp_integration_lib.dotnet_ipc", "DotNetIPCClient", "subprocess",
        "socket", "open(",
    ):
        assert forbidden not in source


def _inspection() -> dict[str, object]:
    fixture = Path(__file__).parents[1] / "mcp_integration_lib" / "tests" / "fixtures" / "exact-base-xref-inspection.json"
    return json.loads(fixture.read_text(encoding="utf-8"))["inspection"]


def _selections() -> list[dict[str, object]]:
    return [
        {
            "logical_component_id": "chassis-main",
            "transform": {
                "rotation_degrees": 0.0,
                "translation": {"x": 10.0, "y": 20.0, "z": 0.0},
                "uniform_scale": 1.0,
            },
        },
        {
            "logical_component_id": "cabin-main",
            "transform": {
                "rotation_degrees": 2.5,
                "translation": {"x": 0.0, "y": 0.0, "z": 5.0},
                "uniform_scale": 1.0,
            },
        },
    ]


def test_build_proposed_extraction_delegates_to_s3a_and_never_approves() -> None:
    module = _module()
    inspection = _inspection()
    proposed = module.build_proposed_base_cad_extraction(
        plan_id="extraction-plan-173-001",
        inspection=inspection,
        selections=_selections(),
        impacted_views=[{"identity": "model-space", "name": "Model"}],
    )
    assert proposed["schema_version"] == "exact-base-xref-extraction-plan-1.0"
    assert proposed["approval"] == {"status": "PROPOSED", "reference": None}
    assert proposed["base_source"] == inspection["base_source"]
    assert [item["logical_component_id"] for item in proposed["components"]] == [
        "chassis-main", "cabin-main"
    ]


def test_proposal_rejects_ineligible_inspection_without_live_fallback() -> None:
    module = _module()
    inspection = _inspection()
    inspection["eligible"] = False
    with pytest.raises(module.BaseCadAdapterError):
        module.build_proposed_base_cad_extraction(
            plan_id="extraction-plan-173-002",
            inspection=inspection,
            selections=_selections(),
        )


def test_approved_match_requires_same_proposal_identity_and_explicit_approval() -> None:
    module = _module()
    proposed = module.build_proposed_base_cad_extraction(
        plan_id="extraction-plan-173-003",
        inspection=_inspection(),
        selections=_selections(),
    )
    approved = deepcopy(proposed)
    approved["approval"] = {"status": "APPROVED", "reference": "approval-173-001"}
    matched = module.require_approved_base_cad_extraction_match(
        approved_plan=approved,
        proposed_plan=proposed,
        inspection=_inspection(),
    )
    assert matched["approval"] == approved["approval"]
    assert matched["components"] == proposed["components"]


@pytest.mark.parametrize("mutation", [
    {"target_drawing_sha256": "f" * 64},
    {"source_revision": "rev-drifted"},
    {"approval": {"status": "PROPOSED", "reference": None}},
])
def test_approved_match_rejects_stale_or_unapproved_plan(mutation: dict[str, object]) -> None:
    module = _module()
    proposed = module.build_proposed_base_cad_extraction(
        plan_id="extraction-plan-173-004",
        inspection=_inspection(),
        selections=_selections(),
    )
    approved = deepcopy(proposed)
    approved["approval"] = {"status": "APPROVED", "reference": "approval-173-002"}
    approved.update(mutation)
    with pytest.raises(module.BaseCadAdapterError):
        module.require_approved_base_cad_extraction_match(
            approved_plan=approved,
            proposed_plan=proposed,
            inspection=_inspection(),
        )


def _handoff() -> dict[str, object]:
    return {
        "schema_version": "base-cad-reuse-handoff-1.0",
        "run_id": "run-R2-175-001",
        "source_bundle_sha256": "1" * 64,
        "source_custody_sha256": "2" * 64,
        "source_fusion_sha256": "3" * 64,
        "base_cad_binding_sha256": "4" * 64,
        "inspection_sha256": "5" * 64,
        "extraction_plan_sha256": "6" * 64,
        "base_source": {
            "source_id": "base-cad-001",
            "sha256": "7" * 64,
            "revision": "rev-A",
        },
        "candidate_input_sha256": "8" * 64,
        "candidate_output_sha256": "9" * 64,
        "live_preflight_evidence_sha256": "a" * 64,
        "components": [
            {
                "logical_component_id": "component-A",
                "source_handle": "A1B2",
                "source_layer": "BODY",
                "source_block": "CHASSIS_MAIN",
                "source_sha256": "b" * 64,
                "source_revision": "rev-A",
                "candidate_handle": "C3D4",
                "transform": {
                    "rotation_degrees": 0.0,
                    "translation": {"x": 1.0, "y": 2.0, "z": 0.0},
                    "uniform_scale": 1.0,
                },
                "provenance": "REUSED_FROM_BASE_CAD",
            },
        ],
        "source_handle_to_candidate_handle": [{"source_handle": "A1B2", "candidate_handle": "C3D4"}],
    }


def _source(*, revision: str = "rev-A", sha256: str = "7" * 64) -> dict[str, str]:
    return {"source_id": "base-cad-001", "sha256": sha256, "revision": revision}


def test_reuse_handoff_is_closed_detached_and_canonical_hashable() -> None:
    module = _module()
    payload = _handoff()
    normalized = module.validate_base_cad_reuse_handoff(payload)
    assert normalized is not payload
    assert normalized["components"] is not payload["components"]
    assert normalized["schema_version"] == "base-cad-reuse-handoff-1.0"
    payload["base_source"]["revision"] = "mutated"
    assert normalized["base_source"]["revision"] == "rev-A"
    assert module.base_cad_reuse_handoff_sha256(payload) == module.base_cad_reuse_handoff_sha256(normalized)


def test_reuse_handoff_hash_uses_existing_canonical_owner() -> None:
    module = _module()
    assert module.base_cad_reuse_handoff_sha256(_handoff()) == canonical_json_sha256(
        module.validate_base_cad_reuse_handoff(_handoff())
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {"schema_version": "base-cad-reuse-handoff-2.0"},
        {"base_source": {"source_id": "base-cad-001", "sha256": "A" * 64, "revision": "rev-A"}},
        {"candidate_handle": "bad handle"},
        {"source_handle_to_candidate_handle": []},
    ],
)
def test_reuse_handoff_malformed_or_forbidden_shape_fails_closed(mutation: dict[str, object]) -> None:
    module = _module()
    payload = _handoff()
    if "candidate_handle" in mutation:
        payload["components"][0]["candidate_handle"] = mutation["candidate_handle"]
    else:
        payload.update(mutation)
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_reuse_handoff(payload)


def test_frozen_reuse_evaluation_is_current_for_exact_source_identity() -> None:
    module = _module()
    result = module.evaluate_frozen_base_cad_reuse(
        handoff=_handoff(), current_base_source=_source()
    )
    assert result["state"] == "CURRENT"
    assert result["affected_component_ids"] == []


@pytest.mark.parametrize("current", [_source(revision="rev-B"), _source(sha256="c" * 64), _source(revision="rev-B", sha256="c" * 64)])
def test_frozen_reuse_evaluation_requires_reextraction_on_identity_drift(current: dict[str, str]) -> None:
    module = _module()
    result = module.evaluate_frozen_base_cad_reuse(
        handoff=_handoff(), current_base_source=current
    )
    assert result["state"] == "STALE_REEXTRACTION_REQUIRED"
    assert result["affected_component_ids"] == ["component-A"]
    assert result["previous_source"] == _handoff()["base_source"]
    assert result["current_source"] == current


def test_reuse_evaluation_has_no_live_execution_or_current_pointer_fields() -> None:
    module = _module()
    result = module.evaluate_frozen_base_cad_reuse(
        handoff=_handoff(), current_base_source=_source()
    )
    assert set(result) == {"state", "prior_handoff_sha256", "affected_component_ids", "previous_source", "current_source"}
