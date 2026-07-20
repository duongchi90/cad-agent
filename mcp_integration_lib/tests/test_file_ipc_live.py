"""Opt-in smoke test for an AutoCAD File IPC session.

Run with CAD_AGENT_FILE_IPC=1 after AutoCAD loads mcp_dispatch.lsp.
"""
import os
import unittest

from mcp_integration_lib.mcp_client import FileIPCLiveMCPClient, make_windows_dispatch_trigger


@unittest.skipUnless(os.getenv("CAD_AGENT_FILE_IPC") == "1", "requires live AutoCAD File IPC")
class FileIPCLiveSmokeTests(unittest.TestCase):
    def test_active_drawing_is_readable(self):
        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        client = FileIPCLiveMCPClient(trigger=make_windows_dispatch_trigger(hwnd))
        self.assertIsInstance(client.entity_list(), list)
