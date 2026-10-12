"""test_dimension_attachment_controls.py - Positive Fixtures and Strong Negative Controls.

Validates 8 critical boundary controls:
1. CTRL-1: Positive - High-confidence unambiguous horizontal attachment.
2. CTRL-2: Positive - Orthogonal shaft diameter with outward normal witness lines.
3. CTRL-3: Negative - Cross-view contamination rejection (different view_id).
4. CTRL-4: Negative - Excessive drafting gap rejection (> 100px away).
5. CTRL-5: Control - Parallel distractor feature disambiguation (margin >= 0.10).
6. CTRL-6: Negative - Invalid / zero-confidence anchor rejection.
7. CTRL-7: Negative - Self-referential anchor pair rejection (from == to).
8. CTRL-8: Negative - Low-confidence geometry fail-closed rejection (< 0.70).

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
    resolve_dimension_cluster,
)


def test_ctrl_1_positive_unambiguous_attachment() -> None:
    """CTRL-1: Positive fixture with standard drafting gap resolves with high confidence."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(
            ((100.0, 30.0), (100.0, 135.0)),
            ((300.0, 30.0), (300.0, 135.0)),
        ),
        confidence=0.95,
    )
    anchors = [
        {"id": "BORE_L", "type": "CIRCLE_CENTER", "view_id": "MAIN", "point_px": [100.0, 150.0], "confidence": 1.0},
        {"id": "BORE_R", "type": "CIRCLE_CENTER", "view_id": "MAIN", "point_px": [300.0, 150.0], "confidence": 1.0},
    ]

    res = resolve_dimension_cluster(
        [], geom, semantic_anchors=anchors, view_id="MAIN", strategy="D", px_per_mm=11.81
    )
    assert res.attachment_resolved
    assert res.best_attachment is not None
    assert res.best_attachment.from_ref["id"] == "BORE_L"
    assert res.best_attachment.to_ref["id"] == "BORE_R"
    assert res.best_attachment.confidence >= 0.90


def test_ctrl_2_positive_vertical_shaft_diameter() -> None:
    """CTRL-2: Positive vertical shaft diameter with horizontal witness lines."""
    geom = DimensionGeometryData(
        dimension_line=((50.0, 100.0), (50.0, 250.0)),
        extension_lines=(
            ((35.0, 100.0), (120.0, 100.0)),
            ((35.0, 250.0), (120.0, 250.0)),
        ),
        confidence=0.92,
    )
    anchors = [
        {"id": "SHAFT_TOP", "type": "CYLINDER_SURFACE", "view_id": "SIDE", "point_px": [135.0, 100.0], "confidence": 0.95},
        {"id": "SHAFT_BOT", "type": "CYLINDER_SURFACE", "view_id": "SIDE", "point_px": [135.0, 250.0], "confidence": 0.95},
    ]

    res = resolve_dimension_cluster(
        [], geom, semantic_anchors=anchors, view_id="SIDE", strategy="D", px_per_mm=11.81
    )
    assert res.attachment_resolved
    assert res.best_attachment is not None
    assert res.best_attachment.from_ref["id"] == "SHAFT_TOP"
    assert res.best_attachment.to_ref["id"] == "SHAFT_BOT"
    assert res.best_attachment.confidence >= 0.85


def test_ctrl_3_negative_cross_view_contamination() -> None:
    """CTRL-3: Anchors from different views cannot resolve attachment."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(
            ((100.0, 50.0), (100.0, 135.0)),
            ((300.0, 50.0), (300.0, 135.0)),
        ),
        confidence=0.95,
    )
    anchors = [
        {"id": "BORE_L", "type": "CIRCLE_CENTER", "view_id": "FRONT", "point_px": [100.0, 140.0], "confidence": 1.0},
        {"id": "BORE_R", "type": "CIRCLE_CENTER", "view_id": "SECTION_A", "point_px": [300.0, 140.0], "confidence": 1.0},
    ]

    # Testing in view "FRONT": second anchor belongs to "SECTION_A"
    res = resolve_dimension_cluster(
        [], geom, semantic_anchors=anchors, view_id="FRONT", strategy="D", px_per_mm=11.81
    )
    # view_membership is 0.0, dropping score by 0.20 -> below 0.85 threshold!
    assert not res.attachment_resolved
    assert "attachment_confidence_below_threshold" in res.reasons


def test_ctrl_4_negative_excessive_gap_rejection() -> None:
    """CTRL-4: Workpiece datums located > 100px away from extension line ends are rejected."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(
            ((100.0, 50.0), (100.0, 100.0)),
            ((300.0, 50.0), (300.0, 100.0)),
        ),
        confidence=0.95,
    )
    anchors = [
        {"id": "FAR_A", "type": "FEATURE", "view_id": "MAIN", "point_px": [100.0, 220.0], "confidence": 1.0},  # 120px gap!
        {"id": "FAR_B", "type": "FEATURE", "view_id": "MAIN", "point_px": [300.0, 220.0], "confidence": 1.0},  # 120px gap!
    ]

    res = resolve_dimension_cluster(
        [], geom, semantic_anchors=anchors, view_id="MAIN", strategy="D", px_per_mm=11.81
    )
    assert not res.attachment_resolved
    assert res.best_attachment is not None
    assert res.best_attachment.confidence < 0.65
    assert "attachment_confidence_below_threshold" in res.reasons


def test_ctrl_5_parallel_distractor_disambiguation() -> None:
    """CTRL-5: True workpiece at 15px gap is preferred over parallel feature at 75px gap with margin >= 0.10."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(
            ((100.0, 50.0), (100.0, 120.0)),
            ((300.0, 50.0), (300.0, 120.0)),
        ),
        confidence=0.95,
    )
    anchors = [
        # True features (15px gap)
        {"id": "TRUE_A", "type": "DATUM", "view_id": "MAIN", "point_px": [100.0, 135.0], "confidence": 1.0},
        {"id": "TRUE_B", "type": "DATUM", "view_id": "MAIN", "point_px": [300.0, 135.0], "confidence": 1.0},
        # Distractor parallel features (75px gap)
        {"id": "DIST_A", "type": "DATUM", "view_id": "MAIN", "point_px": [100.0, 195.0], "confidence": 1.0},
        {"id": "DIST_B", "type": "DATUM", "view_id": "MAIN", "point_px": [300.0, 195.0], "confidence": 1.0},
    ]

    res = resolve_dimension_cluster(
        [], geom, semantic_anchors=anchors, view_id="MAIN", strategy="D", px_per_mm=11.81
    )
    assert res.attachment_resolved
    assert res.best_attachment is not None
    assert res.best_attachment.from_ref["id"] == "TRUE_A"
    assert res.best_attachment.to_ref["id"] == "TRUE_B"
    assert res.second_attachment is not None
    # Confidence separation margin must be >= 0.10
    margin = float(res.best_attachment.confidence) - float(res.second_attachment.confidence)
    assert margin >= 0.10


def test_ctrl_6_negative_zero_confidence_anchor_rejection() -> None:
    """CTRL-6: Anchors with confidence <= 0.0 or malformed structure are rejected."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(
            ((100.0, 50.0), (100.0, 120.0)),
            ((300.0, 50.0), (300.0, 120.0)),
        ),
        confidence=0.95,
    )
    anchors = [
        {"id": "ZERO_CONF", "type": "FEATURE", "view_id": "MAIN", "point_px": [100.0, 120.0], "confidence": 0.0},
        {"id": "CORRUPT_PT", "type": "FEATURE", "view_id": "MAIN", "point_px": "not_a_point", "confidence": 1.0},
        {"id": "VALID_ONLY", "type": "FEATURE", "view_id": "MAIN", "point_px": [300.0, 120.0], "confidence": 1.0},
    ]

    res = resolve_dimension_cluster(
        [], geom, semantic_anchors=anchors, view_id="MAIN", strategy="D", px_per_mm=11.81
    )
    # Only 1 valid anchor exists, cannot pair
    assert not res.attachment_resolved
    assert res.best_attachment is None
    assert "no_attachment_candidates" in res.reasons


def test_ctrl_7_negative_self_referential_anchor_rejection() -> None:
    """CTRL-7: Cannot attach both ends of a linear dimension to the same anchor entity."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(
            ((100.0, 50.0), (100.0, 120.0)),
            ((300.0, 50.0), (300.0, 120.0)),
        ),
        confidence=0.95,
    )
    anchors = [
        {"id": "SINGLE_DATUM", "type": "FEATURE", "view_id": "MAIN", "point_px": [100.0, 120.0], "confidence": 1.0},
    ]

    res = resolve_dimension_cluster(
        [], geom, semantic_anchors=anchors, view_id="MAIN", strategy="D", px_per_mm=11.81
    )
    assert not res.attachment_resolved
    assert res.best_attachment is None
    assert "no_attachment_candidates" in res.reasons


def test_ctrl_8_negative_low_confidence_geometry_gate() -> None:
    """CTRL-8: Dimension geometry with confidence < 0.70 fails closed even if anchor match is perfect."""
    geom = DimensionGeometryData(
        dimension_line=((100.0, 50.0), (300.0, 50.0)),
        extension_lines=(
            ((100.0, 50.0), (100.0, 120.0)),
            ((300.0, 50.0), (300.0, 120.0)),
        ),
        confidence=0.65,  # Below 0.70 threshold!
    )
    anchors = [
        {"id": "PERFECT_A", "type": "DATUM", "view_id": "MAIN", "point_px": [100.0, 120.0], "confidence": 1.0},
        {"id": "PERFECT_B", "type": "DATUM", "view_id": "MAIN", "point_px": [300.0, 120.0], "confidence": 1.0},
    ]

    res = resolve_dimension_cluster(
        [], geom, semantic_anchors=anchors, view_id="MAIN", strategy="D", px_per_mm=11.81
    )
    assert not res.attachment_resolved
    assert "geometry_confidence_below_threshold" in res.reasons
    assert "attachment_unresolved" in res.reasons
