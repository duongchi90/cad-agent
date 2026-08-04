"""Bounded Python client and file helpers for the isolated .NET IPC protocol."""

from __future__ import annotations

import ctypes
import hashlib
import json
import ntpath
import os
import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from ctypes import wintypes
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
DEFAULT_IPC_DIR = Path(r"C:\temp")
IPC_DIR_ENV_VAR = "CAD_AGENT_DOTNET_IPC_DIR"
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
    }
)
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_WM_CHAR = 0x0102
_DOTNET_DISPATCH_COMMAND = "\x1b\x1bCADAGENT_DISPATCH\r"


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
        if approval is not None and not isinstance(approval, Mapping):
            raise ValueError("approval must be an object or null")

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
        region: Mapping[str, Any],
        measurements: Sequence[Mapping[str, Any]],
        artifact_consumer: Callable[[Mapping[str, Any], Mapping[str, Path]], None] | None = None,
        artifact_directory: str | None = None,
        approval: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Capture bounded read-only evidence and hand verified artifacts to a consumer.

        The .NET side retains the request-owned artifact directory until this
        method has validated and optionally copied every artifact.  The
        callback is therefore the handoff boundary for the later atomic
        evidence writer; it runs before Python removes the request-owned
        directory.  A timeout never implies that AutoCAD stopped working, so
        an active lease protects the directory from cleanup.
        """

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
        }
        normalized_path = self._validate_drawing_path("visual_evidence_export", drawing_full_path)
        normalized_sha256 = self._validate_sha256(drawing_sha256)
        normalized_parameters = self._validate_parameters("visual_evidence_export", parameters)
        if normalized_sha256 is None:
            raise ValueError("visual_evidence_export requires drawing_sha256")
        if approval is not None and not isinstance(approval, Mapping):
            raise ValueError("approval must be an object or null")

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
            if artifact_consumer is not None:
                artifact_consumer(result, artifact_paths)
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
        if expected_root.exists() and expected_root.is_symlink():
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
            path = (self.ipc_dir / Path(*relative_parts)).resolve()
            try:
                path.relative_to(expected_root)
            except ValueError as exc:
                raise DotNetIPCProtocolError("visual evidence artifact escapes request ownership") from exc
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
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
            if not root.is_dir() or root.is_symlink():
                return
            lease = root / "active.lease"
            if lease.exists():
                return
            for child in root.iterdir():
                if child.is_symlink() or child.is_file():
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
        return values

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

    @staticmethod
    def _validate_visual_evidence_reference(reference: Any) -> None:
        if not isinstance(reference, Mapping) or set(reference) != {"type", "id"}:
            raise ValueError("parameters.measurements references must be closed objects")
        if reference["type"] not in {"ENTITY", "DATUM"}:
            raise ValueError("parameters.measurements reference type is unsupported")
        if not isinstance(reference["id"], str) or not _VS_T3_IDENTIFIER_PATTERN.fullmatch(reference["id"]):
            raise ValueError("parameters.measurements reference id must be a stable identifier")

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
            DotNetIPCClient._validate_visual_evidence_payload(result.get("payload"))
        for name in ("started_at", "completed_at"):
            if not isinstance(result[name], str) or not result[name]:
                raise DotNetIPCProtocolError(f"result {name} must be a non-empty string")
        if "payload" in result and not isinstance(result["payload"], dict):
            raise DotNetIPCProtocolError("result payload must be an object")

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
