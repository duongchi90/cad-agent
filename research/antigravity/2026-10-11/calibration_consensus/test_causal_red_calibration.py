"""
test_causal_red_calibration.py — Public Causal RED on Current Production Calibration Logic.

Demonstrates 5 concrete failure modes in current primitive_ir_lib/calibration.py:
1. RED 1: 60% Scale Corruption from Fragmented Line Pairing (reproducing real scan benchmark).
2. RED 2: Unverified Single Candidate Return due to require_consensus=False default.
3. RED 3: Permissive 10% Consensus Tolerance violating AGENTS.md 3% Invariant.
4. RED 4: Non-Dimension Sheet Number ("09") Hallucination.
5. RED 5: Cross-Axis Aspect Ratio Distortion Blindness.
"""

from __future__ import annotations

import math
import pytest
import numpy as np

from primitive_ir_lib.calibration import auto_estimate_calibration, find_nearest_line
from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.text_extraction import RawText

try:
    from .calibration_consensus_engine import make_line, make_text, run_strategy_a, run_strategy_d
except ImportError:
    from calibration_consensus_engine import make_line, make_text, run_strategy_a, run_strategy_d


def test_red_1_fragmented_line_60_percent_scale_corruption():
    """Reproduces the real scan failure from calibration-auto-estimate-real-image-benchmark.md.

    Nominal ground truth:
    - Text "1970" (1970 mm)
    - True dimension line: length 538 px -> true scale = 1970 / 538 = 3.66 mm/px.
    - Hough fragmented line: length 337 px -> corrupt scale = 1970 / 337 = 5.85 mm/px (+60% error).
    - The fragmented line's midpoint is 16 px from text center; true line midpoint is 46 px away.

    Causal failure in Strategy A:
    find_nearest_line relies on center distance, so it picks the 337px fragment,
    corrupting the calibration scale by ~60%!
    """
    text_1970 = make_text("1970", (4312, 1333, 4376, 1359), rotation_deg=0.0, id_="t_1970")

    # Fragmented Hough line (closer to text midpoint)
    fragment_line = make_line((4174.0, 1346.0), (4511.0, 1346.0), id_="line_fragment_337")
    # True full dimension line (slightly farther from text midpoint)
    true_dim_line = make_line((4172.0, 1380.0), (4710.0, 1380.0), id_="line_true_538")

    # Current production find_nearest_line:
    chosen_line = find_nearest_line(text_1970, [fragment_line, true_dim_line])
    assert chosen_line is not None
    assert chosen_line.id == "line_fragment_337", "Production must reproduce picking the closer fragment"

    # Calibration scale from chosen line
    scale_prod = text_1970.parsed_value / chosen_line.length_px()
    true_scale = text_1970.parsed_value / true_dim_line.length_px()
    rel_error = abs(scale_prod - true_scale) / true_scale * 100.0

    print(f"\n[RED 1] Production Scale: {scale_prod:.4f} mm/px vs True Scale: {true_scale:.4f} mm/px (Error: {rel_error:.1f}%)")
    assert rel_error > 50.0, f"Expected >50% scale error, got {rel_error:.1f}%"


def test_red_2_unverified_single_candidate_default():
    """Production defaults to require_consensus=False, returning first candidate with 0 verification."""
    # Two conflicting texts giving wildly different scales (3.66 mm/px vs 7.20 mm/px)
    t1 = make_text("1000", (100, 100, 150, 120), id_="t1")
    l1 = make_line((100.0, 130.0), (238.8, 130.0), id_="l1")  # len=138.8 -> scale=7.20

    t2 = make_text("2000", (500, 500, 550, 520), id_="t2")
    l2 = make_line((500.0, 530.0), (1046.0, 530.0), id_="l2")  # len=546.0 -> scale=3.66

    # In production default:
    cal = auto_estimate_calibration([t1, t2], [l1, l2], image_height_px=2000, require_consensus=False)
    assert cal is not None
    # Returns the first candidate without noticing that t2 gives an entirely different scale!
    assert abs(cal.pixel_to_unit_scale - 7.20) < 0.1
    print(f"\n[RED 2] Production accepted unverified scale {cal.pixel_to_unit_scale} without checking consensus")


def test_red_3_permissive_10_percent_tolerance_violates_agents_invariant():
    """AGENTS.md mandates <= 3.0% median relative error. Production consensus allows 10.0%."""
    # Candidates with 8.5% scale discrepancy
    # True scale = 4.00
    # Candidate 1: scale = 4.00
    # Candidate 2: scale = 4.34 (+8.5% error)
    t1 = make_text("1000", (100, 100, 150, 120), id_="t1")
    l1 = make_line((100.0, 130.0), (350.0, 130.0), id_="l1")  # len=250 -> scale=4.00

    t2 = make_text("1000", (500, 500, 550, 520), id_="t2")
    l2 = make_line((500.0, 530.0), (730.41, 530.0), id_="l2")  # len=230.41 -> scale=4.340 (+8.5% error)

    # Production consensus_tolerance_pct=10.0 passes this candidate:
    cal_prod = auto_estimate_calibration([t1, t2], [l1, l2], image_height_px=2000, require_consensus=True, consensus_tolerance_pct=10.0)
    assert cal_prod is not None, "Production 10% tolerance accepts candidates with 8.5% error"

    # But Strategy D (enforcing 3.0% gate) rejects it:
    cal_strat_d = run_strategy_d([t1, t2], [l1, l2], max_relative_error_pct=3.0)
    assert cal_strat_d is None, "Strategy D fails closed when relative error exceeds 3.0%"
    print("\n[RED 3] Production accepted 8.5% discrepancy; Strategy D strictly rejected per AGENTS.md")


def test_red_4_sheet_number_noise_hallucination():
    """Non-dimension sheet number ('09') is matched with border line and returned as calibration."""
    # Text "09" from "Sheet: 09"
    t_sheet = make_text("09", (1000, 1000, 1030, 1020), id_="t_sheet")
    # Title block border line of 200px
    l_border = make_line((900.0, 1025.0), (1100.0, 1025.0), id_="l_border")

    cal = auto_estimate_calibration([t_sheet], [l_border], image_height_px=2000, require_consensus=False)
    assert cal is not None
    assert abs(cal.pixel_to_unit_scale - (9.0 / 200.0)) < 1e-4
    print(f"\n[RED 4] Production hallucinated calibration scale {cal.pixel_to_unit_scale} from sheet number '09'")


def test_red_5_cross_axis_aspect_ratio_distortion():
    """Scanned image has non-uniform scaling (sx = 4.0 mm/px, sy = 5.0 mm/px, a 25% distortion)."""
    # Horizontal dimension: 1000mm on 250px line -> sx = 4.0 mm/px
    th1 = make_text("1000", (100, 100, 150, 120), rotation_deg=0.0, id_="th1")
    lh1 = make_line((100.0, 130.0), (350.0, 130.0), id_="lh1")
    th2 = make_text("2000", (200, 100, 250, 120), rotation_deg=0.0, id_="th2")
    lh2 = make_line((200.0, 130.0), (700.0, 130.0), id_="lh2")

    # Vertical dimension: 1000mm on 200px line -> sy = 5.0 mm/px (25% aspect distortion!)
    tv1 = make_text("1000", (500, 500, 520, 550), rotation_deg=90.0, id_="tv1")
    lv1 = make_line((530.0, 500.0), (530.0, 700.0), id_="lv1")
    tv2 = make_text("2000", (600, 500, 620, 550), rotation_deg=90.0, id_="tv2")
    lv2 = make_line((630.0, 500.0), (630.0, 900.0), id_="lv2")

    # Strategy D detects cross-axis aspect ratio distortion (> 3%) and rejects scalar calibration:
    res_d = run_strategy_d([th1, th2, tv1, tv2], [lh1, lh2, lv1, lv2], max_relative_error_pct=3.0)
    assert res_d is None, "Strategy D must reject scalar calibration when horizontal and vertical scales disagree by 25%"
    print("\n[RED 5] Strategy D successfully rejected non-uniform scan with 25% aspect ratio distortion")
