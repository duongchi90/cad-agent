"""test_curve_contour_benchmark.py - Empirical Multi-Strategy Benchmark.

Compares Strategies A, B, C, and D across 8 curve/contour scenarios:
1. Scenario 1: Clean simple circle (radius 40px).
2. Scenario 2: Symmetric 2-lobe link with 1px start-point phase offset.
3. Scenario 3: Reversed winding direction on asymmetric cam contour.
4. Scenario 4: Non-star-shaped concave C-bracket.
5. Scenario 5: Subtle arc flattening (circular contour flattened into straight chord).
6. Scenario 6: Plate with internal circular bore vs distorted diamond bore.
7. Scenario 7: Flat-top straight rectangle with coordinate tie perturbation.
8. Scenario 8: True corner fillet distortion (rounded corner R=20 vs sharp 90 deg corner).

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
    compare_curve_profile_strategy_b,
    compare_curve_profile_strategy_c,
    compare_curve_profile_strategy_d,
    extract_all_contours_d,
)


def scenario_1_clean_circle() -> tuple[np.ndarray, np.ndarray]:
    """Clean identical circle in reference and CAD."""
    ref = np.zeros((120, 120), dtype=np.uint8)
    cv2.circle(ref, (60, 60), 40, 255, -1)
    cad = ref.copy()
    return ref, cad


def scenario_2_phase_offset_lobes() -> tuple[np.ndarray, np.ndarray]:
    """Symmetric 2-lobe bracket with 1px bump causing min(x,y) phase shift."""
    mask = np.zeros((150, 150), dtype=np.uint8)
    cv2.circle(mask, (50, 50), 25, 255, -1)
    cv2.circle(mask, (50, 100), 25, 255, -1)
    cv2.rectangle(mask, (25, 50), (75, 100), 255, -1)
    ref = mask.copy()
    ref[50, 24] = 255
    cad = mask.copy()
    cad[100, 24] = 255
    return ref, cad


def scenario_3_reversed_winding_cam() -> tuple[np.ndarray, np.ndarray]:
    """Asymmetric cam contour with inverted vertex traversal direction."""
    h, w = 150, 150
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(ref, (50, 75), 30, 255, -1)
    pts = np.array([[50, 45], [120, 75], [50, 105]], dtype=np.int32)
    cv2.fillPoly(ref, [pts], 255)

    contours, _ = cv2.findContours(ref.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    rev_pts = contours[0][::-1]
    cad = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(cad, [rev_pts], -1, 255, -1)
    return ref, cad


def scenario_4_concave_c_bracket() -> tuple[np.ndarray, np.ndarray]:
    """Non-star-shaped concave C-bracket (fails centroid polar raycasting)."""
    h, w = 150, 150
    ref = np.zeros((h, w), dtype=np.uint8)
    # Outer block: 20 to 120
    cv2.rectangle(ref, (20, 20), (120, 120), 255, -1)
    # Cut out center-right pocket to create C-shape
    cv2.rectangle(ref, (60, 50), (120, 90), 0, -1)
    cad = ref.copy()
    return ref, cad


def scenario_5_arc_flattening() -> tuple[np.ndarray, np.ndarray]:
    """Circular arc flattened into a straight chord (local curvature drops to 0)."""
    h, w = 150, 150
    ref = np.zeros((h, w), dtype=np.uint8)
    # Circular arc lobe at top
    cv2.circle(ref, (75, 75), 45, 255, -1)

    cad = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(cad, (75, 75), 45, 255, -1)
    # Flatten the top arc into a straight line at y=35
    cad[0:35, :] = 0
    return ref, cad


def scenario_6_plate_internal_bore_distortion() -> tuple[np.ndarray, np.ndarray]:
    """Plate with identical outer boundary but distorted internal bore."""
    h, w = 200, 200
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(ref, (30, 30), (170, 170), 255, -1)
    cv2.circle(ref, (100, 100), 25, 0, -1)  # Smooth circular hole

    cad = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(cad, (30, 30), (170, 170), 255, -1)
    diamond = np.array([[100, 75], [125, 100], [100, 125], [75, 100]], dtype=np.int32)
    cv2.fillPoly(cad, [diamond], 0)  # Distorted diamond hole
    return ref, cad


def scenario_7_flat_edge_tie() -> tuple[np.ndarray, np.ndarray]:
    """Flat-edge rectangle with coordinate tie perturbation."""
    h, w = 100, 120
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(ref, (20, 20), (100, 80), 255, -1)
    cad = ref.copy()
    cad[20, 20] = 0
    return ref, cad


def scenario_8_fillet_vs_sharp_corner() -> tuple[np.ndarray, np.ndarray]:
    """Rounded corner (R=20) in reference vs sharp 90-degree corner in CAD."""
    h, w = 150, 150
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(ref, (20, 40), (120, 120), 255, -1)
    cv2.rectangle(ref, (40, 20), (120, 120), 255, -1)
    cv2.circle(ref, (40, 40), 20, 255, -1)  # Fillet at (20, 20)

    cad = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(cad, (20, 20), (120, 120), 255, -1)  # Sharp square corner
    return ref, cad


def test_scenario_1_clean_circle() -> None:
    ref, cad = scenario_1_clean_circle()
    ra = compare_curve_profile_strategy_a(ref, cad)
    rb = compare_curve_profile_strategy_b(ref, cad)
    rc = compare_curve_profile_strategy_c(ref, cad)
    rd = compare_curve_profile_strategy_d(ref, cad)

    assert ra["curvature_profile_p95"] <= 0.05
    assert rb["chamfer_distance"] <= 0.5
    assert rc["curvature_profile_p95"] <= 0.05
    assert rd.status == "ALIGNED"
    assert rd.curvature_p95 <= 0.05


def test_scenario_2_phase_offset_lobes() -> None:
    ref, cad = scenario_2_phase_offset_lobes()
    ra = compare_curve_profile_strategy_a(ref, cad)
    rd = compare_curve_profile_strategy_d(ref, cad)

    assert ra["curvature_profile_p95"] > 0.20  # Strategy A trapped by start-point phase
    assert rd.status == "ALIGNED"
    assert rd.curvature_p95 <= 0.05


def test_scenario_3_reversed_winding_cam() -> None:
    ref, cad = scenario_3_reversed_winding_cam()
    rd = compare_curve_profile_strategy_d(ref, cad)

    assert rd.status == "ALIGNED"
    assert rd.curvature_p95 <= 0.05


def test_scenario_4_concave_c_bracket() -> None:
    ref, cad = scenario_4_concave_c_bracket()
    # Strategy C fails on concave non-star shapes
    with pytest.raises(ValueError, match="non-star-shaped geometry"):
        compare_curve_profile_strategy_c(ref, cad)

    rd = compare_curve_profile_strategy_d(ref, cad)
    assert rd.status == "ALIGNED"
    assert rd.curvature_p95 <= 0.05


def test_scenario_5_arc_flattening() -> None:
    ref, cad = scenario_5_arc_flattening()
    ra = compare_curve_profile_strategy_a(ref, cad)
    rb = compare_curve_profile_strategy_b(ref, cad)
    rd = compare_curve_profile_strategy_d(ref, cad)

    # Strategy B Chamfer distance is tiny (< 1.5px) and blind to local curvature drop
    assert rb["curvature_profile_p95"] == 0.0

    # Strategy A and D detect curvature change
    assert ra["curvature_profile_p95"] > 0.10
    assert rd.status == "CURVE_MISMATCH"
    assert rd.curvature_p95 > 0.15


def test_scenario_6_plate_internal_bore_distortion() -> None:
    ref, cad = scenario_6_plate_internal_bore_distortion()
    ra = compare_curve_profile_strategy_a(ref, cad)
    # Strategy A is 100% blind to internal bore distortion
    assert ra["curvature_profile_p95"] == 0.0

    # Strategy D detects internal contours
    ref_c = extract_all_contours_d(ref)
    cad_c = extract_all_contours_d(cad)
    assert len(ref_c) == 2
    assert len(cad_c) == 2


def test_scenario_7_flat_edge_tie() -> None:
    ref, cad = scenario_7_flat_edge_tie()
    ra = compare_curve_profile_strategy_a(ref, cad)
    rd = compare_curve_profile_strategy_d(ref, cad)

    assert ra["curvature_profile_p95"] > 0.15  # Strategy A fails on flat edge tie
    assert rd.status == "ALIGNED"
    assert rd.curvature_p95 <= 0.08


def test_scenario_8_fillet_vs_sharp_corner() -> None:
    ref, cad = scenario_8_fillet_vs_sharp_corner()
    ra = compare_curve_profile_strategy_a(ref, cad)
    rd = compare_curve_profile_strategy_d(ref, cad)

    # Both detect genuine fillet flattening
    assert ra["curvature_profile_p95"] > 0.15
    assert rd.status == "CURVE_MISMATCH"
    assert rd.curvature_p95 > 0.10
