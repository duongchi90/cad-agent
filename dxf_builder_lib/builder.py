"""
builder.py — DXF Builder (Phase 3, mục 2 tài liệu kiến trúc): "build 1 lần"
bằng `ezdxf`, không vẽ từng entity qua MCP/AutoCAD. Đây là module code THẬT
đầu tiên của Phase 3, đứng ngay sau Constraint Solving trong sơ đồ pipeline.

INPUT:
  - `PrimitiveIRDocument` (Phase 1) — nguồn hình học/text chính, đã build
    xong bằng geometry_extraction.py/text_extraction.py.
  - (optional) `solved_primitives` (Phase 2, `constraint_solving.solve_constraints()`)
    — nếu có, GHI ĐÈ toạ độ line "đã làm sạch" thay vì toạ độ đo thô, đúng
    thứ tự pipeline mục 2 (Constraint Solving -> DXF Builder).
  - (optional) `SemanticIRDocument` (Phase 2) — chỉ dùng để suy layer theo
    `part_type` (thanh_ngang/thanh_doc/...), KHÔNG dùng geometry của nó
    (Semantic IR vốn không sao chép geometry, xem models.py mục 11.1).

OUTPUT: file .dxf thật trên đĩa + `BuildResult` ghi lại CHÍNH XÁC những gì
đã ghi vào file cho mỗi primitive (`written_geometry_by_primitive_id`) và
`handle` CAD thật do ezdxf cấp — 2 giá trị này là "nguồn sự thật" để
`reviewer.py` (Headless Reviewer #1) đối chiếu ngược lại sau khi đọc lại
file, và để Repair #2 sau này target đúng entity qua handle (đã xác nhận
handle giữ nguyên 100% qua `drawing_open` AutoCAD LT thật — mục 9.4 tài
liệu kiến trúc).

`Primitive.handle` (field có sẵn từ Phase 1, `None` cho tới khi build)
được GHI ĐÈ trực tiếp lên chính object `primitive_doc.primitives[i]` sau
khi build xong — đúng ghi chú trong `primitive_ir.schema.json`: field này
chuyển từ null sang giá trị thật sau bước ezdxf build, dùng chung 1 schema
xuyên suốt thay vì có bản thứ 2 cho "sau khi build".

Optional dependency: `ezdxf` (`pip install ezdxf --break-system-packages`)
— cùng chiến lược lazy-import/graceful-skip đã dùng cho vision_client.py và
constraint_solving.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from primitive_ir_lib.models import Primitive, PrimitiveIRDocument

# part_type (semantic_ir_lib) -> (tên layer DXF, mã màu ACI)
# Màu khác nhau theo part_type để Reviewer #2 (visual, screenshot AutoCAD)
# dễ phân biệt bằng mắt các nhóm linh kiện khi zoom — không ảnh hưởng gì
# tới Reviewer #1 (headless, chỉ so số).
_LAYER_BY_PART_TYPE: Dict[str, Tuple[str, int]] = {
    # single-primitive parts (pattern_recognition.py)
    "thanh_ngang": ("THANH_NGANG", 1),       # đỏ
    "thanh_doc": ("THANH_DOC", 5),           # xanh dương
    "thanh_xien": ("THANH_XIEN", 3),         # xanh lá
    "lo_bat_vit": ("LO_BAT_VIT", 2),         # vàng
    "duong_vien_tron": ("DUONG_VIEN_TRON", 6),  # tím/magenta
    # compound parts (pattern_compound.py) — Phase 2 nâng cao
    "khung_chu_nhat": ("KHUNG_CHU_NHAT", 4),     # cyan (xanh nước)
    "gia_do": ("GIA_DO", 30),                    # orange (cam)
    "ban_le": ("BAN_LE", 186),                   # light magenta (hồng nhạt)
    "diem_noi": ("DIEM_NOI", 9),                 # light gray (xám nhạt)
    "unclassified": ("UNCLASSIFIED", 8),     # xám
}
_DEFAULT_LAYER: Tuple[str, int] = ("UNCLASSIFIED", 8)
_TEXT_LAYER: Tuple[str, int] = ("TEXT", 7)  # trắng/đen


@dataclass
class BuildResult:
    output_path: str
    handle_by_primitive_id: Dict[str, str] = field(default_factory=dict)
    layer_by_primitive_id: Dict[str, str] = field(default_factory=dict)
    # đúng những gì ĐÃ GHI vào file (đã áp solved override nếu có) — nguồn
    # sự thật cho reviewer.py, KHÔNG phải toạ độ thô trong primitive_doc
    written_geometry_by_primitive_id: Dict[str, dict] = field(default_factory=dict)
    skipped_primitive_ids: List[str] = field(default_factory=list)
    entity_count: int = 0
    # --- Semantic API (mục 12.4, semantic_components.py) — chỉ điền khi gọi
    # build_dxf(..., build_components=True) VÀ có semantic_doc. Đứng SONG
    # SONG với hình học thô ở trên (layer COMP_*, KHÔNG thay thế) — xem
    # docstring đầu semantic_components.py. Hỗ trợ cả single-primitive parts
    # và compound parts (mục 11.4 nâng cao).
    component_handle_by_part_id: Dict[str, str] = field(default_factory=dict)
    component_type_by_part_id: Dict[str, str] = field(default_factory=dict)
    skipped_part_ids: List[str] = field(default_factory=list)
    skipped_part_reasons: Dict[str, str] = field(default_factory=dict)
    component_count: int = 0
    # đúng những gì ĐÃ GHI vào entity INSERT (block name, layer, insert
    # point, x/y/z scale, rotation, ATTRIB) — đọc lại TRỰC TIẾP từ chính
    # entity vừa tạo (đối tượng blockref trong doc, TRƯỚC saveas) thay vì
    # từ ComponentInsertResult, để "nguồn sự thật" luôn khớp bất kể hàm
    # insert nào trong semantic_components.py sinh ra nó — cùng nguyên tắc
    # written_geometry_by_primitive_id ở trên, dùng cho reviewer.py đối
    # chiếu ngược sau khi đọc lại file (round-trip INSERT).
    written_component_by_part_id: Dict[str, dict] = field(default_factory=dict)


def _part_type_by_primitive_id(semantic_doc) -> Dict[str, str]:
    if semantic_doc is None:
        return {}
    mapping: Dict[str, str] = {}
    for part in semantic_doc.parts:
        for pid in part.primitive_ids:
            mapping[pid] = part.part_type
    return mapping


def _layer_for_primitive(prim: Primitive, part_type_by_id: Dict[str, str]) -> Tuple[str, int]:
    if prim.type == "text":
        return _TEXT_LAYER
    part_type = part_type_by_id.get(prim.id)
    if part_type is not None:
        return _LAYER_BY_PART_TYPE.get(part_type, _DEFAULT_LAYER)
    return _DEFAULT_LAYER


def _ensure_layer(doc, name: str, color: int) -> None:
    if name not in doc.layers:
        doc.layers.new(name=name, dxfattribs={"color": color})


def build_dxf(
    primitive_doc: PrimitiveIRDocument,
    output_path: str,
    semantic_doc: Optional[object] = None,
    solved_primitives: Optional[Dict[str, object]] = None,
    dxf_version: str = "R2010",
    build_components: bool = False,
) -> BuildResult:
    """Build 1 file DXF thật từ `primitive_doc`. Trả về `BuildResult` —
    không raise nếu 1 primitive không vẽ được (thiếu geometry/text_data),
    chỉ ghi vào `skipped_primitive_ids` (lỗi dữ liệu cục bộ không nên chặn
    cả bản vẽ, đúng nguyên tắc "ưu tiên rule-based/deterministic" mục 7 —
    phần thiếu dữ liệu nên lộ ra để review, không nên crash toàn bộ).

    `build_components=True` (mặc định `False`, giữ nguyên hành vi cũ) +
    có `semantic_doc`: sau khi vẽ xong hình học thô, gọi thêm
    `semantic_components.assemble_semantic_components()` để chèn lớp
    "linh kiện" (frame_insert_beam/bracket_insert/panel_insert +
    4 hàm compound panel_rect_insert/bracket_L_insert/hinge_insert/
    node_insert, mục 12.4 + 11.4) trên layer riêng `COMP_*`, song song với
    hình học thô — xem docstring đầu `semantic_components.py`.

    Raise ImportError nếu chưa cài `ezdxf`.
    """
    try:
        import ezdxf
    except ImportError as exc:
        raise ImportError(
            "Cần cài package 'ezdxf' để dùng DXF Builder: "
            "pip install ezdxf --break-system-packages"
        ) from exc

    part_type_by_id = _part_type_by_primitive_id(semantic_doc)
    solved_primitives = solved_primitives or {}

    doc = ezdxf.new(dxfversion=dxf_version)
    # CAD-Agent produces geometry in millimetres. Declaring the unit prevents
    # AutoCAD from applying an implicit conversion when it opens the DXF.
    doc.header["$INSUNITS"] = 4  # millimetres
    msp = doc.modelspace()

    result = BuildResult(output_path=output_path)

    for prim in primitive_doc.primitives:
        layer_name, color = _layer_for_primitive(prim, part_type_by_id)
        _ensure_layer(doc, layer_name, color)

        entity = None
        written: Optional[dict] = None

        if prim.type == "line" and prim.geometry is not None:
            s, e = prim.geometry.start, prim.geometry.end
            solved = solved_primitives.get(prim.id)
            if solved is not None:
                s, e = solved.start, solved.end
            entity = msp.add_line((s.x, s.y), (e.x, e.y), dxfattribs={"layer": layer_name})
            written = {"type": "line", "start": (s.x, s.y), "end": (e.x, e.y)}

        elif prim.type == "circle" and prim.geometry is not None:
            c, r = prim.geometry.center, prim.geometry.radius
            entity = msp.add_circle((c.x, c.y), r, dxfattribs={"layer": layer_name})
            written = {"type": "circle", "center": (c.x, c.y), "radius": r}

        elif prim.type == "arc" and prim.geometry is not None:
            g = prim.geometry
            entity = msp.add_arc(
                (g.center.x, g.center.y), g.radius, g.start_angle_deg, g.end_angle_deg,
                dxfattribs={"layer": layer_name},
            )
            written = {
                "type": "arc", "center": (g.center.x, g.center.y), "radius": g.radius,
                "start_angle_deg": g.start_angle_deg, "end_angle_deg": g.end_angle_deg,
            }

        elif prim.type == "text" and prim.text_data is not None:
            td = prim.text_data
            entity = msp.add_text(
                td.content,
                dxfattribs={
                    "layer": layer_name,
                    "height": td.height,
                    "rotation": td.rotation_deg,
                    "insert": (td.position.x, td.position.y),
                },
            )
            written = {
                "type": "text", "content": td.content,
                "insert": (td.position.x, td.position.y),
                "height": td.height, "rotation_deg": td.rotation_deg,
            }

        if entity is None:
            result.skipped_primitive_ids.append(prim.id)
            continue

        handle = entity.dxf.handle
        # ghi đè trực tiếp lên Primitive gốc (null -> giá trị thật, xem
        # docstring module này + primitive_ir.schema.json field 'handle')
        prim.handle = handle
        prim.layer = layer_name

        result.handle_by_primitive_id[prim.id] = handle
        result.layer_by_primitive_id[prim.id] = layer_name
        result.written_geometry_by_primitive_id[prim.id] = written
        result.entity_count += 1

    if build_components and semantic_doc is not None:
        from .semantic_components import assemble_semantic_components

        assembly = assemble_semantic_components(
            doc, msp, semantic_doc, result.written_geometry_by_primitive_id,
        )
        for res in assembly.inserted:
            result.component_handle_by_part_id[res.part_id] = res.handle
            result.component_type_by_part_id[res.part_id] = res.component_type

            blockref_entity = doc.entitydb.get(res.handle)
            insert_pt = blockref_entity.dxf.insert
            attribs = {a.dxf.tag: a.dxf.text for a in blockref_entity.attribs}
            result.written_component_by_part_id[res.part_id] = {
                "block_name": blockref_entity.dxf.name,
                "layer": blockref_entity.dxf.layer,
                "insert": (insert_pt.x, insert_pt.y, insert_pt.z),
                "xscale": blockref_entity.dxf.xscale,
                "yscale": blockref_entity.dxf.yscale,
                "zscale": blockref_entity.dxf.zscale,
                "rotation_deg": blockref_entity.dxf.rotation,
                "attribs": attribs,
            }
        result.skipped_part_ids = assembly.skipped_part_ids
        result.skipped_part_reasons = assembly.skip_reasons
        result.component_count = len(assembly.inserted)

    doc.saveas(output_path)
    return result
