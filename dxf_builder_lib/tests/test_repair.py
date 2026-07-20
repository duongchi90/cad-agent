"""
test_repair.py — test cho `dxf_builder_lib.repair.repair_dxf()` (primitive
thô) và `repair_insert_components()` (INSERT component, thêm 19/07/2026,
HANDOFF.md mục "việc nên làm tiếp" #2 — Repair #1 cho INSERT).

`test_missing_ezdxf_raises_clear_import_error` LUÔN chạy được. Các test còn
lại cần `ezdxf` thật (build file thật, phá theo đúng kiểu lỗi thật, repair,
rồi review lại để xác nhận hết lỗi), tự SKIP nếu chưa cài `ezdxf`, cùng
quy ước đã dùng cho `test_builder.py`/`test_reviewer.py`.

Kịch bản test: không mock thủ công `BuildResult` — mỗi test BUILD đầy đủ từ
`build_dxf()` thật (để `written_geometry_by_primitive_id`/
`written_component_by_part_id` đúng), rồi gây lỗi theo cách thật (sửa file
DXF bằng ezdxf sau build), chạy `review_dxf()` để lấy `mismatches`/
`component_mismatches`, rồi `repair_dxf()`/`repair_insert_components()`,
rồi `review_dxf()` lần 2 để xác nhận không còn mismatch. Đây chính là vòng
lặp thật `build→review→repair→review` như trong pipeline. Fixture INSERT
(`_build_beam_component`) dùng chung với `test_reviewer.py`.
"""

from __future__ import annotations

import os
import tempfile

from primitive_ir_lib.models import (
    Calibration, CircleGeometry, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace,
)
from semantic_ir_lib.models import PrimitiveIRRef, SemanticIRDocument, SemanticPart

from dxf_builder_lib.builder import build_dxf
from dxf_builder_lib.repair import repair_dxf, repair_insert_components
from dxf_builder_lib.reviewer import review_dxf

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


def _beam_semantic_doc(part_type: str = "thanh_ngang", primitive_id: str = "b1") -> SemanticIRDocument:
    """1 part (frame_insert_beam) — cùng fixture với test_reviewer.py, dùng
    chung cho các test repair INSERT bên dưới."""
    return SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=1),
        parts=[SemanticPart(part_type=part_type, primitive_ids=[primitive_id], confidence=1.0)],
        constraints=[],
    )


def _build_beam_component(tmp_dir: str, beam_id: str = "b1", length: float = 500):
    """Build 1 file DXF có đúng 1 component INSERT (frame_beam) — trả
    (build_result, part_id, out_path). Cùng fixture với test_reviewer.py."""
    beam = _line(beam_id, 0, 0, length, 0)
    doc = _doc(beam)
    semantic_doc = _beam_semantic_doc(primitive_id=beam_id)
    out_path = os.path.join(tmp_dir, "out.dxf")
    build_result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)
    part_id = semantic_doc.parts[0].id
    return build_result, part_id, out_path


# ------------------------------------------------------------------ tests --

def test_missing_ezdxf_raises_clear_import_error():
    if _HAS_EZDXF:
        print("SKIP test_missing_ezdxf_raises_clear_import_error (repair) — ezdxf ĐANG cài")
        return
    from dxf_builder_lib.builder import BuildResult
    br = BuildResult(output_path="/tmp/fake.dxf")
    try:
        repair_dxf(br, ["l1: tọa độ sai"])
        assert False, "phải raise ImportError khi chưa cài ezdxf"
    except ImportError as exc:
        assert "ezdxf" in str(exc)
        assert "pip install" in str(exc)
    try:
        repair_insert_components(br, [])
        assert False, "repair_insert_components cũng phải raise ImportError khi chưa cài ezdxf"
    except ImportError as exc:
        assert "ezdxf" in str(exc)
        assert "pip install" in str(exc)
    print("OK   test_missing_ezdxf_raises_clear_import_error (repair)")


def test_repair_empty_mismatches_does_nothing():
    """Không có mismatch -> repair không làm gì, file giữ nguyên."""
    if not _HAS_EZDXF:
        print("SKIP test_repair_empty_mismatches_does_nothing — chưa cài ezdxf")
        return
    l1 = _line("l1", 0, 0, 100, 0)
    doc = _doc(l1)
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(doc, out_path)
        result = repair_dxf(build_result, mismatches=[])
        assert result.repaired_count == 0
        assert result.skipped_count == 0
        # file vẫn pass review sau khi repair rỗng
        review = review_dxf(build_result)
        assert review.passed
    print("OK   test_repair_empty_mismatches_does_nothing")


def test_repair_fixes_geometry_mismatch_on_line():
    """Mô phỏng lỗi dịch thuật thật: sửa tay toạ độ end của LINE trong file
    DXF SAU KHI build, rồi chạy review (phát hiện lỗi), repair (sửa lại
    đúng), review lần 2 (xác nhận hết lỗi)."""
    if not _HAS_EZDXF:
        print("SKIP test_repair_fixes_geometry_mismatch_on_line — chưa cài ezdxf")
        return
    l1 = _line("l1", 0, 0, 100, 0)
    doc = _doc(l1)
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(doc, out_path)

        # phá file: sửa tay toạ độ end của LINE để tạo mismatch
        corrupted = ezdxf.readfile(out_path)
        entity = corrupted.entitydb.get(build_result.handle_by_primitive_id["l1"])
        entity.dxf.end = (999, 999)  # sai hoàn toàn
        corrupted.saveas(out_path)

        review_before = review_dxf(build_result)
        assert not review_before.passed, "phải phát hiện mismatch sau khi phá file"
        assert any("l1" in m for m in review_before.mismatches)

        repair_result = repair_dxf(build_result, review_before.mismatches)
        assert repair_result.repaired_count == 1
        assert "l1" in repair_result.repaired_primitive_ids

        review_after = review_dxf(build_result)
        assert review_after.passed, (
            f"sau repair phải pass review, còn mismatch: {review_after.mismatches}"
        )
    print("OK   test_repair_fixes_geometry_mismatch_on_line")


def test_repair_fixes_layer_mismatch():
    """Layer bị ghi sai trong file DXF (không khớp layer trong BuildResult)
    -> review phát hiện -> repair xoá + vẽ lại -> review pass."""
    if not _HAS_EZDXF:
        print("SKIP test_repair_fixes_layer_mismatch — chưa cài ezdxf")
        return
    c1 = _circle("c1", 50, 50, 10)
    doc = _doc(c1)
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(doc, out_path)

        # phá file: đổi layer của entity sang layer sai
        corrupted = ezdxf.readfile(out_path)
        entity = corrupted.entitydb.get(build_result.handle_by_primitive_id["c1"])
        entity.dxf.layer = "WRONG_LAYER"
        corrupted.saveas(out_path)

        review_before = review_dxf(build_result)
        assert not review_before.passed

        repair_dxf(build_result, review_before.mismatches)

        review_after = review_dxf(build_result)
        assert review_after.passed, f"sau repair phải pass, còn: {review_after.mismatches}"
    print("OK   test_repair_fixes_layer_mismatch")


def test_repair_multiple_entities_independently():
    """Nhiều entity bị lỗi cùng lúc — mỗi cái phải được repair độc lập,
    không cái nào ảnh hưởng cái kia."""
    if not _HAS_EZDXF:
        print("SKIP test_repair_multiple_entities_independently — chưa cài ezdxf")
        return
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 0, 50, 100, 50)
    c1 = _circle("c1", 50, 25, 5)
    doc = _doc(l1, l2, c1)
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(doc, out_path)

        # phá: sửa l1 và l2 (để c1 nguyên vẹn)
        corrupted = ezdxf.readfile(out_path)
        e_l1 = corrupted.entitydb.get(build_result.handle_by_primitive_id["l1"])
        e_l2 = corrupted.entitydb.get(build_result.handle_by_primitive_id["l2"])
        e_l1.dxf.start = (1000, 1000)
        e_l2.dxf.end = (2000, 2000)
        corrupted.saveas(out_path)

        review_before = review_dxf(build_result)
        assert not review_before.passed
        broken_pids = {msg.split(":")[0].strip() for msg in review_before.mismatches}
        assert "l1" in broken_pids
        assert "l2" in broken_pids
        # c1 không nên bị báo lỗi
        assert "c1" not in broken_pids

        repair_result = repair_dxf(build_result, review_before.mismatches)
        assert repair_result.repaired_count == 2
        assert set(repair_result.repaired_primitive_ids) == {"l1", "l2"}

        review_after = review_dxf(build_result)
        assert review_after.passed, f"sau repair phải pass, còn: {review_after.mismatches}"
    print("OK   test_repair_multiple_entities_independently")


def test_repair_insert_empty_mismatches_does_nothing():
    """Không có component_mismatch -> repair không làm gì, file giữ nguyên
    (tương tự test_repair_empty_mismatches_does_nothing nhưng cho INSERT)."""
    if not _HAS_EZDXF:
        print("SKIP test_repair_insert_empty_mismatches_does_nothing — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, out_path = _build_beam_component(tmp)
        result = repair_insert_components(build_result, component_mismatches=[])
        assert result.repaired_count == 0
        assert result.skipped_count == 0
        review = review_dxf(build_result)
        assert review.passed
    print("OK   test_repair_insert_empty_mismatches_does_nothing")


def test_repair_insert_fixes_block_name_mismatch():
    """Mô phỏng lỗi dịch thuật thật: sửa tay block name của entity INSERT
    trong file DXF SAU KHI build, rồi review (phát hiện) -> repair (xoá +
    vẽ lại đúng bằng block gốc) -> review lần 2 (xác nhận hết lỗi)."""
    if not _HAS_EZDXF:
        print("SKIP test_repair_insert_fixes_block_name_mismatch — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, out_path = _build_beam_component(tmp)

        # phá file: tạo 1 block rỗng khác rồi trỏ INSERT sang đó
        corrupted = ezdxf.readfile(out_path)
        if "WRONG_BLOCK" not in corrupted.blocks:
            corrupted.blocks.new(name="WRONG_BLOCK")
        entity = corrupted.entitydb.get(build_result.component_handle_by_part_id[part_id])
        entity.dxf.name = "WRONG_BLOCK"
        corrupted.saveas(out_path)

        review_before = review_dxf(build_result)
        assert not review_before.passed, "phải phát hiện block_name mismatch sau khi phá file"
        assert any(cm.part_id == part_id and cm.field == "block_name" for cm in review_before.component_mismatches)

        repair_result = repair_insert_components(build_result, review_before.component_mismatches)
        assert repair_result.repaired_count == 1
        assert part_id in repair_result.repaired_part_ids

        review_after = review_dxf(build_result)
        assert review_after.passed, (
            f"sau repair phải pass review, còn mismatch: {review_after.format_report()}"
        )
    print("OK   test_repair_insert_fixes_block_name_mismatch")


def test_repair_insert_fixes_scale_and_rotation_mismatch():
    """xscale/rotation bị sửa sai trong file -> review phát hiện nhiều
    field cùng lúc trên 1 part -> repair chỉ cần xoá/vẽ lại 1 lần."""
    if not _HAS_EZDXF:
        print("SKIP test_repair_insert_fixes_scale_and_rotation_mismatch — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, out_path = _build_beam_component(tmp)

        corrupted = ezdxf.readfile(out_path)
        entity = corrupted.entitydb.get(build_result.component_handle_by_part_id[part_id])
        entity.dxf.xscale = 999.0
        entity.dxf.rotation = 45.0
        corrupted.saveas(out_path)

        review_before = review_dxf(build_result)
        assert not review_before.passed
        fields_broken = {cm.field for cm in review_before.component_mismatches if cm.part_id == part_id}
        assert "xscale" in fields_broken
        assert "rotation_deg" in fields_broken

        repair_result = repair_insert_components(build_result, review_before.component_mismatches)
        # 2 field lỗi trên CÙNG 1 part -> chỉ 1 lần repair (xoá + vẽ lại 1 lần)
        assert repair_result.repaired_count == 1
        assert repair_result.repaired_part_ids == [part_id]

        review_after = review_dxf(build_result)
        assert review_after.passed, f"sau repair phải pass, còn: {review_after.format_report()}"
    print("OK   test_repair_insert_fixes_scale_and_rotation_mismatch")


def test_repair_insert_fixes_missing_attrib():
    """1 ATTRIB (vd LENGTH_MM) bị xoá khỏi entity INSERT trong file -> review
    phát hiện thiếu ATTRIB -> repair vẽ lại INSERT với đủ ATTRIB gốc."""
    if not _HAS_EZDXF:
        print("SKIP test_repair_insert_fixes_missing_attrib — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        build_result, part_id, out_path = _build_beam_component(tmp)

        corrupted = ezdxf.readfile(out_path)
        entity = corrupted.entitydb.get(build_result.component_handle_by_part_id[part_id])
        length_attrib = next(a for a in entity.attribs if a.dxf.tag == "LENGTH_MM")
        entity.attribs.remove(length_attrib)
        corrupted.saveas(out_path)

        review_before = review_dxf(build_result)
        assert not review_before.passed
        assert any(
            cm.part_id == part_id and cm.field == "attrib:LENGTH_MM" and cm.actual is None
            for cm in review_before.component_mismatches
        )

        repair_result = repair_insert_components(build_result, review_before.component_mismatches)
        assert repair_result.repaired_count == 1

        review_after = review_dxf(build_result)
        assert review_after.passed, f"sau repair phải pass, còn: {review_after.format_report()}"
    print("OK   test_repair_insert_fixes_missing_attrib")


def test_repair_insert_multiple_parts_independently():
    """2 part (2 dầm khác nhau) cùng bị lỗi -> mỗi part phải được repair độc
    lập, không cái nào ảnh hưởng cái kia — tương tự
    test_repair_multiple_entities_independently nhưng cho INSERT. Build
    riêng 2 file rồi merge component info vào 1 BuildResult để mô phỏng 2
    part cùng tồn tại (đơn giản hơn dựng 1 SemanticIRDocument nhiều part
    ngay từ đầu, nhưng vẫn đúng bản chất: 2 INSERT độc lập trong cùng 1
    file, đều nguồn từ block frame_beam)."""
    if not _HAS_EZDXF:
        print("SKIP test_repair_insert_multiple_parts_independently — chưa cài ezdxf")
        return
    with tempfile.TemporaryDirectory() as tmp:
        beam1 = _line("b1", 0, 0, 500, 0)
        beam2 = _line("b2", 0, 100, 300, 100)
        doc = _doc(beam1, beam2)
        semantic_doc = SemanticIRDocument(
            primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=2),
            parts=[
                SemanticPart(part_type="thanh_ngang", primitive_ids=["b1"], confidence=1.0),
                SemanticPart(part_type="thanh_ngang", primitive_ids=["b2"], confidence=1.0),
            ],
            constraints=[],
        )
        out_path = os.path.join(tmp, "out.dxf")
        build_result = build_dxf(doc, out_path, semantic_doc=semantic_doc, build_components=True)
        pid1, pid2 = semantic_doc.parts[0].id, semantic_doc.parts[1].id
        assert build_result.component_count == 2

        # phá cả 2 (để part khác nguyên vẹn thì test không có gì để so sánh,
        # nên phá cả 2 nhưng theo 2 KIỂU LỖI KHÁC NHAU để chắc chắn mỗi part
        # được repair đúng theo dữ liệu written_component CỦA RIÊNG NÓ)
        corrupted = ezdxf.readfile(out_path)
        e1 = corrupted.entitydb.get(build_result.component_handle_by_part_id[pid1])
        e2 = corrupted.entitydb.get(build_result.component_handle_by_part_id[pid2])
        e1.dxf.layer = "WRONG_LAYER"
        e2.dxf.rotation = 123.0
        corrupted.saveas(out_path)

        review_before = review_dxf(build_result)
        assert not review_before.passed
        broken_pids = {cm.part_id for cm in review_before.component_mismatches}
        assert broken_pids == {pid1, pid2}

        repair_result = repair_insert_components(build_result, review_before.component_mismatches)
        assert repair_result.repaired_count == 2
        assert set(repair_result.repaired_part_ids) == {pid1, pid2}

        review_after = review_dxf(build_result)
        assert review_after.passed, f"sau repair phải pass, còn: {review_after.format_report()}"
        # xác nhận đúng dữ liệu riêng của TỪNG part được khôi phục (không bị
        # lẫn dữ liệu giữa 2 part) — b1 dài 500 khác b2 dài 300 nên xscale
        # (length) phải khác nhau sau repair
        assert build_result.written_component_by_part_id[pid1]["xscale"] == 500
        assert build_result.written_component_by_part_id[pid2]["xscale"] == 300
    print("OK   test_repair_insert_multiple_parts_independently")


_TESTS = [
    test_missing_ezdxf_raises_clear_import_error,
    test_repair_empty_mismatches_does_nothing,
    test_repair_fixes_geometry_mismatch_on_line,
    test_repair_fixes_layer_mismatch,
    test_repair_multiple_entities_independently,
    test_repair_insert_empty_mismatches_does_nothing,
    test_repair_insert_fixes_block_name_mismatch,
    test_repair_insert_fixes_scale_and_rotation_mismatch,
    test_repair_insert_fixes_missing_attrib,
    test_repair_insert_multiple_parts_independently,
]


def run_all():
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
