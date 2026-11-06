"""Regression tests for OCR language configuration in text_extraction.py.

Bug: extract_text_tesseract() mặc định lang="eng", nên mọi ký tự tiếng Việt
có dấu (vd "VẬT LIỆU", "SỐ LƯỢNG") trong title block bị đọc sai/rỗng khi
gói ngôn ngữ 'vie' đã có sẵn trong môi trường thật. Không nơi nào trong
pipeline (run_image, vision_client, table_extraction, demo_pipeline) truyền
lang khác, nên default sai lan truyền toàn hệ thống.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from primitive_ir_lib.text_extraction import (
    _merge_punctuation_joined_rois,
    classify_semantic_role,
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
