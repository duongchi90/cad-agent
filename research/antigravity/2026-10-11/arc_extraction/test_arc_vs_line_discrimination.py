"""Critical Failure Mode 14A: ARC vs LINE Discrimination.

Tests:
- straight lines (various lengths and angles)
- 15-deg arcs
- 30-deg arcs
- 45-deg arcs
- large-radius shallow arcs (R=300, 600, 1200 px with chord ~100px)
- two-segment corners (L-corners at 90, 120, 150, 165 deg)
- three-segment polyline curvature approximations

Verifies fail-closed classification:
- CURVATURE_INSUFFICIENT_FOR_ARC
- PIECEWISE_LINEAR_NOT_ARC
- TRUE_ARC
"""

from __future__ import annotations

import math
from typing import Optional

import cv2
import numpy as np

from test_true_arc_matrix import fit_taubin_weighted, line_fit_rms, thin_zhang_suen_local


def piecewise_polyline_rms(pts_ordered: np.ndarray, max_segments: int = 3) -> tuple[int, float]:
    """Compute RMS distance of ordered chain points to a simplified 2- or 3-segment polyline."""
    if len(pts_ordered) < 4:
        return 1, 0.0
    contour = pts_ordered.reshape(-1, 1, 2).astype(np.float32)
    arc_len = cv2.arcLength(contour, closed=False)
    # Approximate with small epsilon to see if <= 3 straight segments explain the geometry
    approx = cv2.approxPolyDP(contour, epsilon=max(1.2, 0.018 * arc_len), closed=False)
    verts = approx.reshape(-1, 2).astype(np.float64)
    n_segs = max(1, len(verts) - 1)
    if n_segs > max_segments:
        return n_segs, 999.0

    # Distance from each point to nearest segment of the simplified polyline
    min_d2 = np.full(len(pts_ordered), float("inf"), dtype=np.float64)
    for i in range(len(verts) - 1):
        a = verts[i]
        b = verts[i + 1]
        ab = b - a
        ab_len2 = float(np.dot(ab, ab))
        if ab_len2 <= 1e-12:
            d2 = np.sum((pts_ordered - a) ** 2, axis=1)
        else:
            t = np.clip(((pts_ordered - a) @ ab) / ab_len2, 0.0, 1.0)
            proj = a[None, :] + t[:, None] * ab[None, :]
            d2 = np.sum((pts_ordered - proj) ** 2, axis=1)
        min_d2 = np.minimum(min_d2, d2)
    return n_segs, float(np.sqrt(np.mean(min_d2)))


def classify_arc_vs_line(gray: np.ndarray) -> dict:
    """Evaluate a raster stroke and classify as TRUE_ARC, CURVATURE_INSUFFICIENT_FOR_ARC, or PIECEWISE_LINEAR_NOT_ARC."""
    binary = (gray < 220).astype(np.uint8)
    ys_all, xs_all = np.where(binary > 0)
    if len(xs_all) < 5:
        return {"status": "CURVATURE_INSUFFICIENT_FOR_ARC", "reason": "TOO_FEW_PIXELS"}

    x0, x1 = max(0, int(np.min(xs_all)) - 2), min(gray.shape[1], int(np.max(xs_all)) + 3)
    y0, y1 = max(0, int(np.min(ys_all)) - 2), min(gray.shape[0], int(np.max(ys_all)) + 3)
    local_bin = binary[y0:y1, x0:x1]
    dist_map = cv2.distanceTransform(local_bin, cv2.DIST_L2, 3)
    skel = thin_zhang_suen_local(local_bin)
    sy, sx = np.where(skel > 0)

    pts_all = np.column_stack([xs_all.astype(np.float64), ys_all.astype(np.float64)])
    weights_all = (dist_map[ys_all - y0, xs_all - x0] ** 2).astype(np.float64)
    pts_medial = (
        np.column_stack([(sx + x0).astype(np.float64), (sy + y0).astype(np.float64)])
        if len(sx) >= 5 else pts_all
    )

    l_rms = line_fit_rms(pts_medial)
    fit = fit_taubin_weighted(pts_all, weights_all)
    if fit is None:
        return {"status": "CURVATURE_INSUFFICIENT_FOR_ARC", "line_rms": l_rms, "circle_rms": 999.0, "sagitta": 0.0, "r": 0.0, "sweep": 0.0}

    cx, cy, _ = fit
    rad_all = np.hypot(pts_all[:, 0] - cx, pts_all[:, 1] - cy)
    r = float(np.median(rad_all))
    rad_medial = np.hypot(pts_medial[:, 0] - cx, pts_medial[:, 1] - cy)
    c_rms = float(np.sqrt(np.mean((rad_medial - r) ** 2)))

    angles_all = (np.degrees(np.arctan2(pts_all[:, 1] - cy, pts_all[:, 0] - cx)) + 360.0) % 360.0
    sorted_all = np.sort(angles_all)
    diffs_all = np.diff(sorted_all)
    wrap_all = (sorted_all[0] + 360.0) - sorted_all[-1]
    sweep_deg = 360.0 - float(np.max(np.append(diffs_all, wrap_all)))

    angles_medial = (np.degrees(np.arctan2(pts_medial[:, 1] - cy, pts_medial[:, 0] - cx)) + 360.0) % 360.0
    pts_ordered = pts_medial[np.argsort(angles_medial)]
    sagitta_px = r * (1.0 - math.cos(math.radians(min(sweep_deg, 180.0)) / 2.0))

    # Gate 1: Straight line / shallow arc check
    if l_rms <= 0.65 or sagitta_px < 2.2 or sweep_deg < 44.0 or (c_rms / max(l_rms, 1e-6)) > 0.45:
        return {
            "status": "CURVATURE_INSUFFICIENT_FOR_ARC",
            "line_rms": l_rms, "circle_rms": c_rms, "sagitta": sagitta_px, "r": r, "sweep": sweep_deg,
        }

    # Gate 2: Piecewise linear (2-segment corner or 3-segment polyline) check
    # A piecewise-linear corner/polyline has a much lower polyline RMS than circular RMS.
    n_segs, poly_rms = piecewise_polyline_rms(pts_ordered, max_segments=3)
    if n_segs <= 3 and poly_rms < 0.75 * c_rms:
        return {
            "status": "PIECEWISE_LINEAR_NOT_ARC",
            "line_rms": l_rms, "circle_rms": c_rms, "poly_rms": poly_rms, "sagitta": sagitta_px, "r": r, "sweep": sweep_deg,
        }

    if c_rms > max(0.75, 0.04 * r):
        return {
            "status": "RESIDUAL_TOO_HIGH_NOT_ARC",
            "line_rms": l_rms, "circle_rms": c_rms, "sagitta": sagitta_px, "r": r, "sweep": sweep_deg,
        }

    return {
        "status": "TRUE_ARC",
        "line_rms": l_rms, "circle_rms": c_rms, "sagitta": sagitta_px, "r": r, "sweep": sweep_deg,
    }


def run_arc_vs_line_experiment() -> None:
    fixtures = []

    # 1. Straight lines
    for angle_deg, length in [(0, 120), (23, 120), (45, 150), (90, 80)]:
        img = np.full((300, 300), 255, dtype=np.uint8)
        rad = math.radians(angle_deg)
        x1, y1 = int(150 - 0.5 * length * math.cos(rad)), int(150 - 0.5 * length * math.sin(rad))
        x2, y2 = int(150 + 0.5 * length * math.cos(rad)), int(150 + 0.5 * length * math.sin(rad))
        cv2.line(img, (x1, y1), (x2, y2), 0, 2)
        fixtures.append((f"Straight Line (L={length}, ang={angle_deg}deg)", "NON_ARC", img))

    # 2. Short & Medium Arcs (15, 30, 45, 60, 90 deg at R=40 and R=80)
    for sw in (15, 30, 45, 60, 90):
        for r in (40, 80):
            img = np.full((300, 300), 255, dtype=np.uint8)
            cv2.ellipse(img, (150, 150), (r, r), 0, 0, sw, 0, 2)
            exp = "TRUE_ARC" if (sw >= 45 and r * (1 - math.cos(math.radians(sw / 2.0))) >= 2.2) else "NON_ARC"
            fixtures.append((f"Arc (sweep={sw}deg, R={r}px)", exp, img))

    # 3. Large-radius shallow arcs (chord ~ 100px, R=400, 800, 1200)
    for r_large, sw_shallow in [(400, 14), (800, 7), (1200, 5)]:
        img = np.full((300, 300), 255, dtype=np.uint8)
        cv2.ellipse(img, (150 - r_large + 50, 150), (r_large, r_large), 0, -sw_shallow / 2.0, sw_shallow / 2.0, 0, 2)
        fixtures.append((f"Large-R Shallow Arc (R={r_large}, sw={sw_shallow}deg)", "NON_ARC", img))

    # 4. Two-segment corners (L-corners at 90, 120, 150 deg)
    for corner_deg in (90, 120, 150):
        img = np.full((300, 300), 255, dtype=np.uint8)
        cv2.line(img, (90, 150), (150, 150), 0, 2)
        rad = math.radians(180 - corner_deg)
        x2 = int(150 + 60 * math.cos(rad))
        y2 = int(150 - 60 * math.sin(rad))
        cv2.line(img, (150, 150), (x2, y2), 0, 2)
        fixtures.append((f"Two-Segment Corner ({corner_deg}deg)", "NON_ARC", img))

    # 5. Three-segment polyline curvature approximation
    img_poly = np.full((300, 300), 255, dtype=np.uint8)
    pts_poly = np.array([[80, 200], [115, 140], [185, 140], [220, 200]], dtype=np.int32)
    cv2.polylines(img_poly, [pts_poly], isClosed=False, color=0, thickness=2)
    fixtures.append(("Three-Segment Polyline Approx", "NON_ARC", img_poly))

    print("=== SECTION 14A: ARC VS LINE DISCRIMINATION BENCHMARK ===")
    print(f"{'Fixture':<44} | {'Expected':<10} | {'LineRMS':<8} | {'CircRMS':<8} | {'Sagitta':<8} | {'Fit R':<8} | {'Classification'}")
    print("-" * 124)

    false_arcs = 0
    for name, expected, img in fixtures:
        res = classify_arc_vs_line(img)
        status = res["status"]
        if expected == "NON_ARC" and status == "TRUE_ARC":
            false_arcs += 1
        print(
            f"{name:<44} | {expected:<10} | {res['line_rms']:>6.2f}px | {res['circle_rms']:>6.2f}px | "
            f"{res['sagitta']:>6.2f}px | {res['r']:>6.1f}px | {status}"
        )

    print("-" * 124)
    print(f"FALSE_ARC_DETECTIONS_ON_SHALLOW_OR_LINEAR_GEOMETRY={false_arcs}")
    assert false_arcs == 0, f"Expected 0 false arcs on linear/shallow/polyline inputs, got {false_arcs}"


if __name__ == "__main__":
    run_arc_vs_line_experiment()
