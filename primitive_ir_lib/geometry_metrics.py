"""Deterministic geometry metrics for aligned raster evidence."""

from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np


class GeometryMetricError(ValueError):
    """Raised when geometry metric inputs cannot produce finite evidence."""


@dataclass(frozen=True)
class GeometryMetrics:
    silhouette_iou: float
    chamfer_distance_normalized: float
    hausdorff_p95_normalized: float
    centroid_offset_x_ratio: float
    centroid_offset_y_ratio: float
    width_ratio_error: float
    height_ratio_error: float
    missing_edge_ratio: float
    extra_edge_ratio: float
    connected_component_difference: int


def _as_gray_uint8(image: np.ndarray) -> np.ndarray:
    try:
        array = np.asarray(image)
    except (TypeError, ValueError) as exc:
        raise GeometryMetricError("outline input must be an image array") from exc
    if array.ndim == 3:
        if array.shape[2] == 1:
            array = array[:, :, 0]
        elif array.shape[2] == 3:
            array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        elif array.shape[2] == 4:
            array = cv2.cvtColor(array, cv2.COLOR_BGRA2GRAY)
        else:
            raise GeometryMetricError("outline image must have one, three, or four channels")
    if array.ndim != 2 or array.size == 0:
        raise GeometryMetricError("outline image must be a non-empty two-dimensional array")
    if np.issubdtype(array.dtype, np.bool_):
        return array.astype(np.uint8) * 255
    if np.issubdtype(array.dtype, np.floating):
        if not np.isfinite(array).all():
            raise GeometryMetricError("outline image must contain finite values")
        if float(np.max(array)) <= 1.0 and float(np.min(array)) >= 0.0:
            array = array * 255.0
    elif not np.issubdtype(array.dtype, np.number):
        raise GeometryMetricError("outline image must contain numeric values")
    return np.clip(array, 0, 255).astype(np.uint8, copy=False)


def normalize_outline(image: np.ndarray) -> np.ndarray:
    """Return a deterministic, polarity-normalized foreground mask.

    The image border is treated as background evidence.  A nearly uniform
    black border means white foreground; a nearly uniform white border means
    black foreground.  Ambiguous borders fail closed instead of guessing.
    """

    gray = _as_gray_uint8(image)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    border = np.concatenate(
        (binary[0, :], binary[-1, :], binary[:, 0], binary[:, -1])
    )
    black_fraction = float(np.mean(border == 0))
    white_fraction = float(np.mean(border == 255))
    if black_fraction >= 0.98:
        return binary.astype(np.uint8, copy=False)
    if white_fraction >= 0.98:
        return cv2.bitwise_not(binary)
    raise GeometryMetricError("foreground polarity is ambiguous")


def _edge_map(mask: np.ndarray) -> np.ndarray:
    return cv2.Canny(mask, 50, 150, apertureSize=3, L2gradient=True)


def _distance_values(source_edge: np.ndarray, other_edge: np.ndarray) -> np.ndarray:
    other_background = cv2.bitwise_not(other_edge)
    distance = cv2.distanceTransform(other_background, cv2.DIST_L2, 3)
    values = distance[source_edge > 0]
    if values.size == 0:
        raise GeometryMetricError("edge sets must be non-empty")
    return values.astype(np.float64, copy=False)


def _finite_metric(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise GeometryMetricError(f"{name} must be finite")
    return result


def compute_geometry_metrics(reference_mask: np.ndarray, cad_mask: np.ndarray) -> GeometryMetrics:
    """Compute the ten deterministic VS-T0 geometry metrics."""

    reference = normalize_outline(reference_mask)
    cad = normalize_outline(cad_mask)
    if not np.any(reference) or not np.any(cad):
        raise GeometryMetricError("silhouettes must be non-empty")
    if reference.shape != cad.shape:
        raise GeometryMetricError("reference and CAD masks must have equal shapes")

    reference_edge = _edge_map(reference)
    cad_edge = _edge_map(cad)
    if not np.any(reference_edge) or not np.any(cad_edge):
        raise GeometryMetricError("edge sets must be non-empty")

    reference_foreground = reference > 0
    cad_foreground = cad > 0
    intersection = int(np.count_nonzero(reference_foreground & cad_foreground))
    union = int(np.count_nonzero(reference_foreground | cad_foreground))
    if union == 0:
        raise GeometryMetricError("silhouette union must be non-empty")
    silhouette_iou = intersection / union

    reference_to_cad = _distance_values(reference_edge, cad_edge)
    cad_to_reference = _distance_values(cad_edge, reference_edge)
    diagonal = math.hypot(reference.shape[1], reference.shape[0])
    if diagonal <= 0.0:
        raise GeometryMetricError("image diagonal must be positive")
    chamfer = (float(reference_to_cad.mean()) + float(cad_to_reference.mean())) / 2.0
    hausdorff_p95 = max(
        float(np.percentile(reference_to_cad, 95)),
        float(np.percentile(cad_to_reference, 95)),
    )

    reference_moments = cv2.moments(reference)
    cad_moments = cv2.moments(cad)
    if reference_moments["m00"] == 0.0 or cad_moments["m00"] == 0.0:
        raise GeometryMetricError("silhouettes must have measurable area")
    reference_centroid = (
        reference_moments["m10"] / reference_moments["m00"],
        reference_moments["m01"] / reference_moments["m00"],
    )
    cad_centroid = (
        cad_moments["m10"] / cad_moments["m00"],
        cad_moments["m01"] / cad_moments["m00"],
    )
    _, _, reference_width, reference_height = cv2.boundingRect(reference)
    _, _, cad_width, cad_height = cv2.boundingRect(cad)
    if reference_width <= 0 or reference_height <= 0:
        raise GeometryMetricError("reference silhouette bounds must be non-empty")

    tolerance_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    dilated_cad_edge = cv2.dilate(cad_edge, tolerance_kernel)
    dilated_reference_edge = cv2.dilate(reference_edge, tolerance_kernel)
    missing = (reference_edge > 0) & (dilated_cad_edge == 0)
    extra = (cad_edge > 0) & (dilated_reference_edge == 0)
    reference_edge_count = int(np.count_nonzero(reference_edge))
    cad_edge_count = int(np.count_nonzero(cad_edge))
    if reference_edge_count == 0 or cad_edge_count == 0:
        raise GeometryMetricError("edge sets must be non-empty")

    reference_components = int(cv2.connectedComponents(reference, connectivity=8)[0] - 1)
    cad_components = int(cv2.connectedComponents(cad, connectivity=8)[0] - 1)
    values = {
        "silhouette_iou": silhouette_iou,
        "chamfer_distance_normalized": chamfer / diagonal,
        "hausdorff_p95_normalized": hausdorff_p95 / diagonal,
        "centroid_offset_x_ratio": abs(reference_centroid[0] - cad_centroid[0])
        / max(reference_width, 1),
        "centroid_offset_y_ratio": abs(reference_centroid[1] - cad_centroid[1])
        / max(reference_height, 1),
        "width_ratio_error": abs(cad_width / reference_width - 1.0),
        "height_ratio_error": abs(cad_height / reference_height - 1.0),
        "missing_edge_ratio": int(np.count_nonzero(missing)) / reference_edge_count,
        "extra_edge_ratio": int(np.count_nonzero(extra)) / cad_edge_count,
    }
    finite_values = {name: _finite_metric(value, name) for name, value in values.items()}
    return GeometryMetrics(
        silhouette_iou=finite_values["silhouette_iou"],
        chamfer_distance_normalized=finite_values["chamfer_distance_normalized"],
        hausdorff_p95_normalized=finite_values["hausdorff_p95_normalized"],
        centroid_offset_x_ratio=finite_values["centroid_offset_x_ratio"],
        centroid_offset_y_ratio=finite_values["centroid_offset_y_ratio"],
        width_ratio_error=finite_values["width_ratio_error"],
        height_ratio_error=finite_values["height_ratio_error"],
        missing_edge_ratio=finite_values["missing_edge_ratio"],
        extra_edge_ratio=finite_values["extra_edge_ratio"],
        connected_component_difference=abs(reference_components - cad_components),
    )


__all__ = [
    "GeometryMetricError",
    "GeometryMetrics",
    "compute_geometry_metrics",
    "normalize_outline",
]
