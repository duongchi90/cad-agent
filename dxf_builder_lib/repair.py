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

MỞ RỘNG (Repair #1 cho INSERT component, 19/07/2026, HANDOFF.md mục "việc
nên làm tiếp" #2 sau khi Reviewer #1 có round-trip INSERT): `repair_insert_components()`
— CÙNG chiến lược xoá-theo-handle-rồi-vẽ-lại, nhưng nguồn sự thật là
`BuildResult.written_component_by_part_id` (INSERT: block name, layer,
insert point, x/y/z scale, rotation, ATTRIB — xem builder.py) thay vì
`written_geometry_by_primitive_id`, và input là `ReviewResult.component_mismatches`
(đã có `part_id` sẵn trong từng `ComponentMismatch`, KHÔNG cần trích từ
chuỗi tự do như `_primitive_id_from_mismatch()` bên dưới — đây là lợi ích
trực tiếp của việc dùng dataclass thay vì `List[str]` cho lỗi INSERT).
Vẽ lại bằng CHÍNH block đã tồn tại trong file (`msp.add_blockref()` +
`blockref.add_auto_attribs()`) — KHÔNG tự định nghĩa lại block (nằm ngoài
phạm vi Repair #1; nếu block định nghĩa bị thiếu khi cần repair, đó là bất
thường và bị bỏ qua an toàn, xem `repair_insert_components()`).

Optional dependency: `ezdxf` — cùng chiến lược lazy-import/graceful-skip
đã dùng cho vision_client.py, constraint_solving.py, builder.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from .builder import BuildResult
from .reviewer import ComponentMismatch

_EXPECTED_DXFTYPE = {"line": "LINE", "circle": "CIRCLE", "arc": "ARC", "text": "TEXT"}


@dataclass
class RepairResult:
    repaired_count: int = 0
    skipped_count: int = 0           # mismatch được ghi nhận nhưng không sửa được (xem lý do bên dưới)
    repaired_primitive_ids: List[str] = field(default_factory=list)
    skipped_primitive_ids: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)


@dataclass
class ComponentRepairResult:
    """Kết quả Repair #1 cho entity INSERT — tách riêng khỏi `RepairResult`
    (primitive thô) đúng nguyên tắc `ComponentMismatch` tách khỏi
    `mismatches` ở reviewer.py: field dùng `part_id` (không phải
    `primitive_id`), và nguồn lỗi đầu vào là `List[ComponentMismatch]` có
    cấu trúc sẵn, không phải chuỗi tự do."""

    repaired_count: int = 0
    skipped_count: int = 0
    repaired_part_ids: List[str] = field(default_factory=list)
    skipped_part_ids: List[str] = field(default_factory=list)
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


def repair_insert_components(build_result: BuildResult, component_mismatches: List[ComponentMismatch]) -> ComponentRepairResult:
    """Repair #1 cho entity INSERT (Semantic Component API) — nhận
    `component_mismatches` từ `ReviewResult.component_mismatches` (output
    của `review_dxf()`), xoá entity INSERT lỗi theo handle và vẽ lại đúng
    từ `build_result.written_component_by_part_id`.

    CÙNG chiến lược `repair_dxf()` ở trên (xoá-theo-handle-rồi-vẽ-lại từ
    nguồn sự thật lúc build, không tra lại Semantic IR gốc), khác biệt
    duy nhất: đơn vị sửa là INSERT (không phải LINE/CIRCLE/ARC/TEXT), nên
    vẽ lại bằng `msp.add_blockref()` + `blockref.add_auto_attribs()` thay
    vì các hàm `add_line`/`add_circle`/`add_arc`/`add_text` — và vì MỌI
    component type (frame_beam/bracket/panel/...) đều dùng chung cơ chế
    blockref+attrib này (khác primitive thô, mỗi geom_type cần 1 hàm vẽ
    riêng), hàm này generic cho tất cả component type, không cần nhánh
    theo `component_type_by_part_id`.

    Ghi đè `build_result.output_path` (không tạo file mới). Raise
    ImportError nếu chưa cài `ezdxf`. Nếu `component_mismatches` rỗng, trả
    về `ComponentRepairResult` rỗng, không mở/ghi lại file (tránh ghi đè
    không cần thiết, cùng hành vi `repair_dxf()`).
    """
    try:
        import ezdxf
    except ImportError as exc:
        raise ImportError(
            "Cần cài package 'ezdxf' để dùng Repair #1: "
            "pip install ezdxf --break-system-packages"
        ) from exc

    result = ComponentRepairResult()
    if not component_mismatches:
        return result

    # ComponentMismatch đã có part_id sẵn (dataclass có cấu trúc, khác
    # _primitive_id_from_mismatch() ở trên vốn phải trích từ chuỗi tự do)
    # — 1 part có thể có nhiều dòng mismatch (vd cả block_name lẫn 1
    # attrib) nhưng chỉ cần xoá/vẽ lại 1 lần.
    affected_part_ids: Set[str] = {cm.part_id for cm in component_mismatches}

    doc = ezdxf.readfile(build_result.output_path)
    msp = doc.modelspace()
    db = doc.entitydb

    def _ensure_layer(name: str) -> None:
        # không biết lại đúng màu ACI gốc của layer COMP_* tại đây (mapping
        # đó nằm trong semantic_components.py, module này cố tình không
        # import để tránh phụ thuộc chéo) — layer COMP_* luôn phải đã tồn
        # tại từ lúc build gốc nên đây chỉ là lưới an toàn phòng trường hợp
        # bất thường (không nên xảy ra), dùng màu mặc định 7 (trắng/đen).
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs={"color": 7})

    for part_id in sorted(affected_part_ids):
        handle = build_result.component_handle_by_part_id.get(part_id)
        written = build_result.written_component_by_part_id.get(part_id)

        if handle is None or written is None:
            # không có đủ thông tin để sửa — có thể là bug ở builder.py
            # hoặc mismatch phát sinh cho part_id không trong BuildResult
            # (bất thường, không nên xảy ra) — bỏ qua an toàn
            result.skipped_part_ids.append(part_id)
            result.skipped_count += 1
            result.details.append(
                f"{part_id}: BỎ QUA repair — không tìm được handle/written_component trong BuildResult"
            )
            continue

        block_name = written["block_name"]
        if block_name not in doc.blocks:
            # block định nghĩa bị thiếu trong file — bất thường (nằm ngoài
            # phạm vi Repair #1, vốn chỉ sửa lỗi dịch thuật INSERT, không
            # tự định nghĩa lại block), bỏ qua an toàn thay vì crash
            result.skipped_part_ids.append(part_id)
            result.skipped_count += 1
            result.details.append(
                f"{part_id}: BỎ QUA repair — block '{block_name}' không tồn tại trong file DXF"
            )
            continue

        # xoá entity cũ theo handle — entity có thể không còn trong db
        # nếu file đã bị sửa ngoài (bất thường), không crash
        old_entity = db.get(handle)
        if old_entity is not None:
            msp.delete_entity(old_entity)

        _ensure_layer(written["layer"])

        new_entity = msp.add_blockref(
            block_name,
            written["insert"],
            dxfattribs={
                "layer": written["layer"],
                "xscale": written["xscale"],
                "yscale": written["yscale"],
                "zscale": written["zscale"],
                "rotation": written["rotation_deg"],
            },
        )
        new_entity.add_auto_attribs(written.get("attribs", {}))

        # cập nhật handle mới vào BuildResult để review sau repair
        new_handle = new_entity.dxf.handle
        build_result.component_handle_by_part_id[part_id] = new_handle

        result.repaired_part_ids.append(part_id)
        result.repaired_count += 1
        result.details.append(
            f"{part_id}: đã xoá handle cũ '{handle}' và vẽ lại INSERT -> handle mới '{new_handle}' "
            f"block='{block_name}' layer='{written['layer']}'"
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
