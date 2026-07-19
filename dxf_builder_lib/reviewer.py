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

MỞ RỘNG (round-trip INSERT, mục "việc nên làm tiếp" trong HANDOFF.md):
ngoài primitive thô (line/circle/arc/text) ở trên, `review_dxf()` giờ còn
đối chiếu lại từng entity INSERT do `semantic_components.py` chèn (Semantic
Component API, mục 12.4) — dùng CÙNG chiến lược round-trip qua `handle`,
so với `build_result.written_component_by_part_id` (nguồn sự thật đọc lại
trực tiếp từ entity INSERT ngay lúc build, xem `builder.py`). Các trường
kiểm tra: `handle`, block name (`entity.dxf.name`), `layer`, insert point
(x/y/z), `xscale`/`yscale`/`zscale`, `rotation`, và từng ATTRIB (tag/text).
Lỗi INSERT được gom vào `ReviewResult.component_mismatches` — dùng
`ComponentMismatch` (dataclass có field/expected/actual, không phải chuỗi
tự do) để dễ lọc/debug theo part_id hoặc theo field cụ thể, tách biệt với
`mismatches` (primitive thô, vẫn là List[str] như cũ, không đổi hợp đồng
cũ). Repair #1 cho INSERT KHÔNG nằm trong phạm vi module này (xem
HANDOFF.md mục "việc nên làm tiếp" #2 — để lại cho Repair #1/#2 sau).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

from .builder import BuildResult

_DEFAULT_TOLERANCE_MM = 1e-6
_ROTATION_TOLERANCE_DEG = 1e-4
_EXPECTED_DXFTYPE = {"line": "LINE", "circle": "CIRCLE", "arc": "ARC", "text": "TEXT"}
_INSERT_SCALE_FIELDS = ("xscale", "yscale", "zscale")


@dataclass
class ComponentMismatch:
    """1 lỗi cụ thể phát hiện khi round-trip kiểm tra 1 entity INSERT
    (Semantic Component). Structured — KHÔNG phải chuỗi tự do như
    `mismatches` (primitive thô) — để dễ lọc/debug theo `part_id` hoặc
    theo `field` cụ thể (vd lọc riêng mọi lỗi rotation, hay mọi lỗi của
    1 part_id). `message` là bản người-đọc-được, dùng khi cần in báo cáo
    dạng text; `str(mismatch)` trả về đúng `message` để vẫn in được trực
    tiếp trong 1 report gộp chung với `mismatches`."""

    part_id: str
    field: str
    expected: object
    actual: object
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


@dataclass
class ReviewResult:
    passed: bool
    checked_count: int
    mismatches: List[str] = field(default_factory=list)
    # --- round-trip INSERT (Semantic Component API, xem docstring module) ---
    component_checked_count: int = 0
    component_mismatches: List[ComponentMismatch] = field(default_factory=list)

    def format_report(self) -> str:
        """Report lỗi có cấu trúc, gom theo part_id — dùng khi debug thủ
        công (in ra console/log), KHÔNG thay thế `mismatches`/
        `component_mismatches` (vẫn nguyên cho code xử lý tiếp, vd
        Repair #1 dùng `mismatches` trực tiếp)."""
        lines: List[str] = []
        status = "PASS" if self.passed else "FAIL"
        lines.append(f"Reviewer #1: {status}")
        lines.append(
            f"  primitives: {self.checked_count} checked, {len(self.mismatches)} mismatch"
        )
        for m in self.mismatches:
            lines.append(f"    - {m}")
        lines.append(
            f"  components (INSERT): {self.component_checked_count} checked, "
            f"{len(self.component_mismatches)} mismatch"
        )
        by_part: Dict[str, List[ComponentMismatch]] = {}
        for cm in self.component_mismatches:
            by_part.setdefault(cm.part_id, []).append(cm)
        for part_id in sorted(by_part):
            lines.append(f"    - {part_id}:")
            for cm in by_part[part_id]:
                lines.append(
                    f"        [{cm.field}] expected={cm.expected!r} actual={cm.actual!r} — {cm.message}"
                )
        return "\n".join(lines)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _dist3(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


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

    component_mismatches: List[ComponentMismatch] = []
    component_checked = 0

    for part_id, handle in build_result.component_handle_by_part_id.items():
        written = build_result.written_component_by_part_id.get(part_id)
        if written is None:
            component_mismatches.append(ComponentMismatch(
                part_id=part_id, field="written_component", expected="<có ghi nhận>", actual=None,
                message=f"{part_id}: không có written_component ghi nhận lúc build (bug ở builder.py)",
            ))
            continue

        entity = db.get(handle)
        if entity is None:
            component_mismatches.append(ComponentMismatch(
                part_id=part_id, field="handle", expected=handle, actual=None,
                message=f"{part_id}: handle INSERT '{handle}' không tìm thấy sau khi đọc lại DXF",
            ))
            continue

        component_checked += 1
        dxftype = entity.dxftype()
        if dxftype != "INSERT":
            component_mismatches.append(ComponentMismatch(
                part_id=part_id, field="dxftype", expected="INSERT", actual=dxftype,
                message=f"{part_id}: kỳ vọng entity kiểu INSERT, đọc lại được {dxftype}",
            ))
            continue

        actual_block_name = entity.dxf.name
        if actual_block_name != written["block_name"]:
            component_mismatches.append(ComponentMismatch(
                part_id=part_id, field="block_name",
                expected=written["block_name"], actual=actual_block_name,
                message=(
                    f"{part_id}: kỳ vọng block name '{written['block_name']}', "
                    f"đọc lại được '{actual_block_name}'"
                ),
            ))

        actual_layer = entity.dxf.layer
        if actual_layer != written["layer"]:
            component_mismatches.append(ComponentMismatch(
                part_id=part_id, field="layer", expected=written["layer"], actual=actual_layer,
                message=f"{part_id}: kỳ vọng layer INSERT '{written['layer']}', đọc lại được '{actual_layer}'",
            ))

        actual_insert_v = entity.dxf.insert
        actual_insert = (actual_insert_v.x, actual_insert_v.y, actual_insert_v.z)
        expected_insert = written["insert"]
        if _dist3(actual_insert, expected_insert) > tolerance_mm:
            component_mismatches.append(ComponentMismatch(
                part_id=part_id, field="insert_point", expected=expected_insert, actual=actual_insert,
                message=f"{part_id}: điểm chèn INSERT lệch — ghi {expected_insert}, đọc lại {actual_insert}",
            ))

        for axis in _INSERT_SCALE_FIELDS:
            actual_val = getattr(entity.dxf, axis)
            expected_val = written[axis]
            if abs(actual_val - expected_val) > tolerance_mm:
                component_mismatches.append(ComponentMismatch(
                    part_id=part_id, field=axis, expected=expected_val, actual=actual_val,
                    message=f"{part_id}: {axis} INSERT lệch — ghi {expected_val}, đọc lại {actual_val}",
                ))

        actual_rotation = entity.dxf.rotation
        expected_rotation = written["rotation_deg"]
        if abs(actual_rotation - expected_rotation) > _ROTATION_TOLERANCE_DEG:
            component_mismatches.append(ComponentMismatch(
                part_id=part_id, field="rotation_deg",
                expected=expected_rotation, actual=actual_rotation,
                message=(
                    f"{part_id}: góc rotation INSERT lệch — ghi {expected_rotation}, "
                    f"đọc lại {actual_rotation}"
                ),
            ))

        expected_attribs: Dict[str, str] = written["attribs"]
        actual_attribs = {a.dxf.tag: a.dxf.text for a in entity.attribs}
        for tag, expected_text in expected_attribs.items():
            if tag not in actual_attribs:
                component_mismatches.append(ComponentMismatch(
                    part_id=part_id, field=f"attrib:{tag}", expected=expected_text, actual=None,
                    message=f"{part_id}: thiếu ATTRIB '{tag}' sau khi đọc lại DXF (kỳ vọng '{expected_text}')",
                ))
            elif actual_attribs[tag] != expected_text:
                component_mismatches.append(ComponentMismatch(
                    part_id=part_id, field=f"attrib:{tag}",
                    expected=expected_text, actual=actual_attribs[tag],
                    message=(
                        f"{part_id}: ATTRIB '{tag}' lệch — ghi '{expected_text}', "
                        f"đọc lại '{actual_attribs[tag]}'"
                    ),
                ))
        for tag in sorted(set(actual_attribs) - set(expected_attribs)):
            component_mismatches.append(ComponentMismatch(
                part_id=part_id, field=f"attrib:{tag}", expected=None, actual=actual_attribs[tag],
                message=(
                    f"{part_id}: ATTRIB thừa '{tag}'='{actual_attribs[tag]}' "
                    f"không có trong ghi nhận lúc build"
                ),
            ))

    return ReviewResult(
        passed=(len(mismatches) == 0 and len(component_mismatches) == 0),
        checked_count=checked,
        mismatches=mismatches,
        component_checked_count=component_checked,
        component_mismatches=component_mismatches,
    )
