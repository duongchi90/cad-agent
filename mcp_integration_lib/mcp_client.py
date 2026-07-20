"""Transport-independent adapter for the AutoCAD MCP operations used in Phase 4."""
from __future__ import annotations

import base64
import json
import ctypes
from ctypes import wintypes
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol


class MCPTimeoutError(RuntimeError):
    """An MCP operation timed out."""


class MCPToolError(RuntimeError):
    """An MCP operation failed."""


class MCPClient(Protocol):
    def drawing_open(self, path: str) -> Dict[str, Any]: ...
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
        self.fail_entity_get = fail_entity_get

    def _new_handle(self) -> str:
        handle = format(self._next_handle, "X")
        self._next_handle += 1
        return handle

    def preload_entity(self, handle: str, dxftype: str, layer: str, geom: Dict[str, Any]) -> None:
        self._entities[handle] = _FakeEntity(handle, dxftype, layer, geom)

    def drawing_open(self, path: str) -> Dict[str, Any]:
        self.opened_path = path
        return {"ok": True, "payload": {"path": path, "entity_count": len(self._entities)}}

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
                 timeout_s: float = 10.0, poll_interval_s: float = 0.1) -> None:
        self._dir, self._trigger = Path(ipc_dir), trigger
        self._timeout, self._poll = timeout_s, poll_interval_s

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
        return self._dispatch("drawing-open", {"path": path})

    def entity_get(self, entity_id: str) -> Dict[str, Any]:
        return self._dispatch("entity-get", {"entity_id": entity_id})

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


def make_windows_dispatch_trigger(hwnd: int) -> Callable[[], None]:
    """Return a trigger that invokes the loaded AutoLISP dispatcher."""
    def trigger() -> None:
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
        post = ctypes.windll.user32.PostMessageW
        for ch in "\x1b\x1b(c:mcp-dispatch)\r":
            post(target, 0x0102, ord(ch), 0)
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
