"""Causal regression for source-supported circles outside the scan preset range."""

import cv2
import numpy as np

from primitive_ir_lib.geometry_extraction import extract_raw_geometry


IMAGE_SHAPE = (1684, 2382, 3)
PAPER_GRAY = 210
STROKE_GRAY = 30
CENTER = (678, 979)
SOURCE_CIRCLES = ((336, (320, 355)), (425, (410, 440)))


def _paper() -> np.ndarray:
    return np.full(IMAGE_SHAPE, PAPER_GRAY, dtype=np.uint8)


def _source_like_concentric_circles() -> np.ndarray:
    image = _paper()
    for radius, _ in SOURCE_CIRCLES:
        cv2.circle(image, CENTER, radius, (STROKE_GRAY,) * 3, 2, lineType=cv2.LINE_AA)
    return image


def _matches_source_circle(circles, radius: int) -> bool:
    return any(
        abs(circle.center_px[0] - CENTER[0]) <= 8
        and abs(circle.center_px[1] - CENTER[1]) <= 8
        and abs(circle.radius_px - radius) <= 8
        for circle in circles
    )


def test_real_scan_preset_finds_source_supported_large_concentric_circles():
    """The real-scan entry point should not omit clearly supported large circles."""
    detected = extract_raw_geometry(
        _source_like_concentric_circles(), preset="real_scan_tuned_v1"
    ).circles

    missing_radii = [
        radius for radius, _ in SOURCE_CIRCLES
        if not _matches_source_circle(detected, radius)
    ]
    assert not missing_radii, f"source-supported circles omitted at radii {missing_radii}px"


def test_explicit_radius_bands_still_limit_each_circle_query():
    image = _source_like_concentric_circles()

    for radius, (min_radius, max_radius) in SOURCE_CIRCLES:
        detected = extract_raw_geometry(
            image,
            preset="real_scan_tuned_v1",
            min_radius=min_radius,
            max_radius=max_radius,
        ).circles

        assert detected
        assert all(min_radius <= circle.radius_px <= max_radius for circle in detected)
        assert _matches_source_circle(detected, radius)


def test_real_scan_entrypoint_does_not_promote_ellipse_or_open_arc_to_circle():
    controls = []

    ellipse = _paper()
    cv2.ellipse(
        ellipse, CENTER, (425, 250), 0, 0, 360,
        (STROKE_GRAY,) * 3, 2, lineType=cv2.LINE_AA,
    )
    controls.append(ellipse)

    open_ellipse_arc = _paper()
    cv2.ellipse(
        open_ellipse_arc, CENTER, (425, 250), 0, 0, 330,
        (STROKE_GRAY,) * 3, 2, lineType=cv2.LINE_AA,
    )
    controls.append(open_ellipse_arc)

    open_circle_arc = _paper()
    cv2.ellipse(
        open_circle_arc, CENTER, (425, 425), 0, 0, 350,
        (STROKE_GRAY,) * 3, 2, lineType=cv2.LINE_AA,
    )
    controls.append(open_circle_arc)

    for image in controls:
        detected = extract_raw_geometry(
            image, preset="real_scan_tuned_v1"
        ).circles
        assert detected == []
