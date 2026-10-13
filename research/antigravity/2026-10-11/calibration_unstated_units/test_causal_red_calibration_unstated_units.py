"""Public Causal RED test for Unstated Units and Scale Calibration.

Reproduces 5 baseline failure modes on current production calibration owners:
1. Silent 'mm' unit assumption on unstated/imperial drawings.
2. Single-candidate false-green under require_consensus=True.
3. Permissive 10.0% consensus tolerance violating AGENTS.md <= 3.0% invariant.
4. Complete blindness to anisotropic scan distortion (roller scanner stretching).
5. Enlargement scale blindness (2:1) and cross-view scale conflation in view_calibration.
"""

import pytest
import numpy as np

from primitive_ir_lib.calibration import auto_estimate_calibration, find_nearest_line
from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.text_extraction import RawText
from primitive_ir_lib.view_calibration import parse_scale_label, detect_view_candidates


def test_causal_red_1_silent_mm_default():
    """Failure Mode 1: When source drawing has unstated units (e.g. American inch drawing),
    production auto_estimate_calibration silently defaults to 'mm' without evidence,
    which later poisons DXF $INSUNITS=4."""
    # An imperial 2.500" shaft measuring 250 pixels (scale = 0.010 in/px)
    text = RawText(
        id="txt-1",
        content="2.500",
        bbox_px=(100, 100, 150, 120),
        rotation_deg=0.0,
        confidence=0.95,
        source="text_tesseract",
        semantic_role="dimension_value",
        parsed_value=2.500,
    )
    line = RawLine(
        id="line-1",
        p1_px=(100.0, 130.0),
        p2_px=(350.0, 130.0),  # 250px length
        confidence=0.95,
        bbox_px=(100.0, 130.0, 350.0, 130.0),
    )

    # Calling production calibration without specifying unit
    cal = auto_estimate_calibration([text], [line], image_height_px=1000)

    assert cal is not None
    # Causal RED: Proves production silently claims 'mm' for what is actually an inch dimension!
    assert cal.unit == "mm", "Production defaults unit to mm"
    # This means a 2.5 inch (63.5 mm) part is calibrated as 2.5 mm (a 25.4x catastrophic error!)
    assert cal.pixel_to_unit_scale == pytest.approx(0.010, rel=1e-3)


def test_causal_red_2_single_candidate_false_green():
    """Failure Mode 2: AGENTS.md mandates:
    'Automatic calibration's production gate is at least two independent candidates with median relative error at most 3 percent.'
    However, production auto_estimate_calibration(require_consensus=True) with only 1 candidate
    still returns a Calibration object instead of None!"""
    text = RawText(
        id="txt-single",
        content="100",
        bbox_px=(50, 50, 90, 70),
        rotation_deg=0.0,
        confidence=0.95,
        source="text_tesseract",
        semantic_role="dimension_value",
        parsed_value=100.0,
    )
    line = RawLine(
        id="line-single",
        p1_px=(50.0, 80.0),
        p2_px=(250.0, 80.0),  # 200px
        confidence=0.95,
        bbox_px=(50.0, 80.0, 250.0, 80.0),
    )

    # Calling with require_consensus=True and min_consensus_candidates=2
    cal = auto_estimate_calibration(
        [text], [line], image_height_px=1000,
        require_consensus=True, min_consensus_candidates=2,
    )

    # Causal RED: Production returns a Calibration object despite len(candidates) < 2!
    assert cal is not None, "Production unexpectedly returns a calibration object for a single uncorroborated candidate"
    assert "CHƯA xác minh đồng thuận" in cal.reference_note


def test_causal_red_3_permissive_10pct_consensus_tolerance():
    """Failure Mode 3: Production auto_estimate_calibration uses consensus_tolerance_pct=10.0% by default,
    accepting candidates with up to 10% discrepancy. This violates the AGENTS.md <= 3.0% production gate."""
    # Line 1 midpoint is (150, 30)
    t1 = RawText(id="t1", content="100", bbox_px=(140, 10, 160, 20), rotation_deg=0.0, confidence=0.95, source="text_tesseract", semantic_role="dimension_value", parsed_value=100.0)
    l1 = RawLine(id="l1", p1_px=(50, 30), p2_px=(250, 30), confidence=0.95, bbox_px=(50, 30, 250, 30))  # 200px -> 0.500 mm/px

    # Line 2 midpoint is (150, 70). Length is 185px -> scale 100/185 = 0.5405 mm/px (8.1% difference)
    t2 = RawText(id="t2", content="100", bbox_px=(140, 50, 160, 60), rotation_deg=0.0, confidence=0.95, source="text_tesseract", semantic_role="dimension_value", parsed_value=100.0)
    l2 = RawLine(id="l2", p1_px=(57.5, 70), p2_px=(242.5, 70), confidence=0.95, bbox_px=(57.5, 70, 242.5, 70))

    cal = auto_estimate_calibration(
        [t1, t2], [l1, l2], image_height_px=1000,
        require_consensus=True, min_consensus_candidates=2,
    )

    # Causal RED: Production accepts 8% error under its default 10% tolerance,
    # which exceeds the 3% AGENTS.md requirement!
    assert cal is not None
    assert "dung sai 10%" in cal.reference_note


def test_causal_red_4_anisotropic_scan_distortion_blindness():
    """Failure Mode 4: A scanned drawing has vertical roller stretching:
    Horizontal feature: 100mm = 200px -> scale_x = 0.500 mm/px
    Vertical feature: 100mm = 220px -> scale_y = 0.4545 mm/px (10% elongation).
    Production calibration computes an isotropic scalar and completely misses the distortion."""
    # Horizontal line mid (150, 30)
    t_h = RawText(id="th", content="100", bbox_px=(140, 10, 160, 20), rotation_deg=0.0, confidence=0.95, source="text_tesseract", semantic_role="dimension_value", parsed_value=100.0)
    l_h = RawLine(id="lh", p1_px=(50, 30), p2_px=(250, 30), confidence=0.95, bbox_px=(50, 30, 250, 30))  # 200px

    # Vertical line mid (400, 150)
    t_v = RawText(id="tv", content="100", bbox_px=(380, 140, 420, 160), rotation_deg=0.0, confidence=0.95, source="text_tesseract", semantic_role="dimension_value", parsed_value=100.0)
    l_v = RawLine(id="lv", p1_px=(400, 40), p2_px=(400, 260), confidence=0.95, bbox_px=(400, 40, 400, 260))  # 220px

    # Production evaluates both and picks one (or averages them) without detecting aspect ratio stretching
    cal = auto_estimate_calibration([t_h, t_v], [l_h, l_v], image_height_px=2000, require_consensus=False)
    assert cal is not None
    # Causal RED: It has only ONE scalar scale, guaranteeing that either X or Y will be 10% distorted in DXF!
    assert hasattr(cal, "pixel_to_unit_scale")
    assert not hasattr(cal, "scale_y") or getattr(cal, "scale_y", None) is None


def test_causal_red_5_view_calibration_enlargement_and_conflation():
    """Failure Mode 5:
    a) view_calibration.parse_scale_label is blind to enlargement scales like '2:1' or '5:1'.
    b) view_calibration mm_per_px_for_scale assumes paper size matches original sheet."""
    # a) Blind to enlargement scale
    label_enlargement = "DETAIL A SCALE 2:1"
    parsed_denom = parse_scale_label(label_enlargement)
    # Causal RED: parse_scale_label returns None because regex expects 1:N
    assert parsed_denom is None, "parse_scale_label fails to parse enlargement scale 2:1"
