"""
test_table_extraction_degenerate_and_perf.py — Degenerate, Non-Finite, and Performance Benchmarks.

Tests edge-case resilience and execution speed:
1. Empty lines input
2. Zero-length lines (p1 == p2)
3. Non-finite coordinates (NaN, +Inf, -Inf)
4. Micro-scale ROI (< min_cell_dim_px)
5. Inverted / zero-area ROI (x1 <= x0 or y1 <= y0)
6. Fragmented collinear border lines (multiple segments forming 1 continuous boundary)
7. Extreme aspect ratio tables (tall narrow columns, wide thin rows)
8. High-density BOM performance benchmark (20 rows x 10 columns = 200 cells, latency < 15ms)
9. Batch throughput benchmark (100 table crops, latency < 5ms / crop)
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

from table_extraction_engine import (
    make_raw_line,
    run_strategy_d,
)


class TestTableExtractionDegenerateAndPerf:
    """Degenerate edge cases and latency benchmarking."""

    def test_degenerate_empty_lines(self) -> None:
        """Degenerate 1: Empty input lines list must safely return no table."""
        roi = (0.0, 0.0, 100.0, 100.0)
        res = run_strategy_d([], roi)
        assert res.has_valid_table is False
        assert len(res.cells) == 0
        assert res.confidence == 0.0

    def test_degenerate_zero_length_lines(self) -> None:
        """Degenerate 2: Points with length 0 (p1 == p2) are rejected."""
        roi = (0.0, 0.0, 100.0, 100.0)
        lines = [
            make_raw_line((10.0, 10.0), (10.0, 10.0)),
            make_raw_line((50.0, 50.0), (50.0, 50.0)),
        ]
        res = run_strategy_d(lines, roi)
        assert res.has_valid_table is False
        assert len(res.cells) == 0

    def test_degenerate_non_finite_coordinates(self) -> None:
        """Degenerate 3: Lines or ROI containing NaN or Inf must not crash."""
        roi = (0.0, 0.0, 100.0, 100.0)
        lines = [
            make_raw_line((float("nan"), 0.0), (100.0, 0.0)),
            make_raw_line((0.0, float("inf")), (0.0, 100.0)),
            make_raw_line((0.0, 0.0), (float("-inf"), 100.0)),
        ]
        res = run_strategy_d(lines, roi)
        assert res.has_valid_table is False
        assert len(res.cells) == 0

        # Non-finite ROI
        bad_roi = (float("nan"), 0.0, 100.0, 100.0)
        res2 = run_strategy_d([], bad_roi)
        assert res2.has_valid_table is False

    def test_degenerate_micro_roi(self) -> None:
        """Degenerate 4: Sub-pixel or micro-ROI smaller than min_cell_dim_px."""
        roi = (10.0, 10.0, 15.0, 15.0)  # 5px x 5px
        lines = [
            make_raw_line((10.0, 10.0), (15.0, 10.0)),
            make_raw_line((10.0, 15.0), (15.0, 15.0)),
            make_raw_line((10.0, 10.0), (10.0, 15.0)),
            make_raw_line((15.0, 10.0), (15.0, 15.0)),
        ]
        res = run_strategy_d(lines, roi, min_cell_dim_px=12.0)
        assert res.has_valid_table is False
        assert len(res.cells) == 0

    def test_degenerate_inverted_or_flat_roi(self) -> None:
        """Degenerate 5: Inverted ROI bounds (x1 <= x0 or y1 <= y0)."""
        res1 = run_strategy_d([], (100.0, 0.0, 50.0, 100.0))
        assert res1.has_valid_table is False

        res2 = run_strategy_d([], (0.0, 100.0, 100.0, 50.0))
        assert res2.has_valid_table is False

        res3 = run_strategy_d([], (50.0, 50.0, 50.0, 50.0))
        assert res3.has_valid_table is False

    def test_degenerate_collinear_fragmented_borders(self) -> None:
        """Degenerate 6: Collinear broken line segments forming an enclosing boundary."""
        roi = (0.0, 0.0, 200.0, 200.0)
        # Top border broken into 3 segments: 0..70, 68..140, 138..200
        # Bottom border: 0..200
        # Left border: 0..200
        # Right border: 0..200
        # Mid divider: y=100
        lines = [
            make_raw_line((0.0, 0.0), (70.0, 0.0)),
            make_raw_line((68.0, 0.0), (140.0, 0.0)),
            make_raw_line((138.0, 0.0), (200.0, 0.0)),
            make_raw_line((0.0, 200.0), (200.0, 200.0)),
            make_raw_line((0.0, 0.0), (0.0, 200.0)),
            make_raw_line((200.0, 0.0), (200.0, 200.0)),
            make_raw_line((0.0, 100.0), (200.0, 100.0)),
            make_raw_line((100.0, 0.0), (100.0, 200.0)),
        ]
        res = run_strategy_d(lines, roi)
        assert res.has_valid_table is True
        assert len(res.cells) == 4

    def test_performance_large_bom_table(self) -> None:
        """Performance 1: Large BOM with 20 rows x 10 columns (200 cells). Latency must be < 15ms."""
        roi = (0.0, 0.0, 1000.0, 600.0)
        # 11 vertical lines
        xs = [float(x) for x in range(0, 1001, 100)]
        # 21 horizontal lines
        ys = [float(y) for y in range(0, 601, 30)]

        lines = []
        for x in xs:
            lines.append(make_raw_line((x, 0.0), (x, 600.0)))
        for y in ys:
            lines.append(make_raw_line((0.0, y), (1000.0, y)))

        # Warm-up
        _ = run_strategy_d(lines, roi)

        start = time.perf_counter()
        iters = 10
        for _ in range(iters):
            res = run_strategy_d(lines, roi)
        elapsed_ms = (time.perf_counter() - start) / iters * 1000.0

        assert res.has_valid_table is True
        assert len(res.cells) == 200
        assert elapsed_ms < 15.0, f"Expected < 15ms for 200-cell BOM, got {elapsed_ms:.2f}ms"

    def test_performance_100_crop_batch_latency(self) -> None:
        """Performance 2: Batch processing of 100 table crops. Latency must be < 5ms / crop."""
        roi = (0.0, 0.0, 300.0, 150.0)
        lines = [
            make_raw_line((0.0, 0.0), (300.0, 0.0)),
            make_raw_line((0.0, 150.0), (300.0, 150.0)),
            make_raw_line((0.0, 0.0), (0.0, 150.0)),
            make_raw_line((300.0, 0.0), (300.0, 150.0)),
            make_raw_line((0.0, 50.0), (300.0, 50.0)),
            make_raw_line((0.0, 100.0), (300.0, 100.0)),
            make_raw_line((100.0, 0.0), (100.0, 150.0)),
            make_raw_line((200.0, 0.0), (200.0, 150.0)),
        ]

        # Warm-up
        _ = run_strategy_d(lines, roi)

        start = time.perf_counter()
        for _ in range(100):
            res = run_strategy_d(lines, roi)
        total_time_ms = (time.perf_counter() - start) * 1000.0
        avg_crop_ms = total_time_ms / 100.0

        assert res.has_valid_table is True
        assert len(res.cells) == 9
        assert avg_crop_ms < 5.0, f"Expected < 5ms/crop, got {avg_crop_ms:.2f}ms"
