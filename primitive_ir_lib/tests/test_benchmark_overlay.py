"""Tests for visual benchmark overlay generation."""

import json
from pathlib import Path

import cv2
import numpy as np

from primitive_ir_lib.benchmark_overlay import render_overlay


def test_render_overlay_draws_prediction_and_annotation(tmp_path: Path):
    image_path = tmp_path / "page.png"
    prediction_path = tmp_path / "prediction.json"
    annotation_path = tmp_path / "annotation.json"
    output_path = tmp_path / "overlay.png"
    cv2.imwrite(str(image_path), np.full((30, 40, 3), 255, dtype=np.uint8))
    prediction_path.write_text(json.dumps({"lines": [{"p1_px": [2, 5], "p2_px": [35, 5]}]}), encoding="utf-8")
    annotation_path.write_text(json.dumps({"expected_lines": [{"p1_px": [2, 15], "p2_px": [35, 15]}]}), encoding="utf-8")

    result = render_overlay(image_path, prediction_path, output_path, annotation_path)

    assert result["predicted_lines"] == 1
    assert result["expected_lines"] == 1
    image = cv2.imread(str(output_path))
    assert image is not None
    assert image[5, 10, 2] > image[5, 10, 1]  # red prediction
    assert image[15, 10, 1] > image[15, 10, 2]  # green ground truth

def test_render_overlay_filters_short_predictions(tmp_path: Path):
    image_path = tmp_path / "page.png"
    prediction_path = tmp_path / "prediction.json"
    output_path = tmp_path / "overlay.png"
    cv2.imwrite(str(image_path), np.full((20, 40, 3), 255, dtype=np.uint8))
    prediction_path.write_text(json.dumps({"lines": [
        {"p1_px": [2, 5], "p2_px": [5, 5]},
        {"p1_px": [2, 15], "p2_px": [35, 15]},
    ]}), encoding="utf-8")

    result = render_overlay(image_path, prediction_path, output_path, min_length_px=10)

    assert result["predicted_lines"] == 1