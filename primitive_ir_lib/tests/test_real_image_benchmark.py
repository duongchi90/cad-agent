"""Optional end-to-end benchmark for the TP-TL-A001/07/26 real scan.

The source image is intentionally not committed.  Set CAD_AGENT_REAL_IMAGE to
its local PNG/JPG path to run this test.  The test exercises real Hough lines,
real Tesseract OCR and the witness-zone merge regression together.
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import pytesseract

from primitive_ir_lib.geometry_extraction import extract_raw_geometry
from primitive_ir_lib.line_merging import merge_collinear_lines
from primitive_ir_lib.text_extraction import extract_text_tesseract

_IMAGE_ENV = "CAD_AGENT_REAL_IMAGE"
_TESSERACT_ENV = "CAD_AGENT_TESSERACT_CMD"


def _configure_tesseract() -> None:
    command = os.environ.get(_TESSERACT_ENV)
    if command:
        pytesseract.pytesseract.tesseract_cmd = command
        return
    default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if default.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(default)


def test_real_scan_2760_1525_boundary_survives_full_merge():
    image_path = os.environ.get(_IMAGE_ENV)
    if not image_path:
        print(f"SKIP: set {_IMAGE_ENV} to run the real-image benchmark")
        return
    if not Path(image_path).is_file():
        raise AssertionError(f"{_IMAGE_ENV} does not point to a file: {image_path}")

    image = cv2.imread(image_path)
    assert image is not None
    assert image.shape[:2] == (900, 1600), image.shape
    _configure_tesseract()

    # OCR is intentionally passed through even though this scan may misread
    # 1525.  The witness boundary must still survive independently of OCR.
    ocr_texts = extract_text_tesseract(
        image, roi_boxes=[(620, 325, 860, 385)], min_confidence=0,
    )
    geometry = extract_raw_geometry(image, preset="real_scan_tuned_v1")
    selected = [
        line for line in geometry.lines
        if abs(line.p2_px[1] - line.p1_px[1]) <= 3
        and 340 <= (line.p1_px[1] + line.p2_px[1]) / 2 <= 370
        and max(line.p1_px[0], line.p2_px[0]) >= 620
        and min(line.p1_px[0], line.p2_px[0]) <= 860
    ]
    merged = merge_collinear_lines(
        selected,
        image_bgr=image,
        blocking_texts=ocr_texts,
        use_tick_mark_detection=False,
    )
    segments = sorted(
        (round(min(line.p1_px[0], line.p2_px[0])),
         round(max(line.p1_px[0], line.p2_px[0])))
        for line in merged
    )
    assert segments == [(524, 777), (776, 917)], segments


if __name__ == "__main__":
    test_real_scan_2760_1525_boundary_survives_full_merge()
    print("real-image benchmark PASS or SKIP")
