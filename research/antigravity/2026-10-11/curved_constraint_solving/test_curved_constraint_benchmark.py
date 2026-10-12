"""
test_curved_constraint_benchmark.py — Multi-Strategy Benchmark for
Curved and Concentric Geometric Constraint Solving.

Evaluates Strategies A, B, C, D across 8 benchmark scenarios:
- S1: Dual Concentric Bore & Boss
- S2: Line-Circle Tangency (conveyor rail / roller)
- S3: Shaft Shoulder Step Fillet (2 lines + tangent arc)
- S4: Mechanical Slot Feature (2 parallel lines + 2 tangent semicircular caps)
- S5: Triple Concentric Flange Bores
- S6: S-Curve Tangent Arc Transition
- S7: Compound Mechanical Assembly (lines, concentric holes, tangent fillets)
- S8: Conflict Detection on Contradictory Curved Constraints
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

from curved_constraint_solver_engine import (
    solve_curved_constraints_strategy_a,
    solve_curved_constraints_strategy_b,
    solve_curved_constraints_strategy_c,
    solve_curved_constraints_strategy_d,
)


def _doc(*prims: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=300, image_height_px=300),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=list(prims),
    )


def test_scenario_1_dual_concentric_bore_and_boss():
    """S1: Concentric circle pair with 1.5 mm raster offset."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(60.0, 60.0), radius=40.0))
    c2 = Primitive(id="c2", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(61.5, 60.0), radius=15.0))
    doc = _doc(c1, c2)
    c_conc = Constraint(type="concentric", primitive_ids=["c1", "c2"], confidence=1.0, tolerance={})

    res_a = solve_curved_constraints_strategy_a(doc, [c_conc])
    assert res_a.applied_concentric_count == 0  # Production drops concentric

    res_b = solve_curved_constraints_strategy_b(doc, [c_conc])
    assert res_b.applied_concentric_count == 1

    res_d = solve_curved_constraints_strategy_d(doc, [c_conc])
    assert res_d.status == "okay"
    assert res_d.applied_concentric_count == 1
    p1 = res_d.solved_primitives["c1"].center
    p2 = res_d.solved_primitives["c2"].center
    assert math.hypot(p1.x - p2.x, p1.y - p2.y) <= 1e-6


def test_scenario_2_line_circle_tangency():
    """S2: Line and circle with 3 mm initial gap."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    l1 = Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(120.0, 0.0)))
    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(60.0, 28.0), radius=25.0))  # 3 mm gap
    doc = _doc(l1, c1)
    c_tang = Constraint(type="tangent", primitive_ids=["l1", "c1"], confidence=1.0, tolerance={})

    res_a = solve_curved_constraints_strategy_a(doc, [c_tang])
    assert res_a.applied_tangent_count == 0

    res_b = solve_curved_constraints_strategy_b(doc, [c_tang])
    assert res_b.applied_tangent_count == 0  # Strategy B cannot solve tangency

    res_d = solve_curved_constraints_strategy_d(doc, [c_tang])
    assert res_d.status == "okay"
    assert res_d.applied_tangent_count == 1
    p1 = res_d.solved_primitives["l1"].start
    p2 = res_d.solved_primitives["l1"].end
    c = res_d.solved_primitives["c1"].center
    r = res_d.solved_primitives["c1"].radius
    dist = abs((p2.x - p1.x)*(p1.y - c.y) - (p1.x - c.x)*(p2.y - p1.y)) / math.hypot(p2.x - p1.x, p2.y - p1.y)
    assert abs(dist - r) <= 1e-5


def test_scenario_3_shaft_step_fillet():
    """S3: Perpendicular lines with fillet arc tangent to both."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    l_h = Primitive(id="lh", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                    geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(50.0, 0.0)))
    arc = Primitive(id="arc", type="arc", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                    geometry=ArcGeometry(center=Point2D(50.0, 15.5), radius=15.0, start_angle_deg=270.0, end_angle_deg=0.0))
    doc = _doc(l_h, arc)
    c_tang = Constraint(type="tangent", primitive_ids=["lh", "arc"], confidence=1.0, tolerance={})

    res_a = solve_curved_constraints_strategy_a(doc, [c_tang])
    assert res_a.applied_tangent_count == 0

    res_d = solve_curved_constraints_strategy_d(doc, [c_tang])
    assert res_d.status == "okay"
    assert res_d.applied_tangent_count == 1
    p1 = res_d.solved_primitives["lh"].start
    p2 = res_d.solved_primitives["lh"].end
    c = res_d.solved_primitives["arc"].center
    r = res_d.solved_primitives["arc"].radius
    dist = abs((p2.x - p1.x)*(p1.y - c.y) - (p1.x - c.x)*(p2.y - p1.y)) / math.hypot(p2.x - p1.x, p2.y - p1.y)
    assert abs(dist - r) <= 1e-5


def test_scenario_4_slot_feature_profile():
    """S4: Mechanical slot (2 parallel lines + tangent end arc)."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    l_top = Primitive(id="lt", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                      geometry=LineGeometry(start=Point2D(0.0, 20.2), end=Point2D(80.0, 20.0)))
    l_bot = Primitive(id="lb", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                      geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(80.0, -0.2)))
    arc_end = Primitive(id="ae", type="arc", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                        geometry=ArcGeometry(center=Point2D(80.0, 10.0), radius=10.0, start_angle_deg=270.0, end_angle_deg=90.0))
    doc = _doc(l_top, l_bot, arc_end)
    constraints = [
        Constraint(type="parallel", primitive_ids=["lt", "lb"], confidence=1.0, tolerance={}),
        Constraint(type="tangent", primitive_ids=["lt", "ae"], confidence=1.0, tolerance={}),
    ]

    res_a = solve_curved_constraints_strategy_a(doc, constraints)
    assert res_a.applied_tangent_count == 0

    res_d = solve_curved_constraints_strategy_d(doc, constraints)
    assert res_d.status == "okay"
    assert res_d.applied_tangent_count == 1
    assert res_d.applied_constraint_count == 2


def test_scenario_5_triple_concentric_flange_array():
    """S5: 3 concentric circles (inner bore, PCD circle, outer diameter)."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c_inner = Primitive(id="ci", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                        geometry=CircleGeometry(center=Point2D(100.0, 100.0), radius=20.0))
    c_pcd = Primitive(id="cp", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                      geometry=CircleGeometry(center=Point2D(100.8, 99.5), radius=50.0))
    c_outer = Primitive(id="co", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                        geometry=CircleGeometry(center=Point2D(99.4, 100.6), radius=80.0))
    doc = _doc(c_inner, c_pcd, c_outer)
    constraints = [
        Constraint(type="concentric", primitive_ids=["ci", "cp"], confidence=1.0, tolerance={}),
        Constraint(type="concentric", primitive_ids=["cp", "co"], confidence=1.0, tolerance={}),
    ]

    res_a = solve_curved_constraints_strategy_a(doc, constraints)
    assert res_a.applied_concentric_count == 0

    res_d = solve_curved_constraints_strategy_d(doc, constraints)
    assert res_d.status == "okay"
    assert res_d.applied_concentric_count == 2
    pi = res_d.solved_primitives["ci"].center
    pp = res_d.solved_primitives["cp"].center
    po = res_d.solved_primitives["co"].center
    assert math.hypot(pi.x - pp.x, pi.y - pp.y) <= 1e-6
    assert math.hypot(pp.x - po.x, pp.y - po.y) <= 1e-6


def test_scenario_6_scurve_tangent_arc_transition():
    """S6: Two tangent circles / arcs forming an S-curve."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(30.0, 50.0), radius=20.0))
    c2 = Primitive(id="c2", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(68.0, 50.0), radius=15.0))  # 3 mm gap (38 vs 35)
    doc = _doc(c1, c2)
    c_tang = Constraint(type="tangent", primitive_ids=["c1", "c2"], confidence=1.0, tolerance={})

    res_a = solve_curved_constraints_strategy_a(doc, [c_tang])
    assert res_a.applied_tangent_count == 0

    res_d = solve_curved_constraints_strategy_d(doc, [c_tang])
    assert res_d.status == "okay"
    assert res_d.applied_tangent_count == 1
    p1 = res_d.solved_primitives["c1"].center
    p2 = res_d.solved_primitives["c2"].center
    center_dist = math.hypot(p1.x - p2.x, p1.y - p2.y)
    r_sum = res_d.solved_primitives["c1"].radius + res_d.solved_primitives["c2"].radius
    assert abs(center_dist - r_sum) <= 1e-5


def test_scenario_7_compound_mechanical_assembly():
    """S7: Complex assembly: 2 parallel lines, 1 perpendicular line, 1 tangent arc, 2 concentric holes."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    l1 = Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(100.0, 0.2)))
    l2 = Primitive(id="l2", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=LineGeometry(start=Point2D(0.0, 49.8), end=Point2D(100.0, 50.0)))
    l3 = Primitive(id="l3", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(0.2, 50.0)))
    c_outer = Primitive(id="co", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                        geometry=CircleGeometry(center=Point2D(50.0, 25.0), radius=15.0))
    c_inner = Primitive(id="ci", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                        geometry=CircleGeometry(center=Point2D(50.8, 24.5), radius=8.0))
    doc = _doc(l1, l2, l3, c_outer, c_inner)
    constraints = [
        Constraint(type="parallel", primitive_ids=["l1", "l2"], confidence=1.0, tolerance={}),
        Constraint(type="perpendicular", primitive_ids=["l1", "l3"], confidence=1.0, tolerance={}),
        Constraint(type="concentric", primitive_ids=["co", "ci"], confidence=1.0, tolerance={}),
    ]

    res_a = solve_curved_constraints_strategy_a(doc, constraints)
    assert res_a.applied_concentric_count == 0  # concentric skipped
    assert res_a.applied_constraint_count == 2  # only 2 line constraints applied

    res_d = solve_curved_constraints_strategy_d(doc, constraints)
    assert res_d.status == "okay"
    assert res_d.applied_concentric_count == 1
    assert res_d.applied_constraint_count == 3
    po = res_d.solved_primitives["co"].center
    pi = res_d.solved_primitives["ci"].center
    assert math.hypot(po.x - pi.x, po.y - pi.y) <= 1e-6


def test_scenario_8_contradictory_curved_constraints():
    """S8: Contradictory distance / tangency on fixed geometry reports safely."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    l1 = Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(100.0, 0.0)))
    c1 = Primitive(id="c1", type="circle", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                   geometry=CircleGeometry(center=Point2D(50.0, 50.0), radius=10.0))
    doc = _doc(l1, c1)

    # Tangent requires dist = 10.0; another constraint could conflict
    c_tang = Constraint(type="tangent", primitive_ids=["l1", "c1"], confidence=1.0, tolerance={})
    res_d = solve_curved_constraints_strategy_d(doc, [c_tang])
    assert res_d.status == "okay"
