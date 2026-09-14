"""Optional end-to-end benchmark for the TP-TL-A001/07/26 real scan.

The source image is intentionally not committed.  Set CAD_AGENT_REAL_IMAGE to
its local PNG/JPG path to run this test.  The test exercises real Hough lines,
real Tesseract OCR and the witness-zone merge regression together.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import cv2
import pytesseract
import pytest

from primitive_ir_lib.geometry_extraction import extract_raw_geometry
from primitive_ir_lib.line_merging import merge_collinear_lines
from primitive_ir_lib.text_extraction import extract_text_tesseract
from primitive_ir_lib.calibration import Calibration
from primitive_ir_lib.cross_validation import cross_validate

_IMAGE_ENV = "CAD_AGENT_REAL_IMAGE"
_TESSERACT_ENV = "CAD_AGENT_TESSERACT_CMD"
_BVTL_IMAGE_ENV = "CAD_AGENT_BVTL_PAGE1_IMAGE"
_BVTL_PDF_ENV = "CAD_AGENT_BVTL_PAGE1_PDF"
_BVTL_RENDER_SHA256 = "b03477a1f9cd5df4f8ee6125f8faed1bf35586cb4f891c30bf2351929833b9d0"
_BVTL_PDF_SHA256 = "13d822cf828cccc6cd21b19ec3c410f0ea89aef440aeca4c96248e86c08b5b38"
_BVTL_IMAGE_SHAPE = (1685, 2382)
_BVTL_LOGICAL_BBOX = (749, 258, 833, 343)
_BVTL_EXTRACTION_BBOX = (744, 253, 838, 348)

pytestmark = pytest.mark.real_data


def _configure_tesseract() -> None:
    command = os.environ.get(_TESSERACT_ENV)
    if command:
        pytesseract.pytesseract.tesseract_cmd = command
        return
    default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if default.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(default)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _covers_axis_aligned_corridor(
    line,
    orientation: str,
    coordinate: float,
    span_start: float,
    span_end: float,
) -> bool:
    x1, y1 = line.p1_px
    x2, y2 = line.p2_px
    if orientation == "horizontal":
        if abs(y2 - y1) > 4 or abs((y1 + y2) / 2 - coordinate) > 7:
            return False
        return min(x1, x2) <= span_start + 3 and max(x1, x2) >= span_end - 3
    if abs(x2 - x1) > 4 or abs((x1 + x2) / 2 - coordinate) > 7:
        return False
    return min(y1, y2) <= span_start + 3 and max(y1, y2) >= span_end - 3


def _line_intersects_box(line, x0: float, y0: float, x1: float, y1: float) -> bool:
    line_x0 = min(line.p1_px[0], line.p2_px[0])
    line_x1 = max(line.p1_px[0], line.p2_px[0])
    line_y0 = min(line.p1_px[1], line.p2_px[1])
    line_y1 = max(line.p1_px[1], line.p2_px[1])
    return line_x0 <= x1 and line_x1 >= x0 and line_y0 <= y1 and line_y1 >= y0


def test_real_scan_2760_1525_boundary_survives_full_merge():
    image_path = os.environ.get(_IMAGE_ENV)
    if not image_path:
        pytest.skip(f"set {_IMAGE_ENV} to run the real-image benchmark")
    if not Path(image_path).is_file():
        raise AssertionError(f"{_IMAGE_ENV} does not point to a file: {image_path}")

    image = cv2.imread(image_path)
    assert image is not None
    _configure_tesseract()

    if image.shape[:2] == (900, 1600):
        # OCR is intentionally passed through even though this scan may misread
        # 1525.  The witness boundary must still survive independently of OCR.
        ocr_texts = extract_text_tesseract(
            image, roi_boxes=[(620, 325, 860, 385)], min_confidence=0, lang="eng",
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
    elif image.shape[:2] == (1685, 2382):
        # The local high-resolution page scan is the same TP-TL-A001/07/26
        # drawing, with the dimension chain at a different pixel scale.
        ocr_texts = extract_text_tesseract(
            image, roi_boxes=[(650, 610, 1500, 690)], min_confidence=0, lang="eng",
        )
        geometry = extract_raw_geometry(image, preset="real_scan_tuned_v1")
        merged = merge_collinear_lines(
            geometry.lines,
            image_bgr=image,
            blocking_texts=ocr_texts,
            use_tick_mark_detection=True,
        )
        segments = sorted(
            (round(min(line.p1_px[0], line.p2_px[0])),
             round(max(line.p1_px[0], line.p2_px[0])))
            for line in merged
            if abs(line.p2_px[1] - line.p1_px[1]) <= 4
            and 640 <= (line.p1_px[1] + line.p2_px[1]) / 2 <= 680
            and line.length_px() > 10
            and max(line.p1_px[0], line.p2_px[0]) >= 600
            and min(line.p1_px[0], line.p2_px[0]) <= 1500
        )
        assert segments == [(669, 1147), (1147, 1415)], segments
        assert any("2760" in text.content and "1525" in text.content for text in ocr_texts)
    else:
        raise AssertionError(f"unsupported approved private image shape: {image.shape}")

    cross_validate(
        ocr_texts,
        merged,
        Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        merge_collinear=False,
    )


def test_bvtl_page1_source_bound_geometry():
    image_path = os.environ.get(_BVTL_IMAGE_ENV)
    pdf_path = os.environ.get(_BVTL_PDF_ENV)
    if not image_path or not pdf_path:
        pytest.skip(
            f"set both {_BVTL_IMAGE_ENV} and {_BVTL_PDF_ENV} to run the BVTL Page-1 gate"
        )

    image_file = Path(image_path)
    pdf_file = Path(pdf_path)
    assert image_file.is_file(), f"{_BVTL_IMAGE_ENV} does not point to a file: {image_path}"
    assert pdf_file.is_file(), f"{_BVTL_PDF_ENV} does not point to a file: {pdf_path}"
    assert _sha256(image_file) == _BVTL_RENDER_SHA256
    assert _sha256(pdf_file) == _BVTL_PDF_SHA256

    image = cv2.imread(str(image_file), cv2.IMREAD_COLOR)
    assert image is not None
    assert image.shape[:2] == _BVTL_IMAGE_SHAPE

    logical_x0, logical_y0, logical_x1, logical_y1 = _BVTL_LOGICAL_BBOX
    extraction_x0, extraction_y0, extraction_x1, extraction_y1 = _BVTL_EXTRACTION_BBOX
    assert extraction_x0 <= logical_x0 < logical_x1 <= extraction_x1
    assert extraction_y0 <= logical_y0 < logical_y1 <= extraction_y1
    crop = image[extraction_y0:extraction_y1, extraction_x0:extraction_x1]
    geometry = extract_raw_geometry(crop, preset="real_scan_tuned_v1")

    corridors = {
        "top": ("horizontal", logical_y0 - extraction_y0, logical_x0 - extraction_x0, logical_x1 - extraction_x0),
        "bottom": ("horizontal", logical_y1 - extraction_y0, logical_x0 - extraction_x0, logical_x1 - extraction_x0),
        "left": ("vertical", logical_x0 - extraction_x0, logical_y0 - extraction_y0, logical_y1 - extraction_y0),
        "right": ("vertical", logical_x1 - extraction_x0, logical_y0 - extraction_y0, logical_y1 - extraction_y0),
    }
    residual_lines = [
        line
        for line in geometry.lines
        if _line_intersects_box(
            line,
            logical_x0 - extraction_x0,
            logical_y0 - extraction_y0,
            logical_x1 - extraction_x0,
            logical_y1 - extraction_y0,
        )
        and not any(
            _covers_axis_aligned_corridor(line, *spec)
            for spec in corridors.values()
        )
    ]
    assert not residual_lines, [
        (*line.p1_px, *line.p2_px) for line in residual_lines
    ]
    observed = {
        name: any(_covers_axis_aligned_corridor(line, *spec) for line in geometry.lines)
        for name, spec in corridors.items()
    }
    assert not geometry.circles
    assert observed == {name: True for name in corridors}, observed


if __name__ == "__main__":
    test_real_scan_2760_1525_boundary_survives_full_merge()
    print("real-image benchmark PASS or SKIP")
