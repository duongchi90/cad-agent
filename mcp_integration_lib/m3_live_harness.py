"""Opt-in M3 live evidence composition over existing owner callbacks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from cad_agent.approved_repair_adapter import validate_approved_repair_result
from cad_agent.m3_live_record import seal_m3_live_record
from cad_agent.visual_supervisor_adapter import validate_visual_verdict_result


class M3LiveEpochNotRun(ValueError):
    """Raised when the configured mode intentionally does not permit live work."""


class M3LiveEpochError(ValueError):
    """Raised when an owner callback cannot produce a live acceptance record."""


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise M3LiveEpochError(f"{name} must return a mapping")
    return dict(value)


def _validated_r5(value: object, *, expected_verdict: str, name: str) -> dict[str, Any]:
    item = _mapping(value, name=name)
    if item.get("provider_backed") is not True:
        raise M3LiveEpochError(f"{name} must be provider-backed")
    try:
        canonical = validate_visual_verdict_result(
            item["canonical_result"],
            expected_request_sha256=item["request_sha256"],
            expected_candidate_revision_sha256=item["candidate_revision_sha256"],
            expected_candidate_state_sha256=item["candidate_state_sha256"],
            expected_latest_mutation_sha256=item["latest_mutation_sha256"],
        )
    except Exception as exc:
        raise M3LiveEpochError(f"{name} canonical owner result is invalid") from exc
    if canonical["verdict"] != expected_verdict:
        raise M3LiveEpochError(f"{name} canonical verdict must be {expected_verdict}")
    if item.get("verdict") != canonical["verdict"]:
        raise M3LiveEpochError(f"{name} summary verdict is not canonical")
    for field in (
        "request_sha256",
        "observation_sha256",
        "verdict_sha256",
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "latest_mutation_sha256",
        "task6_thread_id",
        "task6_turn_id",
    ):
        if item.get(field) != canonical[field]:
            raise M3LiveEpochError(f"{name} summary is not bound to canonical owner result")
    return item


def _validated_r6(value: object, *, authorization: Mapping[str, object]) -> dict[str, Any]:
    item = _mapping(value, name="execute_repair")
    try:
        canonical = validate_approved_repair_result(
            item["canonical_result"],
            expected_candidate_revision_sha256=item["candidate_revision_sha256"],
            expected_r5_failure_id=item["r5_failure_id"],
            expected_r5_failure_sha256=item["r5_failure_sha256"],
            expected_repair_plan_id=item["repair_plan_id"],
            expected_repair_plan_sha256=item["repair_plan_sha256"],
            expected_repair_plan_version=item["repair_plan_version"],
            expected_repair_operation_contract_version=item[
                "repair_operation_contract_version"
            ],
            expected_repair_operation_contract_fingerprint=item[
                "operation_fingerprint_sha256"
            ],
        )
    except Exception as exc:
        raise M3LiveEpochError("execute_repair canonical owner result is invalid") from exc
    for field, canonical_field in (
        ("authorization_id", "authorization_id"),
        ("candidate_revision_sha256", "candidate_revision_sha256"),
        ("r5_failure_id", "r5_failure_id"),
        ("r5_failure_sha256", "r5_failure_sha256"),
        ("repair_plan_id", "repair_plan_id"),
        ("repair_plan_sha256", "repair_plan_sha256"),
        ("repair_plan_version", "repair_plan_version"),
        ("repair_operation_contract_version", "repair_operation_contract_version"),
        ("operation_fingerprint_sha256", "repair_operation_contract_fingerprint"),
        ("r6_result_sha256", "result_sha256"),
    ):
        if item.get(field) != canonical[canonical_field]:
            raise M3LiveEpochError("execute_repair summary is not bound to canonical owner result")
    if item.get("authorization_id") != authorization.get("authorization_id"):
        raise M3LiveEpochError("execute_repair authorization identity is not bound")
    if canonical["executor_capability"] != item.get("capability"):
        raise M3LiveEpochError("execute_repair capability is not canonical")
    return item


def compose_m3_live_epoch(
    *,
    mode: str,
    epoch_id: str,
    main_sha: str,
    implementation_sha: str,
    plugin_binary_sha256_expected: str,
    plugin_binary_sha256_observed: str,
    started_at: str,
    finished_at: str,
    wall_clock_seconds: float | int,
    observe_runtime: Callable[[], Mapping[str, object]],
    collect_pre_r5: Callable[[Mapping[str, object]], Mapping[str, object]],
    authorize_repair: Callable[[Mapping[str, object]], Mapping[str, object]],
    execute_repair: Callable[[Mapping[str, object]], Mapping[str, object]],
    collect_post_candidate: Callable[
        [Mapping[str, object], Mapping[str, object]], Mapping[str, object]
    ],
    collect_post_r5: Callable[[Mapping[str, object]], Mapping[str, object]],
    collect_transport: Callable[[], Mapping[str, object]],
    collect_integrity: Callable[[], Mapping[str, object]],
    collect_cleanup: Callable[[], Mapping[str, object]],
    collect_human_events: Callable[[], Mapping[str, object]],
) -> dict[str, object]:
    """Run one fixed-order provider-backed evidence composition.

    The callbacks are adapters to existing R4/R5/R6/R7/FileIPC/.NET/provider
    owners. This function owns only order and count; it never retries or
    performs AutoCAD, process, or provider operations itself.
    """

    if mode == "CONTRACT_ONLY":
        raise M3LiveEpochNotRun("R5_MODE=contract-only")
    if mode != "LIVE_PROVIDER_BACKED":
        raise M3LiveEpochError("mode must be LIVE_PROVIDER_BACKED")

    runtime = _mapping(observe_runtime(), name="observe_runtime")
    pre_r5 = _validated_r5(
        collect_pre_r5(runtime), expected_verdict="FAIL", name="collect_pre_r5"
    )

    authorization = _mapping(authorize_repair(pre_r5), name="authorize_repair")
    if authorization.get("authorization_consumed") is not True:
        raise M3LiveEpochError("authorization must be consumed before mutation")
    if authorization.get("candidate_revision_sha256") != pre_r5.get(
        "candidate_revision_sha256"
    ):
        raise M3LiveEpochError("authorization candidate binding is stale or foreign")
    if authorization.get("r5_failure_sha256") != pre_r5.get("verdict_sha256"):
        raise M3LiveEpochError("authorization R5 failure binding is stale or foreign")
    if authorization.get("operation_kind") != "REPAIR_DXF_PRIMITIVE":
        raise M3LiveEpochError("authorization operation kind is not bounded")
    if authorization.get("capability") != "LINE":
        raise M3LiveEpochError("authorization capability is not LINE")
    repair = _validated_r6(execute_repair(authorization), authorization=authorization)
    for key in (
        "authorization_sha256",
        "candidate_revision_sha256",
        "r5_failure_sha256",
        "repair_plan_sha256",
        "operation_fingerprint_sha256",
    ):
        if repair.get(key) != authorization.get(key):
            raise M3LiveEpochError(f"repair result is not bound to authorization.{key}")
    if repair.get("attempts") != 1:
        raise M3LiveEpochError("exactly one repair attempt is required")

    post_candidate = _mapping(
        collect_post_candidate(runtime, repair), name="collect_post_candidate"
    )
    post_r5 = _validated_r5(
        collect_post_r5(post_candidate), expected_verdict="PASS", name="collect_post_r5"
    )
    transport = _mapping(collect_transport(), name="collect_transport")
    integrity = _mapping(collect_integrity(), name="collect_integrity")
    cleanup = _mapping(collect_cleanup(), name="collect_cleanup")
    human_intervention = _mapping(
        collect_human_events(), name="collect_human_events"
    )

    payload = {
        "schema_version": "m3-live-repair-record-1.0",
        "epoch_id": epoch_id,
        "mode": mode,
        "status": "PASS",
        "live_acceptance": True,
        "main_sha": main_sha,
        "implementation_sha": implementation_sha,
        "plugin_binary_sha256_expected": plugin_binary_sha256_expected,
        "plugin_binary_sha256_observed": plugin_binary_sha256_observed,
        "started_at": started_at,
        "finished_at": finished_at,
        "wall_clock_seconds": wall_clock_seconds,
        "runtime": runtime,
        "candidate": post_candidate,
        "pre_r5": pre_r5,
        "repair": repair,
        "post_r5": post_r5,
        "transport": transport,
        "integrity": integrity,
        "cleanup": cleanup,
        "human_intervention": human_intervention,
    }
    return seal_m3_live_record(payload)


__all__ = ["M3LiveEpochError", "M3LiveEpochNotRun", "compose_m3_live_epoch"]
