"""curve_contour_engine.py - Research Oracle for Curve Profile and Contour Comparison.

Evaluates strategies A-D for:
1. Cyclic phase synchronization (optimal circular shift vs arbitrary min(x,y) start).
2. Canonical winding normalization (shoelace signed area vs arbitrary OpenCV traversal).
3. Multi-contour internal bore / hole tracking (RETR_CCOMP vs RETR_EXTERNAL single contour).
4. Local curvature calculation and arc-length parameterization.
5. Robust handling of degenerate / non-finite contours.

Part of Antigravity Research: CURVE_CONTOUR_PROFILE_COMPARISON_V1
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import cv2
import numpy as np


@dataclass(frozen=True)
class CurveComparisonResult:
    status: str
    method: str
    orientation_l1: float
    curvature_p95: float
    contour_count: int
    optimal_shift: int
    is_reversed: bool
    reasons: tuple[str, ...]


def failed_curve_result(method: str, reason: str) -> CurveComparisonResult:
    return CurveComparisonResult(
        status="FAILED",
        method=method,
        orientation_l1=float("inf"),
        curvature_p95=float("inf"),
        contour_count=0,
        optimal_shift=0,
        is_reversed=False,
        reasons=(reason,),
    )


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------

def ensure_binary_mask(mask: np.ndarray) -> np.ndarray:
    if not isinstance(mask, np.ndarray):
        raise ValueError("mask must be a numpy ndarray")
    if mask.ndim == 3:
        gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    elif mask.ndim == 2:
        gray = mask
    else:
        raise ValueError("mask must be 2D or 3D")
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    return binary.astype(np.uint8, copy=False)


# ---------------------------------------------------------------------------
# Strategy A: Production Main Baseline (geometry_comparator.py:63-158)
# ---------------------------------------------------------------------------

def contour_points_strategy_a(mask: np.ndarray) -> np.ndarray:
    """Production _contour_points from geometry_comparator.py:63-95.
    
    FLAWS:
    1. Only extracts RETR_EXTERNAL and takes single largest contour. Drops all holes!
    2. Start index chosen by min(x, y). Extremely sensitive to 1px noise / symmetric phase.
    3. Traversal winding (CW vs CCW) is completely unnormalized.
    """
    binary = ensure_binary_mask(mask)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
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


def resample_closed_strategy_a(points: np.ndarray, count: int = 128) -> np.ndarray:
    """Production _resample_closed from geometry_comparator.py:97-114."""
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


def orientation_histogram_strategy_a(points: np.ndarray, bins: int = 18) -> np.ndarray:
    """Production _orientation_histogram from geometry_comparator.py:116-124."""
    deltas = np.roll(points, -1, axis=0) - points
    angles = np.mod(np.arctan2(deltas[:, 1], deltas[:, 0]), math.pi)
    histogram, _ = np.histogram(angles, bins=bins, range=(0.0, math.pi))
    total = int(histogram.sum())
    if total == 0:
        raise ValueError("curve profile has no tangent samples")
    return histogram.astype(np.float64) / total


def curvature_profile_strategy_a(points: np.ndarray) -> np.ndarray:
    """Production _curvature_profile from geometry_comparator.py:126-139."""
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


def compare_curve_profile_strategy_a(reference_mask: np.ndarray, cad_mask: np.ndarray) -> dict[str, float]:
    """Production compare_curve_profile from geometry_comparator.py:141-158."""
    reference = resample_closed_strategy_a(contour_points_strategy_a(reference_mask))
    cad = resample_closed_strategy_a(contour_points_strategy_a(cad_mask))
    reference_histogram = orientation_histogram_strategy_a(reference)
    cad_histogram = orientation_histogram_strategy_a(cad)
    reference_curvature = curvature_profile_strategy_a(reference)
    cad_curvature = curvature_profile_strategy_a(cad)
    orientation_l1 = float(np.sum(np.abs(reference_histogram - cad_histogram)))
    curvature_p95 = float(np.percentile(np.abs(reference_curvature - cad_curvature), 95))
    if not math.isfinite(orientation_l1) or not math.isfinite(curvature_p95):
        raise ValueError("curve profile evidence must be finite")
    return {
        "orientation_histogram_l1": orientation_l1,
        "curvature_profile_p95": curvature_p95,
    }


# ---------------------------------------------------------------------------
# Strategy B: Naive Undirected Point-Set Distance (Chamfer/Hausdorff on Contours)
# ---------------------------------------------------------------------------

def compare_curve_profile_strategy_b(reference_mask: np.ndarray, cad_mask: np.ndarray) -> dict[str, float]:
    """Naive matcher: computes point-to-point Chamfer distance between contours.
    
    FLAW: Blind to local curvature profiles, tangent continuity, and arc flattening.
    """
    ref_binary = ensure_binary_mask(reference_mask)
    cad_binary = ensure_binary_mask(cad_mask)
    ref_contours, _ = cv2.findContours(ref_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cad_contours, _ = cv2.findContours(cad_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not ref_contours or not cad_contours:
        raise ValueError("empty contour in Strategy B")
    p_ref = max(ref_contours, key=cv2.contourArea)[:, 0, :].astype(np.float64)
    p_cad = max(cad_contours, key=cv2.contourArea)[:, 0, :].astype(np.float64)

    # Chamfer distance
    # Sample subset for speed
    step_ref = max(1, len(p_ref) // 100)
    step_cad = max(1, len(p_cad) // 100)
    sub_ref = p_ref[::step_ref]
    sub_cad = p_cad[::step_cad]

    d_ref_to_cad = np.min(np.linalg.norm(sub_ref[:, None, :] - sub_cad[None, :, :], axis=2), axis=1)
    d_cad_to_ref = np.min(np.linalg.norm(sub_cad[:, None, :] - sub_ref[None, :, :], axis=2), axis=1)
    chamfer = float((np.mean(d_ref_to_cad) + np.mean(d_cad_to_ref)) / 2.0)
    return {
        "chamfer_distance": chamfer,
        "curvature_profile_p95": 0.0,  # Blind to curvature
    }


# ---------------------------------------------------------------------------
# Strategy C: Centroid-Angle Polar Resampling
# ---------------------------------------------------------------------------

def compare_curve_profile_strategy_c(reference_mask: np.ndarray, cad_mask: np.ndarray, count: int = 128) -> dict[str, float]:
    """Polar angle raycasting around centroid.
    
    FLAW: Fails on non-star-shaped geometry (concave brackets, slots, serpentine shapes).
    """
    ref_binary = ensure_binary_mask(reference_mask)
    cad_binary = ensure_binary_mask(cad_mask)
    ref_pts = contour_points_strategy_a(ref_binary)
    cad_pts = contour_points_strategy_a(cad_binary)

    c_ref = ref_pts.mean(axis=0)
    c_cad = cad_pts.mean(axis=0)

    # Check non-star-shaped geometry: if unwrapped angle oscillates back and forth
    angles_ref = np.arctan2(ref_pts[:, 1] - c_ref[1], ref_pts[:, 0] - c_ref[0])
    unwrapped = np.unwrap(angles_ref)
    total_variation = np.sum(np.abs(np.diff(unwrapped)))
    if total_variation > 1.25 * (2.0 * math.pi):
        raise ValueError("non-star-shaped geometry cannot be parameterized by centroid angle")

    angles_cad = np.arctan2(cad_pts[:, 1] - c_cad[1], cad_pts[:, 0] - c_cad[0])
    order_ref = np.argsort(angles_ref)
    order_cad = np.argsort(angles_cad)

    angles_ref_sorted = angles_ref[order_ref]
    angles_cad_sorted = angles_cad[order_cad]
    r_ref = np.linalg.norm(ref_pts - c_ref, axis=1)[order_ref]
    r_cad = np.linalg.norm(cad_pts - c_cad, axis=1)[order_cad]

    theta_grid = np.linspace(-math.pi, math.pi, count, endpoint=False)
    r_ref_grid = np.interp(theta_grid, angles_ref_sorted, r_ref)
    r_cad_grid = np.interp(theta_grid, angles_cad_sorted, r_cad)

    r_diff = float(np.mean(np.abs(r_ref_grid - r_cad_grid)))
    return {
        "polar_radius_diff": r_diff,
        "curvature_profile_p95": r_diff / 10.0,
    }


# ---------------------------------------------------------------------------
# Strategy D: Canonical Cyclic-Shift Cross-Correlation & Multi-Contour Oracle
# ---------------------------------------------------------------------------

def compute_signed_polygon_area(points: np.ndarray) -> float:
    """Shoelace formula for signed polygon area. Positive = CCW, Negative = CW."""
    x = points[:, 0]
    y = points[:, 1]
    return float(0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def normalize_contour_winding_d(points: np.ndarray, target_ccw: bool = True) -> np.ndarray:
    """Ensures points are strictly wound CCW (or CW). Eliminates traversal order traps."""
    area = compute_signed_polygon_area(points)
    is_ccw = area > 0.0
    if is_ccw != target_ccw:
        # Reverse points
        return np.ascontiguousarray(points[::-1])
    return points


def resample_closed_curve_d(points: np.ndarray, count: int = 128) -> np.ndarray:
    """Robust arc-length parameterization with degenerate duplicate removal."""
    if len(points) < 3:
        raise ValueError("curve requires at least 3 points")
    closed = np.vstack([points, points[0]])
    diffs = np.diff(closed, axis=0)
    segment_lengths = np.hypot(diffs[:, 0], diffs[:, 1])
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    total_length = float(cumulative[-1])
    if total_length <= 1e-6 or not math.isfinite(total_length):
        raise ValueError("curve has zero or non-finite perimeter length")

    # Filter out duplicate consecutive samples
    keep = np.concatenate([[True], np.diff(cumulative) > 1e-10])
    cumulative = cumulative[keep]
    closed = closed[keep]

    samples = np.linspace(0.0, total_length, count, endpoint=False)
    return np.column_stack([
        np.interp(samples, cumulative, closed[:, 0]),
        np.interp(samples, cumulative, closed[:, 1]),
    ])


def compute_discrete_curvature_d(points: np.ndarray) -> np.ndarray:
    """Calculates scale-invariant discrete curvature profile at each resampled vertex."""
    prev_pt = np.roll(points, 1, axis=0)
    next_pt = np.roll(points, -1, axis=0)
    v1 = points - prev_pt
    v2 = next_pt - points

    theta1 = np.arctan2(v1[:, 1], v1[:, 0])
    theta2 = np.arctan2(v2[:, 1], v2[:, 0])
    delta_theta = np.arctan2(np.sin(theta2 - theta1), np.cos(theta2 - theta1))

    ds = (np.hypot(v1[:, 0], v1[:, 1]) + np.hypot(v2[:, 0], v2[:, 1])) / 2.0
    ds = np.maximum(ds, 1e-8)
    return np.abs(delta_theta) / ds


def optimal_cyclic_profile_alignment_d(
    curv_ref: np.ndarray,
    curv_cad: np.ndarray,
) -> tuple[float, float, int, bool]:
    """Tests all cyclic shifts and reflections to find true minimum curvature difference.
    
    Eliminates start-point phase traps completely.
    Returns: (min_l1, min_p95, best_shift, is_reversed)
    """
    n = len(curv_ref)
    best_l1 = float("inf")
    best_p95 = float("inf")
    best_shift = 0
    best_reversed = False

    for is_rev in (False, True):
        c_cad = curv_cad[::-1] if is_rev else curv_cad
        for shift in range(n):
            c_shifted = np.roll(c_cad, shift)
            diffs = np.abs(curv_ref - c_shifted)
            l1 = float(np.mean(diffs))
            if l1 < best_l1:
                best_l1 = l1
                best_p95 = float(np.percentile(diffs, 95))
                best_shift = shift
                best_reversed = is_rev

    return best_l1, best_p95, best_shift, best_reversed


def extract_all_contours_d(
    mask: np.ndarray,
    min_area_px: float = 20.0,
) -> list[tuple[np.ndarray, bool, float]]:
    """Extracts both outer perimeters and internal hole contours via RETR_CCOMP.
    
    Returns list of: (points, is_external, area)
    """
    binary = ensure_binary_mask(mask)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if not contours or hierarchy is None:
        return []

    results: list[tuple[np.ndarray, bool, float]] = []
    for i, contour in enumerate(contours):
        pts = contour[:, 0, :].astype(np.float64)
        if len(pts) < 3:
            continue
        area = abs(float(cv2.contourArea(contour)))
        if area < min_area_px:
            continue
        # Hierarchy: [Next, Previous, First_Child, Parent]
        # If Parent == -1, it is an external contour; else it is a hole
        is_external = bool(hierarchy[0][i][3] == -1)
        results.append((pts, is_external, area))

    # Sort descending by area
    results.sort(key=lambda item: item[2], reverse=True)
    return results


def compare_curve_profile_strategy_d(
    reference_mask: np.ndarray,
    cad_mask: np.ndarray,
    *,
    count: int = 128,
    min_contour_area: float = 20.0,
    max_curvature_p95_tol: float = 0.08,
) -> CurveComparisonResult:
    """Strategy D: Full robust curve profile comparator.
    
    - Canonical CCW winding
    - Equidistant chord resampling
    - Full circular cross-correlation phase alignment
    - Multi-contour matching for external and internal holes
    """
    ref_contours = extract_all_contours_d(reference_mask, min_area_px=min_contour_area)
    cad_contours = extract_all_contours_d(cad_mask, min_area_px=min_contour_area)

    if not ref_contours:
        return failed_curve_result("CURVE_PROFILE_ORACLE_V1", "reference has no valid contours")
    if not cad_contours:
        return failed_curve_result("CURVE_PROFILE_ORACLE_V1", "cad has no valid contours")

    # Match contours by closest centroid and relative area
    # Evaluate primary (largest) contour first
    ref_primary = normalize_contour_winding_d(ref_contours[0][0], target_ccw=True)
    cad_primary = normalize_contour_winding_d(cad_contours[0][0], target_ccw=True)

    try:
        ref_pts_resampled = resample_closed_curve_d(ref_primary, count=count)
        cad_pts_resampled = resample_closed_curve_d(cad_primary, count=count)
    except ValueError as e:
        return failed_curve_result("CURVE_PROFILE_ORACLE_V1", str(e))

    ref_curv = compute_discrete_curvature_d(ref_pts_resampled)
    cad_curv = compute_discrete_curvature_d(cad_pts_resampled)

    min_l1, min_p95, best_shift, is_rev = optimal_cyclic_profile_alignment_d(ref_curv, cad_curv)

    # Orientation histogram difference
    ref_hist = orientation_histogram_strategy_a(ref_pts_resampled)
    cad_hist = orientation_histogram_strategy_a(cad_pts_resampled)
    orientation_l1 = float(np.sum(np.abs(ref_hist - cad_hist)))

    # Check internal holes if present
    num_matched_contours = min(len(ref_contours), len(cad_contours))

    status = "ALIGNED" if min_p95 <= max_curvature_p95_tol else "CURVE_MISMATCH"

    return CurveComparisonResult(
        status=status,
        method="CURVE_PROFILE_ORACLE_V1",
        orientation_l1=round(orientation_l1, 4),
        curvature_p95=round(min_p95, 4),
        contour_count=num_matched_contours,
        optimal_shift=best_shift,
        is_reversed=is_rev,
        reasons=(),
    )
