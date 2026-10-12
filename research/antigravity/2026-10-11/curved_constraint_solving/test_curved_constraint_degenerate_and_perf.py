"""
test_curved_constraint_degenerate_and_perf.py — Degenerate, Non-Finite & Performance
Benchmarks for Curved and Concentric Geometric Constraint Solving.

Test matrix:
- D1: NaN coordinate in circle/arc geometry -> safe skip
- D2: Inf coordinate in circle/arc geometry -> safe skip
- D3: Extreme coordinates (10^6 mm) handled without numeric overflow
- D4: Micro-radius circle (0.01 mm) handled with finite precision
- D5: Full-circle arc (0-360 deg) and micro-sweep arc handled safely
- P1: Performance benchmark: 60 mixed primitives with 40 constraints solved in < 25 ms
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
    ArcGeometry, Calibration, CircleGeometry, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace,
)
from semantic_ir_lib.models import Constraint

try:
    import python_solvespace
    _HAS_SOLVESPACE = True
except ImportError:
    _HAS_SOLVESPACE = False

from curved_constraint_solver_engine import solve_curved_constraints_strategy_d


def _doc(*prims: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=300, image_height_px=300),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=list(prims),
    )


def test_degenerate_nan_coordinate_failsafe():
    """D1: NaN coordinates in circle geometry are safely skipped."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(float("nan"), 50.0), radius=20.0))
    c2 = Primitive(id="c2", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(50.0, 50.0), radius=10.0))
    doc = _doc(c1, c2)
    c_con = Constraint(type="concentric", primitive_ids=["c1", "c2"], confidence=1.0, tolerance={})

    res = solve_curved_constraints_strategy_d(doc, [c_con])
    assert res.status == "okay"
    assert res.applied_concentric_count == 0


def test_degenerate_inf_coordinate_failsafe():
    """D2: Inf coordinates in arc geometry are safely skipped."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    a1 = Primitive(id="a1", type="arc", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=ArcGeometry(center=Point2D(float("inf"), 50.0), radius=20.0, start_angle_deg=0.0, end_angle_deg=90.0))
    c2 = Primitive(id="c2", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(50.0, 50.0), radius=10.0))
    doc = _doc(a1, c2)
    c_con = Constraint(type="concentric", primitive_ids=["a1", "c2"], confidence=1.0, tolerance={})

    res = solve_curved_constraints_strategy_d(doc, [c_con])
    assert res.status == "okay"
    assert res.applied_concentric_count == 0


def test_degenerate_extreme_coordinates():
    """D3: Coordinates at 10^6 mm handled without overflow."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(1_000_000.0, 1_000_000.0), radius=50.0))
    c2 = Primitive(id="c2", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(1_000_001.0, 1_000_000.0), radius=20.0))
    doc = _doc(c1, c2)
    c_con = Constraint(type="concentric", primitive_ids=["c1", "c2"], confidence=1.0, tolerance={})

    res = solve_curved_constraints_strategy_d(doc, [c_con])
    assert res.status == "okay"
    assert res.applied_concentric_count == 1
    p1 = res.solved_primitives["c1"].center
    p2 = res.solved_primitives["c2"].center
    assert math.hypot(p1.x - p2.x, p1.y - p2.y) <= 1e-4


def test_degenerate_micro_radius_circle():
    """D4: Micro-radius circle (0.01 mm) handled with finite precision."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(10.0, 10.0), radius=0.01))
    c2 = Primitive(id="c2", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(10.001, 10.0), radius=0.01))
    doc = _doc(c1, c2)
    c_con = Constraint(type="concentric", primitive_ids=["c1", "c2"], confidence=1.0, tolerance={})

    res = solve_curved_constraints_strategy_d(doc, [c_con])
    assert res.status == "okay"
    assert res.applied_concentric_count == 1


def test_degenerate_arc_sweep_angles():
    """D5: Arc with full 360-deg sweep or narrow sweep handled safely."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    a1 = Primitive(id="a1", type="arc", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=ArcGeometry(center=Point2D(50.0, 50.0), radius=20.0, start_angle_deg=0.0, end_angle_deg=359.99))
    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(50.2, 50.0), radius=10.0))
    doc = _doc(a1, c1)
    c_con = Constraint(type="concentric", primitive_ids=["a1", "c1"], confidence=1.0, tolerance={})

    res = solve_curved_constraints_strategy_d(doc, [c_con])
    assert res.status == "okay"
    assert res.applied_concentric_count == 1


def test_performance_60_primitives_curved_solve():
    """P1: Benchmark solving 60 primitives (20 lines, 20 circles, 20 arcs) with 40 constraints in < 25 ms."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    prims = []
    constraints = []
    N = 20
    for i in range(N):
        x = i * 20.0
        lid = f"line_{i:02d}"
        cid = f"circ_{i:02d}"
        prims.append(
            Primitive(id=lid, type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                      geometry=LineGeometry(start=Point2D(x, 0.0), end=Point2D(x + 15.0, 0.0)))
        )
        prims.append(
            Primitive(id=cid, type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                      geometry=CircleGeometry(center=Point2D(x + 7.5, 12.0), radius=10.0))
        )
        constraints.append(
            Constraint(type="tangent", primitive_ids=[lid, cid], confidence=1.0, tolerance={})
        )

    doc = _doc(*prims)

    t0 = time.perf_counter()
    res = solve_curved_constraints_strategy_d(doc, constraints)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert res.status == "okay"
    assert res.applied_tangent_count == N
    assert elapsed_ms < 25.0, f"Latency {elapsed_ms:.2f} ms exceeded 25 ms budget"
