from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from primitive_ir_lib.dimension_observer import DimensionCluster, DimensionDisposition
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


def synthetic_leader_annotation() -> np.ndarray:
    image = np.full((180, 300, 3), 255, dtype=np.uint8)
    cv2.line(image, (42, 125), (155, 50), (0, 0, 0), 2)
    cv2.fillConvexPoly(
        image,
        np.array([[42, 125], [58, 114], [58, 136]], dtype=np.int32),
        (0, 0, 0),
    )
    cv2.putText(image, "4500", (165, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return image


def synthetic_diagonal_non_leader() -> np.ndarray:
    image = np.full((180, 300, 3), 255, dtype=np.uint8)
    cv2.line(image, (42, 125), (155, 50), (0, 0, 0), 2)
    return image


def synthetic_page_with_two_dimension_clusters_and_one_note() -> np.ndarray:
    page = np.full((420, 900, 3), 255, dtype=np.uint8)
    first = synthetic_horizontal_dimension()
    second = synthetic_horizontal_dimension()
    page[20:160, 20:440] = first
    page[190:330, 450:870] = second
    cv2.putText(page, "GHI CHU KY THUAT", (40, 390), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return page


def horizontal_dimension_cluster() -> DimensionCluster:
    return DimensionCluster(
        cluster_id="DIMCLUSTER-001",
        bbox_px=(0, 0, 420, 140),
        member_boxes=((160, 5, 260, 35),),
    )


def matching_horizontal_anchors() -> list[dict[str, object]]:
    return [
        {
            "type": "DATUM",
            "id": "FRONT_AXLE_CENTER",
            "view_id": "SIDE",
            "point_px": [80.0, 115.0],
            "confidence": 1.0,
        },
        {
            "type": "DATUM",
            "id": "REAR_AXLE_CENTER",
            "view_id": "SIDE",
            "point_px": [340.0, 115.0],
            "confidence": 1.0,
        },
    ]


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


def fake_ocr_unreadable(image_bgr: np.ndarray) -> list[RawText]:
    del image_bgr
    return [RawText(
        id="rawtext-unreadable",
        content="",
        bbox_px=(20, 15, 100, 55),
        rotation_deg=0.0,
        confidence=0.0,
        source="text_tesseract",
        parsed_value=None,
        semantic_role="unknown",
    )]


def not_a_dimension_disposition(cluster_id: str) -> DimensionDisposition:
    return DimensionDisposition(
        cluster_id=cluster_id,
        disposition="NOT_A_DIMENSION",
        observation=None,
        reasons=("text_not_dimension_like",),
    )


def write_synthetic_dimension_page(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), synthetic_horizontal_dimension()):
        raise OSError(f"Cannot write synthetic page: {path}")
    return path
