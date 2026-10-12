"""
test_causal_red_bolt_circle_patterns.py — Public Causal RED for Circular Pitch Bolt Pattern Recognition.

Proves 5 concrete failure modes in production Strategy A (semantic_ir_lib/pattern_compound.py):
RED-1: 4-hole flange bolt circle completely omitted (returns 0 compound parts).
RED-2: 6-hole pitch pattern without central circle completely omitted (returns 0 compound parts).
RED-3: 8-hole wheel hub bolt pattern around axle bore completely omitted (returns 0 compound parts).
RED-4: Irregularly scattered random holes falsely clustered by naive proximity Strategy B, while Strategy D correctly rejects.
RED-5: Unequal angular pitch holes on same radius correctly rejected by Strategy D.
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


def test_red_1_four_hole_flange_bolt_circle_omission():
    """RED-1: 4 equal bolt holes spaced 90 deg on 100mm PCD around center bore."""
    center_bore = _circle("C_center", 0.0, 0.0, radius=25.0)
    # 4 bolt holes at R=50mm, angles 0, 90, 180, 270 deg
    holes = [
        _circle("H1", 50.0, 0.0, radius=6.0),
        _circle("H2", 0.0, 50.0, radius=6.0),
        _circle("H3", -50.0, 0.0, radius=6.0),
        _circle("H4", 0.0, -50.0, radius=6.0),
    ]
    primitives = [center_bore] + holes

    # Production Strategy A
    parts_a = run_strategy_a_compound(primitives, constraints=[])
    # Flaw: Production returns 0 compound parts for circular bolt patterns!
    assert len(parts_a) == 0, "Production Strategy A returns 0 parts, omitting 4-hole bolt pattern"

    # Strategy D Oracle
    patterns_d = detect_bolt_circle_patterns(primitives)
    assert len(patterns_d) == 1
    p = patterns_d[0]
    assert p.hole_count == 4
    assert p.center_circle_id == "C_center"
    assert math.isclose(p.pitch_radius_mm, 50.0, abs_tol=1e-3)
    assert math.isclose(p.angular_pitch_deg, 90.0, abs_tol=1e-3)
    assert p.is_full_circle is True

    # Converts to SemanticPart
    sp = p.to_semantic_part()
    assert sp.part_type == "mechanical_hole_feature"
    assert set(sp.primitive_ids) == {"H1", "H2", "H3", "H4", "C_center"}


def test_red_2_six_hole_pcd_pattern_omission_without_center_bore():
    """RED-2: 6 equal bolt holes spaced 60 deg on 120mm PCD with no explicit center circle."""
    pcd_r = 60.0
    holes = []
    for i in range(6):
        ang = math.radians(i * 60.0 + 15.0)  # Rotated 15 deg
        hx = pcd_r * math.cos(ang)
        hy = pcd_r * math.sin(ang)
        holes.append(_circle(f"H{i+1}", hx, hy, radius=5.0))

    # Production Strategy A
    parts_a = run_strategy_a_compound(holes, constraints=[])
    assert len(parts_a) == 0, "Production Strategy A returns 0 parts for 6-hole PCD pattern"

    # Strategy D Oracle
    patterns_d = detect_bolt_circle_patterns(holes)
    assert len(patterns_d) == 1
    p = patterns_d[0]
    assert p.hole_count == 6
    assert p.center_circle_id is None
    assert math.isclose(p.pitch_radius_mm, 60.0, abs_tol=0.1)
    assert math.isclose(p.angular_pitch_deg, 60.0, abs_tol=0.1)
    assert p.is_full_circle is True


def test_red_3_eight_hole_wheel_hub_omission():
    """RED-3: 8 equal bolt holes spaced 45 deg on 140mm PCD around axle bore."""
    axle_bore = _circle("C_axle", 100.0, 100.0, radius=35.0)
    pcd_r = 70.0
    holes = []
    for i in range(8):
        ang = math.radians(i * 45.0)
        hx = 100.0 + pcd_r * math.cos(ang)
        hy = 100.0 + pcd_r * math.sin(ang)
        holes.append(_circle(f"B{i+1}", hx, hy, radius=7.0))

    primitives = [axle_bore] + holes

    # Production Strategy A
    parts_a = run_strategy_a_compound(primitives, constraints=[])
    assert len(parts_a) == 0, "Production Strategy A returns 0 parts for 8-hole hub pattern"

    # Strategy D Oracle
    patterns_d = detect_bolt_circle_patterns(primitives)
    assert len(patterns_d) == 1
    p = patterns_d[0]
    assert p.hole_count == 8
    assert p.center_circle_id == "C_axle"
    assert math.isclose(p.pitch_radius_mm, 70.0, abs_tol=0.1)
    assert math.isclose(p.angular_pitch_deg, 45.0, abs_tol=0.1)


def test_red_4_irregular_scattered_holes_rejected():
    """RED-4: Irregular scattered holes clustered by naive Strategy B but rejected by Strategy D."""
    # 4 holes scattered randomly near origin, not on a circle
    holes = [
        _circle("R1", 10.0, 10.0, radius=5.0),
        _circle("R2", 40.0, 20.0, radius=5.0),
        _circle("R3", -15.0, 35.0, radius=5.0),
        _circle("R4", 25.0, -30.0, radius=5.0),
    ]

    # Strategy B proximity clusters them blindly
    clust_b = run_strategy_b_patterns(holes, max_gap_mm=100.0)
    assert len(clust_b) == 1, "Strategy B blindly clusters scattered holes"

    # Strategy D correctly rejects irregular scattered layout
    pats_d = detect_bolt_circle_patterns(holes)
    assert len(pats_d) == 0, "Strategy D correctly rejects non-circular scattered holes"


def test_red_5_unequal_angular_pitch_rejected():
    """RED-5: Holes on same radius but clustered at irregular angles (0, 15, 30, 180 deg)."""
    pcd_r = 50.0
    irregular_angles = [0.0, 15.0, 30.0, 180.0]
    holes = []
    for i, a_deg in enumerate(irregular_angles):
        ang = math.radians(a_deg)
        hx = pcd_r * math.cos(ang)
        hy = pcd_r * math.sin(ang)
        holes.append(_circle(f"Irr{i+1}", hx, hy, radius=5.0))

    # Strategy D correctly rejects non-uniform angular spacing
    pats_d = detect_bolt_circle_patterns(holes)
    assert len(pats_d) == 0, "Strategy D rejects irregular non-uniform angular spacing"
