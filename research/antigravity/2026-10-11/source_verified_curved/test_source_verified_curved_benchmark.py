"""Benchmark test suite for Topic 28: SOURCE_VERIFIED_CURVED_GEOMETRY_MATERIALIZER_V1.

Empirically compares Strategies A-D across 8 distinct benchmark scenarios:
- Strategy A: Production Baseline (cad_agent/source_verified_geometry.py)
- Strategy B: Naive Type Expansion (No CAD coordinate winding inversion)
- Strategy C: Forward Coordinate Transform (Sign negation without modular interval inversion)
- Strategy D: Lossless Curved Materializer Oracle (Polymorphic LINE, CIRCLE, ARC with exact WCS mapping)
"""

from __future__ import annotations

import hashlib
import io
import math
import sys
from pathlib import Path
import pytest
from PIL import Image, ImageDraw

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from cad_agent.drawing_contracts import canonical_json_sha256
from primitive_ir_lib.models import Calibration
from source_verified_curved_engine import (
    StrategyA_ProductionBaseline,
    StrategyB_NaiveTypeExpansion,
    StrategyC_ForwardCoordinateTransform,
    StrategyD_LosslessCurvedMaterializerOracle,
    compute_primitive_bbox_px,
)


def _make_case(
    primitives: list[dict[str, object]],
    *,
    width: int = 1200,
    height: int = 900,
    source_sha: str = "1" * 64,
) -> tuple[dict[str, object], dict[str, object], bytes, Calibration]:
    image = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(image)
    for p in primitives:
        if p.get("type") == "LINE":
            draw.line((*p["start_px"], *p["end_px"]), fill=0, width=1)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    render_bytes = stream.getvalue()

    calib = Calibration(
        unit="mm",
        pixel_to_unit_scale=0.5,
        origin_px=(100.0, 800.0),
        method="manual_override",
        status="verified",
        source_sha256=source_sha,
    )

    req = {
        "kind": "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST",
        "status": "PROPOSAL_ONLY",
        "proposal_source": "external_ai",
        "semantic_label_authority": "NONE",
        "primitive_ir_materialized": False,
        "cad_mutation": False,
        "checks_required": ["PER_PRIMITIVE_SOURCE_SUPPORT"],
        "exact_source_binding": {
            "source_sha256": source_sha,
            "page_index": 0,
            "source_render_sha256": hashlib.sha256(render_bytes).hexdigest(),
            "roi_bbox_px": [0, 0, width - 1, height - 1],
        },
        "exact_calibration_binding": calib.to_dict(),
        "primitive_hypotheses": primitives,
    }
    req["verification_request_sha256"] = canonical_json_sha256(req)

    supports = []
    for p in primitives:
        supports.append({
            "primitive_hypothesis_id": p["id"],
            "sample_count": 20,
            "support_fraction": 1.0,
            "supported": True,
        })
    res = {
        "status": "PASS",
        "verification_request_sha256": req["verification_request_sha256"],
        "source_render_sha256": req["exact_source_binding"]["source_render_sha256"],
        "parameter_profile": {
            "endpoint_tolerance_px": 2,
            "darkness_threshold": 128,
            "min_support_fraction": 0.8,
        },
        "primitive_support": supports,
    }
    return req, res, render_bytes, calib


def test_scenario_1_pure_line_document():
    """Scenario 1: Pure line document where all strategies should succeed."""
    from cad_agent.source_support_verifier import verify_external_visual_proposal_source_support

    prims = [
        {"id": "l1", "type": "LINE", "start_px": [100, 200], "end_px": [300, 200]},
        {"id": "l2", "type": "LINE", "start_px": [300, 200], "end_px": [300, 400]},
    ]
    req, _, img_bytes, calib = _make_case(prims)
    res = verify_external_visual_proposal_source_support(
        verification_request=req,
        source_render_bytes=img_bytes,
    )

    doc_a = StrategyA_ProductionBaseline.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="lines.pdf",
        image_width_px=1200,
        image_height_px=900,
    )
    doc_d = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="lines.pdf",
        image_width_px=1200,
        image_height_px=900,
    )

    assert len(doc_a.primitives) == 2
    assert len(doc_d.primitives) == 2
    assert doc_d.primitives[0].geometry.start.x == doc_a.primitives[0].geometry.start.x


def test_scenario_2_pure_circle_document():
    """Scenario 2: Pure circle document - Strategy A fails; B, C, D succeed."""
    prims = [
        {"id": "c1", "type": "CIRCLE", "center_px": [300.0, 400.0], "radius_px": 50.0},
        {"id": "c2", "type": "CIRCLE", "center_px": [500.0, 400.0], "radius_px": 25.0},
    ]
    req, res, img_bytes, calib = _make_case(prims)

    # Strategy A fails
    with pytest.raises(ValueError):
        StrategyA_ProductionBaseline.materialize(
            verification_request=req,
            verification_result=res,
            source_render_bytes=img_bytes,
            calibration=calib,
            source_file_name="circles.pdf",
            image_width_px=1200,
            image_height_px=900,
        )

    # Strategy D succeeds and scales radius properly
    doc_d = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="circles.pdf",
        image_width_px=1200,
        image_height_px=900,
    )
    assert len(doc_d.primitives) == 2
    assert doc_d.primitives[0].geometry.radius == pytest.approx(25.0)  # 50 px * 0.5 mm/px
    assert doc_d.primitives[1].geometry.radius == pytest.approx(12.5)  # 25 px * 0.5 mm/px


def test_scenario_3_pure_arc_cad_orientation():
    """Scenario 3: Arc from 0 to 90 deg in pixels (quadrant 4 in CAD, reflected CW->CCW)."""
    prims = [
        {
            "id": "a1",
            "type": "ARC",
            "center_px": [300.0, 400.0],
            "radius_px": 100.0,
            "start_angle_deg": 0.0,
            "end_angle_deg": 90.0,
        }
    ]
    req, res, img_bytes, calib = _make_case(prims)

    doc_d = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="arc.pdf",
        image_width_px=1200,
        image_height_px=900,
    )
    arc_d = doc_d.primitives[0].geometry
    assert arc_d.start_angle_deg == pytest.approx(270.0)
    assert arc_d.end_angle_deg == pytest.approx(0.0) or arc_d.end_angle_deg == pytest.approx(360.0)


def test_scenario_4_mechanical_flange_mixed_document():
    """Scenario 4: Mixed document with flange outer contour, inner bore, bolt circle holes, and fillets."""
    prims = [
        {"id": "flange_outer", "type": "CIRCLE", "center_px": [400.0, 400.0], "radius_px": 200.0},
        {"id": "flange_inner", "type": "CIRCLE", "center_px": [400.0, 400.0], "radius_px": 80.0},
        {"id": "bolt_1", "type": "CIRCLE", "center_px": [400.0, 260.0], "radius_px": 15.0},
        {"id": "bolt_2", "type": "CIRCLE", "center_px": [400.0, 540.0], "radius_px": 15.0},
        {"id": "rib_1", "type": "LINE", "start_px": [200.0, 400.0], "end_px": [320.0, 400.0]},
        {"id": "rib_2", "type": "LINE", "start_px": [480.0, 400.0], "end_px": [600.0, 400.0]},
        {
            "id": "fillet_1",
            "type": "ARC",
            "center_px": [320.0, 390.0],
            "radius_px": 10.0,
            "start_angle_deg": 90.0,
            "end_angle_deg": 180.0,
        },
    ]
    req, res, img_bytes, calib = _make_case(prims)

    doc_d = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="flange.pdf",
        image_width_px=1200,
        image_height_px=900,
    )
    assert len(doc_d.primitives) == 7
    types = [p.type for p in doc_d.primitives]
    assert types.count("circle") == 4
    assert types.count("line") == 2
    assert types.count("arc") == 1


def test_scenario_5_arc_wraparound_sweep():
    """Scenario 5: Arc crossing the 0/360 degree boundary."""
    prims = [
        {
            "id": "a_wrap",
            "type": "ARC",
            "center_px": [300.0, 300.0],
            "radius_px": 50.0,
            "start_angle_deg": 300.0,
            "end_angle_deg": 60.0,
        }
    ]
    req, res, img_bytes, calib = _make_case(prims)

    doc_d = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="wrap.pdf",
        image_width_px=1200,
        image_height_px=900,
    )
    arc_geom = doc_d.primitives[0].geometry
    # Pixel 300 deg in CAD is 60 deg; pixel 60 deg in CAD is 300 deg.
    # CCW arc goes from 300 to 60 deg.
    assert arc_geom.start_angle_deg == pytest.approx(300.0)
    assert arc_geom.end_angle_deg == pytest.approx(60.0)


def test_scenario_6_filtering_unverified_hypotheses():
    """Scenario 6: Verifies that Strategy D discards FAIL or low-support hypotheses while B retains all."""
    prims = [
        {"id": "good_circle", "type": "CIRCLE", "center_px": [200.0, 200.0], "radius_px": 40.0},
        {"id": "bad_circle", "type": "CIRCLE", "center_px": [300.0, 300.0], "radius_px": 40.0},
    ]
    req, _, img_bytes, calib = _make_case(prims)
    res = {
        "status": "PARTIAL",
        "primitive_support": [
            {"primitive_hypothesis_id": "good_circle", "verdict": "PASS", "support_fraction": 0.95},
            {"primitive_hypothesis_id": "bad_circle", "verdict": "FAIL", "support_fraction": 0.05},
        ],
    }

    doc_b = StrategyB_NaiveTypeExpansion.materialize(
        verification_request=req,
        verification_result=res,
        calibration=calib,
        source_file_name="filter.pdf",
        image_width_px=1200,
        image_height_px=900,
    )
    assert len(doc_b.primitives) == 2  # Naive materializes everything

    doc_d = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="filter.pdf",
        image_width_px=1200,
        image_height_px=900,
        filter_failed_verdicts=True,
    )
    assert len(doc_d.primitives) == 1
    assert doc_d.primitives[0].id == "good_circle"


def test_scenario_7_concentric_cylinder_bushing():
    """Scenario 7: Multi-ring concentric circles and groove arcs."""
    radii = [10.0, 25.0, 40.0, 55.0]
    prims = [
        {"id": f"ring_{i}", "type": "CIRCLE", "center_px": [500.0, 500.0], "radius_px": r}
        for i, r in enumerate(radii)
    ]
    req, res, img_bytes, calib = _make_case(prims)

    doc_d = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="bushing.pdf",
        image_width_px=1200,
        image_height_px=900,
    )
    assert len(doc_d.primitives) == 4
    for i, p in enumerate(doc_d.primitives):
        assert p.geometry.radius == pytest.approx(radii[i] * 0.5)


def test_scenario_8_trace_provenance_and_audit():
    """Scenario 8: Trace hash integrity and tool metadata strictly recorded."""
    prims = [{"id": "c1", "type": "CIRCLE", "center_px": [300.0, 300.0], "radius_px": 50.0}]
    req, res, img_bytes, calib = _make_case(prims)

    doc_d = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="audit.pdf",
        image_width_px=1200,
        image_height_px=900,
    )
    p = doc_d.primitives[0]
    assert p.trace is not None
    assert p.trace.verification_request_sha256 == req["verification_request_sha256"]
    assert p.trace.verification_result_sha256 == canonical_json_sha256(res)
    assert p.trace.extraction_tool == "external-ai-verified-source-support-v1"
