"""
test_view_partitioning_controls.py — Positive Fixtures and Strong Negative Controls for View Partitioning.

Rigorous negative controls ensuring zero false views on non-view entities:
1. Isolated sheet margin border frame (0 views emitted)
2. Column of general drawing notes text without geometry (0 views emitted)
3. Scattered alignment ticks and registration marks (0 views emitted)
4. Title block metadata table alone without drawing views (0 views emitted)

Positive fixtures verifying extraction on standard drawing formats:
5. Standard A3 sheet with sheet margin, title block, and 2 orthographic views
6. 3-view assembly with General View, Section View, and Detail Circle
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from view_partitioning_engine import (
    make_test_line,
    make_test_text,
    run_strategy_d,
)


class TestViewPartitioningControls:
    """Controls testing false positive rejection and true positive fidelity."""

    # -------------------------------------------------------------------------
    # Negative Controls
    # -------------------------------------------------------------------------

    def test_negative_control_isolated_drawing_border_frame(self) -> None:
        """Negative Control 1: Empty drawing with only page perimeter margin lines."""
        lines = [
            make_test_line((10, 10), (1390, 10)),
            make_test_line((10, 890), (1390, 890)),
            make_test_line((10, 10), (10, 890)),
            make_test_line((1390, 10), (1390, 890)),
        ]
        res = run_strategy_d([], lines, 1400, 900, 144)
        assert res.has_valid_partition is False
        assert len(res.views) == 0
        assert res.border_bbox_px is not None

    def test_negative_control_general_notes_text_column(self) -> None:
        """Negative Control 2: Text notes column on left side of sheet without geometry lines."""
        texts = [
            make_test_text("GENERAL NOTES:", (50, 100, 200, 120), "n1"),
            make_test_text("1. ALL DIMENSIONS ARE IN MM.", (50, 130, 300, 150), "n2"),
            make_test_text("2. REMOVE ALL BURRS AND SHARP EDGES.", (50, 160, 350, 180), "n3"),
            make_test_text("3. MATERIAL: AISI 304 STAINLESS STEEL.", (50, 190, 370, 210), "n4"),
        ]
        res = run_strategy_d(texts, [], 1400, 900, 144)
        assert res.has_valid_partition is False
        assert len(res.views) == 0

    def test_negative_control_scattered_registration_marks(self) -> None:
        """Negative Control 3: Small isolated alignment ticks / registration crosses."""
        lines = [
            # Cross 1 at (20, 20)
            make_test_line((15, 20), (25, 20)),
            make_test_line((20, 15), (20, 25)),
            # Cross 2 at (1380, 20)
            make_test_line((1375, 20), (1385, 20)),
            make_test_line((1380, 15), (1380, 25)),
        ]
        res = run_strategy_d([], lines, 1400, 900, 144)
        # Small marks (< 15px) filtered out -> 0 views
        assert res.has_valid_partition is False
        assert len(res.views) == 0

    def test_negative_control_title_block_only_sheet(self) -> None:
        """Negative Control 4: Title block in bottom-right corner without any part views."""
        lines = [
            # Title block in bottom-right (x in [950, 1380], y in [700, 880])
            make_test_line((950, 700), (1380, 700)),
            make_test_line((950, 880), (1380, 880)),
            make_test_line((950, 700), (950, 880)),
            make_test_line((1380, 700), (1380, 880)),
            make_test_line((950, 760), (1380, 760)),
            make_test_line((1150, 700), (1150, 880)),
        ]
        res = run_strategy_d([], lines, 1400, 900, 144)
        # Classified into table_bboxes_px, 0 views emitted
        assert res.has_valid_partition is False
        assert len(res.views) == 0
        assert len(res.table_bboxes_px) == 1

    # -------------------------------------------------------------------------
    # Positive Fixtures
    # -------------------------------------------------------------------------

    def test_positive_fixture_standard_two_view_a3_drawing(self) -> None:
        """Positive Fixture 1: Standard A3 drawing with border, title block, and 2 views."""
        # 1600 x 1000 page
        border_lines = [
            make_test_line((10, 10), (1590, 10)),
            make_test_line((10, 990), (1590, 990)),
            make_test_line((10, 10), (10, 990)),
            make_test_line((1590, 10), (1590, 990)),
        ]
        title_lines = [
            make_test_line((1100, 750), (1580, 750)),
            make_test_line((1100, 980), (1580, 980)),
            make_test_line((1100, 750), (1100, 980)),
            make_test_line((1580, 750), (1580, 980)),
        ]
        # Front View: [150, 150, 550, 450]
        v1_lines = [
            make_test_line((150, 150), (550, 150)),
            make_test_line((150, 450), (550, 450)),
            make_test_line((150, 150), (150, 450)),
            make_test_line((550, 150), (550, 450)),
        ]
        # Top View: [150, 550, 550, 850]
        v2_lines = [
            make_test_line((150, 550), (550, 550)),
            make_test_line((150, 850), (550, 850)),
            make_test_line((150, 550), (150, 850)),
            make_test_line((550, 550), (550, 850)),
        ]
        l1 = make_test_text("TL 1:1", (300, 470, 400, 490), "lbl-front")
        l2 = make_test_text("TL 1:1", (300, 870, 400, 890), "lbl-top")

        res = run_strategy_d([l1, l2], border_lines + title_lines + v1_lines + v2_lines, 1600, 1000, 144)
        assert res.has_valid_partition is True
        assert res.confidence >= 0.90
        assert len(res.views) == 2
        assert len(res.table_bboxes_px) == 1
        assert res.border_bbox_px is not None

    def test_positive_fixture_section_and_detail_views(self) -> None:
        """Positive Fixture 2: 3-view assembly with General (1:10), Section A-A (1:5), Detail B (1:2)."""
        # General View: [100, 100, 500, 400]
        v1_lines = [
            make_test_line((100, 100), (500, 100)),
            make_test_line((100, 400), (500, 400)),
            make_test_line((100, 100), (100, 400)),
            make_test_line((500, 100), (500, 400)),
        ]
        # Section A-A: [100, 480, 500, 780]
        v2_lines = [
            make_test_line((100, 480), (500, 480)),
            make_test_line((100, 780), (500, 780)),
            make_test_line((100, 480), (100, 780)),
            make_test_line((500, 480), (500, 780)),
        ]
        # Detail B: [650, 100, 950, 400]
        v3_lines = [
            make_test_line((650, 100), (950, 100)),
            make_test_line((650, 400), (950, 400)),
            make_test_line((650, 100), (650, 400)),
            make_test_line((950, 100), (950, 400)),
        ]
        l1 = make_test_text("TL 1:10", (250, 420, 350, 440), "l-gen")
        l2 = make_test_text("TL 1:5", (250, 800, 350, 820), "l-sec")
        l3 = make_test_text("TL 1:2", (750, 420, 850, 440), "l-det")

        res = run_strategy_d([l1, l2, l3], v1_lines + v2_lines + v3_lines, 1400, 900, 144)
        assert res.has_valid_partition is True
        assert len(res.views) == 3
        assert len(res.unassigned_text_ids) == 0

        denoms = {v.scale_denominator for v in res.views}
        assert denoms == {10, 5, 2}
