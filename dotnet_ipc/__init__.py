"""Isolated Python backend for the AutoCAD Managed .NET File IPC contract."""

from .client import (
    DotNetIPCClient,
    DotNetIPCError,
    DotNetIPCProtocolError,
    DotNetIPCResultError,
    DotNetIPCTimeoutError,
)
from .paths import (
    DEFAULT_IPC_DIR,
    DEFAULT_MAX_READ_BYTES,
    REQUEST_PREFIX,
    RESULT_PREFIX,
    SCHEMA_VERSION,
    atomic_write_json,
    cleanup_request_files,
    get_ipc_dir,
    normalize_request_id,
    normalize_windows_absolute_path,
    read_json_bounded,
    request_filename,
    request_path,
    result_filename,
    result_path,
)

__all__ = [
    "DEFAULT_IPC_DIR",
    "DEFAULT_MAX_READ_BYTES",
    "DotNetIPCClient",
    "DotNetIPCError",
    "DotNetIPCProtocolError",
    "DotNetIPCResultError",
    "DotNetIPCTimeoutError",
    "REQUEST_PREFIX",
    "RESULT_PREFIX",
    "SCHEMA_VERSION",
    "atomic_write_json",
    "cleanup_request_files",
    "get_ipc_dir",
    "normalize_request_id",
    "normalize_windows_absolute_path",
    "read_json_bounded",
    "request_filename",
    "request_path",
    "result_filename",
    "result_path",
]
