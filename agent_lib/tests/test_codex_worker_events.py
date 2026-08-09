from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import agent_lib.codex_worker as worker
import agent_lib.codex_worker_process as worker_process
from agent_lib.codex_worker import CodexWorkerError


THREAD_ID = "THREAD-001"
TURN_ID = "TURN-001"
CANDIDATE = {"schema_version": "repair-plan-1.0"}
WORKER_SOURCE = Path(worker.__file__).read_text(encoding="utf-8")


def _event(kind: str, *, sequence: int | None = None, payload: object | None = None):
    event: dict[str, object] = {"type": kind}
    if sequence is not None:
        event["sequence"] = sequence
    if payload is not None:
        event["payload"] = payload
    return event


def _response(
    *,
    operation: str = "turn",
    status: str | None = None,
    events: list[dict[str, object]] | None = None,
    candidate: object = CANDIDATE,
):
    if status is None:
        status = {
            "start": "ready",
            "resume": "ready",
            "fork": "ready",
            "turn": "completed",
            "steer": "completed",
            "interrupt": "interrupted",
            "close": "closed",
        }[operation]
    response: dict[str, object] = {
        "status": status,
        "thread_id": THREAD_ID,
        "events": [] if events is None else events,
    }
    if operation in {"turn", "steer"} and status == "completed":
        response["turn_id"] = TURN_ID
        response["candidate_output"] = candidate
    return response


def _normalize(response: object, *, operation: str = "turn"):
    return worker._normalize_response(
        response,
        operation=operation,
        expected_thread_id=THREAD_ID,
    )


def _assert_provider_invalid(response: object, *, operation: str = "turn") -> None:
    with pytest.raises(CodexWorkerError) as caught:
        _normalize(response, operation=operation)
    assert caught.value.code == "WORKER_PROVIDER_RESPONSE_INVALID"


# Valid baseline shapes remain accepted. These prove the RED file is exercising
# the existing normalization seam rather than failing from import/fixture noise.
@pytest.mark.parametrize("operation", ["start", "resume", "fork"])
def test_01_ready_lifecycle_requires_thread_ready(operation: str) -> None:
    status, turn_id, events, candidate = _normalize(
        _response(operation=operation, events=[_event("thread.ready")]),
        operation=operation,
    )
    assert status == "ready"
    assert turn_id is None
    assert [event.kind for event in events] == ["thread.ready"]
    assert candidate is None


def test_02_turn_valid_started_then_completed_sequence() -> None:
    status, turn_id, events, candidate = _normalize(
        _response(
            events=[
                _event("turn.started", sequence=1),
                _event("turn.completed", sequence=2),
            ]
        )
    )
    assert status == "completed"
    assert turn_id == TURN_ID
    assert [event.kind for event in events] == ["turn.started", "turn.completed"]
    assert candidate == CANDIDATE


def test_03_unknown_event_type_still_fails_closed() -> None:
    _assert_provider_invalid(
        _response(events=[_event("turn.started"), _event("turn.teleported")])
    )


def test_04_malformed_event_payload_still_fails_closed() -> None:
    response = _response(events=[_event("turn.started")])
    response["events"] = [{"type": "turn.started"}, "not-an-event"]
    _assert_provider_invalid(response)


# Task-6 RED: operation-specific grammar, deterministic sequence progression,
# terminal evidence, and no output after terminal.
def test_05_start_rejects_foreign_turn_terminal() -> None:
    _assert_provider_invalid(
        _response(operation="start", events=[_event("turn.completed")]),
        operation="start",
    )


def test_06_turn_rejects_thread_ready_as_operation_event() -> None:
    _assert_provider_invalid(
        _response(events=[_event("thread.ready"), _event("turn.completed")])
    )


def test_07_turn_rejects_missing_terminal_event() -> None:
    _assert_provider_invalid(_response(events=[_event("turn.started")]))


def test_08_candidate_before_valid_terminal_is_unusable() -> None:
    _assert_provider_invalid(
        _response(events=[_event("turn.started")], candidate={"secret": "candidate"})
    )


def test_09_duplicate_terminal_event_fails_closed() -> None:
    _assert_provider_invalid(
        _response(events=[_event("turn.completed"), _event("turn.completed")])
    )


def test_10_duplicate_nonterminal_event_fails_closed() -> None:
    _assert_provider_invalid(
        _response(
            events=[
                _event("turn.started", sequence=1),
                _event("turn.started", sequence=2),
                _event("turn.completed", sequence=3),
            ]
        )
    )


def test_11_event_after_terminal_fails_closed() -> None:
    _assert_provider_invalid(
        _response(events=[_event("turn.completed"), _event("turn.started")])
    )


def test_12_premature_terminal_then_progress_fails_closed() -> None:
    _assert_provider_invalid(
        _response(
            events=[
                _event("turn.completed", sequence=1),
                _event("turn.steered", sequence=2),
            ]
        )
    )


def test_13_duplicate_sequence_number_fails_closed() -> None:
    _assert_provider_invalid(
        _response(
            events=[
                _event("turn.started", sequence=7),
                _event("turn.completed", sequence=7),
            ]
        )
    )


def test_14_sequence_gap_fails_closed() -> None:
    _assert_provider_invalid(
        _response(
            events=[
                _event("turn.started", sequence=20),
                _event("turn.completed", sequence=22),
            ]
        )
    )


def test_15_sequence_rewind_fails_closed() -> None:
    _assert_provider_invalid(
        _response(
            events=[
                _event("turn.started", sequence=20),
                _event("turn.completed", sequence=19),
            ]
        )
    )


def test_16_failed_turn_requires_provider_failed_terminal() -> None:
    _assert_provider_invalid(
        _response(
            status="failed",
            events=[_event("turn.started", sequence=1)],
        )
    )


def test_17_provider_failed_must_be_terminal() -> None:
    _assert_provider_invalid(
        _response(
            status="failed",
            events=[
                _event("turn.started", sequence=1),
                _event("provider.failed", sequence=2),
                _event("turn.completed", sequence=3),
            ],
        )
    )


def test_18_oversized_raw_event_payload_fails_before_normalized_drop() -> None:
    oversized = "x" * (worker_process.MAX_CONTROL_FRAME_BYTES + 1)
    _assert_provider_invalid(
        _response(
            events=[
                _event("turn.started", sequence=1, payload=oversized),
                _event("turn.completed", sequence=2),
            ]
        )
    )


def test_19_pathological_event_count_fails_closed() -> None:
    events = [_event("turn.started", sequence=index) for index in range(1, 257)]
    events.append(_event("turn.completed", sequence=257))
    _assert_provider_invalid(_response(events=events))


# Task-6 hard-timeout RED. Blocking control I/O is the accepted Task-3 owner;
# therefore its existing exchange and exact read/write primitives must accept
# an absolute operation deadline. A post-return elapsed-time check alone cannot
# preempt a blocked read.
@pytest.mark.parametrize(
    "callable_obj",
    [
        worker_process.exchange_worker_control,
        worker_process._api_read_exact,
        worker_process._api_write_all,
    ],
)
def test_20_blocking_control_owner_accepts_absolute_deadline(callable_obj) -> None:
    parameter_names = set(inspect.signature(callable_obj).parameters)
    assert any("deadline" in name for name in parameter_names), (
        f"{callable_obj.__name__} must receive the Task-6 absolute deadline"
    )


def test_21_task5_control_exchange_can_propagate_same_absolute_deadline() -> None:
    parameter_names = set(inspect.signature(worker._task5_exchange_child_control).parameters)
    assert any("deadline" in name for name in parameter_names)


def test_22_invoke_child_can_propagate_same_absolute_deadline() -> None:
    parameter_names = set(inspect.signature(worker._invoke_child).parameters)
    assert any("deadline" in name for name in parameter_names)


def test_23_post_return_elapsed_check_is_not_the_hard_timeout_owner() -> None:
    invoke_source = inspect.getsource(worker.CodexWorkerSession._invoke)
    assert "time.monotonic() - started > request.timeout_seconds" not in invoke_source


# Existing safety constraints that Task 6 must preserve while adding deadline
# mechanics: no second supervisor/transport in the lifecycle owner.
@pytest.mark.parametrize(
    "forbidden",
    [
        "concurrent.futures",
        "ThreadPoolExecutor",
        "ProcessPoolExecutor",
        "socket.",
        "subprocess.",
        "app_server",
        "mcp_transport",
    ],
)
def test_24_worker_lifecycle_adds_no_second_supervisor_or_transport(forbidden: str) -> None:
    assert forbidden not in WORKER_SOURCE


def test_25_cancel_sets_local_cancelled_before_interrupt_request() -> None:
    source = inspect.getsource(worker.CodexWorkerSession.cancel)
    status_index = source.index('self._status = "CANCELLED"')
    invoke_index = source.index("_invoke_child")
    assert status_index < invoke_index


def test_26_duplicate_cancel_returns_the_same_terminal_result() -> None:
    source = inspect.getsource(worker.CodexWorkerSession.cancel)
    assert "if self._terminal_result is not None:" in source
    assert "return self._terminal_result" in source


def test_27_cleanup_authority_remains_canonical_task3_owner() -> None:
    source = inspect.getsource(worker._task5_round2_cleanup_evidence)
    assert "cleanup_worker_process(handle)" in source
    assert "process_boundary.cleanup" not in source


def test_28_task5_secure_provider_work_still_ignores_caller_invoke() -> None:
    source = inspect.getsource(worker._task5_secure_invoke_child)
    assert "del process_boundary" in source
    assert "_task5_exchange_child_control" in source


def test_29_task5_secure_attestation_still_ignores_caller_attest() -> None:
    source = inspect.getsource(worker._task5_secure_attest_provider_boundary)
    assert "del process_boundary" in source
    assert "_task5_exchange_child_control" in source


def test_30_task5_canonical_start_guard_remains_effective() -> None:
    source = inspect.getsource(worker._task5_round2_open_codex_worker)
    assert "_task5_round2_is_canonical_boundary" in source
    assert "_task5_round3_has_canonical_start_dispatch" in source
