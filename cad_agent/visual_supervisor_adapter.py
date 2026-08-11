"""Pure post-provider visual-verdict finalization adapter.

The adapter is deliberately a small composition seam.  It does not call a
provider, start a worker, persist a verdict, or mutate a candidate.  The
caller supplies evidence from the existing server-owned authorities and this
module only checks that the tuple is still current before aggregating the
provider's untrusted region observations.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CRITICALITIES = frozenset({"CRITICAL", "NORMAL"})
_REGION_STATUSES = frozenset({"PASS", "FAIL", "SKIP", "NOT_RUN"})


class VisualSupervisorAdapterError(ValueError):
    """Categorical, fail-closed refusal for stale or malformed evidence."""


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


def _scope(scope: object, *, label: str) -> dict[str, object]:
    raw = _mapping(scope, label=label)
    required = {
        "schema_version",
        "scope_id",
        "run_id",
        "registry_snapshot_sha256",
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "regions",
    }
    _closed(raw, required, label=label)
    if raw["schema_version"] != "visual-review-scope-1.0":
        _fail(f"{label} schema_version is invalid")
    normalized: dict[str, object] = {
        "schema_version": raw["schema_version"],
        "scope_id": _identifier(raw["scope_id"], label=f"{label}.scope_id"),
        "run_id": _identifier(raw["run_id"], label=f"{label}.run_id"),
        "registry_snapshot_sha256": _sha(
            raw["registry_snapshot_sha256"], label=f"{label}.registry_snapshot_sha256"
        ),
        "candidate_revision_sha256": _sha(
            raw["candidate_revision_sha256"], label=f"{label}.candidate_revision_sha256"
        ),
        "candidate_state_sha256": _sha(
            raw["candidate_state_sha256"], label=f"{label}.candidate_state_sha256"
        ),
    }
    regions = raw["regions"]
    if not isinstance(regions, Sequence) or isinstance(regions, (str, bytes, bytearray)):
        _fail(f"{label}.regions must be a non-empty list")
    normalized_regions: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, region in enumerate(regions):
        item = _mapping(region, label=f"{label}.regions[{index}]")
        region_required = {"region_id", "view_id", "sheet_id", "layout_id", "criticality"}
        _closed(item, region_required, label=f"{label}.regions[{index}]")
        region_id = _identifier(
            item["region_id"], label=f"{label}.regions[{index}].region_id"
        )
        if region_id in seen:
            _fail(f"{label} contains duplicate region_id {region_id}")
        seen.add(region_id)
        normalized_region: dict[str, object] = {"region_id": region_id}
        for field in ("view_id", "sheet_id", "layout_id"):
            normalized_region[field] = _identifier(
                item[field], label=f"{label}.regions[{index}].{field}"
            )
        criticality = item["criticality"]
        if not isinstance(criticality, str) or criticality not in _CRITICALITIES:
            _fail(f"{label}.regions[{index}].criticality is invalid")
        normalized_region["criticality"] = criticality
        normalized_regions.append(normalized_region)
    if not normalized_regions:
        _fail(f"{label}.regions must not be empty")
    normalized["regions"] = sorted(normalized_regions, key=lambda item: str(item["region_id"]))
    return normalized


def _state(value: object, *, label: str, full: bool = True) -> Mapping[str, object]:
    state = _mapping(value, label=label)
    required = {
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "dara_reference_sha256",
        "drawing_sha256",
        "registry_snapshot_sha256",
        "visual_run_manifest_sha256",
        "latest_mutation_sha256",
        "server_scope",
    }
    if full:
        required.update(
            {
                "run_id",
                "current_candidate_revision_sha256",
                "task6_attempt_id",
                "task6_terminal_status",
                "consumed_attempt_ids",
            }
        )
    _closed(
        state,
        required,
        label=label,
        optional={
            "current_candidate_revision_sha256",
            "task6_attempt_id",
            "task6_terminal_status",
            "consumed_attempt_ids",
            "pre_repair_r5_verdict",
            "r6_mutation_sha256",
            "r6_review_verdict",
        },
    )
    if "run_id" in state:
        _identifier(state["run_id"], label=f"{label}.run_id")
    for field in (
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "dara_reference_sha256",
        "drawing_sha256",
        "registry_snapshot_sha256",
        "visual_run_manifest_sha256",
        "latest_mutation_sha256",
    ):
        _sha(state[field], label=f"{label}.{field}")
    if "current_candidate_revision_sha256" in state:
        _sha(
            state["current_candidate_revision_sha256"],
            label=f"{label}.current_candidate_revision_sha256",
        )
    if full and state["current_candidate_revision_sha256"] != state["candidate_revision_sha256"]:
        _fail(f"{label} current candidate selection is stale")
    if "task6_attempt_id" in state:
        _identifier(state["task6_attempt_id"], label=f"{label}.task6_attempt_id")
    if "task6_terminal_status" in state and state["task6_terminal_status"] != "COMPLETED":
        _fail(f"{label} Task6 terminal status is not completed")
    _scope(state["server_scope"], label=f"{label}.server_scope")
    if "consumed_attempt_ids" in state:
        consumed = state["consumed_attempt_ids"]
        if not isinstance(consumed, Sequence) or isinstance(consumed, (str, bytes, bytearray)):
            _fail(f"{label}.consumed_attempt_ids must be a list")
        for index, attempt_id in enumerate(consumed):
            _identifier(attempt_id, label=f"{label}.consumed_attempt_ids[{index}]")
    return state


def _provider(value: object) -> tuple[Mapping[str, object], list[dict[str, object]]]:
    provider = _mapping(value, label="provider_result")
    required = {
        "attempt_id",
        "terminal_status",
        "candidate_revision_sha256",
        "provider_verdict",
        "regions",
    }
    _closed(provider, required, label="provider_result")
    attempt_id = _identifier(provider["attempt_id"], label="provider_result.attempt_id")
    if provider["terminal_status"] != "COMPLETED":
        _fail("Task6 terminal status is timeout/cancel/late or otherwise non-success")
    _sha(provider["candidate_revision_sha256"], label="provider_result.candidate_revision_sha256")
    if not isinstance(provider["provider_verdict"], str) or provider["provider_verdict"] not in {
        "PASS",
        "FAIL",
        "NEEDS_HUMAN",
    }:
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
            "evidence_sha256",
        }
        _closed(item, required_region, label=f"provider_result.regions[{index}]")
        record: dict[str, object] = {}
        for field in ("region_id", "view_id", "sheet_id", "layout_id"):
            record[field] = _identifier(
                item[field], label=f"provider_result.regions[{index}].{field}"
            )
        if not isinstance(item["criticality"], str) or item["criticality"] not in _CRITICALITIES:
            _fail(f"provider_result.regions[{index}].criticality is invalid")
        record["criticality"] = item["criticality"]
        if not isinstance(item["status"], str) or item["status"] not in _REGION_STATUSES:
            _fail(f"provider_result.regions[{index}].status is unknown")
        record["status"] = item["status"]
        record["evidence_sha256"] = _sha(
            item["evidence_sha256"],
            label=f"provider_result.regions[{index}].evidence_sha256",
        )
        normalized.append(record)
    if not normalized:
        _fail("provider regions must not be empty")
    return provider, sorted(normalized, key=lambda item: str(item["region_id"]))


def _assert_scope_matches(
    provider_regions: list[dict[str, object]], authoritative_scope: dict[str, object]
) -> None:
    expected = {
        (
            item["region_id"],
            item["view_id"],
            item["sheet_id"],
            item["layout_id"],
            item["criticality"],
        )
        for item in authoritative_scope["regions"]  # type: ignore[union-attr]
    }
    actual = {
        (
            item["region_id"],
            item["view_id"],
            item["sheet_id"],
            item["layout_id"],
            item["criticality"],
        )
        for item in provider_regions
    }
    if len(actual) != len(provider_regions) or actual != expected:
        _fail("provider regions do not match the server-owned scope")


def _assert_scope_binding(state: Mapping[str, object], *, label: str) -> None:
    scope = _scope(state["server_scope"], label=f"{label}.server_scope")
    bindings = (
        ("run_id", "run_id"),
        ("registry_snapshot_sha256", "registry_snapshot_sha256"),
        ("candidate_revision_sha256", "candidate_revision_sha256"),
        ("candidate_state_sha256", "candidate_state_sha256"),
    )
    for scope_field, state_field in bindings:
        if state_field not in state:
            continue
        if scope[scope_field] != state[state_field]:
            _fail(f"{label} server-owned scope binding is stale or foreign")


def _assert_fresh_tuple(
    authoritative: Mapping[str, object], post_provider: Mapping[str, object]
) -> None:
    comparisons = (
        ("candidate_revision_sha256", "candidate revision/current selection is stale"),
        ("candidate_state_sha256", "candidate state is stale after provider return"),
        ("dara_reference_sha256", "DARA current drawing reference is stale"),
        ("drawing_sha256", "DARA drawing currentness changed after provider return"),
        ("registry_snapshot_sha256", "R3 registry currentness is stale"),
        ("visual_run_manifest_sha256", "visual evidence freshness is stale"),
        ("latest_mutation_sha256", "visual evidence freshness is stale against latest mutation"),
    )
    for field, message in comparisons:
        if authoritative[field] != post_provider[field]:
            _fail(message)
    if _scope(authoritative["server_scope"], label="authoritative_state.server_scope") != _scope(
        post_provider["server_scope"], label="post_provider_state.server_scope"
    ):
        _fail("server-owned scope changed after provider return")


def _assert_r5_not_stale(authoritative: Mapping[str, object]) -> None:
    previous = authoritative.get("pre_repair_r5_verdict")
    mutation = authoritative.get("r6_mutation_sha256")
    if previous is None or mutation is None:
        return
    previous_map = _mapping(previous, label="authoritative_state.pre_repair_r5_verdict")
    previous_mutation = previous_map.get("latest_mutation_sha256")
    if previous_map.get("verdict") == "PASS" and mutation != previous_mutation:
        _fail("pre-repair R5 verdict is stale after R6 mutation/review")


def finalize_visual_verdict(
    *,
    provider_result: Mapping[str, object],
    authoritative_state: Mapping[str, object],
    post_provider_state: Mapping[str, object],
) -> dict[str, object]:
    """Revalidate the authoritative tuple and deterministically aggregate regions."""

    provider, regions = _provider(provider_result)
    authoritative = _state(authoritative_state, label="authoritative_state")
    post_provider = _state(post_provider_state, label="post_provider_state", full=False)
    _assert_scope_binding(authoritative, label="authoritative_state")
    _assert_scope_binding(post_provider, label="post_provider_state")
    _assert_fresh_tuple(authoritative, post_provider)
    _assert_r5_not_stale(authoritative)

    if provider["attempt_id"] != authoritative["task6_attempt_id"]:
        _fail("Task6 attempt identity does not match authoritative attempt")
    if provider["attempt_id"] in authoritative["consumed_attempt_ids"]:
        _fail("replayed or duplicate provider attempt has already been consumed")
    if provider["candidate_revision_sha256"] != authoritative["candidate_revision_sha256"]:
        _fail("provider candidate revision does not match current candidate")

    scope = _scope(authoritative["server_scope"], label="authoritative_state.server_scope")
    _assert_scope_matches(regions, scope)

    statuses = [str(region["status"]) for region in regions]
    if "FAIL" in statuses:
        verdict = "FAIL"
    elif any(status in {"SKIP", "NOT_RUN"} for status in statuses):
        verdict = "NEEDS_HUMAN"
    else:
        verdict = "PASS"
    return {
        "verdict": verdict,
        "attempt_id": provider["attempt_id"],
        "candidate_revision_sha256": provider["candidate_revision_sha256"],
        "regions": copy.deepcopy(regions),
    }


__all__ = ["VisualSupervisorAdapterError", "finalize_visual_verdict"]
