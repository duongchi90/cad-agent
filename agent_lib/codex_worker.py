"""Provider-independent, fail-closed official SDK worker lifecycle seam.

This module composes existing handoff/thread authority with the accepted Task-3
process boundary. Official-SDK compatibility/import/delegate work is child-owned
when the concrete Task-3 boundary is used. Provider responses and candidate
output remain untrusted.
"""

from __future__ import annotations

import base64
import importlib
import math
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from agent_lib.codex_sdk_compat import require_compatible_codex_sdk
from agent_lib.codex_worker_process import (
    ProcessTreeIdentity,
    WorkerCleanupResult,
    WorkerEnvironmentAttestation,
    WorkerProcessError,
    cleanup_worker_process,
    exchange_worker_control,
    launch_worker_process,
    prepare_worker_environment,
    run_worker_control_child,
)
from cad_agent.vision_handoff import (
    BoundWorkerThread,
    ServerOwnedAuthorityContext,
    ServerOwnedWorkerBindingContext,
    ValidatedVisionHandoff,
    VisionHandoffError,
    fork_worker_thread,
    resume_worker_thread,
)

MAX_OPERATION_TIMEOUT_SECONDS = 30.0
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_ALLOWED_EVENTS = frozenset(
    {
        "thread.ready",
        "turn.started",
        "turn.completed",
        "turn.steered",
        "turn.interrupted",
        "thread.closed",
        "provider.failed",
    }
)
_CHILD_ERROR_CODES = frozenset(
    {
        "WORKER_SDK_INCOMPATIBLE",
        "WORKER_PROVIDER_FAILED",
        "WORKER_PROVIDER_RESPONSE_INVALID",
        "WORKER_TIMEOUT",
    }
)


class CodexWorkerError(RuntimeError):
    """Categorical Task-4 failure without raw provider/private detail."""

    def __init__(
        self,
        code: str,
        *,
        primary_code: str | None = None,
        cleanup_result: WorkerCleanupResult | None = None,
    ) -> None:
        self.code = code
        self.primary_code = primary_code or code
        self.cleanup_result = cleanup_result
        super().__init__(code)


def _fail(code: str) -> None:
    raise CodexWorkerError(code)


def _freeze_json_like(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("WORKER_PROVIDER_RESPONSE_INVALID")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        try:
            for key, item in value.items():
                if not isinstance(key, str):
                    _fail("WORKER_PROVIDER_RESPONSE_INVALID")
                frozen[key] = _freeze_json_like(item)
        except CodexWorkerError:
            raise
        except Exception:
            _fail("WORKER_PROVIDER_RESPONSE_INVALID")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        try:
            return tuple(_freeze_json_like(item) for item in value)
        except CodexWorkerError:
            raise
        except Exception:
            _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    _fail("WORKER_PROVIDER_RESPONSE_INVALID")


def _thaw_json_like(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("WORKER_PROVIDER_RESPONSE_INVALID")
        return value
    if isinstance(value, Mapping):
        return {str(key): _thaw_json_like(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_json_like(item) for item in value]
    _fail("WORKER_PROVIDER_RESPONSE_INVALID")


def _identifier(value: object) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    return value


def _validate_timeout(value: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value <= 0
        or value > MAX_OPERATION_TIMEOUT_SECONDS
    ):
        _fail("WORKER_LIMIT_INVALID")
    return float(value)


@dataclass(frozen=True, repr=False)
class AdapterRequest:
    """Immutable normalized request for one child-owned adapter operation."""

    operation: str
    thread_id: str
    handoff_sha256: str
    run_id: str
    approval_mode: str
    experimental_api: bool
    model_identity: str
    config_sha256: str
    output_schema_bytes: bytes
    output_schema_sha256: str
    output_validator_version: str
    sandbox_roots: tuple[str, ...]
    cwd: str
    timeout_seconds: float
    input_payload: object | None = None
    cancelled: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "sandbox_roots", tuple(self.sandbox_roots))
        object.__setattr__(self, "input_payload", _freeze_json_like(self.input_payload))

    def __repr__(self) -> str:
        return (
            "AdapterRequest("
            f"operation={self.operation!r}, thread_id={self.thread_id!r}, "
            f"cancelled={self.cancelled!r})"
        )


@dataclass(frozen=True)
class CodexWorkerEvent:
    """Privacy-safe normalized provider event identity only."""

    kind: str


@dataclass(frozen=True)
class CodexWorkerResult:
    """Normalized Task-4 result; candidate output is always explicitly untrusted."""

    operation: str
    status: str
    success: bool
    thread_id: str
    turn_id: str | None
    events: tuple[CodexWorkerEvent, ...]
    candidate_output: object | None
    candidate_trusted: bool
    failure_code: str | None
    cleanup_result: WorkerCleanupResult | None
    promotion_safe: bool


class WorkerAdapter(Protocol):
    def ensure_compatible(self) -> None: ...
    def invoke(self, request: AdapterRequest) -> object: ...


class WorkerProcessBoundary(Protocol):
    def start(
        self,
        *,
        expected_disposable_root: Path,
        expected_cwd: Path,
    ) -> tuple[WorkerEnvironmentAttestation, object]: ...
    def invoke(self, handle: object, request: AdapterRequest) -> object: ...
    def cleanup(self, handle: object) -> object: ...


def _request_to_wire(request: AdapterRequest) -> Mapping[str, object]:
    return {
        "operation": request.operation,
        "thread_id": request.thread_id,
        "handoff_sha256": request.handoff_sha256,
        "run_id": request.run_id,
        "approval_mode": request.approval_mode,
        "experimental_api": request.experimental_api,
        "model_identity": request.model_identity,
        "config_sha256": request.config_sha256,
        "output_schema_b64": base64.b64encode(request.output_schema_bytes).decode("ascii"),
        "output_schema_sha256": request.output_schema_sha256,
        "output_validator_version": request.output_validator_version,
        "sandbox_roots": list(request.sandbox_roots),
        "cwd": request.cwd,
        "timeout_seconds": request.timeout_seconds,
        "input_payload": _thaw_json_like(request.input_payload),
        "cancelled": request.cancelled,
    }


def _request_from_wire(value: Mapping[str, object]) -> AdapterRequest:
    required = {
        "operation",
        "thread_id",
        "handoff_sha256",
        "run_id",
        "approval_mode",
        "experimental_api",
        "model_identity",
        "config_sha256",
        "output_schema_b64",
        "output_schema_sha256",
        "output_validator_version",
        "sandbox_roots",
        "cwd",
        "timeout_seconds",
        "input_payload",
        "cancelled",
    }
    if set(value) != required:
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    schema_text = value.get("output_schema_b64")
    roots = value.get("sandbox_roots")
    if not isinstance(schema_text, str) or not isinstance(roots, list):
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    if any(not isinstance(root, str) for root in roots):
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    try:
        schema_bytes = base64.b64decode(schema_text.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError):
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    operation = value.get("operation")
    thread_id = value.get("thread_id")
    handoff_sha256 = value.get("handoff_sha256")
    run_id = value.get("run_id")
    approval_mode = value.get("approval_mode")
    experimental_api = value.get("experimental_api")
    model_identity = value.get("model_identity")
    config_sha256 = value.get("config_sha256")
    output_schema_sha256 = value.get("output_schema_sha256")
    output_validator_version = value.get("output_validator_version")
    cwd = value.get("cwd")
    timeout_seconds = value.get("timeout_seconds")
    cancelled = value.get("cancelled")
    strings = (
        operation,
        thread_id,
        handoff_sha256,
        run_id,
        approval_mode,
        model_identity,
        config_sha256,
        output_schema_sha256,
        output_validator_version,
        cwd,
    )
    if any(not isinstance(item, str) for item in strings):
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    if not isinstance(experimental_api, bool) or not isinstance(cancelled, bool):
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    return AdapterRequest(
        operation=operation,
        thread_id=thread_id,
        handoff_sha256=handoff_sha256,
        run_id=run_id,
        approval_mode=approval_mode,
        experimental_api=experimental_api,
        model_identity=model_identity,
        config_sha256=config_sha256,
        output_schema_bytes=schema_bytes,
        output_schema_sha256=output_schema_sha256,
        output_validator_version=output_validator_version,
        sandbox_roots=tuple(roots),
        cwd=cwd,
        timeout_seconds=float(timeout_seconds),
        input_payload=value.get("input_payload"),
        cancelled=cancelled,
    )


class Task3ProcessBoundary:
    """Concrete Task-3 child-control client for Task-4 lifecycle requests."""

    def __init__(
        self,
        *,
        cleanup_deadline_seconds: float,
        max_processes: int,
        source_environment: Mapping[str, str] | None = None,
        _executable: Path | None = None,
        _argv: Sequence[str] | None = None,
    ) -> None:
        self._cleanup_deadline_seconds = float(cleanup_deadline_seconds)
        self._max_processes = max_processes
        self._source_environment = source_environment
        self._executable = Path(_executable or sys.executable).resolve()
        if _argv is None:
            repo_root = str(Path(__file__).resolve().parents[1])
            child_code = (
                "import sys;"
                f"sys.path.insert(0,{repo_root!r});"
                "from agent_lib.codex_worker import _child_main;"
                "raise SystemExit(_child_main())"
            )
            self._argv = ("-c", child_code)
        else:
            self._argv = tuple(_argv)

    def start(
        self,
        *, expected_disposable_root: Path, expected_cwd: Path
    ) -> tuple[WorkerEnvironmentAttestation, object]:
        attestation = prepare_worker_environment(
            disposable_root=expected_disposable_root,
            cwd=expected_cwd,
            source_environment=self._source_environment,
        )
        handle = launch_worker_process(
            environment=attestation,
            expected_disposable_root=expected_disposable_root,
            expected_cwd=expected_cwd,
            executable=self._executable,
            argv=self._argv,
            cleanup_deadline_seconds=self._cleanup_deadline_seconds,
            max_processes=self._max_processes,
            control_channel=True,
        )
        return attestation, handle

    def invoke(self, handle: object, request: AdapterRequest) -> object:
        try:
            response = exchange_worker_control(handle, _request_to_wire(request))  # type: ignore[arg-type]
        except WorkerProcessError:
            _fail("WORKER_PROVIDER_FAILED")
        worker_error = response.get("_worker_error")
        if worker_error is not None:
            if not isinstance(worker_error, str) or worker_error not in _CHILD_ERROR_CODES:
                _fail("WORKER_PROVIDER_FAILED")
            _fail(worker_error)
        return response

    def cleanup(self, handle: object) -> object:
        return cleanup_worker_process(handle)  # type: ignore[arg-type]


class LazyOfficialSdkAdapter:
    """Lazy official-SDK import seam intended to execute inside the child."""

    def __init__(
        self,
        *,
        adapter_factory: Callable[[object], WorkerAdapter],
        compatibility_check: Callable[[], object] = require_compatible_codex_sdk,
        module_loader: Callable[[str], object] = importlib.import_module,
    ) -> None:
        self._adapter_factory = adapter_factory
        self._compatibility_check = compatibility_check
        self._module_loader = module_loader
        self._delegate: WorkerAdapter | None = None

    def ensure_compatible(self) -> None:
        if self._delegate is not None:
            return
        try:
            self._compatibility_check()
            module = self._module_loader("openai_codex")
            delegate = self._adapter_factory(module)
            if not callable(getattr(delegate, "invoke", None)):
                _fail("WORKER_SDK_INCOMPATIBLE")
            self._delegate = delegate
        except CodexWorkerError:
            raise
        except Exception:
            _fail("WORKER_SDK_INCOMPATIBLE")

    def invoke(self, request: AdapterRequest) -> object:
        self.ensure_compatible()
        delegate = self._delegate
        if delegate is None:
            _fail("WORKER_SDK_INCOMPATIBLE")
        return delegate.invoke(request)


def run_codex_worker_child(
    *,
    adapter_factory: Callable[[object], WorkerAdapter],
    compatibility_check: Callable[[], object] = require_compatible_codex_sdk,
    module_loader: Callable[[str], object] = importlib.import_module,
    input_stream=None,
    output_stream=None,
) -> int:
    lazy = LazyOfficialSdkAdapter(
        adapter_factory=adapter_factory,
        compatibility_check=compatibility_check,
        module_loader=module_loader,
    )

    def handler(payload: Mapping[str, object]) -> Mapping[str, object]:
        try:
            request = _request_from_wire(payload)
            response = lazy.invoke(request)
            if not isinstance(response, Mapping):
                return {"_worker_error": "WORKER_PROVIDER_RESPONSE_INVALID"}
            thawed = _thaw_json_like(response)
            if not isinstance(thawed, Mapping):
                return {"_worker_error": "WORKER_PROVIDER_RESPONSE_INVALID"}
            return thawed
        except TimeoutError:
            return {"_worker_error": "WORKER_TIMEOUT"}
        except CodexWorkerError as exc:
            code = exc.code if exc.code in _CHILD_ERROR_CODES else "WORKER_PROVIDER_FAILED"
            return {"_worker_error": code}
        except Exception:
            return {"_worker_error": "WORKER_PROVIDER_FAILED"}

    return run_worker_control_child(
        handler, input_stream=input_stream, output_stream=output_stream
    )


def _unsupported_official_adapter_factory(_module: object) -> WorkerAdapter:
    _fail("WORKER_SDK_INCOMPATIBLE")


def _child_main() -> int:
    return run_codex_worker_child(adapter_factory=_unsupported_official_adapter_factory)


def _sandbox_boundary(
    worker_context: ServerOwnedWorkerBindingContext,
) -> tuple[Path, Path, tuple[str, ...]]:
    if not isinstance(worker_context, ServerOwnedWorkerBindingContext):
        _fail("WORKER_AUTHORITY_MISMATCH")
    sandbox = worker_context.sandbox_policy
    if not isinstance(sandbox, Mapping):
        _fail("WORKER_AUTHORITY_MISMATCH")
    roots = sandbox.get("roots")
    cwd = sandbox.get("cwd")
    write_policy = sandbox.get("write_policy")
    if (
        not isinstance(roots, (list, tuple))
        or len(roots) != 1
        or not isinstance(roots[0], str)
        or not roots[0]
        or not isinstance(cwd, str)
        or not cwd
        or write_policy != "DISPOSABLE_ONLY"
        or cwd != roots[0]
    ):
        _fail("WORKER_AUTHORITY_MISMATCH")
    return Path(roots[0]), Path(cwd), (roots[0],)


def _policy_fields(
    authority_context: ServerOwnedAuthorityContext,
    binding: BoundWorkerThread,
) -> tuple[str, bool, str, str]:
    if not isinstance(authority_context, ServerOwnedAuthorityContext):
        _fail("WORKER_AUTHORITY_MISMATCH")
    policy = authority_context.provider_policy
    if not isinstance(policy, Mapping):
        _fail("WORKER_AUTHORITY_MISMATCH")
    approval_mode = policy.get("approval_mode")
    experimental_api = policy.get("experimental_api")
    if approval_mode != "deny_all" or experimental_api is not False:
        _fail("WORKER_AUTHORITY_MISMATCH")
    model = binding.model_config_identity
    if not isinstance(model, Mapping):
        _fail("WORKER_AUTHORITY_MISMATCH")
    model_identity = model.get("model_identity")
    config_sha256 = model.get("config_sha256")
    if not isinstance(model_identity, str) or not isinstance(config_sha256, str):
        _fail("WORKER_AUTHORITY_MISMATCH")
    return approval_mode, False, model_identity, config_sha256


def _revalidate_binding(
    *,
    handoff: ValidatedVisionHandoff,
    binding: BoundWorkerThread,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
    now: datetime | None,
) -> tuple[Path, Path, tuple[str, ...]]:
    if not isinstance(handoff, ValidatedVisionHandoff) or not isinstance(
        binding, BoundWorkerThread
    ):
        _fail("WORKER_AUTHORITY_MISMATCH")
    try:
        observed = resume_worker_thread(
            binding,
            handoff,
            thread_id=binding.thread_id,
            authority_context=authority_context,
            worker_context=worker_context,
            now=now,
        )
    except (VisionHandoffError, TypeError, ValueError, AttributeError):
        _fail("WORKER_AUTHORITY_MISMATCH")
    if observed != binding:
        _fail("WORKER_AUTHORITY_MISMATCH")
    root, cwd, roots = _sandbox_boundary(worker_context)
    _policy_fields(authority_context, binding)
    return root, cwd, roots


def _validate_process_evidence(
    *,
    attestation: WorkerEnvironmentAttestation,
    handle: object,
    expected_root: Path,
    expected_cwd: Path,
) -> None:
    if not isinstance(attestation, WorkerEnvironmentAttestation):
        _fail("WORKER_PROCESS_EVIDENCE_INVALID")
    if getattr(handle, "environment_attestation", None) != attestation:
        _fail("WORKER_PROCESS_EVIDENCE_INVALID")
    expected_writable = (
        expected_cwd,
        expected_root / "codex-home",
        expected_root / "tmp",
    )
    if (
        attestation.disposable_root != expected_root
        or attestation.cwd != expected_cwd
        or attestation.codex_home != expected_writable[1]
        or attestation.temp_dir != expected_writable[2]
        or attestation.writable_roots != expected_writable
    ):
        _fail("WORKER_PROCESS_EVIDENCE_INVALID")
    try:
        tree = handle.snapshot_process_tree()
    except Exception:
        _fail("WORKER_PROCESS_EVIDENCE_INVALID")
    root_pid = getattr(handle, "root_pid", None)
    if (
        not isinstance(tree, ProcessTreeIdentity)
        or tree.verified is not True
        or tree.member_count != len(tree.member_pids)
        or not isinstance(root_pid, int)
        or isinstance(root_pid, bool)
        or root_pid <= 0
        or tree.root_pid != root_pid
        or root_pid not in tree.member_pids
    ):
        _fail("WORKER_PROCESS_EVIDENCE_INVALID")


def _normalize_events(value: object) -> tuple[CodexWorkerEvent, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    events: list[CodexWorkerEvent] = []
    try:
        for raw in value:
            if not isinstance(raw, Mapping):
                _fail("WORKER_PROVIDER_RESPONSE_INVALID")
            kind = raw.get("type")
            if not isinstance(kind, str) or kind not in _ALLOWED_EVENTS:
                _fail("WORKER_PROVIDER_RESPONSE_INVALID")
            events.append(CodexWorkerEvent(kind=kind))
    except CodexWorkerError:
        raise
    except Exception:
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    return tuple(events)


def _normalize_response(
    value: object,
    *, operation: str, expected_thread_id: str
) -> tuple[str, str | None, tuple[CodexWorkerEvent, ...], object | None]:
    if not isinstance(value, Mapping):
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    try:
        status = value.get("status")
        thread_id = value.get("thread_id")
        events = _normalize_events(value.get("events", ()))
    except CodexWorkerError:
        raise
    except Exception:
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    if thread_id != expected_thread_id:
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    allowed_status = {
        "start": {"ready"},
        "resume": {"ready"},
        "fork": {"ready"},
        "turn": {"completed", "failed"},
        "steer": {"completed", "failed"},
        "interrupt": {"interrupted"},
        "close": {"closed", "failed"},
    }.get(operation)
    if allowed_status is None or status not in allowed_status:
        _fail("WORKER_PROVIDER_RESPONSE_INVALID")
    turn_id: str | None = None
    candidate: object | None = None
    if operation in {"turn", "steer"} and status == "completed":
        turn_id = _identifier(value.get("turn_id"))
        if "candidate_output" not in value:
            _fail("WORKER_PROVIDER_RESPONSE_INVALID")
        candidate = _freeze_json_like(value.get("candidate_output"))
    return str(status), turn_id, events, candidate


def _cleanup_evidence(
    process_boundary: WorkerProcessBoundary, handle: object
) -> tuple[WorkerCleanupResult | None, str | None]:
    try:
        result = process_boundary.cleanup(handle)
    except Exception:
        return None, "WORKER_CLEANUP_FAILED"
    if not isinstance(result, WorkerCleanupResult):
        return None, "WORKER_CLEANUP_EVIDENCE_INVALID"
    if (
        result.status == "CLEANUP_SUCCEEDED"
        and result.success is True
        and result.promotion_safe is True
        and result.survivor_pids == ()
        and result.survivor_count == 0
        and result.error_code is None
    ):
        return result, None
    return result, "WORKER_CLEANUP_FAILED"


def _raise_open_failure(
    process_boundary: WorkerProcessBoundary, handle: object, primary_code: str
) -> None:
    cleanup, cleanup_code = _cleanup_evidence(process_boundary, handle)
    raise CodexWorkerError(
        cleanup_code or primary_code,
        primary_code=primary_code,
        cleanup_result=cleanup,
    )


def _invoke_child(
    process_boundary: WorkerProcessBoundary, handle: object, request: AdapterRequest
) -> object:
    try:
        return process_boundary.invoke(handle, request)
    except TimeoutError:
        raise CodexWorkerError("WORKER_TIMEOUT") from None
    except CodexWorkerError:
        raise
    except Exception:
        raise CodexWorkerError("WORKER_PROVIDER_FAILED") from None


class CodexWorkerSession:
    __slots__ = (
        "_authority_context",
        "_binding",
        "_cleanup_result",
        "_environment_attestation",
        "_handoff",
        "_pending_candidate",
        "_process_boundary",
        "_process_handle",
        "_status",
        "_terminal_result",
        "_worker_context",
    )

    def __init__(
        self,
        *,
        handoff: ValidatedVisionHandoff,
        binding: BoundWorkerThread,
        authority_context: ServerOwnedAuthorityContext,
        worker_context: ServerOwnedWorkerBindingContext,
        process_boundary: WorkerProcessBoundary,
        environment_attestation: WorkerEnvironmentAttestation,
        process_handle: object,
    ) -> None:
        self._handoff = handoff
        self._binding = binding
        self._authority_context = authority_context
        self._worker_context = worker_context
        self._process_boundary = process_boundary
        self._environment_attestation = environment_attestation
        self._process_handle = process_handle
        self._status = "READY"
        self._pending_candidate: object | None = None
        self._cleanup_result: WorkerCleanupResult | None = None
        self._terminal_result: CodexWorkerResult | None = None

    @property
    def binding(self) -> BoundWorkerThread:
        return self._binding

    @property
    def status(self) -> str:
        return self._status

    def _request_with_now(
        self,
        operation: str,
        *,
        input_payload: object | None,
        timeout_seconds: float,
        now: datetime | None,
        cancelled: bool = False,
    ) -> AdapterRequest:
        timeout = _validate_timeout(timeout_seconds)
        root, cwd, roots = _revalidate_binding(
            handoff=self._handoff,
            binding=self._binding,
            authority_context=self._authority_context,
            worker_context=self._worker_context,
            now=now,
        )
        del root
        approval_mode, experimental_api, model_identity, config_sha256 = _policy_fields(
            self._authority_context, self._binding
        )
        return AdapterRequest(
            operation=operation,
            thread_id=self._binding.thread_id,
            handoff_sha256=self._binding.handoff_hash,
            run_id=self._binding.run_id,
            approval_mode=approval_mode,
            experimental_api=experimental_api,
            model_identity=model_identity,
            config_sha256=config_sha256,
            output_schema_bytes=bytes(self._handoff.schema_snapshot.raw_bytes),
            output_schema_sha256=self._binding.output_schema_sha256,
            output_validator_version=self._binding.output_validator_version,
            sandbox_roots=roots,
            cwd=str(cwd),
            timeout_seconds=timeout,
            input_payload=input_payload,
            cancelled=cancelled,
        )

    def _result(
        self,
        *, operation: str, status: str, success: bool,
        turn_id: str | None = None,
        events: tuple[CodexWorkerEvent, ...] = (),
        candidate_output: object | None = None,
        failure_code: str | None = None,
        cleanup_result: WorkerCleanupResult | None = None,
        promotion_safe: bool = False,
    ) -> CodexWorkerResult:
        return CodexWorkerResult(
            operation=operation,
            status=status,
            success=success,
            thread_id=self._binding.thread_id,
            turn_id=turn_id,
            events=events,
            candidate_output=candidate_output,
            candidate_trusted=False,
            failure_code=failure_code,
            cleanup_result=cleanup_result,
            promotion_safe=promotion_safe,
        )

    def _cleanup_failure(self, operation: str, code: str) -> CodexWorkerResult:
        if self._terminal_result is not None:
            return self._terminal_result
        cleanup, cleanup_code = _cleanup_evidence(
            self._process_boundary, self._process_handle
        )
        self._cleanup_result = cleanup
        final_code = cleanup_code or code
        self._pending_candidate = None
        self._status = "FAILED" if self._status != "CANCELLED" else "CANCELLED"
        result = self._result(
            operation=operation,
            status=self._status,
            success=False,
            failure_code=final_code,
            cleanup_result=cleanup,
            promotion_safe=False,
        )
        self._terminal_result = result
        return result

    def _invoke(
        self,
        operation: str,
        payload: object,
        *, timeout_seconds: float, now: datetime | None
    ) -> CodexWorkerResult:
        if self._terminal_result is not None:
            return self._terminal_result
        try:
            request = self._request_with_now(
                operation,
                input_payload=payload,
                timeout_seconds=timeout_seconds,
                now=now,
            )
        except CodexWorkerError:
            return self._cleanup_failure(operation, "WORKER_AUTHORITY_MISMATCH")
        started = time.monotonic()
        try:
            response = _invoke_child(self._process_boundary, self._process_handle, request)
        except CodexWorkerError as exc:
            code = "WORKER_TIMEOUT" if exc.code == "WORKER_TIMEOUT" else "WORKER_PROVIDER_FAILED"
            return self._cleanup_failure(operation, code)
        if time.monotonic() - started > request.timeout_seconds:
            return self._cleanup_failure(operation, "WORKER_TIMEOUT")
        try:
            status, turn_id, events, candidate = _normalize_response(
                response,
                operation=operation,
                expected_thread_id=self._binding.thread_id,
            )
        except CodexWorkerError:
            return self._cleanup_failure(operation, "WORKER_PROVIDER_RESPONSE_INVALID")
        if status == "failed":
            return self._cleanup_failure(operation, "WORKER_PROVIDER_FAILED")
        self._pending_candidate = candidate
        return self._result(
            operation=operation,
            status="COMPLETED",
            success=True,
            turn_id=turn_id,
            events=events,
            candidate_output=candidate,
            promotion_safe=False,
        )

    def turn(
        self, payload: object, *, timeout_seconds: float, now: datetime | None = None
    ) -> CodexWorkerResult:
        return self._invoke("turn", payload, timeout_seconds=timeout_seconds, now=now)

    def steer(
        self, payload: object, *, timeout_seconds: float, now: datetime | None = None
    ) -> CodexWorkerResult:
        return self._invoke("steer", payload, timeout_seconds=timeout_seconds, now=now)

    def interrupt(
        self, *, timeout_seconds: float, now: datetime | None = None
    ) -> CodexWorkerResult:
        if self._terminal_result is not None:
            return self._terminal_result
        try:
            request = self._request_with_now(
                "interrupt",
                input_payload=None,
                timeout_seconds=timeout_seconds,
                now=now,
            )
            response = _invoke_child(self._process_boundary, self._process_handle, request)
            _normalize_response(
                response,
                operation="interrupt",
                expected_thread_id=self._binding.thread_id,
            )
        except Exception:
            return self._cleanup_failure("interrupt", "WORKER_INTERRUPT_FAILED")
        self._status = "INTERRUPTED"
        return self._cleanup_failure("interrupt", "WORKER_INTERRUPTED")

    def cancel(
        self, *, timeout_seconds: float, now: datetime | None = None
    ) -> CodexWorkerResult:
        if self._terminal_result is not None:
            return self._terminal_result
        self._status = "CANCELLED"
        try:
            request = self._request_with_now(
                "interrupt",
                input_payload=None,
                timeout_seconds=timeout_seconds,
                now=now,
                cancelled=True,
            )
            _invoke_child(self._process_boundary, self._process_handle, request)
        except Exception:
            return self._cleanup_failure("cancel", "WORKER_INTERRUPT_FAILED")
        return self._cleanup_failure("cancel", "WORKER_CANCELLED")

    def close(
        self, *, timeout_seconds: float, now: datetime | None = None
    ) -> CodexWorkerResult:
        if self._terminal_result is not None:
            return self._terminal_result
        provider_code: str | None = None
        events: tuple[CodexWorkerEvent, ...] = ()
        try:
            request = self._request_with_now(
                "close",
                input_payload=None,
                timeout_seconds=timeout_seconds,
                now=now,
            )
            response = _invoke_child(self._process_boundary, self._process_handle, request)
            status, _turn_id, events, _candidate = _normalize_response(
                response,
                operation="close",
                expected_thread_id=self._binding.thread_id,
            )
            if status == "failed":
                provider_code = "WORKER_PROVIDER_FAILED"
        except CodexWorkerError as exc:
            provider_code = (
                "WORKER_AUTHORITY_MISMATCH"
                if exc.code == "WORKER_AUTHORITY_MISMATCH"
                else "WORKER_PROVIDER_FAILED"
            )
        except Exception:
            provider_code = "WORKER_PROVIDER_FAILED"
        cleanup, cleanup_code = _cleanup_evidence(
            self._process_boundary, self._process_handle
        )
        self._cleanup_result = cleanup
        if cleanup_code is not None or provider_code is not None:
            self._pending_candidate = None
            self._status = "FAILED"
            result = self._result(
                operation="close",
                status="FAILED",
                success=False,
                events=events,
                failure_code=cleanup_code or provider_code,
                cleanup_result=cleanup,
                promotion_safe=False,
            )
        else:
            self._status = "CLOSED"
            result = self._result(
                operation="close",
                status="CLOSED",
                success=True,
                events=events,
                candidate_output=self._pending_candidate,
                cleanup_result=cleanup,
                promotion_safe=True,
            )
        self._terminal_result = result
        return result


def _open_codex_worker(
    *,
    operation: str,
    handoff: ValidatedVisionHandoff,
    binding: BoundWorkerThread,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
    adapter: WorkerAdapter,
    process_boundary: WorkerProcessBoundary,
    timeout_seconds: float,
    now: datetime | None,
) -> CodexWorkerSession:
    del adapter
    timeout = _validate_timeout(timeout_seconds)
    root, cwd, roots = _revalidate_binding(
        handoff=handoff,
        binding=binding,
        authority_context=authority_context,
        worker_context=worker_context,
        now=now,
    )
    try:
        attestation, handle = process_boundary.start(
            expected_disposable_root=root, expected_cwd=cwd
        )
    except Exception:
        _fail("WORKER_PROCESS_START_FAILED")
    try:
        _validate_process_evidence(
            attestation=attestation,
            handle=handle,
            expected_root=root,
            expected_cwd=cwd,
        )
    except CodexWorkerError as exc:
        _raise_open_failure(process_boundary, handle, exc.code)
    approval_mode, experimental_api, model_identity, config_sha256 = _policy_fields(
        authority_context, binding
    )
    request = AdapterRequest(
        operation=operation,
        thread_id=binding.thread_id,
        handoff_sha256=binding.handoff_hash,
        run_id=binding.run_id,
        approval_mode=approval_mode,
        experimental_api=experimental_api,
        model_identity=model_identity,
        config_sha256=config_sha256,
        output_schema_bytes=bytes(handoff.schema_snapshot.raw_bytes),
        output_schema_sha256=binding.output_schema_sha256,
        output_validator_version=binding.output_validator_version,
        sandbox_roots=roots,
        cwd=str(cwd),
        timeout_seconds=timeout,
    )
    started = time.monotonic()
    try:
        response = _invoke_child(process_boundary, handle, request)
    except CodexWorkerError as exc:
        primary = exc.code if exc.code in _CHILD_ERROR_CODES else "WORKER_PROVIDER_FAILED"
        _raise_open_failure(process_boundary, handle, primary)
    if time.monotonic() - started > timeout:
        _raise_open_failure(process_boundary, handle, "WORKER_TIMEOUT")
    try:
        status, _turn_id, _events, _candidate = _normalize_response(
            response,
            operation=operation,
            expected_thread_id=binding.thread_id,
        )
    except CodexWorkerError:
        _raise_open_failure(process_boundary, handle, "WORKER_PROVIDER_RESPONSE_INVALID")
    if status != "ready":
        _raise_open_failure(process_boundary, handle, "WORKER_PROVIDER_RESPONSE_INVALID")
    return CodexWorkerSession(
        handoff=handoff,
        binding=binding,
        authority_context=authority_context,
        worker_context=worker_context,
        process_boundary=process_boundary,
        environment_attestation=attestation,
        process_handle=handle,
    )


def start_codex_worker(
    *,
    handoff: ValidatedVisionHandoff,
    binding: BoundWorkerThread,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
    adapter: WorkerAdapter,
    process_boundary: WorkerProcessBoundary,
    timeout_seconds: float,
    now: datetime | None = None,
) -> CodexWorkerSession:
    return _open_codex_worker(
        operation="start",
        handoff=handoff,
        binding=binding,
        authority_context=authority_context,
        worker_context=worker_context,
        adapter=adapter,
        process_boundary=process_boundary,
        timeout_seconds=timeout_seconds,
        now=now,
    )


def resume_codex_worker(
    *,
    handoff: ValidatedVisionHandoff,
    binding: BoundWorkerThread,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
    adapter: WorkerAdapter,
    process_boundary: WorkerProcessBoundary,
    timeout_seconds: float,
    now: datetime | None = None,
) -> CodexWorkerSession:
    return _open_codex_worker(
        operation="resume",
        handoff=handoff,
        binding=binding,
        authority_context=authority_context,
        worker_context=worker_context,
        adapter=adapter,
        process_boundary=process_boundary,
        timeout_seconds=timeout_seconds,
        now=now,
    )


def fork_codex_worker(
    *,
    source_handoff: ValidatedVisionHandoff,
    source_binding: BoundWorkerThread,
    source_authority_context: ServerOwnedAuthorityContext,
    source_worker_context: ServerOwnedWorkerBindingContext,
    handoff: ValidatedVisionHandoff,
    binding: BoundWorkerThread,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
    adapter: WorkerAdapter,
    process_boundary: WorkerProcessBoundary,
    timeout_seconds: float,
    now: datetime | None = None,
) -> CodexWorkerSession:
    try:
        expected = fork_worker_thread(
            source_binding,
            handoff,
            source_handoff=source_handoff,
            source_authority_context=source_authority_context,
            source_worker_context=source_worker_context,
            authority_context=authority_context,
            worker_context=worker_context,
            thread_id=binding.thread_id,
            now=now,
        )
    except (VisionHandoffError, TypeError, ValueError, AttributeError):
        _fail("WORKER_AUTHORITY_MISMATCH")
    if expected != binding:
        _fail("WORKER_AUTHORITY_MISMATCH")
    return _open_codex_worker(
        operation="fork",
        handoff=handoff,
        binding=binding,
        authority_context=authority_context,
        worker_context=worker_context,
        adapter=adapter,
        process_boundary=process_boundary,
        timeout_seconds=timeout_seconds,
        now=now,
    )


__all__ = [
    "AdapterRequest",
    "CodexWorkerError",
    "CodexWorkerEvent",
    "CodexWorkerResult",
    "CodexWorkerSession",
    "LazyOfficialSdkAdapter",
    "Task3ProcessBoundary",
    "WorkerAdapter",
    "WorkerProcessBoundary",
    "fork_codex_worker",
    "resume_codex_worker",
    "run_codex_worker_child",
    "start_codex_worker",
]


if __name__ == "__main__":
    raise SystemExit(_child_main())
