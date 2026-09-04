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
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol


class MCPTimeoutError(RuntimeError):
    """An MCP operation timed out."""


class MCPToolError(RuntimeError):
    """An MCP operation failed."""


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

class FileIPCLiveMCPClient:
    """Minimal File IPC client for a loaded AutoLISP MCP dispatcher."""
    def __init__(self, ipc_dir: str, trigger: Optional[Callable[[], None]] = None,
                 timeout_s: float = 10.0, poll_interval_s: float = 0.1,
                 raw_lisp_trigger: Optional[Callable[[str], None]] = None,
                 bootstrap_lisp_path: Optional[str] = None,
                 document_settle_s: float = 2.0,
                 command_trigger: Optional[Callable[[str], None]] = None,
                 start_tab_no_document_probe: Optional[Callable[[], bool]] = None,
                 legacy_fixture_mode: Optional[bool] = None) -> None:
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
        self._active_drawing_path: Optional[str] = None

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
                    return _validate_file_ipc_result(data, request_id, claim)
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

    def drawing_open(self, path: str) -> Dict[str, Any]:
        if self._raw_lisp_trigger is not None and self._bootstrap_lisp_path is not None:
            normalized_path = path.replace("\\", "/").replace('"', '\\"')
            expected_path = _normalized_autocad_path(path)
            active_path = ""
            for attempt in range(2):
                try:
                    self._raw_lisp_trigger(
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
                        '(setq mcp-open-doc (vla-open mcp-docs "' + normalized_path + '"))) '
                        '(vla-activate mcp-open-doc))'
                    )
                except (MCPTimeoutError, MCPToolError) as exc:
                    if (
                        self._command_trigger is None
                        or attempt != 0
                        or not self._start_tab_no_document_is_proven(exc)
                    ):
                        raise
                    self._command_trigger('_.OPEN\r"' + normalized_path + '"')
                time.sleep(self._document_settle_s)
                self._active_drawing_path = expected_path
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

    def drawing_save(self, path: Optional[str] = None) -> None:
        self._dispatch("drawing-save", {"path": path} if path else {})

    def drawing_close(self, save_changes: bool = False) -> None:
        if self._raw_lisp_trigger is not None:
            if save_changes:
                self._raw_lisp_trigger(
                    "(progn (vl-load-com) "
                    "(vla-close (vla-get-ActiveDocument (vlax-get-acad-object)) "
                    ":vlax-true))"
                )
            else:
                if self._command_trigger is not None:
                    self._command_trigger("_.CLOSE\r_N")
                else:
                    self._raw_lisp_trigger('(command-s "_.CLOSE" "_N")')
            time.sleep(self._document_settle_s)
            expected_path = self._active_drawing_path
            if self._command_trigger is not None and expected_path is not None:
                deadline = time.time() + max(5.0, self._document_settle_s * 3.0)
                while time.time() < deadline:
                    try:
                        open_paths = {
                            _normalized_autocad_path(open_path)
                            for open_path in self.drawing_list_open_paths()
                        }
                        if expected_path not in open_paths:
                            break
                    except (MCPTimeoutError, MCPToolError):
                        pass
                    time.sleep(self._poll)
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
        self._active_drawing_path = _normalized_autocad_path(path)

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
        if get_foreground_window() != hwnd:
            show_window(hwnd, 9)
            set_foreground_window(hwnd)
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


def make_windows_lisp_trigger(hwnd: int) -> Callable[[str], None]:
    """Return a trigger that types a complete AutoLISP expression in AutoCAD."""
    return _make_windows_text_trigger(hwnd)


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
