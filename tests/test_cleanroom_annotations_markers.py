"""tests/test_cleanroom_annotations_markers.py.

Cleanroom unit & parity tests for Batch S2: Architectural & Engineering Annotations, Markers, and Openings.
Verifies:
  - GeneralNotesHandler (cadmind-general-notes)
  - LevelMarkerHandler (cadmind-level-marker)
  - SlopeArrowHandler (cadmind-slope-arrow)
  - GridBubbleHandler (cadmind-grid-bubble)
  - OpeningInsertHandler (cadmind-opening-insert)

Strict 1:1 cleanroom fidelity with physical C# source:
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave7Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave8Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave9Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave16Handlers.cs
"""

import math
import pytest

from cad_agent.cleanroom_annotations_markers import (
    DegenerateGeometryError,
    GeneralNotesArgs,
    GeneralNotesHandler,
    GridBubbleArgs,
    GridBubbleHandler,
    LevelMarkerArgs,
    LevelMarkerHandler,
    OpeningInsertArgs,
    OpeningInsertHandler,
    SlopeArrowArgs,
    SlopeArrowHandler,
)
from cad_agent.cleanroom_mechanical import Point2D


# ============================================================================
# 1. GENERAL NOTES TESTS (cadmind-general-notes)
# ============================================================================


class TestGeneralNotesHandler:
    def setup_method(self):
        self.handler = GeneralNotesHandler()

    def test_general_notes_default_layout_and_numbering(self):
        raw_notes = [
            "All dimensions are in millimeters unless noted.",
            "Concrete compressive strength f'c = 30 MPa.",
            "3. Structural steel shall conform to ASTM A992.",
        ]
        args = GeneralNotesArgs(
            origin=[0.0, 0.0],
            title="STRUCTURAL NOTES",
            notes=raw_notes,
            width=150.0,
            has_border=True,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.title == "STRUCTURAL NOTES"
        assert res.note_count == 3
        # total_entities = 1 (title) + 1 (divider) + 3 (paragraphs) + 1 (border) = 6
        assert res.processed_count == 6
        assert len(res.paragraphs) == 3

        # Check automated prefixing: unnumbered gets "1. ", already numbered keeps "3. "
        assert res.paragraphs[0].text.startswith("1. All dimensions")
        assert res.paragraphs[1].text.startswith("2. Concrete compressive")
        assert res.paragraphs[2].text.startswith("3. Structural steel")

        # Check border coordinates
        assert res.border_vertices is not None
        assert len(res.border_vertices) == 4
        assert res.border_vertices[0] == Point2D(0.0, 0.0)
        assert res.border_vertices[1] == Point2D(150.0, 0.0)
        assert res.border_vertices[2].x == 150.0
        assert res.border_vertices[2].y < 0.0  # extends downward
        assert res.border_vertices[3].x == 0.0
        assert math.isclose(res.border_vertices[3].y, -res.total_height)

        # Check divider below title
        assert res.divider is not None
        assert res.divider.start.x == 0.0
        assert res.divider.end.x == 150.0

    def test_general_notes_border_disabled(self):
        args = GeneralNotesArgs(
            notes=["Note 1", "Note 2"],
            has_border=False,
        )
        res = self.handler.execute(args)
        assert res.status == "OK"
        assert res.border_vertices is None
        assert res.processed_count == 4  # title + divider + 2 notes

    def test_general_notes_rejections(self):
        # Empty notes
        with pytest.raises(DegenerateGeometryError, match="at least one note"):
            self.handler.execute(GeneralNotesArgs(notes=[]))

        # None notes
        with pytest.raises(DegenerateGeometryError, match="at least one note"):
            self.handler.execute(GeneralNotesArgs(notes=None))

        # Non-positive width
        with pytest.raises(DegenerateGeometryError, match="Width"):
            self.handler.execute(GeneralNotesArgs(notes=["A"], width=0.0))

        # Non-positive line spacing
        with pytest.raises(DegenerateGeometryError, match="LineSpacing"):
            self.handler.execute(GeneralNotesArgs(notes=["A"], line_spacing=-1.0))


# ============================================================================
# 2. LEVEL MARKER TESTS (cadmind-level-marker)
# ============================================================================


class TestLevelMarkerHandler:
    def setup_method(self):
        self.handler = LevelMarkerHandler()

    def test_level_marker_elevation_formatting_cases(self):
        # Zero elevation -> ±
        assert LevelMarkerHandler.format_elevation(0.0, "EL. ", 3) == "EL. ±0.000"
        assert LevelMarkerHandler.format_elevation(1e-7, "EL. ", 3) == "EL. ±0.000"

        # Positive elevation -> +
        assert LevelMarkerHandler.format_elevation(15.25, "EL. ", 2) == "EL. +15.25"

        # Negative elevation -> -
        assert LevelMarkerHandler.format_elevation(-3.875, "FL ", 3) == "FL -3.875"

        # Precision clamped to [0, 8]
        assert LevelMarkerHandler.format_elevation(5.5, "EL. ", -1) == "EL. +6"

    def test_level_marker_geometry_right_shelf(self):
        args = LevelMarkerArgs(
            origin=[100.0, 50.0],
            elevation=12.5,
            marker_size=6.0,
            shelf_length=30.0,
            direction="Right",
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.formatted_elevation == "EL. +12.500"
        assert res.elevation == 12.5
        assert res.processed_count == 3  # triangle + shelf + text

        # Triangle apex at (100, 50), flat top at y = 50 + 6 = 56
        assert len(res.indicator_triangle) == 3
        assert res.indicator_triangle[0] == Point2D(100.0, 50.0)
        assert res.indicator_triangle[1] == Point2D(97.0, 56.0)
        assert res.indicator_triangle[2] == Point2D(103.0, 56.0)

        # Shelf line from (100, 56) to (130, 56)
        assert res.shelf_line is not None
        assert res.shelf_line.start == Point2D(100.0, 56.0)
        assert res.shelf_line.end == Point2D(130.0, 56.0)

        # Text position above shelf at ox + 2, shelf_y + 1 = (102, 57)
        assert res.text_position == Point2D(102.0, 57.0)

    def test_level_marker_geometry_left_shelf(self):
        args = LevelMarkerArgs(
            origin=[200.0, 0.0],
            elevation=-1.2,
            marker_size=4.0,
            shelf_length=20.0,
            direction="Left",
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.shelf_line.start == Point2D(200.0, 4.0)
        assert res.shelf_line.end == Point2D(180.0, 4.0)
        assert res.text_position == Point2D(198.0, 5.0)

    def test_level_marker_rejections(self):
        with pytest.raises(DegenerateGeometryError, match="MarkerSize"):
            self.handler.execute(LevelMarkerArgs(marker_size=0.0))

        with pytest.raises(DegenerateGeometryError, match="ShelfLength"):
            self.handler.execute(LevelMarkerArgs(shelf_length=-10.0))


# ============================================================================
# 3. SLOPE ARROW TESTS (cadmind-slope-arrow)
# ============================================================================


class TestSlopeArrowHandler:
    def setup_method(self):
        self.handler = SlopeArrowHandler()

    def test_slope_arrow_formats_percent_ratio_degree(self):
        # 2% slope
        assert SlopeArrowHandler.format_slope(2.0, "PERCENT") == "2.0%"
        assert SlopeArrowHandler.format_slope(2.0, "RATIO") == "1:50"
        # atan(0.02) * 180 / pi = 1.14576 -> 1.15°
        assert SlopeArrowHandler.format_slope(2.0, "DEGREE") == "1.15°"

        # 50% slope
        assert SlopeArrowHandler.format_slope(50.0, "RATIO") == "1:2"

    def test_slope_arrow_analytical_geometry(self):
        # Horizontal arrow from (0,0) to (600, 0), arrowhead size 100
        args = SlopeArrowArgs(
            start_x=0.0,
            start_y=0.0,
            end_x=600.0,
            end_y=0.0,
            slope_percent=1.5,
            format="PERCENT",
            arrow_head_size=100.0,
            text_height=50.0,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.entity_count == 3
        assert res.arrow_length == 600.0
        assert res.angle_radians == 0.0
        assert res.formatted_label == "1.5%"

        # Shaft from (0,0) to (600,0)
        assert res.shaft_line.start == Point2D(0.0, 0.0)
        assert res.shaft_line.end == Point2D(600.0, 0.0)

        # Arrowhead wings at end (600, 0):
        # ux=1, uy=0, nx=0, ny=1
        # wing1 = 600 - 100*1 + (100/3)*0, 0 - 0 + (100/3)*1 = (500, 33.333)
        # wing2 = (500, -33.333)
        assert len(res.arrow_head_vertices) == 3
        assert res.arrow_head_vertices[0] == Point2D(600.0, 0.0)
        assert math.isclose(res.arrow_head_vertices[1].x, 500.0)
        assert math.isclose(res.arrow_head_vertices[1].y, 100.0 / 3.0)
        assert math.isclose(res.arrow_head_vertices[2].x, 500.0)
        assert math.isclose(res.arrow_head_vertices[2].y, -100.0 / 3.0)

        # Midpoint text position: (300, 0 + 0.75 * 50 * 1) = (300, 37.5)
        assert math.isclose(res.text_position.x, 300.0)
        assert math.isclose(res.text_position.y, 37.5)
        assert res.text_rotation == 0.0

    def test_slope_arrow_inverted_direction_readability_rotation(self):
        # Backward arrow from (500, 0) to (0, 0): angle = pi -> text rotation = 2*pi (or rotated by pi)
        args = SlopeArrowArgs(
            start_x=500.0,
            start_y=0.0,
            end_x=0.0,
            end_y=0.0,
            slope_percent=5.0,
            arrow_head_size=100.0,
        )
        res = self.handler.execute(args)
        assert res.status == "OK"
        # Text rotation must be rotated by pi to prevent upside-down text
        assert math.isclose(res.text_rotation, 2.0 * math.pi)

    def test_slope_arrow_rejections(self):
        # Length too short (< 3 * arrowhead)
        with pytest.raises(DegenerateGeometryError, match="shaft length too short"):
            self.handler.execute(
                SlopeArrowArgs(start_x=0, start_y=0, end_x=100, end_y=0, arrow_head_size=50.0)
            )

        # Slope percent zero
        with pytest.raises(DegenerateGeometryError, match="SlopePercent"):
            self.handler.execute(SlopeArrowArgs(slope_percent=0.0))

        # Slope percent > 1000
        with pytest.raises(DegenerateGeometryError, match="SlopePercent"):
            self.handler.execute(SlopeArrowArgs(slope_percent=1500.0))

        # Unknown format
        with pytest.raises(DegenerateGeometryError, match="Unknown Format"):
            self.handler.execute(SlopeArrowArgs(format="CUSTOM"))


# ============================================================================
# 4. GRID BUBBLE TESTS (cadmind-grid-bubble)
# ============================================================================


class TestGridBubbleHandler:
    def setup_method(self):
        self.handler = GridBubbleHandler()

    def test_grid_bubble_default_with_tail(self):
        # Center at (0, 0), radius 250, tail start at (-500, 0)
        args = GridBubbleArgs(
            center_x=0.0,
            center_y=0.0,
            bubble_radius=250.0,
            label="A",
            text_height=250.0,
            has_tail=True,
            tail_start_x=-500.0,
            tail_start_y=0.0,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.entity_count == 3  # tail line + circle + text
        assert res.label == "A"
        assert res.bubble_radius == 250.0
        assert res.circle_ir.center == Point2D(0.0, 0.0)
        assert res.circle_ir.radius == 250.0

        # Tail line terminates on bubble boundary:
        # dx = 0 - (-500) = 500, ux = 1, termX = 0 - 250*1 = -250
        assert res.tail_line is not None
        assert res.tail_line.start == Point2D(-500.0, 0.0)
        assert res.tail_line.end == Point2D(-250.0, 0.0)
        assert res.tail_line.length == 250.0

    def test_grid_bubble_no_tail(self):
        args = GridBubbleArgs(
            center_x=100.0,
            center_y=200.0,
            bubble_radius=150.0,
            label="12B",
            has_tail=False,
        )
        res = self.handler.execute(args)
        assert res.status == "OK"
        assert res.entity_count == 2  # circle + text
        assert res.tail_line is None

    def test_grid_bubble_tail_inside_circumference_rejection(self):
        # Tail start distance (100) < BubbleRadius (250) -> must fail
        with pytest.raises(DegenerateGeometryError, match="outside the bubble circumference"):
            self.handler.execute(
                GridBubbleArgs(
                    center_x=0.0,
                    center_y=0.0,
                    bubble_radius=250.0,
                    has_tail=True,
                    tail_start_x=-100.0,
                    tail_start_y=0.0,
                )
            )

        # Empty label rejection
        with pytest.raises(DegenerateGeometryError, match="Label must not be empty"):
            self.handler.execute(GridBubbleArgs(label="   "))


# ============================================================================
# 5. OPENING INSERT TESTS (cadmind-opening-insert)
# ============================================================================


class TestOpeningInsertHandler:
    def setup_method(self):
        self.handler = OpeningInsertHandler()

    def test_door_opening_left_hinge_open_up(self):
        # Width=900, wall=200, center=(0,0), rot=0
        args = OpeningInsertArgs(
            width=900.0,
            wall_thickness=200.0,
            point=[0.0, 0.0],
            rotation=0.0,
            type="door",
            hinge="left",
            open="up",
        )
        res = self.handler.execute(args)

        assert res.status == "SUCCESS"
        assert res.type == "door"
        assert res.width == 900.0
        assert res.wall_thickness == 200.0
        assert res.layer == "A-DOOR"
        assert res.entity_count == 4  # 2 jambs + 1 leaf + 1 arc

        # hw = 450, ht = 100, u=(1,0), v=(0,1)
        # Left jamb: (-450, -100) to (-450, 100)
        assert res.left_jamb.start == Point2D(-450.0, -100.0)
        assert res.left_jamb.end == Point2D(-450.0, 100.0)

        # Right jamb: (450, -100) to (450, 100)
        assert res.right_jamb.start == Point2D(450.0, -100.0)
        assert res.right_jamb.end == Point2D(450.0, 100.0)

        # Left hinge point = (-450, 0)
        # Open up (swingDir=1): leaf line extends along +v to (-450, 900)
        assert res.leaf_line.start == Point2D(-450.0, 0.0)
        assert res.leaf_line.end == Point2D(-450.0, 900.0)

        # Swing arc: center=(-450, 0), radius=900, start=0, end=pi/2
        assert res.swing_arc is not None
        assert res.swing_arc.center == Point2D(-450.0, 0.0)
        assert res.swing_arc.radius == 900.0
        assert math.isclose(res.swing_arc.start_angle_rad, 0.0)
        assert math.isclose(res.swing_arc.end_angle_rad, math.pi / 2.0)

    def test_window_opening_double_glazed(self):
        # Window: width=1200, wall=240, rotation=0
        args = OpeningInsertArgs(
            width=1200.0,
            wall_thickness=240.0,
            point=[100.0, 200.0],
            rotation=0.0,
            type="window",
        )
        res = self.handler.execute(args)

        assert res.status == "SUCCESS"
        assert res.type == "window"
        assert res.layer == "A-GLAZ"
        assert res.entity_count == 4  # 2 jambs + 2 glass lines
        assert len(res.glass_lines) == 2

        # hw=600, ht=120, offset=40
        # Glass 1 at y = 200 - 40 = 160: from -500 to 700
        assert res.glass_lines[0].start == Point2D(-500.0, 160.0)
        assert res.glass_lines[0].end == Point2D(700.0, 160.0)

        # Glass 2 at y = 200 + 40 = 240: from -500 to 700
        assert res.glass_lines[1].start == Point2D(-500.0, 240.0)
        assert res.glass_lines[1].end == Point2D(700.0, 240.0)

    def test_opening_insert_rejections(self):
        with pytest.raises(DegenerateGeometryError, match="INVALID_WIDTH"):
            self.handler.execute(OpeningInsertArgs(width=0.0))

        with pytest.raises(DegenerateGeometryError, match="INVALID_WALL_THICKNESS"):
            self.handler.execute(OpeningInsertArgs(wall_thickness=-20.0))
