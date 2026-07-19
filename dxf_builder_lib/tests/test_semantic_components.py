"""
test_semantic_components.py — test cho `dxf_builder_lib.semantic_components`
(Semantic API domain khung xương/thùng xe cải tạo, mục 12.4 + 11.4): 3 hàm
single-primitive (`frame_insert_beam`, `bracket_insert`, `panel_insert`) +
4 hàm compound (`panel_rect_insert`, `bracket_L_insert`, `hinge_insert`,
`node_insert`), + `assemble_semantic_components()`.

`test_missing_ezdxf_raises_clear_import_error` LUÔN chạy được (không cần
ezdxf). Các test còn lại cần `ezdxf` thật, tự SKIP nếu chưa cài — cùng quy
ước `test_builder.py`/`test_reviewer.py`/`test_repair.py`.
"""

from __future__ import annotations

import math
import os
import tempfile

from primitive_ir_lib.models import (
    Calibration, CircleGeometry, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace,
)

from dxf_builder_lib.builder import build_dxf
from semantic_ir_lib.models import PrimitiveIRRef, SemanticIRDocument, SemanticPart

try:
    import ezdxf  # noqa: F401
    _HAS_EZDXF = True
except ImportError:
    _HAS_EZDXF = False


def _line(id_, x0, y0, x1, y1) -> Primitive:
    return Primitive(
        id=id_, type="line", source="geometry_opencv", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


def _circle(id_, cx, cy, r) -> Primitive:
    return Primitive(
        id=id_, type="circle", source="geometry_opencv", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
    )


def _doc(*prims: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="x.png", page_index=0, image_width_px=100, image_height_px=100),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=list(prims),
    )


# =================================================== single-primitive tests ==

def test_missing_ezdxf_raises_clear_import_error():
    if _HAS_EZDXF:
        print("SKIP test_missing_ezdxf_raises_clear_import_error (semantic_components) — "
              "ezdxf ĐANG cài (test này chỉ có ý nghĩa khi ezdxf CHƯA cài)")
        return
    beam = _line("b1", 0, 0, 500, 0)
    doc = _doc(beam)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=1),
        parts=[SemanticPart(part_type="thanh_ngang", primitive_ids=["b1"], confidence=1.0)],
        constraints=[],
    )
    try:
        build_dxf(doc, "/tmp/should_not_be_created.dxf", semantic_doc=semantic_doc, build_components=True)
        assert False, "phải raise ImportError khi chưa cài ezdxf"
    except ImportError as exc:
        assert "ezdxf" in str(exc)
    print("OK   test_missing_ezdxf_raises_clear_import_error (semantic_components)")


def test_frame_insert_beam_from_thanh_ngang_part():
    if not _HAS_EZDXF:
        print("SKIP test_frame_insert_beam_from_thanh_ngang_part — chưa cài ezdxf")
        return
    beam = _line("b1", 0, 0, 500, 0)  # dầm ngang dài 500mm
    doc = _doc(beam)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=1),
        parts=[SemanticPart(part_type="thanh_ngang", primitive_ids=["b1"], confidence=1.0)],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)

        assert result.component_count == 1
        part_id = semantic_doc.parts[0].id
        assert part_id in result.component_handle_by_part_id
        assert result.component_type_by_part_id[part_id] == "frame_beam"
        assert not result.skipped_part_ids

        reopened = ezdxf.readfile(out_path)
        entity = reopened.entitydb.get(result.component_handle_by_part_id[part_id])
        assert entity.dxftype() == "INSERT"
        assert entity.dxf.name == "COMP_FRAME_BEAM"
        assert abs(entity.dxf.xscale - 500.0) < 1e-6  # xscale = chiều dài dầm thật
        assert abs(entity.dxf.yscale - 1.0) < 1e-6     # yscale cố định, không kéo méo chữ
        attribs = {a.dxf.tag: a.dxf.text for a in entity.attribs}
        assert attribs["PART_ID"] == part_id
        assert attribs["LENGTH_MM"] == "500.00"
    print("OK   test_frame_insert_beam_from_thanh_ngang_part")


def test_bracket_insert_from_lo_bat_vit_part():
    if not _HAS_EZDXF:
        print("SKIP test_bracket_insert_from_lo_bat_vit_part — chưa cài ezdxf")
        return
    hole = _circle("h1", 100, 200, 4.0)  # lỗ bắt vít bán kính 4mm
    doc = _doc(hole)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=1),
        parts=[SemanticPart(part_type="lo_bat_vit", primitive_ids=["h1"], confidence=0.9)],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)

        part_id = semantic_doc.parts[0].id
        assert result.component_type_by_part_id[part_id] == "bracket"

        reopened = ezdxf.readfile(out_path)
        entity = reopened.entitydb.get(result.component_handle_by_part_id[part_id])
        assert entity.dxf.name == "COMP_BRACKET"
        assert entity.dxf.insert.x == 100 and entity.dxf.insert.y == 200
        attribs = {a.dxf.tag: a.dxf.text for a in entity.attribs}
        assert attribs["HOLE_DIAMETER_MM"] == "8.00"  # diameter = 2 * radius
    print("OK   test_bracket_insert_from_lo_bat_vit_part")


def test_panel_insert_from_duong_vien_tron_part():
    if not _HAS_EZDXF:
        print("SKIP test_panel_insert_from_duong_vien_tron_part — chưa cài ezdxf")
        return
    border = _circle("c1", 10, 20, 75.0)  # đường viền tròn bán kính 75mm
    doc = _doc(border)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=1),
        parts=[SemanticPart(part_type="duong_vien_tron", primitive_ids=["c1"], confidence=0.85)],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)

        part_id = semantic_doc.parts[0].id
        assert result.component_type_by_part_id[part_id] == "panel_round"

        reopened = ezdxf.readfile(out_path)
        entity = reopened.entitydb.get(result.component_handle_by_part_id[part_id])
        assert entity.dxf.name == "COMP_PANEL_ROUND"
        assert abs(entity.dxf.xscale - 75.0) < 1e-6
        attribs = {a.dxf.tag: a.dxf.text for a in entity.attribs}
        assert attribs["RADIUS_MM"] == "75.00"
    print("OK   test_panel_insert_from_duong_vien_tron_part")


# =================================================== compound tests (mục 11.4) ==

def test_panel_rect_from_khung_chu_nhat():
    """khung_chu_nhat = 4 line tạo HCN 200x100 -> panel_rect_insert."""
    if not _HAS_EZDXF:
        print("SKIP test_panel_rect_from_khung_chu_nhat — chưa cài ezdxf")
        return
    # HCN từ (0,0) đến (200,100): đáy, phải, trên, trái
    l_bottom = _line("kb", 0, 0, 200, 0)
    l_right = _line("kr", 200, 0, 200, 100)
    l_top = _line("kt", 200, 100, 0, 100)
    l_left = _line("kl", 0, 100, 0, 0)
    doc = _doc(l_bottom, l_right, l_top, l_left)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=4),
        parts=[SemanticPart(
            part_type="khung_chu_nhat",
            primitive_ids=["kb", "kr", "kt", "kl"],
            confidence=0.85,
        )],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)

        assert result.component_count == 1
        part_id = semantic_doc.parts[0].id
        assert result.component_type_by_part_id[part_id] == "panel_rect"
        assert not result.skipped_part_ids

        reopened = ezdxf.readfile(out_path)
        entity = reopened.entitydb.get(result.component_handle_by_part_id[part_id])
        assert entity.dxftype() == "INSERT"
        assert entity.dxf.name == "COMP_PANEL_RECT"
        # bbox 200x100 -> xscale=200, yscale=100
        assert abs(entity.dxf.xscale - 200.0) < 1e-6
        assert abs(entity.dxf.yscale - 100.0) < 1e-6
        attribs = {a.dxf.tag: a.dxf.text for a in entity.attribs}
        assert attribs["WIDTH_MM"] == "200.00"
        assert attribs["HEIGHT_MM"] == "100.00"
    print("OK   test_panel_rect_from_khung_chu_nhat")


def test_bracket_L_from_gia_do():
    """gia_do = 2 line vuông góc + coincident_endpoint tại (0,0)."""
    if not _HAS_EZDXF:
        print("SKIP test_bracket_L_from_gia_do — chưa cài ezdxf")
        return
    # cánh ngang: (0,0) -> (150,0), cánh dọc: (0,0) -> (0,80)
    l_h = _line("lh", 0, 0, 150, 0)
    l_v = _line("lv", 0, 0, 0, 80)
    doc = _doc(l_h, l_v)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=2),
        parts=[SemanticPart(
            part_type="gia_do",
            primitive_ids=["lh", "lv"],
            confidence=0.9,
        )],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)

        assert result.component_count == 1
        part_id = semantic_doc.parts[0].id
        assert result.component_type_by_part_id[part_id] == "bracket_L"

        reopened = ezdxf.readfile(out_path)
        entity = reopened.entitydb.get(result.component_handle_by_part_id[part_id])
        assert entity.dxf.name == "COMP_BRACKET_L"
        # leg_a = length line h = 150, leg_b = length line v = 80
        assert abs(entity.dxf.xscale - 150.0) < 1e-6
        assert abs(entity.dxf.yscale - 80.0) < 1e-6
        # điểm chèn = corner (0,0)
        assert abs(entity.dxf.insert.x) < 1e-6
        assert abs(entity.dxf.insert.y) < 1e-6
        attribs = {a.dxf.tag: a.dxf.text for a in entity.attribs}
        assert attribs["LEG_A_MM"] == "150.00"
        assert attribs["LEG_B_MM"] == "80.00"
    print("OK   test_bracket_L_from_gia_do")


def test_hinge_from_ban_le():
    """ban_le = 2 line song song + 2 circle nhỏ."""
    if not _HAS_EZDXF:
        print("SKIP test_hinge_from_ban_le — chưa cài ezdxf")
        return
    # 2 lá song song theo +X, gap 8mm: lá dưới y=0, lá trên y=8
    l_low = _line("ll", 0, 0, 120, 0)
    l_up = _line("lu", 0, 8, 120, 8)
    # 2 lỗ bắt vít gần endpoint (giả lập trục + vít)
    h1 = _circle("h1", 0, 4, 3.0)
    h2 = _circle("h2", 120, 4, 3.0)
    doc = _doc(l_low, l_up, h1, h2)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=4),
        parts=[SemanticPart(
            part_type="ban_le",
            primitive_ids=["ll", "lu", "h1", "h2"],
            confidence=0.8,
        )],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)

        assert result.component_count == 1
        part_id = semantic_doc.parts[0].id
        assert result.component_type_by_part_id[part_id] == "hinge"

        reopened = ezdxf.readfile(out_path)
        entity = reopened.entitydb.get(result.component_handle_by_part_id[part_id])
        assert entity.dxf.name == "COMP_HINGE"
        # xscale = length line = 120
        assert abs(entity.dxf.xscale - 120.0) < 1e-6
        # gap = 8mm, yscale = gap/0.3 = 26.666...
        assert abs(entity.dxf.yscale - (8.0 / 0.3)) < 1e-3
        attribs = {a.dxf.tag: a.dxf.text for a in entity.attribs}
        assert attribs["LENGTH_MM"] == "120.00"
        assert attribs["GAP_MM"] == "8.00"
    print("OK   test_hinge_from_ban_le")


def test_node_from_diem_noi():
    """diem_noi = 3 line hội tụ 1 điểm (0,0)."""
    if not _HAS_EZDXF:
        print("SKIP test_node_from_diem_noi — chưa cài ezdxf")
        return
    # 3 cánh tủa ra từ (0,0)
    l1 = _line("n1", 0, 0, 100, 0)
    l2 = _line("n2", 0, 0, 0, 80)
    l3 = _line("n3", 0, 0, -60, 60)
    doc = _doc(l1, l2, l3)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=3),
        parts=[SemanticPart(
            part_type="diem_noi",
            primitive_ids=["n1", "n2", "n3"],
            confidence=0.85,
        )],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)

        assert result.component_count == 1
        part_id = semantic_doc.parts[0].id
        assert result.component_type_by_part_id[part_id] == "node"

        reopened = ezdxf.readfile(out_path)
        entity = reopened.entitydb.get(result.component_handle_by_part_id[part_id])
        assert entity.dxf.name == "COMP_NODE"
        # leg_count = 3
        attribs = {a.dxf.tag: a.dxf.text for a in entity.attribs}
        assert attribs["LEG_COUNT"] == "3"
        # size = max leg length (100) -> xscale=100
        assert abs(entity.dxf.xscale - 100.0) < 1e-6
    print("OK   test_node_from_diem_noi")


def test_unclassified_part_is_skipped_with_reason():
    """part_type='unclassified' -> bị skip với lý do rõ ràng."""
    if not _HAS_EZDXF:
        print("SKIP test_unclassified_part_is_skipped_with_reason — chưa cài ezdxf")
        return
    beam = _line("u1", 0, 0, 100, 0)
    doc = _doc(beam)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=1),
        parts=[SemanticPart(part_type="unclassified", primitive_ids=["u1"], confidence=0.5)],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)

        assert result.component_count == 0
        assert len(result.skipped_part_ids) == 1
        part_id = semantic_doc.parts[0].id
        assert part_id in result.skipped_part_reasons
        assert result.skipped_part_reasons[part_id]  # lý do không rỗng
    print("OK   test_unclassified_part_is_skipped_with_reason")


def test_compound_missing_geometry_is_skipped():
    """compound part nhưng 1 primitive thiếu written_geometry -> skip."""
    if not _HAS_EZDXF:
        print("SKIP test_compound_missing_geometry_is_skipped — chưa cài ezdxf")
        return
    # chỉ có 3 line trong doc nhưng part reference 4 primitive
    l1 = _line("a1", 0, 0, 100, 0)
    l2 = _line("a2", 0, 0, 0, 100)
    l3 = _line("a3", 0, 0, -100, 0)
    doc = _doc(l1, l2, l3)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=3),
        parts=[SemanticPart(
            part_type="diem_noi",
            primitive_ids=["a1", "a2", "a3", "a4_missing"],  # a4_missing không tồn tại
            confidence=0.9,
        )],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)

        assert result.component_count == 0
        assert len(result.skipped_part_ids) == 1
        assert "a4_missing" in result.skipped_part_reasons[semantic_doc.parts[0].id]
    print("OK   test_compound_missing_geometry_is_skipped")


def test_build_components_false_by_default_does_not_add_inserts():
    if not _HAS_EZDXF:
        print("SKIP test_build_components_false_by_default_does_not_add_inserts — chưa cài ezdxf")
        return
    beam = _line("b1", 0, 0, 500, 0)
    doc = _doc(beam)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=1),
        parts=[SemanticPart(part_type="thanh_ngang", primitive_ids=["b1"], confidence=1.0)],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        # build_components mặc định False -> hành vi y hệt trước khi có module này
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc)

        assert result.component_count == 0
        assert result.component_handle_by_part_id == {}
        assert result.entity_count == 1  # vẫn vẽ hình học thô bình thường
    print("OK   test_build_components_false_by_default_does_not_add_inserts")


_TESTS = [
    # single-primitive
    test_missing_ezdxf_raises_clear_import_error,
    test_frame_insert_beam_from_thanh_ngang_part,
    test_bracket_insert_from_lo_bat_vit_part,
    test_panel_insert_from_duong_vien_tron_part,
    # compound (mục 11.4 nâng cao)
    test_panel_rect_from_khung_chu_nhat,
    test_bracket_L_from_gia_do,
    test_hinge_from_ban_le,
    test_node_from_diem_noi,
    # edge cases
    test_unclassified_part_is_skipped_with_reason,
    test_compound_missing_geometry_is_skipped,
    test_build_components_false_by_default_does_not_add_inserts,
]


def run_all():
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
