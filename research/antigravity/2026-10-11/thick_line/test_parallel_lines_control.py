"""Negative Controls: Two Real Parallel Lines.

Tests whether candidate normalization strategies improperly merge two genuinely distinct
parallel lines separated by distances D in {2, 3, 5, 8, 12, 20} px.
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


def point_line_distance(pt: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float]) -> float:
    x0, y0 = pt
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    denom = math.hypot(dx, dy)
    if denom == 0:
        return math.hypot(x0 - x1, y0 - y1)
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / denom


def line_angle_deg(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    return math.degrees(math.atan2(dy, dx)) % 180.0


def create_parallel_lines_fixture(
    separation_px: int,
    stroke_width_px: int = 1,
    length: float = 150.0,
    canvas_size: int = 300,
) -> tuple[np.ndarray, list[tuple[tuple[float, float], tuple[float, float]]]]:
    img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    y_center = canvas_size / 2.0
    half_sep = separation_px / 2.0
    x1 = (canvas_size - length) / 2.0
    x2 = x1 + length

    y_line1 = y_center - half_sep
    y_line2 = y_center + half_sep

    # Draw two black lines
    cv2.line(img, (int(round(x1)), int(round(y_line1))), (int(round(x2)), int(round(y_line1))), (0, 0, 0), stroke_width_px)
    cv2.line(img, (int(round(x1)), int(round(y_line2))), (int(round(x2)), int(round(y_line2))), (0, 0, 0), stroke_width_px)

    true_lines = [
        ((x1, y_line1), (x2, y_line1)),
        ((x1, y_line2), (x2, y_line2)),
    ]
    return img, true_lines


# Candidate B1
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
    return skel


def extract_lines_morph(image_bgr: np.ndarray) -> list[RawLine]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    skel = morphological_skeleton(gray)
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


# Candidate C: Edge Pair Collapse
def check_intermediate_ink(gray: np.ndarray, p1: tuple[float, float], p2: tuple[float, float]) -> bool:
    count = max(int(round(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))), 1) + 1
    xs = np.rint(np.linspace(p1[0], p2[0], count)).astype(np.int32)
    ys = np.rint(np.linspace(p1[1], p2[1], count)).astype(np.int32)
    h, w = gray.shape
    valid = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    if not np.any(valid):
        return False
    return float(np.mean(gray[ys[valid], xs[valid]] <= 220)) >= 0.70


def extract_lines_collapse(image_bgr: np.ndarray) -> list[RawLine]:
    raw_lines = extract_lines(image_bgr, hough_threshold=40, min_line_length=30, max_line_gap=10)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    used = set()
    collapsed = []
    n = len(raw_lines)
    for i in range(n):
        if i in used:
            continue
        l1 = raw_lines[i]
        a1 = line_angle_deg(l1.p1_px, l1.p2_px)
        partner = None
        for j in range(i + 1, n):
            if j in used:
                continue
            l2 = raw_lines[j]
            a2 = line_angle_deg(l2.p1_px, l2.p2_px)
            diff = abs(a1 - a2)
            if diff > 90: diff = 180 - diff
            if diff > 3.0: continue
            mid2 = ((l2.p1_px[0] + l2.p2_px[0]) / 2.0, (l2.p1_px[1] + l2.p2_px[1]) / 2.0)
            sep = point_line_distance(mid2, l1.p1_px, l1.p2_px)
            if not (1.5 <= sep <= 20.0): continue
            mid_start = ((l1.p1_px[0] + l2.p1_px[0]) / 2.0, (l1.p1_px[1] + l2.p1_px[1]) / 2.0)
            mid_end = ((l1.p2_px[0] + l2.p2_px[0]) / 2.0, (l1.p2_px[1] + l2.p2_px[1]) / 2.0)
            if check_intermediate_ink(gray, mid_start, mid_end):
                partner = j
                collapsed.append(RawLine(f"c_{i}_{j}", mid_start, mid_end, 0.9, (0, 0, 0, 0)))
                break
        if partner is not None:
            used.add(i)
            used.add(partner)
        else:
            used.add(i)
            collapsed.append(l1)
    return collapsed


def test_parallel_suite():
    separations = [2, 3, 5, 8, 12, 20]
    widths = [1, 3]

    print("=== NEGATIVE CONTROL: TWO REAL PARALLEL LINES ===")
    print(f"{'Sep (px)':<10} | {'Stroke W':<10} | {'Strat A (Count)':<16} | {'Strat B1 Morph':<16} | {'Strat B2 ZS':<16} | {'Strat C Collapse'}")
    print("-" * 88)

    for w in widths:
        for s in separations:
            img, true_lines = create_parallel_lines_fixture(s, stroke_width_px=w)
            lines_a = extract_lines(img, hough_threshold=40, min_line_length=30, max_line_gap=10)
            lines_b1 = extract_lines_morph(img)
            lines_b2 = extract_lines_zs(img)
            lines_c = extract_lines_collapse(img)

            cA = len(lines_a)
            cB1 = len(lines_b1)
            cB2 = len(lines_b2)
            cC = len(lines_c)

            # Check if any strategy falsely merged 2 lines into 1
            merge_b1 = "MERGED(1!)" if cB1 == 1 else f"{cB1} lines"
            merge_b2 = "MERGED(1!)" if cB2 == 1 else f"{cB2} lines"
            merge_c = "MERGED(1!)" if cC == 1 else f"{cC} lines"

            print(f"{s:<10} | {w:<10} | {cA:<16} | {merge_b1:<16} | {merge_b2:<16} | {merge_c}")


if __name__ == "__main__":
    test_parallel_suite()
