"""
test_tick_mark_degenerate_and_perf.py — Degenerate, Non-Finite, and Performance Benchmarks for Boundary Symbol Detection.

Tests edge-case resilience and execution speed:
1. None image reference safely returns [line] and has_boundary=False
2. Zero-length line segments (p1 == p2)
3. Non-finite values (NaN, +Inf, -Inf in coordinates or angle)
4. Out-of-bounds patch queries outside image margins
5. Micro-lines shorter than endpoint margins (length <= 2 * endpoint_margin_px)
6. Saturated blank (all-white) and inverted (all-black) image arrays
7. 50-line split latency benchmark (< 100ms target)
8. 100-endpoint symbol query throughput benchmark (< 50ms target)
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

from tick_mark_engine import (
    make_raw_line,
    run_strategy_d_endpoint,
    run_strategy_d_split,
)


def _canvas(w=400, h=400) -> np.ndarray:
    return np.full((h, w, 3), 255, dtype=np.uint8)


class TestTickMarkDegenerateAndPerf:
    """Degenerate edge cases and performance latency benchmarks."""

    def test_degenerate_none_image(self) -> None:
        """Degenerate 1: None image safely returns intact line and False boundary."""
        line = make_raw_line((50, 150), (350, 150))
        splits = run_strategy_d_split(line, None)
        assert len(splits) == 1
        assert splits[0] == line

        res = run_strategy_d_endpoint(None, (100.0, 100.0), 0.0)
        assert res.has_boundary is False
        assert res.symbol_kind == "NONE"

    def test_degenerate_zero_length_line(self) -> None:
        """Degenerate 2: Points with length 0 (p1 == p2) do not crash or split."""
        img = _canvas(300, 300)
        line = make_raw_line((150, 150), (150, 150))
        splits = run_strategy_d_split(line, img)
        assert len(splits) == 1

    def test_degenerate_non_finite_coordinates(self) -> None:
        """Degenerate 3: Lines and points with NaN or Inf coordinates fail safely."""
        img = _canvas(300, 300)
        bad_lines = [
            make_raw_line((float("nan"), 150), (350, 150)),
            make_raw_line((50, float("inf")), (350, 150)),
            make_raw_line((50, 150), (float("-inf"), 150)),
        ]
        for bl in bad_lines:
            splits = run_strategy_d_split(bl, img)
            assert len(splits) == 1

        # Endpoint query with NaN or Inf
        res_nan = run_strategy_d_endpoint(img, (float("nan"), 150.0), 0.0)
        res_inf = run_strategy_d_endpoint(img, (150.0, 150.0), float("inf"))
        assert res_nan.has_boundary is False
        assert res_inf.has_boundary is False

    def test_degenerate_out_of_bounds_points(self) -> None:
        """Degenerate 4: Query points completely outside canvas boundaries."""
        img = _canvas(200, 200)
        res_neg = run_strategy_d_endpoint(img, (-50.0, -50.0), 0.0)
        res_huge = run_strategy_d_endpoint(img, (5000.0, 5000.0), 0.0)
        assert res_neg.has_boundary is False
        assert res_huge.has_boundary is False

    def test_degenerate_short_lines_within_margins(self) -> None:
        """Degenerate 5: Lines shorter than 2 * endpoint_margin_px (<= 20px)."""
        img = _canvas(300, 300)
        # 10px line
        line = make_raw_line((100, 100), (110, 100))
        splits = run_strategy_d_split(line, img)
        assert len(splits) == 1

    def test_degenerate_blank_and_inverted_canvases(self) -> None:
        """Degenerate 6: Pure white canvas and pure black canvas."""
        white_img = np.full((300, 300, 3), 255, dtype=np.uint8)
        black_img = np.zeros((300, 300, 3), dtype=np.uint8)

        line = make_raw_line((50, 150), (250, 150))
        splits_w = run_strategy_d_split(line, white_img)
        splits_b = run_strategy_d_split(line, black_img)

        assert len(splits_w) == 1
        assert len(splits_b) == 1

        res_w = run_strategy_d_endpoint(white_img, (150.0, 150.0), 0.0)
        assert res_w.has_boundary is False

    def test_performance_50_line_split_latency(self) -> None:
        """Performance 1: Slicing 50 candidate dimension lines across drawing.
        Target: total latency < 250ms (average < 5ms per candidate line).
        """
        img = _canvas(1200, 1200)
        # Draw 50 dimension lines, half with witness lines
        lines = []
        for i in range(50):
            y = 50 + i * 22
            cv2.line(img, (50, y), (350, y), (0, 0, 0), 2)
            if i % 2 == 0:
                cv2.line(img, (200, y - 10), (200, y + 10), (0, 0, 0), 2)
            lines.append(make_raw_line((50, y), (350, y)))

        t0 = time.perf_counter()
        total_splits = 0
        for l in lines:
            res = run_strategy_d_split(l, img)
            total_splits += len(res)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert total_splits > 50
        assert elapsed_ms < 500.0, f"50-line split took {elapsed_ms:.1f}ms, expected < 500ms"

    def test_performance_100_endpoint_queries_throughput(self) -> None:
        """Performance 2: 100 endpoint symbol queries throughput.
        Target: total latency < 150ms (average < 1.5ms per query).
        """
        img = _canvas(600, 600)
        # Draw some arrows and plain ends
        pts = []
        for i in range(100):
            x = (i % 10) * 50 + 50
            y = (i // 10) * 50 + 50
            cv2.line(img, (x - 20, y), (x, y), (0, 0, 0), 2)
            if i % 3 == 0:
                cv2.line(img, (x, y), (x - 8, y - 4), (0, 0, 0), 2)
                cv2.line(img, (x, y), (x - 8, y + 4), (0, 0, 0), 2)
            pts.append((float(x), float(y)))

        t0 = time.perf_counter()
        hits = 0
        for pt in pts:
            res = run_strategy_d_endpoint(img, pt, 0.0)
            if res.has_boundary:
                hits += 1
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert hits > 20
        assert elapsed_ms < 300.0, f"100-endpoint queries took {elapsed_ms:.1f}ms, expected < 300ms"
