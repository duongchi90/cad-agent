"""Tests for drawing-image benchmark artifact creation."""

from pathlib import Path

import cv2
import numpy as np

from primitive_ir_lib.benchmark_image import benchmark_image


def test_benchmark_image_writes_geometry_and_annotation(tmp_path: Path):
    image_path = tmp_path / "mặt_cắt.png"
    image = np.full((100, 200, 3), 255, dtype=np.uint8)
    cv2.line(image, (10, 30), (180, 30), (0, 0, 0), 1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    image_path.write_bytes(encoded.tobytes())

    report = benchmark_image("fixture", image_path, tmp_path / "out", "default")

    page = report["pages"][0]
    assert page["image_width_px"] == 200
    assert (tmp_path / "out" / page["raw_geometry_json"]).is_file()
    assert (tmp_path / "out" / page["annotation_json"]).is_file()