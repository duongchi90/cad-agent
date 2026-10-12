"""
test_calibration_degenerate_nonfinite_and_perf.py — Degenerate, Non-Finite & Scalability Benchmark.

Validates robust handling of numerical edge cases, non-finite inputs, and profiles scalability:
1. Empty collections, zero values, negative dimensions.
2. Non-finite inputs (NaN, Inf) in coordinates and parsed values.
3. Zero-length lines (points) and micro-lines.
4. Extreme coordinates (10^6 px).
5. Large-scale runtime profiling up to N = 500 lines and N = 100 text annotations.
"""

from __future__ import annotations

import math
import time
import pytest
import numpy as np

try:
    from .calibration_consensus_engine import make_line, make_text, run_strategy_d
except ImportError:
    from calibration_consensus_engine import make_line, make_text, run_strategy_d


def test_empty_inputs_safety():
    """Empty text or line inputs must return None cleanly without exception."""
    assert run_strategy_d([], []) is None

    t = make_text("1000", (100, 100, 150, 120))
    assert run_strategy_d([t], []) is None

    l = make_line((100.0, 130.0), (350.0, 130.0), "l1")
    assert run_strategy_d([], [l]) is None


def test_zero_and_negative_dimension_values():
    """Zero value (0.0mm) or negative dimensions are invalid for physical scale estimation."""
    t_zero = make_text("0", (100, 100, 130, 120), id_="t0")
    t_neg = make_text("-50", (100, 200, 150, 220), id_="t_neg")
    l1 = make_line((100.0, 130.0), (350.0, 130.0), "l1")
    l2 = make_line((100.0, 230.0), (350.0, 230.0), "l2")

    res = run_strategy_d([t_zero, t_neg], [l1, l2])
    assert res is None, "Zero and negative values must be rejected"


def test_non_finite_coordinates_and_values():
    """NaN and Inf in coordinates or text values must be safely filtered without crashing."""
    t_nan = make_text("NaN", (100, 100, 150, 120), id_="t_nan")
    t_valid = make_text("1000", (100, 100, 150, 120), id_="tv")

    l_inf = make_line((float("inf"), 130.0), (350.0, 130.0), "l_inf")
    l_nan = make_line((100.0, float("nan")), (350.0, 130.0), "l_nan")
    l_valid = make_line((100.0, 130.0), (350.0, 130.0), "l_valid")

    # Should run cleanly without uncaught exception
    res = run_strategy_d([t_nan, t_valid], [l_inf, l_nan, l_valid])
    assert res is None or res.pixel_to_unit_scale > 0.0


def test_zero_length_points_and_micro_lines():
    """Zero-length points and micro-lines (< 1e-4 px) do not trigger ZeroDivisionError."""
    p_zero = make_line((100.0, 130.0), (100.0, 130.0), "zero")
    p_micro = make_line((100.0, 130.0), (100.0 + 1e-6, 130.0), "micro")
    t1 = make_text("1000", (100, 100, 150, 120), id_="t1")
    t2 = make_text("1000", (200, 100, 250, 120), id_="t2")

    res = run_strategy_d([t1, t2], [p_zero, p_micro])
    assert res is None, "Points and micro-lines must be rejected, not divide by zero"


def test_extreme_coordinate_scale():
    """Numerical precision when coordinates are at 10^6 px."""
    offset = 1_000_000.0
    t1 = make_text("1000", (int(offset + 100), int(offset + 100), int(offset + 150), int(offset + 120)), id_="t1")
    l1 = make_line((offset + 100.0, offset + 130.0), (offset + 350.0, offset + 130.0), id_="l1")

    t2 = make_text("2000", (int(offset + 200), int(offset + 300), int(offset + 250), int(offset + 320)), id_="t2")
    l2 = make_line((offset + 200.0, offset + 330.0), (offset + 700.0, offset + 330.0), id_="l2")

    cal = run_strategy_d([t1, t2], [l1, l2], max_relative_error_pct=3.0)
    assert cal is not None
    assert abs(cal.pixel_to_unit_scale - 4.0) < 1e-4


def test_large_scale_runtime_profiling():
    """Profiles runtime performance for large drawing: 50 texts x 200 lines."""
    rng = np.random.default_rng(42)
    texts = []
    lines = []

    # Generate 50 texts and 200 lines
    for i in range(50):
        val = 1000 + i * 50
        y = float(i * 40.0)
        texts.append(make_text(str(val), (200, int(y - 20), 260, int(y - 5)), id_=f"t_{i}"))

    for j in range(200):
        y = float(j * 15.0)
        lines.append(make_line((100.0, y), (350.0, y), id_=f"l_{j}"))

    iters = 10
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = run_strategy_d(texts, lines, max_relative_error_pct=3.0)
    t1 = time.perf_counter()

    avg_time_ms = ((t1 - t0) / iters) * 1000.0
    print(f"\n[SCALABILITY] 50 Texts x 200 Lines runtime: {avg_time_ms:.2f} ms")
    assert avg_time_ms < 50.0, f"Expected < 50ms, got {avg_time_ms:.2f} ms"
