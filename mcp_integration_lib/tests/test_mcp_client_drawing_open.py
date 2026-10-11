import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    MCPToolError,
    MCPTimeoutError,
)


class DrawingOpenFallbackTests(unittest.TestCase):
    def setUp(self):
        self._ipc_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._ipc_tmp.cleanup)
        self._ipc_dir = self._ipc_tmp.name

    def test_claim_bound_open_waits_for_exact_document_ack_before_loader(self):
        loaded = []
        probes = []
        target = "C:/work/slow-open.dwg"

        def raw(command):
            marker = '(setq mcp-ready-file (open "'
            if marker in command:
                probes.append(command)
                # The first expression is dropped by the opening editor, as in
                # the actual cold DWG log. A later readonly probe executes.
                if len(probes) == 1:
                    return
                path = Path(command.split(marker, 1)[1].split('"', 1)[0])
                token = path.stem.removeprefix("autocad_mcp_document_ready_")
                path.write_text(token + "\n" + target + "\nREADY\n", encoding="utf-8")
            elif command.startswith("(progn (setq *cad-agent-file-ipc-root*"):
                loaded.append(command)

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir, raw_lisp_trigger=raw,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            timeout_s=0.05, poll_interval_s=0.001, document_settle_s=0,
            legacy_fixture_mode=False,
        )

        def dispatch(command, params):
            if command == "ping" and len(probes) < 2:
                raise MCPTimeoutError("dispatcher loader arrived before editor ready")
            return {"DWGPREFIX":"C:/work/", "DWGNAME":"slow-open.dwg"}

        client._dispatch = dispatch
        self.assertEqual({"path":target}, client.drawing_open(target))
        self.assertEqual(1, len(loaded))
        self.assertEqual(2, len(probes))
        self.assertEqual([], list(Path(self._ipc_dir).iterdir()))

    def test_claim_bound_open_without_exact_document_ack_never_loads(self):
        loaded = []

        def raw(command):
            marker = '(setq mcp-ready-file (open "'
            if marker in command:
                path = Path(command.split(marker, 1)[1].split('"', 1)[0])
                token = path.stem.removeprefix("autocad_mcp_document_ready_")
                path.write_text(token + "\nC:/work/protected-source.dwg\nREADY\n", encoding="utf-8")
            elif command.startswith("(progn (setq *cad-agent-file-ipc-root*"):
                loaded.append(command)

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir, raw_lisp_trigger=raw,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            timeout_s=0.02, poll_interval_s=0.001, document_settle_s=0,
            legacy_fixture_mode=False,
        )
        client._dispatch = lambda command, params: {
            "DWGPREFIX":"C:/work/", "DWGNAME":"wanted.dwg",
        }
        with self.assertRaisesRegex(MCPToolError, "DRAWING_OPEN_READINESS_TARGET_MISMATCH"):
            client.drawing_open("C:/work/wanted.dwg")
        self.assertEqual([], loaded)
        self.assertEqual([], list(Path(self._ipc_dir).iterdir()))

    def test_claim_bound_open_rejects_missing_incomplete_or_foreign_ack(self):
        for mode in ("missing", "incomplete", "foreign"):
            with self.subTest(mode=mode):
                loaded = []
                opened = []
                probes = []

                def raw(command):
                    if "vla-open" in command:
                        opened.append(command)
                    marker = '(setq mcp-ready-file (open "'
                    if marker in command:
                        probes.append(command)
                        path = Path(command.split(marker, 1)[1].split('"', 1)[0])
                        token = path.stem.removeprefix("autocad_mcp_document_ready_")
                        if mode != "missing":
                            text = token + "\nC:/work/wanted.dwg\n"
                            if mode == "foreign":
                                text = "foreign-nonce\nC:/work/wanted.dwg\nREADY\n"
                            path.write_text(text, encoding="utf-8")
                    elif command.startswith("(progn (setq *cad-agent-file-ipc-root*"):
                        loaded.append(command)

                client = FileIPCLiveMCPClient(
                    ipc_dir=self._ipc_dir, raw_lisp_trigger=raw,
                    bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
                    timeout_s=0.03, poll_interval_s=0.001, document_settle_s=0,
                    legacy_fixture_mode=False,
                )
                client._dispatch = lambda *_args: self.fail("No dispatch before readiness")
                error = MCPToolError if mode == "foreign" else MCPTimeoutError
                with self.assertRaisesRegex(error, "DRAWING_OPEN_READINESS"):
                    client.drawing_open("C:/work/wanted.dwg")
                self.assertEqual([], loaded)
                self.assertEqual(1, len(opened))
                self.assertLessEqual(len(probes), 3)
                self.assertEqual([], list(Path(self._ipc_dir).iterdir()))

    def _client(self, raw_commands, command_sequences):
        return FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
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
            ipc_dir=self._ipc_dir,
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
            elif command.startswith("(progn (setq *cad-agent-file-ipc-root* "):
                self.assertIn('(load "C:/tools/mcp_dispatch.lsp")', command)
                self.assertIn(str(Path(self._ipc_dir)).replace("\\", "/"), command)
            else:
                self.fail(f"unexpected raw LISP command: {command}")

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
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
            ipc_dir=self._ipc_dir,
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
            ipc_dir=self._ipc_dir,
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

    def test_start_tab_readiness_timeout_uses_one_guarded_open_fallback(self):
        raw_commands = []
        command_sequences = []
        readiness_probes = []
        target = "C:/work/start-tab.dxf"

        def raw_trigger(command):
            raw_commands.append(command)
            marker = '(setq mcp-ready-file (open "'
            if marker in command:
                readiness_probes.append(command)
                if command_sequences:
                    path = Path(command.split(marker, 1)[1].split('"', 1)[0])
                    token = path.stem.removeprefix("autocad_mcp_document_ready_")
                    path.write_text(token + "\n" + target + "\nREADY\n", encoding="utf-8")

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=raw_trigger,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            start_tab_no_document_probe=lambda: True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
            legacy_fixture_mode=False,
        )
        client._dispatch = lambda command, params: (
            {"DWGPREFIX": "C:/work/", "DWGNAME": "start-tab.dxf"}
            if command == "drawing-get-variables" else {}
        )

        self.assertEqual({"path": target}, client.drawing_open(target))
        self.assertEqual(['_.OPEN\r"C:/work/start-tab.dxf"'], command_sequences)
        self.assertGreaterEqual(len(readiness_probes), 2)
        self.assertLessEqual(len(readiness_probes), 6)
        self.assertEqual([], list(Path(self._ipc_dir).iterdir()))

    def test_initial_trigger_error_does_not_repeat_guarded_open_after_readiness_timeout(self):
        command_sequences = []

        def raw_trigger(command):
            if command.startswith("(progn (vl-load-com)"):
                raise MCPTimeoutError("initial AutoCAD LISP delivery timed out")

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=raw_trigger,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            start_tab_no_document_probe=lambda: True,
            timeout_s=0.005,
            poll_interval_s=0,
            document_settle_s=0,
            legacy_fixture_mode=False,
        )

        with self.assertRaises(MCPTimeoutError):
            client.drawing_open("C:/work/start-tab.dxf")

        self.assertEqual(['_.OPEN\r"C:/work/start-tab.dxf"'], command_sequences)
        self.assertEqual([], list(Path(self._ipc_dir).iterdir()))

    def test_rejected_com_or_modal_state_never_falls_back_to_open(self):
        raw_commands = []
        command_sequences = []

        def raw_trigger(command):
            raw_commands.append(command)
            if "vla-open" in command:
                raise MCPToolError("RPC_E_CALL_REJECTED: Select File modal")

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
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

    def test_open_document_listing_retries_transient_windows_cleanup_lock(self):
        raw_commands = []
        listing_path = None

        def raw_trigger(command):
            nonlocal listing_path
            raw_commands.append(command)
            marker = '(setq mcp-doc-file (open "'
            if marker in command:
                listing_path = Path(
                    command.split(marker, 1)[1].split('"', 1)[0].replace("/", "\\")
                )
                listing_path.write_text("C:/work/a.dxf\n", encoding="utf-8")

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=raw_trigger,
            timeout_s=0.01,
            poll_interval_s=0,
        )
        original_unlink = Path.unlink
        attempts = 0

        def transient_lock(path, *args, **kwargs):
            nonlocal attempts
            if path.name.startswith("autocad_mcp_open_documents_") and attempts == 0:
                attempts += 1
                raise PermissionError("listing file is still locked")
            attempts += 1
            return original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", transient_lock):
            self.assertEqual(["C:/work/a.dxf"], client.drawing_list_open_paths())
        self.assertEqual(2, attempts)
        self.assertIsNotNone(listing_path)
        self.assertFalse(listing_path.exists())

    def test_fail_closed_cleanup_preserves_disposable_fixture_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ipc_dir = root / "ipc"
            ipc_dir.mkdir()
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
