from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from mcp_integration_lib import exact_base_xref as contract


FIXTURE = Path(__file__).with_name("fixtures") / "exact-base-xref-inspection.json"


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _inspection() -> dict[str, object]:
    return copy.deepcopy(_fixture()["inspection"])


def _plan() -> dict[str, object]:
    return copy.deepcopy(_fixture()["plan"])


def _assert_inspection_rejected(payload: object) -> None:
    with pytest.raises(contract.ExactBaseXrefError):
        contract.validate_xref_inspection(payload)


def _assert_plan_rejected(payload: object, inspection: object | None = None) -> None:
    with pytest.raises(contract.ExactBaseXrefError):
        contract.validate_extraction_plan(payload, inspection=inspection)


def test_fixture_round_trip_validates_inspection_and_plan() -> None:
    fixture = _fixture()

    inspection = contract.validate_xref_inspection(fixture["inspection"])
    plan = contract.validate_extraction_plan(fixture["plan"], inspection=inspection)

    assert inspection["eligible"] is True
    assert plan["approval"] == {"reference": None, "status": "PROPOSED"}
    assert plan["provenance"] == "REUSED_FROM_BASE_CAD"


def test_builder_is_deterministic_and_copies_only_inspected_component_metadata() -> None:
    fixture = _fixture()
    inspection = contract.validate_xref_inspection(fixture["inspection"])
    selections = [
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

    built = contract.build_extraction_plan(
        plan_id="extraction-plan-001",
        inspection=inspection,
        selections=selections,
        impacted_views=[
            {"identity": "model-space", "name": "Model"},
            {"identity": "layout-001", "name": "Layout1"},
        ],
    )

    assert built == fixture["plan"]
    assert all("target_handle" not in component for component in built["components"])


def test_ineligible_identity_or_dimension_cannot_build_a_plan() -> None:
    identity_failure = _inspection()
    identity_failure["identity_observations"][0]["observed"] = "other-vehicle"
    identity_failure["identity_observations"][0]["status"] = "FAIL"
    identity_failure["eligible"] = False

    validated = contract.validate_xref_inspection(identity_failure)
    assert validated["eligible"] is False
    with pytest.raises(contract.ExactBaseXrefError):
        contract.build_extraction_plan(
            plan_id="blocked-identity",
            inspection=identity_failure,
            selections=[],
        )

    dimension_failure = _inspection()
    dimension_failure["critical_dimensions"][0]["observed"] = 2800.0
    dimension_failure["critical_dimensions"][0]["status"] = "FAIL"
    dimension_failure["eligible"] = False

    validated = contract.validate_xref_inspection(dimension_failure)
    assert validated["eligible"] is False
    with pytest.raises(contract.ExactBaseXrefError):
        contract.build_extraction_plan(
            plan_id="blocked-dimension",
            inspection=dimension_failure,
            selections=[],
        )


def test_identity_or_dimension_status_cannot_claim_pass_when_values_do_not_match() -> None:
    identity_failure = _inspection()
    identity_failure["identity_observations"][0]["observed"] = "other-vehicle"
    _assert_inspection_rejected(identity_failure)

    dimension_failure = _inspection()
    dimension_failure["critical_dimensions"][0]["observed"] = 2800.0
    _assert_inspection_rejected(dimension_failure)


def test_missing_critical_control_is_rejected() -> None:
    payload = _inspection()
    payload["critical_dimensions"] = payload["critical_dimensions"][:-1]
    _assert_inspection_rejected(payload)


@pytest.mark.parametrize("path", ["C:/drawings/base.dwg", "/tmp/base.dwg", "../base.dwg", "approved/../base.dwg", "approved\\base.dwg"])
def test_source_paths_must_be_safe_relative_posix_paths(path: str) -> None:
    payload = _inspection()
    payload["base_source"]["relative_path"] = path
    _assert_inspection_rejected(payload)


@pytest.mark.parametrize("field", ["sha256", "target_drawing_sha256"])
@pytest.mark.parametrize("value", ["A" * 64, "a" * 63, "a" * 65, "not-a-hash"])
def test_source_and_target_hashes_must_be_lowercase_sha256(field: str, value: str) -> None:
    payload = _inspection()
    if field == "sha256":
        payload["base_source"][field] = value
    else:
        payload[field] = value
    _assert_inspection_rejected(payload)


def test_plan_source_hash_and_target_hash_must_match_inspection() -> None:
    inspection = _inspection()
    payload = _plan()

    payload["base_source"]["sha256"] = "c" * 64
    _assert_plan_rejected(payload, inspection)

    payload = _plan()
    payload["target_drawing_sha256"] = "c" * 64
    _assert_plan_rejected(payload, inspection)


@pytest.mark.parametrize("location", ["root", "base_source", "identity_observations", "critical_dimensions", "components", "xref"])
def test_unknown_fields_are_rejected_at_every_inspection_contract_level(location: str) -> None:
    payload = _inspection()
    target = payload if location == "root" else payload[location]
    if isinstance(target, list):
        target[0]["unexpected"] = "reject-me"
    else:
        target["unexpected"] = "reject-me"
    _assert_inspection_rejected(payload)


@pytest.mark.parametrize("location", ["root", "base_source", "components", "transform", "approval", "impacted_views"])
def test_unknown_fields_are_rejected_at_every_plan_contract_level(location: str) -> None:
    payload = _plan()
    if location == "root":
        payload["unexpected"] = "reject-me"
    elif location == "base_source":
        payload[location]["unexpected"] = "reject-me"
    elif location == "components":
        payload[location][0]["unexpected"] = "reject-me"
    elif location == "transform":
        payload["components"][0][location]["unexpected"] = "reject-me"
    elif location == "approval":
        payload[location]["unexpected"] = "reject-me"
    else:
        payload[location][0]["unexpected"] = "reject-me"
    _assert_plan_rejected(payload, _inspection())


def test_duplicate_components_and_uninspected_selections_are_rejected() -> None:
    inspection = _inspection()
    payload = _plan()
    payload["components"].append(copy.deepcopy(payload["components"][0]))
    _assert_plan_rejected(payload, inspection)

    with pytest.raises(contract.ExactBaseXrefError):
        contract.build_extraction_plan(
            plan_id="unknown-component",
            inspection=inspection,
            selections=[
                {
                    "logical_component_id": "not-inspected",
                    "transform": {
                        "rotation_degrees": 0.0,
                        "translation": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "uniform_scale": 1.0,
                    },
                }
            ],
        )


@pytest.mark.parametrize(
    "transform",
    [
        {"rotation_degrees": 0.0, "translation": {"x": 0.0, "y": 0.0, "z": 0.0}, "uniform_scale": -1.0},
        {"rotation_degrees": 0.0, "translation": {"x": 0.0, "y": 0.0, "z": 0.0}, "uniform_scale": 0.0},
        {"rotation_degrees": 0.0, "translation": {"x": 0.0, "y": 0.0, "z": 0.0}, "uniform_scale": 1.0, "scale_x": 2.0},
        {"rotation_degrees": 0.0, "translation": {"x": 0.0, "y": 0.0, "z": 0.0}, "uniform_scale": 1.0, "matrix": [1, 0, 0, 1]},
    ],
)
def test_only_local_translation_rotation_and_positive_uniform_scale_are_allowed(transform: dict[str, object]) -> None:
    payload = _plan()
    payload["components"][0]["transform"] = transform
    _assert_plan_rejected(payload, _inspection())


def test_global_transform_and_reflection_are_rejected() -> None:
    payload = _plan()
    payload["global_transform"] = {"uniform_scale": 1.0}
    _assert_plan_rejected(payload, _inspection())

    payload = _plan()
    payload["components"][0]["reflection"] = False
    _assert_plan_rejected(payload, _inspection())


@pytest.mark.parametrize(
    ("status", "reference"),
    [("APPROVED", None), ("PROPOSED", "approval-001"), ("UNKNOWN", None)],
)
def test_approval_status_requires_an_explicit_non_fabricated_reference(status: str, reference: object) -> None:
    payload = _plan()
    payload["approval"] = {"status": status, "reference": reference}
    _assert_plan_rejected(payload, _inspection())


def test_approved_plan_requires_only_explicit_reference_and_never_gets_fabricated_by_builder() -> None:
    inspection = _inspection()
    proposed = contract.build_extraction_plan(
        plan_id="proposed-plan",
        inspection=inspection,
        selections=[],
    )
    assert proposed["approval"] == {"status": "PROPOSED", "reference": None}

    approved = _plan()
    approved["approval"] = {"status": "APPROVED", "reference": "approval-001"}
    assert contract.validate_extraction_plan(approved, inspection=inspection)["approval"]["status"] == "APPROVED"


@pytest.mark.parametrize("forbidden", ["verdict", "repair", "publication", "approval", "target_handles", "target_entity_handles"])
def test_verdict_repair_publication_approval_and_target_handle_fields_are_rejected(forbidden: str) -> None:
    payload = _plan()
    payload[forbidden] = "forbidden"
    _assert_plan_rejected(payload, _inspection())


def test_inspection_rejects_mutation_claims_and_unequal_dbmod() -> None:
    payload = _inspection()
    payload["changed"] = True
    _assert_inspection_rejected(payload)

    payload = _inspection()
    payload["dbmod_after"] = 1
    _assert_inspection_rejected(payload)


def test_contract_module_has_no_autocad_transport_or_native_imports() -> None:
    tree = ast.parse(Path(contract.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imported.isdisjoint({"autocad", "clr", "ctypes", "dotnet_ipc", "subprocess", "win32com"})
