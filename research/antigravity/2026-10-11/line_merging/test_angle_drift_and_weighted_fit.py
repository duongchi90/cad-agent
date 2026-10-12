"""
test_angle_drift_and_weighted_fit.py — Angular Stability & Length-Squared Weighted Fit Benchmark.

Validates that length-squared weighted orientation fitting (Strategy D) is impervious to
noisy short fragment skews across cardinal and non-cardinal angles, whereas Strategy A
exhibits severe angle skew and lateral endpoint drift due to first-segment angle locking.

Mathematical Formulation:
Given cluster segments {s_i} with lengths L_i and orientations theta_i:
Strategy A:
  ref_angle = theta_0  (biased entirely to whichever segment appears first)
Strategy D:
  w_i = L_i^2
  ref_angle = 0.5 * atan2(sum(w_i * sin(2 * theta_i)), sum(w_i * cos(2 * theta_i))) mod pi
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.line_merging import merge_collinear_lines

try:
    from .line_merging_engine import merge_strategy_d, make_line, angle_diff_mod_pi
except ImportError:
    from line_merging_engine import merge_strategy_d, make_line, angle_diff_mod_pi


def test_angle_stability_across_full_rotation_circle():
    """Evaluates angle stability across 12 angles from 0 to 165 degrees in 15-degree steps.

    Each case consists of:
    - A 400px ground-truth main line segment.
    - A 12px short fragment near the start, rotated by +2.8 degrees relative to true angle.
    - Both segments are collinear within 1.0 px lateral offset.

    Evaluates:
    - Angle error (deg) of merged line vs ground-truth.
    - Lateral endpoint drift (px) of merged line endpoints vs true line axis.
    """
    test_angles = [0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0, 105.0, 120.0, 135.0, 150.0, 165.0]

    strat_a_angle_errors = []
    strat_a_drifts = []
    strat_d_angle_errors = []
    strat_d_drifts = []

    print("\n" + "=" * 90)
    print("ANGULAR STABILITY BENCHMARK (12 ANGLES x PERTURBED FRAGMENT)")
    print("=" * 90)
    print(f"{'Angle':>6} | {'Strat A Error':>14} | {'Strat A Drift':>14} | {'Strat D Error':>14} | {'Strat D Drift':>14}")
    print("-" * 90)

    for true_angle_deg in test_angles:
        rad = math.radians(true_angle_deg)
        dx, dy = math.cos(rad), math.sin(rad)
        nx, ny = -dy, dx

        origin_x, origin_y = 200.0, 200.0

        # Fragment 1: 12px long, rotated by +2.8 deg, starting at t=0
        frag_rad = math.radians(true_angle_deg + 2.8)
        f_dx, f_dy = math.cos(frag_rad), math.sin(frag_rad)
        p1_frag = (origin_x, origin_y)
        p2_frag = (origin_x + f_dx * 12.0, origin_y + f_dy * 12.0)
        l_frag = make_line(p1_frag, p2_frag, "frag")

        # Main line: 400px long, at true angle, from t=15 to t=415
        p1_main = (origin_x + dx * 15.0, origin_y + dy * 15.0)
        p2_main = (origin_x + dx * 415.0, origin_y + dy * 415.0)
        l_main = make_line(p1_main, p2_main, "main")

        # Order: fragment first (triggers Strategy A's first-segment bias)
        lines = [l_frag, l_main]

        # Strategy A
        res_a = merge_collinear_lines(lines, blocking_texts=[], gap_tol_px=25.0)
        assert len(res_a) == 1
        m_a = res_a[0]
        a_dx = m_a.p2_px[0] - m_a.p1_px[0]
        a_dy = m_a.p2_px[1] - m_a.p1_px[1]
        a_angle = math.atan2(a_dy, a_dx) % math.pi
        err_a = math.degrees(angle_diff_mod_pi(a_angle, rad))
        # Lateral drift of endpoint from true line
        drift_a = abs(-(m_a.p2_px[0] - origin_x) * dy + (m_a.p2_px[1] - origin_y) * dx)

        strat_a_angle_errors.append(err_a)
        strat_a_drifts.append(drift_a)

        # Strategy D
        res_d = merge_strategy_d(lines, gap_tol_px=25.0)
        assert len(res_d) == 1
        m_d = res_d[0]
        d_dx = m_d.p2_px[0] - m_d.p1_px[0]
        d_dy = m_d.p2_px[1] - m_d.p1_px[1]
        d_angle = math.atan2(d_dy, d_dx) % math.pi
        err_d = math.degrees(angle_diff_mod_pi(d_angle, rad))
        drift_d = abs(-(m_d.p2_px[0] - origin_x) * dy + (m_d.p2_px[1] - origin_y) * dx)

        strat_d_angle_errors.append(err_d)
        strat_d_drifts.append(drift_d)

        print(f"{true_angle_deg:6.1f}°| {err_a:12.3f}° | {drift_a:12.2f}px | {err_d:12.4f}° | {drift_d:12.4f}px")

    mean_err_a = np.mean(strat_a_angle_errors)
    mean_drift_a = np.mean(strat_a_drifts)
    mean_err_d = np.mean(strat_d_angle_errors)
    mean_drift_d = np.mean(strat_d_drifts)

    print("-" * 90)
    print(f"MEAN:  | {mean_err_a:12.3f}° | {mean_drift_a:12.2f}px | {mean_err_d:12.4f}° | {mean_drift_d:12.4f}px")
    print("=" * 90)

    # Strategy A locks to the 2.8° fragment skew, producing severe drift > 15px
    assert mean_err_a > 2.5, f"Strategy A should have ~2.8° error, got {mean_err_a:.2f}°"
    assert mean_drift_a > 15.0, f"Strategy A should have >15px drift, got {mean_drift_a:.2f}px"

    # Strategy D bounds angle error to < 0.01° and lateral drift to < 0.05px
    assert mean_err_d < 0.01, f"Strategy D angle error must be < 0.01°, got {mean_err_d:.4f}°"
    assert mean_drift_d < 0.05, f"Strategy D lateral drift must be < 0.05px, got {mean_drift_d:.4f}px"


def test_multi_fragment_length_weighted_attenuation():
    """Validates that a chain of 5 fragments with random angular jitter converges to the dominant span.

    Chain layout along true horizontal axis (y=100):
    - seg0: len=15px, angle= +2.5 deg
    - seg1: len=25px, angle= -1.8 deg
    - seg2: len=350px (dominant main span), angle= 0.0 deg
    - seg3: len=20px, angle= +2.0 deg
    - seg4: len=10px, angle= -2.2 deg

    All gaps between consecutive segments are 6px (total line length ~ 450px).
    Expected:
      - Strategy A (starting with seg0) locks to +2.5° error.
      - Strategy D weights seg2 by (350)^2 = 122,500 vs sum of small (15^2+25^2+20^2+10^2) = 1,350.
        Weight ratio > 90:1. Resulting angle error is < 0.03 deg.
    """
    origin_x, origin_y = 50.0, 100.0
    segs_def = [
        (15.0, 2.5),
        (25.0, -1.8),
        (350.0, 0.0),
        (20.0, 2.0),
        (10.0, -2.2),
    ]
    gap = 6.0

    lines = []
    cur_x = origin_x
    for i, (length, angle_jitter_deg) in enumerate(segs_def):
        rad = math.radians(angle_jitter_deg)
        dx, dy = math.cos(rad), math.sin(rad)
        p1 = (cur_x, origin_y)
        p2 = (cur_x + dx * length, origin_y + dy * length)
        lines.append(make_line(p1, p2, f"seg_{i}"))
        cur_x += length + gap

    # Strategy A
    res_a = merge_collinear_lines(lines, blocking_texts=[], gap_tol_px=10.0)
    assert len(res_a) == 1
    m_a = res_a[0]
    ang_a = math.degrees(math.atan2(m_a.p2_px[1] - m_a.p1_px[1], m_a.p2_px[0] - m_a.p1_px[0]))
    drift_a = abs(m_a.p2_px[1] - origin_y)

    # Strategy D
    res_d = merge_strategy_d(lines, gap_tol_px=10.0)
    assert len(res_d) == 1
    m_d = res_d[0]
    ang_d = math.degrees(math.atan2(m_d.p2_px[1] - m_d.p1_px[1], m_d.p2_px[0] - m_d.p1_px[0]))
    drift_d = abs(m_d.p2_px[1] - origin_y)

    print(f"\nMulti-fragment chain: Strat A angle={ang_a:.3f}°, drift={drift_a:.2f}px | Strat D angle={ang_d:.4f}°, drift={drift_d:.4f}px")

    assert abs(ang_a - 2.5) < 0.1, f"Strategy A should lock to seg0 (+2.5°), got {ang_a:.2f}°"
    assert drift_a > 15.0, f"Strategy A drift should exceed 15px, got {drift_a:.2f}px"

    assert abs(ang_d) < 0.03, f"Strategy D angle error must be < 0.03°, got {ang_d:.4f}°"
    assert drift_d < 0.15, f"Strategy D drift must be < 0.15px, got {drift_d:.4f}px"
