"""Dependency-free sanitized Windows worker process boundary.

This module owns only local process isolation facts: a start-empty child
environment, disposable worker directories, Windows Job Object supervision,
and bounded descendant cleanup evidence. It does not import or invoke Codex,
provider/model/auth, AutoCAD, File IPC, approval, or persistence owners.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Protocol


MAX_CLEANUP_DEADLINE_SECONDS = 30.0
MAX_ACTIVE_PROCESSES = 64
_ALLOWED_INHERITED_ENVIRONMENT = (
    "COMSPEC",
    "PATH",
    "PATHEXT",
    "SystemRoot",
    "WINDIR",
)
_REQUIRED_WORKER_ENVIRONMENT = ("CODEX_HOME", "TEMP", "TMP")
_ALLOWED_WORKER_ENVIRONMENT = frozenset(
    (*_ALLOWED_INHERITED_ENVIRONMENT, *_REQUIRED_WORKER_ENVIRONMENT)
)

_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400

_CREATE_SUSPENDED = 0x00000004
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_CREATE_NO_WINDOW = 0x08000000
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
_JOB_OBJECT_BASIC_PROCESS_ID_LIST_CLASS = 3


class WorkerProcessError(RuntimeError):
    """Categorical worker-process failure with no raw private detail."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class WorkerEnvironmentAttestation:
    """Immutable prepared child environment and disposable path identity."""

    environment: Mapping[str, str]
    environment_keys: tuple[str, ...]
    environment_sha256: str
    disposable_root: Path
    cwd: Path
    codex_home: Path
    temp_dir: Path
    writable_roots: tuple[Path, ...]

    def __post_init__(self) -> None:
        frozen_environment = MappingProxyType(dict(self.environment))
        object.__setattr__(self, "environment", frozen_environment)
        object.__setattr__(self, "environment_keys", tuple(self.environment_keys))
        object.__setattr__(self, "writable_roots", tuple(self.writable_roots))


@dataclass(frozen=True)
class ProcessTreeIdentity:
    """Sanitized Job Object membership proof."""

    root_pid: int
    member_pids: tuple[int, ...]
    member_count: int
    verified: bool


@dataclass(frozen=True)
class WorkerCleanupResult:
    """Sanitized terminal cleanup evidence."""

    status: str
    success: bool
    promotion_safe: bool
    survivor_pids: tuple[int, ...]
    survivor_count: int
    error_code: str | None


@dataclass(frozen=True)
class _CreatedProcess:
    process_handle: object
    thread_handle: object
    pid: int


class _ProcessApi(Protocol):
    def create_job(self, max_processes: int) -> object: ...

    def configure_job(self, job_handle: object, max_processes: int) -> None: ...

    def create_suspended_process(
        self,
        *,
        executable: Path,
        argv: tuple[str, ...],
        cwd: Path,
        environment: Mapping[str, str],
    ) -> object: ...

    def assign_process(self, job_handle: object, process_handle: object) -> None: ...

    def resume_process(self, thread_handle: object) -> None: ...

    def query_job_process_ids(
        self, job_handle: object, *, max_processes: int
    ) -> tuple[int, ...]: ...

    def terminate_job(self, job_handle: object) -> None: ...

    def terminate_process(self, process_handle: object) -> None: ...

    def close_handle(self, handle: object) -> None: ...


class WorkerProcessHandle:
    """Opaque local worker process/job handles plus immutable public evidence."""

    __slots__ = (
        "_api",
        "_cleanup_deadline_seconds",
        "_cleanup_result",
        "_job_handle",
        "_max_processes",
        "_process_handle",
        "environment_attestation",
        "root_pid",
    )

    def __init__(
        self,
        *,
        api: _ProcessApi,
        job_handle: object,
        process_handle: object,
        root_pid: int,
        environment_attestation: WorkerEnvironmentAttestation,
        cleanup_deadline_seconds: float,
        max_processes: int,
    ) -> None:
        self._api = api
        self._job_handle = job_handle
        self._process_handle = process_handle
        self.root_pid = root_pid
        self.environment_attestation = environment_attestation
        self._cleanup_deadline_seconds = cleanup_deadline_seconds
        self._max_processes = max_processes
        self._cleanup_result: WorkerCleanupResult | None = None

    def snapshot_process_tree(self) -> ProcessTreeIdentity:
        """Return current Job membership or fail closed when evidence is invalid."""

        try:
            raw = self._api.query_job_process_ids(
                self._job_handle, max_processes=self._max_processes
            )
        except Exception:
            raise WorkerProcessError("WORKER_TREE_EVIDENCE_UNAVAILABLE") from None
        pids = _normalize_member_pids(raw, max_processes=self._max_processes)
        return ProcessTreeIdentity(
            root_pid=self.root_pid,
            member_pids=pids,
            member_count=len(pids),
            verified=True,
        )


def _fail(code: str) -> None:
    raise WorkerProcessError(code)


def _path_contains_windows_reparse_point(path: str | os.PathLike[str]) -> bool:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if os.name != "nt":
        return any(component.is_symlink() for component in (candidate, *candidate.parents))

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_attributes = kernel32.GetFileAttributesW
        get_attributes.argtypes = [wintypes.LPCWSTR]
        get_attributes.restype = wintypes.DWORD
    except (AttributeError, OSError):
        return True

    components = list(candidate.parts)
    if not components:
        return True
    current = Path(components[0])
    for component in components[1:]:
        current /= component
        attributes = get_attributes(str(current))
        if attributes != _INVALID_FILE_ATTRIBUTES and (
            attributes & _FILE_ATTRIBUTE_REPARSE_POINT
        ):
            return True
    attributes = get_attributes(str(current))
    return attributes != _INVALID_FILE_ATTRIBUTES and bool(
        attributes & _FILE_ATTRIBUTE_REPARSE_POINT
    )

def _canonical_existing_directory(
    value: Path,
    *,
    error_code: str,
    path_contains_reparse: Callable[[str | os.PathLike[str]], bool],
) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute() or not candidate.is_dir():
        _fail(error_code)
    if path_contains_reparse(candidate):
        _fail("WORKER_REPARSE_PATH")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        _fail(error_code)
    if path_contains_reparse(resolved):
        _fail("WORKER_REPARSE_PATH")
    return resolved


def _is_contained(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _reject_environment_nul(key: str, value: str) -> None:
    if "\x00" in key or "\x00" in value:
        _fail("WORKER_ENV_INVALID")


def _normalized_source_environment(source: Mapping[str, str]) -> dict[str, str]:
    normalized: dict[str, tuple[str, str]] = {}
    for key, value in source.items():
        if not isinstance(key, str) or not isinstance(value, str):
            _fail("WORKER_ENV_AMBIGUOUS")
        _reject_environment_nul(key, value)
        folded = key.casefold()
        if folded in normalized:
            _fail("WORKER_ENV_AMBIGUOUS")
        normalized[folded] = (key, value)
    return {folded: value for folded, (_name, value) in normalized.items()}


def _environment_digest(environment: Mapping[str, str]) -> str:
    payload = json.dumps(
        sorted(environment.items(), key=lambda item: item[0].casefold()),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def prepare_worker_environment(
    *,
    disposable_root: Path,
    cwd: Path,
    source_environment: Mapping[str, str] | None = None,
    _path_contains_reparse: Callable[
        [str | os.PathLike[str]], bool
    ] = _path_contains_windows_reparse_point,
) -> WorkerEnvironmentAttestation:
    """Prepare one immutable, start-empty worker environment under a safe root."""

    root = _canonical_existing_directory(
        Path(disposable_root),
        error_code="WORKER_DISPOSABLE_ROOT_UNSAFE",
        path_contains_reparse=_path_contains_reparse,
    )
    workdir = _canonical_existing_directory(
        Path(cwd),
        error_code="WORKER_CWD_UNSAFE",
        path_contains_reparse=_path_contains_reparse,
    )
    if not _is_contained(root, workdir):
        _fail("WORKER_CWD_UNSAFE")

    source = _normalized_source_environment(source_environment or os.environ)
    codex_home = root / "codex-home"
    temp_dir = root / "tmp"
    if codex_home.exists() or temp_dir.exists():
        _fail("WORKER_DISPOSABLE_STATE_UNSAFE")

    created: list[Path] = []
    try:
        codex_home.mkdir()
        created.append(codex_home)
        temp_dir.mkdir()
        created.append(temp_dir)
    except OSError:
        for path in reversed(created):
            try:
                path.rmdir()
            except OSError:
                pass
        _fail("WORKER_DISPOSABLE_STATE_UNSAFE")

    if _path_contains_reparse(codex_home) or _path_contains_reparse(temp_dir):
        _fail("WORKER_REPARSE_PATH")

    environment: dict[str, str] = {}
    for canonical_name in _ALLOWED_INHERITED_ENVIRONMENT:
        value = source.get(canonical_name.casefold())
        if value:
            environment[canonical_name] = value
    environment.update(
        {
            "CODEX_HOME": str(codex_home),
            "TEMP": str(temp_dir),
            "TMP": str(temp_dir),
        }
    )
    ordered = dict(sorted(environment.items(), key=lambda item: item[0].casefold()))
    return WorkerEnvironmentAttestation(
        environment=ordered,
        environment_keys=tuple(ordered),
        environment_sha256=_environment_digest(ordered),
        disposable_root=root,
        cwd=workdir,
        codex_home=codex_home,
        temp_dir=temp_dir,
        writable_roots=(workdir, codex_home, temp_dir),
    )


def _validate_limits(*, cleanup_deadline_seconds: float, max_processes: int) -> None:
    if (
        not isinstance(cleanup_deadline_seconds, (int, float))
        or isinstance(cleanup_deadline_seconds, bool)
        or not math.isfinite(float(cleanup_deadline_seconds))
        or cleanup_deadline_seconds <= 0
        or cleanup_deadline_seconds > MAX_CLEANUP_DEADLINE_SECONDS
    ):
        _fail("WORKER_LIMIT_INVALID")
    if (
        isinstance(max_processes, bool)
        or not isinstance(max_processes, int)
        or max_processes <= 0
        or max_processes > MAX_ACTIVE_PROCESSES
    ):
        _fail("WORKER_LIMIT_INVALID")


def _validate_attestation_filesystem(
    attestation: WorkerEnvironmentAttestation,
) -> None:
    for path in (
        attestation.disposable_root,
        attestation.cwd,
        attestation.codex_home,
        attestation.temp_dir,
    ):
        if not path.is_absolute() or not path.is_dir():
            _fail("WORKER_DISPOSABLE_STATE_UNSAFE")
        if _path_contains_windows_reparse_point(path):
            _fail("WORKER_REPARSE_PATH")
    if not _is_contained(attestation.disposable_root, attestation.cwd):
        _fail("WORKER_CWD_UNSAFE")
    if not _is_contained(attestation.disposable_root, attestation.codex_home):
        _fail("WORKER_DISPOSABLE_STATE_UNSAFE")
    if not _is_contained(attestation.disposable_root, attestation.temp_dir):
        _fail("WORKER_DISPOSABLE_STATE_UNSAFE")


def _validate_attestation_environment(
    attestation: WorkerEnvironmentAttestation,
) -> None:
    environment = attestation.environment
    keys = tuple(environment)
    if any(not isinstance(key, str) for key in keys):
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    expected_keys = tuple(sorted(keys, key=lambda name: name.casefold()))
    if keys != expected_keys or attestation.environment_keys != expected_keys:
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    if not set(_REQUIRED_WORKER_ENVIRONMENT).issubset(environment):
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    if any(key not in _ALLOWED_WORKER_ENVIRONMENT for key in keys):
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    if len({key.casefold() for key in keys}) != len(keys):
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    for key, value in environment.items():
        if not isinstance(value, str):
            _fail("WORKER_ENV_ATTESTATION_MISMATCH")
        _reject_environment_nul(key, value)
    if environment["CODEX_HOME"] != str(attestation.codex_home):
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    if environment["TEMP"] != str(attestation.temp_dir):
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    if environment["TMP"] != str(attestation.temp_dir):
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    if attestation.codex_home != attestation.disposable_root / "codex-home":
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    if attestation.temp_dir != attestation.disposable_root / "tmp":
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    if attestation.writable_roots != (
        attestation.cwd,
        attestation.codex_home,
        attestation.temp_dir,
    ):
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    if _environment_digest(environment) != attestation.environment_sha256:
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")


def _validate_executable(executable: Path) -> Path:
    candidate = Path(executable)
    if not candidate.is_absolute() or not candidate.is_file():
        _fail("WORKER_EXECUTABLE_UNSAFE")
    if _path_contains_windows_reparse_point(candidate):
        _fail("WORKER_EXECUTABLE_UNSAFE")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        _fail("WORKER_EXECUTABLE_UNSAFE")
    if _path_contains_windows_reparse_point(resolved):
        _fail("WORKER_EXECUTABLE_UNSAFE")
    return resolved


def _validate_argv(argv: Sequence[str]) -> tuple[str, ...]:
    if isinstance(argv, (str, bytes)):
        _fail("WORKER_ARGUMENTS_INVALID")
    result: list[str] = []
    for item in argv:
        if not isinstance(item, str) or "\x00" in item:
            _fail("WORKER_ARGUMENTS_INVALID")
        result.append(item)
    return tuple(result)


def _safe_close(api: _ProcessApi, handle: object | None) -> bool:
    if handle is None:
        return True
    try:
        api.close_handle(handle)
        return True
    except Exception:
        return False


def _safe_terminate_process(api: _ProcessApi, process_handle: object | None) -> None:
    if process_handle is None:
        return
    try:
        api.terminate_process(process_handle)
    except Exception:
        pass


def _safe_terminate_job(api: _ProcessApi, job_handle: object | None) -> None:
    if job_handle is None:
        return
    try:
        api.terminate_job(job_handle)
    except Exception:
        pass


def launch_worker_process(
    *,
    environment: WorkerEnvironmentAttestation,
    executable: Path,
    argv: Sequence[str],
    cleanup_deadline_seconds: float,
    max_processes: int,
    _process_api: _ProcessApi | None = None,
) -> WorkerProcessHandle:
    """Launch suspended, assign to a kill-on-close Job, then resume."""

    if not isinstance(environment, WorkerEnvironmentAttestation):
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    _validate_limits(
        cleanup_deadline_seconds=cleanup_deadline_seconds,
        max_processes=max_processes,
    )
    _validate_attestation_filesystem(environment)
    _validate_attestation_environment(environment)
    runtime = _validate_executable(Path(executable))
    arguments = _validate_argv(argv)
    api: _ProcessApi = _process_api or _CtypesWindowsProcessApi()

    job_handle: object | None = None
    process_handle: object | None = None
    thread_handle: object | None = None
    try:
        try:
            job_handle = api.create_job(max_processes)
        except Exception:
            _fail("WORKER_JOB_CREATE_FAILED")
        try:
            api.configure_job(job_handle, max_processes)
        except Exception:
            _fail("WORKER_JOB_CONFIG_FAILED")
        try:
            created = api.create_suspended_process(
                executable=runtime,
                argv=arguments,
                cwd=environment.cwd,
                environment=environment.environment,
            )
            process_handle = created.process_handle
            thread_handle = created.thread_handle
            root_pid = created.pid
            if isinstance(root_pid, bool) or not isinstance(root_pid, int) or root_pid <= 0:
                _fail("WORKER_LAUNCH_FAILED")
        except WorkerProcessError:
            raise
        except Exception:
            _fail("WORKER_LAUNCH_FAILED")
        try:
            api.assign_process(job_handle, process_handle)
        except Exception:
            _safe_terminate_process(api, process_handle)
            _fail("WORKER_JOB_ASSIGN_FAILED")
        try:
            api.resume_process(thread_handle)
        except Exception:
            _safe_terminate_job(api, job_handle)
            _fail("WORKER_RESUME_FAILED")
        if not _safe_close(api, thread_handle):
            _safe_terminate_job(api, job_handle)
            _fail("WORKER_LAUNCH_RESOURCE_CLOSE_FAILED")
        thread_handle = None
        return WorkerProcessHandle(
            api=api,
            job_handle=job_handle,
            process_handle=process_handle,
            root_pid=root_pid,
            environment_attestation=environment,
            cleanup_deadline_seconds=float(cleanup_deadline_seconds),
            max_processes=max_processes,
        )
    except WorkerProcessError:
        _safe_close(api, thread_handle)
        _safe_close(api, process_handle)
        _safe_close(api, job_handle)
        raise


def _normalize_member_pids(
    value: object, *, max_processes: int
) -> tuple[int, ...]:
    if not isinstance(value, tuple):
        _fail("WORKER_TREE_EVIDENCE_UNAVAILABLE")
    pids: list[int] = []
    for pid in value:
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            _fail("WORKER_TREE_EVIDENCE_UNAVAILABLE")
        pids.append(pid)
    normalized = tuple(sorted(set(pids)))
    if len(normalized) != len(pids) or len(normalized) > max_processes:
        _fail("WORKER_TREE_EVIDENCE_UNAVAILABLE")
    return normalized


def _cleanup_failure(
    *,
    code: str,
    survivors: tuple[int, ...] = (),
) -> WorkerCleanupResult:
    return WorkerCleanupResult(
        status="CLEANUP_FAILED",
        success=False,
        promotion_safe=False,
        survivor_pids=survivors,
        survivor_count=len(survivors),
        error_code=code,
    )


def _close_cleanup_handles(handle: WorkerProcessHandle) -> bool:
    okay = True
    if handle._process_handle is not None:
        okay = _safe_close(handle._api, handle._process_handle) and okay
        handle._process_handle = None
    if handle._job_handle is not None:
        okay = _safe_close(handle._api, handle._job_handle) and okay
        handle._job_handle = None
    return okay


def cleanup_worker_process(
    handle: WorkerProcessHandle,
    *,
    _clock: Callable[[], float] = time.monotonic,
    _sleep: Callable[[float], None] = time.sleep,
) -> WorkerCleanupResult:
    """Terminate the Job and prove zero survivors within the bounded deadline."""

    if not isinstance(handle, WorkerProcessHandle):
        _fail("WORKER_HANDLE_INVALID")
    if handle._cleanup_result is not None:
        return handle._cleanup_result

    try:
        before = handle.snapshot_process_tree()
    except WorkerProcessError:
        _safe_terminate_job(handle._api, handle._job_handle)
        _close_cleanup_handles(handle)
        result = _cleanup_failure(code="WORKER_TREE_EVIDENCE_UNAVAILABLE")
        handle._cleanup_result = result
        return result

    try:
        handle._api.terminate_job(handle._job_handle)
    except Exception:
        survivors = before.member_pids
        _close_cleanup_handles(handle)
        result = _cleanup_failure(
            code="WORKER_CLEANUP_TERMINATE_FAILED",
            survivors=survivors,
        )
        handle._cleanup_result = result
        return result

    deadline = _clock() + handle._cleanup_deadline_seconds
    survivors = before.member_pids
    while True:
        try:
            current = handle.snapshot_process_tree()
        except WorkerProcessError:
            _close_cleanup_handles(handle)
            result = _cleanup_failure(code="WORKER_TREE_EVIDENCE_UNAVAILABLE")
            handle._cleanup_result = result
            return result
        survivors = current.member_pids
        if not survivors:
            break
        if _clock() >= deadline:
            _close_cleanup_handles(handle)
            result = _cleanup_failure(
                code="WORKER_CLEANUP_SURVIVORS",
                survivors=survivors,
            )
            handle._cleanup_result = result
            return result
        _sleep(0.01)

    if not _close_cleanup_handles(handle):
        result = _cleanup_failure(code="WORKER_CLEANUP_RESOURCE_CLOSE_FAILED")
        handle._cleanup_result = result
        return result
    result = WorkerCleanupResult(
        status="CLEANUP_SUCCEEDED",
        success=True,
        promotion_safe=True,
        survivor_pids=(),
        survivor_count=0,
        error_code=None,
    )
    handle._cleanup_result = result
    return result


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _CtypesWindowsProcessApi:
    """Small Win32 Job Object/CreateProcess adapter for the supported runtime."""

    def __init__(self) -> None:
        if os.name != "nt":
            _fail("WORKER_UNSUPPORTED_PLATFORM")
        try:
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        except (AttributeError, OSError):
            _fail("WORKER_UNSUPPORTED_PLATFORM")
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        k32 = self._kernel32
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.POINTER(_STARTUPINFOW),
            ctypes.POINTER(_PROCESS_INFORMATION),
        ]
        k32.CreateProcessW.restype = wintypes.BOOL
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k32.AssignProcessToJobObject.restype = wintypes.BOOL
        k32.ResumeThread.argtypes = [wintypes.HANDLE]
        k32.ResumeThread.restype = wintypes.DWORD
        k32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        k32.QueryInformationJobObject.restype = wintypes.BOOL
        k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k32.TerminateJobObject.restype = wintypes.BOOL
        k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k32.TerminateProcess.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.restype = wintypes.BOOL

    def create_job(self, max_processes: int) -> object:
        handle = self._kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise OSError
        return handle

    def configure_job(self, job_handle: object, max_processes: int) -> None:
        information = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        information.BasicLimitInformation.LimitFlags = (
            _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        )
        information.BasicLimitInformation.ActiveProcessLimit = max_processes
        if not self._kernel32.SetInformationJobObject(
            job_handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            raise OSError

    def create_suspended_process(
        self,
        *,
        executable: Path,
        argv: tuple[str, ...],
        cwd: Path,
        environment: Mapping[str, str],
    ) -> _CreatedProcess:
        startup = _STARTUPINFOW()
        startup.cb = ctypes.sizeof(startup)
        process = _PROCESS_INFORMATION()
        command_line = ctypes.create_unicode_buffer(
            subprocess.list2cmdline([str(executable), *argv])
        )
        environment_block = "\0".join(
            f"{key}={value}"
            for key, value in sorted(
                environment.items(), key=lambda item: item[0].casefold()
            )
        ) + "\0\0"
        environment_buffer = ctypes.create_unicode_buffer(environment_block)
        flags = _CREATE_SUSPENDED | _CREATE_UNICODE_ENVIRONMENT | _CREATE_NO_WINDOW
        if not self._kernel32.CreateProcessW(
            str(executable),
            command_line,
            None,
            None,
            False,
            flags,
            ctypes.cast(environment_buffer, ctypes.c_void_p),
            str(cwd),
            ctypes.byref(startup),
            ctypes.byref(process),
        ):
            raise OSError
        return _CreatedProcess(
            process_handle=process.hProcess,
            thread_handle=process.hThread,
            pid=int(process.dwProcessId),
        )

    def assign_process(self, job_handle: object, process_handle: object) -> None:
        if not self._kernel32.AssignProcessToJobObject(job_handle, process_handle):
            raise OSError

    def resume_process(self, thread_handle: object) -> None:
        result = self._kernel32.ResumeThread(thread_handle)
        if result == 0xFFFFFFFF:
            raise OSError

    def query_job_process_ids(
        self, job_handle: object, *, max_processes: int
    ) -> tuple[int, ...]:
        class _PROCESS_ID_LIST(ctypes.Structure):
            _fields_ = [
                ("NumberOfAssignedProcesses", wintypes.DWORD),
                ("NumberOfProcessIdsInList", wintypes.DWORD),
                ("ProcessIdList", ctypes.c_size_t * max_processes),
            ]

        payload = _PROCESS_ID_LIST()
        returned = wintypes.DWORD()
        if not self._kernel32.QueryInformationJobObject(
            job_handle,
            _JOB_OBJECT_BASIC_PROCESS_ID_LIST_CLASS,
            ctypes.byref(payload),
            ctypes.sizeof(payload),
            ctypes.byref(returned),
        ):
            raise OSError
        assigned = int(payload.NumberOfAssignedProcesses)
        listed = int(payload.NumberOfProcessIdsInList)
        if assigned != listed or listed > max_processes:
            raise OSError
        return tuple(int(payload.ProcessIdList[index]) for index in range(listed))

    def terminate_job(self, job_handle: object) -> None:
        if not self._kernel32.TerminateJobObject(job_handle, 1):
            raise OSError

    def terminate_process(self, process_handle: object) -> None:
        if not self._kernel32.TerminateProcess(process_handle, 1):
            raise OSError

    def close_handle(self, handle: object) -> None:
        if not self._kernel32.CloseHandle(handle):
            raise OSError


__all__ = [
    "ProcessTreeIdentity",
    "WorkerCleanupResult",
    "WorkerEnvironmentAttestation",
    "WorkerProcessError",
    "WorkerProcessHandle",
    "cleanup_worker_process",
    "launch_worker_process",
    "prepare_worker_environment",
]