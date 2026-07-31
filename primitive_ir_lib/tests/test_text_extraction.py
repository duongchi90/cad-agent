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

from primitive_ir_lib.text_extraction import extract_text_tesseract

_EMPTY_TESSERACT_DATA = {
    "text": [], "conf": [], "block_num": [], "par_num": [], "line_num": [],
    "left": [], "top": [], "width": [], "height": [],
}


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
