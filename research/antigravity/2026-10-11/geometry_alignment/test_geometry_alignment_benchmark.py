"""test_geometry_alignment_benchmark.py - Empirical Multi-Strategy Benchmark.

Compares Strategies A, B, C, and D across 8 geometry alignment scenarios:
1. Scenario 1: Clean multi-datum similarity alignment (4 DATUM anchors).
2. Scenario 2: Single DATUM + 3 DRIVING_DIMENSION (highest-tier starvation).
3. Scenario 3: Single DATUM + 0 DIM + 3 STABLE_ENTITY (3-tier cascade requirement).
4. Scenario 4: N=5 perspective photograph homography anchors.
5. Scenario 5: N=3 collinear anchors along horizontal axis.
6. Scenario 6: Inverted outline with 12% border frame noise / text line crossings.
7. Scenario 7: Metric trend comparison with large IoU gain (+0.25) and +2 component count jump.
8. Scenario 8: Pure edge regression (missing edges jump) without component count change.

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
    compare_metric_trend_strategy_b,
    compare_metric_trend_strategy_c,
    compare_metric_trend_strategy_d,
    estimate_photograph_strategy_a,
    estimate_photograph_strategy_d,
    estimate_similarity_strategy_a,
    estimate_similarity_strategy_b,
    estimate_similarity_strategy_c,
    estimate_similarity_strategy_d,
    normalize_outline_strategy_a,
    normalize_outline_strategy_b,
    normalize_outline_strategy_c,
    normalize_outline_strategy_d,
)


def scenario_1_clean_datum_anchors() -> list[AnchorPair]:
    """Clean 4 DATUM anchors spanning 2D."""
    return [
        AnchorPair("A", (50.0, 50.0), (50.0, 50.0), "DATUM", 1.0),
        AnchorPair("B", (250.0, 50.0), (250.0, 50.0), "DATUM", 1.0),
        AnchorPair("C", (250.0, 180.0), (250.0, 180.0), "DATUM", 1.0),
        AnchorPair("D", (50.0, 180.0), (50.0, 180.0), "DATUM", 1.0),
    ]


def scenario_2_single_datum_plus_dimensions() -> list[AnchorPair]:
    """1 DATUM + 3 DRIVING_DIMENSION anchors."""
    return [
        AnchorPair("DATUM_1", (100.0, 100.0), (100.0, 100.0), "DATUM", 1.0),
        AnchorPair("DIM_1", (300.0, 100.0), (300.0, 100.0), "DRIVING_DIMENSION", 1.0),
        AnchorPair("DIM_2", (300.0, 200.0), (300.0, 200.0), "DRIVING_DIMENSION", 1.0),
        AnchorPair("DIM_3", (100.0, 200.0), (100.0, 200.0), "DRIVING_DIMENSION", 1.0),
    ]


def scenario_3_three_tier_cascade() -> list[AnchorPair]:
    """1 DATUM + 0 DIM + 3 STABLE_ENTITY (requires tier 4 -> tier 2 cascade)."""
    return [
        AnchorPair("DATUM_1", (100.0, 100.0), (100.0, 100.0), "DATUM", 1.0),
        AnchorPair("ENTITY_1", (300.0, 100.0), (300.0, 100.0), "STABLE_ENTITY", 1.0),
        AnchorPair("ENTITY_2", (300.0, 200.0), (300.0, 200.0), "STABLE_ENTITY", 1.0),
        AnchorPair("ENTITY_3", (100.0, 200.0), (100.0, 200.0), "STABLE_ENTITY", 1.0),
    ]


def scenario_4_five_point_photograph_anchors() -> list[AnchorPair]:
    """5 perspective photograph anchors."""
    cad = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0), (50.0, 50.0)]
    ref = []
    for x, y in cad:
        denom = 0.0004 * x + 0.0003 * y + 1.0
        ref.append(((1.1 * x + 0.05 * y + 15.0) / denom, (0.02 * x + 1.15 * y + 25.0) / denom))
    return [
        AnchorPair(f"P{i}", ref[i], cad[i], "VISUAL_FEATURE", 0.95)
        for i in range(len(cad))
    ]


def scenario_5_collinear_anchors() -> list[AnchorPair]:
    """3 collinear anchors along y = 100."""
    cad = [(50.0, 100.0), (150.0, 100.0), (300.0, 100.0)]
    # Target scaled by 1.10 and shifted +10 in x, +5 in y
    ref = [(x * 1.10 + 10.0, y * 1.10 + 5.0) for x, y in cad]
    return [
        AnchorPair(f"C{i}", ref[i], cad[i], "DRIVING_DIMENSION", 1.0)
        for i in range(len(cad))
    ]


def scenario_6_noisy_border_image() -> np.ndarray:
    """White image with 12% black border line noise and black centered rectangle."""
    img = np.full((100, 100), 255, dtype=np.uint8)
    # Perimeter is 400px. 12% = 48px of black border line segments
    img[0, 10:34] = 0
    img[-1, 10:34] = 0
    # Foreground rectangle in center
    img[35:65, 35:65] = 0
    return img


def test_scenario_1_clean_datum_similarity() -> None:
    anchors = scenario_1_clean_datum_anchors()
    ra = estimate_similarity_strategy_a(anchors)
    rb = estimate_similarity_strategy_b(anchors)
    rc = estimate_similarity_strategy_c(anchors)
    rd = estimate_similarity_strategy_d(anchors)

    assert ra.status == "ALIGNED"
    assert rb.status == "ALIGNED"
    assert rc.status == "ALIGNED"
    assert rd.status == "ALIGNED"


def test_scenario_2_tier_starvation() -> None:
    anchors = scenario_2_single_datum_plus_dimensions()
    ra = estimate_similarity_strategy_a(anchors)
    rc = estimate_similarity_strategy_c(anchors)
    rd = estimate_similarity_strategy_d(anchors)

    assert ra.status == "FAILED"  # Strategy A drops tier 3, leaving 1 anchor
    assert rc.status == "ALIGNED"  # Strategy C takes top 2 tiers (tier 4 + tier 3)
    assert rd.status == "ALIGNED"  # Strategy D cascades to accumulate 4 anchors


def test_scenario_3_three_tier_cascade() -> None:
    anchors = scenario_3_three_tier_cascade()
    ra = estimate_similarity_strategy_a(anchors)
    rc = estimate_similarity_strategy_c(anchors)
    rd = estimate_similarity_strategy_d(anchors)

    assert ra.status == "FAILED"  # 1 DATUM kept
    assert rc.status == "FAILED"  # Top 2 tiers are DATUM (1) and DIM (0) -> 1 kept, fails!
    assert rd.status == "ALIGNED"  # Cascades to tier 2 (STABLE_ENTITY), accumulating 4


def test_scenario_4_photograph_homography_five_anchors() -> None:
    anchors = scenario_4_five_point_photograph_anchors()
    ra = estimate_photograph_strategy_a(anchors, source_is_photograph=True)
    rd = estimate_photograph_strategy_d(anchors, source_is_photograph=True)

    assert ra.status == "FAILED"  # strictly requires exactly 4
    assert rd.status == "ALIGNED"  # handles N=5 least squares DLT
    assert rd.residual_rms_px is not None
    assert rd.residual_rms_px < 0.5


def test_scenario_5_collinear_axis_anchors() -> None:
    anchors = scenario_5_collinear_anchors()
    ra = estimate_similarity_strategy_a(anchors)
    rc = estimate_similarity_strategy_c(anchors)
    rd = estimate_similarity_strategy_d(anchors)

    assert ra.status == "FAILED"  # rank < 2 check fails
    assert rc.status == "FAILED"  # rank < 2 check fails
    assert rd.status == "ALIGNED"  # 1D principal axis solves
    assert rd.residual_rms_px is not None
    assert rd.residual_rms_px < 0.05


def test_scenario_6_noisy_border_polarity() -> None:
    img = scenario_6_noisy_border_image()

    with pytest.raises(ValueError):
        normalize_outline_strategy_a(img)

    with pytest.raises(ValueError):
        normalize_outline_strategy_c(img)

    res_b = normalize_outline_strategy_b(img)
    # Strategy B didn't invert, so center is still 0 (black), background is 255 (white)
    assert np.mean(res_b[35:65, 35:65] == 0) > 0.95

    res_d = normalize_outline_strategy_d(img)
    # Strategy D correctly inverted: center foreground is white (255)
    assert np.mean(res_d[35:65, 35:65] == 255) > 0.95


def test_scenario_7_metric_trend_iou_gain_with_component_jump() -> None:
    prev = {
        "silhouette_iou": 0.60,
        "chamfer_distance_normalized": 9.0,
        "hausdorff_p95_normalized": 14.0,
        "missing_edge_ratio": 0.25,
        "extra_edge_ratio": 0.20,
        "connected_component_difference": 0,
    }
    curr = {
        "silhouette_iou": 0.88,  # +0.28 gain
        "chamfer_distance_normalized": 1.2,
        "hausdorff_p95_normalized": 2.0,
        "missing_edge_ratio": 0.02,
        "extra_edge_ratio": 0.02,
        "connected_component_difference": 2,  # +2 component jump
    }

    ta = compare_metric_trend_strategy_a(curr, prev)
    tb = compare_metric_trend_strategy_b(curr, prev)
    tc = compare_metric_trend_strategy_c(curr, prev)
    td = compare_metric_trend_strategy_d(curr, prev)

    assert ta == "REGRESSED"  # Strategy A trapped by component diff
    assert tb == "IMPROVED"  # Strategy B only looks at IoU
    assert tc == "REGRESSED"  # Strategy C trapped by component diff > 1
    assert td == "IMPROVED"  # Strategy D absorbs component diff due to +0.28 IoU gain


def test_scenario_8_pure_edge_regression() -> None:
    prev = {
        "silhouette_iou": 0.85,
        "chamfer_distance_normalized": 2.0,
        "hausdorff_p95_normalized": 3.0,
        "missing_edge_ratio": 0.05,
        "extra_edge_ratio": 0.04,
        "connected_component_difference": 0,
    }
    curr = {
        "silhouette_iou": 0.85,
        "chamfer_distance_normalized": 2.0,
        "hausdorff_p95_normalized": 3.0,
        "missing_edge_ratio": 0.18,  # Edge regression
        "extra_edge_ratio": 0.04,
        "connected_component_difference": 0,
    }

    ta = compare_metric_trend_strategy_a(curr, prev)
    tb = compare_metric_trend_strategy_b(curr, prev)
    tc = compare_metric_trend_strategy_c(curr, prev)
    td = compare_metric_trend_strategy_d(curr, prev)

    assert ta == "REGRESSED"
    assert tb == "UNCHANGED"  # Strategy B is blind to edge regressions
    assert tc == "REGRESSED"
    assert td == "REGRESSED"
