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
import pytesseract

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
        "primitive_ir_lib.text_extraction.pytesseract.get_languages",
        return_value=["eng", "vie", "osd"],
    ), patch(
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
        "primitive_ir_lib.text_extraction.pytesseract.get_languages",
        return_value=["eng", "osd"],
    ), patch(
        "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
        return_value=dict(_EMPTY_TESSERACT_DATA),
    ) as mock_image_to_data:
        extract_text_tesseract(image, roi_boxes=[(0, 0, 100, 100)], lang="eng")

    _, kwargs = mock_image_to_data.call_args
    assert kwargs["lang"] == "eng"


def test_missing_requested_language_refuses_before_ocr_acquisition():
    image = np.full((20, 20, 3), 255, dtype=np.uint8)

    with patch(
        "primitive_ir_lib.text_extraction.pytesseract.get_languages",
        return_value=["eng", "osd"],
    ) as mock_get_languages, patch(
        "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
        return_value=dict(_EMPTY_TESSERACT_DATA),
    ) as mock_image_to_data:
        try:
            extract_text_tesseract(image, roi_boxes=[(0, 0, 20, 20)], lang="vie+eng")
        except ValueError as exc:
            assert "vie" in str(exc)
        else:
            raise AssertionError("missing requested language must be refused")

    mock_get_languages.assert_called_once_with()
    mock_image_to_data.assert_not_called()


def test_fully_available_languages_preserve_ocr_output():
    image = np.full((20, 20, 3), 255, dtype=np.uint8)
    data = {
        "text": ["10,00"], "conf": ["90"], "block_num": [1], "par_num": [1],
        "line_num": [1], "left": [2], "top": [3], "width": [10], "height": [5],
    }

    with patch(
        "primitive_ir_lib.text_extraction.pytesseract.get_languages",
        return_value=["eng", "vie", "osd"],
    ), patch(
        "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
        return_value=data,
    ) as mock_image_to_data:
        result = extract_text_tesseract(
            image, roi_boxes=[(0, 0, 20, 20)], lang="vie+eng",
        )

    assert len(result) == 1
    assert result[0].content == "10,00"
    assert result[0].parsed_value == 10.0
    assert result[0].bbox_px == (2, 3, 12, 8)
    assert mock_image_to_data.call_args.kwargs["lang"] == "vie+eng"


def test_excluded_language_does_not_require_installed_data():
    image = np.full((20, 20, 3), 255, dtype=np.uint8)

    with patch(
        "primitive_ir_lib.text_extraction.pytesseract.get_languages",
        return_value=["eng", "osd"],
    ), patch(
        "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
        return_value=dict(_EMPTY_TESSERACT_DATA),
    ) as mock_image_to_data:
        extract_text_tesseract(
            image, roi_boxes=[(0, 0, 20, 20)], lang="eng+!vie",
        )

    assert mock_image_to_data.call_args.kwargs["lang"] == "eng+!vie"


def test_language_discovery_error_propagates_before_acquisition():
    image = np.full((20, 20, 3), 255, dtype=np.uint8)
    discovery_error = RuntimeError("language discovery failed")

    with patch(
        "primitive_ir_lib.text_extraction.pytesseract.get_languages",
        side_effect=discovery_error,
    ), patch(
        "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
        return_value=dict(_EMPTY_TESSERACT_DATA),
    ) as mock_image_to_data:
        try:
            extract_text_tesseract(image, roi_boxes=[(0, 0, 20, 20)], lang="eng")
        except RuntimeError as exc:
            assert exc is discovery_error
        else:
            raise AssertionError("language discovery error must propagate")

    mock_image_to_data.assert_not_called()


def test_ocr_acquisition_error_propagates_unchanged():
    image = np.full((20, 20, 3), 255, dtype=np.uint8)
    acquisition_error = RuntimeError("OCR acquisition failed")

    with patch(
        "primitive_ir_lib.text_extraction.pytesseract.get_languages",
        return_value=["eng", "osd"],
    ), patch(
        "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
        side_effect=acquisition_error,
    ) as mock_image_to_data:
        try:
            extract_text_tesseract(image, roi_boxes=[(0, 0, 20, 20)], lang="eng")
        except RuntimeError as exc:
            assert exc is acquisition_error
        else:
            raise AssertionError("OCR acquisition error must propagate")

    mock_image_to_data.assert_called_once()


def test_language_availability_is_rechecked_for_each_call():
    image = np.full((20, 20, 3), 255, dtype=np.uint8)
    available_by_runtime = [["eng", "osd"], ["eng", "vie", "osd"]]
    queried_runtimes = []

    def discover_languages():
        queried_runtimes.append(pytesseract.pytesseract.tesseract_cmd)
        return available_by_runtime.pop(0)

    with patch(
        "primitive_ir_lib.text_extraction.pytesseract.get_languages",
        side_effect=discover_languages,
    ) as mock_get_languages, patch(
        "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
        return_value=dict(_EMPTY_TESSERACT_DATA),
    ) as mock_image_to_data:
        with patch("pytesseract.pytesseract.tesseract_cmd", "runtime-a"):
            try:
                extract_text_tesseract(
                    image, roi_boxes=[(0, 0, 20, 20)], lang="vie+eng",
                )
            except ValueError as exc:
                assert "vie" in str(exc)
            else:
                raise AssertionError("the first runtime state lacks vie")
        with patch("pytesseract.pytesseract.tesseract_cmd", "runtime-b"):
            extract_text_tesseract(
                image, roi_boxes=[(0, 0, 20, 20)], lang="vie+eng",
            )

    assert mock_get_languages.call_count == 2
    assert mock_image_to_data.call_count == 1
    assert queried_runtimes == ["runtime-a", "runtime-b"]
