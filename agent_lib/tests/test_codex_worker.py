from __future__ import annotations

import ast
import dataclasses
import inspect
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Mapping

import pytest

from agent_lib.codex_worker import (
    AdapterRequest,
    CodexWorkerError,
    CodexWorkerResult,
    CodexWorkerSession,
    LazyOfficialSdkAdapter,
    fork_codex_worker,
    resume_codex_worker,
    start_codex_worker,
)
from agent_lib.codex_worker_process import (
    ProcessTreeIdentity,
    WorkerCleanupResult,
    WorkerEnvironmentAttestation,
)
from cad_agent.vision_handoff import (
    BoundWorkerThread,
    ServerOwnedWorkerBindingContext,
    bind_worker_thread,
)
from tests.test_vision_handoff import NOW, _authority_context, _base_payload, _bind, _write_schema


SOURCE_MODULE = Path(__file__).parents[1] / "codex_worker.py"
SENTINEL = r"RAW_SECRET C:\customer\private\drawing.dwg OPENAI_API_KEY=token stdout stderr"


class _FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[AdapterRequest] = []
        self.failures: dict[str, BaseException] = {}
        self.responses: dict[str, object] = {}
        self.compatibility_calls = 0

    def ensure_compatible(self) -> None:
        self.compatibility_calls += 1

    def invoke(self, request: AdapterRequest) -> object:
        self.calls.append(request)
        failure = self.failures.get(request.operation)
        if failure is not None:
            raise failure
        if request.operation in self.responses:
            return self.responses[request.operation]
        if request.operation in {"start", "resume", "fork"}:
            return {
                "status": "ready",
                "thread_id": request.thread_id,
                "events": [{"type": "thread.ready"}],
            }
        if request.operation in {"turn", "steer"}:
            return {
                "status": "completed",
                "thread_id": request.thread_id,
                "turn_id": "TURN-001",
                "events": [{"type": "turn.completed", "ignored": SENTINEL}],
                "candidate_output": {"schema_version": "repair-plan-1.0"},
            }
        if request.operation == "interrupt":
            return {
                "status": "interrupted",
                "thread_id": request.thread_id,
                "events": [{"type": "turn.interrupted"}],
            }
        if request.operation == "close":
            return {
                "status": "closed",
                "thread_id": request.thread_id,
                "events": [{"type": "thread.closed"}],
            }
        raise AssertionError(f"unexpected fake operation {request.operation}")


class _FakeProcessHandle:
    def __init__(self, attestation: WorkerEnvironmentAttestation) -> None:
        self.environment_attestation = attestation
        self.root_pid = 4101
        self.tree = ProcessTreeIdentity(
            root_pid=4101,
            member_pids=(4101,),
            member_count=1,
            verified=True,
        )

    def snapshot_process_tree(self) -> ProcessTreeIdentity:
        return self.tree


class _FakeProcessBoundary:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.cleanup_result: object = WorkerCleanupResult(
            status="CLEANUP_SUCCEEDED",
            success=True,
            promotion_safe=True,
            survivor_pids=(),
            survivor_count=0,
            error_code=None,
        )
        self.attestation_mutator = None
        self.handle_mutator = None
        self.adapter: _FakeAdapter | None = None
        self._compatible = False

    def start(
        self,
        *,
        expected_disposable_root: Path,
        expected_cwd: Path,
    ) -> tuple[WorkerEnvironmentAttestation, object]:
        self.calls.append(("start", (expected_disposable_root, expected_cwd)))
        root = Path(expected_disposable_root)
        cwd = Path(expected_cwd)
        codex_home = root / "codex-home"
        temp_dir = root / "tmp"
        environment = MappingProxyType(
            {
                "CODEX_HOME": str(codex_home),
                "TEMP": str(temp_dir),
                "TMP": str(temp_dir),
            }
        )
        attestation = WorkerEnvironmentAttestation(
            environment=environment,
            environment_keys=("CODEX_HOME", "TEMP", "TMP"),
            environment_sha256="a" * 64,
            disposable_root=root,
            cwd=cwd,
            codex_home=codex_home,
            temp_dir=temp_dir,
            writable_roots=(cwd, codex_home, temp_dir),
        )
        if self.attestation_mutator is not None:
            attestation = self.attestation_mutator(attestation)
        handle = _FakeProcessHandle(attestation)
        if self.handle_mutator is not None:
            self.handle_mutator(handle)
        return attestation, handle

    def invoke(self, handle: object, request: AdapterRequest) -> object:
        del handle
        self.calls.append(("invoke", request))
        adapter = self.adapter
        if adapter is None:
            raise AssertionError("fake child adapter not configured")
        if not self._compatible:
            adapter.ensure_compatible()
            self._compatible = True
        return adapter.invoke(request)

    def cleanup(self, handle: object) -> object:
        self.calls.append(("cleanup", handle))
        return self.cleanup_result


@dataclasses.dataclass
class _Fixture:
    schema_path: Path
    handoff: object
    authority: object
    worker_context: ServerOwnedWorkerBindingContext
    binding: BoundWorkerThread
    adapter: _FakeAdapter
    process: _FakeProcessBoundary


def _worker_context(
    handoff: object,
    *,
    thread_id: str = "THREAD-001",
    sandbox_policy: Mapping[str, object] | None = None,
) -> ServerOwnedWorkerBindingContext:
    workspace = handoff.payload["workspace"]
    return ServerOwnedWorkerBindingContext(
        adapter_version="adapter-1.0",
        observed_thread_id=thread_id,
        sandbox_policy=sandbox_policy
        or {
            "roots": list(workspace["roots"]),
            "write_policy": workspace["write_policy"],
            "cwd": workspace["roots"][0],
        },
    )


def _fixture(tmp_path: Path, *, thread_id: str = "THREAD-001") -> _Fixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    authority = _authority_context(dict(handoff.payload))
    worker_context = _worker_context(handoff, thread_id=thread_id)
    binding = bind_worker_thread(
        handoff,
        thread_id=thread_id,
        authority_context=authority,
        worker_context=worker_context,
        now=NOW,
    )
    adapter = _FakeAdapter()
    process = _FakeProcessBoundary()
    process.adapter = adapter
    return _Fixture(
        schema_path=schema_path,
        handoff=handoff,
        authority=authority,
        worker_context=worker_context,
        binding=binding,
        adapter=adapter,
        process=process,
    )


def _start(fx: _Fixture, **overrides: object) -> CodexWorkerSession:
    values = {
        "handoff": fx.handoff,
        "binding": fx.binding,
        "authority_context": fx.authority,
        "worker_context": fx.worker_context,
        "adapter": fx.adapter,
        "process_boundary": fx.process,
        "timeout_seconds": 1.0,
        "now": NOW,
    }
    values.update(overrides)
    return start_codex_worker(**values)


def _fresh_target(
    tmp_path: Path,
    *,
    approval_reference: str = "APPROVAL-002",
    thread_id: str = "THREAD-002",
    payload_mutator=None,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    schema_path = _write_schema(tmp_path / "target-schema.json")
    payload = _base_payload()
    payload.update(
        {
            "handoff_id": "HANDOFF-002",
            "run_id": "RUN-002",
            "request_id": "REQUEST-002",
            "approval_reference": approval_reference,
        }
    )
    if payload_mutator is not None:
        payload_mutator(payload)
    handoff = _bind(schema_path, payload, authority_context=_authority_context(payload))
    authority = _authority_context(dict(handoff.payload))
    worker_context = _worker_context(handoff, thread_id=thread_id)
    binding = bind_worker_thread(
        handoff,
        thread_id=thread_id,
        authority_context=authority,
        worker_context=worker_context,
        now=NOW,
    )
    return handoff, authority, worker_context, binding


def _assert_failed(result: CodexWorkerResult, code: str | None = None) -> None:
    assert result.success is False
    assert result.promotion_safe is False
    assert result.candidate_output is None
    assert result.candidate_trusted is False
    if code is not None:
        assert result.failure_code == code


def test_01_start_valid_exact_binding_uses_fake_only_and_returns_session(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    session = _start(fx)
    assert isinstance(session, CodexWorkerSession)
    assert session.binding == fx.binding
    assert session.status == "READY"
    assert fx.adapter.compatibility_calls == 1
    assert [call.operation for call in fx.adapter.calls] == ["start"]
    assert fx.process.calls[0][0] == "start"


def test_02_start_rejects_missing_or_foreign_handoff_and_binding(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    for key, value in (("handoff", object()), ("binding", object())):
        with pytest.raises(CodexWorkerError) as caught:
            _start(fx, **{key: value})
        assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"
    assert fx.adapter.calls == [] and fx.process.calls == []


def test_03_start_rejects_bare_or_caller_selected_thread_identity(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    foreign_context = replace(fx.worker_context, observed_thread_id="FOREIGN-THREAD")
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx, worker_context=foreign_context)
    assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"
    assert "thread_id" not in inspect.signature(start_codex_worker).parameters


def test_04_resume_rejects_stale_expired_or_foreign_binding(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    for binding, now in (
        (replace(fx.binding, handoff_id="FOREIGN-HANDOFF"), NOW),
        (fx.binding, NOW + timedelta(hours=2)),
    ):
        with pytest.raises(CodexWorkerError) as caught:
            resume_codex_worker(
                handoff=fx.handoff,
                binding=binding,
                authority_context=fx.authority,
                worker_context=fx.worker_context,
                adapter=fx.adapter,
                process_boundary=fx.process,
                timeout_seconds=1.0,
                now=now,
            )
        assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"
    assert fx.adapter.calls == [] and fx.process.calls == []


def test_05_resume_rejects_model_or_config_drift(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    drifted = replace(
        fx.binding,
        model_config_identity={"model_identity": "other", "config_sha256": "f" * 64},
    )
    with pytest.raises(CodexWorkerError) as caught:
        resume_codex_worker(
            handoff=fx.handoff,
            binding=drifted,
            authority_context=fx.authority,
            worker_context=fx.worker_context,
            adapter=fx.adapter,
            process_boundary=fx.process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"


def test_06_resume_rejects_instruction_source_drift(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    drifted = replace(
        fx.binding,
        instruction_source_identity=(
            {"source_id": "foreign", "role": "system", "sha256": "f" * 64},
        ),
    )
    with pytest.raises(CodexWorkerError) as caught:
        resume_codex_worker(
            handoff=fx.handoff,
            binding=drifted,
            authority_context=fx.authority,
            worker_context=fx.worker_context,
            adapter=fx.adapter,
            process_boundary=fx.process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"


def test_07_resume_rejects_sandbox_cwd_or_writable_root_drift(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    foreign_context = replace(
        fx.worker_context,
        sandbox_policy={
            "roots": ["C:/disposable/vision-run-001", "C:/foreign"],
            "write_policy": "DISPOSABLE_ONLY",
            "cwd": "C:/foreign",
        },
    )
    with pytest.raises(CodexWorkerError) as caught:
        resume_codex_worker(
            handoff=fx.handoff,
            binding=fx.binding,
            authority_context=fx.authority,
            worker_context=foreign_context,
            adapter=fx.adapter,
            process_boundary=fx.process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"


def test_08_schema_hash_validator_and_toctou_drift_fail_closed(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    for binding in (
        replace(fx.binding, output_schema_sha256="f" * 64),
        replace(fx.binding, output_validator_version="foreign-validator"),
    ):
        with pytest.raises(CodexWorkerError) as caught:
            _start(fx, binding=binding)
        assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"
    session = _start(fx)
    fx.schema_path.write_text('{"type":"object","changed":true}', encoding="utf-8")
    result = session.turn({"prompt": "untrusted"}, timeout_seconds=1.0, now=NOW)
    _assert_failed(result, "WORKER_AUTHORITY_MISMATCH")
    assert any(call[0] == "cleanup" for call in fx.process.calls)


def test_09_fork_rejects_reused_thread_id(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    target = _fresh_target(tmp_path / "target", thread_id=fx.binding.thread_id)
    with pytest.raises(CodexWorkerError) as caught:
        fork_codex_worker(
            source_handoff=fx.handoff,
            source_binding=fx.binding,
            source_authority_context=fx.authority,
            source_worker_context=fx.worker_context,
            handoff=target[0],
            binding=target[3],
            authority_context=target[1],
            worker_context=target[2],
            adapter=fx.adapter,
            process_boundary=fx.process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"


def test_10_fork_rejects_reused_handoff(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    target_context = _worker_context(fx.handoff, thread_id="THREAD-002")
    target_binding = bind_worker_thread(
        fx.handoff,
        thread_id="THREAD-002",
        authority_context=fx.authority,
        worker_context=target_context,
        now=NOW,
    )
    with pytest.raises(CodexWorkerError) as caught:
        fork_codex_worker(
            source_handoff=fx.handoff,
            source_binding=fx.binding,
            source_authority_context=fx.authority,
            source_worker_context=fx.worker_context,
            handoff=fx.handoff,
            binding=target_binding,
            authority_context=fx.authority,
            worker_context=target_context,
            adapter=fx.adapter,
            process_boundary=fx.process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"


def test_11_fork_rejects_inherited_approval(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    target = _fresh_target(tmp_path / "target", approval_reference=fx.binding.approval_reference)
    with pytest.raises(CodexWorkerError) as caught:
        fork_codex_worker(
            source_handoff=fx.handoff,
            source_binding=fx.binding,
            source_authority_context=fx.authority,
            source_worker_context=fx.worker_context,
            handoff=target[0],
            binding=target[3],
            authority_context=target[1],
            worker_context=target[2],
            adapter=fx.adapter,
            process_boundary=fx.process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"


def test_12_fork_rejects_widened_policy_or_history(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)

    def widen(payload: dict[str, object]) -> None:
        payload["scope"] = dict(payload["scope"])
        payload["scope"]["components"] = ["component-001", "component-002"]
        payload["allowed_operations"] = [
            "READ_ONLY_VISION_ANALYSIS",
            "WRITE_DISPOSABLE_CANDIDATE",
        ]

    target = _fresh_target(tmp_path / "target", payload_mutator=widen)
    with pytest.raises(CodexWorkerError) as caught:
        fork_codex_worker(
            source_handoff=fx.handoff,
            source_binding=fx.binding,
            source_authority_context=fx.authority,
            source_worker_context=fx.worker_context,
            handoff=target[0],
            binding=target[3],
            authority_context=target[1],
            worker_context=target[2],
            adapter=fx.adapter,
            process_boundary=fx.process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"


def test_13_every_lifecycle_request_uses_deny_all_approval(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    session = _start(fx)
    session.turn({"prompt": "x"}, timeout_seconds=1.0, now=NOW)
    session.steer({"instruction": "x"}, timeout_seconds=1.0, now=NOW)
    session.close(timeout_seconds=1.0, now=NOW)
    assert fx.adapter.calls
    assert {call.approval_mode for call in fx.adapter.calls} == {"deny_all"}


def test_14_every_lifecycle_request_disables_experimental_api(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    session = _start(fx)
    session.turn({}, timeout_seconds=1.0, now=NOW)
    session.steer({}, timeout_seconds=1.0, now=NOW)
    session.close(timeout_seconds=1.0, now=NOW)
    assert {call.experimental_api for call in fx.adapter.calls} == {False}


def test_15_full_access_sandbox_is_rejected_before_provider_work(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    bad = replace(
        fx.worker_context,
        sandbox_policy={"roots": ["C:/"], "write_policy": "FULL_ACCESS", "cwd": "C:/"},
    )
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx, worker_context=bad)
    assert caught.value.code == "WORKER_AUTHORITY_MISMATCH"
    assert fx.adapter.calls == [] and fx.process.calls == []


def test_16_public_lifecycle_has_no_mutable_caller_selected_schema_path(tmp_path: Path) -> None:
    for function in (start_codex_worker, resume_codex_worker, fork_codex_worker):
        assert "schema_path" not in inspect.signature(function).parameters
    fx = _fixture(tmp_path)
    with pytest.raises(TypeError):
        start_codex_worker(
            handoff=fx.handoff,
            binding=fx.binding,
            authority_context=fx.authority,
            worker_context=fx.worker_context,
            adapter=fx.adapter,
            process_boundary=fx.process,
            timeout_seconds=1.0,
            now=NOW,
            schema_path=tmp_path / "caller.json",  # type: ignore[call-arg]
        )


def test_17_unexpected_writable_root_or_environment_evidence_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)

    def mutate(attestation: WorkerEnvironmentAttestation) -> WorkerEnvironmentAttestation:
        return replace(
            attestation,
            writable_roots=(*attestation.writable_roots, Path("C:/foreign")),
        )

    fx.process.attestation_mutator = mutate
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx)
    assert caught.value.code == "WORKER_PROCESS_EVIDENCE_INVALID"
    assert fx.adapter.calls == []


def test_18_turn_timeout_rejects_output_and_enters_cleanup(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx.adapter.failures["turn"] = TimeoutError(SENTINEL)
    session = _start(fx)
    result = session.turn({"prompt": SENTINEL}, timeout_seconds=0.1, now=NOW)
    _assert_failed(result, "WORKER_TIMEOUT")
    assert any(call[0] == "cleanup" for call in fx.process.calls)
    assert SENTINEL not in repr(result)


def test_19_steer_preserves_exact_authority_policy_and_schema_binding(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    session = _start(fx)
    result = session.steer({"instruction": "bounded"}, timeout_seconds=1.0, now=NOW)
    assert result.success is True
    request = fx.adapter.calls[-1]
    assert request.operation == "steer"
    assert request.thread_id == fx.binding.thread_id
    assert request.handoff_sha256 == fx.binding.handoff_hash
    assert request.model_identity == fx.binding.model_config_identity["model_identity"]
    assert request.config_sha256 == fx.binding.model_config_identity["config_sha256"]
    assert request.output_schema_sha256 == fx.binding.output_schema_sha256
    assert request.output_validator_version == fx.binding.output_validator_version


def test_20_interrupt_failure_cannot_return_candidate_success(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    session = _start(fx)
    session.turn({}, timeout_seconds=1.0, now=NOW)
    fx.adapter.failures["interrupt"] = RuntimeError(SENTINEL)
    result = session.interrupt(timeout_seconds=1.0, now=NOW)
    _assert_failed(result, "WORKER_INTERRUPT_FAILED")
    assert any(call[0] == "cleanup" for call in fx.process.calls)


def test_21_local_cancel_marks_cancelled_before_interrupt_and_rejects_late_output(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    session = _start(fx)
    fx.adapter.responses["interrupt"] = {
        "status": "completed",
        "thread_id": fx.binding.thread_id,
        "turn_id": "TURN-LATE",
        "events": [{"type": "turn.completed"}],
        "candidate_output": {"late": "must-not-promote"},
    }
    result = session.cancel(timeout_seconds=1.0, now=NOW)
    _assert_failed(result, "WORKER_CANCELLED")
    assert fx.adapter.calls[-1].operation == "interrupt"
    assert fx.adapter.calls[-1].cancelled is True
    assert session.status == "CANCELLED"


@pytest.mark.parametrize("mode", ["cancel", "timeout", "provider_failure"])
def test_22_cancel_timeout_and_provider_failure_always_cleanup(tmp_path: Path, mode: str) -> None:
    fx = _fixture(tmp_path)
    session = _start(fx)
    if mode == "cancel":
        session.cancel(timeout_seconds=1.0, now=NOW)
    else:
        fx.adapter.failures["turn"] = TimeoutError() if mode == "timeout" else RuntimeError()
        session.turn({}, timeout_seconds=0.1, now=NOW)
    assert [name for name, _ in fx.process.calls].count("cleanup") == 1


def test_23_cleanup_survivors_block_promotion(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx.process.cleanup_result = WorkerCleanupResult(
        status="CLEANUP_FAILED",
        success=False,
        promotion_safe=False,
        survivor_pids=(4102,),
        survivor_count=1,
        error_code="WORKER_CLEANUP_SURVIVORS",
    )
    session = _start(fx)
    turn = session.turn({}, timeout_seconds=1.0, now=NOW)
    assert turn.candidate_output is not None and turn.promotion_safe is False
    result = session.close(timeout_seconds=1.0, now=NOW)
    _assert_failed(result, "WORKER_CLEANUP_FAILED")


def test_24_malformed_or_unverified_cleanup_evidence_is_failure(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx.process.cleanup_result = SimpleNamespace(
        status="CLEANUP_SUCCEEDED",
        success=True,
        promotion_safe=True,
        survivor_pids=(),
        survivor_count=0,
        error_code=None,
    )
    session = _start(fx)
    result = session.close(timeout_seconds=1.0, now=NOW)
    _assert_failed(result, "WORKER_CLEANUP_EVIDENCE_INVALID")


def test_25_malformed_or_unknown_provider_terminal_event_is_failure(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx.adapter.responses["turn"] = {
        "status": "mystery",
        "thread_id": fx.binding.thread_id,
        "events": [{"type": "unknown.raw", "payload": SENTINEL}],
        "candidate_output": {"secret": SENTINEL},
    }
    session = _start(fx)
    result = session.turn({}, timeout_seconds=1.0, now=NOW)
    _assert_failed(result, "WORKER_PROVIDER_RESPONSE_INVALID")
    assert SENTINEL not in repr(result)
    assert any(call[0] == "cleanup" for call in fx.process.calls)


def test_26_provider_exception_becomes_categorical_sanitized_failure(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx.adapter.failures["turn"] = RuntimeError(SENTINEL)
    session = _start(fx)
    result = session.turn({}, timeout_seconds=1.0, now=NOW)
    _assert_failed(result, "WORKER_PROVIDER_FAILED")
    assert SENTINEL not in repr(result)


def test_27_raw_prompt_env_stream_credential_or_path_never_appears_in_public_failure_or_events(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx.adapter.responses["turn"] = {
        "status": "failed",
        "thread_id": fx.binding.thread_id,
        "events": [{"type": "provider.failed", "raw": SENTINEL}],
        "error": SENTINEL,
    }
    session = _start(fx)
    result = session.turn({"prompt": SENTINEL}, timeout_seconds=1.0, now=NOW)
    _assert_failed(result, "WORKER_PROVIDER_FAILED")
    assert SENTINEL not in repr(result)
    assert all(SENTINEL not in repr(event) for event in result.events)


def test_28_close_is_idempotent_after_verified_cleanup_and_sticky_after_failure(tmp_path: Path) -> None:
    good = _fixture(tmp_path / "good")
    session = _start(good)
    first = session.close(timeout_seconds=1.0, now=NOW)
    calls = list(good.process.calls)
    second = session.close(timeout_seconds=1.0, now=NOW)
    assert first == second and first.promotion_safe is True
    assert good.process.calls == calls

    bad = _fixture(tmp_path / "bad")
    bad.process.cleanup_result = WorkerCleanupResult(
        status="CLEANUP_FAILED",
        success=False,
        promotion_safe=False,
        survivor_pids=(99,),
        survivor_count=1,
        error_code="WORKER_CLEANUP_SURVIVORS",
    )
    failed_session = _start(bad)
    failed_first = failed_session.close(timeout_seconds=1.0, now=NOW)
    failed_calls = list(bad.process.calls)
    failed_second = failed_session.close(timeout_seconds=1.0, now=NOW)
    assert failed_first == failed_second
    assert failed_first.promotion_safe is False
    assert bad.process.calls == failed_calls


def test_29_lazy_official_sdk_adapter_imports_only_official_sdk_and_has_no_implicit_fallback() -> None:
    loaded: list[str] = []
    delegate = _FakeAdapter()

    def loader(name: str) -> object:
        loaded.append(name)
        return object()

    lazy = LazyOfficialSdkAdapter(
        adapter_factory=lambda _module: delegate,
        compatibility_check=lambda: {"status": "compatible"},
        module_loader=loader,
    )
    assert loaded == []
    lazy.ensure_compatible()
    assert loaded == ["openai_codex"]
    source = SOURCE_MODULE.read_text(encoding="utf-8")
    assert "app-server" not in source
    assert "codex exec" not in source
    assert "mcp_integration_lib" not in source


def test_30_compatibility_rejection_is_child_bound_and_cleanup_preserved(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _ChildOnlyBoundary()
    process.failures["start"] = CodexWorkerError("WORKER_SDK_INCOMPATIBLE")
    imported: list[str] = []

    def loader(name: str) -> object:
        imported.append(name)
        raise AssertionError("host must not import")

    lazy = LazyOfficialSdkAdapter(
        adapter_factory=lambda _module: _FakeAdapter(),
        compatibility_check=lambda: {"status": "compatible"},
        module_loader=loader,
    )
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx, adapter=lazy, process_boundary=process)
    assert caught.value.code == "WORKER_SDK_INCOMPATIBLE"
    assert caught.value.primary_code == "WORKER_SDK_INCOMPATIBLE"
    assert isinstance(caught.value.cleanup_result, WorkerCleanupResult)
    assert imported == []
    assert any(name == "cleanup" for name, _ in process.calls)


def test_31_module_ownership_has_no_autocad_file_ipc_repair_verdict_publication_or_persistence_routes() -> None:
    tree = ast.parse(SOURCE_MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {
        "autocad_plugin",
        "mcp_integration_lib",
        "dxf_builder_lib",
        "semantic_ir_lib",
        "primitive_ir_lib",
    }
    assert {name.split(".", 1)[0] for name in imported}.isdisjoint(forbidden)
    source = SOURCE_MODULE.read_text(encoding="utf-8").lower()
    for token in ("repair_executor", "verified_publisher", "manifest_store", "checkpoint_store"):
        assert token not in source


def test_32_candidate_output_is_explicitly_untrusted_and_grants_no_apply_cad_visual_or_publication_authority(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    session = _start(fx)
    result = session.turn({}, timeout_seconds=1.0, now=NOW)
    assert result.success is True
    assert result.candidate_output == MappingProxyType({"schema_version": "repair-plan-1.0"})
    assert result.candidate_trusted is False
    assert result.promotion_safe is False
    forbidden = {"apply", "approve", "publish", "cad_truth", "verdict", "repair"}
    assert forbidden.isdisjoint({name.lower() for name in dir(result)})


def test_remediation_33_task3_process_owner_exposes_handle_bound_control_surface() -> None:
    import agent_lib.codex_worker_process as process_owner

    assert "control_channel" in inspect.signature(process_owner.launch_worker_process).parameters
    assert callable(getattr(process_owner, "exchange_worker_control", None))
    assert callable(getattr(process_owner, "run_worker_control_child", None))


def test_remediation_34_control_channel_rejects_forged_handle() -> None:
    import agent_lib.codex_worker_process as process_owner

    exchange = getattr(process_owner, "exchange_worker_control")
    with pytest.raises(process_owner.WorkerProcessError) as caught:
        exchange(object(), {"operation": "probe"})
    assert caught.value.code == "WORKER_HANDLE_INVALID"
    assert SENTINEL not in str(caught.value)


@pytest.mark.parametrize("kind", ["malformed", "oversized", "unknown_version"])
def test_remediation_35_child_control_frames_fail_closed_without_raw_detail(kind: str) -> None:
    import io
    import json
    import struct
    import agent_lib.codex_worker_process as process_owner

    maximum = getattr(process_owner, "MAX_CONTROL_FRAME_BYTES")
    if kind == "malformed":
        body = b"{not-json " + SENTINEL.encode("utf-8")
        frame = struct.pack(">I", len(body)) + body
    elif kind == "oversized":
        frame = struct.pack(">I", maximum + 1)
    else:
        body = json.dumps({"version": 999, "request_id": 1, "payload": {"probe": True}}).encode("utf-8")
        frame = struct.pack(">I", len(body)) + body
    output = io.BytesIO()
    exit_code = process_owner.run_worker_control_child(
        lambda _payload: {"status": "ok"},
        input_stream=io.BytesIO(frame),
        output_stream=output,
    )
    assert exit_code != 0
    assert SENTINEL not in output.getvalue().decode("utf-8", errors="ignore")


def test_remediation_36_task3_uses_explicit_minimal_handle_inheritance_only() -> None:
    source = (Path(__file__).parents[1] / "codex_worker_process.py").read_text(encoding="utf-8")
    assert "PROC_THREAD_ATTRIBUTE_HANDLE_LIST" in source
    assert "EXTENDED_STARTUPINFO_PRESENT" in source
    for forbidden in ("socket", "mcp_integration_lib", "app-server", "codex exec"):
        assert forbidden not in source


@pytest.mark.skipif(__import__("os").name != "nt", reason="supported Windows child-control custody evidence")
def test_remediation_37_real_windows_child_control_is_job_bound_sanitized_and_closed(tmp_path: Path) -> None:
    import os
    import sys
    import agent_lib.codex_worker_process as process_owner

    root = tmp_path / "disposable"
    cwd = root / "cwd"
    cwd.mkdir(parents=True)
    source_environment = {
        "PATH": os.environ.get("PATH", ""),
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
        "COMSPEC": os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
        "PATHEXT": os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD"),
        "CUSTOM_SECRET": SENTINEL,
    }
    prepared = process_owner.prepare_worker_environment(
        disposable_root=root,
        cwd=cwd,
        source_environment=source_environment,
    )
    repo_root = str(Path(__file__).parents[2])
    child_code = (
        "import os,sys;"
        f"sys.path.insert(0,{repo_root!r});"
        "from agent_lib.codex_worker_process import run_worker_control_child;"
        "handler=lambda payload:{'pid':os.getpid(),'keys':sorted(os.environ),"
        "'secret_present':'CUSTOM_SECRET' in os.environ};"
        "raise SystemExit(run_worker_control_child(handler))"
    )
    handle = process_owner.launch_worker_process(
        environment=prepared,
        expected_disposable_root=prepared.disposable_root,
        expected_cwd=prepared.cwd,
        executable=Path(sys.executable).resolve(),
        argv=("-c", child_code),
        cleanup_deadline_seconds=5.0,
        max_processes=8,
        control_channel=True,
    )
    response = process_owner.exchange_worker_control(handle, {"operation": "probe"})
    tree = handle.snapshot_process_tree()
    assert response["pid"] in tree.member_pids
    assert response["secret_present"] is False
    assert {"CODEX_HOME", "TEMP", "TMP"}.issubset(response["keys"])
    cleanup = process_owner.cleanup_worker_process(handle)
    assert cleanup.success is True and cleanup.survivor_count == 0
    with pytest.raises(process_owner.WorkerProcessError) as caught:
        process_owner.exchange_worker_control(handle, {"operation": "late"})
    assert caught.value.code == "WORKER_CONTROL_CLOSED"


class _ChildOnlyBoundary(_FakeProcessBoundary):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[AdapterRequest] = []
        self.failures: dict[str, BaseException] = {}
        self.responses: dict[str, object] = {}

    def invoke(self, handle: object, request: AdapterRequest) -> object:
        del handle
        self.requests.append(request)
        failure = self.failures.get(request.operation)
        if failure is not None:
            raise failure
        if request.operation in self.responses:
            return self.responses[request.operation]
        return _FakeAdapter().invoke(request)


def test_remediation_38_host_sdk_import_and_delegate_traps_are_not_invoked(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _ChildOnlyBoundary()
    imported: list[str] = []
    built: list[bool] = []

    def loader(name: str) -> object:
        imported.append(name)
        raise AssertionError("host must not import official SDK")

    lazy = LazyOfficialSdkAdapter(
        adapter_factory=lambda _module: built.append(True) or _FakeAdapter(),
        compatibility_check=lambda: {"status": "compatible"},
        module_loader=loader,
    )
    session = _start(fx, adapter=lazy, process_boundary=process)
    session.turn({}, timeout_seconds=1.0, now=NOW)
    session.steer({}, timeout_seconds=1.0, now=NOW)
    session.close(timeout_seconds=1.0, now=NOW)
    assert imported == [] and built == []
    assert [request.operation for request in process.requests] == ["start", "turn", "steer", "close"]


def test_remediation_39_interrupt_and_cancel_route_through_child_bound_seam(tmp_path: Path) -> None:
    first = _fixture(tmp_path / "interrupt")
    first_process = _ChildOnlyBoundary()
    first_session = _start(first, process_boundary=first_process)
    first_session.interrupt(timeout_seconds=1.0, now=NOW)
    assert [request.operation for request in first_process.requests] == ["start", "interrupt"]

    second = _fixture(tmp_path / "cancel")
    second_process = _ChildOnlyBoundary()
    second_session = _start(second, process_boundary=second_process)
    second_session.cancel(timeout_seconds=1.0, now=NOW)
    assert [request.operation for request in second_process.requests] == ["start", "interrupt"]
    assert second_process.requests[-1].cancelled is True


def _survivor_cleanup() -> WorkerCleanupResult:
    return WorkerCleanupResult(
        status="CLEANUP_FAILED",
        success=False,
        promotion_safe=False,
        survivor_pids=(4102,),
        survivor_count=1,
        error_code="WORKER_CLEANUP_SURVIVORS",
    )


@pytest.mark.parametrize(
    ("cleanup_mode", "expected_code"),
    [
        ("exception", "WORKER_CLEANUP_FAILED"),
        ("malformed", "WORKER_CLEANUP_EVIDENCE_INVALID"),
        ("survivor", "WORKER_CLEANUP_FAILED"),
    ],
)
def test_remediation_40_start_provider_failure_preserves_cleanup_dominance(
    tmp_path: Path,
    cleanup_mode: str,
    expected_code: str,
) -> None:
    fx = _fixture(tmp_path)
    fx.adapter.failures["start"] = RuntimeError(SENTINEL)
    if cleanup_mode == "exception":
        def cleanup(_handle: object) -> object:
            raise RuntimeError(SENTINEL)
        fx.process.cleanup = cleanup  # type: ignore[method-assign]
    elif cleanup_mode == "malformed":
        fx.process.cleanup_result = SimpleNamespace(status="CLEANUP_FAILED", raw=SENTINEL)
    else:
        fx.process.cleanup_result = _survivor_cleanup()

    with pytest.raises(CodexWorkerError) as caught:
        _start(fx)
    assert caught.value.code == expected_code
    assert caught.value.primary_code == "WORKER_PROVIDER_FAILED"
    assert SENTINEL not in str(caught.value) and SENTINEL not in repr(caught.value)
    if cleanup_mode == "survivor":
        assert caught.value.cleanup_result == _survivor_cleanup()


def test_remediation_41_invalid_process_evidence_cannot_hide_cleanup_survivors(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx.process.cleanup_result = _survivor_cleanup()

    def mutate(handle: object) -> None:
        handle.tree = replace(handle.tree, verified=False)

    fx.process.handle_mutator = mutate
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx)
    assert caught.value.code == "WORKER_CLEANUP_FAILED"
    assert caught.value.primary_code == "WORKER_PROCESS_EVIDENCE_INVALID"
    assert caught.value.cleanup_result == _survivor_cleanup()


def test_remediation_42_malformed_start_response_cannot_hide_cleanup_survivors(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx.adapter.responses["start"] = {
        "status": "mystery",
        "thread_id": fx.binding.thread_id,
        "events": [],
    }
    fx.process.cleanup_result = _survivor_cleanup()
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx)
    assert caught.value.code == "WORKER_CLEANUP_FAILED"
    assert caught.value.primary_code == "WORKER_PROVIDER_RESPONSE_INVALID"
    assert caught.value.cleanup_result == _survivor_cleanup()


def test_remediation_43_start_timeout_cleanup_failure_dominates_timeout(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx.adapter.failures["start"] = TimeoutError(SENTINEL)
    fx.process.cleanup_result = _survivor_cleanup()
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx)
    assert caught.value.code == "WORKER_CLEANUP_FAILED"
    assert caught.value.primary_code == "WORKER_TIMEOUT"
    assert caught.value.cleanup_result == _survivor_cleanup()


def test_remediation_44_verified_cleanup_keeps_original_start_failure_category(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx.adapter.failures["start"] = RuntimeError(SENTINEL)
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx)
    assert caught.value.code == "WORKER_PROVIDER_FAILED"
    assert caught.value.primary_code == "WORKER_PROVIDER_FAILED"
    assert isinstance(caught.value.cleanup_result, WorkerCleanupResult)
    assert caught.value.cleanup_result.success is True
    assert SENTINEL not in str(caught.value)


def test_remediation_45_no_forbidden_transport_or_real_provider_route_is_added() -> None:
    worker_source = SOURCE_MODULE.read_text(encoding="utf-8").lower()
    process_source = (Path(__file__).parents[1] / "codex_worker_process.py").read_text(encoding="utf-8").lower()
    forbidden = (
        "app-server",
        "codex exec",
        "mcp_integration_lib",
        "socket.socket",
        "http://",
        "https://",
        "tempfile.namedtemporaryfile",
    )
    for token in forbidden:
        assert token not in worker_source
        assert token not in process_source


# Task-5 test-harness amendment. Successful legacy regressions model the
# authorized Task-3 child control seam; the original _FakeProcessBoundary stays
# intentionally untrusted for provenance-adversarial tests.
import agent_lib.codex_worker as _worker_module
from agent_lib.codex_worker_process import WorkerProcessError as _HarnessWorkerProcessError

_HARNESS_UNSET = object()


def _harness_observation(
    authority: object,
    binding: object,
    worker_context: object,
) -> dict[str, object]:
    policy = authority.provider_policy
    sandbox = worker_context.sandbox_policy
    return {
        "thread_id": binding.thread_id,
        "instruction_sources": [dict(item) for item in binding.instruction_source_identity],
        "approval_mode": policy["approval_mode"],
        "experimental_api": policy["experimental_api"],
        "model_identity": binding.model_config_identity["model_identity"],
        "config_sha256": binding.model_config_identity["config_sha256"],
        "adapter_version": binding.adapter_version,
        "sandbox_write_policy": sandbox["write_policy"],
        "cwd": sandbox["cwd"],
        "writable_roots": list(sandbox["roots"]),
        "full_access": False,
        "auto_review": False,
        "approval_escalation": False,
        "transport": "official_sdk",
        "alternate_transports": [],
    }


class _Task3HarnessHandle(_FakeProcessHandle):
    def __init__(
        self,
        attestation: WorkerEnvironmentAttestation,
        boundary: "_Task3HarnessBoundary",
    ) -> None:
        super().__init__(attestation)
        self.boundary = boundary


class _Task3HarnessBoundary(_FakeProcessBoundary):
    def __init__(self) -> None:
        super().__init__()
        self.attestation_factory = None
        self.attest_calls: list[AdapterRequest] = []
        self.attestation_mutators: dict[str, object] = {}
        self.attestation_responses: dict[str, object] = {}
        self.attestation_failures: dict[str, BaseException] = {}
        self.requests: list[AdapterRequest] = []

    def start(
        self,
        *,
        expected_disposable_root: Path,
        expected_cwd: Path,
    ) -> tuple[WorkerEnvironmentAttestation, object]:
        attestation, raw_handle = super().start(
            expected_disposable_root=expected_disposable_root,
            expected_cwd=expected_cwd,
        )
        handle = _Task3HarnessHandle(attestation, self)
        handle.tree = raw_handle.tree
        return attestation, handle

    def control_attest(self, request: AdapterRequest) -> object:
        self.calls.append(("attest", request))
        self.attest_calls.append(request)
        failure = self.attestation_failures.get(request.operation)
        if failure is not None:
            raise failure
        response = self.attestation_responses.get(request.operation, _HARNESS_UNSET)
        if response is not _HARNESS_UNSET:
            return response
        factory = self.attestation_factory
        if not callable(factory):
            raise CodexWorkerError("WORKER_SDK_ATTESTATION_GAP")
        observed = factory(request)
        if not isinstance(observed, dict):
            return observed
        copied = {
            key: (
                [dict(item) for item in value]
                if key == "instruction_sources"
                else list(value)
                if key in {"writable_roots", "alternate_transports"}
                else value
            )
            for key, value in observed.items()
        }
        mutator = self.attestation_mutators.get(request.operation)
        if callable(mutator):
            mutator(copied)
        return copied

    def control_invoke(self, request: AdapterRequest) -> object:
        self.calls.append(("invoke", request))
        self.requests.append(request)
        adapter = self.adapter
        if adapter is None:
            raise AssertionError("fake child adapter not configured")
        if not self._compatible:
            adapter.ensure_compatible()
            self._compatible = True
        return adapter.invoke(request)


class _ChildOnlyBoundary(_Task3HarnessBoundary):
    def __init__(self) -> None:
        super().__init__()
        self.failures: dict[str, BaseException] = {}
        self.responses: dict[str, object] = {}

    def control_invoke(self, request: AdapterRequest) -> object:
        self.calls.append(("invoke", request))
        self.requests.append(request)
        failure = self.failures.get(request.operation)
        if failure is not None:
            raise failure
        if request.operation in self.responses:
            return self.responses[request.operation]
        return _FakeAdapter().invoke(request)


def _task3_harness_exchange(handle: object, payload: Mapping[str, object]) -> object:
    if not isinstance(handle, _Task3HarnessHandle):
        raise _HarnessWorkerProcessError("WORKER_HANDLE_INVALID")
    request = _worker_module._request_from_wire(payload)
    boundary = handle.boundary
    try:
        if request.operation.startswith(_worker_module._ATTESTATION_OPERATION_PREFIX):
            operation = request.operation[len(_worker_module._ATTESTATION_OPERATION_PREFIX) :]
            request = replace(request, operation=operation)
            return boundary.control_attest(request)
        return boundary.control_invoke(request)
    except TimeoutError:
        return {"_worker_error": "WORKER_TIMEOUT"}
    except CodexWorkerError as exc:
        return {"_worker_error": exc.code}
    except Exception:
        return {"_worker_error": "WORKER_PROVIDER_FAILED"}


@pytest.fixture(autouse=True)
def _authorized_task3_control_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_worker_module, "exchange_worker_control", _task3_harness_exchange)


def _fixture(tmp_path: Path, *, thread_id: str = "THREAD-001") -> _Fixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    authority = _authority_context(dict(handoff.payload))
    worker_context = _worker_context(handoff, thread_id=thread_id)
    binding = bind_worker_thread(
        handoff,
        thread_id=thread_id,
        authority_context=authority,
        worker_context=worker_context,
        now=NOW,
    )
    adapter = _FakeAdapter()
    process = _Task3HarnessBoundary()
    process.adapter = adapter
    process.attestation_factory = lambda _request: _harness_observation(
        authority, binding, worker_context
    )
    return _Fixture(
        schema_path=schema_path,
        handoff=handoff,
        authority=authority,
        worker_context=worker_context,
        binding=binding,
        adapter=adapter,
        process=process,
    )


def _start(fx: _Fixture, **overrides: object) -> CodexWorkerSession:
    values = {
        "handoff": fx.handoff,
        "binding": fx.binding,
        "authority_context": fx.authority,
        "worker_context": fx.worker_context,
        "adapter": fx.adapter,
        "process_boundary": fx.process,
        "timeout_seconds": 1.0,
        "now": NOW,
    }
    values.update(overrides)
    boundary = values.get("process_boundary")
    if isinstance(boundary, _Task3HarnessBoundary):
        if boundary.adapter is None:
            boundary.adapter = fx.adapter
        if boundary.attestation_factory is None:
            boundary.attestation_factory = fx.process.attestation_factory
    return start_codex_worker(**values)
