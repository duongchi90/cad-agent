"""Transport-independent adapter for the AutoCAD MCP operations used in Phase 4."""
from __future__ import annotations

import base64
import json
import ctypes
from ctypes import wintypes
import ntpath
import re
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


class FileIPCLiveMCPClient:
    """Minimal File IPC client for a loaded AutoLISP MCP dispatcher."""
    def __init__(self, ipc_dir: str = "C:/temp", trigger: Optional[Callable[[], None]] = None,
                 timeout_s: float = 10.0, poll_interval_s: float = 0.1,
                 raw_lisp_trigger: Optional[Callable[[str], None]] = None,
                 bootstrap_lisp_path: Optional[str] = None,
                 document_settle_s: float = 2.0,
                 command_trigger: Optional[Callable[[str], None]] = None) -> None:
        self._dir, self._trigger = Path(ipc_dir), trigger
        self._timeout, self._poll = timeout_s, poll_interval_s
        self._raw_lisp_trigger = raw_lisp_trigger
        self._bootstrap_lisp_path = bootstrap_lisp_path
        self._document_settle_s = document_settle_s
        self._command_trigger = command_trigger
        self._active_drawing_path: Optional[str] = None

    def _dispatch(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        request_id = uuid.uuid4().hex[:12]
        cmd = self._dir / f"autocad_mcp_cmd_{request_id}.json"
        result = self._dir / f"autocad_mcp_result_{request_id}.json"
        self._dir.mkdir(parents=True, exist_ok=True)
        try:
            cmd.write_text(json.dumps({"request_id": request_id, "command": command, "params": params}), encoding="utf-8")
            if self._trigger is None:
                raise MCPToolError("File IPC requires an AutoCAD dispatcher trigger")
            self._trigger()
            deadline = time.time() + self._timeout
            while time.time() < deadline:
                if result.exists():
                    data = json.loads(result.read_text(encoding="utf-8"))
                    if data.get("request_id") == request_id:
                        if not data.get("ok", False):
                            raise MCPToolError(str(data.get("error", "unknown MCP tool error")))
                        return data.get("payload", {})
                time.sleep(self._poll)
            raise MCPTimeoutError(f"Timeout waiting for result (request_id={request_id})")
        finally:
            cmd.unlink(missing_ok=True)
            result.unlink(missing_ok=True)

    def entity_list(self, layer: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._dispatch("entity-list", {k: v for k, v in {"layer": layer}.items() if v is not None}).get("entities", [])

    def drawing_open(self, path: str) -> Dict[str, Any]:
        if self._raw_lisp_trigger is not None and self._bootstrap_lisp_path is not None:
            normalized_path = path.replace("\\", "/").replace('"', '\\"')
            normalized_loader = self._bootstrap_lisp_path.replace("\\", "/").replace('"', '\\"')
            expected_path = _normalized_autocad_path(path)
            active_path = ""
            for attempt in range(2):
                # Opening another document replaces the document-scoped
                # AutoLISP namespace. Invoke AutoCAD's COM API, then load the
                # dispatcher in the newly active document. A ping alone is not
                # enough: it can be answered by the previously active drawing.
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
                    time.sleep(self._document_settle_s)
                    self._raw_lisp_trigger('(load "' + normalized_loader + '")')
                    time.sleep(self._document_settle_s)
                    self._wait_for_dispatcher()
                except (MCPTimeoutError, MCPToolError):
                    # After closing the last drawing AutoCAD may be on the
                    # Start tab, where the document-scoped LISP namespace is
                    # unavailable. A command-level OPEN creates the document
                    # at the UI boundary; then the normal LISP bootstrap can
                    # run in that newly active document.
                    if self._command_trigger is None or attempt != 0:
                        raise
                    self._command_trigger('_.OPEN\r"' + normalized_path + '"')
                    time.sleep(self._document_settle_s)
                    self._raw_lisp_trigger('(load "' + normalized_loader + '")')
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
                # Queue a real AutoCAD command at the command boundary. Calling
                # command-s or vla-close from inside the dispatcher expression
                # runs while the drawing is busy and leaves the document open.
                if self._command_trigger is not None:
                    self._command_trigger("_.CLOSE\r_N")
                else:
                    # Backward-compatible fallback for callers that only provide
                    # a LISP trigger; live Windows callers should provide the
                    # command-level trigger above.
                    self._raw_lisp_trigger('(command-s "_.CLOSE" "_N")')
            time.sleep(self._document_settle_s)
            expected_path = self._active_drawing_path
            if self._command_trigger is not None and expected_path is not None:
                # CLOSE is queued at AutoCAD's command boundary. Wait for the
                # document itself to disappear before a caller opens the next
                # DXF; a fixed sleep alone can leave a stale in-memory drawing
                # active after SAVEAS.
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
            result.unlink(missing_ok=True)

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
                '(setq mcp-dim-value '
                '(if mcp-dim-ent '
                "(vl-catch-all-apply 'vla-get-Measurement "
                '(list (vlax-ename->vla-object mcp-dim-ent))) '
                'nil)) '
                '(cond '
                '((not mcp-dim-ent) '
                '(write-line "ERROR:entity not found" mcp-dim-file)) '
                '((vl-catch-all-error-p mcp-dim-value) '
                '(write-line '
                '(strcat "ERROR:" '
                '(vl-catch-all-error-message mcp-dim-value)) '
                'mcp-dim-file)) '
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
    """Return a trigger that types text at AutoCAD's command boundary."""
    def trigger(text: str) -> None:
        mdi_clients: List[int] = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def callback(child: int, _lparam: int) -> bool:
            name = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(child, name, len(name))
            if name.value == "MDIClient":
                mdi_clients.append(child)
                return False
            return True
        ctypes.windll.user32.EnumChildWindows(hwnd, callback_type(callback), 0)
        target = mdi_clients[0] if mdi_clients else hwnd
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        post = ctypes.windll.user32.PostMessageW
        for ch in "\x1b\x1b" + text + "\r":
            post(target, 0x0102, ord(ch), 0)
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
    return lambda: raw_trigger("(c:mcp-dispatch)")


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
