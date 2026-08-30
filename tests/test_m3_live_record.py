from __future__ import annotations

import copy

import pytest

from cad_agent.m3_live_record import (
    M3_LIVE_RECORD_SCHEMA_VERSION,
    M3LiveRecordError,
    seal_m3_live_record,
    validate_m3_live_record,
)


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
    verdict_sha: str,
    task6_turn_id: str,
) -> dict[str, object]:
    return {
        "verdict": verdict,
        "provider_backed": True,
        "request_sha256": request_sha,
        "observation_sha256": observation_sha,
        "verdict_sha256": verdict_sha,
        "candidate_revision_sha256": candidate_sha,
        "candidate_state_sha256": state_sha,
        "latest_mutation_sha256": _sha("7" if verdict == "FAIL" else "d"),
        "task6_thread_id": "thread-m3-live",
        "task6_turn_id": task6_turn_id,
    }


def _valid_payload() -> dict[str, object]:
    pre_candidate = _sha("c")
    pre_state = _sha("d")
    post_candidate = _sha("e")
    post_state = _sha("f")
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
        "pre_r5": _r5(
            verdict="FAIL",
            candidate_sha=pre_candidate,
            state_sha=pre_state,
            request_sha=_sha("4"),
            observation_sha=_sha("5"),
            verdict_sha=_sha("6"),
            task6_turn_id="turn-m3-live-pre",
        ),
        "repair": {
            "authorization_sha256": _sha("8"),
            "authorization_consumed": True,
            "candidate_revision_sha256": pre_candidate,
            "r5_failure_sha256": _sha("6"),
            "repair_plan_sha256": _sha("0"),
            "operation_kind": "REPAIR_DXF_PRIMITIVE",
            "capability": "LINE",
            "operation_fingerprint_sha256": _sha("9"),
            "r6_result_sha256": _sha("a"),
            "outcome": "SUCCESS",
            "attempts": 1,
        },
        "post_r5": _r5(
            verdict="PASS",
            candidate_sha=post_candidate,
            state_sha=post_state,
            request_sha=_sha("0"),
            observation_sha=_sha("1"),
            verdict_sha=_sha("2"),
            task6_turn_id="turn-m3-live-post",
        ),
        "transport": {
            "fileipc": {"attempts": 2, "successes": 2, "failures": 0},
            "dotnetipc": {"attempts": 2, "successes": 2, "failures": 0},
            "task6_provider": {"attempts": 2, "successes": 2, "failures": 0},
            "repair_executor": {"attempts": 1, "successes": 1, "failures": 0},
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
