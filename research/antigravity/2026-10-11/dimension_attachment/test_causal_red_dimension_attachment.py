"""test_causal_red_dimension_attachment.py - Public Causal RED for Dimension Attachment and Clustering.

Reproduces 5 baseline failure modes on production primitive_ir_lib/dimension_observer.py:
1. RED-1: Vertical dimension line overshoot false selection (measures to line[0], picking overshoot into space).
2. RED-2: Standard 300 DPI drafting gap rejection (fixed 20px exponential decay causes false UNRESOLVED).
3. RED-3: Transitive 3-box clustering failure (single-pass greedy breaks, leaving overlapping boxes).
4. RED-4: Non-zero crop offset coordinate mismatch (crop-local extension points vs global anchors).
5. RED-5: Inverted anchor pair topological ordering acceptance.

Part of Antigravity Research: OFFLINE_DIMENSION_CLUSTER_TOPOLOGY_AND_ATTACHMENT_V1
"""

from __future__ import annotations

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

from dimension_attachment_engine import (
    DimensionGeometryData,
    merge_boxes_strategy_a,
    merge_boxes_strategy_d,
    outer_extension_points_strategy_a,
    outer_extension_points_strategy_d,
    resolve_dimension_cluster,
)


def test_red_1_slanted_extension_overshoot_selects_wrong_endpoint() -> None:
    """RED-1: Measuring distance to line[0] causes slight raster slant in far extension to pick overshoot.

    Dimension line: (80, 35) to (340, 35).
    Extension 0 at x=80: (80, 15) [overshoot] to (80, 100) [workpiece].
    Extension 1 at x=340: (348, 20) [overshoot] to (338, 100) [workpiece].

    Distance to line[0]=(80, 35):
    - Extension 1 overshoot (348, 20): hypot(348 - 80, 20 - 35) = hypot(268, -15) = 268.42 px
    - Extension 1 workpiece (338, 100): hypot(338 - 80, 100 - 35) = hypot(258, 65) = 266.06 px

    Production Strategy A picks (348, 20) because 268.42 > 266.06!
    """
    geometry = DimensionGeometryData(
        dimension_line=((80.0, 35.0), (340.0, 35.0)),
        extension_lines=(
            ((80.0, 15.0), (80.0, 100.0)),
            ((348.0, 20.0), (338.0, 100.0)),
        ),
        confidence=1.0,
    )

    # Strategy A (production main)
    pts_a = outer_extension_points_strategy_a(geometry)
    assert len(pts_a) == 2
    assert pts_a[0] == (80.0, 100.0)
    # Extension 1: FAILS in Strategy A by picking overshoot (348, 20) instead of workpiece (338, 100)!
    assert pts_a[1] == (348.0, 20.0)

    # Strategy D (reference oracle)
    pts_d = outer_extension_points_strategy_d(geometry)
    assert len(pts_d) == 2
    assert pts_d[0] == (80.0, 100.0)
    # Strategy D correctly picks the workpiece attachment point
    assert pts_d[1] == (338.0, 100.0)


def test_red_2_standard_300dpi_drafting_gap_falsely_unresolved() -> None:
    """RED-2: Legitimate 1.5mm (18px at 300 DPI) drafting gap drops confidence below 0.85 in Strategy A.

    Extension lines end 18px away from workpiece datums.
    Strategy A: proximity = exp(-(18 + 18) / 20.0) = exp(-1.8) ≈ 0.165
    Score = 0.45 * 0.165 + 0.25 + 0.20 + 0.10 = 0.624 < 0.85 -> UNRESOLVED!
    """
    # Horizontal dimension from x=80 to x=340 at y=35. Workpiece at y=115.
    # Extension lines start at y=15 (overshoot) and stop at y=97 (leaving 18px gap to y=115).
    geometry = DimensionGeometryData(
        dimension_line=((80.0, 35.0), (340.0, 35.0)),
        extension_lines=(
            ((80.0, 15.0), (80.0, 97.0)),
            ((340.0, 15.0), (340.0, 97.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "FRONT", "point_px": [80.0, 115.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "FRONT", "point_px": [340.0, 115.0], "confidence": 1.0},
    ]

    res_a = resolve_dimension_cluster([], geometry, semantic_anchors=anchors, view_id="FRONT", strategy="A")
    # Strategy A fails to resolve valid attachment
    assert not res_a.attachment_resolved
    assert res_a.best_attachment is not None
    assert res_a.best_attachment.confidence < 0.85
    assert "attachment_confidence_below_threshold" in res_a.reasons

    # Strategy D succeeds because drafting gap is within tolerance
    res_d = resolve_dimension_cluster(
        [], geometry, semantic_anchors=anchors, view_id="FRONT", strategy="D", px_per_mm=11.81
    )
    assert res_d.attachment_resolved
    assert res_d.best_attachment is not None
    assert res_d.best_attachment.confidence >= 0.85
    assert res_d.best_attachment.from_ref["id"] == "DATUM_A"
    assert res_d.best_attachment.to_ref["id"] == "DATUM_B"


def test_red_3_transitive_clustering_failure_leaves_overlapping_boxes() -> None:
    """RED-3: Single-pass _merge_boxes breaks on first match, failing transitive closure.

    Box 1: (10, 10, 30, 30)
    Box 2: (50, 10, 70, 30) (gap to Box 1 is 20px > 8px margin)
    Box 3: (25, 15, 55, 35) (y0=15 causes it to sort after Box 1 and 2; bridges both)
    """
    boxes = [
        (10, 10, 30, 30),
        (50, 10, 70, 30),
        (25, 15, 55, 35),
    ]

    merged_a = merge_boxes_strategy_a(boxes)
    # Strategy A fails transitive closure: leaves 2 overlapping boxes!
    assert len(merged_a) == 2
    assert merged_a == [(10, 10, 55, 35), (50, 10, 70, 30)]
    b1, b2 = merged_a
    # These two boxes clearly overlap horizontally (55 > 50 - 8)
    overlaps = not (b1[2] < b2[0] - 8 or b1[0] > b2[2] + 8 or b1[3] < b2[1] - 8 or b1[1] > b2[3] + 8)
    assert overlaps, "Strategy A leaves overlapping unmerged boxes"

    merged_d = merge_boxes_strategy_d(boxes, margin_px=8)
    # Strategy D correctly merges all 3 into 1 connected component
    assert len(merged_d) == 1
    assert merged_d[0] == (10, 10, 70, 35)


def test_red_4_crop_offset_mismatch_destroys_attachment_confidence() -> None:
    """RED-4: Cluster located at non-zero page coordinates fails in Strategy A due to crop coordinate mismatch.

    Crop offset is (200, 300).
    Geometry local coords: line at (80, 35) to (340, 35).
    Global anchors: at (280, 335) and (540, 335).
    """
    geometry = DimensionGeometryData(
        dimension_line=((80.0, 35.0), (340.0, 35.0)),
        extension_lines=(
            ((80.0, 35.0), (80.0, 115.0)),
            ((340.0, 35.0), (340.0, 115.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "FRONT", "point_px": [280.0, 415.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "FRONT", "point_px": [540.0, 415.0], "confidence": 1.0},
    ]

    res_a = resolve_dimension_cluster(
        [], geometry, semantic_anchors=anchors, view_id="FRONT", strategy="A", crop_offset_px=(200.0, 300.0)
    )
    # Strategy A ignores crop offset, yielding distance > 200px and near-zero proximity
    assert not res_a.attachment_resolved
    assert res_a.best_attachment is None or res_a.best_attachment.confidence < 0.60

    res_d = resolve_dimension_cluster(
        [], geometry, semantic_anchors=anchors, view_id="FRONT", strategy="D", crop_offset_px=(200.0, 300.0)
    )
    # Strategy D translates crop offset and resolves attachment cleanly
    assert res_d.attachment_resolved
    assert res_d.best_attachment is not None
    assert res_d.best_attachment.confidence >= 0.85


def test_red_5_inverted_anchor_ordering_indistinguishable_in_strategy_a() -> None:
    """RED-5: Strategy A orientation compatibility uses abs(dot), accepting reversed anchor direction.

    Dimension line points from left to right (+x).
    Inverted candidate (DATUM_B -> DATUM_A) has identical orientation compatibility in Strategy A.
    Strategy D rejects inverted vector where dot product with line orientation is negative.
    """
    geometry = DimensionGeometryData(
        dimension_line=((80.0, 35.0), (340.0, 35.0)),
        extension_lines=(
            ((80.0, 35.0), (80.0, 115.0)),
            ((340.0, 35.0), (340.0, 115.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "FRONT", "point_px": [80.0, 115.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "FRONT", "point_px": [340.0, 115.0], "confidence": 1.0},
    ]

    res_a = resolve_dimension_cluster([], geometry, semantic_anchors=anchors, view_id="FRONT", strategy="A")
    # In Strategy A, the inverted candidate (B -> A) is kept with high orientation score
    inverted_a = [c for c in res_a.candidates if c.from_ref["id"] == "DATUM_B" and c.to_ref["id"] == "DATUM_A"]
    assert len(inverted_a) == 1
    assert inverted_a[0].orientation_compatibility == 1.0  # Falsely scored as perfectly compatible!

    res_d = resolve_dimension_cluster([], geometry, semantic_anchors=anchors, view_id="FRONT", strategy="D")
    # In Strategy D, inverted candidate is rejected (dot product < 0)
    inverted_d = [c for c in res_d.candidates if c.from_ref["id"] == "DATUM_B" and c.to_ref["id"] == "DATUM_A"]
    assert len(inverted_d) == 0
