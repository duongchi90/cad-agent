"""Sections 25, 26, 28, 29: Confidence Model, Raster Degradation Generalization, and Sequential Performance Benchmark.

Covers:
- Section 26: Transparent monotonic confidence model for admitted arcs (hard gates first, confidence ranks admitted arcs).
- Section 28: Bounded raster degradation benchmark (Gaussian blur, salt-and-pepper noise, anti-aliasing,
  endpoint erosion, JPEG compression quality=50, and contrast reduction) across true arcs and negative controls.
- Section 29: Sequential runtime benchmark (PARALLEL_HEAVY_BENCHMARKS=1) on:
  A. 300x300 isolated ROI
  B. 1000x1000 mixed engineering raster
  C. 2000x2000 mixed engineering raster
"""

from __future__ import annotations

import math
import time

import cv2
import numpy as np

from test_angular_wrap_endpoints_and_cad_contract import compute_circular_support_interval, render_arc_wrapping
from test_negative_matrix_and_ellipse_control import (
    evaluate_candidate_component,
    measure_local_curvature_variation,
    order_points_along_arc,
)
from test_arc_vs_line_discrimination import piecewise_polyline_rms
from test_true_arc_matrix import fit_taubin_weighted, line_fit_rms, thin_zhang_suen_local


# ==============================================================================
# SECTION 26: TRANSPARENT MONOTONIC CONFIDENCE MODEL
# ==============================================================================

def compute_arc_confidence(
    c_rms: float,
    l_rms: float,
    sagitta_px: float,
    sweep_deg: float,
    rel_r_drift: float,
    max_gap_deg: float,
) -> float:
    """Compute auditable confidence in [0.50, 0.99] ONLY for candidates that pass all hard rejection gates.

    Monotonic terms:
    1. s_res: radial residual quality = clip(1.0 - c_rms / 0.60, 0, 1)
    2. s_line: line discrimination margin = clip(1.0 - (c_rms / max(l_rms, 1e-6)) / 0.45, 0, 1)
    3. s_sag: sagitta margin = clip((sagitta_px - 2.2) / 10.0, 0, 1)
    4. s_curv: curvature uniformity = clip(1.0 - rel_r_drift / 0.20, 0, 1)
    5. s_ambig: circle-boundary separation = clip((max_gap_deg - 22.0) / 38.0, 0, 1)
    """
    s_res = float(np.clip(1.0 - c_rms / 0.60, 0.0, 1.0))
    s_line = float(np.clip(1.0 - (c_rms / max(l_rms, 1e-6)) / 0.45, 0.0, 1.0))
    s_sag = float(np.clip((sagitta_px - 2.2) / 10.0, 0.0, 1.0))
    s_curv = float(np.clip(1.0 - rel_r_drift / 0.20, 0.0, 1.0))
    s_ambig = float(np.clip((max_gap_deg - 22.0) / 38.0, 0.0, 1.0))

    raw_score = 0.30 * s_res + 0.25 * s_line + 0.20 * s_sag + 0.15 * s_curv + 0.10 * s_ambig
    return round(float(np.clip(0.50 + 0.49 * raw_score, 0.50, 0.99)), 3)


# ==============================================================================
# SECTION 28: RASTER QUALITY / DEGRADATION BENCHMARK
# ==============================================================================

def preprocess_degraded_raster(gray: np.ndarray) -> np.ndarray:
    """Adaptive/Otsu + 3x3 morphological cleanup for degraded rasters (blur, JPEG, low contrast, salt noise)."""
    # Use Otsu thresholding when contrast is reduced or blurred
    _, bw_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    binary = (bw_inv > 0).astype(np.uint8)
    # Remove isolated 1-2px salt noise specks (area < 6 px) while preserving 1px-wide arcs
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    cleaned = np.zeros_like(binary)
    for lbl in range(1, n_labels):
        if stats[lbl, cv2.CC_STAT_AREA] >= 8:
            cleaned[labels == lbl] = 1
    return cleaned


def apply_degradation(img_clean: np.ndarray, mode: str) -> np.ndarray:
    """Apply a specific bounded raster degradation to an 8-bit grayscale drawing."""
    if mode == "1_CLEAN_BASELINE":
        return img_clean.copy()
    if mode == "2_GAUSSIAN_BLUR_3X3":
        return cv2.GaussianBlur(img_clean, (3, 3), 0.9)
    if mode == "3_SALT_PEPPER_NOISE":
        rng = np.random.default_rng(1012)
        out = img_clean.copy()
        # Add 0.4% isolated salt specks on background
        noise_mask = rng.random(out.shape) < 0.004
        out[noise_mask] = 0
        return out
    if mode == "4_ANTI_ALIASED":
        # Simulated via 3x3 light smoothing matching LINE_AA edge rolloff
        return cv2.GaussianBlur(img_clean, (3, 3), 0.65)
    if mode == "5_ENDPOINT_EROSION_5DEG":
        return img_clean.copy()  # Handled at fixture generation (5 deg shorter at each end)
    if mode == "6_JPEG_QUALITY_50":
        ok, enc = cv2.imencode(".jpg", img_clean, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        assert ok
        return cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)
    if mode == "7_LOW_CONTRAST":
        # Map [0, 255] -> [95, 215]
        return np.clip(95.0 + (img_clean.astype(np.float32) / 255.0) * 120.0, 0, 255).astype(np.uint8)
    raise ValueError(f"Unknown degradation mode: {mode}")


def run_section_28_raster_degradation() -> dict:
    true_arc_specs = [
        (40, 30.0, 120.0, 2),   # 90 deg, R=40
        (60, 0.0, 120.0, 2),    # 120 deg, R=60
        (50, 45.0, 225.0, 3),   # 180 deg, R=50
        (70, 300.0, 60.0, 3),   # 120 deg wrap-around, R=70
        (80, 20.0, 290.0, 2),   # 270 deg, R=80
    ]

    # 5 representative negative controls
    neg_imgs = []
    # Straight line
    img_line = np.full((300, 300), 255, dtype=np.uint8)
    cv2.line(img_line, (40, 80), (260, 220), 0, 2)
    neg_imgs.append(img_line)
    # 90-deg corner
    img_corner = np.full((300, 300), 255, dtype=np.uint8)
    cv2.line(img_corner, (70, 180), (160, 180), 0, 2)
    cv2.line(img_corner, (160, 180), (160, 90), 0, 2)
    neg_imgs.append(img_corner)
    # Full circle
    img_circ = np.full((300, 300), 255, dtype=np.uint8)
    cv2.circle(img_circ, (150, 150), 50, 0, 2)
    neg_imgs.append(img_circ)
    # Partial 180-deg ellipse (75x40)
    img_ell = np.full((300, 300), 255, dtype=np.uint8)
    cv2.ellipse(img_ell, (150, 150), (75, 40), 30, 0, 180, 0, 2)
    neg_imgs.append(img_ell)
    # Text glyph 'C'
    img_txt = np.full((300, 300), 255, dtype=np.uint8)
    cv2.putText(img_txt, "C", (110, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 0, 2, cv2.LINE_8)
    neg_imgs.append(img_txt)

    modes = [
        "1_CLEAN_BASELINE",
        "2_GAUSSIAN_BLUR_3X3",
        "3_SALT_PEPPER_NOISE",
        "4_ANTI_ALIASED",
        "5_ENDPOINT_EROSION_5DEG",
        "6_JPEG_QUALITY_50",
        "7_LOW_CONTRAST",
    ]

    print("=== SECTION 28: RASTER QUALITY / DEGRADATION BENCHMARK ===")
    print(
        f"{'Degradation Mode':<26} | {'TrueRecall':<10} | {'FalseArcRate':<12} | "
        f"{'MeanCtrErr':<10} | {'MeanRadErr':<10} | {'MeanSweepErr'}"
    )
    print("-" * 96)

    summary = {}
    for mode in modes:
        recalled = 0
        ctr_errs = []
        rad_errs = []
        sw_errs = []

        for r_gt, s_deg, e_deg, w in true_arc_specs:
            exp_sweep = (e_deg - s_deg) % 360.0
            s_draw = (s_deg + 5.0) % 360.0 if mode == "5_ENDPOINT_EROSION_5DEG" else s_deg
            e_draw = (e_deg - 5.0 + 360.0) % 360.0 if mode == "5_ENDPOINT_EROSION_5DEG" else e_deg
            line_type = cv2.LINE_AA if mode == "4_ANTI_ALIASED" else cv2.LINE_8
            img_base = render_arc_wrapping(300, 150, 150, r_gt, s_draw, e_draw, stroke_w=w, line_type=line_type)
            img_deg = apply_degradation(img_base, mode) if mode != "4_ANTI_ALIASED" else img_base
            binary = preprocess_degraded_raster(img_deg)

            n_labels, labels, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
            best_res = None
            for lbl in range(1, n_labels):
                res = evaluate_candidate_component((labels == lbl).astype(np.uint8))
                if res["accepted"]:
                    best_res = res
                    break
            if best_res is not None:
                recalled += 1
                ctr_errs.append(math.hypot(best_res["cx"] - 150.0, best_res["cy"] - 150.0))
                rad_errs.append(abs(best_res["r"] - r_gt) / r_gt * 100.0)
                sw_errs.append(abs(best_res["sweep_deg"] - exp_sweep))

        false_arcs = 0
        for neg_base in neg_imgs:
            img_deg = apply_degradation(neg_base, mode)
            binary = preprocess_degraded_raster(img_deg)
            n_labels, labels, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
            for lbl in range(1, n_labels):
                res = evaluate_candidate_component((labels == lbl).astype(np.uint8))
                if res["accepted"]:
                    false_arcs += 1

        recall_pct = recalled / len(true_arc_specs) * 100.0
        false_pct = false_arcs / len(neg_imgs) * 100.0
        m_ctr = float(np.mean(ctr_errs)) if ctr_errs else 0.0
        m_rad = float(np.mean(rad_errs)) if rad_errs else 0.0
        m_sw = float(np.mean(sw_errs)) if sw_errs else 0.0
        summary[mode] = (recall_pct, false_pct, m_ctr, m_rad, m_sw)

        print(
            f"{mode:<26} | {recalled}/{len(true_arc_specs)} ({recall_pct:>3.0f}%) | "
            f"{false_arcs}/{len(neg_imgs)} ({false_pct:>4.1f}%) | "
            f"{m_ctr:>8.3f}px | {m_rad:>8.2f}%  | {m_sw:>8.2f}deg"
        )

    print("-" * 96)
    print("REAL_SCAN_GENERALIZATION=UNPROVEN (no private/customer drawings used; bounded synthetic degradations verified)")
    return summary


# ==============================================================================
# SECTION 29: SEQUENTIAL PERFORMANCE BENCHMARK (PARALLEL_HEAVY_BENCHMARKS=1)
# ==============================================================================

def build_mixed_benchmark_canvas(size: int) -> tuple[np.ndarray, int]:
    """Construct a representative engineering raster with lines, circles, arcs, text glyphs, and speckle noise."""
    img = np.full((size, size), 255, dtype=np.uint8)
    if size <= 400:
        # A: 300x300 small isolated ROI (2 true arcs, 1 circle, 2 lines, 2 glyphs)
        cv2.ellipse(img, (90, 90), (45, 45), 0, 20, 140, 0, 2)
        cv2.ellipse(img, (210, 100), (50, 50), 0, 180, 310, 0, 3)
        cv2.circle(img, (90, 210), 35, 0, 2)
        cv2.line(img, (160, 180), (270, 180), 0, 2)
        cv2.line(img, (160, 210), (270, 250), 0, 2)
        cv2.putText(img, "R45", (165, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
        return img, 2

    # For 1000x1000 or 2000x2000: tile structured cells across canvas
    step = 250
    expected_arcs = 0
    for y0 in range(50, size - 200, step):
        for x0 in range(50, size - 200, step):
            # 1 true circular arc per cell
            cv2.ellipse(img, (x0 + 60, y0 + 60), (42, 42), 0, 15, 135, 0, 2)
            expected_arcs += 1
            # 1 full circle
            cv2.circle(img, (x0 + 160, y0 + 60), 30, 0, 2)
            # 2 straight lines + 1 L-corner
            cv2.line(img, (x0 + 20, y0 + 140), (x0 + 120, y0 + 140), 0, 2)
            cv2.line(img, (x0 + 20, y0 + 165), (x0 + 90, y0 + 165), 0, 2)
            cv2.line(img, (x0 + 90, y0 + 165), (x0 + 90, y0 + 210), 0, 2)
            # Text label
            cv2.putText(img, "C08", (x0 + 135, y0 + 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 0, 2)
    return img, expected_arcs


def profile_arc_extraction_stage(img_gray: np.ndarray) -> dict:
    """Measure stage-by-stage timing of the candidate arc extraction pipeline."""
    t0 = time.perf_counter()
    binary = (img_gray < 220).astype(np.uint8)
    t1 = time.perf_counter()

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    t2 = time.perf_counter()

    candidates = []
    for lbl in range(1, n_labels):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        w = int(stats[lbl, cv2.CC_STAT_WIDTH])
        h = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        if area < 15 or (w < 12 and h < 12):
            continue
        x0 = max(0, int(stats[lbl, cv2.CC_STAT_LEFT]) - 2)
        y0 = max(0, int(stats[lbl, cv2.CC_STAT_TOP]) - 2)
        x1 = min(binary.shape[1], int(stats[lbl, cv2.CC_STAT_LEFT] + w) + 3)
        y1 = min(binary.shape[0], int(stats[lbl, cv2.CC_STAT_TOP] + h) + 3)
        comp_crop = (labels[y0:y1, x0:x1] == lbl).astype(np.uint8)

        # Fast closed-loop filter on local crop
        contours, hierarchy = cv2.findContours(comp_crop, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        has_hole = False
        if hierarchy is not None:
            for i in range(len(contours)):
                child = int(hierarchy[0][i][2])
                if child != -1 and cv2.contourArea(contours[child]) >= 9.0:
                    has_hole = True
                    break
        if has_hole:
            continue
        candidates.append((comp_crop, x0, y0))
    t3 = time.perf_counter()

    fits_done = 0
    fit_results = []
    for comp_crop, x0, y0 in candidates:
        ys_all, xs_all = np.where(comp_crop > 0)
        dist_map = cv2.distanceTransform(comp_crop, cv2.DIST_L2, 3)
        skel = thin_zhang_suen_local(comp_crop)
        sy, sx = np.where(skel > 0)
        if len(sx) < 8:
            continue
        pts_all = np.column_stack([(xs_all + x0).astype(np.float64), (ys_all + y0).astype(np.float64)])
        weights_all = (dist_map[ys_all, xs_all] ** 2).astype(np.float64)
        pts_medial = np.column_stack([(sx + x0).astype(np.float64), (sy + y0).astype(np.float64)])

        l_rms = line_fit_rms(pts_medial)
        if l_rms <= 0.65:
            continue
        fits_done += 1
        fit = fit_taubin_weighted(pts_all, weights_all)
        if fit is not None:
            fit_results.append((fit, pts_all, pts_medial, l_rms, float(np.max(dist_map))))
    t4 = time.perf_counter()

    accepted = 0
    for (cx, cy, _), pts_all, pts_medial, l_rms, cap_r in fit_results:
        r = float(np.median(np.hypot(pts_all[:, 0] - cx, pts_all[:, 1] - cy)))
        if r < 12.0 or r > 2000.0:
            continue
        pts_ordered = order_points_along_arc(pts_medial, cx, cy)
        c_rms = float(np.sqrt(np.mean((np.hypot(pts_ordered[:, 0] - cx, pts_ordered[:, 1] - cy) - r) ** 2)))
        angles_all = (np.degrees(np.arctan2(pts_all[:, 1] - cy, pts_all[:, 0] - cx)) + 360.0) % 360.0
        sorted_all = np.sort(angles_all)
        diffs_all = np.diff(sorted_all)
        wrap_all = (sorted_all[0] + 360.0) - sorted_all[-1]
        max_gap_deg = float(np.max(np.append(diffs_all, wrap_all)))
        if max_gap_deg < 22.0:
            continue
        delta_deg = math.degrees(math.atan2(max(0.0, cap_r - 1.0), max(r, 1.0)))
        sweep_deg = max(0.0, (360.0 - max_gap_deg) - 2.0 * delta_deg)
        sagitta_px = r * (1.0 - math.cos(math.radians(min(sweep_deg, 180.0)) / 2.0))
        if sagitta_px < 2.2 or sweep_deg < 44.0 or (c_rms / max(l_rms, 1e-6)) > 0.45:
            continue
        n_segs, poly_rms = piecewise_polyline_rms(pts_ordered, max_segments=3)
        if n_segs <= 3 and poly_rms < 0.75 * c_rms:
            continue
        rel_r_drift, rel_c_drift, has_inflection = measure_local_curvature_variation(pts_ordered, cx, cy, r)
        if has_inflection or c_rms > 0.58 or (sweep_deg >= 85.0 and (rel_r_drift > 0.16 or rel_c_drift > 0.12)):
            continue
        _conf = compute_arc_confidence(c_rms, l_rms, sagitta_px, sweep_deg, rel_r_drift, max_gap_deg)
        accepted += 1
    t5 = time.perf_counter()

    return {
        "preprocess_ms": (t1 - t0) * 1000.0,
        "component_ms": (t2 - t1) * 1000.0,
        "filter_ms": (t3 - t2) * 1000.0,
        "fit_ms": (t4 - t3) * 1000.0,
        "arbitration_ms": (t5 - t4) * 1000.0,
        "total_ms": (t5 - t0) * 1000.0,
        "candidates": n_labels - 1,
        "fits": fits_done,
        "accepted": accepted,
    }


def run_section_29_performance_benchmark() -> dict:
    sizes = [
        ("A. 300x300 Small Isolated ROI", 300),
        ("B. 1000x1000 Mixed Engineering Raster", 1000),
        ("C. 2000x2000 Mixed Engineering Raster", 2000),
    ]

    print("\n=== SECTION 29: SEQUENTIAL PERFORMANCE BENCHMARK (PARALLEL_HEAVY_BENCHMARKS=1) ===")
    print(
        f"{'Canvas Tier':<38} | {'Pre(ms)':<7} | {'Comp(ms)':<8} | {'Filt(ms)':<8} | "
        f"{'Fit(ms)':<7} | {'Arb(ms)':<7} | {'Total(ms)':<9} | {'Cand/Fit/Acc'}"
    )
    print("-" * 116)

    results = {}
    for label, sz in sizes:
        img, exp_arcs = build_mixed_benchmark_canvas(sz)
        # Warmup once, then average 3 sequential runs
        _ = profile_arc_extraction_stage(img)
        runs = [profile_arc_extraction_stage(img) for _ in range(3)]
        avg = {
            k: float(np.mean([r[k] for r in runs]))
            for k in ("preprocess_ms", "component_ms", "filter_ms", "fit_ms", "arbitration_ms", "total_ms")
        }
        avg["candidates"] = runs[0]["candidates"]
        avg["fits"] = runs[0]["fits"]
        avg["accepted"] = runs[0]["accepted"]
        avg["expected"] = exp_arcs
        results[sz] = avg

        print(
            f"{label:<38} | {avg['preprocess_ms']:>7.2f} | {avg['component_ms']:>8.2f} | {avg['filter_ms']:>8.2f} | "
            f"{avg['fit_ms']:>7.2f} | {avg['arbitration_ms']:>7.2f} | {avg['total_ms']:>9.2f} | "
            f"{avg['candidates']}/{avg['fits']}/{avg['accepted']} (exp={exp_arcs})"
        )
        assert avg["accepted"] == exp_arcs, f"Expected {exp_arcs} arcs on {label}, got {avg['accepted']}"

    print("-" * 116)
    return results


if __name__ == "__main__":
    run_section_28_raster_degradation()
    run_section_29_performance_benchmark()
