"""
test_compound_feature_benchmark.py — Multi-Strategy Benchmark Suite for Compound Features.

Benchmarks Strategies A, B, C, D across 8 mechanical engineering scenarios:
1. Scenario 1: Symmetrical Oblong Slot (2 lines + 2 arcs).
2. Scenario 2: Filleted Rectangular Plate (4 lines + 4 corner arcs).
3. Scenario 3: Standard Sharp Rectangular Frame (4 lines, legacy).
4. Scenario 4: Filleted L-Bracket (2 perpendicular lines + 1 corner arc).
5. Scenario 5: Mounting Tab with Concentric Bolt Hole (1 arc + 1 circle + 2 lines).
6. Scenario 6: Double Slot Plate (2 separate slots side-by-side).
7. Scenario 7: Incomplete Slot (2 lines + only 1 end arc -> rejected).
8. Scenario 8: Structural Joint (4 lines intersecting at a weld vertex).
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
    run_strategy_a_compound,
    run_strategy_b,
    run_strategy_c,
)


def test_scenario_1_symmetrical_oblong_slot():
    """Scenario 1: Symmetrical oblong slot (2 lines + 2 semicircular ends)."""
    l_top = make_line((20.0, 20.0), (80.0, 20.0), id_="l_top")
    l_bot = make_line((20.0, 0.0), (80.0, 0.0), id_="l_bot")
    a_left = make_arc((20.0, 10.0), 10.0, 90.0, 270.0, id_="a_left")
    a_right = make_arc((80.0, 10.0), 10.0, 270.0, 90.0, id_="a_right")
    prims = [l_top, l_bot, a_left, a_right]
    csts = [
        make_constraint("parallel", "l_top", "l_bot"),
        make_constraint("tangent", "l_top", "a_left"),
        make_constraint("tangent", "l_bot", "a_left"),
        make_constraint("tangent", "l_top", "a_right"),
        make_constraint("tangent", "l_bot", "a_right"),
    ]

    # Strategy A & C fail
    assert len(run_strategy_a_compound(prims, csts)) == 0
    assert len(run_strategy_c(prims, csts)) == 0

    # Strategy D detects slot
    res_d = detect_compound_features(prims, csts)
    assert len(res_d) == 1
    assert res_d[0].part_type == "mechanical_hole_feature"
    assert set(res_d[0].primitive_ids) == {"l_top", "l_bot", "a_left", "a_right"}


def test_scenario_2_filleted_rectangular_plate():
    """Scenario 2: Filleted rectangular plate (4 lines + 4 corner arcs)."""
    lines = [
        make_line((10.0, 60.0), (90.0, 60.0), id_="l_top"),
        make_line((100.0, 50.0), (100.0, 10.0), id_="l_right"),
        make_line((90.0, 0.0), (10.0, 0.0), id_="l_bot"),
        make_line((0.0, 10.0), (0.0, 50.0), id_="l_left"),
    ]
    arcs = [
        make_arc((90.0, 50.0), 10.0, 0.0, 90.0, id_="a_tr"),
        make_arc((90.0, 10.0), 10.0, 270.0, 360.0, id_="a_br"),
        make_arc((10.0, 10.0), 10.0, 180.0, 270.0, id_="a_bl"),
        make_arc((10.0, 50.0), 10.0, 90.0, 180.0, id_="a_tl"),
    ]
    prims = lines + arcs
    csts = [
        make_constraint("parallel", "l_top", "l_bot"),
        make_constraint("parallel", "l_left", "l_right"),
        make_constraint("perpendicular", "l_top", "l_right"),
        make_constraint("perpendicular", "l_right", "l_bot"),
        make_constraint("perpendicular", "l_bot", "l_left"),
        make_constraint("perpendicular", "l_left", "l_top"),
        make_constraint("tangent", "l_top", "a_tr"),
        make_constraint("tangent", "l_right", "a_tr"),
        make_constraint("tangent", "l_right", "a_br"),
        make_constraint("tangent", "l_bot", "a_br"),
        make_constraint("tangent", "l_bot", "a_bl"),
        make_constraint("tangent", "l_left", "a_bl"),
        make_constraint("tangent", "l_left", "a_tl"),
        make_constraint("tangent", "l_top", "a_tl"),
    ]

    # Strategy A & C fail
    assert len(run_strategy_a_compound(prims, csts)) == 0
    assert len(run_strategy_c(prims, csts)) == 0

    # Strategy D detects khung_chu_nhat with all 8 primitives
    res_d = detect_compound_features(prims, csts)
    assert len(res_d) == 1
    assert res_d[0].part_type == "khung_chu_nhat"
    assert len(res_d[0].primitive_ids) == 8


def test_scenario_3_sharp_rectangular_frame():
    """Scenario 3: Legacy sharp rectangular frame (4 lines, no arcs).
    Must remain 100% backward compatible with Strategy A.
    """
    l1 = make_line((0.0, 0.0), (100.0, 0.0), id_="l1")
    l2 = make_line((100.0, 0.0), (100.0, 50.0), id_="l2")
    l3 = make_line((100.0, 50.0), (0.0, 50.0), id_="l3")
    l4 = make_line((0.0, 50.0), (0.0, 0.0), id_="l4")
    prims = [l1, l2, l3, l4]
    csts = [
        make_constraint("parallel", "l1", "l3"),
        make_constraint("parallel", "l2", "l4"),
        make_constraint("perpendicular", "l1", "l2"),
        make_constraint("coincident_endpoint", "l1", "l2"),
        make_constraint("coincident_endpoint", "l2", "l3"),
        make_constraint("coincident_endpoint", "l3", "l4"),
        make_constraint("coincident_endpoint", "l4", "l1"),
    ]

    # Strategy A, C, and D all detect sharp khung_chu_nhat
    res_a = run_strategy_a_compound(prims, csts)
    res_c = run_strategy_c(prims, csts)
    res_d = detect_compound_features(prims, csts)

    assert len(res_a) == 1 and res_a[0].part_type == "khung_chu_nhat"
    assert len(res_c) == 1 and res_c[0].part_type == "khung_chu_nhat"
    assert len(res_d) == 1 and res_d[0].part_type == "khung_chu_nhat"


def test_scenario_4_filleted_gia_do():
    """Scenario 4: Filleted L-bracket (2 perpendicular lines + 1 fillet arc)."""
    l1 = make_line((0.0, 0.0), (50.0, 0.0), id_="l_h")
    arc = make_arc((50.0, 10.0), 10.0, 270.0, 360.0, id_="a_fillet")
    l2 = make_line((60.0, 10.0), (60.0, 80.0), id_="l_v")
    prims = [l1, arc, l2]
    csts = [
        make_constraint("perpendicular", "l_h", "l_v"),
        make_constraint("tangent", "l_h", "a_fillet"),
        make_constraint("tangent", "l_v", "a_fillet"),
    ]

    assert len(run_strategy_a_compound(prims, csts)) == 0

    res_d = detect_compound_features(prims, csts)
    assert len(res_d) == 1
    assert res_d[0].part_type == "gia_do"
    assert set(res_d[0].primitive_ids) == {"l_h", "l_v", "a_fillet"}


def test_scenario_5_mounting_tab_with_hole():
    """Scenario 5: Mounting lug/tab with concentric bolt hole."""
    a_lug = make_arc((100.0, 100.0), 30.0, 0.0, 180.0, id_="a_lug")
    c_hole = make_circle((100.0, 100.0), 12.0, id_="c_hole")
    l1 = make_line((70.0, 100.0), (70.0, 0.0), id_="l_left")
    l2 = make_line((130.0, 100.0), (130.0, 0.0), id_="l_right")
    prims = [a_lug, c_hole, l1, l2]
    csts = [
        make_constraint("concentric", "a_lug", "c_hole"),
        make_constraint("tangent", "l_left", "a_lug"),
        make_constraint("tangent", "l_right", "a_lug"),
    ]

    assert len(run_strategy_a_compound(prims, csts)) == 0

    res_d = detect_compound_features(prims, csts)
    assert len(res_d) == 1
    assert res_d[0].part_type == "ban_le"
    assert set(res_d[0].primitive_ids) == {"a_lug", "c_hole", "l_left", "l_right"}


def test_scenario_6_double_slot_plate():
    """Scenario 6: Double slot plate (two distinct slots on same part).
    Must detect exactly 2 slot features, with no cross-contamination.
    """
    # Slot 1 at x in [20, 80], y in [0, 20]
    s1_top = make_line((20.0, 20.0), (80.0, 20.0), id_="s1_top")
    s1_bot = make_line((20.0, 0.0), (80.0, 0.0), id_="s1_bot")
    s1_la = make_arc((20.0, 10.0), 10.0, 90.0, 270.0, id_="s1_la")
    s1_ra = make_arc((80.0, 10.0), 10.0, 270.0, 90.0, id_="s1_ra")

    # Slot 2 at x in [120, 180], y in [0, 20]
    s2_top = make_line((120.0, 20.0), (180.0, 20.0), id_="s2_top")
    s2_bot = make_line((120.0, 0.0), (180.0, 0.0), id_="s2_bot")
    s2_la = make_arc((120.0, 10.0), 10.0, 90.0, 270.0, id_="s2_la")
    s2_ra = make_arc((180.0, 10.0), 10.0, 270.0, 90.0, id_="s2_ra")

    prims = [s1_top, s1_bot, s1_la, s1_ra, s2_top, s2_bot, s2_la, s2_ra]
    csts = [
        make_constraint("parallel", "s1_top", "s1_bot"),
        make_constraint("tangent", "s1_top", "s1_la"),
        make_constraint("tangent", "s1_bot", "s1_la"),
        make_constraint("tangent", "s1_top", "s1_ra"),
        make_constraint("tangent", "s1_bot", "s1_ra"),
        make_constraint("parallel", "s2_top", "s2_bot"),
        make_constraint("tangent", "s2_top", "s2_la"),
        make_constraint("tangent", "s2_bot", "s2_la"),
        make_constraint("tangent", "s2_top", "s2_ra"),
        make_constraint("tangent", "s2_bot", "s2_ra"),
    ]

    res_d = detect_compound_features(prims, csts)
    slots = [p for p in res_d if p.part_type == "mechanical_hole_feature"]
    assert len(slots) == 2, "Must detect exactly 2 separate slots"
    pids_s1 = set(slots[0].primitive_ids)
    pids_s2 = set(slots[1].primitive_ids)
    assert len(pids_s1.intersection(pids_s2)) == 0, "Slots must not share primitives"


def test_scenario_7_incomplete_slot_rejection():
    """Scenario 7: Incomplete slot missing 1 end arc (2 lines + 1 arc).
    Must reject and emit 0 slot compound parts.
    """
    l_top = make_line((20.0, 20.0), (80.0, 20.0), id_="l_top")
    l_bot = make_line((20.0, 0.0), (80.0, 0.0), id_="l_bot")
    a_left = make_arc((20.0, 10.0), 10.0, 90.0, 270.0, id_="a_left")
    prims = [l_top, l_bot, a_left]
    csts = [
        make_constraint("parallel", "l_top", "l_bot"),
        make_constraint("tangent", "l_top", "a_left"),
        make_constraint("tangent", "l_bot", "a_left"),
    ]

    res_d = detect_compound_features(prims, csts)
    slots = [p for p in res_d if p.part_type == "mechanical_hole_feature"]
    assert len(slots) == 0, "Incomplete slot with only 1 arc must be rejected"


def test_scenario_8_structural_joint_diem_noi():
    """Scenario 8: Multi-line structural weld joint (4 lines meeting at common vertex)."""
    l1 = make_line((0.0, 0.0), (50.0, 50.0), id_="l1")
    l2 = make_line((100.0, 0.0), (50.0, 50.0), id_="l2")
    l3 = make_line((50.0, 100.0), (50.0, 50.0), id_="l3")
    l4 = make_line((0.0, 50.0), (50.0, 50.0), id_="l4")
    prims = [l1, l2, l3, l4]
    csts = [
        make_constraint("coincident_endpoint", "l1", "l2"),
        make_constraint("coincident_endpoint", "l2", "l3"),
        make_constraint("coincident_endpoint", "l3", "l4"),
        make_constraint("coincident_endpoint", "l4", "l1"),
        make_constraint("coincident_endpoint", "l1", "l3"),
        make_constraint("coincident_endpoint", "l2", "l4"),
    ]

    res_d = detect_compound_features(prims, csts)
    joints = [p for p in res_d if p.part_type == "diem_noi"]
    assert len(joints) == 1
    assert len(joints[0].primitive_ids) == 4
