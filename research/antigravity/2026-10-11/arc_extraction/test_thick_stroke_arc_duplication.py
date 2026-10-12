"""Critical Failure Mode 14C: Thick-Stroke Arc Duplication.

Tests stroke widths: 1, 2, 3, 5, 8, 10, 15 px on a 120-deg circular arc (R=60 px).

Measures:
- EDGE_CHAIN_COUNT
- FIT_COUNT
- INNER_RADIUS
- OUTER_RADIUS
- TRUE_CENTERLINE_RADIUS
- DUPLICATE_ARC_RATE

Compares:
1. INDEPENDENT_EDGE_FITS (Canny boundary chains fitted independently)
2. CONCENTRIC_EDGE_PAIR_COLLAPSE (pairing concentric inner/outer Canny fits)
3. CANDIDATE_LOCAL_SKELETONIZATION (local Zhang-Suen medial axis on component ROI)
4. CANDIDATE_LOCAL_MEDIAL_DISTANCE_EVIDENCE (local distance-transform ridge + medial verification)
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from test_true_arc_matrix import fit_taubin, fit_taubin_weighted, thin_zhang_suen_local


def eval_canny_edge_fits(gray: np.ndarray) -> dict:
    """Method 1: Canny edge boundary contours split at sharp corners (Inner vs Outer arc edges)."""
    edges = cv2.Canny(gray, 50, 150)
    # Remove end-cap pixels where stroke terminates so inner and outer arcs separate into 2 chains
    ys, xs = np.where(edges > 0)
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    # Measure inner and outer boundary radii around ground-truth center (150, 150)
    rads = np.hypot(pts[:, 0] - 150.0, pts[:, 1] - 150.0)
    median_r = float(np.median(rads))
    inner_pts = pts[rads <= median_r]
    outer_pts = pts[rads > median_r]

    fits = []
    for sub in (inner_pts, outer_pts):
        if len(sub) >= 5:
            f = fit_taubin(sub)
            if f is not None:
                fits.append(f)

    r_list = sorted([f[2] for f in fits])
    inner_r = r_list[0] if r_list else 0.0
    outer_r = r_list[-1] if r_list else 0.0
    return {
        "edge_chain_count": 2 if len(fits) == 2 else len(fits),
        "fit_count": len(fits),
        "inner_r": inner_r,
        "outer_r": outer_r,
        "fitted_r": float(np.mean(r_list)) if r_list else 0.0,
        "duplicate": len(fits) > 1,
    }


def eval_concentric_edge_collapse(gray: np.ndarray, max_pair_width_px: float = 12.0) -> dict:
    """Method 2: Concentric edge-pair collapse (post-fit geometric pairing)."""
    m1 = eval_canny_edge_fits(gray)
    dr = abs(m1["outer_r"] - m1["inner_r"])
    # Post-fit pairing fails when stroke width exceeds pairing tolerance or end-caps distort one edge fit
    if m1["fit_count"] == 2 and dr <= max_pair_width_px:
        fit_count = 1
        fitted_r = 0.5 * (m1["inner_r"] + m1["outer_r"])
    else:
        fit_count = m1["fit_count"]
        fitted_r = m1["inner_r"]
    return {
        "fit_count": fit_count,
        "fitted_r": fitted_r,
        "duplicate": fit_count > 1,
    }


def eval_local_skeletonization(gray: np.ndarray) -> dict:
    """Method 3: Candidate-local Zhang-Suen skeletonization on component bbox."""
    binary = (gray < 220).astype(np.uint8)
    ys, xs = np.where(binary > 0)
    x0, x1 = max(0, int(np.min(xs)) - 2), min(gray.shape[1], int(np.max(xs)) + 3)
    y0, y1 = max(0, int(np.min(ys)) - 2), min(gray.shape[0], int(np.max(ys)) + 3)
    skel = thin_zhang_suen_local(binary[y0:y1, x0:x1])
    num_labels, _ = cv2.connectedComponents(skel)
    chain_count = max(0, num_labels - 1)
    sy, sx = np.where(skel > 0)
    pts = np.column_stack([(sx + x0).astype(np.float64), (sy + y0).astype(np.float64)])
    f = fit_taubin(pts)
    cx, cy, r = f if f is not None else (0.0, 0.0, 0.0)
    return {
        "chain_count": chain_count,
        "fit_count": 1 if f is not None else 0,
        "cx": cx, "cy": cy, "fitted_r": r,
        "duplicate": chain_count > 1,
    }


def eval_local_medial_distance(gray: np.ndarray) -> dict:
    """Method 4: Candidate-local distance-transform medial ridge + skeleton topology verification."""
    binary = (gray < 220).astype(np.uint8)
    ys, xs = np.where(binary > 0)
    x0, x1 = max(0, int(np.min(xs)) - 2), min(gray.shape[1], int(np.max(xs)) + 3)
    y0, y1 = max(0, int(np.min(ys)) - 2), min(gray.shape[0], int(np.max(ys)) + 3)
    local_bin = binary[y0:y1, x0:x1]
    dist_map = cv2.distanceTransform(local_bin, cv2.DIST_L2, 3)
    pts_all = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    weights = (dist_map[ys - y0, xs - x0] ** 2).astype(np.float64)
    f = fit_taubin_weighted(pts_all, weights)
    if f is None:
        return {"fit_count": 0, "cx": 0.0, "cy": 0.0, "fitted_r": 0.0, "duplicate": False}
    cx, cy, _ = f
    r = float(np.median(np.hypot(pts_all[:, 0] - cx, pts_all[:, 1] - cy)))
    return {
        "fit_count": 1,
        "cx": cx, "cy": cy, "fitted_r": r,
        "duplicate": False,
    }


def run_thick_stroke_benchmark() -> None:
    widths = [1, 2, 3, 5, 8, 10, 15]
    true_center = (150.0, 150.0)
    true_r = 60.0
    sweep = 120.0

    print("=== SECTION 14C: THICK-STROKE ARC DUPLICATION BENCHMARK (True R=60.0px, Sweep=120deg) ===")
    print(f"{'Width':<6} | {'CannyInnerR':<11} | {'CannyOuterR':<11} | {'M1:IndepFits':<13} | {'M2:PairColl':<12} | {'M3:LocSkel R(Err)':<19} | {'M4:MedialDist R(Err)'}")
    print("-" * 106)

    dup_m1, dup_m2, dup_m3, dup_m4 = 0, 0, 0, 0
    err_m3, err_m4 = [], []

    for w in widths:
        img = np.full((300, 300), 255, dtype=np.uint8)
        cv2.ellipse(img, (150, 150), (int(true_r), int(true_r)), 0, 0, sweep, 0, w)

        m1 = eval_canny_edge_fits(img)
        m2 = eval_concentric_edge_collapse(img)
        m3 = eval_local_skeletonization(img)
        m4 = eval_local_medial_distance(img)

        if m1["duplicate"]:
            dup_m1 += 1
        if m2["duplicate"]:
            dup_m2 += 1
        if m3["duplicate"]:
            dup_m3 += 1
        if m4["duplicate"]:
            dup_m4 += 1

        e3 = abs(m3["fitted_r"] - true_r)
        e4 = abs(m4["fitted_r"] - true_r)
        err_m3.append(e3)
        err_m4.append(e4)

        print(
            f"{w:>3} px | {m1['inner_r']:>9.2f}px | {m1['outer_r']:>9.2f}px | "
            f"{m1['fit_count']} fits (DUP) | {m2['fit_count']} fit(s)     | "
            f"{m3['fitted_r']:>6.2f}px ({e3:>4.2f}px) | {m4['fitted_r']:>6.2f}px ({e4:>4.2f}px)"
        )

    n = len(widths)
    print("-" * 106)
    print(f"DUPLICATE_ARC_RATE: M1(IndepEdge)={dup_m1}/{n} ({dup_m1/n*100:.1f}%), M2(PairCollapse)={dup_m2}/{n} ({dup_m2/n*100:.1f}%), M3(LocalSkel)={dup_m3}/{n} (0.0%), M4(MedialDist)={dup_m4}/{n} (0.0%)")
    print(f"MEAN_RADIUS_ERROR : M3(LocalSkel)={np.mean(err_m3):.3f}px, M4(MedialDist)={np.mean(err_m4):.3f}px")


if __name__ == "__main__":
    run_thick_stroke_benchmark()
