"""
test_causal_red_tick_mark_detection.py — Public Causal RED Benchmarks for Boundary Symbol Detection.

Proves 5 causal failure modes in Strategy A (primitive_ir_lib/tick_mark_detection.py):
1. RED 1: 45° cross-hatch stroke falsely triggers tick mark boundary (1-segment diagonal flaw).
2. RED 2: Diagonal/angled dimension line witness split fails due to unrotated raster drift.
3. RED 3: Acute arrowhead (18° opening angle) dropped because diff < 25° minimum threshold.
4. RED 4: Text descender touching dimension line falsely slices line into fragments.
5. RED 5: Architectural 45° oblique tick mark slash fails to split Hough-fused dimension line.

All 5 fail under Strategy A and succeed under Strategy D.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
import cv2
import numpy as np
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from tick_mark_engine import (
    make_raw_line,
    run_strategy_a_endpoint,
    run_strategy_a_split,
    detect_boundary_symbol_at_point,
    split_line_at_boundaries,
)


def _canvas(w=300, h=300) -> np.ndarray:
    return np.full((h, w, 3), 255, dtype=np.uint8)


class TestCausalRedTickMarkDetection:
    """Causal RED suite confirming production Strategy A defects and Strategy D resolution."""

    def test_red_1_cross_hatch_false_positive_trigger(self) -> None:
        """RED 1: Diagonal cross-hatch strokes near endpoint falsely trigger tick mark in Strategy A."""
        img = _canvas(300, 300)
        # Horizontal line ending at (150, 150)
        cv2.line(img, (50, 150), (150, 150), (0, 0, 0), 2)

        # Draw a repetitive 45° cross-hatch field passing through the area (4 parallel lines)
        for offset in [-20, -10, 0, 10]:
            cv2.line(img, (130 + offset, 170), (170 + offset, 130), (0, 0, 0), 1)

        # Strategy A fails: 1 diagonal segment within window_px triggers False Positive
        res_a = run_strategy_a_endpoint(img, (150.0, 150.0), ref_angle=0.0)
        assert res_a.has_boundary is True, "Strategy A falsely triggered on hatch stroke"

        # Strategy D succeeds: detects repetitive hatch pattern and rejects false boundary
        res_d = detect_boundary_symbol_at_point(img, (150.0, 150.0), ref_angle_rad=0.0)
        assert res_d.has_boundary is False
        assert res_d.symbol_kind == "NONE"

    def test_red_2_tilted_witness_line_split_failure(self) -> None:
        """RED 2: 18° tilted witness line (72° to line) fails to split in Strategy A."""
        img = _canvas(400, 400)
        # Horizontal dimension line from (50, 150) to (350, 150)
        cv2.line(img, (50, 150), (350, 150), (0, 0, 0), 2)
        # Witness line at x=200 tilted by 18 degrees (72 degrees to line)
        dx = int(round(18 * math.cos(math.radians(72.0))))
        dy = int(round(18 * math.sin(math.radians(72.0))))
        cv2.line(img, (200 - dx, 150 - dy), (200 + dx, 150 + dy), (0, 0, 0), 2)

        line = make_raw_line((50, 150), (350, 150))

        # Strategy A fails: drift across 18° tilt exceeds max_offset_drift_px (2.0) -> 0 splits
        splits_a = run_strategy_a_split(line, img)
        assert len(splits_a) == 1, "Strategy A failed to split tilted witness line"

        # Strategy D succeeds: tolerates drafting/scan tilt (70°-110°) and cleanly splits line into 2 segments
        splits_d = split_line_at_boundaries(line, img)
        assert len(splits_d) == 2
        mid_p = splits_d[0].p2_px
        assert mid_p[0] == pytest.approx(200.0, abs=6.0)

    def test_red_3_acute_arrowhead_dropped(self) -> None:
        """RED 3: Acute mechanical arrowhead (opening angle 18°) dropped by Strategy A."""
        img = _canvas(300, 300)
        # Horizontal dimension line ending at (200, 150)
        cv2.line(img, (50, 150), (200, 150), (0, 0, 0), 2)
        # Arrowhead with 10° angle relative to line (opening angle 20°)
        # Wing 1: at +10° -> dx = -15 * cos(10°), dy = -15 * sin(10°)
        # Wing 2: at -10° -> dx = -15 * cos(10°), dy = +15 * sin(10°)
        w1_x = int(round(200 - 18 * math.cos(math.radians(10.0))))
        w1_y = int(round(150 - 18 * math.sin(math.radians(10.0))))
        w2_x = int(round(200 - 18 * math.cos(math.radians(10.0))))
        w2_y = int(round(150 + 18 * math.sin(math.radians(10.0))))
        cv2.line(img, (200, 150), (w1_x, w1_y), (0, 0, 0), 2)
        cv2.line(img, (200, 150), (w2_x, w2_y), (0, 0, 0), 2)

        # Strategy A fails: 10° < 25° diagonal_angle_min_deg -> returns False
        res_a = run_strategy_a_endpoint(img, (200.0, 150.0), ref_angle=0.0)
        assert res_a.has_boundary is False, "Strategy A should drop acute arrowhead < 25°"

        # Strategy D succeeds: acute converging arrowhead detected
        res_d = detect_boundary_symbol_at_point(img, (200.0, 150.0), ref_angle_rad=0.0)
        assert res_d.has_boundary is True
        assert res_d.symbol_kind == "ARROWHEAD"

    def test_red_4_text_descender_false_split(self) -> None:
        """RED 4: Text descender touching dimension line falsely slices line in Strategy A."""
        img = _canvas(400, 300)
        # Horizontal dimension line from (50, 150) to (350, 150)
        cv2.line(img, (50, 150), (350, 150), (0, 0, 0), 2)

        # Draw a text character 'p' with descender touching line at x=200:
        # Descender stem: x in [199, 201], y in [135, 149]
        # Character loop/body: x in [201, 212], y in [135, 145]
        cv2.rectangle(img, (199, 135), (201, 149), (0, 0, 0), -1)  # vertical stem touching line
        cv2.rectangle(img, (201, 135), (212, 145), (0, 0, 0), -1)  # letter bowl

        line = make_raw_line((50, 150), (350, 150))

        # Strategy A fails: column projection sees dark run >= 12px -> falsely splits line!
        splits_a = run_strategy_a_split(line, img)
        assert len(splits_a) >= 2, f"Expected Strategy A to falsely split on text descender, got {len(splits_a)}"

        # Strategy D succeeds: detects character bowl/aspect ratio -> suppresses false split!
        splits_d = split_line_at_boundaries(line, img)
        assert len(splits_d) == 1, "Strategy D should maintain intact dimension line"

    def test_red_5_architectural_45_oblique_slash_split(self) -> None:
        """RED 5: Architectural 45° oblique slash fails to split Hough-fused dimension line in Strategy A."""
        img = _canvas(400, 300)
        # Continuous dimension line from (50, 150) to (350, 150)
        cv2.line(img, (50, 150), (350, 150), (0, 0, 0), 2)
        # Architectural 45° slash at x=200 crossing line from (192, 158) to (208, 142)
        cv2.line(img, (192, 158), (208, 142), (0, 0, 0), 2)

        line = make_raw_line((50, 150), (350, 150))

        # Strategy A fails: split_raw_line_at_internal_witness_lines actively rejects 45° diagonal slashes
        splits_a = run_strategy_a_split(line, img)
        assert len(splits_a) == 1, "Strategy A should fail to split at 45° slash"

        # Strategy D succeeds: detects architectural oblique slash and splits fused line into 2 segments
        splits_d = split_line_at_boundaries(line, img)
        assert len(splits_d) == 2
        mid_p = splits_d[0].p2_px
        assert mid_p[0] == pytest.approx(200.0, abs=6.0)
