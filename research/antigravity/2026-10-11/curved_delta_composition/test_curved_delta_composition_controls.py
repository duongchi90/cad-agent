"""Controls test suite for Topic 29: SOURCE_FUSION_NATIVE_CURVED_DELTA_COMPOSITION_V1.

Exercises positive controls, strict negative controls, and boundary controls:
1. Positive Control: Clean mixed model (Lines, Circles, Arcs) passes
2. Negative Control: Negative max_correspondence_residual raises GEOMETRY_TOLERANCE_INVALID
3. Negative Control: keep_tolerance > max_correspondence_residual raises GEOMETRY_TOLERANCE_INVALID
4. Negative Control: Empty target primitives list raises VERIFIED_TARGET_DOCUMENT_EMPTY
5. Negative Control: Invalid or unproven alignment anchors raises TARGET_BASE_ALIGNMENT_UNPROVEN
6. Boundary Control: Residual exactly equal to keep_tolerance is classified as KEEP
7. Boundary Control: Arc rotation transformation preserves angular sweep length
8. Boundary Control: Concentric circles radius difference boundary threshold
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

from primitive_ir_lib.geometry_alignment import AnchorPair
from primitive_ir_lib.models import (
    ArcGeometry,
    Calibration,
    CircleGeometry,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)
from curved_delta_composition_engine import (
    StrategyD_UnifiedGeometricDeltaComposerOracle,
    apply_alignment_to_target_arc,
)


def _calib() -> Calibration:
    return Calibration(
        unit="mm",
        pixel_to_unit_scale=1.0,
        origin_px=(0.0, 0.0),
        method="manual_override",
        status="verified",
        source_sha256="e" * 64,
    )


def _valid_anchors() -> list[AnchorPair]:
    return [
        AnchorPair("a1", (0.0, 0.0), (0.0, 0.0), "DATUM", 1.0),
        AnchorPair("a2", (100.0, 0.0), (100.0, 0.0), "DATUM", 1.0),
    ]


def test_control_1_positive_clean_mixed_model():
    """Control 1: Positive control for clean mixed model."""
    calib = _calib()
    base_obs = [
        {"observation_id": "b_line", "type": "line", "start": [0.0, 0.0], "end": [50.0, 0.0]},
        {"observation_id": "b_circ", "type": "circle", "center": [25.0, 25.0], "radius": 10.0},
        {"observation_id": "b_arc", "type": "arc", "center": [50.0, 50.0], "radius": 10.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0},
    ]

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("pos.pdf", 0, 1000, 800, "e" * 64),
        calibration=calib,
        primitives=[
            Primitive(id="t_l", type="line", source="geometry_external_ai", confidence=0.98, geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(50.0, 0.0)), trace=Trace(bbox_px=(0, 0, 50, 1))),
            Primitive(id="t_c", type="circle", source="geometry_external_ai", confidence=0.97, geometry=CircleGeometry(center=Point2D(25.0, 25.0), radius=10.0), trace=Trace(bbox_px=(15, 15, 35, 35))),
            Primitive(id="t_a", type="arc", source="geometry_external_ai", confidence=0.95, geometry=ArcGeometry(center=Point2D(50.0, 50.0), radius=10.0, start_angle_deg=0.0, end_angle_deg=90.0), trace=Trace(bbox_px=(50, 50, 60, 60))),
        ],
    )

    res = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_obs,
        verified_target_document=doc,
        alignment_anchors=_valid_anchors(),
        max_correspondence_residual=5.0,
        keep_tolerance=0.5,
    )
    assert res["status"] == "NO_DELTA_IDENTICAL"
    assert len(res["correspondence"]) == 3


def test_control_2_negative_invalid_tolerance():
    """Control 2: Negative control - negative max_residual raises GEOMETRY_TOLERANCE_INVALID."""
    calib = _calib()
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("pos.pdf", 0, 1000, 800, "e" * 64),
        calibration=calib,
        primitives=[
            Primitive(id="t_c", type="circle", source="geometry_external_ai", confidence=0.97, geometry=CircleGeometry(center=Point2D(25.0, 25.0), radius=10.0), trace=Trace(bbox_px=(15, 15, 35, 35))),
        ],
    )

    with pytest.raises(ValueError, match="GEOMETRY_TOLERANCE_INVALID"):
        StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
            base_observations=[],
            verified_target_document=doc,
            alignment_anchors=_valid_anchors(),
            max_correspondence_residual=-1.0,
            keep_tolerance=0.5,
        )


def test_control_3_negative_keep_tolerance_exceeds_max():
    """Control 3: Negative control - keep_tolerance > max_residual raises error."""
    calib = _calib()
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("pos.pdf", 0, 1000, 800, "e" * 64),
        calibration=calib,
        primitives=[
            Primitive(id="t_c", type="circle", source="geometry_external_ai", confidence=0.97, geometry=CircleGeometry(center=Point2D(25.0, 25.0), radius=10.0), trace=Trace(bbox_px=(15, 15, 35, 35))),
        ],
    )

    with pytest.raises(ValueError, match="GEOMETRY_TOLERANCE_INVALID"):
        StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
            base_observations=[],
            verified_target_document=doc,
            alignment_anchors=_valid_anchors(),
            max_correspondence_residual=2.0,
            keep_tolerance=5.0,  # keep > max
        )


def test_control_4_negative_empty_target_document():
    """Control 4: Negative control - empty target primitives raises VERIFIED_TARGET_DOCUMENT_EMPTY."""
    calib = _calib()
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("empty.pdf", 0, 1000, 800, "e" * 64),
        calibration=calib,
        primitives=[],
    )

    with pytest.raises(ValueError, match="VERIFIED_TARGET_DOCUMENT_EMPTY"):
        StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
            base_observations=[],
            verified_target_document=doc,
            alignment_anchors=_valid_anchors(),
            max_correspondence_residual=5.0,
            keep_tolerance=1.0,
        )


def test_control_5_negative_unproven_alignment_anchors():
    """Control 5: Negative control - distorted anchors raise TARGET_BASE_ALIGNMENT_UNPROVEN."""
    calib = _calib()
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("pos.pdf", 0, 1000, 800, "e" * 64),
        calibration=calib,
        primitives=[
            Primitive(id="t_c", type="circle", source="geometry_external_ai", confidence=0.97, geometry=CircleGeometry(center=Point2D(25.0, 25.0), radius=10.0), trace=Trace(bbox_px=(15, 15, 35, 35))),
        ],
    )
    # Scaled anchors (1:2 scale ratio violates 1:1 rigid requirement)
    bad_anchors = [
        AnchorPair("a1", (0.0, 0.0), (0.0, 0.0), "DATUM", 1.0),
        AnchorPair("a2", (100.0, 0.0), (200.0, 0.0), "DATUM", 1.0),
    ]

    with pytest.raises(ValueError, match="TARGET_BASE_ALIGNMENT_SCALE_UNPROVEN"):
        StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
            base_observations=[],
            verified_target_document=doc,
            alignment_anchors=bad_anchors,
            max_correspondence_residual=5.0,
            keep_tolerance=1.0,
        )


def test_control_6_boundary_residual_exactly_at_keep_tolerance():
    """Control 6: Boundary control - residual exactly equal to keep_tolerance is KEEP."""
    calib = _calib()
    base_obs = [
        {"observation_id": "b1", "type": "circle", "center": [100.0, 100.0], "radius": 20.0}
    ]
    # Center shifted by exactly 1.0 mm
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("bound.pdf", 0, 1000, 800, "e" * 64),
        calibration=calib,
        primitives=[
            Primitive(id="t1", type="circle", source="geometry_external_ai", confidence=0.98, geometry=CircleGeometry(center=Point2D(101.0, 100.0), radius=20.0), trace=Trace(bbox_px=(81, 80, 121, 120))),
        ],
    )

    res = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_obs,
        verified_target_document=doc,
        alignment_anchors=_valid_anchors(),
        max_correspondence_residual=5.0,
        keep_tolerance=1.0,  # residual == keep_tolerance
    )
    assert res["correspondence"][0]["action"] == "KEEP"
    assert len(res["deltas"]) == 0


def test_control_7_boundary_arc_rotation_preserves_sweep():
    """Control 7: Boundary control - Arc rotation preserves exact angular sweep length."""
    # 90 degree rotation matrix
    matrix = [
        [0.0, -1.0, 100.0],
        [1.0, 0.0, 50.0],
    ]
    arc = {
        "primitive_id": "a1",
        "center": [10.0, 20.0],
        "radius": 15.0,
        "start_angle_deg": 30.0,
        "end_angle_deg": 120.0,
    }
    aligned = apply_alignment_to_target_arc(arc, matrix)
    # Original sweep: 120 - 30 = 90 deg
    # Aligned angles should rotate by 90 deg: start 30+90=120, end 120+90=210
    assert aligned["start_angle_deg"] == pytest.approx(120.0)
    assert aligned["end_angle_deg"] == pytest.approx(210.0)
    sweep = (aligned["end_angle_deg"] - aligned["start_angle_deg"]) % 360.0
    assert sweep == pytest.approx(90.0)


def test_control_8_boundary_concentric_radius_step():
    """Control 8: Boundary control - Concentric circle radius difference at threshold."""
    calib = _calib()
    base_obs = [
        {"observation_id": "b_c", "type": "circle", "center": [50.0, 50.0], "radius": 20.0}
    ]
    # Radius enlarged by 2.001 mm with max_residual = 2.0 mm -> fails matching, emitted as ADD
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("step.pdf", 0, 1000, 800, "e" * 64),
        calibration=calib,
        primitives=[
            Primitive(id="t_c", type="circle", source="geometry_external_ai", confidence=0.98, geometry=CircleGeometry(center=Point2D(50.0, 50.0), radius=22.001), trace=Trace(bbox_px=(28, 28, 72, 72))),
        ],
    )

    res = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_obs,
        verified_target_document=doc,
        alignment_anchors=_valid_anchors(),
        max_correspondence_residual=2.0,
        keep_tolerance=0.5,
    )
    # Over threshold: target hole is considered an ADD, base hole is considered UNMATCHED
    assert len(res["correspondence"]) == 0
    assert "b_c" in res["unmatched_base_observation_ids"]
    assert any(d["action"] == "ADD" for d in res["deltas"])
