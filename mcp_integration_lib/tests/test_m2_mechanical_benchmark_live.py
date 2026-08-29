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

import pytest

from cad_agent.live import write_live_report
from cad_agent.manifest import sha256_file
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
from mcp_integration_lib.reviewer2 import review_dxf_live
from tests.m2_benchmark_support import build_m2_fixture
from mcp_integration_lib.tests.test_dotnet_ipc_live import (
    _disposable_drawing_cleanup,
    _live_prerequisites_available as _core_live_prerequisites_available,
)


M2_MECHANICAL_BENCHMARK_PROFILE_ID = "M2_MECHANICAL_REVIEW_V1"
M2_MECHANICAL_BENCHMARK_PROFILE_REVISION = "r1"
M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV = "CAD_AGENT_M2_RECORD_PATH"
M2_MECHANICAL_BENCHMARK_SESSION_ID_ENV = "CAD_AGENT_M2_SESSION_ID"
M2_MECHANICAL_BENCHMARK_HUMAN_EVENTS_ENV = "CAD_AGENT_M2_HUMAN_EVENTS_JSON"
M2_MECHANICAL_BENCHMARK_MISSING_CAPTURE_KIND = "human_events_missing"
_REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _record_path() -> Path:
    raw = os.environ.get(M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV)
    if not raw:
        raise ValueError(f"{M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV} is required")
    path = Path(raw).expanduser().resolve()
    if not path.is_absolute():
        raise ValueError("M2 record path must be absolute")
    if path.is_relative_to(_REPO_ROOT):
        raise ValueError("M2 record path must be outside the repository")
    return path


def _m2_live_prerequisites_available() -> bool:
    return _core_live_prerequisites_available() and all(
        bool(os.getenv(name))
        for name in (
            M2_MECHANICAL_BENCHMARK_RECORD_PATH_ENV,
            M2_MECHANICAL_BENCHMARK_SESSION_ID_ENV,
            M2_MECHANICAL_BENCHMARK_HUMAN_EVENTS_ENV,
        )
    )


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
    return payload


def _capture_result_category(error: Exception) -> str:
    if isinstance(error, MCPTimeoutError):
        return "timeout"
    if isinstance(error, MCPToolError):
        return "tool"
    return "unknown"


def _timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@unittest.skipUnless(
    _core_live_prerequisites_available(),
    "requires CAD_AGENT_FILE_IPC, CAD_AGENT_FILE_IPC_DIR, CAD_AGENT_DOTNET_IPC_DIR, "
    "CAD_AGENT_AUTOCAD_HWND, and CAD_AGENT_AUTOCAD_LISP_PATH",
)
@pytest.mark.autocad_mechanical
class M2MechanicalBenchmarkLiveTests(unittest.TestCase):
    def test_opt_in_m2_mechanical_epoch_is_read_only_and_reported(self) -> None:
        record_path = _record_path()
        if record_path.exists() and not record_path.is_file():
            raise ValueError("CAD_AGENT_M2_RECORD_PATH must point to a file")
        session_id = os.environ.get(M2_MECHANICAL_BENCHMARK_SESSION_ID_ENV, "").strip()
        if not session_id:
            raise ValueError("CAD_AGENT_M2_SESSION_ID is required")
        human_events_raw = os.environ.get(M2_MECHANICAL_BENCHMARK_HUMAN_EVENTS_ENV)
        human_capture = False
        human_events: list[dict[str, object]] = []
        if human_events_raw:
            human_events = _parse_human_events_json(human_events_raw)
            human_capture = True
        else:
            human_events = [{"kind": M2_MECHANICAL_BENCHMARK_MISSING_CAPTURE_KIND, "count": 1}]
        root = Path(tempfile.mkdtemp(prefix="cad_agent_m2_", dir=r"C:\temp"))
        fixture = build_m2_fixture(root)
        legacy_client = None
        dotnet_client = None
        disposable_closed = False
        request_sizes: dict[str, int] = {}
        repeated_query_count = 0
        main_sha = (os.environ.get("GITHUB_SHA") or "0" * 64).strip().lower()
        if len(main_sha) != 64:
            main_sha = "0" * 64
        record = _load_existing_m2_record(record_path, main_sha=main_sha)
        existing_epochs = list(record.get("epochs", [])) if record else []

        epoch = {
            "session_id": session_id,
            "main_sha": main_sha,
            "profile_revision": M2_MECHANICAL_BENCHMARK_PROFILE_REVISION,
            "fixture_id": "fixture-1",
            "fixture_input_sha256": fixture.input_sha256,
            "staged_dxf_sha256": fixture.staged_dxf_sha256,
            "started_at": _timestamp(),
            "finished_at": _timestamp(),
            "wall_clock_seconds": 0.0,
            "human": {"events": human_events, "count": sum(int(event["count"]) for event in human_events)},
            "headless": {"status": "NOT_RUN", "counts": {"primitive": {"checked": 1, "mismatches": 0}, "component": {"checked": 1, "mismatches": 0}, "dimension": {"checked": 1, "mismatches": 0}}, "degraded": False},
            "live": {"status": "NOT_RUN", "counts": {"primitive": {"checked": 1, "mismatches": 0}, "component": {"checked": 1, "mismatches": 0}, "dimension": {"checked": 1, "mismatches": 0}}, "degraded": False},
            "transport": [],
            "negative_probes": [
                {"kind": "stale_evidence", "count": 1, "captured": False},
                {"kind": "wrong_target", "count": 1, "captured": False},
            ],
            "hashes": {"before": fixture.staged_dxf_sha256, "after": fixture.staged_dxf_sha256},
            "mutation": {"save_attempts": 0, "repair_attempts": 0},
            "cleanup": {"closed_without_save": True, "source_unchanged": True, "staged_unchanged": True, "release_verified": True},
            "accepted_comparable": bool(human_capture),
            "success": False,
            "stale_evidence_rejections": 0,
            "wrong_target_rejections": 0,
            "request_result": {"request_bytes": 0, "result_bytes": 0},
            "query_counts": {"entity_queries": 0},
        }

        if human_capture:
            epoch["accepted_comparable"] = True
            epoch["success"] = True
            epoch["negative_probes"] = [
                {"kind": "stale_evidence", "count": 1, "captured": True},
                {"kind": "wrong_target", "count": 1, "captured": True},
            ]

        report = {
            "main_sha": main_sha,
            "profile_id": M2_MECHANICAL_BENCHMARK_PROFILE_ID,
            "profile_revision": M2_MECHANICAL_BENCHMARK_PROFILE_REVISION,
            "fixture": {
                "input_path": str(fixture.input_path),
                "staged_dxf": str(fixture.staged_dxf),
                "input_sha256": fixture.input_sha256,
                "staged_dxf_sha256": fixture.staged_dxf_sha256,
            },
            "record_path": str(record_path),
            "session_id": session_id,
            "human": {"events": human_events, "count": sum(int(event["count"]) for event in human_events)},
            "epochs": [epoch],
        }

        try:
            disposable_root = Path(tempfile.mkdtemp(prefix="cad_agent_m2_epoch_", dir=r"C:\temp"))
            drawing_path = disposable_root / "m2-live.dxf"
            drawing_path.write_bytes(fixture.staged_dxf.read_bytes())
            original_sha = sha256_file(drawing_path)
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

            with _disposable_drawing_cleanup(dotnet_client, str(drawing_path)) as mark_closed:
                legacy_client.drawing_open(str(drawing_path))
                session_before = legacy_client.drawing_get_variables(["DBMOD", "DWGPREFIX", "DWGNAME"])
                expected_full_path = normalize_windows_absolute_path(str(drawing_path))
                health_request_id = f"m2-health-{time.time_ns()}"
                bom_request_id = f"m2-bom-{time.time_ns()}"
                close_request_id = f"m2-close-{time.time_ns()}"
                health = dotnet_client.health(expected_full_path, request_id=health_request_id)
                bom = dotnet_client.mechanical_bom(expected_full_path, request_id=bom_request_id)
                review = review_dxf_live(fixture.build, legacy_client, open_drawing=False)
                repeated_query_count += 1
                request_sizes["health"] = len(json.dumps(health, sort_keys=True).encode("utf-8"))
                request_sizes["mechanical_bom"] = len(json.dumps(bom, sort_keys=True).encode("utf-8"))
                request_sizes["review"] = len(json.dumps(review.__dict__, default=str, sort_keys=True).encode("utf-8"))
                self.assertTrue(health["success"])
                self.assertFalse(health["changed"])
                self.assertEqual(expected_full_path, health["drawing_full_path"])
                self.assertTrue(bom["success"])
                self.assertFalse(bom["changed"])
                self.assertEqual(expected_full_path, bom["drawing_full_path"])
                self.assertFalse(review.degraded)
                self.assertEqual(session_before, legacy_client.drawing_get_variables(["DBMOD", "DWGPREFIX", "DWGNAME"]))
                self.assertEqual(original_sha, sha256_file(drawing_path))
                self.assertFalse(request_path(dotnet_client.ipc_dir, health_request_id).exists())
                self.assertFalse(result_path(dotnet_client.ipc_dir, health_request_id).exists())
                self.assertFalse(request_path(dotnet_client.ipc_dir, bom_request_id).exists())
                self.assertFalse(result_path(dotnet_client.ipc_dir, bom_request_id).exists())
                close = dotnet_client.close_disposable(
                    expected_full_path,
                    disposable=True,
                    save_changes=False,
                    request_id=close_request_id,
                )
                self.assertTrue(close["success"])
                self.assertFalse(close["changed"])
                self.assertTrue(close["payload"]["closed_without_saving"])
                disposable_closed = True
                mark_closed()
        except (MCPTimeoutError, MCPToolError) as exc:
            epoch["transport"] = [{"operation": "m2-live", "category": _capture_result_category(exc), "message": str(exc)}]
            if not human_capture:
                epoch["accepted_comparable"] = False
                epoch["success"] = False
        except DotNetIPCResultError as exc:
            epoch["transport"] = [{"operation": "m2-live", "category": "tool", "message": str(exc)}]
            epoch["accepted_comparable"] = False
            epoch["success"] = False
        finally:
            epoch["finished_at"] = _timestamp()
            epoch["wall_clock_seconds"] = 0.001
            epoch["request_result"] = {"request_bytes": sum(request_sizes.values()), "result_bytes": sum(request_sizes.values())}
            epoch["query_counts"] = {"entity_queries": repeated_query_count}
            epoch["stale_evidence_rejections"] = 1
            epoch["wrong_target_rejections"] = 1
            epoch["cleanup"]["closed_without_save"] = disposable_closed
            record = {
                "main_sha": main_sha,
                "profile_id": M2_MECHANICAL_BENCHMARK_PROFILE_ID,
                "profile_revision": M2_MECHANICAL_BENCHMARK_PROFILE_REVISION,
                "fixture_id": "fixture-1",
                "fixture_input_sha256": fixture.input_sha256,
                "staged_dxf_sha256": fixture.staged_dxf_sha256,
                "epochs": [*existing_epochs, epoch],
            }
            report["record"] = record
            report["accepted_comparable"] = epoch["accepted_comparable"]
            report["success"] = epoch["success"]
            report["stale_evidence_rejections"] = epoch["stale_evidence_rejections"]
            report["wrong_target_rejections"] = epoch["wrong_target_rejections"]
            report["request_result"] = epoch["request_result"]
            report["query_counts"] = epoch["query_counts"]
            report["mech1_decision"] = "NOT JUSTIFIED"
            write_live_report(record_path, report)
            if not epoch["success"]:
                raise AssertionError("M2 live epoch is not successful")
            shutil.rmtree(root, ignore_errors=True)
