"""
test_table_extraction_benchmark.py — Systematic Comparison of Strategies A, B, C, D.

Empirically benchmarks 4 strategies across 7 representative table topologies:
1. Regular uniform 3x4 grid
2. Dense BOM table with closely spaced columns (10px spacing)
3. Title block with horizontally merged header row (1 header + 2x4 cells = 9 cells)
4. Specification table with vertically merged multi-row cell (1 span-3 cell + 6 cells = 7 cells)
5. Table with interior text underline noise (short 15px horizontal line)
6. Asymmetric border overshoots (lines extending beyond corners)
7. Complex composite table with both horizontal and vertical merged cells
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
    run_strategy_a,
    run_strategy_b,
    run_strategy_c,
    run_strategy_d,
)


class TestTableExtractionBenchmark:
    """Benchmark suite evaluating Strategies A, B, C, D across engineering drawing table topologies."""

    def test_case_1_regular_uniform_3x4_grid(self) -> None:
        """Case 1: Standard 3 rows x 4 columns table (12 equal cells)."""
        roi = (0.0, 0.0, 400.0, 300.0)
        # Vertical dividers at x = 0, 100, 200, 300, 400
        # Horizontal dividers at y = 0, 100, 200, 300
        lines = []
        for x in [0.0, 100.0, 200.0, 300.0, 400.0]:
            lines.append(make_raw_line((x, 0.0), (x, 300.0)))
        for y in [0.0, 100.0, 200.0, 300.0]:
            lines.append(make_raw_line((0.0, y), (400.0, y)))

        res_a = run_strategy_a(lines, roi)
        res_b = run_strategy_b(lines, roi)
        res_c = run_strategy_c(lines, roi)
        res_d = run_strategy_d(lines, roi)

        assert res_a.has_valid_table and len(res_a.cells) == 12
        assert res_b.has_valid_table and len(res_b.cells) == 12
        assert res_c.has_valid_table and len(res_c.cells) == 12
        assert res_d.has_valid_table and len(res_d.cells) == 12
        assert all(not c.is_merged for c in res_d.cells)

    def test_case_2_closely_spaced_columns_dense_bom(self) -> None:
        """Case 2: Dense BOM table where column dividers are 10px apart.
        Strategy A collapses columns under default merge_tol=12.
        Strategies B, C, D resolve dense columns correctly.
        """
        roi = (50.0, 50.0, 250.0, 150.0)
        # Columns at 50, 60, 70, 80, 250 (e.g. Item No, Qty, Rev, Status, Description)
        xs = [50.0, 60.0, 70.0, 80.0, 250.0]
        # Rows at 50, 100, 150
        ys = [50.0, 100.0, 150.0]

        lines = []
        for x in xs:
            lines.append(make_raw_line((x, 50.0), (x, 150.0)))
        for y in ys:
            lines.append(make_raw_line((50.0, y), (250.0, y)))

        res_a = run_strategy_a(lines, roi, merge_tol=12.0)
        res_b = run_strategy_b(lines, roi)
        res_c = run_strategy_c(lines, roi)
        res_d = run_strategy_d(lines, roi, cluster_radius_px=4.0)

        # Strategy A collapses 50, 60, 70, 80 into single cluster -> only 2 xs -> 1 col x 2 rows = 2 cells
        assert len(res_a.grid_xs) < len(xs)
        assert len(res_a.cells) < 8

        # Strategies B, C, D preserve all 5 columns -> 4 cols x 2 rows = 8 cells
        assert len(res_b.grid_xs) == 5
        assert len(res_b.cells) == 8
        assert len(res_c.cells) == 8
        assert len(res_d.cells) == 8

    def test_case_3_title_block_with_merged_header(self) -> None:
        """Case 3: Title block with 1 merged header spanning 4 columns, followed by 2 rows of 4 columns.
        Expected topology: 1 header cell + 8 data cells = 9 cells.
        Strategy A, B, C fracture header into 4 micro-cells (12 total cells).
        Strategy D preserves 9 cells with 1 merged cell.
        """
        roi = (0.0, 0.0, 400.0, 150.0)
        # Outer boundary
        lines = [
            make_raw_line((0.0, 0.0), (400.0, 0.0)),      # top border
            make_raw_line((0.0, 150.0), (400.0, 150.0)),  # bottom border
            make_raw_line((0.0, 0.0), (0.0, 150.0)),      # left border
            make_raw_line((400.0, 0.0), (400.0, 150.0)),  # right border
            # Horizontal divider between header and data rows at y = 50
            make_raw_line((0.0, 50.0), (400.0, 50.0)),
            # Horizontal divider between row 1 and row 2 at y = 100
            make_raw_line((0.0, 100.0), (400.0, 100.0)),
            # Vertical dividers ONLY in rows 1 and 2 (y in [50, 150]), NOT in header (y in [0, 50])
            make_raw_line((100.0, 50.0), (100.0, 150.0)),
            make_raw_line((200.0, 50.0), (200.0, 150.0)),
            make_raw_line((300.0, 50.0), (300.0, 150.0)),
        ]

        res_a = run_strategy_a(lines, roi)
        res_b = run_strategy_b(lines, roi)
        res_c = run_strategy_c(lines, roi)
        res_d = run_strategy_d(lines, roi)

        # Rigid Cartesian product creates 3 rows x 4 cols = 12 cells
        assert len(res_a.cells) == 12
        assert len(res_b.cells) == 12
        assert len(res_c.cells) == 12

        # Strategy D forms 9 cells: 1 merged header + 8 regular cells
        assert len(res_d.cells) == 9
        merged_cells = [c for c in res_d.cells if c.is_merged]
        assert len(merged_cells) == 1
        header = merged_cells[0]
        assert header.row_start == 0 and header.row_end == 1
        assert header.col_start == 0 and header.col_end == 4

    def test_case_4_multi_row_span_cell(self) -> None:
        """Case 4: Left column spans across 3 rows (e.g. 'PART NUMBER' category),
        while right column is subdivided into 3 rows.
        Expected: 1 merged cell spanning rows 0..3 + 3 row cells in right column = 4 cells.
        """
        roi = (0.0, 0.0, 200.0, 300.0)
        lines = [
            # Outer box
            make_raw_line((0.0, 0.0), (200.0, 0.0)),
            make_raw_line((0.0, 300.0), (200.0, 300.0)),
            make_raw_line((0.0, 0.0), (0.0, 300.0)),
            make_raw_line((200.0, 0.0), (200.0, 300.0)),
            # Vertical column divider between col 0 and col 1 across full height
            make_raw_line((80.0, 0.0), (80.0, 300.0)),
            # Horizontal dividers ONLY in col 1 (x in [80, 200]), NOT in col 0 (x in [0, 80])
            make_raw_line((80.0, 100.0), (200.0, 100.0)),
            make_raw_line((80.0, 200.0), (200.0, 200.0)),
        ]

        res_a = run_strategy_a(lines, roi)
        res_d = run_strategy_d(lines, roi)

        # Strategy A creates 3 rows x 2 cols = 6 cells
        assert len(res_a.cells) == 6

        # Strategy D creates 1 multi-row cell + 3 single cells = 4 cells
        assert len(res_d.cells) == 4
        merged_cells = [c for c in res_d.cells if c.is_merged]
        assert len(merged_cells) == 1
        span_cell = merged_cells[0]
        assert span_cell.col_start == 0 and span_cell.col_end == 1
        assert span_cell.row_start == 0 and span_cell.row_end == 3

    def test_case_5_interior_text_underline_noise(self) -> None:
        """Case 5: Table cell contains a short 20px underline beneath cell text.
        Strategy A treats it as a row divider across the entire table.
        Strategy D rejects it from splitting columns because it doesn't span across column boundaries.
        """
        roi = (0.0, 0.0, 200.0, 200.0)
        # 2x2 grid
        lines = [
            make_raw_line((0.0, 0.0), (200.0, 0.0)),
            make_raw_line((0.0, 100.0), (200.0, 100.0)),
            make_raw_line((0.0, 200.0), (200.0, 200.0)),
            make_raw_line((0.0, 0.0), (0.0, 200.0)),
            make_raw_line((100.0, 0.0), (100.0, 200.0)),
            make_raw_line((200.0, 0.0), (200.0, 200.0)),
            # Short underline inside cell (row 0, col 0): x in [20, 50], y = 70
            make_raw_line((20.0, 70.0), (50.0, 70.0)),
        ]

        res_a = run_strategy_a(lines, roi)
        res_d = run_strategy_d(lines, roi)

        # Strategy A splits y into 4 coordinates (0, 70, 100, 200) -> 3 rows x 2 cols = 6 cells
        assert len(res_a.grid_ys) == 4
        assert len(res_a.cells) == 6

        # Strategy D: y=70 has a short segment that does NOT span column 0 (0..100) or column 1 (100..200).
        # Thus the cells remain 4 cells!
        assert len(res_d.cells) == 4

    def test_case_6_asymmetric_border_overshoots(self) -> None:
        """Case 6: Border lines extend 30px past the corner.
        Strategy A: Midpoint of overshooting border can fall outside ROI, dropping the boundary.
        Strategy D: Line span overlap correctly retains boundary coordinates.
        """
        roi = (100.0, 100.0, 300.0, 300.0)
        # Top border extends from 70 to 330 at y = 100
        # Bottom border extends from 100 to 300 at y = 300
        # Left border extends from 100 to 300 at x = 100
        # Right border extends from 100 to 300 at x = 300
        # Mid divider at x = 200, y = 200
        lines = [
            make_raw_line((70.0, 100.0), (330.0, 100.0)),
            make_raw_line((100.0, 300.0), (300.0, 300.0)),
            make_raw_line((100.0, 100.0), (100.0, 300.0)),
            make_raw_line((300.0, 100.0), (300.0, 300.0)),
            make_raw_line((200.0, 100.0), (200.0, 300.0)),
            make_raw_line((100.0, 200.0), (300.0, 200.0)),
        ]

        res_d = run_strategy_d(lines, roi)
        assert res_d.has_valid_table
        assert len(res_d.cells) == 4
        assert 100.0 in res_d.grid_xs and 300.0 in res_d.grid_xs
        assert 100.0 in res_d.grid_ys and 300.0 in res_d.grid_ys

    def test_case_7_composite_complex_title_block(self) -> None:
        """Case 7: Complex title block with:
        - Row 0: Merged header across col 0..2
        - Row 1: Col 0 (TITLE), Col 1 (DWG NO), Col 2 (REV)
        - Row 2: Col 0 (AUTHOR), Col 1 (DATE), Col 2 spans Rows 1 and 2 (merged vertically)
        """
        roi = (0.0, 0.0, 300.0, 150.0)
        # xs = 0, 100, 200, 300
        # ys = 0, 50, 100, 150
        lines = [
            # Outer box
            make_raw_line((0.0, 0.0), (300.0, 0.0)),
            make_raw_line((0.0, 150.0), (300.0, 150.0)),
            make_raw_line((0.0, 0.0), (0.0, 150.0)),
            make_raw_line((300.0, 0.0), (300.0, 150.0)),
            # Row 0 to Row 1 divider at y = 50 across full width
            make_raw_line((0.0, 50.0), (300.0, 50.0)),
            # Row 1 to Row 2 divider at y = 100 ONLY in cols 0 and 1 (x in [0, 200])
            make_raw_line((0.0, 100.0), (200.0, 100.0)),
            # Col dividers:
            # Between col 0 and 1 at x = 100 in rows 1 and 2 (y in [50, 150])
            make_raw_line((100.0, 50.0), (100.0, 150.0)),
            # Between col 1 and 2 at x = 200 in rows 1 and 2 (y in [50, 150])
            make_raw_line((200.0, 50.0), (200.0, 150.0)),
        ]

        res_d = run_strategy_d(lines, roi)
        assert res_d.has_valid_table
        # Expected cells:
        # 1. Header (row 0, col 0..3) -> merged
        # 2. Row 1, Col 0
        # 3. Row 1, Col 1
        # 4. Row 2, Col 0
        # 5. Row 2, Col 1
        # 6. Col 2 spanning Rows 1..3 (row 1,2, col 2) -> merged vertically
        # Total cells = 6 cells (2 merged, 4 regular)
        assert len(res_d.cells) == 6
        merged_cells = [c for c in res_d.cells if c.is_merged]
        assert len(merged_cells) == 2
