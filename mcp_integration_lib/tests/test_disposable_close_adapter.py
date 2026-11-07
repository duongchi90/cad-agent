"""No native calls: disposal requires an explicit idle-close capability and readback."""
import re
from pathlib import Path

import pytest

from mcp_integration_lib.mcp_client import FileIPCLiveMCPClient, MCPToolError


TARGET = "C:/disposable/candidate.dxf"
BOUND_TARGET = "c:\\disposable\\candidate.dxf"


def test_lisp_close_never_closes_document_from_event_handler():
    source = (Path(__file__).parents[1] / "mcp_dispatch.lsp").read_text(encoding="utf-8")
    callback = re.search(
        r"\(defun mcp-deferred-drawing-close\b(.*?)(?=\n\(defun)", source, re.S
    ).group(1)
    assert "vla-close" not in callback.casefold()
    registration = re.search(
        r"\(defun mcp-defer-drawing-close\b(.*?)(?=\n\(defun)", source, re.S
    ).group(1)
    assert "vlr-lisp-reactor" not in registration.casefold()


def test_unconfigured_disposal_never_sends_native_input(tmp_path):
    calls = []
    client = FileIPCLiveMCPClient(ipc_dir=str(tmp_path), raw_lisp_trigger=calls.append)
    client._active_drawing_path = BOUND_TARGET
    def dispatch(*args):
        calls.append(args)
        return {"DWGPREFIX": "C:/disposable/", "DWGNAME": "candidate.dxf"}

    client._dispatch = dispatch
    with pytest.raises(MCPToolError, match="DISPOSABLE_CLOSE_UNAVAILABLE"):
        client.drawing_close()
    assert calls == []
    assert client._active_drawing_path == BOUND_TARGET


def test_invalid_close_capability_never_sends_native_input(tmp_path):
    calls = []
    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path), disposable_close_client=object(),
        disposable_close_paths=[TARGET], raw_lisp_trigger=calls.append,
    )
    client._active_drawing_path = BOUND_TARGET
    with pytest.raises(MCPToolError, match="DISPOSABLE_CLOSE_UNAVAILABLE"):
        client.drawing_close()
    assert calls == []


@pytest.mark.parametrize("ack", [None, {"success": False},
    {"success": True, "operation": "review", "drawing_full_path": TARGET},
    {"success": True, "operation": "close_disposable", "drawing_full_path": "C:/other.dxf"}])
def test_wrong_dispatch_ack_cannot_clear_target_or_fall_back_to_lisp(tmp_path, ack):
    client, closer = make_client(tmp_path)
    closer.close_disposable = lambda *args, **kwargs: ack
    client.drawing_list_open_paths = lambda: pytest.fail("No census after invalid acknowledgement")
    with pytest.raises(MCPToolError, match="DISPOSABLE_CLOSE_DISPATCH_INVALID"):
        client.drawing_close()
    assert client._active_drawing_path == BOUND_TARGET


class IdleCloser:
    def __init__(self):
        self.calls = []

    def close_disposable(self, path, *, disposable, save_changes):
        self.calls.append((path, disposable, save_changes))
        return {"success": True, "operation": "close_disposable", "drawing_full_path": path}


def make_client(tmp_path):
    closer = IdleCloser()
    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path), disposable_close_client=closer,
        disposable_close_paths=[TARGET], timeout_s=0.02, poll_interval_s=0.001,
    )
    client._active_drawing_path = BOUND_TARGET
    client._dispatch = lambda *_: {"DWGPREFIX": "C:/disposable/", "DWGNAME": "candidate.dxf"}
    return client, closer


@pytest.mark.parametrize("mode", ["unowned", "wrong_active", "save"])
def test_disposal_checks_authorized_path_active_document_and_no_save(tmp_path, mode):
    client, closer = make_client(tmp_path)
    if mode == "unowned":
        client._active_drawing_path = "C:/protected/source.dwg"
    elif mode == "wrong_active":
        client._dispatch = lambda *_: {"DWGPREFIX": "C:/protected/", "DWGNAME": "source.dwg"}
    with pytest.raises(MCPToolError):
        client.drawing_close(save_changes=mode == "save")
    assert closer.calls == []
    assert client._active_drawing_path is not None


@pytest.mark.parametrize("incomplete", [False, True])
def test_idle_dispatch_acknowledgement_cannot_substitute_for_absence(tmp_path, incomplete):
    client, closer = make_client(tmp_path)

    def census():
        if incomplete:
            raise MCPToolError("INCOMPLETE_CENSUS")
        return [TARGET]

    client.drawing_list_open_paths = census
    with pytest.raises(MCPToolError, match="DRAWING_CLOSE_NOT_CONFIRMED"):
        client.drawing_close()
    assert len(closer.calls) == 1
    assert client._active_drawing_path == BOUND_TARGET


def test_idle_close_requires_completed_target_absence_before_releasing_binding(tmp_path):
    client, closer = make_client(tmp_path)
    observations = iter(([TARGET], ["C:/disposable/sentinel.dxf"]))
    client.drawing_list_open_paths = lambda: next(observations)
    client.drawing_close()
    assert closer.calls == [(BOUND_TARGET, True, False)]
    assert client._active_drawing_path is None
