"""Opt-in disposable AutoCAD Mechanical smoke test for the .NET IPC path."""

import os
import shutil
import tempfile
import unittest
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import ezdxf
import pytest

from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCClient,
    make_windows_dotnet_dispatch_trigger,
    normalize_windows_absolute_path,
    request_path,
    result_path,
)
from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    make_windows_dispatch_trigger,
    make_windows_lisp_trigger,
)


pytestmark = pytest.mark.autocad_mechanical


def _live_prerequisites_available() -> bool:
    return (
        os.getenv("CAD_AGENT_FILE_IPC") == "1"
        and bool(os.getenv("CAD_AGENT_AUTOCAD_HWND"))
        and bool(os.getenv("CAD_AGENT_AUTOCAD_LISP_PATH"))
    )


@contextmanager
def _disposable_drawing_cleanup(
    dotnet_client: DotNetIPCClient,
    drawing_path: str,
) -> Iterator[Callable[[], None]]:
    cleanup_needed = True

    def mark_closed() -> None:
        nonlocal cleanup_needed
        cleanup_needed = False

    try:
        yield mark_closed
    finally:
        if cleanup_needed:
            dotnet_client.close_disposable(
                drawing_path,
                disposable=True,
                save_changes=False,
                request_id="dotnet-live-finally-close",
            )


class _CloseRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, bool, str]] = []

    def close_disposable(
        self,
        drawing_path: str,
        *,
        disposable: bool,
        save_changes: bool,
        request_id: str,
    ) -> None:
        self.calls.append((drawing_path, disposable, save_changes, request_id))


class _OpenThenRaise:
    def __init__(self) -> None:
        self.opened_paths: list[str] = []

    def drawing_open(self, drawing_path: str) -> None:
        self.opened_paths.append(drawing_path)
        raise RuntimeError("open raised after opening")


class DisposableCleanupTests(unittest.TestCase):
    def test_closes_when_opening_raises_after_opening(self) -> None:
        drawing_path = r"C:\temp\disposable\dotnet_live.dxf"
        recorder = _CloseRecorder()
        legacy_client = _OpenThenRaise()

        with self.assertRaisesRegex(RuntimeError, "after opening"):
            with _disposable_drawing_cleanup(recorder, drawing_path):
                legacy_client.drawing_open(drawing_path)

        self.assertEqual([drawing_path], legacy_client.opened_paths)
        self.assertEqual(
            [(drawing_path, True, False, "dotnet-live-finally-close")],
            recorder.calls,
        )

    def test_verified_close_disarms_fallback_cleanup(self) -> None:
        drawing_path = r"C:\temp\disposable\dotnet_live.dxf"
        recorder = _CloseRecorder()

        with _disposable_drawing_cleanup(recorder, drawing_path) as mark_closed:
            recorder.close_disposable(
                drawing_path,
                disposable=True,
                save_changes=False,
                request_id="dotnet-live-close",
            )
            mark_closed()

        self.assertEqual(
            [(drawing_path, True, False, "dotnet-live-close")],
            recorder.calls,
        )


@unittest.skipUnless(
    _live_prerequisites_available(),
    "requires CAD_AGENT_FILE_IPC=1, CAD_AGENT_AUTOCAD_HWND, and CAD_AGENT_AUTOCAD_LISP_PATH",
)
class DotNetIPCLiveSmokeTests(unittest.TestCase):
    def test_disposable_dxf_uses_dotnet_health_review_and_close(self) -> None:
        test_directory = Path(tempfile.mkdtemp(prefix="cad_agent_dotnet_live_", dir=r"C:\temp"))
        drawing_path = test_directory / "dotnet_live.dxf"

        try:
            drawing_document = ezdxf.new("R2010")
            drawing_document.modelspace().add_line((0, 0), (10, 0))
            drawing_document.saveas(drawing_path)

            expected_full_path = normalize_windows_absolute_path(str(drawing_path))
            hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
            legacy_client = FileIPCLiveMCPClient(
                trigger=make_windows_dispatch_trigger(hwnd),
                raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
                bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
            )
            dotnet_client = DotNetIPCClient(
                ipc_dir=r"C:\temp",
                trigger=make_windows_dotnet_dispatch_trigger(hwnd),
                timeout_s=20.0,
            )

            with _disposable_drawing_cleanup(dotnet_client, str(drawing_path)) as mark_closed:
                legacy_client.drawing_open(str(drawing_path))
                entities = legacy_client.entity_list()
                self.assertTrue(entities)
                handle = str(entities[0]["handle"])

                health_request_id = "dotnet-live-health"
                health = dotnet_client.health(
                    expected_full_path,
                    request_id=health_request_id,
                )
                self.assertTrue(health["success"])
                self.assertEqual("1.0.0", health["payload"]["plugin_version"])
                self.assertEqual(expected_full_path, health["drawing_full_path"])
                self.assertFalse(health["changed"])
                self.assertFalse(request_path(dotnet_client.ipc_dir, health_request_id).exists())
                self.assertFalse(result_path(dotnet_client.ipc_dir, health_request_id).exists())

                review_request_id = "dotnet-live-review"
                review = dotnet_client.review(
                    expected_full_path,
                    [handle],
                    request_id=review_request_id,
                )
                self.assertTrue(review["success"])
                self.assertEqual(expected_full_path, review["drawing_full_path"])
                self.assertFalse(review["changed"])
                self.assertEqual([], review["errors"])
                self.assertFalse(request_path(dotnet_client.ipc_dir, review_request_id).exists())
                self.assertFalse(result_path(dotnet_client.ipc_dir, review_request_id).exists())

                close_request_id = "dotnet-live-close"
                close = dotnet_client.close_disposable(
                    expected_full_path,
                    disposable=True,
                    save_changes=False,
                    request_id=close_request_id,
                )
                self.assertTrue(close["success"])
                self.assertEqual(expected_full_path, close["drawing_full_path"])
                self.assertFalse(close["changed"])
                self.assertTrue(close["payload"]["closed_without_saving"])
                mark_closed()
                self.assertFalse(request_path(dotnet_client.ipc_dir, close_request_id).exists())
                self.assertFalse(result_path(dotnet_client.ipc_dir, close_request_id).exists())
        finally:
            shutil.rmtree(test_directory)
