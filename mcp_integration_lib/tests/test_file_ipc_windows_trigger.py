"""Corrected RED contract for the existing Windows File-IPC trigger owner.

This file is deliberately offline.  The native user32 double records the
current owner's calls but never starts AutoCAD, COM, File IPC, or a second
transport.  The RED assertions identify the missing execution-proof-capable
boundary without inventing a public receipt or ACK schema.
"""
from __future__ import annotations

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


class RecordingUser32:
    """Deterministic native boundary fake; it never executes AutoLISP."""

    def __init__(
        self,
        *,
        children: list[tuple[int, str, int]] | None = None,
        pid_sequences: dict[int, list[int]] | None = None,
        foreground_hwnd: int = OWNED_HWND,
        send_returns: list[int] | None = None,
        last_errors: list[int] | None = None,
        send_result: int = 1,
    ) -> None:
        self.children = children if children is not None else [
            (RECEIVER_HWND, "MDIClient", OWNED_PID)
        ]
        self.pid_sequences = pid_sequences or {}
        self.foreground_hwnd = foreground_hwnd
        self.send_returns = send_returns or [1]
        self.last_errors = last_errors or [0]
        self.send_result = send_result
        self.enum_calls: list[tuple[int, int]] = []
        self.window_pid_calls: list[int] = []
        self._pid_call_counts: dict[int, int] = {}
        self.focus_calls: list[tuple[str, int]] = []
        self.post_calls: list[tuple[int, int, int, int]] = []
        self.send_calls: list[tuple[int, int, int, int, int, int]] = []
        self.message_calls: list[tuple[str, int, int, int, int]] = []
        self._last_error_calls = 0
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
        return 1

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
        return self.send_returns[min(call_index, len(self.send_returns) - 1)]

    def GetLastError(self):
        error = self.last_errors[min(self._last_error_calls, len(self.last_errors) - 1)]
        self._last_error_calls += 1
        return error


class WindowsTriggerExecutionRedTests(unittest.TestCase):
    def _run_current_trigger(self, user32: RecordingUser32, text: str = EXPRESSION):
        with patch.object(mcp_client.ctypes.windll, "user32", user32):
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
            [call[1] for call in user32.send_calls],
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
            [0x0002] * len(EXPECTED_FRAMED_TEXT),
        )
        self.assertEqual(
            [call[5] for call in user32.send_calls],
            [1000] * len(EXPECTED_FRAMED_TEXT),
        )

    def test_bounded_native_zero_timeout_and_error_fail_closed(self) -> None:
        cases = {
            "zero": (0, 0, MCPToolError),
            "timeout": (0, 1460, MCPTimeoutError),
            "native-error": (0, 5, MCPToolError),
        }
        for case, (send_return, last_error, expected_error) in cases.items():
            with self.subTest(case=case):
                user32 = RecordingUser32(
                    send_returns=[send_return],
                    last_errors=[last_error],
                )
                with self.assertRaises(expected_error) as raised:
                    self._run_current_trigger(user32)
                self.assertEqual(len(user32.send_calls), 1)
                self.assertEqual(user32.post_calls, [])
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
        self.assertTrue(all(target == RECEIVER_HWND for target, *_ in user32.post_calls))

    def test_trigger_does_not_create_a_second_fileipc_owner(self) -> None:
        """The native text boundary must not create a second IPC lifecycle."""
        user32 = RecordingUser32()
        with patch.object(
            mcp_client,
            "FileIPCLiveMCPClient",
            side_effect=AssertionError("trigger created a second FileIPC owner"),
        ):
            self._run_current_trigger(user32)


if __name__ == "__main__":
    unittest.main()
