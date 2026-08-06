import tempfile
import unittest
from pathlib import Path

from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    MCPToolError,
    MCPTimeoutError,
)


class DrawingOpenFallbackTests(unittest.TestCase):
    def _client(self, raw_commands, command_sequences):
        return FileIPCLiveMCPClient(
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

    def test_post_activation_dispatcher_failure_does_not_reenter_open(self):
        raw_commands = []
        command_sequences = []
        client = self._client(raw_commands, command_sequences)

        def dispatch(command, params):
            if command == "ping":
                raise MCPTimeoutError("post-activation dispatcher timeout")
            return {"DWGPREFIX": "C:/work/", "DWGNAME": "a.dxf"}

        client._dispatch = dispatch

        with self.assertRaisesRegex(MCPTimeoutError, "post-activation dispatcher timeout"):
            client.drawing_open("C:/work/a.dxf")

        self.assertEqual([], command_sequences)

    def test_com_activation_failure_falls_back_only_with_positive_start_tab_proof(self):
        raw_commands = []
        command_sequences = []

        def raw_trigger(command):
            raw_commands.append(command)
            if "vla-open" in command:
                raise MCPToolError("COM activation failed")

        client = FileIPCLiveMCPClient(
            raw_lisp_trigger=raw_trigger,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
            start_tab_no_document_probe=lambda: True,
        )
        client._dispatch = lambda command, params: (
            {"DWGPREFIX": "C:/work/", "DWGNAME": "a.dxf"}
            if command == "drawing-get-variables"
            else {}
        )

        self.assertEqual(
            {"path": "C:/work/a.dxf"},
            client.drawing_open("C:/work/a.dxf"),
        )
        self.assertEqual(['_.OPEN\r"C:/work/a.dxf"'], command_sequences)

    def test_com_activation_failure_without_start_tab_proof_fails_closed(self):
        raw_commands = []
        command_sequences = []

        def raw_trigger(command):
            raw_commands.append(command)
            if "vla-open" in command:
                raise MCPToolError("COM activation failed")

        client = FileIPCLiveMCPClient(
            raw_lisp_trigger=raw_trigger,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        with self.assertRaises((MCPToolError, MCPTimeoutError)):
            client.drawing_open("C:/work/a.dxf")

        self.assertEqual([], command_sequences)

    def test_rejected_com_or_modal_state_never_falls_back_to_open(self):
        raw_commands = []
        command_sequences = []

        def raw_trigger(command):
            raw_commands.append(command)
            if "vla-open" in command:
                raise MCPToolError("RPC_E_CALL_REJECTED: Select File modal")

        client = FileIPCLiveMCPClient(
            raw_lisp_trigger=raw_trigger,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
            start_tab_no_document_probe=lambda: True,
        )

        with self.assertRaises((MCPToolError, MCPTimeoutError)):
            client.drawing_open("C:/work/a.dxf")

        self.assertEqual([], command_sequences)

    def test_dispatch_request_and_result_files_are_cleaned_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)

            def trigger():
                command_file = next(ipc_dir.glob("autocad_mcp_cmd_*.json"))
                request_id = command_file.stem.removeprefix("autocad_mcp_cmd_")
                (ipc_dir / f"autocad_mcp_result_{request_id}.json").write_text(
                    '{"request_id": "' + request_id + '", "ok": true, "payload": {}}',
                    encoding="utf-8",
                )

            client = FileIPCLiveMCPClient(
                ipc_dir=tmp,
                trigger=trigger,
                timeout_s=0.1,
                poll_interval_s=0.001,
            )

            self.assertEqual({}, client._dispatch("ping", {}))
            self.assertEqual([], list(ipc_dir.iterdir()))


if __name__ == "__main__":
    unittest.main()
