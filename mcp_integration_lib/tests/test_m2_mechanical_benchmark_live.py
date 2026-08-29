"""Opt-in disposable AutoCAD Mechanical benchmark harness for M2."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cad_agent.live import LiveSafetyError, load_build_evidence, write_live_report
from cad_agent.manifest import sha256_file
from cad_agent.m2_benchmark import append_m2_epoch, new_m2_record, validate_m2_record
from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCClient,
    DotNetIPCResultError,
    make_windows_dotnet_dispatch_trigger,
    normalize_windows_absolute_path,
    request_path,
    result_path,
)
from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    MCPTimeoutError,
    MCPToolError,
    make_windows_dispatch_trigger,
    make_windows_lisp_trigger,
)
from mcp_integration_lib.reviewer2 import LiveReviewResult, review_dxf_live
from mcp_integration_lib.tests.test_dotnet_ipc_live import (
    _cleanup_disposable_fixture_directory,
    _live_prerequisites_available as _core_live_prerequisites_available,
    _wait_for_disposable_drawing_release,
)
from tests.m2_benchmark_support import build_m2_fixture, headless_metrics


M2_MECHANICAL_BENCHMARK_PROFILE_ID = "M2_MECHANICAL_REVIEW_V1"
M2_MECHANICAL_BENCHMARK_PROFILE_REVISION = "r1"
M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV = "CAD_AGENT_M2_RECORD_PATH"
M2_MECHANICAL_BENCHMARK_SESSION_ID_ENV = "CAD_AGENT_M2_SESSION_ID"
M2_MECHANICAL_BENCHMARK_HUMAN_EVENTS_ENV = "CAD_AGENT_M2_HUMAN_EVENTS_JSON"
M2_MECHANICAL_BENCHMARK_MISSING_CAPTURE_KIND = "human_events_missing"
M2_MECHANICAL_BENCHMARK_MISSING_SESSION_KIND = "session_id_missing"
M2_MECHANICAL_BENCHMARK_FIXTURE_ID = "fixture-1"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _json_size(value: object) -> int:
    return len(
        json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    )


def _missing_m2_opt_in_inputs() -> list[str]:
    missing: list[str] = []
    for name in (
        M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV,
        M2_MECHANICAL_BENCHMARK_SESSION_ID_ENV,
        M2_MECHANICAL_BENCHMARK_HUMAN_EVENTS_ENV,
    ):
        if not os.environ.get(name):
            missing.append(name)
    return missing


def _record_path_from_env() -> Path:
    raw = os.environ.get(M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV)
    if not raw:
        raise unittest.SkipTest(
            f"{M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV} is required for the opt-in M2 record path"
        )
    path = Path(raw).expanduser().resolve()
    if not path.is_absolute():
        raise ValueError("M2 record path must be absolute")
    if path.is_relative_to(_REPO_ROOT):
        raise ValueError("M2 record path must be outside the repository")
    return path


def _parse_human_events_json(raw: str | None) -> list[dict[str, object]]:
    if not raw:
        raise ValueError("human events JSON is required")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("human events JSON is invalid") from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError("human events JSON must be a non-empty list")
    events: list[dict[str, object]] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise ValueError(f"human events[{index}] must be an object")
        kind = entry.get("kind")
        count = entry.get("count")
        if not isinstance(kind, str) or not kind:
            raise ValueError(f"human events[{index}].kind must be a non-empty string")
        if type(count) is not int or count <= 0:
            raise ValueError(f"human events[{index}].count must be a positive integer")
        event: dict[str, object] = {"kind": kind, "count": count}
        if "detail" in entry:
            detail = entry["detail"]
            if not isinstance(detail, str) or not detail:
                raise ValueError(f"human events[{index}].detail must be a non-empty string")
            event["detail"] = detail
        events.append(event)
    return events


def _m2_live_prerequisites_available() -> bool:
    return _core_live_prerequisites_available() and not _missing_m2_opt_in_inputs()


def _load_existing_m2_record(path: Path, *, main_sha: str) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"existing M2 record is invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("existing M2 record must be a JSON object")
    existing_main_sha = payload.get("main_sha")
    if existing_main_sha is not None and existing_main_sha != main_sha:
        raise ValueError("existing M2 record belongs to another main SHA")
    return validate_m2_record(payload)


def _transport_counters() -> dict[str, dict[str, int | str]]:
    return {
        "fileipc": {"name": "fileipc", "attempts": 0, "successes": 0, "failures": 0},
        "dotnetipc": {"name": "dotnetipc", "attempts": 0, "successes": 0, "failures": 0},
        "live_review": {"name": "live_review", "attempts": 0, "successes": 0, "failures": 0},
    }


def _transport_records(
    counters: dict[str, dict[str, int | str]],
) -> list[dict[str, int | str]]:
    return [
        dict(counter)
        for key, counter in counters.items()
        if int(counter["attempts"]) > 0
        for counter in [counter]
    ]


def _request_artifacts_removed(
    ipc_dir: str | os.PathLike[str] | None,
    request_ids: tuple[str, ...],
) -> bool:
    return all(
        not request_path(ipc_dir, request_id).exists()
        and not result_path(ipc_dir, request_id).exists()
        for request_id in request_ids
    )


def _copy_review_result(
    review: LiveReviewResult,
    *,
    component_checked: int,
    component_mismatches: int,
) -> dict[str, object]:
    dimension_mismatches = sum(
        1 for message in review.mismatches if "dimension" in message.casefold()
    )
    primitive_mismatches = max(0, len(review.mismatches) - dimension_mismatches)
    return {
        "status": "PASS" if review.passed else "FAIL",
        "counts": {
            "primitive": {
                "checked": review.structural_checked,
                "mismatches": primitive_mismatches,
            },
            "component": {
                "checked": component_checked,
                "mismatches": component_mismatches,
            },
            "dimension": {
                "checked": review.dimension_checked,
                "mismatches": dimension_mismatches,
            },
        },
        "degraded": review.geometry_degraded,
    }


def _headless_epoch_result(fixture) -> dict[str, object]:
    metrics = headless_metrics(fixture)
    return {
        "status": str(metrics["status"]),
        "counts": {
            "primitive": {
                "checked": int(metrics["primitive_checked_count"]),
                "mismatches": int(metrics["primitive_mismatch_count"]),
            },
            "component": {
                "checked": int(metrics["component_checked_count"]),
                "mismatches": int(metrics["component_mismatch_count"]),
            },
            "dimension": {
                "checked": int(metrics["dimension_checked_count"]),
                "mismatches": int(metrics["dimension_mismatch_count"]),
            },
        },
        "degraded": False,
    }


def _initial_epoch(
    *,
    session_id: str,
    main_sha: str,
    fixture,
    human_events: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "session_id": session_id,
        "main_sha": main_sha,
        "profile_revision": M2_MECHANICAL_BENCHMARK_PROFILE_REVISION,
        "fixture_id": M2_MECHANICAL_BENCHMARK_FIXTURE_ID,
        "fixture_input_sha256": fixture.input_sha256,
        "staged_dxf_sha256": fixture.staged_dxf_sha256,
        "started_at": _timestamp(),
        "finished_at": _timestamp(),
        "wall_clock_seconds": 0.0,
        "human": {
            "events": human_events,
            "count": sum(int(event["count"]) for event in human_events),
        },
        "headless": {
            "status": "NOT_RUN",
            "counts": {
                "primitive": {"checked": 0, "mismatches": 0},
                "component": {"checked": 0, "mismatches": 0},
                "dimension": {"checked": 0, "mismatches": 0},
            },
            "degraded": False,
        },
        "live": {
            "status": "NOT_RUN",
            "counts": {
                "primitive": {"checked": 0, "mismatches": 0},
                "component": {"checked": 0, "mismatches": 0},
                "dimension": {"checked": 0, "mismatches": 0},
            },
            "degraded": False,
        },
        "transport": [],
        "negative_probes": [
            {"kind": "stale_evidence", "count": 0, "captured": False},
            {"kind": "wrong_target", "count": 0, "captured": False},
        ],
        "hashes": {
            "before": fixture.staged_dxf_sha256,
            "after": fixture.staged_dxf_sha256,
        },
        "mutation": {"save_attempts": 0, "repair_attempts": 0},
        "cleanup": {
            "closed_without_save": False,
            "source_unchanged": False,
            "staged_unchanged": False,
            "release_verified": False,
        },
        "accepted_comparable": False,
        "success": False,
    }


def _failure_category(error: Exception) -> str:
    if isinstance(error, MCPTimeoutError):
        return "timeout"
    if isinstance(error, MCPToolError):
        return "tool"
    if isinstance(error, DotNetIPCResultError):
        return "dotnet_result"
    return "unknown"


def _apply_failure_outcome(
    epoch: dict[str, object],
    error: Exception,
    *,
    operation: str,
    human_capture_observed: bool,
) -> dict[str, str]:
    _ = human_capture_observed
    epoch["accepted_comparable"] = False
    epoch["success"] = False
    return {
        "operation": operation,
        "category": _failure_category(error),
        "message": str(error),
    }


def _exercise_stale_evidence_rejection(fixture, probe_root: Path) -> dict[str, object]:
    probe_root.mkdir(parents=True, exist_ok=True)
    copied_evidence = probe_root / fixture.build_evidence.name
    copied_dxf = probe_root / fixture.staged_dxf.name
    copied_evidence.write_bytes(fixture.build_evidence.read_bytes())
    copied_dxf.write_bytes(fixture.staged_dxf.read_bytes() + b"\nchanged")
    try:
        load_build_evidence(copied_evidence, copied_dxf)
    except LiveSafetyError as exc:
        return {
            "kind": "stale_evidence",
            "count": 1,
            "captured": True,
            "detail": str(exc),
        }
    return {
        "kind": "stale_evidence",
        "count": 0,
        "captured": False,
        "detail": "stale evidence was not rejected",
    }


def _exercise_wrong_target_rejection(
    *,
    legacy_client: Any,
    dotnet_client: Any,
    intended_full_path: str,
    second_drawing_path: Path,
    reopen_drawing_path: Path,
    request_id: str,
) -> dict[str, object]:
    legacy_client.drawing_open(str(second_drawing_path))
    try:
        dotnet_client.health(intended_full_path, request_id=request_id)
    except (MCPTimeoutError, MCPToolError, DotNetIPCResultError) as exc:
        result = getattr(exc, "result", None)
        operation = str(result.get("operation", "health")) if isinstance(result, dict) else "health"
        return {
            "kind": "wrong_target",
            "count": 1,
            "captured": True,
            "operation": operation,
            "category": _failure_category(exc),
            "detail": str(exc),
        }
    finally:
        legacy_client.drawing_open(str(reopen_drawing_path))
    return {
        "kind": "wrong_target",
        "count": 0,
        "captured": False,
        "operation": "health",
        "category": "missing_refusal",
        "detail": "wrong target identity was not rejected",
    }


def _persist_epoch_record(
    record_path: Path,
    *,
    main_sha: str,
    fixture,
    epoch: dict[str, object],
) -> dict[str, object]:
    record = _load_existing_m2_record(record_path, main_sha=main_sha)
    if record:
        persisted = append_m2_epoch(record, epoch)
    else:
        persisted = append_m2_epoch(
            new_m2_record(
                benchmark_id="m2-mechanical",
                main_sha=main_sha,
                profile_id=M2_MECHANICAL_BENCHMARK_PROFILE_ID,
                profile_revision=M2_MECHANICAL_BENCHMARK_PROFILE_REVISION,
                fixture_id=M2_MECHANICAL_BENCHMARK_FIXTURE_ID,
                fixture_input_sha256=fixture.input_sha256,
                staged_dxf_sha256=fixture.staged_dxf_sha256,
            ),
            epoch,
        )
    validated = validate_m2_record(persisted)
    write_live_report(record_path, validated)
    return validated


def _cleanup_epoch_artifacts(
    *,
    dotnet_client: Any,
    drawing_path: Path,
    expected_full_path: str,
    before_source_sha256: str,
    before_staged_sha256: str,
    request_ids: tuple[str, ...],
    drawing_root: Path,
    probe_root: Path,
    ipc_dir: Path,
    close_request_id: str,
) -> dict[str, bool]:
    closed_without_save = False
    release_waited = False
    request_cleanup_ok = False
    try:
        close = dotnet_client.close_disposable(
            expected_full_path,
            disposable=True,
            save_changes=False,
            request_id=close_request_id,
        )
        closed_without_save = (
            bool(close.get("success"))
            and bool(close.get("payload", {}).get("closed_without_saving"))
            and close.get("changed") is False
        )
    except Exception:
        closed_without_save = False
    source_unchanged = drawing_path.is_file() and sha256_file(drawing_path) == before_source_sha256
    staged_unchanged = drawing_path.is_file() and sha256_file(drawing_path) == before_staged_sha256
    request_cleanup_ok = _request_artifacts_removed(ipc_dir, request_ids)
    try:
        _wait_for_disposable_drawing_release(drawing_path)
        release_waited = True
    except Exception:
        release_waited = False
    try:
        _cleanup_disposable_fixture_directory(
            drawing_root,
            drawing_path,
            original_sha256=before_staged_sha256,
        )
    except Exception:
        pass
    try:
        shutil.rmtree(probe_root)
    except FileNotFoundError:
        pass
    except OSError:
        release_waited = False
    release_verified = (
        closed_without_save
        and source_unchanged
        and staged_unchanged
        and request_cleanup_ok
        and release_waited
        and not drawing_root.exists()
        and not probe_root.exists()
    )
    return {
        "closed_without_save": closed_without_save,
        "source_unchanged": source_unchanged,
        "staged_unchanged": staged_unchanged,
        "release_verified": release_verified,
    }


def _current_main_sha() -> str:
    main_sha = (os.environ.get("GITHUB_SHA") or "0" * 64).strip().lower()
    if len(main_sha) != 64:
        return "0" * 64
    return main_sha


@unittest.skipUnless(
    _core_live_prerequisites_available(),
    "requires CAD_AGENT_FILE_IPC, CAD_AGENT_FILE_IPC_DIR, CAD_AGENT_DOTNET_IPC_DIR, "
    "CAD_AGENT_AUTOCAD_HWND, and CAD_AGENT_AUTOCAD_LISP_PATH",
)
@pytest.mark.autocad_mechanical
class M2MechanicalBenchmarkLiveTests(unittest.TestCase):
    def test_opt_in_m2_mechanical_epoch_is_read_only_and_reported(self) -> None:
        record_path = _record_path_from_env()
        if record_path.exists() and not record_path.is_file():
            raise ValueError("CAD_AGENT_M2_RECORD_PATH must point to a file")

        main_sha = _current_main_sha()
        fixture_root = Path(tempfile.mkdtemp(prefix="cad_agent_m2_fixture_", dir=r"C:\temp"))
        fixture = build_m2_fixture(fixture_root)
        human_events_raw = os.environ.get(M2_MECHANICAL_BENCHMARK_HUMAN_EVENTS_ENV)
        human_capture_observed = bool(human_events_raw)
        session_id = os.environ.get(M2_MECHANICAL_BENCHMARK_SESSION_ID_ENV, "").strip() or "missing-session-id"
        human_events = (
            _parse_human_events_json(human_events_raw)
            if human_capture_observed
            else [{"kind": M2_MECHANICAL_BENCHMARK_MISSING_CAPTURE_KIND, "count": 1}]
        )
        if session_id == "missing-session-id":
            human_events.append({"kind": M2_MECHANICAL_BENCHMARK_MISSING_SESSION_KIND, "count": 1})

        epoch = _initial_epoch(
            session_id=session_id,
            main_sha=main_sha,
            fixture=fixture,
            human_events=human_events,
        )
        epoch["headless"] = _headless_epoch_result(fixture)

        missing_opt_ins = [
            name
            for name in _missing_m2_opt_in_inputs()
            if name != M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV
        ]
        failure_detail: dict[str, str] | None = None
        transport = _transport_counters()
        entity_query_count = 0
        request_result_bytes = 0
        request_ids: list[str] = []
        drawing_root = Path(tempfile.mkdtemp(prefix="cad_agent_m2_epoch_", dir=r"C:\temp"))
        probe_root = Path(tempfile.mkdtemp(prefix="cad_agent_m2_probe_", dir=r"C:\temp"))
        drawing_path = drawing_root / "m2-live.dxf"
        drawing_path.write_bytes(fixture.staged_dxf.read_bytes())
        second_drawing_path = drawing_root / "wrong-target.dxf"
        second_drawing_path.write_bytes(fixture.staged_dxf.read_bytes())
        before_sha = sha256_file(drawing_path)
        epoch["hashes"]["before"] = before_sha
        monotonic_started = time.monotonic()
        expected_full_path = normalize_windows_absolute_path(str(drawing_path))

        close_request_id = f"m2-close-{time.time_ns()}"
        request_ids.append(close_request_id)
        try:
            if missing_opt_ins:
                failure_detail = {
                    "operation": "configuration",
                    "category": "missing_opt_in",
                    "message": ",".join(missing_opt_ins),
                }
                raise AssertionError("missing opt-in inputs")

            hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
            legacy_client = FileIPCLiveMCPClient(
                ipc_dir=os.environ["CAD_AGENT_FILE_IPC_DIR"],
                trigger=make_windows_dispatch_trigger(hwnd),
                raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
                bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
            )
            dotnet_client = DotNetIPCClient(
                ipc_dir=os.environ["CAD_AGENT_DOTNET_IPC_DIR"],
                trigger=make_windows_dotnet_dispatch_trigger(hwnd),
                timeout_s=20.0,
            )

            transport["fileipc"]["attempts"] = int(transport["fileipc"]["attempts"]) + 1
            legacy_client.drawing_open(str(drawing_path))
            transport["fileipc"]["successes"] = int(transport["fileipc"]["successes"]) + 1
            before_state = legacy_client.drawing_get_variables(["DBMOD", "DWGPREFIX", "DWGNAME"])

            health_request_id = f"m2-health-{time.time_ns()}"
            request_ids.append(health_request_id)
            transport["dotnetipc"]["attempts"] = int(transport["dotnetipc"]["attempts"]) + 1
            health = dotnet_client.health(expected_full_path, request_id=health_request_id)
            transport["dotnetipc"]["successes"] = int(transport["dotnetipc"]["successes"]) + 1
            request_result_bytes += _json_size(health)
            self.assertTrue(health["success"])
            self.assertFalse(health["changed"])
            self.assertEqual(expected_full_path, health["drawing_full_path"])

            bom_request_id = f"m2-bom-{time.time_ns()}"
            request_ids.append(bom_request_id)
            transport["dotnetipc"]["attempts"] = int(transport["dotnetipc"]["attempts"]) + 1
            bom = dotnet_client.mechanical_bom(expected_full_path, request_id=bom_request_id)
            transport["dotnetipc"]["successes"] = int(transport["dotnetipc"]["successes"]) + 1
            request_result_bytes += _json_size(bom)
            self.assertTrue(bom["success"])
            self.assertFalse(bom["changed"])
            self.assertEqual(expected_full_path, bom["drawing_full_path"])
            self.assertEqual([], bom["errors"])
            component_count = int(bom["payload"]["component_count"])
            self.assertGreaterEqual(component_count, 1)

            transport["live_review"]["attempts"] = int(transport["live_review"]["attempts"]) + 1
            review = review_dxf_live(fixture.build, legacy_client, open_drawing=False)
            transport["live_review"]["successes"] = int(transport["live_review"]["successes"]) + 1
            request_result_bytes += _json_size(review.__dict__)
            entity_query_count += 1
            epoch["live"] = _copy_review_result(
                review,
                component_checked=component_count,
                component_mismatches=0 if bom["success"] else 1,
            )

            stale_probe = _exercise_stale_evidence_rejection(fixture, probe_root)
            wrong_target_request_id = f"m2-wrong-target-{time.time_ns()}"
            request_ids.append(wrong_target_request_id)
            transport["dotnetipc"]["attempts"] = int(transport["dotnetipc"]["attempts"]) + 1
            wrong_target_probe = _exercise_wrong_target_rejection(
                legacy_client=legacy_client,
                dotnet_client=dotnet_client,
                intended_full_path=expected_full_path,
                second_drawing_path=second_drawing_path,
                reopen_drawing_path=drawing_path,
                request_id=wrong_target_request_id,
            )
            if wrong_target_probe["captured"]:
                transport["dotnetipc"]["failures"] = int(transport["dotnetipc"]["failures"]) + 1
            epoch["negative_probes"] = [
                {
                    "kind": str(stale_probe["kind"]),
                    "count": int(stale_probe["count"]),
                    "captured": bool(stale_probe["captured"]),
                },
                {
                    "kind": str(wrong_target_probe["kind"]),
                    "count": int(wrong_target_probe["count"]),
                    "captured": bool(wrong_target_probe["captured"]),
                },
            ]

            after_state = legacy_client.drawing_get_variables(["DBMOD", "DWGPREFIX", "DWGNAME"])
            self.assertEqual(before_state, after_state)
            self.assertEqual(before_sha, sha256_file(drawing_path))
        except (MCPTimeoutError, MCPToolError, DotNetIPCResultError) as exc:
            operation = "m2-live"
            result = getattr(exc, "result", None)
            if isinstance(result, dict) and isinstance(result.get("operation"), str):
                operation = result["operation"]
            failure_detail = _apply_failure_outcome(
                epoch,
                exc,
                operation=operation,
                human_capture_observed=human_capture_observed,
            )
            if operation == "health":
                transport["dotnetipc"]["failures"] = int(transport["dotnetipc"]["failures"]) + 1
            elif operation == "mechanical_bom":
                transport["dotnetipc"]["failures"] = int(transport["dotnetipc"]["failures"]) + 1
            else:
                transport["live_review"]["failures"] = int(transport["live_review"]["failures"]) + 1
        finally:
            epoch["finished_at"] = _timestamp()
            epoch["wall_clock_seconds"] = max(0.0, time.monotonic() - monotonic_started)
            epoch["hashes"]["after"] = sha256_file(drawing_path) if drawing_path.is_file() else before_sha
            cleanup = _cleanup_epoch_artifacts(
                dotnet_client=locals().get("dotnet_client"),
                drawing_path=drawing_path,
                expected_full_path=expected_full_path,
                before_source_sha256=before_sha,
                before_staged_sha256=before_sha,
                request_ids=tuple(request_ids),
                drawing_root=drawing_root,
                probe_root=probe_root,
                ipc_dir=Path(os.environ["CAD_AGENT_DOTNET_IPC_DIR"]),
                close_request_id=close_request_id,
            )
            epoch["cleanup"] = cleanup
            epoch["transport"] = _transport_records(transport)

            accepted_comparable = (
                not missing_opt_ins
                and human_capture_observed
                and epoch["headless"]["status"] == "PASS"
                and epoch["live"]["status"] == "PASS"
                and not epoch["live"]["degraded"]
                and all(probe["captured"] and probe["count"] > 0 for probe in epoch["negative_probes"])
                and all(bool(value) for value in cleanup.values())
            )
            epoch["accepted_comparable"] = accepted_comparable
            epoch["success"] = accepted_comparable
            persisted = _persist_epoch_record(
                record_path,
                main_sha=main_sha,
                fixture=fixture,
                epoch=epoch,
            )
            if not epoch["success"]:
                detail = failure_detail["message"] if failure_detail else "live benchmark evidence is non-comparable"
                raise AssertionError(
                    f"M2 live epoch is not successful: {detail}; comparable={persisted['aggregate']['comparable_epochs']}"
                )
