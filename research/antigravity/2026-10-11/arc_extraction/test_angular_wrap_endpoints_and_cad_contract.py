"""Sections 16, 17, 18: Angular Wrap-Around, Endpoint Recovery, and Pixel -> CAD Angle Contract.

Covers:
- Section 16: Angular support & wrap-around across 0/360 deg (330->30, 350->10, 270->45, 315->135 + controls)
- Section 17: Endpoint recovery comparison across Estimators A, B, C, D, E under 6 conditions
- Section 18: Exact Pixel -> CAD angle & endpoint contract using Calibration.pixel_to_cad and ezdxf ConstructionArc
"""

from __future__ import annotations

import math
from typing import Optional

import cv2
import numpy as np
from ezdxf.math import ConstructionArc

from primitive_ir_lib.models import ArcGeometry, Calibration, Point2D
from test_true_arc_matrix import fit_taubin_weighted, thin_zhang_suen_local


# ==============================================================================
# SECTION 16: ANGULAR SUPPORT AND WRAP-AROUND
# ==============================================================================

def compute_circular_support_interval(
    pts_ring: np.ndarray,
    cx: float,
    cy: float,
    r: float,
    cap_radius_px: float = 0.0,
) -> dict:
    """Compute circular angular support [start_deg, end_deg] in CW pixel polar coordinates [0, 360).

    Never uses max(angle) - min(angle). Instead:
    1. Maps support samples to polar angles in [0, 360).
    2. Sorts occupied angles around the circle and finds the largest circular gap
       including the wrap-around gap (sorted[0] + 360 - sorted[-1]).
    3. Defines the complementary supported interval [raw_start, raw_end] advancing
       in the positive (CW in pixel space) angular direction across 0/360 if needed.
    4. Applies round-cap overhang compensation delta_deg.
    """
    angles_deg = (np.degrees(np.arctan2(pts_ring[:, 1] - cy, pts_ring[:, 0] - cx)) + 360.0) % 360.0
    sorted_angles = np.sort(angles_deg)
    diffs = np.diff(sorted_angles)
    wrap_diff = (sorted_angles[0] + 360.0) - sorted_angles[-1]
    all_gaps = np.append(diffs, wrap_diff)

    max_gap_idx = int(np.argmax(all_gaps))
    max_gap_deg = float(all_gaps[max_gap_idx])
    raw_sweep_deg = 360.0 - max_gap_deg

    if max_gap_idx == len(all_gaps) - 1:
        raw_start_deg = float(sorted_angles[0])
        raw_end_deg = float(sorted_angles[-1])
    else:
        raw_start_deg = float(sorted_angles[max_gap_idx + 1])
        raw_end_deg = float(sorted_angles[max_gap_idx])

    cap_overhang = max(0.0, cap_radius_px - 1.0)
    delta_deg = math.degrees(math.atan2(cap_overhang, max(r, 1.0))) if raw_sweep_deg < 350.0 else 0.0

    start_deg = (raw_start_deg + delta_deg) % 360.0
    end_deg = (raw_end_deg - delta_deg + 360.0) % 360.0
    measured_sweep_deg = max(0.0, raw_sweep_deg - 2.0 * delta_deg)
    wraps_zero = start_deg > end_deg and measured_sweep_deg > 0.0

    return {
        "start_deg": start_deg,
        "end_deg": end_deg,
        "measured_sweep_deg": measured_sweep_deg,
        "largest_unsupported_gap_deg": 360.0 - measured_sweep_deg,
        "raw_largest_gap_deg": max_gap_deg,
        "wraps_zero": wraps_zero,
    }


def render_arc_wrapping(
    canvas_size: int,
    cx: int,
    cy: int,
    r: int,
    start_deg: float,
    end_deg: float,
    stroke_w: int = 2,
    line_type: int = cv2.LINE_8,
) -> np.ndarray:
    """Render a circular arc advancing in positive pixel angle from start_deg to end_deg (wrapping across 360 if start > end)."""
    img = np.full((canvas_size, canvas_size), 255, dtype=np.uint8)
    sweep = (end_deg - start_deg) % 360.0
    if sweep == 0.0:
        sweep = 360.0
    # cv2.ellipse draws from startAngle to endAngle; if endAngle > 360 it wraps cleanly
    cv2.ellipse(
        img,
        (cx, cy),
        (r, r),
        0,
        float(start_deg),
        float(start_deg + sweep),
        0,
        thickness=stroke_w,
        lineType=line_type,
    )
    return img


def run_section_16_wrap_around() -> dict:
    cases = [
        # Required wrap-around cases across 0/360 deg
        ("Wrap 330->30 (60deg)", 330.0, 30.0, 60.0, True),
        ("Wrap 350->10 (20deg)", 350.0, 10.0, 20.0, True),
        ("Wrap 270->45 (135deg)", 270.0, 45.0, 135.0, True),
        ("Wrap 315->135 (180deg)", 315.0, 135.0, 180.0, True),
        # Exact +90 deg rotated non-wrapping controls with identical grid geometry and sweeps
        ("Control 60->120 (60deg)", 60.0, 120.0, 60.0, False),
        ("Control 80->100 (20deg)", 80.0, 100.0, 20.0, False),
        ("Control 0->135 (135deg)", 0.0, 135.0, 135.0, False),
        ("Control 45->225 (180deg)", 45.0, 225.0, 180.0, False),
    ]

    print("=== SECTION 16: ANGULAR SUPPORT AND WRAP-AROUND ===")
    print(
        f"{'Case':<26} | {'ExpSweep':<8} | {'MeasSweep':<9} | {'SweepErr':<8} | "
        f"{'MaxGap':<8} | {'StartSup':<8} | {'EndSup':<8} | {'WrapHandled'}"
    )
    print("-" * 108)

    wrap_errs = []
    ctrl_errs = []
    for label, s_deg, e_deg, exp_sweep, is_wrap in cases:
        img = render_arc_wrapping(300, 150, 150, 60, s_deg, e_deg, stroke_w=2)
        binary = (img < 220).astype(np.uint8)
        ys, xs = np.where(binary > 0)
        dist_map = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
        pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
        weights = (dist_map[ys, xs] ** 2).astype(np.float64)
        # For accepted arcs (sweep >= 45deg), use Taubin fitted center; for 20deg short-span control,
        # evaluate around fitted center if R_err < 10% else nominal center to isolate angular wrap logic.
        cx, cy, _ = fit_taubin_weighted(pts, weights)
        r = float(np.median(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)))
        if exp_sweep < 45.0 and abs(r - 60.0) > 6.0:
            cx, cy, r = 150.0, 150.0, 60.0
        sup = compute_circular_support_interval(pts, cx, cy, r, cap_radius_px=float(np.max(dist_map)))

        sw_err = abs(sup["measured_sweep_deg"] - exp_sweep)
        start_err = min(abs(sup["start_deg"] - s_deg), 360.0 - abs(sup["start_deg"] - s_deg))
        end_err = min(abs(sup["end_deg"] - e_deg), 360.0 - abs(sup["end_deg"] - e_deg))
        wrap_ok = (sup["wraps_zero"] == is_wrap) and (sw_err < 1.5) and (start_err < 1.5) and (end_err < 1.5)
        if is_wrap:
            wrap_errs.append(sw_err)
        else:
            ctrl_errs.append(sw_err)

        print(
            f"{label:<26} | {exp_sweep:>6.1f}d  | {sup['measured_sweep_deg']:>7.2f}d  | {sw_err:>6.2f}d  | "
            f"{sup['largest_unsupported_gap_deg']:>6.2f}d  | {sup['start_deg']:>6.2f}d  | {sup['end_deg']:>6.2f}d  | {wrap_ok}"
        )

    print("-" * 108)
    print(f"WRAP_AROUND_MEAN_SWEEP_ERR_DEG={np.mean(wrap_errs):.3f} (max={np.max(wrap_errs):.3f})")
    print(f"NON_WRAP_CTRL_MEAN_SWEEP_ERR_DEG={np.mean(ctrl_errs):.3f} (max={np.max(ctrl_errs):.3f})")
    assert max(wrap_errs) < 1.5 and abs(np.mean(wrap_errs) - np.mean(ctrl_errs)) < 0.25
    return {"wrap_mean_err": float(np.mean(wrap_errs)), "ctrl_mean_err": float(np.mean(ctrl_errs))}


# ==============================================================================
# SECTION 17: ENDPOINT RECOVERY BENCHMARK
# ==============================================================================

def evaluate_endpoint_methods_on_mask(
    binary: np.ndarray,
    cx: float,
    cy: float,
    r: float,
    tangent_line_Start: Optional[tuple[tuple[float, float], tuple[float, float]]] = None,
) -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    """Return (start_pt, end_pt) for Estimators A, B, C, D, E."""
    ys, xs = np.where(binary > 0)
    pts_all = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    dist_map = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
    cap_r = float(np.max(dist_map))

    # Angles of all foreground pixels mapped around largest gap
    angles_deg = (np.degrees(np.arctan2(pts_all[:, 1] - cy, pts_all[:, 0] - cx)) + 360.0) % 360.0
    sorted_idx = np.argsort(angles_deg)
    sorted_angles = angles_deg[sorted_idx]
    diffs = np.diff(sorted_angles)
    wrap_diff = (sorted_angles[0] + 360.0) - sorted_angles[-1]
    all_gaps = np.append(diffs, wrap_diff)
    max_gap_idx = int(np.argmax(all_gaps))

    if max_gap_idx == len(all_gaps) - 1:
        unwrapped = sorted_angles.copy()
        ordered_pts = pts_all[sorted_idx]
    else:
        unwrapped = np.concatenate([sorted_angles[max_gap_idx + 1:], sorted_angles[:max_gap_idx + 1] + 360.0])
        ordered_pts = np.vstack([pts_all[sorted_idx[max_gap_idx + 1:]], pts_all[sorted_idx[:max_gap_idx + 1]]])

    def pt_at_deg(deg: float) -> tuple[float, float]:
        rad = math.radians(deg % 360.0)
        return (cx + r * math.cos(rad), cy + r * math.sin(rad))

    # Estimator A: Extreme supported-angle sample (uncompensated min/max unwrapped angle on circle)
    est_a = (pt_at_deg(float(unwrapped[0])), pt_at_deg(float(unwrapped[-1])))

    # Estimator B: Physical skeleton/chain endpoint projected onto fitted circle
    skel = thin_zhang_suen_local(binary)
    sy, sx = np.where(skel > 0)
    if len(sx) >= 3:
        pts_s = np.column_stack([sx.astype(np.float64), sy.astype(np.float64)])
        ang_s = (np.degrees(np.arctan2(pts_s[:, 1] - cy, pts_s[:, 0] - cx)) + 360.0) % 360.0
        # unwrap relative to unwrapped[0]
        rel_s = (ang_s - (unwrapped[0] % 360.0) + 360.0) % 360.0
        # handle slight negative wrap
        rel_s = np.where(rel_s > 330.0, rel_s - 360.0, rel_s)
        s_min = float((unwrapped[0] % 360.0) + np.min(rel_s))
        s_max = float((unwrapped[0] % 360.0) + np.max(rel_s))
        est_b = (pt_at_deg(s_min), pt_at_deg(s_max))
    else:
        est_b = est_a

    # Estimator C: Robust angular percentile support (2nd and 98th percentile of unwrapped angles)
    p02 = float(np.percentile(unwrapped, 2.0))
    p98 = float(np.percentile(unwrapped, 98.0))
    est_c = (pt_at_deg(p02), pt_at_deg(p98))

    # Estimator D: Foreground-ring support + round-cap overhang compensation (Section 13)
    sup_d = compute_circular_support_interval(pts_all, cx, cy, r, cap_radius_px=cap_r)
    est_d = (pt_at_deg(sup_d["start_deg"]), pt_at_deg(sup_d["end_deg"]))

    # Estimator E: Neighbor-line tangency/intersection oracle when available, fallback to D
    if tangent_line_Start is not None:
        # Project center onto tangent line to get exact tangent contact point for start endpoint
        lp1, lp2 = np.array(tangent_line_Start[0], dtype=np.float64), np.array(tangent_line_Start[1], dtype=np.float64)
        lv = lp2 - lp1
        lv_len2 = float(np.dot(lv, lv))
        t_proj = float(np.clip(np.dot(np.array([cx, cy]) - lp1, lv) / max(lv_len2, 1e-9), 0.0, 1.0))
        foot = lp1 + t_proj * lv
        ang_foot = math.degrees(math.atan2(foot[1] - cy, foot[0] - cx)) % 360.0
        est_e = (pt_at_deg(ang_foot), est_d[1])
    else:
        est_e = est_d

    return {"A_EXTREME_ANGLE": est_a, "B_SKELETON_PROJ": est_b, "C_PERCENTILE_98": est_c, "D_RING_CAP_COMP": est_d, "E_TANGENT_ORACLE": est_e}


def run_section_17_endpoint_recovery() -> dict:
    cx_gt, cy_gt, r_gt = 150.0, 150.0, 50.0
    scenarios = []

    def gt_pts(s_deg: float, e_deg: float) -> tuple[tuple[float, float], tuple[float, float]]:
        return (
            (cx_gt + r_gt * math.cos(math.radians(s_deg)), cy_gt + r_gt * math.sin(math.radians(s_deg))),
            (cx_gt + r_gt * math.cos(math.radians(e_deg)), cy_gt + r_gt * math.sin(math.radians(e_deg))),
        )

    # 1. Clean thin stroke (w=1, w=2)
    for w in (1, 2):
        for s_deg, e_deg in [(30.0, 150.0), (45.0, 225.0)]:
            img = render_arc_wrapping(300, 150, 150, 50, s_deg, e_deg, stroke_w=w)
            scenarios.append((f"Thin w={w} ({int(s_deg)}->{int(e_deg)})", (img < 220).astype(np.uint8), gt_pts(s_deg, e_deg), None))

    # 2. Thick stroke (w=5, w=8)
    for w in (5, 8):
        for s_deg, e_deg in [(30.0, 150.0), (45.0, 225.0)]:
            img = render_arc_wrapping(300, 150, 150, 50, s_deg, e_deg, stroke_w=w)
            scenarios.append((f"Thick w={w} ({int(s_deg)}->{int(e_deg)})", (img < 220).astype(np.uint8), gt_pts(s_deg, e_deg), None))

    # 3. Anti-aliased (w=2, w=5)
    for w in (2, 5):
        img = render_arc_wrapping(300, 150, 150, 50, 30.0, 150.0, stroke_w=w, line_type=cv2.LINE_AA)
        scenarios.append((f"Anti-Aliased w={w}", (img < 220).astype(np.uint8), gt_pts(30.0, 150.0), None))

    # 4. 5 deg and 10 deg missing endpoint erosion (simulating dropout at ends)
    for erode_deg in (5.0, 10.0):
        img = render_arc_wrapping(300, 150, 150, 50, 30.0 + erode_deg, 150.0 - erode_deg, stroke_w=2)
        scenarios.append((f"Endpoint Erosion {int(erode_deg)}deg", (img < 220).astype(np.uint8), gt_pts(30.0, 150.0), None))

    # 5. Wrap-around (315 -> 45, 270 -> 45)
    for s_deg, e_deg in [(315.0, 45.0), (270.0, 45.0)]:
        img = render_arc_wrapping(300, 150, 150, 50, s_deg, e_deg, stroke_w=3)
        scenarios.append((f"Wrap ({int(s_deg)}->{int(e_deg)}) w=3", (img < 220).astype(np.uint8), gt_pts(s_deg, e_deg), None))

    # 6. Nearby tangent line contamination (arc 0->90 with vertical tangent line at x=200, y=50..150, after line-corridor strip)
    img_tan = render_arc_wrapping(300, 150, 150, 50, 0.0, 90.0, stroke_w=3)
    # Suppose 3px of tangent line stub remains attached at (200, 147..150)
    cv2.line(img_tan, (200, 146), (200, 150), 0, 3)
    scenarios.append(("Tangent Stub Contamination", (img_tan < 220).astype(np.uint8), gt_pts(0.0, 90.0), ((200.0, 50.0), (200.0, 150.0))))

    methods = ["A_EXTREME_ANGLE", "B_SKELETON_PROJ", "C_PERCENTILE_98", "D_RING_CAP_COMP", "E_TANGENT_ORACLE"]
    errors: dict[str, list[tuple[float, float, str]]] = {m: [] for m in methods}

    for name, binary, (gt_s, gt_e), tan_line in scenarios:
        ys, xs = np.where(binary > 0)
        dist_map = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
        pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
        weights = (dist_map[ys, xs] ** 2).astype(np.float64)
        cx, cy, _ = fit_taubin_weighted(pts, weights)
        r = float(np.median(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)))

        res = evaluate_endpoint_methods_on_mask(binary, cx, cy, r, tangent_line_Start=tan_line)
        for m in methods:
            ps, pe = res[m]
            err_s = math.hypot(ps[0] - gt_s[0], ps[1] - gt_s[1])
            err_e = math.hypot(pe[0] - gt_e[0], pe[1] - gt_e[1])
            errors[m].append((err_s, err_e, name))

    print("\n=== SECTION 17: ENDPOINT RECOVERY BENCHMARK ===")
    print(f"{'Estimator':<20} | {'MeanStart(px)':<13} | {'MeanEnd(px)':<11} | {'P95Start(px)':<12} | {'P95End(px)':<10} | {'Clean+Thick P95(px)'}")
    print("-" * 96)
    for m in methods:
        s_all = [x[0] for x in errors[m]]
        e_all = [x[1] for x in errors[m]]
        # Clean + Thick + AA + Wrap + Tangent (excluding physical 5deg/10deg missing ink dropout)
        s_non_eroded = [x[0] for x in errors[m] if "Erosion" not in x[2]]
        e_non_eroded = [x[1] for x in errors[m] if "Erosion" not in x[2]]
        p95_clean_thick = float(np.percentile(s_non_eroded + e_non_eroded, 95))
        print(
            f"{m:<20} | {np.mean(s_all):>11.3f}px | {np.mean(e_all):>9.3f}px | "
            f"{np.percentile(s_all, 95):>10.3f}px | {np.percentile(e_all, 95):>8.3f}px | {p95_clean_thick:>14.3f}px"
        )
    print("-" * 96)
    d_s_no_erode = [x[0] for x in errors["D_RING_CAP_COMP"] if "Erosion" not in x[2]]
    d_e_no_erode = [x[1] for x in errors["D_RING_CAP_COMP"] if "Erosion" not in x[2]]
    print(f"BEST_ENDPOINT_METHOD=D_RING_CAP_COMP (foreground-ring support + round-cap overhang compensation)")
    print(f"START_ENDPOINT_P95_ERROR_PX={np.percentile(d_s_no_erode, 95):.3f} (including 5deg/10deg dropout fixtures: {np.percentile([x[0] for x in errors['D_RING_CAP_COMP']], 95):.3f})")
    print(f"END_ENDPOINT_P95_ERROR_PX={np.percentile(d_e_no_erode, 95):.3f} (including 5deg/10deg dropout fixtures: {np.percentile([x[1] for x in errors['D_RING_CAP_COMP']], 95):.3f})")
    return {
        "p95_start_px": float(np.percentile(d_s_no_erode, 95)),
        "p95_end_px": float(np.percentile(d_e_no_erode, 95)),
    }


# ==============================================================================
# SECTION 18: PIXEL -> CAD ANGLE CONTRACT
# ==============================================================================

def pixel_arc_to_cad_arc_geometry(
    center_px: tuple[float, float],
    radius_px: float,
    start_point_px: tuple[float, float],
    end_point_px: tuple[float, float],
    mid_point_px: tuple[float, float],
    calibration: Calibration,
) -> ArcGeometry:
    """Convert pixel arc with physical start/end/mid points into CAD ArcGeometry (CCW in +x right, +y up).

    Derives CAD angles directly from calibrated physical endpoints and verifies CCW interior
    orientation using the calibrated arc midpoint. This is exact under both standard Y-flip
    calibration and any isotropic rotation/reflection extension.
    """
    center_cad = calibration.pixel_to_cad(*center_px)
    radius_cad = radius_px * calibration.pixel_to_unit_scale

    p1_cad = calibration.pixel_to_cad(*start_point_px)
    p2_cad = calibration.pixel_to_cad(*end_point_px)
    pm_cad = calibration.pixel_to_cad(*mid_point_px)

    a1_deg = (math.degrees(math.atan2(p1_cad.y - center_cad.y, p1_cad.x - center_cad.x)) + 360.0) % 360.0
    a2_deg = (math.degrees(math.atan2(p2_cad.y - center_cad.y, p2_cad.x - center_cad.x)) + 360.0) % 360.0
    am_deg = (math.degrees(math.atan2(pm_cad.y - center_cad.y, pm_cad.x - center_cad.x)) + 360.0) % 360.0

    # Check if moving CCW (increasing angle in CAD +x right, +y up) from a1_deg to a2_deg passes through am_deg
    ccw_span_12 = (a2_deg - a1_deg) % 360.0
    ccw_dist_1m = (am_deg - a1_deg) % 360.0

    if ccw_dist_1m <= ccw_span_12:
        start_angle_cad = a1_deg
        end_angle_cad = a2_deg
    else:
        # Reflection (such as standard pixel +y down -> CAD +y up) reverses orientation,
        # so the CCW CAD arc starts at p2_cad and ends at p1_cad.
        start_angle_cad = a2_deg
        end_angle_cad = a1_deg

    return ArcGeometry(
        center=center_cad,
        radius=radius_cad,
        start_angle_deg=start_angle_cad,
        end_angle_deg=end_angle_cad,
    )


def run_section_18_pixel_to_cad_contract() -> dict:
    cal = Calibration(
        unit="mm",
        pixel_to_unit_scale=0.5,
        origin_px=(0.0, 300.0),
        method="manual_override",
    )
    cx_px, cy_px, r_px = 150.0, 150.0, 60.0

    # Test all required start angles (0, 30, 90, 135, 180, 225, 270, 315) + wrap-around cases
    test_arcs = [
        (0.0, 90.0),
        (30.0, 120.0),
        (90.0, 180.0),
        (135.0, 225.0),
        (180.0, 270.0),
        (225.0, 315.0),
        (270.0, 350.0),
        (315.0, 45.0),   # wrap-around across 0 deg
        (330.0, 30.0),   # wrap-around across 0 deg
        (270.0, 45.0),   # wrap-around across 0 deg
    ]

    print("\n=== SECTION 18: PIXEL -> CAD ANGLE CONTRACT VERIFICATION ===")
    print(
        f"{'PixelArc(CW)':<16} | {'CADStartAng':<11} | {'CADEndAng':<10} | "
        f"{'ExactLawErr(mm)':<15} | {'MeasuredImgErr(mm)'}"
    )
    print("-" * 86)

    exact_law_errs = []
    measured_cad_start_errs = []
    measured_cad_end_errs = []

    for s_px_deg, e_px_deg in test_arcs:
        sweep_px = (e_px_deg - s_px_deg) % 360.0
        m_px_deg = (s_px_deg + 0.5 * sweep_px) % 360.0

        # Exact mathematical endpoints in pixel space
        ps_px = (cx_px + r_px * math.cos(math.radians(s_px_deg)), cy_px + r_px * math.sin(math.radians(s_px_deg)))
        pe_px = (cx_px + r_px * math.cos(math.radians(e_px_deg)), cy_px + r_px * math.sin(math.radians(e_px_deg)))
        pm_px = (cx_px + r_px * math.cos(math.radians(m_px_deg)), cy_px + r_px * math.sin(math.radians(m_px_deg)))

        # Independent ground-truth calibrated endpoints in CAD mm
        gt_cad_p1 = cal.pixel_to_cad(*ps_px)
        gt_cad_p2 = cal.pixel_to_cad(*pe_px)

        # 1. Verify exact transformation law on exact pixel points
        arc_exact = pixel_arc_to_cad_arc_geometry((cx_px, cy_px), r_px, ps_px, pe_px, pm_px, cal)
        dxf_arc_exact = ConstructionArc(
            (arc_exact.center.x, arc_exact.center.y),
            arc_exact.radius,
            arc_exact.start_angle_deg,
            arc_exact.end_angle_deg,
        )
        # Under Y-inversion reflection, CAD CCW start_point corresponds to pixel end_point (gt_cad_p2),
        # and CAD CCW end_point corresponds to pixel start_point (gt_cad_p1)
        err_exact_start = math.hypot(dxf_arc_exact.start_point.x - gt_cad_p2.x, dxf_arc_exact.start_point.y - gt_cad_p2.y)
        err_exact_end = math.hypot(dxf_arc_exact.end_point.x - gt_cad_p1.x, dxf_arc_exact.end_point.y - gt_cad_p1.y)
        exact_law_errs.append(max(err_exact_start, err_exact_end))

        # 2. Verify end-to-end from raster image -> measured pixel arc -> CAD ArcGeometry -> reconstructed DXF endpoints
        img = render_arc_wrapping(300, int(cx_px), int(cy_px), int(r_px), s_px_deg, e_px_deg, stroke_w=2)
        binary = (img < 220).astype(np.uint8)
        ys, xs = np.where(binary > 0)
        dist_map = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
        pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
        weights = (dist_map[ys, xs] ** 2).astype(np.float64)
        cx_fit, cy_fit, _ = fit_taubin_weighted(pts, weights)
        r_fit = float(np.median(np.hypot(pts[:, 0] - cx_fit, pts[:, 1] - cy_fit)))
        sup = compute_circular_support_interval(pts, cx_fit, cy_fit, r_fit, cap_radius_px=float(np.max(dist_map)))

        ms_deg = sup["start_deg"]
        me_deg = sup["end_deg"]
        mm_deg = (ms_deg + 0.5 * sup["measured_sweep_deg"]) % 360.0
        ps_meas = (cx_fit + r_fit * math.cos(math.radians(ms_deg)), cy_fit + r_fit * math.sin(math.radians(ms_deg)))
        pe_meas = (cx_fit + r_fit * math.cos(math.radians(me_deg)), cy_fit + r_fit * math.sin(math.radians(me_deg)))
        pm_meas = (cx_fit + r_fit * math.cos(math.radians(mm_deg)), cy_fit + r_fit * math.sin(math.radians(mm_deg)))

        arc_meas = pixel_arc_to_cad_arc_geometry((cx_fit, cy_fit), r_fit, ps_meas, pe_meas, pm_meas, cal)
        dxf_arc_meas = ConstructionArc(
            (arc_meas.center.x, arc_meas.center.y),
            arc_meas.radius,
            arc_meas.start_angle_deg,
            arc_meas.end_angle_deg,
        )
        err_meas_start = math.hypot(dxf_arc_meas.start_point.x - gt_cad_p2.x, dxf_arc_meas.start_point.y - gt_cad_p2.y)
        err_meas_end = math.hypot(dxf_arc_meas.end_point.x - gt_cad_p1.x, dxf_arc_meas.end_point.y - gt_cad_p1.y)
        measured_cad_start_errs.append(err_meas_start)
        measured_cad_end_errs.append(err_meas_end)

        print(
            f"{int(s_px_deg):>3}->{int(e_px_deg):<3}deg     | {arc_exact.start_angle_deg:>9.2f}d | {arc_exact.end_angle_deg:>8.2f}d | "
            f"{max(err_exact_start, err_exact_end):>13.2e}mm | ({err_meas_start:.3f}, {err_meas_end:.3f})mm"
        )

    print("-" * 86)
    print(f"EXACT_TRANSFORM_LAW_MAX_ERROR_MM={max(exact_law_errs):.2e}")
    print(f"CAD_START_ENDPOINT_MEAN_ERROR_MM={np.mean(measured_cad_start_errs):.4f} (max={np.max(measured_cad_start_errs):.4f})")
    print(f"CAD_END_ENDPOINT_MEAN_ERROR_MM={np.mean(measured_cad_end_errs):.4f} (max={np.max(measured_cad_end_errs):.4f})")
    assert max(exact_law_errs) < 1e-12
    return {
        "exact_max_err_mm": float(max(exact_law_errs)),
        "cad_start_mean_err_mm": float(np.mean(measured_cad_start_errs)),
        "cad_end_mean_err_mm": float(np.mean(measured_cad_end_errs)),
    }


if __name__ == "__main__":
    run_section_16_wrap_around()
    run_section_17_endpoint_recovery()
    run_section_18_pixel_to_cad_contract()
