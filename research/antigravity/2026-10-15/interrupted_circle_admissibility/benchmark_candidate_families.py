"""Benchmark and Pareto Evaluation Engine for Circle Admissibility Candidates.

Phases 6-11, 14-22, 25-30 of ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015.
Evaluates:
  1. CURRENT_MAIN (Hough baseline)
  2. FORMER_PR518 (Closed-contour gate)
  3. CANDIDATE_B (Angular occupancy threshold)
  4. CANDIDATE_C (Radial normal gradient consistency)
  5. CANDIDATE_F (Occlusion-aware support model)
  6. CANDIDATE_F_HYBRID (Candidate F + OCR text glyph suppression)

Outputs detailed metrics per case, confusion matrices, and Pareto frontier.
"""

from __future__ import annotations

import importlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

cv2 = importlib.import_module("cv2")


BASE_DIR = Path(__file__).parent
MATRIX_FILE = BASE_DIR / "BLIND_CIRCLE_MATRIX.json"
_SQRT2 = float(np.sqrt(2.0))


# -------------------------------------------------------------
# 1. FORMER PR #518 IMPLEMENTATION (Read-Only Exact Model)
# -------------------------------------------------------------
def _pr518_fit_supported_circle_contours(
    edges: np.ndarray,
    min_radius: int = 10,
    max_radius: int = 400,
) -> List[Tuple[float, float, float, float]]:
    """Exact reconstruction of PR #518 _fit_supported_circle_contours."""
    contours, _ = cv2.findContours(edges.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    fit_tolerance_px = _SQRT2
    fits: List[Tuple[float, float, float, float]] = []

    for contour in contours:
        points = np.asarray(contour, dtype=np.float64).reshape(-1, 2)
        if len(points) < 12:
            continue

        origin_x = float(np.mean(points[:, 0]))
        origin_y = float(np.mean(points[:, 1]))
        x = points[:, 0] - origin_x
        y = points[:, 1] - origin_y
        matrix = np.column_stack((x, y, np.ones_like(x)))
        try:
            a, b, c = np.linalg.lstsq(matrix, -(x * x + y * y), rcond=None)[0]
        except np.linalg.LinAlgError:
            continue
        center_x = origin_x + float(-a / 2.0)
        center_y = origin_y + float(-b / 2.0)
        radius_squared = (a * a + b * b) / 4.0 - float(c)
        if not np.isfinite(radius_squared) or radius_squared <= 0.0:
            continue
        radius = float(np.sqrt(radius_squared))
        if radius < min_radius or radius > max_radius:
            continue

        radial_error = np.abs(
            np.hypot(points[:, 0] - center_x, points[:, 1] - center_y) - radius
        )
        max_radial_error = float(np.max(radial_error))
        if max_radial_error > fit_tolerance_px:
            continue

        angles = np.sort(np.mod(
            np.arctan2(points[:, 1] - center_y, points[:, 0] - center_x),
            2.0 * np.pi,
        ))
        angular_gaps = np.diff(np.concatenate((angles, angles[:1] + 2.0 * np.pi)))
        max_gap = float(np.max(angular_gaps))
        contour_spacing_bound_px = fit_tolerance_px + 2.0 * max_radial_error
        max_gap_from_pixel_spacing = 2.0 * float(np.arcsin(min(
            1.0, contour_spacing_bound_px / (2.0 * radius),
        )))
        if max_gap - max_gap_from_pixel_spacing > 1e-12:
            continue

        fits.append((center_x, center_y, radius, max_radial_error))

    return sorted(fits, key=lambda fit: (fit[1], fit[0], fit[2]))


def run_pr518(image_bgr: np.ndarray, min_radius: int = 10, max_radius: int = 400) -> List[Tuple[float, float, float]]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 50, 100)
    fits = _pr518_fit_supported_circle_contours(edges, min_radius=min_radius, max_radius=max_radius)
    return [(f[0], f[1], f[2]) for f in fits]


# -------------------------------------------------------------
# 2. CURRENT MAIN IMPLEMENTATION (OpenCV Hough Baseline)
# -------------------------------------------------------------
def run_current_main(image_bgr: np.ndarray, max_radius: int = 80) -> List[Tuple[float, float, float]]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    if gray.shape[0] < 10 or gray.shape[1] < 10:
        return []
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=40, param1=100, param2=55, minRadius=10, maxRadius=max_radius
    )
    if circles is None:
        return []
    res = []
    for c in circles[0]:
        res.append((float(c[0]), float(c[1]), float(c[2])))
    return res


# -------------------------------------------------------------
# 3. EXTRACT EDGES & PROPOSALS
# -------------------------------------------------------------
def get_hough_proposals(gray: np.ndarray, min_r: int = 10, max_r: int = 400) -> List[Tuple[float, float, float]]:
    if gray.shape[0] < 10 or gray.shape[1] < 10:
        return []
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    # Permissive proposal generation: param2=30 to ensure high recall
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=20, param1=100, param2=30, minRadius=min_r, maxRadius=max_r
    )
    if circles is None:
        return []
    return [(float(c[0]), float(c[1]), float(c[2])) for c in circles[0]]


# -------------------------------------------------------------
# 4. CANDIDATE B: ANGULAR OCCUPANCY GATE
# -------------------------------------------------------------
def evaluate_candidate_b(
    proposals: List[Tuple[float, float, float]],
    edges: np.ndarray,
    min_coverage: float = 0.80,
    max_gap_deg: float = 60.0,
) -> List[Tuple[float, float, float]]:
    h, w = edges.shape
    admitted = []
    num_bins = 72  # 5 degrees per bin

    for cx, cy, r in proposals:
        if r <= 0 or not np.isfinite(cx) or not np.isfinite(cy) or not np.isfinite(r):
            continue
        if cx < -r or cy < -r or cx > w + r or cy > h + r:
            continue

        tol = max(2.5, 0.03 * r)
        bins = np.zeros(num_bins, dtype=bool)

        for b in range(num_bins):
            theta = 2.0 * math.pi * b / num_bins
            sx = cx + r * math.cos(theta)
            sy = cy + r * math.sin(theta)
            x0 = max(0, int(math.floor(sx - tol)))
            x1 = min(w, int(math.ceil(sx + tol + 1)))
            y0 = max(0, int(math.floor(sy - tol)))
            y1 = min(h, int(math.ceil(sy + tol + 1)))
            if x1 <= x0 or y1 <= y0:
                continue
            patch = edges[y0:y1, x0:x1]
            if np.any(patch > 0):
                bins[b] = True

        coverage = np.sum(bins) / num_bins
        # Find max gap
        doubled = np.concatenate((bins, bins))
        max_consec_zeros = 0
        cur_zeros = 0
        for val in doubled:
            if not val:
                cur_zeros += 1
                if cur_zeros > max_consec_zeros:
                    max_consec_zeros = cur_zeros
            else:
                cur_zeros = 0
        max_gap = min(360.0, (max_consec_zeros * 360.0) / num_bins)

        if coverage >= min_coverage and max_gap <= max_gap_deg:
            admitted.append((cx, cy, r))

    return admitted


# -------------------------------------------------------------
# 5. CANDIDATE C: RADIAL NORMAL CONSISTENCY GATE
# -------------------------------------------------------------
def evaluate_candidate_c(
    proposals: List[Tuple[float, float, float]],
    edges: np.ndarray,
    gray: np.ndarray,
    max_median_err_deg: float = 5.0,
    max_p90_err_deg: float = 15.0,
) -> List[Tuple[float, float, float]]:
    h, w = edges.shape
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    gx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
    admitted = []

    for cx, cy, r in proposals:
        if r <= 0 or not np.isfinite(cx) or not np.isfinite(cy) or not np.isfinite(r):
            continue
        tol = max(2.5, 0.03 * r)
        n = max(72, int(2.0 * math.pi * r))
        errors = []

        for i in range(n):
            theta = 2.0 * math.pi * i / n
            sx = cx + r * math.cos(theta)
            sy = cy + r * math.sin(theta)
            x0 = max(0, int(math.floor(sx - tol)))
            x1 = min(w, int(math.ceil(sx + tol + 1)))
            y0 = max(0, int(math.floor(sy - tol)))
            y1 = min(h, int(math.ceil(sy + tol + 1)))
            if x1 <= x0 or y1 <= y0:
                continue
            yy, xx = np.nonzero(edges[y0:y1, x0:x1])
            if len(xx) == 0:
                continue
            xx = xx + x0; yy = yy + y0
            rad = np.hypot(xx - cx, yy - cy)
            dr = np.abs(rad - r)
            best_idx = int(np.argmin(dr))
            if dr[best_idx] > tol:
                continue
            ex, ey = int(xx[best_idx]), int(yy[best_idx])
            g_norm = math.hypot(gx[ey, ex], gy[ey, ex])
            if g_norm <= 1e-3:
                continue
            rx = (ex - cx) / rad[best_idx]
            ry = (ey - cy) / rad[best_idx]
            cos_a = abs((gx[ey, ex] * rx + gy[ey, ex] * ry) / g_norm)
            cos_a = min(1.0, max(0.0, cos_a))
            err_deg = math.degrees(math.acos(cos_a))
            errors.append(err_deg)

        if len(errors) < 20:
            continue
        med = float(np.median(errors))
        p90 = float(np.percentile(errors, 90))
        if med <= max_median_err_deg and p90 <= max_p90_err_deg:
            admitted.append((cx, cy, r))

    return admitted


# -------------------------------------------------------------
# 6. CANDIDATE F: OCCLUSION-AWARE SUPPORT & GAP EXPLANATION
# -------------------------------------------------------------
def evaluate_candidate_f(
    proposals: List[Tuple[float, float, float]],
    edges: np.ndarray,
    gray: np.ndarray,
    text_rois: Optional[List[Tuple[int, int, int, int]]] = None,
) -> List[Tuple[float, float, float]]:
    """Candidate F: Interrupted circles admitted ONLY if all gaps are geometrically explained."""
    h, w = edges.shape
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    gx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
    num_bins = 72  # 5 deg per bin
    admitted = []

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=20, maxLineGap=5)
    line_segments: List[Tuple[float, float, float, float]] = []
    if lines is not None:
        for seg in lines.reshape(-1, 4):
            line_segments.append((float(seg[0]), float(seg[1]), float(seg[2]), float(seg[3])))

    for cx, cy, r in proposals:
        if r <= 0 or not np.isfinite(cx) or not np.isfinite(cy) or not np.isfinite(r):
            continue
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            continue

        tol = max(2.5, 0.03 * r)
        q_bound = 2.0 * math.asin(min(1.0, tol / (2.0 * r)))
        q_bound_deg = math.degrees(q_bound)

        # Normal envelope
        eps_normal = math.degrees(math.asin(min(1.0, tol / r))) + 3.5

        bins_supported = np.zeros(num_bins, dtype=bool)
        bin_normal_errors = []

        for b in range(num_bins):
            theta = 2.0 * math.pi * b / num_bins
            sx = cx + r * math.cos(theta)
            sy = cy + r * math.sin(theta)
            x0 = max(0, int(math.floor(sx - tol)))
            x1 = min(w, int(math.ceil(sx + tol + 1)))
            y0 = max(0, int(math.floor(sy - tol)))
            y1 = min(h, int(math.ceil(sy + tol + 1)))
            if x1 <= x0 or y1 <= y0:
                continue
            yy, xx = np.nonzero(edges[y0:y1, x0:x1])
            if len(xx) == 0:
                continue
            xx = xx + x0; yy = yy + y0
            rad = np.hypot(xx - cx, yy - cy)
            dr = np.abs(rad - r)
            best_idx = int(np.argmin(dr))
            if dr[best_idx] > tol:
                continue
            ex, ey = int(xx[best_idx]), int(yy[best_idx])
            g_norm = math.hypot(gx[ey, ex], gy[ey, ex])
            if g_norm > 1e-3:
                rx = (ex - cx) / rad[best_idx]
                ry = (ey - cy) / rad[best_idx]
                cos_a = abs((gx[ey, ex] * rx + gy[ey, ex] * ry) / g_norm)
                cos_a = min(1.0, max(0.0, cos_a))
                err_deg = math.degrees(math.acos(cos_a))
                if err_deg <= eps_normal + 5.0:  # within derived envelope
                    bins_supported[b] = True
                    bin_normal_errors.append(err_deg)

        if len(bin_normal_errors) == 0:
            continue
        if float(np.median(bin_normal_errors)) > eps_normal + 2.0:
            continue

        # Check unsupported gaps
        # Identify contiguous runs of False in circular buffer
        # Double the array to handle seam wrap
        doubled = np.concatenate((bins_supported, bins_supported))
        gaps: List[Tuple[int, int]] = []  # (start_bin, length)
        cur_start = None
        cur_len = 0
        for i, val in enumerate(doubled):
            if not val:
                if cur_start is None:
                    cur_start = i
                cur_len += 1
            else:
                if cur_start is not None and cur_len > 0:
                    start_mod = cur_start % num_bins
                    if cur_len < num_bins:
                        # Avoid duplicates from doubling
                        if not any(g[0] == start_mod for g in gaps):
                            gaps.append((start_mod, cur_len))
                cur_start = None
                cur_len = 0
        if cur_start is not None and cur_len >= num_bins:
            continue  # completely empty

        all_gaps_explained = True
        total_explained_bins = 0

        for start_bin, length in gaps:
            gap_deg = (length * 360.0) / num_bins
            if gap_deg <= q_bound_deg:
                # Normal pixel spacing gap
                total_explained_bins += length
                continue

            # Gap is larger than quantization -> MUST be explained by an occluder!
            mid_bin = (start_bin + length / 2.0) % num_bins
            mid_theta = 2.0 * math.pi * mid_bin / num_bins
            gap_pt_x = cx + r * math.cos(mid_theta)
            gap_pt_y = cy + r * math.sin(mid_theta)

            gap_explained = False

            # Check 1: Geometric occluder line crossing the gap footprint
            for lx0, ly0, lx1, ly1 in line_segments:
                # Distance from line segment to (gap_pt_x, gap_pt_y)
                # Segment vector
                seg_dx = lx1 - lx0
                seg_dy = ly1 - ly0
                seg_len2 = seg_dx * seg_dx + seg_dy * seg_dy
                if seg_len2 == 0:
                    continue
                t = max(0.0, min(1.0, ((gap_pt_x - lx0) * seg_dx + (gap_pt_y - ly0) * seg_dy) / seg_len2))
                proj_x = lx0 + t * seg_dx
                proj_y = ly0 + t * seg_dy
                dist_to_gap = math.hypot(gap_pt_x - proj_x, gap_pt_y - proj_y)
                if dist_to_gap <= tol + 3.0:
                    gap_explained = True
                    break

            # Check 2: Text ROI covering the gap footprint
            if not gap_explained and text_rois is not None:
                for rx0, ry0, rx1, ry1 in text_rois:
                    if rx0 <= gap_pt_x <= rx1 and ry0 <= gap_pt_y <= ry1:
                        gap_explained = True
                        break

            # Check 3: Ink crossing or white text box on raw image
            if not gap_explained:
                gx0 = max(0, int(gap_pt_x - tol))
                gx1 = min(w, int(gap_pt_x + tol + 1))
                gy0 = max(0, int(gap_pt_y - tol))
                gy1 = min(h, int(gap_pt_y + tol + 1))
                if gx1 > gx0 and gy1 > gy0:
                    raw_patch = gray[gy0:gy1, gx0:gx1]
                    # If high contrast edge or text ink is present near the gap
                    if np.min(raw_patch) < 50:  # dark line/text passing through
                        gap_explained = True

            if gap_explained:
                total_explained_bins += length
            else:
                all_gaps_explained = False
                break

        # A circle is admitted if all its gaps are explained and support + explained = 100%
        # AND it has distributed support across at least 3 quadrants
        quadrant_support = [
            np.any(bins_supported[k*18:(k+1)*18])
            for k in range(4)
        ]
        if all_gaps_explained and sum(quadrant_support) >= 3 and np.sum(bins_supported) >= 18:
            admitted.append((cx, cy, r))

    return admitted


# -------------------------------------------------------------
# 7. CANDIDATE F + ROLE (HYBRID ARCHITECTURE)
# -------------------------------------------------------------
def evaluate_candidate_f_hybrid(
    proposals: List[Tuple[float, float, float]],
    edges: np.ndarray,
    gray: np.ndarray,
    image_bgr: np.ndarray,
) -> List[Tuple[float, float, float]]:
    """Candidate F with role gating: suppresses circles matching text glyphs."""
    admitted_f = evaluate_candidate_f(proposals, edges, gray)
    if not admitted_f:
        return []

    # Run lightweight OCR glyph filter (as in PR #518 and architecture)
    # Character height for glyphs is usually < 25px, radius < 15px
    # If text is present, small circles inside text blocks are suppressed
    final_admitted = []
    for cx, cy, r in admitted_f:
        # If very small circle (r <= 12) embedded in dense text lines
        if r <= 15:
            # Check surrounding aspect ratio and neighboring ink
            y0 = max(0, int(cy - 20))
            y1 = min(gray.shape[0], int(cy + 20))
            x0 = max(0, int(cx - 50))
            x1 = min(gray.shape[1], int(cx + 50))
            patch = gray[y0:y1, x0:x1]
            # If multiple horizontal text lines or high text density
            if np.sum(patch < 100) > 100 and (x1 - x0) > 60:
                # Candidate is a text glyph 'O'/'0', withhold!
                continue
        final_admitted.append((cx, cy, r))
    return final_admitted


# -------------------------------------------------------------
# 8. BENCHMARK EXECUTION ACROSS ALL 81 MATRIX CASES
# -------------------------------------------------------------
def match_circle(candidate: Tuple[float, float, float], ground_truth: List[Dict[str, Any]], tol_px: float = 6.0) -> bool:
    cx, cy, r = candidate
    for gt in ground_truth:
        gcx, gcy = gt["center_px"]
        gr = gt["radius_px"]
        if math.hypot(cx - gcx, cy - gcy) <= tol_px and abs(r - gr) <= tol_px:
            return True
    return False


def run_benchmark():
    matrix_data = json.loads(MATRIX_FILE.read_text(encoding="utf-8"))
    cases = matrix_data["cases"]

    algorithms = [
        "CURRENT_MAIN",
        "FORMER_PR518",
        "CANDIDATE_B_ANGULAR",
        "CANDIDATE_C_NORMAL",
        "CANDIDATE_F_OCCLUSION",
        "CANDIDATE_F_HYBRID",
    ]

    metrics: Dict[str, Dict[str, Any]] = {
        algo: {
            "true_positive": 0,
            "false_negative": 0,
            "false_positive": 0,
            "true_negative": 0,
            "hard_failures": 0,
            "positive_recovered": [],
            "positive_missed": [],
            "false_admissions": [],
        }
        for algo in algorithms
    }

    per_case_results: List[Dict[str, Any]] = []

    for case in cases:
        cid = case["case_id"]
        ccls = case["class"]
        gt = case["ground_truth"]
        must_admit = case["must_admit"]
        must_reject = case["must_reject"]
        hard_if_admit = case["hard_failure_if_admitted"]
        hard_if_reject = case["hard_failure_if_rejected"]

        img_path = BASE_DIR / case["fixture_relpath"]
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 100) if gray.shape[0] >= 10 and gray.shape[1] >= 10 else np.zeros_like(gray)

        # Generate candidates for each algo
        # 1. Main
        main_cands = run_current_main(img)
        # 2. PR518
        pr518_cands = run_pr518(img)
        # Permissive proposals for B, C, F
        raw_props = get_hough_proposals(gray)
        # 3. Candidate B
        cand_b = evaluate_candidate_b(raw_props, edges)
        # 4. Candidate C
        cand_c = evaluate_candidate_c(raw_props, edges, gray)
        # 5. Candidate F
        cand_f = evaluate_candidate_f(raw_props, edges, gray)
        # 6. Candidate F Hybrid
        cand_f_hyb = evaluate_candidate_f_hybrid(raw_props, edges, gray, img)

        algo_cands = {
            "CURRENT_MAIN": main_cands,
            "FORMER_PR518": pr518_cands,
            "CANDIDATE_B_ANGULAR": cand_b,
            "CANDIDATE_C_NORMAL": cand_c,
            "CANDIDATE_F_OCCLUSION": cand_f,
            "CANDIDATE_F_HYBRID": cand_f_hyb,
        }

        case_record = {"case_id": cid, "class": ccls, "name": case["name"], "detections": {}}

        for algo in algorithms:
            cands = algo_cands[algo]
            case_record["detections"][algo] = len(cands)

            if ccls == "POSITIVE_REAL_CIRCLE":
                # Must find ground truth circles
                matched = sum(1 for c in cands if match_circle(c, gt))
                expected = len(gt)
                if matched >= expected:
                    metrics[algo]["true_positive"] += 1
                    metrics[algo]["positive_recovered"].append(cid)
                else:
                    metrics[algo]["false_negative"] += 1
                    metrics[algo]["positive_missed"].append(cid)
                    if hard_if_reject:
                        metrics[algo]["hard_failures"] += 1
            else:
                # Negative or degenerate: should NOT admit circle
                if len(cands) == 0:
                    metrics[algo]["true_negative"] += 1
                else:
                    metrics[algo]["false_positive"] += 1
                    metrics[algo]["false_admissions"].append((cid, len(cands)))
                    if hard_if_admit:
                        metrics[algo]["hard_failures"] += 1

        per_case_results.append(case_record)

    # Compile scorecard
    scorecard = {
        "campaign_id": "ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015",
        "matrix_sha256": "1fc7793f6dc11139b7cc077de2f0d48b659058a4b705dceabd96e4875d13f195",
        "total_cases": len(cases),
        "algorithms": algorithms,
        "metrics": metrics,
        "pareto_summary": {
            algo: {
                "recall_positive": f"{len(metrics[algo]['positive_recovered'])}/24 ({len(metrics[algo]['positive_recovered'])/24.0:.1%})",
                "false_positives": metrics[algo]["false_positive"],
                "hard_failures": metrics[algo]["hard_failures"],
            }
            for algo in algorithms
        },
    }

    out_file = BASE_DIR / "benchmark_results.json"
    out_file.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(json.dumps(scorecard["pareto_summary"], indent=2))


if __name__ == "__main__":
    run_benchmark()
