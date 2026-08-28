"""Corrected RED contract for the existing Windows File-IPC trigger owner.

This file is deliberately offline.  The native user32 double records the
current owner's calls but never starts AutoCAD, COM, File IPC, or a second
transport.  The RED assertions identify the missing execution-proof-capable
boundary without inventing a public receipt or ACK schema.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
import unittest
from unittest.mock import patch

from mcp_integration_lib import mcp_client
from mcp_integration_lib.mcp_client import (
    MCPToolError,
    MCPTimeoutError,
    make_windows_dispatch_trigger,
    make_windows_lisp_trigger,
)


OWNED_HWND = 0x1001
OWNED_PID = 0x2001
FOREIGN_HWND = 0x1002
FOREIGN_PID = 0x2002
RECEIVER_HWND = 0x1101
EXPRESSION = '(setq *r8d-test* "é")'
EXPECTED_FRAMED_TEXT = "\x1b\x1b" + EXPRESSION + "\r"


class RecordingKernel32:
    """Thread last-error surface used by the real bounded-send contract."""

    def __init__(self) -> None:
        self.last_error = 0
        self.set_calls: list[int] = []
        self.get_calls: list[int] = []

    def SetLastError(self, error):
        self.set_calls.append(error)
        self.last_error = error

    def GetLastError(self):
        self.get_calls.append(self.last_error)
        return self.last_error

    def set_native_error(self, error: int) -> None:
        """Model the native call's thread error without inventing a user32 API."""
        self.last_error = error


class RecordingUser32:
    """Deterministic native boundary fake; it never executes AutoLISP."""

    def __init__(
        self,
        *,
        children: list[tuple[int, str, int]] | None = None,
        pid_sequences: dict[int, list[int]] | None = None,
        foreground_hwnd: int = OWNED_HWND,
        set_foreground_result: int = 1,
        send_returns: list[int] | None = None,
        send_errors: list[int] | None = None,
        send_result: int = 1,
    ) -> None:
        self.children = children if children is not None else [
            (RECEIVER_HWND, "MDIClient", OWNED_PID)
        ]
        self.pid_sequences = pid_sequences or {}
        self.foreground_hwnd = foreground_hwnd
        self.set_foreground_result = set_foreground_result
        self.send_returns = send_returns or [1]
        self.send_errors = send_errors or [0]
        self.send_result = send_result
        self.kernel32 = RecordingKernel32()
        self.enum_calls: list[tuple[int, int]] = []
        self.window_pid_calls: list[int] = []
        self._pid_call_counts: dict[int, int] = {}
        self.focus_calls: list[tuple[str, int]] = []
        self.post_calls: list[tuple[int, int, int, int]] = []
        self.send_calls: list[tuple[int, int, int, int, int, int]] = []
        self.message_calls: list[tuple[str, int, int, int, int]] = []
        self.class_names = {child: name for child, name, _pid in self.children}
        self.child_pids = {child: pid for child, _name, pid in self.children}

    def EnumChildWindows(self, hwnd, callback, lparam):
        self.enum_calls.append((hwnd, lparam))
        for child, _name, _pid in self.children:
            if not callback(child, lparam):
                break

    def GetClassNameW(self, child, buffer, _length):
        buffer.value = self.class_names.get(child, "Other")
        return len(buffer.value)

    def GetWindowThreadProcessId(self, hwnd, pid_pointer):
        self.window_pid_calls.append(hwnd)
        sequence = self.pid_sequences.get(hwnd, [self.child_pids.get(hwnd, OWNED_PID)])
        call_index = self._pid_call_counts.get(hwnd, 0)
        self._pid_call_counts[hwnd] = call_index + 1
        pid_pointer._obj.value = sequence[min(call_index, len(sequence) - 1)]
        return 1

    def GetForegroundWindow(self):
        return self.foreground_hwnd

    def ShowWindow(self, hwnd, command):
        self.focus_calls.append(("ShowWindow", hwnd))
        return 1

    def SetForegroundWindow(self, hwnd):
        self.focus_calls.append(("SetForegroundWindow", hwnd))
        return self.set_foreground_result

    def PostMessageW(self, target, message, wparam, lparam):
        call = (target, message, wparam, lparam)
        self.post_calls.append(call)
        self.message_calls.append(("PostMessageW", target, message, wparam, lparam))
        return 1

    def SendMessageTimeoutW(self, target, message, wparam, lparam, flags, timeout, result_pointer):
        self.send_calls.append((target, message, wparam, lparam, flags, timeout))
        self.message_calls.append(("SendMessageTimeoutW", target, message, wparam, lparam))
        result_pointer._obj.value = self.send_result
        call_index = len(self.send_calls) - 1
        self.kernel32.set_native_error(
            self.send_errors[min(call_index, len(self.send_errors) - 1)]
        )
        return self.send_returns[min(call_index, len(self.send_returns) - 1)]


class ForegroundChurningUser32(RecordingUser32):
    """Model an already-foreground window losing focus when reacquired."""

    def ShowWindow(self, hwnd, command):
        result = super().ShowWindow(hwnd, command)
        self.foreground_hwnd = FOREIGN_HWND
        return result

    def SetForegroundWindow(self, hwnd):
        super().SetForegroundWindow(hwnd)
        return 0


class ReacquiringUser32(RecordingUser32):
    """Model the allowed reacquisition path succeeding before delivery."""

    def SetForegroundWindow(self, hwnd):
        result = super().SetForegroundWindow(hwnd)
        self.foreground_hwnd = hwnd
        return result


class WindowsTriggerExecutionRedTests(unittest.TestCase):
    def _run_current_trigger(self, user32: RecordingUser32, text: str = EXPRESSION):
        with (
            patch.object(mcp_client.ctypes.windll, "user32", user32),
            patch.object(mcp_client.ctypes.windll, "kernel32", user32.kernel32),
        ):
            trigger = make_windows_lisp_trigger(OWNED_HWND)
            return trigger(text)

    def test_public_factories_remain_one_argument_compatible(self) -> None:
        lisp_trigger = make_windows_lisp_trigger(OWNED_HWND)
        dispatch_trigger = make_windows_dispatch_trigger(OWNED_HWND)
        self.assertTrue(callable(lisp_trigger))
        self.assertTrue(callable(dispatch_trigger))
        self.assertTrue(getattr(dispatch_trigger, "_mcp_claim_bound", False))

    def test_hwnd_pid_drift_is_rejected_before_delivery(self) -> None:
        """A stale PID after initial binding cannot reach the native queue."""
        user32 = RecordingUser32(
            children=[(OWNED_HWND, "MDIClient", OWNED_PID)],
            pid_sequences={OWNED_HWND: [OWNED_PID, FOREIGN_PID]},
        )
        with self.assertRaises(MCPToolError):
            self._run_current_trigger(user32)
        self.assertEqual(user32.post_calls, [])

    def test_receiver_matrix_fails_closed_without_exactly_one_owned_mdi(self) -> None:
        cases = {
            "zero-owned": [],
            "foreign-only": [(FOREIGN_HWND, "MDIClient", FOREIGN_PID)],
            "multiple-owned": [
                (0x1102, "MDIClient", OWNED_PID),
                (0x1103, "MDIClient", OWNED_PID),
            ],
        }
        for case, children in cases.items():
            with self.subTest(case=case):
                user32 = RecordingUser32(children=children)
                with self.assertRaises(MCPToolError):
                    self._run_current_trigger(user32)
                self.assertEqual(user32.post_calls, [])

    def test_single_owned_mdi_is_selected_even_with_foreign_children(self) -> None:
        user32 = RecordingUser32(
            children=[
                (FOREIGN_HWND, "MDIClient", FOREIGN_PID),
                (RECEIVER_HWND, "MDIClient", OWNED_PID),
            ]
        )
        self._run_current_trigger(user32)
        self.assertEqual(
            [call[0] for call in user32.send_calls],
            [RECEIVER_HWND] * len(EXPECTED_FRAMED_TEXT),
        )
        self.assertEqual(user32.post_calls, [])

    def test_receiver_pid_drift_at_delivery_boundary_is_rejected(self) -> None:
        user32 = RecordingUser32(
            children=[(RECEIVER_HWND, "MDIClient", OWNED_PID)],
            pid_sequences={RECEIVER_HWND: [OWNED_PID, FOREIGN_PID]},
        )
        with self.assertRaises(MCPToolError):
            self._run_current_trigger(user32)
        self.assertEqual(user32.post_calls, [])

    def test_foreground_readback_mismatch_is_rejected_before_delivery(self) -> None:
        user32 = RecordingUser32(
            children=[(RECEIVER_HWND, "MDIClient", OWNED_PID)],
            foreground_hwnd=FOREIGN_HWND,
        )
        with self.assertRaises(MCPToolError):
            self._run_current_trigger(user32)
        self.assertEqual(user32.post_calls, [])

    def test_exact_foreground_does_not_reacquire_before_delivery(self) -> None:
        """The exact foreground precondition must avoid a destructive reacquisition."""
        user32 = ForegroundChurningUser32()
        self._run_current_trigger(user32)
        self.assertEqual(user32.focus_calls, [])
        self.assertEqual(
            [call[0] for call in user32.send_calls],
            [RECEIVER_HWND] * len(EXPECTED_FRAMED_TEXT),
        )

    def test_not_foreground_reacquires_then_delivers(self) -> None:
        """A non-foreground exact owner may reacquire once, then deliver."""
        user32 = ReacquiringUser32(foreground_hwnd=FOREIGN_HWND)
        self._run_current_trigger(user32)
        self.assertEqual(
            user32.focus_calls,
            [("ShowWindow", OWNED_HWND), ("SetForegroundWindow", OWNED_HWND)],
        )
        self.assertEqual(user32.foreground_hwnd, OWNED_HWND)
        self.assertEqual(
            [call[0] for call in user32.send_calls],
            [RECEIVER_HWND] * len(EXPECTED_FRAMED_TEXT),
        )

    def test_set_foreground_return_zero_with_exact_readback_still_delivers(self) -> None:
        user32 = RecordingUser32(set_foreground_result=0)
        self._run_current_trigger(user32)
        self.assertEqual(user32.post_calls, [])
        self.assertEqual(
            [call[0] for call in user32.send_calls],
            [RECEIVER_HWND] * len(EXPECTED_FRAMED_TEXT),
        )
        self.assertEqual(
            [call[1] for call in user32.send_calls],
            [0x0102] * len(EXPECTED_FRAMED_TEXT),
        )

    def test_set_foreground_return_zero_with_foreign_readback_fails_closed(self) -> None:
        user32 = RecordingUser32(
            foreground_hwnd=FOREIGN_HWND,
            set_foreground_result=0,
        )
        with self.assertRaises(MCPToolError):
            self._run_current_trigger(user32)
        self.assertEqual(user32.send_calls, [])
        self.assertEqual(user32.post_calls, [])

    def test_bounded_native_delivery_uses_sendmessage_timeout(self) -> None:
        user32 = RecordingUser32(send_returns=[1] * len(EXPECTED_FRAMED_TEXT))
        self._run_current_trigger(user32)
        self.assertEqual(user32.post_calls, [])
        self.assertEqual(
            [call[0] for call in user32.send_calls],
            [RECEIVER_HWND] * len(EXPECTED_FRAMED_TEXT),
        )
        self.assertEqual(
            [call[1] for call in user32.send_calls],
            [0x0102] * len(EXPECTED_FRAMED_TEXT),
        )
        self.assertEqual(
            [call[4] for call in user32.send_calls],
            [0x0022] * len(EXPECTED_FRAMED_TEXT),
        )
        self.assertEqual(
            [call[5] for call in user32.send_calls],
            [1000] * len(EXPECTED_FRAMED_TEXT),
        )
        self.assertEqual(user32.kernel32.set_calls, [0] * len(EXPECTED_FRAMED_TEXT))
        self.assertEqual(user32.kernel32.get_calls, [])

    def test_bounded_native_zero_timeout_and_error_fail_closed(self) -> None:
        cases = {
            "zero": (0, 0, MCPToolError),
            "timeout": (0, 1460, MCPTimeoutError),
            "native-error": (0, 5, MCPToolError),
            "destroyed-receiver": (0, 1400, MCPToolError),
        }
        for case, (send_return, last_error, expected_error) in cases.items():
            with self.subTest(case=case):
                user32 = RecordingUser32(
                    send_returns=[send_return],
                    send_errors=[last_error],
                )
                with self.assertRaises(expected_error) as raised:
                    self._run_current_trigger(user32)
                self.assertEqual(len(user32.send_calls), 1)
                self.assertEqual(user32.post_calls, [])
                self.assertEqual(user32.kernel32.set_calls, [0])
                self.assertEqual(user32.kernel32.get_calls, [last_error])
                self.assertNotIn(EXPRESSION, str(raised.exception))

    def test_expression_framing_is_exact_and_bounded(self) -> None:
        user32 = RecordingUser32()
        self._run_current_trigger(user32)
        self.assertEqual(
            [call[1] for call in user32.message_calls],
            [RECEIVER_HWND] * len(EXPECTED_FRAMED_TEXT),
        )
        self.assertEqual(
            [call[2] for call in user32.message_calls],
            [0x0102] * len(EXPECTED_FRAMED_TEXT),
        )
        self.assertEqual(
            "".join(chr(call[3]) for call in user32.message_calls),
            EXPECTED_FRAMED_TEXT,
        )
        self.assertEqual(
            [call[4] for call in user32.message_calls],
            [0] * len(EXPECTED_FRAMED_TEXT),
        )

    def test_receiver_discovery_is_single_owned_mdi_boundary(self) -> None:
        user32 = RecordingUser32()
        self._run_current_trigger(user32)
        self.assertEqual(user32.enum_calls, [(OWNED_HWND, 0)])
        self.assertIn(RECEIVER_HWND, user32.window_pid_calls)
        self.assertEqual(len(user32.send_calls), len(EXPECTED_FRAMED_TEXT))
        self.assertTrue(user32.send_calls)
        self.assertTrue(all(target == RECEIVER_HWND for target, *_ in user32.send_calls))
        self.assertEqual(user32.post_calls, [])

    def test_trigger_owner_separation_oracle_and_native_route(self) -> None:
        """The native text owner has no FileIPC lifecycle or persistence dependency."""
        forbidden = {
            "FileIPCLiveMCPClient",
            "_dispatch",
            "_wait_for_dispatcher",
            "_FILE_IPC_REQUEST_PREFIX",
            "_FILE_IPC_RESULT_PREFIX",
            "_validate_file_ipc_root",
            "_file_ipc_root_identity",
            "Path",
            "uuid",
            "secrets",
            "json",
            "os",
        }

        def referenced_forbidden(source: str) -> set[str]:
            tree = ast.parse(textwrap.dedent(source))
            references = {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
            }
            references.update(
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
            )
            return references & forbidden

        synthetic = """
        def synthetic_trigger(text):
            return FileIPCLiveMCPClient(text)
        """
        self.assertEqual(referenced_forbidden(synthetic), {"FileIPCLiveMCPClient"})

        real_source = inspect.getsource(mcp_client._make_windows_text_trigger)
        self.assertEqual(referenced_forbidden(real_source), set())

        user32 = RecordingUser32()
        self._run_current_trigger(user32)
        self.assertEqual(
            [call[0] for call in user32.send_calls],
            [RECEIVER_HWND] * len(EXPECTED_FRAMED_TEXT),
        )
        self.assertEqual(user32.post_calls, [])


if __name__ == "__main__":
    unittest.main()
