"""Empirical Strategy Benchmark Suite comparing Strategies A-D across 8 linetype scenarios.

Scenarios:
1. Horizontal hidden line stroke synthesis (8 dashes -> 1 line)
2. Vertical hidden line stroke synthesis (8 dashes -> 1 line)
3. Horizontal centerline cadence recognition (long-short-long)
4. Vertical centerline cadence recognition
5. Inclined 45° centerline synthesis
6. Phantom line double-dash recognition (long-short-short-long)
7. Adjacent parallel dashed lines disambiguation
8. Noisy dash length and gap jitter tolerance
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
    synthesize_linetypes_strategy_a,
    synthesize_linetypes_strategy_b,
    synthesize_linetypes_strategy_c,
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


def test_benchmark_scenario_01_horizontal_hidden_line_stroke_synthesis():
    """Scenario 1: Horizontal hidden line composed of 8 uniform dashes (4mm dash, 2mm gap)."""
    strokes = []
    for i in range(8):
        x = 10.0 + i * 6.0
        strokes.append(_make_line(f"h_{i}", x, 40.0, x + 4.0, 40.0))

    res_d = extract_linetypes_strategy_d(strokes)
    assert len(res_d.synthesized_lines) == 1
    line = res_d.features = res_d.synthesized_lines[0]
    assert line.linetype == LinetypeKind.DASHED
    assert line.stroke_count == 8
    assert line.start == Point2D(10.0, 40.0)
    assert line.end == Point2D(56.0, 40.0)
    assert abs(line.total_length_mm - 46.0) <= 0.1


def test_benchmark_scenario_02_vertical_hidden_line_synthesis():
    """Scenario 2: Vertical hidden line composed of 8 uniform dashes (4mm dash, 2mm gap)."""
    strokes = []
    for i in range(8):
        y = 20.0 + i * 6.0
        strokes.append(_make_line(f"v_{i}", 80.0, y, 80.0, y + 4.0))

    # Strat A drops vertical lines
    res_a = synthesize_linetypes_strategy_a(strokes)
    assert len(res_a.synthesized_lines) == 0

    # Strat D recovers vertical hidden line
    res_d = extract_linetypes_strategy_d(strokes)
    assert len(res_d.synthesized_lines) == 1
    line = res_d.synthesized_lines[0]
    assert line.linetype == LinetypeKind.DASHED
    assert line.stroke_count == 8
    assert line.start == Point2D(80.0, 20.0)
    assert line.end == Point2D(80.0, 66.0)


def test_benchmark_scenario_03_horizontal_centerline_cadence_recognition():
    """Scenario 3: Horizontal centerline with rhythmic cadence: long (12mm), gap (2mm), short (2.5mm), gap (2mm)..."""
    pattern = [12.0, 2.5, 12.0, 2.5, 12.0]
    gap = 2.0
    strokes = []
    curr_x = 10.0
    for i, length in enumerate(pattern):
        strokes.append(_make_line(f"c_h_{i}", curr_x, 50.0, curr_x + length, 50.0))
        curr_x += length + gap

    res_d = extract_linetypes_strategy_d(strokes)
    assert len(res_d.synthesized_lines) == 1
    line = res_d.synthesized_lines[0]
    assert line.linetype == LinetypeKind.CENTER
    assert line.stroke_count == 5
    assert line.cadence_ratio >= 3.0


def test_benchmark_scenario_04_vertical_centerline_cadence_recognition():
    """Scenario 4: Vertical centerline with rhythmic cadence: long (12mm), short (2.5mm)... along x = 120.0."""
    pattern = [12.0, 2.5, 12.0, 2.5, 12.0]
    gap = 2.0
    strokes = []
    curr_y = 15.0
    for i, length in enumerate(pattern):
        strokes.append(_make_line(f"c_v_{i}", 120.0, curr_y, 120.0, curr_y + length))
        curr_y += length + gap

    res_d = extract_linetypes_strategy_d(strokes)
    assert len(res_d.synthesized_lines) == 1
    line = res_d.synthesized_lines[0]
    assert line.linetype == LinetypeKind.CENTER
    assert line.stroke_count == 5


def test_benchmark_scenario_05_inclined_45deg_centerline_synthesis():
    """Scenario 5: 45° inclined centerline along y = x."""
    # Unit step dx = dy = length / sqrt(2)
    s2 = math.sqrt(2.0)
    pattern = [12.0, 2.5, 12.0, 2.5, 12.0]
    gap = 2.0
    strokes = []
    curr_t = 10.0
    for i, length in enumerate(pattern):
        x0 = curr_t / s2
        y0 = curr_t / s2
        curr_t += length
        x1 = curr_t / s2
        y1 = curr_t / s2
        strokes.append(_make_line(f"c_inc_{i}", x0, y0, x1, y1))
        curr_t += gap

    res_d = extract_linetypes_strategy_d(strokes)
    assert len(res_d.synthesized_lines) == 1
    line = res_d.synthesized_lines[0]
    assert line.linetype == LinetypeKind.CENTER
    assert line.stroke_count == 5


def test_benchmark_scenario_06_phantom_line_double_dash_recognition():
    """Scenario 6: Phantom line with double-short dash: long (14mm), short (2mm), short (2mm), long (14mm)."""
    pattern = [14.0, 2.0, 2.0, 14.0, 2.0, 2.0, 14.0]
    gap = 1.5
    strokes = []
    curr_x = 10.0
    for i, length in enumerate(pattern):
        strokes.append(_make_line(f"ph_{i}", curr_x, 70.0, curr_x + length, 70.0))
        curr_x += length + gap

    res_d = extract_linetypes_strategy_d(strokes)
    assert len(res_d.synthesized_lines) == 1
    line = res_d.synthesized_lines[0]
    assert line.linetype == LinetypeKind.PHANTOM
    assert line.stroke_count == 7


def test_benchmark_scenario_07_adjacent_parallel_dashed_lines_disambiguation():
    """Scenario 7: Adjacent parallel dashed lines (y=30 and y=40) separated cleanly without crosstalk."""
    strokes = []
    for i in range(6):
        x = 10.0 + i * 8.0
        strokes.append(_make_line(f"line1_{i}", x, 30.0, x + 5.0, 30.0))
        strokes.append(_make_line(f"line2_{i}", x, 40.0, x + 5.0, 40.0))

    res_d = extract_linetypes_strategy_d(strokes)
    assert len(res_d.synthesized_lines) == 2
    ys = {round(line.start.y, 1) for line in res_d.synthesized_lines}
    assert ys == {30.0, 40.0}
    assert all(line.stroke_count == 6 for line in res_d.synthesized_lines)


def test_benchmark_scenario_08_noisy_dash_length_and_gap_jitter():
    """Scenario 8: Dashes with ±15% length and gap jitter remain robustly classified as DASHED."""
    # Jittered lengths around 4mm: [3.8, 4.3, 3.9, 4.2, 4.0, 3.7]
    jittered_lengths = [3.8, 4.3, 3.9, 4.2, 4.0, 3.7]
    jittered_gaps = [1.8, 2.2, 1.9, 2.1, 2.0]
    strokes = []
    curr_x = 10.0
    for i, length in enumerate(jittered_lengths):
        strokes.append(_make_line(f"jit_{i}", curr_x, 90.0, curr_x + length, 90.0))
        if i < len(jittered_gaps):
            curr_x += length + jittered_gaps[i]

    res_d = extract_linetypes_strategy_d(strokes)
    assert len(res_d.synthesized_lines) == 1
    line = res_d.synthesized_lines[0]
    assert line.linetype == LinetypeKind.DASHED
    assert line.stroke_count == 6
