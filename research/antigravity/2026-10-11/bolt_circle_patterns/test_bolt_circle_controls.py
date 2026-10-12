"""
test_bolt_circle_controls.py — Positive Fixtures and Strong Negative Controls for Bolt Circle Patterns.

Epic: CIRCULAR_PITCH_BOLT_PATTERN_RECOGNITION_V1
Role: ANTIGRAVITY_RESEARCH
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

from primitive_ir_lib.models import CircleGeometry, LineGeometry, Point2D, Primitive, Trace
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


def _line(id_: str, x0: float, y0: float, x1: float, y1: float) -> Primitive:
    return Primitive(
        id=id_,
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(int(min(x0, x1)), int(min(y0, y1)), int(max(x0, x1)), int(max(y0, y1)))),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


# ---------------------------------------------------------------------------
# Positive Controls
# ---------------------------------------------------------------------------

def test_positive_1_five_hole_star_pattern():
    """Positive 1: 5-hole circular pattern (PCD=110mm, 72 deg pitch)."""
    pcd_r = 55.0
    holes = []
    for i in range(5):
        a = math.radians(i * 72.0)
        holes.append(_circle(f"Star{i+1}", pcd_r * math.cos(a), pcd_r * math.sin(a), 6.0))

    res = detect_bolt_circle_patterns(holes)
    assert len(res) == 1
    assert res[0].hole_count == 5
    assert math.isclose(res[0].angular_pitch_deg, 72.0, abs_tol=0.1)
    assert res[0].is_full_circle is True


def test_positive_2_sixteen_hole_turbine_flange():
    """Positive 2: 16-hole high-density turbine flange (PCD=320mm, 22.5 deg pitch)."""
    pcd_r = 160.0
    holes = []
    for i in range(16):
        a = math.radians(i * 22.5)
        holes.append(_circle(f"Turbine{i+1}", pcd_r * math.cos(a), pcd_r * math.sin(a), 8.0))

    res = detect_bolt_circle_patterns(holes)
    assert len(res) == 1
    assert res[0].hole_count == 16
    assert math.isclose(res[0].angular_pitch_deg, 22.5, abs_tol=0.1)


def test_positive_3_multi_pattern_plate():
    """Positive 3: Multi-pattern plate (1 center bore, 1 inner 4-hole pattern, 1 outer 6-hole pattern)."""
    cen = _circle("CenterBore", 0.0, 0.0, 30.0)

    inner_holes = [
        _circle(f"In{i+1}", 50.0 * math.cos(math.radians(i * 90.0)), 50.0 * math.sin(math.radians(i * 90.0)), 4.0)
        for i in range(4)
    ]
    outer_holes = [
        _circle(f"Out{i+1}", 100.0 * math.cos(math.radians(i * 60.0)), 100.0 * math.sin(math.radians(i * 60.0)), 6.0)
        for i in range(6)
    ]
    scene = [cen] + inner_holes + outer_holes

    res = detect_bolt_circle_patterns(scene)
    assert len(res) == 2
    hole_counts = {p.hole_count for p in res}
    assert hole_counts == {4, 6}


def test_positive_4_semicircular_arc_sector():
    """Positive 4: 4 holes evenly spaced across 180 deg semi-circle (pitch=60 deg)."""
    pcd_r = 70.0
    holes = [
        _circle(f"Semi{i+1}", pcd_r * math.cos(math.radians(i * 60.0)), pcd_r * math.sin(math.radians(i * 60.0)), 5.0)
        for i in range(4)
    ]
    res = detect_bolt_circle_patterns(holes)
    assert len(res) == 1
    assert res[0].hole_count == 4
    assert res[0].is_full_circle is False
    assert math.isclose(res[0].angular_pitch_deg, 60.0, abs_tol=0.1)


# ---------------------------------------------------------------------------
# Strong Negative Controls
# ---------------------------------------------------------------------------

def test_negative_5_unequal_hole_sizes_on_same_circle():
    """Negative 5: 4 holes on same circle, but 2 have radius 4mm and 2 have radius 10mm."""
    # 2 small holes at 0, 180 deg; 2 big holes at 90, 270 deg
    holes = [
        _circle("H_s1", 50.0, 0.0, 4.0),
        _circle("H_b1", 0.0, 50.0, 10.0),
        _circle("H_s2", -50.0, 0.0, 4.0),
        _circle("H_b2", 0.0, -50.0, 10.0),
    ]
    # Each radius group has only 2 holes (< min_hole_count 3) -> rejected!
    res = detect_bolt_circle_patterns(holes)
    assert len(res) == 0


def test_negative_6_elliptical_hole_arrangement():
    """Negative 6: 4 holes placed on an ellipse (a=80, b=40, not a circle)."""
    # Ellipse points at 0, 90, 180, 270 deg
    holes = [
        _circle("E1", 80.0, 0.0, 5.0),
        _circle("E2", 0.0, 40.0, 5.0),
        _circle("E3", -80.0, 0.0, 5.0),
        _circle("E4", 0.0, -40.0, 5.0),
    ]
    res = detect_bolt_circle_patterns(holes)
    assert len(res) == 0, "Elliptical hole pattern must be rejected"


def test_negative_7_background_lines_non_interference():
    """Negative 7: Pattern extraction is completely unperturbed by surrounding background lines and hatch."""
    pcd_r = 50.0
    holes = [
        _circle("H1", 50.0, 0.0, 5.0),
        _circle("H2", 0.0, 50.0, 5.0),
        _circle("H3", -50.0, 0.0, 5.0),
        _circle("H4", 0.0, -50.0, 5.0),
    ]
    # 10 background grid lines
    lines = [_line(f"L{i}", -100.0, -100.0 + i * 20.0, 100.0, -100.0 + i * 20.0) for i in range(10)]
    scene = holes + lines

    res = detect_bolt_circle_patterns(scene)
    assert len(res) == 1
    assert res[0].hole_count == 4


def test_negative_8_less_than_three_holes():
    """Negative 8: 2 isolated holes do not form a circular pattern."""
    holes = [
        _circle("Two1", 50.0, 0.0, 5.0),
        _circle("Two2", -50.0, 0.0, 5.0),
    ]
    res = detect_bolt_circle_patterns(holes)
    assert len(res) == 0
