"""
test_causal_red_dimension_geometry.py — Public Causal RED Benchmarks for Dimension Geometry.

Proves the 5 structural failure modes in Strategy A (primitive_ir_lib/dimension_geometry.py):
1. RED 1: Vertical dimension with horizontal extension lines misclassified as HORIZONTAL_DISTANCE.
2. RED 2: Upward extension lines returning () (0% recall).
3. RED 3: Rightward extension lines returning () (0% recall).
4. RED 4: Aligned (diagonal) dimension line returning None (dropped completely).
5. RED 5: Narrow-gap dimension with outward arrowheads unclassified / truncated.

All 5 fail under Strategy A and pass under Strategy D.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

import sys
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)


from dimension_geometry_engine import (
    run_strategy_a,
    run_strategy_d,
)




def create_blank_canvas(width: int = 300, height: int = 300) -> np.ndarray:
    """Create a white background BGR canvas."""
    return np.full((height, width, 3), 255, dtype=np.uint8)


def draw_arrowhead(img: np.ndarray, tip: tuple[int, int], direction: tuple[float, float], size: int = 8) -> None:
    """Draw a solid triangular arrowhead pointing along direction."""
    tx, ty = tip
    dx, dy = direction
    mag = np.hypot(dx, dy)
    if mag == 0:
        return
    ux, uy = dx / mag, dy / mag
    nx, ny = -uy, ux

    p1 = tip
    p2 = (int(round(tx - size * ux + (size * 0.5) * nx)), int(round(ty - size * uy + (size * 0.5) * ny)))
    p3 = (int(round(tx - size * ux - (size * 0.5) * nx)), int(round(ty - size * uy - (size * 0.5) * ny)))
    pts = np.array([p1, p2, p3], dtype=np.int32)
    cv2.fillPoly(img, [pts], (0, 0, 0))


class TestCausalRedDimensionGeometry:
    """Causal RED suite confirming production Strategy A defects and Strategy D resolution."""

    def test_red_1_vertical_dimension_inversion(self) -> None:
        """RED 1: Vertical dimension with horizontal extension lines is misclassified as HORIZONTAL_DISTANCE."""
        canvas = create_blank_canvas(300, 300)
        # Vertical dimension line from (150, 50) to (150, 250) (length 200)
        cv2.line(canvas, (150, 50), (150, 250), (0, 0, 0), 2)
        # Horizontal extension lines:
        # Top ext: (100, 50) to (180, 50) (length 80)
        cv2.line(canvas, (100, 50), (180, 50), (0, 0, 0), 2)
        # Bottom ext: (100, 250) to (180, 250) (length 80)
        cv2.line(canvas, (100, 250), (180, 250), (0, 0, 0), 2)
        # Arrowheads at vertical endpoints
        draw_arrowhead(canvas, (150, 50), (0, 1))
        draw_arrowhead(canvas, (150, 250), (0, -1))

        # Strategy A failure: candidates = horizontal or vertical picks horizontal extension!
        res_a = run_strategy_a(canvas)
        assert res_a.kind_hint == "HORIZONTAL_DISTANCE", (
            f"Expected Strategy A to misclassify vertical dim as HORIZONTAL_DISTANCE, got {res_a.kind_hint}"
        )
        assert len(res_a.extension_lines) == 0, "Strategy A fails to find extension lines for inverted line"

        # Strategy D resolution
        res_d = run_strategy_d(canvas)
        assert res_d.kind_hint == "VERTICAL_DISTANCE"
        assert res_d.dimension_line is not None
        # Must be vertical: dx < dy
        (p1x, p1y), (p2x, p2y) = res_d.dimension_line
        assert abs(p1x - p2x) <= 3.0 and abs(p1y - p2y) >= 150.0
        assert len(res_d.extension_lines) == 2

    def test_red_2_upward_extension_lines_zero_recall(self) -> None:
        """RED 2: Horizontal dimension with upward extension lines returns () in Strategy A."""
        canvas = create_blank_canvas(300, 300)
        # Horizontal dimension line at y=200, from x=50 to x=250
        cv2.line(canvas, (50, 200), (250, 200), (0, 0, 0), 2)
        # Upward extension lines (y from 80 to 210)
        cv2.line(canvas, (50, 80), (50, 210), (0, 0, 0), 2)
        cv2.line(canvas, (250, 80), (250, 210), (0, 0, 0), 2)
        draw_arrowhead(canvas, (50, 200), (1, 0))
        draw_arrowhead(canvas, (250, 200), (-1, 0))

        # Strategy A fails: only looks downward (y >= y+24.0)
        res_a = run_strategy_a(canvas)
        assert len(res_a.extension_lines) == 0, (
            f"Strategy A unexpectedly detected upward extensions: {res_a.extension_lines}"
        )

        # Strategy D bidirectional check succeeds
        res_d = run_strategy_d(canvas)
        assert res_d.kind_hint == "HORIZONTAL_DISTANCE"
        assert len(res_d.extension_lines) == 2

    def test_red_3_rightward_extension_lines_zero_recall(self) -> None:
        """RED 3: Vertical dimension with rightward extension lines returns () in Strategy A."""
        canvas = create_blank_canvas(300, 300)
        # Vertical dimension line at x=80, from y=50 to y=250
        cv2.line(canvas, (80, 50), (80, 250), (0, 0, 0), 2)
        # Rightward extension lines (x from 75 to 200)
        cv2.line(canvas, (75, 50), (200, 50), (0, 0, 0), 2)
        cv2.line(canvas, (75, 250), (200, 250), (0, 0, 0), 2)
        draw_arrowhead(canvas, (80, 50), (0, 1))
        draw_arrowhead(canvas, (80, 250), (0, -1))

        # Strategy A fails: only looks leftward (x <= x-24.0)
        res_a = run_strategy_a(canvas)
        # res_a will either pick horizontal extension line or find 0 extensions
        assert len(res_a.extension_lines) == 0

        # Strategy D bidirectional check succeeds
        res_d = run_strategy_d(canvas)
        assert res_d.kind_hint == "VERTICAL_DISTANCE"
        assert len(res_d.extension_lines) == 2

    def test_red_4_aligned_dimension_dropped(self) -> None:
        """RED 4: Aligned 45-degree dimension line returns None in Strategy A."""
        canvas = create_blank_canvas(300, 300)
        # 45-degree diagonal dimension line from (50, 50) to (220, 220)
        cv2.line(canvas, (50, 50), (220, 220), (0, 0, 0), 2)
        # Perpendicular 135-degree extension lines
        # At (50, 50): normal vector is (-1, 1)/sqrt(2), span +/- 40px -> (50-28, 50+28) to (50+28, 50-28)
        cv2.line(canvas, (22, 78), (78, 22), (0, 0, 0), 2)
        # At (220, 220): (192, 248) to (248, 192)
        cv2.line(canvas, (192, 248), (248, 192), (0, 0, 0), 2)
        draw_arrowhead(canvas, (50, 50), (1, 1))
        draw_arrowhead(canvas, (220, 220), (-1, -1))

        # Strategy A fails: only checks horizontal or vertical
        res_a = run_strategy_a(canvas)
        assert res_a.dimension_line is None, f"Strategy A unexpectedly found dimension line: {res_a.dimension_line}"

        # Strategy D succeeds
        res_d = run_strategy_d(canvas)
        assert res_d.dimension_line is not None
        assert res_d.kind_hint == "ALIGNED_DISTANCE"
        assert len(res_d.extension_lines) == 2

    def test_red_5_narrow_gap_outward_arrowheads(self) -> None:
        """RED 5: Narrow gap dimension has outward arrowheads; Strategy A cannot classify orientation."""
        canvas = create_blank_canvas(300, 300)
        # Short horizontal dimension line between (135, 150) and (165, 150) (length 30)
        cv2.line(canvas, (135, 150), (165, 150), (0, 0, 0), 2)
        # Extension lines at 135 and 165
        cv2.line(canvas, (135, 110), (135, 190), (0, 0, 0), 2)
        cv2.line(canvas, (165, 110), (165, 190), (0, 0, 0), 2)
        # Outer tail lines
        cv2.line(canvas, (105, 150), (135, 150), (0, 0, 0), 2)
        cv2.line(canvas, (165, 150), (195, 150), (0, 0, 0), 2)
        # Outward pointing arrows (pointing towards extension lines from outside)
        draw_arrowhead(canvas, (135, 150), (1, 0))
        draw_arrowhead(canvas, (165, 150), (-1, 0))

        # Strategy A has no arrow orientation concept
        res_a = run_strategy_a(canvas)
        assert not hasattr(res_a, "arrow_orientation")

        # Strategy D identifies OUTWARD arrow orientation
        res_d = run_strategy_d(canvas)
        assert res_d.arrow_orientation == "OUTWARD"
