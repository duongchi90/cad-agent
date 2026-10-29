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
from primitive_ir_lib.geometry_extraction import RawGeometry, RawLine, RawPdfLine
from primitive_ir_lib.models import Calibration
from primitive_ir_lib.run_image import CalibrationCandidateUnavailableError, _title_block_roi, main, run
from primitive_ir_lib.text_extraction import RawText
from primitive_ir_lib.validator import validate_document
import primitive_ir_lib.run_image as run_image_module


def test_title_block_roi_includes_scale_label_above_lower_third():
    # Observed scale-label bounds in the frozen 6740x4768 Gunnerus render.
    x0, y0, x1, y1 = _title_block_roi(6740, 4768)
    scale_label_bbox = (6041, 2555, 6138, 2575)

    assert x0 <= scale_label_bbox[0]
    assert y0 <= scale_label_bbox[1]
    assert x1 >= scale_label_bbox[2]
    assert y1 >= scale_label_bbox[3]


def test_run_image_serializes_pdf_vector_lines_through_existing_primitive_owner(tmp_path):
    image_path = tmp_path / "page.png"
    output_path = tmp_path / "primitive_ir.json"
    image = np.full((80, 120, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(image_path), image)
    pdf_line = RawPdfLine(
        id="pdf-line-source-bound",
        p1_px=(10.0, 20.0),
        p2_px=(90.0, 20.0),
        confidence=1.0,
        bbox_px=(10.0, 20.0, 90.0, 20.0),
        source_pdf_sha256="a" * 64,
        source_page_index=0,
        source_transform=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        render_sha256="b" * 64,
        render_dpi=72,
        render_origin_px=(0, 0),
        source_layer="UNCLASSIFIED_SOURCE_LAYER",
        source_seqno=4,
        source_item_index=0,
    )

    with patch(
        "primitive_ir_lib.run_image.extract_raw_geometry",
        return_value=RawGeometry(),
    ):
        run(
            image_path=str(image_path),
            output_path=str(output_path),
            scale_mm_per_px=0.5,
            preset="default",
            pdf_vector_lines=[pdf_line],
        )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    pdf_lines = [
        primitive for primitive in payload["primitives"]
        if primitive["source"] == "geometry_pdfvector"
    ]
    assert len(pdf_lines) == 1
    assert pdf_lines[0]["type"] == "line"
    assert pdf_lines[0]["geometry"]["start"] == {"x": 5.0, "y": 30.0}
    assert pdf_lines[0]["geometry"]["end"] == {"x": 45.0, "y": 30.0}
    assert pdf_lines[0]["trace"]["source_pdf_sha256"] == "a" * 64
    assert pdf_lines[0]["trace"]["source_render_sha256"] == "b" * 64
    assert validate_document(payload) == []


def test_pdf_vector_lines_stay_out_of_raster_merge_calibration_and_cross_validation(
    tmp_path, monkeypatch
):
    image_path = tmp_path / "page.png"
    output_path = tmp_path / "primitive_ir.json"
    image = np.full((80, 120, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(image_path), image)
    raster_line = RawLine(
        id="raster-line",
        p1_px=(5.0, 5.0),
        p2_px=(30.0, 5.0),
        confidence=0.8,
        bbox_px=(5.0, 5.0, 30.0, 5.0),
    )
    pdf_line = RawPdfLine(
        id="pdf-line-source-bound",
        p1_px=(40.0, 20.0),
        p2_px=(90.0, 20.0),
        confidence=1.0,
        bbox_px=(40.0, 20.0, 90.0, 20.0),
        source_pdf_sha256="a" * 64,
        source_page_index=0,
        source_transform=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        render_sha256="b" * 64,
        render_dpi=72,
        render_origin_px=(0, 0),
        source_layer="UNCLASSIFIED_SOURCE_LAYER",
        source_seqno=4,
        source_item_index=0,
    )
    calibration_line_inputs = []
    merge_line_inputs = []
    cross_validation_line_inputs = []
    calibration = Calibration(
        unit="mm",
        pixel_to_unit_scale=0.5,
        origin_px=(0.0, float(image.shape[0])),
        method="manual_override",
    )

    monkeypatch.setattr(
        "primitive_ir_lib.run_image.extract_raw_geometry",
        lambda *_args, **_kwargs: RawGeometry(lines=[raster_line]),
    )
    monkeypatch.setattr(
        "primitive_ir_lib.run_image.detect_text_candidate_rois", lambda _image: []
    )
    monkeypatch.setattr(
        "primitive_ir_lib.run_image.auto_estimate_calibration",
        lambda texts, lines, height, unit: (
            calibration_line_inputs.extend(lines) or calibration
        ),
    )
    monkeypatch.setattr(
        "primitive_ir_lib.run_image.merge_collinear_lines",
        lambda lines, **_kwargs: (merge_line_inputs.extend(lines) or lines),
    )
    monkeypatch.setattr(
        "primitive_ir_lib.run_image.cross_validate",
        lambda _texts, lines, _calibration, **_kwargs: (
            cross_validation_line_inputs.extend(lines) or []
        ),
    )

    run(
        image_path=str(image_path),
        output_path=str(output_path),
        auto_calibrate=True,
        merge_lines=True,
        pdf_vector_lines=[pdf_line],
    )

    assert calibration_line_inputs == [raster_line]
    assert merge_line_inputs == [raster_line]
    assert cross_validation_line_inputs == [raster_line]
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    sources = [primitive["source"] for primitive in payload["primitives"]]
    assert sources.count("geometry_pdfvector") == 1
    assert sources.count("geometry_opencv") == 1
    assert validate_document(payload) == []


def test_pdf_source_path_raster_overlap_and_text_collision_are_refused():
    source = RawPdfLine(
        id="pdf-source",
        p1_px=(0.0, 0.0),
        p2_px=(100.0, 0.0),
        confidence=1.0,
        bbox_px=(0.0, 0.0, 100.0, 0.0),
        source_pdf_sha256="a" * 64,
        source_page_index=0,
        source_transform=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        render_sha256="b" * 64,
        render_dpi=72,
        render_origin_px=(0, 0),
        source_layer="SOURCE",
        source_seqno=4,
        source_item_index=0,
    )

    def raster_line(line_id, first, second):
        return RawLine(
            id=line_id,
            p1_px=first,
            p2_px=second,
            confidence=0.8,
            bbox_px=(
                min(first[0], second[0]),
                min(first[1], second[1]),
                max(first[0], second[0]),
                max(first[1], second[1]),
            ),
        )

    assert run_image_module._pdf_line_overlaps_raster(
        [source], [raster_line("coincident", (25.0, 0.0), (75.0, 0.0))], []
    )
    assert not run_image_module._pdf_line_overlaps_raster(
        [source], [raster_line("crossing", (50.0, -20.0), (50.0, 20.0))], []
    )
    assert not run_image_module._pdf_line_overlaps_raster(
        [source], [raster_line("parallel-separated", (0.0, 4.0), (100.0, 4.0))], []
    )
    assert run_image_module._pdf_line_overlaps_raster(
        [source], [raster_line("five-pixel-partial-overlap", (95.0, 0.0), (195.0, 0.0))], []
    )
    text = RawText(
        id="overlapping-text",
        content="GUNNERUS",
        bbox_px=(45, -5, 55, 5),
        rotation_deg=0.0,
        confidence=1.0,
        source="text_pdfvector",
    )
    assert run_image_module._pdf_line_overlaps_raster([source], [], [text])


def test_run_image_refuses_only_overlapping_item_from_compound_pdf_path(
    tmp_path, monkeypatch
):
    image_path = tmp_path / "page.png"
    output_path = tmp_path / "primitive_ir.json"
    image = np.full((200, 220, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(image_path), image)
    raster_line = RawLine(
        id="raster-overlap",
        p1_px=(95.0, 0.0),
        p2_px=(195.0, 0.0),
        confidence=0.8,
        bbox_px=(95.0, 0.0, 195.0, 0.0),
    )
    source_identity = {
        "source_pdf_sha256": "a" * 64,
        "source_page_index": 0,
        "source_transform": (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        "render_sha256": "b" * 64,
        "render_dpi": 72,
        "render_origin_px": (0, 0),
        "source_layer": "SOURCE",
        "source_seqno": 9,
    }
    overlapping_source_item = RawPdfLine(
        id="pdf-item-a",
        p1_px=(100.0, 0.0),
        p2_px=(0.0, 0.0),
        confidence=1.0,
        bbox_px=(0.0, 0.0, 100.0, 0.0),
        source_item_index=0,
        **source_identity,
    )
    independently_witnessed_sibling = RawPdfLine(
        id="pdf-item-b",
        p1_px=(0.0, 0.0),
        p2_px=(0.0, 50.0),
        confidence=1.0,
        bbox_px=(0.0, 0.0, 0.0, 50.0),
        source_item_index=1,
        **source_identity,
    )
    monkeypatch.setattr(
        "primitive_ir_lib.run_image.extract_raw_geometry",
        lambda *_args, **_kwargs: RawGeometry(lines=[raster_line]),
    )

    run(
        image_path=str(image_path),
        output_path=str(output_path),
        scale_mm_per_px=1.0,
        preset="default",
        pdf_vector_lines=[overlapping_source_item, independently_witnessed_sibling],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    pdf_lines = [
        primitive for primitive in payload["primitives"]
        if primitive["source"] == "geometry_pdfvector"
    ]
    assert [primitive["id"] for primitive in pdf_lines] == ["pdf-item-b"]
    assert sum(
        primitive["source"] == "geometry_opencv" and primitive["type"] == "line"
        for primitive in payload["primitives"]
    ) == 1
    assert validate_document(payload) == []

    from dxf_builder_lib.builder import build_dxf
    from dxf_builder_lib.reviewer import review_dxf
    from semantic_ir_lib.io_utils import load_primitive_ir_document

    build = build_dxf(
        load_primitive_ir_document(str(output_path)), str(tmp_path / "candidate.dxf")
    )
    review = review_dxf(build, strict_primitive_inventory=True)
    assert not build.skipped_primitive_ids
    assert review.passed is True


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
    different = RawText("ocr-3", "Ø14", (35, 10, 55, 20), 0.0, 0.9, "text_tesseract")
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
    ]


def test_run_image_excludes_conflicting_spans_but_keeps_unrelated_ocr_text(tmp_path):
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(str(image_path), np.full((80, 120, 3), 255, dtype=np.uint8))
    ocr_conflict = RawText(
        "ocr-conflict", "R7,50", (10, 10, 30, 20), 0.0, 0.9, "text_tesseract"
    )
    pdf_conflict = RawText(
        "pdf-conflict", "R7.50", (10, 10, 30, 20), 0.0, 1.0, "text_pdfvector"
    )
    agreeing_ocr_in_conflict_group = RawText(
        "ocr-agreeing-but-conflicted", "R7.50", (10, 10, 30, 20),
        0.0, 0.8, "text_tesseract",
    )
    unrelated_ocr = RawText(
        "ocr-unrelated", "NOTE", (50, 10, 75, 20), 0.0, 0.9, "text_tesseract"
    )

    with (
        patch("primitive_ir_lib.run_image.extract_raw_geometry", return_value=RawGeometry()),
        patch(
            "primitive_ir_lib.run_image.extract_text_tesseract",
            return_value=[ocr_conflict, agreeing_ocr_in_conflict_group, unrelated_ocr],
        ),
    ):
        run(
            image_path=str(image_path), output_path=str(output_path),
            scale_mm_per_px=1.0, preset="default", ocr_rois=[(0, 0, 120, 80)],
            pdf_vector_texts=[pdf_conflict],
        )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    text_primitives = [item for item in payload["primitives"] if item["type"] == "text"]
    assert [(item["id"], item["text_data"]["content"]) for item in text_primitives] == [
        ("ocr-unrelated", "NOTE")
    ]
    assert not payload["cross_validations"]


def test_run_image_does_not_calibrate_from_conflicting_ocr_dimension(tmp_path):
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(str(image_path), np.full((80, 120, 3), 255, dtype=np.uint8))
    line = RawLine(
        "dimension-line", (10.0, 40.0), (110.0, 40.0), 1.0,
        (10.0, 40.0, 110.0, 40.0),
    )
    ocr_dimension = RawText(
        "ocr-dimension", "100", (50, 20, 70, 35), 0.0, 0.9,
        "text_tesseract", parsed_value=100.0, semantic_role="dimension_value",
    )
    pdf_dimension = RawText(
        "pdf-dimension", "100.0", (50, 20, 70, 35), 0.0, 1.0,
        "text_pdfvector", parsed_value=100.0, semantic_role="dimension_value",
    )

    with (
        patch(
            "primitive_ir_lib.run_image.extract_raw_geometry",
            return_value=RawGeometry(lines=[line]),
        ),
        patch(
            "primitive_ir_lib.run_image.extract_text_tesseract",
            return_value=[ocr_dimension],
        ),
        pytest.raises(CalibrationCandidateUnavailableError),
    ):
        run(
            image_path=str(image_path), output_path=str(output_path),
            preset="default", ocr_rois=[(0, 0, 120, 80)], auto_calibrate=True,
            pdf_vector_texts=[pdf_dimension],
        )

    assert not output_path.exists()


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


@pytest.mark.parametrize("pdf_rotation", [5.0, 10.0, 180.0])
def test_run_image_rejects_same_span_text_with_conflicting_rotation(
    tmp_path, pdf_rotation
):
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(str(image_path), np.full((80, 120, 3), 255, dtype=np.uint8))
    ocr = RawText("ocr-1", "ROTATED", (10, 10, 80, 30), 0.0, 0.9, "text_tesseract")
    vector = RawText(
        "pdf-1", "ROTATED", (10, 10, 80, 30), pdf_rotation, 1.0, "text_pdfvector"
    )

    with (
        patch("primitive_ir_lib.run_image.extract_raw_geometry", return_value=RawGeometry()),
        patch("primitive_ir_lib.run_image.extract_text_tesseract", return_value=[ocr]),
        pytest.raises(ValueError, match=r"ocr-1.*0.*pdf-1") as error,
    ):
        run(
            image_path=str(image_path), output_path=str(output_path),
            scale_mm_per_px=1.0, preset="default", ocr_rois=[(0, 0, 120, 80)],
            pdf_vector_texts=[vector],
        )

    assert "rotation" in str(error.value).lower()
    assert "5" in str(error.value) or "10" in str(error.value) or "180" in str(error.value)
    assert not output_path.exists()


def test_run_image_deduplicates_equivalent_rotation_modulo_360(tmp_path):
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(str(image_path), np.full((80, 120, 3), 255, dtype=np.uint8))
    ocr = RawText("ocr-1", "ROTATED", (10, 10, 80, 30), 5.0, 0.9, "text_tesseract")
    vector = RawText(
        "pdf-1", "ROTATED", (10, 10, 80, 30), 365.0, 1.0, "text_pdfvector"
    )

    with (
        patch("primitive_ir_lib.run_image.extract_raw_geometry", return_value=RawGeometry()),
        patch("primitive_ir_lib.run_image.extract_text_tesseract", return_value=[ocr]),
    ):
        run(
            image_path=str(image_path), output_path=str(output_path),
            scale_mm_per_px=1.0, preset="default", ocr_rois=[(0, 0, 120, 80)],
            pdf_vector_texts=[vector],
        )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    text_primitives = [item for item in payload["primitives"] if item["type"] == "text"]
    assert len(text_primitives) == 1
    assert text_primitives[0]["id"] == "ocr-1"
    assert text_primitives[0]["text_data"]["rotation_deg"] == 5.0


@pytest.mark.parametrize("reverse_pdf_order", [False, True])
def test_run_image_rejects_ambiguous_repeated_pdf_spans(tmp_path, reverse_pdf_order):
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(str(image_path), np.full((80, 120, 3), 255, dtype=np.uint8))
    nested = [
        RawText("pdf-small", "R7,50", (10, 10, 68, 30), 0.0, 1.0, "text_pdfvector"),
        RawText("pdf-large", "R7,50", (10, 10, 92, 40), 0.0, 1.0, "text_pdfvector"),
    ]
    if reverse_pdf_order:
        nested.reverse()
    with (
        patch("primitive_ir_lib.run_image.extract_raw_geometry", return_value=RawGeometry()),
        patch("primitive_ir_lib.run_image.extract_text_tesseract", return_value=[]),
        pytest.raises(ValueError, match="PDF/PDF same-span identity ambiguous") as error,
    ):
        run(
            image_path=str(image_path), output_path=str(output_path),
            scale_mm_per_px=1.0, preset="default", pdf_vector_texts=nested,
        )
    assert "pdf-small" in str(error.value) and "pdf-large" in str(error.value)
    assert not output_path.exists()


@pytest.mark.parametrize("pdf_count,ocr_count", [(2, 1), (1, 2)])
def test_run_image_rejects_non_one_to_one_pdf_ocr_matches(
    tmp_path, pdf_count, ocr_count
):
    image_path = tmp_path / "drawing.png"
    output_path = tmp_path / "primitive_ir.json"
    assert cv2.imwrite(str(image_path), np.full((80, 120, 3), 255, dtype=np.uint8))
    if pdf_count == 2:
        pdf_boxes = [(10, 10, 50, 30), (70, 10, 110, 30)]
        ocr_boxes = [(10, 10, 110, 30)]
    else:
        pdf_boxes = [(10, 10, 110, 30)]
        ocr_boxes = [(10, 10, 50, 30), (70, 10, 110, 30)]
    pdf_texts = [
        RawText(f"pdf-{i}", "R7,50", pdf_boxes[i], 0.0, 1.0, "text_pdfvector")
        for i in range(pdf_count)
    ]
    ocr_texts = [
        RawText(f"ocr-{i}", "R7,50", ocr_boxes[i], 0.0, 0.9, "text_tesseract")
        for i in range(ocr_count)
    ]
    with (
        patch("primitive_ir_lib.run_image.extract_raw_geometry", return_value=RawGeometry()),
        patch(
            "primitive_ir_lib.run_image.extract_text_tesseract", return_value=ocr_texts
        ),
        pytest.raises(ValueError, match="ambiguous OCR/PDF span match"),
    ):
        run(
            image_path=str(image_path), output_path=str(output_path),
            scale_mm_per_px=1.0, preset="default", ocr_rois=[(0, 0, 120, 80)],
            pdf_vector_texts=pdf_texts,
        )
    assert not output_path.exists()


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


def test_source_layer_classification_requires_mutual_unique_full_span_match():
    classify = getattr(run_image_module, "_classify_pdf_layer_line_witnesses", None)
    assert callable(classify), "source-layer line matcher is missing"

    candidate = RawLine("candidate", (10.3, 20.1), (30.2, 20.1), 0.9, (10, 20, 31, 21))
    witness = RawLine("source", (10.0, 20.0), (30.0, 20.0), 1.0, (10, 20, 30, 20))

    result = classify([candidate], [(witness, "HIDDEN")])

    assert result == {"candidate": "HIDDEN"}
    assert candidate.p1_px == (10.3, 20.1)
    assert candidate.p2_px == (30.2, 20.1)


def test_source_layer_classification_rejects_partial_and_ambiguous_support():
    classify = getattr(run_image_module, "_classify_pdf_layer_line_witnesses", None)
    assert callable(classify), "source-layer line matcher is missing"

    partial = RawLine("span-gap", (10, 20), (30, 20), 0.9, (10, 20, 30, 20))
    first = RawLine("first-fragment", (10, 20), (18, 20), 1.0, (10, 20, 18, 20))
    second = RawLine("second-fragment", (22, 20), (30, 20), 1.0, (22, 20, 30, 20))

    ambiguous_line = RawLine("ambiguous", (10, 20), (30, 20), 0.9, (10, 20, 30, 20))
    hidden = RawLine("hidden", (10, 20), (30, 20), 1.0, (10, 20, 30, 20))
    center = RawLine("center", (10, 20), (30, 20), 1.0, (10, 20, 30, 20))

    partial_result = classify([partial], [(first, "HIDDEN"), (second, "HIDDEN")])
    ambiguous_result = classify(
        [ambiguous_line], [(hidden, "HIDDEN"), (center, "CENTERLINE")]
    )

    assert partial_result == {}
    assert ambiguous_result == {}


def test_verified_source_layer_classification_is_applied_to_line_primitive_only():
    raw_line = RawLine("source-line", (10, 20), (30, 20), 0.9, (10, 20, 30, 20))
    document = assemble_document(
        file_name="source.png",
        page_index=0,
        image_width_px=100,
        image_height_px=100,
        calibration=Calibration(
            unit="mm", pixel_to_unit_scale=0.5, origin_px=(0, 100),
            method="manual_override",
        ),
        raw_lines=[raw_line],
        raw_circles=[],
        raw_texts=[],
    )

    run_image_module._apply_pdf_source_layer_classifications(
        document, {"source-line": "CENTERLINE"}
    )

    assert document.primitives[0].layer == "CENTERLINE"
    assert document.primitives[0].geometry.start.x == pytest.approx(5.0)
    assert document.primitives[0].geometry.end.x == pytest.approx(15.0)


if __name__ == "__main__":
    test_run_image_writes_valid_primitive_ir_with_manual_scale()
    print("1/1 test PASS")
