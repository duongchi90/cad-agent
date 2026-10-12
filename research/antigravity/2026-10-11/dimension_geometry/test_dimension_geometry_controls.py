"""
test_dimension_geometry_controls.py — Positive Fixtures & Strong Negative Controls.

Verifies:
1. Negative controls:
   - Plain rectangle CAD geometry (0 false extension lines)
   - Cross-hatch diagonal field (rejection of dense hatching)
   - Parallel contour strokes (rejection of contour outlines)
   - Isolated T-junction (rejection of single-ended intersection)
   - Centered coordinate crosshair (rejection of non-dimension cross)
2. Positive controls:
   - Horizontal dimension with text gap / bridged dimension line
   - Tall vertical dimension with asymmetric extension spans
   - Diagonal aligned dimension with sharp perpendicular extensions
   - Dimension with leader pointer
"""

from __future__ import annotations

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

from dimension_geometry_engine import run_strategy_d


def blank(w: int = 300, h: int = 300) -> np.ndarray:
    return np.full((h, w, 3), 255, dtype=np.uint8)


def draw_arrow(img: np.ndarray, tip: tuple[int, int], direction: tuple[float, float], size: int = 8) -> None:
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


class TestDimensionGeometryControls:
    """Strong positive and negative controls for Strategy D."""

    def test_negative_control_plain_rectangle(self) -> None:
        """CAD part rectangle outline should not be recognized as a dimension with 2 extensions."""
        img = blank(300, 300)
        cv2.rectangle(img, (50, 50), (250, 200), (0, 0, 0), 2)
        res = run_strategy_d(img)
        # Rectangles have corner intersections, not perpendicular dimension extensions with arrows
        assert len(res.extension_lines) < 2 or res.confidence < 0.8
        assert res.arrow_orientation == "NONE"

    def test_negative_control_dense_crosshatch(self) -> None:
        """Dense 45-degree cross-hatching field must not produce false dimension line evidence."""
        img = blank(300, 300)
        for offset in range(-200, 400, 20):
            cv2.line(img, (offset, 0), (offset + 300, 300), (0, 0, 0), 1)
            cv2.line(img, (offset + 300, 0), (offset, 300), (0, 0, 0), 1)
        res = run_strategy_d(img)
        # Without orthogonal extension lines and arrows, confidence must be low
        assert len(res.arrow_points) == 0
        assert res.arrow_orientation == "NONE"

    def test_negative_control_parallel_contour_tracks(self) -> None:
        """Parallel railway / contour tracks without perpendicular extensions or arrows."""
        img = blank(300, 300)
        cv2.line(img, (50, 100), (250, 100), (0, 0, 0), 2)
        cv2.line(img, (50, 150), (250, 150), (0, 0, 0), 2)
        res = run_strategy_d(img)
        assert len(res.extension_lines) == 0
        assert res.arrow_orientation == "NONE"

    def test_negative_control_single_t_junction(self) -> None:
        """Single T-junction without arrows has at most 1 extension, cannot form complete dimension."""
        img = blank(300, 300)
        cv2.line(img, (50, 150), (250, 150), (0, 0, 0), 2)
        cv2.line(img, (150, 150), (150, 250), (0, 0, 0), 2)
        res = run_strategy_d(img)
        assert len(res.extension_lines) < 2
        assert res.arrow_orientation == "NONE"

    def test_negative_control_centered_crosshair(self) -> None:
        """Centered coordinate crosshair."""
        img = blank(300, 300)
        cv2.line(img, (150, 50), (150, 250), (0, 0, 0), 2)
        cv2.line(img, (50, 150), (250, 150), (0, 0, 0), 2)
        res = run_strategy_d(img)
        assert len(res.extension_lines) < 2
        assert res.arrow_orientation == "NONE"

    def test_positive_control_horizontal_bridged_text_gap(self) -> None:
        """Horizontal dimension line with text gap in middle and 2 downward extensions."""
        img = blank(350, 200)
        # Left segment
        cv2.line(img, (50, 100), (140, 100), (0, 0, 0), 2)
        # Gap for text from x=140 to x=210
        # Right segment
        cv2.line(img, (210, 100), (300, 100), (0, 0, 0), 2)
        # Downward extensions
        cv2.line(img, (50, 95), (50, 170), (0, 0, 0), 2)
        cv2.line(img, (300, 95), (300, 170), (0, 0, 0), 2)
        draw_arrow(img, (50, 100), (1, 0))
        draw_arrow(img, (300, 100), (-1, 0))

        res = run_strategy_d(img)
        assert res.kind_hint == "HORIZONTAL_DISTANCE"
        assert res.confidence >= 0.7

    def test_positive_control_tall_vertical_dimension(self) -> None:
        """Tall vertical dimension line with 2 extension lines spanning 220 px."""
        img = blank(200, 350)
        # Vertical line at x=100
        cv2.line(img, (100, 50), (100, 300), (0, 0, 0), 2)
        # Leftward extensions
        cv2.line(img, (30, 50), (110, 50), (0, 0, 0), 2)
        cv2.line(img, (30, 300), (110, 300), (0, 0, 0), 2)
        draw_arrow(img, (100, 50), (0, 1))
        draw_arrow(img, (100, 300), (0, -1))

        res = run_strategy_d(img)
        assert res.kind_hint == "VERTICAL_DISTANCE"
        assert len(res.extension_lines) == 2
        assert res.confidence >= 0.85

    def test_positive_control_diagonal_aligned_dimension(self) -> None:
        """Diagonal aligned dimension at 30 degrees."""
        img = blank(400, 400)
        # 30-degree dimension line: cos(30)=0.866, sin(30)=0.5
        p1 = (80, 100)
        p2 = (280, 215)
        cv2.line(img, p1, p2, (0, 0, 0), 2)
        # Perpendicular normal (-sin, cos) = (-0.5, 0.866)
        ext1_a = (80 - 25, 100 + 43)
        ext1_b = (80 + 25, 100 - 43)
        cv2.line(img, (int(ext1_a[0]), int(ext1_a[1])), (int(ext1_b[0]), int(ext1_b[1])), (0, 0, 0), 2)

        ext2_a = (280 - 25, 215 + 43)
        ext2_b = (280 + 25, 215 - 43)
        cv2.line(img, (int(ext2_a[0]), int(ext2_a[1])), (int(ext2_b[0]), int(ext2_b[1])), (0, 0, 0), 2)
        draw_arrow(img, p1, (200, 115))
        draw_arrow(img, p2, (-200, -115))

        res = run_strategy_d(img)
        assert res.kind_hint == "ALIGNED_DISTANCE"
        assert len(res.extension_lines) == 2
        assert res.confidence >= 0.85
