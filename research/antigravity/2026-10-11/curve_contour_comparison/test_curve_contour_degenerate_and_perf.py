"""test_curve_contour_degenerate_and_perf.py - Degenerate, Non-finite, and Latency Profiling.

Validates 7 edge and performance cases:
1. EDGE-1: Completely blank mask safe handling (returns FAILED result, no uncaught exception).
2. EDGE-2: Micro-contour noise (< 20 px area filtered safely).
3. EDGE-3: Zero perimeter / coincident points contour handling.
4. EDGE-4: Collinear line contour with zero enclosed area.
5. EDGE-5: Dense high-frequency oscillating zigzag contour numerical stability.
6. EDGE-6: Extreme aspect ratio micro-slit contour.
7. PERF-7: Latency and scalability profiling (128-point cyclic matching < 15 ms, 1000x1000 mask < 50 ms).

Part of Antigravity Research: CURVE_CONTOUR_PROFILE_COMPARISON_V1
"""

from __future__ import annotations

import math
import sys
import time
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
    resample_closed_curve_d,
)


def test_edge_1_blank_mask_safe_failure() -> None:
    """EDGE-1: Blank mask returns clean FAILED result."""
    blank = np.zeros((100, 100), dtype=np.uint8)
    res = compare_curve_profile_strategy_d(blank, blank)
    assert res.status == "FAILED"
    assert "no valid contours" in res.reasons[0]


def test_edge_2_micro_contour_noise_filtered() -> None:
    """EDGE-2: 3-pixel isolated noise blobs (area < 20 px) are filtered out safely."""
    img = np.zeros((100, 100), dtype=np.uint8)
    img[10:12, 10:12] = 255  # 4-pixel micro blob
    contours = extract_all_contours_d(img, min_area_px=20.0)
    assert len(contours) == 0


def test_edge_3_zero_perimeter_safe_handling() -> None:
    """EDGE-3: Coincident duplicate points raise ValueError safely in resampler."""
    coincident = np.array([[50.0, 50.0], [50.0, 50.0], [50.0, 50.0]])
    with pytest.raises(ValueError, match="zero or non-finite perimeter length"):
        resample_closed_curve_d(coincident)


def test_edge_4_collinear_zero_area_contour() -> None:
    """EDGE-4: Straight 1D line drawn in binary mask has zero contour area; filtered safely."""
    img = np.zeros((100, 100), dtype=np.uint8)
    cv2.line(img, (20, 50), (80, 50), 255, 1)
    contours = extract_all_contours_d(img, min_area_px=20.0)
    assert len(contours) == 0


def test_edge_5_dense_zigzag_numerical_stability() -> None:
    """EDGE-5: High-frequency alternating zigzag contour executes without float overflow."""
    h, w = 200, 200
    img = np.zeros((h, w), dtype=np.uint8)
    pts = []
    for x in range(30, 170, 5):
        y = 50 if (x // 5) % 2 == 0 else 70
        pts.append([x, y])
    pts.append([165, 120])
    pts.append([30, 120])
    cv2.fillPoly(img, [np.array(pts, dtype=np.int32)], 255)

    res = compare_curve_profile_strategy_d(img, img)
    assert res.status == "ALIGNED"
    assert math.isfinite(res.curvature_p95)
    assert res.curvature_p95 <= 0.05


def test_edge_6_extreme_aspect_ratio_slit() -> None:
    """EDGE-6: Long thin slit (100 px long by 2 px wide) evaluates stably."""
    img = np.zeros((150, 150), dtype=np.uint8)
    cv2.rectangle(img, (20, 74), (120, 76), 255, -1)
    res = compare_curve_profile_strategy_d(img, img)
    assert res.status == "ALIGNED"
    assert res.curvature_p95 <= 0.05


def test_perf_7_latency_and_scalability() -> None:
    """PERF-7: Latency benchmark across 128-sample cyclic alignment and 1000x1000 masks."""
    # 1. Cyclic profile alignment for 128 points
    h, w = 200, 200
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(ref, (100, 100), 50, 255, -1)
    cad = ref.copy()

    t0 = time.perf_counter()
    res = compare_curve_profile_strategy_d(ref, cad, count=128)
    t_128_ms = (time.perf_counter() - t0) * 1000.0
    assert res.status == "ALIGNED"
    assert t_128_ms < 15.0  # Under 15ms for 128-point cyclic cross correlation

    # 2. Multi-contour extraction on 6-hole mounting plate
    plate = np.zeros((300, 300), dtype=np.uint8)
    cv2.rectangle(plate, (20, 20), (280, 280), 255, -1)
    for cx in (80, 150, 220):
        for cy in (100, 200):
            cv2.circle(plate, (cx, cy), 18, 0, -1)

    t0 = time.perf_counter()
    contours = extract_all_contours_d(plate, min_area_px=20.0)
    t_multi_ms = (time.perf_counter() - t0) * 1000.0
    assert len(contours) == 7  # 1 outer plate + 6 bolt holes
    assert t_multi_ms < 25.0  # Under 25ms for multi-contour extraction

    # 3. 1000x1000 image curve comparison
    img_1000 = np.zeros((1000, 1000), dtype=np.uint8)
    cv2.circle(img_1000, (500, 500), 300, 255, -1)
    t0 = time.perf_counter()
    res_1000 = compare_curve_profile_strategy_d(img_1000, img_1000)
    t_1000_ms = (time.perf_counter() - t0) * 1000.0
    assert res_1000.status == "ALIGNED"
    assert t_1000_ms < 50.0  # Under 50ms for 1 megapixel mask
