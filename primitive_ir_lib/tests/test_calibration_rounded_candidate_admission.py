from __future__ import annotations

import json
from unittest.mock import patch

import cv2
import numpy as np

from primitive_ir_lib.calibration import auto_estimate_calibration
from primitive_ir_lib.geometry_extraction import RawGeometry, RawLine
from primitive_ir_lib.run_image import run
from primitive_ir_lib.text_extraction import RawText, classify_semantic_role


def _pair(value: str, center_x: float, line_length: float, suffix: str, y: float):
    role, parsed_value = classify_semantic_role(value)
    text = RawText(
        id=f"text-{suffix}",
        content=value,
        bbox_px=(center_x - 5, y - 15, center_x + 5, y - 5),
        rotation_deg=0.0,
        confidence=1.0,
        source="text_tesseract",
        parsed_value=parsed_value,
        semantic_role=role,
    )
    line = RawLine(
        id=f"line-{suffix}",
        p1_px=(center_x - line_length / 2, y),
        p2_px=(center_x + line_length / 2, y),
        confidence=1.0,
        bbox_px=(center_x - line_length / 2, y, center_x + line_length / 2, y),
    )
    return text, line


def _estimate(pairs, *, require_consensus: bool = False):
    return auto_estimate_calibration(
        [text for text, _line in pairs],
        [line for _text, line in pairs],
        image_height_px=120,
        require_consensus=require_consensus,
    )


def test_positive_reference_rounded_to_zero_does_not_hide_later_valid_candidate():
    tiny = _pair("00.000001", 70, 100, "tiny", 32)
    valid = _pair("100", 270, 100, "valid", 72)

    assert tiny[0].parsed_value == 0.000001
    assert tiny[0].parsed_value / tiny[1].length_px() > 0
    calibration = _estimate([tiny, valid])

    assert calibration is not None
    assert calibration.pixel_to_unit_scale == 1.0
    assert calibration.status == "needs_verification"


def test_only_positive_reference_rounded_to_zero_abstains():
    tiny = _pair("00.000001", 70, 100, "tiny", 32)

    assert _estimate([tiny]) is None


def test_rounded_zero_candidate_does_not_break_consensus_fallback():
    tiny = _pair("00.000001", 70, 100, "tiny", 32)
    valid = _pair("100", 270, 100, "valid", 72)

    calibration = _estimate([tiny, valid], require_consensus=True)

    assert calibration is not None
    assert calibration.pixel_to_unit_scale == 1.0
    assert calibration.status == "needs_verification"
    assert "Chỉ tìm được 1 ứng viên" in (calibration.reference_note or "")


def test_valid_first_and_ordinary_positive_estimate_remain_unchanged():
    tiny = _pair("00.000001", 70, 100, "tiny", 32)
    valid = _pair("100", 270, 100, "valid", 72)

    for calibration in (_estimate([valid, tiny]), _estimate([valid])):
        assert calibration is not None
        assert calibration.pixel_to_unit_scale == 1.0
        assert calibration.status == "needs_verification"


def test_run_image_skips_rounded_zero_candidate_before_registry_admission(tmp_path):
    image_path = tmp_path / "synthetic.png"
    output_path = tmp_path / "primitive_ir.json"
    registry_path = tmp_path / "calibration_registry.json"
    assert cv2.imwrite(str(image_path), np.full((120, 400, 3), 255, dtype=np.uint8))

    tiny_text, tiny_line = _pair("00.000001", 70, 100, "tiny", 32)
    valid_text, valid_line = _pair("100", 270, 100, "valid", 72)
    ocr_data = {
        "text": [tiny_text.content, valid_text.content],
        "conf": ["99", "99"],
        "block_num": [1, 1],
        "par_num": [1, 1],
        "line_num": [1, 2],
        "left": [65, 265],
        "top": [17, 57],
        "width": [10, 10],
        "height": [10, 10],
    }

    with (
        patch(
            "primitive_ir_lib.run_image.extract_raw_geometry",
            return_value=RawGeometry(lines=[tiny_line, valid_line], circles=[]),
        ),
        patch(
            "primitive_ir_lib.text_extraction.pytesseract.get_languages",
            return_value=["vie", "eng"],
        ) as mock_get_languages,
        patch(
            "primitive_ir_lib.text_extraction.pytesseract.image_to_data",
            return_value=ocr_data,
        ) as mock_image_to_data,
    ):
        run(
            image_path=str(image_path),
            output_path=str(output_path),
            auto_calibrate=True,
            calibration_registry_path=registry_path,
            calibration_id="rounded-zero",
            ocr_rois=[(0, 0, 400, 120)],
        )

    mock_get_languages.assert_called_once_with()
    mock_image_to_data.assert_called_once()
    assert mock_image_to_data.call_args.kwargs["lang"] == "vie+eng"

    primitive = json.loads(output_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert primitive["calibration"]["pixel_to_unit_scale"] == 1.0
    assert primitive["calibration"]["status"] == "needs_verification"
    assert registry["records"][0]["scale_mm_per_px"] == 1.0
    assert registry["records"][0]["status"] == "needs_verification"
