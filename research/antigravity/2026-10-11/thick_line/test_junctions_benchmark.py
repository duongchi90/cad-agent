"""Negative Controls: Junctions and Topological Features.

Tests T-junction, L-corner, X-crossing, Rectangle, Open Polyline, Three Parallel Lines
across stroke widths 1, 3, 5, 10 px under Candidate Strategies B1 (Morph), B2 (Zhang-Suen), and C (Collapse).
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


def create_t_junction(width: int, canvas_size: int = 300) -> np.ndarray:
    img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    # Horizontal bar: (50, 150) -> (250, 150)
    cv2.line(img, (50, 150), (250, 150), (0, 0, 0), width)
    # Vertical stem: (150, 150) -> (150, 250)
    cv2.line(img, (150, 150), (150, 250), (0, 0, 0), width)
    return img


def create_l_corner(width: int, canvas_size: int = 300) -> np.ndarray:
    img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    # Horizontal: (50, 150) -> (150, 150)
    cv2.line(img, (50, 150), (150, 150), (0, 0, 0), width)
    # Vertical: (150, 150) -> (150, 250)
    cv2.line(img, (150, 150), (150, 250), (0, 0, 0), width)
    return img


def create_x_crossing(width: int, canvas_size: int = 300) -> np.ndarray:
    img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    # Horizontal: (50, 150) -> (250, 150)
    cv2.line(img, (50, 150), (250, 150), (0, 0, 0), width)
    # Vertical: (150, 50) -> (150, 250)
    cv2.line(img, (150, 50), (150, 250), (0, 0, 0), width)
    return img


def create_rectangle(width: int, canvas_size: int = 300) -> np.ndarray:
    img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    cv2.rectangle(img, (80, 80), (220, 220), (0, 0, 0), width)
    return img


def create_polyline(width: int, canvas_size: int = 300) -> np.ndarray:
    img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    pts = np.array([[50, 100], [150, 100], [200, 200], [250, 150]], np.int32)
    cv2.polylines(img, [pts], isClosed=False, color=(0, 0, 0), thickness=width)
    return img


def create_three_parallel(width: int, separation: int = 15, canvas_size: int = 300) -> np.ndarray:
    img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    for dy in (-separation, 0, separation):
        y = 150 + dy
        cv2.line(img, (50, y), (250, y), (0, 0, 0), width)
    return img


# Candidate B1 (Morphological Skeleton)
def extract_lines_morph(image_bgr: np.ndarray) -> list[RawLine]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    binary = np.where(gray <= 220, 255, 0).astype(np.uint8)
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
    segments = cv2.HoughLinesP(skel, rho=1, theta=np.pi / 180, threshold=40, minLineLength=30, maxLineGap=10)
    if segments is None:
        return []
    seg = np.asarray(segments).reshape(-1, 4)
    return [RawLine(f"m_{i}", (float(x1), float(y1)), (float(x2), float(y2)), 0.9, (0, 0, 0, 0)) for i, (x1, y1, x2, y2) in enumerate(seg)]


# Candidate B2: Zhang-Suen
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


def run_junction_suite():
    widths = [1, 3, 5, 10]
    fixtures = [
        ("T-Junction (expected 2 lines)", create_t_junction, 2),
        ("L-Corner (expected 2 lines)", create_l_corner, 2),
        ("X-Crossing (expected 2 lines)", create_x_crossing, 2),
        ("Rectangle (expected 4 lines)", create_rectangle, 4),
        ("Polyline (expected 3 lines)", create_polyline, 3),
        ("3-Parallel (expected 3 lines)", lambda w: create_three_parallel(w, 20), 3),
    ]

    print("=== JUNCTION & TOPOLOGY CONTROLS ===")
    print(f"{'Fixture':<32} | {'Width':<6} | {'Expected':<8} | {'Strat A':<10} | {'Strat B1 (Morph)':<18} | {'Strat B2 (ZS)'}")
    print("-" * 95)

    for name, factory, expected in fixtures:
        for w in widths:
            img = factory(w)
            lines_a = extract_lines(img, hough_threshold=40, min_line_length=30, max_line_gap=10)
            lines_b1 = extract_lines_morph(img)
            lines_b2 = extract_lines_zs(img)

            cA = len(lines_a)
            cB1 = len(lines_b1)
            cB2 = len(lines_b2)

            print(f"{name:<32} | {w:<6} | {expected:<8} | {cA:<10} | {cB1:<18} | {cB2}")


if __name__ == "__main__":
    run_junction_suite()
