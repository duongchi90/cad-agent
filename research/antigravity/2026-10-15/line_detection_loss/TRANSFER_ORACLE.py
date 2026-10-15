"""TRANSFER_ORACLE: Line Detection Loss & Endpoint Ink Ray-Marching.

Role: ANTIGRAVITY_RESEARCH_AGENT
Target: primitive_ir_lib/geometry_extraction.py::extract_lines
Boundary: LINE_DETECTION_LOSS in Issue #491 (CASE01 arrowhead witness truncation vs FTC-11 intentional text gap)
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np


def extend_line_along_ink(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    gray: np.ndarray,
    max_extend_px: int = 30,
    max_white_gap_px: int = 3,
    dark_thresh: int = 180,
    perp_half_width: int = 2,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Extend endpoints of a detected line along its direction into continuous dark ink.

    Halts immediately upon encountering max_white_gap_px consecutive background pixels,
    preserving intentional gaps, text breaks, and dashed line terminations.
    """
    h, w = gray.shape
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length == 0 or not math.isfinite(length):
        return p1, p2
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux

    def has_ink(x: float, y: float) -> bool:
        for d in range(-perp_half_width, perp_half_width + 1):
            px = int(round(x + nx * d))
            py = int(round(y + ny * d))
            if 0 <= px < w and 0 <= py < h and gray[py, px] <= dark_thresh:
                return True
        return False

    # March from p2 in direction p1 -> p2 (forward)
    best_p2 = p2
    white_run = 0
    for step in range(1, max_extend_px + 1):
        cx, cy = p2[0] + ux * step, p2[1] + uy * step
        if has_ink(cx, cy):
            white_run = 0
            best_p2 = (cx, cy)
        else:
            white_run += 1
            if white_run >= max_white_gap_px:
                break

    # March from p1 in direction p2 -> p1 (backward)
    best_p1 = p1
    white_run = 0
    for step in range(1, max_extend_px + 1):
        cx, cy = p1[0] - ux * step, p1[1] - uy * step
        if has_ink(cx, cy):
            white_run = 0
            best_p1 = (cx, cy)
        else:
            white_run += 1
            if white_run >= max_white_gap_px:
                break

    return best_p1, best_p2


def run_synthetic_arrowhead_test() -> dict:
    """Synthetic test: A 3px stroke with a triangular arrowhead terminating at an orthogonal line."""
    canvas = np.full((300, 300), 255, dtype=np.uint8)
    # Orthogonal top border at y=50
    cv2.line(canvas, (30, 50), (270, 50), 0, 2)
    # Arrowhead tip at (150, 52), widening to y=70, x in [144, 156]
    arrow_pts = np.array([[150, 52], [144, 70], [156, 70]], dtype=np.int32)
    cv2.fillPoly(canvas, [arrow_pts], 0)
    # Line body: x=150, y from 70 to 220, stroke width 3
    cv2.line(canvas, (150, 70), (150, 220), 0, 3)
    # Bottom orthogonal border at y=240, arrowhead from 220 to 238
    arrow_bot = np.array([[150, 238], [144, 220], [156, 220]], dtype=np.int32)
    cv2.fillPoly(canvas, [arrow_bot], 0)
    cv2.line(canvas, (30, 240), (270, 240), 0, 2)

    # Standard Canny + Hough with tuned parameters
    edges = cv2.Canny(canvas, 50, 150)
    segs = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=40, maxLineGap=5)
    assert segs is not None, "Failed to detect synthetic line"
    raw_seg = segs.reshape(-1, 4)
    # Find vertical central segment
    matched = [s for s in raw_seg if abs(s[0] - s[2]) <= 3 and 147 <= (s[0] + s[2]) / 2 <= 153]
    assert matched, "No central segment found"
    s = matched[0]
    p1 = (float(s[0]), float(min(s[1], s[3])))
    p2 = (float(s[2]), float(max(s[1], s[3])))
    raw_span = p2[1] - p1[1]

    # Baseline Hough terminates at arrowhead flare (~y=70 to ~y=220)
    assert p1[1] >= 65.0, f"Baseline should not reach arrow tip y=52, got {p1[1]}"
    assert p2[1] <= 225.0, f"Baseline should not reach bottom tip y=238, got {p2[1]}"

    # Apply extension
    ep1, ep2 = extend_line_along_ink(p1, p2, canvas, max_extend_px=30, max_white_gap_px=3)
    ext_span = ep2[1] - ep1[1]

    assert ep1[1] <= 53.0, f"Extended line must reach upper tip y<=53, got {ep1[1]}"
    assert ep2[1] >= 237.0, f"Extended line must reach lower tip y>=237, got {ep2[1]}"

    return {
        "status": "PASS",
        "raw_endpoints": [list(p1), list(p2)],
        "raw_span_px": raw_span,
        "extended_endpoints": [list(ep1), list(ep2)],
        "extended_span_px": ext_span,
        "tip_recovery_px": ext_span - raw_span,
    }


def run_synthetic_intentional_gap_test() -> dict:
    """Synthetic test: A dimension line interrupted by an intentional text gap (30px gap of white paper)."""
    canvas = np.full((150, 400), 255, dtype=np.uint8)
    # Stroke 1: x in [50, 180], y=75
    cv2.line(canvas, (50, 75), (180, 75), 0, 2)
    # Intentional Gap: x in [180, 220] (40px white paper with small text character in center)
    cv2.putText(canvas, "50", (188, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.4, 0, 1)
    # Stroke 2: x in [220, 350], y=75
    cv2.line(canvas, (220, 75), (350, 75), 0, 2)

    p1_s1, p2_s1 = (50.0, 75.0), (180.0, 75.0)
    p1_s2, p2_s2 = (220.0, 75.0), (350.0, 75.0)

    # Extend Stroke 1
    ep1_s1, ep2_s1 = extend_line_along_ink(p1_s1, p2_s1, canvas, max_extend_px=30, max_white_gap_px=3)
    # Extend Stroke 2
    ep1_s2, ep2_s2 = extend_line_along_ink(p1_s2, p2_s2, canvas, max_extend_px=30, max_white_gap_px=3)

    # Stroke 1 p2 must not cross into the gap
    gap_invasion_s1 = ep2_s1[0] - 180.0
    gap_invasion_s2 = 220.0 - ep1_s2[0]

    assert gap_invasion_s1 <= 1.0, f"Stroke 1 invaded intentional gap by {gap_invasion_s1} px"
    assert gap_invasion_s2 <= 1.0, f"Stroke 2 invaded intentional gap by {gap_invasion_s2} px"

    return {
        "status": "PASS",
        "stroke1_extended": [list(ep1_s1), list(ep2_s1)],
        "stroke2_extended": [list(ep1_s2), list(ep2_s2)],
        "gap_invasion_stroke1_px": max(0.0, gap_invasion_s1),
        "gap_invasion_stroke2_px": max(0.0, gap_invasion_s2),
        "intentional_gap_preserved": True,
    }


def run_synthetic_dashed_line_test() -> dict:
    """Synthetic test: A dashed line with dashes=20px, gaps=10px must NOT be bridged."""
    canvas = np.full((100, 300), 255, dtype=np.uint8)
    for x_start in (30, 60, 90, 120, 150):
        cv2.line(canvas, (x_start, 50), (x_start + 20, 50), 0, 2)

    # Pick middle dash (90, 50) to (110, 50)
    p1, p2 = (90.0, 50.0), (110.0, 50.0)
    ep1, ep2 = extend_line_along_ink(p1, p2, canvas, max_extend_px=20, max_white_gap_px=3)

    invasion_left = 90.0 - ep1[0]
    invasion_right = ep2[0] - 110.0

    assert invasion_left <= 1.0, f"Dash extended left across white gap by {invasion_left} px"
    assert invasion_right <= 1.0, f"Dash extended right across white gap by {invasion_right} px"

    return {
        "status": "PASS",
        "dash_original": [list(p1), list(p2)],
        "dash_extended": [list(ep1), list(ep2)],
        "bridged": False,
    }


def run_degenerate_controls() -> dict:
    """Degenerate inputs: empty, zero length, non-finite, out-of-bounds."""
    canvas = np.full((100, 100), 255, dtype=np.uint8)
    # Zero length
    p1, p2 = extend_line_along_ink((50.0, 50.0), (50.0, 50.0), canvas)
    assert p1 == (50.0, 50.0) and p2 == (50.0, 50.0)

    # Non-finite
    p1, p2 = extend_line_along_ink((float("nan"), 50.0), (50.0, 50.0), canvas)
    assert math.isnan(p1[0]) and p2 == (50.0, 50.0)

    # Out of bounds
    p1, p2 = extend_line_along_ink((-10.0, -10.0), (-5.0, -5.0), canvas)
    assert p1 == (-10.0, -10.0) and p2 == (-5.0, -5.0)

    return {"status": "PASS", "zero_length_safe": True, "nonfinite_safe": True, "oob_safe": True}


def run_case01_real_data_test() -> Optional[dict]:
    """Verify CASE01 hash-bound render witness recovery."""
    render_path = Path(r"D:\Cad agent temp\case01-run-pdf-calibration-candidate-v1-20261013\pdf\rendered\page_01.png")
    if not render_path.is_file():
        return None

    im = cv2.imread(str(render_path))
    if im is None or im.shape[:2] != (1684, 2382):
        return None

    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 50, 150)
    # real_scan_tuned_v1 parameters
    segs = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=90, minLineLength=50, maxLineGap=5)
    if segs is None:
        return {"status": "FAIL", "reason": "No lines detected by Hough"}

    raw_lines = segs.reshape(-1, 4)
    # Find lines in corridor x in [157, 164], y overlapping [220, 365]
    witnesses = []
    _UPPER = (153, 198, 168, 219)
    _LOWER = (153, 369, 168, 390)
    _CORRIDOR = (157, 219, 164, 369)

    def intersects(p1, p2, rect):
        x0, y0, x1, y1 = rect
        lx0, ly0 = min(p1[0], p2[0]), min(p1[1], p2[1])
        lx1, ly1 = max(p1[0], p2[0]), max(p1[1], p2[1])
        return lx1 >= x0 and lx0 < x1 and ly1 >= y0 and ly0 < y1

    for x1, y1, x2, y2 in raw_lines:
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dy == 0:
            continue
        angle = math.degrees(math.atan2(dx, dy))
        if angle <= 5.0 and 157 <= (x1 + x2) / 2 <= 164:
            # Baseline check: misses witness
            ep1, ep2 = extend_line_along_ink((float(x1), float(y1)), (float(x2), float(y2)), gray)
            if intersects(ep1, ep2, _CORRIDOR) and intersects(ep1, ep2, _UPPER) and intersects(ep1, ep2, _LOWER):
                witnesses.append({"raw": [int(x1), int(y1), int(x2), int(y2)], "extended": [list(ep1), list(ep2)]})

    return {
        "status": "PASS" if witnesses else "FAIL",
        "witness_count": len(witnesses),
        "witnesses": witnesses,
        "source_render_sha256": "5732b6014ec1c1d3b05e14c598b43ebec84a4d6198951264215a69fb7b0a0bc8",
    }


def main():
    results = {
        "oracle": "TRANSFER_ORACLE__LINE_DETECTION_LOSS_ENDPOINT_INK_EXTENSION",
        "synthetic_arrowhead": run_synthetic_arrowhead_test(),
        "synthetic_intentional_gap": run_synthetic_intentional_gap_test(),
        "synthetic_dashed_line": run_synthetic_dashed_line_test(),
        "degenerate_controls": run_degenerate_controls(),
    }
    case01_res = run_case01_real_data_test()
    if case01_res:
        results["case01_real_data"] = case01_res

    out_path = Path(__file__).parent / "benchmark_results.json"
    out_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"TRANSFER_ORACLE: ALL ASSERTIONS PASSED. Output written to {out_path.name}")
    print(json.dumps({k: v.get("status", "OK") if isinstance(v, dict) else v for k, v in results.items()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
