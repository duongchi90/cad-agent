from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from cad_agent.m2_benchmark import (
    M2_BENCHMARK_SCHEMA_VERSION,
    M2BenchmarkError,
    aggregate_m2_epochs,
    append_m2_epoch,
    new_m2_record,
    validate_m2_record,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "benchmarks" / "m2-mechanical-benchmark-record.schema.json"

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64


def _event(kind: str, count: int, detail: str = "manual operator load") -> dict[str, object]:
    payload = {"kind": kind, "count": count, "detail": detail}
    return payload


def _counts(checked: int = 1, mismatches: int = 0) -> dict[str, object]:
    return {"checked": checked, "mismatches": mismatches}


def _review(status: str = "PASS", degraded: bool = False) -> dict[str, object]:
    return {
        "status": status,
        "counts": {
            "primitive": _counts(),
            "component": _counts(),
            "dimension": _counts(),
        },
        "degraded": degraded,
    }


def _epoch(
    *,
    session_id: str = "session-a",
    main_sha: str = _SHA_A,
    profile_revision: str = "r1",
    fixture_id: str = "fixture-1",
    fixture_input_sha256: str = _SHA_B,
    staged_dxf_sha256: str = _SHA_C,
    accepted_comparable: bool = True,
    success: bool = True,
    headless: dict[str, object] | None = None,
    live: dict[str, object] | None = None,
    hashes: dict[str, str] | None = None,
    negative_probes: list[dict[str, object]] | None = None,
    cleanup: dict[str, object] | None = None,
    mutation: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "session_id": session_id,
        "main_sha": main_sha,
        "profile_revision": profile_revision,
        "fixture_id": fixture_id,
        "fixture_input_sha256": fixture_input_sha256,
        "staged_dxf_sha256": staged_dxf_sha256,
        "started_at": "2026-08-30T10:00:00Z",
        "finished_at": "2026-08-30T10:05:00Z",
        "wall_clock_seconds": 300.0,
        "human": {
            "events": [_event("NETLOAD", 1)],
            "count": 1,
        },
        "headless": headless or _review(),
        "live": live or _review(),
        "transport": [
            {"name": "fileipc", "attempts": 1, "successes": 1, "failures": 0},
            {"name": "dotnetipc", "attempts": 1, "successes": 1, "failures": 0},
        ],
        "negative_probes": negative_probes or [
            {"kind": "stale_evidence", "count": 1, "captured": True},
            {"kind": "wrong_target", "count": 1, "captured": True},
        ],
        "hashes": hashes or {"before": _SHA_A, "after": _SHA_A},
        "mutation": mutation or {"save_attempts": 0, "repair_attempts": 0},
        "cleanup": cleanup or {
            "closed_without_save": True,
            "source_unchanged": True,
            "staged_unchanged": True,
            "release_verified": True,
        },
        "accepted_comparable": accepted_comparable,
        "success": success,
    }


def _record(**overrides: object) -> dict[str, object]:
    record = {
        "schema_version": M2_BENCHMARK_SCHEMA_VERSION,
        "benchmark_id": "m2-mechanical",
        "main_sha": _SHA_A,
        "profile_id": "M2_MECHANICAL_REVIEW_V1",
        "profile_revision": "r1",
        "fixture_id": "fixture-1",
        "aggregate": {
            "comparable_epochs": 1,
            "successful_epochs": 1,
            "success_rate": 1.0,
            "representative": False,
            "status": "NOT_REPRESENTATIVE",
        },
        "epochs": [_epoch()],
    }
    record.update(overrides)
    return record


def test_schema_is_closed_json() -> None:
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert payload["additionalProperties"] is False
    assert payload["properties"]["schema_version"]["const"] == M2_BENCHMARK_SCHEMA_VERSION


def test_validate_accepts_closed_record() -> None:
    validated = validate_m2_record(
        new_m2_record(
            benchmark_id="m2-mechanical",
            main_sha=_SHA_A,
            profile_id="M2_MECHANICAL_REVIEW_V1",
            profile_revision="r1",
            fixture_id="fixture-1",
        )
    )
    assert validated["schema_version"] == M2_BENCHMARK_SCHEMA_VERSION


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda payload: payload.__setitem__("unknown", True), "unexpected properties"),
        (lambda payload: payload.__setitem__("main_sha", "A" * 64), "lowercase SHA-256"),
        (lambda payload: payload.__setitem__("profile_revision", "bad rev"), "identifier"),
        (lambda payload: payload["epochs"][0].__setitem__("started_at", "2026-08-30 10:00:00"), "RFC3339"),
        (lambda payload: payload["epochs"][0].__setitem__("wall_clock_seconds", -1), "non-negative"),
        (
            lambda payload: payload["epochs"][0]["headless"]["counts"]["dimension"].__setitem__("checked", 0),
            "positive checked counts",
        ),
        (
            lambda payload: payload["epochs"][0].__setitem__("fixture_input_sha256", "g" * 64),
            "lowercase SHA-256",
        ),
    ],
)
def test_validate_rejects_closed_record_drift(mutator, message) -> None:
    payload = _record()
    mutator(payload)
    with pytest.raises(M2BenchmarkError, match=message):
        validate_m2_record(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("transport", [{"name": "fileipc", "attempts": False, "successes": 0, "failures": 0}], "non-negative integer"),
        ("accepted_comparable", "yes", "boolean"),
        ("hashes", {"before": _SHA_A, "after": _SHA_B}, "unchanged hashes"),
        ("negative_probes", [{"kind": "stale_evidence", "count": 1, "captured": False}], "both negative probes"),
        ("negative_probes", [], "non-empty list"),
        ("human", {"events": [_event("NETLOAD", 2)], "count": 1}, "sum of event counts"),
        ("cleanup", {"closed_without_save": False, "source_unchanged": True, "staged_unchanged": True, "release_verified": True}, "cleanup integrity"),
        ("mutation", {"save_attempts": 1, "repair_attempts": 0}, "forbids save or repair"),
        ("headless", _review(status="NOT_CAPTURED"), "NOT_CAPTURED"),
        ("headless", _review(status="NOT_RUN"), "non-comparable status"),
        ("live", _review(status="SKIP"), "accepted_comparable"),
    ],
)
def test_epoch_oracle_rejects_required_false_green_cases(field, value, message) -> None:
    payload = _epoch()
    payload[field] = value
    with pytest.raises(M2BenchmarkError, match=message):
        validate_m2_record(_record(epochs=[payload]))


def test_epoch_rejects_dimension_zero() -> None:
    payload = _epoch()
    payload["headless"]["counts"]["dimension"]["checked"] = 0
    with pytest.raises(M2BenchmarkError, match="positive checked counts"):
        validate_m2_record(_record(epochs=[payload]))


def test_append_enforces_binding_and_pure_copy() -> None:
    record = _record()
    original = copy.deepcopy(record)
    epoch = _epoch()
    epoch["hashes"]["after"] = _SHA_B
    with pytest.raises(M2BenchmarkError, match="unchanged hashes"):
        append_m2_epoch(record, epoch)
    assert record == original


def test_append_rejects_binding_mismatch() -> None:
    record = _record()
    epoch = _epoch(main_sha=_SHA_D)
    with pytest.raises(M2BenchmarkError, match="binding"):
        append_m2_epoch(record, epoch)


def test_aggregate_oracle_supports_baseline_non_representative_and_representative() -> None:
    baseline = aggregate_m2_epochs([])
    assert baseline == {
        "comparable_epochs": 0,
        "successful_epochs": 0,
        "success_rate": None,
        "representative": False,
        "status": "BASELINE_ONLY",
    }
    one = aggregate_m2_epochs([_epoch(session_id="session-a")])
    assert one["comparable_epochs"] == 1
    assert one["successful_epochs"] == 1
    assert one["success_rate"] == 1.0
    assert one["representative"] is False
    assert one["status"] == "NOT_REPRESENTATIVE"
    two_sessions = aggregate_m2_epochs([
        _epoch(session_id="session-a"),
        _epoch(session_id="session-b"),
        _epoch(session_id="session-a"),
    ])
    assert two_sessions["representative"] is True
    assert two_sessions["status"] == "REPRESENTATIVE"


def test_no_comparable_success_rate_is_none() -> None:
    result = aggregate_m2_epochs([_epoch(accepted_comparable=False, success=False, headless=_review(status="SKIP"), live=_review(status="SKIP"), negative_probes=[{"kind": "stale_evidence", "count": 1, "captured": False}], cleanup={"closed_without_save": True, "source_unchanged": True, "staged_unchanged": True, "release_verified": True})])
    assert result["comparable_epochs"] == 0
    assert result["success_rate"] is None
