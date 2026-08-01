"""Paths and bounded JSON file operations for the isolated .NET IPC protocol."""

from __future__ import annotations

import json
import ntpath
import os
import re
import uuid
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


__all__ = [
    "DEFAULT_IPC_DIR",
    "DEFAULT_MAX_READ_BYTES",
    "IPC_DIR_ENV_VAR",
    "JSON_SUFFIX",
    "MAX_REQUEST_ID_LENGTH",
    "REQUEST_PREFIX",
    "RESULT_PREFIX",
    "SCHEMA_VERSION",
    "atomic_write_json",
    "cleanup_request_files",
    "get_ipc_dir",
    "get_request_file_name",
    "get_request_file_path",
    "get_result_file_name",
    "get_result_file_path",
    "normalize_request_id",
    "normalize_windows_absolute_path",
    "read_json_bounded",
    "request_filename",
    "request_path",
    "result_filename",
    "result_path",
]
