"""Regression tests for the real-image Phase 1 CLI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from primitive_ir_lib.run_image import run
from primitive_ir_lib.geometry_extraction import RawGeometry, RawLine
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


if __name__ == "__main__":
    test_run_image_writes_valid_primitive_ir_with_manual_scale()
    print("1/1 test PASS")
