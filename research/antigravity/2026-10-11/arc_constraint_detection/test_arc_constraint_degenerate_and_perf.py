"""
test_arc_constraint_degenerate_and_perf.py — Degenerate, Non-Finite, and Performance Benchmarks.

Tests:
1. Zero-radius arc/circle (safely skipped).
2. Negative radius arc/circle (safely skipped).
3. Zero-length line segment (safely skipped).
4. Equal start and end angle arc (0 deg sweep).
5. Full 360 deg sweep arc.
6. Non-finite values (NaN coordinates, +inf, -inf radii).
7. Empty and single-element primitive sequences.
8. Performance benchmark on 100-primitive complex drawing (target: < 50ms).
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

from arc_constraint_engine import (
    detect_arc_fillet_constraints,
    make_arc,
    make_circle,
    make_line,
)


def test_degenerate_zero_radius():
    """Zero radius arc should be safely filtered out without error."""
    zero_arc = make_arc((10.0, 10.0), 0.0, 0.0, 90.0, id_="zero_arc")
    normal_line = make_line((0.0, 10.0), (20.0, 10.0), id_="line")
    res = detect_arc_fillet_constraints([zero_arc, normal_line])
    assert len(res) == 0


def test_degenerate_negative_radius():
    """Negative radius arc should be safely filtered out without error."""
    neg_arc = make_arc((10.0, 10.0), -5.0, 0.0, 90.0, id_="neg_arc")
    normal_line = make_line((0.0, 10.0), (20.0, 10.0), id_="line")
    res = detect_arc_fillet_constraints([neg_arc, normal_line])
    assert len(res) == 0


def test_degenerate_zero_length_line():
    """Zero length line segment (start == end) should be safely filtered out."""
    point_line = make_line((10.0, 10.0), (10.0, 10.0), id_="point_line")
    normal_arc = make_arc((10.0, 20.0), 10.0, 180.0, 360.0, id_="arc")
    res = detect_arc_fillet_constraints([point_line, normal_arc])
    assert len(res) == 0


def test_degenerate_zero_sweep_arc():
    """Arc with start_angle == end_angle (0-length arc)."""
    flat_arc = make_arc((0.0, 0.0), 10.0, 45.0, 45.0, id_="flat_arc")
    line = make_line((-10.0, 10.0), (10.0, 10.0), id_="line")
    res = detect_arc_fillet_constraints([flat_arc, line])
    # Contact at (0, 10) is angle 90 deg, which is outside 45..45 deg sweep
    assert len([c for c in res if c.type == "tangent"]) == 0


def test_full_circle_arc():
    """Arc with 360 deg sweep (0 to 360) behaves like full circle."""
    full_arc = make_arc((0.0, 10.0), 10.0, 0.0, 360.0, id_="full_arc")
    tangent_line = make_line((-20.0, 0.0), (20.0, 0.0), id_="tan_line")
    res = detect_arc_fillet_constraints([full_arc, tangent_line])
    tangents = [c for c in res if c.type == "tangent"]
    assert len(tangents) == 1


def test_nonfinite_nan_and_inf_handling():
    """Primitives containing NaN or Inf must not cause crashes or corrupted output."""
    nan_arc = make_arc((float("nan"), 10.0), 10.0, 0.0, 90.0, id_="nan_arc")
    inf_circle = make_circle((10.0, 10.0), float("inf"), id_="inf_circle")
    nan_line = make_line((0.0, float("-inf")), (10.0, 10.0), id_="nan_line")
    valid_line = make_line((0.0, 0.0), (10.0, 0.0), id_="valid_line")

    res = detect_arc_fillet_constraints([nan_arc, inf_circle, nan_line, valid_line])
    assert len(res) == 0


def test_empty_and_single_primitive():
    """Empty or single-element inputs safely return empty list."""
    assert detect_arc_fillet_constraints([]) == []
    assert detect_arc_fillet_constraints([make_line((0.0, 0.0), (1.0, 1.0))]) == []
    assert detect_arc_fillet_constraints([make_circle((0.0, 0.0), 5.0)]) == []
    assert detect_arc_fillet_constraints([make_arc((0.0, 0.0), 5.0, 0.0, 90.0)]) == []


def test_performance_100_primitives():
    """Performance benchmark with 100 primitives:
    40 lines, 30 arcs, 30 circles.
    Evaluates thousands of pairwise geometric checks.
    Target: Execution time under 50 milliseconds.
    """
    primitives = []
    # 40 grid lines
    for i in range(20):
        primitives.append(make_line((float(i * 10), 0.0), (float(i * 10), 200.0), id_=f"l_v_{i}"))
        primitives.append(make_line((0.0, float(i * 10)), (200.0, float(i * 10)), id_=f"l_h_{i}"))

    # 30 arcs
    for i in range(30):
        primitives.append(make_arc(
            center=(float(i * 5), float(i * 5)),
            radius=5.0 + (i % 3) * 2.0,
            start_deg=float((i * 15) % 360),
            end_deg=float(((i * 15) + 90) % 360),
            id_=f"arc_{i}",
        ))

    # 30 circles
    for i in range(30):
        primitives.append(make_circle(
            center=(float(i * 6), float(i * 6)),
            radius=8.0 + (i % 4),
            id_=f"circ_{i}",
        ))

    assert len(primitives) == 100

    # Measure wall clock time
    start_t = time.perf_counter()
    constraints = detect_arc_fillet_constraints(primitives)
    duration_s = time.perf_counter() - start_t

    # Target: < 50ms (< 0.050 seconds)
    assert duration_s < 0.050, f"Performance too slow: {duration_s * 1000:.2f} ms > 50 ms"
    assert len(constraints) > 0, "Should detect valid constraints in grid/cluster"
