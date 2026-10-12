"""
test_hatch_and_text_noise_rejection.py — Negative Control Matrix on Hatch and Text Noise.

Validates that non-boundary patterns (dense cross-hatch, diagonal text glyphs, corners)
do NOT falsely trigger tick-mark detection or block valid collinear line merges.

In current production (Strategy A):
Single isolated diagonal Hough strokes trigger detect_tick_mark_at_point, causing:
1. 100% false-positive tick marks inside 45-deg cross-hatch regions.
2. Valid broken centerlines or engineering lines embedded in hatch fail to merge.
3. Slanted text glyphs ('/', 'X', 'V', 'K') near line endpoints block valid merges.

In Strategy D (Centroid-Offset Clustered Oracle):
1. Multiple parallel diagonal strokes (hatch) have high perpendicular spread (> 5px),
   distinguishing them from isolated tick marks (spread <= 5px, max_p <= 8px).
2. 0 false tick marks on dense hatch across spacings (8, 12, 16, 20px) and angles (30°, 45°, 60°).
3. 100% valid broken line merge recall in hatch regions.
"""

from __future__ import annotations

import math
import cv2
import numpy as np

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.line_merging import merge_collinear_lines

try:
    from .line_merging_engine import merge_strategy_d, make_line
except ImportError:
    from line_merging_engine import merge_strategy_d, make_line


def _create_hatch_canvas(
    spacing_px: int,
    hatch_angle_deg: float,
    size: tuple[int, int] = (300, 300),
    cross_hatch: bool = False,
) -> np.ndarray:
    """Renders a background canvas with dense diagonal hatching."""
    w, h = size
    img = np.full((h, w, 3), 255, dtype=np.uint8)

    rad = math.radians(hatch_angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    nx, ny = -dy, dx

    # Draw primary hatch lines
    for offset in range(-h * 2, w * 2, spacing_px):
        p1 = (int(round(offset * nx)), int(round(offset * ny)))
        p2 = (int(round(offset * nx + dx * 600)), int(round(offset * ny + dy * 600)))
        cv2.line(img, p1, p2, (0, 0, 0), 1)

    if cross_hatch:
        rad2 = math.radians(hatch_angle_deg + 90.0)
        dx2, dy2 = math.cos(rad2), math.sin(rad2)
        nx2, ny2 = -dy2, dx2
        for offset in range(-h * 2, w * 2, spacing_px):
            p1 = (int(round(offset * nx2)), int(round(offset * ny2)))
            p2 = (int(round(offset * nx2 + dx2 * 600)), int(round(offset * ny2 + dy2 * 600)))
            cv2.line(img, p1, p2, (0, 0, 0), 1)

    return img


def test_hatch_immunity_matrix():
    """Evaluates 4 spacings x 3 angles x 2 hatch styles (single & cross) = 24 hatch configurations.

    Tests that a valid broken line (gap=10px) is correctly merged across the gap
    despite being surrounded by dense diagonal hatch.
    """
    spacings = [8, 12, 16, 20]
    angles = [30.0, 45.0, 60.0]
    styles = [False, True]  # single hatch, cross hatch

    total_cases = 0
    strat_a_merged = 0
    strat_d_merged = 0

    print("\n" + "=" * 80)
    print("HATCH IMMUNITY BENCHMARK (24 HATCH CONFIGS)")
    print("=" * 80)

    for spacing in spacings:
        for angle in angles:
            for cross in styles:
                total_cases += 1
                img = _create_hatch_canvas(spacing, angle, cross_hatch=cross)

                # Draw a broken horizontal line at y=150: [50, 145] and [155, 250] (gap 10px)
                cv2.line(img, (50, 150), (145, 150), (0, 0, 0), 2)
                cv2.line(img, (155, 150), (250, 150), (0, 0, 0), 2)

                l1 = make_line((50.0, 150.0), (145.0, 150.0), "h_left")
                l2 = make_line((155.0, 150.0), (250.0, 150.0), "h_right")

                # Strategy A
                res_a = merge_collinear_lines([l1, l2], blocking_texts=[], image_bgr=img, gap_tol_px=25.0)
                if len(res_a) == 1:
                    strat_a_merged += 1

                # Strategy D
                res_d = merge_strategy_d([l1, l2], image_bgr=img, gap_tol_px=25.0)
                if len(res_d) == 1:
                    strat_d_merged += 1

    print(f"Total Hatch Test Cases:      {total_cases}")
    print(f"Strategy A Valid Merge Rate: {strat_a_merged} / {total_cases} ({strat_a_merged / total_cases * 100:.1f}%)")
    print(f"Strategy D Valid Merge Rate: {strat_d_merged} / {total_cases} ({strat_d_merged / total_cases * 100:.1f}%)")

    # Strategy A fails because hatch strokes trigger tick-mark detection (blocking merge)
    assert strat_a_merged < 10, f"Strategy A should fail on most hatch cases, got {strat_a_merged}"
    # Strategy D correctly merges all valid broken lines in hatch regions (100% recall)
    assert strat_d_merged == total_cases, f"Strategy D failed on some hatch cases: {strat_d_merged}/{total_cases}"


def test_text_glyph_noise_rejection():
    """Tests that diagonal text glyphs ('/', 'X', 'V', 'K') placed near a broken line gap

    do NOT falsely trigger tick mark detection when they do not touch the line endpoints.
    """
    glyphs = ["/", "X", "V", "K", "N", "Z"]
    for glyph in glyphs:
        img = np.full((120, 240, 3), 255, dtype=np.uint8)
        # Broken line at y=60: [20, 110] and [130, 220] (gap 20px)
        cv2.line(img, (20, 60), (110, 60), (0, 0, 0), 2)
        cv2.line(img, (130, 60), (220, 60), (0, 0, 0), 2)
        # Draw text glyph floating 12px above gap center
        cv2.putText(img, glyph, (115, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

        l1 = make_line((20.0, 60.0), (110.0, 60.0), f"l1_{glyph}")
        l2 = make_line((130.0, 60.0), (220.0, 60.0), f"l2_{glyph}")

        res_d = merge_strategy_d([l1, l2], image_bgr=img, gap_tol_px=25.0)
        assert len(res_d) == 1, f"Strategy D should merge broken line near text glyph '{glyph}'"


if __name__ == "__main__":
    test_hatch_immunity_matrix()
    test_text_glyph_noise_rejection()
    print("HATCH AND TEXT NOISE REJECTION BENCHMARK PASSED.")
