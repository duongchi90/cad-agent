# VS-T1 / VS-T2 Test Fixture Contracts

This file is an authoritative companion to:

- `2026-08-04-vs-t1-dimension-observer.md`
- `2026-08-04-vs-t2-geometry-comparator.md`

Every helper referenced by those plans must use the signatures and deterministic data below. A worker may add more helpers, but it must not silently change these fixtures to make a failing production algorithm pass.

## VS-T1 fixtures

Add the following to `primitive_ir_lib/tests/dimension_test_helpers.py` as the relevant production types become available:

```python
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from primitive_ir_lib.dimension_observer import (
    DimensionCluster,
    DimensionDisposition,
)
from primitive_ir_lib.text_extraction import RawText


def synthetic_horizontal_dimension() -> np.ndarray:
    image = np.full((140, 420, 3), 255, dtype=np.uint8)
    cv2.line(image, (80, 35), (340, 35), (0, 0, 0), 2)
    cv2.line(image, (80, 35), (80, 115), (0, 0, 0), 2)
    cv2.line(image, (340, 35), (340, 115), (0, 0, 0), 2)
    cv2.fillConvexPoly(
        image,
        np.array([[80, 35], [94, 29], [94, 41]], dtype=np.int32),
        (0, 0, 0),
    )
    cv2.fillConvexPoly(
        image,
        np.array([[340, 35], [326, 29], [326, 41]], dtype=np.int32),
        (0, 0, 0),
    )
    cv2.putText(
        image,
        "4500",
        (170, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2,
    )
    return image


def synthetic_isolated_number_crop() -> np.ndarray:
    image = np.full((80, 180, 3), 255, dtype=np.uint8)
    cv2.putText(
        image,
        "4500",
        (25, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
    )
    return image


def synthetic_page_with_two_dimension_clusters_and_one_note() -> np.ndarray:
    page = np.full((420, 900, 3), 255, dtype=np.uint8)
    first = synthetic_horizontal_dimension()
    second = synthetic_horizontal_dimension()
    page[20:160, 20:440] = first
    page[190:330, 450:870] = second
    cv2.putText(
        page,
        "GHI CHU KY THUAT",
        (40, 390),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2,
    )
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
    return [
        RawText(
            id="rawtext-4500",
            content="4500",
            bbox_px=(20, 15, 100, 55),
            rotation_deg=0.0,
            confidence=0.99,
            source="text_tesseract",
            parsed_value=4500.0,
            semantic_role="dimension_value",
        )
    ]


def fake_ocr_unreadable(image_bgr: np.ndarray) -> list[RawText]:
    del image_bgr
    return [
        RawText(
            id="rawtext-unreadable",
            content="",
            bbox_px=(20, 15, 100, 55),
            rotation_deg=0.0,
            confidence=0.0,
            source="text_tesseract",
            parsed_value=None,
            semantic_role="unknown",
        )
    ]


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
```

Add this exact helper to `tests/visual_supervisor_fixtures.py` during VS-T1 Task 1:

```python
def valid_dimension_observer_evidence() -> dict[str, object]:
    return {
        "raw_text_candidates": ["4500"],
        "symbol_text": None,
        "tolerance": {
            "mode": "NONE",
            "upper": None,
            "lower": None,
            "unit": "mm",
        },
        "extension_geometry": {
            "dimension_line": [[80.0, 35.0], [340.0, 35.0]],
            "extension_lines": [
                [[80.0, 35.0], [80.0, 115.0]],
                [[340.0, 35.0], [340.0, 115.0]],
            ],
            "arrow_points": [[80.0, 35.0], [340.0, 35.0]],
        },
        "attachment_candidates": [
            {
                "from_ref": {"type": "DATUM", "id": "FRONT_AXLE_CENTER"},
                "to_ref": {"type": "DATUM", "id": "REAR_AXLE_CENTER"},
                "confidence": 0.94,
                "evidence": ["extension-line-0", "extension-line-1"],
            }
        ],
        "provenance": {
            "observer_version": "dimension-observer-1.0",
            "ocr_engine": "tesseract-5.4.0.20240606",
            "observation_sha256": "9" * 64,
        },
    }
```

The optional observer profile consumed by `profile_path` is a closed JSON object:

```json
{
  "schema_version": "dimension-observer-profile-1.0",
  "default_unit": "mm",
  "clusters": {
    "DIMCLUSTER-001": {
      "role": "REFERENCE",
      "critical": true,
      "blocker_scope": ["SIDE-CABIN"]
    }
  }
}
```

Only the roles `DRIVING`, `REFERENCE`, and `DERIVED` are accepted in this profile. Missing cluster entries do not inherit a role and remain `AMBIGUOUS`.

## VS-T2 fixtures

Add the following to `primitive_ir_lib/tests/geometry_test_helpers.py`:

```python
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
        AnchorPair(str(index), (float(index * 20), 20.0), (float(index * 22), 25.0), "DATUM", 1.0)
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
```

`geometry-anchors-1.0` is closed. Valid `authority` values are `DATUM`, `DRIVING_DIMENSION`, `STABLE_ENTITY`, and `VISUAL_FEATURE`; confidence is finite in `[0, 1]`. A comparison runner validates this file before alignment.
