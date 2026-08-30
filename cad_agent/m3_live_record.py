"""Fail-closed, stateless record contract for one M3 live repair epoch."""

from __future__ import annotations

import copy
import math
import re
from collections.abc import Mapping
from typing import Any

from cad_agent.drawing_contracts import canonical_json_sha256

M3_LIVE_RECORD_SCHEMA_VERSION = "m3-live-repair-record-1.0"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_TOP_LEVEL = {
    "schema_version",
    "epoch_id",
    "mode",
    "status",
    "live_acceptance",
    "main_sha",
    "implementation_sha",
    "plugin_binary_sha256_expected",
    "plugin_binary_sha256_observed",
    "started_at",
    "finished_at",
    "wall_clock_seconds",
    "runtime",
    "candidate",
    "pre_r5",
    "repair",
    "post_r5",
    "transport",
    "integrity",
    "cleanup",
    "human_intervention",
    "record_sha256",
}


class M3LiveRecordError(ValueError):
    """Raised when an M3 live record is incomplete, stale, or contradictory."""


def _fail(path: str, message: str) -> None:
    raise M3LiveRecordError(f"{path}: {message}")


def _object(value: object, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    return value


def _keys(value: Mapping[str, Any], *, path: str, required: set[str], optional: set[str] | None = None) -> None:
    allowed = required | (optional or set())
    missing = sorted(required - set(value))
    unexpected = sorted(set(value) - allowed)
    if missing:
        _fail(path, f"missing required properties: {', '.join(missing)}")
    if unexpected:
        _fail(path, f"unexpected properties: {', '.join(unexpected)}")


def _string(value: object, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(path, "must be a non-empty string")
    return value


def _identifier(value: object, *, path: str) -> str:
    text = _string(value, path=path)
    if _IDENTIFIER.fullmatch(text) is None:
        _fail(path, "has invalid identifier format")
    return text


def _sha(value: object, *, path: str) -> str:
    text = _string(value, path=path)
    if _SHA256.fullmatch(text) is None:
        _fail(path, "must be a lowercase SHA-256")
    return text


def _git_sha(value: object, *, path: str) -> str:
    text = _string(value, path=path)
    if _GIT_SHA.fullmatch(text) is None:
        _fail(path, "must be a lowercase Git commit SHA")
    return text


def _bool(value: object, *, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "must be boolean")
    return value


def _positive_int(value: object, *, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail(path, "must be a positive integer")
    return value


def _timestamp(value: object, *, path: str) -> str:
    text = _string(value, path=path)
    if _TIMESTAMP.fullmatch(text) is None:
        _fail(path, "must be an RFC3339 UTC timestamp")
    return text


def _duration(value: object, *, path: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(path, "must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        _fail(path, "must be finite")
    if value < 0:
        _fail(path, "must be non-negative")
    return value


def _validate_runtime(value: object) -> dict[str, Any]:
    item = _object(value, path="runtime")
    _keys(
        item,
        path="runtime",
        required={
            "observed",
            "autocad_product",
            "plugin_version",
            "pid",
            "hwnd",
            "runtime_identity",
            "active_document_sha256",
        },
    )
    if _bool(item["observed"], path="runtime.observed") is not True:
        _fail("runtime.observed", "must be true for a live record")
    _string(item["autocad_product"], path="runtime.autocad_product")
    _string(item["plugin_version"], path="runtime.plugin_version")
    pid = _positive_int(item["pid"], path="runtime.pid")
    hwnd = _positive_int(item["hwnd"], path="runtime.hwnd")
    runtime_identity = _identifier(item["runtime_identity"], path="runtime.runtime_identity")
    expected_identity = f"acad-pid-{pid}-hwnd-{hwnd}"
    if runtime_identity != expected_identity:
        _fail("runtime.runtime_identity", "must be derived from the observed PID/HWND")
    _sha(item["active_document_sha256"], path="runtime.active_document_sha256")
    return item


def _validate_candidate(value: object) -> dict[str, Any]:
    item = _object(value, path="candidate")
    _keys(
        item,
        path="candidate",
        required={
            "pre_revision_sha256",
            "pre_state_sha256",
            "pre_artifact_sha256",
            "post_revision_sha256",
            "post_state_sha256",
            "post_artifact_sha256",
            "distinct_post",
        },
    )
    for key in (
        "pre_revision_sha256",
        "pre_state_sha256",
        "pre_artifact_sha256",
        "post_revision_sha256",
        "post_state_sha256",
        "post_artifact_sha256",
    ):
        _sha(item[key], path=f"candidate.{key}")
    if _bool(item["distinct_post"], path="candidate.distinct_post") is not True:
        _fail("candidate.distinct_post", "must be true")
    if item["pre_revision_sha256"] == item["post_revision_sha256"]:
        _fail("candidate", "post revision must be distinct from pre revision")
    if item["pre_artifact_sha256"] == item["post_artifact_sha256"]:
        _fail("candidate", "post artifact must be distinct from pre artifact")
    return item


def _validate_r5(value: object, *, path: str, expected_verdict: str, expected_candidate: str, expected_state: str) -> dict[str, Any]:
    item = _object(value, path=path)
    _keys(
        item,
        path=path,
        required={
            "verdict",
            "provider_backed",
            "request_sha256",
            "observation_sha256",
            "verdict_sha256",
            "candidate_revision_sha256",
            "candidate_state_sha256",
            "latest_mutation_sha256",
            "task6_thread_id",
            "task6_turn_id",
        },
    )
    if item["verdict"] != expected_verdict:
        _fail(f"{path}.verdict", f"must be {expected_verdict}")
    if _bool(item["provider_backed"], path=f"{path}.provider_backed") is not True:
        _fail(f"{path}.provider_backed", "must be true; contract-only evidence is not live evidence")
    for key in (
        "request_sha256",
        "observation_sha256",
        "verdict_sha256",
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "latest_mutation_sha256",
    ):
        _sha(item[key], path=f"{path}.{key}")
    if item["candidate_revision_sha256"] != expected_candidate:
        _fail(path, "candidate revision binding is stale or foreign")
    if item["candidate_state_sha256"] != expected_state:
        _fail(path, "candidate state binding is stale or foreign")
    _identifier(item["task6_thread_id"], path=f"{path}.task6_thread_id")
    _identifier(item["task6_turn_id"], path=f"{path}.task6_turn_id")
    return item


def _validate_repair(value: object, *, pre_candidate: str, pre_r5: dict[str, Any]) -> dict[str, Any]:
    item = _object(value, path="repair")
    _keys(
        item,
        path="repair",
        required={
            "authorization_sha256",
            "authorization_consumed",
            "candidate_revision_sha256",
            "r5_failure_sha256",
            "repair_plan_sha256",
            "operation_kind",
            "capability",
            "operation_fingerprint_sha256",
            "r6_result_sha256",
            "outcome",
            "attempts",
        },
    )
    _sha(item["authorization_sha256"], path="repair.authorization_sha256")
    if _bool(item["authorization_consumed"], path="repair.authorization_consumed") is not True:
        _fail("repair.authorization_consumed", "must be true before mutation")
    _sha(item["candidate_revision_sha256"], path="repair.candidate_revision_sha256")
    if item["candidate_revision_sha256"] != pre_candidate:
        _fail("repair.candidate_revision_sha256", "authorization is bound to a stale or foreign candidate")
    _sha(item["r5_failure_sha256"], path="repair.r5_failure_sha256")
    if item["r5_failure_sha256"] != pre_r5["verdict_sha256"]:
        _fail("repair.r5_failure_sha256", "authorization is bound to a stale or foreign R5 failure")
    _sha(item["repair_plan_sha256"], path="repair.repair_plan_sha256")
    if item["operation_kind"] != "REPAIR_DXF_PRIMITIVE":
        _fail("repair.operation_kind", "must be REPAIR_DXF_PRIMITIVE")
    if item["capability"] != "LINE":
        _fail("repair.capability", "must be LINE for the first M3 epoch")
    _sha(item["operation_fingerprint_sha256"], path="repair.operation_fingerprint_sha256")
    _sha(item["r6_result_sha256"], path="repair.r6_result_sha256")
    if item["outcome"] != "SUCCESS":
        _fail("repair.outcome", "must be SUCCESS for live acceptance")
    if item["attempts"] != 1:
        _fail("repair.attempts", "must be exactly one")
    return item


def _validate_transport(value: object) -> dict[str, Any]:
    item = _object(value, path="transport")
    expected = {"fileipc", "dotnetipc", "task6_provider", "repair_executor"}
    if set(item) != expected:
        _fail("transport", "must contain exactly fileipc, dotnetipc, task6_provider, and repair_executor")
    for name, report in item.items():
        entry = _object(report, path=f"transport.{name}")
        _keys(entry, path=f"transport.{name}", required={"attempts", "successes", "failures"})
        attempts = _positive_int(entry["attempts"], path=f"transport.{name}.attempts")
        successes = entry["successes"]
        failures = entry["failures"]
        if isinstance(successes, bool) or not isinstance(successes, int) or successes < 0:
            _fail(f"transport.{name}.successes", "must be a non-negative integer")
        if isinstance(failures, bool) or not isinstance(failures, int) or failures < 0:
            _fail(f"transport.{name}.failures", "must be a non-negative integer")
        if successes + failures != attempts:
            _fail(f"transport.{name}", "successes plus failures must equal attempts")
    return item


def _validate_integrity(value: object) -> dict[str, Any]:
    item = _object(value, path="integrity")
    fields = (
        "source_before_sha256",
        "source_after_sha256",
        "staged_before_sha256",
        "staged_after_sha256",
        "accepted_before_sha256",
        "accepted_after_sha256",
    )
    _keys(item, path="integrity", required=set(fields))
    for field in fields:
        _sha(item[field], path=f"integrity.{field}")
    for before, after in (
        ("source_before_sha256", "source_after_sha256"),
        ("staged_before_sha256", "staged_after_sha256"),
        ("accepted_before_sha256", "accepted_after_sha256"),
    ):
        if item[before] != item[after]:
            _fail("integrity", f"{before} and {after} must match")
    return item


def _validate_cleanup(value: object) -> dict[str, Any]:
    item = _object(value, path="cleanup")
    _keys(
        item,
        path="cleanup",
        required={"closed_without_save", "zero_survivors", "release_verified", "ambiguous"},
    )
    for field in ("closed_without_save", "zero_survivors", "release_verified"):
        if _bool(item[field], path=f"cleanup.{field}") is not True:
            _fail(f"cleanup.{field}", "must be true for live acceptance")
    if _bool(item["ambiguous"], path="cleanup.ambiguous") is not False:
        _fail("cleanup.ambiguous", "must be false")
    return item


def _validate_human(value: object) -> dict[str, Any]:
    item = _object(value, path="human_intervention")
    _keys(item, path="human_intervention", required={"captured", "events"})
    if _bool(item["captured"], path="human_intervention.captured") is not True:
        _fail("human_intervention.captured", "must be true")
    events = item["events"]
    if not isinstance(events, list) or not events:
        _fail("human_intervention.events", "must record the bounded load action")
    for index, event in enumerate(events):
        entry = _object(event, path=f"human_intervention.events[{index}]")
        _keys(entry, path=f"human_intervention.events[{index}]", required={"kind", "count"})
        _identifier(entry["kind"], path=f"human_intervention.events[{index}].kind")
        if isinstance(entry["count"], bool) or not isinstance(entry["count"], int) or entry["count"] <= 0:
            _fail(f"human_intervention.events[{index}].count", "must be positive")
    return item


def validate_m3_live_record(
    record: Mapping[str, object],
    *,
    expected_main_sha: str | None = None,
    expected_plugin_sha256: str | None = None,
) -> dict[str, object]:
    """Validate one complete provider-backed M3 PASS record."""

    if not isinstance(record, Mapping):
        _fail("$", "record must be a mapping")
    item = copy.deepcopy(dict(record))
    _keys(item, path="$", required=_TOP_LEVEL - {"record_sha256"}, optional={"record_sha256"})
    if item["schema_version"] != M3_LIVE_RECORD_SCHEMA_VERSION:
        _fail("schema_version", "does not match the M3 live record schema")
    _identifier(item["epoch_id"], path="epoch_id")
    if item["mode"] != "LIVE_PROVIDER_BACKED":
        _fail("mode", "CONTRACT_ONLY cannot be represented as live acceptance")
    if item["status"] != "PASS" or item["live_acceptance"] is not True:
        _fail("status", "only provider-backed PASS records can be sealed as live acceptance")
    if not isinstance(item["live_acceptance"], bool):
        _fail("live_acceptance", "must be boolean")
    main_sha = _git_sha(item["main_sha"], path="main_sha")
    implementation_sha = _git_sha(item["implementation_sha"], path="implementation_sha")
    if implementation_sha != main_sha:
        _fail("implementation_sha", "must equal the current main implementation identity")
    if expected_main_sha is not None:
        expected = _git_sha(expected_main_sha, path="expected_main_sha")
        if main_sha != expected or implementation_sha != expected:
            _fail("main_sha", "record is stale against the expected current implementation")
    expected_plugin = _sha(item["plugin_binary_sha256_expected"], path="plugin_binary_sha256_expected")
    observed_plugin = _sha(item["plugin_binary_sha256_observed"], path="plugin_binary_sha256_observed")
    if expected_plugin != observed_plugin:
        _fail("plugin_binary_sha256_observed", "loaded plugin identity does not match expected artifact")
    if expected_plugin_sha256 is not None and expected_plugin != _sha(expected_plugin_sha256, path="expected_plugin_sha256"):
        _fail("plugin_binary_sha256_expected", "does not match the expected current build artifact")
    _timestamp(item["started_at"], path="started_at")
    _timestamp(item["finished_at"], path="finished_at")
    _duration(item["wall_clock_seconds"], path="wall_clock_seconds")
    runtime = _validate_runtime(item["runtime"])
    candidate = _validate_candidate(item["candidate"])
    pre_r5 = _validate_r5(
        item["pre_r5"],
        path="pre_r5",
        expected_verdict="FAIL",
        expected_candidate=candidate["pre_revision_sha256"],
        expected_state=candidate["pre_state_sha256"],
    )
    post_r5 = _validate_r5(
        item["post_r5"],
        path="post_r5",
        expected_verdict="PASS",
        expected_candidate=candidate["post_revision_sha256"],
        expected_state=candidate["post_state_sha256"],
    )
    if pre_r5["task6_turn_id"] == post_r5["task6_turn_id"]:
        _fail("post_r5", "must use a fresh Task6 turn")
    _validate_repair(item["repair"], pre_candidate=candidate["pre_revision_sha256"], pre_r5=pre_r5)
    _validate_transport(item["transport"])
    _validate_integrity(item["integrity"])
    _validate_cleanup(item["cleanup"])
    _validate_human(item["human_intervention"])
    if item["runtime"]["active_document_sha256"] != candidate["post_artifact_sha256"]:
        _fail("runtime.active_document_sha256", "must identify the accepted disposable post-repair document")
    if "record_sha256" in item:
        supplied = _sha(item["record_sha256"], path="record_sha256")
        payload = {key: value for key, value in item.items() if key != "record_sha256"}
        if supplied != canonical_json_sha256(payload):
            _fail("record_sha256", "does not match canonical record payload")
    return item


def seal_m3_live_record(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate and seal a provider-backed live record with its canonical hash."""

    candidate = copy.deepcopy(dict(payload))
    candidate.pop("record_sha256", None)
    validated = validate_m3_live_record(candidate)
    sealed = {**validated, "record_sha256": canonical_json_sha256(validated)}
    return validate_m3_live_record(sealed)


__all__ = [
    "M3_LIVE_RECORD_SCHEMA_VERSION",
    "M3LiveRecordError",
    "seal_m3_live_record",
    "validate_m3_live_record",
]
