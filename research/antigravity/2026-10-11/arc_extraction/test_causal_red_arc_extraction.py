"""Public Causal RED: Partial Circular Arc Extraction on Current Main.

Constructs a deterministic raster fixture containing:
- one 90-deg circular arc
- one 180-deg circular arc
- one 270-deg circular arc
- one complete 360-deg circle
- one straight line

Runs the current public geometry extraction and document assembly path
(extract_raw_geometry + build_document) to establish the exact behavioral RED.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from primitive_ir_lib.assemble import build_document
from primitive_ir_lib.calibration import Calibration
from primitive_ir_lib.geometry_extraction import extract_raw_geometry


def build_causal_red_fixture() -> tuple[np.ndarray, dict]:
    """Create a 640x420 white canvas with 3 true arcs, 1 full circle, and 1 line."""
    img = np.full((420, 640, 3), 255, dtype=np.uint8)

    ground_truth = {
        "arcs": [
            {"id": "arc_90", "center": (110.0, 120.0), "radius": 50.0, "start_deg": 0.0, "end_deg": 90.0, "sweep_deg": 90.0},
            {"id": "arc_180", "center": (310.0, 120.0), "radius": 50.0, "start_deg": 0.0, "end_deg": 180.0, "sweep_deg": 180.0},
            {"id": "arc_270", "center": (510.0, 120.0), "radius": 50.0, "start_deg": 0.0, "end_deg": 270.0, "sweep_deg": 270.0},
        ],
        "circles": [
            {"id": "circle_360", "center": (150.0, 310.0), "radius": 50.0},
        ],
        "lines": [
            {"id": "line_horiz", "p1": (300.0, 310.0), "p2": (540.0, 310.0)},
        ],
    }

    # Draw 3 partial arcs (stroke width = 2px)
    for arc in ground_truth["arcs"]:
        cx, cy = int(arc["center"][0]), int(arc["center"][1])
        r = int(arc["radius"])
        cv2.ellipse(
            img,
            (cx, cy),
            (r, r),
            0.0,
            arc["start_deg"],
            arc["end_deg"],
            (0, 0, 0),
            2,
        )

    # Draw 1 full circle (stroke width = 2px)
    for circ in ground_truth["circles"]:
        cx, cy = int(circ["center"][0]), int(circ["center"][1])
        r = int(circ["radius"])
        cv2.circle(img, (cx, cy), r, (0, 0, 0), 2)

    # Draw 1 straight line (stroke width = 2px)
    for line in ground_truth["lines"]:
        p1 = (int(line["p1"][0]), int(line["p1"][1]))
        p2 = (int(line["p2"][0]), int(line["p2"][1]))
        cv2.line(img, p1, p2, (0, 0, 0), 2)

    return img, ground_truth


def run_causal_red() -> None:
    img, gt = build_causal_red_fixture()

    raw_default = extract_raw_geometry(img, preset="default")
    raw_tuned = extract_raw_geometry(img, preset="real_scan_tuned_v1")

    cal = Calibration(
        unit="mm",
        pixel_to_unit_scale=1.0,
        origin_px=(0.0, float(img.shape[0])),
        method="manual_override",
        status="verified",
    )
    doc = build_document(
        file_name="causal_red_arcs.png",
        page_index=0,
        image_width_px=img.shape[1],
        image_height_px=img.shape[0],
        calibration=cal,
        raw_lines=raw_default.lines,
        raw_circles=raw_default.circles,
        raw_texts=[],
    )

    has_raw_arcs_attr = hasattr(raw_default, "arcs")
    raw_arcs_count = len(getattr(raw_default, "arcs", []))
    doc_arc_primitives = [p for p in doc.primitives if p.type == "arc"]

    # Classify which ground-truth objects each detected RawCircle and RawLine lands near
    circle_matches = []
    for c in raw_default.circles:
        best_label = "UNKNOWN"
        best_dist = 999.0
        for a in gt["arcs"]:
            d = math.hypot(c.center_px[0] - a["center"][0], c.center_px[1] - a["center"][1])
            if d < best_dist:
                best_dist = d
                best_label = f"{a['id']} (FALSE CIRCLE CONFLATION)"
        for gc in gt["circles"]:
            d = math.hypot(c.center_px[0] - gc["center"][0], c.center_px[1] - gc["center"][1])
            if d < best_dist:
                best_dist = d
                best_label = f"{gc['id']} (TRUE CIRCLE)"
        circle_matches.append((c.center_px, c.radius_px, best_label, best_dist))

    line_matches = []
    for l in raw_default.lines:
        mx = 0.5 * (l.p1_px[0] + l.p2_px[0])
        my = 0.5 * (l.p1_px[1] + l.p2_px[1])
        if my < 220:
            line_matches.append((l.p1_px, l.p2_px, l.length_px(), "FALSE CHORD ON ARC"))
        else:
            line_matches.append((l.p1_px, l.p2_px, l.length_px(), "TRUE LINE REGION"))

    print("=== PUBLIC CAUSAL RED: ARC EXTRACTION ON CURRENT MAIN ===")
    print(f"EXPECTED_ARCS={len(gt['arcs'])} (90 deg, 180 deg, 270 deg)")
    print(f"EXPECTED_CIRCLES={len(gt['circles'])} (360 deg)")
    print(f"EXPECTED_LINES={len(gt['lines'])} (240px horizontal line)")
    print("-" * 72)
    print(f"HAS_RAW_GEOMETRY_ARCS_FIELD={has_raw_arcs_attr}")
    print(f"CURRENT_RAW_ARCS={raw_arcs_count}")
    print(f"CURRENT_DOC_ARC_PRIMITIVES={len(doc_arc_primitives)}")
    print(f"CURRENT_LINES (default preset)={len(raw_default.lines)}")
    print(f"CURRENT_CIRCLES (default preset)={len(raw_default.circles)}")
    print(f"CURRENT_LINES (real_scan_tuned_v1)={len(raw_tuned.lines)}")
    print(f"CURRENT_CIRCLES (real_scan_tuned_v1)={len(raw_tuned.circles)}")
    print("-" * 72)
    print("DETECTED CIRCLES BREAKDOWN (default preset):")
    for center, rad, label, dist in circle_matches:
        print(f"  center=({center[0]:.1f}, {center[1]:.1f}), r={rad:.1f}px -> {label} (center_err={dist:.2f}px)")
    print("DETECTED LINES BREAKDOWN (default preset):")
    for p1, p2, length, label in line_matches:
        print(f"  p1={p1}, p2={p2}, len={length:.1f}px -> {label}")

    # Assert behavioral RED: 3 arcs exist in raster, 0 arcs emitted
    assert len(doc_arc_primitives) == 0, "Expected 0 arc primitives on current main"
    print("\nVERDICT: CAUSAL RED CONFIRMED — 0/3 partial circular arcs extracted as ARC.")


if __name__ == "__main__":
    run_causal_red()
