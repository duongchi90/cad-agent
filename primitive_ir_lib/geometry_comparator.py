"""Deterministic comparison evidence built from controlled alignment."""

from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np

from primitive_ir_lib.geometry_alignment import AlignmentResult, warp_to_reference
from primitive_ir_lib.geometry_metrics import normalize_outline


@dataclass(frozen=True)
class ComparisonArtifacts:
    aligned_cad: np.ndarray
    overlay: np.ndarray
    missing_mask: np.ndarray
    extra_mask: np.ndarray
    absolute_difference: np.ndarray


def create_comparison_artifacts(
    reference_image: np.ndarray,
    cad_image: np.ndarray,
    alignment: AlignmentResult,
) -> ComparisonArtifacts:
    """Create deterministic overlay and directional difference evidence."""

    if not isinstance(reference_image, np.ndarray) or not isinstance(cad_image, np.ndarray):
        raise ValueError("reference_image and cad_image must be numpy arrays")
    if reference_image.ndim not in {2, 3} or cad_image.ndim not in {2, 3}:
        raise ValueError("reference_image and cad_image must be grayscale or color arrays")
    height, width = reference_image.shape[:2]
    aligned_cad = warp_to_reference(
        cad_image,
        alignment,
        output_size=(width, height),
        is_mask=False,
    )
    reference_mask = normalize_outline(reference_image)
    cad_mask = normalize_outline(aligned_cad)
    missing_mask = np.where((reference_mask > 0) & (cad_mask == 0), 255, 0).astype(np.uint8)
    extra_mask = np.where((cad_mask > 0) & (reference_mask == 0), 255, 0).astype(np.uint8)
    absolute_difference = cv2.absdiff(reference_mask, cad_mask)

    overlay = np.full((height, width, 3), 255, dtype=np.uint8)
    reference_foreground = reference_mask > 0
    cad_foreground = cad_mask > 0
    overlay[reference_foreground & ~cad_foreground] = (0, 0, 255)
    overlay[cad_foreground & ~reference_foreground] = (255, 255, 0)
    overlay[reference_foreground & cad_foreground] = (0, 255, 0)
    return ComparisonArtifacts(
        aligned_cad=aligned_cad,
        overlay=overlay,
        missing_mask=missing_mask,
        extra_mask=extra_mask,
        absolute_difference=absolute_difference,
    )


def _contour_points(mask: np.ndarray) -> np.ndarray:
    normalized = normalize_outline(mask)
    contours, _ = cv2.findContours(normalized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise ValueError("curve profile requires a non-empty contour")

    ranked: list[tuple[float, float, float, float, np.ndarray]] = []
    for contour in contours:
        points = contour[:, 0, :].astype(np.float64)
        if len(points) < 3:
            continue
        moments = cv2.moments(contour)
        if moments["m00"]:
            centroid_x = moments["m10"] / moments["m00"]
            centroid_y = moments["m01"] / moments["m00"]
        else:
            centroid_x, centroid_y = points.mean(axis=0)
        ranked.append(
            (
                -abs(float(cv2.contourArea(contour))),
                float(centroid_x),
                float(centroid_y),
                -float(cv2.arcLength(contour, True)),
                points,
            )
        )
    if not ranked:
        raise ValueError("curve profile requires a contour with at least three points")
    ranked.sort(key=lambda item: item[:4])
    points = ranked[0][4]
    start = min(range(len(points)), key=lambda index: (points[index, 0], points[index, 1]))
    return np.roll(points, -start, axis=0)


def _resample_closed(points: np.ndarray, count: int = 128) -> np.ndarray:
    closed = np.vstack([points, points[0]])
    segment_lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    total = float(cumulative[-1])
    if total <= 0.0 or not math.isfinite(total):
        raise ValueError("curve profile contour must have positive length")
    keep = np.concatenate([[True], np.diff(cumulative) > 1e-12])
    cumulative = cumulative[keep]
    closed = closed[keep]
    samples = np.linspace(0.0, total, count, endpoint=False)
    return np.column_stack(
        [
            np.interp(samples, cumulative, closed[:, axis])
            for axis in range(2)
        ]
    )


def _orientation_histogram(points: np.ndarray, bins: int = 18) -> np.ndarray:
    deltas = np.roll(points, -1, axis=0) - points
    angles = np.mod(np.arctan2(deltas[:, 1], deltas[:, 0]), math.pi)
    histogram, _ = np.histogram(angles, bins=bins, range=(0.0, math.pi))
    total = int(histogram.sum())
    if total == 0:
        raise ValueError("curve profile has no tangent samples")
    return histogram.astype(np.float64) / total


def _curvature_profile(points: np.ndarray) -> np.ndarray:
    previous = np.roll(points, 1, axis=0)
    following = np.roll(points, -1, axis=0)
    first = points - previous
    second = following - points
    first_angles = np.arctan2(first[:, 1], first[:, 0])
    second_angles = np.arctan2(second[:, 1], second[:, 0])
    angle_delta = np.arctan2(
        np.sin(second_angles - first_angles),
        np.cos(second_angles - first_angles),
    )
    segment_scale = (np.linalg.norm(first, axis=1) + np.linalg.norm(second, axis=1)) / 2.0
    return np.abs(angle_delta) / np.maximum(segment_scale, 1e-12)


def compare_curve_profile(reference_mask: np.ndarray, cad_mask: np.ndarray) -> dict[str, float]:
    """Return deterministic orientation and curvature differences for main contours."""

    reference = _resample_closed(_contour_points(reference_mask))
    cad = _resample_closed(_contour_points(cad_mask))
    reference_histogram = _orientation_histogram(reference)
    cad_histogram = _orientation_histogram(cad)
    reference_curvature = _curvature_profile(reference)
    cad_curvature = _curvature_profile(cad)
    orientation_l1 = float(np.sum(np.abs(reference_histogram - cad_histogram)))
    curvature_p95 = float(np.percentile(np.abs(reference_curvature - cad_curvature), 95))
    if not math.isfinite(orientation_l1) or not math.isfinite(curvature_p95):
        raise ValueError("curve profile evidence must be finite")
    return {
        "orientation_histogram_l1": orientation_l1,
        "curvature_profile_p95": curvature_p95,
    }


__all__ = [
    "ComparisonArtifacts",
    "compare_curve_profile",
    "create_comparison_artifacts",
]
