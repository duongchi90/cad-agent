"""Regression controls for source-visible dashed lines in Hough extraction.

The raster and metadata are copied byte-for-byte from the local Argon line
adjudication package. The raster SHA256 is
9ae9b1fa4f56abc5b7147899555df99c4a56144856f0e057421b74afe69d9b2b.
"""

import json
from pathlib import Path

import cv2

from primitive_ir_lib.geometry_extraction import PRESETS, extract_raw_geometry


FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_lines_preserves_visible_gaps_in_dashed_control() -> None:
    image = cv2.imread(str(FIXTURES / "C04_DASHED_HIDDEN_LINE.png"))
    metadata = json.loads((FIXTURES / "C04_DASHED_HIDDEN_LINE.json").read_text(encoding="utf-8"))
    ground_truth = metadata["ground_truth_geometry"]
    x_center = ground_truth["segments"][0]["x1"]
    endpoint_tolerance = 3

    assert image is not None

    for preset in PRESETS:
        lines = extract_raw_geometry(image, preset=preset).lines
        vertical_lines = [
            line
            for line in lines
            if abs(line.p2_px[0] - line.p1_px[0]) <= endpoint_tolerance
            and abs((line.p1_px[0] + line.p2_px[0]) / 2 - x_center) <= endpoint_tolerance
        ]

        for gap in ground_truth["forbidden_gap_intervals"]:
            assert not any(
                min(line.p1_px[1], line.p2_px[1]) <= gap["gap_start"]
                and max(line.p1_px[1], line.p2_px[1]) >= gap["gap_end"]
                for line in vertical_lines
            ), f"{preset} bridged dashed gap {gap}"

        for segment in ground_truth["segments"]:
            segment_low = min(segment["y1"], segment["y2"])
            segment_high = max(segment["y1"], segment["y2"])
            assert any(
                max(segment_low, min(line.p1_px[1], line.p2_px[1]))
                <= min(segment_high, max(line.p1_px[1], line.p2_px[1]))
                and min(
                    segment_high - segment_low,
                    max(line.p1_px[1], line.p2_px[1]) - min(line.p1_px[1], line.p2_px[1]),
                )
                >= 10
                for line in vertical_lines
            ), f"{preset} lost visible dashed segment {segment}"
