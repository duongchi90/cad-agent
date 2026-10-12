"""
test_causal_red_table_extraction.py — Public Causal RED Benchmarks for Table Cell Grid Extraction.

Proves the 5 structural failure modes in Strategy A (primitive_ir_lib/table_extraction.py):
1. RED 1: Single-linkage chaining collapse on closely spaced columns (100% loss of cells).
2. RED 2: Midpoint-only filtering drops valid boundary lines with asymmetric overshoots.
3. RED 3: Merged header cell fragmented into micro-cells under rigid MxN Cartesian product.
4. RED 4: Short interior text underline splits all columns across the entire table.
5. RED 5: Scattered non-table CAD lines falsely accepted as table cells.

All 5 fail under Strategy A and pass under Strategy D.
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
    run_strategy_d,
)


class TestCausalRedTableExtraction:
    """Causal RED suite confirming production Strategy A defects and Strategy D resolution."""

    def test_red_1_single_linkage_chaining_collapse(self) -> None:
        """RED 1: Closely spaced columns (10px spacing with merge_tol=12) collapse into 1 coordinate."""
        # 4 vertical columns spaced 10px apart: x = 100, 110, 120, 130 spanning y = 50 to 150
        lines = [
            make_raw_line((100, 50), (100, 150)),
            make_raw_line((110, 50), (110, 150)),
            make_raw_line((120, 50), (120, 150)),
            make_raw_line((130, 50), (130, 150)),
            # Top and bottom horizontal boundary lines
            make_raw_line((100, 50), (130, 50)),
            make_raw_line((100, 150), (130, 150)),
        ]
        roi = (100.0, 50.0, 130.0, 150.0)

        # Strategy A fails: 100, 110, 120, 130 chain into 1 cluster -> xs has length 1 -> 0 cells!
        res_a = run_strategy_a(lines, roi, merge_tol=12.0)
        assert len(res_a.grid_xs) == 1, f"Expected Strategy A to collapse columns, got xs: {res_a.grid_xs}"
        assert len(res_a.cells) == 0, "Strategy A produced 0 cells due to chaining collapse"

        # Strategy D succeeds: centroid-guarded clustering preserves all 4 column dividers
        res_d = run_strategy_d(lines, roi, cluster_radius_px=5.0)
        assert len(res_d.grid_xs) == 4
        assert len(res_d.cells) == 3

    def test_red_2_midpoint_boundary_drop(self) -> None:
        """RED 2: Midpoint-only filtering drops valid boundary line with asymmetrical overshoot."""
        roi = (50.0, 100.0, 250.0, 300.0)
        lines = [
            # Left boundary: runs from y=40 to y=140 (covers table from 100 to 140, but midpoint is at y=90 < 100-12=88)
            make_raw_line((50, 40), (50, 140)),
            # Segment covering lower part of left boundary: from y=140 to y=300 (midpoint y=220)
            make_raw_line((50, 140), (50, 300)),
            # Right boundary
            make_raw_line((250, 100), (250, 300)),
            # Top & bottom boundaries
            make_raw_line((50, 100), (250, 100)),
            make_raw_line((50, 300), (250, 300)),
        ]

        # Strategy A fails: top-left segment is dropped because its midpoint (90) is outside ROI [100, 300]
        # so xs only gets 50 from the lower segment, but if lower segment is slightly offset or missing, xs fails.
        # More critically, when tested with only the overshooting segment:
        lines_overshoot = [
            make_raw_line((50, 40), (50, 120)),  # midpoint 80 < 88 (dropped!)
            make_raw_line((250, 100), (250, 300)),
            make_raw_line((50, 100), (250, 100)),
            make_raw_line((50, 300), (250, 300)),
        ]
        res_a = run_strategy_a(lines_overshoot, roi, merge_tol=12.0)
        assert 50.0 not in res_a.grid_xs, "Strategy A should drop line with midpoint outside ROI"

        # Strategy D succeeds: interval overlap check detects segment intersects [100, 300]
        res_d = run_strategy_d(lines_overshoot, roi)
        assert any(abs(x - 50.0) <= 6.0 for x in res_d.grid_xs)

    def test_red_3_merged_header_fragmentation(self) -> None:
        """RED 3: Merged header cell spanning 3 columns is falsely fragmented into 3 cells in Strategy A."""
        # 3-column, 2-row table:
        # Row 1 (y=50..100) is a single merged header block across x=50..200
        # Row 2 (y=100..150) has 3 columns: x=50..100, 100..150, 150..200
        roi = (50.0, 50.0, 200.0, 150.0)
        lines = [
            # Top, middle, bottom horizontal lines
            make_raw_line((50, 50), (200, 50)),
            make_raw_line((50, 100), (200, 100)),
            make_raw_line((50, 150), (200, 150)),
            # Outer left and right vertical borders
            make_raw_line((50, 50), (50, 150)),
            make_raw_line((200, 50), (200, 150)),
            # Internal column dividers ONLY in Row 2 (y=100..150)
            make_raw_line((100, 100), (100, 150)),
            make_raw_line((150, 100), (150, 150)),
        ]

        # Strategy A fails: rigid MxN Cartesian product splits Row 1 into 3 cells (total 6 cells)
        res_a = run_strategy_a(lines, roi)
        assert len(res_a.cells) == 6, f"Expected Strategy A to falsely produce 6 cells, got {len(res_a.cells)}"

        # Strategy D succeeds: topological coverage detects no divider in Row 1 -> merges into 1 cell (total 4 cells)
        res_d = run_strategy_d(lines, roi)
        assert len(res_d.cells) == 4, f"Expected 4 cells (1 header + 3 data), got {len(res_d.cells)}"
        header_cell = res_d.cells[0]
        assert header_cell.is_merged is True
        assert header_cell.col_start == 0 and header_cell.col_end == 3

    def test_red_4_cell_interior_underline_splitting(self) -> None:
        """RED 4: Short interior underline inside one cell falsely splits every column across the table."""
        roi = (50.0, 50.0, 200.0, 150.0)
        lines = [
            # Table 2x2 grid
            make_raw_line((50, 50), (200, 50)),
            make_raw_line((50, 100), (200, 100)),
            make_raw_line((50, 150), (200, 150)),
            make_raw_line((50, 50), (50, 150)),
            make_raw_line((125, 50), (125, 150)),
            make_raw_line((200, 50), (200, 150)),
            # Short 20px underline inside top-left cell at y=75
            make_raw_line((60, 75), (80, 75)),
        ]

        # Strategy A fails: underline at y=75 added to ys -> creates 3 rows -> 6 cells instead of 4!
        res_a = run_strategy_a(lines, roi)
        assert len(res_a.grid_ys) == 4, "Strategy A falsely added underline to table grid_ys"
        assert len(res_a.cells) == 6

        # Strategy D succeeds: underline rejected via length & connectivity -> maintains 2x2 grid (4 cells)
        res_d = run_strategy_d(lines, roi, min_cell_dim_px=30.0)
        assert len(res_d.grid_ys) == 3
        assert len(res_d.cells) == 4

    def test_red_5_false_table_on_scattered_cad_lines(self) -> None:
        """RED 5: Scattered non-table CAD lines produce phantom table cells in Strategy A."""
        roi = (50.0, 50.0, 200.0, 200.0)
        # 4 scattered lines that don't form a closed table (open, disconnected)
        lines = [
            make_raw_line((60, 80), (180, 80)),    # Horizontal 1
            make_raw_line((70, 160), (190, 160)),  # Horizontal 2
            make_raw_line((90, 20), (90, 90)),     # Vertical 1
            make_raw_line((150, 140), (150, 250)), # Vertical 2
        ]

        # Strategy A fails: pairs the lines into a Cartesian grid and creates 1 phantom cell
        res_a = run_strategy_a(lines, roi)
        assert len(res_a.cells) >= 1

        # Strategy D succeeds: closure check fails -> has_valid_table is False and 0 cells emitted
        res_d = run_strategy_d(lines, roi)
        assert res_d.has_valid_table is False
        assert len(res_d.cells) == 0
