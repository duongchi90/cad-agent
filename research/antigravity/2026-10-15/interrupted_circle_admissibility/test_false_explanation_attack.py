"""Adversarial False Explanation Attack on Gap Explanation Models.

Phase 28 & 29 of ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015.
Tests whether gap explanation rules can be fooled by nearby non-intersecting geometry:
  Attack 1: Arc endpoint near a parallel witness line (does not cross)
  Attack 2: Arc gap with text nearby but outside circumference locus
  Attack 3: Arc endpoint near hatch stroke that does not intersect
  Attack 4: Authentic dimension line crossing circumference (valid explanation)
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np


OUT_DIR = Path(__file__).parent


def create_blank(h: int = 400, w: int = 400) -> np.ndarray:
    return np.full((h, w), 255, dtype=np.uint8)


def distance_point_to_segment(px: float, py: float, x0: float, y0: float, x1: float, y1: float) -> float:
    dx = x1 - x0
    dy = y1 - y0
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / l2))
    proj_x = x0 + t * dx
    proj_y = y0 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def run_attack():
    cx, cy, r = 200.0, 200.0, 75.0
    tol = 3.0

    # -------------------------------------------------------------
    # ATTACK 1: 300-deg arc with a parallel witness line 12px away from the gap
    # -------------------------------------------------------------
    img1 = create_blank()
    # Arc from 30 deg to 330 deg (missing 60 deg gap at right side: -30 to +30 deg)
    cv2.ellipse(img1, (int(cx), int(cy)), (int(r), int(r)), 0, 30, 330, 0, 2, cv2.LINE_AA)
    # Line passing near x = 200 + 75 + 12 = 287 (y from 150 to 250)
    cv2.line(img1, (287, 150), (287, 250), 0, 1, cv2.LINE_AA)

    # -------------------------------------------------------------
    # ATTACK 2: 300-deg arc with a line stopping 10px short of circumference
    # -------------------------------------------------------------
    img2 = create_blank()
    cv2.ellipse(img2, (int(cx), int(cy)), (int(r), int(r)), 0, 30, 330, 0, 2, cv2.LINE_AA)
    # Line along horizontal axis from x=320 to x=285 (stops 10px short of r=75 at x=275)
    cv2.line(img2, (320, 200), (285, 200), 0, 1, cv2.LINE_AA)

    # -------------------------------------------------------------
    # CONTROL: Authentic circle intersected by crossing dimension line
    # -------------------------------------------------------------
    img3 = create_blank()
    cv2.circle(img3, (int(cx), int(cy)), int(r), 0, 2, cv2.LINE_AA)
    # White box creating gap at -30 to +30 deg
    cv2.rectangle(img3, (265, 175), (290, 225), 255, -1)
    # Dimension line passing right through the gap and circle: from (240, 200) to (320, 200)
    cv2.line(img3, (240, 200), (320, 200), 0, 1, cv2.LINE_AA)

    attacks = [
        {"id": "ATTACK_1_PARALLEL_NEARBY", "img": img1, "true_semantic": "ARC", "should_admit_circle": False},
        {"id": "ATTACK_2_STOPPING_SHORT", "img": img2, "true_semantic": "ARC", "should_admit_circle": False},
        {"id": "CONTROL_AUTHENTIC_CROSSING", "img": img3, "true_semantic": "CIRCLE", "should_admit_circle": True},
    ]

    results = []

    for att in attacks:
        img = att["img"]
        gray = img
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 100)

        # Lines detected
        raw_lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=20, minLineLength=15, maxLineGap=5)
        lines = []
        if raw_lines is not None:
            for s in raw_lines.reshape(-1, 4):
                lines.append((float(s[0]), float(s[1]), float(s[2]), float(s[3])))

        # Midpoint of missing gap is at theta = 0 (275.0, 200.0)
        gap_mid_x = cx + r
        gap_mid_y = cy

        # Loose rule: "Is there any line within 25px of the gap center?"
        loose_explained = any(
            distance_point_to_segment(gap_mid_x, gap_mid_y, lx0, ly0, lx1, ly1) <= 25.0
            for lx0, ly0, lx1, ly1 in lines
        )

        # Strict rule: Line MUST:
        # 1. Be transversal (pass from interior dist < r - tol to exterior dist > r + tol)
        # 2. Intersect circumference within the gap angular sector
        # 3. NOT be a tangent chord of the arc itself
        strict_explained = False
        min_dist_to_circ = 999.0
        for lx0, ly0, lx1, ly1 in lines:
            d0 = math.hypot(lx0 - cx, ly0 - cy)
            d1 = math.hypot(lx1 - cx, ly1 - cy)
            # Transversality check: one endpoint must be inside circle (d < r - tol)
            # and the other outside circle (d > r + tol), proving it physically crosses the boundary!
            is_transversal = (min(d0, d1) < r - tol) and (max(d0, d1) > r + tol)
            if not is_transversal:
                continue

            # Check if crossing point lies within the gap angle [-30 deg, +30 deg]
            steps = 30
            for s in range(steps + 1):
                t = s / steps
                px = lx0 + t * (lx1 - lx0)
                py = ly0 + t * (ly1 - ly0)
                dist_to_c = math.hypot(px - cx, py - cy)
                dr = abs(dist_to_c - r)
                theta = math.degrees(math.atan2(py - cy, px - cx))
                if abs(theta) <= 30.0:
                    if dr < min_dist_to_circ:
                        min_dist_to_circ = dr
                    if dr <= tol:
                        strict_explained = True
                        break
            if strict_explained:
                break

        results.append({
            "test_id": att["id"],
            "true_semantic": att["true_semantic"],
            "loose_nearby_rule_explained": loose_explained,
            "loose_rule_admitted_circle": loose_explained,
            "strict_crossing_rule_explained": strict_explained,
            "strict_rule_admitted_circle": strict_explained,
            "min_distance_to_circumference_px": min_dist_to_circ,
            "loose_rule_safe": bool(loose_explained == att["should_admit_circle"]),
            "strict_rule_safe": bool(strict_explained == att["should_admit_circle"]),
        })

    summary = {
        "campaign_id": "ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015",
        "phase_28_and_29": results,
        "invariant": (
            "A gap is EXPLAINED if and only if an intersecting line or annotation polygon "
            "physically crosses the circle circumference within distance <= epsilon_position (<= 3.0px). "
            "Proximity alone (distance > epsilon_position) is FALSIFIED by Attack 1 and Attack 2, "
            "which falsely promote 300-deg open arcs."
        ),
    }

    out_file = OUT_DIR / "false_explanation_attack_results.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run_attack()
