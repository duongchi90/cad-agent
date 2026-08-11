"""Pure composition boundary for post-provider visual-verdict finalization.

This module intentionally owns no scope, currentness, worker, revision, or
evidence authority.  It accepts immutable records from the existing owners,
revalidates them after the provider returns, and only aggregates untrusted
region statuses.  Missing owner seams are categorical refusals.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence

from agent_lib.codex_worker import CodexWorkerResult, consume_task6_result
from agent_lib.codex_worker_process import WorkerCleanupResult
from cad_agent.candidate_revision import validate_candidate_revision_state
from cad_agent.drawing_artifact_reference import (
    require_current_drawing_artifact_reference,
)
from cad_agent.visual_contracts import validate_visual_contract
from cad_agent.visual_evidence import validate_visual_evidence_freshness


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CRITICALITIES = frozenset({"CRITICAL", "NORMAL"})
_REGION_STATUSES = frozenset({"PASS", "FAIL", "SKIP", "NOT_RUN"})


class VisualSupervisorAdapterError(ValueError):
    """Categorical, fail-closed refusal for malformed or stale evidence."""


def _fail(message: str) -> None:
    raise VisualSupervisorAdapterError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object mapping")
    if any(not isinstance(key, str) for key in value):
        _fail(f"{label} properties must use string keys")
    return value


def _identifier(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        _fail(f"{label} is invalid")
    return value


def _sha(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _closed(
    value: Mapping[str, object],
    required: set[str],
    *,
    label: str,
    optional: set[str] | frozenset[str] = frozenset(),
) -> None:
    keys = set(value)
    missing = required - keys
    if missing:
        _fail(f"{label} is missing required field(s): {', '.join(sorted(missing))}")
    unknown = keys - required - set(optional)
    if unknown:
        _fail(f"{label} contains unknown field(s): {', '.join(sorted(unknown))}")


def _task6_result(value: object, *, label: str) -> CodexWorkerResult:
    """Validate the accepted Task6 public result, never a caller-made mapping."""

    if not isinstance(value, CodexWorkerResult):
        _fail("R5_B3_TASK6_PUBLIC_SEAM_MISSING: task6_result must be CodexWorkerResult")
    if value.operation not in {"turn", "steer"}:
        _fail(f"{label} operation is not a visual provider turn")
    if value.status != "COMPLETED" or value.success is not True:
        _fail(f"{label} terminal result is timeout/cancel/late or failed")
    if value.failure_code is not None:
        _fail(f"{label} carries a worker failure code")
    if value.candidate_trusted is not False or value.promotion_safe is not False:
        _fail(f"{label} exposes trusted/promotion-safe candidate output")
    _identifier(value.thread_id, label=f"{label}.thread_id")
    if value.turn_id is None:
        _fail(
            "R5_B3_TASK6_PUBLIC_SEAM_MISSING: completed Task6 result has no turn identity"
        )
    _identifier(value.turn_id, label=f"{label}.turn_id")
    if not isinstance(value.events, tuple) or not value.events:
        _fail(f"{label}.events must contain terminal worker events")
    if value.cleanup_result is not None and not isinstance(
        value.cleanup_result, WorkerCleanupResult
    ):
        _fail(f"{label}.cleanup_result is not accepted worker cleanup evidence")
    return value


def _cleanup_result(value: object, *, label: str) -> WorkerCleanupResult:
    if not isinstance(value, WorkerCleanupResult):
        _fail(
            "R5_B3_TASK6_PUBLIC_SEAM_MISSING: cleanup_result must be "
            "accepted WorkerCleanupResult"
        )
    if not (
        value.status == "CLEANUP_SUCCEEDED"
        and value.success is True
        and value.promotion_safe is True
        and value.survivor_pids == ()
        and value.survivor_count == 0
        and value.error_code is None
    ):
        _fail(f"{label} is not verified cleanup evidence")
    return value


_OWNER_STATE_FIELDS = {
    "visual_review_scope",
    "candidate_revision_state",
    "drawing_reference",
    "drawing_observation",
    "drawing_artifact_bytes",
    "visual_evidence",
    "visual_run_manifest",
    "manifest_bytes_sha256",
    "drawing_sha256_before_dispatch",
    "task6_result",
    "cleanup_result",
}


def _owner_state(value: object, *, label: str) -> Mapping[str, object]:
    state = _mapping(value, label=label)
    if "task6_result" not in state:
        _fail(
            "R5_B3_TASK6_PUBLIC_SEAM_MISSING: owner state has no accepted task6_result"
        )
    _closed(state, _OWNER_STATE_FIELDS, label=label, optional={"pre_repair_r5_verdict"})
    _sha(state["manifest_bytes_sha256"], label=f"{label}.manifest_bytes_sha256")
    _sha(
        state["drawing_sha256_before_dispatch"],
        label=f"{label}.drawing_sha256_before_dispatch",
    )
    if not isinstance(state["drawing_artifact_bytes"], bytes):
        _fail(f"{label}.drawing_artifact_bytes must be bytes from the DARA owner")
    _task6_result(state["task6_result"], label=f"{label}.task6_result")
    _cleanup_result(state["cleanup_result"], label=f"{label}.cleanup_result")
    return state


def _provider(
    value: object,
) -> tuple[CodexWorkerResult, str, str, list[dict[str, object]]]:
    provider = _mapping(value, label="provider_result")
    required = {"task6_result", "provider_verdict", "candidate_revision_sha256", "regions"}
    _closed(provider, required, label="provider_result")
    task6 = _task6_result(provider["task6_result"], label="provider_result.task6_result")
    candidate_sha = _sha(
        provider["candidate_revision_sha256"],
        label="provider_result.candidate_revision_sha256",
    )
    verdict = provider["provider_verdict"]
    if not isinstance(verdict, str) or verdict not in {"PASS", "FAIL", "NEEDS_HUMAN"}:
        _fail("provider verdict is unknown")
    raw_regions = provider["regions"]
    if not isinstance(raw_regions, Sequence) or isinstance(raw_regions, (str, bytes, bytearray)):
        _fail("provider regions must be a list")
    normalized: list[dict[str, object]] = []
    for index, region in enumerate(raw_regions):
        item = _mapping(region, label=f"provider_result.regions[{index}]")
        required_region = {
            "region_id",
            "view_id",
            "sheet_id",
            "layout_id",
            "criticality",
            "status",
        }
        _closed(item, required_region, label=f"provider_result.regions[{index}]")
        record: dict[str, object] = {}
        for field in ("region_id", "view_id", "sheet_id", "layout_id"):
            record[field] = _identifier(
                item[field], label=f"provider_result.regions[{index}].{field}"
            )
        criticality = item["criticality"]
        if not isinstance(criticality, str) or criticality not in _CRITICALITIES:
            _fail(f"provider_result.regions[{index}].criticality is invalid")
        record["criticality"] = criticality
        status = item["status"]
        if not isinstance(status, str) or status not in _REGION_STATUSES:
            _fail(f"provider_result.regions[{index}].status is unknown")
        record["status"] = status
        normalized.append(record)
    if not normalized:
        _fail("provider regions must not be empty")
    normalized.sort(key=lambda item: str(item["region_id"]))
    return task6, candidate_sha, verdict, normalized


def _scope_payload_from_regions(
    regions: Sequence[Mapping[str, object]], template: Mapping[str, object]
) -> dict[str, object]:
    if not regions:
        _fail("provider regions must not be empty")
    return {
        "schema_version": template["schema_version"],
        "scope_id": template["scope_id"],
        "run_id": template["run_id"],
        "registry_snapshot_sha256": template["registry_snapshot_sha256"],
        "candidate_revision_sha256": template["candidate_revision_sha256"],
        "candidate_state_sha256": template["candidate_state_sha256"],
        "regions": [
            {
                key: region[key]
                for key in ("region_id", "view_id", "sheet_id", "layout_id", "criticality")
            }
            for region in regions
        ],
    }


def _validate_owner_state(
    state: Mapping[str, object], *, label: str, server_scope: Mapping[str, object]
) -> dict[str, object]:
    try:
        scope = validate_visual_contract(
            state["visual_review_scope"],
            contract="visual_review_scope",
            server_scope=server_scope,
        )
        candidate = validate_candidate_revision_state(state["candidate_revision_state"])
        require_current_drawing_artifact_reference(
            reference=state["drawing_reference"],
            observation=state["drawing_observation"],
            artifact_bytes=state["drawing_artifact_bytes"],
        )
        evidence = validate_visual_evidence_freshness(
            state["visual_evidence"],
            state["manifest_bytes_sha256"],
            state["visual_run_manifest"],
            state["drawing_sha256_before_dispatch"],
        )
    except Exception as exc:
        _fail(f"{label} accepted owner validation failed: {exc}")
    return {"scope": scope, "candidate": candidate, "evidence": evidence}


def _assert_r5_not_stale(
    authoritative: Mapping[str, object],
    authoritative_manifest: Mapping[str, object],
) -> None:
    previous = authoritative.get("pre_repair_r5_verdict")
    if previous is None:
        return
    previous_map = _mapping(previous, label="authoritative_state.pre_repair_r5_verdict")
    previous_mutation = _sha(
        previous_map.get("latest_mutation_sha256"),
        label="pre_repair_r5_verdict.latest_mutation_sha256",
    )
    current_mutation = _sha(
        authoritative_manifest.get("latest_mutation_sha256"),
        label="authoritative_state.visual_run_manifest.latest_mutation_sha256",
    )
    if previous_map.get("verdict") == "PASS" and previous_mutation != current_mutation:
        _fail("pre-repair R5 verdict is stale after R6 mutation/review")


def finalize_visual_verdict(
    *,
    provider_result: Mapping[str, object],
    authoritative_state: Mapping[str, object],
    post_provider_state: Mapping[str, object],
    server_scope: Mapping[str, object],
) -> dict[str, object]:
    """Revalidate owner records and aggregate only untrusted provider statuses."""

    external_scope = _mapping(server_scope, label="server_scope")
    authoritative = _owner_state(authoritative_state, label="authoritative_state")
    post_provider = _owner_state(post_provider_state, label="post_provider_state")
    task6, provider_candidate_sha, _provider_verdict, regions = _provider(provider_result)
    owner_task6 = _task6_result(
        authoritative["task6_result"], label="authoritative_state.task6_result"
    )
    if task6 is not owner_task6 or post_provider["task6_result"] is not owner_task6:
        _fail("Task6 result identity changed or was replayed after provider return")

    auth_validated = _validate_owner_state(
        authoritative, label="authoritative_state", server_scope=external_scope
    )
    post_validated = _validate_owner_state(
        post_provider, label="post_provider_state", server_scope=external_scope
    )
    try:
        auth_scope = validate_visual_contract(
            authoritative["visual_review_scope"],
            contract="visual_review_scope",
            server_scope=external_scope,
        )
        post_scope = validate_visual_contract(
            post_provider["visual_review_scope"],
            contract="visual_review_scope",
            server_scope=external_scope,
        )
        provider_scope = validate_visual_contract(
            _scope_payload_from_regions(regions, external_scope),
            contract="visual_review_scope",
            server_scope=external_scope,
        )
    except Exception as exc:
        _fail(f"server-owned visual scope validation failed: {exc}")
    if auth_scope != post_scope or provider_scope != auth_scope:
        _fail("provider regions do not match the server-owned scope")

    auth_candidate = auth_validated["candidate"]
    post_candidate = post_validated["candidate"]
    if auth_candidate != post_candidate:
        _fail("candidate revision/current selection changed after provider return")
    for field, message in (
        ("drawing_reference", "DARA reference changed after provider return"),
        ("drawing_observation", "DARA observation changed after provider return"),
        ("drawing_artifact_bytes", "DARA bytes changed after provider return"),
        ("visual_run_manifest", "visual evidence manifest changed after provider return"),
        ("manifest_bytes_sha256", "visual evidence manifest bytes changed after provider return"),
        (
            "drawing_sha256_before_dispatch",
            "DARA drawing pre-dispatch identity changed after provider return",
        ),
    ):
        if authoritative[field] != post_provider[field]:
            _fail(message)
    selected = auth_candidate.get("current_candidate_revision_sha256")
    if selected is None or provider_candidate_sha != selected:
        _fail("provider candidate revision does not match current candidate")

    if auth_scope["candidate_revision_sha256"] != selected:
        _fail("visual review scope is not bound to the current R4 candidate")
    if auth_scope["candidate_state_sha256"] != auth_candidate["state_sha256"]:
        _fail("visual review scope is not bound to the current R4 state")
    if post_scope["candidate_revision_sha256"] != post_candidate.get(
        "current_candidate_revision_sha256"
    ):
        _fail("post-provider visual scope is stale against R4 current candidate")
    if post_scope["candidate_state_sha256"] != post_candidate["state_sha256"]:
        _fail("post-provider visual scope is stale against R4 state")

    auth_evidence = auth_validated["evidence"]
    post_evidence = post_validated["evidence"]
    if auth_evidence != post_evidence:
        _fail("visual evidence freshness changed after provider return")
    _assert_r5_not_stale(authoritative, authoritative["visual_run_manifest"])  # type: ignore[arg-type]

    try:
        consume_task6_result(
            owner_task6,
            run_id=auth_scope["run_id"],
            operation=owner_task6.operation,
            thread_id=owner_task6.thread_id,
            turn_id=owner_task6.turn_id,
        )
    except Exception:
        _fail("Task6 accepted result could not be consumed")

    statuses = [str(region["status"]) for region in regions]
    if "FAIL" in statuses:
        verdict = "FAIL"
    elif any(status in {"SKIP", "NOT_RUN"} for status in statuses):
        verdict = "NEEDS_HUMAN"
    else:
        verdict = "PASS"
    return {
        "verdict": verdict,
        "task6_thread_id": owner_task6.thread_id,
        "task6_turn_id": owner_task6.turn_id,
        "candidate_revision_sha256": selected,
        "regions": copy.deepcopy(regions),
    }


__all__ = ["VisualSupervisorAdapterError", "finalize_visual_verdict"]
