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
    Calibration, LineGeometry, Point2D, Primitive, PrimitiveIRDocument,
    SourceDocument, Trace,
)

from dxf_builder_lib.builder import BuildResult, build_dxf
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


def _doc(*prims: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="x.png", page_index=0, image_width_px=100, image_height_px=100),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=list(prims),
    )


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


_TESTS = [
    test_missing_ezdxf_raises_clear_import_error,
    test_review_passes_on_correctly_built_dxf,
    test_review_flags_handle_not_found_after_tamper,
    test_review_flags_geometry_mismatch_after_manual_dxf_edit,
    test_review_flags_layer_mismatch,
]


def run_all():
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
