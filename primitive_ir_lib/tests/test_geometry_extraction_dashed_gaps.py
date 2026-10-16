"""Regression controls for source-visible dashed lines in Hough extraction.

The raster and metadata are copied byte-for-byte from the local Argon line
adjudication package. The raster SHA256 is
9ae9b1fa4f56abc5b7147899555df99c4a56144856f0e057421b74afe69d9b2b.
"""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from primitive_ir_lib.geometry_extraction import PRESETS, extract_raw_geometry


FIXTURES = Path(__file__).parent / "fixtures"


def _vertical_control(runs: list[tuple[int, int]]) -> np.ndarray:
    image = np.full((300, 300, 3), 255, dtype=np.uint8)
    for start, end in runs:
        cv2.line(image, (150, start), (150, end), (0, 0, 0), 2)
    return image


def _vertical_lines(image: np.ndarray, preset: str):
    return [
        line
        for line in extract_raw_geometry(image, preset=preset).lines
        if abs(line.p2_px[0] - line.p1_px[0]) <= 3
        and abs((line.p1_px[0] + line.p2_px[0]) / 2 - 150) <= 5
    ]


@pytest.mark.parametrize("preset", list(PRESETS))
@pytest.mark.parametrize(
    ("name", "runs", "gaps"),
    [
        ("three_runs", [(20, 89), (94, 163), (168, 237)], [(91, 92), (165, 166)]),
        ("irregular_gaps", [(20, 89), (94, 163), (173, 242)], [(91, 92), (165, 171)]),
        ("image_truncated_run", [(0, 69), (74, 143), (148, 217)], [(71, 72), (145, 146)]),
    ],
)
def test_insufficient_or_irregular_source_runs_never_bridge_white_gaps(
    preset: str,
    name: str,
    runs: list[tuple[int, int]],
    gaps: list[tuple[int, int]],
) -> None:
    image = _vertical_control(runs)
    lines = _vertical_lines(image, preset)

    for gap_start, gap_end in gaps:
        assert not any(
            min(line.p1_px[1], line.p2_px[1]) <= gap_start
            and max(line.p1_px[1], line.p2_px[1]) >= gap_end
            for line in lines
        ), f"{preset} bridged {name} white gap {gap_start}:{gap_end}"

    for run_start, run_end in runs:
        assert any(
            max(0, min(run_end, max(line.p1_px[1], line.p2_px[1]))
                - max(run_start, min(line.p1_px[1], line.p2_px[1]))) >= 30
            for line in lines
        ), f"{preset} lost independently supported {name} segment {run_start}:{run_end}"


@pytest.mark.parametrize("preset", list(PRESETS))
def test_genuine_solid_source_line_remains_continuous(preset: str) -> None:
    image = _vertical_control([(20, 235)])
    lines = _vertical_lines(image, preset)

    assert any(
        min(line.p1_px[1], line.p2_px[1]) <= 25
        and max(line.p1_px[1], line.p2_px[1]) >= 230
        for line in lines
    ), f"{preset} split a genuinely solid source line"


@pytest.mark.parametrize("preset", list(PRESETS))
def test_independently_supported_short_run_survives_gap_splitting(preset: str) -> None:
    runs = [(20, 89), (94, 109), (114, 183)]
    image = _vertical_control(runs)
    lines = _vertical_lines(image, preset)

    for gap_start, gap_end in [(91, 92), (111, 112)]:
        assert not any(
            min(line.p1_px[1], line.p2_px[1]) <= gap_start
            and max(line.p1_px[1], line.p2_px[1]) >= gap_end
            for line in lines
        ), f"{preset} bridged short-run control gap {gap_start}:{gap_end}"

    assert any(
        max(0, min(109, max(line.p1_px[1], line.p2_px[1]))
            - max(94, min(line.p1_px[1], line.p2_px[1]))) >= 10
        for line in lines
    ), f"{preset} discarded independently supported short source run"


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
