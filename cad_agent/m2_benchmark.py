"""Closed M2 Mechanical benchmark record oracle."""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

M2_BENCHMARK_SCHEMA_VERSION = "m2-mechanical-benchmark-record-1.0"

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_STATUS = {"PASS", "FAIL", "SKIP", "NOT_RUN", "NOT_CAPTURED"}
_AGG_STATUS = {"NOT_RUN", "BASELINE_ONLY", "NOT_REPRESENTATIVE", "REPRESENTATIVE"}


class M2BenchmarkError(ValueError):
    """Raised when an M2 benchmark record cannot be trusted."""


def _fail(message: str) -> None:
    raise M2BenchmarkError(message)


def _object(value: object, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{path} must be an object")
    return value


def _keys(value: Mapping[str, Any], *, path: str, required: set[str], optional: set[str] | None = None) -> None:
    allowed = required | (optional or set())
    missing = sorted(required - set(value))
    unexpected = sorted(set(value) - allowed)
    if missing:
        _fail(f"{path} missing required properties: {', '.join(missing)}")
    if unexpected:
        _fail(f"{path} unexpected properties: {', '.join(unexpected)}")


def _string(value: object, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{path} must be a non-empty string")
    return value


def _identifier(value: object, *, path: str) -> str:
    text = _string(value, path=path)
    if not _IDENTIFIER.fullmatch(text):
        _fail(f"{path} has invalid identifier format")
    return text


def _sha256(value: object, *, path: str) -> str:
    text = _string(value, path=path)
    if not _SHA256.fullmatch(text):
        _fail(f"{path} must be a lowercase SHA-256")
    return text


def _timestamp(value: object, *, path: str) -> str:
    text = _string(value, path=path)
    if not _TIMESTAMP.fullmatch(text):
        _fail(f"{path} must be an RFC3339 UTC timestamp")
    return text


def _bool(value: object, *, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{path} must be boolean")
    return value


def _non_negative_int(value: object, *, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{path} must be a non-negative integer")
    return value


def _finite_non_negative_number(value: object, *, path: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{path} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        _fail(f"{path} must be finite")
    if value < 0:
        _fail(f"{path} must be non-negative")
    return value


def _canonical_copy(value: object) -> object:
    return copy.deepcopy(value)


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return __import__("hashlib").sha256(encoded).hexdigest()


def _validate_count_report(value: object, *, path: str) -> dict[str, Any]:
    item = _object(value, path=path)
    _keys(item, path=path, required={"checked", "mismatches"})
    _non_negative_int(item["checked"], path=f"{path}.checked")
    _non_negative_int(item["mismatches"], path=f"{path}.mismatches")
    return item


def _validate_review_result(value: object, *, path: str) -> dict[str, Any]:
    item = _object(value, path=path)
    _keys(item, path=path, required={"status", "counts", "degraded"})
    if item["status"] not in _STATUS:
        _fail(f"{path}.status must be a recognized status")
    counts = _object(item["counts"], path=f"{path}.counts")
    _keys(counts, path=f"{path}.counts", required={"primitive", "component", "dimension"})
    _validate_count_report(counts["primitive"], path=f"{path}.counts.primitive")
    _validate_count_report(counts["component"], path=f"{path}.counts.component")
    _validate_count_report(counts["dimension"], path=f"{path}.counts.dimension")
    _bool(item["degraded"], path=f"{path}.degraded")
    return item


def _validate_human(value: object, *, path: str) -> dict[str, Any]:
    item = _object(value, path=path)
    _keys(item, path=path, required={"events", "count"})
    events = item["events"]
    if not isinstance(events, list):
        _fail(f"{path}.events must be a list")
    total = 0
    for index, event in enumerate(events):
        entry = _object(event, path=f"{path}.events[{index}]")
        _keys(entry, path=f"{path}.events[{index}]", required={"kind", "count"}, optional={"detail"})
        _identifier(entry["kind"], path=f"{path}.events[{index}].kind")
        total += _non_negative_int(entry["count"], path=f"{path}.events[{index}].count")
        if "detail" in entry and not isinstance(entry["detail"], str):
            _fail(f"{path}.events[{index}].detail must be a string")
    count = _non_negative_int(item["count"], path=f"{path}.count")
    if count != total:
        _fail(f"{path}.count must equal the sum of event counts")
    return item


def _validate_negative_probe(value: object, *, path: str) -> dict[str, Any]:
    item = _object(value, path=path)
    _keys(item, path=path, required={"kind", "count", "captured"})
    if item["kind"] not in {"stale_evidence", "wrong_target"}:
        _fail(f"{path}.kind must be a negative probe kind")
    _non_negative_int(item["count"], path=f"{path}.count")
    _bool(item["captured"], path=f"{path}.captured")
    return item


def _validate_cleanup(value: object, *, path: str) -> dict[str, Any]:
    item = _object(value, path=path)
    _keys(item, path=path, required={"closed_without_save", "source_unchanged", "staged_unchanged", "release_verified"})
    for key in ("closed_without_save", "source_unchanged", "staged_unchanged", "release_verified"):
        _bool(item[key], path=f"{path}.{key}")
    return item


def _validate_mutation(value: object, *, path: str) -> dict[str, Any]:
    item = _object(value, path=path)
    _keys(item, path=path, required={"save_attempts", "repair_attempts"})
    _non_negative_int(item["save_attempts"], path=f"{path}.save_attempts")
    _non_negative_int(item["repair_attempts"], path=f"{path}.repair_attempts")
    return item


def _validate_transport(value: object, *, path: str) -> dict[str, Any]:
    item = _object(value, path=path)
    _keys(item, path=path, required={"name", "attempts", "successes", "failures"})
    _identifier(item["name"], path=f"{path}.name")
    attempts = _non_negative_int(item["attempts"], path=f"{path}.attempts")
    successes = _non_negative_int(item["successes"], path=f"{path}.successes")
    failures = _non_negative_int(item["failures"], path=f"{path}.failures")
    if successes + failures > attempts:
        _fail(f"{path} successes and failures exceed attempts")
    return item


def _validate_epoch(value: object, *, path: str) -> dict[str, Any]:
    item = _object(value, path=path)
    _keys(
        item,
        path=path,
        required={
            "session_id",
            "main_sha",
            "profile_revision",
            "fixture_id",
            "fixture_input_sha256",
            "staged_dxf_sha256",
            "started_at",
            "finished_at",
            "wall_clock_seconds",
            "human",
            "headless",
            "live",
            "transport",
            "negative_probes",
            "hashes",
            "mutation",
            "cleanup",
            "accepted_comparable",
            "success",
        },
    )
    _identifier(item["session_id"], path=f"{path}.session_id")
    _sha256(item["main_sha"], path=f"{path}.main_sha")
    _identifier(item["profile_revision"], path=f"{path}.profile_revision")
    _identifier(item["fixture_id"], path=f"{path}.fixture_id")
    _sha256(item["fixture_input_sha256"], path=f"{path}.fixture_input_sha256")
    _sha256(item["staged_dxf_sha256"], path=f"{path}.staged_dxf_sha256")
    _timestamp(item["started_at"], path=f"{path}.started_at")
    _timestamp(item["finished_at"], path=f"{path}.finished_at")
    _finite_non_negative_number(item["wall_clock_seconds"], path=f"{path}.wall_clock_seconds")
    human = _validate_human(item["human"], path=f"{path}.human")
    headless = _validate_review_result(item["headless"], path=f"{path}.headless")
    live = _validate_review_result(item["live"], path=f"{path}.live")
    transport = item["transport"]
    if not isinstance(transport, list):
        _fail(f"{path}.transport must be a list")
    for index, entry in enumerate(transport):
        _validate_transport(entry, path=f"{path}.transport[{index}]")
    negative_probes = item["negative_probes"]
    if not isinstance(negative_probes, list) or not negative_probes:
        _fail(f"{path}.negative_probes must be a non-empty list")
    captured = 0
    for index, entry in enumerate(negative_probes):
        probe = _validate_negative_probe(entry, path=f"{path}.negative_probes[{index}]")
        captured += probe["count"]
    hashes = _object(item["hashes"], path=f"{path}.hashes")
    _keys(hashes, path=f"{path}.hashes", required={"before", "after"})
    before = _sha256(hashes["before"], path=f"{path}.hashes.before")
    after = _sha256(hashes["after"], path=f"{path}.hashes.after")
    mutation = _validate_mutation(item["mutation"], path=f"{path}.mutation")
    cleanup = _validate_cleanup(item["cleanup"], path=f"{path}.cleanup")
    accepted = _bool(item["accepted_comparable"], path=f"{path}.accepted_comparable")
    success = _bool(item["success"], path=f"{path}.success")
    if item["negative_probes"] == [] and accepted:
        _fail(f"{path} accepted_comparable requires negative probes")
    if item["negative_probes"] == [] and not accepted:
        _fail(f"{path}.negative_probes must not be empty")
    if item["headless"]["status"] == "NOT_CAPTURED" or item["live"]["status"] == "NOT_CAPTURED":
        _fail(f"{path} comparable epoch cannot contain NOT_CAPTURED")
    if any(entry["status"] in {"NOT_CAPTURED", "SKIP", "NOT_RUN"} for entry in (item["headless"], item["live"])):
        if accepted:
            _fail(f"{path} accepted_comparable cannot be true for non-comparable status")
    kinds = {probe["kind"] for probe in negative_probes}
    if accepted and kinds != {"stale_evidence", "wrong_target"}:
        _fail(f"{path} accepted_comparable requires both negative probes")
    if any(probe["captured"] is False for probe in negative_probes):
        if accepted:
            _fail(f"{path} accepted_comparable requires negative probe capture")
    if not cleanup["closed_without_save"] or not cleanup["source_unchanged"] or not cleanup["staged_unchanged"] or not cleanup["release_verified"]:
        if accepted:
            _fail(f"{path} accepted_comparable requires cleanup integrity")
    if success and not accepted:
        _fail(f"{path} success cannot be true when epoch is not accepted_comparable")
    if success:
        if not accepted:
            _fail(f"{path} success requires accepted_comparable")
        if headless["status"] != "PASS" or live["status"] != "PASS":
            _fail(f"{path} success requires PASS reviews")
        if any(
            report["checked"] <= 0
            for report in (
                headless["counts"]["primitive"],
                headless["counts"]["component"],
                headless["counts"]["dimension"],
                live["counts"]["primitive"],
                live["counts"]["component"],
                live["counts"]["dimension"],
            )
        ):
            _fail(f"{path} success requires positive checked counts")
        if any(report["mismatches"] != 0 for report in (
            headless["counts"]["primitive"],
            headless["counts"]["component"],
            headless["counts"]["dimension"],
            live["counts"]["primitive"],
            live["counts"]["component"],
            live["counts"]["dimension"],
        )):
            _fail(f"{path} success requires zero mismatches")
        if live["degraded"]:
            _fail(f"{path} success requires non-degraded live review")
        if before != after:
            _fail(f"{path} success requires unchanged hashes")
        if mutation["save_attempts"] or mutation["repair_attempts"]:
            _fail(f"{path} success forbids save or repair attempts")
        if not cleanup["source_unchanged"] or not cleanup["staged_unchanged"] or not cleanup["release_verified"]:
            _fail(f"{path} success requires cleanup integrity")
        if captured <= 0:
            _fail(f"{path} success requires negative probe capture")
        if kinds != {"stale_evidence", "wrong_target"}:
            _fail(f"{path} success requires both negative probe kinds")
    return item


def _validate_aggregate(value: object, *, path: str) -> dict[str, Any]:
    item = _object(value, path=path)
    _keys(item, path=path, required={"comparable_epochs", "successful_epochs", "success_rate", "representative", "status"})
    comparable = _non_negative_int(item["comparable_epochs"], path=f"{path}.comparable_epochs")
    successful = _non_negative_int(item["successful_epochs"], path=f"{path}.successful_epochs")
    if successful > comparable:
        _fail(f"{path}.successful_epochs cannot exceed comparable_epochs")
    rate = item["success_rate"]
    if rate is not None:
        _finite_non_negative_number(rate, path=f"{path}.success_rate")
        if rate > 1:
            _fail(f"{path}.success_rate cannot exceed 1")
    if not isinstance(item["representative"], bool):
        _fail(f"{path}.representative must be boolean")
    if item["status"] not in _AGG_STATUS:
        _fail(f"{path}.status must be a known aggregate status")
    return item


def validate_m2_record(record: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(record, Mapping):
        _fail("record must be a mapping")
    payload = copy.deepcopy(dict(record))
    _keys(
        payload,
        path="$",
        required={"schema_version", "benchmark_id", "main_sha", "profile_id", "profile_revision", "fixture_id", "aggregate", "epochs"},
    )
    if payload["schema_version"] != M2_BENCHMARK_SCHEMA_VERSION:
        _fail("schema_version must match the M2 benchmark schema")
    _identifier(payload["benchmark_id"], path="benchmark_id")
    _sha256(payload["main_sha"], path="main_sha")
    _identifier(payload["profile_id"], path="profile_id")
    _identifier(payload["profile_revision"], path="profile_revision")
    _identifier(payload["fixture_id"], path="fixture_id")
    epochs = payload["epochs"]
    if not isinstance(epochs, list):
        _fail("epochs must be a list")
    validated_epochs = [_validate_epoch(epoch, path=f"epochs[{index}]") for index, epoch in enumerate(epochs)]
    for index, epoch in enumerate(validated_epochs):
        if (
            epoch["main_sha"] != payload["main_sha"]
            or epoch["profile_revision"] != payload["profile_revision"]
            or epoch["fixture_id"] != payload["fixture_id"]
        ):
            _fail(f"epochs[{index}] does not match record binding")
    payload["epochs"] = validated_epochs
    payload["aggregate"] = _validate_aggregate(payload["aggregate"], path="aggregate")
    comparable_epochs = [epoch for epoch in validated_epochs if epoch["accepted_comparable"]]
    successful_epochs = [epoch for epoch in comparable_epochs if epoch["success"]]
    if payload["aggregate"]["comparable_epochs"] != len(comparable_epochs):
        _fail("aggregate.comparable_epochs must match comparable epoch count")
    if payload["aggregate"]["successful_epochs"] != len(successful_epochs):
        _fail("aggregate.successful_epochs must match successful epoch count")
    if payload["aggregate"]["success_rate"] is None:
        if comparable_epochs:
            _fail("aggregate.success_rate cannot be null when comparable epochs exist")
    else:
        expected = len(successful_epochs) / len(comparable_epochs) if comparable_epochs else None
        if expected is None or not math.isclose(payload["aggregate"]["success_rate"], expected, rel_tol=0, abs_tol=1e-12):
            _fail("aggregate.success_rate does not match comparable epochs")
    representative = len(successful_epochs) >= 3 and len({epoch["session_id"] for epoch in successful_epochs}) >= 2
    if payload["aggregate"]["representative"] != representative:
        _fail("aggregate.representative does not match successful epoch distribution")
    status = "REPRESENTATIVE" if representative else ("NOT_REPRESENTATIVE" if comparable_epochs else "BASELINE_ONLY")
    if payload["aggregate"]["status"] != status and not (status == "BASELINE_ONLY" and payload["aggregate"]["status"] == "NOT_RUN"):
        _fail("aggregate.status does not match aggregate evidence")
    return payload


def new_m2_record(*, benchmark_id: str, main_sha: str, profile_id: str, profile_revision: str, fixture_id: str) -> dict[str, object]:
    record = {
        "schema_version": M2_BENCHMARK_SCHEMA_VERSION,
        "benchmark_id": benchmark_id,
        "main_sha": main_sha,
        "profile_id": profile_id,
        "profile_revision": profile_revision,
        "fixture_id": fixture_id,
        "aggregate": {
            "comparable_epochs": 0,
            "successful_epochs": 0,
            "success_rate": None,
            "representative": False,
            "status": "NOT_RUN",
        },
        "epochs": [],
    }
    return validate_m2_record(record)


def append_m2_epoch(record: Mapping[str, object], epoch: Mapping[str, object]) -> dict[str, object]:
    validated = validate_m2_record(record)
    candidate = _validate_epoch(epoch, path="epoch")
    if (
        candidate["main_sha"] != validated["main_sha"]
        or candidate["profile_revision"] != validated["profile_revision"]
        or candidate["fixture_id"] != validated["fixture_id"]
    ):
        _fail("epoch binding does not match record binding")
    new_record = copy.deepcopy(validated)
    new_record["epochs"].append(candidate)
    return validate_m2_record({
        **new_record,
        "aggregate": aggregate_m2_epochs(new_record["epochs"]),
    })


def aggregate_m2_epochs(epochs: Sequence[Mapping[str, object]]) -> dict[str, object]:
    comparable = []
    successful = []
    for epoch in epochs:
        item = _validate_epoch(epoch, path="epoch")
        if item["accepted_comparable"]:
            comparable.append(item)
            if item["success"]:
                successful.append(item)
    success_rate = None
    if comparable:
        success_rate = len(successful) / len(comparable)
    representative = len(successful) >= 3 and len({epoch["session_id"] for epoch in successful}) >= 2
    status = "REPRESENTATIVE" if representative else ("NOT_REPRESENTATIVE" if comparable else "BASELINE_ONLY")
    return {
        "comparable_epochs": len(comparable),
        "successful_epochs": len(successful),
        "success_rate": success_rate,
        "representative": representative,
        "status": status,
    }
