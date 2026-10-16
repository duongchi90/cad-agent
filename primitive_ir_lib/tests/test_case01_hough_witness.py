"""Focused real-data regression for the frozen CASE01 dimension witness."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

import cv2
import pytest

from primitive_ir_lib.geometry_extraction import extract_raw_geometry


pytestmark = pytest.mark.real_data

_IMAGE_ENV = "CAD_AGENT_CASE01_DIMENSION_WITNESS_IMAGE"
_IMAGE_SHA256 = "5732b6014ec1c1d3b05e14c598b43ebec84a4d6198951264215a69fb7b0a0bc8"
_UPPER_ENDPOINT = (153, 198, 168, 219)
_LOWER_ENDPOINT = (153, 369, 168, 390)
_CORRIDOR = (157, 219, 164, 369)


def _intersects(line, rect: tuple[int, int, int, int]) -> bool:
    x0, y0, x1, y1 = rect
    lx0, ly0, lx1, ly1 = line.bbox_px
    return lx1 >= x0 and lx0 < x1 and ly1 >= y0 and ly0 < y1


def test_tuned_hough_detects_case01_dimension_witness_endpoints() -> None:
    image_value = os.environ.get(_IMAGE_ENV)
    if not image_value:
        pytest.skip(f"set {_IMAGE_ENV} to run the frozen CASE01 real-data regression")

    image_path = Path(image_value)
    assert image_path.is_file(), f"{_IMAGE_ENV} does not point to a file: {image_path}"
    assert hashlib.sha256(image_path.read_bytes()).hexdigest() == _IMAGE_SHA256

    image = cv2.imread(str(image_path))
    assert image is not None
    assert image.shape == (1684, 2382, 3)

    cv2.setRNGSeed(0)
    geometry = extract_raw_geometry(image, preset="real_scan_tuned_v1")
    witnesses = []
    for line in geometry.lines:
        dx = abs(line.p2_px[0] - line.p1_px[0])
        dy = abs(line.p2_px[1] - line.p1_px[1])
        angle_from_vertical = math.degrees(math.atan2(dx, dy))
        if (
            angle_from_vertical <= 5.0
            and _intersects(line, _CORRIDOR)
            and _intersects(line, _UPPER_ENDPOINT)
            and _intersects(line, _LOWER_ENDPOINT)
        ):
            witnesses.append(line)

    assert witnesses, "the tuned Hough output omits the frozen CASE01 dimension endpoints"

_FTC11_IMAGE_ENV = "CAD_AGENT_FTC11_TEXT_GAP_IMAGE"
_FTC11_RENDER_SHA256 = "675f1a991dca7a133f0923bef6aa431f68e719f29780946f358904ace4a2ca00"
_FTC11_ARROW_TIPS = ((622.7999877929688, 467.8800048828125), (1120.56005859375, 180.5999755859375))
_FTC11_TEXT_GAP = (191.174, 383.539)
# Frozen clean-#519 control measured from the exact render with cv2 RNG seed 0.
_FTC11_FROZEN_BASELINE_GAP_FRACTION = 0.6001101000130548
# Allow 1e-9 in fraction units for floating-point projection/union arithmetic.
_FTC11_COVERAGE_ARITHMETIC_TOLERANCE = 1e-9


def test_tuned_hough_does_not_fully_bridge_ftc11_intentional_text_gap() -> None:
    image_value = os.environ.get(_FTC11_IMAGE_ENV)
    if not image_value:
        pytest.skip(f"set {_FTC11_IMAGE_ENV} to run the frozen FTC-11 text-gap regression")

    image_path = Path(image_value)
    assert image_path.is_file(), f"{_FTC11_IMAGE_ENV} does not point to a file: {image_path}"
    assert hashlib.sha256(image_path.read_bytes()).hexdigest() == _FTC11_RENDER_SHA256

    image = cv2.imread(str(image_path))
    assert image is not None
    assert image.shape == (1224, 1584, 3)

    cv2.setRNGSeed(0)
    geometry = extract_raw_geometry(image, preset="real_scan_tuned_v1")
    (ax, ay), (bx, by) = _FTC11_ARROW_TIPS
    axis_length = math.hypot(bx - ax, by - ay)
    ux = (bx - ax) / axis_length
    uy = (by - ay) / axis_length
    gap_start, gap_end = _FTC11_TEXT_GAP

    intervals = []
    for line in geometry.lines:
        (x1, y1), (x2, y2) = line.p1_px, line.p2_px
        dx = x2 - x1
        dy = y2 - y1
        line_length = math.hypot(dx, dy)
        if line_length == 0:
            continue
        orientation_error = math.degrees(
            math.acos(min(1.0, abs((dx * ux + dy * uy) / line_length)))
        )
        perpendicular_distances = (
            abs((x1 - ax) * uy - (y1 - ay) * ux),
            abs((x2 - ax) * uy - (y2 - ay) * ux),
        )
        if orientation_error > 5.0 or max(perpendicular_distances) > 3.0:
            continue
        projections = ((x1 - ax) * ux + (y1 - ay) * uy, (x2 - ax) * ux + (y2 - ay) * uy)
        intervals.append((min(projections), max(projections)))

    unions = []
    for start, end in sorted(intervals):
        if not unions or start > unions[-1][1]:
            unions.append([start, end])
        else:
            unions[-1][1] = max(unions[-1][1], end)

    gap_coverage = sum(
        max(0.0, min(gap_end, end) - max(gap_start, start))
        for start, end in unions
    )
    gap_fraction = gap_coverage / (gap_end - gap_start)
    assert gap_fraction <= (
        _FTC11_FROZEN_BASELINE_GAP_FRACTION + _FTC11_COVERAGE_ARITHMETIC_TOLERANCE
    ), (
        f"detected lines cover {gap_fraction:.16f} of the FTC-11 text-only gap; "
        f"frozen clean-#519 baseline is {_FTC11_FROZEN_BASELINE_GAP_FRACTION:.16f} "
        f"with arithmetic tolerance {_FTC11_COVERAGE_ARITHMETIC_TOLERANCE:.1e}"
    )
