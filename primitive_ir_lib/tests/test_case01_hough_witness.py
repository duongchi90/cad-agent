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
