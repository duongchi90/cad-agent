from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path

import pytest

from cad_agent.dimension_contracts import (
    DimensionPilotContractError,
    read_dimension_contract,
    validate_dimension_evidence,
    validate_dimension_plan,
)
from dimension_pilot_fixtures import (
    approved_dimension_plan,
    offline_dimension_evidence,
    set_nested,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "contracts" / "dimension-pilot"
EXAMPLES = CONTRACT_ROOT / "examples"


def _assert_schema_accepts(
    schema: dict[str, object],
    value: object,
    path: str = "$",
) -> None:
    if "const" in schema:
        assert value == schema["const"], path
    if "enum" in schema:
        assert value in schema["enum"], path
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        if value is None and "null" in schema_type:
            return
        schema_type = next(item for item in schema_type if item != "null")
    if schema_type == "object":
        assert isinstance(value, dict), path
        required = schema.get("required", [])
        assert not [key for key in required if key not in value], path
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            assert not set(value) - set(properties), path
        for key, item in value.items():
            if key in properties:
                _assert_schema_accepts(properties[key], item, f"{path}.{key}")
    elif schema_type == "array":
        assert isinstance(value, list), path
        if "minItems" in schema:
            assert len(value) >= schema["minItems"], path
        if "maxItems" in schema:
            assert len(value) <= schema["maxItems"], path
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            assert len(encoded) == len(set(encoded)), path
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _assert_schema_accepts(item_schema, item, f"{path}[{index}]")
    elif schema_type == "string":
        assert isinstance(value, str), path
        if "minLength" in schema:
            assert len(value) >= schema["minLength"], path
        if "pattern" in schema:
            assert re.fullmatch(schema["pattern"], value), path
    elif schema_type == "number":
        assert isinstance(value, (int, float)) and not isinstance(value, bool), path
        assert math.isfinite(value), path
    elif schema_type == "integer":
        assert isinstance(value, int) and not isinstance(value, bool), path
    elif schema_type == "boolean":
        assert isinstance(value, bool), path
    if "exclusiveMinimum" in schema:
        assert value > schema["exclusiveMinimum"], path


def test_example_contracts_match_runtime_and_json_schema() -> None:
    pairs = (
        ("dimension-pilot-plan", "plan"),
        ("dimension-pilot-evidence", "evidence"),
    )
    for stem, contract in pairs:
        schema = json.loads(
            (CONTRACT_ROOT / f"{stem}.schema.json").read_text(encoding="utf-8")
        )
        payload = read_dimension_contract(
            EXAMPLES / f"{stem}.json",
            contract=contract,
        )
        _assert_schema_accepts(schema, payload, stem)
    assert read_dimension_contract(
        EXAMPLES / "dimension-pilot-plan.json",
        contract="plan",
    )["schema_version"] == "dimension-pilot-plan-1.0"
    assert read_dimension_contract(
        EXAMPLES / "dimension-pilot-evidence.json",
        contract="evidence",
    )["acceptance"] == "NOT_RUN"


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("measurement_tolerance_mm",), 0.0, "positive"),
        (("datum", "x_axis"), [2.0, 0.0], "unit"),
        (("datum", "y_axis"), [1.0, 0.0], "orthogonal"),
        (("datum", "y_axis"), [0.0, -1.0], "right-handed"),
        (("dimensions", 0, "kind"), "radius", "linear"),
        (("dimensions", 0, "status"), "UNRESOLVED", "APPROVED"),
        (("dimensions", 0, "to", "endpoint"), "start", "opposite"),
    ],
)
def test_plan_rejects_unsafe_values(
    path: tuple[object, ...],
    value: object,
    message: str,
) -> None:
    payload = approved_dimension_plan()
    set_nested(payload, path, value)
    with pytest.raises(DimensionPilotContractError, match=message):
        validate_dimension_plan(payload)


def test_plan_rejects_duplicate_dimension_attachment() -> None:
    payload = approved_dimension_plan()
    duplicate = copy.deepcopy(payload["dimensions"][0])
    duplicate["id"] = "DIM-002"
    duplicate["approval"]["reference"] = "DIM-APPROVAL-002"
    payload["dimensions"].append(duplicate)
    with pytest.raises(DimensionPilotContractError, match="attachment"):
        validate_dimension_plan(payload)


def test_plan_rejects_unknown_properties_duplicate_ids_and_nonfinite_values() -> None:
    payload = approved_dimension_plan()
    payload["unexpected"] = True
    with pytest.raises(DimensionPilotContractError, match="Unexpected"):
        validate_dimension_plan(payload)

    payload = approved_dimension_plan()
    payload["constraint_ids"] = ["constraint-1", "constraint-1"]
    with pytest.raises(DimensionPilotContractError, match="constraint_ids"):
        validate_dimension_plan(payload)

    payload = approved_dimension_plan()
    payload["dimensions"][0]["value_mm"] = float("nan")
    with pytest.raises(DimensionPilotContractError, match="finite"):
        validate_dimension_plan(payload)


def test_validation_returns_a_deep_copy() -> None:
    payload = approved_dimension_plan()
    validated = validate_dimension_plan(payload)
    payload["datum"]["origin_mm"][0] = 99.0
    assert validated["datum"]["origin_mm"] == [0.0, 0.0]


def test_evidence_cannot_claim_acceptance_or_pass_with_blockers() -> None:
    payload = offline_dimension_evidence()
    payload["acceptance"] = "PASS"
    with pytest.raises(DimensionPilotContractError, match="NOT_RUN"):
        validate_dimension_evidence(payload)

    payload = offline_dimension_evidence()
    payload["blockers"] = [
        {"code": "x", "path": "$", "expected": None, "actual": None}
    ]
    with pytest.raises(DimensionPilotContractError, match="offline_passed"):
        validate_dimension_evidence(payload)


def test_evidence_pass_requires_dxf_solver_closure_and_measurement() -> None:
    payload = offline_dimension_evidence()
    payload["dxf_sha256"] = None
    with pytest.raises(DimensionPilotContractError, match="dxf_sha256"):
        validate_dimension_evidence(payload)

    payload = offline_dimension_evidence()
    payload["solver"]["model_dof"] = 1
    with pytest.raises(DimensionPilotContractError, match="model_dof"):
        validate_dimension_evidence(payload)

    payload = offline_dimension_evidence()
    payload["measurements"] = []
    with pytest.raises(DimensionPilotContractError, match="measurement"):
        validate_dimension_evidence(payload)


def test_blocked_evidence_allows_null_dxf_and_requires_blocker() -> None:
    payload = offline_dimension_evidence()
    payload["offline_passed"] = False
    payload["dxf_sha256"] = None
    payload["measurements"] = []
    payload["blockers"] = [
        {
            "code": "setup_incomplete",
            "path": "$.setup",
            "expected": "SETUP_VERIFIED",
            "actual": "NEEDS_REVIEW",
        }
    ]
    assert validate_dimension_evidence(payload)["offline_passed"] is False


def test_read_contract_rejects_wrong_kind_and_nonobject_root(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(DimensionPilotContractError, match="root"):
        read_dimension_contract(path, contract="plan")
    with pytest.raises(DimensionPilotContractError, match="unsupported"):
        read_dimension_contract(path, contract="other")
