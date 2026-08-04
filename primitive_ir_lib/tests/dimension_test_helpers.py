from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from primitive_ir_lib.text_extraction import RawText


def synthetic_horizontal_dimension() -> np.ndarray:
    image = np.full((140, 420, 3), 255, dtype=np.uint8)
    cv2.line(image, (80, 35), (340, 35), (0, 0, 0), 2)
    cv2.line(image, (80, 35), (80, 115), (0, 0, 0), 2)
    cv2.line(image, (340, 35), (340, 115), (0, 0, 0), 2)
    cv2.fillConvexPoly(image, np.array([[80, 35], [94, 29], [94, 41]], dtype=np.int32), (0, 0, 0))
    cv2.fillConvexPoly(image, np.array([[340, 35], [326, 29], [326, 41]], dtype=np.int32), (0, 0, 0))
    cv2.putText(image, "4500", (170, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return image


def synthetic_isolated_number_crop() -> np.ndarray:
    image = np.full((80, 180, 3), 255, dtype=np.uint8)
    cv2.putText(image, "4500", (25, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    return image


def fake_ocr_4500(image_bgr: np.ndarray) -> list[RawText]:
    del image_bgr
    return [RawText(
        id="rawtext-4500",
        content="4500",
        bbox_px=(20, 15, 100, 55),
        rotation_deg=0.0,
        confidence=0.99,
        source="text_tesseract",
        parsed_value=4500.0,
        semantic_role="dimension_value",
    )]


def write_synthetic_dimension_page(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), synthetic_horizontal_dimension()):
        raise OSError(f"Cannot write synthetic page: {path}")
    return path
