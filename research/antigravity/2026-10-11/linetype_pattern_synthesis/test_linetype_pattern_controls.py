"""Positive fixtures and strong negative controls for linetype pattern detection and synthesis.

Tests:
1. Positive: Long-stroke centerline with dots (ISO 128)
2. Positive: Dense short-dash hidden line (12 strokes)
3. Positive: 60° inclined dashed line
4. Negative: Continuous solid line preserved unaltered
5. Negative: Isolated stray dashes (< 3 strokes) rejected
6. Negative: Large gap (> 8mm) between distinct features not bridged
7. Negative: Parallel cross-hatch lines rejected
8. Negative: Dimension witness lines not merged
"""

import math
import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from primitive_ir_lib.models import Point2D, LineGeometry, Primitive, Trace
from linetype_pattern_engine import (
    LinetypeKind,
    extract_linetypes_strategy_d,
)


def _make_line(id_: str, x0: float, y0: float, x1: float, y1: float) -> Primitive:
    return Primitive(
        id=id_,
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


def test_control_01_positive_long_stroke_centerline_with_dot():
    """Control 1 (Positive): ISO 128 centerline (long dash 20mm, dot 1mm)."""
    pattern = [20.0, 1.0, 20.0, 1.0, 20.0]
    gap = 2.0
    strokes = []
    curr_x = 10.0
    for i, length in enumerate(pattern):
        strokes.append(_make_line(f"c_dot_{i}", curr_x, 50.0, curr_x + length, 50.0))
        curr_x += length + gap

    res = extract_linetypes_strategy_d(strokes)
    assert len(res.synthesized_lines) == 1
    assert res.synthesized_lines[0].linetype == LinetypeKind.CENTER
    assert res.synthesized_lines[0].stroke_count == 5


def test_control_02_positive_dense_short_dash_hidden_line():
    """Control 2 (Positive): Dense 2mm dashes with 1mm gaps forming a 35mm hidden line."""
    strokes = []
    for i in range(12):
        x = 10.0 + i * 3.0
        strokes.append(_make_line(f"dense_{i}", x, 30.0, x + 2.0, 30.0))

    res = extract_linetypes_strategy_d(strokes)
    assert len(res.synthesized_lines) == 1
    line = res.synthesized_lines[0]
    assert line.linetype == LinetypeKind.DASHED
    assert line.stroke_count == 12


def test_control_03_positive_steep_inclined_60deg_dashed_line():
    """Control 3 (Positive): 60° inclined line (dx = 2.0, dy = 3.464 for 4mm dash)."""
    # 60°: cos(60°) = 0.5, sin(60°) = 0.866025
    c60 = 0.5
    s60 = math.sqrt(3.0) / 2.0
    dash_len = 4.0
    gap_len = 2.0
    strokes = []
    curr_t = 10.0
    for i in range(5):
        x0 = curr_t * c60
        y0 = curr_t * s60
        curr_t += dash_len
        x1 = curr_t * c60
        y1 = curr_t * s60
        strokes.append(_make_line(f"inc60_{i}", x0, y0, x1, y1))
        curr_t += gap_len

    res = extract_linetypes_strategy_d(strokes)
    assert len(res.synthesized_lines) == 1
    line = res.synthesized_lines[0]
    assert line.linetype == LinetypeKind.DASHED
    assert line.stroke_count == 5


def test_control_04_negative_solid_continuous_line_not_split():
    """Control 4 (Negative): A single long solid line is NOT classified as dashed/center."""
    solid = _make_line("solid_1", 10.0, 50.0, 90.0, 50.0)
    res = extract_linetypes_strategy_d([solid])
    assert len(res.synthesized_lines) == 0
    assert "solid_1" in res.unmerged_primitives


def test_control_05_negative_isolated_stray_dashes_rejected():
    """Control 5 (Negative): 2 isolated dashes (< min_strokes_in_chain = 3) are rejected."""
    d1 = _make_line("d1", 10.0, 50.0, 14.0, 50.0)
    d2 = _make_line("d2", 16.0, 50.0, 20.0, 50.0)
    res = extract_linetypes_strategy_d([d1, d2])
    assert len(res.synthesized_lines) == 0
    assert set(res.unmerged_primitives) == {"d1", "d2"}


def test_control_06_negative_large_gap_unrelated_collinear_lines_not_bridged():
    """Control 6 (Negative): Collinear segments with gap 25mm (> max_gap_mm = 8.0) not bridged."""
    # Group 1: 3 dashes from x=10 to x=26
    g1 = [
        _make_line("g1_1", 10.0, 50.0, 14.0, 50.0),
        _make_line("g1_2", 16.0, 50.0, 20.0, 50.0),
        _make_line("g1_3", 22.0, 50.0, 26.0, 50.0),
    ]
    # Group 2: 3 dashes starting at x=55 (gap = 29mm)
    g2 = [
        _make_line("g2_1", 55.0, 50.0, 59.0, 50.0),
        _make_line("g2_2", 61.0, 50.0, 65.0, 50.0),
        _make_line("g2_3", 67.0, 50.0, 71.0, 50.0),
    ]
    res = extract_linetypes_strategy_d(g1 + g2)
    # Must emit 2 separate chains, NOT 1 bridged chain!
    assert len(res.synthesized_lines) == 2
    assert all(line.stroke_count == 3 for line in res.synthesized_lines)


def test_control_07_negative_parallel_cross_hatch_lines_rejected():
    """Control 7 (Negative): Parallel cross-hatch strokes (spacing 5mm, lateral offset)
    are not merged along their transverse direction."""
    hatch_strokes = []
    for i in range(5):
        # 45° hatch lines, spaced laterally along X
        x_base = 10.0 + i * 5.0
        hatch_strokes.append(_make_line(f"hatch_{i}", x_base, 10.0, x_base + 10.0, 20.0))

    res = extract_linetypes_strategy_d(hatch_strokes)
    # Each hatch line is an independent solid line, lateral dist = 3.53mm > lateral_tol_mm (0.8mm)
    assert len(res.synthesized_lines) == 0
    assert len(res.unmerged_primitives) == 5


def test_control_08_negative_collinear_dimension_chain_witnesses_preserved():
    """Control 8 (Negative): Vertical witness lines in a dimension chain (parallel, offset along X)
    do not get falsely collapsed into a dashed line."""
    witnesses = []
    for i in range(4):
        x = 20.0 + i * 15.0  # Spaced 15mm apart along X
        witnesses.append(_make_line(f"wit_{i}", x, 10.0, x, 30.0))

    res = extract_linetypes_strategy_d(witnesses)
    assert len(res.synthesized_lines) == 0
    assert len(res.unmerged_primitives) == 4
