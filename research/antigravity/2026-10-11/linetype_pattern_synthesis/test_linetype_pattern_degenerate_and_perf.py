"""Degenerate cases, numerical safety, non-finite handling, and performance stress tests.

Tests:
1. Degenerate: Empty primitives list
2. Degenerate: Zero-length segments
3. Degenerate: Non-finite coordinates (NaN/Inf)
4. Degenerate: Astronomical coordinates (10^7 mm)
5. Degenerate: Micro-scale features (0.1mm dashes)
6. Degenerate: Duplicate coincident segments
7. Performance: 200 dash fragments throughput (< 100 ms)
"""

import math
import sys
import time
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


def test_degenerate_01_empty_primitives_list():
    """Edge 1: Empty input returns empty features gracefully."""
    res = extract_linetypes_strategy_d([])
    assert len(res.synthesized_lines) == 0
    assert len(res.unmerged_primitives) == 0


def test_degenerate_02_zero_length_segments():
    """Edge 2: Zero-length segments skipped cleanly without ZeroDivisionError."""
    z1 = _make_line("z1", 10.0, 10.0, 10.0, 10.0)
    z2 = _make_line("z2", 20.0, 20.0, 20.0, 20.0)
    res = extract_linetypes_strategy_d([z1, z2])
    assert len(res.synthesized_lines) == 0


def test_degenerate_03_non_finite_coordinates_nan_inf():
    """Edge 3: Segments with NaN / Inf coordinates handled without exception."""
    nan_l = _make_line("nan_l", float("nan"), 10.0, 20.0, 10.0)
    inf_l = _make_line("inf_l", 10.0, float("inf"), 20.0, 20.0)
    try:
        res = extract_linetypes_strategy_d([nan_l, inf_l])
        assert isinstance(res.synthesized_lines, list)
    except Exception as e:
        pytest.fail(f"Raised unexpected exception on non-finite coordinates: {e}")


def test_degenerate_04_astronomical_coordinates():
    """Edge 4: Geometry at astronomical coordinates (10^7 mm) processed without overflow."""
    base_x = 10_000_000.0
    base_y = 10_000_000.0
    strokes = []
    for i in range(5):
        x = base_x + i * 6.0
        strokes.append(_make_line(f"astro_{i}", x, base_y, x + 4.0, base_y))

    res = extract_linetypes_strategy_d(strokes)
    assert len(res.synthesized_lines) == 1
    line = res.synthesized_lines[0]
    assert line.linetype == LinetypeKind.DASHED
    assert line.start == Point2D(base_x, base_y)


def test_degenerate_05_micro_scale_features():
    """Edge 5: Micro-scale dash strokes (0.1mm dash, 0.05mm gap)."""
    strokes = []
    for i in range(6):
        x = 1.0 + i * 0.15
        strokes.append(_make_line(f"micro_{i}", x, 1.0, x + 0.1, 1.0))

    res = extract_linetypes_strategy_d(strokes, max_gap_mm=0.2, lateral_tol_mm=0.05)
    assert len(res.synthesized_lines) == 1
    assert res.synthesized_lines[0].linetype == LinetypeKind.DASHED


def test_degenerate_06_duplicate_coincident_segments():
    """Edge 6: Duplicate coincident segments do not emit duplicate linetype entities."""
    d1 = _make_line("d1", 10.0, 50.0, 14.0, 50.0)
    d2 = _make_line("d2", 10.0, 50.0, 14.0, 50.0)  # Duplicate of d1
    d3 = _make_line("d3", 16.0, 50.0, 20.0, 50.0)
    d4 = _make_line("d4", 22.0, 50.0, 26.0, 50.0)

    res = extract_linetypes_strategy_d([d1, d2, d3, d4])
    assert len(res.synthesized_lines) == 1


def test_perf_07_large_scale_stroke_throughput():
    """Edge 7 (Performance): 200 dash fragments (forming 20 lines) processed in < 100 ms."""
    all_strokes = []
    for line_idx in range(20):
        y = line_idx * 20.0
        # 10 dashes per line
        for dash_idx in range(10):
            x = dash_idx * 8.0
            all_strokes.append(_make_line(f"l_{line_idx}_d_{dash_idx}", x, y, x + 5.0, y))

    t0 = time.perf_counter()
    res = extract_linetypes_strategy_d(all_strokes)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert len(res.synthesized_lines) == 20
    assert elapsed_ms < 100.0, f"Extraction took {elapsed_ms:.2f} ms (budget < 100 ms)"
