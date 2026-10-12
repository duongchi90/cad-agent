"""Degenerate cases, numerical safety, non-finite handling, and performance stress tests.

Tests:
1. Degenerate: Empty primitives list
2. Degenerate: Zero-length segments and zero-radius circles
3. Degenerate: Non-finite coordinates (NaN/Inf)
4. Degenerate: Astronomical coordinates (10^7 mm)
5. Degenerate: Micro-scale features (0.2mm diameter)
6. Degenerate: Duplicate coincident primitives
7. Performance: 50 mechanical hole features throughput (< 100 ms)
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

from primitive_ir_lib.models import Point2D, CircleGeometry, LineGeometry, Primitive, Trace
from hole_feature_engine import (
    HoleType,
    HoleRepresentationKind,
    extract_holes_strategy_d,
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


def _make_circle(id_: str, cx: float, cy: float, r: float) -> Primitive:
    return Primitive(
        id=id_,
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(cx - r, cy - r, cx + r, cy + r)),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
    )


def test_degenerate_01_empty_primitives_list():
    """Edge 1: Empty input returns empty features gracefully."""
    res = extract_holes_strategy_d([])
    assert len(res.features) == 0
    assert len(res.unassociated_primitives) == 0


def test_degenerate_02_zero_length_segments_and_zero_radius():
    """Edge 2: Zero-length lines and zero-radius circles skipped without division error."""
    zero_line = _make_line("z_line", 10.0, 10.0, 10.0, 10.0)
    zero_circ = _make_circle("z_circ", 20.0, 20.0, 0.0)

    res = extract_holes_strategy_d([zero_line, zero_circ])
    # Zero radius circle is discarded or treated as 0-diameter, but no crash
    assert len(res.features) <= 1


def test_degenerate_03_non_finite_coordinates_nan_inf():
    """Edge 3: Primitives with NaN / Inf coordinates handled without exception."""
    nan_line = _make_line("nan_l", float("nan"), 10.0, 20.0, 10.0)
    inf_circ = _make_circle("inf_c", float("inf"), 20.0, 5.0)

    # Should not raise exception
    try:
        res = extract_holes_strategy_d([nan_line, inf_circ])
        assert isinstance(res.features, list)
    except Exception as e:
        pytest.fail(f"Raised unexpected exception on non-finite coordinates: {e}")


def test_degenerate_04_astronomical_coordinates():
    """Edge 4: Geometry at astronomical coordinates (10^7 mm) processed without overflow."""
    base_x = 10_000_000.0
    base_y = 10_000_000.0
    c_in = _make_circle("c_astro_in", base_x, base_y, 5.0)
    c_out = _make_circle("c_astro_out", base_x, base_y, 10.0)

    res = extract_holes_strategy_d([c_in, c_out])
    assert len(res.features) == 1
    f = res.features[0]
    assert f.hole_type == HoleType.COUNTERBORE
    assert f.axis_origin == Point2D(base_x, base_y)
    assert f.through_diameter_mm == 10.0


def test_degenerate_05_micro_scale_features():
    """Edge 5: Micro-scale hole features (0.2mm diameter) processed accurately."""
    c_micro = _make_circle("c_micro", 1.0, 1.0, 0.1)  # diam = 0.2mm

    res = extract_holes_strategy_d([c_micro])
    assert len(res.features) == 1
    assert res.features[0].through_diameter_mm == 0.2


def test_degenerate_06_duplicate_coincident_primitives():
    """Edge 6: Duplicate coincident circles deduplicated without duplicate hole emission."""
    c1 = _make_circle("c1", 50.0, 50.0, 6.0)
    c2 = _make_circle("c2", 50.0, 50.0, 6.0)  # Identical duplicate

    # Both are concentric circles with same radius: inner and outer are both 12mm
    res = extract_holes_strategy_d([c1, c2])
    # Deduplication or pairing into single cluster
    assert len(res.features) == 1


def test_perf_07_large_scale_hole_throughput():
    """Edge 7 (Performance): 50 mechanical holes (mix of plan counterbores and section profiles)
    processed in < 100 ms."""
    all_primitives = []

    # 25 plan counterbores
    for i in range(25):
        cx = i * 40.0
        cy = 50.0
        all_primitives.append(_make_circle(f"cb_in_{i}", cx, cy, 5.0))
        all_primitives.append(_make_circle(f"cb_out_{i}", cx, cy, 10.0))

    # 25 section simple holes (spaced along Y to represent distinct cavity locations)
    for i in range(25):
        base_x = i * 40.0
        base_y = 100.0 + i * 30.0
        all_primitives.append(_make_line(f"wt_{i}", base_x, base_y + 10.0, base_x + 20.0, base_y + 10.0))
        all_primitives.append(_make_line(f"wb_{i}", base_x, base_y, base_x + 20.0, base_y))

    t0 = time.perf_counter()
    res = extract_holes_strategy_d(all_primitives)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert len(res.features) >= 25
    assert elapsed_ms < 100.0, f"Extraction took {elapsed_ms:.2f} ms (budget < 100 ms)"
