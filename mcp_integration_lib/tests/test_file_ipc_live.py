"""Opt-in smoke test for an AutoCAD File IPC session.

Run with CAD_AGENT_FILE_IPC=1, CAD_AGENT_FILE_IPC_DIR, and
CAD_AGENT_AUTOCAD_HWND after AutoCAD loads mcp_dispatch.lsp.
"""
import os
import unittest

import pytest

from mcp_integration_lib.mcp_client import FileIPCLiveMCPClient, make_windows_dispatch_trigger


pytestmark = pytest.mark.autocad_mechanical


def _live_prerequisites_available() -> bool:
    return (
        os.getenv("CAD_AGENT_FILE_IPC") == "1"
        and bool(os.getenv("CAD_AGENT_FILE_IPC_DIR"))
        and bool(os.getenv("CAD_AGENT_AUTOCAD_HWND"))
    )


@unittest.skipUnless(
    _live_prerequisites_available(),
    "requires live AutoCAD File IPC with explicit IPC root and HWND",
)
class FileIPCLiveSmokeTests(unittest.TestCase):
    def test_active_drawing_is_readable(self):
        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        client = FileIPCLiveMCPClient(
            ipc_dir=os.environ["CAD_AGENT_FILE_IPC_DIR"],
            trigger=make_windows_dispatch_trigger(hwnd),
        )
        self.assertIsInstance(client.entity_list(), list)
