"""
test_bolt_circle_degenerate_and_perf.py — Degenerate, Non-Finite & Performance Tests for Bolt Circle Patterns.

Epic: CIRCULAR_PITCH_BOLT_PATTERN_RECOGNITION_V1
Role: ANTIGRAVITY_RESEARCH
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

from primitive_ir_lib.models import CircleGeometry, Point2D, Primitive, Trace
from bolt_circle_engine import detect_bolt_circle_patterns


def _circle(id_: str, cx: float, cy: float, radius: float = 5.0) -> Primitive:
    return Primitive(
        id=id_,
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(int(cx - radius), int(cy - radius), int(cx + radius), int(cy + radius))),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=radius),
    )


def test_degenerate_empty_and_sub_threshold():
    """Verify empty list and < 3 circles return [] safely."""
    assert detect_bolt_circle_patterns([]) == []
    c1 = _circle("C1", 0.0, 0.0, 5.0)
    assert detect_bolt_circle_patterns([c1]) == []
    c2 = _circle("C2", 10.0, 0.0, 5.0)
    assert detect_bolt_circle_patterns([c1, c2]) == []


def test_degenerate_non_circle_primitives_ignored():
    """Verify primitives with type != 'circle' or geometry is None are skipped safely."""
    from primitive_ir_lib.models import LineGeometry
    line_prim = Primitive(
        id="L1",
        type="line",
        source="test",
        confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(10.0, 10.0)),
    )
    assert detect_bolt_circle_patterns([line_prim]) == []


def test_degenerate_nonfinite_coordinates():
    """Verify circles with NaN or Inf coordinates are safely rejected without exception."""
    c_nan = Primitive(
        id="C_nan",
        type="circle",
        source="test",
        confidence=0.95,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(float("nan"), 0.0), radius=5.0),
    )
    c_inf = Primitive(
        id="C_inf",
        type="circle",
        source="test",
        confidence=0.95,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(float("inf"), 10.0), radius=5.0),
    )
    c1 = _circle("C1", 50.0, 0.0, 5.0)
    c2 = _circle("C2", 0.0, 50.0, 5.0)
    c3 = _circle("C3", -50.0, 0.0, 5.0)

    res = detect_bolt_circle_patterns([c_nan, c_inf, c1, c2, c3])
    assert isinstance(res, list)


def test_degenerate_coincident_duplicate_circles():
    """Verify coincident duplicate circles at the exact same location do not divide by zero."""
    # 3 duplicates at the exact same point
    c1 = _circle("Dup1", 50.0, 0.0, 5.0)
    c2 = _circle("Dup2", 50.0, 0.0, 5.0)
    c3 = _circle("Dup3", 50.0, 0.0, 5.0)

    res = detect_bolt_circle_patterns([c1, c2, c3])
    # Cannot form a circle from identical coincident points
    assert len(res) == 0


def test_performance_100_circles_10_patterns():
    """Verify pattern recognition throughput: 100 circles forming 10 distinct bolt patterns across a drawing."""
    workload: list[Primitive] = []
    # 10 separate parts, each has a central bore and 8 bolt holes on R=40mm
    for part_idx in range(10):
        ox = part_idx * 200.0
        oy = (part_idx % 3) * 200.0

        cen = _circle(f"P{part_idx}_Cen", ox, oy, 20.0)
        workload.append(cen)

        for h_idx in range(8):
            a = math.radians(h_idx * 45.0)
            hx = ox + 40.0 * math.cos(a)
            hy = oy + 40.0 * math.sin(a)
            workload.append(_circle(f"P{part_idx}_H{h_idx}", hx, hy, 4.0))

    assert len(workload) == 90  # 10 bores + 80 holes

    start_time = time.perf_counter()
    patterns = detect_bolt_circle_patterns(workload)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Must accurately find all 10 patterns
    assert len(patterns) == 10, f"Expected 10 patterns, got {len(patterns)}"
    # Performance budget < 50ms
    assert elapsed_ms < 50.0, f"Expected < 50ms for 90 circles, got {elapsed_ms:.2f}ms"
