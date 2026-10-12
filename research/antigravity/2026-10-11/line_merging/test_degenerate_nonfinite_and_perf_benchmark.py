"""
test_degenerate_nonfinite_and_perf_benchmark.py — Degenerate, Non-Finite & Scalability Benchmark.

Validates robust handling of edge cases and profiles runtime scalability:
1. Empty inputs, singletons, identical duplicates, contained sub-segments.
2. Zero-length segments (points), micro-segments (len < 1e-4), extreme coordinates.
3. Non-finite values (NaN, Inf) input safety.
4. Runtime profiling up to N = 1000 line segments.
"""

from __future__ import annotations

import math
import time
import numpy as np
import pytest

from primitive_ir_lib.geometry_extraction import RawLine

try:
    from .line_merging_engine import merge_strategy_d, make_line
except ImportError:
    from line_merging_engine import merge_strategy_d, make_line


def test_empty_and_singleton():
    """Empty list and single line inputs."""
    assert merge_strategy_d([]) == []

    l = make_line((10.0, 20.0), (100.0, 20.0), "single")
    res = merge_strategy_d([l])
    assert len(res) == 1
    assert res[0].id == "single"
    assert res[0].p1_px == (10.0, 20.0)
    assert res[0].p2_px == (100.0, 20.0)


def test_zero_length_and_micro_segments():
    """Zero-length points and micro-segments (len < 1e-4) do not trigger ZeroDivisionError."""
    p_zero = make_line((50.0, 50.0), (50.0, 50.0), "zero_len")
    p_micro = make_line((50.0, 50.0), (50.0 + 1e-6, 50.0), "micro")
    l_valid = make_line((60.0, 50.0), (160.0, 50.0), "valid")

    # Should run cleanly without exception
    res = merge_strategy_d([p_zero, p_micro, l_valid], gap_tol_px=25.0)
    assert isinstance(res, list)
    # The valid segment is preserved or merged with the adjacent point
    valid_found = any(abs(r.p2_px[0] - 160.0) < 1e-2 for r in res)
    assert valid_found


def test_duplicate_and_contained_segments():
    """Duplicate lines and nested sub-segments collapse into single maximal span."""
    # Duplicate line
    l1 = make_line((0.0, 100.0), (200.0, 100.0), "l1")
    l2 = make_line((0.0, 100.0), (200.0, 100.0), "l2_dup")
    # Nested sub-segment [50, 150] inside [0, 200]
    l3 = make_line((50.0, 100.0), (150.0, 100.0), "l3_sub")

    res = merge_strategy_d([l1, l2, l3], gap_tol_px=10.0)
    assert len(res) == 1
    merged = res[0]
    assert abs(merged.p1_px[0] - 0.0) < 1e-2
    assert abs(merged.p2_px[0] - 200.0) < 1e-2


def test_extreme_coordinate_scale():
    """Numerical stability when coordinates are at extreme scale (10^6 px)."""
    offset = 1_000_000.0
    l1 = make_line((offset + 0.0, offset + 0.0), (offset + 100.0, offset + 0.0), "l1_big")
    l2 = make_line((offset + 110.0, offset + 0.0), (offset + 250.0, offset + 0.0), "l2_big")

    res = merge_strategy_d([l1, l2], gap_tol_px=20.0)
    assert len(res) == 1
    m = res[0]
    assert abs(m.p1_px[0] - offset) < 1e-2
    assert abs(m.p2_px[0] - (offset + 250.0)) < 1e-2


def test_nan_and_inf_coordinate_safety():
    """Inputs with NaN or Inf coordinates are safely rejected or handled without crashing."""
    valid_line = make_line((0.0, 0.0), (100.0, 0.0), "valid")
    nan_line = make_line((float("nan"), 0.0), (100.0, 0.0), "nan")
    inf_line = make_line((0.0, float("inf")), (100.0, 0.0), "inf")

    # Strategy D filters or survives non-finite lines
    res = merge_strategy_d([valid_line, nan_line, inf_line])
    assert isinstance(res, list)
    # The valid line must still emerge intact
    valid_out = [r for r in res if r.id in ("valid", "merged-d-0")]
    assert len(valid_out) >= 1


def test_scalability_runtime_profiling():
    """Profiles runtime scalability across N = 10, 50, 100, 200, 500, 1000 segments."""
    n_counts = [10, 50, 100, 200, 500, 1000]

    print("\n" + "=" * 70)
    print("RUNTIME SCALABILITY PROFILING (STRATEGY D)")
    print("=" * 70)
    print(f"{'N Segments':>12} | {'Total Time (ms)':>18} | {'Time/Segment (µs)':>20}")
    print("-" * 70)

    for n in n_counts:
        # Generate n broken segments distributed across multiple lines and angles
        lines = []
        rng = np.random.default_rng(42)
        for i in range(n):
            row = i % 20
            col = (i // 20) * 80.0
            x1 = col + float(rng.uniform(0, 10))
            y1 = row * 30.0 + float(rng.uniform(-0.5, 0.5))
            length = float(rng.uniform(30, 70))
            angle = float(rng.choice([0.0, 45.0, 90.0]))
            rad = math.radians(angle)
            x2 = x1 + math.cos(rad) * length
            y2 = y1 + math.sin(rad) * length
            lines.append(make_line((x1, y1), (x2, y2), f"line_{i}"))

        # Warm up
        _ = merge_strategy_d(lines[:10], gap_tol_px=15.0)

        # Profile 5 iterations
        iters = 5
        t0 = time.perf_counter()
        for _ in range(iters):
            _ = merge_strategy_d(lines, gap_tol_px=15.0)
        t1 = time.perf_counter()

        avg_time_ms = ((t1 - t0) / iters) * 1000.0
        time_per_seg_us = (avg_time_ms * 1000.0) / n

        print(f"{n:12d} | {avg_time_ms:18.3f} | {time_per_seg_us:20.2f}")

        # Assert runtime bound: N=100 segments takes < 50ms
        if n == 100:
            assert avg_time_ms < 50.0, f"N=100 took {avg_time_ms:.2f} ms (expected < 50 ms)"

    print("=" * 70)
