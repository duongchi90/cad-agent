"""test_geometry_alignment_controls.py - Positive Fixtures and Strong Negative Controls.

Validates 8 critical boundary controls:
1. CTRL-1: Positive - High-confidence 4-datum similarity with known 3.0 deg rotation and 1.25 scale.
2. CTRL-2: Negative - Excessive rotation rejection (> 5.0 deg max_rotation_deg).
3. CTRL-3: Negative - Scale outside approved bounds ([0.5, 2.0] uniform scale policy).
4. CTRL-4: Negative - Reflection / mirror transformation rejection (det < 0).
5. CTRL-5: Negative - Unsupported authority rejection (unknown string fails closed).
6. CTRL-6: Negative - Low-confidence VISUAL_FEATURE rejection (< 0.8 confidence threshold).
7. CTRL-7: Positive - Perspective photograph homography across N=8 distributed points.
8. CTRL-8: Positive - Pure black background outline normalization with 10% white border noise.

Part of Antigravity Research: RESTRICTED_GEOMETRY_ALIGNMENT_AND_COMPARISON_V1
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
import numpy as np
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from geometry_alignment_engine import (
    AnchorPair,
    estimate_photograph_strategy_d,
    estimate_similarity_strategy_d,
    normalize_outline_strategy_d,
)


def test_ctrl_1_positive_known_rotation_and_scale() -> None:
    """CTRL-1: 4 DATUM anchors rotated by 3.0 deg and scaled by 1.20 resolve accurately."""
    theta = math.radians(3.0)
    scale = 1.20
    tx, ty = 25.0, 40.0
    cad_pts = [(50.0, 50.0), (200.0, 50.0), (200.0, 150.0), (50.0, 150.0)]
    ref_pts = []
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    for x, y in cad_pts:
        xr = scale * (cos_t * x - sin_t * y) + tx
        yr = scale * (sin_t * x + cos_t * y) + ty
        ref_pts.append((xr, yr))

    anchors = [
        AnchorPair(f"D{i}", ref_pts[i], cad_pts[i], "DATUM", 1.0)
        for i in range(len(cad_pts))
    ]

    res = estimate_similarity_strategy_d(anchors)
    assert res.status == "ALIGNED"
    assert res.matrix is not None
    assert res.residual_rms_px is not None
    assert res.residual_rms_px < 0.01

    m = res.matrix
    computed_scale = math.hypot(m[0][0], m[0][1])
    computed_deg = math.degrees(math.atan2(m[1][0], m[0][0]))
    assert abs(computed_scale - scale) < 1e-3
    assert abs(computed_deg - 3.0) < 1e-2


def test_ctrl_2_excessive_rotation_rejection() -> None:
    """CTRL-2: Rotation of 8.0 deg exceeds 5.0 deg threshold and fails closed."""
    theta = math.radians(8.0)
    cad_pts = [(50.0, 50.0), (200.0, 50.0), (200.0, 150.0), (50.0, 150.0)]
    ref_pts = []
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    for x, y in cad_pts:
        xr = cos_t * x - sin_t * y
        yr = sin_t * x + cos_t * y
        ref_pts.append((xr, yr))

    anchors = [
        AnchorPair(f"D{i}", ref_pts[i], cad_pts[i], "DATUM", 1.0)
        for i in range(len(cad_pts))
    ]

    res = estimate_similarity_strategy_d(anchors, max_rotation_deg=5.0)
    assert res.status == "FAILED"
    assert "rotation is outside the approved range" in res.reasons[0]


def test_ctrl_3_scale_bounds_rejection() -> None:
    """CTRL-3: Scale = 2.5 exceeds max_uniform_scale=2.0 and fails closed."""
    scale = 2.5
    cad_pts = [(50.0, 50.0), (200.0, 50.0), (200.0, 150.0), (50.0, 150.0)]
    ref_pts = [(x * scale, y * scale) for x, y in cad_pts]

    anchors = [
        AnchorPair(f"D{i}", ref_pts[i], cad_pts[i], "DATUM", 1.0)
        for i in range(len(cad_pts))
    ]

    res = estimate_similarity_strategy_d(anchors, max_uniform_scale=2.0)
    assert res.status == "FAILED"
    assert "uniform scale is outside the approved range" in res.reasons[0]


def test_ctrl_4_reflection_rejection() -> None:
    """CTRL-4: Mirrored CAD geometry (flipped across Y axis) fails with reflection error."""
    cad_pts = [(50.0, 50.0), (200.0, 50.0), (200.0, 150.0), (50.0, 150.0)]
    # Target is flipped in x: ref_x = -cad_x
    ref_pts = [(-x, y) for x, y in cad_pts]

    anchors = [
        AnchorPair(f"D{i}", ref_pts[i], cad_pts[i], "DATUM", 1.0)
        for i in range(len(cad_pts))
    ]

    res = estimate_similarity_strategy_d(anchors)
    assert res.status == "FAILED"
    assert "reflection is not an allowed alignment" in res.reasons[0]


def test_ctrl_5_unsupported_authority_rejection() -> None:
    """CTRL-5: Unsupported authority string fails validation."""
    anchors = [
        AnchorPair("A", (50.0, 50.0), (50.0, 50.0), "DATUM", 1.0),
        AnchorPair("B", (200.0, 50.0), (200.0, 50.0), "USER_SPECIFIED_TOLERANCE", 1.0),
    ]

    res = estimate_similarity_strategy_d(anchors)
    assert res.status == "FAILED"
    assert "unsupported anchor authority" in res.reasons[0]


def test_ctrl_6_low_confidence_visual_feature_rejection() -> None:
    """CTRL-6: VISUAL_FEATURE with confidence < 0.8 is pruned; if too few remain, fails."""
    anchors = [
        AnchorPair("VF1", (50.0, 50.0), (50.0, 50.0), "VISUAL_FEATURE", 0.75),  # < 0.8
        AnchorPair("VF2", (200.0, 50.0), (200.0, 50.0), "VISUAL_FEATURE", 0.70),  # < 0.8
        AnchorPair("VF3", (100.0, 100.0), (100.0, 100.0), "VISUAL_FEATURE", 0.60),  # < 0.8
    ]

    res = estimate_similarity_strategy_d(anchors)
    assert res.status == "FAILED"
    assert "no anchors meet the approved authority and confidence policy" in res.reasons[0]


def test_ctrl_7_eight_point_photograph_homography() -> None:
    """CTRL-7: N=8 perspective anchors across a 3D bounding envelope."""
    cad_pts = [
        (0.0, 0.0), (100.0, 0.0), (200.0, 0.0),
        (0.0, 100.0), (200.0, 100.0),
        (0.0, 200.0), (100.0, 200.0), (200.0, 200.0),
    ]
    ref_pts = []
    for x, y in cad_pts:
        denom = 0.0003 * x + 0.0002 * y + 1.0
        ref_pts.append(((1.05 * x + 0.02 * y + 10.0) / denom, (0.01 * x + 1.08 * y + 15.0) / denom))

    anchors = [
        AnchorPair(f"K{i}", ref_pts[i], cad_pts[i], "VISUAL_FEATURE", 0.9)
        for i in range(len(cad_pts))
    ]

    res = estimate_photograph_strategy_d(anchors, source_is_photograph=True)
    assert res.status == "ALIGNED"
    assert res.matrix is not None
    assert len(res.matrix) == 3
    assert len(res.matrix[0]) == 3
    assert res.residual_rms_px is not None
    assert res.residual_rms_px < 0.5


def test_ctrl_8_dark_background_with_border_noise() -> None:
    """CTRL-8: Black background image with 10% white noise pixels on border and white center."""
    h, w = 100, 100
    img = np.zeros((h, w), dtype=np.uint8)
    # Add white noise on border (40 pixels out of 400 perimeter = 10%)
    img[0, 10:30] = 255
    img[-1, 10:30] = 255
    # Add white foreground rectangle in center
    img[40:60, 40:60] = 255

    res = normalize_outline_strategy_d(img)
    # Should maintain polarity without inversion: center remains white (255)
    assert np.mean(res[40:60, 40:60] == 255) > 0.95
    # Corners remain black (0)
    assert np.mean(res[0:10, 0:10] == 0) > 0.95
