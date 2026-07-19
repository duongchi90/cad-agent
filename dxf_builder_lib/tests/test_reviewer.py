"""
test_reviewer.py — test cho `dxf_builder_lib.reviewer.review_dxf()`
(Reviewer #1, headless, IR ⇄ DXF).

`test_missing_ezdxf_raises_clear_import_error` LUÔN chạy được. Các test
còn lại cần `ezdxf` thật — build 1 file DXF thật bằng `builder.build_dxf()`
rồi cố tình "phá" nó theo đúng kiểu lỗi dịch thuật thật sự có thể xảy ra
(handle sai lệch, toạ độ bị sửa sau khi build) để xác nhận reviewer bắt
được, tự SKIP nếu chưa cài `ezdxf`.
"""

from __future__ import annotations

import os
import tempfile

from primitive_ir_lib.models import (
    Calibration, CircleGeometry, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace,
)
from semantic_ir_lib.models import PrimitiveIRRef, SemanticIRDocument, SemanticPart

from dxf_builder_lib.builder import BuildResult, build_dxf
from dxf_builder_lib.reviewer import ComponentMismatch, review_dxf

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


def _beam_semantic_doc() -> SemanticIRDocument:
    """1 part thanh_ngang (frame_insert_beam) — dùng chung cho các test
    round-trip INSERT bên dưới."""
    return SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=1),
        parts=[SemanticPart(part_type="thanh_ngang", primitive_ids=["b1"], confidence=1.0)],
        constraints=[],
    )


def _build_beam_component(tmp_dir: str):
    """Build 1 file DXF có đúng 1 component INSERT (frame_beam, từ dầm dài
    500mm) — trả (build_result, part_id, out_path). Dùng chung cho mọi test
    round-trip INSERT bên dưới (mỗi test tự tamper/edit theo đúng loại lỗi
    muốn kiểm tra)."""
    beam = _line("b1", 0, 0, 500, 0)
    doc = _doc(beam)
    semantic_doc = _beam_semantic_doc()
    out_path = os.path.join(tmp_dir, "out.dxf")
    build_result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)
    part_id = semantic_doc.parts[0].id
    return build_result, part_id, out_path


def test_missing_ezdxf_raises_clear_import_error():
    if _HAS_EZDXF:
        print("SKIP test_missing_ezdxf_raises_clear_import_error (reviewer) — ezdxf ĐANG cài")
        return
    fake_result = BuildResult(output_path="/tmp/does_not_matter.dxf")
    try:
        review_dxf(fake_result)
        assert False, "phải raise ImportError khi chưa cài ezdxf"
    except ImportError as exc:
        assert "ezdxf" in str(exc)
    print("OK   test_missing_ezdxf_raises_clear_import_error (reviewer)")


def test_review_passes_on_correctly_built_dxf():
    if not _HAS_EZDXF:
        print("SKIP test_review_passes_on_correctly_built_dxf — chưa cài ezdxf")
        return
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 0, 50, 100, 50)
    doc = _doc(l1, l2)

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(doc, out_path)
        review_result = review_dxf(build_result)

        assert review_result.passed, review_result.mismatches
        assert review_result.checked_count == 2
        assert review_result.mismatches == []
    print("OK   test_review_passes_on_correctly_built_dxf")


def test_review_flags_handle_not_found_after_tamper():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_handle_not_found_after_tamper — chưa cài ezdxf")
        return
    l1 = _line("l1", 0, 0, 100, 0)
    doc = _doc(l1)

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(doc, out_path)
        # mô phỏng lỗi mapping: handle bị ghi sai (vd bug ở builder tương lai)
        build_result.handle_by_primitive_id["l1"] = "FFFFFF"

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any("không tìm thấy" in m for m in review_result.mismatches)
    print("OK   test_review_flags_handle_not_found_after_tamper")


def test_review_flags_geometry_mismatch_after_manual_dxf_edit():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_geometry_mismatch_after_manual_dxf_edit — chưa cài ezdxf")
        return
    l1 = _line("l1", 0, 0, 100, 0)
    doc = _doc(l1)

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(doc, out_path)

        # mô phỏng lỗi dịch thuật thật: 1 bước ghi/serialize sau đó (vd
        # Repair #1) làm lệch toạ độ entity so với những gì Builder DỰ ĐỊNH
        # ghi (written_geometry_by_primitive_id không đổi) -- chỉnh sửa
        # trực tiếp file rồi lưu lại để reviewer đọc lại thấy sai lệch
        edit_doc = ezdxf.readfile(out_path)
        entity = edit_doc.entitydb.get(build_result.handle_by_primitive_id["l1"])
        entity.dxf.end = (999, 999)
        edit_doc.saveas(out_path)

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any("điểm cuối LINE lệch" in m for m in review_result.mismatches)
    print("OK   test_review_flags_geometry_mismatch_after_manual_dxf_edit")


def test_review_flags_layer_mismatch():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_layer_mismatch — chưa cài ezdxf")
        return
    l1 = _line("l1", 0, 0, 100, 0)
    doc = _doc(l1)

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(doc, out_path)
        # mô phỏng bug: BuildResult ghi nhận sai layer so với layer thật
        # sự đã ghi vào entity (layer thật vẫn là UNCLASSIFIED)
        build_result.layer_by_primitive_id["l1"] = "THANH_NGANG"

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any("layer" in m for m in review_result.mismatches)
    print("OK   test_review_flags_layer_mismatch")


# ===================================================== INSERT round-trip ==
# Reviewer #1 mở rộng: round-trip kiểm tra entity INSERT (Semantic
# Component API, semantic_components.py) — handle, block name, layer,
# insert point, x/y/z scale, rotation, ATTRIB. Mỗi test dưới đây cố tình
# "phá" đúng 1 loại lỗi dịch thuật quan trọng, y hệt cách các test primitive
# ở trên đã làm cho LINE/CIRCLE/ARC/TEXT.

def test_review_insert_passes_on_correctly_built_component():
    if not _HAS_EZDXF:
        print("SKIP test_review_insert_passes_on_correctly_built_component — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, _ = _build_beam_component(tmp)
        review_result = review_dxf(build_result)

        assert review_result.passed, review_result.format_report()
        assert review_result.component_checked_count == 1
        assert review_result.component_mismatches == []
    print("OK   test_review_insert_passes_on_correctly_built_component")


def test_review_flags_insert_handle_not_found_after_tamper():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_insert_handle_not_found_after_tamper — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, _ = _build_beam_component(tmp)
        # mô phỏng lỗi mapping: handle component bị ghi sai
        build_result.component_handle_by_part_id[part_id] = "FFFFFF"

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any(
            cm.part_id == part_id and cm.field == "handle" and "không tìm thấy" in cm.message
            for cm in review_result.component_mismatches
        )
    print("OK   test_review_flags_insert_handle_not_found_after_tamper")


def test_review_flags_insert_missing_written_component():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_insert_missing_written_component — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, _ = _build_beam_component(tmp)
        # mô phỏng bug ở builder.py: quên ghi written_component cho part này
        del build_result.written_component_by_part_id[part_id]

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any(
            cm.part_id == part_id and cm.field == "written_component"
            for cm in review_result.component_mismatches
        )
    print("OK   test_review_flags_insert_missing_written_component")


def test_review_flags_insert_block_name_mismatch():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_insert_block_name_mismatch — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, _ = _build_beam_component(tmp)
        # mô phỏng bug: BuildResult ghi nhận sai block name so với entity thật
        build_result.written_component_by_part_id[part_id]["block_name"] = "COMP_WRONG_BLOCK"

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any(
            cm.part_id == part_id and cm.field == "block_name"
            for cm in review_result.component_mismatches
        )
    print("OK   test_review_flags_insert_block_name_mismatch")


def test_review_flags_insert_layer_mismatch():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_insert_layer_mismatch — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, _ = _build_beam_component(tmp)
        build_result.written_component_by_part_id[part_id]["layer"] = "COMP_WRONG_LAYER"

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any(
            cm.part_id == part_id and cm.field == "layer"
            for cm in review_result.component_mismatches
        )
    print("OK   test_review_flags_insert_layer_mismatch")


def test_review_flags_insert_point_mismatch_after_manual_dxf_edit():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_insert_point_mismatch_after_manual_dxf_edit — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, out_path = _build_beam_component(tmp)

        # chỉnh sửa thật entity INSERT trên đĩa (mô phỏng lỗi dịch thuật
        # thật, giống test_review_flags_geometry_mismatch_after_manual_dxf_edit)
        edit_doc = ezdxf.readfile(out_path)
        entity = edit_doc.entitydb.get(build_result.component_handle_by_part_id[part_id])
        entity.dxf.insert = (999.0, 999.0, 0.0)
        edit_doc.saveas(out_path)

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any(
            cm.part_id == part_id and cm.field == "insert_point"
            for cm in review_result.component_mismatches
        )
    print("OK   test_review_flags_insert_point_mismatch_after_manual_dxf_edit")


def test_review_flags_insert_scale_mismatch_after_manual_dxf_edit():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_insert_scale_mismatch_after_manual_dxf_edit — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, out_path = _build_beam_component(tmp)

        edit_doc = ezdxf.readfile(out_path)
        entity = edit_doc.entitydb.get(build_result.component_handle_by_part_id[part_id])
        entity.dxf.xscale = 1.0  # đáng lẽ = 500.0 (chiều dài dầm)
        edit_doc.saveas(out_path)

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any(
            cm.part_id == part_id and cm.field == "xscale"
            for cm in review_result.component_mismatches
        )
    print("OK   test_review_flags_insert_scale_mismatch_after_manual_dxf_edit")


def test_review_flags_insert_rotation_mismatch_after_manual_dxf_edit():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_insert_rotation_mismatch_after_manual_dxf_edit — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, out_path = _build_beam_component(tmp)

        edit_doc = ezdxf.readfile(out_path)
        entity = edit_doc.entitydb.get(build_result.component_handle_by_part_id[part_id])
        entity.dxf.rotation = 45.0  # dầm nằm ngang thật -> phải là 0.0
        edit_doc.saveas(out_path)

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any(
            cm.part_id == part_id and cm.field == "rotation_deg"
            for cm in review_result.component_mismatches
        )
    print("OK   test_review_flags_insert_rotation_mismatch_after_manual_dxf_edit")


def test_review_flags_insert_attrib_value_mismatch_after_manual_dxf_edit():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_insert_attrib_value_mismatch_after_manual_dxf_edit — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, out_path = _build_beam_component(tmp)

        edit_doc = ezdxf.readfile(out_path)
        entity = edit_doc.entitydb.get(build_result.component_handle_by_part_id[part_id])
        for attrib in entity.attribs:
            if attrib.dxf.tag == "LENGTH_MM":
                attrib.dxf.text = "999.99"
        edit_doc.saveas(out_path)

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any(
            cm.part_id == part_id and cm.field == "attrib:LENGTH_MM"
            for cm in review_result.component_mismatches
        )
    print("OK   test_review_flags_insert_attrib_value_mismatch_after_manual_dxf_edit")


def test_review_flags_insert_attrib_missing_after_manual_dxf_edit():
    if not _HAS_EZDXF:
        print("SKIP test_review_flags_insert_attrib_missing_after_manual_dxf_edit — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, out_path = _build_beam_component(tmp)

        # mô phỏng lỗi dịch thuật thật: 1 ATTRIB bị xoá mất khỏi entity
        edit_doc = ezdxf.readfile(out_path)
        entity = edit_doc.entitydb.get(build_result.component_handle_by_part_id[part_id])
        target = next(a for a in entity.attribs if a.dxf.tag == "PROFILE")
        entity.attribs.remove(target)
        edit_doc.saveas(out_path)

        review_result = review_dxf(build_result)
        assert not review_result.passed
        assert any(
            cm.part_id == part_id and cm.field == "attrib:PROFILE" and cm.actual is None
            for cm in review_result.component_mismatches
        )
    print("OK   test_review_flags_insert_attrib_missing_after_manual_dxf_edit")


def test_review_ignores_components_when_build_components_false():
    """build_components=False (mặc định) -> không có component nào để
    kiểm tra, review vẫn PASS bình thường (không đổi hành vi cũ)."""
    if not _HAS_EZDXF:
        print("SKIP test_review_ignores_components_when_build_components_false — chưa cài ezdxf")
        return
    l1 = _line("l1", 0, 0, 100, 0)
    doc = _doc(l1)

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(doc, out_path)  # build_components mặc định False
        review_result = review_dxf(build_result)

        assert review_result.passed
        assert review_result.component_checked_count == 0
        assert review_result.component_mismatches == []
    print("OK   test_review_ignores_components_when_build_components_false")


def test_component_mismatch_is_structured_not_free_text():
    """Xác nhận report có cấu trúc (field/expected/actual, không phải chỉ
    chuỗi tự do) — dùng để lọc/debug, vd lọc riêng mọi lỗi 1 field."""
    if not _HAS_EZDXF:
        print("SKIP test_component_mismatch_is_structured_not_free_text — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, _ = _build_beam_component(tmp)
        build_result.written_component_by_part_id[part_id]["layer"] = "COMP_WRONG_LAYER"

        review_result = review_dxf(build_result)
        assert not review_result.passed
        cm = review_result.component_mismatches[0]
        assert isinstance(cm, ComponentMismatch)
        assert cm.part_id == part_id
        assert cm.field == "layer"
        assert cm.expected == "COMP_WRONG_LAYER"
        assert isinstance(cm.actual, str)
        # format_report() gom theo part_id, dễ debug
        report = review_result.format_report()
        assert part_id in report
        assert "layer" in report
    print("OK   test_component_mismatch_is_structured_not_free_text")


_TESTS = [
    test_missing_ezdxf_raises_clear_import_error,
    test_review_passes_on_correctly_built_dxf,
    test_review_flags_handle_not_found_after_tamper,
    test_review_flags_geometry_mismatch_after_manual_dxf_edit,
    test_review_flags_layer_mismatch,
    # INSERT round-trip (Reviewer #1 mở rộng)
    test_review_insert_passes_on_correctly_built_component,
    test_review_flags_insert_handle_not_found_after_tamper,
    test_review_flags_insert_missing_written_component,
    test_review_flags_insert_block_name_mismatch,
    test_review_flags_insert_layer_mismatch,
    test_review_flags_insert_point_mismatch_after_manual_dxf_edit,
    test_review_flags_insert_scale_mismatch_after_manual_dxf_edit,
    test_review_flags_insert_rotation_mismatch_after_manual_dxf_edit,
    test_review_flags_insert_attrib_value_mismatch_after_manual_dxf_edit,
    test_review_flags_insert_attrib_missing_after_manual_dxf_edit,
    test_review_ignores_components_when_build_components_false,
    test_component_mismatch_is_structured_not_free_text,
]


def run_all():
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
