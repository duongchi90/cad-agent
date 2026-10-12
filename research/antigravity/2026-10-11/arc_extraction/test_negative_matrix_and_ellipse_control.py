"""Sections 19 & 20: False-Positive Negative Matrix and Ellipse Control Benchmark.

Covers:
- Section 19: Consolidated negative-control benchmark across 26 families (lines, parallel lines,
  grid, cross hatch, dense hatch, 90/45/acute corners, rounded rectangle, rectangle, capsule/stadium,
  dimension arrowhead, random noise, speckle clusters, full circle, concentric circles, ellipse,
  and glyphs C, G, O, 0, 8, S, U, J, ) across multiple scales and stroke widths).
- Section 20: Ellipse axis ratios (1.00, 1.05, 1.10, 1.20, 1.50, 2.00) x sweeps (45, 60, 90, 120, 180, 270 deg)
  x orientations (0, 30, 45, 90 deg).
"""

from __future__ import annotations

import math
from typing import Optional

import cv2
import numpy as np

from test_arc_vs_line_discrimination import piecewise_polyline_rms
from test_true_arc_matrix import fit_taubin_weighted, line_fit_rms, thin_zhang_suen_local


def measure_local_curvature_variation(pts_ordered: np.ndarray, cx: float, cy: float, r_full: float) -> tuple[float, float, bool]:
    """Measure sub-arc radius variation (first 60%, middle 60%, last 60%), center drift, and S-inflection."""
    n = len(pts_ordered)
    if n < 12 or r_full <= 1e-6:
        return 0.0, 0.0, False

    p0 = pts_ordered[0]
    p1 = pts_ordered[n // 3]
    p2 = pts_ordered[(2 * n) // 3]
    p3 = pts_ordered[-1]
    cross1 = (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0])
    cross2 = (p2[0] - p1[0]) * (p3[1] - p2[1]) - (p2[1] - p1[1]) * (p3[0] - p2[0])
    has_inflection = (cross1 * cross2) < -4.0

    m1 = max(6, int(0.60 * n))
    m_start = max(1, (n - m1) // 2)
    sub1 = pts_ordered[:m1]
    sub_mid = pts_ordered[m_start:m_start + m1]
    sub2 = pts_ordered[n - m1:]
    fit1 = fit_taubin_weighted(sub1, np.ones(len(sub1), dtype=np.float64))
    fit_m = fit_taubin_weighted(sub_mid, np.ones(len(sub_mid), dtype=np.float64))
    fit2 = fit_taubin_weighted(sub2, np.ones(len(sub2), dtype=np.float64))
    if fit1 is None or fit2 is None or fit_m is None:
        return 1.0, 1.0, has_inflection

    c1x, c1y, r1 = fit1
    cmx, cmy, rm = fit_m
    c2x, c2y, r2 = fit2
    rel_r_drift = max(abs(r1 - r2), abs(rm - r_full), abs(r1 - rm), abs(r2 - rm)) / r_full
    rel_c_drift = max(
        math.hypot(c1x - c2x, c1y - c2y),
        math.hypot(cmx - cx, cmy - cy),
    ) / r_full
    return float(rel_r_drift), float(rel_c_drift), bool(has_inflection)


def order_points_along_arc(pts_medial: np.ndarray, cx: float, cy: float) -> np.ndarray:
    """Order medial points along the supported arc interval from start to end around (cx, cy)."""
    if len(pts_medial) <= 3:
        return pts_medial
    angles_deg = (np.degrees(np.arctan2(pts_medial[:, 1] - cy, pts_medial[:, 0] - cx)) + 360.0) % 360.0
    sorted_idx = np.argsort(angles_deg)
    sorted_angles = angles_deg[sorted_idx]
    diffs = np.diff(sorted_angles)
    wrap_diff = (sorted_angles[0] + 360.0) - sorted_angles[-1]
    all_gaps = np.append(diffs, wrap_diff)
    max_gap_idx = int(np.argmax(all_gaps))
    if max_gap_idx == len(all_gaps) - 1:
        return pts_medial[sorted_idx]
    return np.vstack([pts_medial[sorted_idx[max_gap_idx + 1:]], pts_medial[sorted_idx[:max_gap_idx + 1]]])


def evaluate_candidate_component(comp_mask: np.ndarray, min_radius_px: float = 12.0) -> dict:
    """Evaluate a connected foreground component and return classification & metrics."""
    ys_all, xs_all = np.where(comp_mask > 0)
    if len(xs_all) < 12:
        return {"accepted": False, "reason": "TOO_FEW_PIXELS", "fitted": False}

    # Check closed-loop topology (RETR_CCOMP hierarchy holes)
    contours, hierarchy = cv2.findContours(comp_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    has_hole = False
    if hierarchy is not None:
        for i in range(len(contours)):
            child = int(hierarchy[0][i][2])
            if child != -1 and cv2.contourArea(contours[child]) >= 9.0:
                has_hole = True
                break
    if has_hole:
        return {"accepted": False, "reason": "CLOSED_LOOP_TOPOLOGY", "fitted": False}

    x0, x1 = max(0, int(np.min(xs_all)) - 2), min(comp_mask.shape[1], int(np.max(xs_all)) + 3)
    y0, y1 = max(0, int(np.min(ys_all)) - 2), min(comp_mask.shape[0], int(np.max(ys_all)) + 3)
    local_bin = comp_mask[y0:y1, x0:x1]
    dist_map = cv2.distanceTransform(local_bin, cv2.DIST_L2, 3)
    skel = thin_zhang_suen_local(local_bin)
    sy, sx = np.where(skel > 0)

    pts_all = np.column_stack([xs_all.astype(np.float64), ys_all.astype(np.float64)])
    weights_all = (dist_map[ys_all - y0, xs_all - x0] ** 2).astype(np.float64)
    pts_medial = (
        np.column_stack([(sx + x0).astype(np.float64), (sy + y0).astype(np.float64)])
        if len(sx) >= 8 else pts_all
    )
    if len(pts_medial) < 8:
        return {"accepted": False, "reason": "SHORT_MEDIAL_CHAIN", "fitted": False}

    l_rms = line_fit_rms(pts_medial)
    fit = fit_taubin_weighted(pts_all, weights_all)
    if fit is None:
        return {"accepted": False, "reason": "FIT_DEGENERATE", "fitted": True}

    cx, cy, _ = fit
    rad_all = np.hypot(pts_all[:, 0] - cx, pts_all[:, 1] - cy)
    r = float(np.median(rad_all))
    pts_ordered = order_points_along_arc(pts_medial, cx, cy)
    rad_medial = np.hypot(pts_ordered[:, 0] - cx, pts_ordered[:, 1] - cy)
    c_rms = float(np.sqrt(np.mean((rad_medial - r) ** 2)))
    norm_rms = c_rms / max(r, 1e-6)

    angles_all = (np.degrees(np.arctan2(pts_all[:, 1] - cy, pts_all[:, 0] - cx)) + 360.0) % 360.0
    sorted_all = np.sort(angles_all)
    diffs_all = np.diff(sorted_all)
    wrap_all = (sorted_all[0] + 360.0) - sorted_all[-1]
    max_gap_deg = float(np.max(np.append(diffs_all, wrap_all)))
    cap_r = float(np.max(dist_map))
    delta_deg = math.degrees(math.atan2(max(0.0, cap_r - 1.0), max(r, 1.0)))
    sweep_deg = max(0.0, (360.0 - max_gap_deg) - 2.0 * delta_deg)
    sagitta_px = r * (1.0 - math.cos(math.radians(min(sweep_deg, 180.0)) / 2.0))
    rel_r_drift, rel_c_drift, has_inflection = measure_local_curvature_variation(pts_ordered, cx, cy, r)

    base_metrics = {
        "fitted": True,
        "cx": cx,
        "cy": cy,
        "r": r,
        "sweep_deg": sweep_deg,
        "c_rms": c_rms,
        "norm_rms": norm_rms,
        "curv_var": rel_r_drift,
    }

    # Gate 1: Radius floor and near-full-circle cap
    if r < min_radius_px or r > 2000.0:
        return {**base_metrics, "accepted": False, "reason": "RADIUS_OUT_OF_BOUNDS"}
    if max_gap_deg < 22.0:
        return {**base_metrics, "accepted": False, "reason": "NEAR_FULL_CIRCLE"}

    # Gate 2: Curvature / sagitta / sweep / line-ratio check
    if l_rms <= 0.65 or sagitta_px < 2.2 or sweep_deg < 44.0 or (c_rms / max(l_rms, 1e-6)) > 0.45:
        return {**base_metrics, "accepted": False, "reason": "CURVATURE_INSUFFICIENT_FOR_ARC"}

    # Gate 3: Piecewise linear (corner / polyline / capsule / arrowhead) check
    n_segs, poly_rms = piecewise_polyline_rms(pts_ordered, max_segments=3)
    if n_segs <= 3 and poly_rms < 0.75 * c_rms:
        return {**base_metrics, "accepted": False, "reason": "PIECEWISE_LINEAR_NOT_ARC"}

    # Gate 4: Radial residual & local curvature constancy (rejects ellipses, S/U/J/G/C glyphs)
    if has_inflection:
        return {**base_metrics, "accepted": False, "reason": "INFLECTION_S_CURVE_NOT_ARC"}
    if c_rms > 0.58 or (sweep_deg >= 85.0 and (rel_r_drift > 0.16 or rel_c_drift > 0.12)):
        return {**base_metrics, "accepted": False, "reason": "NON_UNIFORM_CURVATURE_OR_ELLIPSE"}

    return {
        **base_metrics,
        "accepted": True,
        "reason": "ACCEPTED_TRUE_ARC",
    }


def extract_candidate_arcs_from_image(img_gray: np.ndarray) -> dict:
    """Extract connected components from grayscale image and evaluate all candidate chains."""
    binary = (img_gray < 220).astype(np.uint8)
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    raw_chains = 0
    circular_fits = 0
    accepted_arcs = 0
    reasons: list[str] = []

    for lbl in range(1, n_labels):
        comp_mask = (labels == lbl).astype(np.uint8)
        raw_chains += 1
        res = evaluate_candidate_component(comp_mask)
        if res.get("fitted", False):
            circular_fits += 1
        if res["accepted"]:
            accepted_arcs += 1
        else:
            reasons.append(res["reason"])

    primary_reason = reasons[0] if reasons else ("ACCEPTED_TRUE_ARC" if accepted_arcs > 0 else "EMPTY")
    return {
        "raw_chains": raw_chains,
        "circular_fits": circular_fits,
        "accepted_arcs": accepted_arcs,
        "primary_reason": primary_reason,
    }


def build_negative_fixtures() -> list[tuple[str, str, np.ndarray]]:
    """Build consolidated negative-control fixtures across all required families and scales/widths."""
    fixtures: list[tuple[str, str, np.ndarray]] = []

    # 1. Straight lines (w=1, 2, 5)
    for w in (1, 2, 5):
        img = np.full((300, 300), 255, dtype=np.uint8)
        cv2.line(img, (40, 60), (260, 210), 0, w)
        fixtures.append(("LINE", f"Straight Line (w={w}px)", img))

    # 2. Parallel lines
    img = np.full((300, 300), 255, dtype=np.uint8)
    for y in (90, 130, 170, 210):
        cv2.line(img, (50, y), (250, y), 0, 2)
    fixtures.append(("LINE", "Parallel Lines (4x)", img))

    # 3. Grid
    img = np.full((300, 300), 255, dtype=np.uint8)
    for p in range(60, 250, 40):
        cv2.line(img, (50, p), (250, p), 0, 2)
        cv2.line(img, (p, 50), (p, 250), 0, 2)
    fixtures.append(("HATCH", "Orthogonal Grid", img))

    # 4. Cross hatch
    img = np.full((300, 300), 255, dtype=np.uint8)
    cv2.rectangle(img, (60, 60), (240, 240), 0, 2)
    for offset in range(-140, 150, 20):
        p1 = (max(60, 60 + offset), max(60, 60 - offset))
        p2 = (min(240, 240 + offset), min(240, 240 - offset))
        cv2.line(img, p1, p2, 0, 1)
        p3 = (max(60, 60 + offset), min(240, 240 + offset))
        p4 = (min(240, 240 + offset), max(60, 60 + offset))
        cv2.line(img, p3, p4, 0, 1)
    fixtures.append(("HATCH", "Cross Hatch in Box", img))

    # 5. Dense hatch
    img = np.full((300, 300), 255, dtype=np.uint8)
    for y in range(60, 240, 8):
        cv2.line(img, (60, y), (240, y), 0, 1)
    fixtures.append(("HATCH", "Dense Parallel Hatch", img))

    # 6. 90 deg, 45 deg, acute (25 deg) corners + dimension arrowhead + rectangle + rounded rect + capsule
    for corner_deg, label in [(90, "90-deg Corner"), (45, "45-deg Corner"), (25, "Acute 25-deg Corner")]:
        for w in (2, 4):
            img = np.full((300, 300), 255, dtype=np.uint8)
            cv2.line(img, (70, 180), (160, 180), 0, w)
            rad = math.radians(corner_deg)
            cv2.line(img, (160, 180), (int(160 - 90 * math.cos(rad)), int(180 - 90 * math.sin(rad))), 0, w)
            fixtures.append(("CORNER", f"{label} (w={w}px)", img))

    # Dimension arrowhead
    img = np.full((300, 300), 255, dtype=np.uint8)
    cv2.line(img, (60, 150), (240, 150), 0, 2)
    cv2.line(img, (60, 150), (80, 142), 0, 2)
    cv2.line(img, (60, 150), (80, 158), 0, 2)
    cv2.line(img, (240, 150), (220, 142), 0, 2)
    cv2.line(img, (240, 150), (220, 158), 0, 2)
    fixtures.append(("CORNER", "Dimension Arrowhead", img))

    # Rectangle
    img = np.full((300, 300), 255, dtype=np.uint8)
    cv2.rectangle(img, (70, 90), (230, 210), 0, 2)
    fixtures.append(("CORNER", "Rectangle", img))

    # Rounded rectangle (closed loop)
    img = np.full((300, 300), 255, dtype=np.uint8)
    cv2.line(img, (90, 90), (210, 90), 0, 2)
    cv2.line(img, (90, 210), (210, 210), 0, 2)
    cv2.line(img, (70, 110), (70, 190), 0, 2)
    cv2.line(img, (230, 110), (230, 190), 0, 2)
    cv2.ellipse(img, (90, 110), (20, 20), 0, 180, 270, 0, 2)
    cv2.ellipse(img, (210, 110), (20, 20), 0, 270, 360, 0, 2)
    cv2.ellipse(img, (210, 190), (20, 20), 0, 0, 90, 0, 2)
    cv2.ellipse(img, (90, 190), (20, 20), 0, 90, 180, 0, 2)
    fixtures.append(("CORNER", "Rounded Rectangle", img))

    # Capsule / stadium
    img = np.full((300, 300), 255, dtype=np.uint8)
    cv2.line(img, (100, 110), (200, 110), 0, 2)
    cv2.line(img, (100, 190), (200, 190), 0, 2)
    cv2.ellipse(img, (100, 150), (40, 40), 0, 90, 270, 0, 2)
    cv2.ellipse(img, (200, 150), (40, 40), 0, 270, 450, 0, 2)
    fixtures.append(("CORNER", "Capsule / Stadium", img))

    # Random noise & speckle clusters
    rng = np.random.default_rng(42)
    img_noise = np.full((300, 300), 255, dtype=np.uint8)
    for _ in range(120):
        x, y = int(rng.integers(20, 280)), int(rng.integers(20, 280))
        img_noise[y:y + 2, x:x + 2] = 0
    fixtures.append(("NOISE", "Random Salt Noise", img_noise))

    img_speckle = np.full((300, 300), 255, dtype=np.uint8)
    for ang in range(0, 180, 18):
        rad = math.radians(ang)
        x, y = int(150 + 50 * math.cos(rad)), int(150 + 50 * math.sin(rad))
        cv2.circle(img_speckle, (x, y), 2, 0, -1)
    fixtures.append(("NOISE", "Speckle Clusters Along Arc", img_speckle))

    # Full circle & concentric circles
    for r_c, w in [(40, 2), (70, 4)]:
        img = np.full((300, 300), 255, dtype=np.uint8)
        cv2.circle(img, (150, 150), r_c, 0, w)
        fixtures.append(("CIRCLE", f"Full Circle (R={r_c}, w={w})", img))

    img_conc = np.full((300, 300), 255, dtype=np.uint8)
    cv2.circle(img_conc, (150, 150), 35, 0, 2)
    cv2.circle(img_conc, (150, 150), 65, 0, 2)
    fixtures.append(("CIRCLE", "Concentric Circles (R=35,65)", img_conc))

    # Closed Ellipse & Partial 180-deg Ellipse (a=75, b=40)
    img_ell_closed = np.full((300, 300), 255, dtype=np.uint8)
    cv2.ellipse(img_ell_closed, (150, 150), (75, 40), 0, 0, 360, 0, 2)
    fixtures.append(("ELLIPSE", "Full Ellipse (75x40)", img_ell_closed))

    img_ell_open = np.full((300, 300), 255, dtype=np.uint8)
    cv2.ellipse(img_ell_open, (150, 150), (75, 40), 30, 0, 180, 0, 2)
    fixtures.append(("ELLIPSE", "Partial 180d Ellipse (75x40)", img_ell_open))

    # Text glyphs: C, G, O, 0, 8, S, U, J, ) at scales (0.9, 1.6) and widths (1, 2, 3)
    glyphs = ["C", "G", "O", "0", "8", "S", "U", "J", ")"]
    for ch in glyphs:
        for scale, w in [(0.9, 1), (1.6, 2), (2.2, 3)]:
            img = np.full((300, 300), 255, dtype=np.uint8)
            cv2.putText(img, ch, (110, 180), cv2.FONT_HERSHEY_SIMPLEX, scale, 0, w, cv2.LINE_8)
            fixtures.append(("TEXT", f"Glyph '{ch}' (s={scale}, w={w})", img))

    return fixtures


def run_section_19_negative_matrix() -> dict:
    fixtures = build_negative_fixtures()
    family_totals = {
        "TEXT": 0,
        "HATCH": 0,
        "CORNER": 0,
        "LINE": 0,
        "CIRCLE": 0,
        "ELLIPSE": 0,
        "NOISE": 0,
    }
    family_counts = {k: 0 for k in family_totals}
    family_chains = {k: 0 for k in family_totals}
    family_fits = {k: 0 for k in family_totals}

    print("=== SECTION 19: FALSE-POSITIVE NEGATIVE MATRIX ===")
    print(f"{'Family':<8} | {'Fixture':<34} | {'Chains':<6} | {'Fits':<4} | {'FalseArcs':<9} | {'Rejection Reason'}")
    print("-" * 100)

    for fam, name, img in fixtures:
        res = extract_candidate_arcs_from_image(img)
        family_counts[fam] += 1
        family_chains[fam] += res["raw_chains"]
        family_fits[fam] += res["circular_fits"]
        family_totals[fam] += res["accepted_arcs"]
        if fam != "TEXT" or "s=1.6" in name or res["accepted_arcs"] > 0:
            print(
                f"{fam:<8} | {name:<34} | {res['raw_chains']:>6} | {res['circular_fits']:>4} | "
                f"{res['accepted_arcs']:>9} | {res['primary_reason']}"
            )

    total_false = sum(family_totals.values())
    print("-" * 100)
    print(f"TEXT_FALSE_ARCS={family_totals['TEXT']} (across {family_counts['TEXT']} glyph fixtures)")
    print(f"HATCH_FALSE_ARCS={family_totals['HATCH']} (across {family_counts['HATCH']} hatch/grid fixtures)")
    print(f"CORNER_FALSE_ARCS={family_totals['CORNER']} (across {family_counts['CORNER']} corner/box/slot fixtures)")
    print(f"LINE_FALSE_ARCS={family_totals['LINE']} (across {family_counts['LINE']} line fixtures)")
    print(f"CIRCLE_FALSE_ARCS={family_totals['CIRCLE']} (across {family_counts['CIRCLE']} circle fixtures)")
    print(f"TOTAL_FALSE_ARCS={total_false} (across {len(fixtures)} total negative fixtures)")
    return family_totals


def run_section_20_ellipse_control() -> dict:
    axis_ratios = [1.00, 1.05, 1.10, 1.20, 1.50, 2.00]
    sweeps = [45, 60, 90, 120, 180, 270]
    orientations = [0, 30, 45, 90]
    b_minor = 50

    print("\n=== SECTION 20: ELLIPSE CONTROL BENCHMARK ===")
    print(
        f"{'AxisRatio':<9} | {'Sweep':<6} | {'MeanRadRMS':<10} | {'NormRMS':<9} | "
        f"{'CurvVar':<9} | {'RadDrift(%)':<11} | {'AcceptedRate'}"
    )
    print("-" * 82)

    ratio_accepted = {ar: 0 for ar in axis_ratios}
    ratio_total = {ar: 0 for ar in axis_ratios}

    for ar in axis_ratios:
        a_major = int(round(b_minor * ar))
        r_nominal = 0.5 * (a_major + b_minor)
        for sw in sweeps:
            rms_list = []
            norm_rms_list = []
            curv_var_list = []
            r_drift_list = []
            acc_count = 0
            for rot in orientations:
                img = np.full((400, 400), 255, dtype=np.uint8)
                cv2.ellipse(img, (200, 200), (a_major, b_minor), rot, 0, sw, 0, 2)
                comp_mask = (img < 220).astype(np.uint8)
                res = evaluate_candidate_component(comp_mask)
                c_rms = float(res.get("c_rms", 0.0))
                n_rms = float(res.get("norm_rms", 0.0))
                c_var = float(res.get("curv_var", 0.0))
                r_fit = float(res.get("r", r_nominal))
                rms_list.append(c_rms)
                norm_rms_list.append(n_rms)
                curv_var_list.append(c_var)
                r_drift_list.append(abs(r_fit - r_nominal) / r_nominal * 100.0)
                if res["accepted"]:
                    acc_count += 1
                ratio_total[ar] += 1
                if res["accepted"]:
                    ratio_accepted[ar] += 1

            print(
                f"{ar:>8.2f}  | {sw:>4}d  | {np.mean(rms_list):>8.3f}px | {np.mean(norm_rms_list):>8.4f}  | "
                f"{np.mean(curv_var_list):>8.3f}  | {np.mean(r_drift_list):>9.2f}%  | {acc_count}/{len(orientations)}"
            )

    print("-" * 82)
    for ar in axis_ratios:
        rate = ratio_accepted[ar] / max(1, ratio_total[ar]) * 100.0
        print(f"AXIS_RATIO_{ar:.2f}_ACCEPTED={ratio_accepted[ar]}/{ratio_total[ar]} ({rate:.1f}%)")
    return ratio_accepted


if __name__ == "__main__":
    run_section_19_negative_matrix()
    run_section_20_ellipse_control()
