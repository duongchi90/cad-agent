"""Empirical Negative Matrix: Testing False-Positive Elimination across 17 non-circle families.

Families:
1. Rounded rectangle
2. Capsule / slot
3. Ellipse
4. Text 'O'
5. Text '0'
6. Text '8'
7. Text 'C'
8. Text 'G'
9. Dense parallel hatch
10. Cross hatch
11. Orthogonal line crossing grid
12. Three-line junction (Y / T)
13. Four-line rectangle corners
14. Random noise dots
15. Ring-like noise (broken speckle ring)
16. Concentric partial arcs
17. Rounded polyline
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

from primitive_ir_lib.geometry_extraction import extract_circles


def validate_circle_perimeter(
    gray: np.ndarray,
    cx: float,
    cy: float,
    r: float,
    *,
    min_support_fraction: float = 0.75,
    min_sector_fraction: float = 0.833,  # at least 10 of 12 sectors
    max_gap_deg: float = 45.0,
    min_gradient_alignment: float = 0.60,
    num_sectors: int = 12,
    num_samples: int = 180,
    darkness_threshold: int = 220,
) -> dict[str, object]:
    h, w = gray.shape
    angles = np.linspace(0, 2 * math.pi, num_samples, endpoint=False)
    tol = max(1, min(3, int(round(0.08 * r + 1.0))))

    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)

    supported_angles = []
    aligned_angles = []
    sector_bins = [0] * num_sectors
    sector_size = 2 * math.pi / num_sectors

    consec_unsupported = 0
    max_unsupported = 0

    for theta in angles:
        has_ink = False
        best_pt = None
        for dr in range(-tol, tol + 1):
            x = int(round(cx + (r + dr) * math.cos(theta)))
            y = int(round(cy + (r + dr) * math.sin(theta)))
            if 0 <= x < w and 0 <= y < h:
                if gray[y, x] <= darkness_threshold:
                    has_ink = True
                    best_pt = (x, y)
                    break
        if has_ink:
            supported_angles.append(theta)
            idx = int(theta / sector_size) % num_sectors
            sector_bins[idx] += 1
            consec_unsupported = 0

            # Gradient alignment
            bx, by = best_pt
            gx = grad_x[by, bx]
            gy = grad_y[by, bx]
            gmag = math.hypot(gx, gy)
            if gmag > 20.0:
                rx = math.cos(theta)
                ry = math.sin(theta)
                cos_sim = abs(gx * rx + gy * ry) / gmag
                if cos_sim >= 0.707:  # within 45 deg of radial normal
                    aligned_angles.append(theta)
        else:
            consec_unsupported += 1
            max_unsupported = max(max_unsupported, consec_unsupported)

    sup_frac = len(supported_angles) / num_samples
    occ_sectors = sum(1 for c in sector_bins if c > 0)
    sector_frac = occ_sectors / num_sectors
    max_gap = max_unsupported * (360.0 / num_samples)
    grad_align = len(aligned_angles) / max(1, len(supported_angles))

    is_valid = (
        sup_frac >= min_support_fraction
        and sector_frac >= min_sector_fraction
        and max_gap <= max_gap_deg
        and grad_align >= min_gradient_alignment
    )

    reasons = []
    if sup_frac < min_support_fraction:
        reasons.append(f"LOW_SUPPORT({sup_frac*100:.1f}%<{min_support_fraction*100:.0f}%)")
    if sector_frac < min_sector_fraction:
        reasons.append(f"LOW_SECTORS({occ_sectors}/{num_sectors})")
    if max_gap > max_gap_deg:
        reasons.append(f"LARGE_GAP({max_gap:.0f}deg>{max_gap_deg:.0f}deg)")
    if grad_align < min_gradient_alignment:
        reasons.append(f"POOR_GRAD_ALIGN({grad_align*100:.1f}%<{min_gradient_alignment*100:.0f}%)")

    return {
        "valid": is_valid,
        "reason": "; ".join(reasons) if reasons else "VALID_PERIMETER",
        "sup_frac": round(sup_frac, 3),
        "sectors": occ_sectors,
        "max_gap": round(max_gap, 1),
        "grad_align": round(grad_align, 3),
    }


def create_canvas(size: int = 300) -> np.ndarray:
    return np.full((size, size, 3), 255, dtype=np.uint8)


def get_negative_fixtures() -> dict[str, np.ndarray]:
    f = {}
    center = (150, 150)

    # 1. Rounded rectangle
    img1 = create_canvas()
    cv2.line(img1, (120, 110), (180, 110), (0, 0, 0), 2)
    cv2.line(img1, (120, 190), (180, 190), (0, 0, 0), 2)
    cv2.line(img1, (110, 120), (110, 180), (0, 0, 0), 2)
    cv2.line(img1, (190, 120), (190, 180), (0, 0, 0), 2)
    cv2.ellipse(img1, (120, 120), (10, 10), 0, 180, 270, (0, 0, 0), 2)
    cv2.ellipse(img1, (180, 120), (10, 10), 0, 270, 360, (0, 0, 0), 2)
    cv2.ellipse(img1, (180, 180), (10, 10), 0, 0, 90, (0, 0, 0), 2)
    cv2.ellipse(img1, (120, 180), (10, 10), 0, 90, 180, (0, 0, 0), 2)
    f["1. Rounded Rectangle"] = img1

    # 2. Capsule / slot
    img2 = create_canvas()
    cv2.line(img2, (125, 135), (175, 135), (0, 0, 0), 2)
    cv2.line(img2, (125, 165), (175, 165), (0, 0, 0), 2)
    cv2.ellipse(img2, (125, 150), (15, 15), 0, 90, 270, (0, 0, 0), 2)
    cv2.ellipse(img2, (175, 150), (15, 15), 0, 270, 450, (0, 0, 0), 2)
    f["2. Capsule / Slot"] = img2

    # 3. Ellipse (45, 25)
    img3 = create_canvas()
    cv2.ellipse(img3, center, (45, 25), 0, 0, 360, (0, 0, 0), 2)
    f["3. Ellipse"] = img3

    # 4-8. Text glyphs
    for char in ["O", "0", "8", "C", "G"]:
        img_t = create_canvas()
        cv2.putText(img_t, char, (110, 180), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 0, 0), 4)
        f[f"Text '{char}'"] = img_t

    # 9. Dense hatch
    img9 = create_canvas()
    for offset in range(-100, 200, 8):
        cv2.line(img9, (100 + offset, 100), (100 + offset + 100, 200), (0, 0, 0), 1)
    cv2.rectangle(img9, (100, 100), (200, 200), (0, 0, 0), 2)
    f["9. Dense Parallel Hatch"] = img9

    # 10. Cross hatch
    img10 = create_canvas()
    for offset in range(-100, 200, 10):
        cv2.line(img10, (100 + offset, 100), (100 + offset + 100, 200), (0, 0, 0), 1)
        cv2.line(img10, (100 + offset + 100, 100), (100 + offset, 200), (0, 0, 0), 1)
    f["10. Cross Hatch"] = img10

    # 11. Orthogonal grid crossing
    img11 = create_canvas()
    for i in range(5):
        coord = 110 + i * 20
        cv2.line(img11, (110, coord), (190, coord), (0, 0, 0), 2)
        cv2.line(img11, (coord, 110), (coord, 190), (0, 0, 0), 2)
    f["11. Orthogonal Crossing Lines"] = img11

    # 12. 3-line junction
    img12 = create_canvas()
    cv2.line(img12, (150, 150), (150, 230), (0, 0, 0), 2)
    cv2.line(img12, (150, 150), (80, 100), (0, 0, 0), 2)
    cv2.line(img12, (150, 150), (220, 100), (0, 0, 0), 2)
    f["12. Three-Line Junction (Y)"] = img12

    # 13. 4-line corners
    img13 = create_canvas()
    cv2.line(img13, (100, 100), (130, 100), (0, 0, 0), 2); cv2.line(img13, (100, 100), (100, 130), (0, 0, 0), 2)
    cv2.line(img13, (200, 100), (170, 100), (0, 0, 0), 2); cv2.line(img13, (200, 100), (200, 130), (0, 0, 0), 2)
    cv2.line(img13, (100, 200), (130, 200), (0, 0, 0), 2); cv2.line(img13, (100, 200), (100, 170), (0, 0, 0), 2)
    cv2.line(img13, (200, 200), (170, 200), (0, 0, 0), 2); cv2.line(img13, (200, 200), (200, 170), (0, 0, 0), 2)
    f["13. 4 Rectangle Corners"] = img13

    # 14. Random noise dots
    img14 = create_canvas()
    np.random.seed(42)
    for pt in np.random.randint(100, 200, size=(120, 2)):
        cv2.circle(img14, tuple(pt), 1, (0, 0, 0), -1)
    f["14. Random Noise Dots"] = img14

    # 15. Ring-like noise (broken speckle ring)
    img15 = create_canvas()
    for angle in np.linspace(0, 2 * math.pi, 25):
        px = int(150 + 35 * math.cos(angle) + np.random.uniform(-3, 3))
        py = int(150 + 35 * math.sin(angle) + np.random.uniform(-3, 3))
        cv2.circle(img15, (px, py), 2, (0, 0, 0), -1)
    f["15. Broken Speckle Ring"] = img15

    # 16. Concentric partial arcs (90 deg arcs)
    img16 = create_canvas()
    cv2.ellipse(img16, center, (25, 25), 0, 0, 90, (0, 0, 0), 2)
    cv2.ellipse(img16, center, (45, 45), 0, 0, 90, (0, 0, 0), 2)
    f["16. Concentric Partial Arcs"] = img16

    # 17. Rounded polyline
    img17 = create_canvas()
    pts = np.array([[80, 120], [150, 180], [220, 120]], np.int32)
    cv2.polylines(img17, [pts], isClosed=False, color=(0, 0, 0), thickness=3)
    f["17. Rounded Polyline"] = img17

    return f


def run_negative_matrix():
    fixtures = get_negative_fixtures()
    print("=== FALSE-POSITIVE ELIMINATION BENCHMARK ===")
    print(f"{'Fixture':<28} | {'Hough Detected':<16} | {'Validator Accepted':<20} | {'Elimination Verdict'}")
    print("-" * 88)

    total_hough_fps = 0
    total_val_fps = 0

    for name, img in fixtures.items():
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        detected = extract_circles(img, min_radius=10, max_radius=80, param1=100, param2=30, min_dist=20)
        hough_count = len(detected)
        total_hough_fps += hough_count

        accepted_count = 0
        rejection_reasons = []
        for c in detected:
            v = validate_circle_perimeter(gray, c.center_px[0], c.center_px[1], c.radius_px)
            if v["valid"]:
                accepted_count += 1
            else:
                rejection_reasons.append(v["reason"])

        total_val_fps += accepted_count

        if hough_count > 0:
            if accepted_count == 0:
                verdict = f"ELIMINATED 100% ({hough_count} -> 0)"
            else:
                verdict = f"PARTIAL LEAK ({accepted_count}/{hough_count} kept)"
        else:
            verdict = "CLEAN (Hough 0)"

        print(f"{name:<28} | {hough_count:<16} | {accepted_count:<20} | {verdict}")

    print(f"\nTotal False Circles Generated by Hough: {total_hough_fps}")
    print(f"Total False Circles Surviving Validator: {total_val_fps}")
    elimination_rate = (1.0 - total_val_fps / total_hough_fps) * 100.0 if total_hough_fps else 100.0
    print(f"False-Positive Elimination Rate: {elimination_rate:.1f}%")


if __name__ == "__main__":
    run_negative_matrix()
