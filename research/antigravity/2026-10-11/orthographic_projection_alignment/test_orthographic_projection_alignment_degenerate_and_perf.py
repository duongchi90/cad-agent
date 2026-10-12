"""test_orthographic_projection_alignment_degenerate_and_perf.py — Degenerate cases and performance stress suite."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

import pytest

from orthographic_projection_alignment_engine import (
    AlignmentLink,
    OrthographicAlignmentEngine,
    ViewPrimitive,
    ViewRegion,
)


def test_degenerate_01_empty_views_list():
    """Degenerate 1: Empty input collection returns clean empty report."""
    engine = OrthographicAlignmentEngine()
    res = engine.analyze([])
    assert res["valid"] is True
    assert res["view_count"] == 0
    assert len(res["links"]) == 0
    assert res["inferred_projection_system"] == "INDETERMINATE"


def test_degenerate_02_zero_area_or_inverted_bbox():
    """Degenerate 2: Zero-area or inverted bounding boxes are safely filtered without zero division."""
    v_zero_w = ViewRegion("v1", "FRONT", (100.0, 100.0, 100.0, 200.0))  # xmax == xmin
    v_zero_h = ViewRegion("v2", "FRONT", (100.0, 100.0, 200.0, 100.0))  # ymax == ymin
    v_inverted = ViewRegion("v3", "FRONT", (200.0, 200.0, 100.0, 100.0))  # xmax < xmin
    v_valid = ViewRegion("v4", "FRONT", (100.0, 100.0, 200.0, 200.0))

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([v_zero_w, v_zero_h, v_inverted, v_valid])
    assert res["valid"] is True
    assert res["view_count"] == 1  # only v_valid retained


def test_degenerate_03_zero_or_negative_scale():
    """Degenerate 3: Non-positive scale values are filtered safely."""
    v_zero_scale = ViewRegion("v1", "FRONT", (100.0, 100.0, 200.0, 200.0), scale=0.0)
    v_neg_scale = ViewRegion("v2", "FRONT", (100.0, 100.0, 200.0, 200.0), scale=-1.5)
    v_valid = ViewRegion("v3", "FRONT", (100.0, 100.0, 200.0, 200.0), scale=1.0)

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([v_zero_scale, v_neg_scale, v_valid])
    assert res["valid"] is True
    assert res["view_count"] == 1


def test_degenerate_04_non_finite_coordinates_nan_inf():
    """Degenerate 4: NaN and Infinity coordinates are filtered without crashing."""
    v_nan = ViewRegion("v_nan", "FRONT", (float("nan"), 100.0, 200.0, 200.0))
    v_inf = ViewRegion("v_inf", "FRONT", (100.0, float("inf"), 200.0, 200.0))
    v_valid = ViewRegion("v_ok", "FRONT", (100.0, 100.0, 200.0, 200.0))

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([v_nan, v_inf, v_valid])
    assert res["valid"] is True
    assert res["view_count"] == 1


def test_degenerate_05_extreme_astronomical_coordinates():
    """Degenerate 5: Astronomical large coordinates (10^7 mm) process with full numeric stability."""
    offset = 10_000_000.0
    front = ViewRegion("f", "FRONT", (offset + 100.0, offset + 100.0, offset + 300.0, offset + 200.0))
    side = ViewRegion("s", "RIGHT_SIDE", (offset + 350.0, offset + 100.0, offset + 450.0, offset + 200.0))

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([front, side])
    assert res["valid"] is True
    h_links = [l for l in res["links"] if l.relation_type == "VIEWS_ALIGNED_HORIZONTALLY"]
    assert len(h_links) == 1
    assert h_links[0].diagnostics["relative_height_error"] == 0.0


def test_degenerate_06_micro_dimensions():
    """Degenerate 6: Micro-scale features (0.001 mm) do not cause division by zero or underflow errors."""
    front = ViewRegion("f", "FRONT", (0.001, 0.001, 0.003, 0.002))  # W=0.002, H=0.001
    side = ViewRegion("s", "RIGHT_SIDE", (0.005, 0.001, 0.006, 0.002))  # W=0.001, H=0.001

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([front, side])
    assert res["valid"] is True
    h_links = [l for l in res["links"] if l.relation_type == "VIEWS_ALIGNED_HORIZONTALLY"]
    assert len(h_links) == 1


def test_perf_07_large_scale_multi_view_throughput():
    """Performance Stress 7: 50 drawing views with 200 primitives process in < 30ms."""
    views = []
    # Generate 25 pairs of front-side views
    for i in range(25):
        y_base = i * 200.0
        prims_f = [
            ViewPrimitive(f"pf_{i}_1", "LINE", (100.0, y_base), (250.0, y_base)),
            ViewPrimitive(f"pf_{i}_2", "LINE", (100.0, y_base + 50.0), (250.0, y_base + 50.0)),
            ViewPrimitive(f"pf_{i}_3", "LINE", (100.0, y_base + 100.0), (250.0, y_base + 100.0)),
        ]
        vf = ViewRegion(f"front_{i}", "FRONT", (100.0, y_base, 250.0, y_base + 100.0), primitives=prims_f)

        prims_s = [
            ViewPrimitive(f"ps_{i}_1", "LINE", (300.0, y_base), (380.0, y_base)),
            ViewPrimitive(f"ps_{i}_2", "LINE", (300.0, y_base + 50.0), (380.0, y_base + 50.0)),
            ViewPrimitive(f"ps_{i}_3", "LINE", (300.0, y_base + 100.0), (380.0, y_base + 100.0)),
        ]
        vs = ViewRegion(f"side_{i}", "RIGHT_SIDE", (300.0, y_base, 380.0, y_base + 100.0), primitives=prims_s)
        views.extend([vf, vs])

    engine = OrthographicAlignmentEngine()

    start_time = time.perf_counter()
    res = engine.analyze(views)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    assert res["valid"] is True
    assert res["view_count"] == 50
    h_links = [l for l in res["links"] if l.relation_type == "VIEWS_ALIGNED_HORIZONTALLY"]
    assert len(h_links) >= 25
    # Latency budget: < 100 ms for 50 views (1,225 pairwise evaluations)
    assert elapsed_ms < 100.0, f"Analysis took {elapsed_ms:.2f} ms (budget: 100.0 ms)"
