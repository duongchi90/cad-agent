from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dotnet_ipc.client import (
    DotNetIPCClient,
    DotNetIPCResultError,
    DotNetIPCTimeoutError,
)
from dotnet_ipc.paths import atomic_write_json, request_path, result_path


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


if __name__ == "__main__":
    unittest.main()
