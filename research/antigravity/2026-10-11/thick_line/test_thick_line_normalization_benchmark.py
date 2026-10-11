"""Benchmark candidate normalization strategies for thick lines.

Strategies:
A. CURRENT: Gaussian -> Canny -> HoughLinesP
B1. MORPHOLOGICAL_SKELETON: Binarize -> Morphological skeleton -> HoughLinesP
B2. ZHANG_SUEN_THINNING (RESEARCH_ONLY_REFERENCE_IMPLEMENTATION) -> HoughLinesP
C. EDGE_PAIR_CENTER_COLLAPSE: Current Hough -> parallel pair detection -> intermediate ink check -> midpoint collapse
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


def create_line_fixture(
    center: tuple[float, float],
    length: float,
    angle_deg: float,
    stroke_width_px: int,
    canvas_size: int = 400,
) -> tuple[np.ndarray, tuple[float, float], tuple[float, float]]:
    img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    rad = math.radians(angle_deg)
    half_len = length / 2.0
    p1 = (center[0] - half_len * math.cos(rad), center[1] - half_len * math.sin(rad))
    p2 = (center[0] + half_len * math.cos(rad), center[1] + half_len * math.sin(rad))
    cv2.line(img, (int(round(p1[0])), int(round(p1[1]))), (int(round(p2[0])), int(round(p2[1]))), (0, 0, 0), stroke_width_px)
    return img, p1, p2


# --- Strategy B1: Morphological Skeleton (Standard OpenCV) ---
def morphological_skeleton(gray: np.ndarray, darkness_threshold: int = 220) -> np.ndarray:
    # Invert: dark ink becomes 255, background paper becomes 0
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


def extract_lines_morphological_skeleton(
    image_bgr: np.ndarray,
    hough_threshold: int = 40,
    min_line_length: int = 30,
    max_line_gap: int = 10,
) -> list[RawLine]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    skel = morphological_skeleton(gray)
    segments = cv2.HoughLinesP(
        skel, rho=1, theta=np.pi / 180, threshold=hough_threshold,
        minLineLength=min_line_length, maxLineGap=max_line_gap,
    )
    raw_lines: list[RawLine] = []
    if segments is None:
        return raw_lines
    seg = np.asarray(segments).reshape(-1, 4)
    for i, (x1, y1, x2, y2) in enumerate(seg):
        raw_lines.append(
            RawLine(
                id=f"skel_{i}",
                p1_px=(float(x1), float(y1)),
                p2_px=(float(x2), float(y2)),
                confidence=0.9,
                bbox_px=(float(min(x1, x2)), float(min(y1, y2)), float(max(x1, x2)), float(max(y1, y2))),
            )
        )
    return raw_lines


# --- Strategy B2: Zhang-Suen Thinning (RESEARCH_ONLY_REFERENCE_IMPLEMENTATION) ---
def zhang_suen_thinning(binary_ink: np.ndarray) -> np.ndarray:
    """Vectorized / structured Zhang-Suen thinning (0=background, 1=ink)."""
    # Pad image to simplify boundary condition
    padded = np.pad((binary_ink > 0).astype(np.uint8), 1, mode='constant', constant_values=0)
    changed = True
    while changed:
        changed = False
        for step in (1, 2):
            p2 = padded[:-2, 1:-1]
            p3 = padded[:-2, 2:]
            p4 = padded[1:-1, 2:]
            p5 = padded[2:, 2:]
            p6 = padded[2:, 1:-1]
            p7 = padded[2:, :-2]
            p8 = padded[1:-1, :-2]
            p9 = padded[:-2, :-2]
            p1 = padded[1:-1, 1:-1]

            # Condition 1: 2 <= B(P1) <= 6
            b = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            c1 = (b >= 2) & (b <= 6)

            # Condition 2: A(P1) == 1 (0 -> 1 transitions in order p2,p3,...,p9,p2)
            neighbors = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            a = np.zeros_like(p1, dtype=np.uint8)
            for k in range(8):
                a += ((neighbors[k] == 0) & (neighbors[k+1] == 1)).astype(np.uint8)
            c2 = (a == 1)

            if step == 1:
                c3 = (p2 * p4 * p6 == 0)
                c4 = (p4 * p6 * p8 == 0)
            else:
                c3 = (p2 * p4 * p8 == 0)
                c4 = (p2 * p6 * p8 == 0)

            to_remove = (p1 == 1) & c1 & c2 & c3 & c4
            if np.any(to_remove):
                padded[1:-1, 1:-1][to_remove] = 0
                changed = True

    return (padded[1:-1, 1:-1] * 255).astype(np.uint8)


def extract_lines_zhang_suen(
    image_bgr: np.ndarray,
    hough_threshold: int = 40,
    min_line_length: int = 30,
    max_line_gap: int = 10,
) -> list[RawLine]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    binary = np.where(gray <= 220, 1, 0).astype(np.uint8)
    thinned = zhang_suen_thinning(binary)
    segments = cv2.HoughLinesP(
        thinned, rho=1, theta=np.pi / 180, threshold=hough_threshold,
        minLineLength=min_line_length, maxLineGap=max_line_gap,
    )
    raw_lines: list[RawLine] = []
    if segments is None:
        return raw_lines
    seg = np.asarray(segments).reshape(-1, 4)
    for i, (x1, y1, x2, y2) in enumerate(seg):
        raw_lines.append(
            RawLine(
                id=f"zs_{i}",
                p1_px=(float(x1), float(y1)),
                p2_px=(float(x2), float(y2)),
                confidence=0.9,
                bbox_px=(float(min(x1, x2)), float(min(y1, y2)), float(max(x1, x2)), float(max(y1, y2))),
            )
        )
    return raw_lines


# --- Strategy C: Edge Pair Center Collapse (Post-Hough Geometric Pairing) ---
def project_point_onto_line(pt: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float]) -> tuple[float, float]:
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    denom = dx * dx + dy * dy
    if denom == 0:
        return p1
    t = ((pt[0] - p1[0]) * dx + (pt[1] - p1[1]) * dy) / denom
    return (p1[0] + t * dx, p1[1] + t * dy)


def check_intermediate_ink(
    gray: np.ndarray,
    mid_p1: tuple[float, float],
    mid_p2: tuple[float, float],
    darkness_threshold: int = 220,
    min_ink_fraction: float = 0.70,
) -> bool:
    count = max(int(round(math.hypot(mid_p2[0] - mid_p1[0], mid_p2[1] - mid_p1[1]))), 1) + 1
    xs = np.rint(np.linspace(mid_p1[0], mid_p2[0], count)).astype(np.int32)
    ys = np.rint(np.linspace(mid_p1[1], mid_p2[1], count)).astype(np.int32)
    h, w = gray.shape
    valid = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    if not np.any(valid):
        return False
    samples = gray[ys[valid], xs[valid]]
    ink_fraction = float(np.mean(samples <= darkness_threshold))
    return ink_fraction >= min_ink_fraction


def collapse_parallel_edge_pairs(
    raw_lines: list[RawLine],
    image_bgr: np.ndarray,
    max_angle_diff_deg: float = 3.0,
    min_separation_px: float = 1.5,
    max_separation_px: float = 20.0,
) -> list[RawLine]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    used = set()
    collapsed: list[RawLine] = []

    # Sort lines by length descending
    sorted_lines = sorted(raw_lines, key=lambda l: l.length_px(), reverse=True)
    n = len(sorted_lines)

    for i in range(n):
        if i in used:
            continue
        l1 = sorted_lines[i]
        a1 = line_angle_deg(l1.p1_px, l1.p2_px)
        best_partner = None
        best_sep = None

        for j in range(i + 1, n):
            if j in used:
                continue
            l2 = sorted_lines[j]
            a2 = line_angle_deg(l2.p1_px, l2.p2_px)
            ang_diff = abs(a1 - a2)
            if ang_diff > 90:
                ang_diff = 180 - ang_diff
            if ang_diff > max_angle_diff_deg:
                continue

            # Perpendicular separation
            mid2 = ((l2.p1_px[0] + l2.p2_px[0]) / 2.0, (l2.p1_px[1] + l2.p2_px[1]) / 2.0)
            sep = point_line_distance(mid2, l1.p1_px, l1.p2_px)
            if not (min_separation_px <= sep <= max_separation_px):
                continue

            # Check longitudinal overlap
            # Project l2 endpoints onto l1
            proj2_start = project_point_onto_line(l2.p1_px, l1.p1_px, l1.p2_px)
            proj2_end = project_point_onto_line(l2.p2_px, l1.p1_px, l1.p2_px)
            mid_start = ((l1.p1_px[0] + proj2_start[0]) / 2.0, (l1.p1_px[1] + proj2_start[1]) / 2.0)
            mid_end = ((l1.p2_px[0] + proj2_end[0]) / 2.0, (l1.p2_px[1] + proj2_end[1]) / 2.0)

            # Check if intermediate region has dark ink (confirming single stroke)
            if check_intermediate_ink(gray, mid_start, mid_end):
                best_partner = (j, mid_start, mid_end)
                best_sep = sep
                break

        if best_partner is not None:
            j, mid_start, mid_end = best_partner
            used.add(i)
            used.add(j)
            collapsed.append(
                RawLine(
                    id=f"collapsed_{l1.id}_{sorted_lines[j].id}",
                    p1_px=mid_start,
                    p2_px=mid_end,
                    confidence=max(l1.confidence, sorted_lines[j].confidence),
                    bbox_px=(
                        min(mid_start[0], mid_end[0]), min(mid_start[1], mid_end[1]),
                        max(mid_start[0], mid_end[0]), max(mid_start[1], mid_end[1]),
                    ),
                )
            )
        else:
            used.add(i)
            collapsed.append(l1)

    return collapsed


def evaluate_strategy(name: str, extract_fn, widths: list[int], angles: list[int]):
    center = (200.0, 200.0)
    line_len = 200.0
    total_cases = 0
    single_line_cases = 0
    duplicate_cases = 0
    total_offset = 0.0
    max_offset = 0.0

    for w in widths:
        for a in angles:
            total_cases += 1
            img, p1, p2 = create_line_fixture(center, line_len, float(a), w)
            lines = extract_fn(img)
            count = len(lines)
            if count == 1:
                single_line_cases += 1
                off = point_line_distance(
                    ((lines[0].p1_px[0] + lines[0].p2_px[0]) / 2.0, (lines[0].p1_px[1] + lines[0].p2_px[1]) / 2.0),
                    p1, p2,
                )
                total_offset += off
                max_offset = max(max_offset, off)
            elif count >= 2:
                duplicate_cases += 1
                for l in lines:
                    off = point_line_distance(
                        ((l.p1_px[0] + l.p2_px[0]) / 2.0, (l.p1_px[1] + l.p2_px[1]) / 2.0),
                        p1, p2,
                    )
                    total_offset += off
                    max_offset = max(max_offset, off)

    mean_off = total_offset / max(1, (single_line_cases + duplicate_cases * 2))
    return {
        "name": name,
        "single_line_rate": single_line_cases / total_cases,
        "duplicate_rate": duplicate_cases / total_cases,
        "mean_offset": mean_off,
        "max_offset": max_offset,
    }


def main():
    widths = [1, 2, 3, 5, 8, 10, 15]
    angles = [0, 15, 30, 45, 60, 75, 90]
    print("=== NORMALIZATION STRATEGIES BENCHMARK (ISOLATED LINES) ===")

    strategies = [
        ("A. CURRENT (Canny + Hough)", lambda img: extract_lines(img, hough_threshold=40, min_line_length=30, max_line_gap=10)),
        ("B1. MORPH_SKELETON (OpenCV standard)", lambda img: extract_lines_morphological_skeleton(img, hough_threshold=40, min_line_length=30, max_line_gap=10)),
        ("B2. ZHANG_SUEN (Research ref)", lambda img: extract_lines_zhang_suen(img, hough_threshold=40, min_line_length=30, max_line_gap=10)),
        ("C. EDGE_PAIR_COLLAPSE (Post-Hough)", lambda img: collapse_parallel_edge_pairs(extract_lines(img, hough_threshold=40, min_line_length=30, max_line_gap=10), img)),
    ]

    print(f"\n{'Strategy':<38} | {'Single Line':<12} | {'Duplicate Rate':<15} | {'Mean Offset':<12} | {'Max Offset'}")
    print("-" * 92)
    for name, fn in strategies:
        res = evaluate_strategy(name, fn, widths, angles)
        print(f"{res['name']:<38} | {res['single_line_rate']*100:<10.1f}% | {res['duplicate_rate']*100:<13.1f}% | {res['mean_offset']:<10.2f}px | {res['max_offset']:<8.2f}px")


if __name__ == "__main__":
    main()
