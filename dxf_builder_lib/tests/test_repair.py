"""
test_repair.py — test cho `dxf_builder_lib.repair.repair_dxf()`.

`test_missing_ezdxf_raises_clear_import_error` LUÔN chạy được. Các test còn
lại cần `ezdxf` thật (build file thật, phá theo đúng kiểu lỗi thật, repair,
rồi review lại để xác nhận hết lỗi), tự SKIP nếu chưa cài `ezdxf`, cùng
quy ước đã dùng cho `test_builder.py`/`test_reviewer.py`.

Kịch bản test: không mock thủ công `BuildResult` — mỗi test BỎ đầy đủ từ
`build_dxf()` thật (để `written_geometry_by_primitive_id` đúng), rồi gây
lỗi theo cách thật (sửa file DXF bằng ezdxf sau build), chạy `review_dxf()`
để lấy `mismatches`, rồi `repair_dxf()`, rồi `review_dxf()` lần 2 để xác
nhận không còn mismatch. Đây chính là vòng lặp thật `build→review→repair→
review` như trong pipeline.
"""

from __future__ import annotations

import os
import tempfile

from primitive_ir_lib.models import (
    Calibration, CircleGeometry, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace,
)

from dxf_builder_lib.builder import build_dxf
from dxf_builder_lib.repair import repair_dxf
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


_TESTS = [
    test_missing_ezdxf_raises_clear_import_error,
    test_repair_empty_mismatches_does_nothing,
    test_repair_fixes_geometry_mismatch_on_line,
    test_repair_fixes_layer_mismatch,
    test_repair_multiple_entities_independently,
]


def run_all():
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
