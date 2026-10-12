"""
test_view_partitioning_degenerate_and_perf.py — Degenerate, Non-Finite, and Performance Benchmarks.

Tests edge-case resilience and execution speed:
1. Empty inputs (0 lines, 0 texts)
2. Zero-length line segments (p1 == p2)
3. Non-finite values (NaN, +Inf, -Inf in coordinates or image dims)
4. Non-positive image dimensions or DPI (width <= 0, dpi <= 0)
5. Highly fragmented micro-segments (< 5px)
6. Complex multi-view assembly scalability (50 views, 500 lines, latency < 30ms)
7. Batch throughput benchmark (100 drawing runs, latency < 5ms / run)
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from view_partitioning_engine import (
    make_test_line,
    make_test_text,
    run_strategy_d,
)


class TestViewPartitioningDegenerateAndPerf:
    """Degenerate edge cases and latency profiling."""

    def test_degenerate_empty_inputs(self) -> None:
        """Degenerate 1: Empty lists of lines and texts safely return no partition."""
        res = run_strategy_d([], [], 1200, 800, 144)
        assert res.has_valid_partition is False
        assert len(res.views) == 0
        assert res.confidence == 0.0

    def test_degenerate_zero_length_lines(self) -> None:
        """Degenerate 2: Points with length 0 (p1 == p2) do not crash or create phantom views."""
        lines = [
            make_test_line((100, 100), (100, 100)),
            make_test_line((200, 200), (200, 200)),
        ]
        res = run_strategy_d([], lines, 1200, 800, 144)
        assert res.has_valid_partition is False
        assert len(res.views) == 0

    def test_degenerate_non_finite_coordinates(self) -> None:
        """Degenerate 3: Lines, texts, or parameters with NaN or Inf."""
        bad_lines = [
            make_test_line((float("nan"), 100), (300, 100)),
            make_test_line((100, float("inf")), (100, 300)),
            make_test_line((100, 100), (float("-inf"), 300)),
        ]
        res1 = run_strategy_d([], bad_lines, 1200, 800, 144)
        assert res1.has_valid_partition is False

        # Non-finite image dimensions
        res2 = run_strategy_d([], [], float("nan"), 800, 144)
        assert res2.has_valid_partition is False

        # Non-finite DPI
        res3 = run_strategy_d([], [], 1200, 800, float("inf"))
        assert res3.has_valid_partition is False

    def test_degenerate_non_positive_dimensions_or_dpi(self) -> None:
        """Degenerate 4: Zero or negative width, height, or DPI."""
        assert run_strategy_d([], [], 0, 800, 144).has_valid_partition is False
        assert run_strategy_d([], [], 1200, -100, 144).has_valid_partition is False
        assert run_strategy_d([], [], 1200, 800, 0).has_valid_partition is False
        assert run_strategy_d([], [], 1200, 800, -50).has_valid_partition is False

    def test_degenerate_micro_segments_filter(self) -> None:
        """Degenerate 5: Isolated noise dust micro-segments smaller than 5px."""
        lines = [
            make_test_line((100, 100), (103, 100)),
            make_test_line((500, 500), (500, 502)),
        ]
        res = run_strategy_d([], lines, 1200, 800, 144)
        assert res.has_valid_partition is False
        assert len(res.views) == 0

    def test_performance_50_view_complex_assembly(self) -> None:
        """Performance 1: Large format drawing with 50 distinct detail views and 200 lines.
        Latency must be < 30ms (target < 15ms).
        """
        lines = []
        texts = []
        # Create 5x10 grid of 50 views
        for row in range(5):
            for col in range(10):
                x0 = col * 150 + 50
                y0 = row * 150 + 50
                x1 = x0 + 80
                y1 = y0 + 80
                lines.append(make_test_line((x0, y0), (x1, y0)))
                lines.append(make_test_line((x0, y1), (x1, y1)))
                lines.append(make_test_line((x0, y0), (x0, y1)))
                lines.append(make_test_line((x1, y0), (x1, y1)))
                # Scale label
                texts.append(make_test_text("TL 1:1", (x0 + 10, y1 + 10, x0 + 70, y1 + 25), f"lbl-{row}-{col}"))

        # Warm-up
        _ = run_strategy_d(texts, lines, 2000, 1500, 144)

        start = time.perf_counter()
        iters = 5
        for _ in range(iters):
            res = run_strategy_d(texts, lines, 2000, 1500, 144)
        elapsed_ms = (time.perf_counter() - start) / iters * 1000.0

        assert res.has_valid_partition is True
        assert len(res.views) == 50
        assert elapsed_ms < 30.0, f"Expected < 30ms for 50 views, got {elapsed_ms:.2f}ms"

    def test_performance_100_drawing_batch_latency(self) -> None:
        """Performance 2: Batch processing of 100 drawing runs. Latency must be < 5ms / run."""
        lines = [
            make_test_line((100, 100), (400, 100)),
            make_test_line((100, 300), (400, 300)),
            make_test_line((100, 100), (100, 300)),
            make_test_line((400, 100), (400, 300)),
            make_test_line((500, 100), (800, 100)),
            make_test_line((500, 300), (800, 300)),
            make_test_line((500, 100), (500, 300)),
            make_test_line((800, 100), (800, 300)),
        ]
        texts = [
            make_test_text("TL 1:1", (200, 320, 300, 340), "l1"),
            make_test_text("TL 1:2", (600, 320, 700, 340), "l2"),
        ]

        # Warm-up
        _ = run_strategy_d(texts, lines, 1400, 900, 144)

        start = time.perf_counter()
        for _ in range(100):
            res = run_strategy_d(texts, lines, 1400, 900, 144)
        total_ms = (time.perf_counter() - start) * 1000.0
        avg_ms = total_ms / 100.0

        assert res.has_valid_partition is True
        assert len(res.views) == 2
        assert avg_ms < 5.0, f"Expected < 5ms/run, got {avg_ms:.2f}ms"
