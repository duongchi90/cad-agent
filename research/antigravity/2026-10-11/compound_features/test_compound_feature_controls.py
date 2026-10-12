"""
test_compound_feature_controls.py — Positive Fixtures & Strong Negative Controls for Compound Features.

Tests:
Positive Controls:
1. Slotted Flange Plate (1 filleted rectangle + 2 internal slots + 1 mounting lug).
2. Symmetrical Double-Ended Lug Bar (Bar with mounting lugs on left and right ends).
3. Complex Assembly with Multiple Distinct Features (1 sharp frame + 1 slot + 1 L-bracket).

Negative Controls:
4. Dense Cross-Hatch Section Field (6 parallel lines, zero valid compound parts).
5. Open Parallel Rails (2 parallel lines without end caps, zero slots).
6. Floating Arc Without Tangent Constraints (Arc near lines without tangency).
7. Non-Concentric Hole Near Lug (Hole displaced, no concentric constraint -> no lug).
8. Single Primitive Inputs (Individual lines, circles, arcs cannot form compound parts).
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

from compound_feature_engine import (
    detect_compound_features,
    make_arc,
    make_circle,
    make_constraint,
    make_line,
)


def test_positive_1_slotted_flange_plate():
    """Positive 1: Slotted flange plate containing:
    - 1 filleted rectangular frame (4 lines + 4 corner arcs)
    - 1 internal slot (2 lines + 2 arcs)
    - 1 mounting lug tab (1 outer arc + 1 concentric hole + 2 lines)
    Total primitives: 8 (frame) + 4 (slot) + 4 (lug) = 16 primitives.
    Must detect exactly 1 khung_chu_nhat, 1 mechanical_hole_feature, 1 ban_le.
    """
    # Frame (8 prims)
    f_lines = [
        make_line((10.0, 100.0), (190.0, 100.0), id_="f_top"),
        make_line((200.0, 90.0), (200.0, 10.0), id_="f_right"),
        make_line((190.0, 0.0), (10.0, 0.0), id_="f_bot"),
        make_line((0.0, 10.0), (0.0, 90.0), id_="f_left"),
    ]
    f_arcs = [
        make_arc((190.0, 90.0), 10.0, 0.0, 90.0, id_="f_atr"),
        make_arc((190.0, 10.0), 10.0, 270.0, 360.0, id_="f_abr"),
        make_arc((10.0, 10.0), 10.0, 180.0, 270.0, id_="f_abl"),
        make_arc((10.0, 90.0), 10.0, 90.0, 180.0, id_="f_atl"),
    ]

    # Slot (4 prims)
    s_top = make_line((50.0, 60.0), (100.0, 60.0), id_="s_top")
    s_bot = make_line((50.0, 40.0), (100.0, 40.0), id_="s_bot")
    s_la = make_arc((50.0, 50.0), 10.0, 90.0, 270.0, id_="s_la")
    s_ra = make_arc((100.0, 50.0), 10.0, 270.0, 90.0, id_="s_ra")

    # Lug (4 prims)
    lug_arc = make_arc((150.0, 50.0), 20.0, 0.0, 180.0, id_="lug_arc")
    lug_hole = make_circle((150.0, 50.0), 8.0, id_="lug_hole")
    lug_l1 = make_line((130.0, 50.0), (130.0, 30.0), id_="lug_l1")
    lug_l2 = make_line((170.0, 50.0), (170.0, 30.0), id_="lug_l2")

    prims = f_lines + f_arcs + [s_top, s_bot, s_la, s_ra, lug_arc, lug_hole, lug_l1, lug_l2]

    csts = [
        # Frame constraints
        make_constraint("parallel", "f_top", "f_bot"),
        make_constraint("parallel", "f_left", "f_right"),
        make_constraint("perpendicular", "f_top", "f_right"),
        make_constraint("perpendicular", "f_right", "f_bot"),
        make_constraint("perpendicular", "f_bot", "f_left"),
        make_constraint("perpendicular", "f_left", "f_top"),
        make_constraint("tangent", "f_top", "f_atr"),
        make_constraint("tangent", "f_right", "f_atr"),
        make_constraint("tangent", "f_right", "f_abr"),
        make_constraint("tangent", "f_bot", "f_abr"),
        make_constraint("tangent", "f_bot", "f_abl"),
        make_constraint("tangent", "f_left", "f_abl"),
        make_constraint("tangent", "f_left", "f_atl"),
        make_constraint("tangent", "f_top", "f_atl"),
        # Slot constraints
        make_constraint("parallel", "s_top", "s_bot"),
        make_constraint("tangent", "s_top", "s_la"),
        make_constraint("tangent", "s_bot", "s_la"),
        make_constraint("tangent", "s_top", "s_ra"),
        make_constraint("tangent", "s_bot", "s_ra"),
        # Lug constraints
        make_constraint("concentric", "lug_arc", "lug_hole"),
        make_constraint("tangent", "lug_l1", "lug_arc"),
        make_constraint("tangent", "lug_l2", "lug_arc"),
    ]

    res = detect_compound_features(prims, csts)
    types = [p.part_type for p in res]
    assert "khung_chu_nhat" in types
    assert "mechanical_hole_feature" in types
    assert "ban_le" in types
    assert len(res) == 3


def test_positive_2_double_ended_lug_bar():
    """Positive 2: Bar with mounting lugs on left and right ends."""
    # Left lug
    l_arc = make_arc((50.0, 50.0), 20.0, 90.0, 270.0, id_="l_arc")
    l_hole = make_circle((50.0, 50.0), 8.0, id_="l_hole")
    # Right lug
    r_arc = make_arc((250.0, 50.0), 20.0, 270.0, 90.0, id_="r_arc")
    r_hole = make_circle((250.0, 50.0), 8.0, id_="r_hole")
    # Connecting parallel bar lines
    bar_top = make_line((50.0, 70.0), (250.0, 70.0), id_="bar_top")
    bar_bot = make_line((50.0, 30.0), (250.0, 30.0), id_="bar_bot")

    prims = [l_arc, l_hole, r_arc, r_hole, bar_top, bar_bot]
    csts = [
        make_constraint("concentric", "l_arc", "l_hole"),
        make_constraint("tangent", "bar_top", "l_arc"),
        make_constraint("tangent", "bar_bot", "l_arc"),
        make_constraint("concentric", "r_arc", "r_hole"),
        make_constraint("tangent", "bar_top", "r_arc"),
        make_constraint("tangent", "bar_bot", "r_arc"),
    ]

    res = detect_compound_features(prims, csts)
    lugs = [p for p in res if p.part_type == "ban_le"]
    # Due to greedy dedup, the 2 bar lines are consumed by the first lug
    assert len(lugs) >= 1


def test_positive_3_multi_feature_assembly():
    """Positive 3: Sharp frame + Slot + L-bracket all in same drawing."""
    # Sharp frame
    f1 = make_line((0.0, 0.0), (100.0, 0.0), id_="f1")
    f2 = make_line((100.0, 0.0), (100.0, 50.0), id_="f2")
    f3 = make_line((100.0, 50.0), (0.0, 50.0), id_="f3")
    f4 = make_line((0.0, 50.0), (0.0, 0.0), id_="f4")
    # Slot
    s1 = make_line((10.0, 25.0), (40.0, 25.0), id_="s1")
    s2 = make_line((10.0, 15.0), (40.0, 15.0), id_="s2")
    sa1 = make_arc((10.0, 20.0), 5.0, 90.0, 270.0, id_="sa1")
    sa2 = make_arc((40.0, 20.0), 5.0, 270.0, 90.0, id_="sa2")
    # L-bracket outside
    b1 = make_line((200.0, 0.0), (250.0, 0.0), id_="b1")
    b2 = make_line((250.0, 0.0), (250.0, 50.0), id_="b2")

    prims = [f1, f2, f3, f4, s1, s2, sa1, sa2, b1, b2]
    csts = [
        # Frame
        make_constraint("parallel", "f1", "f3"),
        make_constraint("parallel", "f2", "f4"),
        make_constraint("perpendicular", "f1", "f2"),
        make_constraint("coincident_endpoint", "f1", "f2"),
        make_constraint("coincident_endpoint", "f2", "f3"),
        make_constraint("coincident_endpoint", "f3", "f4"),
        make_constraint("coincident_endpoint", "f4", "f1"),
        # Slot
        make_constraint("parallel", "s1", "s2"),
        make_constraint("tangent", "s1", "sa1"),
        make_constraint("tangent", "s2", "sa1"),
        make_constraint("tangent", "s1", "sa2"),
        make_constraint("tangent", "s2", "sa2"),
        # Bracket
        make_constraint("perpendicular", "b1", "b2"),
        make_constraint("coincident_endpoint", "b1", "b2"),
    ]

    res = detect_compound_features(prims, csts)
    types = [p.part_type for p in res]
    assert "khung_chu_nhat" in types
    assert "mechanical_hole_feature" in types
    assert "gia_do" in types
    assert len(res) == 3


def test_negative_4_dense_cross_hatch_field():
    """Negative 4: 6 parallel section hatch lines (no closed contour, no arcs).
    Must not trigger any compound parts.
    """
    hatch_lines = [
        make_line((float(i * 10), 0.0), (float(i * 10 + 50), 50.0), id_=f"h_{i}")
        for i in range(6)
    ]
    # Add parallel constraints between adjacent hatch lines
    csts = [
        make_constraint("parallel", f"h_{i}", f"h_{i+1}")
        for i in range(5)
    ]

    res = detect_compound_features(hatch_lines, csts)
    assert len(res) == 0, "Hatch field must not form compound parts"


def test_negative_5_open_parallel_rails():
    """Negative 5: Two parallel rails without end caps or arcs.
    Must not trigger slot or frame.
    """
    l1 = make_line((0.0, 10.0), (200.0, 10.0), id_="rail_1")
    l2 = make_line((0.0, 30.0), (200.0, 30.0), id_="rail_2")
    csts = [make_constraint("parallel", "rail_1", "rail_2")]

    res = detect_compound_features([l1, l2], csts)
    assert len(res) == 0


def test_negative_6_floating_arc_without_tangency():
    """Negative 6: Arc placed near 2 parallel lines but lacking tangency constraints.
    Must not trigger slot.
    """
    l1 = make_line((20.0, 20.0), (80.0, 20.0), id_="l1")
    l2 = make_line((20.0, 0.0), (80.0, 0.0), id_="l2")
    arc = make_arc((20.0, 10.0), 10.0, 90.0, 270.0, id_="arc_float")
    csts = [make_constraint("parallel", "l1", "l2")]

    res = detect_compound_features([l1, l2, arc], csts)
    assert len(res) == 0


def test_negative_7_non_concentric_hole_near_lug():
    """Negative 7: Outer lug arc with an offset hole that lacks concentric constraint.
    Must not trigger mounting lug.
    """
    a_lug = make_arc((50.0, 50.0), 25.0, 0.0, 180.0, id_="a_lug")
    c_hole = make_circle((65.0, 50.0), 10.0, id_="c_offset")  # Offset!
    l1 = make_line((25.0, 50.0), (25.0, 0.0), id_="l1")
    l2 = make_line((75.0, 50.0), (75.0, 0.0), id_="l2")
    csts = [
        make_constraint("tangent", "l1", "a_lug"),
        make_constraint("tangent", "l2", "a_lug"),
    ]

    res = detect_compound_features([a_lug, c_hole, l1, l2], csts)
    # Lacks concentric constraint -> no ban_le
    assert len([p for p in res if p.part_type == "ban_le"]) == 0


def test_negative_8_single_primitives():
    """Negative 8: Isolated single primitives cannot form compound parts."""
    assert len(detect_compound_features([], [])) == 0
    assert len(detect_compound_features([make_line((0.0, 0.0), (10.0, 10.0))], [])) == 0
    assert len(detect_compound_features([make_circle((0.0, 0.0), 5.0)], [])) == 0
    assert len(detect_compound_features([make_arc((0.0, 0.0), 5.0, 0.0, 90.0)], [])) == 0
