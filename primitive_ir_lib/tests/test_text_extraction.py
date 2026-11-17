"""Regression tests for OCR language configuration in text_extraction.py.

Bug: extract_text_tesseract() mặc định lang="eng", nên mọi ký tự tiếng Việt
có dấu (vd "VẬT LIỆU", "SỐ LƯỢNG") trong title block bị đọc sai/rỗng khi
gói ngôn ngữ 'vie' đã có sẵn trong môi trường thật. Không nơi nào trong
pipeline (run_image, vision_client, table_extraction, demo_pipeline) truyền
lang khác, nên default sai lan truyền toàn hệ thống.
"""

from __future__ import annotations

from unittest.mock import patch
import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np
import pytest
import pytesseract

from primitive_ir_lib.text_extraction import (
    _merge_punctuation_joined_rois,
    classify_semantic_role,
    detect_text_candidate_rois,
    extract_text_tesseract,
)


def test_metric_thread_callout_remains_note_not_dimension_value():
    role, value = classify_semantic_role("M6x1 - 6H")

    assert role == "general_note"
    assert value is None


def test_thread_callout_classifier_does_not_match_ordinary_words_or_extra_text():
    for text in ("MIN", "PIN", "M6x1 6H extra"):
        role, value = classify_semantic_role(text)
        assert (role, value) == ("unknown", None)


_EMPTY_TESSERACT_DATA = {
    "text": [], "conf": [], "block_num": [], "par_num": [], "line_num": [],
    "left": [], "top": [], "width": [], "height": [],
}


def _baseline_observations(monkeypatch, words=None, title="bbox 2 3 38 22; baseline 0 -2", extra=""):
    words = words or [("KEEP", 95, (2, 3, 20, 12)), ("yp", 10, (22, 3, 38, 22))]
    data = {k: [] for k in _EMPTY_TESSERACT_DATA}
    spans = []
    for text, conf, (x0, y0, x1, y1) in words:
        values = dict(text=text, conf=conf, block_num=1, par_num=1, line_num=1,
                      left=x0, top=y0, width=x1-x0, height=y1-y0)
        for k in data:
            data[k].append(values[k])
        spans.append(f'<span class="ocrx_word" title="bbox {x0} {y0} {x1} {y1}">{text}</span>')
    line = f'<span class="ocr_line" title="{title}">{"".join(spans)}</span>'
    hocr = f'<html><body>{line}{extra.replace("LINE", line)}</body></html>'
    monkeypatch.setattr("primitive_ir_lib.text_extraction._tesseract_data_and_hocr", lambda *a, **k: (data, hocr), raising=False)
    return extract_text_tesseract(np.full((100, 100, 3), 255, dtype=np.uint8), [(10, 20, 80, 80)])


def test_ocr_baseline_uses_unfiltered_line_and_roi_offset_once(monkeypatch):
    result = _baseline_observations(monkeypatch)
    assert len(result) == 1
    assert result[0].content == "KEEP"  # low-confidence descender stays rejected
    assert result[0].confidence == 0.95
    assert result[0].bbox_px == (12, 23, 30, 32)
    assert getattr(result[0], "baseline_y_px", None) == 40.0


@pytest.mark.parametrize("title", [
    "bbox 2 3 38 22", "bbox 2 3 38 22; baseline 0 -2; baseline 0 -2",
    "bbox 2 3 38 22; baseline nan -2", "bbox 2 3 38 22; baseline 0 inf",
    "bbox 2 3 38 22; baseline true -2", "bbox 2 3 38 22; baseline 0.01 -2",
    "bbox 2 3 38 22; baseline 0 -2; textangle 90",
    "bbox 2 3 38 22; baseline 0 -2; textangle nan",
    "bbox -2 3 38 22; baseline 0 -2", "bbox 2 3 138 22; baseline 0 -2",
    "bbox 2 3 38 22; baseline 0 -100", "bbox 2 3 38 22; baseline 0 100",
])
def test_unusable_hocr_keeps_admitted_text_without_baseline(monkeypatch, title):
    result = _baseline_observations(monkeypatch, title=title)
    assert result[0].content == "KEEP"
    assert getattr(result[0], "baseline_y_px", None) is None


def test_duplicate_hocr_correspondence_does_not_choose_a_line(monkeypatch):
    result = _baseline_observations(monkeypatch, extra="LINE")
    assert result[0].content == "KEEP"
    assert getattr(result[0], "baseline_y_px", None) is None


def test_repeated_text_lines_bind_by_complete_word_geometry(monkeypatch):
    data = dict(text=["SAME", "SAME"], conf=[90, 90], block_num=[1, 1], par_num=[1, 1],
                line_num=[1, 2], left=[2, 2], top=[3, 33], width=[18, 18], height=[19, 19])
    hocr = '<html>' + ''.join(
        f'<span class="ocr_line" title="bbox 2 {top} 20 {top+19}; baseline 0 -2">'
        f'<span class="ocrx_word" title="bbox 2 {top} 20 {top+19}">SAME</span></span>'
        for top in (33, 3)  # reverse order: line ordinal must not bind metadata
    ) + '</html>'
    monkeypatch.setattr("primitive_ir_lib.text_extraction._tesseract_data_and_hocr", lambda *a, **k: (data, hocr))
    result = extract_text_tesseract(np.zeros((100, 100, 3), dtype=np.uint8), [(10, 20, 80, 90)])
    assert [r.content for r in result] == ["SAME", "SAME"]
    assert [r.baseline_y_px for r in result] == [40.0, 70.0]


@pytest.mark.parametrize("hocr", ["", "<html>", "<html>&undefined;</html>", "<html/>"])
def test_absent_or_unparseable_hocr_preserves_ocr_text(monkeypatch, hocr):
    from primitive_ir_lib.text_extraction import _hocr_baseline_by_line
    assert _hocr_baseline_by_line(dict(_EMPTY_TESSERACT_DATA), hocr, 100, 100) == {}


def test_configurable_dual_output_reuses_tsv_conversion_and_temp_cleanup(monkeypatch):
    from pytesseract import pytesseract as engine
    from primitive_ir_lib.text_extraction import _tesseract_data_and_hocr

    def recognize(**kwargs):
        assert kwargs["lang"] == "eng"
        assert kwargs["config"] == "-c tessedit_create_tsv=1 --psm 11"
        assert kwargs["extension"] == "tsv hocr"
        base = kwargs["output_filename_base"]
        Path(base + ".tsv").write_bytes(b"conf\ttext\n92.8\tGyp100\n")
        Path(base + ".hocr").write_text("<html/>", encoding="utf-8")
        bases.append(base)

    bases = []
    monkeypatch.setattr(engine, "get_tesseract_version", lambda **k: engine.TESSERACT_MIN_VERSION)
    monkeypatch.setattr(engine, "run_tesseract", recognize)
    data, hocr = _tesseract_data_and_hocr(np.zeros((10, 10, 3), dtype=np.uint8), "eng", 11)
    assert data == {"text": ["Gyp100"], "conf": [92]}
    assert hocr == "<html/>"
    assert not list(Path(bases[0]).parent.glob(Path(bases[0]).name + "*"))


def test_dual_output_preserves_tesseract_error_and_cleans_temp(monkeypatch):
    from pytesseract import pytesseract as engine
    from primitive_ir_lib.text_extraction import _tesseract_data_and_hocr

    bases = []
    def fail(**kwargs):
        bases.append(kwargs["output_filename_base"])
        raise engine.TesseractError(7, "recognition failed")
    monkeypatch.setattr(engine, "get_tesseract_version", lambda **k: engine.TESSERACT_MIN_VERSION)
    monkeypatch.setattr(engine, "run_tesseract", fail)
    with pytest.raises(engine.TesseractError, match="recognition failed"):
        _tesseract_data_and_hocr(np.zeros((10, 10, 3), dtype=np.uint8), "eng", 6)
    assert not list(Path(bases[0]).parent.glob(Path(bases[0]).name + "*"))


@pytest.mark.parametrize("hocr_bytes", [None, b"\xff"])
def test_missing_or_undecodable_optional_hocr_retains_tsv(monkeypatch, hocr_bytes):
    from pytesseract import pytesseract as engine
    from primitive_ir_lib.text_extraction import _tesseract_data_and_hocr

    def recognize(**kwargs):
        base = kwargs["output_filename_base"]
        Path(base + ".tsv").write_bytes(b"conf\ttext\n92\tGyp100\n")
        if hocr_bytes is not None:
            Path(base + ".hocr").write_bytes(hocr_bytes)
    monkeypatch.setattr(engine, "get_tesseract_version", lambda **k: engine.TESSERACT_MIN_VERSION)
    monkeypatch.setattr(engine, "run_tesseract", recognize)
    data, hocr = _tesseract_data_and_hocr(np.zeros((10, 10, 3), dtype=np.uint8), "eng", 6)
    assert data == {"conf": [92], "text": ["Gyp100"]}
    assert hocr == ""


def test_extract_text_tesseract_keeps_split_thread_callout_as_note():
    image = np.full((30, 100, 3), 255, dtype=np.uint8)
    data = {
        "text": ["M6x1", "-", "6H"],
        "conf": ["90", "90", "90"],
        "block_num": [1, 1, 1],
        "par_num": [1, 1, 1],
        "line_num": [1, 1, 1],
        "left": [0, 34, 47],
        "top": [0, 0, 0],
        "width": [32, 9, 16],
        "height": [12, 12, 12],
    }

    with patch(
        "primitive_ir_lib.text_extraction._tesseract_data_and_hocr",
        return_value=(data, ""),
    ):
        result = extract_text_tesseract(image, roi_boxes=[(0, 0, 100, 30)])

    assert len(result) == 1
    assert result[0].content == "M6x1 - 6H"
    assert result[0].semantic_role == "general_note"
    assert result[0].parsed_value is None


def test_extract_text_tesseract_defaults_to_vietnamese_and_english():
    """Default lang phải là 'vie+eng', không phải 'eng' đơn thuần, vì title
    block bản vẽ thật luôn có nhãn tiếng Việt có dấu."""
    image = np.full((100, 100, 3), 255, dtype=np.uint8)

    with patch(
        "primitive_ir_lib.text_extraction._tesseract_data_and_hocr",
        return_value=(dict(_EMPTY_TESSERACT_DATA), ""),
    ) as mock_image_to_data:
        extract_text_tesseract(image, roi_boxes=[(0, 0, 100, 100)])

    _, kwargs = mock_image_to_data.call_args
    assert kwargs["lang"] == "vie+eng"


def test_extract_text_tesseract_allows_lang_override():
    """Vẫn phải cho phép override lang tường minh khi cần (vd chỉ 'eng' cho
    mã bản vẽ thuần số/chữ không dấu, tiết kiệm thời gian OCR)."""
    image = np.full((100, 100, 3), 255, dtype=np.uint8)

    with patch(
        "primitive_ir_lib.text_extraction._tesseract_data_and_hocr",
        return_value=(dict(_EMPTY_TESSERACT_DATA), ""),
    ) as mock_image_to_data:
        extract_text_tesseract(image, roi_boxes=[(0, 0, 100, 100)], lang="eng")

    _, kwargs = mock_image_to_data.call_args
    assert kwargs["lang"] == "eng"


def test_roi_merge_uses_short_visible_hyphen_as_join_witness():
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    image[45:48, 31:37, :] = 0

    merged = _merge_punctuation_joined_rois(
        image, [(10, 30, 30, 60), (38, 30, 58, 60)]
    )

    assert merged == [(6, 26, 62, 64)]


def test_roi_merge_preserves_boxes_when_gap_is_blank():
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    boxes = [(10, 30, 30, 60), (38, 30, 58, 60)]

    merged = _merge_punctuation_joined_rois(image, boxes)

    assert merged == boxes


def test_roi_merge_rejects_thin_horizontal_line_as_text_bridge():
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    image[44, 31:45, :] = 0
    boxes = [(10, 30, 30, 60), (48, 30, 68, 60)]

    merged = _merge_punctuation_joined_rois(image, boxes)

    assert merged == boxes


def test_roi_merge_preserves_boxes_when_ink_is_on_a_different_line():
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    image[45:48, 31:37, :] = 0
    boxes = [(10, 30, 30, 60), (38, 65, 58, 95)]

    merged = _merge_punctuation_joined_rois(image, boxes)

    assert merged == boxes


def test_roi_context_padding_scales_with_text_height():
    image = np.full((120, 160, 3), 255, dtype=np.uint8)
    image[47:53, 52:64, :] = 0

    merged = _merge_punctuation_joined_rois(
        image, [(10, 20, 50, 80), (80, 20, 120, 80)]
    )

    assert merged == [(2, 12, 128, 88)]


def test_detector_keeps_dimension_labels_separate_across_long_drafting_line():
    image = np.full((100, 160, 3), 255, dtype=np.uint8)
    for text, position in (("40", (10, 50)), ("60", (64, 50))):
        cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (0, 0, 0), 2)
    cv2.line(image, (0, 54), (150, 54), (0, 0, 0), 2)

    boxes = detect_text_candidate_rois(image)

    assert len(boxes) == 2
    assert all(not (box[0] < 45 and box[2] > 59) for box in boxes)


def test_detector_keeps_table_columns_separate_across_thick_rule():
    image = np.full((100, 150, 3), 255, dtype=np.uint8)
    for text, position in (("12", (20, 43)), ("34", (65, 43)),
                           ("56", (20, 65)), ("78", (65, 65))):
        cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 0, 0), 1, cv2.LINE_8)
    image[47:50, :] = 0

    boxes = detect_text_candidate_rois(image)

    assert len(boxes) == 2
    assert all(not (box[0] < 44 and box[2] > 60) for box in boxes)


@pytest.mark.real_data
def test_fastening_bar_thread_note_survives_pdf_conflict_exclusion(tmp_path):
    source = os.environ.get("CAD_AGENT_FASTENING_BAR_PDF")
    if not source:
        pytest.skip("set CAD_AGENT_FASTENING_BAR_PDF to the approved private source")
    pdf = Path(source)
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == (
        "bf374d514e47f25bf82b9227145e9c057ef398cb76226b2fd4be662b0596b1cd"
    )
    from primitive_ir_lib.run_pdf import run_pdf

    with patch.object(
        pytesseract.pytesseract, "tesseract_cmd",
        os.environ.get("CAD_AGENT_TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    ):
        manifest = run_pdf(pdf, tmp_path / "output", dpi=144,
                           auto_ocr_roi=True, auto_calibrate=True)
    assert manifest["pages"][0]["rendered_png_sha256"] == (
        "e4fc9c6478a66962ae9756c0c2e860e52f0ac87d9195fec305b48c592e531d26"
    )
    document = json.loads((tmp_path / "output/primitive_ir/page_01.json").read_text(encoding="utf-8"))
    notes = [p for p in document["primitives"] if p.get("text_data", {}).get("content") == "M6x1 - 6H"]
    assert len(notes) == 1
    note = notes[0]
    assert note["text_data"]["semantic_role"] == "general_note"
    assert note["text_data"]["parsed_value"] is None
    # Independent source text bbox at 144 DPI: (433.08, 867.43, 557.51, 894.43).
    x0, y0, x1, y1 = note["trace"]["bbox_px"]
    assert 431 <= x0 < x1 <= 560 and 865 <= y0 < y1 <= 897
    assert note["id"] not in json.dumps(document["cross_validations"])
    assert document["calibration"]["status"] == "needs_verification"
