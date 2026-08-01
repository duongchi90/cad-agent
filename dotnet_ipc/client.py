"""Bounded Python client for the isolated AutoCAD .NET file IPC protocol."""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .paths import (
    DEFAULT_MAX_READ_BYTES,
    SCHEMA_VERSION,
    atomic_write_json,
    cleanup_request_files,
    get_ipc_dir,
    normalize_request_id,
    normalize_windows_absolute_path,
    read_json_bounded,
    request_path,
    result_path,
)

SUPPORTED_OPERATIONS = frozenset({"health", "review", "close_disposable"})
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


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
        return values

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
        for name in ("started_at", "completed_at"):
            if not isinstance(result[name], str) or not result[name]:
                raise DotNetIPCProtocolError(f"result {name} must be a non-empty string")
        if "payload" in result and not isinstance(result["payload"], dict):
            raise DotNetIPCProtocolError("result payload must be an object")


__all__ = [
    "DotNetIPCClient",
    "DotNetIPCError",
    "DotNetIPCProtocolError",
    "DotNetIPCResultError",
    "DotNetIPCTimeoutError",
    "SUPPORTED_OPERATIONS",
]
