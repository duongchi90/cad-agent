"""Empirical Benchmark comparing Strategies A-D for Topic 26:
PRIMITIVE_IR_SERIALIZATION_ROUNDTRIP_INTEGRITY_V1.

Evaluates 8 scenarios:
1. Mixed Complete Document (Line, Circle, Arc, Text, CrossValidation)
2. External Visual AI Geometry with Verification Hashes
3. Calibration Pending Verification ('needs_verification')
4. Corrupted Geometry Detection (Negative Radius, Incomplete Arc)
5. Non-Finite Coordinate Rejection (NaN / Inf)
6. Precision Text Callouts & Dimension Roles
7. RFC-8259 Strict Canonical JSON Hashing
8. Extended Builder Assembly with Arcs and Cross-Validations
"""

import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from primitive_ir_lib.models import (
    ArcGeometry,
    Calibration,
    CircleGeometry,
    CrossValidation,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    TextData,
    Trace,
    Validation,
)

from primitive_ir_roundtrip_engine import (
    RawArc,
    StrategyA_ProductionBaseline,
    StrategyB_NaiveShallow,
    StrategyC_StrictSchemaDeserializer,
    StrategyD_LosslessCanonicalRoundtripEngine,
    arc_to_primitive,
    canonical_json_dumps,
    deep_validate_document,
)


def _make_sample_document(calibration_status="verified", include_external_ai=False):
    prims = [
        Primitive(
            id="line-1",
            type="line",
            source="geometry_opencv",
            confidence=0.92,
            geometry=LineGeometry(start=Point2D(10.0, 20.0), end=Point2D(110.0, 20.0)),
            trace=Trace(bbox_px=(10.0, 20.0, 110.0, 22.0), extraction_tool="opencv-hough"),
            validation=Validation(status="reviewer1_pass", notes="Verified line"),
        ),
        Primitive(
            id="circle-1",
            type="circle",
            source="geometry_opencv",
            confidence=0.96,
            geometry=CircleGeometry(center=Point2D(60.0, 50.0), radius=15.0),
            trace=Trace(bbox_px=(45.0, 35.0, 75.0, 65.0), extraction_tool="opencv-hough-circle"),
            validation=Validation(status="unreviewed"),
        ),
        Primitive(
            id="arc-1",
            type="arc",
            source="geometry_opencv",
            confidence=0.88,
            geometry=ArcGeometry(center=Point2D(60.0, 50.0), radius=30.0, start_angle_deg=0.0, end_angle_deg=180.0),
            trace=Trace(bbox_px=(30.0, 50.0, 90.0, 80.0), extraction_tool="taubin-arc"),
            validation=Validation(status="unreviewed"),
        ),
        Primitive(
            id="text-1",
            type="text",
            source="text_tesseract",
            confidence=0.95,
            text_data=TextData(
                content="100.0",
                position=Point2D(60.0, 15.0),
                rotation_deg=0.0,
                height=3.5,
                parsed_value=100.0,
                semantic_role="dimension_value",
            ),
            trace=Trace(bbox_px=(50.0, 10.0, 70.0, 18.0), extraction_tool="tesseract-5.4"),
            validation=Validation(status="reviewer1_pass"),
        ),
    ]

    if include_external_ai:
        prims.append(
            Primitive(
                id="ai-line-1",
                type="line",
                source="geometry_external_ai",
                confidence=0.99,
                geometry=LineGeometry(start=Point2D(10.0, 80.0), end=Point2D(110.0, 80.0)),
                trace=Trace(
                    bbox_px=(10.0, 80.0, 110.0, 82.0),
                    extraction_tool="claude-vision-v1",
                    verification_request_sha256="a" * 64,
                    verification_result_sha256="b" * 64,
                ),
                validation=Validation(status="reviewer2_pass"),
            )
        )

    cvs = [
        CrossValidation(
            id="cv-1",
            text_primitive_id="text-1",
            geometry_primitive_id="line-1",
            status="confirmed",
            text_value=100.0,
            geometry_measured_length=100.0,
            delta_percent=0.0,
            match_threshold_percent=3.0,
        )
    ]

    return PrimitiveIRDocument(
        source_document=SourceDocument("sample_drawing.png", 0, 1200, 900, sha256="c" * 64),
        calibration=Calibration("mm", 1.0, (10.0, 10.0), "known_dimension_reference", status=calibration_status),
        primitives=prims,
        cross_validations=cvs,
    )


def test_scenario_1_mixed_complete_document():
    """Scenario 1: Mixed complete document roundtrip across all strategies."""
    doc = _make_sample_document(calibration_status="verified", include_external_ai=False)
    doc_dict = doc.to_dict()

    # Strategy A
    doc_a = StrategyA_ProductionBaseline.deserialize(doc_dict)
    assert len(doc_a.primitives) == 4
    assert len(doc_a.cross_validations) == 1

    # Strategy B (fails with ValueError on Arc geometry because it lacks arc unpacker)
    with pytest.raises(ValueError, match="arc.*geometry"):
        StrategyB_NaiveShallow.deserialize(doc_dict)

    # Strategy C
    doc_c = StrategyC_StrictSchemaDeserializer.deserialize(doc_dict)
    assert len(doc_c.primitives) == 4

    # Strategy D
    doc_d, equal = StrategyD_LosslessCanonicalRoundtripEngine.roundtrip(doc)
    assert equal is True
    assert len(StrategyD_LosslessCanonicalRoundtripEngine.validate(doc_d.to_dict())) == 0


def test_scenario_2_external_ai_geometry_with_verification_hashes():
    """Scenario 2: Verification SHA256 preservation for external AI proposals."""
    doc = _make_sample_document(calibration_status="verified", include_external_ai=True)
    doc_dict = doc.to_dict()

    # Strategy A: strips SHA256 fields -> validation fails
    doc_a = StrategyA_ProductionBaseline.deserialize(doc_dict)
    val_errors_a = StrategyA_ProductionBaseline.validate(doc_a.to_dict())
    assert len(val_errors_a) == 2  # Fails re-validation!

    # Strategy B: shallow unpacker fails on arc
    with pytest.raises(ValueError, match="arc.*geometry"):
        StrategyB_NaiveShallow.deserialize(doc_dict)

    # Strategy C: preserves sha256
    doc_c = StrategyC_StrictSchemaDeserializer.deserialize(doc_dict)
    ai_c = next(p for p in doc_c.primitives if p.id == "ai-line-1")
    assert ai_c.trace.verification_request_sha256 == "a" * 64

    # Strategy D: preserves and passes deep validation with 0 errors
    doc_d, equal = StrategyD_LosslessCanonicalRoundtripEngine.roundtrip(doc)
    assert equal is True
    assert StrategyD_LosslessCanonicalRoundtripEngine.validate(doc_d.to_dict()) == []


def test_scenario_3_calibration_pending_verification():
    """Scenario 3: Handling calibration status 'needs_verification'."""
    doc = _make_sample_document(calibration_status="needs_verification", include_external_ai=False)
    doc_dict = doc.to_dict()

    # Strategy A: hard crash
    with pytest.raises(ValueError):
        StrategyA_ProductionBaseline.deserialize(doc_dict)

    # Strategy C: succeeds
    doc_c = StrategyC_StrictSchemaDeserializer.deserialize(doc_dict)
    assert doc_c.calibration.status == "needs_verification"

    # Strategy D: roundtrip equal
    doc_d, equal = StrategyD_LosslessCanonicalRoundtripEngine.roundtrip(doc)
    assert equal is True
    assert doc_d.calibration.status == "needs_verification"


def test_scenario_4_corrupted_geometry_detection():
    """Scenario 4: Corrupted circle radius and arc completeness detection."""
    bad_doc = {
        "schema_version": "1.0.0",
        "source_document": {"file_name": "f.png", "page_index": 0, "image_width_px": 100, "image_height_px": 100},
        "calibration": {"unit": "mm", "pixel_to_unit_scale": 1.0, "origin_px": [0, 0], "method": "manual_override"},
        "primitives": [
            {
                "id": "bad-c", "type": "circle", "source": "geometry_opencv", "confidence": 0.9,
                "layer": "UNCLASSIFIED", "handle": None,
                "trace": {"bbox_px": [0, 0, 10, 10]}, "validation": {"status": "unreviewed"},
                "geometry": {"center": {"x": 0, "y": 0}, "radius": -5.0},
            },
            {
                "id": "bad-arc", "type": "arc", "source": "geometry_opencv", "confidence": 0.9,
                "layer": "UNCLASSIFIED", "handle": None,
                "trace": {"bbox_px": [0, 0, 10, 10]}, "validation": {"status": "unreviewed"},
                "geometry": {"center": {"x": 0, "y": 0}},  # Missing radius, angles
            },
        ],
        "cross_validations": [],
    }

    # Strategy A & C validator: 0 errors detected (blind to geometry numbers)
    errs_a = StrategyA_ProductionBaseline.validate(bad_doc)
    assert len(errs_a) == 0

    # Strategy D validator: catches both corrupted primitives
    errs_d = StrategyD_LosslessCanonicalRoundtripEngine.validate(bad_doc)
    assert len(errs_d) >= 2
    assert any("radius" in e for e in errs_d)


def test_scenario_5_non_finite_coordinate_rejection():
    """Scenario 5: Rejection of NaN and Infinity coordinates."""
    nan_doc = {
        "schema_version": "1.0.0",
        "source_document": {"file_name": "f.png", "page_index": 0, "image_width_px": 100, "image_height_px": 100},
        "calibration": {"unit": "mm", "pixel_to_unit_scale": 1.0, "origin_px": [0, 0], "method": "manual_override"},
        "primitives": [
            {
                "id": "nan-p", "type": "line", "source": "geometry_opencv", "confidence": 0.9,
                "layer": "UNCLASSIFIED", "handle": None,
                "trace": {"bbox_px": [0, 0, 10, 10]}, "validation": {"status": "unreviewed"},
                "geometry": {"start": {"x": float("nan"), "y": 0.0}, "end": {"x": 10.0, "y": float("inf")}},
            }
        ],
        "cross_validations": [],
    }

    # Strategy A & C: allows NaN/Inf without errors
    assert len(StrategyA_ProductionBaseline.validate(nan_doc)) == 0

    # Strategy D: catches non-finite values
    errs_d = StrategyD_LosslessCanonicalRoundtripEngine.validate(nan_doc)
    assert len(errs_d) >= 2

    # Canonical serialization fails fast on non-finite
    with pytest.raises(ValueError):
        canonical_json_dumps(nan_doc)


def test_scenario_6_precision_text_and_dimension_roles():
    """Scenario 6: Precision text with floating values and semantic roles."""
    doc = _make_sample_document()
    doc_d, equal = StrategyD_LosslessCanonicalRoundtripEngine.roundtrip(doc)
    assert equal is True

    text_prim = next(p for p in doc_d.primitives if p.type == "text")
    assert text_prim.text_data.parsed_value == 100.0
    assert text_prim.text_data.semantic_role == "dimension_value"
    assert text_prim.text_data.height == 3.5


def test_scenario_7_rfc8259_strict_canonical_json_hashing():
    """Scenario 7: SHA-256 stability under canonical JSON serialization."""
    doc = _make_sample_document(include_external_ai=True)
    hash_1 = StrategyD_LosslessCanonicalRoundtripEngine.compute_sha256(doc)

    # Reload and re-hash
    doc_reloaded = StrategyD_LosslessCanonicalRoundtripEngine.deserialize(doc.to_dict())
    hash_2 = StrategyD_LosslessCanonicalRoundtripEngine.compute_sha256(doc_reloaded)

    assert hash_1 == hash_2
    assert len(hash_1) == 64


def test_scenario_8_extended_builder_assembly_with_arcs():
    """Scenario 8: Extended builder assembly including arc primitives."""
    cal = Calibration("mm", 0.5, (0.0, 0.0), "manual_override")
    raw_arc = RawArc(
        id="raw-arc-1",
        center_px=(100.0, 100.0),
        radius_px=40.0,
        start_angle_deg=45.0,
        end_angle_deg=135.0,
        confidence=0.91,
        bbox_px=(60.0, 60.0, 140.0, 140.0),
    )

    prim_arc = arc_to_primitive(raw_arc, cal, tool="taubin-fit-v1")
    assert prim_arc.type == "arc"
    assert prim_arc.geometry.center.x == 50.0  # 100.0 * 0.5
    assert prim_arc.geometry.center.y == -50.0 # (0 - 100.0) * 0.5
    assert prim_arc.geometry.radius == 20.0    # 40.0 * 0.5
    assert prim_arc.geometry.start_angle_deg == 45.0
    assert prim_arc.geometry.end_angle_deg == 135.0
