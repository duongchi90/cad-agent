from __future__ import annotations

import copy
import json
import hashlib
from pathlib import Path

import pytest

from cad_agent.live import LiveSafetyError, load_build_evidence
from cad_agent.manifest import sha256_file
from cad_agent.m2_benchmark import (
    M2_BENCHMARK_SCHEMA_VERSION,
    M2BenchmarkError,
    aggregate_m2_epochs,
    append_m2_epoch,
    new_m2_record,
    validate_m2_record,
)
from mcp_integration_lib.tests.test_m2_mechanical_benchmark_live import (
    M2_MECHANICAL_BENCHMARK_PROFILE_ID,
    M2_MECHANICAL_BENCHMARK_PROFILE_REVISION,
    _load_existing_m2_record,
    _m2_live_prerequisites_available,
    _parse_human_events_json,
)
from tests.m2_benchmark_support import build_m2_fixture, headless_metrics


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
        "fixture_input_sha256": _SHA_B,
        "staged_dxf_sha256": _SHA_C,
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
            fixture_input_sha256=_SHA_B,
            staged_dxf_sha256=_SHA_C,
        )
    )
    assert validated["schema_version"] == M2_BENCHMARK_SCHEMA_VERSION
    assert validated["fixture_input_sha256"] == _SHA_B
    assert validated["staged_dxf_sha256"] == _SHA_C


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda payload: payload.__setitem__("unknown", True), "unexpected properties"),
        (lambda payload: payload.__setitem__("main_sha", "A" * 64), "lowercase SHA-256"),
        (lambda payload: payload.__setitem__("profile_revision", "bad rev"), "identifier"),
        (lambda payload: payload.__setitem__("fixture_input_sha256", "g" * 64), "lowercase SHA-256"),
        (lambda payload: payload["epochs"][0].__setitem__("started_at", "2026-08-30 10:00:00"), "RFC3339"),
        (lambda payload: payload["epochs"][0].__setitem__("wall_clock_seconds", -1), "non-negative"),
        (
            lambda payload: payload["epochs"][0]["headless"]["counts"]["dimension"].__setitem__("checked", 0),
            "positive checked counts",
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
        ("main_sha", _SHA_D, "binding"),
        ("profile_revision", "r2", "binding"),
        ("fixture_id", "fixture-2", "binding"),
        ("fixture_input_sha256", _SHA_D, "binding"),
        ("staged_dxf_sha256", _SHA_D, "binding"),
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("main_sha", _SHA_D),
        ("profile_revision", "r2"),
        ("fixture_id", "fixture-2"),
        ("fixture_input_sha256", _SHA_D),
        ("staged_dxf_sha256", _SHA_D),
    ],
)
def test_append_rejects_each_binding_mismatch(field: str, value: object) -> None:
    record = _record()
    epoch = _epoch(**{field: value})
    with pytest.raises(M2BenchmarkError, match="binding"):
        append_m2_epoch(record, epoch)


def test_new_record_with_real_hashes_appends_matching_epoch() -> None:
    record = new_m2_record(
        benchmark_id="m2-mechanical",
        main_sha=_SHA_A,
        profile_id="M2_MECHANICAL_REVIEW_V1",
        profile_revision="r1",
        fixture_id="fixture-1",
        fixture_input_sha256=_SHA_B,
        staged_dxf_sha256=_SHA_C,
    )
    epoch = _epoch(fixture_input_sha256=_SHA_B, staged_dxf_sha256=_SHA_C)
    appended = append_m2_epoch(record, epoch)
    assert appended["fixture_input_sha256"] == _SHA_B
    assert appended["staged_dxf_sha256"] == _SHA_C
    assert appended["epochs"][0]["fixture_input_sha256"] == _SHA_B
    assert appended["epochs"][0]["staged_dxf_sha256"] == _SHA_C


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("main_sha", _SHA_D),
        ("profile_revision", "r2"),
        ("fixture_id", "fixture-2"),
        ("fixture_input_sha256", _SHA_D),
        ("staged_dxf_sha256", _SHA_D),
    ],
)
def test_new_record_with_real_hashes_rejects_epoch_mismatches(field: str, value: object) -> None:
    record = new_m2_record(
        benchmark_id="m2-mechanical",
        main_sha=_SHA_A,
        profile_id="M2_MECHANICAL_REVIEW_V1",
        profile_revision="r1",
        fixture_id="fixture-1",
        fixture_input_sha256=_SHA_B,
        staged_dxf_sha256=_SHA_C,
    )
    epoch = _epoch(**{field: value})
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


def test_m2_fixture_support_builds_deterministic_fixture(tmp_path: Path) -> None:
    fixture = build_m2_fixture(tmp_path)

    assert fixture.input_path.exists()
    assert fixture.staged_dxf.exists()
    assert fixture.build_evidence.exists()
    assert fixture.input_sha256 == sha256_file(fixture.input_path)
    assert fixture.staged_dxf_sha256 == sha256_file(fixture.staged_dxf)
    assert b"timestamp" not in fixture.source_bytes.lower()
    assert b"uuid" not in fixture.source_bytes.lower()
    assert b"random" not in fixture.source_bytes.lower()
    assert b"absolute" not in fixture.source_bytes.lower()
    assert fixture.source_json["primitives"][0]["id"] == "line-001"
    assert fixture.source_json["primitives"][1]["id"] == "circle-001"
    assert fixture.source_json["primitives"][2]["id"] == "text-001"
    assert set(fixture.build.handle_by_primitive_id) == {"line-001", "circle-001", "text-001"}
    assert len(set(fixture.build.handle_by_primitive_id.values())) == 3
    assert fixture.build.entity_count == 3
    assert fixture.build.dimension_count == 1
    assert fixture.build.component_count == 1
    assert fixture.build.skipped_primitive_ids == []
    assert fixture.build.component_type_by_part_id["part-001"] == "frame_beam"
    assert fixture.build.component_handle_by_part_id["part-001"]
    assert fixture.build.written_dimension_by_cross_validation_id["cv-001"][
        "approved_value_mm"
    ] is None
    assert fixture.headless.passed is True
    assert fixture.headless.checked_count == 3
    assert fixture.headless.component_checked_count == 1
    assert fixture.headless.dimension_checked_count == 1
    metrics = headless_metrics(fixture)
    assert metrics == {
        "primitive_checked_count": 3,
        "primitive_mismatch_count": 0,
        "component_checked_count": 1,
        "component_mismatch_count": 0,
        "dimension_checked_count": 1,
        "dimension_mismatch_count": 0,
        "status": "PASS",
    }


def test_m2_fixture_support_is_reproducible_across_fresh_roots(tmp_path: Path) -> None:
    first = build_m2_fixture(tmp_path / "first")
    second = build_m2_fixture(tmp_path / "second")

    assert first.input_sha256 == second.input_sha256
    assert first.staged_dxf_sha256 == second.staged_dxf_sha256
    assert first.staged_dxf.read_bytes() == second.staged_dxf.read_bytes()
    assert hashlib.sha256(first.staged_dxf.read_bytes()).hexdigest() == first.staged_dxf_sha256
    assert hashlib.sha256(second.staged_dxf.read_bytes()).hexdigest() == second.staged_dxf_sha256


def test_m2_fixture_build_evidence_round_trips_and_refuses_stale_dxf(tmp_path: Path) -> None:
    fixture = build_m2_fixture(tmp_path)
    loaded = load_build_evidence(fixture.build_evidence, fixture.staged_dxf)

    assert loaded.handle_by_primitive_id == fixture.build.handle_by_primitive_id
    assert loaded.written_geometry_by_primitive_id == fixture.build.written_geometry_by_primitive_id

    copied = tmp_path / "copied-staged.dxf"
    copied.write_bytes(fixture.staged_dxf.read_bytes() + b"\nchanged")
    with pytest.raises(LiveSafetyError, match="SHA-256"):
        load_build_evidence(fixture.build_evidence, copied)

    assert fixture.build_evidence.read_text(encoding="utf-8").strip().startswith("{")


def test_m2_human_events_json_parses_and_rejects_invalid_payloads() -> None:
    events = _parse_human_events_json('[{"kind":"NETLOAD","count":1,"detail":"manual"}]')
    assert events == [{"kind": "NETLOAD", "count": 1, "detail": "manual"}]

    with pytest.raises(ValueError, match="human events"):
        _parse_human_events_json("")
    with pytest.raises(ValueError, match="human events"):
        _parse_human_events_json("[]")
    with pytest.raises(ValueError, match="human events"):
        _parse_human_events_json('[{"kind":"NETLOAD","count":0}]')


def test_m2_missing_capture_is_non_comparable_not_zero() -> None:
    record = new_m2_record(
        benchmark_id="m2-mechanical",
        main_sha=_SHA_A,
        profile_id=M2_MECHANICAL_BENCHMARK_PROFILE_ID,
        profile_revision=M2_MECHANICAL_BENCHMARK_PROFILE_REVISION,
        fixture_id="fixture-1",
        fixture_input_sha256=_SHA_B,
        staged_dxf_sha256=_SHA_C,
    )
    epoch = _record()["epochs"][0]
    epoch["human"]["events"] = []
    epoch["human"]["count"] = 0
    epoch["accepted_comparable"] = False
    epoch["success"] = False
    epoch["headless"]["status"] = "NOT_RUN"
    epoch["live"]["status"] = "NOT_RUN"
    epoch["negative_probes"] = []
    epoch["cleanup"] = {
        "closed_without_save": True,
        "source_unchanged": True,
        "staged_unchanged": True,
        "release_verified": True,
    }

    with pytest.raises(M2BenchmarkError, match="non-empty list"):
        validate_m2_record({**record, "epochs": [epoch]})


def test_m2_live_prerequisites_do_not_hide_missing_record_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAD_AGENT_M2_RECORD_PATH", raising=False)
    monkeypatch.delenv("CAD_AGENT_M2_SESSION_ID", raising=False)
    monkeypatch.delenv("CAD_AGENT_M2_HUMAN_EVENTS_JSON", raising=False)
    assert _m2_live_prerequisites_available() is False


def test_m2_existing_record_from_other_main_sha_is_refused(tmp_path: Path) -> None:
    record_path = tmp_path / "m2-record.json"
    record = _record()
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="main SHA"):
        _load_existing_m2_record(record_path, main_sha=_SHA_D)
