"""
test_parallel_lines_preservation.py — Negative Control Matrix for Parallel Lines Preservation.

Validates that distinct parallel engineering lines (e.g. walls, lineweight outlines,
slot boundaries, parallel clearances) are 100% PRESERVED and NEVER collapsed into a single line.

In current production (Strategy A):
Any two parallel lines with lateral offset <= perp_tol_px (6.0px) that overlap in projection
are unconditionally collapsed into 1 single line (100% loss of parallel structure).

In Strategy D (Overlap-Aware Parallel Guard):
Two parallel lines with lateral offset d_perp >= 1.5px and longitudinal overlap > 10px
are strictly preserved as 2 distinct lines across all angles and offsets.
"""

from __future__ import annotations

import math
from typing import Sequence
import pytest

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.line_merging import merge_collinear_lines

# Allow running both as standalone and via pytest
try:
    from .line_merging_engine import merge_strategy_d
except ImportError:
    from line_merging_engine import merge_strategy_d


def _make_line(p1: tuple[float, float], p2: tuple[float, float], id_: str, conf: float = 0.9) -> RawLine:
    return RawLine(
        id=id_,
        p1_px=p1,
        p2_px=p2,
        confidence=conf,
        bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])),
    )


def _generate_parallel_pair(
    length: float,
    offset_px: float,
    overlap_ratio: float,
    angle_deg: float,
    origin: tuple[float, float] = (100.0, 100.0),
) -> tuple[RawLine, RawLine]:
    """Generates two parallel lines with specified length, perpendicular offset, overlap, and angle."""
    rad = math.radians(angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    nx, ny = -dy, dx  # normal unit vector

    # Line 1: [0, length]
    p1_a = origin
    p2_a = (origin[0] + dx * length, origin[1] + dy * length)

    # Line 2 shifted along axis by (1 - overlap_ratio) * length, and shifted by offset along normal
    shift_along = (1.0 - overlap_ratio) * length
    p1_b = (origin[0] + dx * shift_along + nx * offset_px, origin[1] + dy * shift_along + ny * offset_px)
    p2_b = (p1_b[0] + dx * length, p1_b[1] + dy * length)

    return (
        _make_line(p1_a, p2_a, f"line_a_{offset_px}px_{angle_deg}deg"),
        _make_line(p1_b, p2_b, f"line_b_{offset_px}px_{angle_deg}deg"),
    )


def test_parallel_matrix_across_offsets_and_angles():
    """Evaluates 7 offsets x 5 angles x 3 overlap ratios = 105 parallel test cases."""
    offsets = [2.0, 3.0, 4.0, 5.0, 5.5, 6.0, 8.0]  # offsets <= 6.0px fail in Strategy A
    angles = [0.0, 30.0, 45.0, 60.0, 90.0]
    overlaps = [0.25, 0.50, 1.0]

    total_cases = 0
    strat_a_collapsed = 0
    strat_d_preserved = 0

    print("\n" + "=" * 80)
    print("PARALLEL LINES PRESERVATION MATRIX (105 CONFIGS)")
    print("=" * 80)

    for offset in offsets:
        for angle in angles:
            for overlap in overlaps:
                total_cases += 1
                l1, l2 = _generate_parallel_pair(200.0, offset, overlap, angle)

                # Strategy A
                res_a = merge_collinear_lines([l1, l2], blocking_texts=[], perp_tol_px=6.0, gap_tol_px=25.0)
                if len(res_a) == 1:
                    strat_a_collapsed += 1

                # Strategy D
                res_d = merge_strategy_d([l1, l2], perp_tol_px=6.0, gap_tol_px=25.0)
                if len(res_d) == 2:
                    strat_d_preserved += 1

    print(f"Total Parallel Pairs Tested: {total_cases}")
    print(f"Strategy A Collapsed Count:  {strat_a_collapsed} / {total_cases} ({strat_a_collapsed / total_cases * 100:.1f}%)")
    print(f"Strategy D Preserved Count:  {strat_d_preserved} / {total_cases} ({strat_d_preserved / total_cases * 100:.1f}%)")

    # In Strategy A, every offset <= 6.0px (6 out of 7 offsets = 90 / 105 = 85.7%) is collapsed!
    assert strat_a_collapsed >= 80, f"Expected Strategy A collapse rate >= 80/105, got {strat_a_collapsed}"

    # In Strategy D, 100% of parallel pairs are preserved!
    assert strat_d_preserved == total_cases, f"Strategy D failed to preserve all parallel pairs: {strat_d_preserved}/{total_cases}"


def test_true_collinear_vs_parallel_separation():
    """Verifies that truly collinear segments (offset=0px) ARE merged, while offset=3px lines are NOT merged."""
    # Collinear segments: (0, 0)->(100, 0) and (110, 0)->(200, 0) (gap 10px, offset 0px)
    c1 = _make_line((0.0, 0.0), (100.0, 0.0), "c1")
    c2 = _make_line((110.0, 0.0), (200.0, 0.0), "c2")

    # Parallel segments: (0, 0)->(100, 0) and (0, 3)->(100, 3) (offset 3px, overlap 100%)
    p1 = _make_line((0.0, 0.0), (100.0, 0.0), "p1")
    p2 = _make_line((0.0, 3.0), (100.0, 3.0), "p2")

    res_c = merge_strategy_d([c1, c2])
    res_p = merge_strategy_d([p1, p2])

    assert len(res_c) == 1, "Truly collinear segments must be merged"
    assert abs(res_c[0].length_px() - 200.0) <= 0.1
    assert len(res_p) == 2, "Parallel segments with 3px offset must NOT be merged"


if __name__ == "__main__":
    test_parallel_matrix_across_offsets_and_angles()
    test_true_collinear_vs_parallel_separation()
    print("PARALLEL LINES PRESERVATION MATRIX PASSED.")
