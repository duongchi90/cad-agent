"""Perimeter Support Oracle: Multi-Feature Empirical Benchmark for Circle Validation.

Evaluates:
1. Perimeter support fraction across radial bands (+/-1, +/-2, +/-3 px)
2. Angular bin coverage (12 sectors of 30 deg) & longest unsupported gap
3. Radial gradient alignment (dot product of image gradient with radial unit vector)
4. Inside/outside contrast (r-dr, r, r+dr)
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

from primitive_ir_lib.geometry_extraction import extract_circles, RawCircle


def evaluate_circle_perimeter_oracle(
    gray: np.ndarray,
    cx: float,
    cy: float,
    r: float,
    *,
    radial_tolerance_px: int = 2,
    num_angular_samples: int = 180,
    num_sectors: int = 12,
    darkness_threshold: int = 220,
    gradient_cos_threshold: float = 0.707,  # within +/- 45 deg of radial normal
) -> dict[str, object]:
    h, w = gray.shape
    angles = np.linspace(0, 2 * math.pi, num_angular_samples, endpoint=False)

    # Compute Sobel gradients for radial alignment test
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)

    supported_angles = []
    gradient_aligned_angles = []
    inside_outside_contrast_angles = []

    sector_bins = [0] * num_sectors
    sector_size = 2 * math.pi / num_sectors

    consecutive_unsupported = 0
    max_consecutive_unsupported = 0

    for i, theta in enumerate(angles):
        # 1. Radial search for dark ink
        has_ink = False
        best_pt = None
        best_dr = 0

        for dr in range(-radial_tolerance_px, radial_tolerance_px + 1):
            sample_r = r + dr
            x = int(round(cx + sample_r * math.cos(theta)))
            y = int(round(cy + sample_r * math.sin(theta)))
            if 0 <= x < w and 0 <= y < h:
                if gray[y, x] <= darkness_threshold:
                    has_ink = True
                    best_pt = (x, y)
                    best_dr = dr
                    break

        if has_ink:
            supported_angles.append(theta)
            sector_idx = int(theta / sector_size) % num_sectors
            sector_bins[sector_idx] += 1
            consecutive_unsupported = 0

            # 2. Radial Gradient Alignment
            bx, by = best_pt
            gx = grad_x[by, bx]
            gy = grad_y[by, bx]
            g_mag = math.hypot(gx, gy)
            if g_mag > 30.0:  # meaningful edge
                rx = math.cos(theta)
                ry = math.sin(theta)
                # Cosine of angle between gradient and radial vector
                cos_sim = abs(gx * rx + gy * ry) / g_mag
                if cos_sim >= gradient_cos_threshold:
                    gradient_aligned_angles.append(theta)

            # 3. Inside/Outside Contrast
            # Check r - 3 and r + 3
            rin_x = int(round(cx + (r - radial_tolerance_px - 2) * math.cos(theta)))
            rin_y = int(round(cy + (r - radial_tolerance_px - 2) * math.sin(theta)))
            rout_x = int(round(cx + (r + radial_tolerance_px + 2) * math.cos(theta)))
            rout_y = int(round(cy + (r + radial_tolerance_px + 2) * math.sin(theta)))

            val_in = gray[rin_y, rin_x] if (0 <= rin_x < w and 0 <= rin_y < h) else 255
            val_out = gray[rout_y, rout_x] if (0 <= rout_x < w and 0 <= rout_y < h) else 255
            val_ink = gray[best_pt[1], best_pt[0]]

            # Foreground-background contrast exists if ink is darker than inside/outside
            if (val_in - val_ink >= 30) and (val_out - val_ink >= 30):
                inside_outside_contrast_angles.append(theta)

        else:
            consecutive_unsupported += 1
            max_consecutive_unsupported = max(max_consecutive_unsupported, consecutive_unsupported)

    support_fraction = len(supported_angles) / num_angular_samples
    occupied_sectors = sum(1 for count in sector_bins if count > 0)
    sector_coverage_fraction = occupied_sectors / num_sectors

    deg_per_sample = 360.0 / num_angular_samples
    longest_unsupported_gap_deg = max_consecutive_unsupported * deg_per_sample

    grad_alignment_fraction = len(gradient_aligned_angles) / max(1, len(supported_angles))
    contrast_fraction = len(inside_outside_contrast_angles) / max(1, len(supported_angles))

    return {
        "support_fraction": round(support_fraction, 4),
        "occupied_sectors": occupied_sectors,
        "sector_coverage_fraction": round(sector_coverage_fraction, 4),
        "longest_unsupported_gap_deg": round(longest_unsupported_gap_deg, 1),
        "grad_alignment_fraction": round(grad_alignment_fraction, 4),
        "contrast_fraction": round(contrast_fraction, 4),
    }


def run_oracle_evaluation():
    # Import fixture generator from test_circle_false_positives_red
    from test_circle_false_positives_red import generate_fixtures
    fixtures = generate_fixtures()

    print("=== PERIMETER SUPPORT ORACLE: METRIC PROFILE MATRIX ===")
    print(f"{'Fixture':<34} | {'Expected':<8} | {'Hough Circles':<13} | {'Support':<8} | {'Sectors':<8} | {'Max Gap':<9} | {'GradAlign':<10} | {'Contrast'}")
    print("-" * 115)

    for name, (img, gtype, expected) in fixtures.items():
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        detected = extract_circles(img, min_radius=10, max_radius=80, param1=100, param2=30, min_dist=20)

        if not detected:
            # If no circle detected by Hough, test on expected/true center if exists
            if expected > 0:
                m = evaluate_circle_perimeter_oracle(gray, 150.0, 150.0, 35.0)
                print(f"{name:<34} | {expected:<8} | 0 (true eval) | {m['support_fraction']*100:<6.1f}% | {m['occupied_sectors']:<2}/12   | {m['longest_unsupported_gap_deg']:<5.1f}deg | {m['grad_alignment_fraction']*100:<8.1f}% | {m['contrast_fraction']*100:.1f}%")
            else:
                print(f"{name:<34} | {expected:<8} | 0 circles     | N/A      | N/A      | N/A       | N/A        | N/A")
        else:
            # Evaluate each detected circle candidate
            for idx, c in enumerate(detected[:3]):  # show first up to 3 candidates
                m = evaluate_circle_perimeter_oracle(gray, c.center_px[0], c.center_px[1], c.radius_px)
                prefix = f"{name} (#{idx+1})" if len(detected) > 1 else name
                print(f"{prefix:<34} | {expected:<8} | 1 c(r={c.radius_px:<3.0f})   | {m['support_fraction']*100:<6.1f}% | {m['occupied_sectors']:<2}/12   | {m['longest_unsupported_gap_deg']:<5.1f}deg | {m['grad_alignment_fraction']*100:<8.1f}% | {m['contrast_fraction']*100:.1f}%")


if __name__ == "__main__":
    run_oracle_evaluation()
