import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import mcp_integration_lib.mcp_client as mcp_client_module
from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    MCPToolError,
    MCPTimeoutError,
)


def _claim_bound_trigger(callback):
    setattr(callback, "_mcp_claim_bound", True)
    return callback


class DrawingOpenFallbackTests(unittest.TestCase):
    def setUp(self):
        self._ipc_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._ipc_tmp.cleanup)
        self._ipc_dir = self._ipc_tmp.name

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

    def test_read_only_open_requests_read_only_and_still_verifies_active_document(self):
        raw_commands = []
        command_sequences = []
        target_path = "C:/work/read-only.dxf"

        def raw_trigger(command):
            raw_commands.append(command)

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
            if command == "ping":
                return {}
            if command == "drawing-get-variables":
                return {"DWGPREFIX": "C:/work/", "DWGNAME": "read-only.dxf"}
            raise AssertionError(f"unexpected dispatch: {command}")

        client._dispatch = dispatch

        self.assertEqual(
            {"path": target_path},
            client.drawing_open(target_path, read_only=True),
        )
        self.assertIn(
            '(vla-open mcp-docs "C:/work/read-only.dxf" :vlax-true)',
            raw_commands[0],
        )
        self.assertEqual("c:\\work\\read-only.dxf", client._active_drawing_path)
        self.assertEqual([], command_sequences)

    def test_default_open_preserves_writable_vla_open_signature(self):
        raw_commands = []
        client = self._client(raw_commands, [])

        client._dispatch = lambda command, params: (
            {"DWGPREFIX": "C:/work/", "DWGNAME": "writable.dxf"}
            if command == "drawing-get-variables"
            else {}
        )

        self.assertEqual({"path": "C:/work/writable.dxf"}, client.drawing_open("C:/work/writable.dxf"))
        self.assertIn('(vla-open mcp-docs "C:/work/writable.dxf")', raw_commands[0])
        self.assertNotIn(":vlax-true", raw_commands[0])

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

    def test_read_only_open_fails_closed_instead_of_using_writable_open_fallback(self):
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
            start_tab_no_document_probe=lambda: True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )
        client._dispatch = lambda command, params: (
            {"DWGPREFIX": "C:/work/", "DWGNAME": "a.dxf"}
            if command == "drawing-get-variables"
            else {}
        )

        with self.assertRaisesRegex(MCPToolError, "COM activation failed"):
            client.drawing_open("C:/work/a.dxf", read_only=True)

        self.assertEqual([], command_sequences)
        self.assertEqual(1, len(raw_commands))

    def test_opt_in_start_tab_bootstrap_precedes_source_open_and_can_close(self):
        raw_commands = []
        command_sequences = []
        dispatches = []

        def raw_trigger(command):
            raw_commands.append(command)

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=raw_trigger,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            start_tab_no_document_probe=lambda: True,
            bootstrap_document_ready_probe=lambda: True,
            bootstrap_start_tab=True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        def dispatch(command, params):
            dispatches.append((command, params))
            if command == "ping":
                return {"ready": True}
            if command == "drawing-get-variables":
                return {"DWGPREFIX": "C:/work/", "DWGNAME": "source.dxf"}
            raise AssertionError(f"unexpected dispatch: {command}")

        client._dispatch = dispatch

        self.assertEqual({"path": "C:/work/source.dxf"}, client.drawing_open("C:/work/source.dxf"))
        self.assertEqual(["_.QNEW"], command_sequences)
        self.assertTrue(client._start_tab_bootstrap_active)
        self.assertEqual(2, [command for command, _ in dispatches].count("ping"))
        bootstrap_load_index = next(
            index for index, command in enumerate(raw_commands)
            if '(load "C:/tools/mcp_dispatch.lsp")' in command
        )
        source_open_index = next(
            index for index, command in enumerate(raw_commands)
            if 'vla-open mcp-docs "C:/work/source.dxf"' in command
        )
        self.assertLess(bootstrap_load_index, source_open_index)

        client.close_start_tab_bootstrap()
        self.assertFalse(client._start_tab_bootstrap_active)
        self.assertIn('command-s "_.CLOSE" "_N"', raw_commands[-1])

    def test_start_tab_bootstrap_waits_for_confirmed_document_after_qnew(self):
        events = []
        raw_commands = []
        readiness_checks = iter((False, False, True))

        def command_trigger(command):
            events.append(("command", command))

        def ready_probe():
            value = next(readiness_checks, True)
            events.append(("ready", value))
            return value

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=lambda command: (raw_commands.append(command), events.append(("lisp", command))),
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_trigger,
            start_tab_no_document_probe=lambda: True,
            bootstrap_document_ready_probe=ready_probe,
            bootstrap_start_tab=True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )
        client._dispatch = lambda command, params: (
            {"DWGPREFIX": "C:/work/", "DWGNAME": "source.dxf"}
            if command == "drawing-get-variables"
            else {"ready": True}
        )

        self.assertEqual({"path": "C:/work/source.dxf"}, client.drawing_open("C:/work/source.dxf"))
        self.assertEqual(["_.QNEW"], [event[1] for event in events if event[0] == "command"])
        self.assertEqual([False, False, True], [event[1] for event in events if event[0] == "ready"])
        first_lisp = next(index for index, event in enumerate(events) if event[0] == "lisp")
        last_ready = max(index for index, event in enumerate(events) if event[0] == "ready")
        self.assertLess(last_ready, first_lisp)
        self.assertTrue(any('(load "C:/tools/mcp_dispatch.lsp")' in command for command in raw_commands))

    def test_start_tab_bootstrap_times_out_before_lisp_when_qnew_is_not_confirmed(self):
        raw_commands = []
        command_sequences = []
        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            start_tab_no_document_probe=lambda: True,
            bootstrap_document_ready_probe=lambda: False,
            bootstrap_start_tab=True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        with self.assertRaisesRegex(MCPTimeoutError, "START_TAB_BOOTSTRAP_DOCUMENT_NOT_READY"):
            client.drawing_open("C:/work/source.dxf")

        self.assertEqual(["_.QNEW"], command_sequences)
        self.assertEqual([], raw_commands)
        self.assertFalse(client._start_tab_bootstrap_active)

    def test_start_tab_session_script_is_qnew_only_and_binds_launched_process(self):
        process = SimpleNamespace(pid=7301, poll=lambda: None)
        launch_calls = []
        close_calls = []
        lisp_path = Path(self._ipc_dir) / "mcp_dispatch.lsp"
        plugin_path = Path(self._ipc_dir) / "CadAgent.AutoCAD2027.dll"
        lisp_path.write_text("; test dispatcher\n", encoding="utf-8")
        plugin_path.write_bytes(b"test plugin")

        def launch(executable, script_path):
            launch_calls.append((executable, script_path, script_path.read_bytes()))
            return process

        def find_window(pid):
            launch_calls[0][1].with_suffix(".marker").write_text(
                "CAD_AGENT_START_TAB_BOOTSTRAP_COMPLETE\n", encoding="ascii"
            )
            return 8801 if pid == process.pid else 0

        def close_window(hwnd):
            close_calls.append(hwnd)
            process.poll = lambda: 0

        session = mcp_client_module.WindowsAutoCADStartTabSession(
            acad_executable="C:/Program Files/Autodesk/AutoCAD 2027/acad.exe",
            script_directory=self._ipc_dir,
            bootstrap_plugin_path=str(plugin_path),
            bootstrap_lisp_path=str(lisp_path),
            ipc_root=str(self._ipc_dir),
            timeout_s=0.01,
            poll_interval_s=0,
            process_launcher=launch,
            window_finder=find_window,
            window_closer=close_window,
            start_probe_factory=lambda hwnd: lambda: True,
            document_ready_probe_factory=lambda hwnd: lambda: True,
        )

        bindings = session.launch_blank_document()
        self.assertEqual(8801, bindings.hwnd)
        self.assertTrue(bindings.dispatcher_preloaded)
        self.assertTrue(bindings.bootstrap_completion_confirmed)
        self.assertEqual(1, len(launch_calls))
        script = launch_calls[0][2].decode("utf-8")
        self.assertTrue(script.startswith("_.QNEW\r\n"))
        self.assertIn("_.NETLOAD\r\n", script)
        self.assertIn(plugin_path.as_posix(), script)
        self.assertIn(
            '(setq *cad-agent-file-ipc-root* "'
            + Path(self._ipc_dir).as_posix()
            + '")',
            script,
        )
        self.assertIn('(load "' + lisp_path.as_posix() + '")', script)
        self.assertIn("CAD_AGENT_START_TAB_BOOTSTRAP_COMPLETE", script)
        marker_path = launch_calls[0][1].with_suffix(".marker")
        self.assertIn(marker_path.as_posix(), script)
        self.assertIn(
            '(progn (setq cad-agent-stage-file (open "'
            + marker_path.as_posix()
            + '" "w")) (if cad-agent-stage-file (progn (write-line '
            + '"CAD_AGENT_START_TAB_BOOTSTRAP_COMPLETE"'
            + " cad-agent-stage-file) (close cad-agent-stage-file))))",
            script,
        )
        self.assertNotIn("BVTL", script)
        self.assertNotIn("SAVE", script)
        self.assertNotIn("EXTRACTION", script)

        session.close_without_save()
        self.assertEqual([8801], close_calls)
        self.assertFalse(launch_calls[0][1].exists())
        self.assertFalse(launch_calls[0][1].with_suffix(".marker").exists())

    def test_start_tab_session_rejects_wrong_completion_marker_and_cleans_it(self):
        process = SimpleNamespace(pid=7304, poll=lambda: None)
        launch_calls = []
        close_calls = []
        lisp_path = Path(self._ipc_dir) / "mcp_dispatch.lsp"
        lisp_path.write_text("; test dispatcher\n", encoding="utf-8")

        def launch(executable, script_path):
            launch_calls.append((executable, script_path))
            script_path.with_suffix(".marker").write_text(
                "WRONG_BOOTSTRAP_TOKEN\n", encoding="ascii"
            )
            return process

        def close_window(hwnd):
            close_calls.append(hwnd)
            process.poll = lambda: 0

        session = mcp_client_module.WindowsAutoCADStartTabSession(
            acad_executable="C:/Program Files/AutoCAD 2027/acad.exe",
            script_directory=self._ipc_dir,
            bootstrap_lisp_path=str(lisp_path),
            ipc_root=self._ipc_dir,
            timeout_s=0.01,
            poll_interval_s=0,
            process_launcher=launch,
            window_finder=lambda pid: 8806,
            window_closer=close_window,
            start_probe_factory=lambda hwnd: lambda: True,
            document_ready_probe_factory=lambda hwnd: lambda: True,
        )
        with self.assertRaisesRegex(
            MCPTimeoutError, "START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED"
        ):
            session.launch_blank_document()

        self.assertEqual([8806], close_calls)
        self.assertFalse(launch_calls[0][1].with_suffix(".marker").exists())

    def test_start_tab_session_best_effort_terminates_owned_process_after_close_timeout(self):
        process = SimpleNamespace(pid=7302, poll=lambda: None)
        terminate_calls = []

        def terminate():
            terminate_calls.append(True)
            process.poll = lambda: 0

        process.terminate = terminate
        session = mcp_client_module.WindowsAutoCADStartTabSession(
            acad_executable="C:/Program Files/Autodesk/AutoCAD 2027/acad.exe",
            script_directory=self._ipc_dir,
            timeout_s=0,
            poll_interval_s=0,
            process_launcher=lambda executable, script_path: process,
            window_finder=lambda pid: 8802,
            window_closer=lambda hwnd: None,
            start_probe_factory=lambda hwnd: lambda: True,
            bindings_factory=lambda hwnd: SimpleNamespace(hwnd=hwnd),
        )

        session.launch_blank_document()
        session.close_without_save(best_effort=True)

        self.assertEqual([True], terminate_calls)
        self.assertFalse(session._script_path)

    def test_opt_in_start_tab_uses_startup_session_not_keyboard_qnew(self):
        events = []
        raw_commands = []
        session = SimpleNamespace(
            launch_blank_document=lambda: (
                events.append("launch"),
                SimpleNamespace(
                    hwnd=8801,
                    command_trigger=lambda command: events.append(("command", command)),
                    raw_lisp_trigger=lambda command: (
                        raw_commands.append(command), events.append(("lisp", command))
                    ),
                    dispatch_trigger=_claim_bound_trigger(
                        lambda: events.append("dispatch")
                    ),
                    start_tab_no_document_probe=lambda: True,
                    document_ready_probe=lambda: True,
                    dispatcher_preloaded=True,
                    bootstrap_completion_confirmed=True,
                ),
            )[1],
            close_without_save=lambda: events.append("close"),
        )
        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            bootstrap_start_tab=True,
            bootstrap_start_tab_session_factory=lambda: session,
            bootstrap_document_setup_hook=lambda: events.append("setup"),
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )
        def dispatch(command, params):
            if command == "ping":
                self.assertFalse(client._legacy_fixture_mode)
                events.append("ping")
            if command == "drawing-get-variables":
                return {"DWGPREFIX": "C:/work/", "DWGNAME": "source.dxf"}
            return {"ready": True}

        client._dispatch = dispatch

        self.assertEqual({"path": "C:/work/source.dxf"}, client.drawing_open("C:/work/source.dxf"))
        self.assertEqual("launch", events[0])
        self.assertIn("setup", events)
        self.assertLess(events.index("ping"), events.index("setup"))
        self.assertFalse(any(event == ("command", "_.QNEW") for event in events))
        self.assertFalse(any('(load "C:/tools/mcp_dispatch.lsp")' in command for command in raw_commands))
        client.close_start_tab_bootstrap()
        self.assertIn("close", events)

    def test_preloaded_start_tab_dispatcher_ping_failure_closes_before_source_open(self):
        raw_commands = []
        events = []

        def close_without_save(*, best_effort=False):
            events.append(("close", best_effort))

        session = SimpleNamespace(
            launch_blank_document=lambda: SimpleNamespace(
                hwnd=8803,
                command_trigger=lambda command: events.append(("command", command)),
                raw_lisp_trigger=raw_commands.append,
                dispatch_trigger=_claim_bound_trigger(lambda: None),
                start_tab_no_document_probe=lambda: True,
                document_ready_probe=lambda: True,
                dispatcher_preloaded=True,
                bootstrap_completion_confirmed=True,
            ),
            close_without_save=close_without_save,
        )
        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            bootstrap_start_tab=True,
            bootstrap_start_tab_session_factory=lambda: session,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        def dispatch(command, params):
            if command == "ping":
                raise MCPTimeoutError("dispatcher unavailable")
            self.fail("source dispatch must not run")

        client._dispatch = dispatch

        with self.assertRaisesRegex(MCPTimeoutError, "dispatcher unavailable"):
            client.drawing_open("C:/work/source.dxf")

        self.assertIn(("close", True), events)
        self.assertEqual([], raw_commands)
        self.assertFalse(client._start_tab_bootstrap_active)

    def test_start_tab_session_readiness_timeout_closes_owned_process_before_source_open(self):
        raw_commands = []
        events = []
        def close_without_save(*, best_effort=False):
            events.append("close")
        session = SimpleNamespace(
            launch_blank_document=lambda: SimpleNamespace(
                hwnd=8801,
                command_trigger=lambda command: events.append(("command", command)),
                raw_lisp_trigger=raw_commands.append,
                dispatch_trigger=_claim_bound_trigger(lambda: None),
                start_tab_no_document_probe=lambda: True,
                document_ready_probe=lambda: False,
                bootstrap_completion_confirmed=True,
            ),
            close_without_save=close_without_save,
        )
        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            bootstrap_start_tab=True,
            bootstrap_start_tab_session_factory=lambda: session,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        with self.assertRaisesRegex(MCPTimeoutError, "START_TAB_BOOTSTRAP_DOCUMENT_NOT_READY"):
            client.drawing_open("C:/work/source.dxf")

        self.assertIn("close", events)
        self.assertEqual([], raw_commands)
        self.assertFalse(client._start_tab_bootstrap_active)

    def test_start_tab_session_rejects_unconfirmed_bootstrap_before_dispatch(self):
        events = []
        session = SimpleNamespace(
            launch_blank_document=lambda: SimpleNamespace(
                hwnd=8805,
                command_trigger=lambda command: events.append(("command", command)),
                raw_lisp_trigger=lambda command: events.append(("lisp", command)),
                dispatch_trigger=_claim_bound_trigger(lambda: events.append("dispatch")),
                start_tab_no_document_probe=lambda: True,
                document_ready_probe=lambda: True,
                dispatcher_preloaded=True,
                bootstrap_completion_confirmed=False,
            ),
            close_without_save=lambda **kwargs: events.append(("close", kwargs)),
        )
        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            bootstrap_start_tab=True,
            bootstrap_start_tab_session_factory=lambda: session,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )
        client._dispatch = lambda command, params: self.fail(
            "dispatcher must not run before bootstrap completion acknowledgement"
        )

        with self.assertRaisesRegex(
            MCPToolError, "START_TAB_BOOTSTRAP_COMPLETION_REQUIRED"
        ):
            client.drawing_open("C:/work/source.dxf")

        self.assertNotIn("dispatch", events)
        self.assertIn(("close", {"best_effort": True}), events)

    def test_start_tab_session_requires_completion_ack_after_document_ready(self):
        process = SimpleNamespace(pid=7303, poll=lambda: None)
        launch_calls = []
        close_calls = []
        lisp_path = Path(self._ipc_dir) / "mcp_dispatch.lsp"
        lisp_path.write_text("; test dispatcher\n", encoding="utf-8")

        def launch(executable, script_path):
            launch_calls.append((executable, script_path))
            return process

        def close_window(hwnd):
            close_calls.append(hwnd)
            process.poll = lambda: 0

        session = mcp_client_module.WindowsAutoCADStartTabSession(
            acad_executable="C:/Program Files/AutoCAD 2027/acad.exe",
            script_directory=self._ipc_dir,
            bootstrap_lisp_path=str(lisp_path),
            ipc_root=str(self._ipc_dir),
            timeout_s=0.01,
            poll_interval_s=0,
            process_launcher=launch,
            window_finder=lambda pid: 8805,
            window_closer=close_window,
            start_probe_factory=lambda hwnd: lambda: True,
            document_ready_probe_factory=lambda hwnd: lambda: True,
        )

        with self.assertRaisesRegex(
            MCPTimeoutError, "START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED"
        ):
            session.launch_blank_document()

        self.assertEqual([8805], close_calls)
        self.assertFalse(session._script_path)

    def test_start_tab_session_rejects_unclaimed_dispatcher_trigger(self):
        events = []
        session = SimpleNamespace(
            launch_blank_document=lambda: SimpleNamespace(
                hwnd=8804,
                command_trigger=lambda command: events.append(("command", command)),
                raw_lisp_trigger=lambda command: events.append(("lisp", command)),
                dispatch_trigger=lambda: None,
                start_tab_no_document_probe=lambda: True,
                document_ready_probe=lambda: True,
                dispatcher_preloaded=True,
            ),
            close_without_save=lambda **kwargs: events.append(("close", kwargs)),
        )
        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            bootstrap_start_tab=True,
            bootstrap_start_tab_session_factory=lambda: session,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        with self.assertRaisesRegex(
            MCPToolError, "START_TAB_BOOTSTRAP_CLAIM_REQUIRED"
        ):
            client.drawing_open("C:/work/source.dxf")

        self.assertIn(("close", {"best_effort": True}), events)
        self.assertTrue(client._legacy_fixture_mode)

    def test_start_tab_bootstrap_does_not_run_when_real_document_is_active(self):
        raw_commands = []
        command_sequences = []
        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            start_tab_no_document_probe=lambda: False,
            bootstrap_start_tab=True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )
        client._dispatch = lambda command, params: (
            {"DWGPREFIX": "C:/work/", "DWGNAME": "active.dxf"}
            if command == "drawing-get-variables"
            else {"ready": True}
        )

        self.assertEqual({"path": "C:/work/active.dxf"}, client.drawing_open("C:/work/active.dxf"))
        self.assertEqual([], command_sequences)
        self.assertFalse(client._start_tab_bootstrap_active)
        self.assertTrue(any("vla-open mcp-docs" in command for command in raw_commands))

    def test_start_tab_bootstrap_requires_positive_probe(self):
        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=lambda command: self.fail("raw LISP must not run"),
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=lambda command: self.fail("QNEW must not run"),
            bootstrap_start_tab=True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        with self.assertRaisesRegex(MCPToolError, "START_TAB_BOOTSTRAP_PROBE_REQUIRED"):
            client.drawing_open("C:/work/source.dxf")

    def test_start_tab_bootstrap_ping_failure_closes_blank_without_source_open(self):
        raw_commands = []
        command_sequences = []

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            start_tab_no_document_probe=lambda: True,
            bootstrap_document_ready_probe=lambda: True,
            bootstrap_start_tab=True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )
        client._dispatch = lambda command, params: (
            (_ for _ in ()).throw(MCPTimeoutError("bootstrap ping timeout"))
            if command == "ping"
            else {}
        )

        with self.assertRaisesRegex(MCPTimeoutError, "bootstrap ping timeout"):
            client.drawing_open("C:/work/source.dxf")

        self.assertEqual(["_.QNEW"], command_sequences)
        self.assertFalse(client._start_tab_bootstrap_active)
        self.assertTrue(any('(load "C:/tools/mcp_dispatch.lsp")' in command for command in raw_commands))
        self.assertIn('command-s "_.CLOSE" "_N"', raw_commands[-1])
        self.assertFalse(any("vla-open mcp-docs" in command for command in raw_commands))

    def test_start_tab_bootstrap_load_failure_closes_blank_without_source_open(self):
        raw_commands = []
        command_sequences = []

        def raw_trigger(command):
            raw_commands.append(command)
            if '(load "C:/tools/mcp_dispatch.lsp")' in command:
                raise MCPToolError("bootstrap load failed")

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=raw_trigger,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            start_tab_no_document_probe=lambda: True,
            bootstrap_document_ready_probe=lambda: True,
            bootstrap_start_tab=True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        with self.assertRaisesRegex(MCPToolError, "bootstrap load failed"):
            client.drawing_open("C:/work/source.dxf")

        self.assertEqual(["_.QNEW"], command_sequences)
        self.assertFalse(client._start_tab_bootstrap_active)
        self.assertIn('command-s "_.CLOSE" "_N"', raw_commands[-1])
        self.assertFalse(any("vla-open mcp-docs" in command for command in raw_commands))

    def test_start_tab_bootstrap_command_failure_fails_closed_before_source_open(self):
        raw_commands = []
        command_sequences = []

        def command_trigger(command):
            command_sequences.append(command)
            raise MCPToolError("QNEW failed")

        client = FileIPCLiveMCPClient(
            ipc_dir=self._ipc_dir,
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_trigger,
            start_tab_no_document_probe=lambda: True,
            bootstrap_start_tab=True,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )

        with self.assertRaisesRegex(MCPToolError, "QNEW failed"):
            client.drawing_open("C:/work/source.dxf")

        self.assertEqual(["_.QNEW"], command_sequences)
        self.assertEqual([], raw_commands)

    def test_start_tab_probe_factory_requires_positive_integer_window_handle(self):
        factory = getattr(mcp_client_module, "make_windows_start_tab_no_document_probe", None)
        self.assertTrue(callable(factory))
        for invalid in (0, -1, None, "123", 1.5, True):
            with self.subTest(hwnd=invalid):
                with self.assertRaises(ValueError):
                    factory(invalid)

    def test_start_tab_probe_matches_only_start_window_title(self):
        class FakeUser32:
            def __init__(self):
                self.title = "Autodesk AutoCAD 2027 - [Start]"

            def GetWindowTextLengthW(self, hwnd):
                return len(self.title)

            def GetWindowTextW(self, hwnd, buffer, length):
                buffer.value = self.title
                return len(self.title)

        fake_user32 = FakeUser32()
        with patch.object(mcp_client_module.ctypes.windll, "user32", fake_user32):
            probe = mcp_client_module.make_windows_start_tab_no_document_probe(9001)
            self.assertTrue(probe())
            fake_user32.title = "Autodesk AutoCAD 2027 - [Drawing1.dwg]"
            self.assertFalse(probe())

    def test_start_tab_document_ready_probe_matches_non_start_document_title(self):
        class FakeUser32:
            def __init__(self):
                self.title = "Autodesk AutoCAD 2027 - [Start]"

            def GetWindowTextLengthW(self, hwnd):
                return len(self.title)

            def GetWindowTextW(self, hwnd, buffer, length):
                buffer.value = self.title
                return len(self.title)

        fake_user32 = FakeUser32()
        with patch.object(mcp_client_module.ctypes.windll, "user32", fake_user32):
            factory = getattr(mcp_client_module, "make_windows_start_tab_document_ready_probe", None)
            self.assertTrue(callable(factory))
            probe = factory(9001)
            self.assertFalse(probe())
            fake_user32.title = "Autodesk AutoCAD 2027 - [Drawing1.dwg]"
            self.assertTrue(probe())

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
