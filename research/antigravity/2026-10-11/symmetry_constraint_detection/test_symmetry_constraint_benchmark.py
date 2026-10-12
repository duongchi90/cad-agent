"""
test_symmetry_constraint_benchmark.py
Empirical Strategy Benchmark Suite comparing Strategies A-D across 8 representative mechanical CAD scenarios:
- Strategy A: Current Production Baseline (detect_constraints / detect_circle_constraints)
- Strategy B: Bounding Box Midpoint Pairing
- Strategy C: Pairwise Perpendicular Bisector Induction
- Strategy D: Consensus Axis & Reflection Invariant Oracle
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

from primitive_ir_lib.models import (
    Point2D, Primitive, LineGeometry, CircleGeometry,
    PrimitiveIRDocument, Trace, SourceDocument, Calibration
)
from symmetry_constraint_engine import (
    SymmetryAxis,
    detect_symmetry_strategy_a,
    detect_symmetry_strategy_b,
    detect_symmetry_strategy_c,
    detect_symmetry_strategy_d,
)


def _make_line(id_: str, x0: float, y0: float, x1: float, y1: float, layer: str = "UNCLASSIFIED") -> Primitive:
    return Primitive(
        id=id_,
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(int(min(x0, x1)), int(min(y0, y1)), int(max(x0, x1)), int(max(y0, y1)))),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
        layer=layer,
    )


def _make_circle(id_: str, cx: float, cy: float, r: float, layer: str = "UNCLASSIFIED") -> Primitive:
    return Primitive(
        id=id_,
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(int(cx - r), int(cy - r), int(cx + r), int(cy + r))),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
        layer=layer,
    )


def test_benchmark_scenario_01_stepped_shaft_parallel_steps():
    """Scenario 1: Stepped shaft with horizontal centerline and 2 symmetric step lines."""
    l_axis = _make_line("axis", 0.0, 0.0, 120.0, 0.0, layer="CENTER")
    l_step1_top = _make_line("s1_top", 0.0, 20.0, 60.0, 20.0)
    l_step1_bot = _make_line("s1_bot", 0.0, -20.0, 60.0, -20.0)
    l_step2_top = _make_line("s2_top", 60.0, 15.0, 120.0, 15.0)
    l_step2_bot = _make_line("s2_bot", 60.0, -15.0, 120.0, -15.0)

    lines = [l_axis, l_step1_top, l_step1_bot, l_step2_top, l_step2_bot]
    circles = []

    res_a = detect_symmetry_strategy_a(lines, circles)
    res_b = detect_symmetry_strategy_b(lines, circles)
    res_c = detect_symmetry_strategy_c(lines, circles)
    res_d = detect_symmetry_strategy_d(lines, circles)

    # Strategy A: 0 symmetry pairs
    assert len(res_a.symmetric_pairs) == 0

    # Strategy D: exactly 2 symmetric line pairs discovered
    assert len(res_d.symmetric_pairs) == 2
    pairs_found = {tuple(sorted(p.primitive_ids)) for p in res_d.symmetric_pairs}
    assert ("s1_bot", "s1_top") in pairs_found
    assert ("s2_bot", "s2_top") in pairs_found


def test_benchmark_scenario_02_symmetrical_chamfers():
    """Scenario 2: Symmetrical 45 deg chamfers across horizontal centerline."""
    l_axis = _make_line("axis", 0.0, 0.0, 50.0, 0.0, layer="CENTER")
    l_ch_top = _make_line("ch_top", 0.0, 15.0, 5.0, 20.0)    # dx=5, dy=5 -> 45 deg
    l_ch_bot = _make_line("ch_bot", 0.0, -15.0, 5.0, -20.0)  # dx=5, dy=-5 -> -45 deg

    lines = [l_axis, l_ch_top, l_ch_bot]
    circles = []

    res_a = detect_symmetry_strategy_a(lines, circles)
    res_b = detect_symmetry_strategy_b(lines, circles)
    res_d = detect_symmetry_strategy_d(lines, circles)

    # Strategy A only sees equal_length, 0 symmetry
    assert len(res_a.symmetric_pairs) == 0

    # Strategy D accurately detects chamfer symmetry
    assert len(res_d.symmetric_pairs) == 1
    assert set(res_d.symmetric_pairs[0].primitive_ids) == {"ch_top", "ch_bot"}
    assert res_d.symmetric_pairs[0].endpoint_pairing == ("start", "start")


def test_benchmark_scenario_03_flange_dual_bolt_holes():
    """Scenario 3: Flange with dual bolt holes symmetric about vertical centerline."""
    l_axis = _make_line("axis", 50.0, 0.0, 50.0, 100.0, layer="CENTER")
    hole_left = _make_circle("h_left", 30.0, 50.0, 5.0)
    hole_right = _make_circle("h_right", 70.0, 50.0, 5.0)

    lines = [l_axis]
    circles = [hole_left, hole_right]

    res_a = detect_symmetry_strategy_a(lines, circles)
    res_d = detect_symmetry_strategy_d(lines, circles)

    assert len(res_a.symmetric_pairs) == 0

    assert len(res_d.symmetric_pairs) == 1
    p = res_d.symmetric_pairs[0]
    assert p.feature_type == "circle_pair"
    assert set(p.primitive_ids) == {"h_left", "h_right"}


def test_benchmark_scenario_04_tapered_conical_section():
    """Scenario 4: Tapered section with +/- 7 deg draft angle across horizontal axis."""
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    # Top taper: (10, 20) to (90, 30) -> dy=10, dx=80 -> ~7.125 deg
    l_tap_top = _make_line("tap_top", 10.0, 20.0, 90.0, 30.0)
    # Bot taper: (10, -20) to (90, -30) -> dy=-10, dx=80 -> ~-7.125 deg
    l_tap_bot = _make_line("tap_bot", 10.0, -20.0, 90.0, -30.0)

    lines = [l_axis, l_tap_top, l_tap_bot]
    circles = []

    res_a = detect_symmetry_strategy_a(lines, circles)
    res_d = detect_symmetry_strategy_d(lines, circles)

    assert len(res_a.symmetric_pairs) == 0
    assert len(res_d.symmetric_pairs) == 1
    assert set(res_d.symmetric_pairs[0].primitive_ids) == {"tap_top", "tap_bot"}


def test_benchmark_scenario_05_inclined_non_cardinal_axis():
    """Scenario 5: Inclined symmetry axis at 45 deg with symmetric slot lines."""
    # Axis along y = x
    l_axis = _make_line("axis", 0.0, 0.0, 80.0, 80.0, layer="CENTER")
    # Offset +10 along normal (-sqrt(2)/2, sqrt(2)/2): (0-7.071, 0+7.071) to (80-7.071, 80+7.071)
    l_slot1 = _make_line("slot1", -7.071, 7.071, 72.929, 87.071)
    # Offset -10 along normal: (0+7.071, 0-7.071) to (80+7.071, 80-7.071)
    l_slot2 = _make_line("slot2", 7.071, -7.071, 87.071, 72.929)

    lines = [l_axis, l_slot1, l_slot2]
    circles = []

    res_b = detect_symmetry_strategy_b(lines, circles)
    res_d = detect_symmetry_strategy_d(lines, circles)

    # Strategy B fails on 45 deg inclined axis: it only checks H/V, so it proposes a 0 deg horizontal axis!
    assert res_b.axes[0].angle_deg == 0.0  # False axis

    # Strategy D correctly detects 45 deg axis symmetry
    assert len(res_d.symmetric_pairs) == 1
    assert set(res_d.symmetric_pairs[0].primitive_ids) == {"slot1", "slot2"}
    assert round(res_d.axes[0].angle_deg, 1) == 45.0


def test_benchmark_scenario_06_asymmetric_external_tab_robustness():
    """Scenario 6: Asymmetric external tab on an otherwise symmetric part.
    Strategy B's bounding box shifts, causing false vertical axis election.
    Strategy D anchors to true consensus centerline.
    """
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    l_top = _make_line("l_top", 10.0, 25.0, 90.0, 25.0)
    l_bot = _make_line("l_bot", 10.0, -25.0, 90.0, -25.0)
    # Asymmetric tab protruding far to the top right at y = +80
    l_tab1 = _make_line("tab1", 80.0, 25.0, 80.0, 80.0)
    l_tab2 = _make_line("tab2", 80.0, 80.0, 100.0, 80.0)

    lines = [l_axis, l_top, l_bot, l_tab1, l_tab2]
    circles = []

    res_b = detect_symmetry_strategy_b(lines, circles)
    res_d = detect_symmetry_strategy_d(lines, circles)

    # Strategy B is deceived by bounding box shift: cy is pushed to +27.5mm, so it fails the horizontal axis
    # and falsely selects a vertical axis (axis_bbox_v)
    assert res_b.axes[0].id == "axis_bbox_v"

    # Strategy D uses consensus/explicit axis and correctly recognizes l_top and l_bot across horizontal axis
    assert len(res_d.symmetric_pairs) == 1
    assert set(res_d.symmetric_pairs[0].primitive_ids) == {"l_top", "l_bot"}
    assert res_d.axes[0].angle_deg == 0.0


def test_benchmark_scenario_07_self_symmetric_perpendicular_shoulder():
    """Scenario 7: Transverse shoulder line passing perpendicularly through centerline and bisected by it."""
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    # Vertical line from (50, -30) to (50, +30)
    l_shoulder = _make_line("shoulder", 50.0, -30.0, 50.0, 30.0)

    lines = [l_axis, l_shoulder]
    circles = []

    res_a = detect_symmetry_strategy_a(lines, circles)
    res_d = detect_symmetry_strategy_d(lines, circles)

    assert len(res_a.symmetric_pairs) == 0

    assert len(res_d.symmetric_pairs) == 1
    p = res_d.symmetric_pairs[0]
    assert p.feature_type == "self_symmetric_line"
    assert p.primitive_ids == ["shoulder"]


def test_benchmark_scenario_08_complex_mechanical_workpiece_multi_feature():
    """Scenario 8: Full mechanical workpiece: 2 cylindrical steps, 2 chamfers, 2 bolt holes, 1 shoulder."""
    l_axis = _make_line("axis", 0.0, 0.0, 140.0, 0.0, layer="CENTER")
    # Step 1
    s1_top = _make_line("s1_top", 10.0, 25.0, 60.0, 25.0)
    s1_bot = _make_line("s1_bot", 10.0, -25.0, 60.0, -25.0)
    # Step 2
    s2_top = _make_line("s2_top", 60.0, 15.0, 120.0, 15.0)
    s2_bot = _make_line("s2_bot", 60.0, -15.0, 120.0, -15.0)
    # Chamfers
    ch_top = _make_line("ch_top", 0.0, 20.0, 10.0, 25.0)
    ch_bot = _make_line("ch_bot", 0.0, -20.0, 10.0, -25.0)
    # Shoulder
    sh = _make_line("sh", 60.0, -25.0, 60.0, 25.0)
    # Holes
    h1 = _make_circle("h1", 35.0, 12.0, 4.0)
    h2 = _make_circle("h2", 35.0, -12.0, 4.0)

    lines = [l_axis, s1_top, s1_bot, s2_top, s2_bot, ch_top, ch_bot, sh]
    circles = [h1, h2]

    res_a = detect_symmetry_strategy_a(lines, circles)
    res_d = detect_symmetry_strategy_d(lines, circles)

    # Strategy A detects 0 symmetry
    assert len(res_a.symmetric_pairs) == 0

    # Strategy D detects all 5 symmetric features (2 steps + 1 chamfer + 1 shoulder + 1 hole pair)
    assert len(res_d.symmetric_pairs) == 5
    types = {p.feature_type for p in res_d.symmetric_pairs}
    assert "line_pair" in types
    assert "circle_pair" in types
    assert "self_symmetric_line" in types
