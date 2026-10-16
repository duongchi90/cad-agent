"""Regression controls for source-visible dashed lines in Hough extraction.

The raster and metadata are copied byte-for-byte from the local Argon line
adjudication package. The raster SHA256 is
9ae9b1fa4f56abc5b7147899555df99c4a56144856f0e057421b74afe69d9b2b.
"""

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from primitive_ir_lib.geometry_extraction import PRESETS, extract_lines, extract_raw_geometry


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


@pytest.mark.parametrize(
    ("name", "preset", "target_x", "intervals", "sha256"),
    [
        (
            "CASE01_PRIMARY_ASYMMETRIC_WITNESS",
            "default",
            150,
            ((40, 76), (86, 140)),
            "1eed0a6c6172377d15f142460e32b4f3269fd16c8299bd729d515bacc8780219",
        ),
        (
            "F05_NEARBY_TEXT_AND_EXTENSION",
            "real_scan_tuned_v1",
            150,
            ((50, 93), (100, 145)),
            "44761f6f41e382f07909d3f21bc15da693f9b3ac05a6a100c2cd2ba5aaa8aedb",
        ),
        (
            "F05_NEARBY_TEXT_AND_EXTENSION",
            "default",
            150,
            ((50, 93), (100, 145)),
            "44761f6f41e382f07909d3f21bc15da693f9b3ac05a6a100c2cd2ba5aaa8aedb",
        ),
        (
            "F06_DIMENSION_WITNESS_PAIR",
            "real_scan_tuned_v1",
            100,
            ((50, 88), (95, 146)),
            "572a86a7320b859e275279078bea74cf8c0d2c85c101ad75815288df545b984a",
        ),
        (
            "F06_DIMENSION_WITNESS_PAIR",
            "default",
            100,
            ((50, 88), (95, 146)),
            "572a86a7320b859e275279078bea74cf8c0d2c85c101ad75815288df545b984a",
        ),
    ],
)
def test_raw_extraction_keeps_source_fragments_without_joining_their_gap(
    name: str,
    preset: str,
    target_x: int,
    intervals: tuple[tuple[int, int], tuple[int, int]],
    sha256: str,
) -> None:
    image_path = FIXTURES / f"{name}.png"
    image_bytes = image_path.read_bytes()
    assert hashlib.sha256(image_bytes).hexdigest() == sha256
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    # These frozen source spans are raw geometry controls. A fixture's
    # must_recover annotation concerns downstream logical association and
    # cannot authorize raw extraction to bridge unsupported pixels.

    lines = [
        line
        for line in extract_raw_geometry(image, preset=preset).lines
        if abs(line.p2_px[0] - line.p1_px[0]) <= 3
        and abs((line.p1_px[0] + line.p2_px[0]) / 2 - target_x) <= 5
    ]
    for segment_start, segment_end in intervals:
        segment_length = segment_end - segment_start
        assert any(
            max(
                0,
                min(segment_end, max(line.p1_px[1], line.p2_px[1]))
                - max(segment_start, min(line.p1_px[1], line.p2_px[1])),
            )
            >= 0.75 * segment_length
            for line in lines
        ), f"{preset} lost source-supported {name} interval {segment_start}:{segment_end}"

    for (_, previous_end), (next_start, _) in zip(intervals, intervals[1:]):
        assert not any(
            min(line.p1_px[1], line.p2_px[1]) <= previous_end
            and max(line.p1_px[1], line.p2_px[1]) >= next_start
            for line in lines
        ), f"{preset} joined {name} across unsupported gap {previous_end}:{next_start}"


def test_source_gap_split_drops_zero_length_interval_beside_supported_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = np.full((80, 80, 3), 255, dtype=np.uint8)
    image[20, 50] = (0, 0, 0)
    cv2.line(image, (50, 30), (50, 60), (0, 0, 0), 1)
    monkeypatch.setattr(
        cv2,
        "HoughLinesP",
        lambda *args, **kwargs: np.array([[[50, 20, 50, 60]]], dtype=np.int32),
    )

    lines = extract_lines(image)

    assert lines
    assert all(line.length_px() > 0 for line in lines)
    assert any(line.length_px() >= 25 for line in lines)


def test_splitting_dashed_candidate_does_not_renormalize_unrelated_line_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = np.full((140, 220, 3), 255, dtype=np.uint8)
    cv2.line(image, (20, 40), (74, 40), (0, 0, 0), 1)
    cv2.line(image, (80, 40), (134, 40), (0, 0, 0), 1)
    cv2.line(image, (140, 40), (190, 40), (0, 0, 0), 1)
    cv2.line(image, (30, 100), (130, 100), (0, 0, 0), 1)
    monkeypatch.setattr(
        cv2,
        "HoughLinesP",
        lambda *args, **kwargs: np.array(
            [[[20, 40, 190, 40], [30, 100, 130, 100]]], dtype=np.int32
        ),
    )

    lines = extract_lines(image)

    unrelated_solid = next(
        line
        for line in lines
        if line.p1_px == (30.0, 100.0) and line.p2_px == (130.0, 100.0)
    )
    assert unrelated_solid.confidence == 0.794


def test_source_gap_split_with_only_isolated_pixels_returns_no_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = np.full((80, 80, 3), 255, dtype=np.uint8)
    image[20, 50] = (0, 0, 0)
    image[50, 50] = (0, 0, 0)
    monkeypatch.setattr(
        cv2,
        "HoughLinesP",
        lambda *args, **kwargs: np.array([[[50, 20, 50, 50]]], dtype=np.int32),
    )

    assert extract_lines(image) == []


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


@pytest.mark.parametrize("preset", list(PRESETS))
def test_extract_lines_preserves_dashed_gaps_over_gray_shading(preset: str) -> None:
    image = np.full((300, 300, 3), 161, dtype=np.uint8)
    intervals = ((50, 149), (154, 253))
    for start, end in intervals:
        cv2.line(image, (150, start), (150, end), (0, 0, 0), 2)

    lines = _vertical_lines(image, preset)

    assert not any(
        min(line.p1_px[1], line.p2_px[1]) <= 150
        and max(line.p1_px[1], line.p2_px[1]) >= 153
        for line in lines
    ), f"{preset} bridged the unsupported gray-background gap 150:153"
    for start, end in intervals:
        assert any(
            max(0, min(end, max(line.p1_px[1], line.p2_px[1]))
                - max(start, min(line.p1_px[1], line.p2_px[1]))) >= 75
            for line in lines
        ), f"{preset} lost gray-background source run {start}:{end}"


@pytest.mark.parametrize("preset", list(PRESETS))
def test_extract_lines_keeps_black_solid_line_over_gray_background_continuous(
    preset: str,
) -> None:
    image = np.full((300, 300, 3), 161, dtype=np.uint8)
    cv2.line(image, (150, 30), (150, 270), (0, 0, 0), 2)

    lines = _vertical_lines(image, preset)

    assert any(
        min(line.p1_px[1], line.p2_px[1]) <= 35
        and max(line.p1_px[1], line.p2_px[1]) >= 265
        for line in lines
    ), f"{preset} split a continuous black source line over gray background"


@pytest.mark.parametrize("preset", list(PRESETS))
def test_extract_lines_keeps_visible_gray_source_line_on_white_continuous(
    preset: str,
) -> None:
    image = np.full((300, 300, 3), 255, dtype=np.uint8)
    cv2.line(image, (150, 30), (150, 270), (161, 161, 161), 2)

    lines = _vertical_lines(image, preset)

    assert any(
        min(line.p1_px[1], line.p2_px[1]) <= 35
        and max(line.p1_px[1], line.p2_px[1]) >= 265
        for line in lines
    ), f"{preset} split a visible gray source line on white background"


@pytest.mark.parametrize("preset", list(PRESETS))
def test_extract_lines_splits_canny_visible_gray_strokes_over_gray_background(
    preset: str,
) -> None:
    image = np.full((300, 300, 3), 161, dtype=np.uint8)
    intervals = ((50, 149), (154, 253))
    for start, end in intervals:
        cv2.line(image, (150, start), (150, end), (121, 121, 121), 2)

    lines = _vertical_lines(image, preset)

    assert not any(
        min(line.p1_px[1], line.p2_px[1]) <= 150
        and max(line.p1_px[1], line.p2_px[1]) >= 153
        for line in lines
    ), f"{preset} bridged the faint gray-stroke gap 150:153"
    for start, end in intervals:
        assert any(
            max(0, min(end, max(line.p1_px[1], line.p2_px[1]))
                - max(start, min(line.p1_px[1], line.p2_px[1]))) >= 75
            for line in lines
        ), f"{preset} lost Canny-visible gray source run {start}:{end}"
