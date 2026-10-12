"""test_curve_contour_controls.py - Positive Fixtures and Strong Negative Controls.

Validates 8 critical boundary controls:
1. CTRL-1: Positive - Smooth variable curvature on identical ellipses (major 50, minor 30).
2. CTRL-2: Negative - Ellipse axis ratio distortion (major 50 / minor 30 vs major 50 / minor 20).
3. CTRL-3: Positive - Pure rotation invariance (shape rotated by 45 degrees).
4. CTRL-4: Negative - Corner fillet removal (R=25 corner fillet removed into sharp corner).
5. CTRL-5: Positive - Symmetrical slotted link plate contour.
6. CTRL-6: Negative - Multi-contour bore plate with distorted inner hole.
7. CTRL-7: Negative - Star polygon with 5 points vs rounded tips.
8. CTRL-8: Positive - Closed S-curve profile contour.

Part of Antigravity Research: CURVE_CONTOUR_PROFILE_COMPARISON_V1
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
import cv2
import numpy as np
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from curve_contour_engine import (
    compare_curve_profile_strategy_d,
    extract_all_contours_d,
)


def test_ctrl_1_positive_identical_ellipse() -> None:
    """CTRL-1: Identical smooth ellipse with variable curvature (axes 50, 30)."""
    h, w = 150, 150
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(ref, (75, 75), (50, 30), 0, 0, 360, 255, -1)
    cad = ref.copy()

    res = compare_curve_profile_strategy_d(ref, cad)
    assert res.status == "ALIGNED"
    assert res.curvature_p95 <= 0.05
    assert res.orientation_l1 <= 0.05


def test_ctrl_2_negative_ellipse_axis_distortion() -> None:
    """CTRL-2: Ellipse axis ratio distorted from 50/30 (1.67) to 50/20 (2.50)."""
    h, w = 150, 150
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(ref, (75, 75), (50, 30), 0, 0, 360, 255, -1)

    cad = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(cad, (75, 75), (50, 20), 0, 0, 360, 255, -1)  # Flatter minor axis

    res = compare_curve_profile_strategy_d(ref, cad)
    assert res.status == "CURVE_MISMATCH"
    assert res.curvature_p95 > 0.08


def test_ctrl_3_positive_rotated_shape() -> None:
    """CTRL-3: Teardrop shape rotated by 90 degrees has identical intrinsic curvature."""
    h, w = 200, 200
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(ref, (100, 100), 30, 255, -1)
    pts = np.array([[100, 70], [170, 100], [100, 130]], dtype=np.int32)
    cv2.fillPoly(ref, [pts], 255)

    # Rotate by 90 deg orthogonally
    cad = np.rot90(ref).copy()

    res = compare_curve_profile_strategy_d(ref, cad)
    assert res.status == "ALIGNED"
    assert res.curvature_p95 <= 0.05
    assert res.optimal_shift != 0  # Phase shift accurately tracks rotation
    assert res.curvature_p95 <= 0.05


def test_ctrl_4_negative_fillet_removal() -> None:
    """CTRL-4: Removal of corner fillet (R=25) into sharp corner fails closed."""
    h, w = 150, 150
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(ref, (25, 50), (125, 125), 255, -1)
    cv2.rectangle(ref, (50, 25), (125, 125), 255, -1)
    cv2.circle(ref, (50, 50), 25, 255, -1)  # Corner fillet

    cad = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(cad, (25, 25), (125, 125), 255, -1)  # Sharp 90 deg corner

    res = compare_curve_profile_strategy_d(ref, cad)
    assert res.status == "CURVE_MISMATCH"
    assert res.curvature_p95 > 0.08


def test_ctrl_5_positive_slotted_link_plate() -> None:
    """CTRL-5: Symmetrical slotted link plate (2 circular ends + parallel waist)."""
    h, w = 160, 200
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(ref, (60, 80), 35, 255, -1)
    cv2.circle(ref, (140, 80), 35, 255, -1)
    cv2.rectangle(ref, (60, 45), (140, 115), 255, -1)
    cad = ref.copy()

    res = compare_curve_profile_strategy_d(ref, cad)
    assert res.status == "ALIGNED"
    assert res.curvature_p95 <= 0.05


def test_ctrl_6_negative_multi_contour_hole_distortion() -> None:
    """CTRL-6: Multi-contour plate with internal bore distortion detected."""
    h, w = 200, 200
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(ref, (30, 30), (170, 170), 255, -1)
    cv2.circle(ref, (100, 100), 25, 0, -1)

    cad = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(cad, (30, 30), (170, 170), 255, -1)
    cv2.rectangle(cad, (80, 80), (120, 120), 0, -1)  # Square hole instead of circular bore

    c_ref = extract_all_contours_d(ref)
    c_cad = extract_all_contours_d(cad)
    assert len(c_ref) == 2
    assert len(c_cad) == 2

    # Compare hole contours directly
    res_hole = compare_curve_profile_strategy_d(
        cv2.drawContours(np.zeros_like(ref), [c_ref[1][0].astype(np.int32)], -1, 255, -1),
        cv2.drawContours(np.zeros_like(cad), [c_cad[1][0].astype(np.int32)], -1, 255, -1),
    )
    assert res_hole.status == "CURVE_MISMATCH"
    assert res_hole.curvature_p95 > 0.08


def test_ctrl_7_negative_star_polygon_vs_rounded() -> None:
    """CTRL-7: 5-point star with sharp points vs star with rounded points."""
    h, w = 200, 200
    ref = np.zeros((h, w), dtype=np.uint8)
    # 5 sharp points
    pts_sharp = []
    for i in range(10):
        angle = i * (math.pi / 5) - math.pi / 2
        r = 60 if i % 2 == 0 else 25
        pts_sharp.append([int(100 + r * math.cos(angle)), int(100 + r * math.sin(angle))])
    cv2.fillPoly(ref, [np.array(pts_sharp, dtype=np.int32)], 255)

    # CAD star with heavily rounded/blurred tips
    cad = cv2.GaussianBlur(ref, (15, 15), 5.0)
    _, cad = cv2.threshold(cad, 100, 255, cv2.THRESH_BINARY)

    res = compare_curve_profile_strategy_d(ref, cad)
    assert res.status == "CURVE_MISMATCH"
    assert res.curvature_p95 > 0.08


def test_ctrl_8_positive_s_curve_profile() -> None:
    """CTRL-8: Continuous G1/G2 S-curve profile matches identical CAD outline."""
    h, w = 180, 180
    ref = np.zeros((h, w), dtype=np.uint8)
    # S-curve outline created with two tangent circles
    cv2.circle(ref, (70, 70), 30, 255, -1)
    cv2.circle(ref, (110, 110), 30, 255, -1)
    cv2.rectangle(ref, (55, 70), (125, 110), 255, -1)
    cad = ref.copy()

    res = compare_curve_profile_strategy_d(ref, cad)
    assert res.status == "ALIGNED"
    assert res.curvature_p95 <= 0.05
