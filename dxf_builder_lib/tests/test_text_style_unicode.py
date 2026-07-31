"""Regression tests cho lỗi hiển thị sai tiếng Việt trong DXF preview.

Bug: build_dxf()/repair.py gọi msp.add_text(...) không set dxfattribs
["style"], nên mọi TEXT entity dùng style "Standard" mặc định của
ezdxf.new() (không setup=True) — font của style này là "txt" (txt.shx),
1 font stroke cơ bản KHÔNG có glyph cho ký tự có dấu tiếng Việt (ư, ơ, ệ,
ộ...). Mở file trong AutoCAD, các nhãn như "VẬT LIỆU"/"SỐ LƯỢNG" hiển thị
sai/mất dấu.

Đã reproduce trực tiếp bằng ezdxf:
    doc = ezdxf.new(dxfversion="R2010")
    doc.styles.get("Standard").dxf.font  ->  'txt'   (không phải TTF)

Fix: build_dxf() phải tạo (hoặc dùng lại) 1 text style trỏ tới font TTF hỗ
trợ Unicode (vd "Arial.ttf") và gán dxfattribs["style"] cho MỌI TEXT entity
— cả ở builder.py (build lần đầu) lẫn repair.py (vẽ lại sau repair).
"""

from __future__ import annotations

import tempfile

import pytest

from primitive_ir_lib.models import (
    Calibration, Point2D, Primitive, PrimitiveIRDocument, SourceDocument,
    TextData, Trace,
)

from dxf_builder_lib.builder import build_dxf

try:
    import ezdxf  # noqa: F401
    _HAS_EZDXF = True
except ImportError:
    _HAS_EZDXF = False


def _vietnamese_text_primitive() -> Primitive:
    return Primitive(
        id="t1", type="text", source="text_tesseract", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        text_data=TextData(
            content="VẬT LIỆU: THÉP KHÔNG GỈ",
            position=Point2D(0, 0), rotation_deg=0.0, height=3.5,
        ),
    )


def _doc(*prims: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="x.png", page_index=0, image_width_px=100, image_height_px=100),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=list(prims),
    )


@pytest.mark.skipif(not _HAS_EZDXF, reason="cần cài ezdxf")
def test_build_dxf_text_entity_uses_unicode_ttf_style_not_default_shx():
    """TEXT entity không được để trống dxfattribs['style'] (mặc định
    'Standard'/txt.shx) — phải trỏ tới 1 style dùng font TTF."""
    primitive_doc = _doc(_vietnamese_text_primitive())
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        output_path = f.name

    build_dxf(primitive_doc, output_path)

    saved = ezdxf.readfile(output_path)
    msp = saved.modelspace()
    text_entities = [e for e in msp if e.dxftype() == "TEXT"]
    assert len(text_entities) == 1, "phải có đúng 1 TEXT entity đã ghi"

    entity = text_entities[0]
    style_name = entity.dxf.style
    assert style_name != "Standard", (
        "TEXT không được dùng style 'Standard' mặc định — style đó dùng "
        "font txt.shx, không có glyph tiếng Việt có dấu"
    )

    style = saved.styles.get(style_name)
    font = (style.dxf.font or "").lower()
    assert font.endswith(".ttf"), (
        f"style '{style_name}' phải dùng font TTF Unicode (vd Arial.ttf), "
        f"đang là {style.dxf.font!r} — không hỗ trợ dấu tiếng Việt"
    )


@pytest.mark.skipif(not _HAS_EZDXF, reason="cần cài ezdxf")
def test_build_dxf_creates_unicode_style_only_once_for_multiple_texts():
    """2 primitive text -> chỉ 1 style Unicode được tạo (không trùng lặp
    entry trong styles table)."""
    primitive_doc = _doc(
        _vietnamese_text_primitive(),
        Primitive(
            id="t2", type="text", source="text_tesseract", confidence=0.9,
            trace=Trace(bbox_px=(0, 0, 10, 10)),
            text_data=TextData(content="SỐ LƯỢNG: 4", position=Point2D(10, 10), rotation_deg=0.0, height=3.5),
        ),
    )
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        output_path = f.name

    build_dxf(primitive_doc, output_path)

    saved = ezdxf.readfile(output_path)
    msp = saved.modelspace()
    styles_used = {e.dxf.style for e in msp if e.dxftype() == "TEXT"}
    assert len(styles_used) == 1, "cả 2 TEXT phải dùng chung 1 style Unicode"


@pytest.mark.skipif(not _HAS_EZDXF, reason="cần cài ezdxf")
def test_repair_dxf_rewrites_vietnamese_text_with_unicode_style():
    """Vòng lặp thật build -> tamper -> review -> repair -> review cho TEXT
    tiếng Việt: entity vẽ lại sau repair vẫn phải dùng style Unicode, KHÔNG
    được rơi về 'Standard' mặc định của add_text() không set style."""
    from dxf_builder_lib.repair import repair_dxf
    from dxf_builder_lib.reviewer import review_dxf

    primitive_doc = _doc(_vietnamese_text_primitive())
    with tempfile.TemporaryDirectory() as tmp:
        import os
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(primitive_doc, out_path)

        # phá file: xoá nội dung TEXT để tạo mismatch (mô phỏng lỗi dịch
        # thuật thật, cùng pattern test_repair_fixes_geometry_mismatch_on_line)
        corrupted = ezdxf.readfile(out_path)
        entity = corrupted.entitydb.get(build_result.handle_by_primitive_id["t1"])
        entity.dxf.text = "SAI HOAN TOAN"
        corrupted.saveas(out_path)

        review_before = review_dxf(build_result)
        assert not review_before.passed

        repair_result = repair_dxf(build_result, review_before.mismatches)
        assert repair_result.repaired_count == 1

        saved = ezdxf.readfile(out_path)
        msp = saved.modelspace()
        text_entities = [e for e in msp if e.dxftype() == "TEXT"]
        assert len(text_entities) == 1
        style_name = text_entities[0].dxf.style
        assert style_name != "Standard"
        style = saved.styles.get(style_name)
        assert (style.dxf.font or "").lower().endswith(".ttf")
