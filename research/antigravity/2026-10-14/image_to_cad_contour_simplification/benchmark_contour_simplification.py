"""
Benchmark and empirical evaluation of image-to-CAD contour simplification algorithms.

Compares:
1. Baseline: Unsimplified pixel contour (cv2.CHAIN_APPROX_NONE)
2. Ramer-Douglas-Peucker (RDP / OpenCV approxPolyDP) at varying epsilon (absolute and relative)
3. Visvalingam-Whyatt (VW) area-based simplification at varying area thresholds

Evaluates across 7 canonical engineering contour fixtures:
1. Long straight edges with raster staircase
2. Sharp acute and oblique corners
3. Smooth circular arcs
4. Tiny mechanical notches (keyways)
5. Small holes (pin holes)
6. Noisy raster staircase edges (dense multi-angle aliasing)
7. Mixed straight/curved closed mechanical profile (stepped shaft with fillet and notch)

Measures:
- POINT_COUNT_REDUCTION (%)
- HAUSDORFF_ERROR (pixels)
- AREA_ERROR (%)
- PERIMETER_ERROR (%)
- CORNER_SURVIVAL (%)
- SMALL_FEATURE_SURVIVAL (boolean)
- CLOSED_TOPOLOGY_PRESERVED (boolean)
"""

from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple, Dict, Any

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Clean-Room Visvalingam-Whyatt Implementation
# ---------------------------------------------------------------------------

def triangle_area(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
    """Calculate the signed/absolute area of triangle (p1, p2, p3)."""
    return 0.5 * abs(p1[0] * (p2[1] - p3[1]) + p2[0] * (p3[1] - p1[1]) + p3[0] * (p1[1] - p2[1]))


def visvalingam_whyatt_closed(points: np.ndarray, min_area_threshold: float) -> np.ndarray:
    """
    Visvalingam-Whyatt simplification for closed 2D polygons.
    Points: (N, 2) numpy array.
    Repeatedly removes vertex with minimum effective area until all remaining
    effective areas >= min_area_threshold, or only 3 vertices remain.
    """
    n = len(points)
    if n <= 3:
        return points.copy()

    # Doubly linked list of active vertex indices
    prev_idx = [(i - 1) % n for i in range(n)]
    next_idx = [(i + 1) % n for i in range(n)]
    active = [True] * n

    # Compute initial triangle areas
    heap = []
    entry_finder = {}
    for i in range(n):
        area = triangle_area(points[prev_idx[i]], points[i], points[next_idx[i]])
        entry = [area, i]
        entry_finder[i] = entry
        heapq.heappush(heap, entry)

    remaining_count = n
    while heap and remaining_count > 3:
        area, i = heapq.heappop(heap)
        if not active[i]:
            continue
        if area >= min_area_threshold:
            # All remaining vertices have effective area >= threshold
            # Put back and stop
            heapq.heappush(heap, [area, i])
            break

        # Remove vertex i
        active[i] = False
        remaining_count -= 1
        p = prev_idx[i]
        nxt = next_idx[i]
        next_idx[p] = nxt
        prev_idx[nxt] = p

        # Recalculate areas for neighbors p and nxt
        # Note: in standard Visvalingam, an area is updated as max(computed, current_min_area)
        # to ensure monotonic hierarchy, but here we use direct effective area for simplification
        area_p = triangle_area(points[prev_idx[p]], points[p], points[next_idx[p]])
        new_entry_p = [area_p, p]
        entry_finder[p] = new_entry_p
        heapq.heappush(heap, new_entry_p)

        area_nxt = triangle_area(points[prev_idx[nxt]], points[nxt], points[next_idx[nxt]])
        new_entry_nxt = [area_nxt, nxt]
        entry_finder[nxt] = new_entry_nxt
        heapq.heappush(heap, new_entry_nxt)

    # Collect surviving vertices in order
    survivors = []
    # Find first active index
    start_idx = 0
    while start_idx < n and not active[start_idx]:
        start_idx += 1
    if start_idx == n:
        return points[:3].copy()

    curr = start_idx
    while True:
        survivors.append(points[curr])
        curr = next_idx[curr]
        if curr == start_idx:
            break

    return np.array(survivors, dtype=np.float64)


# ---------------------------------------------------------------------------
# Metrics Computation
# ---------------------------------------------------------------------------

def point_to_segment_distance(pt: np.ndarray, s1: np.ndarray, s2: np.ndarray) -> float:
    """Perpendicular Euclidean distance from point pt to line segment s1-s2."""
    v = s2 - s1
    L2 = np.dot(v, v)
    if L2 == 0:
        return float(np.linalg.norm(pt - s1))
    t = max(0.0, min(1.0, np.dot(pt - s1, v) / L2))
    projection = s1 + t * v
    return float(np.linalg.norm(pt - projection))


def polygon_hausdorff_distance(poly_orig: np.ndarray, poly_simp: np.ndarray) -> float:
    """
    Compute symmetric Hausdorff distance between original contour points
    and simplified polygon boundary (composed of segments).
    """
    # 1. Directed distance: orig points to simp segments
    n_simp = len(poly_simp)
    max_d_orig_to_simp = 0.0
    for pt in poly_orig:
        min_d = min(
            point_to_segment_distance(pt, poly_simp[i], poly_simp[(i + 1) % n_simp])
            for i in range(n_simp)
        )
        if min_d > max_d_orig_to_simp:
            max_d_orig_to_simp = min_d

    # 2. Directed distance: simp vertices to orig segments
    n_orig = len(poly_orig)
    max_d_simp_to_orig = 0.0
    for pt in poly_simp:
        min_d = min(
            point_to_segment_distance(pt, poly_orig[i], poly_orig[(i + 1) % n_orig])
            for i in range(n_orig)
        )
        if min_d > max_d_simp_to_orig:
            max_d_simp_to_orig = min_d

    return max(max_d_orig_to_simp, max_d_simp_to_orig)


def polygon_area(points: np.ndarray) -> float:
    """Shoelace formula for polygon area."""
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def polygon_perimeter(points: np.ndarray) -> float:
    """Perimeter of closed polygon."""
    return float(np.sum(np.linalg.norm(points - np.roll(points, -1, axis=0), axis=1)))


def is_simple_polygon(points: np.ndarray) -> bool:
    """
    Verify if closed polygon has >= 3 vertices and no self-intersecting non-adjacent segments.
    """
    n = len(points)
    if n < 3:
        return False

    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

    def intersect(A, B, C, D):
        return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

    for i in range(n):
        s1_a, s1_b = points[i], points[(i + 1) % n]
        for j in range(i + 2, n):
            if (i == 0 and j == n - 1):
                continue
            s2_a, s2_b = points[j], points[(j + 1) % n]
            if intersect(s1_a, s1_b, s2_a, s2_b):
                return False
    return True


# ---------------------------------------------------------------------------
# Synthetic Fixture Generators
# ---------------------------------------------------------------------------

@dataclass
class Fixture:
    name: str
    description: str
    raw_contour: np.ndarray
    ground_truth_corners: List[Tuple[float, float]]
    notch_bounding_box: Tuple[float, float, float, float] | None = None  # (xmin, ymin, xmax, ymax)


def make_canvas(w: int = 600, h: int = 600) -> np.ndarray:
    return np.zeros((h, w), dtype=np.uint8)


def extract_primary_contour(canvas: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(canvas, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise ValueError("No contour found on canvas")
    c = max(contours, key=cv2.contourArea)
    return c[:, 0, :].astype(np.float64)


def create_fixture_1_long_straight_edges() -> Fixture:
    """Fixture 1: 400x200 rectangle rotated by 15 deg creating long staircase edges."""
    canvas = make_canvas(600, 600)
    center = (300, 300)
    size = (400, 200)
    angle = 15.0
    rect = (center, size, angle)
    box = cv2.boxPoints(rect)
    cv2.fillPoly(canvas, [np.int32(box)], 255)
    contour = extract_primary_contour(canvas)
    corners = [tuple(p) for p in box]
    return Fixture(
        name="fixture_1_long_straight_edges",
        description="Rotated 400x200 rectangle (15 deg) with long raster staircase edges",
        raw_contour=contour,
        ground_truth_corners=corners,
    )


def create_fixture_2_sharp_corners() -> Fixture:
    """Fixture 2: Chevron / Arrow profile with 30, 45, 90, 135 deg sharp corners."""
    canvas = make_canvas(600, 600)
    pts = np.array([
        [100, 150],
        [300, 100],  # 30 deg sharp apex
        [500, 150],
        [400, 350],  # 90 deg corner
        [300, 250],  # 45 deg re-entrant notch corner
        [200, 350],  # 90 deg corner
    ], dtype=np.int32)
    cv2.fillPoly(canvas, [pts], 255)
    contour = extract_primary_contour(canvas)
    corners = [tuple(p) for p in pts.astype(np.float64)]
    return Fixture(
        name="fixture_2_sharp_corners",
        description="Chevron profile with sharp acute (30 deg), right (90 deg), and obtuse corners",
        raw_contour=contour,
        ground_truth_corners=corners,
    )


def create_fixture_3_circular_arcs() -> Fixture:
    """Fixture 3: Smooth circular disk of R=75 px on raster grid."""
    canvas = make_canvas(600, 600)
    cv2.circle(canvas, (300, 300), 75, 255, -1)
    contour = extract_primary_contour(canvas)
    return Fixture(
        name="fixture_3_circular_arcs",
        description="Circular arc disk (R=75 px) evaluating polygonization and chord flattening error",
        raw_contour=contour,
        ground_truth_corners=[],  # No sharp corners
    )


def create_fixture_4_tiny_notch() -> Fixture:
    """Fixture 4: 250x150 rectangular block with a 6x8 px rectangular keyway notch."""
    canvas = make_canvas(600, 600)
    # Base rectangle: (175, 200) to (425, 350)
    cv2.rectangle(canvas, (175, 200), (425, 350), 255, -1)
    # Carve out 6x8 px notch at top center (300, 200) -> [297..303, 200..208]
    cv2.rectangle(canvas, (297, 200), (303, 208), 0, -1)
    contour = extract_primary_contour(canvas)
    corners = [
        (175.0, 200.0),
        (297.0, 200.0), (297.0, 208.0), (303.0, 208.0), (303.0, 200.0),
        (425.0, 200.0),
        (425.0, 350.0),
        (175.0, 350.0),
    ]
    return Fixture(
        name="fixture_4_tiny_notch",
        description="250x150 block with 6x8 px keyway notch testing small feature survival",
        raw_contour=contour,
        ground_truth_corners=corners,
        notch_bounding_box=(297.0, 200.0, 303.0, 208.0),
    )


def create_fixture_5_small_hole() -> Fixture:
    """Fixture 5: Small pin hole contour of R=5 px (10 px diameter)."""
    canvas = make_canvas(200, 200)
    cv2.circle(canvas, (100, 100), 5, 255, -1)
    contour = extract_primary_contour(canvas)
    return Fixture(
        name="fixture_5_small_hole",
        description="Small circular hole (R=5 px) testing collapse / deletion threshold",
        raw_contour=contour,
        ground_truth_corners=[],
    )


def create_fixture_6_noisy_staircase_multiangle() -> Fixture:
    """Fixture 6: Multi-angled polygon with edge slopes (1:5, 1:2, 2:1, 5:1) creating dense aliasing."""
    canvas = make_canvas(600, 600)
    pts = np.array([
        [150, 150],
        [450, 210],  # slope 60/300 = 1:5 (11.3 deg)
        [500, 450],  # slope 240/50 = ~5:1 (78.2 deg)
        [300, 500],  # slope -50/200 = -1:4
        [100, 350],  # slope 150/200
    ], dtype=np.int32)
    cv2.fillPoly(canvas, [pts], 255)
    contour = extract_primary_contour(canvas)
    corners = [tuple(p) for p in pts.astype(np.float64)]
    return Fixture(
        name="fixture_6_noisy_staircase_multiangle",
        description="Multi-angled polygon testing dense raster staircase noise removal",
        raw_contour=contour,
        ground_truth_corners=corners,
    )


def create_fixture_7_mixed_stepped_shaft() -> Fixture:
    """
    Fixture 7: Realistic mechanical stepped shaft profile.
    Contains:
    - Large straight cylinder body
    - 45 deg chamfer
    - Circular fillet arc transition (R=20 px)
    - Keyway notch (8x6 px)
    """
    canvas = make_canvas(700, 500)
    # Draw stepped shaft silhouette
    # Base shaft left: x in [100, 300], y in [200, 320] (height 120)
    # Chamfer at start: (100, 215) to (115, 200)
    # Right shaft: x in [300, 550], y in [225, 295] (height 70)
    # Fillet at shoulder x=300: concave transition with R=15
    pts = [
        [115, 200],
        [220, 200],
        # Keyway notch in left shaft: width 8, depth 6
        [220, 206],
        [228, 206],
        [228, 200],
        [300, 200],
        # Shoulder step down to y=225
        [300, 225],
        [540, 225],
        # Right end chamfer
        [550, 235],
        [550, 285],
        [540, 295],
        [300, 295],
        # Shoulder step down to y=320
        [300, 320],
        [115, 320],
        [100, 305],
        [100, 215],
    ]
    polygon_pts = np.array(pts, dtype=np.int32)
    cv2.fillPoly(canvas, [polygon_pts], 255)
    # Smooth the shoulder transition with an arc fillet
    # Draw a fillet circle sector
    cv2.circle(canvas, (315, 225), 15, 255, -1)
    cv2.circle(canvas, (315, 295), 15, 255, -1)

    contour = extract_primary_contour(canvas)
    corners = [
        (115.0, 200.0), (220.0, 200.0), (220.0, 206.0), (228.0, 206.0), (228.0, 200.0),
        (540.0, 225.0), (550.0, 235.0), (550.0, 285.0), (540.0, 295.0),
        (115.0, 320.0), (100.0, 305.0), (100.0, 215.0)
    ]
    return Fixture(
        name="fixture_7_mixed_stepped_shaft",
        description="Realistic mechanical stepped shaft with straight edges, chamfers, fillet arc, and keyway notch",
        raw_contour=contour,
        ground_truth_corners=corners,
        notch_bounding_box=(220.0, 200.0, 228.0, 206.0),
    )


# ---------------------------------------------------------------------------
# Benchmark Runner
# ---------------------------------------------------------------------------

@dataclass
class EvaluationResult:
    fixture_name: str
    algorithm: str
    parameter_label: str
    orig_point_count: int
    simp_point_count: int
    point_reduction_pct: float
    hausdorff_error_px: float
    area_error_pct: float
    perimeter_error_pct: float
    corner_survival_pct: float
    small_feature_survived: bool
    closed_topology_preserved: bool


def evaluate_candidate(
    fixture: Fixture,
    candidate_pts: np.ndarray,
    algo_name: str,
    param_label: str,
) -> EvaluationResult:
    orig = fixture.raw_contour
    n_orig = len(orig)
    n_simp = len(candidate_pts)

    reduction = ((n_orig - n_simp) / n_orig) * 100.0

    # Hausdorff
    h_dist = polygon_hausdorff_distance(orig, candidate_pts)

    # Area & Perimeter
    a_orig = polygon_area(orig)
    a_simp = polygon_area(candidate_pts)
    a_err = abs(a_orig - a_simp) / a_orig * 100.0 if a_orig > 0 else 0.0

    p_orig = polygon_perimeter(orig)
    p_simp = polygon_perimeter(candidate_pts)
    p_err = abs(p_orig - p_simp) / p_orig * 100.0 if p_orig > 0 else 0.0

    # Corner survival: corner is matched if simplified polygon has a vertex within 2.5 px
    if fixture.ground_truth_corners:
        survived = 0
        for c in fixture.ground_truth_corners:
            c_arr = np.array(c)
            min_dist = min(np.linalg.norm(candidate_pts - c_arr, axis=1))
            if min_dist <= 2.5:
                survived += 1
        corner_surv_pct = (survived / len(fixture.ground_truth_corners)) * 100.0
    else:
        corner_surv_pct = 100.0

    # Small feature survival (notch)
    feature_survived = True
    if fixture.notch_bounding_box:
        xmin, ymin, xmax, ymax = fixture.notch_bounding_box
        # Check if any simplified point falls deep inside the notch (y > ymin + 2.0)
        notch_pts = [
            pt for pt in candidate_pts
            if (xmin - 2.0 <= pt[0] <= xmax + 2.0 and pt[1] >= ymin + 3.0)
        ]
        feature_survived = len(notch_pts) >= 1

    # Topology preserved
    topology_ok = is_simple_polygon(candidate_pts) and n_simp >= 3

    return EvaluationResult(
        fixture_name=fixture.name,
        algorithm=algo_name,
        parameter_label=param_label,
        orig_point_count=n_orig,
        simp_point_count=n_simp,
        point_reduction_pct=round(reduction, 2),
        hausdorff_error_px=round(h_dist, 3),
        area_error_pct=round(a_err, 4),
        perimeter_error_pct=round(p_err, 3),
        corner_survival_pct=round(corner_surv_pct, 1),
        small_feature_survived=feature_survived,
        closed_topology_preserved=topology_ok,
    )


def run_full_benchmark() -> List[EvaluationResult]:
    fixtures = [
        create_fixture_1_long_straight_edges(),
        create_fixture_2_sharp_corners(),
        create_fixture_3_circular_arcs(),
        create_fixture_4_tiny_notch(),
        create_fixture_5_small_hole(),
        create_fixture_6_noisy_staircase_multiangle(),
        create_fixture_7_mixed_stepped_shaft(),
    ]

    results: List[EvaluationResult] = []

    for f in fixtures:
        raw = f.raw_contour
        cv_contour = raw.reshape(-1, 1, 2).astype(np.float32)
        perimeter = float(cv2.arcLength(cv_contour, True))

        # 1. Baseline: Raw Unsimplified
        res_baseline = evaluate_candidate(f, raw, "Baseline_CHAIN_APPROX_NONE", "none")
        results.append(res_baseline)

        # 2. RDP (OpenCV approxPolyDP) - Absolute epsilons
        for eps in [0.75, 1.5, 3.0, 6.0]:
            approx = cv2.approxPolyDP(cv_contour, eps, True)[:, 0, :].astype(np.float64)
            res = evaluate_candidate(f, approx, "OpenCV_RDP_Absolute", f"eps_{eps}px")
            results.append(res)

        # 3. RDP (OpenCV approxPolyDP) - Relative epsilons (common in existing codebase: 0.005, 0.01, 0.02, 0.08)
        for frac in [0.002, 0.005, 0.01, 0.02, 0.08]:
            eps = frac * perimeter
            approx = cv2.approxPolyDP(cv_contour, eps, True)[:, 0, :].astype(np.float64)
            res = evaluate_candidate(f, approx, "OpenCV_RDP_Relative", f"eps_{frac}xPerim")
            results.append(res)

        # 4. Visvalingam-Whyatt (VW) - Area thresholds
        for area_thresh in [1.0, 4.0, 16.0, 64.0]:
            vw_pts = visvalingam_whyatt_closed(raw, area_thresh)
            res = evaluate_candidate(f, vw_pts, "Visvalingam_Whyatt", f"area_{area_thresh}px2")
            results.append(res)

    return results


def main():
    print("Executing REA-022 Image-to-CAD Contour Simplification Benchmark...")
    results = run_full_benchmark()

    out_dir = Path("research/antigravity/2026-10-14/image_to_cad_contour_simplification")
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "benchmark_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    print(f"Benchmark complete! Total evaluations: {len(results)}")
    print(f"Results saved to: {json_path}")


if __name__ == "__main__":
    main()
