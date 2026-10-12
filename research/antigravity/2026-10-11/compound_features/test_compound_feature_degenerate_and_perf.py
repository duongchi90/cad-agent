"""
test_compound_feature_degenerate_and_perf.py — Degenerate, Non-Finite, & Performance Benchmarks.

Tests:
1. Primitives containing NaN and Inf coordinates (safely ignored).
2. Constraints referencing non-existent primitive IDs (stale IDs safely ignored).
3. Self-referential constraints (id1 == id2 safely skipped).
4. Zero-length line and zero-radius arc primitives.
5. Empty primitives and empty constraints lists.
6. Circular overlapping compound structures.
7. Performance benchmark on 120-primitive drawing with 20 compound features (target: < 50ms).
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

from compound_feature_engine import (
    detect_compound_features,
    make_arc,
    make_circle,
    make_constraint,
    make_line,
)


def test_degenerate_nonfinite_nan_and_inf():
    """Primitives with NaN or Inf should not crash compound feature detection."""
    nan_line = make_line((float("nan"), 0.0), (100.0, 0.0), id_="nan_line")
    inf_arc = make_arc((50.0, float("inf")), 10.0, 0.0, 90.0, id_="inf_arc")
    normal_line = make_line((0.0, 0.0), (50.0, 0.0), id_="normal_line")

    csts = [
        make_constraint("tangent", "nan_line", "inf_arc"),
        make_constraint("parallel", "nan_line", "normal_line"),
    ]

    res = detect_compound_features([nan_line, inf_arc, normal_line], csts)
    # Should safely return without crash
    assert isinstance(res, list)


def test_degenerate_stale_constraint_ids():
    """Constraints pointing to IDs that do not exist in primitives list."""
    l1 = make_line((0.0, 0.0), (50.0, 0.0), id_="l1")
    l2 = make_line((0.0, 20.0), (50.0, 20.0), id_="l2")

    csts = [
        make_constraint("parallel", "l1", "l2"),
        make_constraint("tangent", "l1", "ghost_arc_1"),
        make_constraint("tangent", "l2", "ghost_arc_2"),
    ]

    res = detect_compound_features([l1, l2], csts)
    assert len(res) == 0


def test_degenerate_self_referential_constraints():
    """Constraint referencing the same primitive twice (id1 == id2)."""
    l1 = make_line((0.0, 0.0), (50.0, 0.0), id_="l1")
    csts = [make_constraint("parallel", "l1", "l1")]

    res = detect_compound_features([l1], csts)
    assert len(res) == 0


def test_degenerate_zero_length_and_radius():
    """Zero length lines and zero radius arcs."""
    p_line = make_line((10.0, 10.0), (10.0, 10.0), id_="p_line")
    z_arc = make_arc((10.0, 10.0), 0.0, 0.0, 90.0, id_="z_arc")
    csts = [make_constraint("tangent", "p_line", "z_arc")]

    res = detect_compound_features([p_line, z_arc], csts)
    assert len(res) == 0


def test_empty_inputs():
    """Empty lists for primitives and constraints."""
    assert detect_compound_features([], []) == []
    assert detect_compound_features([make_line((0.0, 0.0), (10.0, 0.0))], []) == []


def test_performance_120_primitives_large_assembly():
    """Performance benchmark with 120 primitives forming 20 slots:
    40 lines, 40 arcs, 40 circles.
    Target: < 50 milliseconds.
    """
    prims = []
    csts = []

    # Create 10 distinct slots (40 prims: 20 lines + 20 arcs)
    for i in range(10):
        y = float(i * 30)
        l_top = make_line((10.0, y + 10.0), (60.0, y + 10.0), id_=f"slot_{i}_lt")
        l_bot = make_line((10.0, y), (60.0, y), id_=f"slot_{i}_lb")
        a_l = make_arc((10.0, y + 5.0), 5.0, 90.0, 270.0, id_=f"slot_{i}_al")
        a_r = make_arc((60.0, y + 5.0), 5.0, 270.0, 90.0, id_=f"slot_{i}_ar")

        prims.extend([l_top, l_bot, a_l, a_r])
        csts.extend([
            make_constraint("parallel", f"slot_{i}_lt", f"slot_{i}_lb"),
            make_constraint("tangent", f"slot_{i}_lt", f"slot_{i}_al"),
            make_constraint("tangent", f"slot_{i}_lb", f"slot_{i}_al"),
            make_constraint("tangent", f"slot_{i}_lt", f"slot_{i}_ar"),
            make_constraint("tangent", f"slot_{i}_lb", f"slot_{i}_ar"),
        ])

    # Create 10 distinct mounting lugs (40 prims: 10 arcs + 10 circles + 20 lines)
    for i in range(10):
        x = float(100 + i * 40)
        a_lug = make_arc((x, 50.0), 15.0, 0.0, 180.0, id_=f"lug_{i}_arc")
        c_hole = make_circle((x, 50.0), 6.0, id_=f"lug_{i}_hole")
        l1 = make_line((x - 15.0, 50.0), (x - 15.0, 20.0), id_=f"lug_{i}_l1")
        l2 = make_line((x + 15.0, 50.0), (x + 15.0, 20.0), id_=f"lug_{i}_l2")

        prims.extend([a_lug, c_hole, l1, l2])
        csts.extend([
            make_constraint("concentric", f"lug_{i}_arc", f"lug_{i}_hole"),
            make_constraint("tangent", f"lug_{i}_l1", f"lug_{i}_arc"),
            make_constraint("tangent", f"lug_{i}_l2", f"lug_{i}_arc"),
        ])

    # Add 40 extra background grid lines
    for i in range(20):
        prims.append(make_line((float(i * 20), 0.0), (float(i * 20), 400.0), id_=f"grid_v_{i}"))
        prims.append(make_line((0.0, float(i * 20)), (400.0, float(i * 20)), id_=f"grid_h_{i}"))

    assert len(prims) == 120

    start_t = time.perf_counter()
    parts = detect_compound_features(prims, csts)
    elapsed_s = time.perf_counter() - start_t

    # Performance target: < 50ms (< 0.050s)
    assert elapsed_s < 0.050, f"Performance too slow: {elapsed_s * 1000:.2f} ms > 50 ms"
    # Should detect 10 slots and 10 lugs = 20 compound parts
    assert len(parts) >= 20
