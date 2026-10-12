"""Degenerate cases and performance profiling suite for Topic 29: SOURCE_FUSION_NATIVE_CURVED_DELTA_COMPOSITION_V1.

Evaluates degenerate, non-finite, stress, and latency boundaries:
1. Degenerate zero or negative radius
2. Degenerate non-finite (NaN / Inf) coordinates
3. Extreme coordinate magnitudes (10^6 mm)
4. Coincident zero-sweep arc
5. Completely disjoint base and target collections (100% ADD and 100% UNMATCHED)
6. Stress test: 500 mixed primitives
7. Performance latency profiling (< 25 ms for 100 primitives)
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
    compute_circle_pair_residual,
)


def _calib() -> Calibration:
    return Calibration(
        unit="mm",
        pixel_to_unit_scale=1.0,
        origin_px=(0.0, 0.0),
        method="manual_override",
        status="verified",
        source_sha256="f" * 64,
    )


def _anchors(span: float = 1000.0) -> list[AnchorPair]:
    return [
        AnchorPair("a1", (0.0, 0.0), (0.0, 0.0), "DATUM", 1.0),
        AnchorPair("a2", (span, 0.0), (span, 0.0), "DATUM", 1.0),
    ]


def test_degenerate_1_zero_radius_circle():
    """Degenerate 1: Point circle (radius = 0) compares safely without ZeroDivision."""
    base = {"observation_id": "b0", "type": "circle", "center": [10.0, 10.0], "radius": 0.0}
    target = {"primitive_id": "t0", "type": "circle", "center": [10.0, 10.0], "radius": 0.0}
    res = compute_circle_pair_residual(base, target)
    assert res == 0.0


def test_degenerate_2_non_finite_coordinates():
    """Degenerate 2: Non-finite coordinates fail closed gracefully."""
    base = {"observation_id": "b_nan", "type": "circle", "center": [float("nan"), 10.0], "radius": 5.0}
    target = {"primitive_id": "t_nan", "type": "circle", "center": [10.0, 10.0], "radius": 5.0}
    res = compute_circle_pair_residual(base, target)
    assert math.isnan(res)


def test_degenerate_3_extreme_coordinate_magnitudes():
    """Degenerate 3: Primitives at 10^6 mm maintain floating-point accuracy."""
    calib = _calib()
    base_obs = [
        {"observation_id": "b_far", "type": "circle", "center": [1_000_000.0, 1_000_000.0], "radius": 25.0}
    ]
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("far.pdf", 0, 1000, 800, "f" * 64),
        calibration=calib,
        primitives=[
            Primitive(
                id="t_far",
                type="circle",
                source="geometry_external_ai",
                confidence=0.98,
                geometry=CircleGeometry(center=Point2D(1_000_000.0, 1_000_000.0), radius=25.0),
                trace=Trace(bbox_px=(0, 0, 10, 10)),
            )
        ],
    )

    res = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_obs,
        verified_target_document=doc,
        alignment_anchors=_anchors(span=1_000_000.0),
        max_correspondence_residual=5.0,
        keep_tolerance=0.5,
    )
    assert res["status"] == "NO_DELTA_IDENTICAL"
    assert res["correspondence"][0]["residual"] == pytest.approx(0.0)


def test_degenerate_4_zero_sweep_arc():
    """Degenerate 4: Arc with identical start and end angles matches correctly."""
    calib = _calib()
    base_obs = [
        {
            "observation_id": "b_a0",
            "type": "arc",
            "center": [100.0, 100.0],
            "radius": 20.0,
            "start_angle_deg": 45.0,
            "end_angle_deg": 45.0,
        }
    ]
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("a0.pdf", 0, 1000, 800, "f" * 64),
        calibration=calib,
        primitives=[
            Primitive(
                id="t_a0",
                type="arc",
                source="geometry_external_ai",
                confidence=0.95,
                geometry=ArcGeometry(center=Point2D(100.0, 100.0), radius=20.0, start_angle_deg=45.0, end_angle_deg=45.0),
                trace=Trace(bbox_px=(90, 90, 110, 110)),
            )
        ],
    )

    res = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_obs,
        verified_target_document=doc,
        alignment_anchors=_anchors(),
        max_correspondence_residual=5.0,
        keep_tolerance=0.5,
    )
    assert res["status"] == "NO_DELTA_IDENTICAL"
    assert res["correspondence"][0]["action"] == "KEEP"


def test_degenerate_5_completely_disjoint_collections():
    """Degenerate 5: Disjoint base and target collections partition into 100% ADD and 100% UNMATCHED."""
    calib = _calib()
    # Base holes at x=100
    base_obs = [
        {"observation_id": f"b_{i}", "type": "circle", "center": [100.0, float(i * 50)], "radius": 10.0}
        for i in range(5)
    ]
    # Target holes far away at x=900
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("disjoint.pdf", 0, 1000, 800, "f" * 64),
        calibration=calib,
        primitives=[
            Primitive(
                id=f"t_{i}",
                type="circle",
                source="geometry_external_ai",
                confidence=0.95,
                geometry=CircleGeometry(center=Point2D(900.0, float(i * 50)), radius=10.0),
                trace=Trace(bbox_px=(890, i * 50, 910, i * 50 + 20)),
            )
            for i in range(5)
        ],
    )

    res = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_obs,
        verified_target_document=doc,
        alignment_anchors=_anchors(),
        max_correspondence_residual=10.0,
        keep_tolerance=1.0,
    )
    assert res["status"] == "DELTA_COMPOSED"
    assert len(res["correspondence"]) == 0
    assert len(res["unmatched_base_observation_ids"]) == 5
    adds = [d for d in res["deltas"] if d["action"] == "ADD"]
    assert len(adds) == 5


def test_stress_6_500_mixed_primitives():
    """Stress 6: Correspondence and delta composition over 500 mixed primitives."""
    calib = _calib()
    n = 500
    base_obs = []
    prims = []
    for i in range(n):
        mod = i % 3
        if mod == 0:
            base_obs.append({"observation_id": f"b_{i}", "type": "line", "start": [float(i), 0.0], "end": [float(i), 100.0]})
            prims.append(Primitive(id=f"t_{i}", type="line", source="geometry_external_ai", confidence=0.95, geometry=LineGeometry(start=Point2D(float(i), 0.0), end=Point2D(float(i), 100.0)), trace=Trace(bbox_px=(i, 0, i + 1, 100))))
        elif mod == 1:
            base_obs.append({"observation_id": f"b_{i}", "type": "circle", "center": [float(i), 200.0], "radius": 15.0})
            prims.append(Primitive(id=f"t_{i}", type="circle", source="geometry_external_ai", confidence=0.95, geometry=CircleGeometry(center=Point2D(float(i), 200.0), radius=15.0), trace=Trace(bbox_px=(i - 15, 185, i + 15, 215))))
        else:
            base_obs.append({"observation_id": f"b_{i}", "type": "arc", "center": [float(i), 400.0], "radius": 10.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0})
            prims.append(Primitive(id=f"t_{i}", type="arc", source="geometry_external_ai", confidence=0.95, geometry=ArcGeometry(center=Point2D(float(i), 400.0), radius=10.0, start_angle_deg=0.0, end_angle_deg=90.0), trace=Trace(bbox_px=(i, 400, i + 10, 410))))

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("stress500.pdf", 0, 1000, 800, "f" * 64),
        calibration=calib,
        primitives=prims,
    )

    start_t = time.perf_counter()
    res = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_obs,
        verified_target_document=doc,
        alignment_anchors=_anchors(span=500.0),
        max_correspondence_residual=5.0,
        keep_tolerance=0.5,
    )
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    assert len(res["correspondence"]) == 500
    assert elapsed_ms < 250.0


def test_perf_7_latency_profiling_100_primitives():
    """Perf 7: 100 mixed primitives correspondence executes in under 25 ms."""
    calib = _calib()
    base_obs = []
    prims = []
    for i in range(100):
        if i % 2 == 0:
            base_obs.append({"observation_id": f"b_{i}", "type": "circle", "center": [float(i * 10), 50.0], "radius": 10.0})
            prims.append(Primitive(id=f"t_{i}", type="circle", source="geometry_external_ai", confidence=0.95, geometry=CircleGeometry(center=Point2D(float(i * 10), 50.0), radius=10.0), trace=Trace(bbox_px=(i * 10 - 10, 40, i * 10 + 10, 60))))
        else:
            base_obs.append({"observation_id": f"b_{i}", "type": "arc", "center": [float(i * 10), 100.0], "radius": 12.0, "start_angle_deg": 0.0, "end_angle_deg": 180.0})
            prims.append(Primitive(id=f"t_{i}", type="arc", source="geometry_external_ai", confidence=0.95, geometry=ArcGeometry(center=Point2D(float(i * 10), 100.0), radius=12.0, start_angle_deg=0.0, end_angle_deg=180.0), trace=Trace(bbox_px=(i * 10 - 12, 88, i * 10 + 12, 112))))

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("perf100.pdf", 0, 1000, 800, "f" * 64),
        calibration=calib,
        primitives=prims,
    )

    start_t = time.perf_counter()
    res = StrategyD_UnifiedGeometricDeltaComposerOracle.compose_delta(
        base_observations=base_obs,
        verified_target_document=doc,
        alignment_anchors=_anchors(span=1000.0),
        max_correspondence_residual=5.0,
        keep_tolerance=0.5,
    )
    latency_ms = (time.perf_counter() - start_t) * 1000

    assert len(res["correspondence"]) == 100
    assert latency_ms < 25.0
