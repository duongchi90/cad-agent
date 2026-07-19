"""
semantic_components.py — Semantic API cho domain khung xương/thùng xe cải
 tạo (mục 12.4 tài liệu kiến trúc, việc còn lại của Phase 3): `frame_insert_beam`,
`bracket_insert`, `panel_insert`, + 4 hàm compound (mục 11.4 nâng cao).

BỐI CẢNH: `puran-water/autocad-mcp` (Phase 4) có sẵn `pid_insert_valve/
instrument/pump/tank...` cho domain P&ID nhưng KHÔNG áp dụng được cho domain
thực tế của dự án (khung xương/thùng xe cải tạo) — mục 3 tài liệu kiến trúc
đã ghi rõ phải tự viết Semantic API riêng. Module này là bước đó: các hàm
"insert component" theo đúng mẫu `pid_insert_*` (nhận toạ độ + tham số ngữ
nghĩa, tự lo phần dựng hình + gắn attribute), để Phase 4 (AutoCAD MCP thật)
có thể gọi thẳng như 1 tool, KHÔNG cần biết chi tiết geometry bên trong.

KHÁC BIỆT với `builder.py`: `builder.py` vẽ hình học THÔ (1 primitive = 1
entity LINE/CIRCLE/ARC/TEXT trần, không có khái niệm "linh kiện"). Module
này vẽ THÊM 1 lớp "linh kiện" bằng DXF BLOCK/INSERT (mỗi linh kiện = 1
entity INSERT tham chiếu 1 block định nghĩa sẵn, có ATTRIB mang thông tin
ngữ nghĩa: part_id, kích thước...) — đứng SONG SONG với hình học thô trên
layer riêng (`COMP_*`), không thay thế/không ảnh hưởng tới hình học thô mà
`reviewer.py` (Reviewer #1) đã kiểm chứng ở mức primitive. Sở dĩ tách lớp
riêng: Reviewer #1 hiện chỉ so khớp primitive-level (line/circle/arc/text)
theo đúng thiết kế mục 12.2 — thêm entity INSERT không phá vỡ hợp đồng đó.

Các hàm insert dùng kỹ thuật block tham số hoá chuẩn của AutoCAD (không mới,
nhưng lần đầu áp dụng trong dự án): block định nghĩa 1 lần ở toạ độ đơn vị
(vd đường thẳng đơn vị từ (0,0) đến (1,0)), khi insert dùng `xscale`/
`yscale`/`rotation` khác nhau theo trục để "kéo dài" hình theo đúng kích
thước thật — vd `frame_insert_beam` scale RIÊNG trục X theo chiều dài dầm
(`yscale=1.0` cố định) để chữ ATTRIB không bị kéo méo theo chiều dài dầm.

MAPPING `part_type` (semantic_ir_lib) -> component (mục 12.4 + 11.4):

  Single-primitive parts (pattern_recognition.py, mục 11.2):
  - thanh_ngang / thanh_doc / thanh_xien (line)   -> `frame_insert_beam`
    (thanh khung — dầm ngang/dọc/xiên của khung xương).
  - lo_bat_vit (circle nhỏ, lỗ bắt vít)           -> `bracket_insert`
    (giá đỡ/bản mã lắp tại vị trí lỗ bắt vít — lỗ bắt vít trong domain này
    hầu như luôn đi kèm 1 giá đỡ/bản mã, không tồn tại độc lập).
  - duong_vien_tron (circle lớn, đường viền tròn) -> `panel_insert`
    (tấm/nắp tròn — vd nắp che, tấm chắn bánh, lỗ khoét tròn trên thùng xe).

  Compound parts (pattern_compound.py, mục 11.4 nâng cao):
  - khung_chu_nhat (4 line khung kín)             -> `panel_rect_insert`
    (tấm/khung chữ nhật — biên dạng đa giác kín, vd nắp tấm hông thùng xe,
    cửa mở ra-vào. Khác panel_insert (tròn): dùng bounding box 4 line làm
    kích thước, 1 entity INSERT thay cho 4 LINE rời).
  - gia_do (2 line vuông góc + coincident_endpoint) -> `bracket_L_insert`
    (giá đỡ góc L cấu trúc — thanh thép chữ L hàn góc, khác bracket_insert
    ở trên: bracket_insert gắn VÀO lỗ bắt vít (điểm), còn bracket_L_insert
    là 1 linh kiện góc có 2 cánh. Insert tại góc vuông, 2 cánh scale theo
    chiều dài 2 line).
  - ban_le (2 line song song + 2 lỗ bắt vít)      -> `hinge_insert`
    (bản lề — 2 lá kim loại song song ghép bằng trục ở 1 đầu, kích thước
    suy từ length line + gap giữa 2 line).
  - diem_noi (>=3 line hội tụ 1 điểm)             -> `node_insert`
    (nút hàn/gia cố — ký hiệu chữ thập/nhiều cánh tại điểm hội tụ, số cánh
    = số line hội tụ. Marker cấu trúc cho chỗ giằng hàn).

  - unclassified / part_type khác                 -> BỎ QUA (`skipped_part_ids`),
    chưa có Semantic API tương ứng — đúng nguyên tắc mục 7 (không đoán bừa).

GIỚI HẠN Ở BƯỚC NÀY (thành thật, không nhận vơ đã xong):
  - `panel_rect_insert` chỉ suy đúng width/height khi 4 line khung thật sự
    hợp thành HCN gần trục (sau khi constraint_solving làm sạch). Khung xoáy
    (không trục) hiện lấy bounding box axis-aligned — gần đúng, chưa tối
    ưu. Benchmark trên ảnh scan thật domain khung xương chưa làm.
  - Compound insert CHỈ dùng `written_geometry` (toạ độ đã solve nếu có),
    đúng nguyên tắc "nguồn sự thật" như single-primitive — nhưng nếu
    Constraint Solving chưa chạy (solved_primitives rỗng), toạ độ compound
    sẽ thô và có thể không khớp hình thật.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_BLOCK_FRAME_BEAM = "COMP_FRAME_BEAM"
_BLOCK_BRACKET = "COMP_BRACKET"
_BLOCK_PANEL_ROUND = "COMP_PANEL_ROUND"
_BLOCK_PANEL_RECT = "COMP_PANEL_RECT"
_BLOCK_BRACKET_L = "COMP_BRACKET_L"
_BLOCK_HINGE = "COMP_HINGE"
_BLOCK_NODE = "COMP_NODE"

# part_type (semantic_ir_lib) -> component nào xử lý được
_BEAM_PART_TYPES = {"thanh_ngang", "thanh_doc", "thanh_xien"}
_BRACKET_PART_TYPES = {"lo_bat_vit"}
_PANEL_ROUND_PART_TYPES = {"duong_vien_tron"}
# compound part_type (pattern_compound.py, mục 11.4)
_PANEL_RECT_PART_TYPES = {"khung_chu_nhat"}
_BRACKET_L_PART_TYPES = {"gia_do"}
_HINGE_PART_TYPES = {"ban_le"}
_NODE_PART_TYPES = {"diem_noi"}

_MIN_BRACKET_SIZE_MM = 10.0   # kích thước tối thiểu ký hiệu giá đỡ, tránh vẽ quá nhỏ khi hole_diameter bé
_MIN_NODE_SIZE_MM = 15.0      # kích thước tối thiểu ký hiệu nút hàn, thấy rõ khi zoom
_HINGE_DEFAULT_GAP_MM = 8.0   # gap mặc định giữa 2 lá bản lề nếu không suy được từ geometry


# ============================================================ block templates ==
# Mỗi block template vẽ HÌNH ĐƠN VỊ (size = 1, không có đơn vị) — kích thước
# thật do caller định qua xscale/yscale lúc insert. Đây là kỹ thuật AutoCAD
# chuẩn cho block tham số hoá, tránh phải tạo 1 block riêng cho mỗi size.

def _build_frame_beam_block(block) -> None:
    """Block đơn vị: đường thẳng từ (0,0) -> (1,0) + 2 vạch đầu dầm (ký hiệu
    mặt cắt, phân biệt với LINE trần ở lớp hình học thô) + attribute."""
    block.add_line((0.0, 0.0), (1.0, 0.0))
    block.add_line((0.0, -0.08), (0.0, 0.08))
    block.add_line((1.0, -0.08), (1.0, 0.08))
    block.add_attdef(tag="PART_ID", insert=(0.5, 0.18), height=0.12)
    block.add_attdef(tag="LENGTH_MM", insert=(0.5, -0.28), height=0.12)
    block.add_attdef(tag="PROFILE", insert=(0.5, -0.44), height=0.12)


def _build_bracket_block(block) -> None:
    """Block đơn vị: ký hiệu giá đỡ/bản mã hình tam giác vuông tại gốc toạ
    độ (điểm chèn = đúng tâm lỗ bắt vít mà giá đỡ này gắn vào)."""
    block.add_line((0.0, 0.0), (1.0, 0.0))
    block.add_line((0.0, 0.0), (0.0, 1.0))
    block.add_line((1.0, 0.0), (0.0, 1.0))
    block.add_circle((0.0, 0.0), 0.12)  # đánh dấu tâm lỗ bắt vít
    block.add_attdef(tag="PART_ID", insert=(0.15, 1.15), height=0.15)
    block.add_attdef(tag="HOLE_DIAMETER_MM", insert=(0.15, 1.35), height=0.15)


def _build_panel_round_block(block) -> None:
    """Block đơn vị: đường tròn bán kính 1 + 4 vạch chữ thập ngoài biên
    (phân biệt với CIRCLE trần ở lớp hình học thô — ký hiệu "tấm/nắp tròn")."""
    block.add_circle((0.0, 0.0), 1.0)
    block.add_line((-1.2, 0.0), (-1.0, 0.0))
    block.add_line((1.0, 0.0), (1.2, 0.0))
    block.add_line((0.0, -1.2), (0.0, -1.0))
    block.add_line((0.0, 1.0), (0.0, 1.2))
    block.add_attdef(tag="PART_ID", insert=(0.0, -1.4), height=0.2)
    block.add_attdef(tag="RADIUS_MM", insert=(0.0, -1.65), height=0.2)


def _build_panel_rect_block(block) -> None:
    """Block đơn vị: HCN từ (0,0) đến (1,1) + 4 vạch góc chéo ra ngoài (ký
    hiệu "tấm/khung chữ nhật" — phân biệt với 4 LINE rời ở lớp thô). Insert
    tại tâm HCN (block gốc ở góc dưới trái, nhưng caller dịch điểm chèn tới
    tâm để scale đối xứng — xem panel_rect_insert)."""
    block.add_line((0.0, 0.0), (1.0, 0.0))
    block.add_line((1.0, 0.0), (1.0, 1.0))
    block.add_line((1.0, 1.0), (0.0, 1.0))
    block.add_line((0.0, 1.0), (0.0, 0.0))
    # 4 góc chéo 0.1 đơn vị (thấy rõ khi zoom)
    block.add_line((-0.1, -0.1), (0.1, 0.1))
    block.add_line((0.9, -0.1), (1.1, 0.1))
    block.add_line((-0.1, 1.1), (0.1, 0.9))
    block.add_line((0.9, 1.1), (1.1, 0.9))
    block.add_attdef(tag="PART_ID", insert=(0.5, -0.25), height=0.12)
    block.add_attdef(tag="WIDTH_MM", insert=(0.5, -0.42), height=0.12)
    block.add_attdef(tag="HEIGHT_MM", insert=(0.5, -0.59), height=0.12)


def _build_bracket_L_block(block) -> None:
    """Block đơn vị: ký hiệu giá đỡ góc L — 2 cánh vuông góc dài 1, dày 0.1
    (độ dày tượng trưng, không phải tham số). Block gốc tại góc trong của L
    (điểm chèn = đúng điểm coincident_endpoint của 2 line)."""
    # cánh ngang (theo +X)
    block.add_line((0.0, 0.0), (1.0, 0.0))
    block.add_line((0.0, 0.1), (1.0, 0.1))
    block.add_line((1.0, 0.0), (1.0, 0.1))
    # cánh dọc (theo +Y)
    block.add_line((0.0, 0.0), (0.0, 1.0))
    block.add_line((0.1, 0.0), (0.1, 1.0))
    block.add_line((0.0, 1.0), (0.1, 1.0))
    block.add_attdef(tag="PART_ID", insert=(0.15, 1.15), height=0.12)
    block.add_attdef(tag="LEG_A_MM", insert=(0.15, 1.32), height=0.12)
    block.add_attdef(tag="LEG_B_MM", insert=(0.15, 1.49), height=0.12)


def _build_hinge_block(block) -> None:
    """Block đơn vị: ký hiệu bản lề — 2 lá song song (trên/dưới) dài 1, nối
    bằng 1 vòng tròn nhỏ tại gốc (trục). Block gốc tại tâm vòng tròn trục."""
    # lá dưới (y=0)
    block.add_line((0.0, 0.0), (1.0, 0.0))
    # lá trên (y=0.3 — block đơn vị, gap thật do yscale quyết định)
    block.add_line((0.0, 0.3), (1.0, 0.3))
    # vòng tròn trục tại gốc
    block.add_circle((0.0, 0.15), 0.15)
    # ký hiệu bản lề ở giữa (đường nối 2 lá)
    block.add_line((0.5, 0.0), (0.5, 0.3))
    block.add_attdef(tag="PART_ID", insert=(0.5, 0.55), height=0.12)
    block.add_attdef(tag="LENGTH_MM", insert=(0.5, -0.2), height=0.12)
    block.add_attdef(tag="GAP_MM", insert=(0.5, -0.37), height=0.12)


def _build_node_block(block) -> None:
    """Block đơn vị: ký hiệu nút hàn/gia cố — 4 cánh chữ thập dài 1 + vòng
    tròn nhỏ ở tâm. Số cánh thực tế (do caller vẽ thêm line) có thể > 4, block
    chỉ là ký hiệu cố định; số cánh thật ghi vào ATTRIB LEG_COUNT."""
    # vòng tròn tâm
    block.add_circle((0.0, 0.0), 0.15)
    # 4 cánh chữ thập (đơn vị)
    block.add_line((0.0, 0.0), (1.0, 0.0))
    block.add_line((0.0, 0.0), (-1.0, 0.0))
    block.add_line((0.0, 0.0), (0.0, 1.0))
    block.add_line((0.0, 0.0), (0.0, -1.0))
    block.add_attdef(tag="PART_ID", insert=(0.2, 1.2), height=0.15)
    block.add_attdef(tag="LEG_COUNT", insert=(0.2, 1.4), height=0.15)


def _ensure_component_block(doc, name: str, builder_fn) -> None:
    if name not in doc.blocks:
        block = doc.blocks.new(name=name)
        builder_fn(block)


# ------------------------------------------------------------------ results ==
ComponentType = str  # "frame_beam" | "bracket" | "panel_round" | "panel_rect"
                     # | "bracket_L" | "hinge" | "node"


@dataclass
class ComponentInsertResult:
    part_id: str
    component_type: ComponentType
    handle: str
    layer: str
    insert_point: Tuple[float, float]


# ----------------------------------------------------- 3 hàm single-primitive --
# (giữ nguyên 100% so với bản ZIP gốc — đã có test pass)

def frame_insert_beam(
    doc, msp, start: Tuple[float, float], end: Tuple[float, float],
    layer: str, part_id: str, profile: str = "unknown",
) -> ComponentInsertResult:
    """Chèn 1 dầm khung (thanh ngang/dọc/xiên) từ `start` đến `end`.

    Kỹ thuật: block đơn vị dài 1, insert tại `start`, `xscale=length`,
    `yscale=1.0` (CỐ ĐỊNH — không kéo méo chữ/vạch đầu dầm theo chiều dài),
    `rotation` = góc thật của dầm. Raise ValueError nếu `start == end`
    (dầm không có chiều dài, không phải lỗi hệ thống nên không dùng
    ImportError/crash im lặng — để caller (`assemble_semantic_components`)
    quyết định bỏ qua part đó).
    """
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 0:
        raise ValueError(f"frame_insert_beam: part {part_id} có start == end, không có chiều dài")

    _ensure_component_block(doc, _BLOCK_FRAME_BEAM, _build_frame_beam_block)
    angle_deg = math.degrees(math.atan2(dy, dx))

    blockref = msp.add_blockref(
        _BLOCK_FRAME_BEAM, start,
        dxfattribs={"layer": layer, "xscale": length, "yscale": 1.0, "rotation": angle_deg},
    )
    blockref.add_auto_attribs({"PART_ID": part_id, "LENGTH_MM": f"{length:.2f}", "PROFILE": profile})

    return ComponentInsertResult(
        part_id=part_id, component_type="frame_beam", handle=blockref.dxf.handle,
        layer=layer, insert_point=(start[0], start[1]),
    )


def bracket_insert(
    doc, msp, location: Tuple[float, float], layer: str, part_id: str,
    hole_diameter_mm: float,
) -> ComponentInsertResult:
    """Chèn 1 giá đỡ/bản mã tại `location` (đúng tâm lỗ bắt vít gắn giá đỡ
    này). Kích thước ký hiệu tỉ lệ với `hole_diameter_mm` (tối thiểu
    `_MIN_BRACKET_SIZE_MM` để không vẽ quá nhỏ khi lỗ bé)."""
    if hole_diameter_mm <= 0:
        raise ValueError(f"bracket_insert: part {part_id} có hole_diameter_mm <= 0")

    _ensure_component_block(doc, _BLOCK_BRACKET, _build_bracket_block)
    size = max(hole_diameter_mm * 3.0, _MIN_BRACKET_SIZE_MM)

    blockref = msp.add_blockref(
        _BLOCK_BRACKET, location,
        dxfattribs={"layer": layer, "xscale": size, "yscale": size},
    )
    blockref.add_auto_attribs({"PART_ID": part_id, "HOLE_DIAMETER_MM": f"{hole_diameter_mm:.2f}"})

    return ComponentInsertResult(
        part_id=part_id, component_type="bracket", handle=blockref.dxf.handle,
        layer=layer, insert_point=(location[0], location[1]),
    )


def panel_insert(
    doc, msp, center: Tuple[float, float], radius_mm: float, layer: str, part_id: str,
) -> ComponentInsertResult:
    """Chèn 1 tấm/nắp tròn tại `center`, bán kính `radius_mm` (vd nắp che,
    lỗ khoét tròn trên thùng xe — xem giới hạn ở đầu module về biên dạng
    đa giác thật, chưa hỗ trợ ở bước này)."""
    if radius_mm <= 0:
        raise ValueError(f"panel_insert: part {part_id} có radius_mm <= 0")

    _ensure_component_block(doc, _BLOCK_PANEL_ROUND, _build_panel_round_block)

    blockref = msp.add_blockref(
        _BLOCK_PANEL_ROUND, center,
        dxfattribs={"layer": layer, "xscale": radius_mm, "yscale": radius_mm},
    )
    blockref.add_auto_attribs({"PART_ID": part_id, "RADIUS_MM": f"{radius_mm:.2f}"})

    return ComponentInsertResult(
        part_id=part_id, component_type="panel_round", handle=blockref.dxf.handle,
        layer=layer, insert_point=(center[0], center[1]),
    )


# ----------------------------------------------------- 4 hàm compound mới --
# (mục 11.4 nâng cao — part_type do pattern_compound.py sinh ra)
#
# Thiết kế: mỗi hàm nhận toạ độ ĐÃ SUY RA từ nhiều primitive (caller tính
# bounding box / coincident endpoint / etc.), KHÔNG tự duyệt lại primitive_ids.
# Lý do: tách rõ "suy tham số từ hình học nhiều line" (việc của helper trong
# assemble_semantic_components) khỏi "vẽ block" (việc của hàm insert) — cùng
# nguyên tắc "1 việc / 1 module" đã áp dụng xuyên suốt (Detection tách Solving,
# Pruning tách Solving, Build tách Review...).

def panel_rect_insert(
    doc, msp, center: Tuple[float, float], width_mm: float, height_mm: float,
    layer: str, part_id: str, rotation_deg: float = 0.0,
) -> ComponentInsertResult:
    """Chèn 1 tấm/khung chữ nhật tại `center`, kích thước `width_mm` x
    `height_mm` (suy từ bounding box 4 line của khung_chu_nhat). Insert tại
    TÂM (không phải góc) để scale đối xứng — block đơn vị có gốc ở (0,0) nên
    cần dịch điểm chèn về tâm trước khi add_blockref."""
    if width_mm <= 0 or height_mm <= 0:
        raise ValueError(f"panel_rect_insert: part {part_id} có width/height <= 0")

    _ensure_component_block(doc, _BLOCK_PANEL_RECT, _build_panel_rect_block)
    # dịch điểm chèn về tâm: block gốc ở góc dưới-trái (0,0)-(1,1), tâm = (0.5,0.5)
    # trong toạ độ đã scale = (width/2, height/2) -> trừ đi để insert nằm đúng tâm
    cx = center[0] - (width_mm / 2.0) * math.cos(math.radians(rotation_deg)) + (height_mm / 2.0) * math.sin(math.radians(rotation_deg))
    cy = center[1] - (width_mm / 2.0) * math.sin(math.radians(rotation_deg)) - (height_mm / 2.0) * math.cos(math.radians(rotation_deg))

    blockref = msp.add_blockref(
        _BLOCK_PANEL_RECT, (cx, cy),
        dxfattribs={"layer": layer, "xscale": width_mm, "yscale": height_mm, "rotation": rotation_deg},
    )
    blockref.add_auto_attribs({
        "PART_ID": part_id, "WIDTH_MM": f"{width_mm:.2f}", "HEIGHT_MM": f"{height_mm:.2f}",
    })

    return ComponentInsertResult(
        part_id=part_id, component_type="panel_rect", handle=blockref.dxf.handle,
        layer=layer, insert_point=(center[0], center[1]),
    )


def bracket_L_insert(
    doc, msp, corner: Tuple[float, float], leg_a_mm: float, leg_b_mm: float,
    rotation_deg: float, layer: str, part_id: str,
) -> ComponentInsertResult:
    """Chèn 1 giá đỡ góc L cấu trúc tại `corner` (điểm coincident_endpoint
    của 2 line, = góc trong của L). `leg_a_mm` / `leg_b_mm` = chiều dài 2
    cánh (= length 2 line). `rotation_deg` = hướng cánh A (line thứ nhất)
    so với trục +X — cánh B tự vuông góc (+90°) do block đã thiết kế vậy."""
    if leg_a_mm <= 0 or leg_b_mm <= 0:
        raise ValueError(f"bracket_L_insert: part {part_id} có leg_a/leg_b <= 0")

    _ensure_component_block(doc, _BLOCK_BRACKET_L, _build_bracket_L_block)
    # xscale = leg_a (cánh ngang block), yscale = leg_b (cánh dọc block)
    blockref = msp.add_blockref(
        _BLOCK_BRACKET_L, corner,
        dxfattribs={"layer": layer, "xscale": leg_a_mm, "yscale": leg_b_mm, "rotation": rotation_deg},
    )
    blockref.add_auto_attribs({
        "PART_ID": part_id, "LEG_A_MM": f"{leg_a_mm:.2f}", "LEG_B_MM": f"{leg_b_mm:.2f}",
    })

    return ComponentInsertResult(
        part_id=part_id, component_type="bracket_L", handle=blockref.dxf.handle,
        layer=layer, insert_point=(corner[0], corner[1]),
    )


def hinge_insert(
    doc, msp, pivot: Tuple[float, float], length_mm: float, gap_mm: float,
    rotation_deg: float, layer: str, part_id: str,
) -> ComponentInsertResult:
    """Chèn 1 bản lề tại `pivot` (tâm vòng tròn trục). `length_mm` = chiều
    dài lá (length 2 line song song). `gap_mm` = khoảng cách 2 lá (point-to-
    line distance giữa 2 line). `rotation_deg` = hướng lá so với trục +X."""
    if length_mm <= 0:
        raise ValueError(f"hinge_insert: part {part_id} có length_mm <= 0")
    if gap_mm <= 0:
        gap_mm = _HINGE_DEFAULT_GAP_MM  # fallback an toàn, không vẽ méo

    _ensure_component_block(doc, _BLOCK_HINGE, _build_hinge_block)
    # block đơn vị: lá dài 1 theo X, gap lá = 0.3 (block) -> yscale ép về gap_mm
    # xscale = length_mm. yscale = gap_mm / 0.3 để 2 lá cách nhau đúng gap_mm.
    yscale = gap_mm / 0.3
    blockref = msp.add_blockref(
        _BLOCK_HINGE, pivot,
        dxfattribs={"layer": layer, "xscale": length_mm, "yscale": yscale, "rotation": rotation_deg},
    )
    blockref.add_auto_attribs({
        "PART_ID": part_id, "LENGTH_MM": f"{length_mm:.2f}", "GAP_MM": f"{gap_mm:.2f}",
    })

    return ComponentInsertResult(
        part_id=part_id, component_type="hinge", handle=blockref.dxf.handle,
        layer=layer, insert_point=(pivot[0], pivot[1]),
    )


def node_insert(
    doc, msp, location: Tuple[float, float], leg_count: int, max_leg_mm: float,
    layer: str, part_id: str,
) -> ComponentInsertResult:
    """Chèn 1 ký hiệu nút hàn/gia cố tại `location` (điểm hội tụ). `leg_count`
    = số line hội tụ (cho Reviewer biết độ phức tạp nút). `max_leg_mm` = cánh
    dài nhất (scale ký hiệu cho thấy rõ khi zoom). Block cố định 4 cánh chữ
    thập — số cánh thật ghi vào ATTRIB, KHÔNG vẽ thêm cánh cho chính xác vì
    ký hiệu chỉ là marker, không phải hình học thật (hình học thật đã có ở
    lớp LINE thô)."""
    if leg_count < 2:
        raise ValueError(f"node_insert: part {part_id} có leg_count < 2")
    size = max(max_leg_mm, _MIN_NODE_SIZE_MM)

    _ensure_component_block(doc, _BLOCK_NODE, _build_node_block)
    blockref = msp.add_blockref(
        _BLOCK_NODE, location,
        dxfattribs={"layer": layer, "xscale": size, "yscale": size},
    )
    blockref.add_auto_attribs({"PART_ID": part_id, "LEG_COUNT": str(leg_count)})

    return ComponentInsertResult(
        part_id=part_id, component_type="node", handle=blockref.dxf.handle,
        layer=layer, insert_point=(location[0], location[1]),
    )


# ----------------------------------------------- helper suy tham số compound --
# Các helper này tính toạ độ insert + size từ nhiều primitive, dùng
# written_geometry (đã solve). Tách riêng để dễ test + dễ đổi thuật toán.

def _line_endpoints(geo: dict) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Trích (start, end) từ written geometry dict của line."""
    return (geo["start"][0], geo["start"][1]), (geo["end"][0], geo["end"][1])


def _line_length(geo: dict) -> float:
    s, e = _line_endpoints(geo)
    return math.hypot(e[0] - s[0], e[1] - s[1])


def _line_angle_deg(geo: dict) -> float:
    """Góc line so với +X (deg), không phân biệt chiều (line A->B và B->A
    cùng góc vì đều là 1 đường thẳng về hình học)."""
    s, e = _line_endpoints(geo)
    return math.degrees(math.atan2(e[1] - s[1], e[0] - s[0]))


def _point_to_infinite_line_distance(
    pt: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float],
) -> float:
    """Khoảng cách pt tới đường thẳng vô hạn qua a-b (cho gap bản lề)."""
    ax, ay = b[0] - a[0], b[1] - a[1]
    seg_len = math.hypot(ax, ay)
    if seg_len == 0:
        return math.hypot(pt[0] - a[0], pt[1] - a[1])
    cross = ax * (pt[1] - a[1]) - ay * (pt[0] - a[0])
    return abs(cross) / seg_len


def _shared_endpoint(
    geo_a: dict, geo_b: dict, tol_mm: float = 1e-3,
) -> Optional[Tuple[float, float]]:
    """Tìm endpoint chung của 2 line (coincident_endpoint). Trả điểm chung
    hoặc None nếu 2 line không có endpoint nào trùng."""
    a_ends = _line_endpoints(geo_a)
    b_ends = _line_endpoints(geo_b)
    for pa in a_ends:
        for pb in b_ends:
            if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) <= tol_mm:
                return pa
    return None


def _bbox_of_lines(geos: List[dict]) -> Optional[Tuple[float, float, float, float]]:
    """Bounding box axis-aligned của nhiều line -> (min_x, min_y, max_x, max_y).
    Trả None nếu danh sách rỗng."""
    if not geos:
        return None
    xs: List[float] = []
    ys: List[float] = []
    for g in geos:
        s, e = _line_endpoints(g)
        xs += [s[0], e[0]]
        ys += [s[1], e[1]]
    return min(xs), min(ys), max(xs), max(ys)


def _cluster_center(endpoints: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Tâm (trung bình) của tập endpoint — dùng cho diem_noi (cluster điểm
    hội tụ có thể không khớp tuyệt đối do ảnh scan). Trả (cx, cy)."""
    if not endpoints:
        return (0.0, 0.0)
    cx = sum(p[0] for p in endpoints) / len(endpoints)
    cy = sum(p[1] for p in endpoints) / len(endpoints)
    return (cx, cy)


def _closest_endpoint_to(
    geo: dict, target: Tuple[float, float],
) -> Tuple[float, float]:
    """Endpoint của line gần `target` nhất — dùng cho diem_noi: chỉ lấy đầu
    line hướng vào điểm hội tụ, không phải đầu kia."""
    s, e = _line_endpoints(geo)
    ds = math.hypot(s[0] - target[0], s[1] - target[1])
    de = math.hypot(e[0] - target[0], e[1] - target[1])
    return s if ds <= de else e


# ----------------------------------------------- cầu nối Semantic IR -> Insert --
@dataclass
class ComponentAssembly:
    inserted: List[ComponentInsertResult] = field(default_factory=list)
    skipped_part_ids: List[str] = field(default_factory=list)
    skip_reasons: Dict[str, str] = field(default_factory=dict)


def _layer_for_part_type(part_type: str) -> str:
    return f"COMP_{part_type.upper()}"


def _resolve_single_primitive_part(
    part, doc, msp, geo: dict, layer: str,
) -> Optional[ComponentInsertResult]:
    """Xử lý part có đúng 1 primitive (single-primitive). Trả kết quả insert
    hoặc None nếu part_type không map được (caller sẽ skip). Raise ValueError
    nếu part_type map được nhưng geometry sai loại (vd part_type line nhưng
    primitive là circle)."""
    pid = part.primitive_ids[0]
    if part.part_type in _BEAM_PART_TYPES:
        if geo["type"] != "line":
            raise ValueError(f"part_type={part.part_type} nhưng primitive {pid} không phải line")
        return frame_insert_beam(doc, msp, geo["start"], geo["end"], layer, part.id)
    if part.part_type in _BRACKET_PART_TYPES:
        if geo["type"] != "circle":
            raise ValueError(f"part_type={part.part_type} nhưng primitive {pid} không phải circle")
        return bracket_insert(doc, msp, geo["center"], layer, part.id, hole_diameter_mm=geo["radius"] * 2.0)
    if part.part_type in _PANEL_ROUND_PART_TYPES:
        if geo["type"] != "circle":
            raise ValueError(f"part_type={part.part_type} nhưng primitive {pid} không phải circle")
        return panel_insert(doc, msp, geo["center"], geo["radius"], layer, part.id)
    return None  # part_type không thuộc single-primitive


def _resolve_compound_part(
    part, doc, msp, geos_by_pid: Dict[str, dict], layer: str,
) -> Optional[ComponentInsertResult]:
    """Xử lý part có nhiều primitive (compound). Suy tham số insert từ hình
    học nhiều primitive. Trả kết quả insert, None nếu part_type không thuộc
    compound, raise ValueError nếu dữ liệu không suy ra được."""
    pids = part.primitive_ids

    if part.part_type in _PANEL_RECT_PART_TYPES:
        # khung_chu_nhat: bbox của tất cả line -> center + width + height
        line_geos = [geos_by_pid[p] for p in pids if geos_by_pid.get(p, {}).get("type") == "line"]
        if len(line_geos) < 2:
            raise ValueError(
                f"part_type={part.part_type} nhưng chỉ có {len(line_geos)} line (cần >=2) "
                f"trong {len(pids)} primitive"
            )
        bbox = _bbox_of_lines(line_geos)
        if bbox is None:
            raise ValueError(f"part_type={part.part_type} nhưng không tính được bbox")
        min_x, min_y, max_x, max_y = bbox
        width = max_x - min_x
        height = max_y - min_y
        if width <= 0 or height <= 0:
            raise ValueError(f"part_type={part.part_type} nhưng bbox suy biến (width={width}, height={height})")
        center = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
        # rotation: đo từ line dài nhất (heuristic — khung thật có thể xoay)
        longest = max(line_geos, key=_line_length)
        return panel_rect_insert(doc, msp, center, width, height, layer, part.id, rotation_deg=0.0)

    if part.part_type in _BRACKET_L_PART_TYPES:
        # gia_do: 2 line perpendicular + coincident_endpoint
        line_geos = [geos_by_pid[p] for p in pids if geos_by_pid.get(p, {}).get("type") == "line"]
        if len(line_geos) < 2:
            raise ValueError(
                f"part_type={part.part_type} nhưng chỉ có {len(line_geos)} line (cần đúng 2)"
            )
        ga, gb = line_geos[0], line_geos[1]
        corner = _shared_endpoint(ga, gb)
        if corner is None:
            raise ValueError(f"part_type={part.part_type} nhưng 2 line không có coincident_endpoint chung")
        leg_a = _line_length(ga)
        leg_b = _line_length(gb)
        # rotation = góc của cánh A, với điểm chèn là corner -> cần góc hướng ra xa corner
        # xác định đầu xa corner của line A
        a_start, a_end = _line_endpoints(ga)
        far_a = a_end if math.hypot(a_end[0] - corner[0], a_end[1] - corner[1]) > math.hypot(a_start[0] - corner[0], a_start[1] - corner[1]) else a_start
        rotation = math.degrees(math.atan2(far_a[1] - corner[1], far_a[0] - corner[0]))
        return bracket_L_insert(doc, msp, corner, leg_a, leg_b, rotation, layer, part.id)

    if part.part_type in _HINGE_PART_TYPES:
        # ban_le: 2 line parallel + (tuỳ chọn) circle. Line là chính.
        line_geos = [geos_by_pid[p] for p in pids if geos_by_pid.get(p, {}).get("type") == "line"]
        if len(line_geos) < 2:
            raise ValueError(
                f"part_type={part.part_type} nhưng chỉ có {len(line_geos)} line (cần đúng 2)"
            )
        ga, gb = line_geos[0], line_geos[1]
        # pivot = endpoint đầu của line A (heuristic — bản lề trục ở 1 đầu)
        a_start, _ = _line_endpoints(ga)
        length = _line_length(ga)
        gap = _point_to_infinite_line_distance(a_start, *_line_endpoints(gb))
        if gap <= 0:
            gap = _HINGE_DEFAULT_GAP_MM
        rotation = _line_angle_deg(ga)
        return hinge_insert(doc, msp, a_start, length, gap, rotation, layer, part.id)

    if part.part_type in _NODE_PART_TYPES:
        # diem_noi: >=3 line hội tụ 1 điểm. Lấy cluster center + leg_count.
        line_geos = [geos_by_pid[p] for p in pids if geos_by_pid.get(p, {}).get("type") == "line"]
        if len(line_geos) < 2:
            raise ValueError(
                f"part_type={part.part_type} nhưng chỉ có {len(line_geos)} line (cần >=2)"
            )
        # cluster center = trung bình tất cả endpoint
        all_ends: List[Tuple[float, float]] = []
        for g in line_geos:
            all_ends += list(_line_endpoints(g))
        center = _cluster_center(all_ends)
        # leg_count = số line hội tụ; max_leg = cánh dài nhất
        leg_count = len(line_geos)
        max_leg = max((_line_length(g) for g in line_geos), default=0.0)
        return node_insert(doc, msp, center, leg_count, max_leg, layer, part.id)

    return None  # part_type không thuộc compound


def assemble_semantic_components(
    doc, msp, semantic_doc, written_geometry_by_primitive_id: Dict[str, dict],
) -> ComponentAssembly:
    """Đọc `SemanticIRDocument.parts` (Phase 2), với mỗi part có `part_type`
    đã map được (mục mapping ở docstring đầu module), tra hình học ĐÃ GHI
    thật vào DXF (`written_geometry_by_primitive_id` — nguồn sự thật của
    `builder.py`, đã áp `solved_primitives` nếu có, KHÔNG tra lại toạ độ thô
    — cùng nguyên tắc `reviewer.py` mục 12.2) rồi gọi đúng hàm insert tương
    ứng. Part không map được/thiếu dữ liệu bị bỏ qua với lý do rõ ràng
    trong `skip_reasons`, không raise — lỗi cục bộ không nên chặn cả bản vẽ
    (nguyên tắc mục 7, đã áp dụng xuyên suốt `builder.py`).

    Hỗ trợ cả single-primitive parts (thanh_*/lo_bat_vit/duong_vien_tron)
    và compound parts (khung_chu_nhat/gia_do/ban_le/diem_noi) — đúng trạng
    thái Phase 2 nâng cao (mục 11.4).
    """
    assembly = ComponentAssembly()

    for part in semantic_doc.parts:
        # gom geometry đã ghi của mọi primitive trong part
        geos_by_pid: Dict[str, dict] = {
            pid: written_geometry_by_primitive_id[pid]
            for pid in part.primitive_ids
            if pid in written_geometry_by_primitive_id
        }
        if len(geos_by_pid) != len(part.primitive_ids):
            missing = [p for p in part.primitive_ids if p not in geos_by_pid]
            assembly.skipped_part_ids.append(part.id)
            assembly.skip_reasons[part.id] = (
                f"primitive(s) {missing} không có written_geometry (có thể đã bị "
                f"builder.py skip do thiếu geometry/text_data)"
            )
            continue

        layer = _layer_for_part_type(part.part_type)

        try:
            if len(part.primitive_ids) == 1:
                # single-primitive path (giữ nguyên hành vi ZIP gốc)
                res = _resolve_single_primitive_part(
                    part, doc, msp, geos_by_pid[part.primitive_ids[0]], layer,
                )
                if res is None:
                    assembly.skipped_part_ids.append(part.id)
                    assembly.skip_reasons[part.id] = (
                        f"part_type={part.part_type} chưa có Semantic API tương ứng "
                        f"(chỉ hỗ trợ single={sorted(_BEAM_PART_TYPES | _BRACKET_PART_TYPES | _PANEL_ROUND_PART_TYPES)}, "
                        f"compound={sorted(_PANEL_RECT_PART_TYPES | _BRACKET_L_PART_TYPES | _HINGE_PART_TYPES | _NODE_PART_TYPES)})"
                    )
                    continue
            else:
                # compound path (mục 11.4 nâng cao)
                res = _resolve_compound_part(part, doc, msp, geos_by_pid, layer)
                if res is None:
                    assembly.skipped_part_ids.append(part.id)
                    assembly.skip_reasons[part.id] = (
                        f"part_type={part.part_type} chưa có Semantic API tương ứng "
                        f"(xem danh sách hỗ trợ ở assemble_semantic_components docstring)"
                    )
                    continue
        except ValueError as exc:
            assembly.skipped_part_ids.append(part.id)
            assembly.skip_reasons[part.id] = str(exc)
            continue

        assembly.inserted.append(res)

    return assembly
