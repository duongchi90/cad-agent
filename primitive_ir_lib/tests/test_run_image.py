"""Regression tests for the real-image Phase 1 CLI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cv2
import numpy as np

from primitive_ir_lib.run_image import run
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


if __name__ == "__main__":
    test_run_image_writes_valid_primitive_ir_with_manual_scale()
    print("1/1 test PASS")
