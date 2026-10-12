"""
test_multileader_topology_benchmark.py
Empirical Strategy Benchmark Suite comparing Strategies A-D across 8 representative mechanical CAD scenarios:
- Strategy A: Current Production Baseline (_detect_leader_lines)
- Strategy B: Proximity Bounding Box Union
- Strategy C: Unconstrained Hough Junction Graph
- Strategy D: Strategy D Multileader Topology & Directed Attachment Oracle
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

from primitive_ir_lib.models import Point2D, Primitive, LineGeometry, CircleGeometry, TextData, Trace
from multileader_topology_engine import (
    extract_multileader_strategy_a,
    extract_multileader_strategy_b,
    extract_multileader_strategy_c,
    extract_multileader_strategy_d,
)


def _make_text(id_: str, content: str, x: float, y: float) -> Primitive:
    return Primitive(
        id=id_,
        type="text",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(int(x), int(y), int(x + len(content) * 8), int(y + 12))),
        text_data=TextData(content=content, position=Point2D(x, y), rotation_deg=0.0, height=3.5),
    )


def _make_circle(id_: str, cx: float, cy: float, r: float) -> Primitive:
    return Primitive(
        id=id_,
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(int(cx - r), int(cy - r), int(cx + r), int(cy + r))),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
    )


def _make_line(id_: str, x0: float, y0: float, x1: float, y1: float) -> Primitive:
    return Primitive(
        id=id_,
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(int(min(x0, x1)), int(min(y0, y1)), int(max(x0, x1)), int(max(y0, y1)))),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


def test_benchmark_scenario_01_standard_hole_callout():
    """Scenario 1: Standard hole callout '4x Ø8.5 THRU' pointing to drilled hole circle."""
    c_hole = _make_circle("hole_1", 20.0, 20.0, 10.0)  # Top point on circumference is (20.0, 30.0)
    # Multileader segments:
    # 1. Pointer leg from (20, 30) to (50, 60)
    ptr = (Point2D(20.0, 30.0), Point2D(50.0, 60.0))
    # 2. Arrowhead barb at tip (20, 30) -> (24, 34) (length ~5.6mm)
    barb = (Point2D(20.0, 30.0), Point2D(24.0, 34.0))
    # 3. Horizontal landing shelf (50, 60) -> (80, 60)
    landing = (Point2D(50.0, 60.0), Point2D(80.0, 60.0))
    # 4. Callout text sitting adjacent to landing shelf
    t_callout = _make_text("txt_1", "4x Ø8.5 THRU", 82.0, 61.0)

    segments = [ptr, barb, landing]
    texts = [t_callout]
    cad = [c_hole]

    res_a = extract_multileader_strategy_a(segments, texts, cad)
    res_b = extract_multileader_strategy_b(segments, texts, cad)
    res_c = extract_multileader_strategy_c(segments, texts, cad)
    res_d = extract_multileader_strategy_d(segments, texts, cad)

    # Strategy A inverts topology: it picks the 5.6mm arrowhead barb as the leader line,
    # completely drops the true 42mm pointer line and landing line, and has 0 attachments
    assert res_a.leaders[0].pointer_segment == barb
    assert res_a.leaders[0].landing_segment is None
    assert res_a.leaders[0].attached_feature_id is None
    assert res_a.leaders[0].callout_text_id is None

    # Strategy D succeeds with 100% topology
    assert len(res_d.leaders) == 1
    m = res_d.leaders[0]
    assert m.tip == Point2D(20.0, 30.0)
    assert m.knee == Point2D(50.0, 60.0)
    assert m.landing_end == Point2D(80.0, 60.0)
    assert m.attached_feature_id == "hole_1"
    assert m.attached_feature_type == "circle"
    assert m.callout_text_content == "4x Ø8.5 THRU"
    assert m.arrowhead is not None


def test_benchmark_scenario_02_chamfer_callout():
    """Scenario 2: Chamfer callout '2x C1.5' pointing to an inclined chamfer line."""
    l_chamfer = _make_line("ch_line", 0.0, 15.0, 10.0, 25.0)
    # Pointer leg from (5.0, 20.0) on chamfer to (35.0, 50.0)
    ptr = (Point2D(5.0, 20.0), Point2D(35.0, 50.0))
    barb = (Point2D(5.0, 20.0), Point2D(8.0, 25.0))
    landing = (Point2D(35.0, 50.0), Point2D(65.0, 50.0))
    t_callout = _make_text("txt_ch", "2x C1.5", 67.0, 51.0)

    segments = [ptr, barb, landing]
    texts = [t_callout]
    cad = [l_chamfer]

    res_a = extract_multileader_strategy_a(segments, texts, cad)
    res_d = extract_multileader_strategy_d(segments, texts, cad)

    # Strategy A misidentifies the 5.8mm barb as the leader line, dropping landing and attachments
    assert res_a.leaders[0].pointer_segment == barb
    assert res_a.leaders[0].landing_segment is None
    assert res_a.leaders[0].attached_feature_id is None
    assert len(res_d.leaders) == 1
    m = res_d.leaders[0]
    assert m.attached_feature_id == "ch_line"
    assert m.attached_feature_type == "line"
    assert m.callout_text_content == "2x C1.5"


def test_benchmark_scenario_03_radius_fillet_callout():
    """Scenario 3: Fillet radius callout 'R12' pointing to rounded corner."""
    c_fillet = _make_circle("fillet_arc", 40.0, 40.0, 12.0)
    ptr = (Point2D(40.0, 52.0), Point2D(70.0, 80.0))
    barb = (Point2D(40.0, 52.0), Point2D(43.0, 56.0))
    landing = (Point2D(70.0, 80.0), Point2D(95.0, 80.0))
    t_callout = _make_text("txt_r", "R12", 97.0, 81.0)

    res_d = extract_multileader_strategy_d([ptr, barb, landing], [t_callout], [c_fillet])
    assert len(res_d.leaders) == 1
    assert res_d.leaders[0].attached_feature_id == "fillet_arc"
    assert res_d.leaders[0].callout_text_content == "R12"


def test_benchmark_scenario_04_thread_specification_callout():
    """Scenario 4: Thread callout 'M10x1.5-6H' pointing to threaded bore."""
    c_thread = _make_circle("thread_bore", 100.0, 100.0, 5.0)
    ptr = (Point2D(100.0, 105.0), Point2D(130.0, 135.0))
    barb = (Point2D(100.0, 105.0), Point2D(104.0, 110.0))
    landing = (Point2D(130.0, 135.0), Point2D(165.0, 135.0))
    t_callout = _make_text("txt_m", "M10x1.5-6H", 167.0, 136.0)

    res_d = extract_multileader_strategy_d([ptr, barb, landing], [t_callout], [c_thread])
    assert len(res_d.leaders) == 1
    assert res_d.leaders[0].callout_text_content == "M10x1.5-6H"
    assert res_d.leaders[0].attached_feature_id == "thread_bore"


def test_benchmark_scenario_05_steep_pointer_leg():
    """Scenario 5: Steep pointer leg (75 deg) leader pointing to vertical shoulder."""
    l_shoulder = _make_line("sh_line", 50.0, 0.0, 50.0, 100.0)
    # dx = 10, dy = 37.32 -> ~75 deg
    ptr = (Point2D(50.0, 30.0), Point2D(60.0, 67.32))
    barb = (Point2D(50.0, 30.0), Point2D(52.0, 35.0))
    landing = (Point2D(60.0, 67.32), Point2D(85.0, 67.32))
    t_callout = _make_text("txt_sh", "GRIND Ra 0.8", 87.0, 68.0)

    res_d = extract_multileader_strategy_d([ptr, barb, landing], [t_callout], [l_shoulder])
    assert len(res_d.leaders) == 1
    m = res_d.leaders[0]
    assert m.attached_feature_id == "sh_line"
    assert round(m.measured["pointer_angle_deg"], 1) == 75.0


def test_benchmark_scenario_06_left_pointing_multileader():
    """Scenario 6: Left-pointing leader (knee to landing extends leftward)."""
    c_hole = _make_circle("hole_left", 80.0, 50.0, 6.0)
    ptr = (Point2D(80.0, 44.0), Point2D(60.0, 20.0))  # Points up-right towards hole
    barb = (Point2D(80.0, 44.0), Point2D(77.0, 39.0))
    landing = (Point2D(60.0, 20.0), Point2D(30.0, 20.0))  # Extends leftward to (30, 20)
    t_callout = _make_text("txt_l", "Ø12 C-BORE", 25.0, 21.0)

    res_d = extract_multileader_strategy_d([ptr, barb, landing], [t_callout], [c_hole])
    assert len(res_d.leaders) == 1
    m = res_d.leaders[0]
    assert m.tip == Point2D(80.0, 44.0)
    assert m.knee == Point2D(60.0, 20.0)
    assert m.landing_end == Point2D(30.0, 20.0)
    assert m.callout_text_content == "Ø12 C-BORE"


def test_benchmark_scenario_07_adjacent_dual_leaders_disambiguation():
    """Scenario 7: Two adjacent multileaders within 30 mm. Strategy B confuses text; Strategy D separates cleanly."""
    c1 = _make_circle("hole_a", 20.0, 30.0, 5.0)
    c2 = _make_circle("hole_b", 20.0, 60.0, 5.0)

    # Leader 1
    ptr1 = (Point2D(20.0, 35.0), Point2D(45.0, 50.0))
    barb1 = (Point2D(20.0, 35.0), Point2D(24.0, 38.0))
    land1 = (Point2D(45.0, 50.0), Point2D(70.0, 50.0))
    txt1 = _make_text("txt_a", "HOLE A", 72.0, 51.0)

    # Leader 2
    ptr2 = (Point2D(20.0, 65.0), Point2D(45.0, 80.0))
    barb2 = (Point2D(20.0, 65.0), Point2D(24.0, 68.0))
    land2 = (Point2D(45.0, 80.0), Point2D(70.0, 80.0))
    txt2 = _make_text("txt_b", "HOLE B", 72.0, 81.0)

    segments = [ptr1, barb1, land1, ptr2, barb2, land2]
    texts = [txt1, txt2]
    cad = [c1, c2]

    res_d = extract_multileader_strategy_d(segments, texts, cad)
    assert len(res_d.leaders) == 2
    callouts = {l.callout_text_content for l in res_d.leaders}
    assert callouts == {"HOLE A", "HOLE B"}
    targets = {l.attached_feature_id for l in res_d.leaders}
    assert targets == {"hole_a", "hole_b"}


def test_benchmark_scenario_08_hatch_strokes_distractor_immunity():
    """Scenario 8: True multileader surrounded by 10 background cross-hatch strokes."""
    c_target = _make_circle("hole_h", 50.0, 50.0, 8.0)
    ptr = (Point2D(50.0, 58.0), Point2D(80.0, 88.0))
    barb = (Point2D(50.0, 58.0), Point2D(54.0, 62.0))
    landing = (Point2D(80.0, 88.0), Point2D(110.0, 88.0))
    t_callout = _make_text("txt_h", "Ø16 H7", 112.0, 89.0)

    # 10 background hatch strokes (parallel 45 deg lines without arrowheads or landing shelves)
    hatch_strokes = [
        (Point2D(10.0 + i * 8.0, 0.0), Point2D(40.0 + i * 8.0, 30.0))
        for i in range(10)
    ]

    all_segments = [ptr, barb, landing] + hatch_strokes
    res_c = extract_multileader_strategy_c(all_segments, [t_callout], [c_target])
    res_d = extract_multileader_strategy_d(all_segments, [t_callout], [c_target])

    # Strategy D extracts exactly 1 clean multileader and ignores all 10 hatch strokes
    assert len(res_d.leaders) == 1
    assert res_d.leaders[0].attached_feature_id == "hole_h"
    assert len(res_d.unattached_segments) == 10
