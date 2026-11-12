"""Repair #2: erase and recreate mismatched primitive entities through AutoCAD MCP."""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, List

from dxf_builder_lib.builder import BuildResult
from .mcp_client import MCPClient, MCPTimeoutError, MCPToolError


_SUPPORTED_REPAIR_CAPABILITIES = frozenset({"ERASE", "LINE", "CIRCLE", "ARC", "TEXT"})
_HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CAPABILITY_LAYER_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


@dataclass
class RepairResult:
    repaired_count: int = 0
    skipped_count: int = 0
    repaired_primitive_ids: List[str] = field(default_factory=list)
    skipped_primitive_ids: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)


def _recreate(client: MCPClient, geometry: Dict[str, Any], layer: str) -> str:
    kind = geometry.get("type")
    if kind == "line":
        (x1, y1), (x2, y2) = geometry["start"], geometry["end"]
        response = client.entity_create_line(x1, y1, x2, y2, layer=layer)
    elif kind == "circle":
        x, y = geometry["center"]
        response = client.entity_create_circle(x, y, geometry["radius"], layer=layer)
    elif kind == "arc":
        x, y = geometry["center"]
        response = client.entity_create_arc(x, y, geometry["radius"], geometry["start_angle_deg"], geometry["end_angle_deg"], layer=layer)
    elif kind == "text":
        x, y = geometry["insert"]
        response = client.annotation_create_text(x, y, geometry.get("content", ""), height=geometry.get("height"), rotation=geometry.get("rotation_deg"), layer=layer)
    else:
        raise ValueError("REPAIR_GEOMETRY_INVALID")
    handle = response.get("handle")
    if type(handle) is not str or not _HANDLE_PATTERN.fullmatch(handle):
        raise MCPToolError("REPAIR_HANDLE_INVALID")
    return handle


def execute_supported_repair_capability(
    client: MCPClient,
    *,
    capability: str,
    target_handle: str | None,
    geometry: Mapping[str, object] | None,
    layer: str | None,
) -> str | None:
    """Route one closed repair capability through the existing MCP executor.

    This is intentionally a narrow adapter over the already-owned MCP methods.
    It validates all caller data before the first client mutation and never
    interprets unsupported geometry or arbitrary command-like payloads.
    """

    _validate_capability(capability)
    normalized_target = _validate_target_handle(target_handle, required=capability == "ERASE")
    normalized_layer = _validate_layer(layer, required=False)
    if capability == "ERASE":
        if geometry is not None or layer is not None:
            raise ValueError("REPAIR_GEOMETRY_INVALID")
        _dispatch_erase(client, normalized_target)
        return None

    normalized_geometry = _validate_geometry(capability, geometry)
    try:
        if normalized_target is not None:
            client.entity_erase(normalized_target)
        new_handle = _recreate(client, normalized_geometry, normalized_layer)
        if not _HANDLE_PATTERN.fullmatch(new_handle):
            raise MCPToolError("REPAIR_HANDLE_INVALID")
        return new_handle
    except (MCPTimeoutError, MCPToolError) as exc:
        raise MCPToolError("REPAIR_CAPABILITY_FAILED") from exc


def _validate_capability(capability: object) -> None:
    if type(capability) is not str:
        raise ValueError("REPAIR_CAPABILITY_INVALID")
    if capability not in _SUPPORTED_REPAIR_CAPABILITIES:
        raise ValueError("UNSUPPORTED_REPAIR_OPERATION")


def _validate_target_handle(value: object, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ValueError("REPAIR_HANDLE_INVALID")
        return None
    if type(value) is not str or not _HANDLE_PATTERN.fullmatch(value):
        raise ValueError("REPAIR_HANDLE_INVALID")
    return value


def _validate_layer(value: object, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ValueError("REPAIR_LAYER_INVALID")
        return None
    if type(value) is not str or not _CAPABILITY_LAYER_PATTERN.fullmatch(value):
        raise ValueError("REPAIR_LAYER_INVALID")
    return value


def _finite_number(value: object) -> int | float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise ValueError("REPAIR_GEOMETRY_INVALID")
    try:
        if not math.isfinite(value):
            raise ValueError("REPAIR_GEOMETRY_INVALID")
    except OverflowError as exc:
        raise ValueError("REPAIR_GEOMETRY_INVALID") from exc
    return value


def _point(value: object) -> tuple[int | float, int | float]:
    if type(value) not in (tuple, list) or len(value) != 2:
        raise ValueError("REPAIR_GEOMETRY_INVALID")
    return (_finite_number(value[0]), _finite_number(value[1]))


def _text(value: object) -> str:
    if type(value) is not str or len(value) > 32_768 or "\x00" in value:
        raise ValueError("REPAIR_GEOMETRY_INVALID")
    return value


def _validate_geometry(capability: str, geometry: Mapping[str, object] | None) -> Dict[str, Any]:
    if type(geometry) is not dict or any(type(key) is not str for key in geometry):
        raise ValueError("REPAIR_GEOMETRY_INVALID")
    expected_fields = {
        "LINE": {"type", "start", "end"},
        "CIRCLE": {"type", "center", "radius"},
        "ARC": {"type", "center", "radius", "start_angle_deg", "end_angle_deg"},
        "TEXT": {"type", "content", "insert", "height", "rotation_deg"},
    }[capability]
    if set(geometry) != expected_fields or type(geometry.get("type")) is not str:
        raise ValueError("REPAIR_GEOMETRY_INVALID")
    if geometry["type"] != capability.lower():
        raise ValueError("REPAIR_GEOMETRY_INVALID")
    if capability == "LINE":
        return {
            "type": "line",
            "start": _point(geometry["start"]),
            "end": _point(geometry["end"]),
        }
    if capability == "CIRCLE":
        return {
            "type": "circle",
            "center": _point(geometry["center"]),
            "radius": _finite_number(geometry["radius"]),
        }
    if capability == "ARC":
        return {
            "type": "arc",
            "center": _point(geometry["center"]),
            "radius": _finite_number(geometry["radius"]),
            "start_angle_deg": _finite_number(geometry["start_angle_deg"]),
            "end_angle_deg": _finite_number(geometry["end_angle_deg"]),
        }
    return {
        "type": "text",
        "content": _text(geometry["content"]),
        "insert": _point(geometry["insert"]),
        "height": _finite_number(geometry["height"]),
        "rotation_deg": _finite_number(geometry["rotation_deg"]),
    }


def _dispatch_erase(client: MCPClient, handle: str | None) -> None:
    try:
        client.entity_erase(handle)
    except (MCPTimeoutError, MCPToolError) as exc:
        raise MCPToolError("REPAIR_CAPABILITY_FAILED") from exc


def repair_dxf_live(build_result: BuildResult, mismatches: List[str], client: MCPClient) -> RepairResult:
    """Repair each affected primitive once and update its handle in ``build_result``."""
    result, seen = RepairResult(), set()
    for mismatch in mismatches:
        pid = mismatch.split(":", 1)[0].strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        written = build_result.written_geometry_by_primitive_id.get(pid)
        if written is None:
            result.skipped_count += 1
            result.skipped_primitive_ids.append(pid)
            result.details.append(f"{pid}: bỏ qua repair — không có written_geometry")
            continue
        old_handle = build_result.handle_by_primitive_id.get(pid)
        try:
            kind = written.get("type")
            capability = kind.upper() if type(kind) is str else kind
            build_result.handle_by_primitive_id[pid] = execute_supported_repair_capability(
                client,
                capability=capability,
                target_handle=old_handle,
                geometry=written,
                layer=build_result.layer_by_primitive_id.get(pid, "0"),
            )
        except ValueError as exc:
            result.skipped_count += 1
            result.skipped_primitive_ids.append(pid)
            result.details.append(f"{pid}: bỏ qua repair — {exc}")
            continue
        except (MCPTimeoutError, MCPToolError) as exc:
            raise MCPToolError("REPAIR_CAPABILITY_FAILED") from exc
        result.repaired_count += 1
        result.repaired_primitive_ids.append(pid)
        result.details.append(f"{pid}: đã thay handle '{old_handle}'")
    return result
