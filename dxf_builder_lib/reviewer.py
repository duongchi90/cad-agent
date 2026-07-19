"""
reviewer.py — Reviewer #1: Headless (IR ⇄ DXF), mục 2 tài liệu kiến trúc,
đứng ngay sau DXF Builder. Vai trò đã chốt rõ trong tài liệu kiến trúc:
"chỉ bắt lỗi DỊCH THUẬT (Builder sai), KHÔNG bắt lỗi nhận thức" — nghĩa là
module này KHÔNG phán đoán Pattern Recognition/Constraint Detection có
hiểu đúng bản vẽ hay không (đó là việc của Reviewer #2, visual+zoom, so với
ảnh scan gốc), mà chỉ xác nhận builder.py đã ghi vào file .dxf ĐÚNG những
gì nó DỰ ĐỊNH ghi (deterministic, so số, không dùng VLM — đúng mục 4/7).

CÁCH LÀM: đọc lại CHÍNH file .dxf vừa build bằng `ezdxf.readfile()` (mô
phỏng đúng bước "AutoCAD MCP: drawing_open" sẽ làm ở Phase 4 — nếu round-
trip qua ezdxf reader đã sai thì round-trip qua AutoCAD LT thật chắc chắn
cũng sai), tra theo `handle` (đã xác nhận giữ nguyên 100% qua AutoCAD LT
thật — mục 9.4) để lấy lại đúng entity, rồi so KHỚP TUYỆT ĐỐI (trong
ngưỡng sai số dấu phẩy động rất nhỏ) với `written_geometry_by_primitive_id`
mà `builder.py` đã trả về — đây là "nguồn sự thật" đúng, KHÔNG so lại với
toạ độ thô trong `primitive_doc` (vì builder có thể đã áp solved override
từ Constraint Solving, so với toạ độ thô sẽ ra dương tính giả).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

from .builder import BuildResult

_DEFAULT_TOLERANCE_MM = 1e-6
_EXPECTED_DXFTYPE = {"line": "LINE", "circle": "CIRCLE", "arc": "ARC", "text": "TEXT"}


@dataclass
class ReviewResult:
    passed: bool
    checked_count: int
    mismatches: List[str] = field(default_factory=list)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def review_dxf(build_result: BuildResult, tolerance_mm: float = _DEFAULT_TOLERANCE_MM) -> ReviewResult:
    """Đọc lại `build_result.output_path` và đối chiếu từng primitive đã
    build (theo handle) với `written_geometry_by_primitive_id`. Raise
    ImportError nếu chưa cài `ezdxf` (cùng chiến lược lazy-import khác
    trong dự án)."""
    try:
        import ezdxf
    except ImportError as exc:
        raise ImportError(
            "Cần cài package 'ezdxf' để dùng Reviewer #1: "
            "pip install ezdxf --break-system-packages"
        ) from exc

    doc = ezdxf.readfile(build_result.output_path)
    db = doc.entitydb

    mismatches: List[str] = []
    checked = 0

    for pid, handle in build_result.handle_by_primitive_id.items():
        written = build_result.written_geometry_by_primitive_id.get(pid)
        expected_layer = build_result.layer_by_primitive_id.get(pid)
        if written is None:
            mismatches.append(f"{pid}: không có written_geometry ghi nhận lúc build (bug ở builder.py)")
            continue

        entity = db.get(handle)
        if entity is None:
            mismatches.append(f"{pid}: handle '{handle}' không tìm thấy sau khi đọc lại DXF")
            continue

        checked += 1
        dxftype = entity.dxftype()
        expected_dxftype = _EXPECTED_DXFTYPE.get(written["type"])
        if dxftype != expected_dxftype:
            mismatches.append(
                f"{pid}: kỳ vọng entity kiểu {expected_dxftype}, đọc lại được {dxftype}"
            )
            continue

        actual_layer = entity.dxf.layer
        if expected_layer is not None and actual_layer != expected_layer:
            mismatches.append(
                f"{pid}: kỳ vọng layer '{expected_layer}', đọc lại được '{actual_layer}'"
            )

        if written["type"] == "line":
            actual_start = (entity.dxf.start.x, entity.dxf.start.y)
            actual_end = (entity.dxf.end.x, entity.dxf.end.y)
            if _dist(actual_start, written["start"]) > tolerance_mm:
                mismatches.append(f"{pid}: điểm đầu LINE lệch — ghi {written['start']}, đọc lại {actual_start}")
            if _dist(actual_end, written["end"]) > tolerance_mm:
                mismatches.append(f"{pid}: điểm cuối LINE lệch — ghi {written['end']}, đọc lại {actual_end}")

        elif written["type"] == "circle":
            actual_center = (entity.dxf.center.x, entity.dxf.center.y)
            if _dist(actual_center, written["center"]) > tolerance_mm:
                mismatches.append(f"{pid}: tâm CIRCLE lệch — ghi {written['center']}, đọc lại {actual_center}")
            if abs(entity.dxf.radius - written["radius"]) > tolerance_mm:
                mismatches.append(
                    f"{pid}: bán kính CIRCLE lệch — ghi {written['radius']}, đọc lại {entity.dxf.radius}"
                )

        elif written["type"] == "arc":
            actual_center = (entity.dxf.center.x, entity.dxf.center.y)
            if _dist(actual_center, written["center"]) > tolerance_mm:
                mismatches.append(f"{pid}: tâm ARC lệch — ghi {written['center']}, đọc lại {actual_center}")
            if abs(entity.dxf.radius - written["radius"]) > tolerance_mm:
                mismatches.append(f"{pid}: bán kính ARC lệch")
            if abs(entity.dxf.start_angle - written["start_angle_deg"]) > 1e-4:
                mismatches.append(f"{pid}: góc bắt đầu ARC lệch")
            if abs(entity.dxf.end_angle - written["end_angle_deg"]) > 1e-4:
                mismatches.append(f"{pid}: góc kết thúc ARC lệch")

        elif written["type"] == "text":
            if entity.dxf.text != written["content"]:
                mismatches.append(
                    f"{pid}: nội dung TEXT lệch — ghi {written['content']!r}, đọc lại {entity.dxf.text!r}"
                )
            actual_insert = (entity.dxf.insert.x, entity.dxf.insert.y)
            if _dist(actual_insert, written["insert"]) > tolerance_mm:
                mismatches.append(f"{pid}: vị trí TEXT lệch")

    # thiếu-hụt ngược: mọi primitive Builder đã coi là skip (không vẽ được)
    # không thuộc trách nhiệm Reviewer #1 (đó là lỗi dữ liệu Phase 1/2 gốc,
    # không phải lỗi round-trip DXF) — không kiểm ở đây theo thiết kế.

    return ReviewResult(passed=(len(mismatches) == 0), checked_count=checked, mismatches=mismatches)
