"""Repair #2: erase and recreate mismatched primitive entities through AutoCAD MCP."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from dxf_builder_lib.builder import BuildResult
from .mcp_client import MCPClient, MCPTimeoutError, MCPToolError


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
        raise ValueError(f"loại primitive không nhận ra để vẽ lại: {kind!r}")
    handle = response.get("handle")
    if not handle:
        raise MCPToolError(f"MCP không trả handle sau khi tạo {kind}")
    return str(handle)


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
        if old_handle is not None:
            try:
                client.entity_erase(old_handle)
            except (MCPTimeoutError, MCPToolError):
                pass
        try:
            build_result.handle_by_primitive_id[pid] = _recreate(client, written, build_result.layer_by_primitive_id.get(pid, "0"))
        except (ValueError, MCPTimeoutError, MCPToolError) as exc:
            result.skipped_count += 1
            result.skipped_primitive_ids.append(pid)
            result.details.append(f"{pid}: bỏ qua repair — {exc}")
            continue
        result.repaired_count += 1
        result.repaired_primitive_ids.append(pid)
        result.details.append(f"{pid}: đã thay handle '{old_handle}'")
    return result
