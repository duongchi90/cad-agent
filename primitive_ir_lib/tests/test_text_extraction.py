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
        "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
        return_value=data,
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
        "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
        return_value=dict(_EMPTY_TESSERACT_DATA),
    ) as mock_image_to_data:
        extract_text_tesseract(image, roi_boxes=[(0, 0, 100, 100)])

    _, kwargs = mock_image_to_data.call_args
    assert kwargs["lang"] == "vie+eng"


def test_extract_text_tesseract_allows_lang_override():
    """Vẫn phải cho phép override lang tường minh khi cần (vd chỉ 'eng' cho
    mã bản vẽ thuần số/chữ không dấu, tiết kiệm thời gian OCR)."""
    image = np.full((100, 100, 3), 255, dtype=np.uint8)

    with patch(
        "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
        return_value=dict(_EMPTY_TESSERACT_DATA),
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
