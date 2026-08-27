"""RED contract for the existing Windows File-IPC trigger owner.

This file is deliberately offline.  The fake user32 surface records the
current owner's native calls but never starts AutoCAD, COM, File IPC, or a
second transport.  The failures are the owner boundary under repair: queued
WM_CHAR delivery is not caller-visible AutoLISP execution proof.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from mcp_integration_lib import mcp_client
from mcp_integration_lib.mcp_client import (
    MCPToolError,
    MCPTimeoutError,
    make_windows_lisp_trigger,
)


OWNED_HWND = 0x1001
OWNED_PID = 0x2001
FOREIGN_HWND = 0x1002
FOREIGN_PID = 0x2002
EXPRESSION = '(setq *r8d-test* "é")'
EXPECTED_FRAMED_TEXT = "\x1b\x1b" + EXPRESSION + "\r"


class RecordingUser32:
    """Deterministic native boundary fake; it never executes AutoLISP."""

    def __init__(self, *, receiver_hwnd: int = 0x1101, receiver_pid: int = OWNED_PID) -> None:
        self.receiver_hwnd = receiver_hwnd
        self.receiver_pid = receiver_pid
        self.enum_calls: list[tuple[int, int]] = []
        self.window_pid_calls: list[int] = []
        self.focus_calls: list[tuple[str, int]] = []
        self.post_calls: list[tuple[int, int, int, int]] = []
        self.post_return = 1
        self.execution_ack: dict[str, object] | None = None

    def EnumChildWindows(self, hwnd, callback, lparam):
        self.enum_calls.append((hwnd, lparam))
        callback(self.receiver_hwnd, lparam)

    def GetClassNameW(self, child, buffer, _length):
        buffer.value = "MDIClient" if child == self.receiver_hwnd else "Other"
        return len(buffer.value)

    def GetWindowThreadProcessId(self, hwnd, pid_pointer):
        self.window_pid_calls.append(hwnd)
        pid_pointer._obj.value = self.receiver_pid if hwnd == self.receiver_hwnd else OWNED_PID
        return 1

    def ShowWindow(self, hwnd, command):
        self.focus_calls.append(("ShowWindow", hwnd))
        return 1

    def SetForegroundWindow(self, hwnd):
        self.focus_calls.append(("SetForegroundWindow", hwnd))
        return 1

    def PostMessageW(self, target, message, wparam, lparam):
        self.post_calls.append((target, message, wparam, lparam))
        return self.post_return


class WindowsTriggerExecutionRedTests(unittest.TestCase):
    def _run_current_trigger(self, user32: RecordingUser32, text: str = EXPRESSION):
        with patch.object(mcp_client.ctypes.windll, "user32", user32):
            trigger = make_windows_lisp_trigger(OWNED_HWND)
            return trigger(text)

    def test_current_owner_binds_exact_hwnd_and_pid_before_delivery(self) -> None:
        """A positive HWND alone cannot reject stale or foreign PID custody."""
        user32 = RecordingUser32(receiver_hwnd=OWNED_HWND, receiver_pid=FOREIGN_PID)
        try:
            trigger = make_windows_lisp_trigger(OWNED_HWND, OWNED_PID)
        except TypeError as exc:
            self.fail(
                "current owner has no exact HWND/PID binding boundary: "
                f"{exc}"
            )
        with patch.object(mcp_client.ctypes.windll, "user32", user32):
            with self.assertRaises(MCPToolError):
                trigger(EXPRESSION)

    def test_foreign_receiver_is_rejected_before_any_post(self) -> None:
        user32 = RecordingUser32(receiver_hwnd=FOREIGN_HWND, receiver_pid=FOREIGN_PID)
        with self.assertRaises(MCPToolError):
            self._run_current_trigger(user32)
        self.assertEqual(user32.post_calls, [])

    def test_delivery_failure_or_timeout_is_categorical(self) -> None:
        user32 = RecordingUser32()
        user32.post_return = 0
        with self.assertRaises((MCPToolError, MCPTimeoutError)):
            self._run_current_trigger(user32)

    def test_queue_return_is_not_execution_ack(self) -> None:
        """PostMessageW success must not be reported as executed AutoLISP."""
        user32 = RecordingUser32()
        result = self._run_current_trigger(user32)
        self.assertIsNotNone(result, "queued delivery returned without an execution receipt")
        self.assertTrue(result["execution_ack"]["executed"])

    def test_expression_framing_is_exact_and_bounded(self) -> None:
        user32 = RecordingUser32()
        self._run_current_trigger(user32)
        self.assertEqual([call[0] for call in user32.post_calls], [user32.receiver_hwnd] * len(EXPECTED_FRAMED_TEXT))
        self.assertEqual([call[1] for call in user32.post_calls], [0x0102] * len(EXPECTED_FRAMED_TEXT))
        self.assertEqual("".join(chr(call[2]) for call in user32.post_calls), EXPECTED_FRAMED_TEXT)
        self.assertEqual([call[3] for call in user32.post_calls], [0] * len(EXPECTED_FRAMED_TEXT))

    def test_execution_ack_requires_exact_run_target_and_expression_identity(self) -> None:
        user32 = RecordingUser32()
        user32.execution_ack = {
            "run_id": "run-red-001",
            "hwnd": OWNED_HWND,
            "pid": OWNED_PID,
            "expression_sha256": "expected-expression-sha256",
            "executed": True,
        }
        result = self._run_current_trigger(user32)
        self.assertIsNotNone(result, "caller-visible execution acknowledgement is missing")
        self.assertEqual(result["execution_ack"], user32.execution_ack)

    def test_receiver_discovery_is_single_owned_mdi_boundary(self) -> None:
        user32 = RecordingUser32()
        self._run_current_trigger(user32)
        self.assertEqual(user32.enum_calls, [(OWNED_HWND, 0)])
        self.assertEqual(set(user32.window_pid_calls), {user32.receiver_hwnd})
        self.assertTrue(all(target == user32.receiver_hwnd for target, *_ in user32.post_calls))

    def test_trigger_does_not_create_a_second_fileipc_owner(self) -> None:
        user32 = RecordingUser32()
        self._run_current_trigger(user32)
        self.assertEqual(user32.execution_ack, None)


if __name__ == "__main__":
    unittest.main()
