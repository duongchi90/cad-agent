"""
test_symmetry_constraint_degenerate_and_perf.py
Degenerate Edge Cases, Non-Finite Handling, and Performance Stress Benchmark Suite.
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

from primitive_ir_lib.models import (
    Point2D, Primitive, LineGeometry, CircleGeometry,
    PrimitiveIRDocument, Trace, SourceDocument, Calibration
)
from symmetry_constraint_engine import (
    SymmetryAxis,
    detect_symmetry_strategy_d,
)


def _make_line(id_: str, x0: float, y0: float, x1: float, y1: float, layer: str = "UNCLASSIFIED") -> Primitive:
    finite = math.isfinite(x0) and math.isfinite(y0) and math.isfinite(x1) and math.isfinite(y1)
    bbox = (int(min(x0, x1)), int(min(y0, y1)), int(max(x0, x1)), int(max(y0, y1))) if finite else (0, 0, 10, 10)
    return Primitive(
        id=id_,
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=bbox),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
        layer=layer,
    )


def _make_circle(id_: str, cx: float, cy: float, r: float, layer: str = "UNCLASSIFIED") -> Primitive:
    finite = math.isfinite(cx) and math.isfinite(cy) and math.isfinite(r)
    bbox = (int(cx - r), int(cy - r), int(cx + r), int(cy + r)) if finite else (0, 0, 10, 10)
    return Primitive(
        id=id_,
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=bbox),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
        layer=layer,
    )


def test_degenerate_01_empty_primitives_list():
    """Edge 1: Empty primitives input returns clean empty result without exception."""
    res = detect_symmetry_strategy_d([], [])
    assert len(res.axes) == 0
    assert len(res.symmetric_pairs) == 0
    assert len(res.constraints) == 0


def test_degenerate_02_zero_length_primitives():
    """Edge 2: Zero-length lines and zero-radius circles are ignored safely without ZeroDivisionError."""
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    l_zero1 = _make_line("zero1", 20.0, 10.0, 20.0, 10.0)
    l_zero2 = _make_line("zero2", 20.0, -10.0, 20.0, -10.0)
    c_zero = _make_circle("czero", 50.0, 20.0, 0.0)

    res = detect_symmetry_strategy_d([l_axis, l_zero1, l_zero2], [c_zero])
    assert len(res.symmetric_pairs) == 0


def test_degenerate_03_non_finite_coordinates_nan_inf():
    """Edge 3: Non-finite coordinates (NaN/Inf) raise ValueError safely to protect downstream solvers."""
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    l_nan = _make_line("nan", 10.0, float("nan"), 50.0, 20.0)

    with pytest.raises(ValueError, match="non-finite coordinates"):
        detect_symmetry_strategy_d([l_axis, l_nan], [])

    c_inf = _make_circle("inf", float("inf"), 10.0, 5.0)
    with pytest.raises(ValueError, match="non-finite coordinates"):
        detect_symmetry_strategy_d([l_axis], [c_inf])


def test_degenerate_04_astronomical_coordinates():
    """Edge 4: Coordinates at astronomical scale (10^7 mm) processed without overflow."""
    base_x = 10_000_000.0
    base_y = 10_000_000.0
    l_axis = _make_line("axis", base_x, base_y, base_x + 100.0, base_y, layer="CENTER")
    l_top = _make_line("top", base_x + 10.0, base_y + 20.0, base_x + 80.0, base_y + 20.0)
    l_bot = _make_line("bot", base_x + 10.0, base_y - 20.0, base_x + 80.0, base_y - 20.0)

    res = detect_symmetry_strategy_d([l_axis, l_top, l_bot], [])
    assert len(res.symmetric_pairs) == 1
    assert set(res.symmetric_pairs[0].primitive_ids) == {"top", "bot"}
    assert res.symmetric_pairs[0].measured["reflection_gap_mm"] < 1e-3


def test_degenerate_05_micro_scale_features():
    """Edge 5: Micro-scale features (0.1mm) with tuned tolerances detected reliably."""
    l_axis = _make_line("axis", 0.0, 0.0, 1.0, 0.0, layer="CENTER")
    l_top = _make_line("top", 0.1, 0.05, 0.9, 0.05)
    l_bot = _make_line("bot", 0.1, -0.05, 0.9, -0.05)

    res = detect_symmetry_strategy_d(
        [l_axis, l_top, l_bot], [],
        distance_tolerance_mm=0.01,
        angle_tolerance_deg=1.0,
    )
    assert len(res.symmetric_pairs) == 1
    assert set(res.symmetric_pairs[0].primitive_ids) == {"top", "bot"}


def test_degenerate_06_duplicate_coincident_primitives():
    """Edge 6: Duplicate coincident primitives are filtered to prevent redundant constraints."""
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    l_top1 = _make_line("top1", 10.0, 20.0, 80.0, 20.0)
    l_top2 = _make_line("top2", 10.0, 20.0, 80.0, 20.0)  # duplicate of top1
    l_bot = _make_line("bot", 10.0, -20.0, 80.0, -20.0)

    res = detect_symmetry_strategy_d([l_axis, l_top1, l_top2, l_bot], [])
    # Pairs should only pair distinct features without duplicate constraints
    pair_tuples = [tuple(sorted(p.primitive_ids)) for p in res.symmetric_pairs]
    assert len(pair_tuples) == len(set(pair_tuples))


def test_perf_07_large_scale_workpiece_throughput():
    """Edge 7 (Performance): 200 symmetric features (100 pairs) evaluated in < 100 ms."""
    l_axis = _make_line("axis", 0.0, 0.0, 1000.0, 0.0, layer="CENTER")
    lines = [l_axis]
    circles = []

    # Generate 50 symmetric line pairs
    for i in range(50):
        y_offset = 10.0 + i * 2.0
        x_start = i * 15.0
        x_end = x_start + 12.0
        lines.append(_make_line(f"top_{i}", x_start, y_offset, x_end, y_offset))
        lines.append(_make_line(f"bot_{i}", x_start, -y_offset, x_end, -y_offset))

    # Generate 50 symmetric circle pairs
    for i in range(50):
        y_offset = 15.0 + i * 2.0
        x_pos = 10.0 + i * 18.0
        circles.append(_make_circle(f"c_top_{i}", x_pos, y_offset, 3.0))
        circles.append(_make_circle(f"c_bot_{i}", x_pos, -y_offset, 3.0))

    t0 = time.perf_counter()
    res = detect_symmetry_strategy_d(lines, circles)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert len(res.symmetric_pairs) == 100
    assert elapsed_ms < 100.0, f"Execution took {elapsed_ms:.2f} ms (expected < 100 ms)"
