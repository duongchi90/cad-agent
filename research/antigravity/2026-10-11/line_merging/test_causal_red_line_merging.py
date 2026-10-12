"""
test_causal_red_line_merging.py — Baseline Causal RED for Collinear Line Merging.

Demonstrates 6 distinct failure modes in current production
primitive_ir_lib.line_merging.merge_collinear_lines on main (47808851b22472e213c8b8d77b735f9dbb88d699):

1. FAILURE 1 (Angle skew from first-segment bias):
   A cluster with a long 400px horizontal line and a short 15px segment tilted by 2.8°
   locks its reference angle to 2.8° when the short segment is first in the cluster,
   distorting the merged line's endpoint by > 10px.
2. FAILURE 2 (Single-endpoint perpendicular test leak):
   A 250px segment tilted by 3.0° with first endpoint perp=2px has its second endpoint
   drift to perp=15.1px (> perp_tol=6px). Current production merges it anyway because
   it only tests (x0j, y0j).
3. FAILURE 3 (Parallel line collapse):
   Two distinct parallel lines (e.g. wall outline / slot) separated by 4px (<= perp_tol=6px)
   with overlapping longitudinal projection are collapsed into a single false centerline.
4. FAILURE 4 (Dimension chain bridging without text anchor):
   Two adjacent dimension lines separated by a 20px gap with a perpendicular (90°) witness line
   at the boundary are falsely merged into 1 line if text OCR fails (blocking_texts=[]),
   because detect_tick_mark_at_point only looks for 25°-65° Hough strokes.
5. FAILURE 5 (False tick mark on cross-hatch):
   A valid broken engineering line (gap=10px, centerline break) embedded in 45° cross-hatch
   is blocked from merging because hatch strokes trigger false tick-mark detections.
6. FAILURE 6 (T-junction bridging):
   Two collinear segments separated by a 15px gap where a perpendicular line forms a real
   T-junction are falsely merged right through the T-junction.
"""

from __future__ import annotations

import math
import cv2
import numpy as np

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.line_merging import merge_collinear_lines
from primitive_ir_lib.tick_mark_detection import detect_tick_mark_at_point


def _make_line(p1: tuple[float, float], p2: tuple[float, float], id_: str, conf: float = 0.9) -> RawLine:
    return RawLine(
        id=id_,
        p1_px=p1,
        p2_px=p2,
        confidence=conf,
        bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])),
    )


def test_red_1_first_segment_angle_skew():
    """Short tilted fragment appearing first skews the entire long line angle."""
    # Short segment 15px tilted by 2.8 deg
    # Long segment 400px strictly horizontal
    dx_short = 15.0 * math.cos(math.radians(2.8))
    dy_short = 15.0 * math.sin(math.radians(2.8))
    short_line = _make_line((0.0, 0.0), (dx_short, dy_short), "short_tilted")
    long_line = _make_line((20.0, 0.0), (420.0, 0.0), "long_horizontal")

    # When short line is first:
    merged_short_first = merge_collinear_lines([short_line, long_line], blocking_texts=[], gap_tol_px=25.0)
    assert len(merged_short_first) == 1
    m = merged_short_first[0]
    p1, p2 = m.p1_px, m.p2_px
    angle_deg = math.degrees(math.atan2(abs(p2[1] - p1[1]), abs(p2[0] - p1[0])))
    dy_end = abs(p2[1] - 0.0)

    # In current production, angle is skewed to ~2.8 deg and endpoint dy drifts > 15px!
    # A correct weighted estimator would give angle < 0.2 deg and dy < 1.0 px.
    print(f"\n[RED 1] Merged angle: {angle_deg:.3f} deg, endpoint y drift: {dy_end:.2f} px")
    assert angle_deg > 2.0, f"Expected causal RED angle skew > 2.0 deg, got {angle_deg}"
    assert dy_end > 10.0, f"Expected causal RED endpoint drift > 10.0 px, got {dy_end}"


def test_red_2_single_endpoint_perp_leak():
    """Segment with far endpoint perp=15.1px (> 6px tol) is falsely merged."""
    # Base line: (0, 0) -> (300, 0)
    base_line = _make_line((0.0, 0.0), (300.0, 0.0), "base")
    # Diverging line: starts at (50, 2) [perp=2px <= 6px], angle 2.5 deg (within 3.0 deg tol), length 250px
    # Far endpoint y = 2.0 + 250 * sin(2.5 deg) = 2.0 + 10.90 = 12.90 px (> 6.0 px)
    p1 = (50.0, 2.0)
    p2 = (50.0 + 250.0 * math.cos(math.radians(2.5)), 2.0 + 250.0 * math.sin(math.radians(2.5)))
    diverging_line = _make_line(p1, p2, "diverging")

    far_endpoint_perp = abs(p2[1])
    assert far_endpoint_perp > 12.0

    # Current production checks only perp of (x0j, y0j) which is 2.0 <= 6.0!
    merged = merge_collinear_lines([base_line, diverging_line], blocking_texts=[], perp_tol_px=6.0)
    # Causal failure: it merges lines whose far endpoint diverges by 12.9px (> perp_tol=6.0px)!
    print(f"\n[RED 2] Diverging line far perp: {far_endpoint_perp:.2f} px. Merged count: {len(merged)}")
    assert len(merged) == 1, "Expected causal failure: diverging line merged because only endpoint 1 is checked"


def test_red_3_parallel_line_collapse():
    """Two parallel lines separated by 4px are collapsed into 1 single line."""
    line_top = _make_line((50.0, 100.0), (250.0, 100.0), "wall_top")
    line_bot = _make_line((50.0, 104.0), (250.0, 104.0), "wall_bot")  # 4px offset <= perp_tol=6px

    merged = merge_collinear_lines([line_top, line_bot], blocking_texts=[], perp_tol_px=6.0)
    print(f"\n[RED 3] Parallel lines (4px offset) merged count: {len(merged)}")
    # Current production collapses distinct parallel lines into 1!
    assert len(merged) == 1, "Expected causal failure: 4px parallel lines collapsed into single line"


def test_red_4_dimension_chain_bridging_without_text():
    """Adjacent dimension lines separated by 20px with perpendicular witness are merged if OCR fails."""
    # Image with two dimension segments: (20, 100)-(180, 100) and (200, 100)-(350, 100)
    # At x=190, a perpendicular 90 deg witness line runs from y=70 to y=130.
    image = np.full((200, 400, 3), 255, dtype=np.uint8)
    cv2.line(image, (20, 100), (180, 100), (0, 0, 0), 2)
    cv2.line(image, (200, 100), (350, 100), (0, 0, 0), 2)
    cv2.line(image, (190, 70), (190, 130), (0, 0, 0), 2)  # 90-deg witness line

    l1 = _make_line((20.0, 100.0), (180.0, 100.0), "dim_left")
    l2 = _make_line((200.0, 100.0), (350.0, 100.0), "dim_right")

    # If OCR missed text (blocking_texts=[]), detect_tick_mark_at_point looks for 25-65 deg strokes.
    # The witness line is 90 deg, so detect_tick_mark_at_point returns False!
    # And gap is 20px <= gap_tol_px=25px.
    merged = merge_collinear_lines([l1, l2], blocking_texts=[], image_bgr=image, gap_tol_px=25.0)
    print(f"\n[RED 4] Dimension chain (gap 20px, 90-deg witness, no text) merged count: {len(merged)}")
    # Current production merges the two dimensions!
    assert len(merged) == 1, "Expected causal failure: dimension chain bridged into single line"


def test_red_5_false_tick_mark_on_cross_hatch():
    """Valid broken centerline in 45-deg cross-hatch is blocked from merging."""
    # Image with broken centerline: (50, 100)-(150, 100) and (160, 100)-(260, 100) (gap 10px)
    # Background has 45-deg hatch lines spaced every 15px
    image = np.full((200, 300, 3), 255, dtype=np.uint8)
    cv2.line(image, (50, 100), (150, 100), (0, 0, 0), 1)
    cv2.line(image, (160, 100), (260, 100), (0, 0, 0), 1)
    for offset in range(-100, 400, 15):
        cv2.line(image, (offset, 0), (offset + 200, 200), (0, 0, 0), 1)

    # Check tick mark detection at the gap endpoint (150, 100)
    has_tick = detect_tick_mark_at_point(image, (150.0, 100.0), 0.0)
    print(f"\n[RED 5] Hatch triggers tick mark at gap endpoint: {has_tick}")
    # Current production sees a 45 deg stroke and flags a tick mark!
    assert has_tick is True, "Expected causal failure: 45-deg hatch falsely detected as tick mark"


def test_red_6_t_junction_bridging():
    """Two collinear segments with a perpendicular line forming a T-junction at gap are merged."""
    # Horizontal line: (20, 100)-(95, 100) and (105, 100)-(200, 100) (gap 10px)
    # Vertical line terminates at (100, 100) and extends down to (100, 180) (T-junction)
    l_left = _make_line((20.0, 100.0), (95.0, 100.0), "h_left")
    l_right = _make_line((105.0, 100.0), (200.0, 100.0), "h_right")
    v_stem = _make_line((100.0, 100.0), (100.0, 180.0), "v_stem")

    merged = merge_collinear_lines([l_left, l_right, v_stem], blocking_texts=[], gap_tol_px=25.0)
    # Count how many horizontal lines remain
    h_lines = [l for l in merged if abs(l.p1_px[1] - l.p2_px[1]) <= 2.0]
    print(f"\n[RED 6] T-junction gap bridged into horizontal lines: {len(h_lines)}")
    # Current production merges l_left and l_right into 1 line, bridging through the T-junction!
    assert len(h_lines) == 1, "Expected causal failure: T-junction gap bridged into 1 line"


if __name__ == "__main__":
    test_red_1_first_segment_angle_skew()
    test_red_2_single_endpoint_perp_leak()
    test_red_3_parallel_line_collapse()
    test_red_4_dimension_chain_bridging_without_text()
    test_red_5_false_tick_mark_on_cross_hatch()
    test_red_6_t_junction_bridging()
    print("\nALL 6 CAUSAL RED TESTS CONFIRMED EXPECTED FAILURES.")
