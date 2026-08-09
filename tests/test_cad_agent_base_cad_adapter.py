from __future__ import annotations

from copy import deepcopy
import importlib
import inspect
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
            "source_id": "base-vehicle-001",
            "sha256": "a" * 64,
            "revision": "rev-2026-08-05-01",
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
                "source_sha256": "a" * 64,
                "source_revision": "rev-2026-08-05-01",
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


def _source(
    *,
    source_id: str = "base-vehicle-001",
    revision: str = "rev-2026-08-05-01",
    sha256: str = "a" * 64,
) -> dict[str, str]:
    return {
        "relative_path": "approved/base-vehicle.dwg",
        "source_id": source_id,
        "sha256": sha256,
        "revision": revision,
    }


def _live_inspection() -> dict[str, object]:
    fixture = Path(__file__).parents[1] / "mcp_integration_lib" / "tests" / "fixtures" / "exact-base-xref-inspection.json"
    return json.loads(fixture.read_text(encoding="utf-8"))["inspection"]


def test_reuse_handoff_is_closed_detached_and_canonical_hashable() -> None:
    module = _module()
    payload = _handoff()
    normalized = module.validate_base_cad_reuse_handoff(payload)
    baseline_hash = module.base_cad_reuse_handoff_sha256(payload)
    assert normalized is not payload
    assert normalized["components"] is not payload["components"]
    assert normalized["schema_version"] == "base-cad-reuse-handoff-1.0"
    payload["base_source"]["revision"] = "mutated"
    assert normalized["base_source"]["revision"] == "rev-2026-08-05-01"
    assert module.base_cad_reuse_handoff_sha256(payload) != baseline_hash
    assert module.base_cad_reuse_handoff_sha256(normalized) == baseline_hash


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
        handoff=_handoff(), current_live_inspection=_live_inspection()
    )
    assert result["state"] == "CURRENT"
    assert result["affected_component_ids"] == []


@pytest.mark.parametrize(
    ("current", "reason_codes"),
    [
        (_source(source_id="base-vehicle-002"), ["SOURCE_ID_CHANGED"]),
        (_source(sha256="c" * 64), ["SOURCE_SHA256_CHANGED"]),
        (_source(revision="rev-B"), ["SOURCE_REVISION_CHANGED"]),
        (
            _source(source_id="base-vehicle-002", revision="rev-B", sha256="c" * 64),
            ["SOURCE_ID_CHANGED", "SOURCE_REVISION_CHANGED", "SOURCE_SHA256_CHANGED"],
        ),
    ],
)
def test_frozen_reuse_evaluation_requires_reextraction_on_identity_drift(
    current: dict[str, str], reason_codes: list[str]
) -> None:
    module = _module()
    inspection = _live_inspection()
    inspection["base_source"] = current
    result = module.evaluate_frozen_base_cad_reuse(
        handoff=_handoff(), current_live_inspection=inspection
    )
    assert result["state"] == "STALE_REEXTRACTION_REQUIRED"
    assert result["affected_component_ids"] == ["component-A"]
    assert result["affected_component_ids"] == sorted(result["affected_component_ids"])
    assert result["reason_codes"] == sorted(reason_codes)
    assert result["previous_source"] == _handoff()["base_source"]
    assert result["current_source"] == current


def test_two_component_stale_reuse_reports_sorted_affected_component_ids() -> None:
    module = _module()
    handoff = _handoff_with_two_components()
    inspection = _live_inspection()
    inspection["base_source"] = _source(sha256="c" * 64)
    result = module.evaluate_frozen_base_cad_reuse(
        handoff=handoff, current_live_inspection=inspection
    )
    assert result["state"] == "STALE_REEXTRACTION_REQUIRED"
    assert result["affected_component_ids"] == ["component-A", "component-B"]
    assert result["affected_component_ids"] == sorted(result["affected_component_ids"])
    assert result["reason_codes"] == ["SOURCE_SHA256_CHANGED"]


def test_reuse_evaluation_has_no_live_execution_or_current_pointer_fields() -> None:
    module = _module()
    assert list(inspect.signature(module.evaluate_frozen_base_cad_reuse).parameters) == [
        "handoff", "current_live_inspection"
    ]
    result = module.evaluate_frozen_base_cad_reuse(
        handoff=_handoff(), current_live_inspection=_live_inspection()
    )
    assert set(result) == {
        "state", "prior_handoff_sha256", "affected_component_ids", "previous_source",
        "current_source", "reason_codes",
    }


def test_current_live_inspection_must_match_root_and_component_source_identity() -> None:
    module = _module()
    payload = _handoff()
    with pytest.raises(module.BaseCadAdapterError):
        payload["components"][0]["source_sha256"] = "c" * 64
        module.validate_base_cad_reuse_handoff(payload)

    payload = _handoff()
    with pytest.raises(module.BaseCadAdapterError):
        payload["components"][0]["source_revision"] = "rev-B"
        module.validate_base_cad_reuse_handoff(payload)

    inspection = _live_inspection()
    inspection["base_source"] = _source(source_id="base-vehicle-002")
    result = module.evaluate_frozen_base_cad_reuse(
        handoff=_handoff(), current_live_inspection=inspection
    )
    assert result["reason_codes"] == ["SOURCE_ID_CHANGED"]


def _handoff_with_two_components() -> dict[str, object]:
    payload = _handoff()
    second = deepcopy(payload["components"][0])
    second.update(
        {
            "logical_component_id": "component-B",
            "source_handle": "C3D4",
            "source_block": "CABIN_MAIN",
            "candidate_handle": "E5F6",
        }
    )
    payload["components"] = [second, payload["components"][0]]
    payload["source_handle_to_candidate_handle"] = [
        {"source_handle": "C3D4", "candidate_handle": "E5F6"},
        {"source_handle": "A1B2", "candidate_handle": "C3D4"},
    ]
    return payload


def test_handoff_component_and_mapping_permutations_are_deterministic() -> None:
    module = _module()
    first = _handoff_with_two_components()
    second = deepcopy(first)
    second["components"] = list(reversed(second["components"]))
    second["source_handle_to_candidate_handle"] = list(reversed(second["source_handle_to_candidate_handle"]))
    assert module.validate_base_cad_reuse_handoff(first) == module.validate_base_cad_reuse_handoff(second)
    assert module.base_cad_reuse_handoff_sha256(first) == module.base_cad_reuse_handoff_sha256(second)


def test_reversed_source_candidate_mapping_fails_closed() -> None:
    module = _module()
    payload = _handoff_with_two_components()
    payload["source_handle_to_candidate_handle"] = [
        {"source_handle": "A1B2", "candidate_handle": "E5F6"},
        {"source_handle": "C3D4", "candidate_handle": "C3D4"},
    ]
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_reuse_handoff(payload)


def test_duplicate_candidate_handles_fail_closed_with_valid_source_mapping() -> None:
    module = _module()
    payload = _handoff_with_two_components()
    payload["components"][0]["candidate_handle"] = payload["components"][1]["candidate_handle"]
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_reuse_handoff(payload)


def _casefold_duplicate_source_handle_with_valid_mapping(payload: dict[str, object]) -> None:
    payload["components"][0]["source_handle"] = "a1b2"
    payload["source_handle_to_candidate_handle"] = [
        {"source_handle": "a1b2", "candidate_handle": "E5F6"},
        {"source_handle": "A1B2", "candidate_handle": "C3D4"},
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["components"].append(deepcopy(payload["components"][0])),
        lambda payload: payload["components"][1].__setitem__("logical_component_id", "component-A"),
        _casefold_duplicate_source_handle_with_valid_mapping,
        lambda payload: payload["source_handle_to_candidate_handle"].pop(),
        lambda payload: payload["source_handle_to_candidate_handle"].__setitem__(
            0, {"source_handle": "orphan", "candidate_handle": "E5F6"}
        ),
        lambda payload: payload["source_handle_to_candidate_handle"].append(
            {"source_handle": "extra", "candidate_handle": "extra-candidate"}
        ),
    ],
)
def test_duplicate_case_alias_or_orphan_mapping_fails_closed(mutation) -> None:
    module = _module()
    payload = _handoff_with_two_components()
    mutation(payload)
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_reuse_handoff(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("components.0.source_sha256", "c" * 64),
        ("components.0.source_revision", "rev-B"),
        ("components.0.provenance", "GENERATED"),
        ("components.0.source_handle", "changed-handle"),
        ("components.0.candidate_handle", "changed-candidate"),
    ],
)
def test_root_component_provenance_and_handle_mutations_fail_or_change_identity(
    field: str, value: object
) -> None:
    module = _module()
    payload = _handoff()
    target = payload["components"][0]
    target[field.split(".")[-1]] = value
    if field.endswith("source_handle"):
        with pytest.raises(module.BaseCadAdapterError):
            module.validate_base_cad_reuse_handoff(payload)
    elif field.endswith("candidate_handle"):
        with pytest.raises(module.BaseCadAdapterError):
            module.validate_base_cad_reuse_handoff(payload)
    else:
        with pytest.raises(module.BaseCadAdapterError):
            module.validate_base_cad_reuse_handoff(payload)


@pytest.mark.parametrize("field", ["approval", "verdict", "repair", "publication", "approval_issuer"])
def test_root_authority_fields_are_rejected(field: str) -> None:
    module = _module()
    payload = _handoff()
    payload[field] = {"status": "APPROVED"}
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_reuse_handoff(payload)


def test_s3a_compatible_layer_and_block_pairs_are_accepted() -> None:
    module = _module()
    inspection_components = {
        item["source_handle"]: item for item in _live_inspection()["components"]
    }
    payload = _handoff_with_two_components()
    for component in payload["components"]:
        source = inspection_components[component["source_handle"]]
        component["source_layer"] = source["source_layer"]
        component["source_block"] = source["source_block"]
    normalized = module.validate_base_cad_reuse_handoff(payload)
    assert {
        (item["source_layer"], item["source_block"]) for item in normalized["components"]
    } == {("BODY", "CABIN_MAIN"), ("BODY", "CHASSIS_MAIN")}


def test_s3a_incompatible_layer_and_block_pair_fails_closed() -> None:
    module = _module()
    payload = _handoff_with_two_components()
    next(item for item in payload["components"] if item["source_handle"] == "A1B2")[
        "source_block"
    ] = "CABIN_MAIN"
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_reuse_handoff(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["components"][0]["transform"].__setitem__("path", "private"),
        lambda payload: payload["components"][0]["transform"].pop("translation"),
        lambda payload: payload["components"][0].__setitem__("unknown", "value"),
        lambda payload: payload["base_source"].pop("revision"),
    ],
)
def test_nested_forbidden_unknown_or_missing_fields_fail_closed(mutation) -> None:
    module = _module()
    payload = _handoff()
    mutation(payload)
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_reuse_handoff(payload)


def test_malformed_current_s3a_inspection_fails_closed_without_live_fallback() -> None:
    module = _module()
    inspection = _live_inspection()
    inspection.pop("base_source")
    with pytest.raises(module.BaseCadAdapterError):
        module.evaluate_frozen_base_cad_reuse(
            handoff=_handoff(), current_live_inspection=inspection
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda inspection: inspection.__setitem__("eligible", False),
        lambda inspection: inspection.__setitem__("schema_version", "foreign-inspection-1.0"),
        lambda inspection: inspection["base_source"].__setitem__("sha256", "C" * 64),
        lambda inspection: inspection["components"].__getitem__(0).pop("source_block"),
    ],
)
def test_foreign_or_ineligible_current_inspection_fails_closed(mutation) -> None:
    module = _module()
    inspection = _live_inspection()
    mutation(inspection)
    with pytest.raises(module.BaseCadAdapterError):
        module.evaluate_frozen_base_cad_reuse(
            handoff=_handoff(), current_live_inspection=inspection
        )


def test_slice_two_has_no_extraction_transport_or_current_pointer_owner() -> None:
    module = _module()
    assert not hasattr(module, "execute_base_cad_extraction")
    source = Path(module.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "DotNetIPCClient", "exact_base_xref_extraction", "subprocess", "socket",
        "current_pointer", "registry", "revision_store", "approval_issuer",
    ):
        assert forbidden not in source
