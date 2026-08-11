"""Bounded Python client and file helpers for the isolated .NET IPC protocol."""

from __future__ import annotations

import ctypes
import hashlib
import json
import ntpath
import os
import re
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp_integration_lib.autocad_render_evidence import (
    AutoCADRenderEvidenceError,
    validate_render_evidence,
    validate_render_request,
)
from mcp_integration_lib.exact_base_xref import (
    ExactBaseXrefError,
    validate_extraction_plan,
    validate_xref_inspection,
)
from cad_agent.visual_evidence import (
    VisualEvidenceError,
    assert_dimension_register_unchanged,
    build_dimension_register_datum_bindings,
    snapshot_dimension_register,
    snapshot_visual_run_manifest,
    validate_visual_evidence_freshness,
)

SCHEMA_VERSION = "1.0"
DEFAULT_IPC_DIR = Path(r"C:\temp")
IPC_DIR_ENV_VAR = "CAD_AGENT_DOTNET_IPC_DIR"
DEFAULT_DISPOSABLE_WORKSPACE_DIR = "disposable-workspaces"
MAX_REQUEST_ID_LENGTH = 128
DEFAULT_MAX_READ_BYTES = 1024 * 1024

REQUEST_PREFIX = "cadagent_dotnet_request_"
RESULT_PREFIX = "cadagent_dotnet_result_"
JSON_SUFFIX = ".json"

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_VS_T3_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_LOWERCASE_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_VS_T3_CAPTURED_AT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)
_VS_T3_ARTIFACT_POLICY = "vs-t3-artifacts-1"
SUPPORTED_OPERATIONS = frozenset(
    {
        "health",
        "review",
        "close_disposable",
        "mechanical_bom",
        "drawing_setup_audit",
        "visual_evidence_export",
        "native_render_evidence",
        "exact_base_xref_inspection",
        "exact_base_xref_extraction",
    }
)
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_WM_CHAR = 0x0102
_DOTNET_DISPATCH_COMMAND = "\x1b\x1bCADAGENT_DISPATCH\r"
_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
_EXACT_BASE_XREF_INSPECTION = "exact_base_xref_inspection"
_EXACT_BASE_XREF_EXTRACTION = "exact_base_xref_extraction"
_EXACT_BASE_XREF_INSPECTION_TARGET_ROLE = "INSPECTION_HOST"
_EXACT_BASE_XREF_EXTRACTION_TARGET_ROLE = "DISPOSABLE_CANDIDATE"
_EXACT_BASE_XREF_LIVE_OWNED_FIELDS = frozenset(
    {
        "observed",
        "status",
        "eligible",
        "changed",
        "dbmod_before",
        "dbmod_after",
        "live_bounds",
        "live_hashes",
        "live_timestamps",
    }
)


def _get_user32() -> Any:
    """Return the Win32 user32 API lazily so the trigger remains offline-testable."""

    return ctypes.windll.user32


def make_windows_dotnet_dispatch_trigger(hwnd: int) -> Callable[[], None]:
    """Return a trigger that posts ``CADAGENT_DISPATCH`` to AutoCAD."""

    if type(hwnd) is not int or hwnd <= 0:
        raise ValueError("hwnd must be a positive integer")

    def trigger() -> None:
        user32 = _get_user32()
        mdi_clients: list[int] = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(child: int, _lparam: int) -> bool:
            name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(child, name, len(name))
            if name.value == "MDIClient":
                mdi_clients.append(child)
                return False
            return True

        user32.EnumChildWindows(hwnd, callback_type(callback), 0)
        target = mdi_clients[0] if mdi_clients else hwnd
        for character in _DOTNET_DISPATCH_COMMAND:
            user32.PostMessageW(target, _WM_CHAR, ord(character), 0)

    return trigger


def get_ipc_dir(ipc_dir: str | os.PathLike[str] | None = None) -> Path:
    """Return the configured IPC directory as an absolute path.

    An explicit directory wins over ``CAD_AGENT_DOTNET_IPC_DIR``.  The
    protocol default is ``C:\\temp`` so it is shared with the AutoCAD side.
    """

    configured = ipc_dir
    if configured is None:
        configured = os.environ.get(IPC_DIR_ENV_VAR) or DEFAULT_IPC_DIR
    path = Path(configured).expanduser()
    if not str(path):
        raise ValueError("ipc_dir must not be empty")
    return path.resolve()


def normalize_request_id(request_id: str) -> str:
    """Validate a request id before using it in a file name."""

    if not isinstance(request_id, str) or not request_id:
        raise ValueError("request_id must not be empty")
    if len(request_id) > MAX_REQUEST_ID_LENGTH or not _REQUEST_ID_PATTERN.fullmatch(request_id):
        raise ValueError("request_id contains unsupported filename characters or is too long")
    return request_id


def scavenge_visual_evidence_artifacts(
    ipc_dir: str | os.PathLike[str],
    *,
    now: float | None = None,
    ttl_seconds: float = 24 * 60 * 60,
) -> tuple[str, ...]:
    """Remove only old, lease-free VS-T3 request directories.

    The managed exporter holds ``active.lease`` open with exclusive sharing.
    A failed exclusive open therefore leaves a live AutoCAD operation alone on
    Windows.  A directory without a lease is claimed with an exclusive create
    before its contents are removed.  Reparse points, symlinks, unexpected
    names, and fresh directories are never removed.
    """

    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")
    root = Path(ipc_dir).resolve() / "artifacts"
    if _path_contains_windows_reparse_point(root) or not root.is_dir():
        return ()
    current = time.time() if now is None else float(now)
    removed: list[str] = []
    for candidate in list(root.iterdir()):
        if _path_contains_windows_reparse_point(candidate) or not candidate.is_dir():
            continue
        try:
            request_id = normalize_request_id(candidate.name)
            age = current - candidate.stat().st_mtime
        except (OSError, ValueError):
            continue
        if age < ttl_seconds:
            continue

        lease = candidate / "active.lease"
        lease_handle = _claim_visual_evidence_lease(lease)
        if lease_handle is None:
            continue
        try:
            lease_handle.close()
            lease_handle = None
            lease.unlink(missing_ok=True)
            _remove_tree_without_reparse(candidate)
            removed.append(request_id)
        except (FileExistsError, PermissionError, OSError):
            continue
        finally:
            if lease_handle is not None:
                try:
                    lease_handle.close()
                except OSError:
                    pass
    return tuple(removed)


def _claim_visual_evidence_lease(lease: Path):
    """Return an exclusively locked lease handle, or None when it is active."""

    handle = None
    try:
        if lease.exists():
            handle = lease.open("r+b", buffering=0)
        else:
            handle = lease.open("xb", buffering=0)
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except (FileExistsError, PermissionError, OSError):
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        return None


def _remove_tree_without_reparse(path: Path) -> None:
    """Delete a directory only when every component is a normal file/dir."""

    if _path_contains_windows_reparse_point(path) or not path.is_dir():
        raise OSError(f"unsafe artifact path: {path}")
    for child in path.iterdir():
        if _path_contains_windows_reparse_point(child):
            raise OSError(f"reparse point in artifact path: {child}")
        if child.is_dir():
            _remove_tree_without_reparse(child)
        elif child.is_file():
            child.unlink()
        else:
            raise OSError(f"unsupported artifact path: {child}")
    path.rmdir()


def _snapshot_vs_t3_manifest(
    manifest_path: Path,
    *,
    drawing_full_path: str,
    run_id: str,
    latest_mutation_sha256: str,
    expected_sha256: str,
) -> tuple[bytes, Mapping[str, Any], str]:
    """Snapshot the complete Visual Run Manifest before dispatch.

    The managed AutoCAD side receives only the trusted values copied from this
    snapshot.  Python keeps the complete byte snapshot so a later change to
    authority, state, drawing identity, or any other manifest field cannot be
    mistaken for an unchanged mutation hash.
    """

    candidate = Path(manifest_path)
    if _path_contains_windows_reparse_point(candidate):
        raise ValueError("visual run manifest path contains a reparse point")
    try:
        raw, manifest, digest = snapshot_visual_run_manifest(candidate)
    except VisualEvidenceError as exc:
        raise ValueError(str(exc)) from exc
    if digest != expected_sha256:
        raise ValueError("visual run manifest hash does not match the request")
    if manifest.get("run_id") != run_id:
        raise ValueError("visual run manifest run_id does not match the request")
    if manifest.get("latest_mutation_sha256") != latest_mutation_sha256:
        raise ValueError("visual run manifest latest_mutation_sha256 does not match the request")
    try:
        manifest_path_value = manifest["drawing"]["absolute_path"]
        manifest_drawing_path = normalize_windows_absolute_path(manifest_path_value)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("visual run manifest drawing path is invalid") from exc
    if manifest_drawing_path != drawing_full_path:
        raise ValueError("visual run manifest drawing path does not match the request")
    return raw, manifest, digest


def _assert_vs_t3_manifest_unchanged(
    manifest_path: Path,
    expected_raw: bytes,
    expected_digest: str,
) -> None:
    """Reject any manifest-byte change before or after evidence handoff."""

    if _path_contains_windows_reparse_point(manifest_path):
        raise DotNetIPCProtocolError("visual run manifest path contains a reparse point")
    try:
        current_raw, _manifest, current_digest = snapshot_visual_run_manifest(manifest_path)
    except VisualEvidenceError as exc:
        raise DotNetIPCProtocolError(str(exc)) from exc
    if current_raw != expected_raw or current_digest != expected_digest:
        raise DotNetIPCProtocolError("visual run manifest changed during evidence export")


def _requested_datum_ids(measurements: Sequence[Mapping[str, Any]]) -> set[str]:
    """Return DATUM ids requested by measurements without trusting their values."""

    datum_ids: set[str] = set()
    for measurement in measurements:
        if not isinstance(measurement, Mapping):
            continue
        for name in ("reference", "to_reference"):
            reference = measurement.get(name)
            if not isinstance(reference, Mapping) or reference.get("type") != "DATUM":
                continue
            datum_id = reference.get("id")
            if isinstance(datum_id, str):
                datum_ids.add(datum_id)
    return datum_ids


def _assert_dimension_register_snapshot(
    snapshot: tuple[Path, bytes, str],
) -> None:
    path, raw, digest = snapshot
    try:
        assert_dimension_register_unchanged(path, raw, digest)
    except VisualEvidenceError as exc:
        raise DotNetIPCProtocolError(str(exc)) from exc


def _path_contains_windows_reparse_point(path: str | os.PathLike[str]) -> bool:
    """Return whether a path or any existing component is a Windows reparse point.

    ``Path.is_symlink()`` does not reliably identify junctions and mount points.
    The Win32 file attributes are checked component-by-component so a missing
    child below a junction is still rejected.  On non-Windows platforms the
    equivalent symlink walk keeps the offline implementation deterministic.
    """

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if os.name != "nt":
        return any(component.is_symlink() for component in (candidate, *candidate.parents))

    try:
        get_attributes = ctypes.windll.kernel32.GetFileAttributesW
        get_attributes.argtypes = [wintypes.LPCWSTR]
        get_attributes.restype = wintypes.DWORD
    except AttributeError:
        return candidate.is_symlink()

    components = list(candidate.parts)
    current = Path(components[0])
    for component in components[1:]:
        current /= component
        attributes = get_attributes(str(current))
        if attributes != _INVALID_FILE_ATTRIBUTES and attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            return True
    attributes = get_attributes(str(current))
    return attributes != _INVALID_FILE_ATTRIBUTES and bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def normalize_windows_absolute_path(path: str | os.PathLike[str]) -> str:
    """Normalize a full Windows path without accepting a relative path."""

    try:
        raw_path = os.fspath(path)
    except TypeError as exc:
        raise ValueError("drawing_full_path must be a full absolute Windows path") from exc
    if not isinstance(raw_path, str) or not raw_path or "\x00" in raw_path:
        raise ValueError("drawing_full_path must be a full absolute Windows path")

    is_drive_path = bool(_WINDOWS_DRIVE_PATH.match(raw_path))
    is_unc_path = raw_path.startswith("\\\\") and len(raw_path) > 2
    if not (is_drive_path or is_unc_path):
        raise ValueError("drawing_full_path must be a full absolute Windows path")

    normalized = ntpath.normpath(raw_path.replace("/", "\\"))
    if not normalized or normalized == ".":
        raise ValueError("drawing_full_path must be a full absolute Windows path")
    return normalized


def request_filename(request_id: str) -> str:
    return f"{REQUEST_PREFIX}{normalize_request_id(request_id)}{JSON_SUFFIX}"


def result_filename(request_id: str) -> str:
    return f"{RESULT_PREFIX}{normalize_request_id(request_id)}{JSON_SUFFIX}"


def request_path(
    ipc_dir: str | os.PathLike[str] | None,
    request_id: str,
) -> Path:
    return get_ipc_dir(ipc_dir) / request_filename(request_id)


def result_path(
    ipc_dir: str | os.PathLike[str] | None,
    request_id: str,
) -> Path:
    return get_ipc_dir(ipc_dir) / result_filename(request_id)


def cleanup_request_files(
    ipc_dir: str | os.PathLike[str] | None,
    request_id: str,
) -> None:
    """Delete only the request/result pair owned by ``request_id``."""

    for path in (request_path(ipc_dir, request_id), result_path(ipc_dir, request_id)):
        if _path_contains_windows_reparse_point(path.parent):
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def atomic_write_json(
    destination: str | os.PathLike[str],
    value: Any,
    *,
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
) -> None:
    """Write JSON as UTF-8 through a same-directory temporary file and replace."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    target = Path(destination)
    encoded = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    if len(encoded) > max_bytes:
        raise ValueError(f"JSON exceeds the {max_bytes}-byte limit")

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def read_json_bounded(
    source: str | os.PathLike[str],
    *,
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
) -> Any:
    """Read one complete UTF-8 JSON file while enforcing a byte limit."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    source_path = Path(source)
    try:
        if source_path.stat().st_size > max_bytes:
            raise ValueError(f"JSON exceeds the {max_bytes}-byte limit")
        encoded = source_path.read_bytes()
    except FileNotFoundError:
        raise
    if len(encoded) > max_bytes:
        raise ValueError(f"JSON exceeds the {max_bytes}-byte limit")
    try:
        text = encoded.decode("utf-8-sig")
        return json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("JSON file is invalid UTF-8 or malformed JSON") from exc


# Descriptive aliases for callers that prefer the C# JsonFileStore naming.
get_request_file_name = request_filename
get_result_file_name = result_filename
get_request_file_path = request_path
get_result_file_path = result_path


class DotNetIPCError(RuntimeError):
    """Base exception for transport and protocol failures."""


class DotNetIPCTimeoutError(DotNetIPCError, TimeoutError):
    """The bounded wait for a result expired."""


class DotNetIPCProtocolError(DotNetIPCError):
    """The dispatcher returned an invalid or unrelated result."""


class DotNetIPCResultError(DotNetIPCError):
    """The dispatcher returned a contract result with ``success=false``."""

    def __init__(self, message: str, *, result: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.result = dict(result) if result is not None else None


class DisposableWorkspaceError(DotNetIPCError):
    """Base error for the server-owned disposable workspace seam."""


@dataclass(slots=True)
class _DisposableWorkspaceLifecycle:
    value: str = "active"


@dataclass(frozen=True, slots=True)
class DisposableWorkspaceLease:
    """Immutable server-issued identity for one disposable workspace."""

    lease_id: str
    workspace_path: Path
    candidate_identity: str
    source_identity: str
    source_fingerprint: str
    purpose: str
    disposable: bool
    save_changes: bool
    created_at: float
    expires_at: float
    _lifecycle: _DisposableWorkspaceLifecycle = field(repr=False, compare=False)

    @property
    def lifecycle_state(self) -> str:
        """Return the owner-controlled lifecycle state without exposing mutation."""

        return self._lifecycle.value


@dataclass(frozen=True, slots=True)
class DisposableWorkspaceClosure:
    """Immutable evidence emitted after one close/cleanup attempt."""

    lease_id: str
    workspace_path: Path
    candidate_identity: str
    source_identity: str
    source_fingerprint: str
    close_outcome: str
    cleanup_outcome: str
    save_changes: bool
    lifecycle_state: str


class DisposableWorkspaceClosureError(DisposableWorkspaceError):
    """Fail-closed close/cleanup evidence; the lease remains open for retry."""

    def __init__(self, closure: DisposableWorkspaceClosure) -> None:
        self.closure = closure
        super().__init__(
            "disposable workspace close did not reach a terminal zero-survivor state"
        )


@dataclass(slots=True)
class _DisposableWorkspaceState:
    """Private canonical lifecycle and binding snapshot for one lease."""

    lease_id: str
    workspace_path: Path
    candidate_identity: str
    source_identity: str
    source_fingerprint: str
    purpose: str
    expires_at: float
    lifecycle_state: str = "active"
    closure: DisposableWorkspaceClosure | None = field(default=None, repr=False)
    failure: DisposableWorkspaceClosure | None = field(default=None, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


class DotNetIPCClient:
    """Write, trigger, and bounded-poll one request at a time.

    ``trigger`` is intentionally injected and takes no arguments.  In
    production it can invoke ``CADAGENT_DISPATCH``; tests can provide a fake
    dispatcher that reads the request file and writes the matching result.
    """

    def __init__(
        self,
        ipc_dir: str | Path | None = None,
        trigger: Callable[[], None] | None = None,
        *,
        timeout_s: float = 10.0,
        poll_interval_s: float = 0.1,
        max_read_bytes: int = DEFAULT_MAX_READ_BYTES,
        request_id_factory: Callable[[], str] | None = None,
        disposable_root: str | Path | None = None,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if poll_interval_s < 0:
            raise ValueError("poll_interval_s must not be negative")
        if max_read_bytes <= 0:
            raise ValueError("max_read_bytes must be positive")

        self.ipc_dir = get_ipc_dir(ipc_dir)
        self.trigger = trigger
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self.max_read_bytes = max_read_bytes
        self.request_id_factory = request_id_factory or (lambda: uuid.uuid4().hex)
        self._disposable_root = self._resolve_disposable_root(disposable_root)
        self._disposable_leases: dict[str, DisposableWorkspaceLease] = {}
        self._disposable_closures: dict[str, DisposableWorkspaceClosure] = {}
        self._disposable_states: dict[str, _DisposableWorkspaceState] = {}

    def request(
        self,
        operation: str,
        drawing_full_path: str | Path | None = None,
        *,
        drawing_sha256: str | None = None,
        parameters: Mapping[str, Any] | None = None,
        approval: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch one validated request and return its complete result JSON."""

        normalized_operation = self._validate_operation(operation)
        normalized_path = self._validate_drawing_path(normalized_operation, drawing_full_path)
        normalized_parameters = self._validate_parameters(
            normalized_operation,
            parameters if parameters is not None else {},
        )
        normalized_sha256 = self._validate_sha256(drawing_sha256)
        if normalized_operation in {
            _EXACT_BASE_XREF_INSPECTION,
            _EXACT_BASE_XREF_EXTRACTION,
        }:
            self._validate_exact_base_xref_hash(normalized_sha256, "drawing_sha256")
            self._validate_exact_base_xref_paths(
                normalized_path,
                normalized_parameters["source_full_path"],
                candidate_output_path=normalized_parameters.get("candidate_output_path"),
            )
        if approval is not None and not isinstance(approval, Mapping):
            raise ValueError("approval must be an object or null")
        if normalized_operation == _EXACT_BASE_XREF_INSPECTION and approval is not None:
            raise ValueError("exact_base_xref_inspection approval must be null")
        if normalized_operation == _EXACT_BASE_XREF_EXTRACTION:
            self._validate_exact_base_xref_approval(
                normalized_parameters["extraction_plan"]["approval"],
                approval,
            )

        actual_request_id = normalize_request_id(
            request_id if request_id is not None else self.request_id_factory()
        )
        request = {
            "request_id": actual_request_id,
            "schema_version": SCHEMA_VERSION,
            "operation": normalized_operation,
            "drawing_full_path": normalized_path,
            "drawing_sha256": normalized_sha256,
            "parameters": normalized_parameters,
            "approval": dict(approval) if approval is not None else None,
        }
        request_file = request_path(self.ipc_dir, actual_request_id)
        result_file = result_path(self.ipc_dir, actual_request_id)

        # A reused id must not consume an old result, but no other request id
        # is touched here or in the finally block below.
        result_file.unlink(missing_ok=True)
        try:
            atomic_write_json(request_file, request, max_bytes=self.max_read_bytes)
            if self.trigger is None:
                raise DotNetIPCError("File IPC requires an AutoCAD dispatcher trigger")
            self.trigger()
            result = self._poll_result(result_file, actual_request_id, normalized_operation)
            if result["success"] is not True:
                errors = result.get("errors", [])
                message = "; ".join(str(error) for error in errors) if errors else "request failed"
                raise DotNetIPCResultError(message, result=result)
            return result
        finally:
            cleanup_request_files(self.ipc_dir, actual_request_id)

    def health(
        self,
        drawing_full_path: str | Path | None = None,
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "health",
            drawing_full_path,
            request_id=request_id,
        )

    def review(
        self,
        drawing_full_path: str | Path,
        handles: Sequence[str],
        *,
        drawing_sha256: str | None = None,
        approval: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if isinstance(handles, (str, bytes)):
            raise ValueError("handles must be a sequence of strings")
        return self.request(
            "review",
            drawing_full_path,
            drawing_sha256=drawing_sha256,
            parameters={"handles": list(handles)},
            approval=approval,
            request_id=request_id,
        )

    def close_disposable(
        self,
        drawing_full_path: str | Path,
        *,
        disposable: bool = True,
        save_changes: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if disposable is not True:
            raise ValueError("parameters.disposable must be true")
        if save_changes is not False:
            raise ValueError("parameters.save_changes must be false")
        return self.request(
            "close_disposable",
            drawing_full_path,
            parameters={"disposable": True, "save_changes": False},
            request_id=request_id,
        )

    def issue_disposable_workspace(
        self,
        *,
        candidate_identity: str,
        source_identity: str,
        source_fingerprint: str,
        purpose: str,
        workspace_root: str | Path | None = None,
        ttl_seconds: float = 60 * 60,
    ) -> DisposableWorkspaceLease:
        """Issue one owner-selected, disposable workspace lease.

        The caller may narrow the configured root for a bounded purpose, but
        cannot choose the lease identity or a path outside the owner's root.
        No AutoCAD operation is performed during issuance.
        """

        self._validate_disposable_binding(
            candidate_identity,
            source_identity,
            source_fingerprint,
            purpose,
        )
        if type(ttl_seconds) not in (int, float) or isinstance(ttl_seconds, bool):
            raise ValueError("disposable workspace ttl_seconds must be a finite positive number")
        if not float(ttl_seconds) > 0 or not float(ttl_seconds) < 7 * 24 * 60 * 60:
            raise ValueError("disposable workspace ttl_seconds must be a finite positive number")
        requested_root = self._resolve_requested_disposable_root(workspace_root)
        try:
            requested_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError("disposable workspace root is unavailable") from exc
        if _path_contains_windows_reparse_point(requested_root):
            raise ValueError("disposable workspace root is unsafe")

        for _ in range(4):
            lease_id = uuid.uuid4().hex
            workspace_path = requested_root / f"lease-{lease_id}"
            try:
                workspace_path.mkdir()
            except FileExistsError:
                continue
            except OSError as exc:
                raise ValueError("disposable workspace could not be created") from exc
            if _path_contains_windows_reparse_point(workspace_path):
                try:
                    workspace_path.rmdir()
                except OSError:
                    pass
                raise ValueError("disposable workspace is unsafe")
            created_at = time.time()
            lifecycle = _DisposableWorkspaceLifecycle()
            lease = DisposableWorkspaceLease(
                lease_id=lease_id,
                workspace_path=workspace_path.resolve(),
                candidate_identity=candidate_identity,
                source_identity=source_identity,
                source_fingerprint=source_fingerprint,
                purpose=purpose,
                disposable=True,
                save_changes=False,
                created_at=created_at,
                expires_at=created_at + float(ttl_seconds),
                _lifecycle=lifecycle,
            )
            self._disposable_leases[lease_id] = lease
            self._disposable_states[lease_id] = _DisposableWorkspaceState(
                lease_id=lease_id,
                workspace_path=workspace_path.resolve(),
                candidate_identity=candidate_identity,
                source_identity=source_identity,
                source_fingerprint=source_fingerprint,
                purpose=purpose,
                expires_at=created_at + float(ttl_seconds),
            )
            return lease
        raise ValueError("disposable workspace identity collision")

    def close_disposable_workspace(
        self,
        lease: DisposableWorkspaceLease,
        *,
        candidate_identity: str,
        source_identity: str,
        source_fingerprint: str,
    ) -> DisposableWorkspaceClosure:
        """Close and remove one issued workspace, returning immutable evidence."""

        self._validate_disposable_lease(lease)
        state = self._disposable_states.get(lease.lease_id)
        if state is None:
            raise DotNetIPCProtocolError("disposable workspace lease provenance invalid")

        with state.lock:
            # Terminal evidence is replayable only for the exact owner binding.
            # Validate the caller tuple before exposing cached closure/failure
            # records so mismatched or hostile replays fail closed without
            # touching the terminal lifecycle state.
            self._validate_disposable_binding(
                candidate_identity,
                source_identity,
                source_fingerprint,
                state.purpose,
            )
            if (
                candidate_identity != state.candidate_identity
                or source_identity != state.source_identity
                or source_fingerprint != state.source_fingerprint
            ):
                raise DotNetIPCProtocolError("disposable workspace binding mismatch")

            existing = state.closure or self._disposable_closures.get(lease.lease_id)
            if existing is not None:
                return existing
            if state.failure is not None:
                raise DisposableWorkspaceClosureError(state.failure) from None

            if state.lifecycle_state != "active":
                raise DotNetIPCProtocolError("disposable workspace lease is not active")
            if time.time() >= state.expires_at:
                raise DotNetIPCProtocolError("disposable workspace lease is expired")
            if not self._workspace_path_is_owned(state.workspace_path):
                closure = self._failed_disposable_closure(
                    lease,
                    state=state,
                    close_outcome="not_attempted",
                    cleanup_outcome="failed",
                    lifecycle_state="cleanup_failed",
                )
                state.failure = closure
                raise DisposableWorkspaceClosureError(closure)

            state.lifecycle_state = "closing"
            try:
                self.close_disposable(
                    str(state.workspace_path),
                    disposable=True,
                    save_changes=False,
                    request_id=f"close-{state.lease_id}",
                )
            except (DotNetIPCError, OSError, ValueError):
                state.lifecycle_state = "active"
                closure = self._failed_disposable_closure(
                    lease,
                    state=state,
                    close_outcome="failed",
                    cleanup_outcome="not_attempted",
                    lifecycle_state="close_failed",
                )
                state.failure = closure
                raise DisposableWorkspaceClosureError(closure) from None

            try:
                _remove_tree_without_reparse(state.workspace_path)
                if state.workspace_path.exists():
                    raise OSError("disposable workspace survivors remain")
            except (OSError, ValueError):
                state.lifecycle_state = "active"
                closure = self._failed_disposable_closure(
                    lease,
                    state=state,
                    close_outcome="closed",
                    cleanup_outcome="failed",
                    lifecycle_state="cleanup_failed",
                )
                state.failure = closure
                raise DisposableWorkspaceClosureError(closure) from None

            closure = DisposableWorkspaceClosure(
                lease_id=state.lease_id,
                workspace_path=state.workspace_path,
                candidate_identity=state.candidate_identity,
                source_identity=state.source_identity,
                source_fingerprint=state.source_fingerprint,
                close_outcome="closed",
                cleanup_outcome="zero_survivors",
                save_changes=False,
                lifecycle_state="closed",
            )
            state.lifecycle_state = "closed"
            state.closure = closure
            lease._lifecycle.value = "closed"
            self._disposable_closures[state.lease_id] = closure
            return closure

    @staticmethod
    def _validate_disposable_binding(
        candidate_identity: str,
        source_identity: str,
        source_fingerprint: str,
        purpose: str,
    ) -> None:
        for value, label in (
            (candidate_identity, "candidate_identity"),
            (source_identity, "source_identity"),
            (purpose, "purpose"),
        ):
            if type(value) is not str or not value or len(value) > 256 or "\x00" in value:
                raise ValueError(f"disposable workspace {label} is invalid")
        if not _VS_T3_IDENTIFIER_PATTERN.fullmatch(purpose):
            raise ValueError("disposable workspace purpose is invalid")
        if type(source_fingerprint) is not str or not _SHA256_PATTERN.fullmatch(
            source_fingerprint
        ):
            raise ValueError("disposable workspace source_fingerprint is invalid")

    @staticmethod
    def _path_value(value: str | Path, label: str) -> Path:
        path_type = type(Path("."))
        if type(value) is not str and type(value) is not path_type:
            raise ValueError(f"disposable workspace {label} is invalid")
        if type(value) is str and (not value or "\x00" in value):
            raise ValueError(f"disposable workspace {label} is invalid")
        return Path(value)

    def _resolve_disposable_root(self, value: str | Path | None) -> Path:
        if value is None:
            candidate = self.ipc_dir / DEFAULT_DISPOSABLE_WORKSPACE_DIR
        else:
            candidate = self._path_value(value, "root")
            if not candidate.is_absolute():
                raise ValueError("disposable workspace root must be absolute")
        candidate = candidate.resolve(strict=False)
        if _path_contains_windows_reparse_point(candidate):
            raise ValueError("disposable workspace root is unsafe")
        try:
            candidate.relative_to(self.ipc_dir)
        except ValueError as exc:
            raise ValueError("disposable workspace root is outside the IPC root") from exc
        return candidate

    def _resolve_requested_disposable_root(self, value: str | Path | None) -> Path:
        if value is None:
            return self._disposable_root
        candidate = self._path_value(value, "root")
        if not candidate.is_absolute():
            raise ValueError("disposable workspace root must be absolute")
        if _path_contains_windows_reparse_point(candidate):
            raise ValueError("disposable workspace root is unsafe")
        candidate = candidate.resolve(strict=False)
        try:
            candidate.relative_to(self._disposable_root)
        except ValueError as exc:
            raise ValueError("disposable workspace root is outside the owner root") from exc
        return candidate

    def _workspace_path_is_owned(self, path: Path) -> bool:
        if _path_contains_windows_reparse_point(path) or not path.is_dir():
            return False
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(self._disposable_root)
        except ValueError:
            return False
        return True

    def _validate_disposable_lease(self, lease: DisposableWorkspaceLease) -> None:
        if type(lease) is not DisposableWorkspaceLease:
            raise DotNetIPCProtocolError("disposable workspace lease provenance invalid")
        if type(lease.lease_id) is not str or self._disposable_leases.get(lease.lease_id) is not lease:
            raise DotNetIPCProtocolError("disposable workspace lease provenance invalid")
        if lease.disposable is not True or lease.save_changes is not False:
            raise DotNetIPCProtocolError("disposable workspace lease policy invalid")

    @staticmethod
    def _failed_disposable_closure(
        lease: DisposableWorkspaceLease,
        *,
        state: _DisposableWorkspaceState | None = None,
        close_outcome: str,
        cleanup_outcome: str,
        lifecycle_state: str,
    ) -> DisposableWorkspaceClosure:
        source = state if state is not None else lease
        return DisposableWorkspaceClosure(
            lease_id=source.lease_id,
            workspace_path=source.workspace_path,
            candidate_identity=source.candidate_identity,
            source_identity=source.source_identity,
            source_fingerprint=source.source_fingerprint,
            close_outcome=close_outcome,
            cleanup_outcome=cleanup_outcome,
            save_changes=False,
            lifecycle_state=lifecycle_state,
        )

    def mechanical_bom(
        self,
        drawing_full_path: str | Path,
        *,
        request_id: str | None = None,
        drawing_sha256: str | None = None,
        approval: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "mechanical_bom",
            drawing_full_path,
            drawing_sha256=drawing_sha256,
            parameters={},
            approval=approval,
            request_id=request_id,
        )

    def drawing_setup_audit(
        self,
        drawing_full_path: str | Path,
        *,
        drawing_sha256: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "drawing_setup_audit",
            drawing_full_path,
            drawing_sha256=drawing_sha256,
            parameters={},
            approval=None,
            request_id=request_id,
        )

    def native_render_evidence(
        self,
        drawing_full_path: str | Path,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Transport one validated S2A request through the existing File IPC envelope.

        The current dispatcher deliberately returns ``NATIVE_RENDER_NOT_IMPLEMENTED``.
        A successful response is accepted only after its payload is validated against
        the exact S2A request supplied by the caller.
        """

        normalized_request = validate_render_request(request)

        parameters = {
            name: normalized_request[name]
            for name in (
                "run_id",
                "latest_mutation_sha256",
                "visual_run_manifest_sha256",
                "layout",
                "artifact_kind",
                "render_options",
                "requested_at",
            )
        }
        result = self.request(
            "native_render_evidence",
            drawing_full_path,
            drawing_sha256=normalized_request["drawing_sha256"],
            parameters=parameters,
            approval=None,
            request_id=normalized_request["request_id"],
        )
        try:
            validate_render_evidence(result.get("payload"), normalized_request)
        except AutoCADRenderEvidenceError as exc:
            raise DotNetIPCProtocolError(str(exc)) from exc
        return result

    def exact_base_xref_inspection(
        self,
        drawing_full_path: str | Path,
        *,
        drawing_sha256: str,
        source_full_path: str | Path,
        inspection: Mapping[str, Any],
        source_revision: str | None = None,
        run_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Send only S3A inspection expectations to the read-only live gate."""

        validated_inspection = self._validate_offline_xref_inspection(inspection)
        resolved_revision, resolved_run_id = self._resolve_xref_identity(
            validated_inspection,
            source_revision=source_revision,
            run_id=run_id,
        )
        normalized_source = normalize_windows_absolute_path(source_full_path)
        normalized_drawing = normalize_windows_absolute_path(drawing_full_path)
        self._validate_exact_base_xref_hash(drawing_sha256, "drawing_sha256")
        self._validate_exact_base_xref_paths(
            normalized_drawing,
            normalized_source,
            candidate_output_path=None,
        )
        result = self.request(
            _EXACT_BASE_XREF_INSPECTION,
            normalized_drawing,
            drawing_sha256=drawing_sha256,
            parameters={
                "run_id": resolved_run_id,
                "source_full_path": normalized_source,
                "source_revision": resolved_revision,
                "inspection_expectations": self._inspection_expectations(validated_inspection),
                "target_role": _EXACT_BASE_XREF_INSPECTION_TARGET_ROLE,
            },
            approval=None,
            request_id=(
                validated_inspection["request_id"]
                if request_id is None
                else request_id
            ),
        )
        self._validate_exact_base_xref_inspection_result(
            result,
            validated_inspection=validated_inspection,
            drawing_full_path=normalized_drawing,
            drawing_sha256=drawing_sha256,
            run_id=resolved_run_id,
        )
        return result

    def exact_base_xref_extraction(
        self,
        drawing_full_path: str | Path,
        *,
        drawing_sha256: str,
        source_full_path: str | Path,
        inspection: Mapping[str, Any],
        extraction_plan: Mapping[str, Any],
        candidate_output_path: str | Path,
        approval: Mapping[str, Any] | None = None,
        source_revision: str | None = None,
        run_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Validate an offline S3A plan before sending a candidate-only request."""

        validated_inspection = self._validate_offline_xref_inspection(inspection)
        try:
            validated_plan = validate_extraction_plan(
                extraction_plan,
                inspection=validated_inspection,
            )
        except ExactBaseXrefError as exc:
            raise ValueError(str(exc)) from exc
        self._validate_exact_base_xref_approval(validated_plan["approval"], approval)
        resolved_revision, resolved_run_id = self._resolve_xref_identity(
            validated_inspection,
            source_revision=(
                validated_plan["source_revision"]
                if source_revision is None
                else source_revision
            ),
            run_id=validated_plan["run_id"] if run_id is None else run_id,
        )
        if resolved_revision != validated_plan["source_revision"]:
            raise ValueError("source_revision does not match the extraction plan")
        if resolved_run_id != validated_plan["run_id"]:
            raise ValueError("run_id does not match the extraction plan")

        normalized_source = normalize_windows_absolute_path(source_full_path)
        normalized_drawing = normalize_windows_absolute_path(drawing_full_path)
        normalized_output = normalize_windows_absolute_path(candidate_output_path)
        self._validate_exact_base_xref_hash(drawing_sha256, "drawing_sha256")
        self._validate_exact_base_xref_paths(
            normalized_drawing,
            normalized_source,
            candidate_output_path=normalized_output,
        )
        result = self.request(
            _EXACT_BASE_XREF_EXTRACTION,
            normalized_drawing,
            drawing_sha256=drawing_sha256,
            parameters={
                "run_id": resolved_run_id,
                "source_full_path": normalized_source,
                "source_revision": resolved_revision,
                "inspection_expectations": self._inspection_expectations(validated_inspection),
                "extraction_plan": validated_plan,
                "target_role": _EXACT_BASE_XREF_EXTRACTION_TARGET_ROLE,
                "candidate_output_path": normalized_output,
            },
            approval=approval,
            request_id=validated_plan["request_id"] if request_id is None else request_id,
        )
        self._validate_exact_base_xref_extraction_result(
            result,
            validated_inspection=validated_inspection,
            validated_plan=validated_plan,
            drawing_full_path=normalized_drawing,
            drawing_sha256=drawing_sha256,
            candidate_output_path=normalized_output,
            run_id=resolved_run_id,
        )
        return result

    def visual_evidence_export(
        self,
        drawing_full_path: str | Path,
        *,
        drawing_sha256: str,
        run_id: str,
        evidence_id: str,
        region_id: str,
        latest_mutation_sha256: str,
        visual_run_manifest_sha256: str,
        visual_run_manifest_path: str | os.PathLike[str],
        region: Mapping[str, Any],
        measurements: Sequence[Mapping[str, Any]],
        dimension_register_path: str | os.PathLike[str] | None = None,
        artifact_consumer: Callable[[Mapping[str, Any], Mapping[str, Path]], None] | None = None,
        artifact_directory: str | None = None,
        approval: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Capture bounded read-only evidence and hand verified artifacts to a consumer.

        The .NET side retains the request-owned artifact directory until this
        method has validated and copied or promoted every artifact.  The
        callback is therefore the mandatory handoff boundary for the later
        atomic evidence writer; it runs before Python removes the
        request-owned directory.  A timeout never implies that AutoCAD
        stopped working, so an active lease protects the directory from
        cleanup.  DATUM bindings are derived here from one validated,
        byte-snapshotted Dimension Register; callers cannot provide approval
        strings, register hashes, or entity handles directly.
        """

        if not callable(artifact_consumer):
            raise ValueError("visual_evidence_export requires an artifact_consumer handoff callback")
        scavenge_visual_evidence_artifacts(self.ipc_dir)
        actual_request_id = normalize_request_id(
            request_id if request_id is not None else self.request_id_factory()
        )
        normalized_artifact_directory = artifact_directory or f"artifacts/{actual_request_id}"
        self._validate_request_artifact_directory(normalized_artifact_directory, actual_request_id)
        parameters = {
            "run_id": run_id,
            "evidence_id": evidence_id,
            "region_id": region_id,
            "latest_mutation_sha256": latest_mutation_sha256,
            "visual_run_manifest_sha256": visual_run_manifest_sha256,
            "artifact_policy_version": _VS_T3_ARTIFACT_POLICY,
            "artifact_directory": normalized_artifact_directory,
            "region": dict(region),
            "measurements": [dict(measurement) for measurement in measurements],
            "datum_bindings": [],
        }
        normalized_path = self._validate_drawing_path("visual_evidence_export", drawing_full_path)
        normalized_sha256 = self._validate_sha256(drawing_sha256)
        normalized_manifest_sha256 = self._validate_sha256(visual_run_manifest_sha256)
        if normalized_sha256 is None:
            raise ValueError("visual_evidence_export requires drawing_sha256")
        if normalized_manifest_sha256 is None:
            raise ValueError("visual_evidence_export requires visual_run_manifest_sha256")
        if approval is not None and not isinstance(approval, Mapping):
            raise ValueError("approval must be an object or null")

        manifest_path = Path(visual_run_manifest_path)
        manifest_raw_before, manifest_before, manifest_digest_before = _snapshot_vs_t3_manifest(
            manifest_path,
            drawing_full_path=normalized_path,
            run_id=run_id,
            latest_mutation_sha256=latest_mutation_sha256,
            expected_sha256=normalized_manifest_sha256,
        )
        register_snapshot: tuple[Path, bytes, str] | None = None
        datum_ids = _requested_datum_ids(measurements)
        if datum_ids:
            if dimension_register_path is None:
                raise ValueError(
                    "visual_evidence_export DATUM measurements require dimension_register_path"
                )
            register_path = Path(dimension_register_path)
            register_raw, register, register_digest = snapshot_dimension_register(register_path)
            source = manifest_before.get("source")
            if not isinstance(source, Mapping):
                raise ValueError("visual run manifest source scope is invalid")
            source_sha256 = source.get("source_sha256")
            page_ids = source.get("page_ids")
            if not isinstance(source_sha256, str) or not isinstance(page_ids, list):
                raise ValueError("visual run manifest source scope is invalid")
            parameters["datum_bindings"] = build_dimension_register_datum_bindings(
                register,
                datum_ids=datum_ids,
                run_id=run_id,
                region_id=region_id,
                manifest_sha256=normalized_manifest_sha256,
                register_sha256=register_digest,
                source_sha256=source_sha256,
                allowed_page_ids={page_id for page_id in page_ids if isinstance(page_id, str)},
            )
            register_snapshot = (register_path, register_raw, register_digest)

        normalized_parameters = self._validate_parameters("visual_evidence_export", parameters)
        self._validate_visual_evidence_datum_bindings(
            normalized_parameters,
            expected_run_id=run_id,
            expected_region_id=region_id,
            expected_manifest_sha256=normalized_manifest_sha256,
        )
        if register_snapshot is not None:
            _assert_dimension_register_snapshot(register_snapshot)

        request = {
            "request_id": actual_request_id,
            "schema_version": SCHEMA_VERSION,
            "operation": "visual_evidence_export",
            "drawing_full_path": normalized_path,
            "drawing_sha256": normalized_sha256,
            "parameters": normalized_parameters,
            "approval": dict(approval) if approval is not None else None,
        }
        request_file = request_path(self.ipc_dir, actual_request_id)
        result_file = result_path(self.ipc_dir, actual_request_id)
        result_file.unlink(missing_ok=True)
        try:
            atomic_write_json(request_file, request, max_bytes=self.max_read_bytes)
            if self.trigger is None:
                raise DotNetIPCError("File IPC requires an AutoCAD dispatcher trigger")
            self.trigger()
            result = self._poll_result(result_file, actual_request_id, "visual_evidence_export")
            if result["success"] is not True:
                errors = result.get("errors", [])
                message = "; ".join(str(error) for error in errors) if errors else "request failed"
                raise DotNetIPCResultError(message, result=result)
            artifact_paths = self._verify_visual_evidence_artifacts(
                result,
                actual_request_id,
                normalized_artifact_directory,
            )
            try:
                validate_visual_evidence_freshness(
                    result,
                    manifest_digest_before,
                    manifest_before,
                    normalized_sha256,
                )
            except VisualEvidenceError as exc:
                raise DotNetIPCProtocolError(str(exc)) from exc
            _assert_vs_t3_manifest_unchanged(manifest_path, manifest_raw_before, manifest_digest_before)
            if register_snapshot is not None:
                _assert_dimension_register_snapshot(register_snapshot)
            artifact_consumer(result, artifact_paths)
            _assert_vs_t3_manifest_unchanged(manifest_path, manifest_raw_before, manifest_digest_before)
            if register_snapshot is not None:
                _assert_dimension_register_snapshot(register_snapshot)
            return result
        finally:
            cleanup_request_files(self.ipc_dir, actual_request_id)
            self._cleanup_request_artifacts_if_lease_free(
                normalized_artifact_directory,
                actual_request_id,
            )

    @staticmethod
    def _validate_request_artifact_directory(artifact_directory: str, request_id: str) -> None:
        if not isinstance(artifact_directory, str):
            raise ValueError("artifact_directory must be a string")
        parts = artifact_directory.replace("\\", "/").split("/")
        if parts != ["artifacts", request_id]:
            raise ValueError("artifact_directory must be exactly artifacts/<request_id>")

    def _verify_visual_evidence_artifacts(
        self,
        result: Mapping[str, Any],
        request_id: str,
        artifact_directory: str,
    ) -> dict[str, Path]:
        payload = result.get("payload")
        if not isinstance(payload, Mapping):
            raise DotNetIPCProtocolError("visual evidence result payload must be an object")
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != 3:
            raise DotNetIPCProtocolError("visual evidence must contain exactly three artifacts")
        expected_root = (self.ipc_dir / "artifacts" / request_id).resolve()
        if _path_contains_windows_reparse_point(self.ipc_dir / "artifacts" / request_id):
            raise DotNetIPCProtocolError("visual evidence artifact directory must not be a symlink")
        if not expected_root.is_dir():
            raise DotNetIPCProtocolError("visual evidence artifact directory is missing")

        paths: dict[str, Path] = {}
        total_bytes = 0
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                raise DotNetIPCProtocolError("visual evidence artifact descriptor must be an object")
            kind = artifact.get("kind")
            if kind not in {"render", "entity_map", "measurements"}:
                raise DotNetIPCProtocolError("visual evidence artifact kind is unsupported")
            relative_path = artifact.get("relative_path")
            if not isinstance(relative_path, str):
                raise DotNetIPCProtocolError("visual evidence artifact path must be a string")
            relative_parts = relative_path.replace("\\", "/").split("/")
            if (
                any(part in {"", ".", ".."} for part in relative_parts)
                or relative_parts[:2] != ["artifacts", request_id]
                or len(relative_parts) < 3
            ):
                raise DotNetIPCProtocolError("visual evidence artifact path is unsafe or not request-owned")
            raw_path = self.ipc_dir / Path(*relative_parts)
            if _path_contains_windows_reparse_point(raw_path):
                raise DotNetIPCProtocolError("visual evidence artifact path contains a reparse point")
            path = raw_path.resolve()
            try:
                path.relative_to(expected_root)
            except ValueError as exc:
                raise DotNetIPCProtocolError("visual evidence artifact escapes request ownership") from exc
            if _path_contains_windows_reparse_point(path):
                raise DotNetIPCProtocolError("visual evidence artifact path contains a symlink")
            if not path.is_file():
                raise DotNetIPCProtocolError("visual evidence artifact file is missing")
            byte_length = artifact.get("byte_length")
            if type(byte_length) is not int or byte_length < 1 or byte_length > 32 * 1024 * 1024:
                raise DotNetIPCProtocolError("visual evidence artifact byte_length is invalid")
            max_bytes = 8 * 1024 * 1024 if kind == "render" else 8 * 1024 * 1024 if kind == "entity_map" else 4 * 1024 * 1024
            if byte_length > max_bytes:
                raise DotNetIPCProtocolError("visual evidence artifact exceeds its kind limit")
            data = path.read_bytes()
            if len(data) != byte_length:
                raise DotNetIPCProtocolError("visual evidence artifact byte length does not match its descriptor")
            digest = hashlib.sha256(data).hexdigest()
            if digest != artifact.get("sha256"):
                raise DotNetIPCProtocolError("visual evidence artifact SHA-256 does not match its descriptor")
            total_bytes += len(data)
            if total_bytes > 32 * 1024 * 1024:
                raise DotNetIPCProtocolError("visual evidence artifacts exceed the total byte limit")
            paths[kind] = path
        if set(paths) != {"render", "entity_map", "measurements"}:
            raise DotNetIPCProtocolError("visual evidence artifact kinds must be unique and complete")
        return paths

    def _cleanup_request_artifacts_if_lease_free(
        self,
        artifact_directory: str,
        request_id: str,
    ) -> None:
        try:
            self._validate_request_artifact_directory(artifact_directory, request_id)
            root = (self.ipc_dir / "artifacts" / request_id).resolve()
            if not root.is_dir() or _path_contains_windows_reparse_point(root):
                return
            lease = root / "active.lease"
            if lease.exists():
                return
            for child in root.iterdir():
                if _path_contains_windows_reparse_point(child):
                    return
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    # The exporter owns a flat directory. Refuse to recurse
                    # into an unexpected tree during best-effort cleanup.
                    return
            root.rmdir()
        except (FileNotFoundError, OSError, ValueError):
            # Cleanup is deliberately best-effort; the 24-hour scavenger is
            # responsible for orphaned lease-free directories.
            return

    def _poll_result(
        self,
        result_file: Path,
        request_id: str,
        operation: str,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_s
        while True:
            if result_file.is_file():
                result = read_json_bounded(result_file, max_bytes=self.max_read_bytes)
                self._validate_result(result, request_id, operation)
                return result

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DotNetIPCTimeoutError(
                    f"Timeout waiting for result (request_id={request_id})"
                )
            time.sleep(min(self.poll_interval_s, remaining))

    @staticmethod
    def _validate_operation(operation: str) -> str:
        if not isinstance(operation, str) or operation not in SUPPORTED_OPERATIONS:
            raise ValueError(f"unsupported operation: {operation!r}")
        return operation

    @staticmethod
    def _validate_drawing_path(
        operation: str,
        drawing_full_path: str | Path | None,
    ) -> str | None:
        if drawing_full_path is None:
            if operation != "health":
                raise ValueError("drawing_full_path may be null only for health")
            return None
        return normalize_windows_absolute_path(drawing_full_path)

    @staticmethod
    def _validate_sha256(drawing_sha256: str | None) -> str | None:
        if drawing_sha256 is not None and (
            not isinstance(drawing_sha256, str)
            or not _SHA256_PATTERN.fullmatch(drawing_sha256)
        ):
            raise ValueError("drawing_sha256 must be null or a 64-character hexadecimal SHA-256")
        return drawing_sha256

    @staticmethod
    def _validate_parameters(
        operation: str,
        parameters: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(parameters, Mapping):
            raise ValueError("parameters must be an object")
        values = dict(parameters)
        if operation == "health":
            if values:
                raise ValueError("health parameters must be an empty object")
        elif operation == "mechanical_bom":
            if values:
                raise ValueError("mechanical_bom parameters must be an empty object")
        elif operation == "drawing_setup_audit":
            if values:
                raise ValueError("drawing_setup_audit parameters must be an empty object")
        elif operation == "review":
            handles = values.get("handles")
            if not isinstance(handles, list) or not handles:
                raise ValueError("parameters.handles must be a non-empty array")
            if any(not isinstance(handle, str) or not handle.strip() for handle in handles):
                raise ValueError("parameters.handles must contain non-empty strings")
            if len(handles) != len(set(handles)):
                raise ValueError("parameters.handles must not contain duplicates")
            if set(values) != {"handles"}:
                raise ValueError("review parameters contain unsupported fields")
        elif operation == "close_disposable":
            if values != {"disposable": True, "save_changes": False}:
                raise ValueError(
                    "close_disposable requires disposable=true and save_changes=false"
                )
        elif operation == "visual_evidence_export":
            DotNetIPCClient._validate_visual_evidence_parameters(values)
        elif operation == "native_render_evidence":
            DotNetIPCClient._validate_native_render_parameters(values)
        elif operation == _EXACT_BASE_XREF_INSPECTION:
            DotNetIPCClient._validate_exact_base_xref_inspection_parameters(values)
        elif operation == _EXACT_BASE_XREF_EXTRACTION:
            DotNetIPCClient._validate_exact_base_xref_extraction_parameters(values)
        return values

    @staticmethod
    def _validate_offline_xref_inspection(payload: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return validate_xref_inspection(payload)
        except ExactBaseXrefError as exc:
            raise ValueError(str(exc)) from exc

    @staticmethod
    def _inspection_expectations(inspection: Mapping[str, Any]) -> dict[str, Any]:
        identity = {
            item["field"]: item["target"]
            for item in inspection["identity_observations"]
        }
        return {
            "source": {
                key: inspection["base_source"][key]
                for key in ("source_id", "revision", "sha256")
            },
            "identity": identity,
            "critical_dimensions": [
                {
                    "control": item["control"],
                    "target": item["target"],
                    "tolerance": item["tolerance"],
                    "unit": item["unit"],
                }
                for item in inspection["critical_dimensions"]
            ],
            "xref": {"name": inspection["xref"]["name"]},
            "components": [
                {
                    key: component[key]
                    for key in (
                        "component_type",
                        "logical_component_id",
                        "provenance",
                        "source_block",
                        "source_handle",
                        "source_layer",
                    )
                }
                for component in inspection["components"]
            ],
        }

    @staticmethod
    def _resolve_xref_identity(
        inspection: Mapping[str, Any],
        *,
        source_revision: str | None,
        run_id: str | None,
    ) -> tuple[str, str]:
        expected_revision = inspection["base_source"]["revision"]
        expected_run_id = inspection["run_id"]
        if source_revision is not None and source_revision != expected_revision:
            raise ValueError("source_revision does not match the offline inspection")
        if run_id is not None and run_id != expected_run_id:
            raise ValueError("run_id does not match the offline inspection")
        return expected_revision, expected_run_id

    @staticmethod
    def _validate_exact_base_xref_hash(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not _LOWERCASE_SHA256_PATTERN.fullmatch(value):
            raise ValueError(f"{field_name} must be a lowercase 64-character SHA-256")
        return value

    @staticmethod
    def _validate_exact_base_xref_paths(
        drawing_full_path: str | None,
        source_full_path: str | Path,
        *,
        candidate_output_path: str | Path | None,
    ) -> None:
        if drawing_full_path is None:
            raise ValueError("drawing_full_path is required for exact-base Xref operations")
        normalized_drawing = normalize_windows_absolute_path(drawing_full_path).casefold()
        normalized_source = normalize_windows_absolute_path(source_full_path).casefold()
        if normalized_source == normalized_drawing:
            raise ValueError("source_full_path must not equal drawing_full_path")
        if candidate_output_path is not None:
            normalized_output = normalize_windows_absolute_path(candidate_output_path).casefold()
            if normalized_output in {normalized_drawing, normalized_source}:
                raise ValueError(
                    "candidate_output_path must be distinct from drawing_full_path and source_full_path"
                )

    @staticmethod
    def _validate_exact_base_xref_expectations(expectations: Any) -> None:
        required = {"source", "identity", "critical_dimensions", "xref", "components"}
        if not isinstance(expectations, Mapping) or set(expectations) != required:
            raise ValueError("inspection_expectations must be a closed object")

        def reject_live_owned(value: Any, context: str) -> None:
            if isinstance(value, Mapping):
                for key, nested in value.items():
                    if key in _EXACT_BASE_XREF_LIVE_OWNED_FIELDS:
                        raise ValueError(f"{context}.{key} is live-owned and must not be supplied")
                    reject_live_owned(nested, f"{context}.{key}")
            elif isinstance(value, list):
                for index, nested in enumerate(value):
                    reject_live_owned(nested, f"{context}[{index}]")

        reject_live_owned(expectations, "inspection_expectations")
        if not isinstance(expectations["source"], Mapping) or set(expectations["source"]) != {
            "source_id",
            "revision",
            "sha256",
        }:
            raise ValueError("inspection_expectations.source is not closed")
        DotNetIPCClient._validate_exact_base_xref_hash(
            expectations["source"]["sha256"],
            "inspection_expectations.source.sha256",
        )
        for name in ("source_id", "revision"):
            if not isinstance(expectations["source"][name], str) or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(
                expectations["source"][name]
            ):
                raise ValueError(f"inspection_expectations.source.{name} is invalid")
        if not isinstance(expectations["identity"], Mapping) or set(expectations["identity"]) != {
            "vehicle",
            "model",
        }:
            raise ValueError("inspection_expectations.identity is not closed")
        for name in ("vehicle", "model"):
            if not isinstance(expectations["identity"][name], str) or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(
                expectations["identity"][name]
            ):
                raise ValueError(f"inspection_expectations.identity.{name} is invalid")
        dimensions = expectations["critical_dimensions"]
        if not isinstance(dimensions, list) or len(dimensions) != 5:
            raise ValueError("inspection_expectations.critical_dimensions must contain five controls")
        for dimension in dimensions:
            if not isinstance(dimension, Mapping) or set(dimension) != {
                "control",
                "target",
                "tolerance",
                "unit",
            }:
                raise ValueError("inspection_expectations.critical_dimensions entries are not closed")
        if not isinstance(expectations["xref"], Mapping) or set(expectations["xref"]) != {"name"}:
            raise ValueError("inspection_expectations.xref is not closed")
        components = expectations["components"]
        if not isinstance(components, list) or not components:
            raise ValueError("inspection_expectations.components must not be empty")
        component_fields = {
            "component_type",
            "logical_component_id",
            "provenance",
            "source_block",
            "source_handle",
            "source_layer",
        }
        for component in components:
            if not isinstance(component, Mapping) or set(component) != component_fields:
                raise ValueError("inspection_expectations.components entries are not closed")

    @staticmethod
    def _validate_exact_base_xref_inspection_parameters(parameters: Mapping[str, Any]) -> None:
        required = {
            "run_id",
            "source_full_path",
            "source_revision",
            "inspection_expectations",
            "target_role",
        }
        if set(parameters) != required:
            raise ValueError("exact_base_xref_inspection parameters must be closed")
        for name in ("run_id", "source_revision"):
            if not isinstance(parameters[name], str) or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(
                parameters[name]
            ):
                raise ValueError(f"parameters.{name} is invalid")
        normalize_windows_absolute_path(parameters["source_full_path"])
        if parameters["target_role"] != _EXACT_BASE_XREF_INSPECTION_TARGET_ROLE:
            raise ValueError("parameters.target_role must be INSPECTION_HOST")
        DotNetIPCClient._validate_exact_base_xref_expectations(
            parameters["inspection_expectations"]
        )

    @staticmethod
    def _validate_exact_base_xref_extraction_parameters(parameters: Mapping[str, Any]) -> None:
        required = {
            "run_id",
            "source_full_path",
            "source_revision",
            "inspection_expectations",
            "extraction_plan",
            "target_role",
            "candidate_output_path",
        }
        if set(parameters) != required:
            raise ValueError("exact_base_xref_extraction parameters must be closed")
        for name in ("run_id", "source_revision"):
            if not isinstance(parameters[name], str) or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(
                parameters[name]
            ):
                raise ValueError(f"parameters.{name} is invalid")
        normalize_windows_absolute_path(parameters["source_full_path"])
        normalize_windows_absolute_path(parameters["candidate_output_path"])
        if parameters["target_role"] != _EXACT_BASE_XREF_EXTRACTION_TARGET_ROLE:
            raise ValueError("parameters.target_role must be DISPOSABLE_CANDIDATE")
        DotNetIPCClient._validate_exact_base_xref_expectations(
            parameters["inspection_expectations"]
        )
        try:
            plan = validate_extraction_plan(parameters["extraction_plan"])
        except ExactBaseXrefError as exc:
            raise ValueError(str(exc)) from exc
        if plan["approval"]["status"] != "APPROVED" or not isinstance(
            plan["approval"]["reference"], str
        ):
            raise ValueError("extraction_plan.approval must be APPROVED with a reference")

    @staticmethod
    def _canonical_json(value: Any) -> str:
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("approval must contain canonical JSON values") from exc

    @staticmethod
    def _validate_exact_base_xref_approval(
        plan_approval: Any,
        envelope_approval: Mapping[str, Any] | None,
    ) -> None:
        if not isinstance(plan_approval, Mapping):
            raise ValueError("extraction_plan.approval is required")
        if plan_approval.get("status") != "APPROVED" or not isinstance(
            plan_approval.get("reference"), str
        ) or not plan_approval["reference"]:
            raise ValueError("extraction_plan.approval must be APPROVED with a reference")
        if not isinstance(envelope_approval, Mapping):
            raise ValueError("extraction approval must be an object")
        if DotNetIPCClient._canonical_json(dict(plan_approval)) != DotNetIPCClient._canonical_json(
            dict(envelope_approval)
        ):
            raise ValueError("extraction_plan.approval must exactly match envelope approval")

    @staticmethod
    def _validate_native_render_parameters(parameters: Mapping[str, Any]) -> None:
        required = {
            "run_id",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "layout",
            "artifact_kind",
            "render_options",
            "requested_at",
        }
        if set(parameters) != required:
            missing = sorted(required.difference(parameters))
            unsupported = sorted(set(parameters).difference(required))
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if unsupported:
                details.append("unsupported " + ", ".join(unsupported))
            raise ValueError("native_render_evidence parameters: " + "; ".join(details))

        candidate = {
            "schema_version": "autocad-native-render-request-1.0",
            "request_id": "native-render-request",
            "run_id": parameters["run_id"],
            "drawing_sha256": "a" * 64,
            "latest_mutation_sha256": parameters["latest_mutation_sha256"],
            "visual_run_manifest_sha256": parameters["visual_run_manifest_sha256"],
            "layout": parameters["layout"],
            "artifact_kind": parameters["artifact_kind"],
            "render_options": parameters["render_options"],
            "requested_at": parameters["requested_at"],
        }
        try:
            validate_render_request(candidate)
        except AutoCADRenderEvidenceError as exc:
            raise ValueError(str(exc)) from exc

    @staticmethod
    def _validate_visual_evidence_parameters(parameters: Mapping[str, Any]) -> None:
        required = {
            "run_id",
            "evidence_id",
            "region_id",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "artifact_policy_version",
            "artifact_directory",
            "region",
            "measurements",
            "datum_bindings",
        }
        if set(parameters) != required:
            missing = sorted(required.difference(parameters))
            unsupported = sorted(set(parameters).difference(required))
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if unsupported:
                details.append("unsupported " + ", ".join(unsupported))
            raise ValueError("visual_evidence_export parameters: " + "; ".join(details))

        for name in ("run_id", "evidence_id", "region_id"):
            value = parameters[name]
            if not isinstance(value, str) or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(value):
                raise ValueError(f"parameters.{name} must be a stable identifier")

        for name in ("latest_mutation_sha256", "visual_run_manifest_sha256"):
            value = parameters[name]
            if not isinstance(value, str) or not _LOWERCASE_SHA256_PATTERN.fullmatch(value):
                raise ValueError(f"parameters.{name} must be a lowercase SHA-256")

        if parameters["artifact_policy_version"] != _VS_T3_ARTIFACT_POLICY:
            raise ValueError(
                "parameters.artifact_policy_version must be vs-t3-artifacts-1"
            )
        artifact_directory = parameters["artifact_directory"]
        if (
            not isinstance(artifact_directory, str)
            or not artifact_directory
            or artifact_directory.startswith(("/", "\\"))
            or re.match(r"^[A-Za-z]:", artifact_directory)
            or any(part in ("", ".", "..") for part in artifact_directory.replace("\\", "/").split("/"))
        ):
            raise ValueError("parameters.artifact_directory must be a safe relative path")

        region = parameters["region"]
        if not isinstance(region, Mapping):
            raise ValueError("parameters.region must be an object")
        region_required = {
            "model_bbox_mm",
            "pixel_size",
            "background",
            "include_layers",
            "exclude_layers",
        }
        if set(region) != region_required:
            raise ValueError("parameters.region must be a closed object")
        bbox = region["model_bbox_mm"]
        if (
            not isinstance(bbox, list)
            or len(bbox) != 4
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in bbox)
        ):
            raise ValueError("parameters.region.model_bbox_mm must contain four numbers")
        pixel_size = region["pixel_size"]
        if (
            not isinstance(pixel_size, list)
            or len(pixel_size) != 2
            or any(type(value) is not int or not 1 <= value <= 8192 for value in pixel_size)
        ):
            raise ValueError("parameters.region.pixel_size must contain two positive integers")
        if region["background"] not in {"WHITE", "BLACK"}:
            raise ValueError("parameters.region.background is unsupported")
        for name in ("include_layers", "exclude_layers"):
            layers = region[name]
            if (
                not isinstance(layers, list)
                or any(not isinstance(layer, str) or not layer for layer in layers)
                or len(layers) != len(set(layers))
            ):
                raise ValueError(f"parameters.region.{name} must contain unique layer names")

        measurements = parameters["measurements"]
        if not isinstance(measurements, list) or len(measurements) > 10000:
            raise ValueError("parameters.measurements must be an array of at most 10000 items")
        measurement_ids: set[str] = set()
        for measurement in measurements:
            if not isinstance(measurement, Mapping):
                raise ValueError("parameters.measurements entries must be objects")
            allowed = {"id", "kind", "reference", "to_reference"}
            if set(measurement).difference(allowed) or not {"id", "kind", "reference"}.issubset(measurement):
                raise ValueError("parameters.measurements entries must be closed")
            identifier = measurement["id"]
            if not isinstance(identifier, str) or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(identifier):
                raise ValueError("parameters.measurements.id must be a stable identifier")
            if identifier in measurement_ids:
                raise ValueError("parameters.measurements ids must be unique")
            measurement_ids.add(identifier)
            if measurement["kind"] not in {"DISTANCE", "ANGLE", "RADIUS", "DIAMETER", "BOUNDING_BOX"}:
                raise ValueError("parameters.measurements.kind is unsupported")
            DotNetIPCClient._validate_visual_evidence_reference(measurement["reference"])
            if "to_reference" in measurement:
                DotNetIPCClient._validate_visual_evidence_reference(measurement["to_reference"])

        DotNetIPCClient._validate_visual_evidence_datum_bindings_shape(parameters["datum_bindings"])

        binding_ids = {
            binding["id"]
            for binding in parameters["datum_bindings"]
            if isinstance(binding, Mapping) and isinstance(binding.get("id"), str)
        }
        for measurement in measurements:
            for name in ("reference", "to_reference"):
                reference = measurement.get(name)
                if isinstance(reference, Mapping) and reference.get("type") == "DATUM":
                    if reference.get("id") not in binding_ids:
                        raise ValueError("measurement DATUM reference is not provenance-bound")


    @staticmethod
    def _validate_visual_evidence_reference(reference: Any) -> None:
        if not isinstance(reference, Mapping) or set(reference) != {"type", "id"}:
            raise ValueError("parameters.measurements references must be closed objects")
        if reference["type"] not in {"ENTITY", "DATUM"}:
            raise ValueError("parameters.measurements reference type is unsupported")
        if not isinstance(reference["id"], str) or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(reference["id"]):
            raise ValueError("parameters.measurements reference id must be a stable identifier")

    @staticmethod
    def _validate_visual_evidence_datum_bindings_shape(bindings: Any) -> None:
        if not isinstance(bindings, list) or len(bindings) > 10000:
            raise ValueError("parameters.datum_bindings must be an array of at most 10000 items")
        required = {
            "id",
            "entity_handle",
            "run_id",
            "region_id",
            "visual_run_manifest_sha256",
            "dimension_register_sha256",
            "dimension_id",
            "approval",
        }
        seen: set[str] = set()
        for binding in bindings:
            if not isinstance(binding, Mapping) or set(binding) != required:
                raise ValueError("parameters.datum_bindings entries must be closed provenance objects")
            for name in ("id", "entity_handle", "run_id", "region_id", "dimension_id"):
                value = binding[name]
                if not isinstance(value, str) or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(value):
                    raise ValueError(f"parameters.datum_bindings.{name} is invalid")
            for name in ("visual_run_manifest_sha256", "dimension_register_sha256"):
                value = binding[name]
                if not isinstance(value, str) or not _LOWERCASE_SHA256_PATTERN.fullmatch(value):
                    raise ValueError(f"parameters.datum_bindings.{name} must be a lowercase SHA-256")
            if binding["approval"] != "DIMENSION_REGISTER_CONFIRMED":
                raise ValueError("parameters.datum_bindings.approval is not approved")
            if binding["id"] in seen:
                raise ValueError("parameters.datum_bindings ids must be unique")
            seen.add(binding["id"])

    @staticmethod
    def _validate_visual_evidence_datum_bindings(
        parameters: Mapping[str, Any],
        *,
        expected_run_id: str,
        expected_region_id: str,
        expected_manifest_sha256: str,
    ) -> None:
        for binding in parameters["datum_bindings"]:
            if binding["run_id"] != expected_run_id:
                raise ValueError("parameters.datum_bindings.run_id does not match the request")
            if binding["region_id"] != expected_region_id:
                raise ValueError("parameters.datum_bindings.region_id does not match the request")
            if binding["visual_run_manifest_sha256"] != expected_manifest_sha256:
                raise ValueError(
                    "parameters.datum_bindings.visual_run_manifest_sha256 does not match the request"
                )

    @staticmethod
    def _validate_result(
        result: Any,
        request_id: str,
        operation: str,
    ) -> None:
        if not isinstance(result, dict):
            raise DotNetIPCProtocolError("result JSON must be an object")
        required = {
            "request_id",
            "success",
            "operation",
            "drawing_full_path",
            "changed",
            "entity_handles",
            "warnings",
            "errors",
            "started_at",
            "completed_at",
        }
        allowed = required | {"payload"}
        unsupported = sorted(set(result).difference(allowed))
        if unsupported:
            raise DotNetIPCProtocolError(
                "result JSON contains unsupported properties: " + ", ".join(unsupported)
            )
        missing = sorted(required.difference(result))
        if missing:
            raise DotNetIPCProtocolError(
                f"result JSON is missing required properties: {', '.join(missing)}"
            )
        if result["request_id"] != request_id:
            raise DotNetIPCProtocolError("result request_id does not match the requested id")
        if type(result["success"]) is not bool:
            raise DotNetIPCProtocolError("result success must be a boolean")
        if result["operation"] != operation:
            raise DotNetIPCProtocolError("result operation does not match the request")
        if result["drawing_full_path"] is not None:
            try:
                normalize_windows_absolute_path(result["drawing_full_path"])
            except ValueError as exc:
                raise DotNetIPCProtocolError(str(exc)) from exc
        elif operation != "health":
            raise DotNetIPCProtocolError("result drawing_full_path may be null only for health")
        if type(result["changed"]) is not bool:
            raise DotNetIPCProtocolError("result changed must be a boolean")
        for name in ("entity_handles", "warnings", "errors"):
            values = result[name]
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise DotNetIPCProtocolError(f"result {name} must be an array of strings")
        if operation == "drawing_setup_audit" and (
            result["changed"] is not False or result["entity_handles"]
        ):
            raise DotNetIPCProtocolError(
                "drawing_setup_audit result must be read-only and contain no entity handles"
            )
        if operation == "visual_evidence_export":
            if result["changed"] is not False or result["entity_handles"]:
                raise DotNetIPCProtocolError(
                    "visual_evidence_export result must be read-only and contain no entity handles"
                )
            if result["success"] is True:
                DotNetIPCClient._validate_visual_evidence_payload(result.get("payload"))
        if operation == "native_render_evidence":
            if result["changed"] is not False or result["entity_handles"]:
                raise DotNetIPCProtocolError(
                    "native_render_evidence result must be read-only and contain no entity handles"
                )
            if result["success"] is False and result.get("payload") not in (None, {}):
                raise DotNetIPCProtocolError(
                    "native_render_evidence failure result must not contain evidence payload"
                )
        if operation == _EXACT_BASE_XREF_INSPECTION:
            if result["changed"] is not False or result["entity_handles"]:
                raise DotNetIPCProtocolError(
                    "exact_base_xref_inspection result must be read-only and contain no entity handles"
                )
            if result["success"] is False and result.get("payload") not in (None, {}):
                raise DotNetIPCProtocolError(
                    "exact_base_xref_inspection failure result must not contain evidence payload"
                )
        if operation == _EXACT_BASE_XREF_EXTRACTION:
            if result["success"] is True:
                if result["changed"] is not True or not result["entity_handles"]:
                    raise DotNetIPCProtocolError(
                        "exact_base_xref_extraction success must contain candidate handles"
                    )
                if result["entity_handles"] != sorted(set(result["entity_handles"])):
                    raise DotNetIPCProtocolError(
                        "exact_base_xref_extraction candidate handles must be sorted and unique"
                    )
                if not isinstance(result.get("payload"), dict):
                    raise DotNetIPCProtocolError(
                        "exact_base_xref_extraction success requires an evidence payload"
                    )
            elif result["changed"] is not False or result["entity_handles"] or result.get("payload") not in (
                None,
                {},
            ):
                raise DotNetIPCProtocolError(
                    "exact_base_xref_extraction failure must be cleaned up and empty"
                )
        for name in ("started_at", "completed_at"):
            if not isinstance(result[name], str) or not result[name]:
                raise DotNetIPCProtocolError(f"result {name} must be a non-empty string")
        if "payload" in result and not isinstance(result["payload"], dict):
            raise DotNetIPCProtocolError("result payload must be an object")

    @staticmethod
    def _validate_exact_base_xref_inspection_result(
        result: Mapping[str, Any],
        *,
        validated_inspection: Mapping[str, Any],
        drawing_full_path: str,
        drawing_sha256: str,
        run_id: str,
    ) -> None:
        if result["drawing_full_path"].casefold() != drawing_full_path.casefold():
            raise DotNetIPCProtocolError(
                "exact_base_xref_inspection result drawing_full_path is not canonical"
            )
        try:
            payload = validate_xref_inspection(result.get("payload"))
        except ExactBaseXrefError as exc:
            raise DotNetIPCProtocolError(
                f"exact_base_xref_inspection payload is invalid: {exc}"
            ) from exc
        if payload["request_id"] != result["request_id"]:
            raise DotNetIPCProtocolError(
                "exact_base_xref_inspection payload request_id does not match result"
            )
        if payload["run_id"] != run_id:
            raise DotNetIPCProtocolError(
                "exact_base_xref_inspection payload run_id does not match request"
            )
        if payload["base_source"] != validated_inspection["base_source"]:
            raise DotNetIPCProtocolError(
                "exact_base_xref_inspection payload source identity does not match expectations"
            )
        if payload["target_drawing_sha256"] != drawing_sha256:
            raise DotNetIPCProtocolError(
                "exact_base_xref_inspection payload target hash does not match request"
            )

    @staticmethod
    def _validate_exact_base_xref_extraction_result(
        result: Mapping[str, Any],
        *,
        validated_inspection: Mapping[str, Any],
        validated_plan: Mapping[str, Any],
        drawing_full_path: str,
        drawing_sha256: str,
        candidate_output_path: str,
        run_id: str,
    ) -> None:
        payload = result.get("payload")
        if not isinstance(payload, Mapping):
            raise DotNetIPCProtocolError(
                "exact_base_xref_extraction result payload must be an object"
            )
        required = {
            "accepted_target_overwrite",
            "candidate_changed_during_operation",
            "candidate_input_path",
            "candidate_input_sha256",
            "candidate_output_path",
            "candidate_output_sha256",
            "components",
            "live_preflight",
            "plan_id",
            "request_id",
            "run_id",
            "save_performed",
            "schema_version",
            "source_handle_to_candidate_handle",
            "source_mutated",
            "source_revision",
            "source_saved",
            "source_sha256_after",
            "source_sha256_before",
            "warnings",
        }
        if set(payload) != required:
            raise DotNetIPCProtocolError(
                "exact_base_xref_extraction payload must be a closed evidence object"
            )
        if result["drawing_full_path"].casefold() != drawing_full_path.casefold():
            raise DotNetIPCProtocolError(
                "exact_base_xref_extraction result drawing_full_path is not canonical"
            )
        try:
            normalized_input = normalize_windows_absolute_path(payload["candidate_input_path"])
            normalized_output = normalize_windows_absolute_path(payload["candidate_output_path"])
            expected_source = validated_inspection["base_source"]["sha256"]
            candidate_input_hash = DotNetIPCClient._validate_exact_base_xref_hash(
                payload["candidate_input_sha256"],
                "candidate_input_sha256",
            )
            DotNetIPCClient._validate_exact_base_xref_hash(
                payload["candidate_output_sha256"],
                "candidate_output_sha256",
            )
            source_before = DotNetIPCClient._validate_exact_base_xref_hash(
                payload["source_sha256_before"],
                "source_sha256_before",
            )
            source_after = DotNetIPCClient._validate_exact_base_xref_hash(
                payload["source_sha256_after"],
                "source_sha256_after",
            )
        except (TypeError, ValueError) as exc:
            raise DotNetIPCProtocolError(
                f"exact_base_xref_extraction evidence path or hash is invalid: {exc}"
            ) from exc
        if normalized_input.casefold() != drawing_full_path.casefold():
            raise DotNetIPCProtocolError(
                "candidate_input_path does not match the active candidate drawing"
            )
        if normalized_output.casefold() != candidate_output_path.casefold():
            raise DotNetIPCProtocolError(
                "candidate_output_path does not match the request"
            )
        if candidate_input_hash != drawing_sha256:
            raise DotNetIPCProtocolError("candidate input hash does not match the request")
        if source_before != expected_source or source_after != expected_source:
            raise DotNetIPCProtocolError("source hash changed or does not match inspection")
        if payload["accepted_target_overwrite"] is not False:
            raise DotNetIPCProtocolError("accepted_target_overwrite must be false")
        if payload["candidate_changed_during_operation"] is not True:
            raise DotNetIPCProtocolError("candidate_changed_during_operation must be true")
        if payload["save_performed"] is not True:
            raise DotNetIPCProtocolError("save_performed must be true")
        if payload["source_mutated"] is not False or payload["source_saved"] is not False:
            raise DotNetIPCProtocolError("source must remain read-only")
        if payload["schema_version"] != "exact-base-xref-extraction-result-1.0":
            raise DotNetIPCProtocolError("extraction result schema_version is unsupported")
        if payload["request_id"] != result["request_id"] or payload["run_id"] != run_id:
            raise DotNetIPCProtocolError("extraction evidence identity does not match request")
        if payload["plan_id"] != validated_plan["plan_id"]:
            raise DotNetIPCProtocolError("extraction evidence plan_id does not match plan")
        if payload["source_revision"] != validated_plan["source_revision"]:
            raise DotNetIPCProtocolError("extraction evidence source revision does not match plan")

        preflight = payload["live_preflight"]
        if not isinstance(preflight, Mapping) or set(preflight) != {
            "dbmod_after",
            "dbmod_before",
            "eligible",
            "evidence_sha256",
            "inspection_id",
            "source_sha256",
            "target_drawing_sha256",
            "xref",
        }:
            raise DotNetIPCProtocolError("live_preflight evidence is not closed")
        if preflight["eligible"] is not True:
            raise DotNetIPCProtocolError("live_preflight must be eligible")
        if preflight["source_sha256"] != expected_source:
            raise DotNetIPCProtocolError("live_preflight source hash does not match inspection")
        if preflight["target_drawing_sha256"] != drawing_sha256:
            raise DotNetIPCProtocolError("live_preflight target hash does not match request")
        xref = preflight["xref"]
        if not isinstance(xref, Mapping) or xref.get("read_only") is not True or xref.get("status") != "INSPECTED":
            raise DotNetIPCProtocolError("live_preflight Xref is not inspected read-only")

        components = payload["components"]
        mappings = payload["source_handle_to_candidate_handle"]
        if not isinstance(components, list) or not components or not isinstance(mappings, list):
            raise DotNetIPCProtocolError("extraction evidence components and mappings are required")
        candidate_handles: list[str] = []
        component_pairs: set[tuple[str, str]] = set()
        for component in components:
            if not isinstance(component, Mapping):
                raise DotNetIPCProtocolError("component evidence must be an object")
            for name in (
                "candidate_handle",
                "logical_component_id",
                "provenance",
                "source_block",
                "source_handle",
                "source_layer",
                "source_revision",
                "source_sha256",
                "transform",
            ):
                if name not in component:
                    raise DotNetIPCProtocolError(f"component evidence is missing {name}")
            if component["provenance"] != "REUSED_FROM_BASE_CAD":
                raise DotNetIPCProtocolError("component provenance is not REUSED_FROM_BASE_CAD")
            if component["source_revision"] != validated_plan["source_revision"]:
                raise DotNetIPCProtocolError("component source revision does not match plan")
            if component["source_sha256"] != expected_source:
                raise DotNetIPCProtocolError("component source hash does not match inspection")
            candidate_handles.append(component["candidate_handle"])
            component_pairs.add((component["source_handle"], component["candidate_handle"]))
        if candidate_handles != result["entity_handles"]:
            raise DotNetIPCProtocolError("entity_handles do not match native candidate evidence")
        mapping_pairs: set[tuple[str, str]] = set()
        for mapping in mappings:
            if not isinstance(mapping, Mapping) or set(mapping) != {"source_handle", "candidate_handle"}:
                raise DotNetIPCProtocolError("source_handle_to_candidate_handle entries are not closed")
            mapping_pairs.add((mapping["source_handle"], mapping["candidate_handle"]))
        if mapping_pairs != component_pairs:
            raise DotNetIPCProtocolError("source_handle_to_candidate_handle is incomplete or inconsistent")

    @staticmethod
    def _validate_visual_evidence_payload(payload: Any) -> None:
        if not isinstance(payload, Mapping):
            raise DotNetIPCProtocolError("visual_evidence_export payload must be an object")
        required = {
            "run_id",
            "evidence_id",
            "region_id",
            "drawing_sha256_before",
            "drawing_sha256_after",
            "dbmod_before",
            "dbmod_after",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "region_config_sha256",
            "session_state_sha256_before",
            "session_state_sha256_after",
            "transient_state_restored",
            "captured_at_utc",
            "artifacts",
        }
        if set(payload) != required:
            raise DotNetIPCProtocolError("visual_evidence_export payload must be a closed object")
        for name in ("run_id", "evidence_id", "region_id"):
            if not isinstance(payload[name], str) or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(payload[name]):
                raise DotNetIPCProtocolError(f"visual evidence payload {name} is invalid")
        for name in (
            "drawing_sha256_before",
            "drawing_sha256_after",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "region_config_sha256",
            "session_state_sha256_before",
            "session_state_sha256_after",
        ):
            if not isinstance(payload[name], str) or not _LOWERCASE_SHA256_PATTERN.fullmatch(payload[name]):
                raise DotNetIPCProtocolError(f"visual evidence payload {name} is invalid")
        if payload["drawing_sha256_before"] != payload["drawing_sha256_after"]:
            raise DotNetIPCProtocolError("visual evidence drawing hashes must be equal")
        if payload["dbmod_before"] != payload["dbmod_after"]:
            raise DotNetIPCProtocolError("visual evidence DBMOD values must be equal")
        if payload["session_state_sha256_before"] != payload["session_state_sha256_after"]:
            raise DotNetIPCProtocolError("visual evidence session-state hashes must be equal")
        if payload["transient_state_restored"] is not True:
            raise DotNetIPCProtocolError("visual evidence transient state was not restored")
        if (
            not isinstance(payload["captured_at_utc"], str)
            or not _VS_T3_CAPTURED_AT_PATTERN.fullmatch(payload["captured_at_utc"])
        ):
            raise DotNetIPCProtocolError("visual evidence captured_at_utc must be RFC3339 UTC")
        artifacts = payload["artifacts"]
        if not isinstance(artifacts, list) or len(artifacts) != 3:
            raise DotNetIPCProtocolError("visual evidence must contain exactly three artifacts")
        kinds: set[str] = set()
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                raise DotNetIPCProtocolError("visual evidence artifacts must be objects")
            artifact_required = {
                "artifact_id",
                "kind",
                "relative_path",
                "sha256",
                "byte_length",
                "mime_type",
            }
            if set(artifact).difference(artifact_required | {"width", "height"}) or not artifact_required.issubset(artifact):
                raise DotNetIPCProtocolError("visual evidence artifact descriptor must be closed")
            if artifact["kind"] not in {"render", "entity_map", "measurements"}:
                raise DotNetIPCProtocolError("visual evidence artifact kind is unsupported")
            if artifact["kind"] in kinds:
                raise DotNetIPCProtocolError("visual evidence artifact kinds must be unique")
            kinds.add(artifact["kind"])
            if (
                not isinstance(artifact["artifact_id"], str)
                or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(artifact["artifact_id"])
            ):
                raise DotNetIPCProtocolError("visual evidence artifact_id is invalid")
            relative_path = artifact["relative_path"]
            if (
                not isinstance(relative_path, str)
                or not relative_path
                or relative_path.startswith(("/", "\\"))
                or re.match(r"^[A-Za-z]:", relative_path)
                or any(part in ("", ".", "..") for part in relative_path.replace("\\", "/").split("/"))
            ):
                raise DotNetIPCProtocolError("visual evidence artifact path is unsafe")
            if not isinstance(artifact["sha256"], str) or not _LOWERCASE_SHA256_PATTERN.fullmatch(artifact["sha256"]):
                raise DotNetIPCProtocolError("visual evidence artifact hash is invalid")
            if type(artifact["byte_length"]) is not int or not 1 <= artifact["byte_length"] <= 33554432:
                raise DotNetIPCProtocolError("visual evidence artifact byte_length is invalid")
            if artifact["mime_type"] not in {"image/png", "application/json"}:
                raise DotNetIPCProtocolError("visual evidence artifact MIME type is unsupported")


__all__ = [
    "DEFAULT_IPC_DIR",
    "DEFAULT_MAX_READ_BYTES",
    "DotNetIPCClient",
    "DotNetIPCError",
    "DotNetIPCProtocolError",
    "DotNetIPCResultError",
    "DotNetIPCTimeoutError",
    "IPC_DIR_ENV_VAR",
    "JSON_SUFFIX",
    "MAX_REQUEST_ID_LENGTH",
    "REQUEST_PREFIX",
    "RESULT_PREFIX",
    "SCHEMA_VERSION",
    "SUPPORTED_OPERATIONS",
    "atomic_write_json",
    "cleanup_request_files",
    "get_ipc_dir",
    "get_request_file_name",
    "get_request_file_path",
    "get_result_file_name",
    "get_result_file_path",
    "make_windows_dotnet_dispatch_trigger",
    "normalize_request_id",
    "normalize_windows_absolute_path",
    "read_json_bounded",
    "request_filename",
    "request_path",
    "result_filename",
    "result_path",
]
