"""Hash-bound CASE01 regression for dimension-arrow endpoint detection."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from primitive_ir_lib.geometry_extraction import (
    _extend_line_endpoints_along_ink,
    extract_lines,
)


_IMAGE_ENV = "CAD_AGENT_CASE01_LINE_IMAGE"
_RENDER_SHA256 = "5732b6014ec1c1d3b05e14c598b43ebec84a4d6198951264215a69fb7b0a0bc8"
_UPPER_WITNESS = (153, 198, 168, 219)
_LOWER_WITNESS = (153, 369, 168, 390)
_LINE_CORRIDOR = (157, 219, 164, 369)
_FTC11_IMAGE_ENV = "CAD_AGENT_FTC11_IMAGE"
_FTC11_RENDER_SHA256 = "675f1a991dca7a133f0923bef6aa431f68e719f29780946f358904ace4a2ca00"
_FTC11_AXIS_START = (622.8, 467.88)
_FTC11_AXIS_END = (1120.56, 180.6)
_FTC11_GAP_PROJECTION = (191.174, 383.539)


def _intersects(line, rect: tuple[int, int, int, int]) -> bool:
    x0, y0, x1, y1 = rect
    lx0, ly0 = min(line.p1_px[0], line.p2_px[0]), min(line.p1_px[1], line.p2_px[1])
    lx1, ly1 = max(line.p1_px[0], line.p2_px[0]), max(line.p1_px[1], line.p2_px[1])
    return lx1 >= x0 and lx0 < x1 and ly1 >= y0 and ly0 < y1


@pytest.mark.real_data
def test_case01_dimension_line_reaches_both_frozen_arrow_witnesses() -> None:
    image_value = os.environ.get(_IMAGE_ENV)
    if not image_value:
        pytest.skip(f"set {_IMAGE_ENV} to run the frozen CASE01 source-render regression")

    image_path = Path(image_value)
    assert image_path.is_file(), f"{_IMAGE_ENV} does not point to a file: {image_path}"
    image_bytes = image_path.read_bytes()
    assert hashlib.sha256(image_bytes).hexdigest() == _RENDER_SHA256
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    assert image.shape[:2] == (1684, 2382)

    lines = extract_lines(
        image,
        hough_threshold=90,
        min_line_length=50,
        max_line_gap=5,
    )
    candidates = [
        line
        for line in lines
        if abs(line.p2_px[0] - line.p1_px[0]) <= 5
        and 157 <= (line.p1_px[0] + line.p2_px[0]) / 2 <= 164
        and _intersects(line, _LINE_CORRIDOR)
        and _intersects(line, _UPPER_WITNESS)
        and _intersects(line, _LOWER_WITNESS)
    ]
    assert candidates, (
        "the frozen CASE01 dimension line must reach both source-visible arrow witnesses; "
        f"current detections: {[(line.p1_px, line.p2_px) for line in lines if 157 <= (line.p1_px[0] + line.p2_px[0]) / 2 <= 164]}"
    )


def test_ray_march_does_not_follow_an_adjacent_connected_glyph_stroke() -> None:
    gray = np.full((100, 150), 255, dtype=np.uint8)
    cv2.line(gray, (20, 50), (80, 50), 0, 2)
    cv2.line(gray, (82, 50), (82, 52), 0, 1)
    cv2.line(gray, (82, 52), (115, 52), 0, 1)

    _, extended_end = _extend_line_endpoints_along_ink((20.0, 50.0), (80.0, 50.0), gray)

    assert extended_end[0] <= 84.0, f"adjacent one-pixel glyph stem caused a long extension: {extended_end}"


def test_ray_march_preserves_white_paper_between_separated_collinear_segments() -> None:
    image = np.full((120, 220, 3), 255, dtype=np.uint8)
    cv2.line(image, (20, 60), (80, 60), (0, 0, 0), 2)
    cv2.line(image, (120, 60), (180, 60), (0, 0, 0), 2)

    lines = extract_lines(image, hough_threshold=20, min_line_length=20, max_line_gap=5)

    assert not any(
        min(line.p1_px[0], line.p2_px[0]) <= 80
        and max(line.p1_px[0], line.p2_px[0]) >= 120
        and abs(line.p1_px[1] - line.p2_px[1]) <= 3
        for line in lines
    ), f"white-paper gap was bridged: {[(line.p1_px, line.p2_px) for line in lines]}"


@pytest.mark.parametrize(("gap_pixels", "second_start_x"), [(1, 72), (2, 73)])
def test_ray_march_does_not_reconnect_short_unsupported_white_gaps(
    gap_pixels: int, second_start_x: int
) -> None:
    gray = np.full((80, 140), 255, dtype=np.uint8)
    cv2.line(gray, (20, 40), (70, 40), 0, 2)
    cv2.line(gray, (second_start_x, 40), (110, 40), 0, 2)

    _, first_end = _extend_line_endpoints_along_ink((20.0, 40.0), (70.0, 40.0), gray)
    second_start, _ = _extend_line_endpoints_along_ink(
        (float(second_start_x), 40.0), (110.0, 40.0), gray
    )

    # Collinearity and gap width alone are not an independent geometric witness.
    assert first_end == (70.0, 40.0)
    assert second_start == (float(second_start_x), 40.0)


def test_ray_march_does_not_solidify_a_dashed_line() -> None:
    image = np.full((100, 240, 3), 255, dtype=np.uint8)
    for x_start in (20, 50, 80, 110, 140):
        cv2.line(image, (x_start, 50), (x_start + 20, 50), (0, 0, 0), 2)

    lines = extract_lines(image, hough_threshold=10, min_line_length=10, max_line_gap=5)

    assert not any(
        min(line.p1_px[0], line.p2_px[0]) <= 80
        and max(line.p1_px[0], line.p2_px[0]) >= 110
        and abs(line.p1_px[1] - line.p2_px[1]) <= 3
        for line in lines
    ), f"dashes were solidified: {[(line.p1_px, line.p2_px) for line in lines]}"


def test_ray_march_degenerate_and_out_of_image_inputs_are_safe() -> None:
    gray = np.full((40, 40), 255, dtype=np.uint8)
    same = (12.0, 12.0)
    assert _extend_line_endpoints_along_ink(same, same, gray) == (same, same)

    nan_point = (math.nan, 12.0)
    returned = _extend_line_endpoints_along_ink(nan_point, same, gray)
    assert math.isnan(returned[0][0]) and returned[1] == same
    assert _extend_line_endpoints_along_ink((-10.0, -10.0), (-5.0, -5.0), gray) == (
        (-10.0, -10.0), (-5.0, -5.0),
    )


@pytest.mark.real_data
def test_ftc11_interrupted_dimension_is_not_joined_across_its_frozen_text_gap() -> None:
    image_value = os.environ.get(_FTC11_IMAGE_ENV)
    if not image_value:
        pytest.skip(f"set {_FTC11_IMAGE_ENV} to run the frozen FTC-11 interruption control")

    image_path = Path(image_value)
    assert image_path.is_file(), f"{_FTC11_IMAGE_ENV} does not point to a file: {image_path}"
    image_bytes = image_path.read_bytes()
    assert hashlib.sha256(image_bytes).hexdigest() == _FTC11_RENDER_SHA256
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    assert image.shape[:2] == (1224, 1584)

    axis_dx = _FTC11_AXIS_END[0] - _FTC11_AXIS_START[0]
    axis_dy = _FTC11_AXIS_END[1] - _FTC11_AXIS_START[1]
    axis_length = math.hypot(axis_dx, axis_dy)
    ux, uy = axis_dx / axis_length, axis_dy / axis_length
    nx, ny = -uy, ux
    lines = extract_lines(image, hough_threshold=90, min_line_length=50, max_line_gap=5)
    for line in lines:
        dx = line.p2_px[0] - line.p1_px[0]
        dy = line.p2_px[1] - line.p1_px[1]
        length = math.hypot(dx, dy)
        if not length:
            continue
        alignment = abs((dx * ux + dy * uy) / length)
        if alignment < math.cos(math.radians(3)):
            continue
        perpendicular = max(
            abs((point[0] - _FTC11_AXIS_START[0]) * nx + (point[1] - _FTC11_AXIS_START[1]) * ny)
            for point in (line.p1_px, line.p2_px)
        )
        if perpendicular > 6.0:
            continue
        projections = [
            (point[0] - _FTC11_AXIS_START[0]) * ux + (point[1] - _FTC11_AXIS_START[1]) * uy
            for point in (line.p1_px, line.p2_px)
        ]
        assert not (
            min(projections) <= _FTC11_GAP_PROJECTION[0]
            and max(projections) >= _FTC11_GAP_PROJECTION[1]
        ), f"one extracted segment bridged FTC-11's 192 px text gap: {line.p1_px} -> {line.p2_px}"
