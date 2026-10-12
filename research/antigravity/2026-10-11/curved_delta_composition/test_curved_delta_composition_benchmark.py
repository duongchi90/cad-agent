"""Benchmark test suite for Topic 29: SOURCE_FUSION_NATIVE_CURVED_DELTA_COMPOSITION_V1.

Compares Strategies A-D across 8 distinct benchmark scenarios:
- Strategy A: Current Production Baseline (Line-only composer)
- Strategy B: Center-Point Only Matching (Disregards radius, fails on concentric features)
- Strategy C: Uncoupled Type Matchers (Independent matchers without cross-feature validation)
- Strategy D: Unified Polymorphic Geometric Delta Composer Oracle
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
    StrategyA_ProductionBaseline,
    StrategyB_CenterPointOnlyMatching,
    StrategyC_UncoupledTypeMatchers,
    StrategyD_UnifiedGeometricDeltaComposerOracle,
)


def _calib() -> Calibration:
    return Calibration(
        unit="mm",
        pixel_to_unit_scale=1.0,
        origin_px=(0.0, 0.0),
        method="manual_override",
        status="verified",
        source_sha256="d" * 64,
    )


def _anchors() -> list[AnchorPair]:
    return [
        AnchorPair("a1", (0.0, 0.0), (0.0, 0.0), "DATUM", 1.0),
        AnchorPair("a2", (200.0, 0.0), (200.0, 0.0), "DATUM", 1.0),
    ]


def test_scenario_1_identical_circles_keep():
    """Scenario 1: Identical base and target circles result in 100% KEEP and 0 residual."""
    calib = _calib()
    base_circles = [
        {"observation_id": "b_c1", "type": "circle", "center": [100.0, 100.0], "radius": 20.0},
        {"observation_id": "b_c2", "type": "circle", "center": [300.0, 100.0], "radius": 15.0},
    ]

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("ident.pdf", 0, 1000, 800, "d" * 64),
        calibration=calib,
        primitives=[
            Primitive(
                id="t_c1",
                type="circle",
                source="geometry_external_ai",
                confidence=0.98,
                geometry=CircleGeometry(center=Point2D(100.0, 100.0), radius=20.0),
                trace=Trace(bbox_px=(80, 80, 120, 120)),
            ),
            Primitive(
                id="t_c2",
                type="circle",
                source="geometry_external_ai",
                confidence=0.98,
                geometry=CircleGeometry(center=Point2D(300.0, 100.0), radius=15.0),
                trace=Trace(bbox_px=(285, 85, 315, 115)),
            ),
        ],
    )

    res_d = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_circles,
        verified_target_document=doc,
        alignment_anchors=_anchors(),
        max_correspondence_residual=5.0,
        keep_tolerance=0.5,
    )

    assert res_d["status"] == "NO_DELTA_IDENTICAL"
    assert len(res_d["correspondence"]) == 2
    assert all(c["action"] == "KEEP" for c in res_d["correspondence"])
    assert all(c["residual"] == 0.0 for c in res_d["correspondence"])
    assert len(res_d["deltas"]) == 0


def test_scenario_2_concentric_bore_radius_mutation():
    """Scenario 2: Concentric bore enlarged; outer flange preserved."""
    calib = _calib()
    base_circles = [
        {"observation_id": "flange_outer", "type": "circle", "center": [200.0, 200.0], "radius": 80.0},
        {"observation_id": "bore_inner", "type": "circle", "center": [200.0, 200.0], "radius": 25.0},
    ]

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("concentric.pdf", 0, 1000, 800, "d" * 64),
        calibration=calib,
        primitives=[
            # Outer flange remains 80 mm
            Primitive(
                id="t_flange",
                type="circle",
                source="geometry_external_ai",
                confidence=0.99,
                geometry=CircleGeometry(center=Point2D(200.0, 200.0), radius=80.0),
                trace=Trace(bbox_px=(120, 120, 280, 280)),
            ),
            # Inner bore enlarged from 25 mm to 30 mm (MUTATE by 5 mm)
            Primitive(
                id="t_bore",
                type="circle",
                source="geometry_external_ai",
                confidence=0.97,
                geometry=CircleGeometry(center=Point2D(200.0, 200.0), radius=30.0),
                trace=Trace(bbox_px=(170, 170, 230, 230)),
            ),
        ],
    )

    res_d = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_circles,
        verified_target_document=doc,
        alignment_anchors=_anchors(),
        max_correspondence_residual=10.0,
        keep_tolerance=1.0,
    )

    assert res_d["status"] == "DELTA_COMPOSED"
    corr = {c["base_observation_id"]: c for c in res_d["correspondence"]}
    assert corr["flange_outer"]["action"] == "KEEP"
    assert corr["flange_outer"]["residual"] == 0.0

    assert corr["bore_inner"]["action"] == "MUTATE"
    assert corr["bore_inner"]["residual"] == pytest.approx(5.0)

    deltas = res_d["deltas"]
    assert len(deltas) == 1
    assert deltas[0]["base_observation_id"] == "bore_inner"
    assert deltas[0]["before"]["radius"] == 25.0
    assert deltas[0]["after"]["radius"] == 30.0


def test_scenario_3_translated_hole_mutation():
    """Scenario 3: Hole shifted by dx=3.0 mm is detected as MUTATE with exact residual."""
    calib = _calib()
    base_circles = [
        {"observation_id": "hole_1", "type": "circle", "center": [100.0, 100.0], "radius": 10.0}
    ]

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("shift.pdf", 0, 1000, 800, "d" * 64),
        calibration=calib,
        primitives=[
            # Center shifted from (100, 100) to (103, 100)
            Primitive(
                id="t_hole_1",
                type="circle",
                source="geometry_external_ai",
                confidence=0.96,
                geometry=CircleGeometry(center=Point2D(103.0, 100.0), radius=10.0),
                trace=Trace(bbox_px=(93, 90, 113, 110)),
            )
        ],
    )

    res_d = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_circles,
        verified_target_document=doc,
        alignment_anchors=_anchors(),
        max_correspondence_residual=5.0,
        keep_tolerance=0.5,
    )

    assert res_d["status"] == "DELTA_COMPOSED"
    delta = res_d["deltas"][0]
    assert delta["action"] == "MUTATE"
    assert delta["residual"] == pytest.approx(3.0)
    assert delta["before"]["center"] == [100.0, 100.0]
    assert delta["after"]["center"] == [103.0, 100.0]


def test_scenario_4_added_hole_proposal():
    """Scenario 4: Target contains an additional hole not present in base."""
    calib = _calib()
    base_circles = [
        {"observation_id": "h1", "type": "circle", "center": [100.0, 100.0], "radius": 10.0}
    ]

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("add.pdf", 0, 1000, 800, "d" * 64),
        calibration=calib,
        primitives=[
            Primitive(
                id="t_h1",
                type="circle",
                source="geometry_external_ai",
                confidence=0.98,
                geometry=CircleGeometry(center=Point2D(100.0, 100.0), radius=10.0),
                trace=Trace(bbox_px=(90, 90, 110, 110)),
            ),
            # Newly added hole at (200, 100)
            Primitive(
                id="t_h2_new",
                type="circle",
                source="geometry_external_ai",
                confidence=0.95,
                geometry=CircleGeometry(center=Point2D(200.0, 100.0), radius=10.0),
                trace=Trace(bbox_px=(190, 90, 210, 110)),
            ),
        ],
    )

    res_d = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_circles,
        verified_target_document=doc,
        alignment_anchors=_anchors(),
        max_correspondence_residual=5.0,
        keep_tolerance=0.5,
    )

    assert res_d["status"] == "DELTA_COMPOSED"
    add_deltas = [d for d in res_d["deltas"] if d["action"] == "ADD"]
    assert len(add_deltas) == 1
    assert add_deltas[0]["target_primitive_id"] == "t_h2_new"
    assert add_deltas[0]["geometry"]["center"] == [200.0, 100.0]


def test_scenario_5_removed_hole_unmatched_base():
    """Scenario 5: Deleted hole in target emits an unmatched base observation."""
    calib = _calib()
    base_circles = [
        {"observation_id": "h_keep", "type": "circle", "center": [100.0, 100.0], "radius": 10.0},
        {"observation_id": "h_deleted", "type": "circle", "center": [250.0, 100.0], "radius": 10.0},
    ]

    # Target only contains h_keep
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("del.pdf", 0, 1000, 800, "d" * 64),
        calibration=calib,
        primitives=[
            Primitive(
                id="t_keep",
                type="circle",
                source="geometry_external_ai",
                confidence=0.98,
                geometry=CircleGeometry(center=Point2D(100.0, 100.0), radius=10.0),
                trace=Trace(bbox_px=(90, 90, 110, 110)),
            )
        ],
    )

    res_d = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_circles,
        verified_target_document=doc,
        alignment_anchors=_anchors(),
        max_correspondence_residual=5.0,
        keep_tolerance=0.5,
    )

    assert "h_deleted" in res_d["unmatched_base_observation_ids"]
    assert "h_keep" not in res_d["unmatched_base_observation_ids"]


def test_scenario_6_fillet_arc_radius_mutation():
    """Scenario 6: Corner fillet arc radius modified from R10 to R15."""
    calib = _calib()
    base_arcs = [
        {
            "observation_id": "fillet_corner",
            "type": "arc",
            "center": [50.0, 50.0],
            "radius": 10.0,
            "start_angle_deg": 0.0,
            "end_angle_deg": 90.0,
        }
    ]

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("fillet.pdf", 0, 1000, 800, "d" * 64),
        calibration=calib,
        primitives=[
            Primitive(
                id="t_fillet",
                type="arc",
                source="geometry_external_ai",
                confidence=0.93,
                geometry=ArcGeometry(center=Point2D(50.0, 50.0), radius=15.0, start_angle_deg=0.0, end_angle_deg=90.0),
                trace=Trace(bbox_px=(45, 45, 65, 65)),
            )
        ],
    )

    res_d = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_arcs,
        verified_target_document=doc,
        alignment_anchors=_anchors(),
        max_correspondence_residual=10.0,
        keep_tolerance=0.5,
    )

    assert res_d["status"] == "DELTA_COMPOSED"
    delta = res_d["deltas"][0]
    assert delta["action"] == "MUTATE"
    assert delta["residual"] == pytest.approx(5.0)
    assert delta["before"]["radius"] == 10.0
    assert delta["after"]["radius"] == 15.0


def test_scenario_7_full_mixed_mechanical_assembly():
    """Scenario 7: Mixed document with lines, circles, and fillet arcs matches polymorphically."""
    calib = _calib()
    base_prims = [
        {"observation_id": "line_1", "type": "line", "start": [0.0, 0.0], "end": [100.0, 0.0]},
        {"observation_id": "line_2", "type": "line", "start": [100.0, 0.0], "end": [100.0, 100.0]},
        {"observation_id": "hole_center", "type": "circle", "center": [50.0, 50.0], "radius": 15.0},
        {"observation_id": "fillet_1", "type": "arc", "center": [90.0, 10.0], "radius": 10.0, "start_angle_deg": 90.0, "end_angle_deg": 180.0},
    ]

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("mixed.pdf", 0, 1000, 800, "d" * 64),
        calibration=calib,
        primitives=[
            Primitive(id="t_l1", type="line", source="geometry_external_ai", confidence=0.98, geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(100.0, 0.0)), trace=Trace(bbox_px=(0, 0, 100, 1))),
            Primitive(id="t_l2", type="line", source="geometry_external_ai", confidence=0.98, geometry=LineGeometry(start=Point2D(100.0, 0.0), end=Point2D(100.0, 100.0)), trace=Trace(bbox_px=(99, 0, 100, 100))),
            Primitive(id="t_c1", type="circle", source="geometry_external_ai", confidence=0.97, geometry=CircleGeometry(center=Point2D(50.0, 50.0), radius=15.0), trace=Trace(bbox_px=(35, 35, 65, 65))),
            Primitive(id="t_a1", type="arc", source="geometry_external_ai", confidence=0.94, geometry=ArcGeometry(center=Point2D(90.0, 10.0), radius=10.0, start_angle_deg=90.0, end_angle_deg=180.0), trace=Trace(bbox_px=(80, 0, 100, 20))),
        ],
    )

    res_d = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_prims,
        verified_target_document=doc,
        alignment_anchors=_anchors(),
        max_correspondence_residual=5.0,
        keep_tolerance=0.5,
    )

    assert res_d["status"] == "NO_DELTA_IDENTICAL"
    assert len(res_d["correspondence"]) == 4
    types = [c["type"] for c in res_d["correspondence"]]
    assert types.count("line") == 2
    assert types.count("circle") == 1
    assert types.count("arc") == 1


def test_scenario_8_ambiguous_symmetric_circle_candidates():
    """Scenario 8: Equidistant symmetric candidates trigger fail-closed AMBIGUOUS status."""
    calib = _calib()
    # Two base holes at exactly (+20, 0) and (-20, 0) from center
    base_circles = [
        {"observation_id": "hole_left", "type": "circle", "center": [80.0, 100.0], "radius": 10.0},
        {"observation_id": "hole_right", "type": "circle", "center": [120.0, 100.0], "radius": 10.0},
    ]

    # Target hole centered at (100, 100) exactly halfway between both: distance is 20.0 mm to both!
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("symm.pdf", 0, 1000, 800, "d" * 64),
        calibration=calib,
        primitives=[
            Primitive(
                id="t_ambig",
                type="circle",
                source="geometry_external_ai",
                confidence=0.95,
                geometry=CircleGeometry(center=Point2D(100.0, 100.0), radius=10.0),
                trace=Trace(bbox_px=(90, 90, 110, 110)),
            )
        ],
    )

    res_d = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_circles,
        verified_target_document=doc,
        alignment_anchors=_anchors(),
        max_correspondence_residual=25.0,
        keep_tolerance=1.0,
    )

    assert res_d.get("correspondence_status") == "AMBIGUOUS"
    assert len(res_d.get("deltas", [])) == 0
