"""
test_causal_red_arc_constraints.py — Public Causal RED for Arc, Fillet, and Curved Constraints.

Demonstrates 5 concrete failure modes in production main / naive strategies:
RED-1: Infinite-line tangent false positive on distant collinear segment (Production detect_circle_constraints).
RED-2: Line-arc fillet transition omitted / ValueError in Production Strategy A.
RED-3: Arc-arc tangent S-curve transition omitted in Production Strategy A.
RED-4: Hole-to-lug (circle-to-arc) concentricity omitted in Production Strategy A.
RED-5: Out-of-sweep contact point false tangency in Naive Strategy B.
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
)


def test_red_1_distant_line_infinite_tangent_false_positive():
    """RED-1: Circle at (0, 10) with r=10. Tangent line is y=0.
    However, the line segment is at x in [100, 200], y=0 (100mm away along the tangent line).
    Production detect_circle_constraints (Strategy A) computes distance from center to infinite line,
    finds dist=10.0, gap=0.0 <= 5.0mm, and falsely flags tangency!
    Strategy D uses bounded line segment projection, finds closest point is (100, 0),
    distance is hypot(100, 10) = 100.5mm, gap = 90.5mm > 5.0mm, correctly rejecting.
    """
    circ = make_circle(center=(0.0, 10.0), radius=10.0, id_="circ_1")
    # Distant line along the y=0 tangent line
    distant_line = make_line((100.0, 0.0), (200.0, 0.0), id_="line_distant")

    # Strategy A: Falsely emits tangent constraint!
    strat_a_res = run_strategy_a([distant_line, circ])
    tangents_a = [c for c in strat_a_res if c.type == "tangent"]
    assert len(tangents_a) == 1, "Strategy A should reproduce false positive tangent"
    assert tangents_a[0].primitive_ids == ["line_distant", "circ_1"]

    # Strategy D: Correctly rejects false tangency
    strat_d_res = detect_arc_fillet_constraints([distant_line, circ])
    tangents_d = [c for c in strat_d_res if c.type == "tangent"]
    assert len(tangents_d) == 0, "Strategy D must reject distant line from circle tangency"


def test_red_2_line_arc_fillet_omitted_in_strategy_a():
    """RED-2: Quarter-arc fillet connecting horizontal line y=10 (x: 0..50) to vertical line x=60 (y: 20..70).
    Fillet arc: center=(50, 10), radius=10, sweep: 270 deg to 360 deg.
    At 270 deg: (50, 0) -> touches line 1 tangent!
    At 0 deg: (60, 10) -> touches vertical line x=60 from y=10 to 60 tangent!
    Strategy A does not support arc primitives and completely omits or raises on arc.
    Strategy D detects tangency for both line1-arc and line2-arc, plus coincident endpoints.
    """
    line1 = make_line((0.0, 0.0), (50.0, 0.0), id_="line_h")
    fillet = make_arc(center=(50.0, 10.0), radius=10.0, start_deg=270.0, end_deg=360.0, id_="fillet_arc")
    line2 = make_line((60.0, 10.0), (60.0, 60.0), id_="line_v")

    # Strategy A ignores arc entirely
    strat_a_res = run_strategy_a([line1, fillet, line2])
    tangents_a = [c for c in strat_a_res if c.type == "tangent"]
    assert len(tangents_a) == 0, "Strategy A completely ignores arc fillets"

    # Strategy D detects tangent on both lines
    strat_d_res = detect_arc_fillet_constraints([line1, fillet, line2])
    tangents_d = [c for c in strat_d_res if c.type == "tangent"]
    assert len(tangents_d) == 2, "Strategy D must detect tangency for both fillet connections"
    assert {tuple(c.primitive_ids) for c in tangents_d} == {("line_h", "fillet_arc"), ("line_v", "fillet_arc")}

    # Also detects coincident endpoints
    coinc = [c for c in strat_d_res if c.type == "coincident_endpoint"]
    assert len(coinc) == 2


def test_red_3_arc_arc_s_curve_tangency_omitted_in_strategy_a():
    """RED-3: S-curve formed by two tangent arcs:
    Arc 1: center=(20, 20), radius=20, sweep: 0 to 90 deg. At 90 deg: point=(20, 40).
    Arc 2: center=(20, 60), radius=20, sweep: 180 to 270 deg. At 270 deg: point=(20, 40).
    Center distance = 40 = r1 + r2. External tangency at (20, 40).
    Strategy A completely ignores arc-arc relations.
    Strategy D detects arc-arc external tangency.
    """
    arc1 = make_arc(center=(20.0, 20.0), radius=20.0, start_deg=0.0, end_deg=90.0, id_="arc_s1")
    arc2 = make_arc(center=(20.0, 60.0), radius=20.0, start_deg=180.0, end_deg=270.0, id_="arc_s2")

    strat_a_res = run_strategy_a([arc1, arc2])
    assert len(strat_a_res) == 0, "Strategy A cannot detect arc-arc constraints"

    strat_d_res = detect_arc_fillet_constraints([arc1, arc2])
    tangents_d = [c for c in strat_d_res if c.type == "tangent"]
    assert len(tangents_d) == 1, "Strategy D must detect arc-arc tangency in S-curve"
    assert set(tangents_d[0].primitive_ids) == {"arc_s1", "arc_s2"}


def test_red_4_circle_arc_mounting_lug_concentricity_omitted_in_strategy_a():
    """RED-4: Mounting lug: outer semicircular arc center=(50, 50), r=25, sweep: 0 to 180 deg.
    Inner mounting hole: circle center=(50, 50), r=10.
    Strategy A only handles circle-circle concentricity; circle-arc is ignored.
    Strategy D detects concentricity between circle and arc.
    """
    lug_outer = make_arc(center=(50.0, 50.0), radius=25.0, start_deg=0.0, end_deg=180.0, id_="lug_arc")
    bolt_hole = make_circle(center=(50.0, 50.0), radius=10.0, id_="bolt_hole")

    strat_a_res = run_strategy_a([lug_outer, bolt_hole])
    concentric_a = [c for c in strat_a_res if c.type == "concentric"]
    assert len(concentric_a) == 0, "Strategy A omits circle-arc concentricity"

    strat_d_res = detect_arc_fillet_constraints([lug_outer, bolt_hole])
    concentric_d = [c for c in strat_d_res if c.type == "concentric"]
    assert len(concentric_d) == 1, "Strategy D must detect concentricity between outer lug arc and bolt hole"
    assert set(concentric_d[0].primitive_ids) == {"lug_arc", "bolt_hole"}


def test_red_5_out_of_sweep_contact_point_false_tangency_in_strategy_b():
    """RED-5: Line is tangent to the circle containing the arc, but contact point is OUTSIDE the arc sweep.
    Arc: center=(0, 0), radius=20, sweep: 0 to 90 deg (first quadrant only).
    Line: horizontal line y=-20 from x=-30 to +30.
    Infinite line y=-20 is tangent to the circle at (0, -20) (angle = 270 deg).
    Angle 270 deg is NOT in [0, 90] sweep!
    Naive Strategy B ignores sweep and flags tangency.
    Strategy D checks sweep interval and rejects tangency.
    """
    arc_q1 = make_arc(center=(0.0, 0.0), radius=20.0, start_deg=0.0, end_deg=90.0, id_="arc_q1")
    line_bottom = make_line((-30.0, -20.0), (30.0, -20.0), id_="line_bottom")

    strat_b_res = run_strategy_b([arc_q1, line_bottom])
    tangents_b = [c for c in strat_b_res if c.type == "tangent"]
    assert len(tangents_b) == 1, "Strategy B must reproduce false tangency on out-of-sweep contact"

    strat_d_res = detect_arc_fillet_constraints([arc_q1, line_bottom])
    tangents_d = [c for c in strat_d_res if c.type == "tangent"]
    assert len(tangents_d) == 0, "Strategy D must reject out-of-sweep contact point"
