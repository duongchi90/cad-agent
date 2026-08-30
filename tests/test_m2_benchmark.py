from __future__ import annotations

import copy
import json
import hashlib
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import pytest
import mcp_integration_lib.tests.test_m2_mechanical_benchmark_live as m2_live
import tests.m2_benchmark_support as m2_fixture_support

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
    M2_MECHANICAL_BENCHMARK_HUMAN_EVENTS_ENV,
    M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV,
    M2_MECHANICAL_BENCHMARK_SESSION_ID_ENV,
    _apply_failure_outcome,
    _cleanup_epoch_artifacts,
    _copy_review_result,
    _exercise_stale_evidence_rejection,
    _exercise_wrong_target_rejection,
    _current_main_sha,
    _initial_epoch,
    _load_existing_m2_record,
    _missing_m2_opt_in_inputs,
    _persist_epoch_record,
    _persist_m2_measurements_artifact,
    _m2_live_prerequisites_available,
    _parse_human_events_json,
    _record_path_from_env,
    _request_artifacts_removed,
    _transport_for_operation,
    _transport_counters,
    _transport_records,
)
from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCProtocolError,
    DotNetIPCResultError,
    DotNetIPCTimeoutError,
)
from mcp_integration_lib.dotnet_ipc import request_path, result_path
from mcp_integration_lib.mcp_client import MCPTimeoutError, MCPToolError
from mcp_integration_lib.reviewer2 import LiveReviewResult
from tests.m2_benchmark_support import build_m2_fixture, headless_metrics


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "benchmarks" / "m2-mechanical-benchmark-record.schema.json"

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64
_GIT_SHA_A = "a" * 40
_GIT_SHA_B = "b" * 40
_GIT_SHA_C = "c" * 40
_GIT_SHA_D = "d" * 40


def _git_output(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


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
        "geometry_checked": 1,
        "mismatches": [],
        "warnings": [],
    }


def _epoch(
    *,
    session_id: str = "session-a",
    main_sha: str = _GIT_SHA_A,
    profile_revision: str = "r1",
    fixture_id: str = "fixture-1",
    fixture_input_sha256: str = _SHA_B,
    staged_dxf_sha256: str = _SHA_C,
    accepted_comparable: bool = True,
    success: bool = True,
    headless: dict[str, object] | None = None,
    live: dict[str, object] | None = None,
    hashes: dict[str, str] | None = None,
    source_hashes: dict[str, str] | None = None,
    staged_hashes: dict[str, str] | None = None,
    negative_probes: list[dict[str, object]] | None = None,
    cleanup: dict[str, object] | None = None,
    mutation: dict[str, object] | None = None,
    human_captured: bool = True,
    environment: dict[str, object] | None = None,
    failure: dict[str, str] | None = None,
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
            "captured": human_captured,
        },
        "headless": headless or _review(),
        "live": live or _review(),
        "transport": [
            {"name": "fileipc", "attempts": 1, "successes": 1, "failures": 0},
            {"name": "dotnetipc", "attempts": 1, "successes": 1, "failures": 0},
            {"name": "live_review", "attempts": 1, "successes": 1, "failures": 0},
        ],
        "negative_probes": negative_probes or [
            {
                "kind": "stale_evidence",
                "count": 1,
                "captured": True,
                "operation": "load_build_evidence",
                "category": "stale_evidence",
                "detail": "stale evidence was rejected",
            },
            {
                "kind": "wrong_target",
                "count": 1,
                "captured": True,
                "operation": "wrong_target",
                "category": "dotnet_result",
                "detail": "active drawing identity was rejected",
            },
        ],
        "hashes": hashes or {"before": _SHA_C, "after": _SHA_C},
        "source_hashes": source_hashes or {"before": _SHA_B, "after": _SHA_B},
        "staged_hashes": staged_hashes or {"before": _SHA_C, "after": _SHA_C},
        "mutation": mutation or {"save_attempts": 0, "repair_attempts": 0},
        "cleanup": cleanup or {
            "closed_without_save": True,
            "source_unchanged": True,
            "staged_unchanged": True,
            "release_verified": True,
        },
        "environment": environment or {
            "captured": True,
            "autocad_product": "AutoCAD Mechanical 2027",
            "plugin_version": "1.0.0",
            "python_version": "3.11.9",
            "ipc_root_id": "ipc-root-001",
            "runtime_identity": f"acad-{session_id}",
            "implementation_sha": _GIT_SHA_A,
            "pr_head_sha": _GIT_SHA_A,
            "harness_sha": _GIT_SHA_A,
            "plugin_binary_sha256": _SHA_D,
        },
        "failure": failure,
        "accepted_comparable": accepted_comparable,
        "success": success,
    }


def _record(**overrides: object) -> dict[str, object]:
    record = {
        "schema_version": M2_BENCHMARK_SCHEMA_VERSION,
        "benchmark_id": "m2-mechanical",
        "main_sha": _GIT_SHA_A,
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


def test_schema_separates_git_commit_identity_from_sha256_hashes() -> None:
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert payload["properties"]["main_sha"] == {"$ref": "#/$defs/git_commit_sha"}
    assert payload["$defs"]["git_commit_sha"]["pattern"] == "^[0-9a-f]{40}$"
    assert payload["properties"]["fixture_input_sha256"] == {"$ref": "#/$defs/sha256"}
    assert payload["properties"]["staged_dxf_sha256"] == {"$ref": "#/$defs/sha256"}
    assert payload["$defs"]["epoch"]["properties"]["main_sha"] == {
        "$ref": "#/$defs/git_commit_sha"
    }


def test_schema_environment_binds_runtime_and_build_identity() -> None:
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    environment = payload["$defs"]["environment"]

    identity_fields = {
        "runtime_identity",
        "implementation_sha",
        "pr_head_sha",
        "harness_sha",
        "plugin_binary_sha256",
    }
    assert set(environment["required"]) == {
        "captured",
        "autocad_product",
        "plugin_version",
        "python_version",
        "ipc_root_id",
    }
    assert identity_fields <= set(payload["$defs"]["accepted_environment"]["allOf"][1]["required"])
    assert environment["properties"]["runtime_identity"] == {"type": ["string", "null"]}
    assert environment["properties"]["implementation_sha"] == {
        "anyOf": [{"$ref": "#/$defs/git_commit_sha"}, {"type": "null"}]
    }
    assert environment["properties"]["pr_head_sha"] == {
        "anyOf": [{"$ref": "#/$defs/git_commit_sha"}, {"type": "null"}]
    }
    assert environment["properties"]["harness_sha"] == {
        "anyOf": [{"$ref": "#/$defs/git_commit_sha"}, {"type": "null"}]
    }
    assert environment["properties"]["plugin_binary_sha256"] == {
        "anyOf": [{"$ref": "#/$defs/sha256"}, {"type": "null"}]
    }


def test_schema_has_accepted_epoch_constraints_for_identity_transport_and_probes() -> None:
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    epoch = payload["$defs"]["epoch"]
    accepted = next(
        clause["then"]
        for clause in epoch["allOf"]
        if clause["if"]["properties"]["accepted_comparable"]["const"] is True
    )
    assert accepted["properties"]["environment"]["$ref"] == "#/$defs/accepted_environment"
    transport = payload["$defs"]["accepted_transport"]
    assert transport["minItems"] == 3
    assert transport["maxItems"] == 3
    assert transport["uniqueItems"] is True
    assert transport["items"] == {"$ref": "#/$defs/accepted_transport_entry"}
    probes = payload["$defs"]["accepted_negative_probes"]
    assert probes["minItems"] == 2
    assert probes["maxItems"] == 2
    assert probes["items"] == {"$ref": "#/$defs/accepted_negative_probe"}
    accepted_probe = payload["$defs"]["accepted_negative_probe"]
    assert accepted_probe["allOf"][1]["properties"]["count"] == {
        "type": "integer",
        "minimum": 1,
    }
    assert accepted_probe["allOf"][1]["properties"]["captured"] == {"const": True}


def test_schema_negative_probe_binds_kind_to_operation() -> None:
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    probe = payload["$defs"]["accepted_negative_probe"]["allOf"][1]

    assert "oneOf" not in payload["$defs"]["negative_probe"]
    assert probe["oneOf"] == [
        {
            "properties": {
                "kind": {"const": "stale_evidence"},
                "operation": {"const": "load_build_evidence"},
                "category": {"const": "stale_evidence"},
            }
        },
        {
            "properties": {
                "kind": {"const": "wrong_target"},
                "operation": {"const": "wrong_target"},
                "category": {
                    "enum": [
                        "dotnet_result",
                        "dotnet_timeout",
                        "dotnet_protocol",
                        "tool",
                        "timeout",
                    ]
                },
            }
        },
    ]


def test_schema_preserves_legacy_non_authoritative_probe_shape() -> None:
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    base_probe = payload["$defs"]["negative_probe"]
    accepted_probe = payload["$defs"]["accepted_negative_probe"]

    assert "oneOf" not in base_probe
    assert accepted_probe["allOf"][1]["properties"]["captured"] == {"const": True}
    assert accepted_probe["allOf"][1]["properties"]["count"] == {
        "type": "integer",
        "minimum": 1,
    }


def test_schema_legacy_probe_can_use_old_operation_but_accepted_cannot() -> None:
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    base_probe = payload["$defs"]["negative_probe"]
    accepted_variants = payload["$defs"]["accepted_negative_probe"]["allOf"][1]["oneOf"]

    assert base_probe["properties"]["operation"] == {"$ref": "#/$defs/identifier"}
    assert all(
        variant["properties"]["operation"].get("const") != "health"
        for variant in accepted_variants
    )


def test_validate_accepts_exact_current_main_git_identity() -> None:
    record = new_m2_record(
        benchmark_id="m2-mechanical",
        main_sha=_GIT_SHA_A,
        profile_id="M2_MECHANICAL_REVIEW_V1",
        profile_revision="r1",
        fixture_id="fixture-1",
        fixture_input_sha256=_SHA_B,
        staged_dxf_sha256=_SHA_C,
    )

    assert record["main_sha"] == _GIT_SHA_A


def test_validate_accepts_closed_record() -> None:
    validated = validate_m2_record(
        new_m2_record(
            benchmark_id="m2-mechanical",
            main_sha=_GIT_SHA_A,
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
        (lambda payload: payload.__setitem__("main_sha", "A" * 40), "lowercase Git commit SHA"),
        (lambda payload: payload.__setitem__("profile_revision", "bad rev"), "identifier"),
        (lambda payload: payload.__setitem__("fixture_input_sha256", "g" * 64), "lowercase SHA-256"),
        (lambda payload: payload["epochs"][0].__setitem__("started_at", "2026-08-30 10:00:00"), "RFC3339"),
        (lambda payload: payload["epochs"][0].__setitem__("wall_clock_seconds", -1), "non-negative"),
        (
            lambda payload: payload["epochs"][0]["headless"]["counts"]["dimension"].__setitem__("checked", 0),
            "positive geometry and checked counts",
        ),
    ],
)
def test_validate_rejects_closed_record_drift(mutator, message) -> None:
    payload = _record()
    mutator(payload)
    with pytest.raises(M2BenchmarkError, match=message):
        validate_m2_record(payload)


@pytest.mark.parametrize(
    "field",
    [
        "runtime_identity",
        "implementation_sha",
        "pr_head_sha",
        "harness_sha",
        "plugin_binary_sha256",
    ],
)
def test_accepted_epoch_requires_decision_grade_identity(field: str) -> None:
    payload = _epoch()
    payload["environment"].pop(field)

    with pytest.raises(M2BenchmarkError, match="environment"):
        validate_m2_record(_record(epochs=[payload]))


def test_accepted_epoch_requires_matching_implementation_and_harness_heads() -> None:
    payload = _epoch()
    payload["environment"]["harness_sha"] = _GIT_SHA_D

    with pytest.raises(M2BenchmarkError, match="identity binding"):
        validate_m2_record(_record(epochs=[payload]))


def test_aggregate_uses_observed_runtime_identity_not_caller_labels() -> None:
    epochs = [
        _epoch(session_id="caller-label-a"),
        _epoch(session_id="caller-label-b"),
        _epoch(session_id="caller-label-c"),
    ]
    for epoch in epochs:
        epoch["environment"]["runtime_identity"] = "acad-pid-100-hwnd-200"

    aggregate = aggregate_m2_epochs(epochs)

    assert aggregate["representative"] is False
    assert aggregate["status"] == "NOT_REPRESENTATIVE"


def test_accepted_epoch_requires_complete_transport_accounting() -> None:
    payload = _epoch()
    payload["transport"] = [
        {"name": "fileipc", "attempts": 1, "successes": 1, "failures": 0},
        {"name": "dotnetipc", "attempts": 1, "successes": 1, "failures": 0},
    ]

    with pytest.raises(M2BenchmarkError, match="transport accounting"):
        validate_m2_record(_record(epochs=[payload]))


def test_accepted_epoch_rejects_duplicate_transport_channel_names() -> None:
    payload = _epoch()
    payload["transport"].append(copy.deepcopy(payload["transport"][0]))

    with pytest.raises(M2BenchmarkError, match="transport accounting"):
        validate_m2_record(_record(epochs=[payload]))


def test_accepted_epoch_requires_negative_probe_operation_semantics() -> None:
    payload = _epoch()
    payload["negative_probes"][0]["operation"] = "health"

    with pytest.raises(M2BenchmarkError, match="operation"):
        validate_m2_record(_record(epochs=[payload]))


def test_accepted_epoch_requires_wrong_target_probe_operation() -> None:
    payload = _epoch()
    payload["negative_probes"][1]["operation"] = "health"

    with pytest.raises(M2BenchmarkError, match="operation"):
        validate_m2_record(_record(epochs=[payload]))


def test_legacy_non_authoritative_probe_metadata_remains_loadable() -> None:
    payload = _epoch(accepted_comparable=False, success=False, human_captured=False)
    payload["headless"]["status"] = "NOT_RUN"
    payload["live"]["status"] = "NOT_RUN"
    payload["negative_probes"][1] = {
        "kind": "wrong_target",
        "count": 0,
        "captured": False,
        "operation": "health",
        "category": "not_run",
        "detail": "not run",
    }
    validated = validate_m2_record(
        _record(
            epochs=[payload],
            aggregate={
                "comparable_epochs": 0,
                "successful_epochs": 0,
                "success_rate": None,
                "representative": False,
                "status": "BASELINE_ONLY",
            },
        )
    )
    assert validated["epochs"][0] == payload


def test_legacy_non_captured_environment_without_identity_remains_loadable() -> None:
    payload = _epoch(accepted_comparable=False, success=False, human_captured=False)
    payload["headless"]["status"] = "NOT_RUN"
    payload["live"]["status"] = "NOT_RUN"
    payload["environment"] = {
        "captured": False,
        "autocad_product": None,
        "plugin_version": None,
        "python_version": None,
        "ipc_root_id": None,
    }
    validated = validate_m2_record(
        _record(
            epochs=[payload],
            aggregate={
                "comparable_epochs": 0,
                "successful_epochs": 0,
                "success_rate": None,
                "representative": False,
                "status": "BASELINE_ONLY",
            },
        )
    )
    assert validated["epochs"][0]["environment"] == payload["environment"]


def test_accepted_epoch_requires_expected_negative_probe_category() -> None:
    payload = _epoch()
    payload["negative_probes"][0]["category"] = "wrong_target"

    with pytest.raises(M2BenchmarkError, match="category"):
        validate_m2_record(_record(epochs=[payload]))


def test_accepted_epoch_requires_each_transport_channel_attempt() -> None:
    payload = _epoch()
    payload["transport"][0]["attempts"] = 0
    payload["transport"][0]["successes"] = 0

    with pytest.raises(M2BenchmarkError, match="transport accounting"):
        validate_m2_record(_record(epochs=[payload]))


def test_failure_accounting_uses_tracked_operation_over_result_metadata() -> None:
    epoch = _epoch(accepted_comparable=True, success=True)
    transport = _transport_counters()
    transport["fileipc"]["attempts"] = 1
    error = DotNetIPCResultError(
        "variables failed",
        result={"operation": "health", "errors": ["WRONG_OPERATION"]},
    )

    detail = m2_live._record_m2_failure(
        epoch,
        transport,
        error,
        current_operation="drawing_get_variables",
        human_capture_observed=True,
    )

    assert detail["operation"] == "drawing_get_variables"
    assert _transport_records(transport) == [
        {"name": "fileipc", "attempts": 1, "successes": 0, "failures": 1}
    ]


def test_semantic_failure_after_successful_transport_does_not_double_count() -> None:
    epoch = _epoch(accepted_comparable=True, success=True)
    transport = _transport_counters()
    transport["dotnetipc"]["attempts"] = 1
    transport["dotnetipc"]["successes"] = 1

    detail = m2_live._record_m2_failure(
        epoch,
        transport,
        MCPToolError("plugin identity did not match build identity"),
        current_operation="health",
        human_capture_observed=True,
    )

    assert detail["operation"] == "health"
    assert _transport_records(transport) == [
        {"name": "dotnetipc", "attempts": 1, "successes": 1, "failures": 0}
    ]


@pytest.mark.parametrize(
    ("process_path", "accepted"),
    [
        (Path(r"C:\Program Files\Autodesk\AutoCAD 2027\acad.exe"), True),
        (Path(r"C:\Windows\System32\notepad.exe"), False),
    ],
)
def test_runtime_identity_process_guard_is_autocad_only(
    process_path: Path,
    accepted: bool,
) -> None:
    if accepted:
        assert m2_live._validate_autocad_process_path(process_path) == process_path
    else:
        with pytest.raises(MCPToolError, match="acad.exe"):
            m2_live._validate_autocad_process_path(process_path)


def test_current_implementation_sha_rejects_dirty_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args, **kwargs):
        if args[1] == "status":
            return SimpleNamespace(stdout=" M tests/test_m2_benchmark.py\n")
        return SimpleNamespace(stdout=_GIT_SHA_A)

    monkeypatch.setattr(m2_live.subprocess, "run", fake_run)

    with pytest.raises(MCPToolError, match="clean"):
        m2_live._current_implementation_sha()


@pytest.mark.parametrize(
    "health_payload",
    [
        {"plugin_version": "1.0.0", "plugin_binary_sha256": _SHA_C},
        {"plugin_version": "1.0.0"},
    ],
)
def test_health_identity_requires_loaded_plugin_hash_match(
    health_payload: dict[str, str],
) -> None:
    with pytest.raises(MCPToolError, match="plugin identity"):
        m2_live._validated_health_plugin_identity(
            {"payload": health_payload},
            expected_sha256=_SHA_D,
        )


def test_plugin_binary_identity_requires_existing_release_dll(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(m2_live, "_PLUGIN_DLL_PATH", tmp_path / "missing.dll")

    with pytest.raises(MCPToolError, match="missing"):
        m2_live._plugin_binary_sha256()


def test_accepted_epoch_requires_positive_capture_count_for_each_negative_probe() -> None:
    payload = _epoch()
    payload["negative_probes"][1]["count"] = 0

    with pytest.raises(M2BenchmarkError, match="positive negative probe capture"):
        validate_m2_record(_record(epochs=[payload]))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("main_sha", _GIT_SHA_D, "binding"),
        ("profile_revision", "r2", "binding"),
        ("fixture_id", "fixture-2", "binding"),
        ("fixture_input_sha256", _SHA_D, "binding"),
        ("staged_dxf_sha256", _SHA_D, "binding"),
        ("transport", [{"name": "fileipc", "attempts": False, "successes": 0, "failures": 0}], "non-negative integer"),
        ("accepted_comparable", "yes", "boolean"),
        ("hashes", {"before": _SHA_A, "after": _SHA_B}, "unchanged hashes"),
        ("source_hashes", {"before": _SHA_B, "after": _SHA_D}, "source hashes binding"),
        ("staged_hashes", {"before": _SHA_C, "after": _SHA_D}, "staged hashes binding"),
        (
            "negative_probes",
            [{
                "kind": "stale_evidence",
                "count": 1,
                "captured": False,
                "operation": "load_build_evidence",
                "category": "not_run",
                "detail": "not run",
            }],
            "both negative probes",
        ),
        ("negative_probes", [], "non-empty list"),
        ("human", {"events": [_event("NETLOAD", 2)], "count": 1, "captured": True}, "sum of event counts"),
        ("cleanup", {"closed_without_save": False, "source_unchanged": True, "staged_unchanged": True, "release_verified": True}, "cleanup integrity"),
        ("mutation", {"save_attempts": 1, "repair_attempts": 0}, "forbids save or repair"),
        ("headless", _review(status="NOT_CAPTURED"), "non-comparable status"),
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
    with pytest.raises(M2BenchmarkError, match="positive geometry and checked counts"):
        validate_m2_record(_record(epochs=[payload]))


def test_accepted_epoch_requires_explicit_human_capture() -> None:
    payload = _epoch(human_captured=False)
    with pytest.raises(M2BenchmarkError, match="human capture"):
        validate_m2_record(_record(epochs=[payload]))


def test_accepted_epoch_requires_live_geometry_measurement() -> None:
    payload = _epoch()
    payload["live"]["geometry_checked"] = 0
    with pytest.raises(M2BenchmarkError, match="geometry"):
        validate_m2_record(_record(epochs=[payload]))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_hashes", {"before": _SHA_D, "after": _SHA_D}, "source hashes binding"),
        ("staged_hashes", {"before": _SHA_D, "after": _SHA_D}, "staged hashes binding"),
    ],
)
def test_accepted_epoch_requires_hash_pairs_to_match_fixture_binding(
    field: str,
    value: dict[str, str],
    message: str,
) -> None:
    payload = _epoch()
    payload[field] = value
    with pytest.raises(M2BenchmarkError, match=message):
        validate_m2_record(_record(epochs=[payload]))


def test_non_comparable_not_captured_epoch_is_retained_for_diagnosis() -> None:
    record = new_m2_record(
        benchmark_id="m2-mechanical",
        main_sha=_GIT_SHA_A,
        profile_id=M2_MECHANICAL_BENCHMARK_PROFILE_ID,
        profile_revision=M2_MECHANICAL_BENCHMARK_PROFILE_REVISION,
        fixture_id="fixture-1",
        fixture_input_sha256=_SHA_B,
        staged_dxf_sha256=_SHA_C,
    )
    epoch = _epoch(accepted_comparable=False, success=False, human_captured=False)
    epoch["headless"]["status"] = "NOT_CAPTURED"
    epoch["live"]["status"] = "NOT_CAPTURED"
    epoch["negative_probes"] = [
        {
            "kind": "stale_evidence",
            "count": 0,
            "captured": False,
            "operation": "load_build_evidence",
            "category": "not_run",
            "detail": "not run",
        },
        {
            "kind": "wrong_target",
            "count": 0,
            "captured": False,
            "operation": "health",
            "category": "not_run",
            "detail": "not run",
        },
    ]
    validated = validate_m2_record({
        **record,
        "aggregate": {
            "comparable_epochs": 0,
            "successful_epochs": 0,
            "success_rate": None,
            "representative": False,
            "status": "BASELINE_ONLY",
        },
        "epochs": [epoch],
    })
    assert validated["epochs"][0]["accepted_comparable"] is False


def test_failure_outcome_is_persisted_on_epoch() -> None:
    payload = _epoch()
    detail = _apply_failure_outcome(
        payload,
        MCPToolError("mechanical_bom failed"),
        operation="mechanical_bom",
        human_capture_observed=True,
    )
    assert payload["failure"] == detail


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
    epoch = _epoch(main_sha=_GIT_SHA_D)
    with pytest.raises(M2BenchmarkError, match="binding"):
        append_m2_epoch(record, epoch)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("main_sha", _GIT_SHA_D),
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
        main_sha=_GIT_SHA_A,
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
        ("main_sha", _GIT_SHA_D),
        ("profile_revision", "r2"),
        ("fixture_id", "fixture-2"),
        ("fixture_input_sha256", _SHA_D),
        ("staged_dxf_sha256", _SHA_D),
    ],
)
def test_new_record_with_real_hashes_rejects_epoch_mismatches(field: str, value: object) -> None:
    record = new_m2_record(
        benchmark_id="m2-mechanical",
        main_sha=_GIT_SHA_A,
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
    result = aggregate_m2_epochs([_epoch(
        accepted_comparable=False,
        success=False,
        headless=_review(status="SKIP"),
        live=_review(status="SKIP"),
        negative_probes=[{
            "kind": "stale_evidence",
            "count": 1,
            "captured": False,
            "operation": "load_build_evidence",
            "category": "not_run",
            "detail": "not run",
        }],
        cleanup={"closed_without_save": True, "source_unchanged": True, "staged_unchanged": True, "release_verified": True},
    )])
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


def test_m2_live_component_expectations_follow_written_builder_truth(tmp_path: Path) -> None:
    fixture = build_m2_fixture(tmp_path)

    assert m2_live._expected_component_bom(fixture) == [
        {
            "block_name": "COMP_FRAME_BEAM",
            "attributes": [
                {"tag": "PART_ID", "value": "part-001"},
                {"tag": "LENGTH_MM", "value": "100.00"},
                {"tag": "PROFILE", "value": "unknown"},
            ],
        }
    ]


def test_m2_live_bom_attribute_order_is_not_semantic() -> None:
    expected = [
        {"tag": "PART_ID", "value": "part-001"},
        {"tag": "LENGTH_MM", "value": "100.00"},
        {"tag": "PROFILE", "value": "unknown"},
    ]
    observed = [expected[1], expected[0], expected[2]]

    assert m2_live._bom_attributes_equal(expected, observed)


def test_m2_fixture_support_is_reproducible_across_fresh_roots(tmp_path: Path) -> None:
    first = build_m2_fixture(tmp_path / "first")
    second = build_m2_fixture(tmp_path / "second")

    assert first.input_sha256 == second.input_sha256
    assert first.staged_dxf_sha256 == second.staged_dxf_sha256
    assert first.staged_dxf.read_bytes() == second.staged_dxf.read_bytes()
    assert hashlib.sha256(first.staged_dxf.read_bytes()).hexdigest() == first.staged_dxf_sha256
    assert hashlib.sha256(second.staged_dxf.read_bytes()).hexdigest() == second.staged_dxf_sha256


def test_m2_fixture_support_is_stable_across_python_hash_seeds(tmp_path: Path) -> None:
    hashes: list[str] = []
    for seed in ("0", "4"):
        root = tmp_path / f"seed-{seed}"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    "from tests.m2_benchmark_support import build_m2_fixture; "
                    f"print(build_m2_fixture(Path(r'{root}')).staged_dxf_sha256)"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        hashes.append(result.stdout.strip().splitlines()[-1])

    assert hashes[0] == hashes[1]


def test_m2_fixture_reviews_the_final_normalized_dxf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reviewed_bytes: list[bytes] = []
    original_review = m2_fixture_support.review_dxf

    def review_and_capture(build: object):
        reviewed_bytes.append(Path(build.output_path).read_bytes())
        return original_review(build)

    monkeypatch.setattr(m2_fixture_support, "review_dxf", review_and_capture)
    fixture = build_m2_fixture(tmp_path)

    assert len(reviewed_bytes) == 2
    assert reviewed_bytes[-1] == fixture.staged_dxf.read_bytes()


def test_m2_fixture_support_freezes_known_dynamic_header_values(tmp_path: Path) -> None:
    fixture = build_m2_fixture(tmp_path)
    data = fixture.staged_dxf.read_bytes()

    for variable in (b"$TDCREATE", b"$TDUCREATE", b"$TDUPDATE", b"$TDUUPDATE"):
        assert b"  9\r\n" + variable + b"\r\n 40\r\n2451544.5\r\n" in data

    assert b"  9\r\n$TDINDWG\r\n 40\r\n0.0\r\n" in data
    assert b"\r\nLINE\r\n" in data
    assert b"COMP_FRAME_BEAM" in data
    assert b"\r\nDIMENSION\r\n" in data


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


def test_cleanup_uses_distinct_source_and_staged_hashes(tmp_path: Path) -> None:
    fixture = build_m2_fixture(tmp_path / "fixture")
    fixture_root = tmp_path / "fixture"
    drawing_root = tmp_path / "drawing-root"
    probe_root = tmp_path / "probe-root"
    drawing_root.mkdir()
    probe_root.mkdir()
    drawing_path = drawing_root / "staged.dxf"
    drawing_path.write_bytes(fixture.staged_dxf.read_bytes())
    ipc_dir = tmp_path / "ipc"
    ipc_dir.mkdir()

    class FakeDotNetClient:
        def close_disposable(
            self,
            drawing_full_path: str,
            *,
            disposable: bool,
            save_changes: bool,
            request_id: str,
        ) -> dict[str, object]:
            return {
                "success": True,
                "changed": False,
                "payload": {"closed_without_saving": True},
            }

    cleanup = _cleanup_epoch_artifacts(
        dotnet_client=FakeDotNetClient(),
        input_path=fixture.input_path,
        drawing_path=drawing_path,
        expected_full_path=r"C:\temp\staged.dxf",
        before_input_sha256=fixture.input_sha256,
        before_staged_sha256=fixture.staged_dxf_sha256,
        request_ids=(),
        drawing_root=drawing_root,
        probe_root=probe_root,
        fixture_root=fixture_root,
        ipc_dir=ipc_dir,
        close_request_id="close-id",
    )

    assert cleanup["source_unchanged"] is True
    assert cleanup["staged_unchanged"] is True


@pytest.mark.parametrize(
    ("mutate_input", "before_input_sha256", "before_staged_sha256", "expected_source", "expected_staged"),
    [
        (True, None, None, False, True),
        (False, "0" * 64, None, False, True),
        (False, None, "0" * 64, True, False),
    ],
)
def test_cleanup_refuses_false_truth_when_input_or_staged_hashes_do_not_match(
    tmp_path: Path,
    mutate_input: bool,
    before_input_sha256: str | None,
    before_staged_sha256: str | None,
    expected_source: bool,
    expected_staged: bool,
) -> None:
    fixture = build_m2_fixture(tmp_path / "fixture")
    fixture_root = tmp_path / "fixture"
    drawing_root = tmp_path / "drawing-root"
    probe_root = tmp_path / "probe-root"
    drawing_root.mkdir()
    probe_root.mkdir()
    input_copy = tmp_path / "input.json"
    input_copy.write_bytes(fixture.input_path.read_bytes())
    drawing_path = drawing_root / "staged.dxf"
    drawing_path.write_bytes(fixture.staged_dxf.read_bytes())
    if mutate_input:
        input_copy.write_bytes(input_copy.read_bytes() + b"\nchanged")
    ipc_dir = tmp_path / "ipc"
    ipc_dir.mkdir()

    class FakeDotNetClient:
        def close_disposable(
            self,
            drawing_full_path: str,
            *,
            disposable: bool,
            save_changes: bool,
            request_id: str,
        ) -> dict[str, object]:
            return {
                "success": True,
                "changed": False,
                "payload": {"closed_without_saving": True},
            }

    cleanup = _cleanup_epoch_artifacts(
        dotnet_client=FakeDotNetClient(),
        input_path=input_copy,
        drawing_path=drawing_path,
        expected_full_path=r"C:\temp\staged.dxf",
        before_input_sha256=before_input_sha256 or fixture.input_sha256,
        before_staged_sha256=before_staged_sha256 or fixture.staged_dxf_sha256,
        request_ids=(),
        drawing_root=drawing_root,
        probe_root=probe_root,
        fixture_root=fixture_root,
        ipc_dir=ipc_dir,
        close_request_id="close-id",
    )

    assert cleanup["source_unchanged"] is expected_source
    assert cleanup["staged_unchanged"] is expected_staged


def test_m2_human_events_json_parses_and_rejects_invalid_payloads() -> None:
    events = _parse_human_events_json('[{"kind":"NETLOAD","count":1,"detail":"manual"}]')
    assert events == [{"kind": "NETLOAD", "count": 1, "detail": "manual"}]

    with pytest.raises(ValueError, match="human events"):
        _parse_human_events_json("")
    assert _parse_human_events_json("[]") == []
    with pytest.raises(ValueError, match="human events"):
        _parse_human_events_json('[{"kind":"NETLOAD","count":0}]')


def test_m2_missing_capture_is_non_comparable_not_zero() -> None:
    record = new_m2_record(
        benchmark_id="m2-mechanical",
        main_sha=_GIT_SHA_A,
        profile_id=M2_MECHANICAL_BENCHMARK_PROFILE_ID,
        profile_revision=M2_MECHANICAL_BENCHMARK_PROFILE_REVISION,
        fixture_id="fixture-1",
        fixture_input_sha256=_SHA_B,
        staged_dxf_sha256=_SHA_C,
    )
    epoch = _record()["epochs"][0]
    epoch["human"]["events"] = []
    epoch["human"]["count"] = 0
    epoch["human"]["captured"] = False
    epoch["accepted_comparable"] = False
    epoch["success"] = False
    epoch["headless"]["status"] = "NOT_RUN"
    epoch["live"]["status"] = "NOT_RUN"
    epoch["negative_probes"] = [
        {
            "kind": "stale_evidence",
            "count": 0,
            "captured": False,
            "operation": "load_build_evidence",
            "category": "not_run",
            "detail": "not run",
        },
        {
            "kind": "wrong_target",
            "count": 0,
            "captured": False,
            "operation": "health",
            "category": "not_run",
            "detail": "not run",
        },
    ]
    epoch["cleanup"] = {
        "closed_without_save": True,
        "source_unchanged": True,
        "staged_unchanged": True,
        "release_verified": True,
    }

    validated = validate_m2_record({
        **record,
        "aggregate": {
            "comparable_epochs": 0,
            "successful_epochs": 0,
            "success_rate": None,
            "representative": False,
            "status": "BASELINE_ONLY",
        },
        "epochs": [epoch],
    })
    assert validated["epochs"][0]["human"]["captured"] is False


@pytest.mark.parametrize("category", ["dotnet_timeout", "dotnet_protocol", "tool", "timeout"])
def test_m2_accepted_wrong_target_requires_semantic_refusal(category: str) -> None:
    record = _record()
    record["epochs"][0]["negative_probes"][1]["category"] = category

    with pytest.raises(ValueError, match="category"):
        validate_m2_record(record)


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
        _load_existing_m2_record(record_path, main_sha=_GIT_SHA_D)


def test_persist_epoch_record_writes_schema_valid_record_and_appends_existing_epochs(
    tmp_path: Path,
) -> None:
    fixture = build_m2_fixture(tmp_path / "fixture")
    record_path = tmp_path / "m2-record.json"
    first = _initial_epoch(
        session_id="session-a",
        main_sha=_GIT_SHA_A,
        fixture=fixture,
        human_events=[_event("NETLOAD", 1)],
    )
    first["headless"] = _review()
    first["live"] = _review()
    first["negative_probes"] = [
        {
            "kind": "stale_evidence",
            "count": 1,
            "captured": True,
            "operation": "load_build_evidence",
            "category": "stale_evidence",
            "detail": "stale evidence was rejected",
        },
        {
            "kind": "wrong_target",
            "count": 1,
            "captured": True,
            "operation": "wrong_target",
            "category": "dotnet_result",
            "detail": "wrong target was rejected",
        },
    ]
    first["cleanup"] = {
        "closed_without_save": True,
        "source_unchanged": True,
        "staged_unchanged": True,
        "release_verified": True,
    }
    first["environment"] = {
        "captured": True,
        "autocad_product": "AutoCAD Mechanical 2027",
        "plugin_version": "1.0.0",
        "python_version": "3.11.9",
        "ipc_root_id": "ipc-root-001",
        "runtime_identity": "acad-pid-100-hwnd-200",
        "implementation_sha": _GIT_SHA_A,
        "pr_head_sha": _GIT_SHA_A,
        "harness_sha": _GIT_SHA_A,
        "plugin_binary_sha256": _SHA_D,
    }
    first["transport"] = [
        {"name": "fileipc", "attempts": 1, "successes": 1, "failures": 0},
        {"name": "dotnetipc", "attempts": 1, "successes": 1, "failures": 0},
        {"name": "live_review", "attempts": 1, "successes": 1, "failures": 0},
    ]
    first["accepted_comparable"] = True
    first["success"] = True

    persisted = _persist_epoch_record(
        record_path,
        main_sha=_GIT_SHA_A,
        fixture=fixture,
        epoch=first,
    )
    assert validate_m2_record(persisted) == persisted
    assert json.loads(record_path.read_text(encoding="utf-8")) == persisted

    second = copy.deepcopy(first)
    second["session_id"] = "session-b"
    second["started_at"] = "2026-08-30T10:06:00Z"
    second["finished_at"] = "2026-08-30T10:07:00Z"
    appended = _persist_epoch_record(
        record_path,
        main_sha=_GIT_SHA_A,
        fixture=fixture,
        epoch=second,
    )
    assert len(appended["epochs"]) == 2
    assert appended["epochs"][0]["session_id"] == "session-a"
    assert appended["epochs"][1]["session_id"] == "session-b"


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (MCPTimeoutError("timed out"), "timeout"),
        (MCPToolError("mechanical_bom failed"), "tool"),
        (
            DotNetIPCResultError(
                "wrong target",
                result={"operation": "mechanical_bom", "errors": ["WRONG_TARGET"]},
            ),
            "dotnet_result",
        ),
        (DotNetIPCTimeoutError("dotnet timed out"), "dotnet_timeout"),
        (DotNetIPCProtocolError("invalid result identity"), "dotnet_protocol"),
    ],
)
def test_failure_after_human_capture_clears_false_green_and_retains_category(
    tmp_path: Path,
    error: Exception,
    category: str,
) -> None:
    fixture = build_m2_fixture(tmp_path / "fixture")
    epoch = _initial_epoch(
        session_id="session-a",
        main_sha=_GIT_SHA_A,
        fixture=fixture,
        human_events=[_event("NETLOAD", 1)],
    )
    epoch["accepted_comparable"] = True
    epoch["success"] = True

    detail = _apply_failure_outcome(
        epoch,
        error,
        operation="mechanical_bom",
        human_capture_observed=True,
    )

    assert detail == {
        "operation": "mechanical_bom",
        "category": category,
        "message": str(error),
    }
    assert epoch["accepted_comparable"] is False
    assert epoch["success"] is False
    assert epoch["failure"] == detail


def test_late_failure_does_not_overwrite_existing_causal_detail() -> None:
    epoch = _epoch(accepted_comparable=True, success=True)
    causal_detail = {
        "operation": "configuration",
        "category": "missing_opt_in",
        "message": "CAD_AGENT_M2_RECORD_PATH",
    }
    epoch["failure"] = causal_detail

    _apply_failure_outcome(
        epoch,
        AssertionError("late comparability failure"),
        operation="m2-live",
        human_capture_observed=True,
    )

    assert epoch["accepted_comparable"] is False
    assert epoch["success"] is False
    assert epoch["failure"] == causal_detail


def test_stale_evidence_probe_uses_real_refusal_and_observed_counter(tmp_path: Path) -> None:
    fixture = build_m2_fixture(tmp_path / "fixture")
    probe = _exercise_stale_evidence_rejection(fixture, tmp_path / "probe")

    assert probe["kind"] == "stale_evidence"
    assert probe["captured"] is True
    assert probe["count"] == 1
    assert "SHA-256" in probe["detail"]


def test_persist_m2_measurements_artifact_writes_sidecar_json(tmp_path: Path) -> None:
    record_path = tmp_path / "m2-record.json"

    artifact = _persist_m2_measurements_artifact(
        record_path,
        main_sha=_GIT_SHA_A,
        measurements={"request_result_bytes": 123, "entity_query_count": 2},
    )

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload == {
        "kind": "m2_mechanical_measurements",
        "record_path": str(record_path),
        "main_sha": _GIT_SHA_A,
        "reference_decision": "Task 4 should consume this sidecar because the closed M2 record cannot accept extra fields.",
        "measurements": {"request_result_bytes": 123, "entity_query_count": 2},
    }


def test_measurements_sidecar_writes_outside_repo_and_survives_failure(tmp_path: Path) -> None:
    record_path = tmp_path / "records" / "m2-record.json"
    record_path.parent.mkdir(parents=True)

    artifact = _persist_m2_measurements_artifact(
        record_path,
        main_sha=_GIT_SHA_A,
        measurements={"request_result_bytes": 0, "entity_query_count": 0},
    )

    assert artifact.parent == record_path.parent
    assert artifact.suffix == ".json"
    assert artifact.name.endswith(".measurements.json")
    assert not artifact.is_relative_to(Path(__file__).resolve().parents[1])
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["kind"] == "m2_mechanical_measurements"
    assert "secret" not in json.dumps(payload)

    second = _persist_m2_measurements_artifact(
        record_path,
        main_sha=_GIT_SHA_A,
        measurements={"request_result_bytes": 7, "entity_query_count": 3},
    )
    assert second == artifact
    assert json.loads(second.read_text(encoding="utf-8"))["measurements"] == {
        "request_result_bytes": 7,
        "entity_query_count": 3,
    }


def test_current_main_sha_uses_origin_main_from_a_feature_branch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_output(repo, "init", "-b", "main")
    _git_output(repo, "config", "user.email", "tests@example.invalid")
    _git_output(repo, "config", "user.name", "M2 benchmark tests")
    (repo / "state.txt").write_text("main\n", encoding="utf-8")
    _git_output(repo, "add", "state.txt")
    _git_output(repo, "commit", "-m", "main base")
    main_sha = _git_output(repo, "rev-parse", "HEAD")
    _git_output(repo, "switch", "-c", "codex/m2-mechanical-benchmark")
    (repo / "state.txt").write_text("feature\n", encoding="utf-8")
    _git_output(repo, "add", "state.txt")
    _git_output(repo, "commit", "-m", "feature change")
    feature_sha = _git_output(repo, "rev-parse", "HEAD")
    _git_output(repo, "branch", "-D", "main")
    _git_output(repo, "update-ref", "refs/remotes/origin/main", main_sha)
    monkeypatch.setattr(
        "mcp_integration_lib.tests.test_m2_mechanical_benchmark_live._REPO_ROOT",
        repo,
    )
    monkeypatch.setenv("GITHUB_SHA", feature_sha)

    assert len(main_sha) == 40
    assert len(feature_sha) == 40
    assert _current_main_sha() == main_sha
    assert _current_main_sha() != feature_sha


def test_current_main_sha_fails_closed_when_origin_main_ref_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_output(repo, "init", "-b", "codex/m2-mechanical-benchmark")
    monkeypatch.setattr(
        "mcp_integration_lib.tests.test_m2_mechanical_benchmark_live._REPO_ROOT",
        repo,
    )
    monkeypatch.setenv("GITHUB_SHA", "2" * 40)

    with pytest.raises(RuntimeError, match="current main SHA"):
        _current_main_sha()


def test_current_main_sha_fails_closed_when_origin_main_output_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_SHA", "2" * 40)

    def fake_run(*args, **kwargs):
        assert args[0] == [
            "git",
            "rev-parse",
            "--verify",
            "origin/main^{commit}",
        ]
        return subprocess.CompletedProcess(args[0], 0, stdout=f"{_SHA_C}\n", stderr="")

    monkeypatch.setattr(
        "mcp_integration_lib.tests.test_m2_mechanical_benchmark_live.subprocess.run",
        fake_run,
    )

    with pytest.raises(RuntimeError, match="current main SHA"):
        _current_main_sha()


def test_wrong_target_probe_uses_second_drawing_and_observed_refusal(tmp_path: Path) -> None:
    observed_paths: list[str] = []
    transport = _transport_counters()

    class FakeLegacyClient:
        def drawing_open(self, drawing_path: str) -> None:
            observed_paths.append(drawing_path)

        def drawing_close(self, save_changes: bool = False) -> None:
            assert save_changes is False

    class FakeDotNetClient:
        def health(self, drawing_full_path: str, *, request_id: str) -> dict[str, object]:
            raise DotNetIPCResultError(
                "wrong target identity",
                result={
                    "operation": "health",
                    "drawing_full_path": drawing_full_path,
                    "request_id": request_id,
                    "success": False,
                    "errors": [
                        "The requested drawing_full_path does not match the active document full path."
                    ],
                },
            )

        def close_disposable(
            self,
            _drawing_full_path: str,
            *,
            disposable: bool,
            save_changes: bool,
            request_id: str,
        ) -> dict[str, object]:
            assert disposable is True
            assert save_changes is False
            assert request_id.endswith("-close")
            return {
                "success": True,
                "changed": False,
                "payload": {"closed_without_saving": True},
            }

    intended = tmp_path / "intended.dxf"
    wrong = tmp_path / "wrong.dxf"
    intended.write_text("intended", encoding="utf-8")
    wrong.write_text("wrong", encoding="utf-8")

    probe = _exercise_wrong_target_rejection(
        legacy_client=FakeLegacyClient(),
        dotnet_client=FakeDotNetClient(),
        transport=transport,
        intended_full_path=r"C:\temp\intended.dxf",
        second_drawing_path=wrong,
        reopen_drawing_path=intended,
        request_id="wrong-target-probe",
    )

    assert probe["kind"] == "wrong_target"
    assert probe["captured"] is True
    assert probe["count"] == 1
    assert probe["operation"] == "wrong_target"
    assert probe["category"] == "dotnet_result"
    assert observed_paths == [str(wrong), str(intended)]
    assert _transport_records(transport) == [
        {"name": "fileipc", "attempts": 2, "successes": 2, "failures": 0},
        {"name": "dotnetipc", "attempts": 2, "successes": 2, "failures": 0},
    ]


def test_wrong_target_probe_does_not_treat_timeout_as_semantic_refusal(tmp_path: Path) -> None:
    transport = _transport_counters()

    class FakeLegacyClient:
        def drawing_open(self, _drawing_path: str) -> None:
            return None

        def drawing_close(self, save_changes: bool = False) -> None:
            assert save_changes is False

    class FakeDotNetClient:
        def health(self, _drawing_full_path: str, *, request_id: str) -> dict[str, object]:
            _ = request_id
            raise DotNetIPCTimeoutError("health timed out")

        def close_disposable(
            self,
            _drawing_full_path: str,
            *,
            disposable: bool,
            save_changes: bool,
            request_id: str,
        ) -> dict[str, object]:
            assert disposable is True
            assert save_changes is False
            assert request_id.endswith("-close")
            return {
                "success": True,
                "changed": False,
                "payload": {"closed_without_saving": True},
            }

    intended = tmp_path / "intended.dxf"
    wrong = tmp_path / "wrong.dxf"
    intended.write_text("intended", encoding="utf-8")
    wrong.write_text("wrong", encoding="utf-8")

    probe = _exercise_wrong_target_rejection(
        legacy_client=FakeLegacyClient(),
        dotnet_client=FakeDotNetClient(),
        transport=transport,
        intended_full_path=r"C:\temp\intended.dxf",
        second_drawing_path=wrong,
        reopen_drawing_path=intended,
        request_id="wrong-target-timeout",
    )

    assert probe["captured"] is False
    assert probe["count"] == 0
    assert probe["category"] == "dotnet_timeout"
    assert _transport_records(transport) == [
        {"name": "fileipc", "attempts": 2, "successes": 2, "failures": 0},
        {"name": "dotnetipc", "attempts": 2, "successes": 1, "failures": 1},
    ]


def test_missing_opt_in_inputs_are_reported_explicitly_without_false_green(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    record_path = tmp_path / "m2-record.json"
    monkeypatch.setenv(M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV, str(record_path))
    monkeypatch.delenv(M2_MECHANICAL_BENCHMARK_SESSION_ID_ENV, raising=False)
    monkeypatch.delenv(M2_MECHANICAL_BENCHMARK_HUMAN_EVENTS_ENV, raising=False)

    missing = _missing_m2_opt_in_inputs()

    assert missing == [
        M2_MECHANICAL_BENCHMARK_SESSION_ID_ENV,
        M2_MECHANICAL_BENCHMARK_HUMAN_EVENTS_ENV,
    ]


def test_missing_record_path_reports_skip_instead_of_false_green(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV, raising=False)
    monkeypatch.setenv(M2_MECHANICAL_BENCHMARK_SESSION_ID_ENV, "session-a")
    monkeypatch.setenv(
        M2_MECHANICAL_BENCHMARK_HUMAN_EVENTS_ENV,
        '[{"kind":"NETLOAD","count":1}]',
    )

    with pytest.raises(unittest.SkipTest, match="record path"):
        _record_path_from_env()


def test_relative_record_path_is_rejected_before_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV, "relative-m2-record.json")
    with pytest.raises(ValueError, match="absolute"):
        _record_path_from_env()


def test_cleanup_reports_observed_truth_and_removes_exact_directories(
    tmp_path: Path,
) -> None:
    drawing_root = tmp_path / "drawing-root"
    probe_root = tmp_path / "probe-root"
    fixture_root = tmp_path / "fixture-root"
    drawing_root.mkdir()
    probe_root.mkdir()
    fixture_root.mkdir()
    input_path = tmp_path / "input.json"
    input_path.write_text("fixture", encoding="utf-8")
    drawing_path = drawing_root / "staged.dxf"
    drawing_path.write_text("fixture", encoding="utf-8")
    drawing_sha = sha256_file(drawing_path)
    input_sha = sha256_file(input_path)

    ipc_dir = tmp_path / "ipc"
    ipc_dir.mkdir()
    for request_id in ("close-id",):
        (ipc_dir / request_path(ipc_dir, request_id).name).write_text("req", encoding="utf-8")
        (ipc_dir / result_path(ipc_dir, request_id).name).write_text("res", encoding="utf-8")

    close_calls: list[tuple[str, bool, bool, str]] = []

    class FakeDotNetClient:
        def close_disposable(
            self,
            drawing_full_path: str,
            *,
            disposable: bool,
            save_changes: bool,
            request_id: str,
        ) -> dict[str, object]:
            close_calls.append((drawing_full_path, disposable, save_changes, request_id))
            request_path(ipc_dir, request_id).unlink(missing_ok=True)
            result_path(ipc_dir, request_id).unlink(missing_ok=True)
            return {
                "success": True,
                "changed": False,
                "payload": {"closed_without_saving": True},
            }

    cleanup = _cleanup_epoch_artifacts(
        dotnet_client=FakeDotNetClient(),
        input_path=input_path,
        drawing_path=drawing_path,
        expected_full_path=r"C:\temp\staged.dxf",
        before_input_sha256=input_sha,
        before_staged_sha256=drawing_sha,
        request_ids=("close-id",),
        drawing_root=drawing_root,
        probe_root=probe_root,
        fixture_root=fixture_root,
        ipc_dir=ipc_dir,
        close_request_id="close-id",
    )

    assert cleanup == {
        "closed_without_save": True,
        "source_unchanged": True,
        "staged_unchanged": True,
        "release_verified": True,
    }
    assert close_calls == [(r"C:\temp\staged.dxf", True, False, "close-id")]
    assert not drawing_root.exists()
    assert not probe_root.exists()
    assert not fixture_root.exists()


def test_transport_helpers_preserve_observed_attempts() -> None:
    counters = _transport_counters()
    counters["fileipc"]["attempts"] += 1
    counters["fileipc"]["successes"] += 1
    counters["dotnetipc"]["attempts"] += 2
    counters["dotnetipc"]["failures"] += 1
    counters["live_review"]["attempts"] += 1
    counters["live_review"]["successes"] += 1

    assert _transport_records(counters) == [
        {"name": "fileipc", "attempts": 1, "successes": 1, "failures": 0},
        {"name": "dotnetipc", "attempts": 2, "successes": 0, "failures": 1},
        {"name": "live_review", "attempts": 1, "successes": 1, "failures": 0},
    ]


@pytest.mark.parametrize(
    ("operation", "expected_transport", "error"),
    [
        ("drawing_open", "fileipc", MCPTimeoutError("drawing open timed out")),
        ("drawing_get_variables", "fileipc", MCPTimeoutError("drawing variables timed out")),
        ("health", "dotnetipc", MCPToolError("health failed")),
        ("mechanical_bom", "dotnetipc", DotNetIPCTimeoutError("BOM timed out")),
        (
            "wrong_target",
            "live_review",
            DotNetIPCResultError(
                "wrong target",
                result={"operation": "wrong_target", "errors": ["WRONG_TARGET"]},
            ),
        ),
        ("review", "live_review", DotNetIPCProtocolError("review protocol failed")),
    ],
)
def test_metadata_free_live_failure_retains_operation_through_counter_path(
    operation: str,
    expected_transport: str,
    error: Exception,
) -> None:
    epoch = _epoch(accepted_comparable=True, success=True)
    transport = _transport_counters()
    transport[expected_transport]["attempts"] = 1

    detail = m2_live._record_m2_failure(
        epoch,
        transport,
        error,
        current_operation=operation,
        human_capture_observed=True,
    )

    assert detail["operation"] == operation
    assert epoch["accepted_comparable"] is False
    assert epoch["success"] is False
    assert _transport_records(transport) == [
        {
            "name": expected_transport,
            "attempts": 1,
            "successes": 0,
            "failures": 1,
        }
    ]


@pytest.mark.parametrize(
    ("operation", "expected_transport"),
    [
        ("m2-live", "fileipc"),
        ("drawing_open", "fileipc"),
        ("drawing_get_variables", "fileipc"),
        ("health", "dotnetipc"),
        ("mechanical_bom", "dotnetipc"),
        ("wrong_target", "live_review"),
        ("review", "live_review"),
        ("load_build_evidence", "live_review"),
    ],
)
def test_m2_failure_operation_maps_to_transport(
    operation: str,
    expected_transport: str,
) -> None:
    assert _transport_for_operation(operation) == expected_transport


def test_request_artifacts_removed_requires_every_request_and_result(tmp_path: Path) -> None:
    ipc_dir = tmp_path / "ipc"
    ipc_dir.mkdir()
    request_ids = ("one", "two")
    for request_id in request_ids:
        request_path(ipc_dir, request_id).write_text("req", encoding="utf-8")
        result_path(ipc_dir, request_id).write_text("res", encoding="utf-8")

    assert _request_artifacts_removed(ipc_dir, request_ids) is False

    for request_id in request_ids:
        request_path(ipc_dir, request_id).unlink()
        result_path(ipc_dir, request_id).unlink()

    assert _request_artifacts_removed(ipc_dir, request_ids) is True


def test_copy_review_result_maps_live_review_metrics_without_inventing_counts() -> None:
    live = LiveReviewResult(
        passed=True,
        structural_checked=3,
        geometry_checked=2,
        dimension_checked=1,
        geometry_degraded=False,
        mismatches=[],
        warnings=[],
    )
    bom = {"payload": {"component_count": 1}}

    copied = _copy_review_result(live, component_checked=1, component_mismatches=0)

    assert copied == {
        "status": "PASS",
        "counts": {
            "primitive": {"checked": 3, "mismatches": 0},
            "component": {"checked": 1, "mismatches": 0},
            "dimension": {"checked": 1, "mismatches": 0},
        },
        "degraded": False,
        "geometry_checked": 2,
        "mismatches": [],
        "warnings": [],
    }
