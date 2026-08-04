from __future__ import annotations

import pytest

from cad_agent.visual_contracts import (
    VisualContractError,
    require_dimension_gate_ready,
    require_auto_publish_authorized,
    require_region_verified,
    validate_visual_contract,
)
from tests.visual_supervisor_fixtures import (
    INITIAL_TARGET_SHA,
    RUN_ID,
    TARGET_PATH,
    valid_dimension_register,
    valid_auto_publish_authorization,
    valid_region_verification_register,
    valid_repair_plan,
)


def test_dimension_gate_rejects_incomplete_cluster_disposition() -> None:
    payload = valid_dimension_register()
    payload["coverage"]["clusters_detected"] = 2
    with pytest.raises(VisualContractError, match="clusters"):
        require_dimension_gate_ready(payload)


def test_dimension_gate_accepts_complete_confirmed_register() -> None:
    require_dimension_gate_ready(valid_dimension_register())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("verdict", "PASS"),
        ("publish", True),
        ("publication_policy", "AUTO"),
        ("target_path", "D:\\Synthetic\\drawing.dwg"),
    ],
)
def test_repair_plan_rejects_pass_and_publish_authority(field: str, value: object) -> None:
    payload = valid_repair_plan()
    payload[field] = value
    with pytest.raises(VisualContractError, match="Unexpected properties"):
        validate_visual_contract(payload, contract="repair_plan")


def test_repair_plan_rejects_direct_pixel_coordinate_operation() -> None:
    payload = valid_repair_plan()
    payload["operations"][0]["operation"] = "MOVE_TO_PIXEL"
    with pytest.raises(VisualContractError, match="operation"):
        validate_visual_contract(payload, contract="repair_plan")


def test_repair_plan_requires_affected_regions() -> None:
    payload = valid_repair_plan()
    payload["affected_regions"] = []
    with pytest.raises(VisualContractError, match="affected_regions"):
        validate_visual_contract(payload, contract="repair_plan")


def test_region_verified_rejects_stale_mutation_binding() -> None:
    payload = valid_region_verification_register()
    payload["cad_evidence"]["latest_mutation_sha256"] = "9" * 64
    with pytest.raises(VisualContractError, match="stale"):
        require_region_verified(payload)


@pytest.mark.parametrize(
    ("gate", "status"),
    [("geometry", "FAIL"), ("visual", "FAIL"), ("engineering", "FAIL")],
)
def test_region_verified_requires_every_constituent_gate(gate: str, status: str) -> None:
    payload = valid_region_verification_register()
    payload[gate]["status"] = status
    with pytest.raises(VisualContractError, match=gate):
        require_region_verified(payload)


def test_region_verified_rejects_unresolved_critical_items() -> None:
    payload = valid_region_verification_register()
    payload["unresolved_critical_items"] = ["DIM-SIDE-014"]
    with pytest.raises(VisualContractError, match="unresolved"):
        require_region_verified(payload)


def test_publish_authorization_requires_single_use_and_expiry() -> None:
    payload = valid_auto_publish_authorization()
    payload["single_use"] = False
    with pytest.raises(VisualContractError, match="single_use"):
        validate_visual_contract(payload, contract="auto_publish_authorization")


def test_publish_authorization_rejects_consumed_permission() -> None:
    payload = valid_auto_publish_authorization()
    payload["consumed"] = True
    with pytest.raises(VisualContractError, match="consumed"):
        require_auto_publish_authorized(
            payload,
            run_id=RUN_ID,
            target_path=TARGET_PATH,
            target_sha256=INITIAL_TARGET_SHA,
        )


def test_publish_authorization_rejects_target_hash_mismatch() -> None:
    with pytest.raises(VisualContractError, match="target SHA"):
        require_auto_publish_authorized(
            valid_auto_publish_authorization(),
            run_id=RUN_ID,
            target_path=TARGET_PATH,
            target_sha256="9" * 64,
        )


def test_publish_authorization_accepts_exact_binding() -> None:
    require_auto_publish_authorized(
        valid_auto_publish_authorization(),
        run_id=RUN_ID,
        target_path=TARGET_PATH,
        target_sha256=INITIAL_TARGET_SHA,
    )
