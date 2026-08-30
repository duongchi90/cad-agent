from __future__ import annotations

import copy

import pytest

from cad_agent.approved_repair_adapter import R6_RESULT_SCHEMA_VERSION
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.m3_live_record import (
    M3_LIVE_RECORD_SCHEMA_VERSION,
    M3LiveRecordError,
    seal_m3_live_record,
    validate_m3_live_record,
)
from cad_agent.repair_operation_contract import REPAIR_OPERATION_SCHEMA_VERSION
from cad_agent.visual_supervisor_adapter import R5_VISUAL_VERDICT_RESULT_SCHEMA_VERSION


MAIN_SHA = "a" * 40
PLUGIN_SHA = "b" * 64


def _sha(seed: str) -> str:
    return (seed * 64)[:64]


def _r5(
    *,
    verdict: str,
    candidate_sha: str,
    state_sha: str,
    request_sha: str,
    observation_sha: str,
    task6_turn_id: str,
) -> dict[str, object]:
    latest_mutation_sha = _sha("7" if verdict == "FAIL" else "d")
    result_payload = {
        "schema_version": R5_VISUAL_VERDICT_RESULT_SCHEMA_VERSION,
        "request_sha256": request_sha,
        "observation_sha256": observation_sha,
        "verdict": verdict,
        "candidate_revision_sha256": candidate_sha,
        "candidate_state_sha256": state_sha,
        "registry_snapshot_sha256": _sha("1"),
        "drawing_reference_sha256": _sha("2"),
        "drawing_observation_sha256": _sha("3"),
        "latest_mutation_sha256": latest_mutation_sha,
        "task6_thread_id": "thread-m3-live",
        "task6_turn_id": task6_turn_id,
        "regions": [
            {
                "region_id": "region-m3-live",
                "view_id": "view-m3-live",
                "sheet_id": "sheet-m3-live",
                "layout_id": "layout-m3-live",
                "criticality": "CRITICAL",
                "status": verdict,
            }
        ],
    }
    canonical_sha = canonical_json_sha256(result_payload)
    canonical_result = {
        **result_payload,
        "verdict_id": canonical_sha,
        "verdict_sha256": canonical_sha,
    }
    return {
        "verdict": verdict,
        "provider_backed": True,
        "request_sha256": request_sha,
        "observation_sha256": observation_sha,
        "verdict_sha256": canonical_sha,
        "candidate_revision_sha256": candidate_sha,
        "candidate_state_sha256": state_sha,
        "latest_mutation_sha256": latest_mutation_sha,
        "task6_thread_id": "thread-m3-live",
        "task6_turn_id": task6_turn_id,
        "canonical_result": canonical_result,
    }


def _r6_result(
    *,
    candidate_sha: str,
    r5_failure: dict[str, object],
    repair_plan_sha: str,
    operation_fingerprint: str,
    authorization_id: str,
) -> dict[str, object]:
    semantic = {
        "schema_version": R6_RESULT_SCHEMA_VERSION,
        "candidate_revision_id": "candidate-m3-live",
        "candidate_revision_sha256": candidate_sha,
        "candidate_artifact_reference_id": "artifact-m3-live",
        "candidate_artifact_reference_sha256": _sha("4"),
        "r5_failure_id": r5_failure["canonical_result"]["verdict_id"],
        "r5_failure_sha256": r5_failure["verdict_sha256"],
        "repair_plan_id": "plan-m3-live",
        "repair_plan_sha256": repair_plan_sha,
        "repair_plan_version": "repair-plan-1.0",
        "repair_operation_contract_version": REPAIR_OPERATION_SCHEMA_VERSION,
        "repair_operation_contract_fingerprint": operation_fingerprint,
        "authorization_id": authorization_id,
        "executor_capability": "LINE",
        "executor_result_category": "HANDLE_RETURNED",
        "mutation_outcome": "SUCCESS",
        "closure": {
            "lease_id": "lease-m3-live",
            "candidate_identity": "candidate-m3-live",
            "source_identity": r5_failure["canonical_result"]["verdict_id"],
            "source_fingerprint": r5_failure["verdict_sha256"],
            "close_outcome": "closed",
            "cleanup_outcome": "zero_survivors",
            "save_changes": False,
            "lifecycle_state": "closed",
        },
        "requires_new_r5_cycle": True,
    }
    return {**semantic, "result_sha256": canonical_json_sha256(semantic)}


def _valid_payload() -> dict[str, object]:
    pre_candidate = _sha("c")
    pre_state = _sha("d")
    post_candidate = _sha("e")
    post_state = _sha("f")
    pre_r5 = _r5(
        verdict="FAIL",
        candidate_sha=pre_candidate,
        state_sha=pre_state,
        request_sha=_sha("4"),
        observation_sha=_sha("5"),
        task6_turn_id="turn-m3-live-pre",
    )
    post_r5 = _r5(
        verdict="PASS",
        candidate_sha=post_candidate,
        state_sha=post_state,
        request_sha=_sha("0"),
        observation_sha=_sha("1"),
        task6_turn_id="turn-m3-live-post",
    )
    repair_plan_sha = _sha("0")
    operation_fingerprint = _sha("9")
    r6_result = _r6_result(
        candidate_sha=pre_candidate,
        r5_failure=pre_r5,
        repair_plan_sha=repair_plan_sha,
        operation_fingerprint=operation_fingerprint,
        authorization_id="auth-m3-live",
    )
    return {
        "schema_version": M3_LIVE_RECORD_SCHEMA_VERSION,
        "epoch_id": "m3-line-live-001",
        "mode": "LIVE_PROVIDER_BACKED",
        "status": "PASS",
        "live_acceptance": True,
        "main_sha": MAIN_SHA,
        "implementation_sha": MAIN_SHA,
        "plugin_binary_sha256_expected": PLUGIN_SHA,
        "plugin_binary_sha256_observed": PLUGIN_SHA,
        "started_at": "2026-08-30T11:00:00Z",
        "finished_at": "2026-08-30T11:00:12Z",
        "wall_clock_seconds": 12.0,
        "runtime": {
            "observed": True,
            "autocad_product": "AutoCAD Mechanical 2027",
            "plugin_version": "1.0.0",
            "pid": 27812,
            "hwnd": 10881220,
            "runtime_identity": "acad-pid-27812-hwnd-10881220",
            "active_document_sha256": _sha("3"),
        },
        "candidate": {
            "pre_revision_sha256": pre_candidate,
            "pre_state_sha256": pre_state,
            "pre_artifact_sha256": _sha("2"),
            "post_revision_sha256": post_candidate,
            "post_state_sha256": post_state,
            "post_artifact_sha256": _sha("3"),
            "distinct_post": True,
        },
        "pre_r5": pre_r5,
        "repair": {
            "authorization_sha256": _sha("8"),
            "authorization_id": "auth-m3-live",
            "authorization_consumed": True,
            "candidate_revision_sha256": pre_candidate,
            "r5_failure_id": pre_r5["canonical_result"]["verdict_id"],
            "r5_failure_sha256": pre_r5["verdict_sha256"],
            "repair_plan_id": "plan-m3-live",
            "repair_plan_sha256": repair_plan_sha,
            "repair_plan_version": "repair-plan-1.0",
            "repair_operation_contract_version": REPAIR_OPERATION_SCHEMA_VERSION,
            "operation_kind": "REPAIR_DXF_PRIMITIVE",
            "capability": "LINE",
            "operation_fingerprint_sha256": operation_fingerprint,
            "r6_result_sha256": r6_result["result_sha256"],
            "outcome": "SUCCESS",
            "attempts": 1,
            "canonical_result": r6_result,
        },
        "post_r5": post_r5,
        "transport": {
            "fileipc": {"attempts": 1, "successes": 1, "failures": 0, "retries": 0},
            "dotnetipc": {"attempts": 1, "successes": 1, "failures": 0, "retries": 0},
            "task6_provider": {"attempts": 1, "successes": 1, "failures": 0, "retries": 0},
            "repair_executor": {"attempts": 1, "successes": 1, "failures": 0, "retries": 0},
        },
        "integrity": {
            "source_before_sha256": _sha("3"),
            "source_after_sha256": _sha("3"),
            "staged_before_sha256": _sha("4"),
            "staged_after_sha256": _sha("4"),
            "accepted_before_sha256": _sha("5"),
            "accepted_after_sha256": _sha("5"),
        },
        "cleanup": {
            "closed_without_save": True,
            "zero_survivors": True,
            "release_verified": True,
            "ambiguous": False,
        },
        "human_intervention": {
            "captured": True,
            "events": [
                {"kind": "NETLOAD", "count": 1},
                {"kind": "APPLOAD", "count": 1},
            ],
        },
    }


def test_seal_and_validate_provider_backed_live_record() -> None:
    sealed = seal_m3_live_record(_valid_payload())

    assert len(sealed["record_sha256"]) == 64
    assert validate_m3_live_record(
        sealed,
        expected_main_sha=MAIN_SHA,
        expected_plugin_sha256=PLUGIN_SHA,
    ) == sealed


@pytest.mark.parametrize(
    ("path", "mutator"),
    [
        ("plugin_binary_sha256_observed", lambda item: item.update(plugin_binary_sha256_observed=_sha("z"))),
        ("pre_r5.provider_backed", lambda item: item["pre_r5"].update(provider_backed=False)),
        ("post_r5.candidate_revision_sha256", lambda item: item["post_r5"].update(candidate_revision_sha256=_sha("z"))),
        ("repair.attempts", lambda item: item["repair"].update(attempts=2)),
        ("transport.dotnetipc", lambda item: item["transport"].update(dotnetipc={"attempts": 1, "successes": 2, "failures": 0})),
        ("cleanup.ambiguous", lambda item: item["cleanup"].update(ambiguous=True)),
    ],
)
def test_live_record_rejects_non_decision_grade_evidence(path: str, mutator) -> None:
    payload = _valid_payload()
    mutator(payload)

    with pytest.raises(M3LiveRecordError, match=path.split(".")[0]):
        seal_m3_live_record(payload)


def test_live_record_rejects_contract_only_pass_and_unexpected_keys() -> None:
    contract_only = _valid_payload()
    contract_only["mode"] = "CONTRACT_ONLY"
    with pytest.raises(M3LiveRecordError, match="CONTRACT_ONLY|live"):
        seal_m3_live_record(contract_only)

    unexpected = _valid_payload()
    unexpected["caller_supplied_hash"] = PLUGIN_SHA
    with pytest.raises(M3LiveRecordError, match="unexpected"):
        seal_m3_live_record(unexpected)

    branch_drift = _valid_payload()
    branch_drift["implementation_sha"] = "c" * 40
    with pytest.raises(M3LiveRecordError, match="implementation_sha"):
        seal_m3_live_record(branch_drift)


def test_live_record_rejects_forged_record_hash() -> None:
    sealed = seal_m3_live_record(_valid_payload())
    forged = copy.deepcopy(sealed)
    forged["record_sha256"] = _sha("z")

    with pytest.raises(M3LiveRecordError, match="record_sha256"):
        validate_m3_live_record(forged)


def test_live_record_rejects_transport_failure_or_retry() -> None:
    payload = _valid_payload()
    payload["transport"]["fileipc"] = {
        "attempts": 2,
        "successes": 1,
        "failures": 1,
        "retries": 1,
    }

    with pytest.raises(M3LiveRecordError, match="transport"):
        seal_m3_live_record(payload)


def test_live_record_rejects_reduced_fabricated_r5_result() -> None:
    payload = _valid_payload()
    payload["pre_r5"]["canonical_result"] = {
        key: value
        for key, value in payload["pre_r5"].items()
        if key != "canonical_result"
    }

    with pytest.raises(M3LiveRecordError, match="R5|canonical"):
        seal_m3_live_record(payload)


def test_live_record_rejects_fabricated_r6_result() -> None:
    payload = _valid_payload()
    payload["repair"]["canonical_result"] = {
        key: value
        for key, value in payload["repair"].items()
        if key != "canonical_result"
    }

    with pytest.raises(M3LiveRecordError, match="R6|canonical"):
        seal_m3_live_record(payload)


def test_live_record_accepts_zero_human_interventions() -> None:
    payload = _valid_payload()
    payload["human_intervention"] = {"captured": True, "events": []}

    sealed = seal_m3_live_record(payload)

    assert sealed["human_intervention"] == {"captured": True, "events": []}


def test_live_record_rejects_repair_executor_retry_even_when_reconciled() -> None:
    payload = _valid_payload()
    payload["transport"]["repair_executor"] = {
        "attempts": 2,
        "successes": 2,
        "failures": 0,
        "retries": 0,
    }

    with pytest.raises(M3LiveRecordError, match="transport|repair"):
        seal_m3_live_record(payload)
