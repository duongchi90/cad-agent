"""
test_tick_mark_benchmark.py — Systematic Comparison of Strategies A, B, C, D for Dimension Boundary Detection.

Empirically benchmarks 4 strategies across 8 dimension boundary conditions:
1. Standard 90° orthogonal witness line splitting continuous dimension line.
2. Tilted / isometric witness line (18° tilt / 72° to line).
3. Architectural 45° oblique tick mark slash splitting continuous dimension line.
4. Mechanical acute arrowhead (18° opening angle) at line endpoint.
5. Closed solid filled triangular arrowhead at line endpoint.
6. Repetitive cross-hatch field rejection (45° ANSI section lines).
7. Touching text descender ('p') noise rejection.
8. Multi-span continuous dimension chain with internal witness lines.
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
    run_strategy_b_endpoint,
    run_strategy_b_split,
    run_strategy_c_endpoint,
    run_strategy_c_split,
    run_strategy_d_endpoint,
    run_strategy_d_split,
)


def _canvas(w=400, h=400) -> np.ndarray:
    return np.full((h, w, 3), 255, dtype=np.uint8)


class TestTickMarkBenchmark:
    """Benchmark comparing Strategies A, B, C, D on drafting symbols and noise discrimination."""

    def test_case_1_orthogonal_90deg_witness_line_split(self) -> None:
        """Case 1: Standard 90° orthogonal witness line splitting a continuous dimension line."""
        img = _canvas(400, 300)
        # Main line from (50, 150) to (350, 150)
        cv2.line(img, (50, 150), (350, 150), (0, 0, 0), 2)
        # Perpendicular witness line at x=200 from y=120 to y=180
        cv2.line(img, (200, 120), (200, 180), (0, 0, 0), 2)

        line = make_raw_line((50, 150), (350, 150))

        splits_a = run_strategy_a_split(line, img)
        splits_b = run_strategy_b_split(line, img)
        splits_c = run_strategy_c_split(line, img)
        splits_d = run_strategy_d_split(line, img)

        # Strategy A splits 90° line cleanly
        assert len(splits_a) == 2
        # Strategy B does not support splitting
        assert len(splits_b) == 1
        # Strategy C splits 90° line cleanly
        assert len(splits_c) == 2
        # Strategy D splits 90° line cleanly and precisely at x=200
        assert len(splits_d) == 2
        assert splits_d[0].p2_px[0] == pytest.approx(200.0, abs=4.0)

    def test_case_2_tilted_72deg_isometric_witness_line_split(self) -> None:
        """Case 2: Tilted witness line (18° tilt / 72° to line) due to isometric projection or scan slant."""
        img = _canvas(400, 400)
        cv2.line(img, (50, 150), (350, 150), (0, 0, 0), 2)
        dx = int(round(18 * math.cos(math.radians(72.0))))
        dy = int(round(18 * math.sin(math.radians(72.0))))
        cv2.line(img, (200 - dx, 150 - dy), (200 + dx, 150 + dy), (0, 0, 0), 2)

        line = make_raw_line((50, 150), (350, 150))

        splits_a = run_strategy_a_split(line, img)
        splits_b = run_strategy_b_split(line, img)
        splits_c = run_strategy_c_split(line, img)
        splits_d = run_strategy_d_split(line, img)

        # Strategies A, B, C fail to split due to excessive unrotated column drift
        assert len(splits_a) == 1
        assert len(splits_b) == 1
        assert len(splits_c) == 1
        # Strategy D succeeds
        assert len(splits_d) == 2
        assert splits_d[0].p2_px[0] == pytest.approx(200.0, abs=6.0)

    def test_case_3_architectural_45deg_oblique_tick_split(self) -> None:
        """Case 3: Architectural 45° oblique tick mark slash splitting a dimension chain."""
        img = _canvas(400, 300)
        cv2.line(img, (50, 150), (350, 150), (0, 0, 0), 2)
        # 45° slash at x=200
        cv2.line(img, (192, 158), (208, 142), (0, 0, 0), 2)

        line = make_raw_line((50, 150), (350, 150))

        splits_a = run_strategy_a_split(line, img)
        splits_b = run_strategy_b_split(line, img)
        splits_c = run_strategy_c_split(line, img)
        splits_d = run_strategy_d_split(line, img)

        # Strategies A, B, C reject 45° oblique slashes
        assert len(splits_a) == 1
        assert len(splits_b) == 1
        assert len(splits_c) == 1
        # Strategy D detects oblique slash and splits line
        assert len(splits_d) == 2
        assert splits_d[0].p2_px[0] == pytest.approx(200.0, abs=6.0)

    def test_case_4_acute_arrowhead_at_endpoint(self) -> None:
        """Case 4: Mechanical acute arrowhead (18° opening angle) terminating at endpoint."""
        img = _canvas(300, 300)
        cv2.line(img, (50, 150), (200, 150), (0, 0, 0), 2)
        w1_x = int(round(200 - 18 * math.cos(math.radians(10.0))))
        w1_y = int(round(150 - 18 * math.sin(math.radians(10.0))))
        w2_x = int(round(200 - 18 * math.cos(math.radians(10.0))))
        w2_y = int(round(150 + 18 * math.sin(math.radians(10.0))))
        cv2.line(img, (200, 150), (w1_x, w1_y), (0, 0, 0), 2)
        cv2.line(img, (200, 150), (w2_x, w2_y), (0, 0, 0), 2)

        pt = (200.0, 150.0)
        res_a = run_strategy_a_endpoint(img, pt, ref_angle=0.0)
        res_b = run_strategy_b_endpoint(img, pt, ref_angle=0.0)
        res_c = run_strategy_c_endpoint(img, pt, ref_angle_rad=0.0)
        res_d = run_strategy_d_endpoint(img, pt, ref_angle_rad=0.0)

        # Strategies A, B require angle >= 25° -> fail
        assert res_a.has_boundary is False
        assert res_b.has_boundary is False
        # Strategy C only detects 90° witness -> fails
        assert res_c.has_boundary is False
        # Strategy D detects acute converging arrowhead
        assert res_d.has_boundary is True
        assert res_d.symbol_kind == "ARROWHEAD"

    def test_case_5_solid_filled_arrowhead(self) -> None:
        """Case 5: Solid filled triangular arrowhead (AutoCAD standard _CLOSEDFILLED)."""
        img = _canvas(300, 300)
        cv2.line(img, (50, 150), (200, 150), (0, 0, 0), 2)
        # Draw filled triangle at endpoint (200, 150) pointing right
        pts = np.array([[200, 150], [185, 144], [185, 156]], dtype=np.int32)
        cv2.fillPoly(img, [pts], (0, 0, 0))

        pt = (200.0, 150.0)
        res_a = run_strategy_a_endpoint(img, pt, ref_angle=0.0)
        res_d = run_strategy_d_endpoint(img, pt, ref_angle_rad=0.0)

        # Strategy D detects solid filled arrowhead
        assert res_d.has_boundary is True
        assert res_d.symbol_kind == "ARROWHEAD"

    def test_case_6_repetitive_cross_hatch_rejection(self) -> None:
        """Case 6: Repetitive cross-hatch section lines (45° parallel strokes) do not trigger false ticks."""
        img = _canvas(300, 300)
        cv2.line(img, (50, 150), (150, 150), (0, 0, 0), 2)
        # 4 parallel 45° section lines passing near the endpoint
        for offset in [-20, -10, 0, 10]:
            cv2.line(img, (130 + offset, 170), (170 + offset, 130), (0, 0, 0), 1)

        pt = (150.0, 150.0)
        res_a = run_strategy_a_endpoint(img, pt, ref_angle=0.0)
        res_d = run_strategy_d_endpoint(img, pt, ref_angle_rad=0.0)

        # Strategy A has False Positive (single diagonal segment triggers it)
        assert res_a.has_boundary is True
        # Strategy D rejects repetitive hatch pattern
        assert res_d.has_boundary is False
        assert res_d.symbol_kind == "NONE"

    def test_case_7_touching_text_descender_rejection(self) -> None:
        """Case 7: Touching text descender ('p') must not falsely split continuous dimension line."""
        img = _canvas(400, 300)
        cv2.line(img, (50, 150), (350, 150), (0, 0, 0), 2)
        cv2.rectangle(img, (199, 135), (201, 149), (0, 0, 0), -1)  # stem
        cv2.rectangle(img, (201, 135), (212, 145), (0, 0, 0), -1)  # letter bowl

        line = make_raw_line((50, 150), (350, 150))

        splits_a = run_strategy_a_split(line, img)
        splits_d = run_strategy_d_split(line, img)

        # Strategy A falsely splits on text stem
        assert len(splits_a) >= 2
        # Strategy D identifies 2D text component and preserves line intact
        assert len(splits_d) == 1

    def test_case_8_three_span_continuous_dimension_chain(self) -> None:
        """Case 8: Continuous dimension chain with 2 internal witness lines dividing into 3 spans."""
        img = _canvas(500, 300)
        # Long continuous line from (50, 150) to (450, 150) (length = 400px)
        cv2.line(img, (50, 150), (450, 150), (0, 0, 0), 2)
        # Internal witness line 1 at x=150 (span 1 = 100px)
        cv2.line(img, (150, 120), (150, 180), (0, 0, 0), 2)
        # Internal witness line 2 at x=300 (span 2 = 150px, span 3 = 150px)
        cv2.line(img, (300, 120), (300, 180), (0, 0, 0), 2)

        line = make_raw_line((50, 150), (450, 150))

        splits_d = run_strategy_d_split(line, img)

        assert len(splits_d) == 3
        # Check span 1 endpoint
        assert splits_d[0].p2_px[0] == pytest.approx(150.0, abs=4.0)
        # Check span 2 endpoint
        assert splits_d[1].p2_px[0] == pytest.approx(300.0, abs=4.0)
        # Check span 3 endpoints
        assert splits_d[2].p1_px[0] == pytest.approx(300.0, abs=4.0)
        assert splits_d[2].p2_px[0] == pytest.approx(450.0, abs=4.0)
