"""Controls and boundary test suite for Cross-Validation Primitive Association.

Covers 8 positive and negative boundary controls:
1. Control 1: Positive orthogonal H and V dimension pair.
2. Control 2: Negative cross-view distractor rejection (> max_perp_dist).
3. Control 3: Negative perpendicular line rejection (0° text with 90° line).
4. Control 4: Positive circle diameter with non-unity scale.
5. Control 5: Positive arc radius with non-unity scale.
6. Control 6: Negative conflicting diameter (text 75 vs circle 50).
7. Control 7: Ambiguity guard on equidistant conflicting candidates.
8. Control 8: Tolerance threshold boundary test (within 3% vs > 3%).
"""

import sys
from pathlib import Path
import pytest
import math

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from cross_validation_engine import (
    RawLine,
    RawCircle,
    RawArc,
    RawText,
    Calibration,
    strategy_d_cross_validate,
)


def _cal(scale: float = 1.0) -> Calibration:
    return Calibration(pixel_to_unit_scale=scale)


def test_ctrl_1_positive_orthogonal_h_and_v_pair():
    """Control 1: Simultaneous horizontal and vertical dimensions."""
    line_h = RawLine("lh", (100.0, 100.0), (220.0, 100.0))  # 120px
    line_v = RawLine("lv", (300.0, 200.0), (300.0, 280.0))  # 80px

    text_h = RawText("th", "120", (150.0, 85.0, 170.0, 95.0), rotation_deg=0.0, parsed_value=120.0)
    text_v = RawText("tv", "80", (305.0, 230.0, 315.0, 250.0), rotation_deg=90.0, parsed_value=80.0)

    results = strategy_d_cross_validate([text_h, text_v], raw_lines=[line_h, line_v], calibration=_cal())

    assert len(results) == 2
    assert results[0].geometry_id == "lh"
    assert results[0].status == "confirmed"
    assert results[1].geometry_id == "lv"
    assert results[1].status == "confirmed"


def test_ctrl_2_negative_cross_view_distractor_distance():
    """Control 2: Text far from all geometry must fail safe to unverified."""
    line = RawLine("l1", (100.0, 100.0), (200.0, 100.0))
    # Text placed at (150, 200) -> 100px perpendicular distance (> 40px max_perp)
    text = RawText("t_far", "100", (140.0, 195.0, 160.0, 205.0), rotation_deg=0.0, parsed_value=100.0)

    results = strategy_d_cross_validate([text], raw_lines=[line], calibration=_cal(), max_perp_dist_px=40.0)
    assert len(results) == 1
    assert results[0].geometry_id == ""
    assert results[0].status == "unverified"


def test_ctrl_3_negative_perpendicular_line_rejection():
    """Control 3: Horizontal text (0°) near an isolated vertical line (90°) must NOT associate."""
    vert_line = RawLine("lv", (100.0, 50.0), (100.0, 150.0))
    text_h = RawText("th", "100", (105.0, 95.0, 125.0, 105.0), rotation_deg=0.0, parsed_value=100.0)

    results = strategy_d_cross_validate([text_h], raw_lines=[vert_line], calibration=_cal())
    assert len(results) == 1
    assert results[0].geometry_id == ""
    assert results[0].status == "unverified"


def test_ctrl_4_positive_circle_diameter_with_scale():
    """Control 4: Circle with non-unity pixel scale."""
    # Radius = 25px, scale = 2.5 mm/px -> Diameter = 2 * 25 * 2.5 = 125.0 mm
    cal = _cal(scale=2.5)
    circle = RawCircle("c1", (300.0, 300.0), 25.0)
    text = RawText("t_diam", "Ø125", (290.0, 260.0, 310.0, 275.0), rotation_deg=0.0, parsed_value=125.0, callout_type="diameter")

    results = strategy_d_cross_validate([text], raw_circles=[circle], calibration=cal)
    assert len(results) == 1
    assert results[0].geometry_id == "c1"
    assert results[0].geometry_type == "circle"
    assert results[0].measured_value == 125.0
    assert results[0].status == "confirmed"


def test_ctrl_5_positive_arc_radius_with_scale():
    """Control 5: Arc with non-unity scale."""
    # Radius = 40px, scale = 1.25 mm/px -> Radius = 50.0 mm
    cal = _cal(scale=1.25)
    arc = RawArc("a1", (200.0, 200.0), 40.0, start_angle_deg=0.0, end_angle_deg=180.0)
    text = RawText("t_rad", "R50", (190.0, 150.0, 210.0, 165.0), rotation_deg=0.0, parsed_value=50.0, callout_type="radius")

    results = strategy_d_cross_validate([text], raw_arcs=[arc], calibration=cal)
    assert len(results) == 1
    assert results[0].geometry_id == "a1"
    assert results[0].geometry_type == "arc"
    assert results[0].measured_value == 50.0
    assert results[0].status == "confirmed"


def test_ctrl_6_negative_conflicting_diameter():
    """Control 6: Text says Ø75, circle measures Ø50 -> status='conflict'."""
    circle = RawCircle("c1", (200.0, 200.0), 25.0)  # diameter 50mm
    text = RawText("t_diam", "Ø75", (190.0, 165.0, 210.0, 180.0), rotation_deg=0.0, parsed_value=75.0, callout_type="diameter")

    results = strategy_d_cross_validate([text], raw_circles=[circle], calibration=_cal())
    assert len(results) == 1
    assert results[0].geometry_id == "c1"
    assert results[0].status == "conflict"
    assert results[0].measured_value == 50.0
    assert abs(results[0].delta_percent - 33.3333) < 0.1


def test_ctrl_7_ambiguity_guard_equidistant_dual_candidates():
    """Control 7: Ambiguity guard triggers when two candidates are equidistant but conflicting in length."""
    # Rail 1 at y=90: length 100px, centered at x=200
    rail_1 = RawLine("r1", (150.0, 90.0), (250.0, 90.0))
    # Rail 2 at y=110: length 200px, centered at x=200
    rail_2 = RawLine("r2", (100.0, 110.0), (300.0, 110.0))

    # Text placed at exactly (200, 100) (10px from r1, 10px from r2, centered on both rails)
    # Both have identical perp distance (10px) and zero axial center offset. Rail 1 measures 100, Rail 2 measures 200.
    text = RawText("t_amb", "150", (190.0, 95.0, 210.0, 105.0), rotation_deg=0.0, parsed_value=150.0)

    results = strategy_d_cross_validate([text], raw_lines=[rail_1, rail_2], calibration=_cal(), ambiguity_margin=0.05)
    assert len(results) == 1
    # Must report ambiguous status rather than randomly picking one
    assert results[0].status == "ambiguous"


def test_ctrl_8_tolerance_threshold_boundary():
    """Control 8: Boundary check on threshold_percent=3.0%."""
    line = RawLine("l1", (100.0, 100.0), (200.0, 100.0))  # 100px

    # Within 3.0%: 102.8mm (delta = 2.72% <= 3.0%)
    t_pass = RawText("t_pass", "102.8", (140.0, 85.0, 160.0, 95.0), rotation_deg=0.0, parsed_value=102.8)
    res_pass = strategy_d_cross_validate([t_pass], raw_lines=[line], calibration=_cal(), threshold_percent=3.0)
    assert res_pass[0].status == "confirmed"

    # Beyond 3.0%: 103.5mm (delta = 3.38% > 3.0%)
    t_fail = RawText("t_fail", "103.5", (140.0, 85.0, 160.0, 95.0), rotation_deg=0.0, parsed_value=103.5)
    res_fail = strategy_d_cross_validate([t_fail], raw_lines=[line], calibration=_cal(), threshold_percent=3.0)
    assert res_fail[0].status == "conflict"
