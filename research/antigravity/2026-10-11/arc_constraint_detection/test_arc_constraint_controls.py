"""
test_arc_constraint_controls.py — Positive Fixtures and Strong Negative Controls for Arc Constraints.

Tests:
Positive Controls:
1. Closed Rounded Rectangle (4 lines + 4 corner arcs -> 8 tangencies, 8 coincident endpoints, 6 equal radii).
2. Keyhole Feature (Center bore circle + tangent neck lines).
3. Triple Concentric Feature (1 circle + 2 concentric arcs).

Negative Controls:
4. Parallel Line-Arc Offset (12mm outward gap > 5mm tolerance).
5. Non-Concentric Offset Lug (8mm center offset > 5mm tolerance).
6. Orthogonal Radial Spoke (Line intersects arc perpendicularly).
7. Disjoint Arcs with Gap (15mm gap between arc perimeters).
8. Unequal Radii Arcs (R10 vs R25 -> zero equal radius constraints).
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
)


def test_positive_1_closed_rounded_rectangle():
    """Positive 1: 100x60mm rounded rectangle with 4 R10 corner fillets.
    - Top line: (10, 60) to (90, 60)
    - Right line: (100, 50) to (100, 10)
    - Bottom line: (90, 0) to (10, 0)
    - Left line: (0, 10) to (0, 50)
    - Top-Right arc: center (90, 50), r=10, [0, 90]
    - Bottom-Right arc: center (90, 10), r=10, [270, 360]
    - Bottom-Left arc: center (10, 10), r=10, [180, 270]
    - Top-Left arc: center (10, 50), r=10, [90, 180]
    """
    lines = [
        make_line((10.0, 60.0), (90.0, 60.0), id_="line_top"),
        make_line((100.0, 50.0), (100.0, 10.0), id_="line_right"),
        make_line((90.0, 0.0), (10.0, 0.0), id_="line_bot"),
        make_line((0.0, 10.0), (0.0, 50.0), id_="line_left"),
    ]
    fillets = [
        make_arc((90.0, 50.0), 10.0, 0.0, 90.0, id_="arc_tr"),
        make_arc((90.0, 10.0), 10.0, 270.0, 360.0, id_="arc_br"),
        make_arc((10.0, 10.0), 10.0, 180.0, 270.0, id_="arc_bl"),
        make_arc((10.0, 50.0), 10.0, 90.0, 180.0, id_="arc_tl"),
    ]
    prims = lines + fillets
    res = detect_arc_fillet_constraints(prims)

    tangents = [c for c in res if c.type == "tangent"]
    coincident = [c for c in res if c.type == "coincident_endpoint"]
    equal_r = [c for c in res if c.type == "equal_length"]

    # Each of 4 corner arcs is tangent to 2 adjacent lines -> 8 tangencies
    assert len(tangents) == 8
    # Each of 4 corner arcs connects to 2 adjacent lines at endpoints -> 8 coincident endpoints
    assert len(coincident) == 8
    # 4 identical fillet radii -> 4*3/2 = 6 equal radius constraints
    assert len(equal_r) == 6


def test_positive_2_keyhole_neck_tangents():
    """Positive 2: Keyhole slot with a circle and 2 tangent lines exiting the bore.
    Bore circle: center (50, 50), r=20.
    Tangent line 1: (50, 70) to (100, 70) (top neck line, tangent at (50, 70)).
    Tangent line 2: (50, 30) to (100, 30) (bottom neck line, tangent at (50, 30)).
    """
    bore = make_circle((50.0, 50.0), 20.0, id_="bore")
    line1 = make_line((50.0, 70.0), (100.0, 70.0), id_="neck_top")
    line2 = make_line((50.0, 30.0), (100.0, 30.0), id_="neck_bot")

    res = detect_arc_fillet_constraints([bore, line1, line2])
    tangents = [c for c in res if c.type == "tangent"]
    assert len(tangents) == 2
    assert {tuple(c.primitive_ids) for c in tangents} == {("neck_top", "bore"), ("neck_bot", "bore")}


def test_positive_3_triple_concentric_feature():
    """Positive 3: Bushing with 1 center hole circle and 2 concentric semicircular arcs.
    Center: (200, 200).
    Circle r=10. Arc 1 r=25 [0, 180]. Arc 2 r=40 [0, 180].
    """
    c_hole = make_circle((200.0, 200.0), 10.0, id_="hole")
    arc_mid = make_arc((200.0, 200.0), 25.0, 0.0, 180.0, id_="arc_mid")
    arc_out = make_arc((200.0, 200.0), 40.0, 0.0, 180.0, id_="arc_out")

    res = detect_arc_fillet_constraints([c_hole, arc_mid, arc_out])
    concentric = [c for c in res if c.type == "concentric"]
    # 3 pairs: (c_hole, arc_mid), (c_hole, arc_out), (arc_mid, arc_out)
    assert len(concentric) == 3


def test_negative_4_parallel_line_arc_offset():
    """Negative 4: Line parallel to tangent line, but shifted outward by 12mm (tolerance=5mm).
    Arc: center (0, 10), r=10. True tangent is y=0.
    Shifted line: y=-12 from x=0 to 50.
    Radial gap = |-12 - 10| = 22mm - 10mm = 12mm > 5mm.
    Must emit 0 tangency constraints.
    """
    arc = make_arc((0.0, 10.0), 10.0, 180.0, 360.0, id_="arc")
    line_offset = make_line((0.0, -12.0), (50.0, -12.0), id_="line_offset")

    res = detect_arc_fillet_constraints([arc, line_offset], distance_tolerance_mm=5.0)
    tangents = [c for c in res if c.type == "tangent"]
    assert len(tangents) == 0


def test_negative_5_non_concentric_offset_lug():
    """Negative 5: Hole shifted 8mm away from lug center (tolerance=5mm).
    Lug arc: center (50, 50), r=25.
    Hole circle: center (58, 50), r=10. Center distance = 8.0mm > 5.0mm.
    Must emit 0 concentric constraints.
    """
    lug = make_arc((50.0, 50.0), 25.0, 0.0, 180.0, id_="lug")
    hole_shifted = make_circle((58.0, 50.0), 10.0, id_="hole_shifted")

    res = detect_arc_fillet_constraints([lug, hole_shifted], distance_tolerance_mm=5.0)
    concentric = [c for c in res if c.type == "concentric"]
    assert len(concentric) == 0


def test_negative_6_orthogonal_radial_spoke():
    """Negative 6: Line points straight towards circle center (radial spoke).
    Circle: center (0, 0), r=20.
    Line: (20, 0) to (50, 0).
    Distance from center to line is 0.0mm. Radial gap = |0 - 20| = 20mm > 5mm.
    Must emit 0 tangency constraints.
    """
    circ = make_circle((0.0, 0.0), 20.0, id_="circ")
    spoke = make_line((20.0, 0.0), (50.0, 0.0), id_="spoke")

    res = detect_arc_fillet_constraints([circ, spoke])
    tangents = [c for c in res if c.type == "tangent"]
    assert len(tangents) == 0


def test_negative_7_disjoint_arcs_with_gap():
    """Negative 7: Two arcs facing each other but separated by 15mm gap.
    Arc 1: center (0, 0), r=20, sweep [0, 90].
    Arc 2: center (55, 0), r=20, sweep [90, 180].
    Center distance = 55. r1 + r2 = 40. Ext gap = |55 - 40| = 15mm > 5mm.
    Must emit 0 tangency constraints.
    """
    arc1 = make_arc((0.0, 0.0), 20.0, 0.0, 90.0, id_="arc1")
    arc2 = make_arc((55.0, 0.0), 20.0, 90.0, 180.0, id_="arc2")

    res = detect_arc_fillet_constraints([arc1, arc2], distance_tolerance_mm=5.0)
    tangents = [c for c in res if c.type == "tangent"]
    assert len(tangents) == 0


def test_negative_8_unequal_radii_arcs():
    """Negative 8: R10 arc vs R25 arc (150% difference > 3% length tolerance).
    Must emit 0 equal radius constraints.
    """
    arc1 = make_arc((0.0, 0.0), 10.0, 0.0, 90.0, id_="arc_r10")
    arc2 = make_arc((100.0, 100.0), 25.0, 0.0, 90.0, id_="arc_r25")

    res = detect_arc_fillet_constraints([arc1, arc2])
    equal_r = [c for c in res if c.type == "equal_length"]
    assert len(equal_r) == 0
