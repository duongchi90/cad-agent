"""
test_tick_mark_controls.py — Positive Fixtures and Strong Negative Controls for Boundary Symbol Detection.

Strong Negative Controls:
1. Plain isolated line segment (0 splits, has_boundary=False)
2. Dense cross-hatch section field (0 splits, has_boundary=False)
3. Parallel track lines (0 splits, has_boundary=False)
4. Touching dimension text block "125.50" (0 splits, has_boundary=False)
5. 90° contour corner L-junction at endpoint (not an arrowhead/tick mark)

Positive Fixtures:
6. 4-span architectural dimension chain with 45° oblique tick marks
7. Stepped shaft mechanical dimension chain with orthogonal witness lines
8. Dimension line with solid filled arrowheads at both endpoints
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
    run_strategy_d_endpoint,
    run_strategy_d_split,
)


def _canvas(w=500, h=400) -> np.ndarray:
    return np.full((h, w, 3), 255, dtype=np.uint8)


class TestTickMarkControls:
    """Controls testing false positive rejection and true positive fidelity."""

    # -------------------------------------------------------------------------
    # Negative Controls
    # -------------------------------------------------------------------------

    def test_negative_control_plain_line_segment(self) -> None:
        """Negative Control 1: Plain isolated line segment with no marks or crossings."""
        img = _canvas(300, 300)
        cv2.line(img, (50, 150), (250, 150), (0, 0, 0), 2)

        line = make_raw_line((50, 150), (250, 150))
        splits = run_strategy_d_split(line, img)

        assert len(splits) == 1
        res_start = run_strategy_d_endpoint(img, (50.0, 150.0), 0.0)
        res_end = run_strategy_d_endpoint(img, (250.0, 150.0), 0.0)
        assert res_start.has_boundary is False
        assert res_end.has_boundary is False

    def test_negative_control_dense_cross_hatch_field(self) -> None:
        """Negative Control 2: Dense 45° cross-hatch section field (6 parallel lines)."""
        img = _canvas(400, 400)
        cv2.line(img, (50, 200), (350, 200), (0, 0, 0), 2)
        # 6 parallel hatch lines spaced by 12px
        for offset in range(-36, 48, 12):
            cv2.line(img, (150 + offset, 240), (230 + offset, 160), (0, 0, 0), 1)

        line = make_raw_line((50, 200), (350, 200))
        splits = run_strategy_d_split(line, img)

        # Repetitive cross-hatching must NOT slice dimension line
        assert len(splits) == 1

        res = run_strategy_d_endpoint(img, (200.0, 200.0), 0.0)
        assert res.has_boundary is False

    def test_negative_control_parallel_tracks(self) -> None:
        """Negative Control 3: Parallel line running alongside candidate dimension line."""
        img = _canvas(400, 300)
        cv2.line(img, (50, 150), (350, 150), (0, 0, 0), 2)
        # Parallel track 15px above
        cv2.line(img, (50, 135), (350, 135), (0, 0, 0), 2)

        line = make_raw_line((50, 150), (350, 150))
        splits = run_strategy_d_split(line, img)
        assert len(splits) == 1

    def test_negative_control_touching_dimension_text_block(self) -> None:
        """Negative Control 4: Text string '125.50' sitting 2px above dimension line."""
        img = _canvas(400, 300)
        cv2.line(img, (50, 150), (350, 150), (0, 0, 0), 2)
        # Render text characters near the line
        cv2.putText(img, "125.50", (160, 146), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        line = make_raw_line((50, 150), (350, 150))
        splits = run_strategy_d_split(line, img)

        # Text touching or hovering above line must not cause false internal splits
        assert len(splits) == 1

    def test_negative_control_right_angle_contour_corner(self) -> None:
        """Negative Control 5: Right-angle corner of part contour at endpoint."""
        img = _canvas(300, 300)
        # Horizontal contour meeting vertical contour at (200, 150)
        cv2.line(img, (50, 150), (200, 150), (0, 0, 0), 2)
        cv2.line(img, (200, 150), (200, 250), (0, 0, 0), 2)

        # Single perpendicular turn at endpoint is not an arrowhead
        res = run_strategy_d_endpoint(img, (200.0, 150.0), 0.0)
        assert res.symbol_kind != "ARROWHEAD"

    # -------------------------------------------------------------------------
    # Positive Fixtures
    # -------------------------------------------------------------------------

    def test_positive_fixture_architectural_dimension_chain(self) -> None:
        """Positive Fixture 6: 4-span architectural dimension chain divided by 45° oblique slashes."""
        img = _canvas(600, 300)
        # Continuous dimension line from (50, 150) to (550, 150) (length = 500px)
        cv2.line(img, (50, 150), (550, 150), (0, 0, 0), 2)

        # 3 internal 45° oblique tick marks at x = 175, 300, 425
        tick_offsets = [175, 300, 425]
        for x_tick in tick_offsets:
            cv2.line(img, (x_tick - 8, 158), (x_tick + 8, 142), (0, 0, 0), 2)

        line = make_raw_line((50, 150), (550, 150))
        splits = run_strategy_d_split(line, img)

        # 3 internal ticks produce 4 continuous spans
        assert len(splits) == 4
        # Verify split points
        assert splits[0].p2_px[0] == pytest.approx(175.0, abs=5.0)
        assert splits[1].p2_px[0] == pytest.approx(300.0, abs=5.0)
        assert splits[2].p2_px[0] == pytest.approx(425.0, abs=5.0)
        assert splits[3].p2_px[0] == pytest.approx(550.0, abs=5.0)

    def test_positive_fixture_mechanical_shaft_dimension_chain(self) -> None:
        """Positive Fixture 7: Mechanical stepped shaft chain with 2 orthogonal witness lines."""
        img = _canvas(600, 300)
        cv2.line(img, (60, 150), (540, 150), (0, 0, 0), 2)

        # Witness lines at x=200 and x=380 extending symmetrically across the line
        cv2.line(img, (200, 115), (200, 185), (0, 0, 0), 2)
        cv2.line(img, (380, 115), (380, 185), (0, 0, 0), 2)

        line = make_raw_line((60, 150), (540, 150))
        splits = run_strategy_d_split(line, img)

        assert len(splits) == 3
        assert splits[0].p2_px[0] == pytest.approx(200.0, abs=4.0)
        assert splits[1].p2_px[0] == pytest.approx(380.0, abs=4.0)

    def test_positive_fixture_solid_filled_arrow_endpoints(self) -> None:
        """Positive Fixture 8: Dimension line with solid filled arrows at both ends."""
        img = _canvas(400, 300)
        cv2.line(img, (100, 150), (300, 150), (0, 0, 0), 2)

        # Left arrow at (100, 150) pointing left
        left_tri = np.array([[100, 150], [115, 144], [115, 156]], dtype=np.int32)
        cv2.fillPoly(img, [left_tri], (0, 0, 0))

        # Right arrow at (300, 150) pointing right
        right_tri = np.array([[300, 150], [285, 144], [285, 156]], dtype=np.int32)
        cv2.fillPoly(img, [right_tri], (0, 0, 0))

        # Left endpoint points along line (+x, angle=0)
        res_left = run_strategy_d_endpoint(img, (100.0, 150.0), 0.0)
        # Right endpoint points along line (-x, angle=pi)
        res_right = run_strategy_d_endpoint(img, (300.0, 150.0), math.pi)

        assert res_left.has_boundary is True
        assert res_left.symbol_kind == "ARROWHEAD"
        assert res_right.has_boundary is True
        assert res_right.symbol_kind == "ARROWHEAD"
