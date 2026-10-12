"""
test_multileader_topology_degenerate_and_perf.py
Degenerate Edge Cases, Non-Finite Handling, and Performance Stress Benchmark Suite for Multileader Topology.
"""

from __future__ import annotations

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

from primitive_ir_lib.models import Point2D, Primitive, LineGeometry, CircleGeometry, TextData, Trace
from multileader_topology_engine import (
    extract_multileader_strategy_d,
)


def _make_text(id_: str, content: str, x: float, y: float) -> Primitive:
    finite = math.isfinite(x) and math.isfinite(y)
    bbox = (int(x), int(y), int(x + len(content) * 8), int(y + 12)) if finite else (0, 0, 10, 10)
    return Primitive(
        id=id_,
        type="text",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=bbox),
        text_data=TextData(content=content, position=Point2D(x, y), rotation_deg=0.0, height=3.5),
    )


def _make_circle(id_: str, cx: float, cy: float, r: float) -> Primitive:
    finite = math.isfinite(cx) and math.isfinite(cy) and math.isfinite(r)
    bbox = (int(cx - r), int(cy - r), int(cx + r), int(cy + r)) if finite else (0, 0, 10, 10)
    return Primitive(
        id=id_,
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=bbox),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
    )


def test_degenerate_01_empty_segments_list():
    """Edge 1: Empty input returns clean empty result without exception."""
    res = extract_multileader_strategy_d([], [], [])
    assert len(res.leaders) == 0
    assert len(res.unattached_segments) == 0


def test_degenerate_02_zero_length_segments():
    """Edge 2: Zero-length segments handled safely without ZeroDivisionError."""
    seg_zero = (Point2D(20.0, 20.0), Point2D(20.0, 20.0))
    res = extract_multileader_strategy_d([seg_zero], [], [])
    assert len(res.leaders) == 0


def test_degenerate_03_non_finite_coordinates_nan_inf():
    """Edge 3: Non-finite coordinates (NaN/Inf) raise ValueError safely to protect downstream solvers."""
    seg_nan = (Point2D(10.0, float("nan")), Point2D(40.0, 40.0))
    with pytest.raises(ValueError, match="non-finite coordinates"):
        extract_multileader_strategy_d([seg_nan], [], [])

    txt_inf = _make_text("txt_inf", "INF", float("inf"), 20.0)
    seg_valid = (Point2D(10.0, 10.0), Point2D(40.0, 40.0))
    with pytest.raises(ValueError, match="non-finite position"):
        extract_multileader_strategy_d([seg_valid], [txt_inf], [])


def test_degenerate_04_astronomical_coordinates():
    """Edge 4: Coordinates at astronomical scale (10^7 mm) processed without overflow."""
    base_x = 10_000_000.0
    base_y = 10_000_000.0
    ptr = (Point2D(base_x, base_y), Point2D(base_x + 30.0, base_y + 30.0))
    barb = (Point2D(base_x, base_y), Point2D(base_x + 4.0, base_y + 4.0))
    landing = (Point2D(base_x + 30.0, base_y + 30.0), Point2D(base_x + 60.0, base_y + 30.0))
    txt = _make_text("txt_astro", "ASTRO", base_x + 62.0, base_y + 31.0)
    c_target = _make_circle("hole_astro", base_x, base_y - 10.0, 10.0)

    res = extract_multileader_strategy_d([ptr, barb, landing], [txt], [c_target])
    assert len(res.leaders) == 1
    l = res.leaders[0]
    assert l.tip == Point2D(base_x, base_y)
    assert l.attached_feature_id == "hole_astro"


def test_degenerate_05_micro_scale_features():
    """Edge 5: Micro-scale features (0.1mm) with tuned tolerances detected reliably."""
    ptr = (Point2D(0.1, 0.1), Point2D(0.4, 0.4))
    barb = (Point2D(0.1, 0.1), Point2D(0.14, 0.14))
    landing = (Point2D(0.4, 0.4), Point2D(0.7, 0.4))
    txt = _make_text("txt_micro", "MICRO", 0.72, 0.41)
    c_micro = _make_circle("hole_micro", 0.1, 0.05, 0.05)

    res = extract_multileader_strategy_d(
        [ptr, barb, landing], [txt], [c_micro],
        snap_tol_mm=0.05, text_proximity_mm=0.15,
        min_pointer_len_mm=0.2, min_landing_len_mm=0.2,
        arrowhead_min_len_mm=0.02, arrowhead_max_len_mm=0.5,
    )
    assert len(res.leaders) == 1
    assert res.leaders[0].attached_feature_id == "hole_micro"


def test_degenerate_06_duplicate_coincident_segments():
    """Edge 6: Duplicate coincident segments deduplicated without emitting duplicate leaders."""
    ptr1 = (Point2D(10.0, 10.0), Point2D(40.0, 40.0))
    ptr2 = (Point2D(10.0, 10.0), Point2D(40.0, 40.0))  # duplicate of ptr1
    barb = (Point2D(10.0, 10.0), Point2D(14.0, 14.0))
    landing = (Point2D(40.0, 40.0), Point2D(70.0, 40.0))
    txt = _make_text("txt_dup", "DUP", 72.0, 41.0)

    res = extract_multileader_strategy_d([ptr1, ptr2, barb, landing], [txt], [])
    assert len(res.leaders) == 1
    assert len(res.unattached_segments) == 0


def test_perf_07_large_scale_multileader_throughput():
    """Edge 7 (Performance): 50 complete multileaders (150 segments + 50 text primitives) processed in < 100 ms."""
    all_segments = []
    all_texts = []
    all_circles = []

    for i in range(50):
        bx = i * 60.0
        by = (i % 5) * 100.0
        c = _make_circle(f"hole_{i}", bx, by - 10.0, 10.0)
        ptr = (Point2D(bx, by), Point2D(bx + 25.0, by + 25.0))
        barb = (Point2D(bx, by), Point2D(bx + 4.0, by + 4.0))
        landing = (Point2D(bx + 25.0, by + 25.0), Point2D(bx + 50.0, by + 25.0))
        t = _make_text(f"txt_{i}", f"CALLOUT_{i}", bx + 52.0, by + 26.0)

        all_circles.append(c)
        all_segments.extend([ptr, barb, landing])
        all_texts.append(t)

    t0 = time.perf_counter()
    res = extract_multileader_strategy_d(all_segments, all_texts, all_circles)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert len(res.leaders) == 50
    assert elapsed_ms < 100.0, f"Extraction took {elapsed_ms:.2f} ms (expected < 100 ms)"
