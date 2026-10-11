"""Empirical Test: Arc vs Circle Conflation in HoughCircles.

Tests visible circumference coverage:
15, 30, 45, 60, 90, 120, 180, 240, 300, 330, 360 degrees.
Measures:
- VISIBLE_ARC_FRACTION
- HOUGH_CANDIDATE_PRESENT
- CENTER_ERROR
- RADIUS_ERROR
- PERIMETER_SUPPORT_FRACTION (actual dark pixels along full 360 circumference)
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


def measure_perimeter_support(
    gray: np.ndarray,
    cx: float,
    cy: float,
    r: float,
    radial_tolerance_px: int = 2,
    num_samples: int = 360,
    darkness_threshold: int = 220,
) -> float:
    """Sample full 360 degrees. Returns fraction of angles having ink within +/- radial_tolerance_px."""
    angles = np.linspace(0, 2 * math.pi, num_samples, endpoint=False)
    h, w = gray.shape
    supported = 0

    for theta in angles:
        has_ink = False
        for dr in range(-radial_tolerance_px, radial_tolerance_px + 1):
            sample_r = r + dr
            x = int(round(cx + sample_r * math.cos(theta)))
            y = int(round(cy + sample_r * math.sin(theta)))
            if 0 <= x < w and 0 <= y < h:
                if gray[y, x] <= darkness_threshold:
                    has_ink = True
                    break
        if has_ink:
            supported += 1

    return supported / num_samples


def run_arc_conflation_audit():
    canvas_size = 300
    true_center = (150.0, 150.0)
    true_radius = 40.0
    arc_angles = [15, 30, 45, 60, 90, 120, 180, 240, 300, 330, 360]

    print("=== ARC VS CIRCLE CONFLATION AUDIT ===")
    print(f"{'Arc Span':<10} | {'Arc Frac':<10} | {'Hough Candidate?':<18} | {'Center Err':<12} | {'Radius Err':<12} | {'Perimeter Support'}")
    print("-" * 88)

    for deg in arc_angles:
        img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
        # Draw arc centered at (150, 150) from 0 to deg
        cv2.ellipse(img, (int(true_center[0]), int(true_center[1])), (int(true_radius), int(true_radius)), 0, 0, deg, (0, 0, 0), 2)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        detected = extract_circles(img, min_radius=20, max_radius=60, param1=100, param2=30, min_dist=20)

        arc_frac = deg / 360.0
        hough_present = len(detected) > 0

        if hough_present:
            c = detected[0]
            center_err = math.hypot(c.center_px[0] - true_center[0], c.center_px[1] - true_center[1])
            radius_err = abs(c.radius_px - true_radius)
            support = measure_perimeter_support(gray, c.center_px[0], c.center_px[1], c.radius_px)
            c_err_str = f"{center_err:.2f} px"
            r_err_str = f"{radius_err:.2f} px"
            sup_str = f"{support*100:.1f}%"
            cand_str = f"YES ({len(detected)} circle)"
        else:
            c_err_str = "N/A"
            r_err_str = "N/A"
            # Support along ground truth
            support = measure_perimeter_support(gray, true_center[0], true_center[1], true_radius)
            sup_str = f"{support*100:.1f}% (true)"
            cand_str = "NO"

        print(f"{deg:>4} deg   | {arc_frac:<10.2f} | {cand_str:<18} | {c_err_str:<12} | {r_err_str:<12} | {sup_str}")


if __name__ == "__main__":
    run_arc_conflation_audit()
