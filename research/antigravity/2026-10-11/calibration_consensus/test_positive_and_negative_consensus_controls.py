"""
test_positive_and_negative_consensus_controls.py — Positive Fixtures & Strong Negative Controls.

Validates that Strategy D strictly adheres to the AGENTS.md invariant:
- Gate: >= 2 independent candidates with median relative error <= 3.0%.
- Positive fixtures with <= 3% error PASS cleanly.
- Negative controls (single candidate, > 3% error, conflicting views, noise numbers) FAIL CLOSED.
"""

from __future__ import annotations

import pytest

try:
    from .calibration_consensus_engine import make_line, make_text, run_strategy_d
except ImportError:
    from calibration_consensus_engine import make_line, make_text, run_strategy_d


def test_positive_two_candidate_horizontal():
    """Positive: Exactly 2 independent horizontal candidates agreeing within 1.0% error."""
    t1 = make_text("1000", (100, 100, 150, 120), id_="t1")
    l1 = make_line((100.0, 130.0), (350.0, 130.0), id_="l1")  # len=250 -> s=4.000

    t2 = make_text("2000", (200, 300, 250, 320), id_="t2")
    l2 = make_line((200.0, 330.0), (702.0, 330.0), id_="l2")  # len=502 -> s=3.984 (0.4% error)

    cal = run_strategy_d([t1, t2], [l1, l2], max_relative_error_pct=3.0)
    assert cal is not None
    assert abs(cal.pixel_to_unit_scale - 4.0) < 0.05
    assert "Strategy D Consensus: 2/2" in cal.reference_note


def test_positive_three_candidate_vertical():
    """Positive: 3 vertical candidates with minor sensor discretization jitter (< 1.5% error)."""
    t1 = make_text("1200", (1465, 320, 1495, 380), rotation_deg=90.0, id_="tv1")
    l1 = make_line((1500.0, 200.0), (1500.0, 500.0), id_="lv1")  # len=300 -> s=4.000

    t2 = make_text("2400", (1665, 470, 1695, 530), rotation_deg=90.0, id_="tv2")
    l2 = make_line((1700.0, 200.0), (1700.0, 796.0), id_="lv2")  # len=596 -> s=4.027 (0.7% error)

    t3 = make_text("1600", (1865, 370, 1895, 430), rotation_deg=90.0, id_="tv3")
    l3 = make_line((1900.0, 200.0), (1900.0, 603.0), id_="lv3")  # len=403 -> s=3.970 (0.7% error)

    cal = run_strategy_d([t1, t2, t3], [l1, l2, l3], max_relative_error_pct=3.0)
    assert cal is not None
    assert abs(cal.pixel_to_unit_scale - 4.0) < 0.05
    assert "Strategy D Consensus: 3/3" in cal.reference_note


def test_positive_mixed_horizontal_and_vertical_consistent():
    """Positive: 2 horizontal and 2 vertical candidates all agreeing within 1.0% error."""
    th1 = make_text("1000", (100, 100, 150, 120), id_="th1")
    lh1 = make_line((100.0, 130.0), (350.0, 130.0), id_="lh1")  # s=4.00

    th2 = make_text("2000", (200, 300, 250, 320), id_="th2")
    lh2 = make_line((200.0, 330.0), (700.0, 330.0), id_="lh2")  # s=4.00

    tv1 = make_text("1200", (1465, 320, 1495, 380), rotation_deg=90.0, id_="tv1")
    lv1 = make_line((1500.0, 200.0), (1500.0, 500.0), id_="lv1")  # s=4.00

    tv2 = make_text("2400", (1665, 470, 1695, 530), rotation_deg=90.0, id_="tv2")
    lv2 = make_line((1700.0, 200.0), (1700.0, 800.0), id_="lv2")  # s=4.00

    cal = run_strategy_d([th1, th2, tv1, tv2], [lh1, lh2, lv1, lv2], max_relative_error_pct=3.0)
    assert cal is not None
    assert abs(cal.pixel_to_unit_scale - 4.0) < 0.01
    assert "Strategy D Consensus: 4/4" in cal.reference_note


def test_negative_single_candidate_fails_closed():
    """Negative: Exactly 1 valid candidate exists. Must return None (fail closed per AGENTS.md)."""
    t1 = make_text("1000", (100, 100, 150, 120), id_="t1")
    l1 = make_line((100.0, 130.0), (350.0, 130.0), id_="l1")  # s=4.00

    cal = run_strategy_d([t1], [l1], max_relative_error_pct=3.0, min_consensus_candidates=2)
    assert cal is None, "Single candidate must fail closed (cannot confirm consensus)"


def test_negative_relative_error_exceeds_3_percent():
    """Negative: 2 candidates with 3.8% relative error (> 3.0% gate) must return None."""
    t1 = make_text("1000", (100, 100, 150, 120), id_="t1")
    l1 = make_line((100.0, 130.0), (350.0, 130.0), id_="l1")  # s=4.000

    t2 = make_text("1000", (500, 500, 550, 520), id_="t2")
    l2 = make_line((500.0, 530.0), (741.0, 530.0), id_="l2")  # len=241 -> s=4.149 (3.73% error)

    cal = run_strategy_d([t1, t2], [l1, l2], max_relative_error_pct=3.0)
    assert cal is None, "3.73% error exceeds 3.0% gate; must return None"


def test_negative_mixed_view_conflict_without_majority():
    """Negative: Two different views on same page with 1 candidate each (s=7.05 vs s=3.52)."""
    t1 = make_text("1000", (100, 100, 150, 120), id_="t_v1")
    l1 = make_line((100.0, 130.0), (241.8, 130.0), id_="l_v1")  # s=7.052

    t2 = make_text("1000", (1000, 1000, 1050, 1020), id_="t_v2")
    l2 = make_line((1000.0, 1030.0), (1284.1, 1030.0), id_="l_v2")  # s=3.521

    cal = run_strategy_d([t1, t2], [l1, l2], max_relative_error_pct=3.0)
    assert cal is None, "Mixed-scale conflicting views with 1 candidate each must fail closed"


def test_negative_all_noise_numbers():
    """Negative: Only sheet numbers and revision numbers present ('09', '1', '2')."""
    t1 = make_text("09", (100, 100, 130, 120), id_="t_sheet")
    l1 = make_line((50.0, 125.0), (250.0, 125.0), id_="l1")

    t2 = make_text("1", (500, 500, 520, 520), id_="t_rev")
    l2 = make_line((450.0, 525.0), (550.0, 525.0), id_="l2")

    cal = run_strategy_d([t1, t2], [l1, l2], max_relative_error_pct=3.0)
    assert cal is None, "All noise numbers must be filtered out, returning None"
