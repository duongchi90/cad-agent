"""Regression test for the multi-page PDF to Primitive IR runner."""

import json
from pathlib import Path
from unittest.mock import patch

import fitz

from primitive_ir_lib.run_pdf import run_pdf


def test_run_pdf_creates_manifest_and_page_ir(tmp_path: Path):
    pdf_path = tmp_path / "fixture.pdf"
    output_dir = tmp_path / "output"
    document = fitz.open()
    for offset in (0, 10):
        page = document.new_page(width=200, height=100)
        page.draw_line((10, 20 + offset), (190, 20 + offset), color=(0, 0, 0), width=1)
    document.save(str(pdf_path))
    document.close()

    manifest = run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="default")

    assert len(manifest["pages"]) == 2
    saved = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(saved["pages"]) == 2
    for page in saved["pages"]:
        ir_path = output_dir / page["primitive_ir"]
        assert ir_path.is_file()
        payload = json.loads(ir_path.read_text(encoding="utf-8"))
        assert payload["source_document"]["image_width_px"] == 200
        assert page["primitive_count"] == len(payload["primitives"])


def _make_blank_pdf(pdf_path: Path) -> None:
    """Fixture tối thiểu — chỉ cần tồn tại trên đĩa, không cần nội dung, vì
    các test dưới đây kiểm tra nhánh validate xảy ra TRƯỚC khi fitz.open()
    được gọi (xem run_pdf(): is_file() -> dpi -> scale -> auto_calibrate
    checks, tất cả trước dòng `document = fitz.open(...)`)."""
    pdf_path.write_bytes(b"")


def test_run_pdf_requires_scale_or_auto_calibrate(tmp_path: Path):
    pdf_path = tmp_path / "fixture.pdf"
    _make_blank_pdf(pdf_path)
    try:
        run_pdf(pdf_path, tmp_path / "output")
        raise AssertionError("Phải raise ValueError khi không có scale lẫn auto_calibrate")
    except ValueError as exc:
        assert "auto_calibrate" in str(exc)


def test_run_pdf_auto_calibrate_requires_prefix_with_registry(tmp_path: Path):
    pdf_path = tmp_path / "fixture.pdf"
    _make_blank_pdf(pdf_path)
    try:
        run_pdf(
            pdf_path, tmp_path / "output",
            auto_calibrate=True,
            calibration_registry_path=tmp_path / "registry.json",
            calibration_id_prefix=None,
        )
        raise AssertionError("Phải raise ValueError khi có registry nhưng thiếu calibration_id_prefix")
    except ValueError as exc:
        assert "calibration_id_prefix" in str(exc)


def test_run_pdf_forwards_auto_flags_and_per_page_calibration_id(tmp_path: Path):
    """Regression cho phần đã bổ sung: run_pdf() phải forward auto_ocr_roi/
    auto_calibrate/calibration_registry_path xuống run() cho MỖI trang, và
    tự sinh calibration_id riêng theo dạng '<prefix>_pageNN' cho từng trang
    (không dùng chung 1 id — mỗi trang PDF là 1 ảnh/sha256 khác nhau).
    Mock run() để không phụ thuộc vào việc Tesseract có đọc được text render
    từ fitz hay không (rủi ro do font/dpi), chỉ kiểm tra ĐÚNG tham số được
    truyền xuống — phần logic OCR/calibration thật đã có test riêng ở
    primitive_ir_lib/tests/test_run_image.py và được verify thủ công khi
    phát triển tính năng này."""
    pdf_path = tmp_path / "fixture.pdf"
    output_dir = tmp_path / "output"
    document = fitz.open()
    for offset in (0, 10):
        page = document.new_page(width=200, height=100)
        page.draw_line((10, 20 + offset), (190, 20 + offset), color=(0, 0, 0), width=1)
    document.save(str(pdf_path))
    document.close()

    captured_calls = []

    def fake_run(image_path, output_path, scale_mm_per_px=None, preset="real_scan_tuned_v1",
                 ocr_rois=None, tesseract_cmd=None, merge_lines=False, auto_ocr_roi=False,
                 auto_calibrate=False, calibration_registry_path=None, calibration_id=None,
                 view_candidates_output_path=None, view_candidates_dpi=None):
        captured_calls.append(dict(
            auto_ocr_roi=auto_ocr_roi, auto_calibrate=auto_calibrate,
            calibration_registry_path=calibration_registry_path,
            calibration_id=calibration_id,
                view_candidates_output_path=view_candidates_output_path,
                view_candidates_dpi=view_candidates_dpi,
        ))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps({
            "primitives": [{
                "id": "scale", "type": "text", "trace": {"bbox_px": [10, 20, 60, 40]},
                "text_data": {"content": "TL 1:40"},
            }], "cross_validations": [],
            "calibration": {"method": "known_dimension_reference", "pixel_to_unit_scale": 5.0},
        }), encoding="utf-8")
        return str(output_path)

    registry_path = tmp_path / "registry.json"
    with patch("primitive_ir_lib.run_pdf.run", side_effect=fake_run):
        manifest = run_pdf(
            pdf_path, output_dir,
            auto_ocr_roi=True, auto_calibrate=True,
            calibration_registry_path=registry_path,
            calibration_id_prefix="tau190",
        )

    assert len(captured_calls) == 2
    assert [c["calibration_id"] for c in captured_calls] == ["tau190_page01", "tau190_page02"]
    for c in captured_calls:
        assert c["auto_ocr_roi"] is True
        assert c["auto_calibrate"] is True
        assert c["calibration_registry_path"] == registry_path
        assert c["view_candidates_output_path"] is not None
        assert c["view_candidates_dpi"] == 144

    assert manifest["scale_mm_per_px"] == "auto"
    assert [p["scale_mm_per_px"] for p in manifest["pages"]] == [5.0, 5.0]
    assert [p["calibration_method"] for p in manifest["pages"]] == ["known_dimension_reference"] * 2
    assert manifest["pages"][0]["scale_label_candidates"][0]["scale_denominator"] == 40
    assert manifest["pages"][0]["scale_label_candidates"][0]["status"] == "needs_verification"


_TESTS = [
    test_run_pdf_requires_scale_or_auto_calibrate,
    test_run_pdf_auto_calibrate_requires_prefix_with_registry,
    test_run_pdf_forwards_auto_flags_and_per_page_calibration_id,
]

if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        test_run_pdf_creates_manifest_and_page_ir(Path(directory))
    print("OK   test_run_pdf_creates_manifest_and_page_ir")

    passed = 0
    for t in _TESTS:
        with tempfile.TemporaryDirectory() as directory:
            t(Path(directory))
        print(f"OK   {t.__name__}")
        passed += 1
    print(f"\n{passed + 1}/{passed + 1} test PASS")
