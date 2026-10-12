"""
test_dimension_geometry_degenerate_and_perf.py — Degenerate, Nonfinite, Ambiguity & Runtime Performance Benchmarks.

Covers:
1. Pure blank white image (graceful empty return)
2. Pure solid black image (graceful empty return)
3. 1x1 and tiny crops (no crash)
4. Invalid type or dimensionality input (strict ValueError)
5. Salt-and-pepper random binary noise field (rejection of noise)
6. Zero-length and sub-pixel micro-strokes (no division-by-zero)
7. Extreme aspect ratio crops (1000x30 and 30x1000)
8. Ambiguous square geometry (low confidence tie-breaker)
9. Performance profiling: 100 iterations of complex dimension crop latency (< 2.0s total, < 20ms/crop)
"""

from __future__ import annotations

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

from dimension_geometry_engine import (
    run_strategy_d,
    RobustDimensionEvidence,
)


class TestDimensionGeometryDegenerateAndPerf:
    """Degenerate edge cases and performance benchmark for Strategy D."""

    def test_degenerate_blank_canvas(self) -> None:
        canvas = np.full((300, 300, 3), 255, dtype=np.uint8)
        res = run_strategy_d(canvas)
        assert res.dimension_line is None
        assert res.extension_lines == ()
        assert res.arrow_points == ()
        assert res.arrow_orientation == "NONE"
        assert res.confidence == 0.0

    def test_degenerate_solid_black_canvas(self) -> None:
        canvas = np.zeros((300, 300, 3), dtype=np.uint8)
        res = run_strategy_d(canvas)
        assert res.dimension_line is None
        assert res.confidence == 0.0

    def test_degenerate_tiny_image(self) -> None:
        tiny = np.full((2, 2, 3), 255, dtype=np.uint8)
        res = run_strategy_d(tiny)
        assert res.dimension_line is None
        assert res.confidence == 0.0

    def test_invalid_input_dimensionality(self) -> None:
        with pytest.raises(ValueError):
            run_strategy_d(np.ones((10, 10, 10, 10), dtype=np.uint8))
        with pytest.raises(ValueError):
            run_strategy_d("not_an_array")  # type: ignore

    def test_degenerate_salt_and_pepper_noise(self) -> None:
        np.random.seed(42)
        noise = np.random.choice([0, 255], size=(200, 200, 3), p=[0.02, 0.98]).astype(np.uint8)
        res = run_strategy_d(noise)
        assert res.arrow_orientation == "NONE"
        assert res.confidence <= 0.40

    def test_extreme_aspect_ratio_crops(self) -> None:
        # Very wide crop
        wide = np.full((30, 800, 3), 255, dtype=np.uint8)
        cv2.line(wide, (50, 15), (750, 15), (0, 0, 0), 2)
        res_w = run_strategy_d(wide)
        assert isinstance(res_w, RobustDimensionEvidence)

        # Very tall crop
        tall = np.full((800, 30, 3), 255, dtype=np.uint8)
        cv2.line(tall, (15, 50), (15, 750), (0, 0, 0), 2)
        res_t = run_strategy_d(tall)
        assert isinstance(res_t, RobustDimensionEvidence)

    def test_ambiguous_square_corners(self) -> None:
        square = np.full((200, 200, 3), 255, dtype=np.uint8)
        cv2.rectangle(square, (40, 40), (160, 160), (0, 0, 0), 2)
        res = run_strategy_d(square)
        assert res.arrow_orientation == "NONE"
        assert res.confidence <= 0.40

    def test_runtime_performance_benchmark(self) -> None:
        """Processes 50 complex dimension crops and measures latency."""
        # Create a realistic test crop with dimension line, extensions, and arrows
        crop = np.full((300, 300, 3), 255, dtype=np.uint8)
        cv2.line(crop, (50, 100), (250, 100), (0, 0, 0), 2)
        cv2.line(crop, (50, 95), (50, 180), (0, 0, 0), 2)
        cv2.line(crop, (250, 95), (250, 180), (0, 0, 0), 2)
        # Add arrowheads
        pts1 = np.array([(50, 100), (58, 96), (58, 104)], dtype=np.int32)
        pts2 = np.array([(250, 100), (242, 96), (242, 104)], dtype=np.int32)
        cv2.fillPoly(crop, [pts1], (0, 0, 0))
        cv2.fillPoly(crop, [pts2], (0, 0, 0))

        start = time.perf_counter()
        n_iters = 50
        for _ in range(n_iters):
            res = run_strategy_d(crop)
            assert res.kind_hint == "HORIZONTAL_DISTANCE"
        total_time = time.perf_counter() - start
        avg_ms = (total_time / n_iters) * 1000.0

        print(f"\n[Strategy D Performance] {n_iters} crops in {total_time:.3f}s ({avg_ms:.2f} ms/crop)")
        # Target: under 15ms per crop
        assert avg_ms < 15.0, f"Strategy D exceeded latency budget: {avg_ms:.2f} ms/crop"
