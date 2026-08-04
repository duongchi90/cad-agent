from __future__ import annotations

import cv2
import numpy as np
from dataclasses import replace

from primitive_ir_lib.geometry_comparator import (
    compare_curve_profile,
    compare_metric_trend,
    create_comparison_artifacts,
)
from primitive_ir_lib.tests.geometry_test_helpers import (
    circular_arc_mask,
    flattened_arc_mask,
    good_metrics,
    identity_alignment,
    identity_metrics,
    nearly_same_metrics,
    rectangle_mask,
    shifted_metrics,
    two_component_mask,
)


def test_artifacts_have_fixed_shapes_and_binary_masks() -> None:
    reference = cv2.cvtColor(rectangle_mask(), cv2.COLOR_GRAY2BGR)
    cad = reference.copy()
    artifacts = create_comparison_artifacts(reference, cad, identity_alignment())
    assert artifacts.aligned_cad.shape == reference.shape
    assert set(np.unique(artifacts.missing_mask)) <= {0, 255}
    assert set(np.unique(artifacts.extra_mask)) <= {0, 255}
    assert set(np.unique(artifacts.absolute_difference)) <= {0, 255}


def test_missing_and_extra_masks_are_directional() -> None:
    reference = cv2.cvtColor(two_component_mask(), cv2.COLOR_GRAY2BGR)
    cad_mask = rectangle_mask(dx=5)
    cad = cv2.cvtColor(cad_mask, cv2.COLOR_GRAY2BGR)
    artifacts = create_comparison_artifacts(reference, cad, identity_alignment())
    assert np.count_nonzero(artifacts.missing_mask) > 0
    assert np.count_nonzero(artifacts.extra_mask) > 0


def test_curve_profile_detects_arc_flattening() -> None:
    evidence = compare_curve_profile(circular_arc_mask(), flattened_arc_mask())
    assert evidence["orientation_histogram_l1"] > 0.0
    assert evidence["curvature_profile_p95"] > 0.0


def test_first_candidate_is_baseline() -> None:
    assert compare_metric_trend(identity_metrics(), None) == "BASELINE"


def test_missing_feature_regression_cannot_be_averaged_away() -> None:
    previous = good_metrics()
    current = replace(previous, silhouette_iou=0.99, missing_edge_ratio=0.2)
    assert compare_metric_trend(current, previous) == "REGRESSED"


def test_nonregressing_improvement_is_improved() -> None:
    previous = shifted_metrics()
    current = replace(previous, silhouette_iou=0.95, centroid_offset_x_ratio=0.01)
    assert compare_metric_trend(current, previous) == "IMPROVED"


def test_changes_within_epsilon_are_unchanged() -> None:
    assert compare_metric_trend(
        good_metrics(), nearly_same_metrics(), epsilon=1e-5
    ) == "UNCHANGED"
