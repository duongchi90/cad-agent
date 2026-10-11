"""Hatch, Dimension, and Dashed Pattern Controls Benchmark.

Tests whether candidate normalization strategies reduce duplicate edges without:
- turning hatch into false major lines
- bridging dashed gaps incorrectly
- merging dimension-adjacent geometry
- manufacturing false continuity
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


# Strat B1: Morphological Skeleton
def extract_lines_morph(image_bgr: np.ndarray, min_line_length: int = 30) -> list[RawLine]:
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
    segments = cv2.HoughLinesP(skel, rho=1, theta=np.pi / 180, threshold=40, minLineLength=min_line_length, maxLineGap=10)
    if segments is None:
        return []
    seg = np.asarray(segments).reshape(-1, 4)
    return [RawLine(f"m_{i}", (float(x1), float(y1)), (float(x2), float(y2)), 0.9, (0, 0, 0, 0)) for i, (x1, y1, x2, y2) in enumerate(seg)]


# Strat B2: Zhang-Suen
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


def extract_lines_zs(image_bgr: np.ndarray, min_line_length: int = 30) -> list[RawLine]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    binary = np.where(gray <= 220, 1, 0).astype(np.uint8)
    thinned = zhang_suen_thinning(binary)
    segments = cv2.HoughLinesP(thinned, rho=1, theta=np.pi / 180, threshold=40, minLineLength=min_line_length, maxLineGap=10)
    if segments is None:
        return []
    seg = np.asarray(segments).reshape(-1, 4)
    return [RawLine(f"zs_{i}", (float(x1), float(y1)), (float(x2), float(y2)), 0.9, (0, 0, 0, 0)) for i, (x1, y1, x2, y2) in enumerate(seg)]


def run_hatch_and_dimension_suite():
    print("=== HATCH, DIMENSION, AND PATTERN CONTROLS ===")

    # 1. Dense Parallel Hatch (spacing 6px, stroke 1px, 10 lines)
    img_dense_hatch = np.full((300, 300, 3), 255, dtype=np.uint8)
    for i in range(10):
        y = 50 + i * 6
        cv2.line(img_dense_hatch, (50, y), (150, y), (0, 0, 0), 1)

    # 2. Sparse Hatch (spacing 15px, stroke 1px, 6 lines)
    img_sparse_hatch = np.full((300, 300, 3), 255, dtype=np.uint8)
    for i in range(6):
        y = 50 + i * 15
        cv2.line(img_sparse_hatch, (50, y), (150, y), (0, 0, 0), 1)

    # 3. Dimension Extension Line: thick feature line (5px) with thin extension lines (1px) meeting it
    img_dim = np.full((300, 300, 3), 255, dtype=np.uint8)
    # Feature line: (50, 150) -> (250, 150), width 5px
    cv2.line(img_dim, (50, 150), (250, 150), (0, 0, 0), 5)
    # Extension lines at ends: (50, 150) -> (50, 220) and (250, 150) -> (250, 220), width 1px
    cv2.line(img_dim, (50, 150), (50, 220), (0, 0, 0), 1)
    cv2.line(img_dim, (250, 150), (250, 220), (0, 0, 0), 1)
    # Dimension line: (50, 200) -> (250, 200), width 1px
    cv2.line(img_dim, (50, 200), (250, 200), (0, 0, 0), 1)

    # 4. Dashed line: 15px dash, 10px gap, total 200px (8 dashes)
    img_dashed = np.full((300, 300, 3), 255, dtype=np.uint8)
    x = 50
    while x < 250:
        cv2.line(img_dashed, (x, 150), (min(x + 15, 250), 150), (0, 0, 0), 3)
        x += 25

    fixtures = [
        ("Dense Hatch (10 lines, gap 6px)", img_dense_hatch, 10),
        ("Sparse Hatch (6 lines, gap 15px)", img_sparse_hatch, 6),
        ("Feature (5px) + Dimension (1px)", img_dim, 4), # 1 feature + 2 ext + 1 dim = 4 lines
        ("Dashed Line (3px stroke, 10px gaps)", img_dashed, 0), # Each dash is 15px (< min_line_length 30) -> should NOT bridge into 1 long line
    ]

    print(f"{'Fixture':<38} | {'Strat A (Baseline)':<20} | {'Strat B1 (Morph)':<18} | {'Strat B2 (ZS)'}")
    print("-" * 92)
    for name, img, expected in fixtures:
        lA = extract_lines(img, hough_threshold=40, min_line_length=30, max_line_gap=5)
        lB1 = extract_lines_morph(img, min_line_length=30)
        lB2 = extract_lines_zs(img, min_line_length=30)

        # For dashed line, check whether any long line (> 100px) was falsely synthesized
        if "Dashed" in name:
            longA = [l for l in lA if l.length_px() > 100]
            longB1 = [l for l in lB1 if l.length_px() > 100]
            longB2 = [l for l in lB2 if l.length_px() > 100]
            resA = f"{len(lA)} lines ({len(longA)} bridged)"
            resB1 = f"{len(lB1)} lines ({len(longB1)} bridged)"
            resB2 = f"{len(lB2)} lines ({len(longB2)} bridged)"
        else:
            resA = f"{len(lA)} lines"
            resB1 = f"{len(lB1)} lines"
            resB2 = f"{len(lB2)} lines"

        print(f"{name:<38} | {resA:<20} | {resB1:<18} | {resB2}")


if __name__ == "__main__":
    run_hatch_and_dimension_suite()
