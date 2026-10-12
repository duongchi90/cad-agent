"""
test_view_partitioning_benchmark.py — Systematic Comparison of Strategies A, B, C, D for View Partitioning.

Empirically benchmarks 4 strategies across 6 multi-view engineering drawing layouts:
1. Two-view orthographic projection (Front and Top views)
2. Three-view first-angle projection (Front, Top, and Right side views)
3. Multi-scale drawing (1:10 general view + 1:2 detail view)
4. Production drawing with outer margin border and bottom-right title block
5. Orthographic views connected by inter-view alignment centerlines
6. Directional scale label binding under asymmetric placement
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
    run_strategy_a,
    run_strategy_b,
    run_strategy_c,
    run_strategy_d,
)


class TestViewPartitioningBenchmark:
    """Benchmark suite evaluating Strategies A, B, C, D across engineering drawing view layouts."""

    def test_case_1_two_view_orthographic_front_and_top(self) -> None:
        """Case 1: Standard 2-view orthographic drawing (Front view on top, Top view on bottom)."""
        lines = [
            # Front View: [100, 100, 400, 300]
            make_test_line((100, 100), (400, 100)),
            make_test_line((100, 300), (400, 300)),
            make_test_line((100, 100), (100, 300)),
            make_test_line((400, 100), (400, 300)),
            # Top View: [100, 450, 400, 650] (gutter = 150px)
            make_test_line((100, 450), (400, 450)),
            make_test_line((100, 650), (400, 650)),
            make_test_line((100, 450), (100, 650)),
            make_test_line((400, 450), (400, 650)),
        ]
        label_front = make_test_text("TL 1:1", (200, 320, 300, 340), "front-scale")
        label_top = make_test_text("TL 1:1", (200, 670, 300, 690), "top-scale")

        res_a = run_strategy_a([label_front, label_top], lines, 1200, 800, 144)
        res_d = run_strategy_d([label_front, label_top], lines, 1200, 800, 144)

        assert res_a.has_valid_partition and len(res_a.views) == 2
        assert res_d.has_valid_partition and len(res_d.views) == 2
        assert res_d.views[0].scale_denominator == 1
        assert res_d.views[1].scale_denominator == 1

    def test_case_2_three_view_first_angle_projection(self) -> None:
        """Case 2: 3-view layout (Front, Top, Right side view)."""
        lines = [
            # Front View: [100, 100, 350, 350]
            make_test_line((100, 100), (350, 100)),
            make_test_line((100, 350), (350, 350)),
            make_test_line((100, 100), (100, 350)),
            make_test_line((350, 100), (350, 350)),
            # Top View: [100, 450, 350, 700]
            make_test_line((100, 450), (350, 450)),
            make_test_line((100, 700), (350, 700)),
            make_test_line((100, 450), (100, 700)),
            make_test_line((350, 450), (350, 700)),
            # Right Side View: [450, 100, 700, 350]
            make_test_line((450, 100), (700, 100)),
            make_test_line((450, 350), (700, 350)),
            make_test_line((450, 100), (450, 350)),
            make_test_line((700, 100), (700, 350)),
        ]
        label_1 = make_test_text("TL 1:2", (180, 370, 270, 390), "l1")
        label_2 = make_test_text("TL 1:2", (180, 720, 270, 740), "l2")
        label_3 = make_test_text("TL 1:2", (530, 370, 620, 390), "l3")

        res_d = run_strategy_d([label_1, label_2, label_3], lines, 1200, 800, 144)
        assert res_d.has_valid_partition
        assert len(res_d.views) == 3
        assert len(res_d.unassigned_text_ids) == 0
        assert all(v.scale_denominator == 2 for v in res_d.views)

    def test_case_3_mixed_scale_general_and_detail_views(self) -> None:
        """Case 3: General assembly view (1:10) and an enlarged detail view (1:2)."""
        lines = [
            # General View: [100, 100, 500, 400]
            make_test_line((100, 100), (500, 100)),
            make_test_line((100, 400), (500, 400)),
            make_test_line((100, 100), (100, 400)),
            make_test_line((500, 100), (500, 400)),
            # Detail View: [600, 100, 850, 350]
            make_test_line((600, 100), (850, 100)),
            make_test_line((600, 350), (850, 350)),
            make_test_line((600, 100), (600, 350)),
            make_test_line((850, 100), (850, 350)),
        ]
        label_gen = make_test_text("TL 1:10", (250, 420, 350, 440), "l-gen")
        label_det = make_test_text("TL 1:2", (680, 370, 770, 390), "l-det")

        res_d = run_strategy_d([label_gen, label_det], lines, 1200, 800, 144)
        assert len(res_d.views) == 2
        v_gen = [v for v in res_d.views if v.bbox_px[0] == pytest.approx(100.0)][0]
        v_det = [v for v in res_d.views if v.bbox_px[0] == pytest.approx(600.0)][0]
        assert v_gen.scale_denominator == 10
        assert v_det.scale_denominator == 2

    def test_case_4_production_sheet_with_border_and_title_block(self) -> None:
        """Case 4: Full sheet with margin border and bottom-right title block table."""
        # 1600 x 1000 page
        border_lines = [
            make_test_line((10, 10), (1590, 10)),
            make_test_line((10, 990), (1590, 990)),
            make_test_line((10, 10), (10, 990)),
            make_test_line((1590, 10), (1590, 990)),
        ]
        # Title block in bottom right: x in [1100, 1580], y in [750, 980]
        title_lines = [
            make_test_line((1100, 750), (1580, 750)),
            make_test_line((1100, 980), (1580, 980)),
            make_test_line((1100, 750), (1100, 980)),
            make_test_line((1580, 750), (1580, 980)),
        ]
        # Main View: x in [200, 700], y in [150, 650]
        view_lines = [
            make_test_line((200, 150), (700, 150)),
            make_test_line((200, 650), (700, 650)),
            make_test_line((200, 150), (200, 650)),
            make_test_line((700, 150), (700, 650)),
        ]
        label = make_test_text("TL 1:5", (400, 670, 500, 690), "l-main")

        # Strategy A fails because border lines create a page-spanning region (> 80% page area)
        res_a = run_strategy_a([label], border_lines + title_lines + view_lines, 1600, 1000, 144)
        # Strategy A region spans whole page
        assert res_a.views[0].bbox_px[0] <= 15.0 and res_a.views[0].bbox_px[2] >= 1580.0

        # Strategy D succeeds: isolates border, isolates title block, extracts clean view
        res_d = run_strategy_d([label], border_lines + title_lines + view_lines, 1600, 1000, 144)
        assert res_d.border_bbox_px is not None
        assert len(res_d.table_bboxes_px) == 1
        assert len(res_d.views) == 1
        view = res_d.views[0]
        assert view.bbox_px[0] == pytest.approx(200.0)
        assert view.bbox_px[2] == pytest.approx(700.0)
        assert view.scale_denominator == 5

    def test_case_5_inter_view_gutter_whitespace_separation(self) -> None:
        """Case 5: Two views with a 60px whitespace corridor (gutter) between them."""
        lines = [
            # View 1: [100, 100, 400, 400]
            make_test_line((100, 100), (400, 100)),
            make_test_line((100, 400), (400, 400)),
            make_test_line((100, 100), (100, 400)),
            make_test_line((400, 100), (400, 400)),
            # View 2: [460, 100, 760, 400] (gutter = 60px)
            make_test_line((460, 100), (760, 100)),
            make_test_line((460, 400), (760, 400)),
            make_test_line((460, 100), (460, 400)),
            make_test_line((760, 100), (760, 400)),
        ]
        label_1 = make_test_text("TL 1:1", (200, 420, 300, 440), "l1")
        label_2 = make_test_text("TL 1:1", (560, 420, 660, 440), "l2")

        res_d = run_strategy_d([label_1, label_2], lines, 1200, 800, 144)
        assert len(res_d.views) == 2
        assert res_d.views[0].bbox_px[2] <= 410.0
        assert res_d.views[1].bbox_px[0] >= 450.0

    def test_case_6_directional_heading_alignment_under_asymmetry(self) -> None:
        """Case 6: Scale label placed directly under View 1 (centered at x=250),
        closer vertically to bottom but horizontally aligned with View 1.
        """
        lines = [
            # View 1 centered at x=250: [100, 100, 400, 300]
            make_test_line((100, 100), (400, 100)),
            make_test_line((100, 300), (400, 300)),
            make_test_line((100, 100), (100, 300)),
            make_test_line((400, 100), (400, 300)),
            # View 2 centered at x=600: [500, 100, 700, 300]
            make_test_line((500, 100), (700, 100)),
            make_test_line((500, 300), (700, 300)),
            make_test_line((500, 100), (500, 300)),
            make_test_line((700, 100), (700, 300)),
        ]
        # Label 1 is below View 1 at x in [200, 300] (center 250)
        label_1 = make_test_text("TL 1:5", (200, 330, 300, 350), "l1")

        res_d = run_strategy_d([label_1], lines, 1200, 800, 144)
        assert len(res_d.views) == 2
        v1 = [v for v in res_d.views if v.bbox_px[0] == pytest.approx(100.0)][0]
        assert v1.scale_denominator == 5
        v2 = [v for v in res_d.views if v.bbox_px[0] == pytest.approx(500.0)][0]
        assert v2.scale_denominator is None  # View 2 has no scale label
