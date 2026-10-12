"""
test_symmetry_constraint_controls.py
Positive and Negative Controls for Symmetry Axis & Symmetric Feature Constraint Detection & Solving.
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

from primitive_ir_lib.models import (
    Point2D, Primitive, LineGeometry, CircleGeometry,
    PrimitiveIRDocument, Trace, SourceDocument, Calibration
)
from symmetry_constraint_engine import (
    SymmetryAxis,
    detect_symmetry_strategy_d,
    solve_with_symmetry_constraints,
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


def _make_doc(*primitives: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="control.png", page_index=0, image_width_px=1000, image_height_px=1000),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=list(primitives),
    )


def test_control_01_positive_bilateral_line_pair():
    """Control 1 (Positive): Exact bilateral line pair with explicit centerline."""
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    l_top = _make_line("l_top", 10.0, 20.0, 80.0, 20.0)
    l_bot = _make_line("l_bot", 10.0, -20.0, 80.0, -20.0)

    res = detect_symmetry_strategy_d([l_axis, l_top, l_bot], [])
    assert len(res.symmetric_pairs) == 1
    p = res.symmetric_pairs[0]
    assert set(p.primitive_ids) == {"l_top", "l_bot"}
    assert p.measured["reflection_gap_mm"] < 1e-4
    assert p.confidence == 1.0


def test_control_02_positive_dual_symmetric_circles():
    """Control 2 (Positive): Dual circles symmetric across vertical axis."""
    l_axis = _make_line("axis", 50.0, 0.0, 50.0, 100.0, layer="CENTER")
    c_left = _make_circle("c_left", 20.0, 50.0, 6.0)
    c_right = _make_circle("c_right", 80.0, 50.0, 6.0)

    res = detect_symmetry_strategy_d([l_axis], [c_left, c_right])
    assert len(res.symmetric_pairs) == 1
    p = res.symmetric_pairs[0]
    assert p.feature_type == "circle_pair"
    assert set(p.primitive_ids) == {"c_left", "c_right"}
    assert p.measured["center_gap_mm"] < 1e-4


def test_control_03_positive_inferred_axis_consensus():
    """Control 3 (Positive): 2 independent symmetric pairs discover axis WITHOUT explicit layer tag."""
    # Step 1
    s1_top = _make_line("s1_top", 0.0, 30.0, 50.0, 30.0)
    s1_bot = _make_line("s1_bot", 0.0, -30.0, 50.0, -30.0)
    # Step 2
    s2_top = _make_line("s2_top", 50.0, 20.0, 100.0, 20.0)
    s2_bot = _make_line("s2_bot", 50.0, -20.0, 100.0, -20.0)

    res = detect_symmetry_strategy_d([s1_top, s1_bot, s2_top, s2_bot], [])
    # Consensus clustering discovers the horizontal axis
    assert len(res.axes) == 1
    assert round(res.axes[0].angle_deg, 1) == 0.0
    assert len(res.symmetric_pairs) == 2


def test_control_04_negative_asymmetric_line_lengths_rejected():
    """Control 4 (Negative): Parallel lines with unequal lengths rejected as symmetric pair."""
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    l_top = _make_line("l_top", 10.0, 20.0, 70.0, 20.0)  # len = 60
    l_bot = _make_line("l_bot", 10.0, -20.0, 40.0, -20.0) # len = 30 (50% shorter)

    res = detect_symmetry_strategy_d([l_axis, l_top, l_bot], [])
    # Must be rejected due to length disparity
    assert len(res.symmetric_pairs) == 0


def test_control_05_negative_asymmetric_axis_offsets_rejected():
    """Control 5 (Negative): Parallel lines of equal length but asymmetric axis offset rejected."""
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    l_top = _make_line("l_top", 10.0, 25.0, 70.0, 25.0)   # offset = +25mm
    l_bot = _make_line("l_bot", 10.0, -15.0, 70.0, -15.0) # offset = -15mm (gap = 10mm > tol 5mm)

    res = detect_symmetry_strategy_d([l_axis, l_top, l_bot], [])
    assert len(res.symmetric_pairs) == 0


def test_control_06_negative_single_isolated_pair_cannot_invent_axis():
    """Control 6 (Negative): A single isolated parallel line pair without explicit centerline cannot invent an axis."""
    l_top = _make_line("l_top", 10.0, 20.0, 70.0, 20.0)
    l_bot = _make_line("l_bot", 10.0, -20.0, 70.0, -20.0)

    # Only 1 pair present -> does NOT meet AXIS_CONSENSUS_MIN_PAIRS (>= 2)
    res = detect_symmetry_strategy_d([l_top, l_bot], [])
    assert len(res.axes) == 0
    assert len(res.symmetric_pairs) == 0


def test_control_07_positive_solvespace_symmetry_convergence():
    """Control 7 (Positive): Noisy scan coordinates (+/- 0.4mm) solved to exact symmetry via SolveSpace."""
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    # Scan noise: top line at y=20.4, bottom line at y=-19.6
    l_top_noisy = _make_line("top", 10.0, 20.4, 80.0, 20.4)
    l_bot_noisy = _make_line("bot", 10.0, -19.6, 80.0, -19.6)

    doc = _make_doc(l_axis, l_top_noisy, l_bot_noisy)
    res_detect = detect_symmetry_strategy_d([l_axis, l_top_noisy, l_bot_noisy], [])
    assert len(res_detect.symmetric_pairs) == 1

    solve_res = solve_with_symmetry_constraints(doc, res_detect.symmetric_pairs, res_detect.axes)
    assert solve_res.status == "okay"
    assert solve_res.applied_symmetry_count == 1
    # Residual must be exactly 0 (or < 1e-5 mm)
    assert solve_res.symmetry_residual_mm < 1e-4

    coords = solve_res.solved_coordinates
    top_s, top_e = coords["top"]
    bot_s, bot_e = coords["bot"]
    # Exactly symmetric: y_top + y_bot == 0.0
    assert abs(top_s.y + bot_s.y) < 1e-4
    assert abs(top_e.y + bot_e.y) < 1e-4
    assert top_s.y > 0.0 and bot_s.y < 0.0


def test_control_08_negative_distractor_orthogonal_lines_ignored():
    """Control 8 (Negative): Background crosshair and unrelated orthogonal frame lines do not trigger false pairs."""
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    l_top = _make_line("l_top", 10.0, 20.0, 80.0, 20.0)
    l_bot = _make_line("l_bot", 10.0, -20.0, 80.0, -20.0)
    # Unrelated vertical crosshairs and diagonal grid
    l_v1 = _make_line("v1", 0.0, -50.0, 0.0, 50.0)
    l_diag = _make_line("diag", -20.0, -20.0, 120.0, 40.0)

    res = detect_symmetry_strategy_d([l_axis, l_top, l_bot, l_v1, l_diag], [])
    # Only l_top and l_bot, plus l_v1 as self-symmetric
    pairs = [p for p in res.symmetric_pairs if p.feature_type == "line_pair"]
    assert len(pairs) == 1
    assert set(pairs[0].primitive_ids) == {"l_top", "l_bot"}
