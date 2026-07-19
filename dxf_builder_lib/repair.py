"""
repair.py — Repair #1: Headless (ezdxf), đứng ngay sau Reviewer #1 trong sơ
đồ pipeline mục 2 tài liệu kiến trúc. Vai trò đã chốt rõ: "sửa lỗi DỊCH
THUẬT do Builder mắc" — không sửa lỗi nhận thức (lỗi đó là việc Reviewer #2
visual+zoom + Repair #2 MCP ở Phase 4).

CHIẾN LƯỢC: xoá entity bị lỗi theo handle (đã xác nhận handle giữ nguyên
100% qua ezdxf round-trip, mục 9.4 tài liệu kiến trúc), rồi vẽ lại đúng
từ `BuildResult.written_geometry_by_primitive_id` — đây là nguồn sự thật
(những gì Builder ĐÃ DỰ ĐỊNH ghi), không tra lại Primitive IR gốc (tránh
đọc sai toạ độ thô khi entity đã được áp solved override từ Constraint
Solving).

Sau khi repair, lưu lại file DXF VÀO ĐÚNG PATH CŨ (ghi đè) rồi trả về
`RepairResult` — caller nên chạy lại `review_dxf(build_result)` trên file
đã repair để xác nhận lỗi đã hết (2 lần review: 1 trước repair để lấy
danh sách lỗi, 1 sau repair để xác nhận). `repair_dxf()` KHÔNG tự gọi
review lại (tách trách nhiệm, cùng nguyên tắc pruning tách khỏi solving,
review tách khỏi build).

Optional dependency: `ezdxf` — cùng chiến lược lazy-import/graceful-skip
đã dùng cho vision_client.py, constraint_solving.py, builder.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set

from .builder import BuildResult

_EXPECTED_DXFTYPE = {"line": "LINE", "circle": "CIRCLE", "arc": "ARC", "text": "TEXT"}


@dataclass
class RepairResult:
    repaired_count: int = 0
    skipped_count: int = 0           # mismatch được ghi nhận nhưng không sửa được (xem lý do bên dưới)
    repaired_primitive_ids: List[str] = field(default_factory=list)
    skipped_primitive_ids: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)


def _primitive_id_from_mismatch(mismatch_msg: str) -> str:
    """Trích primitive_id từ chuỗi mismatch do `review_dxf()` sinh ra.
    Tất cả mismatch đều có dạng '<pid>: ...', nên chỉ cần lấy phần trước
    dấu ':' đầu tiên."""
    return mismatch_msg.split(":", 1)[0].strip()


def repair_dxf(build_result: BuildResult, mismatches: List[str]) -> RepairResult:
    """Nhận `mismatches` từ `ReviewResult.mismatches` (output của
    `review_dxf()`), xoá entity lỗi theo handle và vẽ lại đúng từ
    `build_result.written_geometry_by_primitive_id`.

    Ghi đè `build_result.output_path` (không tạo file mới — caller không
    cần cập nhật path). Raise ImportError nếu chưa cài `ezdxf`.
    """
    try:
        import ezdxf
    except ImportError as exc:
        raise ImportError(
            "Cần cài package 'ezdxf' để dùng Repair #1: "
            "pip install ezdxf --break-system-packages"
        ) from exc

    result = RepairResult()
    if not mismatches:
        return result

    # nhóm mismatch theo primitive_id — 1 entity có thể có nhiều dòng lỗi
    # (ví dụ cả handle sai lẫn layer sai) nhưng chỉ cần xoá/vẽ lại 1 lần
    affected_pids: Set[str] = set()
    for msg in mismatches:
        pid = _primitive_id_from_mismatch(msg)
        affected_pids.add(pid)

    doc = ezdxf.readfile(build_result.output_path)
    msp = doc.modelspace()
    db = doc.entitydb

    def _ensure_layer(name: str, color: int) -> None:
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs={"color": color})

    for pid in sorted(affected_pids):
        handle = build_result.handle_by_primitive_id.get(pid)
        written = build_result.written_geometry_by_primitive_id.get(pid)
        layer = build_result.layer_by_primitive_id.get(pid, "UNCLASSIFIED")

        if handle is None or written is None:
            # không có đủ thông tin để sửa — có thể là bug ở builder.py
            # hoặc mismatch do Reviewer phát sinh cho primitive không trong
            # BuildResult (bất thường, không nên xảy ra) — bỏ qua an toàn
            result.skipped_primitive_ids.append(pid)
            result.skipped_count += 1
            result.details.append(
                f"{pid}: BỎ QUA repair — không tìm được handle/written_geometry trong BuildResult"
            )
            continue

        # xoá entity cũ theo handle — entity có thể không còn trong db
        # nếu file đã bị sửa ngoài (bất thường), không crash
        old_entity = db.get(handle)
        if old_entity is not None:
            msp.delete_entity(old_entity)

        # vẽ lại đúng từ written_geometry (nguồn sự thật từ builder)
        _ensure_layer(layer, _layer_color_for(layer))
        geom_type = written.get("type")
        new_entity = None

        if geom_type == "line":
            s, e = written["start"], written["end"]
            new_entity = msp.add_line(s, e, dxfattribs={"layer": layer})

        elif geom_type == "circle":
            c, r = written["center"], written["radius"]
            new_entity = msp.add_circle(c, r, dxfattribs={"layer": layer})

        elif geom_type == "arc":
            c, r = written["center"], written["radius"]
            new_entity = msp.add_arc(
                c, r, written["start_angle_deg"], written["end_angle_deg"],
                dxfattribs={"layer": layer},
            )

        elif geom_type == "text":
            new_entity = msp.add_text(
                written["content"],
                dxfattribs={
                    "layer": layer,
                    "height": written["height"],
                    "rotation": written["rotation_deg"],
                    "insert": written["insert"],
                },
            )

        if new_entity is None:
            result.skipped_primitive_ids.append(pid)
            result.skipped_count += 1
            result.details.append(f"{pid}: BỎ QUA repair — geom_type không nhận ra: {geom_type!r}")
            continue

        # cập nhật handle mới vào BuildResult để review sau repair
        # dùng đúng handle thật do ezdxf cấp (handle của entity vừa vẽ lại)
        new_handle = new_entity.dxf.handle
        build_result.handle_by_primitive_id[pid] = new_handle

        result.repaired_primitive_ids.append(pid)
        result.repaired_count += 1
        result.details.append(
            f"{pid}: đã xoá handle cũ '{handle}' và vẽ lại -> handle mới '{new_handle}' "
            f"layer='{layer}' type={geom_type}"
        )

    doc.saveas(build_result.output_path)
    return result


def _layer_color_for(layer_name: str) -> int:
    """Tra lại màu ACI cho layer theo đúng mapping đã dùng trong builder.py.
    Tách ra thành helper ở đây thay vì import trực tiếp từ builder để tránh
    circular-import (builder không import repair). Nếu layer không trong danh
    sách biết, dùng màu trắng/đen (7) — không crash."""
    _COLORS: Dict[str, int] = {
        "THANH_NGANG": 1, "THANH_DOC": 5, "THANH_XIEN": 3,
        "LO_BAT_VIT": 2, "DUONG_VIEN_TRON": 6,
        "KHUNG_CHU_NHAT": 4, "GIA_DO": 30, "BAN_LE": 186, "DIEM_NOI": 9,
        "UNCLASSIFIED": 8, "TEXT": 7,
    }
    return _COLORS.get(layer_name, 7)
