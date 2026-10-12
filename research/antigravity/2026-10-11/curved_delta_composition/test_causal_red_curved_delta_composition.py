"""Public Causal RED test suite for Topic 29: SOURCE_FUSION_NATIVE_CURVED_DELTA_COMPOSITION_V1.

Reproduces 5 baseline failure modes on cad_agent/source_fusion_proposal.py:
1. Target document containing CircleGeometry crashes line delta composer with AttributeError
2. Target document containing ArcGeometry crashes line delta composer with AttributeError
3. Base native circle observations rejected by line-only parser (_native_lines)
4. Strategy B center-point only matching falsely pairs concentric circles of different radii
5. Strategy D Oracle resolves polymorphic curved deltas with exact residual metric
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from cad_agent.source_fusion_proposal import (
    _native_lines,
    compose_verified_native_line_delta,
)
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
    StrategyB_CenterPointOnlyMatching,
    StrategyD_UnifiedGeometricDeltaComposerOracle,
    compute_circle_pair_residual,
    compute_arc_pair_residual,
)


def _dummy_calib() -> Calibration:
    return Calibration(
        unit="mm",
        pixel_to_unit_scale=1.0,
        origin_px=(0.0, 0.0),
        method="manual_override",
        status="verified",
        source_sha256="c" * 64,
    )


def _identity_anchors() -> list[AnchorPair]:
    return [
        AnchorPair("a1", (0.0, 0.0), (0.0, 0.0), "DATUM", 1.0),
        AnchorPair("a2", (100.0, 0.0), (100.0, 0.0), "DATUM", 1.0),
    ]


def test_red_1_target_circle_crashes_production_composer():
    """RED 1: Passing a target document with CircleGeometry crashes baseline with AttributeError."""
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("test.pdf", 0, 1000, 800, "c" * 64),
        calibration=_dummy_calib(),
        primitives=[
            Primitive(
                id="c1",
                type="circle",
                source="geometry_external_ai",
                confidence=0.95,
                geometry=CircleGeometry(center=Point2D(100.0, 100.0), radius=20.0),
                trace=Trace(bbox_px=(80, 80, 120, 120)),
            )
        ],
    )

    base_obs = [
        {"observation_id": "b1", "start": [10.0, 10.0], "end": [50.0, 10.0]}
    ]

    # Baseline attempts to access primitive.geometry.start on CircleGeometry, causing AttributeError
    with pytest.raises((AttributeError, ValueError)):
        compose_verified_native_line_delta(
            base_native_line_observations=base_obs,
            verified_target_document=doc,
            verification_request={},
            verification_result={},
            source_render_bytes=b"fake",
            calibration=_dummy_calib(),
            base_coordinate_unit="mm",
            max_correspondence_residual=5.0,
            keep_tolerance=1.0,
            target_to_base_alignment_anchors=_identity_anchors(),
            max_alignment_residual=2.0,
        )


def test_red_2_target_arc_crashes_production_composer():
    """RED 2: Passing a target document with ArcGeometry crashes baseline with AttributeError."""
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("test.pdf", 0, 1000, 800, "c" * 64),
        calibration=_dummy_calib(),
        primitives=[
            Primitive(
                id="a1",
                type="arc",
                source="geometry_external_ai",
                confidence=0.92,
                geometry=ArcGeometry(center=Point2D(200.0, 200.0), radius=15.0, start_angle_deg=0.0, end_angle_deg=90.0),
                trace=Trace(bbox_px=(185, 185, 215, 215)),
            )
        ],
    )

    base_obs = [
        {"observation_id": "b1", "start": [10.0, 10.0], "end": [50.0, 10.0]}
    ]

    with pytest.raises((AttributeError, ValueError)):
        compose_verified_native_line_delta(
            base_native_line_observations=base_obs,
            verified_target_document=doc,
            verification_request={},
            verification_result={},
            source_render_bytes=b"fake",
            calibration=_dummy_calib(),
            base_coordinate_unit="mm",
            max_correspondence_residual=5.0,
            keep_tolerance=1.0,
            target_to_base_alignment_anchors=_identity_anchors(),
            max_alignment_residual=2.0,
        )


def test_red_3_base_native_circle_observations_rejected():
    """RED 3: Base native circle observations lacking start/end are rejected by _native_lines."""
    base_circle_obs = [
        {"observation_id": "c_base_1", "type": "circle", "center": [150.0, 150.0], "radius": 25.0}
    ]

    with pytest.raises(ValueError, match="NATIVE_LINE_OBSERVATION_INVALID"):
        _native_lines(base_circle_obs)


def test_red_4_strategy_b_false_pairing_on_concentric_circles():
    """RED 4: Strategy B (center-only) falsely pairs two concentric circles with different radii."""
    base_circles = [
        {"observation_id": "outer_flange", "type": "circle", "center": [200.0, 200.0], "radius": 100.0},
        {"observation_id": "inner_bore", "type": "circle", "center": [200.0, 200.0], "radius": 20.0},
    ]
    # Target only contains the inner bore
    target_circles = [
        {"primitive_id": "t_bore", "type": "circle", "center": [200.0, 200.0], "radius": 20.0}
    ]

    # Strategy B only checks center distance: distance is 0.0 for BOTH outer_flange and inner_bore!
    # Because outer_flange appears first, Strategy B greedily matches t_bore to outer_flange!
    res_b = StrategyB_CenterPointOnlyMatching.compose_delta(
        base_observations=base_circles,
        target_primitives=target_circles,
        max_residual=5.0,
        keep_tolerance=1.0,
    )

    matched_base = res_b["matches"][0]["base_id"]
    # Strategy B makes a false pairing: matches 20mm bore to 100mm flange because centers coincide!
    assert matched_base == "outer_flange"

    # In contrast, true residual between 100mm flange and 20mm bore is 80mm:
    flange_residual = compute_circle_pair_residual(base_circles[0], target_circles[0])
    bore_residual = compute_circle_pair_residual(base_circles[1], target_circles[0])
    assert flange_residual == 80.0
    assert bore_residual == 0.0


def test_red_5_strategy_d_resolves_curved_deltas_correctly():
    """RED 5: Strategy D correctly distinguishes KEEP, MUTATE, and ADD on circles and arcs."""
    calib = _dummy_calib()
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("test.pdf", 0, 1000, 800, "c" * 64),
        calibration=calib,
        primitives=[
            # Circle 1: Unchanged (center (100, 100), r=20) -> KEEP
            Primitive(
                id="t_c1",
                type="circle",
                source="geometry_external_ai",
                confidence=0.98,
                geometry=CircleGeometry(center=Point2D(100.0, 100.0), radius=20.0),
                trace=Trace(bbox_px=(80, 80, 120, 120)),
            ),
            # Circle 2: Enlarged bore (center (300, 300), r=25 vs base r=20) -> MUTATE
            Primitive(
                id="t_c2",
                type="circle",
                source="geometry_external_ai",
                confidence=0.97,
                geometry=CircleGeometry(center=Point2D(300.0, 300.0), radius=25.0),
                trace=Trace(bbox_px=(275, 275, 325, 325)),
            ),
            # Circle 3: New hole (center (500, 500), r=15) -> ADD
            Primitive(
                id="t_c3",
                type="circle",
                source="geometry_external_ai",
                confidence=0.95,
                geometry=CircleGeometry(center=Point2D(500.0, 500.0), radius=15.0),
                trace=Trace(bbox_px=(485, 485, 515, 515)),
            ),
        ],
    )

    base_obs = [
        {"observation_id": "b_c1", "type": "circle", "center": [100.0, 100.0], "radius": 20.0},
        {"observation_id": "b_c2", "type": "circle", "center": [300.0, 300.0], "radius": 20.0},
    ]

    res_d = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_obs,
        verified_target_document=doc,
        alignment_anchors=_identity_anchors(),
        max_correspondence_residual=10.0,
        keep_tolerance=0.5,
    )

    assert res_d["status"] == "DELTA_COMPOSED"
    corr = res_d["correspondence"]
    assert len(corr) == 2
    # c1 is KEEP
    item_c1 = next(item for item in corr if item["base_observation_id"] == "b_c1")
    assert item_c1["action"] == "KEEP"
    assert item_c1["residual"] == 0.0

    # c2 is MUTATE
    item_c2 = next(item for item in corr if item["base_observation_id"] == "b_c2")
    assert item_c2["action"] == "MUTATE"
    assert item_c2["residual"] == pytest.approx(5.0)

    # Deltas should contain the MUTATE and the ADD
    deltas = res_d["deltas"]
    assert len(deltas) == 2
    mutate_delta = next(d for d in deltas if d["action"] == "MUTATE")
    assert mutate_delta["base_observation_id"] == "b_c2"
    assert mutate_delta["before"]["radius"] == 20.0
    assert mutate_delta["after"]["radius"] == 25.0

    add_delta = next(d for d in deltas if d["action"] == "ADD")
    assert add_delta["target_primitive_id"] == "t_c3"
    assert add_delta["geometry"]["radius"] == 15.0
