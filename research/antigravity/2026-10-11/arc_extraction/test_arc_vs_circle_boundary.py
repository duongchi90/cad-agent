"""Critical Failure Mode 14B: ARC vs CIRCLE Boundary & Mutual Exclusion.

Tests angular sweeps:
- 300 deg
- 330 deg
- 345 deg
- 350 deg
- 355 deg
- 360 deg

Measures:
- angular support fraction
- largest unsupported angular gap (deg)
- endpoint separation (px)
- topological loop closure evidence

Classifies into mutually exclusive states:
- ARC
- CIRCLE
- AMBIGUOUS_NEAR_FULL_CIRCLE
Never emits both ARC and CIRCLE from the same physical evidence.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from test_true_arc_matrix import fit_taubin_weighted, thin_zhang_suen_local


def evaluate_arc_vs_circle_boundary(gray: np.ndarray) -> dict:
    """Measure closure, angular support, largest gap, endpoint separation, and classify."""
    binary = (gray < 220).astype(np.uint8)
    ys_all, xs_all = np.where(binary > 0)
    x0, x1 = max(0, int(np.min(xs_all)) - 2), min(gray.shape[1], int(np.max(xs_all)) + 3)
    y0, y1 = max(0, int(np.min(ys_all)) - 2), min(gray.shape[0], int(np.max(ys_all)) + 3)
    local_bin = binary[y0:y1, x0:x1]

    dist_map = cv2.distanceTransform(local_bin, cv2.DIST_L2, 3)
    max_half_w = float(np.max(dist_map))
    skel = thin_zhang_suen_local(local_bin)

    # Topological closure check: count degree-1 endpoints on skeleton and inner hole components
    padded_skel = np.pad(skel, 1, mode="constant", constant_values=0)
    sy, sx = np.where(skel > 0)
    deg1_count = 0
    for y_p, x_p in zip(sy + 1, sx + 1):
        nb = int(np.sum(padded_skel[y_p - 1 : y_p + 2, x_p - 1 : x_p + 2])) - 1
        if nb == 1:
            deg1_count += 1

    # Check if background has an enclosed inner hole (hierarchy in findContours)
    contours, hierarchy = cv2.findContours(local_bin, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    has_enclosed_hole = False
    if hierarchy is not None:
        for h_node in hierarchy[0]:
            if h_node[3] != -1:  # has parent contour -> interior hole
                has_enclosed_hole = True
                break

    pts_all = np.column_stack([xs_all.astype(np.float64), ys_all.astype(np.float64)])
    weights_all = (dist_map[ys_all - y0, xs_all - x0] ** 2).astype(np.float64)
    cx, cy, _ = fit_taubin_weighted(pts_all, weights_all)
    rad_all = np.hypot(pts_all[:, 0] - cx, pts_all[:, 1] - cy)
    r = float(np.median(rad_all))

    # Sample 360 angular bins around circumference at radius r (+/- max_half_w + 1)
    num_bins = 360
    supported_bins = np.zeros(num_bins, dtype=bool)
    angles_all = (np.degrees(np.arctan2(pts_all[:, 1] - cy, pts_all[:, 0] - cx)) + 360.0) % 360.0
    bin_indices = np.floor(angles_all).astype(int) % num_bins
    supported_bins[bin_indices] = True

    angular_support = float(np.mean(supported_bins))

    # Largest contiguous unsupported gap (in degrees) + cap compensation
    order = np.argsort(angles_all)
    sorted_ang = angles_all[order]
    diffs = np.diff(sorted_ang)
    wrap_diff = (sorted_ang[0] + 360.0) - sorted_ang[-1]
    all_gaps = np.append(diffs, wrap_diff)
    max_gap_idx = int(np.argmax(all_gaps))
    raw_gap_deg = float(all_gaps[max_gap_idx])

    cap_overhang_px = max(0.0, max_half_w - 1.0)
    cap_angle_deg = math.degrees(math.atan2(cap_overhang_px, r)) if r > 1.0 else 0.0
    effective_gap_deg = 0.0 if has_enclosed_hole else (raw_gap_deg + 2.0 * cap_angle_deg)

    # Endpoint separation in pixels
    if has_enclosed_hole:
        endpoint_sep_px = 0.0
    else:
        endpoint_sep_px = 2.0 * r * math.sin(math.radians(min(effective_gap_deg, 180.0) / 2.0))

    closure_evidence = has_enclosed_hole and (deg1_count == 0)

    # Mutually exclusive classification
    if closure_evidence and effective_gap_deg <= 5.0:
        classification = "CIRCLE"
        emitted_arcs = 0
        emitted_circles = 1
    elif (not closure_evidence) and effective_gap_deg >= 20.0 and endpoint_sep_px >= max(3.5, 2.0 * max_half_w):
        classification = "ARC"
        emitted_arcs = 1
        emitted_circles = 0
    else:
        classification = "AMBIGUOUS_NEAR_FULL_CIRCLE"
        emitted_arcs = 0
        emitted_circles = 0

    return {
        "r": r,
        "angular_support": angular_support,
        "largest_gap_deg": effective_gap_deg,
        "endpoint_sep_px": endpoint_sep_px,
        "closure_evidence": closure_evidence,
        "classification": classification,
        "emitted_arcs": emitted_arcs,
        "emitted_circles": emitted_circles,
    }


def run_arc_vs_circle_benchmark() -> None:
    sweeps = [300, 330, 345, 350, 355, 360]
    radii = [25, 50, 90]

    print("=== SECTION 14B: ARC VS CIRCLE BOUNDARY & MUTUAL EXCLUSION BENCHMARK ===")
    print(f"{'Radius':<8} | {'Sweep':<8} | {'AngSupport':<11} | {'MaxGap(deg)':<12} | {'EndptSep(px)':<13} | {'ClosedLoop':<11} | {'Classification':<28} | {'Arc/Circ Emitted'}")
    print("-" * 126)

    dual_emissions = 0
    for r in radii:
        for sw in sweeps:
            img = np.full((300, 300), 255, dtype=np.uint8)
            cv2.ellipse(img, (150, 150), (r, r), 0, 0, sw, 0, 2)
            res = evaluate_arc_vs_circle_boundary(img)
            if res["emitted_arcs"] + res["emitted_circles"] > 1:
                dual_emissions += 1
            print(
                f"{r:>5} px | {sw:>5} deg | {res['angular_support']*100:>9.1f}% | "
                f"{res['largest_gap_deg']:>10.2f}   | {res['endpoint_sep_px']:>11.2f}   | "
                f"{str(res['closure_evidence']):<11} | {res['classification']:<28} | "
                f"ARC={res['emitted_arcs']}, CIRCLE={res['emitted_circles']}"
            )

    print("-" * 126)
    print(f"DUAL_EMISSION_VIOLATIONS={dual_emissions}")
    assert dual_emissions == 0, "Never emit both ARC and CIRCLE from the same physical evidence"


if __name__ == "__main__":
    run_arc_vs_circle_benchmark()
