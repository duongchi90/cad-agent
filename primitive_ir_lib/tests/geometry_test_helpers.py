from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

from primitive_ir_lib.geometry_alignment import AnchorPair, AlignmentResult
from primitive_ir_lib.geometry_metrics import GeometryMetrics


def rectangle_mask(*, dx: int = 0, dy: int = 0) -> np.ndarray:
    image = np.zeros((160, 240), dtype=np.uint8)
    cv2.rectangle(image, (40 + dx, 45 + dy), (190 + dx, 120 + dy), 255, -1)
    return image


def two_component_mask() -> np.ndarray:
    image = rectangle_mask()
    cv2.circle(image, (215, 35), 12, 255, -1)
    return image


def single_component_mask() -> np.ndarray:
    return rectangle_mask()


def circular_arc_mask() -> np.ndarray:
    image = np.zeros((180, 240), dtype=np.uint8)
    cv2.ellipse(image, (120, 120), (80, 60), 0, 190, 350, 255, 3)
    return image


def flattened_arc_mask() -> np.ndarray:
    image = np.zeros((180, 240), dtype=np.uint8)
    points = np.array(
        [[40, 120], [80, 95], [120, 88], [160, 95], [200, 120]],
        dtype=np.int32,
    )
    cv2.polylines(image, [points], False, 255, 3)
    return image


def identity_anchor_pairs() -> list[AnchorPair]:
    return [
        AnchorPair("A", (40.0, 45.0), (40.0, 45.0), "DATUM", 1.0),
        AnchorPair("B", (190.0, 120.0), (190.0, 120.0), "DATUM", 1.0),
        AnchorPair("C", (40.0, 120.0), (40.0, 120.0), "DATUM", 1.0),
    ]


def synthetic_similarity_anchor_pairs(
    *,
    translation: tuple[float, float],
    rotation_deg: float,
    scale: float,
) -> list[AnchorPair]:
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    output: list[AnchorPair] = []
    for item in identity_anchor_pairs():
        x, y = item.reference_px
        cad_x = scale * (cosine * x - sine * y) + translation[0]
        cad_y = scale * (sine * x + cosine * y) + translation[1]
        output.append(
            AnchorPair(
                item.anchor_id,
                item.reference_px,
                (cad_x, cad_y),
                item.authority,
                item.confidence,
            )
        )
    return output


def reflected_anchor_pairs() -> list[AnchorPair]:
    return [
        AnchorPair(
            item.anchor_id,
            item.reference_px,
            (-item.reference_px[0] + 240.0, item.reference_px[1]),
            item.authority,
            item.confidence,
        )
        for item in identity_anchor_pairs()
    ]


def nonuniform_three_anchor_pairs() -> list[AnchorPair]:
    return [
        AnchorPair(
            item.anchor_id,
            item.reference_px,
            (item.reference_px[0] * 1.4, item.reference_px[1] * 0.8),
            item.authority,
            item.confidence,
        )
        for item in identity_anchor_pairs()
    ]


def four_perspective_anchors() -> list[AnchorPair]:
    return [
        AnchorPair("A", (20.0, 20.0), (30.0, 25.0), "DATUM", 1.0),
        AnchorPair("B", (220.0, 20.0), (205.0, 12.0), "DATUM", 1.0),
        AnchorPair("C", (220.0, 140.0), (225.0, 150.0), "DATUM", 1.0),
        AnchorPair("D", (20.0, 140.0), (12.0, 132.0), "DATUM", 1.0),
    ]


def five_perspective_anchors() -> list[AnchorPair]:
    return four_perspective_anchors() + [
        AnchorPair("E", (120.0, 80.0), (120.0, 80.0), "DATUM", 1.0)
    ]


def four_collinear_anchors() -> list[AnchorPair]:
    return [
        AnchorPair(
            str(index),
            (float(index * 20), 20.0),
            (float(index * 22), 25.0),
            "DATUM",
            1.0,
        )
        for index in range(4)
    ]


def identity_alignment() -> AlignmentResult:
    return AlignmentResult(
        status="ALIGNED",
        method="VERIFIED_ANCHOR_SIMILARITY",
        matrix=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        anchor_ids=("A", "B", "C"),
        residual_rms_px=0.0,
        reasons=(),
    )


def identity_metrics() -> GeometryMetrics:
    return GeometryMetrics(
        silhouette_iou=1.0,
        chamfer_distance_normalized=0.0,
        hausdorff_p95_normalized=0.0,
        centroid_offset_x_ratio=0.0,
        centroid_offset_y_ratio=0.0,
        width_ratio_error=0.0,
        height_ratio_error=0.0,
        missing_edge_ratio=0.0,
        extra_edge_ratio=0.0,
        connected_component_difference=0,
    )


def good_metrics() -> GeometryMetrics:
    return GeometryMetrics(
        silhouette_iou=0.94,
        chamfer_distance_normalized=0.02,
        hausdorff_p95_normalized=0.03,
        centroid_offset_x_ratio=0.02,
        centroid_offset_y_ratio=0.02,
        width_ratio_error=0.02,
        height_ratio_error=0.02,
        missing_edge_ratio=0.01,
        extra_edge_ratio=0.01,
        connected_component_difference=0,
    )


def shifted_metrics() -> GeometryMetrics:
    return GeometryMetrics(
        silhouette_iou=0.80,
        chamfer_distance_normalized=0.08,
        hausdorff_p95_normalized=0.09,
        centroid_offset_x_ratio=0.08,
        centroid_offset_y_ratio=0.04,
        width_ratio_error=0.04,
        height_ratio_error=0.03,
        missing_edge_ratio=0.03,
        extra_edge_ratio=0.03,
        connected_component_difference=0,
    )


def nearly_same_metrics() -> GeometryMetrics:
    source = good_metrics()
    return GeometryMetrics(
        silhouette_iou=source.silhouette_iou + 1e-7,
        chamfer_distance_normalized=source.chamfer_distance_normalized,
        hausdorff_p95_normalized=source.hausdorff_p95_normalized,
        centroid_offset_x_ratio=source.centroid_offset_x_ratio,
        centroid_offset_y_ratio=source.centroid_offset_y_ratio,
        width_ratio_error=source.width_ratio_error,
        height_ratio_error=source.height_ratio_error,
        missing_edge_ratio=source.missing_edge_ratio,
        extra_edge_ratio=source.extra_edge_ratio,
        connected_component_difference=source.connected_component_difference,
    )


def write_mask(path: Path, mask: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), mask):
        raise OSError(f"Cannot write synthetic mask: {path}")
    return path


def write_anchor_file(path: Path, anchors: list[AnchorPair]) -> Path:
    payload = {
        "schema_version": "geometry-anchors-1.0",
        "anchors": [
            {
                "anchor_id": item.anchor_id,
                "reference_px": list(item.reference_px),
                "cad_px": list(item.cad_px),
                "authority": item.authority,
                "confidence": item.confidence,
            }
            for item in anchors
        ],
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path
