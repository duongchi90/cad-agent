"""test_geometry_alignment_degenerate_and_perf.py - Degenerate, Non-finite, and Latency Profiling.

Validates 7 edge and performance cases:
1. EDGE-1: Empty anchor sequence safe handling (returns FAILED result, no uncaught exception).
2. EDGE-2: Duplicate anchor IDs and duplicate coordinate points rejection.
3. EDGE-3: Non-finite coordinates (NaN, Inf) in anchor points.
4. EDGE-4: Non-finite or out-of-range confidence values (< 0, > 1, NaN).
5. EDGE-5: Extreme coordinates (10^6 px) numerical stability.
6. EDGE-6: Zero-spread coincident anchor points safe handling.
7. PERF-7: Latency and scalability profiling (100 similarity anchors, 50 homography anchors, 1000x1000 image).

Part of Antigravity Research: RESTRICTED_GEOMETRY_ALIGNMENT_AND_COMPARISON_V1
"""

from __future__ import annotations

import math
import sys
import time
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


def test_edge_1_empty_anchors_safe_failure() -> None:
    """EDGE-1: Empty anchors sequence returns clean failure."""
    res = estimate_similarity_strategy_d([])
    assert res.status == "FAILED"
    assert "no anchors meet the approved authority" in res.reasons[0]


def test_edge_2_duplicate_ids_and_points_rejected() -> None:
    """EDGE-2: Duplicate anchor IDs and duplicate points fail validation."""
    # Duplicate ID
    anchors_dup_id = [
        AnchorPair("A", (10.0, 10.0), (10.0, 10.0), "DATUM", 1.0),
        AnchorPair("A", (20.0, 20.0), (20.0, 20.0), "DATUM", 1.0),
    ]
    res_id = estimate_similarity_strategy_d(anchors_dup_id)
    assert res_id.status == "FAILED"
    assert "duplicate anchor IDs" in res_id.reasons[0]

    # Duplicate Point
    anchors_dup_pt = [
        AnchorPair("A", (10.0, 10.0), (10.0, 10.0), "DATUM", 1.0),
        AnchorPair("B", (10.0, 10.0), (20.0, 20.0), "DATUM", 1.0),
    ]
    res_pt = estimate_similarity_strategy_d(anchors_dup_pt)
    assert res_pt.status == "FAILED"
    assert "duplicate reference points" in res_pt.reasons[0]


def test_edge_3_non_finite_coordinates_rejected() -> None:
    """EDGE-3: NaN and Inf coordinate points are rejected."""
    anchors_nan = [
        AnchorPair("A", (float("nan"), 10.0), (10.0, 10.0), "DATUM", 1.0),
        AnchorPair("B", (20.0, 20.0), (20.0, 20.0), "DATUM", 1.0),
    ]
    res_nan = estimate_similarity_strategy_d(anchors_nan)
    assert res_nan.status == "FAILED"
    assert "anchor points must be finite" in res_nan.reasons[0]

    anchors_inf = [
        AnchorPair("A", (float("inf"), 10.0), (10.0, 10.0), "DATUM", 1.0),
        AnchorPair("B", (20.0, 20.0), (20.0, 20.0), "DATUM", 1.0),
    ]
    res_inf = estimate_similarity_strategy_d(anchors_inf)
    assert res_inf.status == "FAILED"
    assert "anchor points must be finite" in res_inf.reasons[0]


def test_edge_4_invalid_confidence_values_rejected() -> None:
    """EDGE-4: Confidences < 0, > 1, or NaN fail validation."""
    for bad_conf in [-0.1, 1.5, float("nan")]:
        anchors = [
            AnchorPair("A", (10.0, 10.0), (10.0, 10.0), "DATUM", bad_conf),
            AnchorPair("B", (20.0, 20.0), (20.0, 20.0), "DATUM", 1.0),
        ]
        res = estimate_similarity_strategy_d(anchors)
        assert res.status == "FAILED"
        assert "anchor confidence must be finite in [0, 1]" in res.reasons[0]


def test_edge_5_extreme_coordinates_numerical_stability() -> None:
    """EDGE-5: Coordinates at 10^6 px scale resolve without numerical overflow."""
    scale = 1.05
    offset = 1_000_000.0
    cad_pts = [(offset + 100.0, offset + 100.0),
               (offset + 500.0, offset + 100.0),
               (offset + 500.0, offset + 400.0),
               (offset + 100.0, offset + 400.0)]
    ref_pts = [(x * scale, y * scale) for x, y in cad_pts]

    anchors = [
        AnchorPair(f"E{i}", ref_pts[i], cad_pts[i], "DATUM", 1.0)
        for i in range(len(cad_pts))
    ]

    res = estimate_similarity_strategy_d(anchors)
    assert res.status == "ALIGNED"
    assert res.matrix is not None
    assert res.residual_rms_px is not None
    assert res.residual_rms_px < 0.1


def test_edge_6_coincident_points_rejection() -> None:
    """EDGE-6: Distinct IDs but coincident CAD points fail validation."""
    anchors = [
        AnchorPair("A", (10.0, 10.0), (50.0, 50.0), "DATUM", 1.0),
        AnchorPair("B", (20.0, 20.0), (50.0, 50.0), "DATUM", 1.0),  # Duplicate CAD point
    ]
    res = estimate_similarity_strategy_d(anchors)
    assert res.status == "FAILED"
    assert "duplicate CAD points" in res.reasons[0]


def test_perf_7_latency_and_scalability() -> None:
    """PERF-7: Scalability benchmark across large anchor sets and high-resolution images."""
    # 1. 100 anchors similarity alignment
    n_sim = 100
    cad_sim = [(float(i * 10), float((i % 10) * 10)) for i in range(n_sim)]
    ref_sim = [(x * 1.02 + 5.0, y * 1.02 + 8.0) for x, y in cad_sim]
    anchors_sim = [
        AnchorPair(f"S{i:03d}", ref_sim[i], cad_sim[i], "DRIVING_DIMENSION", 1.0)
        for i in range(n_sim)
    ]

    t0 = time.perf_counter()
    res_sim = estimate_similarity_strategy_d(anchors_sim)
    t_sim_ms = (time.perf_counter() - t0) * 1000.0
    assert res_sim.status == "ALIGNED"
    assert t_sim_ms < 15.0  # Under 15ms for 100 anchors

    # 2. 50 anchors homography
    n_homo = 50
    cad_homo = [(float((i % 7) * 20), float((i // 7) * 20)) for i in range(n_homo)]
    ref_homo = []
    for x, y in cad_homo:
        denom = 0.0002 * x + 0.0001 * y + 1.0
        ref_homo.append(((1.05 * x + 0.02 * y + 10.0) / denom, (0.01 * x + 1.04 * y + 12.0) / denom))
    anchors_homo = [
        AnchorPair(f"H{i:03d}", ref_homo[i], cad_homo[i], "VISUAL_FEATURE", 0.9)
        for i in range(n_homo)
    ]

    t0 = time.perf_counter()
    res_homo = estimate_photograph_strategy_d(anchors_homo, source_is_photograph=True)
    t_homo_ms = (time.perf_counter() - t0) * 1000.0
    assert res_homo.status == "ALIGNED"
    assert t_homo_ms < 30.0  # Under 30ms for 50 homography anchors

    # 3. 1000x1000 image outline normalization
    img_1000 = np.full((1000, 1000), 255, dtype=np.uint8)
    img_1000[200:800, 200:800] = 0
    t0 = time.perf_counter()
    norm_img = normalize_outline_strategy_d(img_1000)
    t_img_ms = (time.perf_counter() - t0) * 1000.0
    assert norm_img.shape == (1000, 1000)
    assert t_img_ms < 50.0  # Under 50ms for 1 megapixel image
