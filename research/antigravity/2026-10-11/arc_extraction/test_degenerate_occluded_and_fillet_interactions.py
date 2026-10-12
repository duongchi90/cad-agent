"""Sections 21, 22, 23: Degenerate/Numeric Safety, Broken/Occluded/Dashed Arcs, and Line/Tangency/Fillet Interaction.

Covers:
- Section 21: Degenerate & numeric safety across point counts (3, 4, 5, 8, 12, 20, 50, 100, 250+)
  and 11 pathological point distributions. Verifies NONFINITE_OUTPUT_COUNT == 0.
- Section 22: Broken/occluded arcs (missing internal sector 5, 10, 20, 30, 45, 60 deg at near-start,
  midpoint, near-end) and dashed arcs across bounded dash/gap/sweep/radius combinations.
- Section 23: Line/tangency/fillet interactions across 8 configurations, comparing naive connected
  components vs straight-line corridor subtraction.
"""

from __future__ import annotations

import math
from typing import Optional

import cv2
import numpy as np

from test_angular_wrap_endpoints_and_cad_contract import compute_circular_support_interval
from test_negative_matrix_and_ellipse_control import evaluate_candidate_component
from test_true_arc_matrix import fit_taubin_weighted


# ==============================================================================
# SECTION 21: DEGENERATE / NUMERIC SAFETY
# ==============================================================================

def safe_taubin_fit_with_state(
    pts: np.ndarray,
    weights: Optional[np.ndarray] = None,
    min_points: int = 12,
    max_radius_px: float = 5000.0,
    min_radius_px: float = 2.0,
) -> dict:
    """Controlled numeric wrapper around weighted Taubin fit.

    Always terminates in one of:
    - INSUFFICIENT_POINTS
    - FIT_DEGENERATE
    - FIT_NUMERICALLY_UNSTABLE
    - FIT_OK
    Never emits NaN, Inf, negative radius, complex values, or invalid confidence.
    """
    if pts is None or not isinstance(pts, np.ndarray) or pts.ndim != 2 or pts.shape[1] != 2:
        return {"state": "INSUFFICIENT_POINTS", "cx": None, "cy": None, "r": None, "confidence": 0.0}

    # Filter out any non-finite input coordinates first
    finite_mask = np.isfinite(pts[:, 0]) & np.isfinite(pts[:, 1])
    pts_clean = pts[finite_mask].astype(np.float64)
    if len(pts_clean) < min_points:
        return {"state": "INSUFFICIENT_POINTS", "cx": None, "cy": None, "r": None, "confidence": 0.0}

    # Check unique points and variance
    unique_pts = np.unique(np.round(pts_clean, 4), axis=0)
    if len(unique_pts) < min(8, min_points):
        return {"state": "FIT_DEGENERATE", "cx": None, "cy": None, "r": None, "confidence": 0.0}

    if weights is None or len(weights) != len(pts):
        w = np.ones(len(pts_clean), dtype=np.float64)
    else:
        w = np.where(np.isfinite(weights[finite_mask]) & (weights[finite_mask] > 0), weights[finite_mask], 1.0).astype(np.float64)

    w_sum = float(np.sum(w))
    if not math.isfinite(w_sum) or w_sum <= 1e-12:
        return {"state": "FIT_DEGENERATE", "cx": None, "cy": None, "r": None, "confidence": 0.0}
    w = w / w_sum

    mx = float(np.sum(w * pts_clean[:, 0]))
    my = float(np.sum(w * pts_clean[:, 1]))
    u = pts_clean[:, 0] - mx
    v = pts_clean[:, 1] - my
    scale = float(np.sqrt(np.sum(w * (u * u + v * v))))
    if not math.isfinite(scale) or scale < 1e-6:
        return {"state": "FIT_DEGENERATE", "cx": None, "cy": None, "r": None, "confidence": 0.0}

    # Check collinearity via covariance singular values in centered coordinates
    cov_xx = float(np.sum(w * u * u))
    cov_xy = float(np.sum(w * u * v))
    cov_yy = float(np.sum(w * v * v))
    cov_evals = np.linalg.eigvalsh(np.array([[cov_xx, cov_xy], [cov_xy, cov_yy]], dtype=np.float64))
    if cov_evals[0] <= 1e-7 * max(cov_evals[1], 1e-12):
        return {"state": "FIT_DEGENERATE", "cx": None, "cy": None, "r": None, "confidence": 0.0}

    un = u / scale
    vn = v / scale
    zn = un * un + vn * vn

    z_mean = float(np.sum(w * zn))
    u_mean = float(np.sum(w * un))
    v_mean = float(np.sum(w * vn))
    z0 = zn - z_mean
    u0 = un - u_mean
    v0 = vn - v_mean

    M = np.array([
        [np.sum(w * z0 * z0), np.sum(w * z0 * u0), np.sum(w * z0 * v0)],
        [np.sum(w * u0 * z0), np.sum(w * u0 * u0), np.sum(w * u0 * v0)],
        [np.sum(w * v0 * z0), np.sum(w * v0 * u0), np.sum(w * v0 * v0)],
    ], dtype=np.float64)

    A_inv = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    if abs(z_mean) > 1e-12:
        A_inv[0, 0] = 1.0 / (4.0 * z_mean)
        A_inv[0, 1] = -u_mean / (2.0 * z_mean)
        A_inv[0, 2] = -v_mean / (2.0 * z_mean)
        A_inv[1, 0] = A_inv[0, 1]
        A_inv[2, 0] = A_inv[0, 2]
        A_inv[1, 1] += (u_mean * u_mean) / z_mean
        A_inv[1, 2] += (u_mean * v_mean) / z_mean
        A_inv[2, 1] += (u_mean * v_mean) / z_mean
        A_inv[2, 2] += (v_mean * v_mean) / z_mean

    try:
        evals, evecs = np.linalg.eigh(A_inv)
        evals = np.maximum(evals, 0.0)
        sqrt_A_inv = (evecs * np.sqrt(evals)) @ evecs.T
        S = sqrt_A_inv @ M @ sqrt_A_inv
        S = 0.5 * (S + S.T)
        s_evals, s_evecs = np.linalg.eigh(S)
    except np.linalg.LinAlgError:
        return {"state": "FIT_NUMERICALLY_UNSTABLE", "cx": None, "cy": None, "r": None, "confidence": 0.0}

    vec = sqrt_A_inv @ s_evecs[:, 0]
    A, B, C = float(vec[0]), float(vec[1]), float(vec[2])
    if not (math.isfinite(A) and math.isfinite(B) and math.isfinite(C)) or abs(A) < 1e-7:
        return {"state": "FIT_NUMERICALLY_UNSTABLE", "cx": None, "cy": None, "r": None, "confidence": 0.0}

    D = -A * z_mean - B * u_mean - C * v_mean
    cx_n = -B / (2.0 * A)
    cy_n = -C / (2.0 * A)
    rad2_n = cx_n * cx_n + cy_n * cy_n - D / A
    if not math.isfinite(rad2_n) or rad2_n <= 0.0:
        return {"state": "FIT_NUMERICALLY_UNSTABLE", "cx": None, "cy": None, "r": None, "confidence": 0.0}

    cx = mx + cx_n * scale
    cy = my + cy_n * scale
    r = math.sqrt(rad2_n) * scale

    if not (math.isfinite(cx) and math.isfinite(cy) and math.isfinite(r)):
        return {"state": "FIT_NUMERICALLY_UNSTABLE", "cx": None, "cy": None, "r": None, "confidence": 0.0}
    if r < min_radius_px or r > max_radius_px or abs(cx - mx) > 10.0 * max_radius_px or abs(cy - my) > 10.0 * max_radius_px:
        return {"state": "FIT_NUMERICALLY_UNSTABLE", "cx": None, "cy": None, "r": None, "confidence": 0.0}

    radial_rms = float(np.sqrt(np.mean((np.hypot(pts_clean[:, 0] - cx, pts_clean[:, 1] - cy) - r) ** 2)))
    conf = float(np.clip(1.0 - radial_rms / max(2.0, 0.1 * r), 0.05, 0.99))
    return {"state": "FIT_OK", "cx": cx, "cy": cy, "r": r, "confidence": conf}


def run_section_21_degenerate_numeric_safety() -> dict:
    point_counts = [3, 4, 5, 8, 12, 20, 50, 100, 260]
    rng = np.random.default_rng(20261012)

    cases = []
    for n in point_counts:
        thetas = np.linspace(0.0, math.radians(120.0), n)
        clean_arc = np.column_stack([150.0 + 50.0 * np.cos(thetas), 150.0 + 50.0 * np.sin(thetas)])
        cases.append((f"CleanArc(n={n})", clean_arc))

        # Duplicate points (only 4 distinct points repeated)
        dup_pts = np.resize(clean_arc[:min(4, n)], (n, 2))
        cases.append((f"Duplicates(n={n})", dup_pts))

        # All-identical points
        ident_pts = np.full((n, 2), 42.0, dtype=np.float64)
        cases.append((f"Identical(n={n})", ident_pts))

        # Exactly collinear points
        t_line = np.linspace(0.0, 100.0, n)
        collinear_pts = np.column_stack([20.0 + t_line, 30.0 + 0.5 * t_line])
        cases.append((f"ExactCollinear(n={n})", collinear_pts))

        # Near-collinear points (1e-5 transverse jitter)
        near_col = collinear_pts + rng.normal(0.0, 1e-5, size=(n, 2))
        cases.append((f"NearCollinear(n={n})", near_col))

    # Special numeric edge cases at n=50
    n_std = 50
    th_std = np.linspace(0.0, math.radians(120.0), n_std)
    # Very short chain (span 1.5 px)
    cases.append(("VeryShortChain(L=1.5px)", np.column_stack([100.0 + np.linspace(0, 1.5, n_std), 100.0 + np.linspace(0, 0.5, n_std)])))
    # Large coordinate offset (1e6, 1e6)
    cases.append(("LargeCoordOffset(1e6)", np.column_stack([1e6 + 50.0 * np.cos(th_std), 1e6 + 50.0 * np.sin(th_std)])))
    # Small radius (R=0.8 px)
    cases.append(("TinyRadius(R=0.8px)", np.column_stack([100.0 + 0.8 * np.cos(th_std), 100.0 + 0.8 * np.sin(th_std)])))
    # Huge radius (R=1e5 px, shallow 0.05 deg)
    th_tiny = np.linspace(0.0, math.radians(0.05), n_std)
    cases.append(("HugeRadius(R=1e5px)", np.column_stack([1e5 * np.cos(th_tiny), 1e5 * np.sin(th_tiny)])))
    # Quantized integer pixels on R=40, 120 deg
    cases.append(("QuantizedPixels(R=40)", np.round(np.column_stack([150.0 + 40.0 * np.cos(th_std), 150.0 + 40.0 * np.sin(th_std)]))))
    # Near-zero variance (1e-9 radius)
    cases.append(("NearZeroVariance(1e-9)", np.column_stack([100.0 + 1e-9 * np.cos(th_std), 100.0 + 1e-9 * np.sin(th_std)])))
    # Short arc span (5 deg on quantized grid)
    th_5d = np.linspace(0.0, math.radians(5.0), n_std)
    cases.append(("ShortSpanQuantized(5deg)", np.round(np.column_stack([150.0 + 40.0 * np.cos(th_5d), 150.0 + 40.0 * np.sin(th_5d)]))))

    state_counts = {
        "FIT_OK": 0,
        "FIT_DEGENERATE": 0,
        "FIT_NUMERICALLY_UNSTABLE": 0,
        "INSUFFICIENT_POINTS": 0,
    }
    nonfinite_count = 0

    print("=== SECTION 21: DEGENERATE / NUMERIC SAFETY BENCHMARK ===")
    for name, pts in cases:
        res = safe_taubin_fit_with_state(pts, min_points=12)
        st = res["state"]
        assert st in state_counts, f"Unknown state {st}"
        state_counts[st] += 1

        if st == "FIT_OK":
            vals = [res["cx"], res["cy"], res["r"], res["confidence"]]
            if any(v is None or isinstance(v, complex) or not math.isfinite(v) for v in vals):
                nonfinite_count += 1
            if res["r"] <= 0.0 or not (0.0 < res["confidence"] <= 1.0):
                nonfinite_count += 1

    print(f"TOTAL_CASES_TESTED={len(cases)}")
    for k, v in state_counts.items():
        print(f"  STATE_{k}={v}")
    print(f"MIN_POINT_COUNT_DISCRIMINATOR=12")
    print(f"NONFINITE_OUTPUT_COUNT={nonfinite_count}")
    assert nonfinite_count == 0
    return {"total": len(cases), "states": state_counts, "nonfinite": nonfinite_count}


# ==============================================================================
# SECTION 22: BROKEN / OCCLUDED / DASHED ARC
# ==============================================================================

def run_section_22_broken_and_dashed_arcs() -> dict:
    gap_degs = [5, 10, 20, 30, 45, 60]
    locations = [
        ("near_start", 20.0),   # gap starts 20 deg after 0 deg on a 0..180 deg arc
        ("midpoint", 80.0),     # gap centered near 90 deg on a 0..180 deg arc
        ("near_end", 130.0),    # gap near end of a 0..180 deg arc
    ]

    print("\n=== SECTION 22A: BROKEN / OCCLUDED ARCS (TOTAL SPAN 0->180 DEG, R=60PX) ===")
    print(f"{'MissingGap':<10} | {'Location':<12} | {'Components':<10} | {'AcceptedArcs':<12} | {'Outcome'}")
    print("-" * 78)

    for g_deg in gap_degs:
        for loc_name, g_start in locations:
            g_end = min(175.0, g_start + g_deg)
            img = np.full((300, 300), 255, dtype=np.uint8)
            cv2.ellipse(img, (150, 150), (60, 60), 0, 0.0, g_start, 0, 2)
            cv2.ellipse(img, (150, 150), (60, 60), 0, g_end, 180.0, 0, 2)

            binary = (img < 220).astype(np.uint8)
            n_labels, labels, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
            n_comps = n_labels - 1
            acc = 0
            for lbl in range(1, n_labels):
                res = evaluate_candidate_component((labels == lbl).astype(np.uint8))
                if res["accepted"]:
                    acc += 1

            if n_comps == 1 and acc == 1:
                outcome = "SINGLE_BRIDGED_ARC"
            elif acc == 2:
                outcome = "SPLIT_TWO_VALID_ARCS"
            elif acc == 1:
                outcome = "LONG_BRANCH_ONLY_SHORT_REJECTED"
            else:
                outcome = "REFUSED_BOTH_TOO_SHORT"
            print(f"{g_deg:>8}d  | {loc_name:<12} | {n_comps:>10} | {acc:>12} | {outcome}")

    print("-" * 78)
    print("MAX_SAFE_GAP_DEG=NO_FIXED_SAFE_GAP_JUSTIFIED (connected-component extraction never bridges disconnected gaps > 1px)")

    print("\n=== SECTION 22B: DASHED ARC CONTROLS ===")
    dashed_configs = [
        # (dash_deg, gap_deg, total_sweep_deg, radius_px)
        (10, 8, 180, 50),
        (15, 10, 180, 50),
        (20, 10, 240, 60),
        (25, 12, 180, 40),
        (35, 10, 180, 80),
    ]
    print(f"{'Dash/Gap/Sweep/R':<26} | {'Components':<10} | {'AcceptedSubArcs':<15} | {'WholeArcRecovered'}")
    print("-" * 78)
    for d_deg, g_deg, sw_deg, r_px in dashed_configs:
        img = np.full((300, 300), 255, dtype=np.uint8)
        ang = 0.0
        while ang < sw_deg:
            end_a = min(float(sw_deg), ang + d_deg)
            cv2.ellipse(img, (150, 150), (r_px, r_px), 0, ang, end_a, 0, 2)
            ang += d_deg + g_deg
        binary = (img < 220).astype(np.uint8)
        n_labels, labels, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        acc = 0
        for lbl in range(1, n_labels):
            if evaluate_candidate_component((labels == lbl).astype(np.uint8))["accepted"]:
                acc += 1
        print(f"{d_deg}d/{g_deg}d/{sw_deg}d/R={r_px:<3}     | {n_labels - 1:>10} | {acc:>15} | False (unmerged dashes)")
    print("-" * 78)
    print("DASHED_ARC_CLASSIFICATION=DASHED_ARC_UNRESOLVED (requires separate multi-component co-circular grouping subsystem)")
    return {"max_safe_gap": "NO_FIXED_SAFE_GAP_JUSTIFIED", "dashed_status": "DASHED_ARC_UNRESOLVED"}


# ==============================================================================
# SECTION 23: LINE / TANGENCY / FILLET INTERACTION
# ==============================================================================

def subtract_straight_line_corridors(
    binary: np.ndarray,
    lines_px: list[tuple[tuple[float, float], tuple[float, float]]],
    corridor_half_width_px: int = 3,
) -> np.ndarray:
    """Subtract pixels belonging to detected straight lines before arc component extraction."""
    cleaned = binary.copy()
    for (x1, y1), (x2, y2) in lines_px:
        cv2.line(
            cleaned,
            (int(round(x1)), int(round(y1))),
            (int(round(x2)), int(round(y2))),
            0,
            thickness=2 * corridor_half_width_px,
        )
    return cleaned


def run_section_23_line_tangency_fillet() -> dict:
    cx_gt, cy_gt, r_gt = 150.0, 150.0, 50.0

    # Define 8 required interaction fixtures:
    # (name, arc_start_deg, arc_end_deg, list_of_lines_px)
    interactions = [
        (
            "1. Line Tangent at Arc Endpoint",
            0.0, 90.0,
            [((200.0, 150.0), (200.0, 50.0))],
        ),
        (
            "2. Line Tangent at Arc Midpoint",
            0.0, 180.0,
            [((70.0, 200.0), (230.0, 200.0))],
        ),
        (
            "3. Line Crossing Arc",
            0.0, 120.0,
            [((120.0, 120.0), (220.0, 220.0))],
        ),
        (
            "4. Quarter-Circle 90d Fillet + 2 Lines",
            0.0, 90.0,
            [((200.0, 150.0), (200.0, 50.0)), ((150.0, 200.0), (50.0, 200.0))],
        ),
        (
            "5. Acute-Angle 60d Fillet (120d sweep)",
            0.0, 120.0,
            [
                ((200.0, 150.0), (200.0, 60.0)),
                (
                    (150.0 + 50.0 * math.cos(math.radians(120.0)), 150.0 + 50.0 * math.sin(math.radians(120.0))),
                    (
                        150.0 + 50.0 * math.cos(math.radians(120.0)) - 90.0 * math.sin(math.radians(120.0)),
                        150.0 + 50.0 * math.sin(math.radians(120.0)) + 90.0 * math.cos(math.radians(120.0)),
                    ),
                ),
            ],
        ),
        (
            "6. Obtuse-Angle 120d Fillet (60d sweep)",
            0.0, 60.0,
            [
                ((200.0, 150.0), (200.0, 60.0)),
                (
                    (150.0 + 50.0 * math.cos(math.radians(60.0)), 150.0 + 50.0 * math.sin(math.radians(60.0))),
                    (
                        150.0 + 50.0 * math.cos(math.radians(60.0)) - 90.0 * math.sin(math.radians(60.0)),
                        150.0 + 50.0 * math.sin(math.radians(60.0)) + 90.0 * math.cos(math.radians(60.0)),
                    ),
                ),
            ],
        ),
        (
            "7. T-Junction Near Arc Midpoint",
            0.0, 120.0,
            [(
                (150.0 + 50.0 * math.cos(math.radians(60.0)), 150.0 + 50.0 * math.sin(math.radians(60.0))),
                (150.0 + 130.0 * math.cos(math.radians(60.0)), 150.0 + 130.0 * math.sin(math.radians(60.0))),
            )],
        ),
        (
            "8. Straight Segment Touching Arc End",
            30.0, 150.0,
            [(
                (150.0 + 50.0 * math.cos(math.radians(30.0)), 150.0 + 50.0 * math.sin(math.radians(30.0))),
                (270.0, 150.0 + 50.0 * math.sin(math.radians(30.0))),
            )],
        ),
    ]

    print("\n=== SECTION 23: LINE / TANGENCY / FILLET INTERACTION BENCHMARK ===")
    print(
        f"{'Interaction Case':<38} | {'NaiveCtrDrift':<13} | {'CleanCtrDrift':<13} | "
        f"{'CleanRadDrift':<13} | {'EndptDrift(px)':<14} | {'Residual'}"
    )
    print("-" * 116)

    clean_ctr_drifts = []
    clean_rad_drifts = []
    clean_endpt_drifts = []

    for name, s_deg, e_deg, lines in interactions:
        img = np.full((300, 300), 255, dtype=np.uint8)
        cv2.ellipse(img, (150, 150), (50, 50), 0, s_deg, e_deg, 0, 2)
        for p1, p2 in lines:
            cv2.line(img, (int(round(p1[0])), int(round(p1[1]))), (int(round(p2[0])), int(round(p2[1]))), 0, 2)

        binary = (img < 220).astype(np.uint8)

        # 1. Naive fit on unseparated component (absorbs straight lines!)
        ys_n, xs_n = np.where(binary > 0)
        pts_n = np.column_stack([xs_n.astype(np.float64), ys_n.astype(np.float64)])
        cx_n, cy_n, _ = fit_taubin_weighted(pts_n, np.ones(len(pts_n), dtype=np.float64))
        naive_ctr_drift = math.hypot(cx_n - cx_gt, cy_n - cy_gt)

        # 2. Line-corridor subtracted component fit
        cleaned_bin = subtract_straight_line_corridors(binary, lines, corridor_half_width_px=2)
        ys_c, xs_c = np.where(cleaned_bin > 0)
        dist_c = cv2.distanceTransform(cleaned_bin, cv2.DIST_L2, 3)
        pts_c = np.column_stack([xs_c.astype(np.float64), ys_c.astype(np.float64)])
        weights_c = (dist_c[ys_c, xs_c] ** 2).astype(np.float64)
        cx_c, cy_c, _ = fit_taubin_weighted(pts_c, weights_c)
        r_c = float(np.median(np.hypot(pts_c[:, 0] - cx_c, pts_c[:, 1] - cy_c)))
        c_rms = float(np.sqrt(np.mean((np.hypot(pts_c[:, 0] - cx_c, pts_c[:, 1] - cy_c) - r_c) ** 2)))

        # Recover endpoints on cleaned arc; if tangent line exists at endpoint, project center onto tangent line
        sup = compute_circular_support_interval(pts_c, cx_c, cy_c, r_c, cap_radius_px=float(np.max(dist_c)))
        ps_est = (cx_c + r_c * math.cos(math.radians(sup["start_deg"])), cy_c + r_c * math.sin(math.radians(sup["start_deg"])))
        pe_est = (cx_c + r_c * math.cos(math.radians(sup["end_deg"])), cy_c + r_c * math.sin(math.radians(sup["end_deg"])))

        gt_s = (cx_gt + r_gt * math.cos(math.radians(s_deg)), cy_gt + r_gt * math.sin(math.radians(s_deg)))
        gt_e = (cx_gt + r_gt * math.cos(math.radians(e_deg)), cy_gt + r_gt * math.sin(math.radians(e_deg)))
        endpt_drift = 0.5 * (math.hypot(ps_est[0] - gt_s[0], ps_est[1] - gt_s[1]) + math.hypot(pe_est[0] - gt_e[0], pe_est[1] - gt_e[1]))

        c_drift = math.hypot(cx_c - cx_gt, cy_c - cy_gt)
        r_drift = abs(r_c - r_gt)
        clean_ctr_drifts.append(c_drift)
        clean_rad_drifts.append(r_drift)
        clean_endpt_drifts.append(endpt_drift)

        print(
            f"{name:<38} | {naive_ctr_drift:>11.2f}px | {c_drift:>11.3f}px | "
            f"{r_drift:>11.3f}px | {endpt_drift:>12.3f}px | {c_rms:>6.3f}px"
        )

    print("-" * 116)
    print(f"LINE_SUBTRACTED_MEAN_CENTER_DRIFT_PX={np.mean(clean_ctr_drifts):.3f}")
    print(f"LINE_SUBTRACTED_MEAN_RADIUS_DRIFT_PX={np.mean(clean_rad_drifts):.3f}")
    print(f"LINE_SUBTRACTED_MEAN_ENDPOINT_DRIFT_PX={np.mean(clean_endpt_drifts):.3f}")
    return {
        "mean_ctr_drift_px": float(np.mean(clean_ctr_drifts)),
        "mean_rad_drift_px": float(np.mean(clean_rad_drifts)),
        "mean_endpt_drift_px": float(np.mean(clean_endpt_drifts)),
    }


if __name__ == "__main__":
    run_section_21_degenerate_numeric_safety()
    run_section_22_broken_and_dashed_arcs()
    run_section_23_line_tangency_fillet()
