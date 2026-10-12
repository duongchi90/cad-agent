"""
test_bolt_circle_benchmark.py — Multi-Strategy Benchmark Suite for Bolt Circle Pattern Recognition.

Epic: CIRCULAR_PITCH_BOLT_PATTERN_RECOGNITION_V1
Role: ANTIGRAVITY_RESEARCH

Benchmarks Strategies A, B, C, D across 8 mechanical engineering scenarios:
1. Scenario 1: 4-Hole Pipe Flange (PCD=100mm, 90 deg)
2. Scenario 2: 6-Hole Motor End-Bell (PCD=150mm, 60 deg)
3. Scenario 3: 8-Hole Wheel Hub (PCD=114.3mm, 45 deg)
4. Scenario 4: 12-Hole Pressure Flange (PCD=200mm, 30 deg)
5. Scenario 5: Sector 3-Hole Arc Pattern (pitch=45 deg)
6. Scenario 6: Dual Concentric Bolt Circles (inner 4-hole + outer 8-hole)
7. Scenario 7: Mixed Scene (1 flange pattern + 4 scattered chassis holes)
8. Scenario 8: Linear Hole Row (4 holes in a straight line -> rejected)
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

from primitive_ir_lib.models import CircleGeometry, Point2D, Primitive, Trace
from semantic_ir_lib.pattern_compound import build_compound_parts as run_strategy_a_compound

from bolt_circle_engine import (
    detect_bolt_circle_patterns,
    run_strategy_b_patterns,
    run_strategy_c_patterns,
)


def _circle(id_: str, cx: float, cy: float, radius: float = 5.0) -> Primitive:
    return Primitive(
        id=id_,
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(int(cx - radius), int(cy - radius), int(cx + radius), int(cy + radius))),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=radius),
    )


def test_scenario_1_four_hole_pipe_flange():
    """Scenario 1: 4-Hole Flange (PCD=100mm, 90 deg pitch)."""
    pcd_r = 50.0
    center_c = _circle("C0", 0.0, 0.0, 20.0)
    holes = [
        _circle("H1", 50.0, 0.0, 5.0),
        _circle("H2", 0.0, 50.0, 5.0),
        _circle("H3", -50.0, 0.0, 5.0),
        _circle("H4", 0.0, -50.0, 5.0),
    ]
    scene = [center_c] + holes

    res_a = run_strategy_a_compound(scene, [])
    res_b = run_strategy_b_patterns(scene)
    res_c = run_strategy_c_patterns(scene)
    res_d = detect_bolt_circle_patterns(scene)

    assert len(res_a) == 0
    assert len(res_b) == 1
    assert len(res_c) == 1
    assert len(res_d) == 1
    assert res_d[0].hole_count == 4
    assert res_d[0].center_circle_id == "C0"


def test_scenario_2_six_hole_motor_end_bell():
    """Scenario 2: 6-Hole Motor End-Bell (PCD=150mm, 60 deg pitch)."""
    pcd_r = 75.0
    holes = []
    for i in range(6):
        a = math.radians(i * 60.0)
        holes.append(_circle(f"M{i+1}", pcd_r * math.cos(a), pcd_r * math.sin(a), 6.0))

    res_a = run_strategy_a_compound(holes, [])
    res_d = detect_bolt_circle_patterns(holes)

    assert len(res_a) == 0
    assert len(res_d) == 1
    assert res_d[0].hole_count == 6
    assert math.isclose(res_d[0].angular_pitch_deg, 60.0, abs_tol=0.1)


def test_scenario_3_eight_hole_wheel_hub():
    """Scenario 3: 8-Hole Wheel Hub (PCD=114.3mm, 45 deg pitch)."""
    pcd_r = 57.15
    hub_bore = _circle("Bore", 0.0, 0.0, 30.0)
    holes = []
    for i in range(8):
        a = math.radians(i * 45.0)
        holes.append(_circle(f"W{i+1}", pcd_r * math.cos(a), pcd_r * math.sin(a), 7.0))
    scene = [hub_bore] + holes

    res_d = detect_bolt_circle_patterns(scene)
    assert len(res_d) == 1
    assert res_d[0].hole_count == 8
    assert math.isclose(res_d[0].pitch_radius_mm, 57.15, abs_tol=0.1)


def test_scenario_4_twelve_hole_pressure_flange():
    """Scenario 4: 12-Hole Pressure Flange (PCD=200mm, 30 deg pitch)."""
    pcd_r = 100.0
    flange_bore = _circle("FlangeBore", 0.0, 0.0, 50.0)
    holes = []
    for i in range(12):
        a = math.radians(i * 30.0)
        holes.append(_circle(f"P{i+1}", pcd_r * math.cos(a), pcd_r * math.sin(a), 8.0))
    scene = [flange_bore] + holes

    res_d = detect_bolt_circle_patterns(scene)
    assert len(res_d) == 1
    assert res_d[0].hole_count == 12
    assert math.isclose(res_d[0].angular_pitch_deg, 30.0, abs_tol=0.1)


def test_scenario_5_sector_three_hole_arc():
    """Scenario 5: Sector 3-Hole Arc Pattern (pitch=45 deg across quadrant)."""
    pcd_r = 60.0
    holes = [
        _circle("S1", pcd_r * math.cos(0.0), pcd_r * math.sin(0.0), 5.0),
        _circle("S2", pcd_r * math.cos(math.radians(45.0)), pcd_r * math.sin(math.radians(45.0)), 5.0),
        _circle("S3", pcd_r * math.cos(math.radians(90.0)), pcd_r * math.sin(math.radians(90.0)), 5.0),
    ]

    res_d = detect_bolt_circle_patterns(holes)
    assert len(res_d) == 1
    assert res_d[0].hole_count == 3
    assert res_d[0].is_full_circle is False
    assert math.isclose(res_d[0].angular_pitch_deg, 45.0, abs_tol=0.1)


def test_scenario_6_dual_concentric_bolt_circles():
    """Scenario 6: Dual concentric bolt circles (inner 4-hole PCD=80mm, outer 8-hole PCD=160mm)."""
    cen = _circle("Cen", 0.0, 0.0, 15.0)

    # Inner 4 holes on R=40mm (radius=4.0)
    inner = [
        _circle("In1", 40.0, 0.0, 4.0),
        _circle("In2", 0.0, 40.0, 4.0),
        _circle("In3", -40.0, 0.0, 4.0),
        _circle("In4", 0.0, -40.0, 4.0),
    ]

    # Outer 8 holes on R=80mm (radius=6.0)
    outer = []
    for i in range(8):
        a = math.radians(i * 45.0 + 22.5)
        outer.append(_circle(f"Out{i+1}", 80.0 * math.cos(a), 80.0 * math.sin(a), 6.0))

    scene = [cen] + inner + outer

    res_d = detect_bolt_circle_patterns(scene)
    assert len(res_d) == 2, f"Expected 2 concentric patterns, got {len(res_d)}"
    counts = {p.hole_count for p in res_d}
    assert counts == {4, 8}


def test_scenario_7_mixed_flange_and_scattered_scene():
    """Scenario 7: 1 4-hole flange + 4 scattered random chassis holes."""
    flange = [
        _circle("F_cen", 0.0, 0.0, 20.0),
        _circle("F1", 50.0, 0.0, 5.0),
        _circle("F2", 0.0, 50.0, 5.0),
        _circle("F3", -50.0, 0.0, 5.0),
        _circle("F4", 0.0, -50.0, 5.0),
    ]
    # Scattered holes far away
    scattered = [
        _circle("Chassis1", 300.0, 100.0, 5.0),
        _circle("Chassis2", 350.0, 150.0, 5.0),
        _circle("Chassis3", 280.0, 200.0, 5.0),
        _circle("Chassis4", 400.0, 120.0, 5.0),
    ]
    scene = flange + scattered

    # Strategy C merges all 8 holes because they have equal radius 5.0!
    res_c = run_strategy_c_patterns(scene)
    assert len(res_c) == 1
    assert res_c[0].hole_count == 8  # False group!

    # Strategy D isolates the true 4-hole flange and rejects scattered holes
    res_d = detect_bolt_circle_patterns(scene)
    assert len(res_d) == 1
    assert res_d[0].hole_count == 4
    assert set(res_d[0].hole_ids) == {"F1", "F2", "F3", "F4"}


def test_scenario_8_linear_hole_row_negative():
    """Scenario 8: 4 holes arranged in a straight line (collinear) -> must NOT form circular pattern."""
    line_holes = [
        _circle("L1", 0.0, 0.0, 5.0),
        _circle("L2", 20.0, 0.0, 5.0),
        _circle("L3", 40.0, 0.0, 5.0),
        _circle("L4", 60.0, 0.0, 5.0),
    ]

    res_d = detect_bolt_circle_patterns(line_holes)
    assert len(res_d) == 0, "Linear hole row must not be classified as a circular bolt pattern"
