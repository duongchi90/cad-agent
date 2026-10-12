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

from primitive_ir_lib.cross_validation import cross_validate
from primitive_ir_lib.calibration import find_nearest_line
from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.text_extraction import RawText
from primitive_ir_lib.models import Calibration

from cross_validation_engine import (
    strategy_d_cross_validate,
    RawCircle,
    RawArc,
    RawText as EngineRawText,
    RawLine as EngineRawLine,
    Calibration as EngineCalibration,
)


def _make_calibration(scale: float = 1.0) -> Calibration:
    return Calibration(
        unit="mm",
        pixel_to_unit_scale=scale,
        origin_px=(0.0, 0.0),
        method="known_dimension_reference",
    )


def test_red_1_horizontal_text_angle_bypass_selects_orthogonal_witness_line():
    """RED 1: rotation_deg % 180 == 0 disables angle filtering in find_nearest_line.

    Horizontal dimension text (0°) sitting near a vertical witness line (90°)
    falsely associates with the witness line because its midpoint is closer than
    the horizontal dimension line's midpoint.
    """
    cal = _make_calibration(1.0)

    # True horizontal dimension line: length 200px, midpoint at (200, 100)
    dim_line = RawLine(
        id="dim_line_200",
        p1_px=(100.0, 100.0),
        p2_px=(300.0, 100.0),
        confidence=1.0,
        bbox_px=(100.0, 100.0, 300.0, 100.0),
    )

    # Vertical witness line: length 60px, midpoint at (100, 100)
    witness_line = RawLine(
        id="witness_vert_60",
        p1_px=(100.0, 70.0),
        p2_px=(100.0, 130.0),
        confidence=1.0,
        bbox_px=(100.0, 70.0, 100.0, 130.0),
    )

    # Horizontal text "200" placed at (120, 85) (offset towards left witness line)
    # Distance to witness midpoint (100, 100): sqrt(20^2 + 15^2) = 25px
    # Distance to dim_line midpoint (200, 100): sqrt(80^2 + 15^2) = 81.39px
    text = RawText(
        id="txt_200",
        content="200",
        bbox_px=(110, 75, 130, 95),  # center (120, 85)
        rotation_deg=0.0,
        confidence=1.0,
        source="text_tesseract",
        parsed_value=200.0,
        semantic_role="dimension_value",
    )

    # Production cross_validate
    prod_results = cross_validate([text], [dim_line, witness_line], cal, threshold_percent=3.0)

    # FAILS in production: picks the vertical witness line!
    assert len(prod_results) == 1
    prod_res = prod_results[0]
    assert prod_res.geometry_primitive_id == "witness_vert_60"
    assert prod_res.status == "conflict"  # Catastrophic false conflict on valid geometry

    # Strategy D correctly rejects the 90° line and binds to the true horizontal dim line
    engine_dim = EngineRawLine(id="dim_line_200", p1_px=(100.0, 100.0), p2_px=(300.0, 100.0))
    engine_wit = EngineRawLine(id="witness_vert_60", p1_px=(100.0, 70.0), p2_px=(100.0, 130.0))
    engine_txt = EngineRawText(
        id="txt_200",
        content="200",
        bbox_px=(110.0, 75.0, 130.0, 95.0),
        rotation_deg=0.0,
        parsed_value=200.0,
    )
    d_results = strategy_d_cross_validate(
        [engine_txt],
        raw_lines=[engine_dim, engine_wit],
        calibration=EngineCalibration(1.0),
    )
    assert len(d_results) == 1
    assert d_results[0].geometry_id == "dim_line_200"
    assert d_results[0].status == "confirmed"


def test_red_2_staggered_text_on_long_line_exceeds_threshold():
    """RED 2: Staggered text on a long dimension line exceeds max_distance_px (150px)

    and gets stolen by an adjacent short feature line.
    """
    cal = _make_calibration(1.0)

    # Long dimension line: length 500px, midpoint at (350, 200)
    long_dim = RawLine(
        id="long_dim_500",
        p1_px=(100.0, 200.0),
        p2_px=(600.0, 200.0),
        confidence=1.0,
        bbox_px=(100.0, 200.0, 600.0, 200.0),
    )

    # Short feature line: length 60px, midpoint at (150, 170)
    short_feat = RawLine(
        id="short_feat_60",
        p1_px=(120.0, 170.0),
        p2_px=(180.0, 170.0),
        confidence=1.0,
        bbox_px=(120.0, 170.0, 180.0, 170.0),
    )

    # Text placed at (160, 185) (staggered drafting placement)
    # Distance to long_dim midpoint (350, 200): sqrt(190^2 + 15^2) = 190.59px > 150px!
    # Distance to short_feat midpoint (150, 170): sqrt(10^2 + 15^2) = 18.02px <= 150px
    text = RawText(
        id="txt_500",
        content="500",
        bbox_px=(150, 175, 170, 195),
        rotation_deg=0.0,
        confidence=1.0,
        source="text_tesseract",
        parsed_value=500.0,
        semantic_role="dimension_value",
    )

    prod_results = cross_validate([text], [long_dim, short_feat], cal, max_distance_px=150.0)
    assert len(prod_results) == 1
    # FAILS in production: associates with short_feat and produces conflict
    assert prod_results[0].geometry_primitive_id == "short_feat_60"
    assert prod_results[0].status == "conflict"

    # Strategy D evaluates perpendicular distance (15px) inside axial corridor [100, 600]
    engine_long = EngineRawLine(id="long_dim_500", p1_px=(100.0, 200.0), p2_px=(600.0, 200.0))
    engine_short = EngineRawLine(id="short_feat_60", p1_px=(120.0, 170.0), p2_px=(180.0, 170.0))
    engine_txt = EngineRawText(
        id="txt_500",
        content="500",
        bbox_px=(150.0, 175.0, 170.0, 195.0),
        rotation_deg=0.0,
        parsed_value=500.0,
    )
    d_results = strategy_d_cross_validate(
        [engine_txt],
        raw_lines=[engine_long, engine_short],
        calibration=EngineCalibration(1.0),
    )
    assert len(d_results) == 1
    assert d_results[0].geometry_id == "long_dim_500"
    assert d_results[0].status == "confirmed"


def test_red_3_chained_dimensions_greedy_duplicate_stealing():
    """RED 3: Independent per-text matching allows multiple texts to claim the same line."""
    cal = _make_calibration(1.0)

    # Chained dimension span 1: Line 1 = 100px
    line_1 = RawLine(
        id="line_span_1",
        p1_px=(0.0, 100.0),
        p2_px=(100.0, 100.0),
        confidence=1.0,
        bbox_px=(0.0, 100.0, 100.0, 100.0),
    )

    # Text 1 for span 1: centered at (50, 85)
    text_1 = RawText(
        id="txt_1",
        content="100",
        bbox_px=(40, 75, 60, 95),
        rotation_deg=0.0,
        confidence=1.0,
        source="text_tesseract",
        parsed_value=100.0,
        semantic_role="dimension_value",
    )

    # Text 2 for missing span 2: centered at (130, 85), parsed_value = 60.0
    # Distance from Text 2 to line_1 midpoint (50, 100): sqrt(80^2 + 15^2) = 81.39px <= 150px
    text_2 = RawText(
        id="txt_2",
        content="60",
        bbox_px=(120, 75, 140, 95),
        rotation_deg=0.0,
        confidence=1.0,
        source="text_tesseract",
        parsed_value=60.0,
        semantic_role="dimension_value",
    )

    prod_results = cross_validate([text_1, text_2], [line_1], cal, max_distance_px=150.0)
    assert len(prod_results) == 2
    # FAILS in production: line_span_1 is assigned to BOTH text_1 and text_2!
    assert prod_results[0].geometry_primitive_id == "line_span_1"
    assert prod_results[1].geometry_primitive_id == "line_span_1"
    assert prod_results[1].status == "conflict"  # text_2 falsely conflicts on text_1's line!

    # Strategy D bipartite matching enforces 1-to-1: text_1 gets line_span_1, text_2 is unverified
    engine_l1 = EngineRawLine(id="line_span_1", p1_px=(0.0, 100.0), p2_px=(100.0, 100.0))
    engine_t1 = EngineRawText(id="txt_1", content="100", bbox_px=(40.0, 75.0, 60.0, 95.0), parsed_value=100.0)
    engine_t2 = EngineRawText(id="txt_2", content="60", bbox_px=(120.0, 75.0, 140.0, 95.0), parsed_value=60.0)

    d_results = strategy_d_cross_validate([engine_t1, engine_t2], raw_lines=[engine_l1])
    assert len(d_results) == 2
    assert d_results[0].geometry_id == "line_span_1"
    assert d_results[0].status == "confirmed"
    assert d_results[1].geometry_id == ""
    assert d_results[1].status == "unverified"


def test_red_4_circular_dimension_blindness():
    """RED 4: cross_validate only accepts raw_lines, completely blind to circles/arcs."""
    cal = _make_calibration(1.0)

    # Circle with diameter 50px (radius 25px) at (300, 300)
    # A short centerline is nearby: length 40px
    centerline = RawLine(
        id="centerline_40",
        p1_px=(300.0, 280.0),
        p2_px=(300.0, 320.0),
        confidence=1.0,
        bbox_px=(300.0, 280.0, 300.0, 320.0),
    )

    text_diam = RawText(
        id="txt_diam_50",
        content="Ø50",
        bbox_px=(290, 255, 310, 275),  # center (300, 265)
        rotation_deg=0.0,
        confidence=1.0,
        source="text_tesseract",
        parsed_value=50.0,
        semantic_role="dimension_value",
    )

    # In production, cross_validate has no parameter for raw_circles
    prod_results = cross_validate([text_diam], [centerline], cal)
    assert len(prod_results) == 1
    # FAILS in production: either pairs with centerline or fails to unverified, cannot verify circle
    assert prod_results[0].geometry_primitive_id == "centerline_40"
    assert prod_results[0].status == "conflict"

    # Strategy D accepts raw_circles and understands diameter callouts
    engine_circ = RawCircle(id="circ_50", center_px=(300.0, 300.0), radius_px=25.0)
    engine_txt = EngineRawText(
        id="txt_diam_50",
        content="Ø50",
        bbox_px=(290.0, 255.0, 310.0, 275.0),
        rotation_deg=0.0,
        parsed_value=50.0,
        callout_type="diameter",
    )
    d_results = strategy_d_cross_validate(
        [engine_txt],
        raw_lines=[EngineRawLine("centerline_40", (300.0, 280.0), (300.0, 320.0))],
        raw_circles=[engine_circ],
    )
    assert len(d_results) == 1
    assert d_results[0].geometry_id == "circ_50"
    assert d_results[0].geometry_type == "circle"
    assert d_results[0].status == "confirmed"


def test_red_5_stacked_baseline_rails_select_wrong_dimension():
    """RED 5: Parallel baseline dimension rails where midpoint distance selects the wrong line."""
    cal = _make_calibration(1.0)

    # Lower rail: length 200px at y=120, midpoint at (200, 120)
    rail_lower = RawLine(
        id="rail_lower_200",
        p1_px=(100.0, 120.0),
        p2_px=(300.0, 120.0),
        confidence=1.0,
        bbox_px=(100.0, 120.0, 300.0, 120.0),
    )

    # Upper rail: length 300px at y=150, midpoint at (250, 150)
    rail_upper = RawLine(
        id="rail_upper_300",
        p1_px=(100.0, 150.0),
        p2_px=(400.0, 150.0),
        confidence=1.0,
        bbox_px=(100.0, 150.0, 400.0, 150.0),
    )

    # Text "300" for upper rail placed at (180, 138) (between rails, perpendicular to upper rail is 12px)
    # Distance to rail_lower midpoint (200, 120): sqrt(20^2 + 18^2) = 26.9px
    # Distance to rail_upper midpoint (250, 150): sqrt(70^2 + 12^2) = 71.0px
    text_300 = RawText(
        id="txt_300",
        content="300",
        bbox_px=(170, 128, 190, 148),
        rotation_deg=0.0,
        confidence=1.0,
        source="text_tesseract",
        parsed_value=300.0,
        semantic_role="dimension_value",
    )

    prod_results = cross_validate([text_300], [rail_lower, rail_upper], cal)
    assert len(prod_results) == 1
    # FAILS in production: picks rail_lower because 26.9px < 71.0px
    assert prod_results[0].geometry_primitive_id == "rail_lower_200"
    assert prod_results[0].status == "conflict"

    # Strategy D perpendicular corridor + length consistency selects rail_upper
    engine_lower = EngineRawLine("rail_lower_200", (100.0, 120.0), (300.0, 120.0))
    engine_upper = EngineRawLine("rail_upper_300", (100.0, 150.0), (400.0, 150.0))
    engine_txt = EngineRawText(
        id="txt_300",
        content="300",
        bbox_px=(170.0, 128.0, 190.0, 148.0),
        rotation_deg=0.0,
        parsed_value=300.0,
    )
    d_results = strategy_d_cross_validate([engine_txt], raw_lines=[engine_lower, engine_upper])
    assert len(d_results) == 1
    assert d_results[0].geometry_id == "rail_upper_300"
    assert d_results[0].status == "confirmed"
