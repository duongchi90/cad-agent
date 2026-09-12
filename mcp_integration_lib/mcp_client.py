"""Transport-independent adapter for the AutoCAD MCP operations used in Phase 4."""
from __future__ import annotations

import base64
import json
import ctypes
from ctypes import wintypes
import ntpath
import os
import re
import secrets
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol


class MCPTimeoutError(RuntimeError):
    """An MCP operation timed out."""


class MCPToolError(RuntimeError):
    """An MCP operation failed."""


@dataclass(frozen=True)
class BootstrapTimingEvent:
    """One privacy-safe monotonic timestamp from the disposable bootstrap path."""

    name: str
    monotonic_s: float


class BootstrapTimingRecorder:
    """Collect optional bootstrap timing without affecting runtime behavior."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._events: List[BootstrapTimingEvent] = []

    def record(self, event_name: str) -> None:
        self._events.append(
            BootstrapTimingEvent(
                name=event_name,
                monotonic_s=float(self._clock()),
            )
        )

    def record_once(self, event_name: str) -> None:
        if any(event.name == event_name for event in self._events):
            return
        self.record(event_name)

    @property
    def events(self) -> tuple[BootstrapTimingEvent, ...]:
        return tuple(self._events)


def _record_bootstrap_timing(
    recorder: Optional[BootstrapTimingRecorder], event_name: str
) -> None:
    """Best-effort observability must never change the bootstrap outcome."""
    if recorder is None:
        return
    try:
        recorder.record(event_name)
    except Exception:
        pass


def _record_bootstrap_timing_once(
    recorder: Optional[BootstrapTimingRecorder], event_name: str
) -> None:
    """Record a shared transition once while keeping observation best effort."""
    if recorder is None:
        return
    try:
        record_once = getattr(recorder, "record_once", None)
        if callable(record_once):
            record_once(event_name)
        else:
            recorder.record(event_name)
    except Exception:
        pass


def _normalized_autocad_path(path: str) -> str:
    """Normalize an AutoCAD Windows document path for identity comparison."""
    return ntpath.normpath(path.replace("/", "\\")).casefold()


class MCPClient(Protocol):
    def drawing_open(self, path: str) -> Dict[str, Any]: ...
    def drawing_close(self, save_changes: bool = False) -> None: ...
    def drawing_list_open_paths(self) -> List[str]: ...
    def drawing_save(self, path: Optional[str] = None) -> None: ...
    def drawing_save_as_dxf(self, path: str) -> None: ...
    def drawing_get_variables(self, names: List[str]) -> Dict[str, Any]: ...
    def block_get_attributes(self, entity_id: str) -> Dict[str, str]: ...
    def block_update_attribute(self, entity_id: str, tag: str, value: str) -> None: ...
    def entity_create_line(self, x1: float, y1: float, x2: float, y2: float, layer: Optional[str] = None) -> Dict[str, Any]: ...
    def entity_create_circle(self, cx: float, cy: float, radius: float, layer: Optional[str] = None) -> Dict[str, Any]: ...
    def entity_create_arc(self, cx: float, cy: float, radius: float, start_angle: float, end_angle: float, layer: Optional[str] = None) -> Dict[str, Any]: ...
    def annotation_create_text(self, x: float, y: float, text: str, height: Optional[float] = None, rotation: Optional[float] = None, layer: Optional[str] = None) -> Dict[str, Any]: ...
    def entity_list(self, layer: Optional[str] = None) -> List[Dict[str, Any]]: ...
    def entity_get(self, entity_id: str) -> Dict[str, Any]: ...
    def entity_erase(self, entity_id: str) -> None: ...


@dataclass
class _FakeEntity:
    handle: str
    dxftype: str
    layer: str
    geom: Dict[str, Any]


class FakeMCPClient:
    """In-memory AutoCAD stand-in for deterministic Phase 4 tests and demos."""
    def __init__(self, fail_entity_get: bool = True) -> None:
        self._entities: Dict[str, _FakeEntity] = {}
        self._next_handle = 0x300
        self.opened_path: Optional[str] = None
        self.closed_without_save = False
        self._open_paths: set[str] = set()
        self.fail_entity_get = fail_entity_get

    def _new_handle(self) -> str:
        handle = format(self._next_handle, "X")
        self._next_handle += 1
        return handle

    def preload_entity(self, handle: str, dxftype: str, layer: str, geom: Dict[str, Any]) -> None:
        self._entities[handle] = _FakeEntity(handle, dxftype, layer, geom)

    def drawing_open(self, path: str) -> Dict[str, Any]:
        self.opened_path = path
        self._open_paths.add(_normalized_autocad_path(path))
        return {"ok": True, "payload": {"path": path, "entity_count": len(self._entities)}}

    def drawing_close(self, save_changes: bool = False) -> None:
        self.closed_without_save = not save_changes
        if self.opened_path is not None:
            self._open_paths.discard(_normalized_autocad_path(self.opened_path))
        self.opened_path = None

    def drawing_list_open_paths(self) -> List[str]:
        return sorted(self._open_paths)

    def drawing_save(self, path: Optional[str] = None) -> None: pass

    def drawing_save_as_dxf(self, path: str) -> None: self.drawing_save(path)

    def drawing_get_variables(self, names: List[str]) -> Dict[str, Any]:
        return {name: None for name in names}

    def block_get_attributes(self, entity_id: str) -> Dict[str, str]:
        entity = self._entities.get(entity_id)
        return dict(entity.geom.get("attributes", {})) if entity is not None else {}

    def block_update_attribute(self, entity_id: str, tag: str, value: str) -> None:
        entity = self._entities.get(entity_id)
        if entity is None:
            raise MCPToolError(f"entity {entity_id!r} does not exist")
        entity.geom.setdefault("attributes", {})[tag] = value

    def entity_list(self, layer: Optional[str] = None) -> List[Dict[str, Any]]:
        return [{"type": entity.dxftype, "handle": entity.handle, "layer": entity.layer}
                for entity in self._entities.values() if layer is None or layer == entity.layer]

    def entity_get(self, entity_id: str) -> Dict[str, Any]:
        if self.fail_entity_get:
            raise MCPTimeoutError(f"Timeout waiting for entity:get {entity_id}")
        entity = self._entities.get(entity_id)
        if entity is None:
            raise MCPToolError(f"entity {entity_id!r} does not exist")
        return {"handle": entity.handle, "type": entity.dxftype, "layer": entity.layer, **entity.geom}

    def entity_erase(self, entity_id: str) -> None:
        self._entities.pop(entity_id, None)

    def _create(self, dxftype: str, layer: Optional[str], geom: Dict[str, Any]) -> Dict[str, Any]:
        handle = self._new_handle()
        self._entities[handle] = _FakeEntity(handle, dxftype, layer or "0", geom)
        return {"entity_type": dxftype, "handle": handle}

    def entity_create_line(self, x1, y1, x2, y2, layer=None):
        return self._create("LINE", layer, {"start": (x1, y1), "end": (x2, y2)})
    def entity_create_circle(self, cx, cy, radius, layer=None):
        return self._create("CIRCLE", layer, {"center": (cx, cy), "radius": radius})
    def entity_create_arc(self, cx, cy, radius, start_angle, end_angle, layer=None):
        return self._create("ARC", layer, {"center": (cx, cy), "radius": radius, "start_angle_deg": start_angle, "end_angle_deg": end_angle})
    def annotation_create_text(self, x, y, text, height=None, rotation=None, layer=None):
        return self._create("TEXT", layer, {"insert": (x, y), "content": text, "height": height, "rotation_deg": rotation})
    def tamper(self, handle: str, **overrides: Any) -> None:
        self._entities[handle].geom.update(overrides)


_FILE_IPC_MAX_JSON_BYTES = 1024 * 1024
_FILE_IPC_REQUEST_PREFIX = "autocad_mcp_cmd_"
_FILE_IPC_RESULT_PREFIX = "autocad_mcp_result_"
_FILE_IPC_ALLOWED_COMMANDS = frozenset({
    "ping",
    "entity-list",
    "drawing-open",
    "drawing-save",
    "drawing-close",
    "drawing-list-open-paths",
    "drawing-save-as-dxf",
    "drawing-get-variables",
    "block-get-attributes",
    "block-update-attribute",
    "entity-get",
    "entity-erase",
    "create-line",
    "create-circle",
    "create-arc",
    "create-text",
})


def _file_ipc_path_has_reparse_point(path: Path) -> bool:
    chain = [path, *path.parents]
    if os.name == "nt":
        get_attrs = ctypes.windll.kernel32.GetFileAttributesW
        get_attrs.argtypes = [ctypes.c_wchar_p]
        get_attrs.restype = ctypes.c_uint32
        for component in chain:
            attrs = get_attrs(str(component))
            if attrs != 0xFFFFFFFF and attrs & 0x400:
                return True
        return False
    return any(component.is_symlink() for component in chain)


def _validate_file_ipc_root(value: str) -> Path:
    if not isinstance(value, str) or not value or any(ord(ch) < 32 for ch in value):
        raise ValueError("IPC_ROOT_INVALID")
    win_value = value.replace("/", "\\")
    drive, tail = ntpath.splitdrive(win_value)
    windows_looking = (
        os.name == "nt"
        or bool(drive)
        or value.startswith("\\\\")
        or value.startswith("//")
    )
    if windows_looking:
        if win_value.startswith("\\\\") or not drive or not tail.startswith("\\"):
            raise ValueError("IPC_ROOT_INVALID")
        normalized = ntpath.normpath(win_value)
        if normalized != win_value:
            raise ValueError("IPC_ROOT_INVALID")
        root = Path(normalized)
        if os.name != "nt":
            raise ValueError("IPC_ROOT_INVALID")
    else:
        root = Path(value)
        if not root.is_absolute() or os.path.normpath(value) != value:
            raise ValueError("IPC_ROOT_INVALID")
    if not root.exists() or not root.is_dir() or _file_ipc_path_has_reparse_point(root):
        raise ValueError("IPC_ROOT_INVALID")
    return root


def _file_ipc_root_identity(path: Path) -> tuple[int, int]:
    stat_result = os.stat(path, follow_symlinks=False)
    return (stat_result.st_dev, stat_result.st_ino)


def _strict_file_ipc_json_object(raw: bytes, *, error_code: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")

        def pairs_hook(pairs):
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate key")
                value[key] = item
            return value

        data = json.loads(text, object_pairs_hook=pairs_hook)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise MCPToolError(error_code) from exc
    if not isinstance(data, dict):
        raise MCPToolError(error_code)
    return data


def _validate_file_ipc_result(
    data: dict[str, Any], request_id: str, claim: Optional[str] = None
) -> dict[str, Any]:
    if data.get("request_id") != request_id or type(data.get("ok")) is not bool:
        raise MCPToolError("IPC_RESULT_INVALID")
    if claim is None:
        if "claim" in data:
            raise MCPToolError("IPC_RESULT_INVALID")
    elif data.get("claim") != claim:
        raise MCPToolError("IPC_RESULT_INVALID")
    if data["ok"] is True:
        expected_keys = {"request_id", "ok", "payload"}
        if claim is not None:
            expected_keys.add("claim")
        if (
            set(data) != expected_keys
            or not isinstance(data["payload"], dict)
        ):
            raise MCPToolError("IPC_RESULT_INVALID")
        return data["payload"]
    expected_keys = {"request_id", "ok", "error"}
    if claim is not None:
        expected_keys.add("claim")
    if (
        set(data) != expected_keys
        or not isinstance(data["error"], str)
        or not data["error"]
    ):
        raise MCPToolError("IPC_RESULT_INVALID")
    raise MCPToolError(data["error"])


def _autolisp_string_literal(value: str) -> str:
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("IPC_ROOT_INVALID")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


_START_TAB_BOOTSTRAP_COMPLETION_TOKEN = "CAD_AGENT_START_TAB_BOOTSTRAP_COMPLETE"
_START_TAB_BOOTSTRAP_COMPLETION_MARKER_SUFFIX = ".marker"
_START_TAB_EVALUATOR_ENTRY_TOKEN = "CAD_AGENT_START_TAB_EVALUATOR_ENTRY"
_START_TAB_EVALUATOR_ENTRY_MARKER_SUFFIX = ".evaluator-entry"
_START_TAB_STAGE_MARKERS = (
    ("post_qnew_entry", "CAD_AGENT_START_TAB_POST_QNEW_ENTRY"),
    ("netload_return", "CAD_AGENT_START_TAB_NETLOAD_RETURN"),
    ("dispatcher_load_return", "CAD_AGENT_START_TAB_DISPATCHER_LOAD_RETURN"),
    (
        "completion_marker_writer_return",
        "CAD_AGENT_START_TAB_COMPLETION_MARKER_WRITER_RETURN",
    ),
)


def _start_tab_completion_marker_path(
    script_path: Path, ipc_root: Optional[Path]
) -> Path:
    """Resolve the unique completion marker inside the exact owned root."""
    if ipc_root is not None:
        return ipc_root / (
            f"{script_path.stem}{_START_TAB_BOOTSTRAP_COMPLETION_MARKER_SUFFIX}"
        )
    return script_path.with_suffix(_START_TAB_BOOTSTRAP_COMPLETION_MARKER_SUFFIX)


def _start_tab_completion_marker_expression(marker_path: Path) -> str:
    """Build the canonical AutoLISP marker writer proven by live diagnostics."""
    return _start_tab_stage_marker_expression(
        marker_path, _START_TAB_BOOTSTRAP_COMPLETION_TOKEN
    )


def _start_tab_evaluator_entry_marker_path(
    script_path: Path, ipc_root: Path
) -> Path:
    """Resolve the unique evaluator-entry marker inside the exact owned root."""
    return ipc_root / (
        f"{script_path.stem}{_START_TAB_EVALUATOR_ENTRY_MARKER_SUFFIX}"
    )


def _start_tab_evaluator_entry_marker_expression(marker_path: Path) -> str:
    """Build the fixed-token marker for startup evaluator entry."""
    return _start_tab_stage_marker_expression(
        marker_path, _START_TAB_EVALUATOR_ENTRY_TOKEN
    )


def _start_tab_stage_marker_expression(marker_path: Path, token: str) -> str:
    """Build a fixed-token, same-root stage marker writer."""
    marker_literal = _autolisp_string_literal(
        str(marker_path).replace("\\", "/")
    )
    token_literal = _autolisp_string_literal(token)
    return (
        "(progn (setq cad-agent-stage-file (open "
        + marker_literal
        + ' "w")) (if cad-agent-stage-file (progn (write-line '
        + token_literal
        + " cad-agent-stage-file) (close cad-agent-stage-file))))"
    )


def _start_tab_stage_marker_paths(
    script_path: Path, ipc_root: Optional[Path]
) -> tuple[tuple[str, Path, str], ...]:
    if ipc_root is None:
        return ()
    root = ipc_root
    return tuple(
        (
            event_name,
            root / f"{script_path.stem}.stage-{event_name.replace('_', '-')}",
            token,
        )
        for event_name, token in _START_TAB_STAGE_MARKERS
    )


_RAW_LISP_DRAWING_OPEN_ACK_TOKEN = "CAD_AGENT_DRAWING_OPEN_RECEIVER_EVALUATED"
_RAW_LISP_DRAWING_OPEN_ACK_PREFIX = "autocad_mcp_drawing_open_ack_"
_RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED = (
    "RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED"
)


@dataclass(frozen=True)
class WindowsStartTabBootstrapBindings:
    """Window-bound triggers and probes for an owned AutoCAD session."""

    hwnd: int
    command_trigger: Callable[[str], None]
    raw_lisp_trigger: Callable[[str], None]
    dispatch_trigger: Callable[[], None]
    start_tab_no_document_probe: Callable[[], bool]
    document_ready_probe: Callable[[], bool]
    dispatcher_preloaded: bool = False
    bootstrap_completion_confirmed: bool = False


class WindowsAutoCADStartTabSession:
    """Own a disposable AutoCAD startup-script session for Start-tab bootstrap."""

    def __init__(
        self,
        acad_executable: str,
        script_directory: str,
        *,
        timeout_s: float = 30.0,
        poll_interval_s: float = 0.1,
        process_launcher: Optional[Callable[[Path, Path], Any]] = None,
        window_finder: Optional[Callable[[int], int]] = None,
        window_closer: Optional[Callable[[int], None]] = None,
        bootstrap_plugin_path: Optional[str] = None,
        bootstrap_lisp_path: Optional[str] = None,
        ipc_root: Optional[str] = None,
        start_probe_factory: Optional[Callable[[int], Callable[[], bool]]] = None,
        document_ready_probe_factory: Optional[
            Callable[[int], Callable[[], bool]]
        ] = None,
        bindings_factory: Optional[
            Callable[[int], WindowsStartTabBootstrapBindings]
        ] = None,
        timing_recorder: Optional[BootstrapTimingRecorder] = None,
        stage_timing_enabled: bool = False,
    ) -> None:
        executable = Path(acad_executable).resolve()
        script_root = Path(script_directory).resolve()
        if executable.name.casefold() != "acad.exe":
            raise ValueError("acad_executable must name acad.exe")
        if not script_root.is_dir():
            raise ValueError("script_directory must be an existing directory")
        if timeout_s < 0 or poll_interval_s < 0:
            raise ValueError("session timeouts must not be negative")
        if type(stage_timing_enabled) is not bool:
            raise ValueError("stage_timing_enabled must be a bool")
        self._acad_executable = executable
        self._script_directory = script_root
        self._timeout_s = timeout_s
        self._poll_interval_s = poll_interval_s
        self._process_launcher = process_launcher or _launch_windows_autocad_with_script
        self._window_finder = window_finder or _find_windows_main_window_for_pid
        self._window_closer = window_closer or _close_windows_main_window
        if bootstrap_plugin_path is None:
            self._bootstrap_plugin_path = None
        else:
            plugin_path = Path(bootstrap_plugin_path).resolve()
            if not plugin_path.is_file():
                raise ValueError("bootstrap_plugin_path must be an existing file")
            self._bootstrap_plugin_path = plugin_path
        if (bootstrap_lisp_path is None) != (ipc_root is None):
            raise ValueError("bootstrap_lisp_path and ipc_root must be supplied together")
        if bootstrap_lisp_path is None:
            self._bootstrap_lisp_path = None
            self._ipc_root = None
        else:
            lisp_path = Path(bootstrap_lisp_path).resolve()
            if not lisp_path.is_file():
                raise ValueError("bootstrap_lisp_path must be an existing file")
            self._bootstrap_lisp_path = lisp_path
            self._ipc_root = _validate_file_ipc_root(str(ipc_root))
        self._start_probe_factory = (
            start_probe_factory or make_windows_start_tab_no_document_probe
        )
        self._document_ready_probe_factory = (
            document_ready_probe_factory
            or make_windows_start_tab_document_ready_probe
        )
        self._bindings_factory = bindings_factory
        self._timing_recorder = timing_recorder or BootstrapTimingRecorder()
        self._stage_timing_enabled = stage_timing_enabled
        self._process: Any = None
        self._hwnd: Optional[int] = None
        self._script_path: Optional[Path] = None
        self._completion_marker_path: Optional[Path] = None
        self._evaluator_entry_marker_path: Optional[Path] = None
        self._stage_marker_paths: tuple[tuple[str, Path, str], ...] = ()
        self._observed_stage_markers: set[str] = set()

    @property
    def hwnd(self) -> Optional[int]:
        return self._hwnd

    @property
    def timing_events(self) -> tuple[BootstrapTimingEvent, ...]:
        return self._timing_recorder.events

    def _startup_script_bytes(self) -> bytes:
        # Keep the owned /b script at the proven phase boundary.  Any action
        # after QNEW must be sent to the same HWND only after document-ready
        # confirmation; this avoids AutoCAD consuming the remaining script
        # while it is still leaving the Start tab.
        return b"_.QNEW\r\n"

    def _stage_marker_expression(self, event_name: str) -> str:
        for name, path, token in self._stage_marker_paths:
            if name == event_name:
                return _start_tab_stage_marker_expression(path, token)
        raise MCPToolError("START_TAB_BOOTSTRAP_STAGE_MARKER_REQUIRED")

    def launch_blank_document(self) -> WindowsStartTabBootstrapBindings:
        if self._process is not None:
            raise MCPToolError("START_TAB_BOOTSTRAP_SESSION_ALREADY_STARTED")
        script_path = self._script_directory / (
            f"cad-agent-start-tab-{uuid.uuid4().hex}.scr"
        )
        completion_marker_path = _start_tab_completion_marker_path(
            script_path, self._ipc_root
        )
        completion_marker_path.unlink(missing_ok=True)
        self._completion_marker_path = completion_marker_path
        if self._bootstrap_lisp_path is not None and self._ipc_root is not None:
            evaluator_entry_marker_path = _start_tab_evaluator_entry_marker_path(
                script_path, self._ipc_root
            )
            if evaluator_entry_marker_path.exists():
                raise MCPToolError(
                    "START_TAB_BOOTSTRAP_EVALUATOR_ENTRY_PATH_CONFLICT"
                )
            self._evaluator_entry_marker_path = evaluator_entry_marker_path
        else:
            self._evaluator_entry_marker_path = None
        self._stage_marker_paths = (
            _start_tab_stage_marker_paths(script_path, self._ipc_root)
            if self._stage_timing_enabled
            else ()
        )
        self._observed_stage_markers.clear()
        for _, stage_path, _ in self._stage_marker_paths:
            stage_path.unlink(missing_ok=True)
        script_path.write_bytes(self._startup_script_bytes())
        self._script_path = script_path
        try:
            _record_bootstrap_timing(self._timing_recorder, "process_launch")
            process = self._process_launcher(self._acad_executable, script_path)
            pid = int(process.pid)
            if pid <= 0:
                raise MCPToolError("START_TAB_BOOTSTRAP_PROCESS_ID_INVALID")
            self._process = process
            deadline = time.monotonic() + self._timeout_s
            while True:
                if process.poll() is not None:
                    raise MCPToolError("START_TAB_BOOTSTRAP_PROCESS_EXITED")
                candidate = int(self._window_finder(pid) or 0)
                start_tab_ready = (
                    candidate > 0 and self._start_probe_factory(candidate)()
                )
                document_ready = (
                    candidate > 0
                    and not start_tab_ready
                    and self._document_ready_probe_factory(candidate)()
                )
                if start_tab_ready or document_ready:
                    _record_bootstrap_timing(
                        self._timing_recorder, "start_window_observed"
                    )
                    self._hwnd = candidate
                    if self._bindings_factory is not None:
                        bindings = self._bindings_factory(candidate)
                    else:
                        bindings = WindowsStartTabBootstrapBindings(
                            hwnd=candidate,
                            command_trigger=make_windows_command_trigger(candidate),
                            raw_lisp_trigger=make_windows_lisp_trigger(candidate),
                            dispatch_trigger=make_windows_dispatch_trigger(candidate),
                            start_tab_no_document_probe=self._start_probe_factory(candidate),
                            document_ready_probe=self._document_ready_probe_factory(candidate),
                        )
                    runtime_required = (
                        self._bootstrap_plugin_path is not None
                        or self._bootstrap_lisp_path is not None
                    )
                    if runtime_required:
                        document_ready_probe = self._document_ready_probe_factory(candidate)
                        self._wait_for_document_ready(document_ready_probe)
                        self._run_process_bound_runtime_bootstrap(bindings)
                        bindings = self._confirm_bootstrap_bindings(bindings)
                    elif isinstance(bindings, WindowsStartTabBootstrapBindings):
                        bindings = replace(
                            bindings,
                            bootstrap_completion_confirmed=True,
                        )
                    return bindings
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MCPTimeoutError(
                        "START_TAB_BOOTSTRAP_START_NOT_OBSERVED"
                    )
                time.sleep(min(self._poll_interval_s, remaining))
        except Exception:
            self.close_without_save(best_effort=True)
            raise

    def _wait_for_document_ready(
        self, document_ready_probe: Callable[[], bool]
    ) -> None:
        deadline = time.monotonic() + self._timeout_s
        while True:
            try:
                if bool(document_ready_probe()):
                    _record_bootstrap_timing_once(
                        self._timing_recorder, "document_ready_transition"
                    )
                    return
            except Exception:
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MCPTimeoutError("START_TAB_BOOTSTRAP_DOCUMENT_NOT_READY")
            time.sleep(min(self._poll_interval_s, remaining))

    def _run_process_bound_runtime_bootstrap(
        self, bindings: WindowsStartTabBootstrapBindings
    ) -> None:
        if self._stage_marker_paths:
            bindings.raw_lisp_trigger(self._stage_marker_expression("post_qnew_entry"))
        if self._bootstrap_plugin_path is not None:
            plugin_literal = _autolisp_string_literal(
                str(self._bootstrap_plugin_path).replace("\\", "/")
            )
            bindings.command_trigger("_.NETLOAD\r" + plugin_literal + "\r")
            if self._stage_marker_paths:
                bindings.raw_lisp_trigger(
                    self._stage_marker_expression("netload_return")
                )
        if self._bootstrap_lisp_path is None:
            return
        if self._ipc_root is None or self._completion_marker_path is None:
            raise MCPToolError("START_TAB_BOOTSTRAP_COMPLETION_PATH_REQUIRED")
        if self._evaluator_entry_marker_path is None:
            raise MCPToolError("START_TAB_BOOTSTRAP_EVALUATOR_ENTRY_PATH_REQUIRED")
        bindings.raw_lisp_trigger(
            self._dispatcher_load_expression(
                evaluator_entry_marker_path=self._evaluator_entry_marker_path
            )
        )
        self._wait_for_evaluator_entry_ack()
        if self._stage_marker_paths:
            bindings.raw_lisp_trigger(
                self._stage_marker_expression("dispatcher_load_return")
            )
        bindings.raw_lisp_trigger(
            _start_tab_completion_marker_expression(self._completion_marker_path)
        )
        if self._stage_marker_paths:
            bindings.raw_lisp_trigger(
                self._stage_marker_expression("completion_marker_writer_return")
            )
        self._wait_for_completion_ack()

    def _dispatcher_load_expression(
        self, *, evaluator_entry_marker_path: Optional[Path] = None
    ) -> str:
        if self._bootstrap_lisp_path is None or self._ipc_root is None:
            raise MCPToolError("File IPC dispatcher bootstrap is not configured")
        root_literal = _autolisp_string_literal(
            str(self._ipc_root).replace("\\", "/")
        )
        lisp_literal = _autolisp_string_literal(
            str(self._bootstrap_lisp_path).replace("\\", "/")
        )
        dispatcher_expression = (
            "(progn (setq *cad-agent-file-ipc-root* "
            + root_literal
            + ") (load "
            + lisp_literal
            + "))"
        )
        if evaluator_entry_marker_path is None:
            return dispatcher_expression
        return (
            "(progn "
            + _start_tab_evaluator_entry_marker_expression(
                evaluator_entry_marker_path
            )
            + " "
            + dispatcher_expression[7:]
        )

    def _confirm_bootstrap_bindings(
        self, bindings: WindowsStartTabBootstrapBindings
    ) -> WindowsStartTabBootstrapBindings:
        if isinstance(bindings, WindowsStartTabBootstrapBindings):
            return replace(
                bindings,
                dispatcher_preloaded=self._bootstrap_lisp_path is not None,
                bootstrap_completion_confirmed=True,
            )
        try:
            bindings.dispatcher_preloaded = self._bootstrap_lisp_path is not None
            bindings.bootstrap_completion_confirmed = True
            return bindings
        except (AttributeError, TypeError):
            return WindowsStartTabBootstrapBindings(
                hwnd=bindings.hwnd,
                command_trigger=bindings.command_trigger,
                raw_lisp_trigger=bindings.raw_lisp_trigger,
                dispatch_trigger=bindings.dispatch_trigger,
                start_tab_no_document_probe=bindings.start_tab_no_document_probe,
                document_ready_probe=bindings.document_ready_probe,
                dispatcher_preloaded=self._bootstrap_lisp_path is not None,
                bootstrap_completion_confirmed=True,
            )

    def close_without_save(self, *, best_effort: bool = False) -> None:
        _record_bootstrap_timing(self._timing_recorder, "cleanup_start")
        process = self._process
        hwnd = self._hwnd
        try:
            if process is not None and process.poll() is None:
                if hwnd is not None:
                    try:
                        self._window_closer(hwnd)
                    except Exception:
                        if not best_effort:
                            raise
                elif not best_effort:
                    raise MCPToolError("START_TAB_BOOTSTRAP_CLOSE_TARGET_MISSING")

                deadline = time.monotonic() + self._timeout_s
                if not self._wait_for_process_exit(process, deadline):
                    if not best_effort:
                        raise MCPTimeoutError(
                            "START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED"
                        )
                    terminate = getattr(process, "terminate", None)
                    if callable(terminate):
                        try:
                            terminate()
                        except Exception:
                            pass
                        self._wait_for_process_exit(
                            process, time.monotonic() + self._timeout_s
                        )
        except Exception:
            if not best_effort:
                raise
        finally:
            if self._script_path is not None:
                try:
                    self._script_path.unlink(missing_ok=True)
                except OSError:
                    if not best_effort:
                        raise
            if self._completion_marker_path is not None:
                try:
                    self._completion_marker_path.unlink(missing_ok=True)
                except OSError:
                    if not best_effort:
                        raise
            if self._evaluator_entry_marker_path is not None:
                if self._evaluator_entry_marker_path.parent != self._ipc_root:
                    if not best_effort:
                        raise MCPToolError(
                            "START_TAB_BOOTSTRAP_EVALUATOR_ENTRY_ROOT_CHANGED"
                        )
                else:
                    try:
                        self._evaluator_entry_marker_path.unlink(missing_ok=True)
                    except OSError:
                        if not best_effort:
                            raise
            for _, stage_path, _ in self._stage_marker_paths:
                try:
                    stage_path.unlink(missing_ok=True)
                except OSError:
                    if not best_effort:
                        raise
            if process is not None and process.poll() is not None:
                self._process = None
                self._hwnd = None
            elif process is None:
                self._hwnd = None
            if best_effort or self._process is None:
                self._script_path = None
                self._completion_marker_path = None
                self._evaluator_entry_marker_path = None
                self._stage_marker_paths = ()
                self._observed_stage_markers.clear()
            _record_bootstrap_timing(self._timing_recorder, "cleanup_end")

    def _wait_for_process_exit(self, process: Any, deadline: float) -> bool:
        while process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(self._poll_interval_s, remaining))
        return True

    def _wait_for_evaluator_entry_ack(self) -> None:
        path = self._evaluator_entry_marker_path
        if path is None:
            raise MCPToolError("START_TAB_BOOTSTRAP_EVALUATOR_ENTRY_PATH_REQUIRED")
        deadline = time.monotonic() + self._timeout_s
        while True:
            try:
                if (
                    path.is_file()
                    and path.read_text(encoding="ascii").strip()
                    == _START_TAB_EVALUATOR_ENTRY_TOKEN
                ):
                    return
            except (OSError, UnicodeError):
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MCPTimeoutError("STARTUP_EVALUATOR_ENTRY_NOT_CONFIRMED")
            time.sleep(min(self._poll_interval_s, remaining))

    def _wait_for_completion_ack(
        self,
        *,
        document_ready_probe: Optional[Callable[[], bool]] = None,
    ) -> None:
        path = self._completion_marker_path
        if path is None:
            raise MCPToolError("START_TAB_BOOTSTRAP_COMPLETION_PATH_REQUIRED")
        _record_bootstrap_timing(
            self._timing_recorder, "completion_wait_start"
        )
        deadline = time.monotonic() + self._timeout_s
        document_ready_observed = False
        while True:
            self._observe_stage_markers()
            if document_ready_probe is not None and not document_ready_observed:
                try:
                    if bool(document_ready_probe()):
                        _record_bootstrap_timing_once(
                            self._timing_recorder,
                            "document_ready_transition",
                        )
                        document_ready_observed = True
                except Exception:
                    pass
            try:
                if (
                    path.is_file()
                    and path.read_text(encoding="ascii").strip()
                    == _START_TAB_BOOTSTRAP_COMPLETION_TOKEN
                ):
                    _record_bootstrap_timing(
                        self._timing_recorder, "completion_marker_observed"
                    )
                    return
            except (OSError, UnicodeError):
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _record_bootstrap_timing(
                    self._timing_recorder, "completion_timeout"
                )
                raise MCPTimeoutError(
                    "START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED"
                )
            time.sleep(min(self._poll_interval_s, remaining))

    def _observe_stage_markers(self) -> None:
        for event_name, stage_path, token in self._stage_marker_paths:
            if event_name in self._observed_stage_markers:
                continue
            try:
                if (
                    stage_path.is_file()
                    and stage_path.read_text(encoding="ascii").strip() == token
                ):
                    _record_bootstrap_timing_once(
                        self._timing_recorder, event_name
                    )
                    self._observed_stage_markers.add(event_name)
            except (OSError, UnicodeError):
                pass

class FileIPCLiveMCPClient:
    """Minimal File IPC client for a loaded AutoLISP MCP dispatcher."""
    def __init__(self, ipc_dir: str, trigger: Optional[Callable[[], None]] = None,
                 timeout_s: float = 10.0, poll_interval_s: float = 0.1,
                 raw_lisp_trigger: Optional[Callable[[str], None]] = None,
                 bootstrap_lisp_path: Optional[str] = None,
                 document_settle_s: float = 2.0,
                 command_trigger: Optional[Callable[[str], None]] = None,
                 start_tab_no_document_probe: Optional[Callable[[], bool]] = None,
                 legacy_fixture_mode: Optional[bool] = None,
                 bootstrap_start_tab: bool = False,
                 bootstrap_document_ready_probe: Optional[Callable[[], bool]] = None,
                 bootstrap_document_ready_timeout_s: Optional[float] = None,
                 bootstrap_start_tab_session_factory: Optional[
                     Callable[[], WindowsAutoCADStartTabSession]
                 ] = None,
                 bootstrap_document_setup_hook: Optional[Callable[[], None]] = None,
                 timing_recorder: Optional[BootstrapTimingRecorder] = None) -> None:
        self._dir = _validate_file_ipc_root(ipc_dir)
        self._root_identity = _file_ipc_root_identity(self._dir)
        self._trigger = trigger
        if legacy_fixture_mode is None:
            legacy_fixture_mode = not bool(
                getattr(trigger, "_mcp_claim_bound", False)
            )
        if type(legacy_fixture_mode) is not bool:
            raise TypeError("legacy_fixture_mode must be a bool or None")
        self._legacy_fixture_mode = legacy_fixture_mode
        self._timeout, self._poll = timeout_s, poll_interval_s
        self._raw_lisp_trigger = raw_lisp_trigger
        self._bootstrap_lisp_path = bootstrap_lisp_path
        self._document_settle_s = document_settle_s
        self._command_trigger = command_trigger
        self._start_tab_no_document_probe = start_tab_no_document_probe
        self._bootstrap_document_ready_probe = bootstrap_document_ready_probe
        self._bootstrap_document_ready_timeout_s = (
            self._timeout
            if bootstrap_document_ready_timeout_s is None
            else bootstrap_document_ready_timeout_s
        )
        self._bootstrap_start_tab_session_factory = bootstrap_start_tab_session_factory
        self._bootstrap_document_setup_hook = bootstrap_document_setup_hook
        self._timing_recorder = timing_recorder or BootstrapTimingRecorder()
        self._bootstrap_dispatcher_preloaded = False
        if type(bootstrap_start_tab) is not bool:
            raise TypeError("bootstrap_start_tab must be a bool")
        self._bootstrap_start_tab = bootstrap_start_tab
        self._active_drawing_path: Optional[str] = None
        self._start_tab_bootstrap_active = False
        self._start_tab_bootstrap_session: Optional[WindowsAutoCADStartTabSession] = None
        self._last_exchange_evidence: Optional[Dict[str, Any]] = None

    @property
    def last_exchange_evidence(self) -> Optional[Dict[str, Any]]:
        """Return privacy-safe evidence for the latest validated exchange."""
        if self._last_exchange_evidence is None:
            return None
        return dict(self._last_exchange_evidence)

    @property
    def timing_events(self) -> tuple[BootstrapTimingEvent, ...]:
        return self._timing_recorder.events

    def _assert_root_unchanged(self) -> None:
        try:
            if (
                not self._dir.is_dir()
                or _file_ipc_path_has_reparse_point(self._dir)
                or _file_ipc_root_identity(self._dir) != self._root_identity
            ):
                raise MCPToolError("IPC_ROOT_CHANGED")
        except (OSError, ValueError) as exc:
            raise MCPToolError("IPC_ROOT_CHANGED") from exc

    def _dispatch(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # Evidence is scoped to the current exchange.  Never let a prior
        # terminal success describe a later failed or incomplete request.
        self._last_exchange_evidence = None
        if command not in _FILE_IPC_ALLOWED_COMMANDS:
            raise MCPToolError("IPC_COMMAND_UNSUPPORTED")
        self._assert_root_unchanged()
        request_candidates = sorted(self._dir.glob(f"{_FILE_IPC_REQUEST_PREFIX}*.json"))
        if len(request_candidates) > 1:
            raise MCPToolError("IPC_REQUEST_AMBIGUOUS")
        if request_candidates:
            candidate = request_candidates[0]
            try:
                if candidate.stat().st_size > _FILE_IPC_MAX_JSON_BYTES:
                    raise MCPToolError("IPC_REQUEST_OVERSIZED")
                _strict_file_ipc_json_object(
                    candidate.read_bytes(),
                    error_code="IPC_REQUEST_INVALID",
                )
            except MCPToolError:
                raise
            except OSError as exc:
                raise MCPToolError("IPC_REQUEST_INVALID") from exc
            raise MCPToolError("IPC_REQUEST_INVALID")
        if list(self._dir.glob(f"{_FILE_IPC_REQUEST_PREFIX}*.json.part")):
            raise MCPToolError("IPC_REQUEST_INVALID")
        if (
            list(self._dir.glob(f"{_FILE_IPC_RESULT_PREFIX}*.json"))
            or list(self._dir.glob(f"{_FILE_IPC_RESULT_PREFIX}*.json.part"))
        ):
            raise MCPToolError("IPC_RESULT_CONFLICT")

        request_id = uuid.uuid4().hex[:12]
        claim = None if self._legacy_fixture_mode else secrets.token_hex(32)
        cmd = self._dir / f"{_FILE_IPC_REQUEST_PREFIX}{request_id}.json"
        result = self._dir / f"{_FILE_IPC_RESULT_PREFIX}{request_id}.json"
        cmd_part = self._dir / f"{_FILE_IPC_REQUEST_PREFIX}{request_id}.json.part"
        result_part = self._dir / f"{_FILE_IPC_RESULT_PREFIX}{request_id}.json.part"
        request = {
            "request_id": request_id,
            "command": command,
            "params": params,
        }
        if claim is not None:
            request["claim"] = claim
        raw = json.dumps(request, separators=(",", ":")).encode("utf-8")
        if len(raw) > _FILE_IPC_MAX_JSON_BYTES:
            raise MCPToolError("IPC_REQUEST_OVERSIZED")
        owned_paths = (cmd_part, cmd, result_part, result)
        root_safe_for_cleanup = True
        try:
            self._assert_root_unchanged()
            try:
                with cmd_part.open("xb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as exc:
                raise MCPToolError("IPC_REQUEST_INVALID") from exc
            self._assert_root_unchanged()
            os.replace(cmd_part, cmd)
            self._assert_root_unchanged()
            if self._trigger is None:
                raise MCPToolError("File IPC requires an AutoCAD dispatcher trigger")
            self._trigger()
            self._assert_root_unchanged()
            deadline = time.time() + self._timeout
            while time.time() < deadline:
                self._assert_root_unchanged()
                candidates = sorted(self._dir.glob(f"{_FILE_IPC_RESULT_PREFIX}*.json"))
                if any(candidate != result for candidate in candidates):
                    raise MCPToolError("IPC_RESULT_CONFLICT")
                if result in candidates:
                    self._assert_root_unchanged()
                    try:
                        with result.open("rb") as handle:
                            raw_result = handle.read(_FILE_IPC_MAX_JSON_BYTES + 1)
                    except OSError as exc:
                        raise MCPToolError("IPC_RESULT_INVALID") from exc
                    if len(raw_result) > _FILE_IPC_MAX_JSON_BYTES:
                        raise MCPToolError("IPC_RESULT_OVERSIZED")
                    data = _strict_file_ipc_json_object(
                        raw_result,
                        error_code="IPC_RESULT_INVALID",
                    )
                    payload = _validate_file_ipc_result(data, request_id, claim)
                    self._last_exchange_evidence = {
                        "request_id": request_id,
                        "command": command,
                        "claim_bound": claim is not None,
                        "terminal": True,
                        "ok": True,
                    }
                    return payload
                time.sleep(self._poll)
            raise MCPTimeoutError(f"Timeout waiting for result (request_id={request_id})")
        finally:
            try:
                self._assert_root_unchanged()
            except MCPToolError:
                root_safe_for_cleanup = False
            if root_safe_for_cleanup:
                for owned_path in owned_paths:
                    try:
                        owned_path.unlink(missing_ok=True)
                    except OSError:
                        pass

    def entity_list(self, layer: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._dispatch("entity-list", {k: v for k, v in {"layer": layer}.items() if v is not None}).get("entities", [])

    def drawing_open(self, path: str, *, read_only: bool = False) -> Dict[str, Any]:
        if type(read_only) is not bool:
            raise ValueError("read_only must be a bool")
        if self._bootstrap_start_tab:
            self.ensure_start_tab_bootstrap()
        if (
            self._bootstrap_dispatcher_preloaded
            and self._trigger is not None
            and getattr(self._trigger, "_mcp_claim_bound", False) is True
        ):
            params: Dict[str, Any] = {"path": path}
            if read_only:
                params["read_only"] = True
            result = self._dispatch("drawing-open", params)
            self._active_drawing_path = _normalized_autocad_path(path)
            return result
        if self._raw_lisp_trigger is not None and self._bootstrap_lisp_path is not None:
            normalized_path = path.replace("\\", "/").replace('"', '\\"')
            expected_path = _normalized_autocad_path(path)
            active_path = ""
            read_only_argument = " :vlax-true" if read_only else ""
            for attempt in range(2):
                try:
                    self._send_drawing_open_raw_lisp(
                        '(progn (vl-load-com) '
                        '(setq mcp-docs (vla-get-Documents (vlax-get-acad-object)) '
                        'mcp-target-path (findfile "' + normalized_path + '") '
                        'mcp-open-doc nil) '
                        '(if (not mcp-target-path) '
                        '(setq mcp-target-path "' + normalized_path + '")) '
                        '(vlax-for mcp-candidate-doc mcp-docs '
                        '(if (= (strcase (vla-get-FullName mcp-candidate-doc)) '
                        '(strcase mcp-target-path)) '
                        '(setq mcp-open-doc mcp-candidate-doc))) '
                        '(if (not mcp-open-doc) '
                        '(setq mcp-open-doc (vla-open mcp-docs "' + normalized_path + '"' + read_only_argument + '))) '
                        '(vla-activate mcp-open-doc))',
                        _RAW_LISP_DRAWING_OPEN_ACK_TOKEN,
                        ack_before="(vla-activate mcp-open-doc)",
                    )
                except (MCPTimeoutError, MCPToolError) as exc:
                    if str(exc) == _RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED:
                        raise
                    if (
                        read_only
                        or self._command_trigger is None
                        or attempt != 0
                        or not self._start_tab_no_document_is_proven(exc)
                    ):
                        raise
                    self._command_trigger('_.OPEN\r"' + normalized_path + '"')
                time.sleep(self._document_settle_s)
                self._active_drawing_path = expected_path
                if not self._bootstrap_dispatcher_preloaded:
                    self._load_dispatcher_for_active_document()
                self._wait_for_dispatcher()
                variables = self.drawing_get_variables(["DWGPREFIX", "DWGNAME"])
                active_path = _normalized_autocad_path(
                    ntpath.join(
                        str(variables.get("DWGPREFIX", "")),
                        str(variables.get("DWGNAME", "")),
                    )
                )
                if active_path == expected_path:
                    self._active_drawing_path = expected_path
                    return {"path": path}
                if attempt == 0:
                    time.sleep(self._poll)
            raise MCPToolError(
                "AutoCAD did not activate requested drawing "
                f"{expected_path!r}; active drawing is {active_path!r}"
            )
        result = self._dispatch("drawing-open", {"path": path})
        self._active_drawing_path = _normalized_autocad_path(path)
        return result

    def ensure_start_tab_bootstrap(self) -> bool:
        """Create a disposable blank document only for an opt-in Start-tab path."""
        if not self._bootstrap_start_tab:
            return False
        if self._start_tab_bootstrap_active:
            return False
        if (
            self._bootstrap_start_tab_session_factory is None
            and (self._raw_lisp_trigger is None or self._bootstrap_lisp_path is None)
        ):
            raise MCPToolError("START_TAB_BOOTSTRAP_LISP_REQUIRED")
        try:
            if self._bootstrap_start_tab_session_factory is not None:
                session = self._bootstrap_start_tab_session_factory()
                if session is None:
                    raise MCPToolError("START_TAB_BOOTSTRAP_SESSION_REQUIRED")
                self._start_tab_bootstrap_session = session
                bindings = session.launch_blank_document()
                self._apply_start_tab_bootstrap_bindings(bindings)
            else:
                if self._start_tab_no_document_probe is None:
                    raise MCPToolError("START_TAB_BOOTSTRAP_PROBE_REQUIRED")
                if self._command_trigger is None:
                    raise MCPToolError("START_TAB_BOOTSTRAP_COMMAND_REQUIRED")
                try:
                    start_tab = bool(self._start_tab_no_document_probe())
                except Exception as exc:
                    raise MCPToolError("START_TAB_BOOTSTRAP_PROBE_FAILED") from exc
                if not start_tab:
                    return False
                self._command_trigger("_.QNEW")

            self._wait_for_bootstrap_document()
            self._start_tab_bootstrap_active = True
            if not self._bootstrap_dispatcher_preloaded:
                self._load_dispatcher_for_active_document()
            self._wait_for_dispatcher()
            if self._bootstrap_document_setup_hook is not None:
                self._bootstrap_document_setup_hook()
                time.sleep(self._document_settle_s)
        except Exception:
            try:
                if self._start_tab_bootstrap_session is not None:
                    self._start_tab_bootstrap_session.close_without_save(best_effort=True)
                    self._start_tab_bootstrap_session = None
                    self._start_tab_bootstrap_active = False
                    self._bootstrap_dispatcher_preloaded = False
                elif self._start_tab_bootstrap_active:
                    self.close_start_tab_bootstrap()
            except Exception:
                pass
            raise
        return True

    def _apply_start_tab_bootstrap_bindings(
        self,
        bindings: WindowsStartTabBootstrapBindings,
    ) -> None:
        if type(bindings.hwnd) is not int or bindings.hwnd <= 0:
            raise MCPToolError("START_TAB_BOOTSTRAP_WINDOW_INVALID")
        required = (
            bindings.command_trigger,
            bindings.raw_lisp_trigger,
            bindings.dispatch_trigger,
            bindings.start_tab_no_document_probe,
            bindings.document_ready_probe,
        )
        if not all(callable(value) for value in required):
            raise MCPToolError("START_TAB_BOOTSTRAP_BINDINGS_INVALID")
        dispatcher_preloaded = getattr(bindings, "dispatcher_preloaded", False)
        if type(dispatcher_preloaded) is not bool:
            raise MCPToolError("START_TAB_BOOTSTRAP_BINDINGS_INVALID")
        if getattr(bindings.dispatch_trigger, "_mcp_claim_bound", False) is not True:
            raise MCPToolError("START_TAB_BOOTSTRAP_CLAIM_REQUIRED")
        completion_confirmed = getattr(bindings, "bootstrap_completion_confirmed", False)
        if completion_confirmed is not True:
            raise MCPToolError("START_TAB_BOOTSTRAP_COMPLETION_REQUIRED")
        self._command_trigger = bindings.command_trigger
        self._raw_lisp_trigger = bindings.raw_lisp_trigger
        self._trigger = bindings.dispatch_trigger
        self._start_tab_no_document_probe = bindings.start_tab_no_document_probe
        self._bootstrap_document_ready_probe = bindings.document_ready_probe
        self._bootstrap_dispatcher_preloaded = dispatcher_preloaded
        self._legacy_fixture_mode = False

    def _wait_for_bootstrap_document(self) -> None:
        probe = self._bootstrap_document_ready_probe
        if probe is None:
            raise MCPToolError("START_TAB_BOOTSTRAP_DOCUMENT_PROBE_REQUIRED")
        deadline = time.monotonic() + max(0.0, self._bootstrap_document_ready_timeout_s)
        while True:
            try:
                if bool(probe()):
                    _record_bootstrap_timing_once(
                        self._timing_recorder, "document_ready_transition"
                    )
                    return
            except Exception:
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MCPTimeoutError("START_TAB_BOOTSTRAP_DOCUMENT_NOT_READY")
            time.sleep(min(max(0.0, self._poll), remaining))

    def close_start_tab_bootstrap(self) -> None:
        """Close the tracked unsaved bootstrap document without saving it."""
        if not self._start_tab_bootstrap_active:
            return
        if self._start_tab_bootstrap_session is not None:
            self._start_tab_bootstrap_session.close_without_save()
            self._start_tab_bootstrap_session = None
            self._start_tab_bootstrap_active = False
            self._bootstrap_dispatcher_preloaded = False
            return
        if self._raw_lisp_trigger is None:
            raise MCPToolError("START_TAB_BOOTSTRAP_LISP_REQUIRED")
        self._raw_lisp_trigger(
            '(progn (vl-load-com) '
            '(setq mcp-bootstrap-doc '
            '(vla-get-ActiveDocument (vlax-get-acad-object))) '
            '(if (= (vla-get-FullName mcp-bootstrap-doc) "") '
            '(command-s "_.CLOSE" "_N") '
            '(princ "START_TAB_BOOTSTRAP_CLOSE_TARGET_MISMATCH")))'
        )
        time.sleep(self._document_settle_s)
        if self._start_tab_no_document_probe is not None:
            try:
                if not self._start_tab_no_document_probe():
                    raise MCPToolError("START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED")
            except MCPToolError:
                raise
            except Exception as exc:
                raise MCPToolError("START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED") from exc
        self._start_tab_bootstrap_active = False

    def _load_dispatcher_for_active_document(self) -> None:
        if self._raw_lisp_trigger is None or self._bootstrap_lisp_path is None:
            raise MCPToolError("File IPC dispatcher bootstrap is not configured")
        self._assert_root_unchanged()
        root_literal = _autolisp_string_literal(str(self._dir).replace("\\", "/"))
        loader_literal = _autolisp_string_literal(
            self._bootstrap_lisp_path.replace("\\", "/")
        )
        self._raw_lisp_trigger(
            "(progn (setq *cad-agent-file-ipc-root* "
            + root_literal
            + ") (load "
            + loader_literal
            + "))"
        )
        time.sleep(self._document_settle_s)

    def _start_tab_no_document_is_proven(self, error: Exception) -> bool:
        message = str(error).casefold()
        if any(marker in message for marker in ("rpc_e_call_rejected", "modal", "select file", "dialog")):
            return False
        probe = self._start_tab_no_document_probe
        if probe is not None:
            try:
                return bool(probe())
            except Exception:
                return False
        return False

    def _wait_for_dispatcher(self) -> None:
        deadline = time.time() + self._timeout
        last_error: Optional[Exception] = None
        while time.time() < deadline:
            try:
                self._dispatch("ping", {})
                return
            except (MCPTimeoutError, MCPToolError) as exc:
                last_error = exc
                time.sleep(self._poll)
        raise MCPTimeoutError(f"AutoCAD dispatcher did not become ready: {last_error}")

    def _send_drawing_open_raw_lisp(
        self,
        expression: str,
        token: str,
        *,
        ack_before: Optional[str] = None,
    ) -> None:
        if self._legacy_fixture_mode:
            if self._raw_lisp_trigger is None:
                raise MCPToolError("RAW_LISP_TRIGGER_REQUIRED")
            self._raw_lisp_trigger(expression)
            return
        self._send_raw_lisp_with_ack(expression, token, ack_before=ack_before)

    def _send_raw_lisp_with_ack(
        self,
        expression: str,
        token: str,
        *,
        ack_before: Optional[str] = None,
    ) -> Dict[str, str]:
        """Send one owner-built expression and require its exact marker receipt."""
        if self._raw_lisp_trigger is None:
            raise MCPToolError("RAW_LISP_TRIGGER_REQUIRED")
        self._assert_root_unchanged()
        marker_id = uuid.uuid4().hex[:12]
        marker_path = self._dir / f"{_RAW_LISP_DRAWING_OPEN_ACK_PREFIX}{marker_id}.txt"
        if marker_path.exists():
            raise MCPToolError("RAW_LISP_ACK_PATH_CONFLICT")
        marker_expression = _start_tab_stage_marker_expression(marker_path, token)
        if ack_before is None:
            wrapped_expression = "(progn " + expression + " " + marker_expression + ")"
        else:
            marker_position = expression.rfind(ack_before)
            if marker_position < 0:
                raise MCPToolError("RAW_LISP_ACK_PLACEMENT_INVALID")
            wrapped_expression = (
                "(progn "
                + expression[:marker_position]
                + marker_expression
                + " "
                + expression[marker_position:]
                + ")"
            )
        root_safe_for_cleanup = True
        try:
            self._raw_lisp_trigger(wrapped_expression)
            self._assert_root_unchanged()
            deadline = time.monotonic() + max(0.0, self._timeout)
            while True:
                try:
                    if (
                        marker_path.is_file()
                        and marker_path.read_text(encoding="ascii").strip() == token
                    ):
                        return {
                            "raw_lisp_evaluator_receipt": "CONFIRMED",
                            "receiver_consumption": "NOT_SEPARATELY_OBSERVABLE",
                        }
                except (OSError, UnicodeError):
                    pass
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MCPTimeoutError(
                        _RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED
                    )
                time.sleep(min(max(0.0, self._poll), remaining))
        finally:
            try:
                self._assert_root_unchanged()
            except MCPToolError:
                root_safe_for_cleanup = False
            if root_safe_for_cleanup:
                for attempt in range(10):
                    try:
                        marker_path.unlink(missing_ok=True)
                        break
                    except PermissionError as exc:
                        if attempt == 9:
                            raise MCPToolError(
                                "RAW_LISP_ACK_CLEANUP_FAILED"
                            ) from exc
                        time.sleep(self._poll)
                    except OSError as exc:
                        raise MCPToolError(
                            "RAW_LISP_ACK_CLEANUP_FAILED"
                        ) from exc

    def drawing_save(self, path: Optional[str] = None) -> None:
        self._dispatch("drawing-save", {"path": path} if path else {})

    def _assert_active_document_matches(self, expected_path: Optional[str]) -> str:
        if expected_path is None:
            raise MCPToolError("DRAWING_CLOSE_TARGET_UNBOUND")
        variables = self.drawing_get_variables(["DWGPREFIX", "DWGNAME"])
        prefix = variables.get("DWGPREFIX")
        name = variables.get("DWGNAME")
        active_path = _normalized_autocad_path(
            ntpath.join(str(prefix or ""), str(name or ""))
        )
        if not prefix or not name or active_path != expected_path:
            raise MCPToolError("DRAWING_CLOSE_TARGET_MISMATCH")
        return _autolisp_string_literal(expected_path.replace("\\", "/"))

    def drawing_close(self, save_changes: bool = False) -> None:
        if self._raw_lisp_trigger is not None:
            expected_path = self._active_drawing_path
            expected_literal = self._assert_active_document_matches(expected_path)
            if save_changes:
                self._raw_lisp_trigger(
                    "(progn (vl-load-com) "
                    "(setq mcp-close-doc "
                    "(vla-get-ActiveDocument (vlax-get-acad-object)) "
                    "mcp-close-target (findfile "
                    + expected_literal
                    + ")) "
                    "(if (not mcp-close-target) "
                    "(setq mcp-close-target "
                    + expected_literal
                    + ")) "
                    "(if (= (strcase (vla-get-FullName mcp-close-doc)) "
                    "(strcase mcp-close-target)) "
                    "(vla-close mcp-close-doc :vlax-true) "
                    '(princ "DRAWING_CLOSE_TARGET_MISMATCH")))'
                )
            else:
                # Queue no-save close at AutoCAD's command boundary. Direct
                # COM close can race the active File IPC dispatcher and
                # report that the drawing is busy.
                self._raw_lisp_trigger(
                    "(progn (vl-load-com) "
                    "(setq mcp-close-doc "
                    "(vla-get-ActiveDocument (vlax-get-acad-object)) "
                    "mcp-close-target (findfile "
                    + expected_literal
                    + ")) "
                    "(if (not mcp-close-target) "
                    "(setq mcp-close-target "
                    + expected_literal
                    + ")) "
                    "(if (= (strcase (vla-get-FullName mcp-close-doc)) "
                    "(strcase mcp-close-target)) "
                    '(command-s "_.CLOSE" "_N") '
                    '(princ "DRAWING_CLOSE_TARGET_MISMATCH")))'
                )
            time.sleep(self._document_settle_s)
            if expected_path is not None:
                deadline = time.time() + max(5.0, self._document_settle_s * 3.0)
                close_confirmed = False
                while time.time() < deadline:
                    try:
                        open_paths = {
                            _normalized_autocad_path(open_path)
                            for open_path in self.drawing_list_open_paths()
                        }
                        if expected_path not in open_paths:
                            close_confirmed = True
                            break
                    except (MCPTimeoutError, MCPToolError):
                        pass
                    time.sleep(self._poll)
                if not close_confirmed:
                    raise MCPToolError("DRAWING_CLOSE_NOT_CONFIRMED")
            self._active_drawing_path = None
            return
        self._dispatch("drawing-close", {"save_changes": save_changes})

    def drawing_list_open_paths(self) -> List[str]:
        if self._raw_lisp_trigger is None:
            return self._dispatch("drawing-list-open-paths", {}).get("paths", [])
        token = uuid.uuid4().hex[:12]
        result = self._dir / f"autocad_mcp_open_documents_{token}.txt"
        lisp_path = str(result).replace("\\", "/").replace('"', '\\"')
        try:
            self._raw_lisp_trigger(
                '(progn (vl-load-com) '
                f'(setq mcp-doc-file (open "{lisp_path}" "w")) '
                '(vlax-for mcp-open-doc '
                '(vla-get-Documents (vlax-get-acad-object)) '
                '(write-line (vla-get-FullName mcp-open-doc) mcp-doc-file)) '
                "(close mcp-doc-file))"
            )
            deadline = time.time() + self._timeout
            while time.time() < deadline:
                if result.is_file():
                    return [
                        line.strip()
                        for line in result.read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    ]
                time.sleep(self._poll)
            raise MCPTimeoutError("Timeout waiting for AutoCAD open-document list")
        finally:
            for attempt in range(10):
                try:
                    result.unlink(missing_ok=True)
                    break
                except PermissionError as exc:
                    if attempt == 9:
                        raise MCPToolError(
                            "IPC_OPEN_DOCUMENTS_CLEANUP_FAILED"
                        ) from exc
                    time.sleep(self._poll)

    def drawing_save_as_dxf(self, path: str) -> None:
        self._dispatch("drawing-save-as-dxf", {"path": path.replace("\\", "/")})

    def drawing_get_variables(self, names: List[str]) -> Dict[str, Any]:
        return self._dispatch("drawing-get-variables", {"names_str": ";".join(names)})

    def block_get_attributes(self, entity_id: str) -> Dict[str, str]:
        for attempt in range(2):
            try:
                return self._dispatch(
                    "block-get-attributes",
                    {"entity_id": entity_id},
                ).get("attributes", {})
            except MCPTimeoutError:
                if attempt == 0:
                    time.sleep(self._poll)
                    continue
                raise
        return {}

    def block_update_attribute(self, entity_id: str, tag: str, value: str) -> None:
        self._dispatch("block-update-attribute", {"entity_id": entity_id, "tag": tag, "value": value})

    def entity_get(self, entity_id: str) -> Dict[str, Any]:
        payload = self._dispatch("entity-get", {"entity_id": entity_id})
        if (
            str(payload.get("type", "")).upper() == "DIMENSION"
            and "measurement" not in payload
            and self._raw_lisp_trigger is not None
        ):
            payload["measurement"] = self._dimension_measurement(entity_id)
        return payload

    def _dimension_measurement(self, entity_id: str) -> float:
        if not re.fullmatch(r"[0-9A-Fa-f]+", entity_id):
            raise MCPToolError("DIMENSION measurement requires a valid handle")
        token = uuid.uuid4().hex[:12]
        result = (
            self._dir
            / f"autocad_mcp_dimension_measurement_{token}.txt"
        )
        lisp_path = str(result).replace("\\", "/").replace('"', '\\"')
        result.touch()
        try:
            self._raw_lisp_trigger(
                '(progn (vl-load-com) '
                f'(setq mcp-dim-ent (handent "{entity_id}")) '
                f'(setq mcp-dim-file (open "{lisp_path}" "w")) '
                '(setq mcp-dim-data '
                '(if mcp-dim-ent '
                '(entget mcp-dim-ent) '
                'nil)) '
                '(setq mcp-dim-value '
                '(if mcp-dim-data '
                '(cdr (assoc 42 mcp-dim-data)) '
                'nil)) '
                '(if (or (not (numberp mcp-dim-value)) '
                '(< mcp-dim-value 0.0)) '
                '(setq mcp-dim-value '
                '(if (and (assoc 13 mcp-dim-data) '
                '(assoc 14 mcp-dim-data)) '
                '(distance (cdr (assoc 13 mcp-dim-data)) '
                '(cdr (assoc 14 mcp-dim-data))) '
                'nil))) '
                '(cond '
                '((not mcp-dim-ent) '
                '(write-line "ERROR:entity not found" mcp-dim-file)) '
                '((not (numberp mcp-dim-value)) '
                '(write-line "ERROR:DXF measurement and dimension endpoints are missing" mcp-dim-file)) '
                '(T (write-line (rtos mcp-dim-value 2 12) mcp-dim-file))) '
                '(close mcp-dim-file) '
                '(setq mcp-dim-file nil))'
            )
            deadline = time.time() + self._timeout
            while time.time() < deadline:
                content = result.read_text(encoding="utf-8").strip()
                if content:
                    if content.startswith("ERROR:"):
                        raise MCPToolError(
                            "AutoCAD DIMENSION measurement failed: "
                            + content.removeprefix("ERROR:")
                        )
                    try:
                        return float(content)
                    except ValueError as exc:
                        raise MCPToolError(
                            "AutoCAD returned an invalid DIMENSION measurement"
                        ) from exc
                time.sleep(self._poll)
            raise MCPTimeoutError(
                "Timeout waiting for AutoCAD DIMENSION measurement"
            )
        finally:
            for _ in range(10):
                try:
                    result.unlink(missing_ok=True)
                    break
                except PermissionError:
                    time.sleep(self._poll)

    def entity_erase(self, entity_id: str) -> None:
        self._dispatch("entity-erase", {"entity_id": entity_id})

    def entity_create_line(self, x1, y1, x2, y2, layer=None):
        return self._dispatch("create-line", {k: v for k, v in {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "layer": layer}.items() if v is not None})

    def entity_create_circle(self, cx, cy, radius, layer=None):
        return self._dispatch("create-circle", {k: v for k, v in {"cx": cx, "cy": cy, "radius": radius, "layer": layer}.items() if v is not None})

    def entity_create_arc(self, cx, cy, radius, start_angle, end_angle, layer=None):
        return self._dispatch("create-arc", {k: v for k, v in {"cx": cx, "cy": cy, "radius": radius, "start_angle": start_angle, "end_angle": end_angle, "layer": layer}.items() if v is not None})

    def annotation_create_text(self, x, y, text, height=None, rotation=None, layer=None):
        return self._dispatch("create-text", {k: v for k, v in {"x": x, "y": y, "text": text, "height": height, "rotation": rotation, "layer": layer}.items() if v is not None})


def _make_windows_text_trigger(hwnd: int) -> Callable[[str], None]:
    """Return a bounded, exact-owner trigger for AutoCAD's command boundary."""
    def trigger(text: str) -> None:
        user32 = ctypes.windll.user32

        def set_native_signature(function: Any, argtypes: list[Any], restype: Any) -> None:
            try:
                function.argtypes = argtypes
                function.restype = restype
            except (AttributeError, TypeError):
                # Test doubles expose the same callable surface without ctypes metadata.
                pass

        get_window_thread_process_id = user32.GetWindowThreadProcessId
        get_class_name = user32.GetClassNameW
        enum_child_windows = user32.EnumChildWindows
        is_window_visible = user32.IsWindowVisible
        show_window = user32.ShowWindow
        set_foreground_window = user32.SetForegroundWindow
        get_foreground_window = user32.GetForegroundWindow
        post_message = user32.PostMessageW
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        set_native_signature(
            get_window_thread_process_id,
            [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)],
            wintypes.DWORD,
        )
        set_native_signature(
            get_class_name,
            [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],
            ctypes.c_int,
        )
        set_native_signature(
            enum_child_windows,
            [wintypes.HWND, callback_type, wintypes.LPARAM],
            wintypes.BOOL,
        )
        set_native_signature(is_window_visible, [wintypes.HWND], wintypes.BOOL)
        set_native_signature(show_window, [wintypes.HWND, ctypes.c_int], wintypes.BOOL)
        set_native_signature(set_foreground_window, [wintypes.HWND], wintypes.BOOL)
        set_native_signature(get_foreground_window, [], wintypes.HWND)
        set_native_signature(
            post_message,
            [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
            wintypes.BOOL,
        )

        def window_pid(window: int) -> int:
            pid = wintypes.DWORD()
            if not get_window_thread_process_id(window, ctypes.byref(pid)):
                raise MCPToolError("WINDOW_IDENTITY_INVALID")
            if not pid.value:
                raise MCPToolError("WINDOW_IDENTITY_INVALID")
            return int(pid.value)

        owner_pid = window_pid(hwnd)
        mdi_clients: List[int] = []
        callback_error: Optional[str] = None

        def callback(child: int, _lparam: int) -> bool:
            nonlocal callback_error
            name = ctypes.create_unicode_buffer(256)
            if not get_class_name(child, name, len(name)):
                callback_error = "WINDOW_CLASS_INVALID"
                return False
            if name.value == "MDIClient":
                mdi_clients.append(child)
            return True

        enum_result = enum_child_windows(hwnd, callback_type(callback), 0)
        if callback_error is not None:
            raise MCPToolError(callback_error)
        if enum_result is not None and not enum_result:
            raise MCPToolError("WINDOW_ENUMERATION_FAILED")
        owned_mdi_clients = [
            child for child in mdi_clients if window_pid(child) == owner_pid
        ]
        visible_owned_mdi_clients = [
            child for child in owned_mdi_clients if is_window_visible(child)
        ]
        if len(visible_owned_mdi_clients) != 1:
            raise MCPToolError("WINDOW_RECEIVER_AMBIGUOUS")
        target = visible_owned_mdi_clients[0]

        if window_pid(hwnd) != owner_pid or window_pid(target) != owner_pid:
            raise MCPToolError("WINDOW_IDENTITY_CHANGED")
        _reacquire_windows_foreground(hwnd)
        if get_foreground_window() != hwnd:
            raise MCPToolError("WINDOW_FOREGROUND_INVALID")

        framed_text = ("\x1b\x1b" + text + "\r").encode("utf-16-le")
        for offset in range(0, len(framed_text), 2):
            if window_pid(hwnd) != owner_pid or window_pid(target) != owner_pid:
                raise MCPToolError("WINDOW_IDENTITY_CHANGED")
            if get_foreground_window() != hwnd:
                raise MCPToolError("WINDOW_FOREGROUND_INVALID")
            code_unit = int.from_bytes(framed_text[offset:offset + 2], "little")
            if not post_message(target, 0x0102, code_unit, 0):
                raise MCPToolError("WINDOW_DELIVERY_FAILED")
    return trigger


def _reacquire_windows_foreground(hwnd: int) -> None:
    """Reacquire one owned top-level window without weakening exact readback."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    def set_native_signature(function: Any, argtypes: list[Any], restype: Any) -> None:
        try:
            function.argtypes = argtypes
            function.restype = restype
        except (AttributeError, TypeError):
            # Test doubles expose the same callable surface without ctypes metadata.
            pass

    get_window_thread_process_id = user32.GetWindowThreadProcessId
    get_current_thread_id = kernel32.GetCurrentThreadId
    attach_thread_input = user32.AttachThreadInput
    show_window = user32.ShowWindow
    set_foreground_window = user32.SetForegroundWindow
    get_foreground_window = user32.GetForegroundWindow
    set_native_signature(
        get_window_thread_process_id,
        [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)],
        wintypes.DWORD,
    )
    set_native_signature(get_current_thread_id, [], wintypes.DWORD)
    set_native_signature(
        attach_thread_input,
        [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL],
        wintypes.BOOL,
    )
    set_native_signature(show_window, [wintypes.HWND, ctypes.c_int], wintypes.BOOL)
    set_native_signature(set_foreground_window, [wintypes.HWND], wintypes.BOOL)
    set_native_signature(get_foreground_window, [], wintypes.HWND)

    current_foreground_hwnd = int(get_foreground_window() or 0)
    if current_foreground_hwnd == hwnd:
        return

    def foreground_snapshot(window: int) -> dict[str, object]:
        if window <= 0:
            return {"hwnd": window, "pid": None}
        process_id = wintypes.DWORD()
        try:
            if not get_window_thread_process_id(window, ctypes.byref(process_id)):
                return {"hwnd": window, "pid": None}
        except Exception:
                return {"hwnd": window, "pid": None}
        return {"hwnd": window, "pid": int(process_id.value)}

    target_snapshot = foreground_snapshot(hwnd)
    caller_thread_id: Optional[int] = None
    foreground_thread_id: Optional[int] = None
    attach_result: object = None
    show_window_result: object = None
    set_foreground_result: object = None
    detach_result: object = None

    def foreground_failure(
        stage: str,
        *,
        before: dict[str, object],
        after_set: Optional[dict[str, object]] = None,
        after_detach: Optional[dict[str, object]] = None,
        cause: Optional[BaseException] = None,
    ) -> MCPToolError:
        diagnostic: dict[str, object] = {
            "stage": stage,
            "target": target_snapshot,
            "caller_thread_id": caller_thread_id,
            "foreground_thread_id": foreground_thread_id,
            "attach_result": attach_result,
            "show_window_result": show_window_result,
            "set_foreground_result": set_foreground_result,
            "detach_result": detach_result,
            "attach_not_required": caller_thread_id == foreground_thread_id,
            "foreground_before": before,
            "foreground_after_set": after_set,
            "foreground_after_detach": after_detach,
        }
        if cause is not None:
            diagnostic["native_error"] = type(cause).__name__
        error = MCPToolError("WINDOW_FOREGROUND_INVALID")
        error._foreground_handoff_diagnostic = diagnostic
        return error

    foreground_before = foreground_snapshot(current_foreground_hwnd)
    if current_foreground_hwnd <= 0:
        raise foreground_failure("ATTACH_FAILED", before=foreground_before)

    def window_thread_id(window: int) -> int:
        process_id = wintypes.DWORD()
        try:
            thread_id = int(
                get_window_thread_process_id(window, ctypes.byref(process_id)) or 0
            )
        except Exception as exc:
            raise foreground_failure("ATTACH_FAILED", before=foreground_before) from exc
        if thread_id <= 0:
            raise foreground_failure("ATTACH_FAILED", before=foreground_before)
        return thread_id

    try:
        caller_thread_id = int(get_current_thread_id() or 0)
        foreground_thread_id = window_thread_id(current_foreground_hwnd)
    except MCPToolError:
        raise
    except Exception as exc:
        raise foreground_failure(
            "ATTACH_FAILED", before=foreground_before, cause=exc
        ) from exc
    if caller_thread_id <= 0:
        raise foreground_failure("ATTACH_FAILED", before=foreground_before)

    attached = False
    failure: Optional[MCPToolError] = None
    foreground_after_set: Optional[dict[str, object]] = None
    foreground_after_detach: Optional[dict[str, object]] = None
    try:
        if caller_thread_id != foreground_thread_id:
            try:
                attach_result = attach_thread_input(
                    caller_thread_id, foreground_thread_id, True
                )
                attached = bool(attach_result)
            except Exception as exc:
                failure = foreground_failure(
                    "ATTACH_FAILED", before=foreground_before, cause=exc
                )
            if not attached and failure is None:
                failure = foreground_failure("ATTACH_FAILED", before=foreground_before)
        if attached or caller_thread_id == foreground_thread_id:
            try:
                show_window_result = show_window(hwnd, 9)
                set_foreground_result = set_foreground_window(hwnd)
                foreground_after_set = foreground_snapshot(
                    int(get_foreground_window() or 0)
                )
                if int(foreground_after_set["hwnd"]) != hwnd:
                    failure = foreground_failure(
                        "EXACT_HWND_READBACK_MISMATCH",
                        before=foreground_before,
                        after_set=foreground_after_set,
                    )
            except MCPToolError as exc:
                failure = exc
            except Exception as exc:
                failure = foreground_failure(
                    "SHOW_OR_SET_NATIVE_ERROR",
                    before=foreground_before,
                    after_set=foreground_after_set,
                    cause=exc,
                )
    finally:
        if attached:
            detach_failure: Optional[MCPToolError] = None
            try:
                detach_result = attach_thread_input(
                    caller_thread_id, foreground_thread_id, False
                )
                detached = bool(detach_result)
                foreground_after_detach = foreground_snapshot(
                    int(get_foreground_window() or 0)
                )
                if not detached:
                    detach_failure = foreground_failure(
                        "DETACH_FAILED",
                        before=foreground_before,
                        after_set=foreground_after_set,
                        after_detach=foreground_after_detach,
                    )
            except Exception as exc:
                detach_failure = foreground_failure(
                    "DETACH_FAILED",
                    before=foreground_before,
                    after_set=foreground_after_set,
                    after_detach=foreground_after_detach,
                    cause=exc,
                )
            if failure is not None:
                diagnostic = failure._foreground_handoff_diagnostic
                diagnostic["foreground_after_detach"] = foreground_after_detach
                diagnostic["detach_result"] = detach_result
            if detach_failure is not None:
                if failure is None:
                    failure = detach_failure
                else:
                    diagnostic = failure._foreground_handoff_diagnostic
                    diagnostic["detach_stage"] = "DETACH_FAILED"
    if failure is not None:
        raise failure


def make_windows_lisp_trigger(hwnd: int) -> Callable[[str], None]:
    """Return a trigger that types a complete AutoLISP expression in AutoCAD."""
    return _make_windows_text_trigger(hwnd)


def make_windows_start_tab_no_document_probe(hwnd: int) -> Callable[[], bool]:
    """Return a probe that positively recognizes AutoCAD's documentless Start tab."""
    read_title = _make_windows_main_window_title_reader(hwnd)

    def probe() -> bool:
        title = read_title()
        return title is not None and title.casefold().endswith("[start]")

    return probe


def make_windows_start_tab_document_ready_probe(hwnd: int) -> Callable[[], bool]:
    """Return a probe that confirms QNEW left AutoCAD's documentless Start tab."""
    read_title = _make_windows_main_window_title_reader(hwnd)

    def probe() -> bool:
        title = read_title()
        return title is not None and not title.casefold().endswith("[start]")

    return probe


def _resolve_bundle_plugin_path(bundle_path: str) -> str:
    """Resolve the single existing DLL declared by a disposable bundle manifest."""
    bundle_root = Path(bundle_path).resolve()
    if not bundle_root.is_dir():
        raise ValueError("bootstrap_bundle_path must be an existing directory")
    manifest_path = bundle_root / "PackageContents.xml"
    if not manifest_path.is_file():
        raise ValueError("bootstrap_bundle_path must contain PackageContents.xml")

    try:
        manifest_root = ET.parse(manifest_path).getroot()
    except ET.ParseError as exc:
        raise ValueError("bootstrap bundle manifest must be valid XML") from exc
    entries = manifest_root.findall("./Components/ComponentEntry")
    if len(entries) != 1:
        raise ValueError("bootstrap bundle manifest must contain exactly one ComponentEntry")

    module_name = entries[0].attrib.get("ModuleName", "")
    module_path = Path(module_name)
    if not module_name or module_path.is_absolute():
        raise ValueError("bootstrap bundle ModuleName must be a non-empty relative path")
    resolved_module_path = (bundle_root / module_name.replace("/", os.sep)).resolve()
    if not resolved_module_path.is_relative_to(bundle_root):
        raise ValueError("bootstrap bundle ModuleName must remain inside the bundle root")
    if resolved_module_path.suffix.casefold() != ".dll":
        raise ValueError("bootstrap bundle ModuleName must name a DLL")
    if not resolved_module_path.is_file():
        raise ValueError("bootstrap bundle ModuleName must name an existing DLL")
    return str(resolved_module_path)


def make_windows_start_tab_session_factory(
    acad_executable: str,
    script_directory: str,
    *,
    bootstrap_plugin_path: Optional[str] = None,
    bootstrap_bundle_path: Optional[str] = None,
    bootstrap_lisp_path: Optional[str] = None,
    ipc_root: Optional[str] = None,
    timeout_s: float = 30.0,
    poll_interval_s: float = 0.1,
    timing_recorder: Optional[BootstrapTimingRecorder] = None,
    stage_timing_enabled: bool = False,
) -> Callable[[], WindowsAutoCADStartTabSession]:
    """Create a factory for disposable AutoCAD sessions bootstrapped by a script."""
    executable = Path(acad_executable).resolve()
    script_root = Path(script_directory).resolve()
    if executable.name.casefold() != "acad.exe" or not executable.is_file():
        raise ValueError("acad_executable must be an existing acad.exe")
    if not script_root.is_dir():
        raise ValueError("script_directory must be an existing directory")
    if bootstrap_plugin_path is not None and bootstrap_bundle_path is not None:
        raise ValueError(
            "bootstrap_plugin_path and bootstrap_bundle_path are mutually exclusive"
        )
    resolved_bootstrap_plugin_path = bootstrap_plugin_path
    if bootstrap_bundle_path is not None:
        resolved_bootstrap_plugin_path = _resolve_bundle_plugin_path(
            bootstrap_bundle_path
        )

    def factory() -> WindowsAutoCADStartTabSession:
        return WindowsAutoCADStartTabSession(
            str(executable),
            str(script_root),
            bootstrap_plugin_path=resolved_bootstrap_plugin_path,
            bootstrap_lisp_path=bootstrap_lisp_path,
            ipc_root=ipc_root,
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
            timing_recorder=timing_recorder,
            stage_timing_enabled=stage_timing_enabled,
        )

    return factory


def _launch_windows_autocad_with_script(
    executable: Path,
    script_path: Path,
) -> Any:
    return subprocess.Popen(
        [str(executable), "/nologo", "/b", str(script_path)],
        close_fds=True,
    )


def _find_windows_main_window_for_pid(pid: int) -> int:
    if type(pid) is not int or pid <= 0:
        raise ValueError("pid must be a positive integer")
    user32 = ctypes.windll.user32
    enum_windows = user32.EnumWindows
    get_window_thread_process_id = user32.GetWindowThreadProcessId
    is_window_visible = user32.IsWindowVisible
    get_window_text_length = user32.GetWindowTextLengthW
    get_window_text = user32.GetWindowTextW
    try:
        enum_windows.argtypes = [
            ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
            wintypes.LPARAM,
        ]
        enum_windows.restype = wintypes.BOOL
        get_window_thread_process_id.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_window_thread_process_id.restype = wintypes.DWORD
        is_window_visible.argtypes = [wintypes.HWND]
        is_window_visible.restype = wintypes.BOOL
        get_window_text_length.argtypes = [wintypes.HWND]
        get_window_text_length.restype = ctypes.c_int
        get_window_text.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        get_window_text.restype = ctypes.c_int
    except (AttributeError, TypeError):
        pass

    windows: list[int] = []

    def callback(window: int, _lparam: int) -> bool:
        observed_pid = wintypes.DWORD()
        if not get_window_thread_process_id(window, ctypes.byref(observed_pid)):
            return True
        if int(observed_pid.value) != pid or not is_window_visible(window):
            return True
        length = int(get_window_text_length(window))
        if length <= 0:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        if int(get_window_text(window, title, len(title))) > 0:
            windows.append(int(window))
        return True

    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    enum_windows(callback_type(callback), 0)
    if len(windows) == 1:
        return windows[0]
    return 0


def _close_windows_main_window(hwnd: int) -> None:
    if type(hwnd) is not int or hwnd <= 0:
        raise ValueError("hwnd must be a positive integer")
    post_message = ctypes.windll.user32.PostMessageW
    try:
        post_message.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        post_message.restype = wintypes.BOOL
    except (AttributeError, TypeError):
        pass
    if not post_message(hwnd, 0x0010, 0, 0):
        raise MCPToolError("START_TAB_BOOTSTRAP_CLOSE_REQUEST_FAILED")


def _make_windows_main_window_title_reader(hwnd: int) -> Callable[[], Optional[str]]:
    if type(hwnd) is not int or hwnd <= 0:
        raise ValueError("hwnd must be a positive integer")

    def read_title() -> Optional[str]:
        user32 = ctypes.windll.user32
        get_window_text_length = user32.GetWindowTextLengthW
        get_window_text = user32.GetWindowTextW
        try:
            get_window_text_length.argtypes = [wintypes.HWND]
            get_window_text_length.restype = ctypes.c_int
            get_window_text.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            get_window_text.restype = ctypes.c_int
        except (AttributeError, TypeError):
            pass
        length = int(get_window_text_length(hwnd))
        if length <= 0:
            return None
        title = ctypes.create_unicode_buffer(length + 1)
        if int(get_window_text(hwnd, title, len(title))) <= 0:
            return None
        normalized = title.value.rstrip()
        return normalized or None

    return read_title


def make_windows_command_trigger(hwnd: int) -> Callable[[str], None]:
    """Return a trigger that types an AutoCAD command sequence.

    Use ``\r`` between command inputs, for example ``"_.CLOSE\r_N"``.
    The final Enter is appended by the trigger.
    """
    return _make_windows_text_trigger(hwnd)


def make_windows_dispatch_trigger(hwnd: int) -> Callable[[], None]:
    """Return a trigger that invokes the loaded AutoLISP dispatcher."""
    raw_trigger = make_windows_lisp_trigger(hwnd)

    def trigger() -> None:
        raw_trigger("(c:mcp-dispatch)")

    setattr(trigger, "_mcp_claim_bound", True)
    return trigger


CallTool = Callable[[str, str, Dict[str, Any]], Dict[str, Any]]


class LiveMCPClient:
    """Adapter around a runtime-provided ``call_tool(tool, operation, args)`` callback."""
    def __init__(self, call_tool: CallTool, retries: int = 2, retry_delay_s: float = 0.5) -> None:
        self._call, self._retries, self._retry_delay_s = call_tool, retries, retry_delay_s

    def _invoke(self, tool: str, operation: str, **kwargs: Any) -> Dict[str, Any]:
        result = self._call(tool, operation, {k: v for k, v in kwargs.items() if v is not None})
        if result.get("ok") is False:
            error = str(result.get("error", "unknown MCP error"))
            if "timeout" in error.lower():
                raise MCPTimeoutError(error)
            raise MCPToolError(error)
        return result

    def drawing_open(self, path: str): return self._invoke("drawing", "open", data={"path": path})
    def drawing_close(self, save_changes=False): self._invoke("drawing", "close", data={"save_changes": save_changes})
    def drawing_list_open_paths(self): return self._invoke("drawing", "list_open_paths")["payload"]["paths"]
    def drawing_save(self, path=None): self._invoke("drawing", "save", data={"path": path} if path else {})
    def drawing_save_as_dxf(self, path): self._invoke("drawing", "save_as_dxf", data={"path": path})
    def drawing_get_variables(self, names): return self._invoke("drawing", "get_variables", data={"names": names})["payload"]
    def block_get_attributes(self, entity_id): return self._invoke("block", "get_attributes", entity_id=entity_id)["payload"].get("attributes", {})
    def block_update_attribute(self, entity_id, tag, value): self._invoke("block", "update_attribute", entity_id=entity_id, tag=tag, value=value)
    def entity_create_line(self, x1, y1, x2, y2, layer=None): return self._invoke("entity", "create_line", x1=x1, y1=y1, x2=x2, y2=y2, layer=layer)["payload"]
    def entity_create_circle(self, cx, cy, radius, layer=None): return self._invoke("entity", "create_circle", data={"cx": cx, "cy": cy, "radius": radius}, layer=layer)["payload"]
    def entity_create_arc(self, cx, cy, radius, start_angle, end_angle, layer=None): return self._invoke("entity", "create_arc", data={"cx": cx, "cy": cy, "radius": radius, "start_angle": start_angle, "end_angle": end_angle}, layer=layer)["payload"]
    def annotation_create_text(self, x, y, text, height=None, rotation=None, layer=None): return self._invoke("annotation", "create_text", data={"x": x, "y": y, "text": text, "height": height, "rotation": rotation}, layer=layer)["payload"]
    def entity_list(self, layer=None): return self._invoke("entity", "list", layer=layer)["payload"]["entities"]
    def entity_get(self, entity_id):
        last_error = None
        for attempt in range(self._retries + 1):
            try:
                return self._invoke("entity", "get", entity_id=entity_id)["payload"]
            except MCPTimeoutError as exc:
                last_error = exc
                if attempt < self._retries:
                    time.sleep(self._retry_delay_s)
        raise last_error
    def entity_erase(self, entity_id): self._invoke("entity", "erase", entity_id=entity_id)
    def view_get_screenshot(self):
        payload = self._invoke("view", "get_screenshot").get("payload")
        return payload if isinstance(payload, bytes) else base64.b64decode(payload)
