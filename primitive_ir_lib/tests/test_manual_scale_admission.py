from __future__ import annotations

import math
import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from primitive_ir_lib.geometry_extraction import RawGeometry
from primitive_ir_lib.run_image import run


def _write_frozen_synthetic(path: Path) -> None:
    image = np.full((32, 48, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (8, 8), (39, 23), (0, 0, 0), 1)
    assert cv2.imwrite(str(path), image)


@pytest.mark.parametrize(
    "scale",
    [math.nan, math.inf, 0.0, -1.0],
    ids=["nan", "positive-infinity", "zero", "negative"],
)
def test_manual_scale_rejects_nonfinite_before_geometry_or_output(tmp_path: Path, scale: float) -> None:
    image_path = tmp_path / "frozen-synthetic.png"
    output_path = tmp_path / "should-not-exist.json"
    _write_frozen_synthetic(image_path)

    with patch("primitive_ir_lib.run_image.extract_raw_geometry") as acquire_geometry:
        with pytest.raises(ValueError, match="scale_mm_per_px"):
            run(
                image_path=str(image_path),
                output_path=str(output_path),
                scale_mm_per_px=scale,
                auto_calibrate=False,
                auto_ocr_roi=False,
                view_candidates_output_path=None,
                preset="default",
            )

    acquire_geometry.assert_not_called()
    assert not output_path.exists()


def test_manual_scale_rejects_boolean_type_control(tmp_path: Path) -> None:
    image_path = tmp_path / "frozen-synthetic.png"
    output_path = tmp_path / "should-not-exist.json"
    _write_frozen_synthetic(image_path)

    with patch("primitive_ir_lib.run_image.extract_raw_geometry") as acquire_geometry:
        with pytest.raises(ValueError, match="scale_mm_per_px"):
            run(
                image_path=str(image_path),
                output_path=str(output_path),
                scale_mm_per_px=True,
                auto_calibrate=False,
                auto_ocr_roi=False,
                view_candidates_output_path=None,
                preset="default",
            )

    acquire_geometry.assert_not_called()
    assert not output_path.exists()


def test_manual_scale_accepts_finite_positive_and_preserves_serialization(tmp_path: Path) -> None:
    image_path = tmp_path / "frozen-synthetic.png"
    output_path = tmp_path / "primitive-ir.json"
    _write_frozen_synthetic(image_path)

    with patch(
        "primitive_ir_lib.run_image.extract_raw_geometry", return_value=RawGeometry()
    ) as acquire_geometry:
        run(
            image_path=str(image_path),
            output_path=str(output_path),
            scale_mm_per_px=0.5,
            auto_calibrate=False,
            auto_ocr_roi=False,
            view_candidates_output_path=None,
            preset="default",
        )

    acquire_geometry.assert_called_once()
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["calibration"]["pixel_to_unit_scale"] == 0.5
    assert result["calibration"]["status"] == "verified"
