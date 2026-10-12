"""Causal RED test suite for Topic 28: SOURCE_VERIFIED_CURVED_GEOMETRY_MATERIALIZER_V1.

Proves the causal failure of the current production owner (cad_agent/source_verified_geometry.py)
which hard-rejects non-LINE primitives (CIRCLE, ARC) and lacks curved bounding box computation.
"""

from __future__ import annotations

import hashlib
import io
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
from cad_agent.source_verified_geometry import (
    materialize_verified_external_visual_lines,
)
from primitive_ir_lib.models import Calibration
from source_verified_curved_engine import (
    StrategyA_ProductionBaseline,
    StrategyD_LosslessCurvedMaterializerOracle,
    compute_primitive_bbox_px,
    pixel_arc_to_cad_arc,
)


def _make_case(
    primitives: list[dict[str, object]],
    *,
    width: int = 1000,
    height: int = 800,
    source_sha: str = "a" * 64,
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
        pixel_to_unit_scale=0.1,
        origin_px=(100.0, 700.0),
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


def test_red_1_production_rejects_circle_hypothesis():
    """RED 1: Production baseline raises ValueError('VERIFICATION_REQUEST_INVALID') for CIRCLE."""
    req, res, img_bytes, calib = _make_case(
        [
            {
                "id": "c1",
                "type": "CIRCLE",
                "center_px": [300.0, 300.0],
                "radius_px": 50.0,
            }
        ]
    )

    # Baseline fails with VERIFICATION_REQUEST_INVALID because type != LINE
    with pytest.raises(ValueError, match="VERIFICATION_REQUEST_INVALID"):
        materialize_verified_external_visual_lines(
            verification_request=req,
            verification_result=res,
            source_render_bytes=img_bytes,
            calibration=calib,
            source_file_name="drawing.pdf",
            image_width_px=1000,
            image_height_px=800,
        )


def test_red_2_production_rejects_arc_hypothesis():
    """RED 2: Production baseline raises ValueError('VERIFICATION_REQUEST_INVALID') for ARC."""
    req, res, img_bytes, calib = _make_case(
        [
            {
                "id": "a1",
                "type": "ARC",
                "center_px": [300.0, 300.0],
                "radius_px": 50.0,
                "start_angle_deg": 0.0,
                "end_angle_deg": 90.0,
            }
        ]
    )

    # Baseline fails on ARC
    with pytest.raises(ValueError, match="VERIFICATION_REQUEST_INVALID"):
        materialize_verified_external_visual_lines(
            verification_request=req,
            verification_result=res,
            source_render_bytes=img_bytes,
            calibration=calib,
            source_file_name="drawing.pdf",
            image_width_px=1000,
            image_height_px=800,
        )


def test_red_3_production_rejects_mixed_line_curved_document():
    """RED 3: Production baseline aborts whole document if a single curved primitive is present."""
    req, res, img_bytes, calib = _make_case(
        [
            {"id": "l1", "type": "LINE", "start_px": [100, 100], "end_px": [200, 100]},
            {"id": "c1", "type": "CIRCLE", "center_px": [300, 300], "radius_px": 40.0},
        ]
    )

    with pytest.raises(ValueError, match="VERIFICATION_REQUEST_INVALID"):
        StrategyA_ProductionBaseline.materialize(
            verification_request=req,
            verification_result=res,
            source_render_bytes=img_bytes,
            calibration=calib,
            source_file_name="mixed.pdf",
            image_width_px=1000,
            image_height_px=800,
        )


def test_red_4_curved_bbox_calculation():
    """RED 4: Verifies exact bounding box calculations for circles and arcs including extrema."""
    circle_hyp = {
        "id": "c1",
        "type": "CIRCLE",
        "center_px": [200.0, 300.0],
        "radius_px": 50.0,
    }
    bbox_c = compute_primitive_bbox_px(circle_hyp)
    assert bbox_c == (150, 250, 250, 350)

    # Arc crossing 0 degrees: start=315 deg, end=45 deg
    arc_hyp = {
        "id": "a1",
        "type": "ARC",
        "center_px": [200.0, 300.0],
        "radius_px": 100.0,
        "start_angle_deg": 315.0,
        "end_angle_deg": 45.0,
    }
    bbox_a = compute_primitive_bbox_px(arc_hyp)
    # 0 deg extremum is included: max x is 200 + 100 = 300
    assert bbox_a[2] == 300
    # y range spans +/- 100 * sin(45) ~ 70.71 -> min y ~ 300 - 71 = 229, max y ~ 300 + 71 = 371
    assert bbox_a[0] == 270
    assert bbox_a[1] == 229
    assert bbox_a[3] == 371


def test_red_5_strategy_d_oracle_materializes_curved_correctly():
    """RED 5: Strategy D successfully materializes mixed line, circle, and arc primitives."""
    req, res, img_bytes, calib = _make_case(
        [
            {"id": "l1", "type": "LINE", "start_px": [100.0, 100.0], "end_px": [200.0, 100.0]},
            {"id": "c1", "type": "CIRCLE", "center_px": [300.0, 300.0], "radius_px": 40.0},
            {
                "id": "a1",
                "type": "ARC",
                "center_px": [400.0, 400.0],
                "radius_px": 50.0,
                "start_angle_deg": 0.0,
                "end_angle_deg": 90.0,
            },
        ]
    )

    doc = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="mixed.pdf",
        image_width_px=1000,
        image_height_px=800,
    )

    assert len(doc.primitives) == 3
    p_line = next(p for p in doc.primitives if p.id == "l1")
    p_circ = next(p for p in doc.primitives if p.id == "c1")
    p_arc = next(p for p in doc.primitives if p.id == "a1")

    assert p_line.type == "line"
    assert p_circ.type == "circle"
    assert p_arc.type == "arc"

    assert p_circ.geometry.radius == pytest.approx(4.0)
    assert p_arc.geometry.radius == pytest.approx(5.0)
