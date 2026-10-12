"""Positive and Negative Controls for Topic 26:
PRIMITIVE_IR_SERIALIZATION_ROUNDTRIP_INTEGRITY_V1.

8 formal boundary controls:
1. Positive complete document identity roundtrip
2. Positive arc geometry parameter preservation
3. Negative circle non-positive radius rejection
4. Negative arc non-positive radius rejection
5. Negative text empty or non-positive height rejection
6. Negative missing required document/primitive fields
7. Negative invalid enums (type, source, role, unit, method)
8. Negative cross-validation dangling primitive ID rejection
"""

import copy
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
    StrategyD_LosslessCanonicalRoundtripEngine,
    canonical_json_dumps,
    deep_validate_document,
)


def _base_valid_doc():
    return {
        "schema_version": "1.0.0",
        "source_document": {
            "file_name": "ctrl.png",
            "page_index": 0,
            "image_width_px": 800,
            "image_height_px": 600,
        },
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 1.0,
            "origin_px": [0.0, 0.0],
            "method": "known_dimension_reference",
            "status": "verified",
        },
        "primitives": [
            {
                "id": "line-p1",
                "type": "line",
                "source": "geometry_opencv",
                "confidence": 0.95,
                "layer": "UNCLASSIFIED",
                "handle": None,
                "trace": {"bbox_px": [0.0, 0.0, 100.0, 0.0]},
                "validation": {"status": "unreviewed"},
                "geometry": {
                    "start": {"x": 0.0, "y": 0.0},
                    "end": {"x": 100.0, "y": 0.0},
                },
            },
            {
                "id": "text-p1",
                "type": "text",
                "source": "text_tesseract",
                "confidence": 0.90,
                "layer": "UNCLASSIFIED",
                "handle": None,
                "trace": {"bbox_px": [40.0, 5.0, 60.0, 15.0]},
                "validation": {"status": "unreviewed"},
                "text_data": {
                    "content": "100",
                    "position": {"x": 50.0, "y": 10.0},
                    "rotation_deg": 0.0,
                    "height": 2.5,
                    "parsed_value": 100.0,
                    "semantic_role": "dimension_value",
                },
            },
        ],
        "cross_validations": [
            {
                "id": "cv-1",
                "text_primitive_id": "text-p1",
                "geometry_primitive_id": "line-p1",
                "status": "confirmed",
                "text_value": 100.0,
                "geometry_measured_length": 100.0,
                "delta_percent": 0.0,
                "match_threshold_percent": 3.0,
            }
        ],
    }


def test_ctrl_1_positive_complete_identity():
    """Ctrl 1: Positive roundtrip identity doc == from_dict(to_dict(doc))."""
    doc_dict = _base_valid_doc()
    assert deep_validate_document(doc_dict) == []

    reloaded = StrategyD_LosslessCanonicalRoundtripEngine.deserialize(doc_dict)
    reloaded_dict = reloaded.to_dict()
    assert deep_validate_document(reloaded_dict) == []

    # Strict byte identity
    assert canonical_json_dumps(doc_dict) == canonical_json_dumps(reloaded_dict)


def test_ctrl_2_positive_arc_geometry_preservation():
    """Ctrl 2: Positive preservation of arc parameters across roundtrip."""
    doc_dict = _base_valid_doc()
    arc_prim = {
        "id": "arc-p1",
        "type": "arc",
        "source": "geometry_opencv",
        "confidence": 0.89,
        "layer": "UNCLASSIFIED",
        "handle": None,
        "trace": {"bbox_px": [10.0, 10.0, 50.0, 50.0]},
        "validation": {"status": "unreviewed"},
        "geometry": {
            "center": {"x": 30.0, "y": 30.0},
            "radius": 20.0,
            "start_angle_deg": 30.0,
            "end_angle_deg": 150.0,
        },
    }
    doc_dict["primitives"].append(arc_prim)
    assert deep_validate_document(doc_dict) == []

    reloaded = StrategyD_LosslessCanonicalRoundtripEngine.deserialize(doc_dict)
    arc_obj = next(p for p in reloaded.primitives if p.id == "arc-p1")
    assert arc_obj.geometry.center.x == 30.0
    assert arc_obj.geometry.center.y == 30.0
    assert arc_obj.geometry.radius == 20.0
    assert arc_obj.geometry.start_angle_deg == 30.0
    assert arc_obj.geometry.end_angle_deg == 150.0


def test_ctrl_3_negative_circle_non_positive_radius():
    """Ctrl 3: Negative rejection of circle with radius <= 0."""
    for bad_r in [0.0, -0.001, -100.0]:
        doc_dict = _base_valid_doc()
        doc_dict["primitives"].append({
            "id": "circle-bad", "type": "circle", "source": "geometry_opencv", "confidence": 0.9,
            "layer": "UNCLASSIFIED", "handle": None,
            "trace": {"bbox_px": [0.0, 0.0, 10.0, 10.0]}, "validation": {"status": "unreviewed"},
            "geometry": {"center": {"x": 0.0, "y": 0.0}, "radius": bad_r},
        })
        errs = deep_validate_document(doc_dict)
        assert any("radius" in e for e in errs), f"Expected radius error for r={bad_r}"


def test_ctrl_4_negative_arc_non_positive_radius():
    """Ctrl 4: Negative rejection of arc with radius <= 0."""
    for bad_r in [0.0, -5.0]:
        doc_dict = _base_valid_doc()
        doc_dict["primitives"].append({
            "id": "arc-bad", "type": "arc", "source": "geometry_opencv", "confidence": 0.9,
            "layer": "UNCLASSIFIED", "handle": None,
            "trace": {"bbox_px": [0.0, 0.0, 10.0, 10.0]}, "validation": {"status": "unreviewed"},
            "geometry": {"center": {"x": 0.0, "y": 0.0}, "radius": bad_r, "start_angle_deg": 0.0, "end_angle_deg": 90.0},
        })
        errs = deep_validate_document(doc_dict)
        assert any("radius" in e for e in errs), f"Expected radius error for r={bad_r}"


def test_ctrl_5_negative_text_empty_or_non_positive_height():
    """Ctrl 5: Negative rejection of text with height <= 0 or invalid content."""
    # Non-positive height
    for bad_h in [0.0, -2.0]:
        doc_dict = _base_valid_doc()
        doc_dict["primitives"][1]["text_data"]["height"] = bad_h
        errs = deep_validate_document(doc_dict)
        assert any("height" in e for e in errs)

    # Non-string content
    doc_dict2 = _base_valid_doc()
    doc_dict2["primitives"][1]["text_data"]["content"] = 12345
    errs2 = deep_validate_document(doc_dict2)
    assert any("content" in e for e in errs2)


def test_ctrl_6_negative_missing_required_fields():
    """Ctrl 6: Negative rejection of missing required document and primitive fields."""
    # Missing document level required field
    for req in ("schema_version", "source_document", "calibration", "primitives"):
        doc_dict = _base_valid_doc()
        del doc_dict[req]
        errs = deep_validate_document(doc_dict)
        assert any(req in e for e in errs)

    # Missing primitive level required field
    for req_p in ("id", "type", "source", "confidence", "layer", "handle", "trace", "validation"):
        doc_dict = _base_valid_doc()
        del doc_dict["primitives"][0][req_p]
        errs = deep_validate_document(doc_dict)
        assert any(req_p in e for e in errs)


def test_ctrl_7_negative_invalid_enums():
    """Ctrl 7: Negative rejection of invalid enum values."""
    # Invalid primitive type
    doc1 = _base_valid_doc()
    doc1["primitives"][0]["type"] = "spline"
    assert any("type 'spline'" in e for e in deep_validate_document(doc1))

    # Invalid primitive source
    doc2 = _base_valid_doc()
    doc2["primitives"][0]["source"] = "llm_generative"
    assert any("source 'llm_generative'" in e for e in deep_validate_document(doc2))

    # Invalid semantic role
    doc3 = _base_valid_doc()
    doc3["primitives"][1]["text_data"]["semantic_role"] = "magic_annotation"
    assert any("semantic_role 'magic_annotation'" in e for e in deep_validate_document(doc3))

    # Invalid calibration unit
    doc4 = _base_valid_doc()
    doc4["calibration"]["unit"] = "inches"
    assert any("unit 'inches'" in e for e in deep_validate_document(doc4))

    # Invalid calibration method
    doc5 = _base_valid_doc()
    doc5["calibration"]["method"] = "magic_scale"
    assert any("method 'magic_scale'" in e for e in deep_validate_document(doc5))


def test_ctrl_8_negative_cross_validation_dangling_ids():
    """Ctrl 8: Negative rejection of dangling IDs in cross_validations."""
    # Dangling text primitive id
    doc1 = _base_valid_doc()
    doc1["cross_validations"][0]["text_primitive_id"] = "non-existent-text"
    errs1 = deep_validate_document(doc1)
    assert any("text_primitive_id 'non-existent-text' not found" in e for e in errs1)

    # Dangling geometry primitive id
    doc2 = _base_valid_doc()
    doc2["cross_validations"][0]["geometry_primitive_id"] = "non-existent-line"
    errs2 = deep_validate_document(doc2)
    assert any("geometry_primitive_id 'non-existent-line' not found" in e for e in errs2)
