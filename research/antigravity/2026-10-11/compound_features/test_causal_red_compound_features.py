"""
test_causal_red_compound_features.py — Public Causal RED Benchmarks for Compound Feature Assembly.

Demonstrates 5 concrete failure modes in production Strategy A (semantic_ir_lib/pattern_compound.py):
RED-1: Elongated slot (2 lines + 2 tangent arcs) completely omitted in Strategy A.
RED-2: Filleted rectangular frame (4 lines + 4 corner fillet arcs) omitted in Strategy A.
RED-3: Filleted L-bracket (2 lines + 1 corner fillet arc) omitted in Strategy A.
RED-4: Mounting lug (outer arc + concentric hole circle + 2 tangent lines) omitted in Strategy A.
RED-5: Adjacent disjoint contours falsely merged by Naive Proximity Strategy B.
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
)


def test_red_1_elongated_slot_omitted_in_strategy_a():
    """RED-1: Elongated slot formed by 2 parallel lines and 2 tangent semicircles.
    Lines:
      top: (20, 20) to (80, 20)
      bot: (20, 0) to (80, 0)
    Arcs:
      left: center=(20, 10), r=10, [90, 270]
      right: center=(80, 10), r=10, [270, 90]
    Constraints:
      parallel(top, bot)
      tangent(top, left), tangent(bot, left)
      tangent(top, right), tangent(bot, right)
    Strategy A completely ignores arcs and emits 0 compound parts!
    Strategy D recognizes mechanical_hole_feature (slot).
    """
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

    # Strategy A: Fails to detect slot
    res_a = run_strategy_a_compound(prims, csts)
    assert len(res_a) == 0, "Strategy A should reproduce omission of elongated slot"

    # Strategy D: Correctly detects slot
    res_d = detect_compound_features(prims, csts)
    slots = [p for p in res_d if p.part_type == "mechanical_hole_feature"]
    assert len(slots) == 1
    assert set(slots[0].primitive_ids) == {"l_top", "l_bot", "a_left", "a_right"}


def test_red_2_filleted_rectangle_omitted_in_strategy_a():
    """RED-2: Rectangular frame with 4 corner fillets (4 lines + 4 arcs).
    Because the lines are separated by corner arcs, line-line coincident_endpoint constraints DO NOT EXIST.
    Strategy A looks for line-line coincident endpoints, so it returns 0 parts!
    Strategy D recognizes the filleted rectangular frame as khung_chu_nhat.
    """
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
        # Corner tangencies
        make_constraint("tangent", "l_top", "a_tr"),
        make_constraint("tangent", "l_right", "a_tr"),
        make_constraint("tangent", "l_right", "a_br"),
        make_constraint("tangent", "l_bot", "a_br"),
        make_constraint("tangent", "l_bot", "a_bl"),
        make_constraint("tangent", "l_left", "a_bl"),
        make_constraint("tangent", "l_left", "a_tl"),
        make_constraint("tangent", "l_top", "a_tl"),
    ]

    # Strategy A: Emits 0 compound parts
    res_a = run_strategy_a_compound(prims, csts)
    assert len(res_a) == 0, "Strategy A should reproduce failure to detect filleted rectangle"

    # Strategy D: Emits khung_chu_nhat with all 8 primitives
    res_d = detect_compound_features(prims, csts)
    frames = [p for p in res_d if p.part_type == "khung_chu_nhat"]
    assert len(frames) == 1
    assert len(frames[0].primitive_ids) == 8


def test_red_3_filleted_gia_do_omitted_in_strategy_a():
    """RED-3: L-bracket with a fillet transition at the corner:
    Horizontal line + Vertical line joined by a corner arc.
    Strategy A only accepts direct line-line coincident endpoints.
    Strategy D recognizes filleted L-bracket as gia_do.
    """
    l1 = make_line((0.0, 0.0), (40.0, 0.0), id_="l_h")
    arc = make_arc((40.0, 10.0), 10.0, 270.0, 360.0, id_="a_corner")
    l2 = make_line((50.0, 10.0), (50.0, 60.0), id_="l_v")
    prims = [l1, arc, l2]

    csts = [
        make_constraint("perpendicular", "l_h", "l_v"),
        make_constraint("tangent", "l_h", "a_corner"),
        make_constraint("tangent", "l_v", "a_corner"),
    ]

    res_a = run_strategy_a_compound(prims, csts)
    assert len(res_a) == 0, "Strategy A fails on filleted L-bracket"

    res_d = detect_compound_features(prims, csts)
    brackets = [p for p in res_d if p.part_type == "gia_do"]
    assert len(brackets) == 1
    assert set(brackets[0].primitive_ids) == {"l_h", "l_v", "a_corner"}


def test_red_4_mounting_lug_omitted_in_strategy_a():
    """RED-4: Mounting lug / tab:
    Outer semicircular arc + Concentric bolt hole circle + 2 tangent neck lines.
    Strategy A ignores arc and fails to assemble the mounting lug.
    Strategy D recognizes mounting lug (ban_le).
    """
    a_lug = make_arc((50.0, 50.0), 25.0, 0.0, 180.0, id_="a_lug")
    c_hole = make_circle((50.0, 50.0), 10.0, id_="c_hole")
    l1 = make_line((25.0, 50.0), (25.0, 0.0), id_="l_left")
    l2 = make_line((75.0, 50.0), (75.0, 0.0), id_="l_right")
    prims = [a_lug, c_hole, l1, l2]

    csts = [
        make_constraint("concentric", "a_lug", "c_hole"),
        make_constraint("tangent", "l_left", "a_lug"),
        make_constraint("tangent", "l_right", "a_lug"),
    ]

    res_a = run_strategy_a_compound(prims, csts)
    assert len(res_a) == 0, "Strategy A fails on mounting lug"

    res_d = detect_compound_features(prims, csts)
    lugs = [p for p in res_d if p.part_type == "ban_le"]
    assert len(lugs) == 1
    assert set(lugs[0].primitive_ids) == {"a_lug", "c_hole", "l_left", "l_right"}


def test_red_5_naive_proximity_false_merging_in_strategy_b():
    """RED-5: Two separate adjacent features (Slot and nearby isolated contour line).
    The isolated contour line passes within 1mm of the slot bounding box.
    Naive Proximity Strategy B groups everything with overlapping bounding boxes into one huge part!
    Strategy D only binds primitives governed by explicit topological constraints.
    """
    l_top = make_line((20.0, 20.0), (80.0, 20.0), id_="l_top")
    l_bot = make_line((20.0, 0.0), (80.0, 0.0), id_="l_bot")
    a_left = make_arc((20.0, 10.0), 10.0, 90.0, 270.0, id_="a_left")
    a_right = make_arc((80.0, 10.0), 10.0, 270.0, 90.0, id_="a_right")
    # Nearby parallel boundary line (distance 2mm above slot, overlapping bbox!)
    l_nearby = make_line((10.0, 22.0), (90.0, 22.0), id_="l_nearby")

    prims = [l_top, l_bot, a_left, a_right, l_nearby]
    csts = [
        make_constraint("parallel", "l_top", "l_bot"),
        make_constraint("tangent", "l_top", "a_left"),
        make_constraint("tangent", "l_bot", "a_left"),
        make_constraint("tangent", "l_top", "a_right"),
        make_constraint("tangent", "l_bot", "a_right"),
    ]

    # Strategy B: Falsely lumps all 5 primitives together!
    res_b = run_strategy_b(prims, csts)
    assert len(res_b) == 1
    assert len(res_b[0].primitive_ids) == 5, "Strategy B falsely clusters unrelated nearby line"

    # Strategy D: Accurately isolates the slot (4 primitives) without contaminating it
    res_d = detect_compound_features(prims, csts)
    slots = [p for p in res_d if p.part_type == "mechanical_hole_feature"]
    assert len(slots) == 1
    assert "l_nearby" not in slots[0].primitive_ids
    assert len(slots[0].primitive_ids) == 4
