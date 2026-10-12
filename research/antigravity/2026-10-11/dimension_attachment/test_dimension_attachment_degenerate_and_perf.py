"""test_dimension_attachment_degenerate_and_perf.py - Degenerate, Non-finite, and Latency Profiling.

Validates 7 edge cases:
1. Empty boxes and empty anchors handling (safe no-op, no exception).
2. Zero-length dimension line (dx=0, dy=0) safe handling (no ZeroDivisionError).
3. Single extension line (< 2 extension lines) safe handling.
4. Non-finite coordinates (NaN, Inf) in anchors and geometry (filtered out).
5. Extreme coordinates (10^6 px) numerical stability (no float overflow).
6. Collinear / degenerate extension lines.
7. Scalability and latency profiling (100 boxes DSU merge + 50 anchors matching < 25 ms).

Part of Antigravity Research: OFFLINE_DIMENSION_CLUSTER_TOPOLOGY_AND_ATTACHMENT_V1
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

from dimension_attachment_engine import (
    DimensionGeometryData,
    merge_boxes_strategy_d,
    outer_extension_points_strategy_d,
    point_to_segment_distance,
    resolve_dimension_cluster,
)


def test_edge_1_empty_inputs_safe_noop() -> None:
    """Empty boxes and empty anchors return clean empty results without error."""
    geom = DimensionGeometryData(dimension_line=None, extension_lines=())
    res = resolve_dimension_cluster([], geom, semantic_anchors=[], view_id="MAIN", strategy="D")
    assert res.cluster_boxes == []
    assert res.outer_endpoints == []
    assert res.candidates == []
    assert not res.attachment_resolved
    assert "no_attachment_candidates" in res.reasons


def test_edge_2_zero_length_dimension_line_no_zerodiv() -> None:
    """Zero-length dimension line ((100, 100), (100, 100)) does not crash with ZeroDivisionError."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 100.0), (100.0, 100.0)),
        extension_lines=(
            ((100.0, 100.0), (100.0, 150.0)),
            ((100.0, 100.0), (100.0, 150.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "A1", "type": "FEATURE", "view_id": "MAIN", "point_px": [100.0, 150.0], "confidence": 1.0},
        {"id": "A2", "type": "FEATURE", "view_id": "MAIN", "point_px": [200.0, 150.0], "confidence": 1.0},
    ]
    res = resolve_dimension_cluster([], geom, semantic_anchors=anchors, view_id="MAIN", strategy="D")
    assert not res.attachment_resolved
    assert res.best_attachment is None


def test_edge_3_single_extension_line_safe_return() -> None:
    """Fewer than 2 extension lines safely returns without candidates."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(((100.0, 50.0), (100.0, 120.0)),),  # Only 1 extension line
        confidence=1.0,
    )
    anchors = [
        {"id": "A1", "type": "FEATURE", "view_id": "MAIN", "point_px": [100.0, 120.0], "confidence": 1.0},
        {"id": "A2", "type": "FEATURE", "view_id": "MAIN", "point_px": [300.0, 120.0], "confidence": 1.0},
    ]
    res = resolve_dimension_cluster([], geom, semantic_anchors=anchors, view_id="MAIN", strategy="D")
    assert not res.attachment_resolved
    assert res.candidates == []


def test_edge_4_non_finite_coordinates_filtered() -> None:
    """Anchors containing NaN or Inf coordinates are safely filtered out."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(
            ((100.0, 50.0), (100.0, 120.0)),
            ((300.0, 50.0), (300.0, 120.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "NAN_ANCHOR", "type": "FEATURE", "view_id": "MAIN", "point_px": [float("nan"), 120.0], "confidence": 1.0},
        {"id": "INF_ANCHOR", "type": "FEATURE", "view_id": "MAIN", "point_px": [100.0, float("inf")], "confidence": 1.0},
        {"id": "VALID_A", "type": "FEATURE", "view_id": "MAIN", "point_px": [100.0, 120.0], "confidence": 1.0},
        {"id": "VALID_B", "type": "FEATURE", "view_id": "MAIN", "point_px": [300.0, 120.0], "confidence": 1.0},
    ]
    res = resolve_dimension_cluster([], geom, semantic_anchors=anchors, view_id="MAIN", strategy="D")
    assert res.attachment_resolved
    assert res.best_attachment is not None
    assert res.best_attachment.from_ref["id"] == "VALID_A"
    assert res.best_attachment.to_ref["id"] == "VALID_B"


def test_edge_5_extreme_coordinates_numerical_stability() -> None:
    """Coordinates at 10^6 px scale operate without overflow or precision collapse."""
    offset = 1_000_000.0
    geom = DimensionGeometryData(
        dimension_line=((offset + 100.0, offset + 50.0), (offset + 300.0, offset + 50.0)),
        extension_lines=(
            ((offset + 100.0, offset + 50.0), (offset + 100.0, offset + 120.0)),
            ((offset + 300.0, offset + 50.0), (offset + 300.0, offset + 120.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "BIG_A", "type": "FEATURE", "view_id": "MAIN", "point_px": [offset + 100.0, offset + 125.0], "confidence": 1.0},
        {"id": "BIG_B", "type": "FEATURE", "view_id": "MAIN", "point_px": [offset + 300.0, offset + 125.0], "confidence": 1.0},
    ]
    res = resolve_dimension_cluster([], geom, semantic_anchors=anchors, view_id="MAIN", strategy="D")
    assert res.attachment_resolved
    assert res.best_attachment is not None
    assert res.best_attachment.from_ref["id"] == "BIG_A"
    assert res.best_attachment.to_ref["id"] == "BIG_B"
    assert math.isfinite(res.best_attachment.confidence)


def test_edge_6_collinear_extension_lines_safe_selection() -> None:
    """Extension lines that lie along the dimension line segment evaluate safely."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(
            ((50.0, 50.0), (100.0, 50.0)),
            ((300.0, 50.0), (350.0, 50.0)),
        ),
        confidence=1.0,
    )
    pts = outer_extension_points_strategy_d(geom)
    assert len(pts) == 2
    # Both points have valid Euclidean coordinates
    assert all(math.isfinite(p[0]) and math.isfinite(p[1]) for p in pts)


def test_perf_7_scalability_and_latency() -> None:
    """100 cluster boxes transitive merging and 50 semantic anchors matching executes in < 25 ms."""
    # Create a chain of 100 overlapping boxes
    boxes = [(i * 5, 10, i * 5 + 12, 30) for i in range(100)]
    # Create 50 semantic anchors along a line spaced by 50px
    anchors = [
        {"id": f"ANCHOR_{i}", "type": "FEATURE", "view_id": "MAIN", "point_px": [float(i * 50), 120.0], "confidence": 0.9}
        for i in range(50)
    ]
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(
            ((100.0, 50.0), (100.0, 115.0)),
            ((300.0, 50.0), (300.0, 115.0)),
        ),
        confidence=1.0,
    )

    t0 = time.perf_counter()
    res = resolve_dimension_cluster(boxes, geom, semantic_anchors=anchors, view_id="MAIN", strategy="D")
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000.0

    assert len(res.cluster_boxes) == 1
    assert res.attachment_resolved
    assert res.best_attachment is not None
    assert res.best_attachment.from_ref["id"] == "ANCHOR_2"
    assert res.best_attachment.to_ref["id"] == "ANCHOR_6"
    assert latency_ms < 25.0, f"Latency was {latency_ms:.2f} ms (expected < 25 ms)"
