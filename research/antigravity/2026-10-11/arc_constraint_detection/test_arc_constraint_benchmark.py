"""
test_arc_constraint_benchmark.py — Multi-Strategy Benchmark Suite for Arc & Fillet Constraints.

Benchmarks Strategies A, B, C, D across 8 engineering drawing scenarios:
1. Scenario 1: Corner Fillet Transition (2 lines + 1 tangent quarter-arc).
2. Scenario 2: Slotted Plate (2 parallel lines + 2 semicircular tangent arcs).
3. Scenario 3: Concentric Lug with Bolt Hole (1 circle + 1 concentric semicircular arc).
4. Scenario 4: Compound S-Curve (2 mutually tangent arcs).
5. Scenario 5: Distant Collinear Line (Line along tangent axis but far away).
6. Scenario 6: Out-of-Sweep Line (Line tangent to underlying circle, but outside arc angle).
7. Scenario 7: Touching Non-Tangent Corner (Line ends at arc endpoint at non-tangent angle).
8. Scenario 8: Equal Radius Multi-Fillet (4 matching R5 fillet arcs).
"""

from __future__ import annotations

import sys
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
    run_strategy_a,
    run_strategy_b,
    run_strategy_c,
)


def test_scenario_1_corner_fillet_transition():
    """Scenario 1: Corner fillet between horizontal line and vertical line.
    Line 1: (0, 0) to (40, 0).
    Arc: center=(40, 10), radius=10, sweep: 270 deg to 360 deg.
    Line 2: (50, 10) to (50, 50).
    """
    line1 = make_line((0.0, 0.0), (40.0, 0.0), id_="line_h")
    fillet = make_arc(center=(40.0, 10.0), radius=10.0, start_deg=270.0, end_deg=360.0, id_="fillet_arc")
    line2 = make_line((50.0, 10.0), (50.0, 50.0), id_="line_v")
    prims = [line1, fillet, line2]

    # Strategy A: Fails to detect arc constraints
    res_a = run_strategy_a(prims)
    assert len([c for c in res_a if c.type == "tangent"]) == 0

    # Strategy D: Correctly detects both tangencies
    res_d = detect_arc_fillet_constraints(prims)
    tangents_d = [c for c in res_d if c.type == "tangent"]
    assert len(tangents_d) == 2
    assert {tuple(c.primitive_ids) for c in tangents_d} == {("line_h", "fillet_arc"), ("line_v", "fillet_arc")}


def test_scenario_2_slotted_plate():
    """Scenario 2: Slotted plate feature with 2 parallel lines and 2 semicircular ends.
    Top line: (20, 20) to (80, 20).
    Bottom line: (20, 0) to (80, 0).
    Left arc: center=(20, 10), radius=10, sweep: 90 deg to 270 deg.
    Right arc: center=(80, 10), radius=10, sweep: 270 deg to 90 deg.
    """
    top_line = make_line((20.0, 20.0), (80.0, 20.0), id_="slot_top")
    bot_line = make_line((20.0, 0.0), (80.0, 0.0), id_="slot_bot")
    left_arc = make_arc(center=(20.0, 10.0), radius=10.0, start_deg=90.0, end_deg=270.0, id_="slot_left")
    right_arc = make_arc(center=(80.0, 10.0), radius=10.0, start_deg=270.0, end_deg=90.0, id_="slot_right")
    prims = [top_line, bot_line, left_arc, right_arc]

    # Strategy D: Detects 4 tangency pairs (top-left, bot-left, top-right, bot-right)
    # and equal radius between the two end arcs
    res_d = detect_arc_fillet_constraints(prims)
    tangents_d = [c for c in res_d if c.type == "tangent"]
    assert len(tangents_d) == 4
    equal_r = [c for c in res_d if c.type == "equal_length"]
    assert len(equal_r) == 1
    assert set(equal_r[0].primitive_ids) == {"slot_left", "slot_right"}


def test_scenario_3_concentric_lug_with_bolt_hole():
    """Scenario 3: Lug with concentric bolt hole.
    Outer arc: center=(100, 100), radius=30, sweep: 0 to 180 deg.
    Inner hole: center=(100, 100), radius=12 (circle).
    """
    lug = make_arc(center=(100.0, 100.0), radius=30.0, start_deg=0.0, end_deg=180.0, id_="lug_outer")
    hole = make_circle(center=(100.0, 100.0), radius=12.0, id_="bolt_hole")
    prims = [lug, hole]

    res_a = run_strategy_a(prims)
    assert len([c for c in res_a if c.type == "concentric"]) == 0

    res_d = detect_arc_fillet_constraints(prims)
    concentric = [c for c in res_d if c.type == "concentric"]
    assert len(concentric) == 1
    assert set(concentric[0].primitive_ids) == {"lug_outer", "bolt_hole"}


def test_scenario_4_compound_s_curve():
    """Scenario 4: S-curve transition between two opposing arcs.
    Arc 1: center=(0, 20), radius=20, sweep: 270 to 360 deg. (end at (20, 20))
    Arc 2: center=(40, 20), radius=20, sweep: 90 to 180 deg. (start at (20, 20))
    Center dist = 40 = r1 + r2. External tangency at (20, 20).
    """
    arc1 = make_arc(center=(0.0, 20.0), radius=20.0, start_deg=270.0, end_deg=360.0, id_="arc_s1")
    arc2 = make_arc(center=(40.0, 20.0), radius=20.0, start_deg=90.0, end_deg=180.0, id_="arc_s2")
    prims = [arc1, arc2]

    res_d = detect_arc_fillet_constraints(prims)
    tangents = [c for c in res_d if c.type == "tangent"]
    assert len(tangents) == 1
    assert set(tangents[0].primitive_ids) == {"arc_s1", "arc_s2"}


def test_scenario_5_distant_collinear_rejection():
    """Scenario 5: Collinear tangent axis line placed 150mm away from arc.
    Arc: center=(0, 15), radius=15, sweep: 180 to 360 deg (bottom half). Contact would be at (0, 0).
    Line: y=0, x from 150 to 250.
    """
    arc = make_arc(center=(0.0, 15.0), radius=15.0, start_deg=180.0, end_deg=360.0, id_="arc_base")
    line = make_line((150.0, 0.0), (250.0, 0.0), id_="line_far")
    prims = [arc, line]

    # Strategy B falsely detects tangency because infinite line passes tangent
    res_b = run_strategy_b(prims)
    assert len([c for c in res_b if c.type == "tangent"]) == 1

    # Strategy D rejects because line segment does not encompass contact point
    res_d = detect_arc_fillet_constraints(prims)
    assert len([c for c in res_d if c.type == "tangent"]) == 0


def test_scenario_6_out_of_sweep_rejection():
    """Scenario 6: Line touches the circle bounding box but at an angle where the arc is absent.
    Arc: center=(0, 0), radius=25, sweep: 0 to 90 deg (first quadrant).
    Line: horizontal line y=25 from x=-50 to -10 (second quadrant).
    Circle contact point would be at (0, 25) (angle = 90 deg).
    Wait, angle 90 deg is right at the boundary.
    Let's place line at x=-25 (vertical line x=-25 from y=-20 to 20).
    Circle contact point is at (-25, 0) (angle = 180 deg).
    Angle 180 deg is far outside [0, 90] sweep!
    """
    arc = make_arc(center=(0.0, 0.0), radius=25.0, start_deg=0.0, end_deg=90.0, id_="arc_q1")
    line = make_line((-25.0, -20.0), (-25.0, 20.0), id_="line_q2")
    prims = [arc, line]

    # Strategy B falsely detects tangency
    res_b = run_strategy_b(prims)
    assert len([c for c in res_b if c.type == "tangent"]) == 1

    # Strategy D rejects due to sweep angle check
    res_d = detect_arc_fillet_constraints(prims)
    assert len([c for c in res_d if c.type == "tangent"]) == 0


def test_scenario_7_touching_non_tangent_corner():
    """Scenario 7: Line touches arc endpoint orthogonally (not tangent).
    Arc: center=(0, 0), radius=20, sweep: 0 to 90 deg. Endpoint at 90 deg is (0, 20).
    Tangent vector at (0, 20) is horizontal (-1, 0).
    Line: vertical line x=0 from y=20 to y=60. (Orthogonal to tangent vector!)
    Endpoint touches at (0, 20).
    Strategy C (endpoint proximity matcher) falsely flags this as tangent because endpoints touch!
    Strategy D rejects tangency because distance from center (0,0) to line x=0 is 0.0,
    radial gap = |0 - 20| = 20mm > 5.0mm. But Strategy D correctly identifies coincident_endpoint!
    """
    arc = make_arc(center=(0.0, 0.0), radius=20.0, start_deg=0.0, end_deg=90.0, id_="arc_corner")
    line = make_line((0.0, 20.0), (0.0, 60.0), id_="line_ortho")
    prims = [arc, line]

    # Strategy C falsely flags tangency
    res_c = run_strategy_c(prims)
    assert len([c for c in res_c if c.type == "tangent"]) == 1

    # Strategy D rejects tangency, but accepts coincident_endpoint
    res_d = detect_arc_fillet_constraints(prims)
    tangents = [c for c in res_d if c.type == "tangent"]
    coincident = [c for c in res_d if c.type == "coincident_endpoint"]
    assert len(tangents) == 0, "Orthogonal touching line is NOT tangent"
    assert len(coincident) == 1, "Must detect coincident endpoint"


def test_scenario_8_equal_radius_multi_fillet():
    """Scenario 8: Four R5 fillet arcs on four corners of a rectangular plate.
    All four arcs share radius=5.0mm.
    Strategy D identifies all 6 pairwise equal radius constraints.
    """
    fillets = [
        make_arc(center=(10.0, 10.0), radius=5.0, start_deg=180.0, end_deg=270.0, id_="f1"),
        make_arc(center=(50.0, 10.0), radius=5.0, start_deg=270.0, end_deg=360.0, id_="f2"),
        make_arc(center=(50.0, 40.0), radius=5.0, start_deg=0.0, end_deg=90.0, id_="f3"),
        make_arc(center=(10.0, 40.0), radius=5.0, start_deg=90.0, end_deg=180.0, id_="f4"),
    ]
    res_d = detect_arc_fillet_constraints(fillets)
    eq_r = [c for c in res_d if c.type == "equal_length"]
    # 4 choose 2 = 6 pairs
    assert len(eq_r) == 6
    for c in eq_r:
        assert c.measured["radius_diff_percent"] == 0.0
