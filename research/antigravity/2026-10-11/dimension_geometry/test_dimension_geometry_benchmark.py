"""
test_dimension_geometry_benchmark.py — Multi-Candidate Empirical Benchmark.

Compares 4 candidate strategies:
- Strategy A: Current Production Main (primitive_ir_lib/dimension_geometry.py)
- Strategy B: Naive Bidirectional Extension (two-way check, but inherits line selection bug)
- Strategy C: Orthogonal Pair Matching (ranks dimension line by orthogonal extension count, H/V only)
- Strategy D: Dimension Topology Oracle (Bidirectional extension, aligned support, inward/outward arrows)

Evaluated across 9 benchmark cases:
1. Horizontal dimension with downward extensions
2. Horizontal dimension with upward extensions
3. Vertical dimension with leftward extensions
4. Vertical dimension with rightward extensions
5. Vertical dimension with horizontal extensions (inversion trap)
6. Aligned 45-degree diagonal dimension
7. Aligned 135-degree diagonal dimension
8. Narrow gap outward arrowheads
9. Leader annotation with shelf line
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

from dimension_geometry_engine import (
    run_strategy_a,
    run_strategy_b,
    run_strategy_c,
    run_strategy_d,
)


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


def fixture_h_downward() -> np.ndarray:
    img = blank()
    cv2.line(img, (50, 100), (250, 100), (0, 0, 0), 2)
    cv2.line(img, (50, 95), (50, 180), (0, 0, 0), 2)
    cv2.line(img, (250, 95), (250, 180), (0, 0, 0), 2)
    draw_arrow(img, (50, 100), (1, 0))
    draw_arrow(img, (250, 100), (-1, 0))
    return img


def fixture_h_upward() -> np.ndarray:
    img = blank()
    cv2.line(img, (50, 200), (250, 200), (0, 0, 0), 2)
    cv2.line(img, (50, 80), (50, 205), (0, 0, 0), 2)
    cv2.line(img, (250, 80), (250, 205), (0, 0, 0), 2)
    draw_arrow(img, (50, 200), (1, 0))
    draw_arrow(img, (250, 200), (-1, 0))
    return img


def fixture_v_leftward() -> np.ndarray:
    img = blank()
    cv2.line(img, (200, 50), (200, 250), (0, 0, 0), 2)
    cv2.line(img, (100, 50), (205, 50), (0, 0, 0), 2)
    cv2.line(img, (100, 250), (205, 250), (0, 0, 0), 2)
    draw_arrow(img, (200, 50), (0, 1))
    draw_arrow(img, (200, 250), (0, -1))
    return img


def fixture_v_rightward() -> np.ndarray:
    img = blank()
    cv2.line(img, (100, 50), (100, 250), (0, 0, 0), 2)
    cv2.line(img, (95, 50), (200, 50), (0, 0, 0), 2)
    cv2.line(img, (95, 250), (200, 250), (0, 0, 0), 2)
    draw_arrow(img, (100, 50), (0, 1))
    draw_arrow(img, (100, 250), (0, -1))
    return img


def fixture_v_horizontal_trap() -> np.ndarray:
    img = blank()
    # Vertical dimension line (length 200)
    cv2.line(img, (150, 50), (150, 250), (0, 0, 0), 2)
    # Horizontal extension lines (length 80 each)
    cv2.line(img, (110, 50), (190, 50), (0, 0, 0), 2)
    cv2.line(img, (110, 250), (190, 250), (0, 0, 0), 2)
    draw_arrow(img, (150, 50), (0, 1))
    draw_arrow(img, (150, 250), (0, -1))
    return img


def fixture_aligned_45() -> np.ndarray:
    img = blank()
    cv2.line(img, (60, 60), (220, 220), (0, 0, 0), 2)
    # Perpendicular extensions at (60, 60) and (220, 220)
    cv2.line(img, (35, 85), (85, 35), (0, 0, 0), 2)
    cv2.line(img, (195, 245), (245, 195), (0, 0, 0), 2)
    draw_arrow(img, (60, 60), (1, 1))
    draw_arrow(img, (220, 220), (-1, -1))
    return img


def fixture_aligned_135() -> np.ndarray:
    img = blank()
    cv2.line(img, (60, 220), (220, 60), (0, 0, 0), 2)
    # Perpendicular extensions
    cv2.line(img, (35, 195), (85, 245), (0, 0, 0), 2)
    cv2.line(img, (195, 35), (245, 85), (0, 0, 0), 2)
    draw_arrow(img, (60, 220), (1, -1))
    draw_arrow(img, (220, 60), (-1, 1))
    return img


def fixture_narrow_outward() -> np.ndarray:
    img = blank()
    cv2.line(img, (135, 150), (165, 150), (0, 0, 0), 2)
    cv2.line(img, (135, 110), (135, 190), (0, 0, 0), 2)
    cv2.line(img, (165, 110), (165, 190), (0, 0, 0), 2)
    cv2.line(img, (105, 150), (135, 150), (0, 0, 0), 2)
    cv2.line(img, (165, 150), (195, 150), (0, 0, 0), 2)
    draw_arrow(img, (135, 150), (1, 0))
    draw_arrow(img, (165, 150), (-1, 0))
    return img


def fixture_leader_annotation() -> np.ndarray:
    img = blank()
    # Slanted pointer line
    cv2.line(img, (50, 250), (150, 150), (0, 0, 0), 2)
    # Horizontal landing shelf line
    cv2.line(img, (150, 150), (250, 150), (0, 0, 0), 2)
    draw_arrow(img, (50, 250), (-1, 1))
    return img


class TestDimensionGeometryBenchmark:
    """Rigorous empirical comparison of Strategies A, B, C, D."""

    def test_benchmark_case_1_horizontal_downward(self) -> None:
        img = fixture_h_downward()
        res_a = run_strategy_a(img)
        res_b = run_strategy_b(img)
        res_c = run_strategy_c(img)
        res_d = run_strategy_d(img)

        # All strategies handle standard horizontal downward
        assert res_a.kind_hint == "HORIZONTAL_DISTANCE" and len(res_a.extension_lines) == 2
        assert res_b.kind_hint == "HORIZONTAL_DISTANCE" and len(res_b.extension_lines) == 2
        assert res_c.kind_hint == "HORIZONTAL_DISTANCE" and len(res_c.extension_lines) == 2
        assert res_d.kind_hint == "HORIZONTAL_DISTANCE" and len(res_d.extension_lines) == 2
        assert res_d.arrow_orientation == "INWARD"

    def test_benchmark_case_2_horizontal_upward(self) -> None:
        img = fixture_h_upward()
        res_a = run_strategy_a(img)
        res_b = run_strategy_b(img)
        res_c = run_strategy_c(img)
        res_d = run_strategy_d(img)

        # Strategy A fails (0 extensions)
        assert len(res_a.extension_lines) == 0
        # Strategies B, C, D pass bidirectional check
        assert len(res_b.extension_lines) == 2
        assert len(res_c.extension_lines) == 2
        assert len(res_d.extension_lines) == 2

    def test_benchmark_case_3_vertical_leftward(self) -> None:
        img = fixture_v_leftward()
        res_a = run_strategy_a(img)
        res_b = run_strategy_b(img)
        res_c = run_strategy_c(img)
        res_d = run_strategy_d(img)

        # In this crop, horizontal lines are present (ext lines).
        # Strategy A and B pick horizontal extension line due to candidates = horizontal or vertical!
        assert res_a.kind_hint == "HORIZONTAL_DISTANCE"
        assert res_b.kind_hint == "HORIZONTAL_DISTANCE"
        # Strategy C and D correctly identify vertical dimension line
        assert res_c.kind_hint == "VERTICAL_DISTANCE" and len(res_c.extension_lines) == 2
        assert res_d.kind_hint == "VERTICAL_DISTANCE" and len(res_d.extension_lines) == 2

    def test_benchmark_case_4_vertical_rightward(self) -> None:
        img = fixture_v_rightward()
        res_a = run_strategy_a(img)
        res_b = run_strategy_b(img)
        res_c = run_strategy_c(img)
        res_d = run_strategy_d(img)

        # Strategy A and B fail
        assert res_a.kind_hint == "HORIZONTAL_DISTANCE"
        assert res_b.kind_hint == "HORIZONTAL_DISTANCE"
        # Strategy C and D pass
        assert res_c.kind_hint == "VERTICAL_DISTANCE" and len(res_c.extension_lines) == 2
        assert res_d.kind_hint == "VERTICAL_DISTANCE" and len(res_d.extension_lines) == 2

    def test_benchmark_case_5_vertical_inversion_trap(self) -> None:
        img = fixture_v_horizontal_trap()
        res_a = run_strategy_a(img)
        res_b = run_strategy_b(img)
        res_c = run_strategy_c(img)
        res_d = run_strategy_d(img)

        # Strategy A and B pick horizontal extension line
        assert res_a.kind_hint == "HORIZONTAL_DISTANCE"
        assert res_b.kind_hint == "HORIZONTAL_DISTANCE"
        # Strategy C and D resolve correctly
        assert res_c.kind_hint == "VERTICAL_DISTANCE" and len(res_c.extension_lines) == 2
        assert res_d.kind_hint == "VERTICAL_DISTANCE" and len(res_d.extension_lines) == 2

    def test_benchmark_case_6_aligned_45(self) -> None:
        img = fixture_aligned_45()
        res_a = run_strategy_a(img)
        res_b = run_strategy_b(img)
        res_c = run_strategy_c(img)
        res_d = run_strategy_d(img)

        # Strategies A, B, C fail to detect aligned dimension
        assert res_a.dimension_line is None
        assert res_b.dimension_line is None
        assert res_c.dimension_line is None
        # Strategy D succeeds
        assert res_d.kind_hint == "ALIGNED_DISTANCE"
        assert len(res_d.extension_lines) == 2

    def test_benchmark_case_7_aligned_135(self) -> None:
        img = fixture_aligned_135()
        res_a = run_strategy_a(img)
        res_b = run_strategy_b(img)
        res_c = run_strategy_c(img)
        res_d = run_strategy_d(img)

        # Strategies A, B, C fail
        assert res_a.dimension_line is None
        assert res_b.dimension_line is None
        assert res_c.dimension_line is None
        # Strategy D succeeds
        assert res_d.kind_hint == "ALIGNED_DISTANCE"
        assert len(res_d.extension_lines) == 2

    def test_benchmark_case_8_narrow_gap_outward_arrows(self) -> None:
        img = fixture_narrow_outward()
        res_a = run_strategy_a(img)
        res_b = run_strategy_b(img)
        res_c = run_strategy_c(img)
        res_d = run_strategy_d(img)

        # Only Strategy D provides outward arrow orientation
        assert not hasattr(res_a, "arrow_orientation")
        assert not hasattr(res_b, "arrow_orientation")
        assert not hasattr(res_c, "arrow_orientation")
        assert res_d.arrow_orientation == "OUTWARD"

    def test_benchmark_case_9_leader_annotation(self) -> None:
        img = fixture_leader_annotation()
        res_a = run_strategy_a(img)
        res_b = run_strategy_b(img)
        res_c = run_strategy_c(img)
        res_d = run_strategy_d(img)

        # All strategies detect leader lines via shared leader extraction
        assert len(res_a.leader_lines) >= 1
        assert len(res_b.leader_lines) >= 1
        assert len(res_c.leader_lines) >= 1
        assert len(res_d.leader_lines) >= 1
