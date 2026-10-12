"""True Arc Empirical Matrix (Section 13).

Measures representative combinations of:
- RADII_PX: 5, 8, 12, 20, 40, 80, 120
- SWEEP_DEG: 15, 30, 45, 60, 90, 120, 180, 240, 270, 300, 330
- START_ANGLE_DEG: 0, 30, 90, 135, 225
- STROKE_WIDTH_PX: 1, 2, 3, 5, 8
- Anti-aliased (LINE_AA) vs Non-antialiased (LINE_8) controls

Records all 16 required metrics for each configuration.
"""

from __future__ import annotations

import math
from typing import Optional

import cv2
import numpy as np


def thin_zhang_suen_local(binary: np.ndarray) -> np.ndarray:
    """Candidate-local topology-preserving 2-pass Zhang-Suen skeletonization.

    Operates strictly on a local cropped component mask (0/1 uint8), never globally.
    """
    img = np.pad((binary > 0).astype(np.uint8), 1, mode="constant", constant_values=0)
    changed = True
    while changed:
        changed = False
        for pass_idx in (0, 1):
            p2 = img[:-2, 1:-1]
            p3 = img[:-2, 2:]
            p4 = img[1:-1, 2:]
            p5 = img[2:, 2:]
            p6 = img[2:, 1:-1]
            p7 = img[2:, :-2]
            p8 = img[1:-1, :-2]
            p9 = img[:-2, :-2]

            neighbors = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            transitions = (
                ((p2 == 0) & (p3 == 1)).astype(np.uint8)
                + ((p3 == 0) & (p4 == 1)).astype(np.uint8)
                + ((p4 == 0) & (p5 == 1)).astype(np.uint8)
                + ((p5 == 0) & (p6 == 1)).astype(np.uint8)
                + ((p6 == 0) & (p7 == 1)).astype(np.uint8)
                + ((p7 == 0) & (p8 == 1)).astype(np.uint8)
                + ((p8 == 0) & (p9 == 1)).astype(np.uint8)
                + ((p9 == 0) & (p2 == 1)).astype(np.uint8)
            )
            cond = (img[1:-1, 1:-1] == 1) & (neighbors >= 2) & (neighbors <= 6) & (transitions == 1)
            if pass_idx == 0:
                cond &= (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                cond &= (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)

            if np.any(cond):
                img[1:-1, 1:-1][cond] = 0
                changed = True
    return img[1:-1, 1:-1]


def fit_taubin_weighted(pts: np.ndarray, weights: Optional[np.ndarray] = None) -> Optional[tuple[float, float, float]]:
    """Taubin (1991) gradient-normalized algebraic circle fit (with optional medial weights)."""
    n = len(pts)
    if n < 3:
        return None
    x = pts[:, 0].astype(np.float64)
    y = pts[:, 1].astype(np.float64)
    if weights is None:
        w = np.ones(n, dtype=np.float64) / float(n)
    else:
        w_raw = np.asarray(weights, dtype=np.float64)
        w_sum = float(np.sum(w_raw))
        w = w_raw / w_sum if w_sum > 0 else np.ones(n, dtype=np.float64) / float(n)

    mx = float(np.sum(w * x))
    my = float(np.sum(w * y))
    X = x - mx
    Y = y - my
    Z = X * X + Y * Y
    Mz = float(np.sum(w * Z))
    if Mz <= 1e-12:
        return None
    Z0 = Z - Mz
    V = np.column_stack([Z0, X, Y])
    M = V.T @ (V * w[:, None])
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


def fit_taubin(pts: np.ndarray) -> Optional[tuple[float, float, float]]:
    return fit_taubin_weighted(pts, None)


def line_fit_rms(pts: np.ndarray) -> float:
    """Orthogonal (total least squares) straight-line RMS residual."""
    if len(pts) < 2:
        return 0.0
    centered = pts - np.mean(pts, axis=0)
    cov = (centered.T @ centered) / float(len(pts))
    evals = np.linalg.eigvalsh(cov)
    return math.sqrt(max(0.0, float(evals[0])))


def extract_and_evaluate_arc(
    gray: np.ndarray,
    min_sweep_deg: float = 45.0,
    max_sweep_deg: float = 340.0,
    min_sagitta_px: float = 2.0,
) -> Optional[dict]:
    """Extract candidate medial arc points, fit Taubin circle, and recover angular span/endpoints."""
    binary = (gray < 220).astype(np.uint8)
    ys_all, xs_all = np.where(binary > 0)
    if len(xs_all) < 5:
        return None

    # Local bbox crop for candidate-local distance transform & skeletonization
    x0, x1 = max(0, int(np.min(xs_all)) - 2), min(gray.shape[1], int(np.max(xs_all)) + 3)
    y0, y1 = max(0, int(np.min(ys_all)) - 2), min(gray.shape[0], int(np.max(ys_all)) + 3)
    local_bin = binary[y0:y1, x0:x1]

    # Distance transform gives local medial ridge weight (peaks at true stroke centerline)
    dist_map = cv2.distanceTransform(local_bin, cv2.DIST_L2, 3)
    max_half_w = float(np.max(dist_map))
    skel = thin_zhang_suen_local(local_bin)
    sy, sx = np.where(skel > 0)

    pts_all = np.column_stack([xs_all.astype(np.float64), ys_all.astype(np.float64)])
    weights_all = (dist_map[ys_all - y0, xs_all - x0] ** 2).astype(np.float64)

    # Fit circle on distance-ridge weighted foreground points (avoids endpoint erosion bias on short arcs)
    fit = fit_taubin_weighted(pts_all, weights_all)
    if fit is None:
        return None
    cx, cy, r_raw = fit
    if r_raw < 3.0 or r_raw > 2000.0:
        return None

    # Refine centerline radius as distance-weighted median radial distance to (cx, cy)
    rad_all = np.hypot(pts_all[:, 0] - cx, pts_all[:, 1] - cy)
    r = float(np.median(rad_all))

    # Evaluate medial radial residuals on skeleton points (or ridge points if skeleton too short)
    if len(sx) >= 5:
        pts_medial = np.column_stack([(sx + x0).astype(np.float64), (sy + y0).astype(np.float64)])
    else:
        pts_medial = pts_all
    rad_medial = np.hypot(pts_medial[:, 0] - cx, pts_medial[:, 1] - cy)
    residuals = np.abs(rad_medial - r)
    rms_res = float(np.sqrt(np.mean(residuals ** 2)))
    max_res = float(np.max(residuals))

    # Recover angular span from un-eroded foreground points near the centerline radius
    ring_mask = np.abs(rad_all - r) <= max(1.5, max_half_w + 0.5)
    pts_ring = pts_all[ring_mask] if np.sum(ring_mask) >= 5 else pts_all

    angles_deg = (np.degrees(np.arctan2(pts_ring[:, 1] - cy, pts_ring[:, 0] - cx)) + 360.0) % 360.0
    order = np.argsort(angles_deg)
    sorted_angles = angles_deg[order]
    diffs = np.diff(sorted_angles)
    wrap_diff = (sorted_angles[0] + 360.0) - sorted_angles[-1]
    all_gaps = np.append(diffs, wrap_diff)

    max_gap_idx = int(np.argmax(all_gaps))
    max_gap_deg = float(all_gaps[max_gap_idx])
    raw_sweep_deg = 360.0 - max_gap_deg

    start_idx = (max_gap_idx + 1) % len(sorted_angles)
    end_idx = max_gap_idx
    raw_start_deg = float(sorted_angles[start_idx])
    raw_end_deg = float(sorted_angles[end_idx])

    # Compensate for round stroke-cap overhang on thick strokes (cap radius = max(0, max_half_w - 1.0))
    cap_overhang_px = max(0.0, max_half_w - 1.0)
    cap_angle_deg = math.degrees(math.atan2(cap_overhang_px, r)) if r > 1.0 else 0.0
    if raw_sweep_deg > 2.0 * cap_angle_deg + 5.0:
        start_angle_deg = (raw_start_deg + cap_angle_deg) % 360.0
        end_angle_deg = (raw_end_deg - cap_angle_deg + 360.0) % 360.0
        measured_sweep_deg = raw_sweep_deg - 2.0 * cap_angle_deg
    else:
        start_angle_deg = raw_start_deg
        end_angle_deg = raw_end_deg
        measured_sweep_deg = raw_sweep_deg

    start_pt = (cx + r * math.cos(math.radians(start_angle_deg)), cy + r * math.sin(math.radians(start_angle_deg)))
    end_pt = (cx + r * math.cos(math.radians(end_angle_deg)), cy + r * math.sin(math.radians(end_angle_deg)))

    sagitta_px = r * (1.0 - math.cos(math.radians(min(measured_sweep_deg, 180.0)) / 2.0))
    l_rms = line_fit_rms(pts_medial)

    fit_accepted = (
        rms_res <= max(0.75, 0.04 * r)
        and max_res <= max(1.8, 0.09 * r)
        and r >= 4.5
    )
    arc_classified = (
        fit_accepted
        and sagitta_px >= min_sagitta_px
        and measured_sweep_deg >= min_sweep_deg
        and measured_sweep_deg <= max_sweep_deg
        and (l_rms >= 0.80 or measured_sweep_deg >= 60.0)
        and rms_res < 0.65 * max(l_rms, 1e-6)
    )

    return {
        "cx": cx,
        "cy": cy,
        "r": r,
        "rms_res": rms_res,
        "max_res": max_res,
        "measured_sweep_deg": measured_sweep_deg,
        "start_angle_deg": start_angle_deg,
        "end_angle_deg": end_angle_deg,
        "start_pt": start_pt,
        "end_pt": end_pt,
        "sagitta_px": sagitta_px,
        "line_rms_px": l_rms,
        "fit_accepted": fit_accepted,
        "arc_classified": arc_classified,
    }


def _angle_diff_deg(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def eval_single_config(
    r: float,
    sweep_deg: float,
    start_deg: float,
    stroke_w: int,
    line_type: int = cv2.LINE_8,
) -> dict:
    canvas = 360
    tcx, tcy = 180.0, 180.0
    gray = np.full((canvas, canvas), 255, dtype=np.uint8)
    cv2.ellipse(
        gray,
        (int(tcx), int(tcy)),
        (int(round(r)), int(round(r))),
        0.0,
        start_deg,
        start_deg + sweep_deg,
        0,
        stroke_w,
        lineType=line_type,
    )

    expected_start = start_deg % 360.0
    expected_end = (start_deg + sweep_deg) % 360.0
    true_start_pt = (tcx + r * math.cos(math.radians(expected_start)), tcy + r * math.sin(math.radians(expected_start)))
    true_end_pt = (tcx + r * math.cos(math.radians(expected_end)), tcy + r * math.sin(math.radians(expected_end)))

    res = extract_and_evaluate_arc(gray)
    if res is None:
        return {
            "r": r, "sweep": sweep_deg, "start": start_deg, "w": stroke_w,
            "CENTER_ERROR_PX": 999.0, "CENTER_ERROR_OVER_RADIUS": 99.0,
            "RADIUS_ERROR_PX": 999.0, "RADIUS_ERROR_PERCENT": 100.0,
            "RADIAL_RMS_RESIDUAL_PX": 999.0, "RADIAL_MAX_RESIDUAL_PX": 999.0,
            "EXPECTED_SWEEP_DEG": sweep_deg, "MEASURED_SWEEP_DEG": 0.0, "SWEEP_ERROR_DEG": sweep_deg,
            "START_ENDPOINT_ERROR_PX": 999.0, "END_ENDPOINT_ERROR_PX": 999.0,
            "EXPECTED_START_ANGLE": expected_start, "MEASURED_START_ANGLE": 0.0,
            "EXPECTED_END_ANGLE": expected_end, "MEASURED_END_ANGLE": 0.0,
            "FIT_ACCEPTED": False, "ARC_CLASSIFIED": False,
        }

    c_err = math.hypot(res["cx"] - tcx, res["cy"] - tcy)
    r_err = abs(res["r"] - r)
    sw_err = abs(res["measured_sweep_deg"] - sweep_deg)
    s_ep_err = math.hypot(res["start_pt"][0] - true_start_pt[0], res["start_pt"][1] - true_start_pt[1])
    e_ep_err = math.hypot(res["end_pt"][0] - true_end_pt[0], res["end_pt"][1] - true_end_pt[1])

    return {
        "r": r, "sweep": sweep_deg, "start": start_deg, "w": stroke_w,
        "CENTER_ERROR_PX": c_err,
        "CENTER_ERROR_OVER_RADIUS": c_err / r,
        "RADIUS_ERROR_PX": r_err,
        "RADIUS_ERROR_PERCENT": (r_err / r) * 100.0,
        "RADIAL_RMS_RESIDUAL_PX": res["rms_res"],
        "RADIAL_MAX_RESIDUAL_PX": res["max_res"],
        "EXPECTED_SWEEP_DEG": sweep_deg,
        "MEASURED_SWEEP_DEG": res["measured_sweep_deg"],
        "SWEEP_ERROR_DEG": sw_err,
        "START_ENDPOINT_ERROR_PX": s_ep_err,
        "END_ENDPOINT_ERROR_PX": e_ep_err,
        "EXPECTED_START_ANGLE": expected_start,
        "MEASURED_START_ANGLE": res["start_angle_deg"],
        "EXPECTED_END_ANGLE": expected_end,
        "MEASURED_END_ANGLE": res["end_angle_deg"],
        "FIT_ACCEPTED": res["fit_accepted"],
        "ARC_CLASSIFIED": res["arc_classified"],
    }


def run_true_arc_matrix() -> None:
    radii = [5, 8, 12, 20, 40, 80, 120]
    sweeps = [15, 30, 45, 60, 90, 120, 180, 240, 270, 300, 330]
    start_angles = [0, 30, 90, 135, 225]
    stroke_widths = [1, 2, 3, 5, 8]

    print("=== SECTION 13: REPRESENTATIVE TRUE ARC MATRIX ===")
    # Sub-matrix 1: All 7 radii x 11 sweeps (77 cases) at w=2, start=0
    rows_r_sw = []
    for r in radii:
        for sw in sweeps:
            rows_r_sw.append(eval_single_config(float(r), float(sw), 0.0, 2))

    print("\n--- 13A. SUMMARY BY SWEEP ANGLE (Across Radii >= 12px, w=2px, start=0deg) ---")
    print(f"{'Sweep':<8} | {'FitAcc':<8} | {'ArcCls':<8} | {'CtrErr(px)':<11} | {'Ctr/R':<8} | {'RadErr%':<9} | {'RMS(px)':<8} | {'SwpErr(deg)':<12} | {'EndptErr(px)'}")
    print("-" * 106)
    for sw in sweeps:
        sub = [m for m in rows_r_sw if m["sweep"] == sw and m["r"] >= 12]
        fa = sum(1 for m in sub if m["FIT_ACCEPTED"])
        ac = sum(1 for m in sub if m["ARC_CLASSIFIED"])
        ce = np.mean([m["CENTER_ERROR_PX"] for m in sub])
        cor = np.mean([m["CENTER_ERROR_OVER_RADIUS"] for m in sub])
        rep = np.mean([m["RADIUS_ERROR_PERCENT"] for m in sub])
        rms = np.mean([m["RADIAL_RMS_RESIDUAL_PX"] for m in sub])
        swe = np.mean([m["SWEEP_ERROR_DEG"] for m in sub])
        epe = np.mean([0.5 * (m["START_ENDPOINT_ERROR_PX"] + m["END_ENDPOINT_ERROR_PX"]) for m in sub])
        print(f"{sw:>5} deg | {fa}/{len(sub):<5} | {ac}/{len(sub):<5} | {ce:>9.3f}   | {cor:>6.3f}   | {rep:>7.2f}% | {rms:>6.3f}   | {swe:>9.2f}    | {epe:>9.3f}")

    print("\n--- 13B. SUMMARY BY RADIUS (Across Sweeps >= 45deg, w=2px, start=0deg) ---")
    print(f"{'Radius':<8} | {'FitAcc':<8} | {'ArcCls':<8} | {'CtrErr(px)':<11} | {'RadErr(px)':<11} | {'RadErr%':<9} | {'RMS(px)':<8} | {'MaxRes(px)':<11} | {'EndptErr(px)'}")
    print("-" * 106)
    for r in radii:
        sub = [m for m in rows_r_sw if m["r"] == r and m["sweep"] >= 45]
        fa = sum(1 for m in sub if m["FIT_ACCEPTED"])
        ac = sum(1 for m in sub if m["ARC_CLASSIFIED"])
        ce = np.mean([m["CENTER_ERROR_PX"] for m in sub])
        re = np.mean([m["RADIUS_ERROR_PX"] for m in sub])
        rep = np.mean([m["RADIUS_ERROR_PERCENT"] for m in sub])
        rms = np.mean([m["RADIAL_RMS_RESIDUAL_PX"] for m in sub])
        mxr = np.mean([m["RADIAL_MAX_RESIDUAL_PX"] for m in sub])
        epe = np.mean([0.5 * (m["START_ENDPOINT_ERROR_PX"] + m["END_ENDPOINT_ERROR_PX"]) for m in sub])
        print(f"{r:>5} px | {fa}/{len(sub):<5} | {ac}/{len(sub):<5} | {ce:>9.3f}   | {re:>9.3f}   | {rep:>7.2f}% | {rms:>6.3f}   | {mxr:>9.3f}   | {epe:>9.3f}")

    # Sub-matrix 2: Start angles [0, 30, 90, 135, 225] x Stroke widths [1, 2, 3, 5, 8] at r=40, sweep=90 & 180
    print("\n--- 13C. SUMMARY BY STROKE WIDTH & START ANGLE (r=40px, sweeps=[90, 180], 5 start angles) ---")
    print(f"{'StrokeW':<8} | {'ArcCls':<8} | {'CtrErr(px)':<11} | {'RadErr(px)':<11} | {'RadErr%':<9} | {'SwpErr(deg)':<12} | {'StartEpErr':<11} | {'EndEpErr'}")
    print("-" * 98)
    for w in stroke_widths:
        sub_w = []
        for sa in start_angles:
            for sw in (90.0, 180.0):
                sub_w.append(eval_single_config(40.0, sw, float(sa), w))
        ac = sum(1 for m in sub_w if m["ARC_CLASSIFIED"])
        ce = np.mean([m["CENTER_ERROR_PX"] for m in sub_w])
        re = np.mean([m["RADIUS_ERROR_PX"] for m in sub_w])
        rep = np.mean([m["RADIUS_ERROR_PERCENT"] for m in sub_w])
        swe = np.mean([m["SWEEP_ERROR_DEG"] for m in sub_w])
        se = np.mean([m["START_ENDPOINT_ERROR_PX"] for m in sub_w])
        ee = np.mean([m["END_ENDPOINT_ERROR_PX"] for m in sub_w])
        print(f"{w:>5} px | {ac}/{len(sub_w):<5} | {ce:>9.3f}   | {re:>9.3f}   | {rep:>7.2f}% | {swe:>9.2f}    | {se:>9.3f}   | {ee:>8.3f}")

    # Sub-matrix 3: Anti-aliased (LINE_AA) vs Non-antialiased (LINE_8) control
    print("\n--- 13D. ANTI-ALIASED (LINE_AA) VS NON-ANTIALIASED (LINE_8) CONTROL (r=40px, w=2px, sweeps 45..300) ---")
    for lt_name, lt_flag in [("NON_AA (LINE_8)", cv2.LINE_8), ("ANTI_ALIASED (LINE_AA)", cv2.LINE_AA)]:
        sub_lt = [eval_single_config(40.0, float(sw), 30.0, 2, line_type=lt_flag) for sw in (45, 90, 180, 270, 300)]
        ac = sum(1 for m in sub_lt if m["ARC_CLASSIFIED"])
        ce = np.mean([m["CENTER_ERROR_PX"] for m in sub_lt])
        rep = np.mean([m["RADIUS_ERROR_PERCENT"] for m in sub_lt])
        swe = np.mean([m["SWEEP_ERROR_DEG"] for m in sub_lt])
        print(f"  {lt_name:<24}: ArcCls={ac}/{len(sub_lt)}, MeanCtrErr={ce:.3f}px, MeanRadErr={rep:.2f}%, MeanSweepErr={swe:.2f}deg")


if __name__ == "__main__":
    run_true_arc_matrix()
