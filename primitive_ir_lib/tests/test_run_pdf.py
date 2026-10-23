"""Regression test for the multi-page PDF to Primitive IR runner."""

import json
import hashlib
import math
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
import cv2
import numpy as np

from primitive_ir_lib.run_pdf import run_pdf
from primitive_ir_lib.text_extraction import RawText


def test_run_pdf_emits_vector_text_and_binds_pdf_to_rendered_page(tmp_path: Path):
    pdf_path = tmp_path / "vector-text.pdf"
    output_dir = tmp_path / "output"
    document = fitz.open()
    page = document.new_page(width=240, height=120)
    page.insert_text((50, 60), "R7,50", fontsize=12)
    document.save(pdf_path)
    document.close()

    with patch("primitive_ir_lib.run_image.extract_text_tesseract", return_value=[]):
        manifest = run_pdf(
            pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="default",
            auto_ocr_roi=True,
        )

    payload = json.loads((output_dir / manifest["pages"][0]["primitive_ir"]).read_text())
    assert manifest["status"] == "complete"
    texts = [p for p in payload["primitives"] if p["type"] == "text"]
    assert [(p["text_data"]["content"], p["source"]) for p in texts] == [
        ("R7,50", "text_pdfvector")
    ]
    assert texts[0]["trace"]["extraction_tool"] == "pymupdf"

    rendered_path = output_dir / manifest["pages"][0]["rendered_png"]
    assert payload["source_document"]["sha256"] == hashlib.sha256(
        rendered_path.read_bytes()
    ).hexdigest()
    assert manifest["source_pdf_sha256"] == hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    page_record = manifest["pages"][0]
    assert page_record["page_index"] == 0
    assert page_record["rendered_png_sha256"] == payload["source_document"]["sha256"]
    assert page_record["render_scale_px_per_point"] == 1.0
    assert page_record["page_rotation_matrix"] == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    source_doc = fitz.open(pdf_path)
    span = next(
        span
        for block in source_doc[0].get_text("dict")["blocks"]
        if "lines" in block
        for line in block["lines"]
        for span in line["spans"]
        if span["text"] == "R7,50"
    )
    x0, y0, x1, y1 = span["bbox"]
    assert texts[0]["trace"]["bbox_px"] == [
        math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1)
    ]
    source_doc.close()


def test_run_pdf_preserves_text_rotation_from_line_direction(tmp_path: Path):
    pdf_path = tmp_path / "independently-rotated-text.pdf"
    output_dir = tmp_path / "output"
    document = fitz.open()
    page = document.new_page(width=240, height=120)
    origin = fitz.Point(50, 60)
    page.insert_text(origin, "ROTATED", fontsize=12, morph=(origin, fitz.Matrix(45)))
    document.save(pdf_path)
    document.close()

    with patch("primitive_ir_lib.run_image.extract_text_tesseract", return_value=[]):
        manifest = run_pdf(
            pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="default",
            auto_ocr_roi=True,
        )

    payload = json.loads((output_dir / manifest["pages"][0]["primitive_ir"]).read_text())
    text = next(p for p in payload["primitives"] if p["type"] == "text")
    assert text["text_data"]["rotation_deg"] == pytest.approx(45.0, abs=0.5)


def test_run_pdf_marks_manifest_failed_when_same_span_rotation_conflicts(
    tmp_path: Path, monkeypatch
):
    pdf_path = tmp_path / "rotated-text.pdf"
    output_dir = tmp_path / "output"
    document = fitz.open()
    page = document.new_page(width=240, height=120)
    origin = fitz.Point(50, 60)
    page.insert_text(origin, "ROTATED", fontsize=12, morph=(origin, fitz.Matrix(5)))
    document.save(pdf_path)
    document.close()
    (output_dir / "primitive_ir").mkdir(parents=True)
    (output_dir / "primitive_ir" / "page_01.json").write_text(
        '{"primitives": [{"id": "old-success"}]}', encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps({"status": "complete", "pages": [{"page_index": 0}]}),
        encoding="utf-8",
    )

    vector = RawText("pdf-1", "ROTATED", (10, 10, 80, 30), 5.0, 1.0, "text_pdfvector")
    ocr = RawText("ocr-1", "ROTATED", (10, 10, 80, 30), 0.0, 0.9, "text_tesseract")
    monkeypatch.setattr(
        "primitive_ir_lib.run_pdf._page_vector_texts",
        lambda *args, **kwargs: ([vector], "extracted", 0),
    )
    monkeypatch.setattr(
        "primitive_ir_lib.run_image.extract_text_tesseract", lambda *args, **kwargs: [ocr]
    )

    with pytest.raises(ValueError, match="rotation"):
        run_pdf(
            pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="default",
            auto_ocr_roi=True,
        )

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["pages"] == []
    assert manifest["failed_page_index"] == 0
    assert manifest["error"]["type"] == "ValueError"
    # The old generated page file is retained for diagnostics, but the current
    # manifest explicitly invalidates it as a result of this failed run.
    assert json.loads(
        (output_dir / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )["primitives"][0]["id"] == "old-success"


def test_run_pdf_geometry_only_mode_does_not_emit_embedded_text(tmp_path: Path):
    pdf_path = tmp_path / "geometry-only.pdf"
    output_dir = tmp_path / "output"
    document = fitz.open()
    page = document.new_page(width=240, height=120)
    page.insert_text((50, 60), "R7,50", fontsize=12)
    document.save(pdf_path)
    document.close()

    with patch("primitive_ir_lib.run_image.extract_text_tesseract", return_value=[]):
        manifest = run_pdf(
            pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="default",
            auto_ocr_roi=False,
        )

    payload = json.loads((output_dir / manifest["pages"][0]["primitive_ir"]).read_text())
    assert not [primitive for primitive in payload["primitives"] if primitive["type"] == "text"]
    assert manifest["pages"][0]["pdf_vector_text_status"] == "disabled"


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_run_pdf_vector_text_bbox_matches_rendered_text_after_rotation_and_crop(
    tmp_path: Path, rotation: int
):
    pdf_path = tmp_path / f"rotated-cropped-{rotation}.pdf"
    output_dir = tmp_path / "output"
    document = fitz.open()
    page = document.new_page(width=220, height=140)
    page.insert_text((70, 70), "R7,50", fontsize=14)
    page.set_cropbox(fitz.Rect(20, 15, 205, 125))
    page.set_rotation(rotation)
    document.save(pdf_path)
    document.close()

    with patch("primitive_ir_lib.run_image.extract_text_tesseract", return_value=[]):
        manifest = run_pdf(
            pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="default",
            auto_ocr_roi=True,
        )

    page_record = manifest["pages"][0]
    payload = json.loads((output_dir / page_record["primitive_ir"]).read_text())
    text = next(p for p in payload["primitives"] if p["type"] == "text")
    rendered = cv2.imread(str(output_dir / page_record["rendered_png"]))
    ys, xs = np.where(np.any(rendered < 200, axis=2))
    ink_bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    x0, y0, x1, y1 = text["trace"]["bbox_px"]
    assert x0 <= ink_bbox[0] + 2
    assert y0 <= ink_bbox[1] + 2
    assert x1 >= ink_bbox[2] - 2
    assert y1 >= ink_bbox[3] - 2
    assert page_record["page_rotation_matrix"] != [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


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
        assert payload["source_document"]["page_index"] == page["page_index"]
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


@pytest.mark.parametrize(
    ("scale", "label"),
    [(float("nan"), "NaN"), (float("inf"), "+Infinity"), (True, "Boolean True")],
)
def test_run_pdf_rejects_invalid_manual_scale_before_render_or_output_staging(
    tmp_path: Path, scale: float | bool, label: str
) -> None:
    pdf_path = tmp_path / "fixture.pdf"
    output_dir = tmp_path / "output"
    document = fitz.open()
    page = document.new_page(width=80, height=60)
    page.draw_line((10, 20), (70, 20))
    document.save(pdf_path)
    document.close()

    extraction_calls: list[Path] = []

    def fake_run(*, image_path: str, output_path: str, view_candidates_output_path: str, **kwargs: object) -> str:
        extraction_calls.append(Path(image_path))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            json.dumps({
                "primitives": [],
                "cross_validations": [],
                "calibration": {"method": "manual_override", "pixel_to_unit_scale": scale},
            }),
            encoding="utf-8",
        )
        Path(view_candidates_output_path).write_text("[]", encoding="utf-8")
        return output_path

    caught: ValueError | None = None
    with patch("primitive_ir_lib.run_pdf.run", side_effect=fake_run), patch(
        "primitive_ir_lib.run_pdf.fitz.open", wraps=fitz.open
    ) as open_document:
        try:
            run_pdf(pdf_path, output_dir, scale_mm_per_px=scale, dpi=72, preset="default")
        except ValueError as exc:
            caught = exc

    assert caught is not None, (
        f"{label} manual scale was accepted; fitz.open calls={open_document.call_count}, "
        f"extraction calls={len(extraction_calls)}, staged paths="
        f"{sorted(str(path.relative_to(output_dir)) for path in output_dir.rglob('*')) if output_dir.exists() else []}"
    )
    assert open_document.call_count == 0
    assert extraction_calls == []
    assert not output_dir.exists()


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
                 view_candidates_output_path=None, view_candidates_dpi=None,
                 calibration_status="verified", calibration_source_sha256=None,
                 pdf_vector_texts=None, source_page_index=0):
        captured_calls.append(dict(
            auto_ocr_roi=auto_ocr_roi, auto_calibrate=auto_calibrate,
            calibration_registry_path=calibration_registry_path,
            calibration_id=calibration_id,
                view_candidates_output_path=view_candidates_output_path,
                view_candidates_dpi=view_candidates_dpi,
            pdf_vector_texts=pdf_vector_texts,
            source_page_index=source_page_index,
        ))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps({
            "primitives": [{
                "id": "scale", "type": "text", "trace": {"bbox_px": [10, 20, 60, 40]},
                "text_data": {"content": "TL 1:40"},
            }], "cross_validations": [],
            "calibration": {"method": "known_dimension_reference", "pixel_to_unit_scale": 5.0},
        }), encoding="utf-8")
        Path(view_candidates_output_path).write_text(json.dumps([{
            "source_text_id": "scale", "bbox_px": [10, 20, 60, 40],
            "region_bbox_px": [0, 0, 100, 100], "scale_denominator": 40,
            "pixel_to_unit_scale": 7.0555555556, "status": "needs_verification",
        }]), encoding="utf-8")
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
    assert [c["source_page_index"] for c in captured_calls] == [0, 1]
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
    assert "region_bbox_px" in manifest["pages"][0]["scale_label_candidates"][0]


def test_run_pdf_materializes_review_only_child_ir_for_evidenced_view(tmp_path: Path):
    pdf_path = tmp_path / "fixture.pdf"
    output_dir = tmp_path / "output"
    document = fitz.open()
    page = document.new_page(width=200, height=100)
    page.draw_line((20, 20), (180, 20), color=(0, 0, 0), width=1)
    document.save(str(pdf_path))
    document.close()

    def fake_run(image_path, output_path, scale_mm_per_px=None, preset="real_scan_tuned_v1",
                 ocr_rois=None, tesseract_cmd=None, merge_lines=False, auto_ocr_roi=False,
                 auto_calibrate=False, calibration_registry_path=None, calibration_id=None,
                 view_candidates_output_path=None, view_candidates_dpi=None,
                 calibration_status="verified", calibration_source_sha256=None,
                 pdf_vector_texts=None, source_page_index=0):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps({
            "primitives": [], "cross_validations": [],
            "calibration": {
                "method": "manual_override",
                "pixel_to_unit_scale": scale_mm_per_px,
                "status": calibration_status,
                "source_sha256": calibration_source_sha256,
            },
        }), encoding="utf-8")
        if view_candidates_output_path is not None:
            candidate = {
                "source_text_id": "scale", "bbox_px": [70, 10, 100, 20],
                "region_bbox_px": [20, 10, 180, 40], "scale_denominator": 10,
                "pixel_to_unit_scale": 1.7638888889, "status": "needs_verification",
                "dimension_evidence": {
                    "text_primitive_id": "dim", "geometry_primitive_id": "line",
                    "text_value": 100.0, "geometry_measured_length": 100.0,
                    "delta_percent": 0.0,
                },
            }
            overlap = {
                **candidate,
                "source_text_id": "scale-overlap",
                "bbox_px": [75, 12, 105, 22],
            }
            Path(view_candidates_output_path).write_text(
                json.dumps([candidate, overlap]),
                encoding="utf-8",
            )
        return str(output_path)

    with patch("primitive_ir_lib.run_pdf.run", side_effect=fake_run):
        manifest = run_pdf(
            pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72,
            auto_ocr_roi=True,
        )

    candidate = manifest["pages"][0]["scale_label_candidates"][0]
    child = candidate["child_ir"]
    child_path = output_dir / child
    assert child_path.is_file()
    child_payload = json.loads(child_path.read_text(encoding="utf-8"))
    assert child_payload["calibration"]["pixel_to_unit_scale"] == pytest.approx(1.7638888889)
    assert child_payload["calibration"]["status"] == "needs_verification"
    assert child_payload["calibration"]["source_sha256"] == candidate["child_image_sha256"]
    assert candidate["status"] == "needs_verification"
    assert candidate["child_state"] == "needs_verification"
    assert candidate["child_ir_sha256"]
    assert candidate["child_image_sha256"]
    assert manifest["pages"][0]["scale_label_candidates"][1]["child_state"] == "skipped_overlap"
    sidecar = json.loads(
        (output_dir / "primitive_ir" / "page_01.view_candidates.json").read_text(
            encoding="utf-8"
        )
    )
    assert sidecar == manifest["pages"][0]["scale_label_candidates"]


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
