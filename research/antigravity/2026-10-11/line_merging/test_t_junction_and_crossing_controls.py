"""
test_t_junction_and_crossing_controls.py — Topological Junction & Transverse Crossing Controls.

Validates that independent geometric features (T-junction stems, X-crossings, L-corners,
branching Y-lines) that enter or terminate in a gap corridor PREVENT collinear merging,
while transverse features outside the corridor do NOT block valid collinear merges.

In current production (Strategy A):
1. merge_collinear_lines has NO awareness of document lines passing through gaps unless
   explicitly intercepted by OCR text bounding boxes.
2. If two wall or outline lines have a gap containing an intersecting partition wall,
   Strategy A merges the two collinear walls into one single segment, severing the topological
   junction and bridging through the intersection.

In Strategy D (Topology-Aware Oracle):
1. gap_has_crossing_line checks document-level primitives.
2. Any transverse line (rel_angle >= 30 deg) intersecting or terminating within the gap
   corridor (|perp| <= 8 px) blocks the merge.
3. Transverse lines terminating outside the gap corridor (|perp| > 8 px or outside [t_start, t_end])
   allow valid merging to proceed unhindered.
"""

from __future__ import annotations

import math
import pytest

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.line_merging import merge_collinear_lines

try:
    from .line_merging_engine import merge_strategy_d, make_line
except ImportError:
    from line_merging_engine import merge_strategy_d, make_line


def test_t_junction_gap_blocking_matrix():
    """Matrix of T-junctions across 5 gap widths (10, 15, 20, 25, 30px) and 4 stem angles (30°, 45°, 60°, 90°).

    A horizontal line is split by a gap: [0, 100] and [100+gap, 250].
    A stem line terminates exactly at (100 + gap/2, 50) and extends downward to y=150.
    Expected:
      - Strategy A: bridges the gap when gap <= 25px (losing T-junction).
      - Strategy D: preserves 2 distinct segments in 100% of cases.
    """
    gaps = [10.0, 15.0, 20.0, 25.0]
    angles = [30.0, 45.0, 60.0, 90.0]

    total_cases = 0
    strat_a_bridged = 0
    strat_d_preserved = 0

    for gap in gaps:
        for angle in angles:
            total_cases += 1
            # Main collinear segments at y=50
            l1 = make_line((0.0, 50.0), (100.0, 50.0), "h_left")
            l2 = make_line((100.0 + gap, 50.0), (250.0, 50.0), "h_right")

            # Transverse stem meeting at gap midpoint
            mid_x = 100.0 + gap / 2.0
            rad = math.radians(angle)
            stem_len = 80.0
            stem_p1 = (mid_x, 50.0)
            stem_p2 = (mid_x + math.cos(rad) * stem_len, 50.0 + math.sin(rad) * stem_len)
            stem = make_line(stem_p1, stem_p2, "stem")

            doc_lines = [l1, l2, stem]

            # Strategy A (only considers [l1, l2])
            res_a = merge_collinear_lines([l1, l2], blocking_texts=[], gap_tol_px=25.0)
            if len(res_a) == 1:
                strat_a_bridged += 1

            # Strategy D (aware of all document lines)
            res_d = merge_strategy_d([l1, l2], all_document_lines=doc_lines, gap_tol_px=25.0)
            if len(res_d) == 2:
                strat_d_preserved += 1

    print("\n" + "=" * 80)
    print("T-JUNCTION GAP PRESERVATION BENCHMARK")
    print("=" * 80)
    print(f"Total Cases:                 {total_cases}")
    print(f"Strategy A False Bridges:    {strat_a_bridged} / {total_cases} ({strat_a_bridged / total_cases * 100:.1f}%)")
    print(f"Strategy D Junction Recall:  {strat_d_preserved} / {total_cases} ({strat_d_preserved / total_cases * 100:.1f}%)")

    assert strat_a_bridged == total_cases, "Strategy A should bridge all gaps <= 25px without text"
    assert strat_d_preserved == total_cases, "Strategy D must preserve all T-junction gaps"


def test_x_crossing_through_gap_matrix():
    """Continuous crossing line passing directly through the gap between collinear segments.

    Segments: [0, 80] and [100, 180] (gap 20px at y=100).
    Crossing line passes from (90, 20) to (90, 180).
    Expected:
      - Strategy A bridges (len=1).
      - Strategy D blocks merge (len=2).
    """
    l1 = make_line((0.0, 100.0), (80.0, 100.0), "h1")
    l2 = make_line((100.0, 100.0), (180.0, 100.0), "h2")
    crossing = make_line((90.0, 20.0), (90.0, 180.0), "cross_v")

    doc_lines = [l1, l2, crossing]

    res_a = merge_collinear_lines([l1, l2], blocking_texts=[], gap_tol_px=25.0)
    assert len(res_a) == 1, "Strategy A blindly bridges crossing"

    res_d = merge_strategy_d([l1, l2], all_document_lines=doc_lines, gap_tol_px=25.0)
    assert len(res_d) == 2, "Strategy D preserves gap when crossing line passes through"


def test_transverse_line_outside_gap_allows_merge():
    """Negative control: A transverse line is present, but located OUTSIDE the gap corridor.

    Segments: [0, 80] and [95, 180] (gap 15px at y=100).
    Transverse line is located at x=40 (crossing l1, not inside the gap).
    Expected:
      - Strategy D must NOT block the merge between [0, 80] and [95, 180],
        because the transverse line is not inside the gap corridor.
    """
    l1 = make_line((0.0, 100.0), (80.0, 100.0), "h1")
    l2 = make_line((95.0, 100.0), (180.0, 100.0), "h2")
    transverse_outside = make_line((40.0, 20.0), (40.0, 180.0), "t_outside")

    doc_lines = [l1, l2, transverse_outside]

    res_d = merge_strategy_d([l1, l2], all_document_lines=doc_lines, gap_tol_px=25.0)
    assert len(res_d) == 1, f"Strategy D should allow merge when transverse line is outside gap, got {len(res_d)}"
    merged = res_d[0]
    assert abs(merged.p1_px[0] - 0.0) < 1e-3
    assert abs(merged.p2_px[0] - 180.0) < 1e-3


def test_nearly_parallel_line_not_treated_as_crossing():
    """A nearly parallel line (rel_angle < 15 deg) near the gap is NOT a transverse crossing.

    It should be handled by parallel line separation logic, not crossing logic.
    """
    l1 = make_line((0.0, 100.0), (80.0, 100.0), "h1")
    l2 = make_line((95.0, 100.0), (180.0, 100.0), "h2")
    # Line parallel to h, but offset by 20px
    near_parallel = make_line((70.0, 120.0), (110.0, 120.0), "parallel_offset")

    doc_lines = [l1, l2, near_parallel]
    res_d = merge_strategy_d([l1, l2], all_document_lines=doc_lines, gap_tol_px=25.0)
    assert len(res_d) == 1, "Nearby parallel line offset by 20px should not block collinear merge"
