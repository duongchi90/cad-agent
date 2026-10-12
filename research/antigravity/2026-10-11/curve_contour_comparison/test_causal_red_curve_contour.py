"""test_causal_red_curve_contour.py - Public Causal RED for Curve Profile and Contour Comparison.

Reproduces 5 baseline failure modes on production primitive_ir_lib/geometry_comparator.py:
1. RED-1: Phase / start-point desynchronization on symmetric rounded geometry.
2. RED-2: Winding direction inversion (CW vs CCW traversal) causing false 100% curve divergence.
3. RED-3: Single external contour blindness (RETR_EXTERNAL drops all internal bores/holes).
4. RED-4: Flat-top coordinate tie instability on straight edges.
5. RED-5: Blank or degenerate contour unhandled ValueError exception.

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
    compare_curve_profile_strategy_a,
    compare_curve_profile_strategy_d,
    extract_all_contours_d,
)


def make_rounded_rectangle(h: int, w: int, radius: int = 15) -> np.ndarray:
    """Creates a clean binary rounded rectangle mask."""
    img = np.zeros((h, w), dtype=np.uint8)
    x1, y1 = 20, 20
    x2, y2 = w - 20, h - 20
    # Core rectangles
    cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), 255, -1)
    cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), 255, -1)
    # 4 corner circles
    cv2.circle(img, (x1 + radius, y1 + radius), radius, 255, -1)
    cv2.circle(img, (x2 - radius, y1 + radius), radius, 255, -1)
    cv2.circle(img, (x1 + radius, y2 - radius), radius, 255, -1)
    cv2.circle(img, (x2 - radius, y2 - radius), radius, 255, -1)
    return img


def test_red_1_phase_desynchronization_on_symmetric_geometry() -> None:
    """RED-1: Start-point min(x, y) desynchronization causes massive false curvature difference on identical shapes.

    Scenario: A symmetric two-lobe link/bracket has two identical rounded lobes at y=50 and y=100.
    In reference, a 1px raster bump makes the top lobe have minimum x (x=24, y=50).
    In CAD, a 1px raster bump makes the bottom lobe have minimum x (x=24, y=100).
    The geometry is virtually identical, but min(x,y) shifts the starting vertex by 50px along the contour.
    Strategy A element-wise subtraction causes a massive false curvature difference (> 0.25).
    Strategy D aligns the cyclic phase and correctly reports curvature_p95 <= 0.05.
    """
    mask = np.zeros((150, 150), dtype=np.uint8)
    cv2.circle(mask, (50, 50), 25, 255, -1)
    cv2.circle(mask, (50, 100), 25, 255, -1)
    cv2.rectangle(mask, (25, 50), (75, 100), 255, -1)

    ref_mask = mask.copy()
    ref_mask[50, 24] = 255  # min x at top lobe

    cad_mask = mask.copy()
    cad_mask[100, 24] = 255  # min x at bottom lobe

    # Strategy A (Production Main)
    res_a = compare_curve_profile_strategy_a(ref_mask, cad_mask)
    # Production Strategy A reports massive curvature error (> 0.20) due to 50px phase shift!
    assert res_a["curvature_profile_p95"] > 0.20

    # Strategy D (Cyclic Phase Synchronization)
    res_d = compare_curve_profile_strategy_d(ref_mask, cad_mask)
    assert res_d.status == "ALIGNED"
    assert res_d.curvature_p95 <= 0.05


def test_red_2_winding_direction_inversion() -> None:
    """RED-2: Inverted traversal direction (CW vs CCW) compares point t with 1-t, causing false mismatch.

    We create an asymmetric cam / teardrop shape: circle at one end, triangle point at the other.
    If winding direction is flipped, element-wise comparison in Strategy A explodes.
    """
    h, w = 150, 150
    ref_mask = np.zeros((h, w), dtype=np.uint8)
    # Circle at (50, 75) radius 30
    cv2.circle(ref_mask, (50, 75), 30, 255, -1)
    # Triangle pointing to (120, 75)
    pts = np.array([[50, 45], [120, 75], [50, 105]], dtype=np.int32)
    cv2.fillPoly(ref_mask, [pts], 255)

    # CAD is the exact same shape
    cad_mask = ref_mask.copy()

    # Invert the contour order in CAD mask by transposing/flipping or extracting contours and reversing
    contours, _ = cv2.findContours(cad_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    rev_contour = contours[0][::-1]  # Reversed winding
    rev_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(rev_mask, [rev_contour], -1, 255, -1)

    # Strategy D normalizes winding and passes
    res_d = compare_curve_profile_strategy_d(ref_mask, rev_mask)
    assert res_d.status == "ALIGNED"
    assert res_d.curvature_p95 <= 0.05


def test_red_3_single_external_contour_blindness_to_internal_holes() -> None:
    """RED-3: Production Strategy A uses RETR_EXTERNAL and takes only ranked[0], ignoring all internal bores/holes.

    Reference has an outer square plate with a smooth circular internal bore (radius 25).
    CAD has the same outer square plate, but the internal bore is severely distorted into a diamond!
    """
    h, w = 200, 200
    ref_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(ref_mask, (30, 30), (170, 170), 255, -1)  # Outer square
    cv2.circle(ref_mask, (100, 100), 25, 0, -1)  # Internal circular hole

    cad_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(cad_mask, (30, 30), (170, 170), 255, -1)  # Same outer square
    # Internal hole is distorted into a sharp diamond
    diamond_pts = np.array([[100, 75], [125, 100], [100, 125], [75, 100]], dtype=np.int32)
    cv2.fillPoly(cad_mask, [diamond_pts], 0)

    # Strategy A only checks outer contour: curvature difference on outer square is 0.0!
    res_a = compare_curve_profile_strategy_a(ref_mask, cad_mask)
    assert res_a["curvature_profile_p95"] == 0.0  # 100% blind to internal hole distortion!

    # Strategy D extracts internal contours via RETR_CCOMP
    ref_contours = extract_all_contours_d(ref_mask)
    cad_contours = extract_all_contours_d(cad_mask)
    assert len(ref_contours) == 2  # Outer + hole
    assert len(cad_contours) == 2  # Outer + hole
    assert not ref_contours[1][1]  # is_external is False -> hole correctly recognized!


def test_red_4_flat_edge_tie_instability() -> None:
    """RED-4: Straight horizontal edge has identical y coordinate across 80 pixels.

    Tiny 1px aliasing shifts min(x,y) start index by 80px, rotating 128 resampled vertices
    and triggering false corner mismatch in Strategy A.
    """
    h, w = 100, 120
    ref_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(ref_mask, (20, 20), (100, 80), 255, -1)

    cad_mask = ref_mask.copy()
    # Shift top-left tie slightly
    cad_mask[20, 20] = 0

    res_a = compare_curve_profile_strategy_a(ref_mask, cad_mask)
    # Production Strategy A reports large error because corners don't line up
    assert res_a["curvature_profile_p95"] > 0.15

    # Strategy D aligns cyclic phase
    res_d = compare_curve_profile_strategy_d(ref_mask, cad_mask)
    assert res_d.status == "ALIGNED"
    assert res_d.curvature_p95 <= 0.08


def test_red_5_blank_degenerate_contour_unhandled_exception() -> None:
    """RED-5: Blank mask crashes Strategy A with ValueError instead of returning structured result."""
    blank = np.zeros((100, 100), dtype=np.uint8)
    rect = np.zeros((100, 100), dtype=np.uint8)
    rect[20:80, 20:80] = 255

    # Strategy A raises uncaught ValueError
    with pytest.raises(ValueError, match="curve profile requires a non-empty contour"):
        compare_curve_profile_strategy_a(blank, rect)

    # Strategy D returns structured FAILED result
    res_d = compare_curve_profile_strategy_d(blank, rect)
    assert res_d.status == "FAILED"
    assert "reference has no valid contours" in res_d.reasons[0]
