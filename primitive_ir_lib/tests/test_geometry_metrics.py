from __future__ import annotations

import numpy as np
import pytest

from primitive_ir_lib.geometry_metrics import GeometryMetricError, compute_geometry_metrics
from primitive_ir_lib.tests.geometry_test_helpers import (
    rectangle_mask,
    single_component_mask,
    two_component_mask,
)


def test_identical_masks_have_identity_metrics() -> None:
    mask = rectangle_mask()
    metrics = compute_geometry_metrics(mask, mask.copy())
    assert metrics.silhouette_iou == 1.0
    assert metrics.chamfer_distance_normalized == 0.0
    assert metrics.hausdorff_p95_normalized == 0.0
    assert metrics.missing_edge_ratio == 0.0
    assert metrics.extra_edge_ratio == 0.0
    assert metrics.connected_component_difference == 0


def test_shifted_rectangle_reports_distance_and_centroid_offset() -> None:
    metrics = compute_geometry_metrics(rectangle_mask(), rectangle_mask(dx=10))
    assert metrics.silhouette_iou < 1.0
    assert metrics.centroid_offset_x_ratio > 0.0
    assert metrics.hausdorff_p95_normalized > 0.0


def test_missing_disconnected_feature_changes_components_and_edges() -> None:
    metrics = compute_geometry_metrics(two_component_mask(), single_component_mask())
    assert metrics.missing_edge_ratio > 0.0
    assert metrics.connected_component_difference == 1


def test_empty_mask_is_rejected() -> None:
    empty = np.zeros((64, 64), dtype=np.uint8)
    with pytest.raises(GeometryMetricError, match="empty"):
        compute_geometry_metrics(empty, rectangle_mask())


def test_color_masks_are_normalized_to_the_same_metrics() -> None:
    mask = rectangle_mask()
    color = np.repeat(mask[:, :, None], 3, axis=2)
    assert compute_geometry_metrics(mask, color).silhouette_iou == 1.0
