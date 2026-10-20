"""tests/test_cleanroom_callouts_tables.py.

Cleanroom unit & parity tests for Batch S3:
Detail Callouts, Section Marks, Area Labels, Detail Views & Schedule Tables.
Verifies:
  - DetailCalloutHandler (cadmind-detail-callout)
  - SectionMarkHandler (cadmind-section-mark)
  - AreaLabelHandler (cadmind-area-label)
  - DetailViewHandler (cadmind-detail-view)
  - ScheduleTableHandler (cadmind-schedule-table)

Strict 1:1 cleanroom fidelity with physical C# source:
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierAWave1Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierAWave6Handlers.cs
"""

import math
import pytest

from cad_agent.cleanroom_callouts_tables import (
    AreaLabelArgs,
    AreaLabelHandler,
    DegenerateGeometryError,
    DetailCalloutArgs,
    DetailCalloutHandler,
    DetailViewArgs,
    DetailViewHandler,
    ScheduleTableArgs,
    ScheduleTableHandler,
    SectionMarkArgs,
    SectionMarkHandler,
)
from cad_agent.cleanroom_mechanical import Point2D


# ============================================================================
# 1. DETAIL CALLOUT TESTS (cadmind-detail-callout)
# ============================================================================


class TestDetailCalloutHandler:
    def setup_method(self):
        self.handler = DetailCalloutHandler()

    def test_detail_callout_geometry_no_leader(self):
        args = DetailCalloutArgs(
            center=[100.0, 200.0],
            radius=8.0,
            detail_id="C",
            sheet_ref="A-04",
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.detail_id == "C"
        assert res.sheet_ref == "A-04"
        assert res.ir_entity_count == 4  # circle + chord + 2 texts
        assert res.processed_count == 0  # 0 native entities mutated offline
        assert res.leader_line is None

        # Circle verification
        assert res.bubble_circle.center == Point2D(100.0, 200.0)
        assert res.bubble_circle.radius == 8.0

        # Dividing chord line from (100-8, 200) to (100+8, 200)
        assert res.dividing_chord.start == Point2D(92.0, 200.0)
        assert res.dividing_chord.end == Point2D(108.0, 200.0)

        # Upper text at (cx - 1, cy + radius * 0.25) = (99, 202)
        assert res.detail_id_pos == Point2D(99.0, 202.0)

        # Lower text at (cx - 2, cy - radius * 0.65) = (98, 200 - 5.2) = (98, 194.8)
        assert math.isclose(res.sheet_ref_pos.x, 98.0)
        assert math.isclose(res.sheet_ref_pos.y, 194.8)

    def test_detail_callout_with_leader_rim_intersection(self):
        # Center at (0,0), radius 10, leader to (0, 30) along +Y
        args = DetailCalloutArgs(
            center=[0.0, 0.0],
            radius=10.0,
            leader_endpoint=[0.0, 30.0],
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.ir_entity_count == 5  # +1 for leader
        assert res.processed_count == 0  # 0 native entities mutated offline
        assert res.leader_line is not None
        # Rim intersection along +Y is (0, 10)
        assert math.isclose(res.leader_line.start.x, 0.0)
        assert math.isclose(res.leader_line.start.y, 10.0)
        assert res.leader_line.end == Point2D(0.0, 30.0)

    def test_detail_callout_rejections(self):
        with pytest.raises(DegenerateGeometryError, match="Radius"):
            self.handler.execute(DetailCalloutArgs(radius=0.0))

        with pytest.raises(DegenerateGeometryError, match="Radius"):
            self.handler.execute(DetailCalloutArgs(radius=-5.0))


# ============================================================================
# 2. SECTION MARK TESTS (cadmind-section-mark)
# ============================================================================


class TestSectionMarkHandler:
    def setup_method(self):
        self.handler = SectionMarkHandler()

    def test_section_mark_horizontal_cutting_plane(self):
        args = SectionMarkArgs(
            start_point=[0.0, 0.0],
            end_point=[200.0, 0.0],
            section_id="A",
            arrow_size=5.0,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.full_label == "A-A"
        assert res.tip_label == "A"
        assert res.ir_entity_count == 5
        assert res.processed_count == 0  # 0 native entities mutated offline

        # Cut line from (0,0) to (200,0)
        assert res.cut_line.start == Point2D(0.0, 0.0)
        assert res.cut_line.end == Point2D(200.0, 0.0)

        # Normal is (0, 1), arrows point in +Y direction with length 5
        assert res.arrow_line_start.start == Point2D(0.0, 0.0)
        assert res.arrow_line_start.end == Point2D(0.0, 5.0)

        assert res.arrow_line_end.start == Point2D(200.0, 0.0)
        assert res.arrow_line_end.end == Point2D(200.0, 5.0)

        # Text position at arrow_end + normal * 1.5 = (0, 6.5) and (200, 6.5)
        assert res.text_pos_start == Point2D(0.0, 6.5)
        assert res.text_pos_end == Point2D(200.0, 6.5)

    def test_section_mark_pre_hyphenated_id(self):
        args = SectionMarkArgs(
            start_point=[0.0, 0.0],
            end_point=[100.0, 0.0],
            section_id="S-02",
        )
        res = self.handler.execute(args)
        assert res.full_label == "S-02"
        assert res.tip_label == "S"

    def test_section_mark_coincident_points_rejection(self):
        with pytest.raises(DegenerateGeometryError, match="coincident"):
            self.handler.execute(SectionMarkArgs(start_point=[50.0, 50.0], end_point=[50.0, 50.0]))

        with pytest.raises(DegenerateGeometryError, match="ArrowSize"):
            self.handler.execute(SectionMarkArgs(arrow_size=0.0))


# ============================================================================
# 3. AREA LABEL TESTS (cadmind-area-label)
# ============================================================================


class TestAreaLabelHandler:
    def setup_method(self):
        self.handler = AreaLabelHandler()

    def test_area_label_default_m2_scaling(self):
        # 12.5 m² = 12,500,000 mm² with scale_factor 1e-6
        args = AreaLabelArgs(
            position=[50.0, 100.0],
            area_value_mm2=12500000.0,
            scale_factor=0.000001,
            unit="m2",
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.display_area == 12.5
        assert res.label_text == "Area: 12.50 m2"
        assert res.position == Point2D(50.0, 100.0)
        assert res.ir_entity_count == 1
        assert res.processed_count == 0  # 0 native entities mutated offline

    def test_area_label_custom_unit_and_prefix(self):
        args = AreaLabelArgs(
            prefix="ROOM AREA: ",
            unit="sq.ft",
            scale_factor=1.0,
            area_value_mm2=450.75,
        )
        res = self.handler.execute(args)
        assert res.label_text == "ROOM AREA: 450.75 sq.ft"

    def test_area_label_rejections(self):
        with pytest.raises(DegenerateGeometryError, match="ScaleFactor"):
            self.handler.execute(AreaLabelArgs(scale_factor=-1.0))

        with pytest.raises(DegenerateGeometryError, match="AreaValueMm2"):
            self.handler.execute(AreaLabelArgs(area_value_mm2=0.0))


# ============================================================================
# 4. DETAIL VIEW TESTS (cadmind-detail-view)
# ============================================================================


class TestDetailViewHandler:
    def setup_method(self):
        self.handler = DetailViewHandler()

    def test_detail_view_analytical_geometry(self):
        # Center at (0,0), radius 10, leader angle 0 (along +X)
        args = DetailViewArgs(
            center=[0.0, 0.0],
            radius=10.0,
            label="B",
            leader_angle=0.0,
            height=3.5,
            scale="1:2",
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.label == "B"
        assert res.radius == 10.0
        assert res.ir_entity_count == 5  # circle + leader + shoulder + label + scale
        assert res.processed_count == 0  # 0 native entities mutated offline

        # Circle at (0,0) radius 10
        assert res.boundary_circle.center == Point2D(0.0, 0.0)
        assert res.boundary_circle.radius == 10.0

        # Leader from rim (10, 0) with extLen = max(10, 10*0.4) = 10 -> elbow at (20, 0)
        assert math.isclose(res.leader_line.start.x, 10.0)
        assert math.isclose(res.leader_line.start.y, 0.0)
        assert math.isclose(res.leader_line.end.x, 20.0)
        assert math.isclose(res.leader_line.end.y, 0.0)

        # Shoulder line from (20, 0) extending 16 along +X -> (36, 0)
        assert res.shoulder_line.start == Point2D(20.0, 0.0)
        assert res.shoulder_line.end == Point2D(36.0, 0.0)

        # Label text at elbow.x + 2, elbow.y + 1.5 = (22, 1.5)
        assert res.label_text_pos == Point2D(22.0, 1.5)

        # Scale text at elbow.x + 2, elbow.y - height * 1.3 = (22, -4.55)
        assert res.scale_text_pos is not None
        assert res.scale_text_pos.x == 22.0
        assert math.isclose(res.scale_text_pos.y, -3.5 * 1.3)

    def test_detail_view_no_scale_text(self):
        args = DetailViewArgs(scale=None)
        res = self.handler.execute(args)
        assert res.status == "OK"
        assert res.scale_text_pos is None
        assert res.ir_entity_count == 4
        assert res.processed_count == 0

    def test_detail_view_rejections(self):
        with pytest.raises(DegenerateGeometryError, match="Radius"):
            self.handler.execute(DetailViewArgs(radius=0.0))

        with pytest.raises(DegenerateGeometryError, match="Height"):
            self.handler.execute(DetailViewArgs(height=-1.0))


# ============================================================================
# 5. SCHEDULE TABLE TESTS (cadmind-schedule-table)
# ============================================================================


class TestScheduleTableHandler:
    def setup_method(self):
        self.handler = ScheduleTableHandler()

    def test_schedule_table_summation_column_and_grid(self):
        headers = ["MARK", "QTY", "WEIGHT (kg)"]
        rows = [
            ["W1", 4, 120.5],
            ["W2", 2, 85.0],
            ["W3", 6, 210.25],
        ]
        args = ScheduleTableArgs(
            origin=[0.0, 0.0],
            title="STEEL MEMBER SCHEDULE",
            headers=headers,
            rows=rows,
            sum_column=2,  # sum WEIGHT
            height=3.0,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.column_count == 3
        assert res.row_count == 3
        # Sum = 120.5 + 85.0 + 210.25 = 415.75
        assert res.sum_total is not None
        assert math.isclose(res.sum_total, 415.75)

        # Total width must be positive and equal to sum of column widths
        assert res.total_width > 0.0
        assert res.total_height > 0.0
        assert len(res.cells) > 0
        assert len(res.grid_lines) > 0

        # Check summation row text exists (1:1 C# parity: "TOTAL" in col 0, formatted sum in col 2)
        sum_cells = [c for c in res.cells if c.text == "415.75"]
        assert len(sum_cells) == 1
        total_label_cells = [c for c in res.cells if c.text == "TOTAL"]
        assert len(total_label_cells) == 1
        assert res.processed_count == 0
        assert res.ir_entity_count > 0

        # Check title cell exists
        title_cells = [c for c in res.cells if c.text == "STEEL MEMBER SCHEDULE"]
        assert len(title_cells) == 1

    def test_schedule_table_no_title_and_no_sum(self):
        headers = ["COL1", "COL2"]
        rows = [["A", "B"], ["C", "D"]]
        args = ScheduleTableArgs(
            headers=headers,
            rows=rows,
            title=None,
            sum_column=None,
        )
        res = self.handler.execute(args)
        assert res.status == "OK"
        assert res.sum_total is None
        title_cells = [c for c in res.cells if c.row == -1]
        assert len(title_cells) == 0

    def test_schedule_table_rejections(self):
        with pytest.raises(DegenerateGeometryError, match="at least one header"):
            self.handler.execute(ScheduleTableArgs(headers=[]))

        with pytest.raises(DegenerateGeometryError, match="at least one data row"):
            self.handler.execute(ScheduleTableArgs(headers=["A"], rows=[]))

        with pytest.raises(DegenerateGeometryError, match="Height"):
            self.handler.execute(ScheduleTableArgs(headers=["A"], rows=[["1"]], height=0.0))
