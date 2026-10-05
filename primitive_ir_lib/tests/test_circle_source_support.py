"""Public synthetic topology controls; no private drawing pixels or coordinates."""

import cv2
import numpy as np
import pytest

from primitive_ir_lib.geometry_extraction import extract_raw_geometry


def _open_curve_and_full_circle(scale):
    image = np.full((320 * scale, 420 * scale, 3), 255, dtype=np.uint8)
    # Multiple concentric open arcs are strong Hough votes, not closed contours.
    for radius in (58, 62, 66):
        cv2.ellipse(
            image, (110 * scale, 155 * scale), (radius * scale, radius * scale),
            0, 175, 285, (0, 0, 0), 2 * scale, cv2.LINE_AA,
        )
    cv2.circle(image, (305 * scale, 155 * scale), 42 * scale, (0, 0, 0),
               2 * scale, cv2.LINE_AA)
    return image


def _geometry(image, scale):
    return extract_raw_geometry(
        image, param2=18, min_dist=20 * scale,
        min_radius=25 * scale, max_radius=80 * scale,
    )


@pytest.mark.parametrize("scale", [1, 2])
def test_open_curves_do_not_become_closed_circles_beside_a_real_circle(scale):
    circles = _geometry(_open_curve_and_full_circle(scale), scale).circles
    assert circles, "Rejecting everything is not a successful circle repair"
    assert not [c for c in circles if c.center_px[0] < 210 * scale]
    assert any(
        np.linalg.norm(np.array(c.center_px) - (305 * scale, 155 * scale)) < 5 * scale
        and abs(c.radius_px - 42 * scale) < 5 * scale
        for c in circles
    )


@pytest.mark.parametrize("start_angle", [25, 85])
def test_nearly_complete_arc_with_a_long_gap_is_not_closed(start_angle):
    image = np.full((320, 420, 3), 255, dtype=np.uint8)
    cv2.ellipse(image, (110, 155), (60, 60), 0, start_angle, start_angle + 310,
                (0, 0, 0), 2, cv2.LINE_AA)
    cv2.circle(image, (305, 155), 42, (0, 0, 0), 2, cv2.LINE_AA)
    circles = _geometry(image, 1).circles
    assert circles, "The independent full circle must still be admitted"
    assert not [c for c in circles if c.center_px[0] < 210]
    assert any(np.linalg.norm(np.array(c.center_px) - (305, 155)) < 5 for c in circles)


def test_disconnected_arc_fragments_do_not_gain_circle_semantics():
    image = np.full((320, 420, 3), 255, dtype=np.uint8)
    for angle in range(0, 360, 30):
        cv2.ellipse(image, (110, 155), (60, 60), 0, angle, angle + 8,
                    (0, 0, 0), 2, cv2.LINE_AA)
    cv2.circle(image, (305, 155), 42, (0, 0, 0), 2, cv2.LINE_AA)
    circles = _geometry(image, 1).circles
    assert circles
    assert not [c for c in circles if c.center_px[0] < 210]


@pytest.mark.parametrize("scale,thickness", [(1, 1), (1, 3), (2, 2), (2, 5)])
def test_complete_circle_with_crossing_centerlines_survives(scale, thickness):
    image = np.full((220 * scale, 220 * scale, 3), 255, dtype=np.uint8)
    cv2.circle(image, (110 * scale, 110 * scale), 55 * scale, (0, 0, 0), thickness,
               cv2.LINE_AA)
    cv2.line(image, (35 * scale, 110 * scale), (185 * scale, 110 * scale),
             (0, 0, 0), thickness)
    cv2.line(image, (110 * scale, 35 * scale), (110 * scale, 185 * scale),
             (0, 0, 0), thickness)
    circles = _geometry(image, scale).circles
    assert circles
    assert any(np.linalg.norm(np.array(c.center_px) - (110 * scale, 110 * scale))
               < 5 * scale for c in circles)


def test_small_existing_synthetic_circle_survives_default_preset():
    image = np.full((160, 240, 3), 255, dtype=np.uint8)
    cv2.circle(image, (120, 100), 18, (0, 0, 0), 2)
    circles = extract_raw_geometry(image).circles
    assert any(np.linalg.norm(np.array(c.center_px) - (120, 100)) < 4 for c in circles)


def test_circle_admission_is_deterministic_excluding_generated_ids():
    image = _open_curve_and_full_circle(1)
    first = _geometry(image, 1).circles
    second = _geometry(image, 1).circles
    assert first and second
    assert [(c.center_px, c.radius_px, c.confidence) for c in first] == [
        (c.center_px, c.radius_px, c.confidence) for c in second
    ]


def test_blank_source_truthfully_has_no_circle():
    image = np.full((160, 240, 3), 255, dtype=np.uint8)
    assert extract_raw_geometry(image).circles == []
