from __future__ import annotations

from copy import deepcopy
import importlib.util
from importlib import import_module
import json
from pathlib import Path

import pytest


_FACADE_TEST_MODULE = Path(__file__).with_name("test_cad_agent_cad_read_facade.py")


def _skills():
    try:
        return import_module("cad_agent.mechanical_skills")
    except ModuleNotFoundError as error:
        raise AssertionError("Phase 2 Mechanical skill facade is not implemented") from error


def _owner_observation() -> dict[str, object]:
    spec = importlib.util.spec_from_file_location(
        "phase2_facade_fixtures", _FACADE_TEST_MODULE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    facade = import_module("cad_agent.cad_read_facade")
    return facade.observe_drawing(client=module._client(), **module._bound_kwargs())


def _source_bound_binding() -> dict[str, object]:
    source_sha256 = "1" * 64
    return {
        "source_sha256": source_sha256,
        "page_index": 0,
        "roi_bbox_px": [10, 20, 410, 220],
        "source_render_sha256": "2" * 64,
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 0.5,
            "origin_px": [10.0, 20.0],
            "method": "manual_override",
            "reference_note": "P1 source dimensions",
            "status": "verified",
            "source_sha256": source_sha256,
        },
        "profile_id": "simple-stepped-shaft-p1-v1",
    }


def _source_bound_proposal() -> dict[str, object]:
    binding = _source_bound_binding()
    return {
        "schema_version": "p1-source-bound-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "dimensions_mm": {
            "shaft_diameter_a": 40.0,
            "shaft_diameter_b": 60.0,
            "segment_length_a": 80.0,
            "segment_length_b": 50.0,
            "hole_diameter": 10.0,
            "hole_axial_position": 95.0,
        },
        "evidence_refs": {},
    }


def test_catalog_has_read_bom_compile_only_bundle_and_deferred_generic_geometry() -> None:
    catalog = _skills().get_mechanical_skill_catalog()

    assert set(catalog) == {"schema_version", "skills", "catalog_sha256"}
    assert catalog["schema_version"] == "mechanical-skill-catalog-1.0"
    records = {item["skill_id"]: item for item in catalog["skills"]}
    assert records["inspect.mechanical_bom"]["support_state"] == "READ_ONLY"
    assert records["inspect.mechanical_bom"]["owner_route_id"] == (
        "DOTNET_IPC_MECHANICAL_BOM_READ"
    )
    assert records["geometry.simple_shaft_pilot"]["support_state"] == "COMPILE_ONLY"
    assert records["geometry.simple_shaft_pilot"]["owner_route_id"] == (
        "MECHANICAL_PILOT_COMPILE_ONLY"
    )
    assert records["geometry.simple_shaft_pilot"]["capability_refs"] == [
        "mechanical_shaft_step",
        "mechanical_hole_feature",
    ]
    assert records["geometry.shaft_step"]["support_state"] == "DEFERRED_UNSUPPORTED"
    assert records["geometry.keyway"]["support_state"] == "DEFERRED_UNSUPPORTED"
    assert records["geometry.hole_feature"]["support_state"] == "DEFERRED_UNSUPPORTED"


def test_catalog_copy_is_defensive_and_search_is_deterministic() -> None:
    skills = _skills()
    first = skills.get_mechanical_skill_catalog()
    first["skills"][0]["title"] = "tampered"

    second = skills.get_mechanical_skill_catalog()
    assert second["skills"][0]["title"] != "tampered"
    assert skills.search_skills("mechanical bom")[0]["skill_id"] == (
        "inspect.mechanical_bom"
    )
    assert [item["skill_id"] for item in skills.search_skills("shaft")] == [
        "geometry.simple_shaft_pilot"
    ]
    deferred = skills.search_skills("shaft", include_deferred=True)
    deferred_ids = [item["skill_id"] for item in deferred]
    assert set(deferred_ids) == {
        "geometry.simple_shaft_pilot",
        "geometry.shaft_step",
        "geometry.keyway",
    }


@pytest.mark.parametrize("intent", ["", "x" * 257])
def test_search_rejects_unbounded_or_empty_intent(intent: str) -> None:
    with pytest.raises(_skills().MechanicalSkillError, match="INTENT_INVALID"):
        _skills().search_skills(intent)


@pytest.mark.parametrize("limit", [0, 26, True, "10"])
def test_search_rejects_invalid_limit(limit: object) -> None:
    with pytest.raises(_skills().MechanicalSkillError, match="LIMIT_INVALID"):
        _skills().search_skills("bom", limit=limit)


def test_catalog_validator_rejects_tampering_and_unknown_fields() -> None:
    skills = _skills()
    catalog = skills.get_mechanical_skill_catalog()

    tampered = deepcopy(catalog)
    tampered["skills"][0]["title"] = "tampered"
    with pytest.raises(skills.MechanicalSkillError, match="RECORD_HASH_MISMATCH"):
        skills.validate_mechanical_skill_catalog(tampered)

    extra = deepcopy(catalog)
    extra["unexpected"] = True
    with pytest.raises(skills.MechanicalSkillError, match="CATALOG_SCHEMA_INVALID"):
        skills.validate_mechanical_skill_catalog(extra)


def test_invoke_compiles_one_closed_read_only_plan_bound_to_owner_observation() -> None:
    skills = _skills()
    observation = _owner_observation()

    plan = skills.invoke_skill(
        "inspect.mechanical_bom",
        parameters={},
        drawing_observation=observation,
    )

    assert set(plan) == {
        "schema_version",
        "skill_id",
        "skill_version",
        "catalog_sha256",
        "catalog_record_sha256",
        "support_state",
        "output_kind",
        "owner_route_id",
        "capability_refs",
        "drawing_binding",
        "operation_plan",
        "max_operations",
        "plan_sha256",
    }
    assert plan["schema_version"] == "skill-invocation-plan-1.0"
    expected_binding = {
        key: value for key, value in observation["binding"].items() if key != "drawing_path"
    }
    assert plan["drawing_binding"] == expected_binding
    assert plan["operation_plan"] == {
        "operation": "mechanical_bom",
        "parameters": {},
    }
    assert "drawing_path" not in json.dumps(plan)
    assert "ipc_root" not in json.dumps(plan)
    assert "HWND" not in json.dumps(plan)
    assert skills.validate_skill_invocation_plan(plan) == plan


def test_invoke_simple_shaft_bundle_returns_compile_only_plan_without_cad_observation() -> None:
    skills = _skills()
    proposal = _source_bound_proposal()
    binding = _source_bound_binding()

    plan = skills.invoke_skill(
        "geometry.simple_shaft_pilot",
        parameters={"proposal": proposal, "expected_binding": binding},
    )

    assert plan["schema_version"] == "p1-source-bound-compile-plan-1.0"
    assert plan["proposal_source"] == "external_ai"
    assert plan["source_binding"] == binding
    assert plan["geometry_contract"]["line_count"] == 8
    assert plan["geometry_contract"]["circle_count"] == 1
    assert plan["feature_contract"]["shaft-profile-001"]["kind"] == "shaft_step"
    assert plan["feature_contract"]["hole-axial-001"]["kind"] == "hole_feature"
    assert "geometry_opencv" not in json.dumps(plan, sort_keys=True)
    assert "drawing_binding" not in plan


def test_invoke_reuses_phase1_owner_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    facade = import_module("cad_agent.cad_read_facade")
    original = facade.validate_observe_drawing_result
    calls: list[dict[str, object]] = []

    def recording_validator(payload: dict[str, object]) -> dict[str, object]:
        calls.append(payload)
        return original(payload)

    monkeypatch.setattr(facade, "validate_observe_drawing_result", recording_validator)
    _skills().invoke_skill(
        "inspect.mechanical_bom",
        parameters={},
        drawing_observation=_owner_observation(),
    )

    assert len(calls) == 1


def test_invoke_rejects_invalid_parameters_deferred_skills_and_tampered_observation() -> None:
    skills = _skills()
    observation = _owner_observation()

    with pytest.raises(skills.MechanicalSkillError, match="PARAMETERS_INVALID"):
        skills.invoke_skill(
            "inspect.mechanical_bom",
            parameters={"unexpected": True},
            drawing_observation=observation,
        )
    with pytest.raises(skills.MechanicalSkillError, match="SKILL_NOT_INVOCABLE"):
        skills.invoke_skill(
            "geometry.keyway", parameters={}, drawing_observation=observation
        )

    tampered = deepcopy(observation)
    tampered["result_sha256"] = "0" * 64
    with pytest.raises(skills.MechanicalSkillError, match="DRAWING_OBSERVATION_INVALID"):
        skills.invoke_skill(
            "inspect.mechanical_bom", parameters={}, drawing_observation=tampered
        )


def test_compile_only_bundle_refuses_arbitrary_parameters() -> None:
    skills = _skills()
    with pytest.raises(skills.MechanicalSkillError, match="PARAMETERS_INVALID"):
        skills.invoke_skill(
            "geometry.simple_shaft_pilot",
            parameters={"command": "LINE"},
        )


def test_plan_validator_rejects_tampering_and_route_override_is_not_an_api() -> None:
    skills = _skills()
    plan = skills.invoke_skill(
        "inspect.mechanical_bom",
        parameters={},
        drawing_observation=_owner_observation(),
    )
    tampered = deepcopy(plan)
    tampered["operation_plan"]["operation"] = "entity-erase"
    with pytest.raises(skills.MechanicalSkillError, match="PLAN_HASH_MISMATCH"):
        skills.validate_skill_invocation_plan(tampered)

    with pytest.raises(TypeError):
        skills.invoke_skill(
            "inspect.mechanical_bom",
            parameters={},
            drawing_observation=_owner_observation(),
            owner_route_id="ARBITRARY",
        )


def test_skill_module_has_no_arbitrary_execution_surface() -> None:
    skills = _skills()
    source = Path(skills.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "eval(",
        "exec(",
        "importlib",
        "subprocess",
        "os.system",
        "Popen",
        "raw_lisp",
        "drawing_save",
        "entity_create",
        "entity_erase",
    ):
        assert forbidden not in source
