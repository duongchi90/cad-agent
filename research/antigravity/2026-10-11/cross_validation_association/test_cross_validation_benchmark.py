"""Benchmark suite comparing Strategies A, B, C, D for Cross-Validation Primitive Association.

Evaluates 8 realistic drawing scenarios:
1. Scenario 1: Standard centered horizontal dimension.
2. Scenario 2: Staggered horizontal dimension near vertical witness line.
3. Scenario 3: Staggered text on long dimension (400px).
4. Scenario 4: Chained adjacent dimensions with missing segment (mutual exclusion test).
5. Scenario 5: Circular diameter dimension (Ø40 on circle).
6. Scenario 6: Radial dimension (R15 on arc fillet).
7. Scenario 7: Stacked parallel baseline rails.
8. Scenario 8: Aligned diagonal 45° dimension.
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
    strategy_a_cross_validate,
    strategy_b_cross_validate,
    strategy_c_cross_validate,
    strategy_d_cross_validate,
)


def _cal(scale: float = 1.0) -> Calibration:
    return Calibration(pixel_to_unit_scale=scale)


def test_scenario_1_standard_centered_horizontal():
    """Scenario 1: Clean, centered horizontal dimension line."""
    line = RawLine("l1", (100.0, 100.0), (250.0, 100.0))  # 150px
    text = RawText("t1", "150", (165.0, 85.0, 185.0, 95.0), rotation_deg=0.0, parsed_value=150.0)

    res_a = strategy_a_cross_validate([text], [line], _cal())
    res_b = strategy_b_cross_validate([text], [line], _cal())
    res_c = strategy_c_cross_validate([text], [line], _cal())
    res_d = strategy_d_cross_validate([text], raw_lines=[line], calibration=_cal())

    assert res_a[0].status == "confirmed"
    assert res_b[0].status == "confirmed"
    assert res_c[0].status == "confirmed"
    assert res_d[0].status == "confirmed"


def test_scenario_2_staggered_near_vertical_witness():
    """Scenario 2: Text near vertical witness line (0° angle bypass bug)."""
    dim_line = RawLine("dim", (100.0, 100.0), (350.0, 100.0))  # 250px
    witness = RawLine("wit", (100.0, 70.0), (100.0, 130.0))   # 60px vertical
    text = RawText("t1", "250", (110.0, 85.0, 130.0, 95.0), rotation_deg=0.0, parsed_value=250.0)

    res_a = strategy_a_cross_validate([text], [dim_line, witness], _cal())
    res_b = strategy_b_cross_validate([text], [dim_line, witness], _cal())
    res_c = strategy_c_cross_validate([text], [dim_line, witness], _cal())
    res_d = strategy_d_cross_validate([text], raw_lines=[dim_line, witness], calibration=_cal())

    # Strategy A fails (picks vertical witness line)
    assert res_a[0].geometry_id == "wit"
    assert res_a[0].status == "conflict"

    # Strategies B, C, D correctly pair with dim_line
    assert res_b[0].geometry_id == "dim"
    assert res_b[0].status == "confirmed"
    assert res_c[0].geometry_id == "dim"
    assert res_c[0].status == "confirmed"
    assert res_d[0].geometry_id == "dim"
    assert res_d[0].status == "confirmed"


def test_scenario_3_staggered_long_line():
    """Scenario 3: Long dimension (400px) with offset text exceeding midpoint radius."""
    long_line = RawLine("l_long", (100.0, 200.0), (500.0, 200.0))  # 400px, midpoint (300, 200)
    short_line = RawLine("l_short", (120.0, 175.0), (170.0, 175.0))  # 50px, midpoint (145, 175)
    # Text at (140, 185) (offset 160px from midpoint)
    text = RawText("t1", "400", (130.0, 180.0, 150.0, 190.0), rotation_deg=0.0, parsed_value=400.0)

    res_a = strategy_a_cross_validate([text], [long_line, short_line], _cal(), max_distance_px=150.0)
    res_b = strategy_b_cross_validate([text], [long_line, short_line], _cal(), max_distance_px=150.0)
    res_c = strategy_c_cross_validate([text], [long_line, short_line], _cal())
    res_d = strategy_d_cross_validate([text], raw_lines=[long_line, short_line], calibration=_cal())

    # Strategy A, B, and C fail:
    # A & B fail because midpoint distance > 150px
    # C fails because greedy corridor distance prefers 10px perp dist of l_short over 15px perp dist of l_long
    assert res_a[0].geometry_id == "l_short"
    assert res_a[0].status == "conflict"
    assert res_b[0].geometry_id == "l_short"
    assert res_b[0].status == "conflict"
    assert res_c[0].geometry_id == "l_short"
    assert res_c[0].status == "conflict"

    # Only Strategy D successfully pairs with l_long via multi-objective optimization (corridor + length consistency)
    assert res_d[0].geometry_id == "l_long"
    assert res_d[0].status == "confirmed"


def test_scenario_4_chained_dimensions_mutual_exclusion():
    """Scenario 4: Chained adjacent dimensions where one segment is missing."""
    line_1 = RawLine("l1", (0.0, 100.0), (100.0, 100.0))  # 100px
    # True line for span 2 is missing
    t1 = RawText("t1", "100", (40.0, 80.0, 60.0, 90.0), rotation_deg=0.0, parsed_value=100.0)
    t2 = RawText("t2", "80", (120.0, 80.0, 140.0, 90.0), rotation_deg=0.0, parsed_value=80.0)

    res_a = strategy_a_cross_validate([t1, t2], [line_1], _cal())
    res_b = strategy_b_cross_validate([t1, t2], [line_1], _cal())
    res_c = strategy_c_cross_validate([t1, t2], [line_1], _cal())
    res_d = strategy_d_cross_validate([t1, t2], raw_lines=[line_1], calibration=_cal())

    # Strategy A, B, C greedily assign l1 to t2 as well!
    assert res_a[1].geometry_id == "l1"
    assert res_a[1].status == "conflict"
    assert res_b[1].geometry_id == "l1"
    assert res_b[1].status == "conflict"

    # Strategy D strictly enforces 1-to-1 matching: t2 remains unverified!
    assert res_d[0].geometry_id == "l1"
    assert res_d[0].status == "confirmed"
    assert res_d[1].geometry_id == ""
    assert res_d[1].status == "unverified"


def test_scenario_5_circular_diameter_dimension():
    """Scenario 5: Circular diameter callout Ø40 on a circle of radius 20."""
    circle = RawCircle("c1", (200.0, 200.0), 20.0)  # radius 20, diameter 40
    line_noise = RawLine("l_noise", (200.0, 180.0), (200.0, 220.0))  # 40px center mark
    text = RawText("t1", "Ø40", (190.0, 160.0, 210.0, 175.0), rotation_deg=0.0, parsed_value=40.0, callout_type="diameter")

    res_a = strategy_a_cross_validate([text], [line_noise], _cal())
    res_b = strategy_b_cross_validate([text], [line_noise], _cal())
    res_c = strategy_c_cross_validate([text], [line_noise], _cal())
    res_d = strategy_d_cross_validate([text], raw_lines=[line_noise], raw_circles=[circle], calibration=_cal())

    # Strategies A, B, C are blind to circles
    assert res_a[0].geometry_type != "circle"
    assert res_b[0].geometry_type != "circle"
    assert res_c[0].geometry_type != "circle"

    # Strategy D matches the circle and confirms diameter 40
    assert res_d[0].geometry_id == "c1"
    assert res_d[0].geometry_type == "circle"
    assert res_d[0].measured_value == 40.0
    assert res_d[0].status == "confirmed"


def test_scenario_6_radial_dimension_on_arc():
    """Scenario 6: Radial callout R15 on a fillet arc of radius 15."""
    arc = RawArc("arc1", (100.0, 100.0), 15.0, start_angle_deg=0.0, end_angle_deg=90.0)
    text = RawText("t1", "R15", (110.0, 90.0, 130.0, 105.0), rotation_deg=0.0, parsed_value=15.0, callout_type="radius")

    res_a = strategy_a_cross_validate([text], [], _cal())
    res_b = strategy_b_cross_validate([text], [], _cal())
    res_c = strategy_c_cross_validate([text], [], _cal())
    res_d = strategy_d_cross_validate([text], raw_arcs=[arc], calibration=_cal())

    assert res_a[0].status == "unverified"
    assert res_b[0].status == "unverified"
    assert res_c[0].status == "unverified"

    # Strategy D recognizes the arc radius and confirms
    assert res_d[0].geometry_id == "arc1"
    assert res_d[0].geometry_type == "arc"
    assert res_d[0].measured_value == 15.0
    assert res_d[0].status == "confirmed"


def test_scenario_7_stacked_baseline_rails():
    """Scenario 7: Stacked baseline rails where text midpoint is closer to wrong rail."""
    rail_lower = RawLine("r_lower", (100.0, 100.0), (300.0, 100.0))  # length 200, mid (200, 100)
    rail_upper = RawLine("r_upper", (100.0, 130.0), (400.0, 130.0))  # length 300, mid (250, 130)
    # Text "300" placed at (180, 120): dist to lower is 20px dx, 20px dy -> 28.2px
    # dist to upper is 70px dx, 10px dy -> 70.7px
    text = RawText("t1", "300", (170.0, 115.0, 190.0, 125.0), rotation_deg=0.0, parsed_value=300.0)

    res_a = strategy_a_cross_validate([text], [rail_lower, rail_upper], _cal())
    res_b = strategy_b_cross_validate([text], [rail_lower, rail_upper], _cal())
    res_c = strategy_c_cross_validate([text], [rail_lower, rail_upper], _cal())
    res_d = strategy_d_cross_validate([text], raw_lines=[rail_lower, rail_upper], calibration=_cal())

    # Strategy A and B pick lower rail due to midpoint proximity
    assert res_a[0].geometry_id == "r_lower"
    assert res_a[0].status == "conflict"
    assert res_b[0].geometry_id == "r_lower"
    assert res_b[0].status == "conflict"

    # Strategy C and D pick upper rail
    assert res_c[0].geometry_id == "r_upper"
    assert res_c[0].status == "confirmed"
    assert res_d[0].geometry_id == "r_upper"
    assert res_d[0].status == "confirmed"


def test_scenario_8_aligned_diagonal_dimension():
    """Scenario 8: Diagonal 45° dimension."""
    # 45° line from (100, 100) to (200, 200): length 141.421px
    # With scale 0.70710678, CAD length is 100.0mm
    cal = _cal(scale=1.0 / math.sqrt(2.0))
    line = RawLine("l_diag", (100.0, 100.0), (200.0, 200.0))
    text = RawText("t1", "100", (140.0, 135.0, 160.0, 155.0), rotation_deg=45.0, parsed_value=100.0)

    res_a = strategy_a_cross_validate([text], [line], cal)
    res_b = strategy_b_cross_validate([text], [line], cal)
    res_c = strategy_c_cross_validate([text], [line], cal)
    res_d = strategy_d_cross_validate([text], raw_lines=[line], calibration=cal)

    assert res_a[0].status == "confirmed"
    assert res_b[0].status == "confirmed"
    assert res_c[0].status == "confirmed"
    assert res_d[0].status == "confirmed"
