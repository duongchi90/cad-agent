import hashlib
import json
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

    def test_post_activation_start_tab_sentinel_does_not_reenter_open(self):
        raw_commands = []
        command_sequences = []
        client = self._client(raw_commands, command_sequences)

        def dispatch(command, params):
            if command == "ping":
                raise MCPTimeoutError("start tab has no dispatcher")
            return {"DWGPREFIX": "C:/work/", "DWGNAME": "a.dxf"}

        client._dispatch = dispatch

        with self.assertRaisesRegex(MCPTimeoutError, "start tab has no dispatcher"):
            client.drawing_open("C:/work/a.dxf")

        self.assertEqual([], command_sequences)

    def test_post_activation_start_tab_sentinel_with_probe_does_not_reenter_open(self):
        raw_commands = []
        command_sequences = []
        client = FileIPCLiveMCPClient(
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            start_tab_no_document_probe=lambda: True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        def dispatch(command, params):
            if command == "ping":
                raise MCPTimeoutError("start tab has no dispatcher")
            return {"DWGPREFIX": "C:/work/", "DWGNAME": "a.dxf"}

        client._dispatch = dispatch

        with self.assertRaisesRegex(MCPTimeoutError, "start tab has no dispatcher"):
            client.drawing_open("C:/work/a.dxf")

        self.assertEqual([], command_sequences)

    def test_already_open_active_target_is_not_reopened(self):
        raw_commands = []
        command_sequences = []
        target_path = "C:/work/already-active.dxf"
        active_document = {"full_name": target_path}
        com_activation_attempts = []
        com_open_attempts = []

        def raw_trigger(command):
            raw_commands.append(command)
            if command.startswith("(progn (vl-load-com)"):
                com_activation_attempts.append(active_document["full_name"])
                if active_document["full_name"].casefold() != target_path.casefold():
                    com_open_attempts.append(target_path)
                    active_document["full_name"] = target_path
            elif command.startswith('(load "'):
                return
            else:
                self.fail(f"unexpected raw LISP command: {command}")

        client = FileIPCLiveMCPClient(
            raw_lisp_trigger=raw_trigger,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        def dispatch(command, params):
            if command == "drawing-get-variables":
                return {"DWGPREFIX": "C:/work/", "DWGNAME": "already-active.dxf"}
            return {}

        client._dispatch = dispatch

        self.assertEqual({"path": target_path}, client.drawing_open(target_path))
        self.assertEqual([target_path], com_activation_attempts)
        self.assertEqual([], com_open_attempts)
        self.assertEqual([], command_sequences)
        self.assertEqual("c:\\work\\already-active.dxf", client._active_drawing_path)
        self.assertEqual(target_path, active_document["full_name"])

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

    def test_fail_closed_cleanup_preserves_disposable_fixture_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ipc_dir = root / "ipc"
            target = root / "disposable-target.dxf"
            original_bytes = b"disposable CAD fixture bytes\x00\x01\x02"
            target.write_bytes(original_bytes)
            before_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            raw_commands = []
            command_sequences = []

            def raw_trigger(command):
                raw_commands.append(command)

            def trigger():
                command_file = next(ipc_dir.glob("autocad_mcp_cmd_*.json"))
                request_id = command_file.stem.removeprefix("autocad_mcp_cmd_")
                (ipc_dir / f"autocad_mcp_result_{request_id}.json").write_text(
                    json.dumps(
                        {
                            "request_id": request_id,
                            "ok": False,
                            "error": "post-activation dispatcher failure",
                        }
                    ),
                    encoding="utf-8",
                )

            client = FileIPCLiveMCPClient(
                ipc_dir=str(ipc_dir),
                trigger=trigger,
                raw_lisp_trigger=raw_trigger,
                bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
                command_trigger=command_sequences.append,
                timeout_s=0.1,
                poll_interval_s=0.001,
                document_settle_s=0,
            )

            with self.assertRaisesRegex(MCPTimeoutError, "post-activation dispatcher failure"):
                client.drawing_open(str(target))

            self.assertEqual(before_hash, hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertEqual(original_bytes, target.read_bytes())
            self.assertEqual([], list(ipc_dir.iterdir()))
            self.assertEqual([], command_sequences)


if __name__ == "__main__":
    unittest.main()
