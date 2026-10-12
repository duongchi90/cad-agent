"""Benchmark Circular Arc Fitting Strategies (Section 12).

Compares:
- STRATEGY_A = KASA_ALGEBRAIC_FIT
- STRATEGY_B = TAUBIN_ALGEBRAIC_FIT
- STRATEGY_C = PRATT_FIT
- STRATEGY_D = OPENCV_MIN_ENCLOSING_CIRCLE_CONTROL
- STRATEGY_E = RANSAC_TAUBIN_FIT (evaluated on clean vs outlier-contaminated chains)
"""

from __future__ import annotations

import math
import time
from typing import Optional

import cv2
import numpy as np


def fit_kasa(pts: np.ndarray) -> Optional[tuple[float, float, float]]:
    """STRATEGY_A: Kasa (1976) algebraic circle fit."""
    if len(pts) < 3:
        return None
    x = pts[:, 0].astype(np.float64)
    y = pts[:, 1].astype(np.float64)
    mx, my = float(np.mean(x)), float(np.mean(y))
    X = x - mx
    Y = y - my
    Z = X * X + Y * Y
    A_mat = np.column_stack([X, Y, np.ones_like(X)])
    try:
        sol, _, rank, _ = np.linalg.lstsq(A_mat, -Z, rcond=None)
    except np.linalg.LinAlgError:
        return None
    if rank < 3:
        return None
    B, C, D = float(sol[0]), float(sol[1]), float(sol[2])
    cx_rel = -0.5 * B
    cy_rel = -0.5 * C
    r_sq = cx_rel * cx_rel + cy_rel * cy_rel - D
    if r_sq <= 0 or not math.isfinite(r_sq):
        return None
    return (mx + cx_rel, my + cy_rel, math.sqrt(r_sq))


def fit_taubin(pts: np.ndarray) -> Optional[tuple[float, float, float]]:
    """STRATEGY_B: Taubin (1991) gradient-normalized algebraic circle fit."""
    n = len(pts)
    if n < 3:
        return None
    x = pts[:, 0].astype(np.float64)
    y = pts[:, 1].astype(np.float64)
    mx, my = float(np.mean(x)), float(np.mean(y))
    X = x - mx
    Y = y - my
    Z = X * X + Y * Y
    Mz = float(np.mean(Z))
    if Mz <= 1e-12:
        return None
    Z0 = Z - Mz
    V = np.column_stack([Z0, X, Y])
    M = (V.T @ V) / float(n)
    inv_sqrt_4Mz = 1.0 / math.sqrt(4.0 * Mz)
    scale = np.array([inv_sqrt_4Mz, 1.0, 1.0], dtype=np.float64)
    S = (M * scale[:, None]) * scale[None, :]
    try:
        evals, evecs = np.linalg.eigh(S)
    except np.linalg.LinAlgError:
        return None
    v = evecs[:, 0]
    A = float(v[0]) * inv_sqrt_4Mz
    B = float(v[1])
    C = float(v[2])
    if abs(A) <= 1e-12:
        return None
    cx_rel = -B / (2.0 * A)
    cy_rel = -C / (2.0 * A)
    r_sq = cx_rel * cx_rel + cy_rel * cy_rel + Mz
    if r_sq <= 0 or not math.isfinite(r_sq):
        return None
    return (mx + cx_rel, my + cy_rel, math.sqrt(r_sq))


def fit_pratt(pts: np.ndarray) -> Optional[tuple[float, float, float]]:
    """STRATEGY_C: Pratt (1987) exact-gradient-constraint algebraic circle fit."""
    n = len(pts)
    if n < 3:
        return None
    x = pts[:, 0].astype(np.float64)
    y = pts[:, 1].astype(np.float64)
    mx, my = float(np.mean(x)), float(np.mean(y))
    X = x - mx
    Y = y - my
    Z = X * X + Y * Y
    V = np.column_stack([Z, X, Y, np.ones_like(X)])
    M = (V.T @ V) / float(n)
    B_inv = np.array([
        [0.0, 0.0, 0.0, -0.5],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [-0.5, 0.0, 0.0, 0.0],
    ], dtype=np.float64)
    try:
        evals, evecs = np.linalg.eig(B_inv @ M)
    except np.linalg.LinAlgError:
        return None
    best_idx = -1
    best_val = float("inf")
    for idx, val in enumerate(evals):
        if abs(val.imag) > 1e-6:
            continue
        rval = float(val.real)
        if rval >= -1e-9 and rval < best_val:
            best_val = rval
            best_idx = idx
    if best_idx < 0:
        return None
    vec = evecs[:, best_idx].real
    A, B, C, D = float(vec[0]), float(vec[1]), float(vec[2]), float(vec[3])
    if abs(A) <= 1e-12:
        return None
    cx_rel = -B / (2.0 * A)
    cy_rel = -C / (2.0 * A)
    r_sq = cx_rel * cx_rel + cy_rel * cy_rel - (D / A)
    if r_sq <= 0 or not math.isfinite(r_sq):
        return None
    return (mx + cx_rel, my + cy_rel, math.sqrt(r_sq))


def fit_min_enclosing(pts: np.ndarray) -> Optional[tuple[float, float, float]]:
    """STRATEGY_D: OpenCV minEnclosingCircle control."""
    if len(pts) < 3:
        return None
    (cx, cy), r = cv2.minEnclosingCircle(pts.astype(np.float32))
    if r <= 0:
        return None
    return (float(cx), float(cy), float(r))


def _circle_from_3pts(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> Optional[tuple[float, float, float]]:
    ax, ay = float(p1[0]), float(p1[1])
    bx, by = float(p2[0]), float(p2[1])
    cx, cy = float(p3[0]), float(p3[1])
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-8:
        return None
    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    return (ux, uy, r)


def fit_ransac_taubin(
    pts: np.ndarray,
    inlier_thresh_px: float = 1.5,
    num_iters: int = 40,
) -> Optional[tuple[float, float, float]]:
    """Optional RANSAC + Taubin refit for outlier-contaminated contours."""
    n = len(pts)
    if n < 6:
        return fit_taubin(pts)
    rng = np.random.default_rng(42)
    best_inliers = None
    best_count = 0
    for _ in range(num_iters):
        idx = rng.choice(n, size=3, replace=False)
        cand = _circle_from_3pts(pts[idx[0]], pts[idx[1]], pts[idx[2]])
        if cand is None:
            continue
        cx, cy, r = cand
        if r <= 1.0 or r > 5000.0:
            continue
        dists = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r)
        mask = dists <= inlier_thresh_px
        count = int(np.sum(mask))
        if count > best_count:
            best_count = count
            best_inliers = pts[mask]
    if best_inliers is None or best_count < 5:
        return fit_taubin(pts)
    return fit_taubin(best_inliers)


def sample_rasterized_arc_points(
    radius: float,
    sweep_deg: float,
    stroke_width: int = 1,
    center: tuple[float, float] = (200.0, 200.0),
) -> np.ndarray:
    """Render an arc to a raster canvas and extract foreground pixel coordinates."""
    img = np.full((400, 400), 255, dtype=np.uint8)
    cv2.ellipse(
        img,
        (int(center[0]), int(center[1])),
        (int(round(radius)), int(round(radius))),
        0.0,
        0.0,
        sweep_deg,
        0,
        stroke_width,
    )
    ys, xs = np.where(img < 128)
    return np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])


def run_benchmark() -> None:
    radii = [12.0, 20.0, 40.0, 80.0, 120.0]
    sweeps = [30.0, 45.0, 60.0, 90.0, 120.0, 180.0, 270.0, 330.0]
    true_center = (200.0, 200.0)

    strategies = [
        ("STRATEGY_A (KASA)", fit_kasa),
        ("STRATEGY_B (TAUBIN)", fit_taubin),
        ("STRATEGY_C (PRATT)", fit_pratt),
        ("STRATEGY_D (MIN_ENCLOSING)", fit_min_enclosing),
        ("STRATEGY_E (RANSAC+TAUBIN)", fit_ransac_taubin),
    ]

    print("=== SECTION 12: CIRCULAR ARC FITTING STRATEGIES BENCHMARK (CLEAN RASTER ARCS) ===")
    print(f"Tested across {len(radii)} radii {radii} x {len(sweeps)} sweeps {sweeps} = {len(radii)*len(sweeps)} cases")
    print("-" * 108)
    print(f"{'Strategy':<28} | {'Mean Ctr Err':<13} | {'90deg Ctr Err':<14} | {'30deg Ctr Err':<14} | {'Mean Rad Err%':<14} | {'Time/Fit (us)'}")
    print("-" * 108)

    for name, fn in strategies:
        c_errs = []
        c_errs_90 = []
        c_errs_30 = []
        r_err_pcts = []
        t0 = time.perf_counter()
        for r in radii:
            for sw in sweeps:
                pts = sample_rasterized_arc_points(r, sw, stroke_width=2, center=true_center)
                res = fn(pts)
                if res is None:
                    c_err = 999.0
                    r_pct = 100.0
                else:
                    cx, cy, rf = res
                    c_err = math.hypot(cx - true_center[0], cy - true_center[1])
                    r_pct = abs(rf - r) / r * 100.0
                c_errs.append(c_err)
                r_err_pcts.append(r_pct)
                if sw == 90.0:
                    c_errs_90.append(c_err)
                if sw == 30.0:
                    c_errs_30.append(c_err)
        dt_us = (time.perf_counter() - t0) / (len(radii) * len(sweeps)) * 1e6
        print(
            f"{name:<28} | {np.mean(c_errs):>9.3f} px | {np.mean(c_errs_90):>10.3f} px | "
            f"{np.mean(c_errs_30):>10.3f} px | {np.mean(r_err_pcts):>11.2f} % | {dt_us:>9.1f} us"
        )

    print("\n=== CONTAMINATION SENSITIVITY TEST (90-DEG ARC R=50PX + 15% OUTLIER SPUR PIXELS) ===")
    pts_clean = sample_rasterized_arc_points(50.0, 90.0, stroke_width=1, center=true_center)
    rng = np.random.default_rng(123)
    n_out = max(1, int(0.15 * len(pts_clean)))
    # Add tangent spur / witness line contamination off the arc
    spur_x = np.linspace(250.0, 275.0, n_out)
    spur_y = np.full(n_out, 200.0) + rng.normal(0, 0.5, size=n_out)
    pts_contaminated = np.vstack([pts_clean, np.column_stack([spur_x, spur_y])])

    for name, fn in strategies:
        res = fn(pts_contaminated)
        if res is not None:
            cx, cy, rf = res
            cerr = math.hypot(cx - true_center[0], cy - true_center[1])
            rerr = abs(rf - 50.0)
            print(f"  {name:<28}: center_err={cerr:6.2f} px, radius_err={rerr:6.2f} px (fitted R={rf:.2f})")


if __name__ == "__main__":
    run_benchmark()
