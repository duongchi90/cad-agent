"""Empirical Causal RED: Demonstrating current-main Hough false-positive circles.

Evaluates current public owner: primitive_ir_lib.geometry_extraction.extract_circles()
across fixture families A-Q.
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

from primitive_ir_lib.geometry_extraction import extract_circles, RawCircle


def create_canvas(size: int = 300) -> np.ndarray:
    return np.full((size, size, 3), 255, dtype=np.uint8)


def generate_fixtures() -> dict[str, tuple[np.ndarray, str, int]]:
    """Returns dict of name -> (image, ground_truth_type, expected_circle_count)."""
    fixtures = {}
    center = (150, 150)

    # A. True clean thin circle (r=35, w=1)
    imgA = create_canvas()
    cv2.circle(imgA, center, 35, (0, 0, 0), 1)
    fixtures["A. True Clean Thin Circle (r=35)"] = (imgA, "TRUE_CIRCLE", 1)

    # B. True thick circle (r=35, w=5)
    imgB = create_canvas()
    cv2.circle(imgB, center, 35, (0, 0, 0), 5)
    fixtures["B. True Thick Circle (r=35, w=5)"] = (imgB, "TRUE_CIRCLE", 1)

    # C. Partial circle / arc (90 deg arc of r=35)
    imgC = create_canvas()
    cv2.ellipse(imgC, center, (35, 35), 0, 0, 90, (0, 0, 0), 2)
    fixtures["C. Partial Circle / Arc (90 deg)"] = (imgC, "ARC_NOT_CIRCLE", 0)

    # D. Rounded rectangle (80x50, r=15 corners)
    imgD = create_canvas()
    # 4 rounded corners
    cv2.line(imgD, (125, 110), (175, 110), (0, 0, 0), 2)
    cv2.line(imgD, (125, 190), (175, 190), (0, 0, 0), 2)
    cv2.line(imgD, (110, 125), (110, 175), (0, 0, 0), 2)
    cv2.line(imgD, (190, 125), (190, 175), (0, 0, 0), 2)
    cv2.ellipse(imgD, (125, 125), (15, 15), 0, 180, 270, (0, 0, 0), 2)
    cv2.ellipse(imgD, (175, 125), (15, 15), 0, 270, 360, (0, 0, 0), 2)
    cv2.ellipse(imgD, (175, 175), (15, 15), 0, 0, 90, (0, 0, 0), 2)
    cv2.ellipse(imgD, (125, 175), (15, 15), 0, 90, 180, (0, 0, 0), 2)
    fixtures["D. Rounded Rectangle (80x50, r=15)"] = (imgD, "ROUNDED_RECT", 0)

    # E. Text glyph O
    imgE = create_canvas()
    cv2.putText(imgE, "O", (110, 180), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 0, 0), 4)
    fixtures["E. Text Glyph 'O'"] = (imgE, "TEXT_GLYPH", 0)

    # F. Text glyph 0
    imgF = create_canvas()
    cv2.putText(imgF, "0", (110, 180), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 0, 0), 4)
    fixtures["F. Text Glyph '0'"] = (imgF, "TEXT_GLYPH", 0)

    # G. Text glyph 8
    imgG = create_canvas()
    cv2.putText(imgG, "8", (110, 180), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 0, 0), 4)
    fixtures["G. Text Glyph '8'"] = (imgG, "TEXT_GLYPH", 0)

    # H. Dense hatch (lines at 45 deg, spacing 8px in a 100x100 box)
    imgH = create_canvas()
    for offset in range(-100, 200, 8):
        cv2.line(imgH, (100 + offset, 100), (100 + offset + 100, 200), (0, 0, 0), 1)
    cv2.rectangle(imgH, (100, 100), (200, 200), (0, 0, 0), 2)
    fixtures["H. Dense Hatch in Boundary (gap=8)"] = (imgH, "HATCH", 0)

    # I. Hatch intersection / cross-hatch (45 deg and 135 deg, gap 10px)
    imgI = create_canvas()
    for offset in range(-100, 200, 10):
        cv2.line(imgI, (100 + offset, 100), (100 + offset + 100, 200), (0, 0, 0), 1)
        cv2.line(imgI, (100 + offset + 100, 100), (100 + offset, 200), (0, 0, 0), 1)
    fixtures["I. Cross-Hatch (gap=10)"] = (imgI, "CROSS_HATCH", 0)

    # J. Crossing LINEs (orthogonal grid 5x5, spacing 20px)
    imgJ = create_canvas()
    for i in range(5):
        coord = 110 + i * 20
        cv2.line(imgJ, (110, coord), (190, coord), (0, 0, 0), 2)
        cv2.line(imgJ, (coord, 110), (coord, 190), (0, 0, 0), 2)
    fixtures["J. Orthogonal Grid Crossing Lines"] = (imgJ, "CROSSING_LINES", 0)

    # K. Rectangular corner cluster (four 90-deg corners forming an open box)
    imgK = create_canvas()
    # 4 distinct corners
    cv2.line(imgK, (100, 100), (130, 100), (0, 0, 0), 2); cv2.line(imgK, (100, 100), (100, 130), (0, 0, 0), 2)
    cv2.line(imgK, (200, 100), (170, 100), (0, 0, 0), 2); cv2.line(imgK, (200, 100), (200, 130), (0, 0, 0), 2)
    cv2.line(imgK, (100, 200), (130, 200), (0, 0, 0), 2); cv2.line(imgK, (100, 200), (100, 170), (0, 0, 0), 2)
    cv2.line(imgK, (200, 200), (170, 200), (0, 0, 0), 2); cv2.line(imgK, (200, 200), (200, 170), (0, 0, 0), 2)
    fixtures["K. Rectangular Corner Cluster"] = (imgK, "CORNERS", 0)

    # L. Concentric circles (r=20 and r=45)
    imgL = create_canvas()
    cv2.circle(imgL, center, 20, (0, 0, 0), 2)
    cv2.circle(imgL, center, 45, (0, 0, 0), 2)
    fixtures["L. Concentric Circles (r=20, r=45)"] = (imgL, "TRUE_CIRCLE", 2)

    # M. Circle + tangent line (r=35, tangent at top)
    imgM = create_canvas()
    cv2.circle(imgM, center, 35, (0, 0, 0), 2)
    cv2.line(imgM, (50, 115), (250, 115), (0, 0, 0), 2)
    fixtures["M. Circle + Tangent Line"] = (imgM, "CIRCLE_PLUS_LINE", 1)

    # N. Circle + crossing line (r=35, line through center)
    imgN = create_canvas()
    cv2.circle(imgN, center, 35, (0, 0, 0), 2)
    cv2.line(imgN, (50, 150), (250, 150), (0, 0, 0), 2)
    fixtures["N. Circle + Crossing Line"] = (imgN, "CIRCLE_PLUS_LINE", 1)

    # O. Random speckle / noise (salt and pepper in 100x100 zone)
    imgO = create_canvas()
    np.random.seed(42)
    noise_pts = np.random.randint(100, 200, size=(120, 2))
    for pt in noise_pts:
        cv2.circle(imgO, tuple(pt), 1, (0, 0, 0), -1)
    fixtures["O. Random Speckle Noise"] = (imgO, "NOISE", 0)

    # P. Ellipse (axes=(45, 25))
    imgP = create_canvas()
    cv2.ellipse(imgP, center, (45, 25), 0, 0, 360, (0, 0, 0), 2)
    fixtures["P. Ellipse (axes=45, 25)"] = (imgP, "ELLIPSE", 0)

    # Q. Rounded slot / capsule (two semicircles r=15 separated by 50px)
    imgQ = create_canvas()
    cv2.line(imgQ, (125, 135), (175, 135), (0, 0, 0), 2)
    cv2.line(imgQ, (125, 165), (175, 165), (0, 0, 0), 2)
    cv2.ellipse(imgQ, (125, 150), (15, 15), 0, 90, 270, (0, 0, 0), 2)
    cv2.ellipse(imgQ, (175, 150), (15, 15), 0, 270, 450, (0, 0, 0), 2)
    fixtures["Q. Rounded Slot / Capsule (r=15)"] = (imgQ, "CAPSULE", 0)

    return fixtures


def run_failure_model_audit():
    fixtures = generate_fixtures()
    print("=== EMPIRICAL CAUSAL RED: HOUGH CIRCLE DETECTOR FAILURE AUDIT ===")
    print(f"{'Fixture Family':<38} | {'Type':<16} | {'Expected':<8} | {'Detected':<8} | {'Confidence':<10} | {'Verdict'}")
    print("-" * 105)

    false_positive_count = 0
    total_non_circle_fixtures = 0

    for name, (img, gtype, expected) in fixtures.items():
        detected = extract_circles(img, min_radius=10, max_radius=80, param1=100, param2=30, min_dist=20)
        det_count = len(detected)

        is_non_circle = (expected == 0)
        if is_non_circle:
            total_non_circle_fixtures += 1
            if det_count > 0:
                false_positive_count += 1
                verdict = f"FALSE_POSITIVE (+{det_count})"
            else:
                verdict = "PASS (Rejected)"
        else:
            if det_count == expected:
                verdict = "PASS (Detected)"
            elif det_count > expected:
                verdict = f"EXTRA_CANDIDATES (+{det_count - expected})"
            else:
                verdict = f"MISSED (-{expected - det_count})"

        conf_str = f"{detected[0].confidence:.2f}" if det_count > 0 else "N/A"
        print(f"{name:<38} | {gtype:<16} | {expected:<8} | {det_count:<8} | {conf_str:<10} | {verdict}")

    print(f"\nNon-Circle Fixtures: {total_non_circle_fixtures}")
    print(f"False-Positive Trigger Rate: {false_positive_count}/{total_non_circle_fixtures} ({false_positive_count/total_non_circle_fixtures*100:.1f}%)")


if __name__ == "__main__":
    run_failure_model_audit()
