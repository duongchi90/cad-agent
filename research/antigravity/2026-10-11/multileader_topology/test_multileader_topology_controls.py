"""
test_multileader_topology_controls.py
Positive and Negative Controls for Multileader Line, Dogleg Knee, and Callout Topology.
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


def test_control_01_positive_standard_acute_arrow_leader():
    """Control 1 (Positive): Standard multileader with acute arrow, landing shelf, and callout."""
    ptr = (Point2D(10.0, 10.0), Point2D(40.0, 40.0))
    barb = (Point2D(10.0, 10.0), Point2D(14.0, 14.0))
    landing = (Point2D(40.0, 40.0), Point2D(70.0, 40.0))
    txt = _make_text("txt_1", "NOTE 1", 72.0, 41.0)
    c_target = _make_circle("hole_target", 10.0, 0.0, 10.0)  # (10, 10) is on circumference

    res = extract_multileader_strategy_d([ptr, barb, landing], [txt], [c_target])
    assert len(res.leaders) == 1
    l = res.leaders[0]
    assert l.tip == Point2D(10.0, 10.0)
    assert l.knee == Point2D(40.0, 40.0)
    assert l.landing_end == Point2D(70.0, 40.0)
    assert l.confidence == 1.0


def test_control_02_positive_curved_feature_attachment():
    """Control 2 (Positive): Snaps tip to circle circumference within 1.0 mm."""
    c_bore = _make_circle("bore_hole", 50.0, 50.0, 15.0)
    # Circumference point at (50, 65). Tip at (50.5, 65.2) -> distance ~0.53 mm
    ptr = (Point2D(50.5, 65.2), Point2D(75.0, 90.0))
    barb = (Point2D(50.5, 65.2), Point2D(54.0, 68.0))
    landing = (Point2D(75.0, 90.0), Point2D(100.0, 90.0))

    res = extract_multileader_strategy_d([ptr, barb, landing], [], [c_bore])
    assert len(res.leaders) == 1
    l = res.leaders[0]
    assert l.attached_feature_id == "bore_hole"
    assert l.attached_feature_type == "circle"
    assert l.attached_feature_distance_mm < 1.0


def test_control_03_positive_linear_feature_attachment():
    """Control 3 (Positive): Snaps tip to linear workpiece edge."""
    l_edge = _make_line("top_edge", 0.0, 100.0, 200.0, 100.0)
    # Tip at (50, 100.5) -> distance 0.5 mm from horizontal top_edge
    ptr = (Point2D(50.0, 100.5), Point2D(80.0, 130.0))
    barb = (Point2D(50.0, 100.5), Point2D(53.0, 104.0))
    landing = (Point2D(80.0, 130.0), Point2D(110.0, 130.0))

    res = extract_multileader_strategy_d([ptr, barb, landing], [], [l_edge])
    assert len(res.leaders) == 1
    l = res.leaders[0]
    assert l.attached_feature_id == "top_edge"
    assert l.attached_feature_type == "line"


def test_control_04_negative_detached_floating_arrowhead_rejected():
    """Control 4 (Negative): Isolated arrowhead barb without a connecting pointer leg rejected."""
    barb_isolated = (Point2D(10.0, 10.0), Point2D(15.0, 15.0))
    txt = _make_text("txt_iso", "FLOATING", 20.0, 20.0)

    res = extract_multileader_strategy_d([barb_isolated], [txt], [])
    assert len(res.leaders) == 0


def test_control_05_negative_isolated_horizontal_line_not_leader():
    """Control 5 (Negative): Isolated horizontal line without connecting pointer leg is not a leader."""
    horiz_line = (Point2D(50.0, 50.0), Point2D(100.0, 50.0))
    txt = _make_text("txt_h", "HORIZ", 105.0, 50.0)

    res = extract_multileader_strategy_d([horiz_line], [txt], [])
    assert len(res.leaders) == 0


def test_control_06_negative_distant_unrelated_text_not_associated():
    """Control 6 (Negative): Text located 80 mm away from landing shelf is not falsely associated."""
    ptr = (Point2D(10.0, 10.0), Point2D(40.0, 40.0))
    barb = (Point2D(10.0, 10.0), Point2D(14.0, 14.0))
    landing = (Point2D(40.0, 40.0), Point2D(70.0, 40.0))
    # Distant text at x=150, y=120
    txt_distant = _make_text("txt_far", "FAR TITLE", 150.0, 120.0)

    res = extract_multileader_strategy_d([ptr, barb, landing], [txt_distant], [])
    assert len(res.leaders) == 1
    assert res.leaders[0].callout_text_id is None


def test_control_07_positive_dogleg_knee_angle_preservation():
    """Control 7 (Positive): Knee vertex coordinates and horizontal landing shelf alignment preserved."""
    ptr = (Point2D(20.0, 20.0), Point2D(45.0, 55.0))
    barb = (Point2D(20.0, 20.0), Point2D(23.0, 25.0))
    landing = (Point2D(45.0, 55.0), Point2D(85.0, 55.0))

    res = extract_multileader_strategy_d([ptr, barb, landing], [], [])
    assert len(res.leaders) == 1
    l = res.leaders[0]
    assert l.knee == Point2D(45.0, 55.0)
    # Landing line must be exactly horizontal: y1 == y2 == 55.0
    assert l.landing_segment[0].y == 55.0
    assert l.landing_segment[1].y == 55.0


def test_control_08_negative_dimension_witness_lines_rejected():
    """Control 8 (Negative): Dimension extension witness lines (orthogonal perpendiculars) rejected as leaders."""
    # Vertical extension lines of a linear dimension at x=50 and x=100
    ext1 = (Point2D(50.0, 10.0), Point2D(50.0, 40.0))
    ext2 = (Point2D(100.0, 10.0), Point2D(100.0, 40.0))
    dim_line = (Point2D(50.0, 35.0), Point2D(100.0, 35.0))

    res = extract_multileader_strategy_d([ext1, ext2, dim_line], [], [])
    assert len(res.leaders) == 0
