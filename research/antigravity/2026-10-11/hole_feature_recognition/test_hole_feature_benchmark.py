"""Empirical benchmark comparing Strategies A-D across 8 mechanical hole scenarios.

Scenarios:
1. Plan-view simple through hole
2. Plan-view counterbore hole (concentric circles)
3. Section-view counterbore hole (stepped bore)
4. Section-view blind hole with 118° conical drill point tip
5. Section-view countersink hole (90° cone)
6. Cross-view synthesis (Plan concentric + Section stepped profile)
7. Multiple adjacent holes disambiguation
8. Vertical-axis hole in section view
"""

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

from primitive_ir_lib.models import Point2D, CircleGeometry, LineGeometry, Primitive, Trace
from hole_feature_engine import (
    HoleType,
    HoleRepresentationKind,
    extract_holes_strategy_a,
    extract_holes_strategy_b,
    extract_holes_strategy_c,
    extract_holes_strategy_d,
)


def _make_line(id_: str, x0: float, y0: float, x1: float, y1: float) -> Primitive:
    return Primitive(
        id=id_,
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


def _make_circle(id_: str, cx: float, cy: float, r: float) -> Primitive:
    return Primitive(
        id=id_,
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(cx - r, cy - r, cx + r, cy + r)),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
    )


def test_benchmark_scenario_01_plan_view_simple_through_hole():
    """Scenario 1: Simple through hole in plan view (diam = 12.0mm, r = 6.0mm)."""
    c = _make_circle("hole_01", 50.0, 50.0, 6.0)
    primitives = [c]

    res_d = extract_holes_strategy_d(primitives)
    assert len(res_d.features) == 1
    f = res_d.features[0]
    assert f.hole_type == HoleType.SIMPLE_THROUGH
    assert f.representation == HoleRepresentationKind.PLAN_VIEW
    assert f.through_diameter_mm == 12.0
    assert f.is_through is True


def test_benchmark_scenario_02_plan_view_counterbore_hole():
    """Scenario 2: Counterbore hole in plan view: inner d=10.0mm (r=5.0), outer D_cb=20.0mm (r=10.0)."""
    c_inner = _make_circle("c_in", 80.0, 80.0, 5.0)
    c_outer = _make_circle("c_out", 80.0, 80.0, 10.0)
    primitives = [c_inner, c_outer]

    # Strat A treats as 2 independent holes
    res_a = extract_holes_strategy_a(primitives)
    assert len(res_a.features) == 2
    assert all(feat.hole_type == HoleType.SIMPLE_THROUGH for feat in res_a.features)

    # Strat D pairs into single counterbore feature
    res_d = extract_holes_strategy_d(primitives)
    assert len(res_d.features) == 1
    f = res_d.features[0]
    assert f.hole_type == HoleType.COUNTERBORE
    assert f.through_diameter_mm == 10.0
    assert f.counterbore_diameter_mm == 20.0
    assert f.axis_origin == Point2D(80.0, 80.0)


def test_benchmark_scenario_03_section_view_counterbore_hole():
    """Scenario 3: Stepped counterbore hole in section view.
    Outer bore: diam 20.0mm, depth 6.0mm (x=10 to x=16, y=40 to y=60).
    Inner bore: diam 10.0mm, depth 24.0mm (x=16 to x=40, y=45 to y=55).
    """
    # Outer bore walls (y = 60 and y = 40)
    w_out_top = _make_line("w_out_t", 10.0, 60.0, 16.0, 60.0)
    w_out_bot = _make_line("w_out_b", 10.0, 40.0, 16.0, 40.0)
    # Inner bore walls (y = 55 and y = 45)
    w_in_top = _make_line("w_in_t", 16.0, 55.0, 40.0, 55.0)
    w_in_bot = _make_line("w_in_b", 16.0, 45.0, 40.0, 45.0)
    # Shoulders at x=16
    sh_top = _make_line("sh_t", 16.0, 55.0, 16.0, 60.0)
    sh_bot = _make_line("sh_b", 16.0, 40.0, 16.0, 45.0)

    primitives = [w_out_top, w_out_bot, w_in_top, w_in_bot, sh_top, sh_bot]

    # Strat A emits 0 features
    res_a = extract_holes_strategy_a(primitives)
    assert len(res_a.features) == 0

    # Strat D recovers counterbore geometry
    res_d = extract_holes_strategy_d(primitives)
    assert len(res_d.features) == 1
    f = res_d.features[0]
    assert f.hole_type == HoleType.COUNTERBORE
    assert f.through_diameter_mm == 10.0
    assert f.counterbore_diameter_mm == 20.0
    assert f.counterbore_depth_mm == 6.0
    assert f.total_depth_mm == 30.0


def test_benchmark_scenario_04_section_view_blind_hole_with_118deg_tip():
    """Scenario 4: Blind hole in section view: diam = 14.0mm (y=43 to y=57),
    cylindrical depth = 25.0mm (x=10 to x=35), terminating in 118° drill point tip (apex at x=39.2).
    Included angle 118° -> half-angle to axis = 59°, angle to transverse = 31°.
    """
    w_top = _make_line("w_top", 10.0, 57.0, 35.0, 57.0)
    w_bot = _make_line("w_bot", 10.0, 43.0, 35.0, 43.0)
    # Conical tip: from (35, 57) to (39.2, 50.0) and from (35, 43) to (39.2, 50.0)
    # dy = 7.0, dx = 7.0 / tan(59°) = 7.0 / 1.6643 = 4.206
    tip_top = _make_line("tip_t", 35.0, 57.0, 39.2, 50.0)
    tip_bot = _make_line("tip_b", 35.0, 43.0, 39.2, 50.0)

    primitives = [w_top, w_bot, tip_top, tip_bot]

    res_d = extract_holes_strategy_d(primitives)
    assert len(res_d.features) == 1
    f = res_d.features[0]
    assert f.hole_type == HoleType.BLIND
    assert f.through_diameter_mm == 14.0
    assert f.is_through is False
    assert f.drill_point_angle_deg is not None
    assert abs(f.drill_point_angle_deg - 118.0) <= 3.0


def test_benchmark_scenario_05_section_view_countersink_hole():
    """Scenario 5: Countersink hole in section view:
    Through-hole diam = 8.0mm (y=46 to y=54), length from x=14 to x=34.
    Countersink cone expands from diam 8.0 to diam 16.0mm (y=42 to y=58) at x=10 with 90° included cone (45° chamfer).
    """
    w_top = _make_line("w_top", 14.0, 54.0, 34.0, 54.0)
    w_bot = _make_line("w_bot", 14.0, 46.0, 34.0, 46.0)
    # 45° chamfer: from (10, 58) to (14, 54) and (10, 42) to (14, 46)
    cs_top = _make_line("cs_top", 10.0, 58.0, 14.0, 54.0)
    cs_bot = _make_line("cs_bot", 10.0, 42.0, 14.0, 46.0)

    primitives = [w_top, w_bot, cs_top, cs_bot]

    res_d = extract_holes_strategy_d(primitives)
    assert len(res_d.features) == 1
    f = res_d.features[0]
    assert f.hole_type == HoleType.COUNTERSINK
    assert f.through_diameter_mm == 8.0
    assert f.countersink_angle_deg is not None
    assert abs(f.countersink_angle_deg - 90.0) <= 2.0


def test_benchmark_scenario_06_cross_view_synthesis_plan_and_section():
    """Scenario 6: Cross-view synthesis between plan-view concentric circles and section-view stepped profile."""
    # Plan view at (100, 100): inner r=5.0 (d=10), outer r=9.0 (d=18)
    c_in = _make_circle("c_in", 100.0, 100.0, 5.0)
    c_out = _make_circle("c_out", 100.0, 100.0, 9.0)

    # Section view at x=200: outer d=18 (y=41 to 59), inner d=10 (y=45 to 55)
    w_out_t = _make_line("w_ot", 200.0, 59.0, 205.0, 59.0)
    w_out_b = _make_line("w_ob", 200.0, 41.0, 205.0, 41.0)
    w_in_t = _make_line("w_it", 205.0, 55.0, 225.0, 55.0)
    w_in_b = _make_line("w_ib", 205.0, 45.0, 225.0, 45.0)
    sh_t = _make_line("sh_t", 205.0, 55.0, 205.0, 59.0)
    sh_b = _make_line("sh_b", 205.0, 41.0, 205.0, 45.0)

    primitives = [c_in, c_out, w_out_t, w_out_b, w_in_t, w_in_b, sh_t, sh_b]

    res_d = extract_holes_strategy_d(primitives)
    # Synthesized feature emitted
    assert len(res_d.features) == 1
    f = res_d.features[0]
    assert f.representation == HoleRepresentationKind.SYNTHESIZED_CROSS_VIEW
    assert f.hole_type == HoleType.COUNTERBORE
    assert f.through_diameter_mm == 10.0
    assert f.counterbore_diameter_mm == 18.0
    assert f.axis_origin == Point2D(100.0, 100.0)  # Inherited plan coordinates
    assert f.counterbore_depth_mm == 5.0
    assert f.total_depth_mm == 25.0


def test_benchmark_scenario_07_multiple_adjacent_holes_disambiguation():
    """Scenario 7: Multiple adjacent holes cleanly disambiguated without crosstalk."""
    # Hole 1: Plan counterbore at (50, 50)
    c1_in = _make_circle("c1_in", 50.0, 50.0, 4.0)
    c1_out = _make_circle("c1_out", 50.0, 50.0, 8.0)
    # Hole 2: Plan simple hole at (120, 50)
    c2 = _make_circle("c2", 120.0, 50.0, 6.0)

    primitives = [c1_in, c1_out, c2]
    res_d = extract_holes_strategy_d(primitives)

    assert len(res_d.features) == 2
    types = {f.through_diameter_mm: f.hole_type for f in res_d.features}
    assert types[8.0] == HoleType.COUNTERBORE
    assert types[12.0] == HoleType.SIMPLE_THROUGH


def test_benchmark_scenario_08_steep_axis_vertical_hole_in_section():
    """Scenario 8: Vertical-axis hole in section view (walls vertical, shoulder horizontal)."""
    # Walls at x=45 and x=55 (diam 10mm), length along Y from y=20 to y=50
    w_left = _make_line("w_l", 45.0, 20.0, 45.0, 50.0)
    w_right = _make_line("w_r", 55.0, 20.0, 55.0, 50.0)

    primitives = [w_left, w_right]
    res_d = extract_holes_strategy_d(primitives)

    assert len(res_d.features) == 1
    f = res_d.features[0]
    assert f.through_diameter_mm == 10.0
    assert f.representation == HoleRepresentationKind.SECTION_VIEW
