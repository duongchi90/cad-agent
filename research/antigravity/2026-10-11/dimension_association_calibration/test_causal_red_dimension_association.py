"""Causal RED test suite reproducing 5 baseline failure modes in production dimension-geometry association.

Failure Modes:
RED 1: Text Gap Line Halving: Dimension text placed in a gap between two line segments.
       Production picks one segment, resulting in a 150% scale error (80px vs true 200px span).
RED 2: Horizontal Text Perpendicular Hijacking: Horizontal text bypasses angle filtering
       and binds to a nearby vertical witness line or part contour.
RED 3: Diameter Callout Blindness: Production find_nearest_line only accepts lines,
       completely blind to circles and boreholes with 'Ø50' callouts.
RED 4: Extension Line Midpoint Stealing: Witness line perpendicular to dimension
       has its midpoint closer to text than fragmented dimension segments.
RED 5: Out-of-Span / Outside Leader Dimension Drop: Text placed outside narrow extension
       lines with leader pointer is discarded or associated with wrong body line.
"""

import pytest
import numpy as np

from primitive_ir_lib.calibration import find_nearest_line, auto_estimate_calibration
from primitive_ir_lib.text_extraction import RawText
from primitive_ir_lib.geometry_extraction import RawLine


def test_red_1_text_gap_halves_line_length_causing_catastrophic_scale_error():
    """RED 1: A 200px horizontal dimension line has a central gap where text '100' sits.
    The line is fragmented into two 80px segments:
      - seg1: (100, 100) -> (180, 100) [length 80px, midpoint (140, 100)]
      - seg2: (220, 100) -> (300, 100) [length 80px, midpoint (260, 100)]
    Text '100' is at (185, 90, 215, 110) with center (200, 100).
    True span is 200px (100 to 300), so true scale is 100.0 / 200.0 = 0.50 mm/px.
    Production pairs with one 80px segment, giving scale 100.0 / 80.0 = 1.25 mm/px (+150% error!)."""
    text = RawText(
        id="dim_text_1",
        content="100",
        bbox_px=(185.0, 90.0, 215.0, 110.0),
        rotation_deg=0.0,
        confidence=0.98,
        source="ocr",
        parsed_value=100.0,
        semantic_role="dimension_value",
    )
    seg1 = RawLine(id="seg1", p1_px=(100.0, 100.0), p2_px=(180.0, 100.0), confidence=0.95, bbox_px=(100.0, 100.0, 180.0, 100.0))
    seg2 = RawLine(id="seg2", p1_px=(220.0, 100.0), p2_px=(300.0, 100.0), confidence=0.95, bbox_px=(220.0, 100.0, 300.0, 100.0))

    # Production find_nearest_line picks one segment:
    matched_line = find_nearest_line(text, [seg1, seg2], max_distance_px=150.0)
    assert matched_line is not None
    assert matched_line.id in ("seg1", "seg2")

    # The matched length is only 80px instead of the true 200px span:
    matched_length = matched_line.length_px()
    assert matched_length == 80.0

    # Scale calculation produces 1.25 mm/px instead of 0.50 mm/px
    estimated_scale = text.parsed_value / matched_length
    true_scale = 100.0 / 200.0
    relative_error = abs(estimated_scale - true_scale) / true_scale
    assert relative_error == 1.50  # 150% scale error!


def test_red_2_horizontal_text_binds_to_perpendicular_vertical_line():
    """RED 2: Production bypasses angle filtering when text.rotation_deg == 0.0.
    A horizontal dimension text '50' at (200, 100) is near a vertical witness line
    from (210, 40) to (210, 160) [midpoint (210, 100), dist=10px].
    The horizontal dimension line is at y=120 from (150, 120) to (250, 120) [midpoint (200, 120), dist=20px].
    Because 10px < 20px, find_nearest_line picks the VERTICAL line!"""
    text = RawText(
        id="dim_text_h",
        content="50",
        bbox_px=(190.0, 95.0, 210.0, 105.0),
        rotation_deg=0.0,  # Horizontal text
        confidence=0.95,
        source="ocr",
        parsed_value=50.0,
        semantic_role="dimension_value",
    )
    vertical_witness = RawLine(id="vert_witness", p1_px=(210.0, 40.0), p2_px=(210.0, 160.0), confidence=0.95, bbox_px=(210.0, 40.0, 210.0, 160.0))
    horizontal_dim_line = RawLine(id="horiz_dim", p1_px=(150.0, 120.0), p2_px=(250.0, 120.0), confidence=0.95, bbox_px=(150.0, 120.0, 250.0, 120.0))

    # Production picks vertical line because midpoint is 10px vs 20px!
    best = find_nearest_line(text, [vertical_witness, horizontal_dim_line])
    assert best is not None
    assert best.id == "vert_witness"  # Fatal error: horizontal dimension text paired with vertical line!


def test_red_3_diameter_callout_completely_unsupported():
    """RED 3: In mechanical drawings, diameter callouts 'Ø50' or '%%c50' refer to boreholes.
    find_nearest_line only accepts List[RawLine]. It has zero ability to match circles."""
    text = RawText(
        id="dim_diam",
        content="Ø50",
        bbox_px=(300.0, 200.0, 340.0, 220.0),
        rotation_deg=0.0,
        confidence=0.95,
        source="ocr",
        parsed_value=50.0,
        semantic_role="dimension_value",
    )
    # Even if drawing has a borehole circle at (300, 200) with diameter 100px (radius 50px),
    # find_nearest_line cannot accept or evaluate circles.
    # If no lines exist nearby, it returns None.
    best = find_nearest_line(text, [])
    assert best is None


def test_red_4_extension_line_midpoint_stealing():
    """RED 4: Extension witness lines often have midpoints very close to dimension text.
    In a vertical dimension where text is rotated 90 deg, but text rotation detection
    has slight error (e.g. 0 deg or 85 deg), witness line midpoint steals the match."""
    text = RawText(
        id="dim_vert",
        content="80",
        bbox_px=(90.0, 190.0, 110.0, 210.0),
        rotation_deg=0.0,  # OCR reported 0 rotation for vertical dimension
        confidence=0.90,
        source="ocr",
        parsed_value=80.0,
        semantic_role="dimension_value",
    )
    # Horizontal extension line passing right above the dimension line:
    ext_line = RawLine(id="ext_line", p1_px=(80.0, 200.0), p2_px=(130.0, 200.0), confidence=0.90, bbox_px=(80.0, 200.0, 130.0, 200.0))
    # Vertical dimension line:
    dim_line = RawLine(id="dim_line", p1_px=(120.0, 100.0), p2_px=(120.0, 300.0), confidence=0.90, bbox_px=(120.0, 100.0, 120.0, 300.0))

    # Midpoint of ext_line is (105, 200), dist to text center (100, 200) is 5px.
    # Midpoint of dim_line is (120, 200), dist is 20px.
    best = find_nearest_line(text, [ext_line, dim_line])
    assert best.id == "ext_line"  # Steals match, giving scale 80 / 50 = 1.6 instead of 80 / 200 = 0.4!


def test_red_5_auto_estimate_calibration_fails_on_case01_pattern():
    """RED 5: Mimics CASE01 where 14 OCR texts exist, but because texts sit in gaps or near
    witness lines without touching arrows (image_bgr is None or Hough lines broken),
    auto_estimate_calibration returns None or mismatched candidates."""
    # Texts with dimension_value
    texts = [
        RawText(id="t1", content="25.4", bbox_px=(100.0, 100.0, 140.0, 115.0), rotation_deg=0.0, confidence=0.9, source="ocr", parsed_value=25.4, semantic_role="dimension_value"),
        RawText(id="t2", content="50.0", bbox_px=(300.0, 300.0, 340.0, 315.0), rotation_deg=0.0, confidence=0.9, source="ocr", parsed_value=50.0, semantic_role="dimension_value"),
    ]
    # Broken segments only (Hough lines fragmented)
    lines = [
        RawLine(id="l1", p1_px=(10.0, 107.0), p2_px=(80.0, 107.0), confidence=0.8, bbox_px=(10.0, 107.0, 80.0, 107.0)),
        RawLine(id="l2", p1_px=(160.0, 107.0), p2_px=(230.0, 107.0), confidence=0.8, bbox_px=(160.0, 107.0, 230.0, 107.0)),
    ]

    # Without consensus or with consensus, both segments give ~70px instead of true 220px span
    cal = auto_estimate_calibration(texts, lines, image_height_px=1000, require_consensus=True)
    # Fails consensus or gives corrupted scale:
    # l1 length is 70px -> scale = 25.4 / 70 = 0.3628 (true scale is 25.4 / 220 = 0.1154, 300% error!)
    if cal is not None:
        assert abs(cal.pixel_to_unit_scale - 0.1154) / 0.1154 > 1.0  # > 100% error
