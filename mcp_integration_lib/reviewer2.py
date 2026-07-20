"""Reviewer #2: validate a built DXF after AutoCAD opens it through MCP."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose
from typing import Any, Dict, List

from dxf_builder_lib.builder import BuildResult
from .mcp_client import MCPClient, MCPTimeoutError, MCPToolError

_DXF_TYPE = {"line": "LINE", "circle": "CIRCLE", "arc": "ARC", "text": "TEXT"}


@dataclass
class LiveReviewResult:
    passed: bool = True
    structural_checked: int = 0
    geometry_checked: int = 0
    geometry_degraded: bool = False
    mismatches: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def mismatch(self, message: str) -> None:
        self.passed = False
        self.mismatches.append(message)


def _same(a: Any, b: Any, tolerance: float = 1e-6) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return isclose(float(a), float(b), abs_tol=tolerance)
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)) and {len(a), len(b)} == {2, 3}:
        short, long = (a, b) if len(a) == 2 else (b, a)
        return _same(short, long[:2], tolerance) and isclose(float(long[2]), 0.0, abs_tol=tolerance)
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)) and len(a) == len(b):
        return all(_same(x, y, tolerance) for x, y in zip(a, b))
    return a == b


def _actual(geometry: Dict[str, Any], *names: str) -> Any:
    return next((geometry[name] for name in names if name in geometry), None)


def _check_geometry(pid: str, written: Dict[str, Any], actual: Dict[str, Any], result: LiveReviewResult) -> None:
    kind = written.get("type")
    fields = {
        "line": (("start", "điểm đầu LINE"), ("end", "điểm cuối LINE")),
        "circle": (("center", "tâm CIRCLE"), ("radius", "bán kính CIRCLE")),
        "arc": (("center", "tâm ARC"), ("radius", "bán kính ARC"), ("start_angle_deg", "góc đầu ARC"), ("end_angle_deg", "góc cuối ARC")),
        "text": (("insert", "điểm chèn TEXT"), ("content", "nội dung TEXT"), ("height", "chiều cao TEXT"), ("rotation_deg", "góc xoay TEXT")),
    }.get(kind, ())
    for field, label in fields:
        aliases = (field, "text") if field == "content" else (field, field.replace("_deg", ""))
        if not _same(written.get(field), _actual(actual, *aliases)):
            result.mismatch(f"{pid}: {label} lệch so với geometry đã build")


def review_dxf_live(build_result: BuildResult, client: MCPClient, *, open_drawing: bool = True,
                    attempt_geometry: bool = True) -> LiveReviewResult:
    """Check handles/type/layer always; degrade gracefully when ``entity:get`` times out."""
    result = LiveReviewResult()
    if open_drawing:
        try:
            client.drawing_open(build_result.output_path)
        except (MCPTimeoutError, MCPToolError) as exc:
            result.mismatch(f"drawing: không mở được DXF qua MCP: {exc}")
            return result
    try:
        listed = {str(entity.get("handle")): entity for entity in client.entity_list()}
    except (MCPTimeoutError, MCPToolError) as exc:
        result.mismatch(f"drawing: không thể entity:list qua MCP: {exc}")
        return result
    for pid, handle in build_result.handle_by_primitive_id.items():
        written = build_result.written_geometry_by_primitive_id.get(pid)
        if written is None:
            result.mismatch(f"{pid}: không có written_geometry ghi nhận lúc build")
            continue
        result.structural_checked += 1
        entity = listed.get(str(handle))
        if entity is None:
            result.mismatch(f"{pid}: không thấy handle '{handle}' trong entity:list")
            continue
        expected_type = _DXF_TYPE.get(written.get("type"))
        if expected_type is None or str(entity.get("type", "")).upper() != expected_type:
            result.mismatch(f"{pid}: type AutoCAD không khớp geometry đã build")
        if entity.get("layer") != build_result.layer_by_primitive_id.get(pid, "0"):
            result.mismatch(f"{pid}: layer AutoCAD không khớp geometry đã build")
        if not attempt_geometry:
            continue
        try:
            actual = client.entity_get(str(handle))
        except (MCPTimeoutError, MCPToolError) as exc:
            result.geometry_degraded = True
            result.warnings.append(f"{pid}: bỏ qua geometry check ({exc})")
        else:
            result.geometry_checked += 1
            _check_geometry(pid, written, actual, result)
    return result
