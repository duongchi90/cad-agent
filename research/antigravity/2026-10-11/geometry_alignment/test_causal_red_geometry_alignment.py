"""test_causal_red_geometry_alignment.py - Public Causal RED for Geometry Alignment and Comparison.

Reproduces 5 baseline failure modes on production geometry_alignment.py & geometry_metrics.py:
1. RED-1: Highest-tier starvation in anchor selection (single DATUM anchor discards valid lower-tier anchors).
2. RED-2: Rigid 0.98 border polarity crash (border lines / noise cause ambiguous polarity exception).
3. RED-3: Strict exactly-four anchor rejection for photograph homography (rejects N=5 or N=6 valid perspective anchors).
4. RED-4: Collinear anchor rank failure on N >= 3 anchors along a single axis.
5. RED-5: Connected component count trap in directional metric trend comparison.

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
    compare_metric_trend_strategy_a,
    compare_metric_trend_strategy_d,
    estimate_photograph_strategy_a,
    estimate_photograph_strategy_d,
    estimate_similarity_strategy_a,
    estimate_similarity_strategy_d,
    normalize_outline_strategy_a,
    normalize_outline_strategy_d,
    select_anchors_strategy_a,
    select_anchors_strategy_d,
)


def test_red_1_highest_tier_starvation_single_datum() -> None:
    """RED-1: Single DATUM anchor discards DRIVING_DIMENSION anchors, causing total alignment failure.

    Scenario: A drawing view has 1 identified DATUM anchor (tier 4) and 3 DRIVING_DIMENSION
    anchors (tier 3). Production Strategy A selects ONLY the highest tier (tier 4),
    leaving exactly 1 anchor, which fails 'at least two anchors are required'.
    """
    anchors = [
        AnchorPair("A_DATUM", (100.0, 100.0), (100.0, 100.0), "DATUM", 1.0),
        AnchorPair("B_DIM", (300.0, 100.0), (300.0, 100.0), "DRIVING_DIMENSION", 1.0),
        AnchorPair("C_DIM", (300.0, 250.0), (300.0, 250.0), "DRIVING_DIMENSION", 1.0),
        AnchorPair("D_DIM", (100.0, 250.0), (100.0, 250.0), "DRIVING_DIMENSION", 1.0),
    ]

    # Strategy A (Production Main)
    selected_a, fail_a = select_anchors_strategy_a(anchors)
    assert fail_a is None
    assert selected_a is not None
    assert len(selected_a) == 1  # Only 1 DATUM retained!
    assert selected_a[0].anchor_id == "A_DATUM"

    res_a = estimate_similarity_strategy_a(anchors)
    assert res_a.status == "FAILED"
    assert "at least two anchors are required" in res_a.reasons[0]

    # Strategy D (Cascading Tier Consensus)
    selected_d, fail_d = select_anchors_strategy_d(anchors, min_anchors_needed=2)
    assert fail_d is None
    assert selected_d is not None
    assert len(selected_d) == 4  # Cascaded down to include tier 3!

    res_d = estimate_similarity_strategy_d(anchors)
    assert res_d.status == "ALIGNED"
    assert res_d.matrix is not None
    assert res_d.residual_rms_px is not None
    assert res_d.residual_rms_px <= 0.01


def test_red_2_rigid_border_polarity_noise_crash() -> None:
    """RED-2: Rigid 0.98 threshold crashes when border frame or noise occupies 2.5% of perimeter.

    Production Strategy A requires black_fraction >= 0.98 or white_fraction >= 0.98.
    If border has 2.5% black lines (e.g. extension line crossing sheet border), white_fraction
    is 0.975, triggering ValueError("foreground polarity is ambiguous").
    """
    h, w = 100, 100
    # Create white image (255)
    img = np.full((h, w), 255, dtype=np.uint8)
    # Add a thin black line crossing the top and bottom borders (taking 5 pixels out of 400 perimeter px = ~1.25% to 2.5%)
    # Perimeter = 100 + 100 + 100 + 100 = 400 pixels
    # Add 12 black pixels along border (3%) -> white fraction = 388 / 400 = 0.97 < 0.98
    img[0, 10:16] = 0
    img[-1, 10:16] = 0
    # Add some foreground object in center
    img[40:60, 40:60] = 0

    # Strategy A crashes
    with pytest.raises(ValueError, match="foreground polarity is ambiguous"):
        normalize_outline_strategy_a(img)

    # Strategy D succeeds via corner patches and inset consensus
    normalized_d = normalize_outline_strategy_d(img)
    assert normalized_d.shape == (h, w)
    # Foreground object in center should be white (255) in normalized output
    assert np.mean(normalized_d[40:60, 40:60] == 255) > 0.95
    # Background should be black (0)
    assert np.mean(normalized_d[0:10, 0:10] == 0) > 0.95


def test_red_3_strict_n4_homography_rejection() -> None:
    """RED-3: Production photograph alignment fails when N > 4 valid perspective anchors are supplied.

    Strategy A rejects N=6 valid perspective anchors with 'photograph alignment requires exactly four anchors'.
    Strategy D uses least-squares DLT homography to solve arbitrary N >= 4.
    """
    # 6 coplanar perspective points
    cad_pts = [
        (0.0, 0.0), (100.0, 0.0), (200.0, 0.0),
        (0.0, 100.0), (100.0, 100.0), (200.0, 100.0),
    ]
    # Perspective projective mapping: x' = (1.2*x + 0.1*y + 10) / (0.0005*x + 1), y' = (0.05*x + 1.1*y + 20) / (0.0005*x + 1)
    ref_pts = []
    for x, y in cad_pts:
        denom = 0.0005 * x + 1.0
        ref_pts.append(((1.2 * x + 0.1 * y + 10.0) / denom, (0.05 * x + 1.1 * y + 20.0) / denom))

    anchors = [
        AnchorPair(f"P{i}", ref_pts[i], cad_pts[i], "VISUAL_FEATURE", 0.9)
        for i in range(len(cad_pts))
    ]

    # Strategy A
    res_a = estimate_photograph_strategy_a(anchors, source_is_photograph=True)
    assert res_a.status == "FAILED"
    assert "photograph alignment requires exactly four anchors" in res_a.reasons[0]

    # Strategy D
    res_d = estimate_photograph_strategy_d(anchors, source_is_photograph=True)
    assert res_d.status == "ALIGNED"
    assert res_d.matrix is not None
    assert res_d.residual_rms_px is not None
    assert res_d.residual_rms_px < 0.5


def test_red_4_collinear_anchors_rank_failure() -> None:
    """RED-4: N >= 3 collinear anchors fail 2D rank check in Production Strategy A.

    3 anchors along a horizontal datum line: (50, 100), (150, 100), (250, 100).
    Strategy A: centered rank is 1 < 2 -> fails with 'three or more anchors must span two dimensions'.
    Strategy D: extracts 1D principal axis and solves scale + translation accurately.
    """
    cad_pts = [(50.0, 100.0), (150.0, 100.0), (250.0, 100.0)]
    # Target scaled by 1.25 and shifted by +20 in x, +10 in y
    ref_pts = [(50.0 * 1.25 + 20.0, 100.0 * 1.25 + 10.0),
               (150.0 * 1.25 + 20.0, 100.0 * 1.25 + 10.0),
               (250.0 * 1.25 + 20.0, 100.0 * 1.25 + 10.0)]

    anchors = [
        AnchorPair("A", ref_pts[0], cad_pts[0], "DRIVING_DIMENSION", 1.0),
        AnchorPair("B", ref_pts[1], cad_pts[1], "DRIVING_DIMENSION", 1.0),
        AnchorPair("C", ref_pts[2], cad_pts[2], "DRIVING_DIMENSION", 1.0),
    ]

    # Strategy A
    res_a = estimate_similarity_strategy_a(anchors)
    assert res_a.status == "FAILED"
    assert "three or more anchors must span two dimensions" in res_a.reasons[0]

    # Strategy D
    res_d = estimate_similarity_strategy_d(anchors)
    assert res_d.status == "ALIGNED"
    assert res_d.matrix is not None
    assert res_d.residual_rms_px is not None
    assert res_d.residual_rms_px < 0.05
    # Verify scale is ~1.25
    s = math.hypot(res_d.matrix[0][0], res_d.matrix[0][1])
    assert abs(s - 1.25) < 1e-4


def test_red_5_component_count_trap_in_metric_trend() -> None:
    """RED-5: Increase in connected_component_difference falsely rejects huge IoU gain.

    Scenario: A repair repairs outline geometry dramatically (IoU 0.65 -> 0.90, Chamfer 8.0 -> 1.5,
    missing edge 0.20 -> 0.02). However, a single small tick mark detaches, increasing
    connected_component_difference from 0 to 1.
    Production Strategy A flags REGRESSED unconditionally.
    Strategy D gates the component count check on IoU gain, correctly concluding IMPROVED.
    """
    prev = {
        "silhouette_iou": 0.65,
        "chamfer_distance_normalized": 8.0,
        "hausdorff_p95_normalized": 12.0,
        "missing_edge_ratio": 0.20,
        "extra_edge_ratio": 0.15,
        "connected_component_difference": 0,
    }
    curr = {
        "silhouette_iou": 0.90,
        "chamfer_distance_normalized": 1.5,
        "hausdorff_p95_normalized": 2.5,
        "missing_edge_ratio": 0.02,
        "extra_edge_ratio": 0.02,
        "connected_component_difference": 1,  # +1 component diff
    }

    # Strategy A
    trend_a = compare_metric_trend_strategy_a(curr, prev)
    assert trend_a == "REGRESSED"

    # Strategy D
    trend_d = compare_metric_trend_strategy_d(curr, prev)
    assert trend_d == "IMPROVED"
