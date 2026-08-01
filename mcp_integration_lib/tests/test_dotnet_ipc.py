from __future__ import annotations

import importlib
import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mcp_integration_lib import dotnet_ipc
from mcp_integration_lib.dotnet_ipc import (
    DEFAULT_IPC_DIR,
    REQUEST_PREFIX,
    RESULT_PREFIX,
    DotNetIPCClient,
    DotNetIPCResultError,
    DotNetIPCTimeoutError,
    atomic_write_json,
    cleanup_request_files,
    get_ipc_dir,
    normalize_request_id,
    normalize_windows_absolute_path,
    request_filename,
    request_path,
    result_filename,
    result_path,
)


class RecordingUser32:
    def __init__(self) -> None:
        self.class_names: dict[int, str] = {}
        self.enum_calls: list[tuple[int, int]] = []
        self.post_calls: list[tuple[int, int, int, int]] = []

    def EnumChildWindows(self, hwnd, callback, lparam):
        self.enum_calls.append((hwnd, lparam))
        for child, class_name in ((101, "Palette"), (202, "MDIClient"), (303, "Other")):
            self.class_names[child] = class_name
            if not callback(child, lparam):
                break

    def GetClassNameW(self, child, buffer, _length):
        buffer.value = self.class_names[child]
        return len(buffer.value)

    def PostMessageW(self, target, message, wparam, lparam):
        self.post_calls.append((target, message, wparam, lparam))
        return True


class WindowsDotNetTriggerTests(unittest.TestCase):
    def test_rejects_non_positive_or_non_integer_window_handles(self) -> None:
        user32 = RecordingUser32()
        factory = getattr(dotnet_ipc, "make_windows_dotnet_dispatch_trigger", None)
        self.assertTrue(callable(factory))

        with patch.object(dotnet_ipc, "_get_user32", return_value=user32, create=True) as get_user32:
            for hwnd in (0, -1, None, "123", 1.5, True):
                with self.subTest(hwnd=hwnd):
                    with self.assertRaises(ValueError):
                        factory(hwnd)

        get_user32.assert_not_called()

    def test_posts_exact_dispatch_message_sequence_to_mdi_child(self) -> None:
        user32 = RecordingUser32()
        factory = getattr(dotnet_ipc, "make_windows_dotnet_dispatch_trigger", None)
        self.assertTrue(callable(factory))

        with patch.object(dotnet_ipc, "_get_user32", return_value=user32, create=True):
            trigger = factory(9001)
            trigger()

        command = "\x1b\x1bCADAGENT_DISPATCH\r"
        self.assertEqual([(9001, 0)], user32.enum_calls)
        self.assertEqual(
            [(202, 0x0102, ord(character), 0) for character in command],
            user32.post_calls,
        )


def _result(request: dict[str, object], payload: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "request_id": request["request_id"],
        "success": True,
        "operation": request["operation"],
        "drawing_full_path": request["drawing_full_path"],
        "changed": False,
        "entity_handles": [],
        "warnings": [],
        "errors": [],
        "started_at": "2026-08-01T00:00:00Z",
        "completed_at": "2026-08-01T00:00:00Z",
        "payload": payload or {},
    }


class FakeDispatcher:
    def __init__(self, ipc_dir: Path, payload: dict[str, object] | None = None) -> None:
        self.ipc_dir = ipc_dir
        self.payload = payload or {}
        self.requests: list[dict[str, object]] = []
        self.request_bytes = b""

    def __call__(self) -> None:
        request_files = list(self.ipc_dir.glob("cadagent_dotnet_request_*.json"))
        self.assert_one_request(request_files)
        self.request_bytes = request_files[0].read_bytes()
        request = json.loads(self.request_bytes.decode("utf-8"))
        self.requests.append(request)
        atomic_write_json(
            result_path(self.ipc_dir, str(request["request_id"])),
            _result(request, self.payload),
        )

    @staticmethod
    def assert_one_request(request_files: list[Path]) -> None:
        if len(request_files) != 1:
            raise AssertionError(f"expected one request file, got {request_files!r}")


class DotNetIPCClientTests(unittest.TestCase):
    def test_request_preserves_utf8_and_request_id(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            dispatcher = FakeDispatcher(ipc_dir, {"message": "Đường kính Ω"})
            client = DotNetIPCClient(
                ipc_dir=ipc_dir,
                trigger=dispatcher,
                request_id_factory=lambda: "health-20260801-001",
            )

            result = client.request(
                "health",
                approval={"note": "Kiểm tra Ω"},
            )

            self.assertEqual("health-20260801-001", result["request_id"])
            self.assertEqual("Kiểm tra Ω", dispatcher.requests[0]["approval"]["note"])
            self.assertIn("Kiểm tra Ω".encode("utf-8"), dispatcher.request_bytes)
            self.assertFalse(list(ipc_dir.glob("cadagent_dotnet_*.json")))

    def test_health_allows_null_drawing_path(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            dispatcher = FakeDispatcher(ipc_dir)
            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=dispatcher)

            client.health()

            self.assertEqual("health", dispatcher.requests[0]["operation"])
            self.assertIsNone(dispatcher.requests[0]["drawing_full_path"])
            self.assertEqual({}, dispatcher.requests[0]["parameters"])

    def test_review_sends_handles_and_normalized_path(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            dispatcher = FakeDispatcher(ipc_dir)
            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=dispatcher)

            client.review(r"C:/drawings/parts/../sample.dwg", ["10", "A0"])

            request = dispatcher.requests[0]
            self.assertEqual("review", request["operation"])
            self.assertEqual(r"C:\drawings\sample.dwg", request["drawing_full_path"])
            self.assertEqual({"handles": ["10", "A0"]}, request["parameters"])

    def test_mechanical_bom_sends_empty_parameters_and_preserves_payload(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            payload = {
                "component_count": 1,
                "components": [
                    {
                        "handle": "2F",
                        "block_name": "COMP_FRAME",
                        "attributes": [{"tag": "PART_ID", "value": "FRAME-001"}],
                    }
                ],
            }
            dispatcher = FakeDispatcher(ipc_dir, payload)
            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=dispatcher)

            result = client.mechanical_bom(r"C:\temp\bom.dxf", request_id="bom-001")

            self.assertEqual("mechanical_bom", dispatcher.requests[0]["operation"])
            self.assertEqual({}, dispatcher.requests[0]["parameters"])
            self.assertEqual(payload, result["payload"])

    def test_mechanical_bom_rejects_unsupported_parameters_before_trigger(self) -> None:
        with TemporaryDirectory() as temporary:
            trigger_calls = 0

            def trigger() -> None:
                nonlocal trigger_calls
                trigger_calls += 1

            client = DotNetIPCClient(ipc_dir=temporary, trigger=trigger)

            with self.assertRaisesRegex(ValueError, "mechanical_bom parameters"):
                client.request(
                    "mechanical_bom",
                    r"C:\temp\bom.dxf",
                    parameters={"filter": "COMP_FRAME"},
                )

            self.assertEqual(0, trigger_calls)

    def test_close_disposable_rejects_unsafe_flags_before_trigger(self) -> None:
        with TemporaryDirectory() as temporary:
            trigger_calls = 0

            def trigger() -> None:
                nonlocal trigger_calls
                trigger_calls += 1

            client = DotNetIPCClient(ipc_dir=temporary, trigger=trigger)
            for kwargs in ({"disposable": False}, {"save_changes": True}):
                with self.subTest(kwargs=kwargs):
                    with self.assertRaises(ValueError):
                        client.close_disposable(r"C:\temp\sample.dwg", **kwargs)

            self.assertEqual(0, trigger_calls)

    def test_timeout_is_bounded_and_cleans_only_this_request(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            old_file = ipc_dir / "autocad_mcp_result_legacy.json"
            old_file.write_text("legacy", encoding="utf-8")
            request_id = "timeout-001"
            client = DotNetIPCClient(
                ipc_dir=ipc_dir,
                trigger=lambda: None,
                timeout_s=0.05,
                poll_interval_s=0.01,
                request_id_factory=lambda: request_id,
            )

            started = time.monotonic()
            with self.assertRaises(DotNetIPCTimeoutError):
                client.health()
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 0.5)
            self.assertFalse(request_path(ipc_dir, request_id).exists())
            self.assertFalse(result_path(ipc_dir, request_id).exists())
            self.assertTrue(old_file.exists())

    def test_non_success_result_raises_and_cleans_request(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)

            def trigger() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                failed = _result(request)
                failed["success"] = False
                failed["errors"] = ["document mismatch"]
                atomic_write_json(result_path(ipc_dir, str(request["request_id"])), failed)

            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=trigger)
            with self.assertRaises(DotNetIPCResultError) as context:
                client.review(r"C:\temp\sample.dwg", ["10"])

            self.assertIn("document mismatch", str(context.exception))
            self.assertFalse(list(ipc_dir.glob("cadagent_dotnet_*.json")))

    def test_oversized_result_is_rejected_by_bounded_read(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)

            def trigger() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                oversized = _result(request, {"data": "x" * 256})
                result_file = result_path(ipc_dir, str(request["request_id"]))
                result_file.write_text(json.dumps(oversized), encoding="utf-8")

            client = DotNetIPCClient(
                ipc_dir=ipc_dir,
                trigger=trigger,
                max_read_bytes=128,
            )
            with self.assertRaises(ValueError):
                client.health()
            self.assertFalse(list(ipc_dir.glob("cadagent_dotnet_*.json")))


class PathUtilityTests(unittest.TestCase):
    def test_autocad_marker_is_scoped_to_live_smoke_class(self) -> None:
        live_module = importlib.import_module(
            "mcp_integration_lib.tests.test_dotnet_ipc_live"
        )

        self.assertNotIn("pytestmark", vars(live_module))
        live_markers = getattr(live_module.DotNetIPCLiveSmokeTests, "pytestmark", [])
        self.assertEqual(["autocad_mechanical"], [marker.name for marker in live_markers])
        self.assertFalse(hasattr(live_module.DisposableCleanupTests, "pytestmark"))

    def test_request_and_result_names_use_the_new_prefix(self) -> None:
        request_id = "health-20260801-001"

        self.assertEqual(
            f"{REQUEST_PREFIX}{request_id}.json",
            request_filename(request_id),
        )
        self.assertEqual(
            f"{RESULT_PREFIX}{request_id}.json",
            result_filename(request_id),
        )

    def test_request_ids_are_safe_for_file_names(self) -> None:
        self.assertEqual("abc-123_X", normalize_request_id("abc-123_X"))

        for invalid in ("", " ", "../escape", "bad.id", "a\\b", "a" * 129):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalize_request_id(invalid)

    def test_paths_are_scoped_to_the_ipc_directory(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            request = request_path(ipc_dir, "one")
            result = result_path(ipc_dir, "one")

            self.assertEqual(ipc_dir / "cadagent_dotnet_request_one.json", request)
            self.assertEqual(ipc_dir / "cadagent_dotnet_result_one.json", result)

    def test_normalizes_absolute_windows_paths_and_rejects_relative_paths(self) -> None:
        self.assertEqual(
            r"C:\drawings\sample.dwg",
            normalize_windows_absolute_path(r"C:/drawings/parts/../sample.dwg"),
        )
        self.assertEqual(
            r"\\server\share\sample.dwg",
            normalize_windows_absolute_path(r"\\server\share\folder\..\sample.dwg"),
        )

        for invalid in ("sample.dwg", r"C:sample.dwg", "", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalize_windows_absolute_path(invalid)

    def test_ipc_directory_env_override_is_resolved(self) -> None:
        with TemporaryDirectory() as temporary:
            previous = os.environ.get("CAD_AGENT_DOTNET_IPC_DIR")
            try:
                os.environ["CAD_AGENT_DOTNET_IPC_DIR"] = temporary
                self.assertEqual(Path(temporary).resolve(), get_ipc_dir())
            finally:
                if previous is None:
                    os.environ.pop("CAD_AGENT_DOTNET_IPC_DIR", None)
                else:
                    os.environ["CAD_AGENT_DOTNET_IPC_DIR"] = previous

        self.assertEqual(Path(DEFAULT_IPC_DIR), Path(r"C:\temp"))

    def test_cleanup_removes_only_the_requested_pair(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            request_path(ipc_dir, "one").write_text("one", encoding="utf-8")
            result_path(ipc_dir, "one").write_text("one", encoding="utf-8")
            request_path(ipc_dir, "two").write_text("two", encoding="utf-8")
            result_path(ipc_dir, "two").write_text("two", encoding="utf-8")
            old_dispatcher = ipc_dir / "autocad_mcp_result_legacy.json"
            old_dispatcher.write_text("legacy", encoding="utf-8")

            cleanup_request_files(ipc_dir, "one")

            self.assertFalse(request_path(ipc_dir, "one").exists())
            self.assertFalse(result_path(ipc_dir, "one").exists())
            self.assertTrue(request_path(ipc_dir, "two").exists())
            self.assertTrue(result_path(ipc_dir, "two").exists())
            self.assertTrue(old_dispatcher.exists())


if __name__ == "__main__":
    unittest.main()
