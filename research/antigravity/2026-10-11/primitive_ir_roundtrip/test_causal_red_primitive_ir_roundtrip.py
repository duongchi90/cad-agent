"""Causal RED tests reproducing baseline serialization and validation failures.

Proves 5 failure modes on CURRENT production code:
- semantic_ir_lib.io_utils._primitive_ir_document_from_dict
- primitive_ir_lib.validator.validate_document
- primitive_ir_lib.assemble.build_document
"""

import inspect
import json
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

from primitive_ir_lib.assemble import build_document
from primitive_ir_lib.models import (
    Calibration,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)
from primitive_ir_lib.validator import validate_document
from semantic_ir_lib.io_utils import _primitive_ir_document_from_dict
from primitive_ir_roundtrip_engine import (
    deep_validate_document,
    deserialize_primitive_ir_document_lossless,
)


def test_red_1_trace_external_ai_hashes_silently_dropped():
    """RED 1: Baseline deserializer drops verification SHA256 fields, breaking AI trace."""
    prim = Primitive(
        id="prim-ai-1",
        type="line",
        source="geometry_external_ai",
        confidence=0.98,
        geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(100.0, 0.0)),
        trace=Trace(
            bbox_px=(0.0, 0.0, 100.0, 10.0),
            extraction_tool="claude-vision-v1",
            extracted_at="2026-10-11T12:00:00Z",
            verification_request_sha256="1111111111111111111111111111111111111111111111111111111111111111",
            verification_result_sha256="2222222222222222222222222222222222222222222222222222222222222222",
        ),
    )
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("sample.png", 0, 800, 600),
        calibration=Calibration("mm", 1.0, (0.0, 0.0), "manual_override"),
        primitives=[prim],
    )
    doc_dict = doc.to_dict()

    # Original document passes validation
    assert validate_document(doc_dict) == []

    # Deserializing via baseline production deserializer
    reloaded = _primitive_ir_document_from_dict(doc_dict)
    reloaded_dict = reloaded.to_dict()

    # Causal Failure: SHA256 fields are silently stripped from trace
    reloaded_trace = reloaded_dict["primitives"][0]["trace"]
    assert "verification_request_sha256" not in reloaded_trace
    assert "verification_result_sha256" not in reloaded_trace

    # Re-validating the reloaded document now fails schema validation!
    errors = validate_document(reloaded_dict)
    assert len(errors) == 2
    assert any("verification_request_sha256" in err for err in errors)
    assert any("verification_result_sha256" in err for err in errors)

    # Strategy D preserves hashes
    d_reloaded = deserialize_primitive_ir_document_lossless(doc_dict)
    d_trace = d_reloaded.to_dict()["primitives"][0]["trace"]
    assert d_trace["verification_request_sha256"] == "1111111111111111111111111111111111111111111111111111111111111111"
    assert d_trace["verification_result_sha256"] == "2222222222222222222222222222222222222222222222222222222222222222"


def test_red_2_needs_verification_calibration_crashes_deserializer():
    """RED 2: Baseline deserializer hard-crashes on 'needs_verification' calibration."""
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("sample.png", 0, 800, 600),
        calibration=Calibration("mm", 1.0, (0.0, 0.0), "manual_override", status="needs_verification"),
        primitives=[
            Primitive(
                id="prim-1",
                type="line",
                source="geometry_opencv",
                confidence=0.9,
                geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(50.0, 50.0)),
                trace=Trace(bbox_px=(0.0, 0.0, 50.0, 50.0)),
            )
        ],
    )
    doc_dict = doc.to_dict()

    # Causal Failure: Baseline deserializer crashes with ValueError
    with pytest.raises(ValueError, match="needs_verification"):
        _primitive_ir_document_from_dict(doc_dict)

    # Strategy D preserves status safely
    reloaded = deserialize_primitive_ir_document_lossless(doc_dict)
    assert reloaded.calibration.status == "needs_verification"


def test_red_3_baseline_validator_accepts_corrupt_geometry_and_scale():
    """RED 3: Baseline validator has blind spots for invalid geometry numbers and negative scale."""
    corrupt_doc = {
        "schema_version": "1.0.0",
        "source_document": {
            "file_name": "corrupt.png",
            "page_index": 0,
            "image_width_px": 500,
            "image_height_px": 500,
        },
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": -10.5,  # Invalid: negative scale
            "origin_px": [0.0, 0.0],
            "method": "manual_override",
            "status": "verified",
        },
        "primitives": [
            {
                "id": "circle-1",
                "type": "circle",
                "source": "geometry_opencv",
                "confidence": 0.95,
                "layer": "UNCLASSIFIED",
                "handle": None,
                "trace": {"bbox_px": [0.0, 0.0, 20.0, 20.0]},
                "validation": {"status": "unreviewed"},
                "geometry": {
                    "center": {"x": 10.0, "y": 10.0},
                    "radius": -25.0,  # Invalid: negative radius
                },
            },
            {
                "id": "arc-1",
                "type": "arc",
                "source": "geometry_opencv",
                "confidence": 0.85,
                "layer": "UNCLASSIFIED",
                "handle": None,
                "trace": {"bbox_px": [0.0, 0.0, 20.0, 20.0]},
                "validation": {"status": "unreviewed"},
                "geometry": {
                    "center": {"x": 10.0, "y": 10.0},
                    # Invalid: missing radius, start_angle_deg, end_angle_deg
                },
            },
        ],
        "cross_validations": [],
    }

    # Causal Failure: Baseline validator flags ZERO errors
    baseline_errors = validate_document(corrupt_doc)
    assert len(baseline_errors) == 0

    # Strategy D catches all 3 critical errors
    deep_errors = deep_validate_document(corrupt_doc)
    assert len(deep_errors) >= 3
    assert any("pixel_to_unit_scale" in err for err in deep_errors)
    assert any("radius" in err for err in deep_errors)
    assert any("start_angle_deg" in err for err in deep_errors)


def test_red_4_baseline_validator_accepts_nan_and_inf_emitting_invalid_json():
    """RED 4: Baseline validator permits non-finite NaN/Inf numbers, violating RFC 8259."""
    nan_doc = {
        "schema_version": "1.0.0",
        "source_document": {
            "file_name": "nan.png",
            "page_index": 0,
            "image_width_px": 500,
            "image_height_px": 500,
        },
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 1.0,
            "origin_px": [0.0, 0.0],
            "method": "manual_override",
            "status": "verified",
        },
        "primitives": [
            {
                "id": "line-nan",
                "type": "line",
                "source": "geometry_opencv",
                "confidence": 0.9,
                "layer": "UNCLASSIFIED",
                "handle": None,
                "trace": {"bbox_px": [0.0, 0.0, 10.0, 10.0]},
                "validation": {"status": "unreviewed"},
                "geometry": {
                    "start": {"x": float("nan"), "y": 0.0},
                    "end": {"x": 10.0, "y": float("inf")},
                },
            }
        ],
        "cross_validations": [],
    }

    # Causal Failure: Baseline validator flags ZERO errors
    baseline_errors = validate_document(nan_doc)
    assert len(baseline_errors) == 0

    # json.dumps emits non-standard NaN / Infinity literals
    serialized = json.dumps(nan_doc)
    assert "NaN" in serialized
    assert "Infinity" in serialized

    # Strategy D detects and rejects non-finite values
    deep_errors = deep_validate_document(nan_doc)
    assert len(deep_errors) >= 2
    assert any("finite" in err for err in deep_errors)


def test_red_5_production_builder_omits_arc_primitives():
    """RED 5: Production assemble.build_document has no parameter for raw_arcs."""
    sig = inspect.signature(build_document)
    params = list(sig.parameters.keys())

    # Causal Failure: raw_arcs is absent from the official builder parameter list
    assert "raw_lines" in params
    assert "raw_circles" in params
    assert "raw_texts" in params
    assert "raw_arcs" not in params
