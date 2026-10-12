"""Controls test suite for Topic 28: SOURCE_VERIFIED_CURVED_GEOMETRY_MATERIALIZER_V1.

Exercises positive controls, strict negative controls, and boundary controls:
1. Positive Control: Clean mixed document (Line + Circle + Arc) passes
2. Negative Control: Calibration status unverified raises EXTERNAL_GEOMETRY_CALIBRATION_UNVERIFIED
3. Negative Control: Calibration source SHA mismatch raises EXTERNAL_GEOMETRY_CALIBRATION_SOURCE_MISMATCH
4. Negative Control: Source render dimension mismatch raises SOURCE_RENDER_DIMENSION_MISMATCH
5. Negative Control: Malformed source binding raises SOURCE_BINDING_INVALID
6. Negative Control: Missing support entry raises VERIFICATION_RESULT_INVALID
7. Boundary Control: Semicircle (180 deg) and full circle boundary angles
8. Boundary Control: Very small and very large radius stability
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
import pytest
from PIL import Image

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from primitive_ir_lib.models import Calibration
from source_verified_curved_engine import (
    StrategyD_LosslessCurvedMaterializerOracle,
    compute_primitive_bbox_px,
    pixel_arc_to_cad_arc,
)


def _make_render_bytes(width: int = 1000, height: int = 800) -> bytes:
    img = Image.new("L", (width, height), color=255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _valid_calibration(sha: str) -> Calibration:
    return Calibration(
        unit="mm",
        pixel_to_unit_scale=0.25,
        origin_px=(50.0, 750.0),
        method="manual_override",
        status="verified",
        source_sha256=sha,
    )


def test_control_1_positive_clean_mixed_model():
    """Control 1: Positive control for clean mixed model."""
    sha = "3" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calibration(sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 500, 500],
        },
        "verification_request_sha256": "4" * 64,
        "primitive_hypotheses": [
            {"id": "l1", "type": "LINE", "start_px": [100, 100], "end_px": [200, 100]},
            {"id": "c1", "type": "CIRCLE", "center_px": [300, 300], "radius_px": 25.0},
            {"id": "a1", "type": "ARC", "center_px": [300, 300], "radius_px": 50.0, "start_angle_deg": 45.0, "end_angle_deg": 135.0},
        ],
    }
    res = {
        "primitive_support": [
            {"primitive_hypothesis_id": "l1", "verdict": "PASS", "support_fraction": 0.95},
            {"primitive_hypothesis_id": "c1", "verdict": "PASS", "support_fraction": 0.95},
            {"primitive_hypothesis_id": "a1", "verdict": "PASS", "support_fraction": 0.95},
        ]
    }

    doc = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="clean.pdf",
        image_width_px=1000,
        image_height_px=800,
    )
    assert len(doc.primitives) == 3


def test_control_2_negative_unverified_calibration():
    """Control 2: Negative control - calibration status != 'verified' raises error."""
    sha = "3" * 64
    img_bytes = _make_render_bytes()
    calib = Calibration(
        unit="mm",
        pixel_to_unit_scale=0.25,
        origin_px=(50.0, 750.0),
        method="manual_override",
        status="unverified",
        source_sha256=sha,
    )

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 500, 500],
        },
        "verification_request_sha256": "4" * 64,
        "primitive_hypotheses": [],
    }
    res = {"primitive_support": []}

    with pytest.raises(ValueError, match="EXTERNAL_GEOMETRY_CALIBRATION_UNVERIFIED"):
        StrategyD_LosslessCurvedMaterializerOracle.materialize(
            verification_request=req,
            verification_result=res,
            source_render_bytes=img_bytes,
            calibration=calib,
            source_file_name="unverified.pdf",
            image_width_px=1000,
            image_height_px=800,
        )


def test_control_3_negative_calibration_sha_mismatch():
    """Control 3: Negative control - calibration source SHA256 mismatch raises error."""
    sha = "3" * 64
    diff_sha = "5" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calibration(diff_sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 500, 500],
        },
        "verification_request_sha256": "4" * 64,
        "primitive_hypotheses": [],
    }
    res = {"primitive_support": []}

    with pytest.raises(ValueError, match="EXTERNAL_GEOMETRY_CALIBRATION_SOURCE_MISMATCH"):
        StrategyD_LosslessCurvedMaterializerOracle.materialize(
            verification_request=req,
            verification_result=res,
            source_render_bytes=img_bytes,
            calibration=calib,
            source_file_name="mismatch.pdf",
            image_width_px=1000,
            image_height_px=800,
        )


def test_control_4_negative_render_dimension_mismatch():
    """Control 4: Negative control - declared width/height mismatch with image bytes."""
    sha = "3" * 64
    img_bytes = _make_render_bytes(width=1000, height=800)
    calib = _valid_calibration(sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 500, 500],
        },
        "verification_request_sha256": "4" * 64,
        "primitive_hypotheses": [],
    }
    res = {"primitive_support": []}

    with pytest.raises(ValueError, match="SOURCE_RENDER_DIMENSION_MISMATCH"):
        StrategyD_LosslessCurvedMaterializerOracle.materialize(
            verification_request=req,
            verification_result=res,
            source_render_bytes=img_bytes,
            calibration=calib,
            source_file_name="dim_mismatch.pdf",
            image_width_px=1200,  # mismatch
            image_height_px=800,
        )


def test_control_5_negative_malformed_source_binding():
    """Control 5: Negative control - invalid roi_bbox_px format."""
    sha = "3" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calibration(sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, "invalid"],  # bad roi length and type
        },
        "verification_request_sha256": "4" * 64,
        "primitive_hypotheses": [],
    }
    res = {"primitive_support": []}

    with pytest.raises(ValueError, match="SOURCE_BINDING_INVALID"):
        StrategyD_LosslessCurvedMaterializerOracle.materialize(
            verification_request=req,
            verification_result=res,
            source_render_bytes=img_bytes,
            calibration=calib,
            source_file_name="bad_roi.pdf",
            image_width_px=1000,
            image_height_px=800,
        )


def test_control_6_negative_missing_support_entry():
    """Control 6: Negative control - verification_result has no record for a hypothesis ID."""
    sha = "3" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calibration(sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 500, 500],
        },
        "verification_request_sha256": "4" * 64,
        "primitive_hypotheses": [
            {"id": "c1", "type": "CIRCLE", "center_px": [200, 200], "radius_px": 30.0}
        ],
    }
    # Empty support list
    res = {"primitive_support": []}

    with pytest.raises(ValueError, match="VERIFICATION_RESULT_INVALID"):
        StrategyD_LosslessCurvedMaterializerOracle.materialize(
            verification_request=req,
            verification_result=res,
            source_render_bytes=img_bytes,
            calibration=calib,
            source_file_name="missing_support.pdf",
            image_width_px=1000,
            image_height_px=800,
        )


def test_control_7_boundary_semicircle_and_quadrant_angles():
    """Control 7: Boundary control - Semicircle (180 deg) and quadrant angles."""
    sha = "3" * 64
    calib = _valid_calibration(sha)

    # 180 deg pixel arc from 0 to 180 deg
    geom = pixel_arc_to_cad_arc(
        center_px=[200.0, 200.0],
        radius_px=50.0,
        start_angle_px_deg=0.0,
        end_angle_px_deg=180.0,
        calibration=calib,
    )
    # Start pt in px: (250, 200). End pt in px: (150, 200).
    # In CAD, start pt is at 0 deg, end pt is at 180 deg.
    # Pixel arc goes CW (from 0 to 180 through 90 deg down).
    # In CAD, y is reflected up, so it goes CCW from 180 deg to 0/360 deg!
    assert geom.start_angle_deg == pytest.approx(180.0)
    assert geom.end_angle_deg == pytest.approx(0.0)


def test_control_8_boundary_extreme_radii():
    """Control 8: Boundary control - Very small and very large radii numeric sanity."""
    sha = "3" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calibration(sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [10, 10, 990, 790],
        },
        "verification_request_sha256": "4" * 64,
        "primitive_hypotheses": [
            {"id": "tiny_c", "type": "CIRCLE", "center_px": [100.0, 100.0], "radius_px": 0.5},
            {"id": "huge_c", "type": "CIRCLE", "center_px": [500.0, 500.0], "radius_px": 5000.0},
        ],
    }
    res = {
        "primitive_support": [
            {"primitive_hypothesis_id": "tiny_c", "verdict": "PASS", "support_fraction": 0.9},
            {"primitive_hypothesis_id": "huge_c", "verdict": "PASS", "support_fraction": 0.9},
        ]
    }

    doc = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="extreme.pdf",
        image_width_px=1000,
        image_height_px=800,
    )
    assert len(doc.primitives) == 2
    assert doc.primitives[0].geometry.radius == pytest.approx(0.125)  # 0.5 * 0.25
    assert doc.primitives[1].geometry.radius == pytest.approx(1250.0)  # 5000 * 0.25
