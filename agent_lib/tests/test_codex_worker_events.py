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


PRIVATE_SENTINEL = (
    r"RAW_SECRET C:\customer\private\drawing.dwg "
    "OPENAI_API_KEY=token stdout stderr"
)


class _MutableClock:
    def __init__(self, now: float) -> None:
        self.now = now
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return self.now


class _ScriptedClock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)
        self.last = 0.0

    def __call__(self) -> float:
        try:
            self.last = next(self._values)
        except StopIteration:
            pass
        return self.last


class _DeadlineEvent(dict):
    def __init__(
        self,
        *args,
        clock: _MutableClock,
        deadline: float,
        expire_after_type: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.clock = clock
        self.deadline = deadline
        self.expire_after_type = expire_after_type

    def get(self, key, default=None):
        if key == "type" and self.clock.now >= self.deadline:
            raise AssertionError("event processed after operation deadline")
        value = super().get(key, default)
        if key == "type" and self.expire_after_type:
            self.clock.now = self.deadline
        return value


def _assert_timeout(callable_obj) -> None:
    with pytest.raises(CodexWorkerError) as caught:
        callable_obj()
    assert caught.value.code == "WORKER_TIMEOUT"
    assert str(caught.value) == "WORKER_TIMEOUT"
    assert PRIVATE_SENTINEL not in str(caught.value)


def _adapter_request(
    operation: str, *, timeout_seconds: float = 1.0, cancelled: bool = False
) -> worker.AdapterRequest:
    return worker.AdapterRequest(
        operation=operation,
        thread_id=THREAD_ID,
        handoff_sha256="a" * 64,
        run_id="RUN-001",
        approval_mode="deny_all",
        experimental_api=False,
        model_identity="model-1",
        config_sha256="b" * 64,
        output_schema_bytes=b"{}",
        output_schema_sha256="c" * 64,
        output_validator_version="validator-1",
        sandbox_roots=("C:/disposable/task6",),
        cwd="C:/disposable/task6",
        timeout_seconds=timeout_seconds,
        cancelled=cancelled,
    )


def _clean_cleanup() -> worker_process.WorkerCleanupResult:
    return worker_process.WorkerCleanupResult(
        status="CLEANUP_SUCCEEDED",
        success=True,
        promotion_safe=True,
        survivor_pids=(),
        survivor_count=0,
        error_code=None,
    )


def _bare_session(*, candidate: object = CANDIDATE) -> worker.CodexWorkerSession:
    class _Binding:
        thread_id = THREAD_ID

    session = object.__new__(worker.CodexWorkerSession)
    session._authority_context = object()
    session._binding = _Binding()
    session._cleanup_result = None
    session._environment_attestation = None
    session._handoff = object()
    session._pending_candidate = candidate
    session._process_boundary = object()
    session._process_handle = object()
    session._status = "READY"
    session._terminal_result = None
    session._worker_context = object()
    return session


def _install_request_builder(monkeypatch) -> None:
    def build_request(
        _self,
        operation: str,
        *,
        input_payload: object | None,
        timeout_seconds: float,
        now,
        cancelled: bool = False,
    ):
        del input_payload, now
        return _adapter_request(
            operation, timeout_seconds=timeout_seconds, cancelled=cancelled
        )

    monkeypatch.setattr(worker.CodexWorkerSession, "_request_with_now", build_request)


def _install_clean_cleanup(monkeypatch, calls: list[object] | None = None) -> None:
    def cleanup(process_boundary, handle):
        del process_boundary
        if calls is not None:
            calls.append(handle)
        return _clean_cleanup(), None

    monkeypatch.setattr(worker, "_cleanup_evidence", cleanup)


# Cell-4 RED hardening: non-turn lifecycle grammar must be closed too.
@pytest.mark.parametrize(
    ("operation", "events"),
    [
        ("resume", []),
        ("resume", [_event("thread.ready"), _event("thread.ready")]),
        ("resume", [_event("thread.ready"), _event("turn.completed")]),
        ("fork", []),
        ("fork", [_event("thread.ready"), _event("thread.ready")]),
        ("fork", [_event("turn.completed")]),
        ("steer", []),
        ("steer", [_event("thread.ready")]),
        ("steer", [_event("turn.completed"), _event("turn.completed")]),
        ("steer", [_event("turn.completed"), _event("turn.started")]),
        ("interrupt", []),
        ("interrupt", [_event("turn.completed")]),
        ("interrupt", [_event("turn.interrupted"), _event("turn.interrupted")]),
        ("interrupt", [_event("turn.interrupted"), _event("turn.completed")]),
        ("close", []),
        ("close", [_event("turn.completed")]),
        ("close", [_event("thread.closed"), _event("thread.closed")]),
        ("close", [_event("thread.closed"), _event("turn.completed")]),
    ],
)
def test_31_nonturn_lifecycle_rejects_missing_foreign_duplicate_or_late_events(
    operation: str, events: list[dict[str, object]]
) -> None:
    _assert_provider_invalid(
        _response(operation=operation, events=events), operation=operation
    )


@pytest.mark.parametrize(
    "events",
    [
        [
            _event("turn.started", sequence=10),
            _event("turn.completed", sequence=12),
        ],
        [
            _event("turn.started", sequence=10),
            _event("turn.completed", sequence=9),
        ],
        [
            _event("turn.started", sequence=10),
            _event("turn.completed", sequence=10),
        ],
    ],
)
def test_32_steer_rejects_sequence_gap_rewind_or_duplicate(
    events: list[dict[str, object]],
) -> None:
    _assert_provider_invalid(_response(operation="steer", events=events), operation="steer")


@pytest.mark.parametrize(
    ("operation", "terminal"),
    [
        ("resume", "thread.ready"),
        ("fork", "thread.ready"),
        ("steer", "turn.completed"),
        ("interrupt", "turn.interrupted"),
        ("close", "thread.closed"),
    ],
)
def test_33_nonturn_malformed_unknown_failures_do_not_leak_private_payload(
    operation: str, terminal: str
) -> None:
    response = _response(
        operation=operation,
        events=[
            _event(terminal),
            {"type": "foreign.event", "payload": PRIVATE_SENTINEL},
        ],
    )
    with pytest.raises(CodexWorkerError) as caught:
        _normalize(response, operation=operation)
    assert caught.value.code == "WORKER_PROVIDER_RESPONSE_INVALID"
    assert str(caught.value) == "WORKER_PROVIDER_RESPONSE_INVALID"
    assert PRIVATE_SENTINEL not in str(caught.value)


# The same absolute deadline must govern event acceptance. Adding a parameter
# but checking only before/after the whole response is insufficient.
def test_34_timeout_before_first_event_preempts_acceptance(monkeypatch) -> None:
    deadline = 10.0
    clock = _MutableClock(deadline)
    event = _DeadlineEvent(
        _event("turn.completed", sequence=1),
        clock=clock,
        deadline=deadline,
    )
    monkeypatch.setattr(worker.time, "monotonic", clock)

    _assert_timeout(
        lambda: worker._normalize_response(
            _response(events=[event], candidate={"private": PRIVATE_SENTINEL}),
            operation="turn",
            expected_thread_id=THREAD_ID,
            deadline=deadline,
        )
    )


def test_35_timeout_between_progress_and_terminal_cannot_reset(monkeypatch) -> None:
    deadline = 20.0
    clock = _MutableClock(19.0)
    progress = _DeadlineEvent(
        _event("turn.started", sequence=1),
        clock=clock,
        deadline=deadline,
        expire_after_type=True,
    )
    terminal = _DeadlineEvent(
        _event("turn.completed", sequence=2),
        clock=clock,
        deadline=deadline,
    )
    monkeypatch.setattr(worker.time, "monotonic", clock)

    _assert_timeout(
        lambda: worker._normalize_response(
            _response(events=[progress, terminal]),
            operation="turn",
            expected_thread_id=THREAD_ID,
            deadline=deadline,
        )
    )


def test_36_candidate_present_before_terminal_is_discarded_on_timeout(
    monkeypatch,
) -> None:
    deadline = 30.0
    clock = _MutableClock(29.0)
    progress = _DeadlineEvent(
        _event("turn.started", sequence=1, payload={"private": PRIVATE_SENTINEL}),
        clock=clock,
        deadline=deadline,
        expire_after_type=True,
    )
    terminal = _DeadlineEvent(
        _event("turn.completed", sequence=2),
        clock=clock,
        deadline=deadline,
    )
    monkeypatch.setattr(worker.time, "monotonic", clock)

    _assert_timeout(
        lambda: worker._normalize_response(
            _response(
                events=[progress, terminal],
                candidate={"private": PRIVATE_SENTINEL},
            ),
            operation="turn",
            expected_thread_id=THREAD_ID,
            deadline=deadline,
        )
    )


def test_37_one_deadline_is_minted_before_attestation_and_reused_for_invoke(
    monkeypatch,
) -> None:
    session = _bare_session(candidate=None)
    _install_request_builder(monkeypatch)
    clock = _MutableClock(100.0)
    monkeypatch.setattr(worker.time, "monotonic", clock)
    seen: list[tuple[str, float | None, int]] = []

    def attest(
        process_boundary,
        handle,
        request,
        *,
        binding,
        authority_context,
        worker_context,
        deadline=None,
    ) -> None:
        del process_boundary, handle, request, binding, authority_context, worker_context
        seen.append(("attest", deadline, clock.calls))

    def invoke(process_boundary, handle, request, *, deadline=None):
        del process_boundary, handle, request
        seen.append(("invoke", deadline, clock.calls))
        return _response(events=[_event("turn.completed")])

    monkeypatch.setattr(worker, "_attest_provider_boundary", attest)
    monkeypatch.setattr(worker, "_invoke_child", invoke)

    result = session.turn({"prompt": "safe"}, timeout_seconds=2.0)

    assert result.success is True
    assert [name for name, _deadline, _calls in seen] == ["attest", "invoke"]
    assert seen[0][2] >= 1
    assert seen[0][1] == seen[1][1] == 102.0


def test_38_task5_attestation_and_work_forward_exact_same_control_deadline(
    monkeypatch,
) -> None:
    seen: list[float | None] = []

    def exchange(handle, payload, *, deadline=None):
        del handle, payload
        seen.append(deadline)
        return {}

    monkeypatch.setattr(worker, "exchange_worker_control", exchange)
    request = _adapter_request("turn")
    absolute_deadline = 250.5

    worker._task5_exchange_child_control(
        object(), request, attestation=True, deadline=absolute_deadline
    )
    worker._task5_exchange_child_control(
        object(), request, attestation=False, deadline=absolute_deadline
    )

    assert seen == [absolute_deadline, absolute_deadline]


@pytest.mark.skipif(
    worker_process.os.name != "nt",
    reason="Windows native control-pipe preemption evidence",
)
def test_39_blocked_control_read_is_preempted_by_absolute_deadline(tmp_path: Path) -> None:
    root = tmp_path / "blocked-control"
    cwd = root / "cwd"
    cwd.mkdir(parents=True)
    environment = worker_process.prepare_worker_environment(
        disposable_root=root,
        cwd=cwd,
    )
    handle = worker_process.launch_worker_process(
        environment=environment,
        expected_disposable_root=root,
        expected_cwd=cwd,
        executable=Path(worker.sys.executable).resolve(),
        argv=("-c", "import time; time.sleep(30)"),
        cleanup_deadline_seconds=1.0,
        max_processes=8,
        control_channel=True,
    )
    started = worker_process.time.monotonic()
    try:
        with pytest.raises(worker_process.WorkerProcessError) as caught:
            worker_process.exchange_worker_control(
                handle,
                {"operation": "probe"},
                deadline=started + 0.25,
            )
        assert caught.value.code == "WORKER_TIMEOUT"
        assert str(caught.value) == "WORKER_TIMEOUT"
        assert worker_process.time.monotonic() - started < 2.0
    finally:
        cleanup = worker_process.cleanup_worker_process(handle)
        assert cleanup.survivor_count == 0
        assert cleanup.promotion_safe is True


# Local CANCELLED must win before interrupt/ack and late provider output.
def test_40_cancel_is_local_first_deadline_bounded_and_cleanup_always_runs(
    monkeypatch,
) -> None:
    session = _bare_session(candidate={"private": PRIVATE_SENTINEL})
    _install_request_builder(monkeypatch)
    cleanup_calls: list[object] = []
    _install_clean_cleanup(monkeypatch, cleanup_calls)
    monkeypatch.setattr(worker.time, "monotonic", _MutableClock(300.0))
    seen: list[tuple[str, float | None, bool]] = []

    def invoke(process_boundary, handle, request, *, deadline=None):
        del process_boundary, handle
        seen.append((session.status, deadline, request.cancelled))
        return _response(operation="interrupt", events=[_event("turn.interrupted")])

    monkeypatch.setattr(worker, "_invoke_child", invoke)
    result = session.cancel(timeout_seconds=1.0)

    assert seen == [("CANCELLED", 301.0, True)]
    assert cleanup_calls == [session._process_handle]
    assert result.status == "CANCELLED"
    assert result.candidate_output is None
    assert result.promotion_safe is False
    assert PRIVATE_SENTINEL not in repr(result)


@pytest.mark.parametrize(
    "response",
    [
        _response(operation="interrupt", events=[]),
        {
            "status": "completed",
            "thread_id": THREAD_ID,
            "turn_id": TURN_ID,
            "events": [
                _event("turn.completed", payload={"private": PRIVATE_SENTINEL})
            ],
            "candidate_output": {"private": PRIVATE_SENTINEL},
        },
        {
            "status": "cancelled",
            "thread_id": THREAD_ID,
            "events": [
                _event("turn.interrupted", payload={"private": PRIVATE_SENTINEL})
            ],
            "failure_code": "WORKER_TIMEOUT",
        },
    ],
)
def test_41_cancel_rejects_missing_forged_late_or_provider_minted_ack(
    monkeypatch, response: object
) -> None:
    session = _bare_session(candidate={"private": PRIVATE_SENTINEL})
    _install_request_builder(monkeypatch)
    _install_clean_cleanup(monkeypatch)
    monkeypatch.setattr(worker.time, "monotonic", _MutableClock(400.0))
    monkeypatch.setattr(
        worker,
        "_invoke_child",
        lambda *_args, **_kwargs: response,
    )

    result = session.cancel(timeout_seconds=1.0)

    assert result.status == "CANCELLED"
    assert result.candidate_output is None
    assert result.promotion_safe is False
    assert result.failure_code in {
        "WORKER_INTERRUPT_FAILED",
        "WORKER_PROVIDER_RESPONSE_INVALID",
    }
    assert PRIVATE_SENTINEL not in repr(result)


def test_42_duplicate_interrupt_is_idempotent_and_ack_is_deadline_bounded(
    monkeypatch,
) -> None:
    session = _bare_session(candidate={"private": PRIVATE_SENTINEL})
    _install_request_builder(monkeypatch)
    _install_clean_cleanup(monkeypatch)
    monkeypatch.setattr(worker.time, "monotonic", _MutableClock(500.0))
    deadlines: list[float | None] = []

    def invoke(process_boundary, handle, request, *, deadline=None):
        del process_boundary, handle, request
        deadlines.append(deadline)
        return _response(operation="interrupt", events=[_event("turn.interrupted")])

    monkeypatch.setattr(worker, "_invoke_child", invoke)
    first = session.interrupt(timeout_seconds=1.0)
    second = session.interrupt(timeout_seconds=1.0)

    assert second is first
    assert deadlines == [501.0]
    assert first.candidate_output is None
    assert first.promotion_safe is False


def test_43_timeout_terminal_ignores_all_late_provider_output(monkeypatch) -> None:
    session = _bare_session(candidate={"private": PRIVATE_SENTINEL})
    cleanup_calls: list[object] = []
    _install_clean_cleanup(monkeypatch, cleanup_calls)
    terminal = session._cleanup_failure("turn", "WORKER_TIMEOUT")
    monkeypatch.setattr(
        worker,
        "_invoke_child",
        lambda *_args, **_kwargs: pytest.fail("late provider work ran after timeout"),
    )

    late = session.turn({"private": PRIVATE_SENTINEL}, timeout_seconds=1.0)

    assert late is terminal
    assert late.failure_code == "WORKER_TIMEOUT"
    assert late.candidate_output is None
    assert late.promotion_safe is False
    assert cleanup_calls == [session._process_handle]
    assert PRIVATE_SENTINEL not in repr(late)


# Cleanup remains canonical Task-3 ownership with its own bounded deadline.
def test_44_cleanup_survivor_dominates_primary_failure_and_blocks_promotion(
    monkeypatch,
) -> None:
    class _CallerBoundary:
        def cleanup(self, _handle):
            raise AssertionError("caller cleanup authority must not run")

    failed = worker_process.WorkerCleanupResult(
        status="CLEANUP_FAILED",
        success=False,
        promotion_safe=False,
        survivor_pids=(4102,),
        survivor_count=1,
        error_code="WORKER_CLEANUP_SURVIVORS",
    )
    canonical_calls: list[object] = []

    def canonical(handle):
        canonical_calls.append(handle)
        return failed

    monkeypatch.setattr(worker, "cleanup_worker_process", canonical)
    session = _bare_session(candidate={"private": PRIVATE_SENTINEL})
    session._process_boundary = _CallerBoundary()
    result = session._cleanup_failure("turn", "WORKER_TIMEOUT")

    assert canonical_calls == [session._process_handle]
    assert result.failure_code == "WORKER_CLEANUP_FAILED"
    assert result.cleanup_result == failed
    assert result.candidate_output is None
    assert result.promotion_safe is False
    assert PRIVATE_SENTINEL not in repr(result)


def test_45_cleanup_deadline_is_separate_bounded_and_sticky() -> None:
    class _CleanupApi:
        def __init__(self) -> None:
            self.results = [(4101, 4102), (4102,)]

        def query_job_process_ids(self, _job, *, max_processes: int):
            assert max_processes == 8
            return self.results.pop(0)

        def terminate_job(self, _job) -> None:
            return None

        def close_handle(self, _handle) -> None:
            return None

    api = _CleanupApi()
    handle = worker_process.WorkerProcessHandle(
        api=api,
        job_handle="job",
        process_handle="process",
        root_pid=4101,
        environment_attestation=object(),
        cleanup_deadline_seconds=0.1,
        max_processes=8,
    )
    worker_process._register_issued_handle(handle)
    first = worker_process.cleanup_worker_process(
        handle,
        _clock=_ScriptedClock(50.0, 50.2),
        _sleep=lambda _seconds: None,
    )
    second = worker_process.cleanup_worker_process(
        handle,
        _clock=_ScriptedClock(99.0),
        _sleep=lambda _seconds: None,
    )

    assert first.status == "CLEANUP_FAILED"
    assert first.error_code == "WORKER_CLEANUP_SURVIVORS"
    assert first.survivor_pids == (4102,)
    assert first.promotion_safe is False
    assert second == first


@pytest.mark.parametrize(
    "primary",
    ["WORKER_TIMEOUT", "WORKER_CANCELLED", "WORKER_PROVIDER_FAILED"],
)
def test_46_timeout_cancel_provider_failure_all_cleanup_without_promotion(
    monkeypatch, primary: str
) -> None:
    session = _bare_session(candidate={"private": PRIVATE_SENTINEL})
    cleanup_calls: list[object] = []
    _install_clean_cleanup(monkeypatch, cleanup_calls)
    if primary == "WORKER_CANCELLED":
        session._status = "CANCELLED"

    result = session._cleanup_failure("turn", primary)

    assert cleanup_calls == [session._process_handle]
    assert result.candidate_output is None
    assert result.promotion_safe is False
    assert result.cleanup_result == _clean_cleanup()
    assert PRIVATE_SENTINEL not in repr(result)


# Cell-4 second hardened RED: start must be as closed as every other lifecycle
# operation, including structural/sequence validation and privacy-safe rejection.
@pytest.mark.parametrize(
    "events",
    [
        [],
        [
            _event("thread.ready", sequence=1),
            _event("thread.ready", sequence=2, payload=PRIVATE_SENTINEL),
        ],
        [
            _event("thread.ready", sequence=1),
            _event("turn.started", sequence=2, payload=PRIVATE_SENTINEL),
        ],
        [
            {"type": 7, "payload": PRIVATE_SENTINEL},
        ],
        [
            {"type": "foreign.event", "payload": PRIVATE_SENTINEL},
        ],
        [
            {"type": "thread.ready", "sequence": "not-an-int", "payload": PRIVATE_SENTINEL},
        ],
    ],
)
def test_47_start_rejects_missing_duplicate_late_malformed_unknown_or_bad_sequence(
    events: list[dict[str, object]],
) -> None:
    with pytest.raises(CodexWorkerError) as caught:
        _normalize(_response(operation="start", events=events), operation="start")
    assert caught.value.code == "WORKER_PROVIDER_RESPONSE_INVALID"
    assert str(caught.value) == "WORKER_PROVIDER_RESPONSE_INVALID"
    assert PRIVATE_SENTINEL not in str(caught.value)


# Task 6 may extend only the existing Task-3 process/control owner. Deadline
# mechanics must not smuggle in a second supervisor, Job, transport or cleanup
# authority in the second production file.
def test_48_process_owner_retains_single_supervisor_transport_and_cleanup_authority() -> None:
    process_source = Path(worker_process.__file__).read_text(encoding="utf-8")
    forbidden = (
        "concurrent.futures",
        "ThreadPoolExecutor",
        "ProcessPoolExecutor",
        "threading.Thread",
        "multiprocessing",
        "socket.",
        "socketserver",
        "subprocess.Popen",
        "subprocess.run",
        "subprocess.call",
        "CreateThread(",
        "watchdog",
        "app_server",
        "mcp_transport",
    )
    for marker in forbidden:
        assert marker not in process_source

    assert process_source.count("CreateJobObjectW(") == 1
    assert process_source.count("def create_job(") == 1
    assert process_source.count("def exchange_worker_control(") == 1
    assert process_source.count("def cleanup_worker_process(") == 1
