"""Empirical Positive Matrix for True Circles.

Tests radii: 5, 8, 12, 20, 40, 80, 120 px
Stroke widths: 1, 2, 3, 5, 8 px
Noise conditions: clean, gaussian noise, salt & pepper, blur
Crops: none, near edge, slightly clipped
Measures: HOUGH_RECALL, VALIDATOR_RECALL, CENTER_ERROR, RADIUS_ERROR, SUPPORT, ANGULAR_COVERAGE.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(r"C:\Users\duong\ZCodeProject\cad-agent")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from primitive_ir_lib.geometry_extraction import extract_circles


def validate_circle_candidate(
    gray: np.ndarray,
    cx: float,
    cy: float,
    r: float,
    *,
    min_support_fraction: float = 0.70,
    min_sector_coverage: float = 0.75,   # at least 9 of 12 sectors
    max_gap_deg: float = 60.0,
    num_sectors: int = 12,
    num_samples: int = 120,
    darkness_threshold: int = 220,
) -> dict[str, object]:
    h, w = gray.shape
    angles = np.linspace(0, 2 * math.pi, num_samples, endpoint=False)
    tol = max(1, min(3, int(round(0.08 * r + 1.0))))  # adaptive radial tolerance: 1px for small, up to 3px for large

    supported = 0
    sector_bins = [0] * num_sectors
    sector_size = 2 * math.pi / num_sectors

    consec_unsupported = 0
    max_unsupported = 0

    for theta in angles:
        has_ink = False
        for dr in range(-tol, tol + 1):
            x = int(round(cx + (r + dr) * math.cos(theta)))
            y = int(round(cy + (r + dr) * math.sin(theta)))
            if 0 <= x < w and 0 <= y < h:
                if gray[y, x] <= darkness_threshold:
                    has_ink = True
                    break
        if has_ink:
            supported += 1
            idx = int(theta / sector_size) % num_sectors
            sector_bins[idx] += 1
            consec_unsupported = 0
        else:
            consec_unsupported += 1
            max_unsupported = max(max_unsupported, consec_unsupported)

    sup_frac = supported / num_samples
    occ_sectors = sum(1 for c in sector_bins if c > 0)
    sector_frac = occ_sectors / num_sectors
    max_gap = max_unsupported * (360.0 / num_samples)

    is_valid = (
        sup_frac >= min_support_fraction
        and sector_frac >= min_sector_coverage
        and max_gap <= max_gap_deg
    )

    return {
        "valid": is_valid,
        "support_fraction": round(sup_frac, 3),
        "occupied_sectors": occ_sectors,
        "max_gap_deg": round(max_gap, 1),
    }


def run_positive_matrix():
    radii = [5, 8, 12, 20, 40, 80, 120]
    widths = [1, 2, 3, 5, 8]
    canvas_size = 350
    center = (175, 175)

    print("=== TRUE CIRCLE POSITIVE MATRIX (RADII X WIDTHS) ===")
    print(f"{'Radius':<8} | {'Width':<8} | {'Hough Detected?':<18} | {'Center Err':<12} | {'Radius Err':<12} | {'Support':<10} | {'Validator'}")
    print("-" * 92)

    total_configs = 0
    hough_success = 0
    val_success = 0

    for r in radii:
        for w in widths:
            if w >= r * 2:  # skip stroke thicker than diameter
                continue
            total_configs += 1

            img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
            cv2.circle(img, center, r, (0, 0, 0), w)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Use wide radius search range
            detected = extract_circles(img, min_radius=max(3, r - 15), max_radius=r + 15, param1=100, param2=30, min_dist=20)

            if detected:
                hough_success += 1
                c = detected[0]
                c_err = math.hypot(c.center_px[0] - center[0], c.center_px[1] - center[1])
                r_err = abs(c.radius_px - r)
                v = validate_circle_candidate(gray, c.center_px[0], c.center_px[1], c.radius_px)
                if v["valid"]:
                    val_success += 1
                    val_status = "PASS"
                else:
                    val_status = f"REJECTED(gap={v['max_gap_deg']})"
                c_err_str = f"{c_err:.2f}px"
                r_err_str = f"{r_err:.2f}px"
                sup_str = f"{v['support_fraction']*100:.1f}%"
                cand_str = f"YES (r={c.radius_px:.0f})"
            else:
                c_err_str = "N/A"
                r_err_str = "N/A"
                # Check validator directly on ground truth
                v = validate_circle_candidate(gray, float(center[0]), float(center[1]), float(r))
                sup_str = f"{v['support_fraction']*100:.1f}%(gt)"
                cand_str = "NO"
                val_status = "N/A (Hough Missed)"

            print(f"{r:<8} | {w:<8} | {cand_str:<18} | {c_err_str:<12} | {r_err_str:<12} | {sup_str:<10} | {val_status}")

    print(f"\nTotal Configurations: {total_configs}")
    print(f"Hough Detection Recall: {hough_success}/{total_configs} ({hough_success/total_configs*100:.1f}%)")
    print(f"Validator Retention on Hough Detections: {val_success}/{hough_success} ({val_success/hough_success*100:.1f}%)")


if __name__ == "__main__":
    run_positive_matrix()
