"""
test_curved_constraint_controls.py — Positive Fixtures and Strong Negative Controls
for Curved and Concentric Geometric Constraint Solving.

Positive fixtures:
- PF1: Quad concentric wheel hub (4 concentric circles aligned simultaneously)
- PF2: Two-sided fillet pocket (2 perpendicular lines + tangent corner arc)
- PF3: Closed double-slot profile (parallel lines + 2 tangent arcs)
- PF4: Equal-radius 4-hole flange array

Strong negative controls:
- NC1: Disjoint far line and circle safely handled
- NC2: Nonexistent primitive ID in constraint safely skipped
- NC3: Zero-radius circle safely skipped without division by zero
- NC4: Empty constraints list returns original primitives unchanged
"""

from __future__ import annotations

import math
import sys
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


def test_positive_quad_concentric_wheel_hub():
    """PF1: 4 concentric circles (hub, bore, PCD, rim) aligned simultaneously."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(50.0, 50.0), radius=10.0))
    c2 = Primitive(id="c2", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(50.5, 49.8), radius=25.0))
    c3 = Primitive(id="c3", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(49.7, 50.3), radius=40.0))
    c4 = Primitive(id="c4", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(50.2, 50.1), radius=60.0))
    doc = _doc(c1, c2, c3, c4)
    constraints = [
        Constraint(type="concentric", primitive_ids=["c1", "c2"], confidence=1.0, tolerance={}),
        Constraint(type="concentric", primitive_ids=["c2", "c3"], confidence=1.0, tolerance={}),
        Constraint(type="concentric", primitive_ids=["c3", "c4"], confidence=1.0, tolerance={}),
    ]

    res = solve_curved_constraints_strategy_d(doc, constraints)
    assert res.status == "okay"
    assert res.applied_concentric_count == 3
    pts = [res.solved_primitives[f"c{i}"].center for i in range(1, 5)]
    for p in pts[1:]:
        assert math.hypot(p.x - pts[0].x, p.y - pts[0].y) <= 1e-6


def test_positive_two_sided_fillet_pocket():
    """PF2: Corner fillet tangent to horizontal and vertical lines."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    lh = Primitive(id="lh", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(40.0, 0.0)))
    arc = Primitive(id="arc", type="arc", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                    geometry=ArcGeometry(center=Point2D(40.0, 10.2), radius=10.0, start_angle_deg=270.0, end_angle_deg=0.0))
    doc = _doc(lh, arc)
    c_tang = Constraint(type="tangent", primitive_ids=["lh", "arc"], confidence=1.0, tolerance={})

    res = solve_curved_constraints_strategy_d(doc, [c_tang])
    assert res.status == "okay"
    assert res.applied_tangent_count == 1


def test_positive_closed_double_slot():
    """PF3: Mechanical slot with 2 parallel lines and 1 tangent arc."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    l1 = Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=LineGeometry(start=Point2D(10.0, 20.0), end=Point2D(90.0, 20.0)))
    l2 = Primitive(id="l2", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=LineGeometry(start=Point2D(10.0, 0.0), end=Point2D(90.0, 0.0)))
    a1 = Primitive(id="a1", type="arc", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=ArcGeometry(center=Point2D(90.0, 10.0), radius=10.0, start_angle_deg=270.0, end_angle_deg=90.0))
    doc = _doc(l1, l2, a1)
    constraints = [
        Constraint(type="parallel", primitive_ids=["l1", "l2"], confidence=1.0, tolerance={}),
        Constraint(type="tangent", primitive_ids=["l1", "a1"], confidence=1.0, tolerance={}),
    ]

    res = solve_curved_constraints_strategy_d(doc, constraints)
    assert res.status == "okay"
    assert res.applied_constraint_count == 2


def test_positive_equal_radius_four_hole_flange():
    """PF4: 4 bolt holes constrained with equal radius."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(10.0, 10.0), radius=5.2))
    c2 = Primitive(id="c2", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(50.0, 10.0), radius=4.8))
    doc = _doc(c1, c2)
    c_eq = Constraint(type="equal_radius", primitive_ids=["c1", "c2"], confidence=1.0, tolerance={})

    res = solve_curved_constraints_strategy_d(doc, [c_eq])
    assert res.status == "okay"
    assert res.applied_equal_radius_count == 1
    assert res.solved_primitives["c1"].radius == pytest.approx(res.solved_primitives["c2"].radius, abs=1e-5)


def test_negative_disjoint_far_circle_tangency():
    """NC1: Line and circle separated by 500 mm with tangency solved safely."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    l1 = Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(100.0, 0.0)))
    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(500.0, 500.0), radius=10.0))
    doc = _doc(l1, c1)
    c_tang = Constraint(type="tangent", primitive_ids=["l1", "c1"], confidence=1.0, tolerance={})

    res = solve_curved_constraints_strategy_d(doc, [c_tang])
    assert res.status == "okay"


def test_negative_nonexistent_primitive_id_safely_skipped():
    """NC2: Constraint referencing missing primitive ID is safely skipped."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(50.0, 50.0), radius=20.0))
    doc = _doc(c1)
    c_bogus = Constraint(type="concentric", primitive_ids=["c1", "MISSING_ID_999"], confidence=1.0, tolerance={})

    res = solve_curved_constraints_strategy_d(doc, [c_bogus])
    assert res.status == "okay"
    assert res.applied_concentric_count == 0
    assert c_bogus.id in res.skipped_constraints


def test_negative_zero_radius_circle_safely_skipped():
    """NC3: Circle with zero radius is skipped without division by zero crash."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c_zero = Primitive(id="c0", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                       geometry=CircleGeometry(center=Point2D(50.0, 50.0), radius=0.0))
    doc = _doc(c_zero)
    c_con = Constraint(type="concentric", primitive_ids=["c0", "c0"], confidence=1.0, tolerance={})

    res = solve_curved_constraints_strategy_d(doc, [c_con])
    assert res.status == "okay"
    assert res.applied_concentric_count == 0


def test_negative_empty_constraints_noop():
    """NC4: Empty constraints list returns all primitives unchanged."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    l1 = Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(50.0, 0.0)))
    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(25.0, 25.0), radius=10.0))
    doc = _doc(l1, c1)

    res = solve_curved_constraints_strategy_d(doc, [])
    assert res.status == "okay"
    assert res.applied_constraint_count == 0
    assert len(res.skipped_constraints) == 0
    assert res.solved_primitives["c1"].center.x == 25.0
    assert res.solved_primitives["c1"].center.y == 25.0
