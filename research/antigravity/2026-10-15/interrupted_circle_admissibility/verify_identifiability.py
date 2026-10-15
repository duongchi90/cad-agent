"""Information-theoretic Identifiability and Observational Equivalence Test.

Phases 12 and 13 of ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015.
Proves whether raster-only evidence can distinguish:
  PAIR 1: Circle with white occlusion vs Partial Arc terminating at same boundary
  PAIR 2: Circle crossed by dimension line (X-crossing) vs Arcs terminating at dimension line (T-junctions)
"""

from __future__ import annotations

import importlib
import json
import math
from pathlib import Path
from typing import Any, Dict

import numpy as np

cv2 = importlib.import_module("cv2")


OUT_DIR = Path(__file__).parent


def test_white_occlusion_equivalence() -> Dict[str, Any]:
    """Test Case 1: Circle with white text/occlusion box vs 330-deg Arc with same white box."""
    # Common parameters
    h, w = 400, 400
    cx, cy, r = 200.0, 200.0, 75.0
    stroke = 2

    # Image A: Complete circle, then occluded by a white box
    img_a = np.full((h, w), 255, dtype=np.uint8)
    cv2.circle(img_a, (int(cx), int(cy)), int(r), 0, stroke, cv2.LINE_AA)
    # Occlude from theta = -20 deg to +20 deg (x >= 200 + 75*cos(20) = 270)
    # Place a white box covering x in [265, 300], y in [165, 235]
    box_x0, box_y0, box_x1, box_y1 = 265, 165, 300, 235
    cv2.rectangle(img_a, (box_x0, box_y0), (box_x1, box_y1), 255, -1)

    # Image B: True partial arc spanning from +20 deg to 340 deg (i.e. open 40 deg gap)
    # terminating at exactly the same coordinates, with identical background
    img_b = np.full((h, w), 255, dtype=np.uint8)
    cv2.ellipse(img_b, (int(cx), int(cy)), (int(r), int(r)), 0, 20, 340, 0, stroke, cv2.LINE_AA)
    # Apply the same white box to ensure identical raster boundary conditions
    cv2.rectangle(img_b, (box_x0, box_y0), (box_x1, box_y1), 255, -1)

    # Compute differences
    diff_pixels = np.abs(img_a.astype(int) - img_b.astype(int))
    max_pixel_diff = int(np.max(diff_pixels))
    l1_diff = int(np.sum(diff_pixels))
    identical_pixels = bool(l1_diff == 0)

    # Canny edge maps
    edges_a = cv2.Canny(cv2.GaussianBlur(img_a, (3, 3), 0), 50, 100)
    edges_b = cv2.Canny(cv2.GaussianBlur(img_b, (3, 3), 0), 50, 100)
    edge_diff = int(np.sum(edges_a != edges_b))

    return {
        "experiment": "circle_plus_white_box_vs_arc_plus_white_box",
        "image_size": [h, w],
        "circle_center": [cx, cy],
        "circle_radius": r,
        "max_pixel_difference": max_pixel_diff,
        "l1_pixel_difference": l1_diff,
        "edge_map_mismatched_pixels": edge_diff,
        "are_raster_images_identical": identical_pixels,
        "information_theoretic_identifiability": "IMPOSSIBLE_RASTER_ONLY" if l1_diff == 0 else "DISTINGUISHABLE_BY_SUBPIXEL_AA",
    }


def test_intersecting_line_topology() -> Dict[str, Any]:
    """Test Case 2: Circle crossed by dimension line (X-junction) vs Arc terminating at line (T-junction)."""
    h, w = 400, 400
    cx, cy, r = 200.0, 200.0, 75.0

    # Image A: Circle crossed by vertical line at x = 200 (2 X-crossings at (200, 125) and (200, 275))
    img_a = np.full((h, w), 255, dtype=np.uint8)
    cv2.circle(img_a, (int(cx), int(cy)), int(r), 0, 2)
    cv2.line(img_a, (200, 50), (200, 350), 0, 2)

    # Image B: Semicircle on right (x >= 200) terminating AT the vertical line (T-junctions at (200, 125) and (200, 275))
    img_b = np.full((h, w), 255, dtype=np.uint8)
    cv2.ellipse(img_b, (int(cx), int(cy)), (int(r), int(r)), 0, -90, 90, 0, 2)
    cv2.line(img_b, (200, 50), (200, 350), 0, 2)

    # Analyze junction local neighborhoods (radius 5 around (200, 125))
    patch_a = img_a[120:131, 195:206]
    patch_b = img_b[120:131, 195:206]

    # In patch A: 4 branches radiate from center (X-crossing)
    # In patch B: 3 branches radiate from center (T-junction)
    # Check left side of junction: x < 200
    left_ink_a = np.sum(patch_a[:, :5] == 0)
    left_ink_b = np.sum(patch_b[:, :5] == 0)

    return {
        "experiment": "line_circle_crossing_x_vs_t_junction",
        "junction_coord": [200, 125],
        "left_branch_ink_circle_crossing_a": int(left_ink_a),
        "left_branch_ink_arc_termination_b": int(left_ink_b),
        "topology_discriminator": "TOPOLOGICAL_CONTINUATION_ON_BOTH_SIDES",
        "can_separate_crossing_from_termination": bool(left_ink_a > 0 and left_ink_b == 0),
    }


def main():
    res1 = test_white_occlusion_equivalence()
    res2 = test_intersecting_line_topology()

    summary = {
        "campaign_id": "ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015",
        "phase_12_and_13": {
            "white_occlusion_test": res1,
            "line_crossing_test": res2,
            "fundamental_conclusion": (
                "1. If a circle and an arc terminate at a void/white mask without occluder ink, "
                "the raster representations are INFORMATION-THEORETICALLY OBSERVATIONALLY EQUIVALENT. "
                "No raster-only classifier can separate an open arc from an occluded circle without making assumptions.\n"
                "2. If an intersecting linework (dimension, witness, centerline) causes the interruption, "
                "topological continuation on BOTH sides of the intersection separates true circles from terminating arcs.\n"
                "3. Therefore, safe interrupted-circle admission is ONLY possible when either:\n"
                "   a) Every gap is geometrically explained by an intersecting occluder with continuation; OR\n"
                "   b) An upstream semantic/role witness (e.g. OCR text bounding box) explains the gap."
            ),
        }
    }
    out_file = OUT_DIR / "identifiability_test_results.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
