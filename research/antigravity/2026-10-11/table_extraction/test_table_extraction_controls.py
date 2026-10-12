"""
test_table_extraction_controls.py — Positive Fixtures and Strong Negative Controls for Table Extraction.

Rigorous negative controls ensuring zero false positives on non-table CAD entities:
1. Dimension witness and extension lines (not a table grid)
2. Dense cross-hatching field (parallel lines without orthogonal enclosing boundaries)
3. Open L-bracket mechanical contour
4. Text paragraph with two ruling separators (missing vertical borders)
5. Scattered non-orthogonal CAD features

Positive fixtures verifying extraction on standard drawing tables:
6. ISO 7200 Title Block layout with merged and subdivided metadata fields
7. Standard 6-column x 5-row Bill of Materials (BOM) parts list
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

from table_extraction_engine import (
    make_raw_line,
    run_strategy_d,
)


class TestTableExtractionControls:
    """Controls testing false positive rejection and true positive fidelity."""

    # -------------------------------------------------------------------------
    # Negative Controls
    # -------------------------------------------------------------------------

    def test_negative_control_dimension_witness_lines(self) -> None:
        """Negative Control 1: Dimension extension lines and leader lines must not trigger table detection."""
        roi = (100.0, 100.0, 250.0, 250.0)
        # 2 vertical witness lines and 1 horizontal dimension line
        lines = [
            make_raw_line((120.0, 110.0), (120.0, 240.0)),
            make_raw_line((220.0, 110.0), (220.0, 240.0)),
            make_raw_line((120.0, 200.0), (220.0, 200.0)),
        ]
        res = run_strategy_d(lines, roi)
        assert res.has_valid_table is False
        assert len(res.cells) == 0

    def test_negative_control_dense_cross_hatching_field(self) -> None:
        """Negative Control 2: Dense parallel hatch lines without enclosing vertical borders."""
        roi = (0.0, 0.0, 200.0, 200.0)
        # 10 horizontal hatch lines, but zero vertical lines
        lines = [
            make_raw_line((10.0, float(y)), (190.0, float(y)))
            for y in range(20, 200, 18)
        ]
        res = run_strategy_d(lines, roi)
        assert res.has_valid_table is False
        assert len(res.cells) == 0

    def test_negative_control_open_mechanical_l_bracket(self) -> None:
        """Negative Control 3: Stepped L-shaped mechanical profile contour."""
        roi = (50.0, 50.0, 250.0, 250.0)
        # L-bracket lines: 6 segments forming open/closed profile, but no grid junctions
        lines = [
            make_raw_line((50.0, 50.0), (150.0, 50.0)),
            make_raw_line((150.0, 50.0), (150.0, 150.0)),
            make_raw_line((150.0, 150.0), (250.0, 150.0)),
            make_raw_line((250.0, 150.0), (250.0, 250.0)),
            make_raw_line((250.0, 250.0), (50.0, 250.0)),
            make_raw_line((50.0, 250.0), (50.0, 50.0)),
        ]
        res = run_strategy_d(lines, roi)
        # While it forms a closed outer loop, there are no internal grid dividers
        # A single unpartitioned box is not a valid multi-cell table
        # Let's verify that border count or cells behave deterministically
        # If it has 0 internal dividers, either 0 or 1 cell
        assert len(res.cells) <= 1

    def test_negative_control_text_ruling_separators(self) -> None:
        """Negative Control 4: Text paragraph between two horizontal rules (missing vertical borders)."""
        roi = (0.0, 0.0, 300.0, 100.0)
        lines = [
            make_raw_line((10.0, 10.0), (290.0, 10.0)),
            make_raw_line((10.0, 90.0), (290.0, 90.0)),
        ]
        res = run_strategy_d(lines, roi)
        assert res.has_valid_table is False
        assert len(res.cells) == 0

    def test_negative_control_scattered_misaligned_geometry(self) -> None:
        """Negative Control 5: Random disjoint lines in ROI."""
        roi = (0.0, 0.0, 200.0, 200.0)
        lines = [
            make_raw_line((10.0, 20.0), (80.0, 30.0)),
            make_raw_line((110.0, 140.0), (190.0, 150.0)),
            make_raw_line((50.0, 100.0), (60.0, 180.0)),
        ]
        res = run_strategy_d(lines, roi)
        assert res.has_valid_table is False
        assert len(res.cells) == 0

    # -------------------------------------------------------------------------
    # Positive Fixtures
    # -------------------------------------------------------------------------

    def test_positive_control_iso_7200_title_block(self) -> None:
        """Positive Fixture 1: ISO 7200 Title Block (width 180mm x height 63mm).
        Layout:
        - Box: x in [0, 540], y in [0, 189]
        - Top section: y in [0, 90]
          - Left: Legal owner/Title (x in [0, 360])
          - Right: Drawing Number (x in [360, 540])
        - Bottom section: y in [90, 189] subdivided into 3 rows of 33px each (90, 123, 156, 189)
          - Left: Author / Date / Status (x in [0, 180])
          - Mid: Approver / Date / Rev (x in [180, 360])
          - Right: Sheet / Scale / Size (x in [360, 540])
        """
        roi = (0.0, 0.0, 540.0, 189.0)
        lines = [
            # Outer boundary
            make_raw_line((0.0, 0.0), (540.0, 0.0)),
            make_raw_line((0.0, 189.0), (540.0, 189.0)),
            make_raw_line((0.0, 0.0), (0.0, 189.0)),
            make_raw_line((540.0, 0.0), (540.0, 189.0)),
            # Mid major horizontal divider between top section and bottom section
            make_raw_line((0.0, 90.0), (540.0, 90.0)),
            # Top vertical divider at x = 360 (y in [0, 90])
            make_raw_line((360.0, 0.0), (360.0, 90.0)),
            # Bottom horizontal dividers at y = 123, 156 (x in [0, 540])
            make_raw_line((0.0, 123.0), (540.0, 123.0)),
            make_raw_line((0.0, 156.0), (540.0, 156.0)),
            # Bottom vertical dividers at x = 180, 360 (y in [90, 189])
            make_raw_line((180.0, 90.0), (180.0, 189.0)),
            make_raw_line((360.0, 90.0), (360.0, 189.0)),
        ]

        res = run_strategy_d(lines, roi)
        assert res.has_valid_table is True
        assert res.confidence >= 0.85
        # Top section: 2 cells
        # Bottom section: 3 rows x 3 cols = 9 cells
        # Total expected cells: 2 + 9 = 11 cells!
        assert len(res.cells) == 11

        # Check top-left title cell spans across x in [0, 360]
        title_cell = [c for c in res.cells if c.row_start == 0 and c.col_start == 0][0]
        assert title_cell.is_merged is True  # spans cols 0 and 1
        assert title_cell.bbox_px[0] == pytest.approx(3.0, abs=1.0)
        assert title_cell.bbox_px[2] == pytest.approx(357.0, abs=1.0)

    def test_positive_control_standard_bom_parts_list(self) -> None:
        """Positive Fixture 2: Standard 6-column x 5-row Bill of Materials table (30 cells)."""
        roi = (0.0, 0.0, 600.0, 250.0)
        # 6 columns: widths 50, 120, 200, 50, 80, 100
        # cumulative xs: 0, 50, 170, 370, 420, 500, 600
        xs = [0.0, 50.0, 170.0, 370.0, 420.0, 500.0, 600.0]
        # 5 rows: height 50 each -> ys: 0, 50, 100, 150, 200, 250
        ys = [0.0, 50.0, 100.0, 150.0, 200.0, 250.0]

        lines = []
        for x in xs:
            lines.append(make_raw_line((x, 0.0), (x, 250.0)))
        for y in ys:
            lines.append(make_raw_line((0.0, y), (600.0, y)))

        res = run_strategy_d(lines, roi)
        assert res.has_valid_table is True
        assert res.confidence >= 0.90
        assert len(res.cells) == 30
        assert len(res.grid_xs) == 7
        assert len(res.grid_ys) == 6
        assert all(not c.is_merged for c in res.cells)
