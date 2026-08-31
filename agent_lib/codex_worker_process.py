"""Dependency-free sanitized Windows worker process boundary.

This module owns local process isolation facts: a start-empty child environment,
disposable worker directories, Windows Job Object supervision, a narrow
handle-bound child control channel, and bounded descendant cleanup evidence.
It does not import or invoke Codex, provider/model/auth, AutoCAD, File IPC,
approval, or persistence owners.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import time
import weakref
from collections.abc import Callable, Mapping, Sequence
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import BinaryIO, Protocol


MAX_CLEANUP_DEADLINE_SECONDS = 30.0
MAX_ACTIVE_PROCESSES = 64
MAX_CONTROL_FRAME_BYTES = 1_048_576
_CONTROL_FRAME_VERSION = 1
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
_AUTHENTICATED_STATE = "HUMAN_AUTHENTICATED_ATTESTED"
_SUPPORTED_AUTH_MODE = "chatgpt"
_AUTH_ENTRY_MANIFEST_VERSION = "worker-auth-entry-manifest-1"
_AUTH_FILE_NAME = "auth.json"
_BLOCKED_AUTH_BASENAMES = frozenset(
    {
        "agents.md",
        "config.toml",
        "instructions.md",
        "prompt.md",
    }
)
_CREATE_SUSPENDED = 0x00000004
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_CREATE_NO_WINDOW = 0x08000000
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_STARTF_USESTDHANDLES = 0x00000100
PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
_HANDLE_FLAG_INHERIT = 0x00000001
_GENERIC_WRITE = 0x40000000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_PIPE_NOWAIT = 0x00000001
_ERROR_PIPE_BUSY = 231
_ERROR_NO_DATA = 232
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
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))
        object.__setattr__(self, "environment_keys", tuple(self.environment_keys))
        object.__setattr__(self, "writable_roots", tuple(self.writable_roots))


@dataclass(frozen=True)
class WorkerAuthFileObservation:
    """Privacy-safe authenticated-home entry metadata; never file contents."""

    relative_path: str
    entry_type: str
    byte_count: int
    sha256: str | None


@dataclass(frozen=True)
class WorkerAuthenticationAttestation:
    """One-shot server-owned proof for an authenticated disposable home."""

    environment: WorkerEnvironmentAttestation
    executable: Path
    executable_sha256: str
    executable_version: str
    auth_mode: str
    home_manifest_sha256: str
    home_entries: tuple[WorkerAuthFileObservation, ...]
    state: str = _AUTHENTICATED_STATE

    def __post_init__(self) -> None:
        object.__setattr__(self, "home_entries", tuple(self.home_entries))


@dataclass(frozen=True)
class WorkerAuthPurgeResult:
    """Sanitized proof that an authenticated home no longer retains state."""

    status: str
    success: bool
    deleted_file_count: int
    deleted_bytes: int
    survivor_count: int
    error_code: str | None


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
    auth_state_purged: bool = False


@dataclass(frozen=True)
class _CreatedProcess:
    process_handle: object
    thread_handle: object
    pid: int
    control_read_handle: object | None = None
    control_write_handle: object | None = None


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
        "_authentication_custody",
        "_cleanup_deadline_seconds",
        "_cleanup_result",
        "_control_read_handle",
        "_control_write_handle",
        "_job_handle",
        "_max_processes",
        "_process_handle",
        "_request_id",
        "environment_attestation",
        "root_pid",
        "__weakref__",
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
        authentication_custody: WorkerAuthenticationAttestation | None = None,
        control_read_handle: object | None = None,
        control_write_handle: object | None = None,
    ) -> None:
        self._api = api
        self._authentication_custody = authentication_custody
        self._job_handle = job_handle
        self._process_handle = process_handle
        self.root_pid = root_pid
        self.environment_attestation = environment_attestation
        self._cleanup_deadline_seconds = cleanup_deadline_seconds
        self._max_processes = max_processes
        self._cleanup_result: WorkerCleanupResult | None = None
        self._control_read_handle = control_read_handle
        self._control_write_handle = control_write_handle
        self._request_id = 0

    def snapshot_process_tree(self) -> ProcessTreeIdentity:
        _require_issued_handle(self)
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


_ISSUED_WORKER_HANDLES: dict[
    int, weakref.ReferenceType[WorkerProcessHandle]
] = {}


@dataclass
class _AuthenticationCustodyState:
    reference: weakref.ReferenceType[WorkerAuthenticationAttestation]
    consumed: bool = False
    purged: bool = False
    purge_result: WorkerAuthPurgeResult | None = None


_ISSUED_ENVIRONMENTS: dict[
    int, weakref.ReferenceType[WorkerEnvironmentAttestation]
] = {}
_ISSUED_AUTHENTICATIONS: dict[int, _AuthenticationCustodyState] = {}


def _fail(code: str) -> None:
    raise WorkerProcessError(code)


def _register_issued_handle(handle: WorkerProcessHandle) -> None:
    handle_id = id(handle)

    def discard(expired_ref: weakref.ReferenceType[WorkerProcessHandle]) -> None:
        current = _ISSUED_WORKER_HANDLES.get(handle_id)
        if current is expired_ref:
            _ISSUED_WORKER_HANDLES.pop(handle_id, None)

    _ISSUED_WORKER_HANDLES[handle_id] = weakref.ref(handle, discard)


def _register_issued_environment(environment: WorkerEnvironmentAttestation) -> None:
    environment_id = id(environment)

    def discard(expired_ref: weakref.ReferenceType[WorkerEnvironmentAttestation]) -> None:
        current = _ISSUED_ENVIRONMENTS.get(environment_id)
        if current is expired_ref:
            _ISSUED_ENVIRONMENTS.pop(environment_id, None)

    _ISSUED_ENVIRONMENTS[environment_id] = weakref.ref(environment, discard)


def _require_issued_environment(environment: object) -> WorkerEnvironmentAttestation:
    if type(environment) is not WorkerEnvironmentAttestation:
        _fail("WORKER_AUTH_STATE_UNSAFE")
    reference = _ISSUED_ENVIRONMENTS.get(id(environment))
    if reference is None or reference() is not environment:
        _fail("WORKER_AUTH_STATE_UNSAFE")
    return environment


def _register_authentication_attestation(
    attestation: WorkerAuthenticationAttestation,
) -> None:
    _ISSUED_AUTHENTICATIONS[id(attestation)] = _AuthenticationCustodyState(
        reference=weakref.ref(attestation)
    )


def _require_authentication_attestation(
    attestation: object,
) -> _AuthenticationCustodyState:
    if type(attestation) is not WorkerAuthenticationAttestation:
        _fail("WORKER_AUTH_STATE_UNSAFE")
    state = _ISSUED_AUTHENTICATIONS.get(id(attestation))
    if state is None or state.reference() is not attestation:
        _fail("WORKER_AUTH_STATE_UNSAFE")
    return state


def _require_issued_handle(handle: object) -> WorkerProcessHandle:
    if not isinstance(handle, WorkerProcessHandle):
        _fail("WORKER_HANDLE_INVALID")
    reference = _ISSUED_WORKER_HANDLES.get(id(handle))
    if reference is None or reference() is not handle:
        _fail("WORKER_HANDLE_INVALID")
    return handle


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


def _canonical_launch_boundary(
    *, expected_disposable_root: Path, expected_cwd: Path
) -> tuple[Path, Path]:
    root = _canonical_existing_directory(
        Path(expected_disposable_root),
        error_code="WORKER_DISPOSABLE_ROOT_UNSAFE",
        path_contains_reparse=_path_contains_windows_reparse_point,
    )
    workdir = _canonical_existing_directory(
        Path(expected_cwd),
        error_code="WORKER_CWD_UNSAFE",
        path_contains_reparse=_path_contains_windows_reparse_point,
    )
    if not _is_contained(root, workdir):
        _fail("WORKER_CWD_UNSAFE")
    return root, workdir


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
        {"CODEX_HOME": str(codex_home), "TEMP": str(temp_dir), "TMP": str(temp_dir)}
    )
    ordered = dict(sorted(environment.items(), key=lambda item: item[0].casefold()))
    attestation = WorkerEnvironmentAttestation(
        environment=ordered,
        environment_keys=tuple(ordered),
        environment_sha256=_environment_digest(ordered),
        disposable_root=root,
        cwd=workdir,
        codex_home=codex_home,
        temp_dir=temp_dir,
        writable_roots=(workdir, codex_home, temp_dir),
    )
    _register_issued_environment(attestation)
    return attestation


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
    *,
    expected_disposable_root: Path,
    expected_cwd: Path,
    require_empty: bool = True,
) -> Path:
    approved_root, approved_cwd = _canonical_launch_boundary(
        expected_disposable_root=expected_disposable_root,
        expected_cwd=expected_cwd,
    )
    attested_root = _canonical_existing_directory(
        Path(attestation.disposable_root),
        error_code="WORKER_DISPOSABLE_ROOT_UNSAFE",
        path_contains_reparse=_path_contains_windows_reparse_point,
    )
    attested_cwd = _canonical_existing_directory(
        Path(attestation.cwd),
        error_code="WORKER_CWD_UNSAFE",
        path_contains_reparse=_path_contains_windows_reparse_point,
    )
    attested_codex_home = _canonical_existing_directory(
        Path(attestation.codex_home),
        error_code="WORKER_DISPOSABLE_STATE_UNSAFE",
        path_contains_reparse=_path_contains_windows_reparse_point,
    )
    attested_temp = _canonical_existing_directory(
        Path(attestation.temp_dir),
        error_code="WORKER_DISPOSABLE_STATE_UNSAFE",
        path_contains_reparse=_path_contains_windows_reparse_point,
    )
    if Path(attestation.disposable_root) != attested_root or attested_root != approved_root:
        _fail("WORKER_DISPOSABLE_ROOT_UNSAFE")
    if Path(attestation.cwd) != attested_cwd or attested_cwd != approved_cwd:
        _fail("WORKER_CWD_UNSAFE")
    if (
        Path(attestation.codex_home) != attested_codex_home
        or attested_codex_home != approved_root / "codex-home"
    ):
        _fail("WORKER_DISPOSABLE_STATE_UNSAFE")
    if (
        Path(attestation.temp_dir) != attested_temp
        or attested_temp != approved_root / "tmp"
    ):
        _fail("WORKER_DISPOSABLE_STATE_UNSAFE")
    if not _is_contained(approved_root, attested_cwd):
        _fail("WORKER_CWD_UNSAFE")
    if not _is_contained(approved_root, attested_codex_home):
        _fail("WORKER_DISPOSABLE_STATE_UNSAFE")
    if not _is_contained(approved_root, attested_temp):
        _fail("WORKER_DISPOSABLE_STATE_UNSAFE")
    if require_empty:
        try:
            if any(attested_codex_home.iterdir()) or any(attested_temp.iterdir()):
                _fail("WORKER_DISPOSABLE_STATE_UNSAFE")
        except OSError:
            _fail("WORKER_DISPOSABLE_STATE_UNSAFE")
    return attested_cwd


def _validate_attestation_environment(attestation: WorkerEnvironmentAttestation) -> None:
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except (OSError, ValueError):
        _fail("WORKER_AUTH_STATE_UNSAFE")
    return digest.hexdigest()


def _auth_manifest(entries: Sequence[WorkerAuthFileObservation]) -> str:
    payload = {
        "version": _AUTH_ENTRY_MANIFEST_VERSION,
        "entries": [
            {
                "relative_path": entry.relative_path,
                "entry_type": entry.entry_type,
                "byte_count": entry.byte_count,
                "sha256": entry.sha256,
            }
            for entry in entries
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _auth_inventory(
    codex_home: Path,
) -> tuple[tuple[WorkerAuthFileObservation, ...], str]:
    if not codex_home.is_dir() or _path_contains_windows_reparse_point(codex_home):
        _fail("WORKER_AUTH_STATE_UNSAFE")
    entries: list[WorkerAuthFileObservation] = []

    def on_error(_error: OSError) -> None:
        _fail("WORKER_AUTH_STATE_UNSAFE")

    try:
        for current, directories, files in os.walk(
            codex_home, topdown=True, followlinks=False, onerror=on_error
        ):
            current_path = Path(current)
            for name in (*directories, *files):
                path = current_path / name
                relative = path.relative_to(codex_home).as_posix()
                if path.is_symlink() or _path_contains_windows_reparse_point(path):
                    _fail("WORKER_AUTH_STATE_UNSAFE")
                if path.is_dir():
                    entries.append(
                        WorkerAuthFileObservation(
                            relative_path=relative,
                            entry_type="dir",
                            byte_count=0,
                            sha256=None,
                        )
                    )
                elif path.is_file():
                    size = path.stat().st_size
                    entries.append(
                        WorkerAuthFileObservation(
                            relative_path=relative,
                            entry_type="file",
                            byte_count=size,
                            sha256=_sha256_file(path),
                        )
                    )
                else:
                    _fail("WORKER_AUTH_STATE_UNSAFE")
    except (OSError, RuntimeError, ValueError):
        _fail("WORKER_AUTH_STATE_UNSAFE")
    ordered = tuple(sorted(entries, key=lambda entry: entry.relative_path.casefold()))
    return ordered, _auth_manifest(ordered)


def _validate_auth_entry_policy(
    entries: Sequence[WorkerAuthFileObservation],
) -> None:
    auth_file_seen = False
    for entry in entries:
        parts = tuple(part.casefold() for part in entry.relative_path.split("/"))
        basename = parts[-1] if parts else ""
        if (
            basename in _BLOCKED_AUTH_BASENAMES
            or (basename.startswith("agents") and basename.endswith(".md"))
            or "instruction" in basename
            or "prompt" in basename
            or basename.startswith(".env")
            or any(
                "mcp" in part or "plugin" in part or "marketplace" in part
                for part in parts
            )
        ):
            _fail("WORKER_AUTH_AMBIENT_STATE")
        if parts == (_AUTH_FILE_NAME,):
            if entry.entry_type != "file":
                _fail("WORKER_AUTH_STATE_UNSAFE")
            auth_file_seen = True
        elif not parts or parts[0] not in {"log", "tmp"}:
            _fail("WORKER_AUTH_AMBIENT_STATE")
    if not auth_file_seen:
        _fail("WORKER_AUTH_NOT_AUTHENTICATED")


def _command_output(result: object) -> tuple[int, str]:
    return_code = getattr(result, "returncode", None)
    stdout = getattr(result, "stdout", "")
    stderr = getattr(result, "stderr", "")
    if (
        isinstance(return_code, bool)
        or not isinstance(return_code, int)
        or not isinstance(stdout, str)
        or not isinstance(stderr, str)
    ):
        _fail("WORKER_AUTH_COMMAND_FAILED")
    return return_code, f"{stdout}\n{stderr}"


def attest_authenticated_worker_environment(
    *,
    environment: WorkerEnvironmentAttestation,
    executable: Path,
    expected_executable_sha256: str,
    expected_executable_version: str,
    _command_runner: Callable[..., object],
) -> WorkerAuthenticationAttestation:
    """Observe official login state and bind it to one issued disposable home."""

    _require_issued_environment(environment)
    _validate_attestation_filesystem(
        environment,
        expected_disposable_root=environment.disposable_root,
        expected_cwd=environment.cwd,
        require_empty=False,
    )
    _validate_attestation_environment(environment)
    runtime = _validate_executable(executable)
    if (
        not isinstance(expected_executable_sha256, str)
        or len(expected_executable_sha256) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in expected_executable_sha256)
    ):
        _fail("WORKER_EXECUTABLE_UNSAFE")
    if _sha256_file(runtime).casefold() != expected_executable_sha256.casefold():
        _fail("WORKER_EXECUTABLE_IDENTITY_MISMATCH")
    if (
        not isinstance(expected_executable_version, str)
        or not expected_executable_version.strip()
        or "\n" in expected_executable_version
        or "\r" in expected_executable_version
    ):
        _fail("WORKER_EXECUTABLE_VERSION_MISMATCH")
    try:
        version_result = _command_runner(
            (str(runtime), "--version"),
            cwd=environment.cwd,
            environment=environment.environment,
        )
        version_code, version_output = _command_output(version_result)
        status_result = _command_runner(
            (str(runtime), "login", "status"),
            cwd=environment.cwd,
            environment=environment.environment,
        )
        status_code, status_output = _command_output(status_result)
    except WorkerProcessError:
        raise
    except Exception:
        _fail("WORKER_AUTH_COMMAND_FAILED")
    if version_code != 0 or expected_executable_version.strip() not in version_output.splitlines():
        _fail("WORKER_EXECUTABLE_VERSION_MISMATCH")
    if status_code != 0 or "logged in using chatgpt" not in status_output.casefold():
        _fail("WORKER_NOT_AUTHENTICATED")
    entries, manifest = _auth_inventory(environment.codex_home)
    _validate_auth_entry_policy(entries)
    attestation = WorkerAuthenticationAttestation(
        environment=environment,
        executable=runtime,
        executable_sha256=expected_executable_sha256.casefold(),
        executable_version=expected_executable_version.strip(),
        auth_mode=_SUPPORTED_AUTH_MODE,
        home_manifest_sha256=manifest,
        home_entries=entries,
    )
    _register_authentication_attestation(attestation)
    return attestation


def _validate_authenticated_custody(
    custody: WorkerAuthenticationAttestation,
    *,
    expected_disposable_root: Path,
    expected_cwd: Path,
    executable: Path,
) -> tuple[Path, _AuthenticationCustodyState]:
    state = _require_authentication_attestation(custody)
    if state.consumed or state.purged or custody.state != _AUTHENTICATED_STATE:
        _fail("WORKER_AUTH_STATE_REUSE")
    environment = custody.environment
    _require_issued_environment(environment)
    workdir = _validate_attestation_filesystem(
        environment,
        expected_disposable_root=expected_disposable_root,
        expected_cwd=expected_cwd,
        require_empty=False,
    )
    _validate_attestation_environment(environment)
    runtime = _validate_executable(executable)
    if runtime != custody.executable:
        _fail("WORKER_EXECUTABLE_IDENTITY_MISMATCH")
    if _sha256_file(runtime).casefold() != custody.executable_sha256.casefold():
        _fail("WORKER_EXECUTABLE_IDENTITY_MISMATCH")
    entries, manifest = _auth_inventory(environment.codex_home)
    _validate_auth_entry_policy(entries)
    if manifest != custody.home_manifest_sha256 or entries != custody.home_entries:
        _fail("WORKER_AUTH_STATE_DRIFT")
    return workdir, state


def purge_worker_authentication_state(
    attestation: WorkerAuthenticationAttestation,
) -> WorkerAuthPurgeResult:
    """Delete only the exact issued authenticated-home contents, once."""

    state = _require_authentication_attestation(attestation)
    environment = attestation.environment
    if state.purged and state.purge_result is not None:
        try:
            if any(environment.codex_home.iterdir()):
                _fail("WORKER_AUTH_STATE_DRIFT")
        except WorkerProcessError:
            raise
        except (OSError, RuntimeError):
            _fail("WORKER_AUTH_STATE_DRIFT")
        return state.purge_result
    _require_issued_environment(environment)
    _validate_attestation_filesystem(
        environment,
        expected_disposable_root=environment.disposable_root,
        expected_cwd=environment.cwd,
        require_empty=False,
    )
    entries, _manifest = _auth_inventory(environment.codex_home)
    deleted_files = 0
    deleted_bytes = 0
    try:
        for entry in sorted(entries, key=lambda item: item.relative_path.count("/"), reverse=True):
            path = environment.codex_home / Path(entry.relative_path)
            if entry.entry_type == "file":
                deleted_bytes += entry.byte_count
                path.unlink()
                deleted_files += 1
            elif entry.entry_type == "dir":
                path.rmdir()
            else:
                _fail("WORKER_AUTH_STATE_UNSAFE")
        if any(environment.codex_home.iterdir()):
            _fail("WORKER_AUTH_STATE_PURGE_FAILED")
    except WorkerProcessError:
        raise
    except (OSError, RuntimeError, ValueError):
        _fail("WORKER_AUTH_STATE_PURGE_FAILED")
    result = WorkerAuthPurgeResult(
        status="AUTH_STATE_PURGED",
        success=True,
        deleted_file_count=deleted_files,
        deleted_bytes=deleted_bytes,
        survivor_count=0,
        error_code=None,
    )
    state.purged = True
    state.purge_result = result
    return result


def _safe_close(api: _ProcessApi, handle: object | None) -> bool:
    if handle is None:
        return True
    try:
        api.close_handle(handle)
        return True
    except Exception:
        return False


def _safe_terminate_process(api: _ProcessApi, process_handle: object | None) -> None:
    if process_handle is not None:
        try:
            api.terminate_process(process_handle)
        except Exception:
            pass


def _safe_terminate_job(api: _ProcessApi, job_handle: object | None) -> None:
    if job_handle is not None:
        try:
            api.terminate_job(job_handle)
        except Exception:
            pass


def _launch_worker_process(
    *,
    environment: WorkerEnvironmentAttestation,
    expected_disposable_root: Path,
    expected_cwd: Path,
    executable: Path,
    argv: Sequence[str],
    cleanup_deadline_seconds: float,
    max_processes: int,
    custody: WorkerAuthenticationAttestation | None,
    control_channel: bool = False,
    _process_api: _ProcessApi | None = None,
) -> WorkerProcessHandle:
    if not isinstance(environment, WorkerEnvironmentAttestation):
        _fail("WORKER_ENV_ATTESTATION_MISMATCH")
    if not isinstance(control_channel, bool):
        _fail("WORKER_ARGUMENTS_INVALID")
    _validate_limits(
        cleanup_deadline_seconds=cleanup_deadline_seconds, max_processes=max_processes
    )
    workdir = _validate_attestation_filesystem(
        environment,
        expected_disposable_root=expected_disposable_root,
        expected_cwd=expected_cwd,
        require_empty=custody is None,
    )
    _validate_attestation_environment(environment)
    runtime = _validate_executable(Path(executable))
    arguments = _validate_argv(argv)
    api: _ProcessApi = _process_api or _CtypesWindowsProcessApi()
    job_handle = process_handle = thread_handle = None
    control_read_handle = control_write_handle = None
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
            if control_channel:
                create_controlled = getattr(api, "create_suspended_process_with_control", None)
                if not callable(create_controlled):
                    _fail("WORKER_CONTROL_UNAVAILABLE")
                created = create_controlled(
                    executable=runtime,
                    argv=arguments,
                    cwd=workdir,
                    environment=environment.environment,
                )
            else:
                created = api.create_suspended_process(
                    executable=runtime,
                    argv=arguments,
                    cwd=workdir,
                    environment=environment.environment,
                )
            process_handle = created.process_handle
            thread_handle = created.thread_handle
            control_read_handle = getattr(created, "control_read_handle", None)
            control_write_handle = getattr(created, "control_write_handle", None)
            root_pid = created.pid
            if isinstance(root_pid, bool) or not isinstance(root_pid, int) or root_pid <= 0:
                _fail("WORKER_LAUNCH_FAILED")
            if control_channel and (
                control_read_handle is None or control_write_handle is None
            ):
                _fail("WORKER_CONTROL_UNAVAILABLE")
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
        handle = WorkerProcessHandle(
            api=api,
            job_handle=job_handle,
            process_handle=process_handle,
            root_pid=root_pid,
            environment_attestation=environment,
            cleanup_deadline_seconds=float(cleanup_deadline_seconds),
            max_processes=max_processes,
            authentication_custody=custody,
            control_read_handle=control_read_handle,
            control_write_handle=control_write_handle,
        )
        _register_issued_handle(handle)
        return handle
    except WorkerProcessError:
        _safe_close(api, control_read_handle)
        _safe_close(api, control_write_handle)
        _safe_close(api, thread_handle)
        _safe_close(api, process_handle)
        _safe_close(api, job_handle)
        raise


def launch_worker_process(
    *,
    environment: WorkerEnvironmentAttestation,
    expected_disposable_root: Path,
    expected_cwd: Path,
    executable: Path,
    argv: Sequence[str],
    cleanup_deadline_seconds: float,
    max_processes: int,
    control_channel: bool = False,
    _process_api: _ProcessApi | None = None,
) -> WorkerProcessHandle:
    return _launch_worker_process(
        environment=environment,
        expected_disposable_root=expected_disposable_root,
        expected_cwd=expected_cwd,
        executable=executable,
        argv=argv,
        cleanup_deadline_seconds=cleanup_deadline_seconds,
        max_processes=max_processes,
        custody=None,
        control_channel=control_channel,
        _process_api=_process_api,
    )


def launch_authenticated_worker_process(
    *,
    custody: WorkerAuthenticationAttestation,
    expected_disposable_root: Path,
    expected_cwd: Path,
    executable: Path,
    argv: Sequence[str],
    cleanup_deadline_seconds: float,
    max_processes: int,
    control_channel: bool = False,
    _process_api: _ProcessApi | None = None,
) -> WorkerProcessHandle:
    state = _require_authentication_attestation(custody)
    try:
        _validate_authenticated_custody(
            custody,
            expected_disposable_root=expected_disposable_root,
            expected_cwd=expected_cwd,
            executable=executable,
        )
        state.consumed = True
        return _launch_worker_process(
            environment=custody.environment,
            expected_disposable_root=expected_disposable_root,
            expected_cwd=expected_cwd,
            executable=executable,
            argv=argv,
            cleanup_deadline_seconds=cleanup_deadline_seconds,
            max_processes=max_processes,
            custody=custody,
            control_channel=control_channel,
            _process_api=_process_api,
        )
    except WorkerProcessError:
        state.consumed = True
        try:
            purge_worker_authentication_state(custody)
        except WorkerProcessError:
            pass
        raise


def _normalize_member_pids(value: object, *, max_processes: int) -> tuple[int, ...]:
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


def _encode_control_frame(payload: Mapping[str, object]) -> bytes:
    try:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        _fail("WORKER_CONTROL_FRAME_INVALID")
    if not body or len(body) > MAX_CONTROL_FRAME_BYTES:
        _fail("WORKER_CONTROL_FRAME_INVALID")
    return struct.pack(">I", len(body)) + body


def _decode_control_body(body: bytes) -> Mapping[str, object]:
    if not body or len(body) > MAX_CONTROL_FRAME_BYTES:
        _fail("WORKER_CONTROL_FRAME_INVALID")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("WORKER_CONTROL_FRAME_INVALID")
    if not isinstance(value, Mapping):
        _fail("WORKER_CONTROL_FRAME_INVALID")
    return value


def _require_operation_deadline(deadline: float | None) -> None:
    if deadline is None:
        return
    if (
        isinstance(deadline, bool)
        or not isinstance(deadline, (int, float))
        or not math.isfinite(float(deadline))
    ):
        _fail("WORKER_LIMIT_INVALID")
    if time.monotonic() >= float(deadline):
        _fail("WORKER_TIMEOUT")


def _api_write_all(
    api: object, handle: object, data: bytes, *, deadline: float | None = None
) -> None:
    writer = getattr(api, "write_handle", None)
    deadline_writer = getattr(api, "write_handle_deadline", None)
    if not callable(writer):
        _fail("WORKER_CONTROL_UNAVAILABLE")
    offset = 0
    while offset < len(data):
        _require_operation_deadline(deadline)
        try:
            if deadline is not None and callable(deadline_writer):
                written = deadline_writer(handle, data[offset:], deadline=float(deadline))
            else:
                written = writer(handle, data[offset:])
        except WorkerProcessError:
            raise
        except Exception:
            _fail("WORKER_CONTROL_IO_FAILED")
        if isinstance(written, bool) or not isinstance(written, int) or written <= 0:
            _fail("WORKER_CONTROL_IO_FAILED")
        offset += written


def _api_read_exact(
    api: object, handle: object, size: int, *, deadline: float | None = None
) -> bytes:
    reader = getattr(api, "read_handle", None)
    deadline_reader = getattr(api, "read_handle_deadline", None)
    if not callable(reader):
        _fail("WORKER_CONTROL_UNAVAILABLE")
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        _require_operation_deadline(deadline)
        try:
            if deadline is not None and callable(deadline_reader):
                chunk = deadline_reader(handle, remaining, deadline=float(deadline))
            else:
                chunk = reader(handle, remaining)
        except WorkerProcessError:
            raise
        except Exception:
            _fail("WORKER_CONTROL_IO_FAILED")
        if not isinstance(chunk, bytes) or not chunk:
            _fail("WORKER_CONTROL_IO_FAILED")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def exchange_worker_control(
    handle: WorkerProcessHandle,
    payload: Mapping[str, object],
    *,
    deadline: float | None = None,
) -> Mapping[str, object]:
    handle = _require_issued_handle(handle)
    _require_operation_deadline(deadline)
    if not isinstance(payload, Mapping):
        _fail("WORKER_CONTROL_FRAME_INVALID")
    if (
        handle._cleanup_result is not None
        or handle._control_read_handle is None
        or handle._control_write_handle is None
    ):
        _fail("WORKER_CONTROL_CLOSED")
    handle._request_id += 1
    request_id = handle._request_id
    frame = _encode_control_frame(
        {"version": _CONTROL_FRAME_VERSION, "request_id": request_id, "payload": dict(payload)}
    )
    _api_write_all(
        handle._api,
        handle._control_write_handle,
        frame,
        deadline=deadline,
    )
    header = _api_read_exact(
        handle._api,
        handle._control_read_handle,
        4,
        deadline=deadline,
    )
    length = struct.unpack(">I", header)[0]
    if length <= 0 or length > MAX_CONTROL_FRAME_BYTES:
        _fail("WORKER_CONTROL_FRAME_INVALID")
    body = _api_read_exact(
        handle._api,
        handle._control_read_handle,
        length,
        deadline=deadline,
    )
    envelope = _decode_control_body(body)
    if (
        envelope.get("version") != _CONTROL_FRAME_VERSION
        or envelope.get("request_id") != request_id
    ):
        _fail("WORKER_CONTROL_FRAME_INVALID")
    response = envelope.get("payload")
    if not isinstance(response, Mapping):
        _fail("WORKER_CONTROL_FRAME_INVALID")
    return MappingProxyType(dict(response))


def _stream_read_exact(
    stream: BinaryIO, size: int, *, allow_clean_eof: bool = False
) -> bytes | None:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            if allow_clean_eof and not chunks:
                return None
            raise WorkerProcessError("WORKER_CONTROL_FRAME_INVALID")
        if not isinstance(chunk, bytes):
            raise WorkerProcessError("WORKER_CONTROL_FRAME_INVALID")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def run_worker_control_child(
    handler: Callable[[Mapping[str, object]], Mapping[str, object]],
    *, input_stream: BinaryIO | None = None, output_stream: BinaryIO | None = None
) -> int:
    source = input_stream if input_stream is not None else sys.stdin.buffer
    sink = output_stream if output_stream is not None else sys.stdout.buffer
    while True:
        try:
            header = _stream_read_exact(source, 4, allow_clean_eof=True)
            if header is None:
                return 0
            length = struct.unpack(">I", header)[0]
            if length <= 0 or length > MAX_CONTROL_FRAME_BYTES:
                return 2
            body = _stream_read_exact(source, length)
            if body is None:
                return 2
            envelope = _decode_control_body(body)
            if envelope.get("version") != _CONTROL_FRAME_VERSION:
                return 2
            request_id = envelope.get("request_id")
            payload = envelope.get("payload")
            if (
                isinstance(request_id, bool)
                or not isinstance(request_id, int)
                or request_id <= 0
                or not isinstance(payload, Mapping)
            ):
                return 2
            try:
                response = handler(payload)
            except Exception:
                response = {"_worker_error": "WORKER_CONTROL_HANDLER_FAILED"}
            if not isinstance(response, Mapping):
                response = {"_worker_error": "WORKER_CONTROL_RESPONSE_INVALID"}
            frame = _encode_control_frame(
                {
                    "version": _CONTROL_FRAME_VERSION,
                    "request_id": request_id,
                    "payload": dict(response),
                }
            )
            sink.write(frame)
            sink.flush()
        except (WorkerProcessError, OSError, ValueError, TypeError):
            return 2


def _cleanup_failure(
    *, code: str, survivors: tuple[int, ...] = ()
) -> WorkerCleanupResult:
    return WorkerCleanupResult(
        status="CLEANUP_FAILED",
        success=False,
        promotion_safe=False,
        survivor_pids=survivors,
        survivor_count=len(survivors),
        error_code=code,
    )


def _close_control_handles(handle: WorkerProcessHandle) -> bool:
    okay = True
    if handle._control_write_handle is not None:
        okay = _safe_close(handle._api, handle._control_write_handle) and okay
        handle._control_write_handle = None
    if handle._control_read_handle is not None:
        okay = _safe_close(handle._api, handle._control_read_handle) and okay
        handle._control_read_handle = None
    return okay


def _close_cleanup_handles(handle: WorkerProcessHandle) -> bool:
    okay = _close_control_handles(handle)
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
    handle = _require_issued_handle(handle)
    if handle._cleanup_result is not None:
        return handle._cleanup_result
    control_close_ok = _close_control_handles(handle)
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
        _close_cleanup_handles(handle)
        result = _cleanup_failure(
            code="WORKER_CLEANUP_TERMINATE_FAILED", survivors=before.member_pids
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
                code="WORKER_CLEANUP_SURVIVORS", survivors=survivors
            )
            handle._cleanup_result = result
            return result
        _sleep(0.01)
    resource_close_ok = _close_cleanup_handles(handle)
    if not control_close_ok or not resource_close_ok:
        result = _cleanup_failure(code="WORKER_CLEANUP_RESOURCE_CLOSE_FAILED")
        handle._cleanup_result = result
        return result
    auth_state_purged = False
    if handle._authentication_custody is not None:
        try:
            purge_worker_authentication_state(handle._authentication_custody)
        except WorkerProcessError:
            result = _cleanup_failure(code="WORKER_AUTH_STATE_PURGE_FAILED")
            handle._cleanup_result = result
            return result
        auth_state_purged = True
    result = WorkerCleanupResult(
        status="CLEANUP_SUCCEEDED",
        success=True,
        promotion_safe=True,
        survivor_pids=(),
        survivor_count=0,
        error_code=None,
        auth_state_purged=auth_state_purged,
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


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", _STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", wintypes.BOOL),
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
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
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
            ctypes.c_void_p,
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
        k32.CreatePipe.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(_SECURITY_ATTRIBUTES),
            wintypes.DWORD,
        ]
        k32.CreatePipe.restype = wintypes.BOOL
        k32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
        k32.SetHandleInformation.restype = wintypes.BOOL
        k32.SetNamedPipeHandleState.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        k32.SetNamedPipeHandleState.restype = wintypes.BOOL
        k32.PeekNamedPipe.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        k32.PeekNamedPipe.restype = wintypes.BOOL
        k32.InitializeProcThreadAttributeList.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)
        ]
        k32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        k32.UpdateProcThreadAttribute.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        k32.UpdateProcThreadAttribute.restype = wintypes.BOOL
        k32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
        k32.DeleteProcThreadAttributeList.restype = None
        k32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_SECURITY_ATTRIBUTES),
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.ReadFile.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        k32.ReadFile.restype = wintypes.BOOL
        k32.WriteFile.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        k32.WriteFile.restype = wintypes.BOOL

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

    @staticmethod
    def _environment_buffer(environment: Mapping[str, str]):
        block = "\0".join(
            f"{key}={value}"
            for key, value in sorted(environment.items(), key=lambda item: item[0].casefold())
        ) + "\0\0"
        return ctypes.create_unicode_buffer(block)

    def create_suspended_process(
        self,
        *, executable: Path, argv: tuple[str, ...], cwd: Path, environment: Mapping[str, str]
    ) -> _CreatedProcess:
        startup = _STARTUPINFOW()
        startup.cb = ctypes.sizeof(startup)
        process = _PROCESS_INFORMATION()
        command_line = ctypes.create_unicode_buffer(
            subprocess.list2cmdline([str(executable), *argv])
        )
        environment_buffer = self._environment_buffer(environment)
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

    def _create_pipe(self) -> tuple[object, object]:
        security = _SECURITY_ATTRIBUTES(
            nLength=ctypes.sizeof(_SECURITY_ATTRIBUTES),
            lpSecurityDescriptor=None,
            bInheritHandle=True,
        )
        read_handle = wintypes.HANDLE()
        write_handle = wintypes.HANDLE()
        if not self._kernel32.CreatePipe(
            ctypes.byref(read_handle), ctypes.byref(write_handle), ctypes.byref(security), 0
        ):
            raise OSError
        return read_handle, write_handle

    def _set_not_inheritable(self, handle: object) -> None:
        if not self._kernel32.SetHandleInformation(handle, _HANDLE_FLAG_INHERIT, 0):
            raise OSError

    def _set_pipe_nowait(self, handle: object) -> None:
        mode = wintypes.DWORD(_PIPE_NOWAIT)
        if not self._kernel32.SetNamedPipeHandleState(
            handle, ctypes.byref(mode), None, None
        ):
            raise OSError

    def _create_null_writer(self, security: _SECURITY_ATTRIBUTES) -> object:
        handle = self._kernel32.CreateFileW(
            "NUL",
            _GENERIC_WRITE,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE,
            ctypes.byref(security),
            _OPEN_EXISTING,
            _FILE_ATTRIBUTE_NORMAL,
            None,
        )
        invalid = ctypes.c_void_p(-1).value
        if not handle or ctypes.cast(handle, ctypes.c_void_p).value == invalid:
            raise OSError
        return handle

    def create_suspended_process_with_control(
        self,
        *, executable: Path, argv: tuple[str, ...], cwd: Path, environment: Mapping[str, str]
    ) -> _CreatedProcess:
        child_read = child_write = parent_read = parent_write = stderr_handle = None
        attribute_list = None
        process = _PROCESS_INFORMATION()
        attribute_buffer = None
        try:
            child_read, parent_write = self._create_pipe()
            parent_read, child_write = self._create_pipe()
            self._set_not_inheritable(parent_write)
            self._set_not_inheritable(parent_read)
            self._set_pipe_nowait(parent_write)
            security = _SECURITY_ATTRIBUTES(
                nLength=ctypes.sizeof(_SECURITY_ATTRIBUTES),
                lpSecurityDescriptor=None,
                bInheritHandle=True,
            )
            stderr_handle = self._create_null_writer(security)
            size = ctypes.c_size_t(0)
            self._kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
            if size.value <= 0:
                raise OSError
            attribute_buffer = ctypes.create_string_buffer(size.value)
            attribute_list = ctypes.cast(attribute_buffer, ctypes.c_void_p)
            if not self._kernel32.InitializeProcThreadAttributeList(
                attribute_list, 1, 0, ctypes.byref(size)
            ):
                raise OSError
            inherited = (wintypes.HANDLE * 3)(child_read, child_write, stderr_handle)
            if not self._kernel32.UpdateProcThreadAttribute(
                attribute_list,
                0,
                PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                ctypes.cast(inherited, ctypes.c_void_p),
                ctypes.sizeof(inherited),
                None,
                None,
            ):
                raise OSError
            startup = _STARTUPINFOEXW()
            startup.StartupInfo.cb = ctypes.sizeof(startup)
            startup.StartupInfo.dwFlags = _STARTF_USESTDHANDLES
            startup.StartupInfo.hStdInput = child_read
            startup.StartupInfo.hStdOutput = child_write
            startup.StartupInfo.hStdError = stderr_handle
            startup.lpAttributeList = attribute_list
            command_line = ctypes.create_unicode_buffer(
                subprocess.list2cmdline([str(executable), *argv])
            )
            environment_buffer = self._environment_buffer(environment)
            flags = (
                _CREATE_SUSPENDED
                | _CREATE_UNICODE_ENVIRONMENT
                | _CREATE_NO_WINDOW
                | EXTENDED_STARTUPINFO_PRESENT
            )
            if not self._kernel32.CreateProcessW(
                str(executable),
                command_line,
                None,
                None,
                True,
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
                control_read_handle=parent_read,
                control_write_handle=parent_write,
            )
        except Exception:
            for handle in (parent_read, parent_write):
                if handle is not None:
                    _safe_close(self, handle)
            raise
        finally:
            for handle in (child_read, child_write, stderr_handle):
                if handle is not None:
                    _safe_close(self, handle)
            if attribute_list is not None:
                self._kernel32.DeleteProcThreadAttributeList(attribute_list)
            del attribute_buffer

    def _pipe_available(self, handle: object) -> int:
        available = wintypes.DWORD()
        if not self._kernel32.PeekNamedPipe(
            handle, None, 0, None, ctypes.byref(available), None
        ):
            raise OSError
        return int(available.value)

    @staticmethod
    def _deadline_sleep(deadline: float) -> None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WorkerProcessError("WORKER_TIMEOUT")
        time.sleep(min(0.005, remaining))

    def read_handle(self, handle: object, size: int) -> bytes:
        requested = min(size, 64 * 1024)
        buffer = ctypes.create_string_buffer(requested)
        read = wintypes.DWORD()
        if not self._kernel32.ReadFile(
            handle, buffer, requested, ctypes.byref(read), None
        ):
            raise OSError
        return bytes(buffer.raw[: int(read.value)])

    def read_handle_deadline(self, handle: object, size: int, *, deadline: float) -> bytes:
        while True:
            if time.monotonic() >= deadline:
                raise WorkerProcessError("WORKER_TIMEOUT")
            available = self._pipe_available(handle)
            if available > 0:
                return self.read_handle(handle, min(size, available))
            self._deadline_sleep(deadline)

    def write_handle(self, handle: object, data: bytes) -> int:
        chunk = data[: 64 * 1024]
        buffer = ctypes.create_string_buffer(chunk, len(chunk))
        written = wintypes.DWORD()
        if not self._kernel32.WriteFile(
            handle, buffer, len(chunk), ctypes.byref(written), None
        ):
            raise OSError
        return int(written.value)

    def write_handle_deadline(self, handle: object, data: bytes, *, deadline: float) -> int:
        chunk = data[: 64 * 1024]
        while True:
            if time.monotonic() >= deadline:
                raise WorkerProcessError("WORKER_TIMEOUT")
            buffer = ctypes.create_string_buffer(chunk, len(chunk))
            written = wintypes.DWORD()
            ctypes.set_last_error(0)
            if self._kernel32.WriteFile(
                handle, buffer, len(chunk), ctypes.byref(written), None
            ):
                count = int(written.value)
                if count > 0:
                    return count
            else:
                error = ctypes.get_last_error()
                if error not in {_ERROR_PIPE_BUSY, _ERROR_NO_DATA}:
                    raise OSError
            self._deadline_sleep(deadline)

    def assign_process(self, job_handle: object, process_handle: object) -> None:
        if not self._kernel32.AssignProcessToJobObject(job_handle, process_handle):
            raise OSError

    def resume_process(self, thread_handle: object) -> None:
        if self._kernel32.ResumeThread(thread_handle) == 0xFFFFFFFF:
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
    "MAX_CONTROL_FRAME_BYTES",
    "ProcessTreeIdentity",
    "WorkerAuthFileObservation",
    "WorkerAuthPurgeResult",
    "WorkerAuthenticationAttestation",
    "WorkerCleanupResult",
    "WorkerEnvironmentAttestation",
    "WorkerProcessError",
    "WorkerProcessHandle",
    "cleanup_worker_process",
    "exchange_worker_control",
    "attest_authenticated_worker_environment",
    "launch_authenticated_worker_process",
    "launch_worker_process",
    "purge_worker_authentication_state",
    "prepare_worker_environment",
    "run_worker_control_child",
]
