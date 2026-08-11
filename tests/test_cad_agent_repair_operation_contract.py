"""Causal and contract tests for the neutral repair-operation payload."""

from __future__ import annotations

import copy
import math

import pytest

from cad_agent.repair_operation_contract import (
    REPAIR_OPERATION_SCHEMA_VERSION,
    RepairOperationContractError,
    canonicalize_repair_operation,
    normalize_repair_operation,
)


def _line_payload() -> dict[str, object]:
    return {
        "schema_version": REPAIR_OPERATION_SCHEMA_VERSION,
        "operation": "REPAIR_DXF_PRIMITIVE",
        "target": {"stable_entity_id": "entity-1", "feature": "line"},
        "parameters": {
            "entity_type": "LINE",
            "start": [0.0, 0.0],
            "end": [10.0, 0.0],
        },
        "preserve_anchors": ["anchor-1"],
        "constraint_refs": ["constraint-1"],
    }


def _component_payload() -> dict[str, object]:
    return {
        "schema_version": REPAIR_OPERATION_SCHEMA_VERSION,
        "operation": "REPAIR_DXF_COMPONENT",
        "target": {"stable_entity_id": "part-1", "feature": "component"},
        "parameters": {
            "block_name": "FRAME_BEAM",
            "insert": [1.0, 2.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
            "rotation_deg": 0.0,
            "attributes": {"PART_ID": "part-1"},
        },
        "preserve_anchors": [],
        "constraint_refs": [],
    }


def test_missing_public_contract_is_now_a_causal_red_or_green_surface() -> None:
    normalized = normalize_repair_operation(_line_payload())
    assert normalized.schema_version == REPAIR_OPERATION_SCHEMA_VERSION
    assert normalized.operation == "REPAIR_DXF_PRIMITIVE"


@pytest.mark.parametrize("entity_type", ["LINE", "CIRCLE", "ARC", "TEXT"])
def test_primitive_variants_have_closed_operation_specific_payloads(entity_type: str) -> None:
    payload = _line_payload()
    payload["parameters"] = {
        "entity_type": entity_type,
        **{
            "LINE": {"start": [0.0, 0.0], "end": [1.0, 1.0]},
            "CIRCLE": {"center": [0.0, 0.0], "radius": 2.0},
            "ARC": {
                "center": [0.0, 0.0],
                "radius": 2.0,
                "start_angle_deg": 0.0,
                "end_angle_deg": 90.0,
            },
            "TEXT": {
                "content": "OK",
                "insert": [0.0, 0.0],
                "height": 1.0,
                "rotation_deg": 0.0,
            },
        }[entity_type],
    }
    result = normalize_repair_operation(payload)
    assert result.parameters["entity_type"] == entity_type


def test_component_variant_maps_only_to_existing_insert_repair_owner() -> None:
    result = normalize_repair_operation(_component_payload())
    assert result.operation == "REPAIR_DXF_COMPONENT"
    assert result.parameters["block_name"] == "FRAME_BEAM"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p.__setitem__("operation", "INVENT_NEW_PRIMITIVE"),
        lambda p: p["parameters"].__setitem__("extra", 1),
        lambda p: p.__setitem__("unexpected", True),
        lambda p: p["target"].__setitem__("callable", lambda: None),
    ],
)
def test_unknown_fields_and_dynamic_payloads_fail_closed(mutator) -> None:
    payload = _line_payload()
    mutator(payload)
    with pytest.raises(RepairOperationContractError):
        normalize_repair_operation(payload)


def test_bool_nan_and_infinity_are_not_numbers() -> None:
    payload = _line_payload()
    payload["parameters"]["start"] = [True, 0.0]
    with pytest.raises(RepairOperationContractError):
        normalize_repair_operation(payload)
    payload = _line_payload()
    payload["parameters"]["start"] = [math.nan, 0.0]
    with pytest.raises(RepairOperationContractError):
        normalize_repair_operation(payload)
    payload = _line_payload()
    payload["parameters"]["start"] = [math.inf, 0.0]
    with pytest.raises(RepairOperationContractError):
        normalize_repair_operation(payload)


class _HostileStr(str):
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return hash("REPAIR_DXF_PRIMITIVE")


def test_hostile_string_subclass_is_rejected_at_trust_boundary() -> None:
    payload = _line_payload()
    payload["operation"] = _HostileStr("INVENT_NEW_PRIMITIVE")
    with pytest.raises(RepairOperationContractError):
        normalize_repair_operation(payload)


def test_normalization_is_deterministic_and_immutable_against_caller_mutation() -> None:
    payload = _line_payload()
    original = canonicalize_repair_operation(payload)
    normalized = normalize_repair_operation(payload)
    payload["parameters"]["start"][0] = 999.0
    assert canonicalize_repair_operation(normalized) == original
    assert normalized.parameters["start"] == (0.0, 0.0)


def test_copy_and_mutable_nested_containers_do_not_change_normalized_record() -> None:
    payload = _component_payload()
    normalized = normalize_repair_operation(payload)
    cloned = copy.deepcopy(payload)
    cloned["parameters"]["attributes"]["PART_ID"] = "changed"
    assert normalized.parameters["attributes"]["PART_ID"] == "part-1"


def test_canonicalization_is_privacy_safe() -> None:
    payload = _line_payload()
    payload["target"]["stable_entity_id"] = "private-drawing-secret"
    with pytest.raises(RepairOperationContractError) as exc:
        payload["parameters"]["entity_type"] = "UNSUPPORTED"
        normalize_repair_operation(payload)
    assert "private-drawing-secret" not in str(exc.value)
