from __future__ import annotations

import copy

import pytest

from mcp_integration_lib.m3_live_harness import (
    M3LiveEpochNotRun,
    compose_m3_live_epoch,
)
from tests.test_m3_live_record import MAIN_SHA, PLUGIN_SHA, _sha, _valid_payload


def _callbacks():
    payload = _valid_payload()
    calls: list[str] = []

    def observe_runtime():
        calls.append("runtime")
        return copy.deepcopy(payload["runtime"])

    def collect_pre_r5(_runtime):
        calls.append("pre_r5")
        return copy.deepcopy(payload["pre_r5"])

    def authorize_repair(pre_r5):
        calls.append("authorize")
        assert pre_r5["verdict"] == "FAIL"
        return {
            "authorization_sha256": payload["repair"]["authorization_sha256"],
            "authorization_id": payload["repair"]["authorization_id"],
            "authorization_consumed": True,
            "candidate_revision_sha256": payload["repair"]["candidate_revision_sha256"],
            "r5_failure_sha256": payload["repair"]["r5_failure_sha256"],
            "repair_plan_sha256": payload["repair"]["repair_plan_sha256"],
            "operation_kind": payload["repair"]["operation_kind"],
            "capability": payload["repair"]["capability"],
            "operation_fingerprint_sha256": payload["repair"]["operation_fingerprint_sha256"],
        }

    def execute_repair(authorization):
        calls.append("repair")
        assert authorization["authorization_consumed"] is True
        return copy.deepcopy(payload["repair"])

    def collect_post_candidate(runtime, repair):
        calls.append("post_candidate")
        assert runtime["observed"] is True
        assert repair["attempts"] == 1
        return copy.deepcopy(payload["candidate"])

    def collect_post_r5(candidate):
        calls.append("post_r5")
        assert candidate["distinct_post"] is True
        return copy.deepcopy(payload["post_r5"])

    def collect_transport():
        calls.append("transport")
        return copy.deepcopy(payload["transport"])

    def collect_integrity():
        calls.append("integrity")
        return copy.deepcopy(payload["integrity"])

    def collect_cleanup():
        calls.append("cleanup")
        return copy.deepcopy(payload["cleanup"])

    def collect_human_events():
        calls.append("human")
        return copy.deepcopy(payload["human_intervention"])

    return calls, {
        "observe_runtime": observe_runtime,
        "collect_pre_r5": collect_pre_r5,
        "authorize_repair": authorize_repair,
        "execute_repair": execute_repair,
        "collect_post_candidate": collect_post_candidate,
        "collect_post_r5": collect_post_r5,
        "collect_transport": collect_transport,
        "collect_integrity": collect_integrity,
        "collect_cleanup": collect_cleanup,
        "collect_human_events": collect_human_events,
    }


def test_provider_backed_driver_calls_existing_owner_seams_in_order() -> None:
    calls, callbacks = _callbacks()

    record = compose_m3_live_epoch(
        mode="LIVE_PROVIDER_BACKED",
        epoch_id="m3-line-live-001",
        main_sha=MAIN_SHA,
        implementation_sha=MAIN_SHA,
        plugin_binary_sha256_expected=PLUGIN_SHA,
        plugin_binary_sha256_observed=PLUGIN_SHA,
        started_at="2026-08-30T11:00:00Z",
        finished_at="2026-08-30T11:00:12Z",
        wall_clock_seconds=12.0,
        **callbacks,
    )

    assert record["status"] == "PASS"
    assert record["live_acceptance"] is True
    assert record["repair"]["attempts"] == 1
    assert calls == [
        "runtime",
        "pre_r5",
        "authorize",
        "repair",
        "post_candidate",
        "post_r5",
        "transport",
        "integrity",
        "cleanup",
        "human",
    ]


def test_contract_only_driver_does_not_invoke_live_callbacks() -> None:
    calls, callbacks = _callbacks()

    with pytest.raises(M3LiveEpochNotRun, match="contract-only"):
        compose_m3_live_epoch(
            mode="CONTRACT_ONLY",
            epoch_id="m3-line-contract-001",
            main_sha=MAIN_SHA,
            implementation_sha=MAIN_SHA,
            plugin_binary_sha256_expected=PLUGIN_SHA,
            plugin_binary_sha256_observed=PLUGIN_SHA,
            started_at="2026-08-30T11:00:00Z",
            finished_at="2026-08-30T11:00:12Z",
            wall_clock_seconds=12.0,
            **callbacks,
        )

    assert calls == []


def test_driver_rejects_pre_repair_pass_before_mutation() -> None:
    calls, callbacks = _callbacks()
    original = callbacks["collect_pre_r5"]

    def pre_pass(runtime):
        result = original(runtime)
        result["verdict"] = "PASS"
        return result

    callbacks["collect_pre_r5"] = pre_pass

    with pytest.raises(Exception, match="pre-repair|FAIL|canonical"):
        compose_m3_live_epoch(
            mode="LIVE_PROVIDER_BACKED",
            epoch_id="m3-line-live-002",
            main_sha=MAIN_SHA,
            implementation_sha=MAIN_SHA,
            plugin_binary_sha256_expected=PLUGIN_SHA,
            plugin_binary_sha256_observed=PLUGIN_SHA,
            started_at="2026-08-30T11:00:00Z",
            finished_at="2026-08-30T11:00:12Z",
            wall_clock_seconds=12.0,
            **callbacks,
        )

    assert calls == ["runtime", "pre_r5"]


def test_driver_rejects_rebound_authorization_before_mutation() -> None:
    calls, callbacks = _callbacks()
    original = callbacks["authorize_repair"]

    def rebound_authorization(pre_r5):
        result = original(pre_r5)
        result["candidate_revision_sha256"] = _sha("z")
        return result

    callbacks["authorize_repair"] = rebound_authorization

    with pytest.raises(Exception, match="authorization.*candidate|stale|foreign"):
        compose_m3_live_epoch(
            mode="LIVE_PROVIDER_BACKED",
            epoch_id="m3-line-live-003",
            main_sha=MAIN_SHA,
            implementation_sha=MAIN_SHA,
            plugin_binary_sha256_expected=PLUGIN_SHA,
            plugin_binary_sha256_observed=PLUGIN_SHA,
            started_at="2026-08-30T11:00:00Z",
            finished_at="2026-08-30T11:00:12Z",
            wall_clock_seconds=12.0,
            **callbacks,
        )

    assert calls == ["runtime", "pre_r5", "authorize"]
