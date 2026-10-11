"""Circle and Closed Contour Interaction with Line Normalization.

Tests thin circle, thick circle, circle + tangent line, circle + crossing line, rounded rectangle.
Measures:
- FALSE_LINE_COUNT (chords falsely extracted from circles by line extractor)
- False chord geometry
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

from primitive_ir_lib.geometry_extraction import extract_lines, RawLine


# Strat B2: Zhang-Suen Thinning
def zhang_suen_thinning(binary_ink: np.ndarray) -> np.ndarray:
    padded = np.pad((binary_ink > 0).astype(np.uint8), 1, mode='constant', constant_values=0)
    changed = True
    while changed:
        changed = False
        for step in (1, 2):
            p2 = padded[:-2, 1:-1]; p3 = padded[:-2, 2:]; p4 = padded[1:-1, 2:]; p5 = padded[2:, 2:]
            p6 = padded[2:, 1:-1]; p7 = padded[2:, :-2]; p8 = padded[1:-1, :-2]; p9 = padded[:-2, :-2]
            p1 = padded[1:-1, 1:-1]
            b = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            c1 = (b >= 2) & (b <= 6)
            neighbors = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            a = np.zeros_like(p1, dtype=np.uint8)
            for k in range(8):
                a += ((neighbors[k] == 0) & (neighbors[k+1] == 1)).astype(np.uint8)
            c2 = (a == 1)
            c3 = (p2 * p4 * p6 == 0) if step == 1 else (p2 * p4 * p8 == 0)
            c4 = (p4 * p6 * p8 == 0) if step == 1 else (p2 * p6 * p8 == 0)
            to_remove = (p1 == 1) & c1 & c2 & c3 & c4
            if np.any(to_remove):
                padded[1:-1, 1:-1][to_remove] = 0
                changed = True
    return (padded[1:-1, 1:-1] * 255).astype(np.uint8)


def extract_lines_zs(image_bgr: np.ndarray) -> list[RawLine]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    binary = np.where(gray <= 220, 1, 0).astype(np.uint8)
    thinned = zhang_suen_thinning(binary)
    segments = cv2.HoughLinesP(thinned, rho=1, theta=np.pi / 180, threshold=40, minLineLength=30, maxLineGap=10)
    if segments is None:
        return []
    seg = np.asarray(segments).reshape(-1, 4)
    return [RawLine(f"zs_{i}", (float(x1), float(y1)), (float(x2), float(y2)), 0.9, (0, 0, 0, 0)) for i, (x1, y1, x2, y2) in enumerate(seg)]


def run_circle_interaction_suite():
    print("=== CIRCLE & CLOSED CONTOUR INTERACTION ===")
    canvas_size = 300
    center = (150, 150)
    radius = 50

    # 1. Thin Circle (1px)
    img_thin_circ = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    cv2.circle(img_thin_circ, center, radius, (0, 0, 0), 1)

    # 2. Thick Circle (5px)
    img_thick_circ = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    cv2.circle(img_thick_circ, center, radius, (0, 0, 0), 5)

    # 3. Circle + Tangent Line (1 true line expected)
    img_tangent = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    cv2.circle(img_tangent, center, radius, (0, 0, 0), 3)
    cv2.line(img_tangent, (50, 100), (250, 100), (0, 0, 0), 3) # tangent at top (y = 150 - 50 = 100)

    # 4. Circle + Crossing Line (1 true line through center)
    img_crossing = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    cv2.circle(img_crossing, center, radius, (0, 0, 0), 3)
    cv2.line(img_crossing, (50, 150), (250, 150), (0, 0, 0), 3)

    # 5. Rounded Rectangle
    img_round_rect = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    # 4 flat segments + rounded corners
    cv2.line(img_round_rect, (90, 80), (210, 80), (0, 0, 0), 3)
    cv2.line(img_round_rect, (90, 220), (210, 220), (0, 0, 0), 3)
    cv2.line(img_round_rect, (80, 90), (80, 210), (0, 0, 0), 3)
    cv2.line(img_round_rect, (220, 90), (220, 210), (0, 0, 0), 3)
    cv2.ellipse(img_round_rect, (90, 90), (10, 10), 0, 180, 270, (0, 0, 0), 3)
    cv2.ellipse(img_round_rect, (210, 90), (10, 10), 0, 270, 360, (0, 0, 0), 3)
    cv2.ellipse(img_round_rect, (210, 210), (10, 10), 0, 0, 90, (0, 0, 0), 3)
    cv2.ellipse(img_round_rect, (90, 210), (10, 10), 0, 90, 180, (0, 0, 0), 3)

    fixtures = [
        ("Isolated Thin Circle (r=50, w=1)", img_thin_circ, 0),
        ("Isolated Thick Circle (r=50, w=5)", img_thick_circ, 0),
        ("Circle + Tangent Line (w=3)", img_tangent, 1),
        ("Circle + Crossing Line (w=3)", img_crossing, 1),
        ("Rounded Rectangle (w=3)", img_round_rect, 4),
    ]

    print(f"{'Fixture':<36} | {'Expected Lines':<16} | {'Strat A (Baseline)':<20} | {'Strat B2 (Thinned)'}")
    print("-" * 88)
    for name, img, exp in fixtures:
        lA = extract_lines(img, hough_threshold=40, min_line_length=30, max_line_gap=10)
        lB2 = extract_lines_zs(img)
        print(f"{name:<36} | {exp:<16} | {len(lA):<20} | {len(lB2)}")


if __name__ == "__main__":
    run_circle_interaction_suite()
