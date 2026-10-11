"""Empirical Test: Global Thinning vs Line-Only Preprocessing on Circles and Closed Shapes.

Tests whether global skeletonization before extract_circles() degrades circle detection.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(r"C:\Users\duong\ZCodeProject\cad-agent")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from primitive_ir_lib.geometry_extraction import extract_circles, extract_lines


def morphological_skeleton(gray: np.ndarray, darkness_threshold: int = 220) -> np.ndarray:
    binary = np.where(gray <= darkness_threshold, 255, 0).astype(np.uint8)
    skel = np.zeros_like(binary)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    img = binary.copy()
    while True:
        eroded = cv2.erode(img, element)
        temp = cv2.dilate(eroded, element)
        temp = cv2.subtract(img, temp)
        skel = cv2.bitwise_or(skel, temp)
        img = eroded.copy()
        if cv2.countNonZero(img) == 0:
            break
    # Invert back to black on white for consumer
    return cv2.bitwise_not(skel)


def run_circle_comparison():
    print("=== GLOBAL THINNING VS LINE-ONLY ON CIRCLES ===")
    canvas_size = 300
    center = (150, 150)
    radius = 50

    widths = [1, 3, 5, 8, 12]
    print(f"{'Stroke W':<10} | {'Original Circles':<18} | {'Orig Radius Err':<18} | {'Thinned Circles':<18} | {'Thinned Radius Err'}")
    print("-" * 85)

    for w in widths:
        # Fixture: clean circle
        img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
        cv2.circle(img, center, radius, (0, 0, 0), w)

        # 1. Original extract_circles (grayscale Gaussian blur)
        orig_circs = extract_circles(img, min_radius=30, max_radius=80, param1=100, param2=30, min_dist=20)
        orig_count = len(orig_circs)
        orig_r_err = f"{abs(orig_circs[0].radius_px - radius):.1f}px" if orig_count > 0 else "MISSED"

        # 2. Thinned image passed to extract_circles (Global Thinning)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thinned_gray = morphological_skeleton(gray)
        thinned_bgr = cv2.cvtColor(thinned_gray, cv2.COLOR_GRAY2BGR)
        thinned_circs = extract_circles(thinned_bgr, min_radius=30, max_radius=80, param1=100, param2=30, min_dist=20)
        thinned_count = len(thinned_circs)
        thinned_r_err = f"{abs(thinned_circs[0].radius_px - radius):.1f}px" if thinned_count > 0 else "MISSED"

        print(f"{w:<10} | {orig_count:<18} | {orig_r_err:<18} | {thinned_count:<18} | {thinned_r_err}")

    # Test 2: Solid filled circle (e.g. alignment fiducial, bolt head, pin)
    img_solid = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    cv2.circle(img_solid, center, radius, (0, 0, 0), -1)

    orig_solid = extract_circles(img_solid, min_radius=30, max_radius=80, param1=100, param2=30, min_dist=20)
    gray_solid = cv2.cvtColor(img_solid, cv2.COLOR_BGR2GRAY)
    thinned_solid_gray = morphological_skeleton(gray_solid)
    thinned_solid_bgr = cv2.cvtColor(thinned_solid_gray, cv2.COLOR_GRAY2BGR)
    thinned_solid = extract_circles(thinned_solid_bgr, min_radius=30, max_radius=80, param1=100, param2=30, min_dist=20)

    print(f"\nSolid Disk (r=50):")
    print(f"  Original: detected {len(orig_solid)} circles (r={orig_solid[0].radius_px if orig_solid else 'NONE'})")
    print(f"  Thinned:  detected {len(thinned_solid)} circles (r={thinned_solid[0].radius_px if thinned_solid else 'NONE'})")


if __name__ == "__main__":
    run_circle_comparison()
