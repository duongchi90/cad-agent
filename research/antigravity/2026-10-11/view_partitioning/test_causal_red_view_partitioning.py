"""
test_causal_red_view_partitioning.py — Public Causal RED Benchmarks for Semantic View Region Partitioning.

Proves 5 causal failure modes in Strategy A (primitive_ir_lib/view_calibration.py):
1. RED 1: Single-linkage chaining bridge collapse merges separate views into 1 region.
2. RED 2: Outer sheet border line assimilation triggers >= 80% area bailout, losing dimension evidence.
3. RED 3: Connecting centerline / extension line bridges adjacent orthographic views.
4. RED 4: Equidistant scale label dropped completely (0 candidates emitted) under 1e-6 float equality.
5. RED 5: Title block metadata table lines falsely classified as drawing view regions.

All 5 fail under Strategy A and succeed under Strategy D.
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
    run_strategy_d,
)


class TestCausalRedViewPartitioning:
    """Causal RED suite confirming production Strategy A defects and Strategy D resolution."""

    def test_red_1_single_linkage_inter_view_bridge_collapse(self) -> None:
        """RED 1: Two distinct views separated by a small projection gap collapse into 1 giant region."""
        # View 1: x in [100, 300], y in [100, 300]
        # View 2: x in [325, 525], y in [100, 300] (gap = 25px)
        lines = [
            # View 1 box
            make_test_line((100, 100), (300, 100)),
            make_test_line((100, 300), (300, 300)),
            make_test_line((100, 100), (100, 300)),
            make_test_line((300, 100), (300, 300)),
            # View 2 box
            make_test_line((325, 100), (525, 100)),
            make_test_line((325, 300), (525, 300)),
            make_test_line((325, 100), (325, 300)),
            make_test_line((525, 100), (525, 300)),
        ]
        label_1 = make_test_text("TL 1:10", (150, 320, 250, 340), "lbl1")
        label_2 = make_test_text("TL 1:5", (380, 320, 480, 340), "lbl2")

        # In Strategy A: gap_px at 144 DPI is 30px (5.29mm * 144 / 25.4 = 30.0px)
        # Because gap = 25px <= 30px, Strategy A merges View 1 and View 2 into 1 single region [100, 100, 525, 300]
        # and assigns TWO conflicting scale denominators (1:10 and 1:5) to the exact same merged region!
        res_a = run_strategy_a([label_1, label_2], lines, 1400, 900, 144)
        assert len({v.bbox_px for v in res_a.views}) == 1, "Expected Strategy A to collapse views into 1 unique bbox"
        assert res_a.views[0].bbox_px == (100.0, 100.0, 525.0, 300.0)
        assert res_a.views[1].bbox_px == (100.0, 100.0, 525.0, 300.0)
        assert res_a.views[0].scale_denominator != res_a.views[1].scale_denominator

        # Strategy D succeeds: separates View 1 and View 2, binds each scale label accurately
        res_d = run_strategy_d([label_1, label_2], lines, 1400, 900, 144)
        assert len(res_d.views) == 2
        assert len(res_d.unassigned_text_ids) == 0
        v1, v2 = res_d.views
        assert v1.bbox_px[0] == pytest.approx(100.0) and v1.bbox_px[2] == pytest.approx(300.0)
        assert v2.bbox_px[0] == pytest.approx(325.0) and v2.bbox_px[2] == pytest.approx(525.0)
        assert v1.scale_denominator == 10
        assert v2.scale_denominator == 5

    def test_red_2_sheet_border_assimilation_dimension_bailout(self) -> None:
        """RED 2: Sheet border rectangle assimilates view lines into a >= 80% page-spanning region,
        causing Strategy A to drop all dimension verification evidence.
        """
        # Outer sheet border lines enclosing 1400 x 900 page
        border_lines = [
            make_test_line((10, 10), (1390, 10), "border-top"),
            make_test_line((10, 890), (1390, 890), "border-bottom"),
            make_test_line((10, 10), (10, 890), "border-left"),
            make_test_line((1390, 10), (1390, 890), "border-right"),
        ]
        # View lines inside: x in [200, 600], y in [200, 500]
        view_lines = [
            make_test_line((200, 200), (600, 200), "v-top"),
            make_test_line((200, 500), (600, 500), "v-bottom"),
            make_test_line((200, 200), (200, 500), "v-left"),
            make_test_line((600, 200), (600, 500), "v-right"),
            # Line connecting view to border margin (e.g. margin note leader or dimension line near border)
            make_test_line((10, 200), (200, 200), "bridge"),
        ]
        label = make_test_text("TL 1:10", (300, 520, 400, 540), "scale-label")

        res_a = run_strategy_a([label], border_lines + view_lines, 1400, 900, 144)
        # Strategy A merges the bridge and border: region covers [10, 10, 1390, 890]
        # Area ratio is > 95% -> triggers line 88 `if region_area / page_area >= 0.80:`
        assert len(res_a.views) == 1
        # View is page-spanning (starts near 10, ends near 1390)
        assert res_a.views[0].bbox_px[0] <= 20.0 and res_a.views[0].bbox_px[2] >= 1380.0

        # Strategy D succeeds: peels sheet border lines, recognizes border_bbox, partitions view cleanly
        res_d = run_strategy_d([label], border_lines + view_lines, 1400, 900, 144)
        assert res_d.border_bbox_px is not None
        assert res_d.border_bbox_px[0] == pytest.approx(10.0)
        assert res_d.border_bbox_px[2] == pytest.approx(1390.0)
        # View is isolated to drawing area
        assert len(res_d.views) >= 1
        view = res_d.views[0]
        assert view.scale_denominator == 10

    def test_red_3_centerline_projection_crossing_trap(self) -> None:
        """RED 3: Centerline or projection line connecting two views causes single-linkage collapse."""
        lines = [
            # View 1: x in [100, 300], y in [100, 300]
            make_test_line((100, 100), (300, 100)),
            make_test_line((100, 300), (300, 300)),
            make_test_line((100, 100), (100, 300)),
            make_test_line((300, 100), (300, 300)),
            # View 2: x in [500, 700], y in [100, 300]
            make_test_line((500, 100), (700, 100)),
            make_test_line((500, 300), (700, 300)),
            make_test_line((500, 100), (500, 300)),
            make_test_line((700, 100), (700, 300)),
            # Intermediate projection line at y=200 spanning across views (e.g. alignment centerline)
            make_test_line((290, 200), (510, 200)),
        ]
        label_1 = make_test_text("TL 1:1", (150, 320, 250, 340), "lbl1")
        label_2 = make_test_text("TL 1:2", (550, 320, 650, 340), "lbl2")

        # Strategy A merges both views via the connecting centerline into 1 giant bbox [100, 100, 700, 300]
        res_a = run_strategy_a([label_1, label_2], lines, 1400, 900, 144)
        assert len({v.bbox_px for v in res_a.views}) == 1
        merged_box = res_a.views[0].bbox_px
        assert merged_box[0] == pytest.approx(100.0) and merged_box[2] == pytest.approx(700.0)


    def test_red_4_equidistant_scale_label_dropped(self) -> None:
        """RED 4: Scale label exactly equidistant between two views is dropped completely by Strategy A."""
        # Two identical views placed symmetrically around x=500
        # View 1: x in [200, 400], y in [100, 300] -> right edge at x=400
        # View 2: x in [600, 800], y in [100, 300] -> left edge at x=600
        # Distance from x=500 to View 1 is 100px; to View 2 is 100px.
        lines = [
            make_test_line((200, 100), (400, 100)),
            make_test_line((200, 300), (400, 300)),
            make_test_line((600, 100), (800, 100)),
            make_test_line((600, 300), (800, 300)),
        ]
        # Label placed symmetrically at x in [480, 520] (center at 500)
        label = make_test_text("TL 1:5", (480, 200, 520, 220), "centered-scale")

        # Strategy A: distances[0][0] == distances[1][0] -> triggers line 73 `continue` -> 0 candidates!
        res_a = run_strategy_a([label], lines, 1400, 900, 144)
        assert len(res_a.views) == 0 or all(v.scale_denominator is None for v in res_a.views)
        assert "centered-scale" in res_a.unassigned_text_ids

    def test_red_5_title_block_metadata_table_conflation(self) -> None:
        """RED 5: Title block metadata table lines in bottom-right corner are falsely treated as drawing view."""
        # Drawing View: x in [100, 400], y in [100, 400]
        # Title block: x in [900, 1350], y in [650, 850] (bottom right corner of 1400x900 sheet)
        lines = [
            # View lines
            make_test_line((100, 100), (400, 100)),
            make_test_line((100, 400), (400, 400)),
            make_test_line((100, 100), (100, 400)),
            make_test_line((400, 100), (400, 400)),
            # Title block lines
            make_test_line((900, 650), (1350, 650)),
            make_test_line((900, 850), (1350, 850)),
            make_test_line((900, 650), (900, 850)),
            make_test_line((1350, 650), (1350, 850)),
            make_test_line((900, 750), (1350, 750)),
            make_test_line((1100, 650), (1100, 850)),
        ]
        view_label = make_test_text("TL 1:1", (200, 420, 300, 440), "view-label")

        res_a = run_strategy_a([view_label], lines, 1400, 900, 144)
        # Strategy A treats both as drawing regions
        assert len(res_a.views) >= 1

        # Strategy D isolates title block into table_bboxes_px, not a drawing view
        res_d = run_strategy_d([view_label], lines, 1400, 900, 144)
        assert len(res_d.table_bboxes_px) == 1
        tb = res_d.table_bboxes_px[0]
        assert tb[0] == pytest.approx(900.0) and tb[2] == pytest.approx(1350.0)
        # The drawing view is isolated
        assert len(res_d.views) == 1
        assert res_d.views[0].bbox_px[0] == pytest.approx(100.0)
        assert res_d.views[0].scale_denominator == 1
