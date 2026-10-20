"""tests/test_cleanroom_basic_shared.py.

Cleanroom unit & parity tests for Batch S1: Basic Shared CAD Tools.
Verifies:
  - GridAxesHandler (cadmind-grid-axes)
  - RevCloudHandler (cadmind-rev-cloud)
  - RoomNumberHandler (cadmind-room-number)
  - AutoNumberHandler (cadmind-auto-number)
  - DrawingFrameHandler (cadmind-drawing-frame)

Strict 1:1 cleanroom fidelity with physical C# source:
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave7Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave8Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave9Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/DrawingFrameHandler.cs
"""

import math
import pytest

from cad_agent.cleanroom_basic_shared import (
    AutoNumberArgs,
    AutoNumberHandler,
    DegenerateGeometryError,
    DrawingFrameArgs,
    DrawingFrameHandler,
    GridAxesArgs,
    GridAxesHandler,
    RevCloudArgs,
    RevCloudHandler,
    RoomNumberArgs,
    RoomNumberHandler,
)
from cad_agent.cleanroom_mechanical import Point2D


# ============================================================================
# 1. GRID AXES TESTS (cadmind-grid-axes)
# ============================================================================


class TestGridAxesHandler:
    def setup_method(self):
        self.handler = GridAxesHandler()

    def test_grid_axes_default_routing_payload_parity(self):
        # Parity with PluginDispatcherRoutingTests.cs:
        # {"HorizontalSpacings":[50.0],"VerticalSpacings":[60.0]}
        args = GridAxesArgs(
            horizontal_spacings=[50.0],
            vertical_spacings=[60.0],
            origin=[0.0, 0.0],
            extension=25.0,
            bubble_radius=6.0,
            text_height=4.0,
            bubble_at_start=True,
            bubble_at_end=False,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        # 1 spacing horizontal -> 2 axes (y=0, y=50)
        # 1 spacing vertical -> 2 axes (x=0, x=60)
        assert res.horizontal_axis_count == 2
        assert res.vertical_axis_count == 2
        assert res.bubble_count == 4  # 2 horizontal start bubbles + 2 vertical start bubbles
        # total entities: 4 lines + 4 bubbles * 2 (circle + text) = 12
        assert res.processed_count == 12
        assert len(res.axes) == 4

        # Check horizontal axis 1 (num=1 at y=0)
        ax_h1 = res.axes[0]
        assert ax_h1.axis_type == "HORIZONTAL"
        assert ax_h1.label == "1"
        assert ax_h1.line.start.y == 0.0
        assert ax_h1.line.end.y == 0.0
        assert ax_h1.line.start.x == -25.0  # minX(0) - Extension(25)
        assert ax_h1.line.end.x == 85.0   # maxX(60) + Extension(25)
        assert len(ax_h1.bubbles) == 1
        assert ax_h1.bubbles[0].center.x == -31.0  # -25 - BubbleRadius(6)
        assert ax_h1.bubbles[0].center.y == 0.0
        assert ax_h1.bubbles[0].label == "1"

        # Check vertical axis 1 (label='A' at x=0)
        ax_v1 = res.axes[2]
        assert ax_v1.axis_type == "VERTICAL"
        assert ax_v1.label == "A"
        assert ax_v1.line.start.x == 0.0
        assert ax_v1.line.end.x == 0.0
        assert ax_v1.line.start.y == -25.0
        assert ax_v1.line.end.y == 75.0   # maxY(50) + Extension(25)
        assert len(ax_v1.bubbles) == 1
        assert ax_v1.bubbles[0].center.x == 0.0
        assert ax_v1.bubbles[0].center.y == -31.0
        assert ax_v1.bubbles[0].label == "A"

        # Check vertical axis 2 (label='B' at x=60)
        ax_v2 = res.axes[3]
        assert ax_v2.label == "B"
        assert ax_v2.line.start.x == 60.0

    def test_grid_axes_both_ends_bubbles_and_alpha_wrapping(self):
        # Test BubbleAtStart and BubbleAtEnd simultaneously
        # Also test alpha labels beyond 26 columns
        v_spacings = [10.0] * 27  # 27 spacings -> 28 vertical axes: A..Z, AA, AB
        args = GridAxesArgs(
            horizontal_spacings=[100.0],
            vertical_spacings=v_spacings,
            bubble_at_start=True,
            bubble_at_end=True,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.horizontal_axis_count == 2
        assert res.vertical_axis_count == 28
        # Bubbles at both ends: 2 * 2 + 28 * 2 = 60 bubbles
        assert res.bubble_count == 60

        # Check column 25 is 'Z', column 26 is 'AA', column 27 is 'AB'
        v_axes = [ax for ax in res.axes if ax.axis_type == "VERTICAL"]
        assert v_axes[0].label == "A"
        assert v_axes[25].label == "Z"
        assert v_axes[26].label == "AA"
        assert v_axes[27].label == "AB"

    def test_grid_axes_alpha_helper_derivation(self):
        assert GridAxesHandler._get_alpha_label(0) == "A"
        assert GridAxesHandler._get_alpha_label(25) == "Z"
        assert GridAxesHandler._get_alpha_label(26) == "AA"
        assert GridAxesHandler._get_alpha_label(27) == "AB"
        assert GridAxesHandler._get_alpha_label(51) == "AZ"
        assert GridAxesHandler._get_alpha_label(52) == "BA"

    def test_grid_axes_degenerate_geometry_rejections(self):
        # Empty spacings
        with pytest.raises(DegenerateGeometryError, match="At least one axis spacing required"):
            self.handler.execute(GridAxesArgs(horizontal_spacings=[], vertical_spacings=[]))

        # Negative bubble radius
        with pytest.raises(DegenerateGeometryError, match="BubbleRadius"):
            self.handler.execute(GridAxesArgs(horizontal_spacings=[50.0], bubble_radius=-2.0))

        # Zero text height
        with pytest.raises(DegenerateGeometryError, match="TextHeight"):
            self.handler.execute(GridAxesArgs(horizontal_spacings=[50.0], text_height=0.0))

        # Negative extension
        with pytest.raises(DegenerateGeometryError, match="Extension"):
            self.handler.execute(GridAxesArgs(horizontal_spacings=[50.0], extension=-5.0))

        # Non-finite spacing
        with pytest.raises(DegenerateGeometryError):
            self.handler.execute(GridAxesArgs(horizontal_spacings=[float("nan")]))

    def test_grid_axes_arbitrary_origin_and_alpha_normalization(self):
        # Non-zero origin, custom start number and lowercase start alpha
        args = GridAxesArgs(
            horizontal_spacings=[100.0, 200.0],
            vertical_spacings=[150.0],
            origin=[500.0, -250.0],
            start_number=101,
            start_alpha="c",  # lowercase -> should normalize to 'C'
            bubble_at_start=True,
            bubble_at_end=True,
        )
        res = self.handler.execute(args)
        assert res.status == "OK"
        assert res.horizontal_axis_count == 3  # at y = -250, -150, 50
        assert res.vertical_axis_count == 2    # at x = 500, 650
        assert res.bubble_count == 10          # (3 + 2) * 2

        # Check horizontal axis labels: 101, 102, 103
        h_axes = [ax for ax in res.axes if ax.axis_type == "HORIZONTAL"]
        assert [ax.label for ax in h_axes] == ["101", "102", "103"]

        # Check vertical axis labels: 'C', 'D'
        v_axes = [ax for ax in res.axes if ax.axis_type == "VERTICAL"]
        assert [ax.label for ax in v_axes] == ["C", "D"]

    def test_grid_axes_non_letter_alpha_fallback(self):
        # Invalid start_alpha fallback to 'A'
        args = GridAxesArgs(
            vertical_spacings=[50.0],
            start_alpha="99",
        )
        res = self.handler.execute(args)
        v_axes = [ax for ax in res.axes if ax.axis_type == "VERTICAL"]
        assert v_axes[0].label == "A"


# ============================================================================
# 2. REVISION CLOUD TESTS (cadmind-rev-cloud)
# ============================================================================


class TestRevCloudHandler:
    def setup_method(self):
        self.handler = RevCloudHandler()

    def test_rev_cloud_routing_payload_ccw_outward_bulge(self):
        # Parity with PluginDispatcherRoutingTests.cs:
        # {"BoundaryPoints":[[0,0],[100,0],[100,100],[0,100]],"RevTag":"1"}
        pts = [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]]  # CCW
        args = RevCloudArgs(
            boundary_points=pts,
            arc_length=12.0,
            bulge=0.52,
            rev_tag="1",
            tag_size=7.0,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.has_tag is True
        assert res.rev_tag == "1"
        # CCW polygon: signed area = 100 * 100 = 10000 > 0
        # Inward side is left, outward is right -> bulge must be negative (-0.52)
        assert res.bulge == -0.52

        # Subdivisions: edge length = 100, segs = max(1, round(100/12)) = round(8.333) = 8
        # 4 edges * 8 segs = 32 vertices
        assert res.segment_count == 32
        assert len(res.vertices) == 32

        # Delta tag present: processed_count = 1 (pline) + 2 (triangle + text) = 3
        assert res.processed_count == 3
        assert res.tag is not None
        assert res.tag.text == "1"
        assert math.isclose(res.tag.text_height, 7.0 * 0.45)
        # Tag placed at pts[0] + tag_size = (0+7, 0+7) = (7, 7)
        assert math.isclose(res.tag.center.x, 7.0)
        assert math.isclose(res.tag.center.y, 7.0)
        assert len(res.tag.triangle_vertices) == 3

    def test_rev_cloud_clockwise_outward_bulge(self):
        # Clockwise polygon: signed area < 0 -> outward bulge is positive (+0.52)
        pts = [[0.0, 0.0], [0.0, 100.0], [100.0, 100.0], [100.0, 0.0]]  # CW
        args = RevCloudArgs(boundary_points=pts, arc_length=12.0, bulge=0.52)
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.bulge == 0.52
        assert res.has_tag is False
        assert res.processed_count == 1  # polyline only

    def test_rev_cloud_degenerate_geometry_rejections(self):
        # Fewer than 3 points
        with pytest.raises(DegenerateGeometryError, match="at least 3"):
            self.handler.execute(RevCloudArgs(boundary_points=[[0.0, 0.0], [10.0, 10.0]]))

        # Non-positive arc length
        with pytest.raises(DegenerateGeometryError, match="ArcLength"):
            self.handler.execute(
                RevCloudArgs(
                    boundary_points=[[0, 0], [10, 0], [10, 10]],
                    arc_length=-1.0,
                )
            )

        # Non-positive bulge
        with pytest.raises(DegenerateGeometryError, match="Bulge"):
            self.handler.execute(
                RevCloudArgs(
                    boundary_points=[[0, 0], [10, 0], [10, 10]],
                    bulge=0.0,
                )
            )

    def test_rev_cloud_l_shaped_polygon_segment_count(self):
        # 6-vertex L-shaped polygon
        pts = [
            [0.0, 0.0],
            [200.0, 0.0],
            [200.0, 100.0],
            [100.0, 100.0],
            [100.0, 200.0],
            [0.0, 200.0],
        ]
        args = RevCloudArgs(boundary_points=pts, arc_length=25.0, bulge=0.5)
        res = self.handler.execute(args)
        assert res.status == "OK"
        # Edges: 200 (8 segs), 100 (4 segs), 100 (4 segs), 100 (4 segs), 100 (4 segs), 200 (8 segs)
        # Total segs = 8 + 4 + 4 + 4 + 4 + 8 = 32
        assert res.segment_count == 32
        assert len(res.vertices) == 32

    def test_rev_cloud_whitespace_rev_tag_treated_as_no_tag(self):
        pts = [[0.0, 0.0], [50.0, 0.0], [50.0, 50.0], [0.0, 50.0]]
        args = RevCloudArgs(boundary_points=pts, rev_tag="   ")
        res = self.handler.execute(args)
        assert res.has_tag is False
        assert res.rev_tag is None
        assert res.tag is None
        assert res.processed_count == 1


# ============================================================================
# 3. ROOM NUMBER TESTS (cadmind-room-number)
# ============================================================================


class TestRoomNumberHandler:
    def setup_method(self):
        self.handler = RoomNumberHandler()

    def test_room_number_routing_payload_parity(self):
        # Parity with PluginDispatcherRoutingTests.cs:
        # {"CenterX":0,"CenterY":0,"RoomName":"OFFICE","RoomNumber":"101"}
        args = RoomNumberArgs(
            center_x=0.0,
            center_y=0.0,
            room_name="OFFICE",
            room_number="101",
            box_width=900.0,
            box_height=360.0,
            text_height=150.0,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.room_name == "OFFICE"
        assert res.room_number == "101"
        assert res.box_width == 900.0
        assert res.box_height == 360.0
        # No area -> 3 entities (box, number, name)
        assert res.entity_count == 3

        # Box geometry verification: hw=450, hh=180
        box = res.box_ir
        assert box is not None
        assert len(box.box_vertices) == 4
        assert box.box_vertices[0] == Point2D(-450.0, -180.0)
        assert box.box_vertices[1] == Point2D(450.0, -180.0)
        assert box.box_vertices[2] == Point2D(450.0, 180.0)
        assert box.box_vertices[3] == Point2D(-450.0, 180.0)

        # Room number centered at (0, 0)
        assert box.room_number_pos == Point2D(0.0, 0.0)

        # Room name centered above box at CenterY + hh + 0.85 * TextHeight
        # 0 + 180 + 0.85 * 150 = 180 + 127.5 = 307.5
        assert math.isclose(box.room_name_pos.x, 0.0)
        assert math.isclose(box.room_name_pos.y, 307.5)

    def test_room_number_with_area_takeoff(self):
        args = RoomNumberArgs(
            center_x=100.0,
            center_y=200.0,
            room_name="conference room",
            room_number="204B",
            area_sq_m=42.75,
            box_width=1000.0,
            box_height=400.0,
            text_height=150.0,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.room_name == "CONFERENCE ROOM"
        assert res.room_number == "204B"
        assert res.entity_count == 4  # box, number, name, area

        box = res.box_ir
        assert box is not None
        assert box.area_text == "42.8 m²"  # formatted F1: 42.8
        # Area text centered below box at CenterY - hh - 0.75 * TextHeight
        # 200 - 200 - 0.75 * 150 = -112.5
        assert math.isclose(box.area_pos.x, 100.0)
        assert math.isclose(box.area_pos.y, -112.5)

    def test_room_number_dimension_and_empty_validations(self):
        # Empty room name
        with pytest.raises(DegenerateGeometryError, match="must not be empty"):
            self.handler.execute(RoomNumberArgs(room_name=""))

        # Empty room number
        with pytest.raises(DegenerateGeometryError, match="must not be empty"):
            self.handler.execute(RoomNumberArgs(room_number="   "))

        # Box height too small (< 1.4 * text_height)
        with pytest.raises(DegenerateGeometryError, match="Box dimensions too small"):
            self.handler.execute(RoomNumberArgs(box_height=130.0, text_height=100.0))

        # Box width too small (< 2.0 * text_height)
        with pytest.raises(DegenerateGeometryError, match="Box dimensions too small"):
            self.handler.execute(RoomNumberArgs(box_width=180.0, text_height=100.0))

        # Negative area
        with pytest.raises(DegenerateGeometryError, match="AreaSqM cannot be negative"):
            self.handler.execute(RoomNumberArgs(area_sq_m=-1.0))

    def test_room_number_exact_boundary_thresholds(self):
        # Exactly on the threshold: box_height == 1.4 * text_height, box_width == 2.0 * text_height
        th = 50.0
        args = RoomNumberArgs(
            box_width=100.0,   # 2.0 * 50.0
            box_height=70.0,   # 1.4 * 50.0
            text_height=th,
        )
        res = self.handler.execute(args)
        assert res.status == "OK"

        # Just below width threshold
        with pytest.raises(DegenerateGeometryError, match="Box dimensions too small"):
            self.handler.execute(RoomNumberArgs(box_width=99.99, box_height=70.0, text_height=th))

        # Just below height threshold
        with pytest.raises(DegenerateGeometryError, match="Box dimensions too small"):
            self.handler.execute(RoomNumberArgs(box_width=100.0, box_height=69.99, text_height=th))


# ============================================================================
# 4. AUTO NUMBER TESTS (cadmind-auto-number)
# ============================================================================


class TestAutoNumberHandler:
    def setup_method(self):
        self.handler = AutoNumberHandler()

    def test_auto_number_routing_payload_parity(self):
        # Parity with PluginDispatcherRoutingTests.cs:
        # {"Points":[[0,0],[100,0]]}
        pts = [[0.0, 0.0], [100.0, 0.0]]
        args = AutoNumberArgs(points=pts)
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.tag_count == 2
        assert res.entity_count == 2  # NONE enclosure -> 1 entity per point
        assert res.first_label == "TAG-01"
        assert res.last_label == "TAG-02"
        assert len(res.tags) == 2
        assert res.tags[0].label == "TAG-01"
        assert res.tags[1].label == "TAG-02"
        assert res.tags[0].enclosure == "NONE"

    def test_auto_number_enclosures_circle_and_box(self):
        pts = [[0.0, 0.0], [50.0, 50.0], [100.0, 100.0]]

        # Circle enclosure
        res_circle = self.handler.execute(
            AutoNumberArgs(
                points=pts,
                start_number=10,
                step=5,
                padding=3,
                prefix="C-",
                suffix="-X",
                text_height=20.0,
                enclosure="CIRCLE",
                enclosure_padding=15.0,
            )
        )
        assert res_circle.tag_count == 3
        assert res_circle.entity_count == 6  # 3 texts + 3 circles
        assert res_circle.first_label == "C-010-X"
        assert res_circle.last_label == "C-020-X"

        # Check circle radius analytical formula:
        # r = (0.5 * TextHeight * max(1.5, len(label))) + EnclosurePadding
        # len("C-010-X") = 7. max(1.5, 7) = 7.
        # r = 0.5 * 20.0 * 7 + 15.0 = 70.0 + 15.0 = 85.0
        assert math.isclose(res_circle.tags[0].circle_radius, 85.0)

        # Box enclosure
        res_box = self.handler.execute(
            AutoNumberArgs(
                points=pts,
                start_number=1,
                text_height=20.0,
                enclosure="BOX",
                enclosure_padding=10.0,
            )
        )
        assert res_box.entity_count == 6
        tag0 = res_box.tags[0]
        assert tag0.box_vertices is not None
        assert len(tag0.box_vertices) == 4
        # hw = 0.5 * 20.0 * max(1.5, 6) + 10 = 10 * 6 + 10 = 70.0
        # hh = 0.75 * 20.0 + 10 = 15.0 + 10 = 25.0
        assert tag0.box_vertices[0] == Point2D(-70.0, -25.0)
        assert tag0.box_vertices[2] == Point2D(70.0, 25.0)

    def test_auto_number_negative_step_and_consecutive_duplicates(self):
        # Step down
        pts = [[0.0, 0.0], [10.0, 0.0]]
        res = self.handler.execute(AutoNumberArgs(points=pts, start_number=5, step=-1, padding=2))
        assert res.first_label == "TAG-05"
        assert res.last_label == "TAG-04"

        # Consecutive duplicate rejection
        pts_dup = [[10.0, 10.0], [10.00000001, 10.00000001]]
        with pytest.raises(DegenerateGeometryError, match="Consecutive duplicate"):
            self.handler.execute(AutoNumberArgs(points=pts_dup))

        # Step == 0 rejection
        with pytest.raises(DegenerateGeometryError, match="Step cannot be zero"):
            self.handler.execute(AutoNumberArgs(points=[[0, 0], [1, 1]], step=0))

    def test_auto_number_padding_zero_and_max_bounds(self):
        pts = [[0, 0], [10, 10]]
        # Padding 0 -> unpadded string
        res0 = self.handler.execute(AutoNumberArgs(points=pts, start_number=7, padding=0, prefix="P"))
        assert res0.first_label == "P7"
        assert res0.last_label == "P8"

        # Padding 8 (max valid)
        res8 = self.handler.execute(AutoNumberArgs(points=pts, start_number=42, padding=8, prefix="ID-"))
        assert res8.first_label == "ID-00000042"

        # Padding > 8 rejection
        with pytest.raises(DegenerateGeometryError, match="Padding must be between 0 and 8"):
            self.handler.execute(AutoNumberArgs(points=pts, padding=9))

        # Padding < 0 rejection
        with pytest.raises(DegenerateGeometryError, match="Padding must be between 0 and 8"):
            self.handler.execute(AutoNumberArgs(points=pts, padding=-1))


# ============================================================================
# 5. DRAWING FRAME TESTS (cadmind-drawing-frame)
# ============================================================================


class TestDrawingFrameHandler:
    def setup_method(self):
        self.handler = DrawingFrameHandler()

    def test_drawing_frame_iso_a3_landscape_default(self):
        # Standard A3 is 420 x 297 mm
        args = DrawingFrameArgs(size="A3", scale=1.0, orientation="landscape", title_block=True)
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.size == "A3"
        assert res.scale == 1.0
        assert res.width == 420.0
        assert res.height == 297.0
        assert len(res.frame_handles) == 3

        frame = res.frame_ir
        assert frame is not None
        # Outer border: (0,0) to (420, 297)
        assert frame.outer_border[0] == Point2D(0.0, 0.0)
        assert frame.outer_border[1] == Point2D(420.0, 0.0)
        assert frame.outer_border[2] == Point2D(420.0, 297.0)
        assert frame.outer_border[3] == Point2D(0.0, 297.0)

        # Inner margin: margin=10, leftMargin=25
        assert frame.inner_margin_border[0] == Point2D(25.0, 10.0)
        assert frame.inner_margin_border[1] == Point2D(410.0, 10.0)
        assert frame.inner_margin_border[2] == Point2D(410.0, 287.0)
        assert frame.inner_margin_border[3] == Point2D(25.0, 287.0)

        # Title block: 180x36mm anchored at (w - margin - 180, margin)
        # tbX = 420 - 10 - 180 = 230, tbY = 10
        assert frame.title_block_border is not None
        assert frame.title_block_border[0] == Point2D(230.0, 10.0)
        assert frame.title_block_border[1] == Point2D(410.0, 10.0)
        assert frame.title_block_border[2] == Point2D(410.0, 46.0)
        assert frame.title_block_border[3] == Point2D(230.0, 46.0)

    def test_drawing_frame_iso_a4_portrait_scaled(self):
        # A4: 297 x 210, portrait -> width=210, height=297
        # Scale 2.0 -> width=420, height=594
        args = DrawingFrameArgs(size="A4", scale=2.0, orientation="portrait", title_block=True)
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.scale == 2.0
        assert res.width == 420.0
        assert res.height == 594.0

        frame = res.frame_ir
        assert frame is not None
        # Margin: margin=20, leftMargin=50
        assert frame.inner_margin_border[0] == Point2D(50.0, 20.0)
        assert frame.inner_margin_border[1] == Point2D(400.0, 20.0)

        # Title block: tbW = 360, tbH = 72
        # tbX = 420 - 20 - 360 = 40, tbY = 20
        assert frame.title_block_border is not None
        assert frame.title_block_border[0] == Point2D(40.0, 20.0)
        assert frame.title_block_border[1] == Point2D(400.0, 20.0)
        assert frame.title_block_border[2] == Point2D(400.0, 92.0)
        assert frame.title_block_border[3] == Point2D(40.0, 92.0)

    def test_drawing_frame_fallback_and_no_titleblock(self):
        # Unknown size defaults to A3 (420 x 297)
        # Negative scale defaults to 1.0
        args = DrawingFrameArgs(size="UNKNOWN_SIZE", scale=-3.5, title_block=False)
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.scale == 1.0
        assert res.width == 420.0
        assert res.height == 297.0
        assert len(res.frame_handles) == 2  # No title block
        assert res.frame_ir.title_block_border is None

    @pytest.mark.parametrize(
        "size, expected_w, expected_h",
        [
            ("A0", 1189.0, 841.0),
            ("A1", 841.0, 594.0),
            ("A2", 594.0, 420.0),
            ("A3", 420.0, 297.0),
            ("A4", 297.0, 210.0),
            ("a0", 1189.0, 841.0),
            ("a2", 594.0, 420.0),
        ],
    )
    def test_drawing_frame_all_iso_sizes_landscape(self, size, expected_w, expected_h):
        res = self.handler.execute(DrawingFrameArgs(size=size, orientation="landscape"))
        assert res.status == "OK"
        assert res.width == expected_w
        assert res.height == expected_h

