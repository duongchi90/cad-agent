"""Empirical Causal RED: Thick raster line produces duplicate Hough edge lines.

Tests CURRENT public owner: primitive_ir_lib.geometry_extraction.extract_lines()
across stroke widths (1, 2, 3, 5, 8, 10, 15 px) and angles (0, 15, 30, 45, 60, 75, 90 deg).
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
    """Perpendicular distance from pt to infinite line through p1, p2."""
    x0, y0 = pt
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    denom = math.hypot(dx, dy)
    if denom == 0:
        return math.hypot(x0 - x1, y0 - y1)
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / denom


def line_angle_deg(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Angle of line segment in degrees in [0, 180)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle = math.degrees(math.atan2(dy, dx)) % 180.0
    return angle


def create_line_fixture(
    center: tuple[float, float],
    length: float,
    angle_deg: float,
    stroke_width_px: int,
    canvas_size: int = 400,
) -> tuple[np.ndarray, tuple[float, float], tuple[float, float]]:
    """Draw a single isolated dark line (0) on white background (255)."""
    img = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    rad = math.radians(angle_deg)
    half_len = length / 2.0
    p1 = (center[0] - half_len * math.cos(rad), center[1] - half_len * math.sin(rad))
    p2 = (center[0] + half_len * math.cos(rad), center[1] + half_len * math.sin(rad))

    pt1_int = (int(round(p1[0])), int(round(p1[1])))
    pt2_int = (int(round(p2[0])), int(round(p2[1])))

    cv2.line(img, pt1_int, pt2_int, (0, 0, 0), stroke_width_px, lineType=cv2.LINE_8)
    return img, p1, p2


def analyze_extracted_lines(
    detected: list[RawLine],
    true_p1: tuple[float, float],
    true_p2: tuple[float, float],
    expected_angle_deg: float,
    stroke_width_px: int,
) -> dict[str, object]:
    """Measure offset, angle error, and whether a duplicate edge pair is present."""
    count = len(detected)
    if count == 0:
        return {
            "count": 0,
            "duplicate_pair": False,
            "max_offset": 0.0,
            "offsets": [],
            "angle_errors": [],
        }

    offsets = []
    angle_errors = []
    for line in detected:
        # Distance of midpoint to true line
        mid = ((line.p1_px[0] + line.p2_px[0]) / 2.0, (line.p1_px[1] + line.p2_px[1]) / 2.0)
        dist = point_line_distance(mid, true_p1, true_p2)
        offsets.append(dist)

        # Angle error modulo 180
        det_angle = line_angle_deg(line.p1_px, line.p2_px)
        diff = abs(det_angle - (expected_angle_deg % 180.0))
        if diff > 90.0:
            diff = 180.0 - diff
        angle_errors.append(diff)

    # Check for duplicate edge pair:
    # At least 2 lines, approximately parallel (diff < 5 deg),
    # lying on opposite sides of true centerline (offset > 0.5 px) or separation ~ stroke_width
    duplicate_pair = False
    if count >= 2:
        # Check all pairs
        for i in range(count):
            for j in range(i + 1, count):
                l1, l2 = detected[i], detected[j]
                a1 = line_angle_deg(l1.p1_px, l1.p2_px)
                a2 = line_angle_deg(l2.p1_px, l2.p2_px)
                ang_diff = abs(a1 - a2)
                if ang_diff > 90:
                    ang_diff = 180 - ang_diff
                if ang_diff < 5.0:
                    mid1 = ((l1.p1_px[0] + l1.p2_px[0]) / 2.0, (l1.p1_px[1] + l1.p2_px[1]) / 2.0)
                    mid2 = ((l2.p1_px[0] + l2.p2_px[0]) / 2.0, (l2.p1_px[1] + l2.p2_px[1]) / 2.0)
                    sep = point_line_distance(mid1, l2.p1_px, l2.p2_px)
                    # For a thick stroke, separation is ~ stroke_width (e.g. within [0.5 * W, 1.5 * W])
                    if sep >= max(1.5, 0.5 * stroke_width_px):
                        duplicate_pair = True
                        break
            if duplicate_pair:
                break

    return {
        "count": count,
        "duplicate_pair": duplicate_pair,
        "max_offset": max(offsets) if offsets else 0.0,
        "offsets": offsets,
        "angle_errors": angle_errors,
    }


def run_baseline_causal_suite():
    widths = [1, 2, 3, 5, 8, 10, 15]
    angles = [0, 15, 30, 45, 60, 75, 90]
    line_length = 200.0
    center = (200.0, 200.0)

    print("=== EMPIRICAL CAUSAL RED: THICK LINE DOUBLE-EDGE ARTIFACT SUITE ===")
    print(f"{'Width':<6} | {'Angle':<6} | {'Count':<6} | {'Duplicate Pair':<15} | {'Offsets (px)':<20} | {'Max Offset':<10} | {'Max Angle Err'}")
    print("-" * 90)

    summary = {w: {"total": 0, "duplicate": 0, "offsets": []} for w in widths}

    for w in widths:
        for a in angles:
            img, p1, p2 = create_line_fixture(center, line_length, float(a), w)
            detected = extract_lines(img, hough_threshold=40, min_line_length=30, max_line_gap=10)
            res = analyze_extracted_lines(detected, p1, p2, float(a), w)

            summary[w]["total"] += 1
            if res["duplicate_pair"]:
                summary[w]["duplicate"] += 1
            if res["offsets"]:
                summary[w]["offsets"].extend(res["offsets"])

            offset_str = ", ".join(f"{x:.1f}" for x in res["offsets"][:3])
            if len(res["offsets"]) > 3:
                offset_str += "..."
            max_ang = f"{max(res['angle_errors']):.1f} deg" if res["angle_errors"] else "N/A"
            print(f"{w:<6} | {a:<6} | {res['count']:<6} | {str(res['duplicate_pair']):<15} | {offset_str:<20} | {res['max_offset']:<10.2f} | {max_ang}")

    print("\n=== SUMMARY BY STROKE WIDTH ===")
    print(f"{'Stroke Width':<14} | {'Duplicate Rate':<16} | {'Mean Offset (px)':<18} | {'Max Offset (px)':<16} | {'Verdict'}")
    print("-" * 80)
    for w in widths:
        tot = summary[w]["total"]
        dups = summary[w]["duplicate"]
        rate = dups / tot if tot else 0.0
        offs = summary[w]["offsets"]
        mean_off = sum(offs) / len(offs) if offs else 0.0
        max_off = max(offs) if offs else 0.0
        verdict = "PASS (SINGLE)" if rate == 0 else f"FAIL (DUPLICATE EDGES {rate*100:.0f}%)"
        print(f"{w:<14} | {dups}/{tot} ({rate*100:.1f}%)    | {mean_off:<18.2f} | {max_off:<16.2f} | {verdict}")


if __name__ == "__main__":
    run_baseline_causal_suite()
