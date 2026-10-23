"""Regression tests for the real-image Phase 1 CLI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from primitive_ir_lib.calibration_registry import add_record, get_verified_scale
from primitive_ir_lib.assemble import build_document as assemble_document
from primitive_ir_lib.geometry_extraction import RawGeometry, RawLine
from primitive_ir_lib.run_image import CalibrationCandidateUnavailableError, main, run
from primitive_ir_lib.text_extraction import RawText
from primitive_ir_lib.validator import validate_document


def test_run_image_writes_valid_primitive_ir_with_manual_scale():
    image = np.full((160, 240, 3), 255, dtype=np.uint8)
    cv2.line(image, (20, 40), (220, 40), (0, 0, 0), 2)
    cv2.circle(image, (120, 100), 18, (0, 0, 0), 2)

    with tempfile.TemporaryDirectory() as directory:
        image_path = Path(directory) / "drawing.png"
        output_path = Path(directory) / "primitive_ir.json"
        assert cv2.imwrite(str(image_path), image)

        saved_path = run(
            image_path=str(image_path),
            output_path=str(output_path),
            scale_mm_per_px=0.5,
            preset="default",
        )

        assert saved_path == str(output_path)
        document = json.loads(output_path.read_text(encoding="utf-8"))
        assert document["calibration"]["method"] == "manual_override"
        assert document["calibration"]["pixel_to_unit_scale"] == 0.5
        assert document["calibration"]["status"] == "verified"
        assert document["source_document"]["sha256"]
        assert document["primitives"]
        assert validate_document(document) == []


def test_confirmed_validation_references_a_serialized_line(tmp_path):
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(
        str(image_path),
        np.full((80, 140, 3), 255, dtype=np.uint8),
    )
    serialized_line = RawLine(
        id="serialized-line",
        p1_px=(10.0, 40.0),
        p2_px=(110.0, 40.0),
        confidence=1.0,
        bbox_px=(10.0, 40.0, 110.0, 40.0),
    )
    dimension_text = RawText(
        id="dimension-text",
        content="100",
        bbox_px=(50, 20, 70, 35),
        rotation_deg=0.0,
        confidence=1.0,
        source="text_tesseract",
        parsed_value=100.0,
        semantic_role="dimension_value",
    )
    remapped_line = RawLine(
        id="cross-validation-only-line",
        p1_px=serialized_line.p1_px,
        p2_px=serialized_line.p2_px,
        confidence=1.0,
        bbox_px=serialized_line.bbox_px,
    )
    with (
        patch(
            "primitive_ir_lib.run_image.extract_raw_geometry",
            return_value=RawGeometry(lines=[serialized_line]),
        ),
        patch(
            "primitive_ir_lib.run_image.extract_text_tesseract",
            return_value=[dimension_text],
        ),
        patch(
            "primitive_ir_lib.cross_validation.merge_collinear_lines",
            return_value=[remapped_line],
        ),
    ):
        run(
            image_path=str(image_path),
            output_path=str(output_path),
            scale_mm_per_px=1.0,
            preset="default",
            ocr_rois=[(0, 0, 140, 80)],
        )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    primitive_ids = {item["id"] for item in payload["primitives"]}
    confirmed = [
        item for item in payload["cross_validations"]
        if item["status"] == "confirmed"
    ]
    assert confirmed
    assert all(
        item["geometry_primitive_id"] in primitive_ids for item in confirmed
    )


def test_run_image_deduplicates_same_span_without_dangling_ocr_references(tmp_path):
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(str(image_path), np.full((80, 120, 3), 255, dtype=np.uint8))
    vector = RawText("pdf-1", "R7,50", (10, 10, 30, 20), 0.0, 1.0, "text_pdfvector")
    duplicate = RawText("ocr-1", "R7,50", (9, 10, 31, 20), 0.0, 0.9, "text_tesseract")
    repeated = RawText("ocr-2", "R7,50", (50, 10, 70, 20), 0.0, 0.9, "text_tesseract")
    near_overlap = RawText("ocr-4", "R7,50", (13, 10, 33, 20), 0.0, 0.9, "text_tesseract")
    different = RawText("ocr-3", "Ø14", (10, 10, 30, 20), 0.0, 0.9, "text_tesseract")
    contained_ocr = RawText("ocr-5", "R7,50", (80, 40, 90, 50), 0.0, 0.9, "text_tesseract")
    containing_vector = RawText(
        "pdf-2", "R7,50", (70, 30, 110, 70), 0.0, 1.0, "text_pdfvector"
    )

    with (
        patch("primitive_ir_lib.run_image.extract_raw_geometry", return_value=RawGeometry()),
        patch(
            "primitive_ir_lib.run_image.extract_text_tesseract",
                return_value=[duplicate, repeated, near_overlap, different, contained_ocr],
        ),
    ):
        run(
            image_path=str(image_path), output_path=str(output_path),
            scale_mm_per_px=1.0, preset="default", ocr_rois=[(0, 0, 120, 80)],
            pdf_vector_texts=[vector, containing_vector],
        )

    document = json.loads(output_path.read_text(encoding="utf-8"))
    texts = [item for item in document["primitives"] if item["type"] == "text"]
    assert [(item["text_data"]["content"], item["source"]) for item in texts] == [
        ("R7,50", "text_tesseract"),
        ("R7,50", "text_tesseract"),
        ("R7,50", "text_tesseract"),
        ("Ø14", "text_tesseract"),
        ("R7,50", "text_tesseract"),
        ("R7,50", "text_pdfvector"),
    ]


def test_run_image_cross_validation_references_saved_text_after_pdf_dedup(tmp_path):
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(str(image_path), np.full((80, 140, 3), 255, dtype=np.uint8))
    line = RawLine(
        "dimension-line", (10.0, 40.0), (110.0, 40.0), 1.0,
        (10.0, 40.0, 110.0, 40.0),
    )
    ocr_text = RawText(
        "ocr-dimension", "100", (50, 20, 70, 35), 0.0, 1.0,
        "text_tesseract", parsed_value=100.0, semantic_role="dimension_value",
    )
    vector_text = RawText(
        "pdf-dimension", "100", (50, 20, 70, 35), 0.0, 1.0,
        "text_pdfvector", parsed_value=100.0, semantic_role="dimension_value",
    )
    with (
        patch("primitive_ir_lib.run_image.extract_raw_geometry", return_value=RawGeometry(lines=[line])),
        patch("primitive_ir_lib.run_image.extract_text_tesseract", return_value=[ocr_text]),
    ):
        run(
            image_path=str(image_path), output_path=str(output_path),
            scale_mm_per_px=1.0, preset="default", ocr_rois=[(0, 0, 140, 80)],
            pdf_vector_texts=[vector_text],
        )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    primitive_ids = {item["id"] for item in payload["primitives"]}
    assert payload["cross_validations"]
    assert all(
        item["text_primitive_id"] in primitive_ids
        for item in payload["cross_validations"]
    )


def test_pdf_vector_numeric_text_is_not_used_for_automatic_calibration(tmp_path):
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(str(image_path), np.full((80, 120, 3), 255, dtype=np.uint8))
    line = RawLine("line-1", (10.0, 40.0), (110.0, 40.0), 1.0, (10, 40, 110, 40))
    vector_dimension = RawText(
        "pdf-dimension", "100", (50, 20, 70, 35), 0.0, 1.0,
        "text_pdfvector", parsed_value=100.0, semantic_role="dimension_value",
    )
    with (
        patch("primitive_ir_lib.run_image.extract_raw_geometry", return_value=RawGeometry(lines=[line])),
        patch("primitive_ir_lib.run_image.extract_text_tesseract", return_value=[]),
        pytest.raises(CalibrationCandidateUnavailableError),
    ):
        run(
            image_path=str(image_path), output_path=str(output_path),
            auto_calibrate=True, preset="default", ocr_rois=[(0, 0, 120, 80)],
            pdf_vector_texts=[vector_dimension],
        )


def test_run_image_passes_ocr_lang_override_to_tesseract(tmp_path):
    """run() phải truyền lang xuống extract_text_tesseract khi người dùng
    override qua --ocr-lang, thay vì luôn phụ thuộc default nội bộ."""
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(
        str(image_path),
        np.full((80, 140, 3), 255, dtype=np.uint8),
    )

    with patch(
        "primitive_ir_lib.run_image.extract_text_tesseract",
        return_value=[],
    ) as mock_extract:
        run(
            image_path=str(image_path),
            output_path=str(output_path),
            scale_mm_per_px=1.0,
            preset="default",
            ocr_rois=[(0, 0, 140, 80)],
            ocr_lang="eng",
        )

    _, kwargs = mock_extract.call_args
    assert kwargs["lang"] == "eng"


def test_registry_with_nonfinite_verified_scale_is_rejected_before_image_staging(tmp_path):
    image_path = tmp_path / "drawing.png"
    registry_path = tmp_path / "calibrations.json"
    image_path.write_bytes(b"synthetic owned image")
    add_record(registry_path, "fixture", image_path, 0.25, "Known synthetic reference")
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["records"][0]["scale_mm_per_px"] = float("inf")
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    argv = [
        "run_image", "--image", str(image_path), "--output", str(tmp_path / "ir.json"),
        "--calibration-registry", str(registry_path), "--calibration-id", "fixture",
    ]

    with (
        patch("sys.argv", argv),
        patch("primitive_ir_lib.run_image._configure_console_output"),
        patch("primitive_ir_lib.run_image.run") as stage_image,
        pytest.raises(SystemExit) as exc_info,
    ):
        main()

    assert exc_info.value.code == 2
    stage_image.assert_not_called()


@pytest.mark.parametrize("boolean_scale", [True, False], ids=["true", "false"])
def test_registry_with_boolean_verified_scale_is_rejected_before_image_staging(
    tmp_path, boolean_scale: bool,
):
    image_path = tmp_path / "drawing.png"
    registry_path = tmp_path / "calibrations.json"
    image_path.write_bytes(b"synthetic owned image")
    add_record(registry_path, "fixture", image_path, 0.25, "Known synthetic reference")
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["records"][0]["scale_mm_per_px"] = boolean_scale
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    argv = [
        "run_image", "--image", str(image_path), "--output", str(tmp_path / "ir.json"),
        "--calibration-registry", str(registry_path), "--calibration-id", "fixture",
    ]

    with (
        patch("sys.argv", argv),
        patch("primitive_ir_lib.run_image._configure_console_output"),
        patch("primitive_ir_lib.run_image.run") as stage_image,
        pytest.raises(SystemExit) as exc_info,
    ):
        main()

    assert exc_info.value.code == 2
    stage_image.assert_not_called()


def test_auto_candidate_stays_review_only_through_primitive_and_registry_outputs(tmp_path):
    image_path = tmp_path / "synthetic.png"
    output_path = tmp_path / "primitive_ir.json"
    registry_path = tmp_path / "calibrations.json"
    image = np.full((80, 240, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(image_path), image)
    line = RawLine(
        id="synthetic-dimension-line", p1_px=(20.0, 50.0), p2_px=(220.0, 50.0),
        confidence=1.0, bbox_px=(20.0, 50.0, 220.0, 50.0),
    )
    dimension = RawText(
        id="synthetic-dimension", content="100", bbox_px=(105, 30, 135, 45),
        rotation_deg=0.0, confidence=1.0, source="text_tesseract",
        parsed_value=100.0, semantic_role="dimension_value",
    )
    built_documents = []

    def capture_document(*args, **kwargs):
        document = assemble_document(*args, **kwargs)
        built_documents.append(document)
        return document

    with (
        patch(
            "primitive_ir_lib.run_image.extract_raw_geometry",
            return_value=RawGeometry(lines=[line]),
        ),
        patch(
            "primitive_ir_lib.run_image.extract_text_tesseract",
            return_value=[dimension],
        ),
        patch(
            "primitive_ir_lib.run_image.build_document",
            side_effect=capture_document,
        ),
    ):
        run(
            image_path=str(image_path), output_path=str(output_path),
            auto_calibrate=True, calibration_registry_path=registry_path,
            calibration_id="synthetic-auto", ocr_rois=[(0, 0, 240, 80)],
        )

    primitive_payload = json.loads(output_path.read_text(encoding="utf-8"))
    registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
    candidate = registry_payload["records"][0]
    assert primitive_payload["calibration"]["pixel_to_unit_scale"] == 0.5
    assert primitive_payload["calibration"]["status"] == "needs_verification"
    assert primitive_payload["calibration"]["source_sha256"] == candidate["sha256"]
    assert candidate["status"] == "needs_verification"
    assert candidate["scale_mm_per_px"] == 0.5
    with pytest.raises(ValueError, match="No verified calibration"):
        get_verified_scale(registry_path, "synthetic-auto", image_path)

    from semantic_ir_lib.io_utils import _primitive_ir_document_from_dict

    with pytest.raises(ValueError, match="needs_verification"):
        _primitive_ir_document_from_dict(primitive_payload)
    from dxf_builder_lib.builder import build_dxf

    assert len(built_documents) == 1
    with pytest.raises(ValueError, match="needs_verification"):
        build_dxf(built_documents[0], str(tmp_path / "candidate.dxf"))


if __name__ == "__main__":
    test_run_image_writes_valid_primitive_ir_with_manual_scale()
    print("1/1 test PASS")
