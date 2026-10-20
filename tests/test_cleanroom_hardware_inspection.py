"""tests/test_cleanroom_hardware_inspection.py.

Cleanroom unit & parity tests for Batch M5:
Hardware Fasteners, Title Block Annotation & Geometric Inspection.
Verifies:
  - RivetPinHandler (cadmind-rivet-pin)
  - MachiningNoteHandler (cadmind-machining-note)
  - SheetNumberHandler (cadmind-sheet-number)
  - SurfaceAreaHandler (cadmind-surface-area)
  - DivideMeasureHandler (cadmind-divide-measure)

Strict 1:1 cleanroom fidelity with physical C# source:
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave10Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave11Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave13Handlers.cs
"""

import math
import pytest

from cad_agent.cleanroom_mechanical import Arc2D, CircleIR, LineSegment2D, Point2D
from cad_agent.cleanroom_hardware_inspection import (
    DegenerateGeometryError,
    DivideMeasureArgs,
    DivideMeasureHandler,
    MachiningNoteArgs,
    MachiningNoteHandler,
    RivetPinArgs,
    RivetPinHandler,
    SheetNumberArgs,
    SheetNumberHandler,
    SurfaceAreaArgs,
    SurfaceAreaHandler,
)


# ============================================================================
# 1. RIVET PIN TESTS (cadmind-rivet-pin)
# ============================================================================


class TestRivetPinHandler:
    def setup_method(self):
        self.handler = RivetPinHandler()

    def test_default_rivet_pin_analytical_geometry(self):
        # Default: d=10, L=50, Dh=17.5, Hh=7.5
        args = RivetPinArgs()
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.entity_count == 4
        assert res.layer == "M-FASTENER-RIVET"
        assert res.shank_diameter == 10.0
        assert res.shank_length == 50.0
        assert res.head_diameter == 17.5
        assert res.head_height == 7.5

        # Analytical sagitta dome radius: R_arc = Hh/2 + Dh^2 / (8*Hh)
        # R_arc = 7.5/2 + 17.5^2 / (8 * 7.5) = 3.75 + 306.25 / 60 = 8.854166666666666
        expected_r = (7.5 / 2.0) + (17.5**2 / (8.0 * 7.5))
        assert pytest.approx(res.r_arc, rel=1e-6) == expected_r

        # Base line along Y axis at X=0: (0, -8.75) to (0, +8.75)
        assert res.base_line.start.x == pytest.approx(0.0)
        assert res.base_line.start.y == pytest.approx(-8.75)
        assert res.base_line.end.x == pytest.approx(0.0)
        assert res.base_line.end.y == pytest.approx(+8.75)

        # Shank outline: 4 segments (0, -5) -> (50, -5) -> (50, 5) -> (0, 5)
        assert len(res.shank_segments) == 4
        seg0, seg1, seg2, seg3 = res.shank_segments
        assert seg0.start.x == pytest.approx(0.0) and seg0.start.y == pytest.approx(-5.0)
        assert seg0.end.x == pytest.approx(50.0) and seg0.end.y == pytest.approx(-5.0)
        assert seg1.end.x == pytest.approx(50.0) and seg1.end.y == pytest.approx(5.0)
        assert seg2.end.x == pytest.approx(0.0) and seg2.end.y == pytest.approx(5.0)
        assert seg3.end.x == pytest.approx(0.0) and seg3.end.y == pytest.approx(-5.0)

        # Centerline: from -Hh - 0.25*d to L + 0.25*d
        # cl_start = -7.5 - 2.5 = -10.0; cl_end = 50 + 2.5 = 52.5
        assert res.centerline.start.x == pytest.approx(-10.0)
        assert res.centerline.start.y == pytest.approx(0.0)
        assert res.centerline.end.x == pytest.approx(52.5)
        assert res.centerline.end.y == pytest.approx(0.0)

    def test_custom_dimensions_and_rotation(self):
        # 90 deg rotation, origin at (100, 200)
        args = RivetPinArgs(
            origin_x=100.0,
            origin_y=200.0,
            shank_diameter=12.0,
            shank_length=60.0,
            head_diameter=22.0,
            head_height=9.0,
            rotation_deg=90.0,
            layer="CUSTOM_RIVET",
        )
        res = self.handler.execute(args)
        assert res.layer == "CUSTOM_RIVET"
        assert res.shank_diameter == 12.0
        assert res.head_diameter == 22.0
        assert res.head_height == 9.0

        # With 90 deg rotation, (0, -11) becomes (100 - (-11)*sin(90), 200 + (-11)*cos(90)) = (111, 200)
        assert res.base_line.start.x == pytest.approx(111.0)
        assert res.base_line.start.y == pytest.approx(200.0)

    @pytest.mark.parametrize(
        "kwargs, err_match",
        [
            ({"shank_diameter": 0.0}, "ShankDiameter and ShankLength must be positive"),
            ({"shank_length": -5.0}, "ShankDiameter and ShankLength must be positive"),
            ({"head_diameter": -1.0}, "HeadDiameter and HeadHeight must not be negative"),
            ({"head_height": -2.0}, "HeadDiameter and HeadHeight must not be negative"),
            ({"shank_diameter": 10.0, "head_diameter": 10.0}, "HeadDiameter must strictly exceed ShankDiameter"),
            ({"shank_diameter": 10.0, "head_diameter": 10.00005}, "HeadDiameter must strictly exceed ShankDiameter"),
            ({"shank_diameter": 10.0, "head_diameter": 18.0, "head_height": 20.0}, "not exceed HeadDiameter"),
            ({"origin_x": float("nan")}, "finite numbers"),
            ({"rotation_deg": float("inf")}, "finite numbers"),
        ],
    )
    def test_rivet_pin_rejections(self, kwargs, err_match):
        with pytest.raises(DegenerateGeometryError, match=err_match):
            self.handler.execute(RivetPinArgs(**kwargs))


# ============================================================================
# 2. MACHINING NOTE TESTS (cadmind-machining-note)
# ============================================================================


class TestMachiningNoteHandler:
    def setup_method(self):
        self.handler = MachiningNoteHandler()

    def test_default_machining_note_geometry(self):
        args = MachiningNoteArgs()
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.entity_count == 4
        assert res.layer == "M-ANNO-NOTE"
        assert res.note_text == "FINISH TURN"
        assert res.sub_note is None

        # Leader from (0,0) to (15,10)
        assert res.leader_line.start.x == pytest.approx(0.0)
        assert res.leader_line.start.y == pytest.approx(0.0)
        assert res.leader_line.end.x == pytest.approx(15.0)
        assert res.leader_line.end.y == pytest.approx(10.0)

        # Shelf line: landing_x >= target_x -> sigma = 1.0
        # shelfLen = max(4*2.5, 11*0.75*2.5) = max(10, 20.625) = 20.625
        # shelfEndX = 15 + 20.625 = 35.625
        assert res.shelf_line.start.x == pytest.approx(15.0)
        assert res.shelf_line.start.y == pytest.approx(10.0)
        assert res.shelf_line.end.x == pytest.approx(35.625)
        assert res.shelf_line.end.y == pytest.approx(10.0)

        # Primary text position: min(15, 35.625) + 0.2*2.5 = 15 + 0.5 = 15.5
        # Y = 10 + 0.35*2.5 = 10.875
        assert res.primary_text_pos.x == pytest.approx(15.5)
        assert res.primary_text_pos.y == pytest.approx(10.875)
        assert res.primary_text_height == 2.5

    def test_machining_note_with_subnote_and_left_landing(self):
        # landing to the left of target (LandingX < TargetX)
        args = MachiningNoteArgs(
            target_x=50.0,
            target_y=50.0,
            landing_x=20.0,
            landing_y=70.0,
            note_text="GRIND",
            sub_note="Ra 0.8 MAX",
            text_height=3.0,
            arrow_size=4.0,
            layer="M-ANNO-GRIND",
        )
        res = self.handler.execute(args)

        assert res.entity_count == 5
        assert res.layer == "M-ANNO-GRIND"
        assert res.sub_note == "Ra 0.8 MAX"

        # sigma = -1.0
        # shelfLen = max(4*3.0, 5*0.75*3.0) = max(12.0, 11.25) = 12.0
        # shelfEndX = 20.0 - 12.0 = 8.0
        assert res.shelf_line.end.x == pytest.approx(8.0)
        assert res.shelf_line.end.y == pytest.approx(70.0)

        # textStartX = min(20.0, 8.0) + 0.2*3.0 = 8.0 + 0.6 = 8.6
        assert res.primary_text_pos.x == pytest.approx(8.6)
        assert res.sub_text_pos.x == pytest.approx(8.6)
        # subTextY = 70.0 - 1.35*3.0 = 70.0 - 4.05 = 65.95
        assert res.sub_text_pos.y == pytest.approx(65.95)
        assert res.sub_text_height == pytest.approx(0.85 * 3.0)

    @pytest.mark.parametrize(
        "kwargs, err_match",
        [
            ({"target_x": 10.0, "landing_x": 10.0001, "target_y": 10.0, "landing_y": 10.0001}, "must not be coincident"),
            ({"note_text": ""}, "NoteText must not be empty"),
            ({"note_text": "   "}, "NoteText must not be empty"),
            ({"text_height": 0.0}, "TextHeight and ArrowSize must be positive"),
            ({"arrow_size": -1.0}, "TextHeight and ArrowSize must be positive"),
            ({"target_x": float("nan")}, "finite numbers"),
        ],
    )
    def test_machining_note_rejections(self, kwargs, err_match):
        with pytest.raises(DegenerateGeometryError, match=err_match):
            self.handler.execute(MachiningNoteArgs(**kwargs))


# ============================================================================
# 3. SHEET NUMBER TESTS (cadmind-sheet-number)
# ============================================================================


class TestSheetNumberHandler:
    def setup_method(self):
        self.handler = SheetNumberHandler()

    def test_single_sheet_badge_geometry(self):
        args = SheetNumberArgs()
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.entity_count == 4
        assert res.count == 1
        assert len(res.badges) == 1

        b0 = res.badges[0]
        assert b0.circle.center.x == pytest.approx(0.0)
        assert b0.circle.center.y == pytest.approx(0.0)
        assert b0.circle.radius == 6.0

        # Divider line: from (-6, 0) to (+6, 0)
        assert b0.divider.start.x == pytest.approx(-6.0)
        assert b0.divider.end.x == pytest.approx(6.0)

        # Upper text: "A-101" at (0, 0.22*6) = (0, 1.32)
        assert b0.upper_text == "A-101"
        assert b0.upper_text_pos.x == pytest.approx(0.0)
        assert b0.upper_text_pos.y == pytest.approx(1.32)
        # ht = min(2.5, 0.42*6) = min(2.5, 2.52) = 2.5
        assert b0.upper_text_height == 2.5

        # Lower text: "OF 10" at (0, -0.55*6) = (0, -3.3)
        assert b0.lower_text == "OF 10"
        assert b0.lower_text_pos.x == pytest.approx(0.0)
        assert b0.lower_text_pos.y == pytest.approx(-3.3)
        assert b0.lower_text_height == pytest.approx(0.75 * 2.5)

    def test_batch_sheet_badges_alphanumeric_and_numeric_progression(self):
        # 1. Alphanumeric batching (appends -1, -2, -3)
        args_alpha = SheetNumberArgs(
            count=3,
            sheet_no="M-200",
            total_sheets="50",
            batch_step_x=20.0,
            radius=6.0,
        )
        res_alpha = self.handler.execute(args_alpha)
        assert res_alpha.entity_count == 12  # 3 * 4
        assert [b.upper_text for b in res_alpha.badges] == ["M-200-1", "M-200-2", "M-200-3"]

        # 2. Integer numeric batching (increments 101, 102, 103)
        args_num = SheetNumberArgs(
            count=3,
            sheet_no="101",
            total_sheets="150",
            batch_step_x=20.0,
            radius=6.0,
        )
        res_num = self.handler.execute(args_num)
        assert [b.upper_text for b in res_num.badges] == ["101", "102", "103"]

    def test_badge_with_sheet_title_extension(self):
        args = SheetNumberArgs(
            sheet_no="S-01",
            total_sheets="",  # empty -> "SHEET"
            sheet_title="FOUNDATION PLAN",
            radius=10.0,
            text_height=3.0,
        )
        res = self.handler.execute(args)
        assert res.entity_count == 6
        b = res.badges[0]
        assert b.lower_text == "SHEET"
        assert b.title_line is not None
        assert b.title_text == "FOUNDATION PLAN"
        # title starts at cx + R = 10.0
        assert b.title_line.start.x == pytest.approx(10.0)
        assert b.title_line.start.y == pytest.approx(0.0)

    @pytest.mark.parametrize(
        "kwargs, err_match",
        [
            ({"count": 3, "radius": 10.0, "batch_step_x": 15.0}, r"magnitude must be at least 2 \* Radius"),
            ({"count": 0}, "Count must be at least 1"),
            ({"radius": 0.0}, "Radius must be positive"),
            ({"text_height": -1.0}, "TextHeight must be positive"),
            ({"sheet_no": "  "}, "SheetNo must not be empty"),
        ],
    )
    def test_sheet_number_rejections(self, kwargs, err_match):
        with pytest.raises(DegenerateGeometryError, match=err_match):
            self.handler.execute(SheetNumberArgs(**kwargs))


# ============================================================================
# 4. SURFACE AREA TESTS (cadmind-surface-area)
# ============================================================================


class TestSurfaceAreaHandler:
    def setup_method(self):
        self.handler = SurfaceAreaHandler()

    def test_circle_and_rectangle_surface_area_exact_oracles(self):
        # Circle R=10: A = pi * 100 = 314.159265..., P = 2 * pi * 10 = 62.831853...
        circle = CircleIR(center=Point2D(0, 0), radius=10.0)

        # Rectangle 100 x 50: A = 5000, P = 300
        rect = [
            Point2D(0, 0),
            Point2D(100, 0),
            Point2D(100, 50),
            Point2D(0, 50),
        ]

        # Case 1: thickness = 0 (2D face area)
        args_2d = SurfaceAreaArgs(profiles=[circle, rect], thickness=0.0, decimals=2)
        res_2d = self.handler.execute(args_2d)

        assert res_2d.status == "SUCCESS"
        assert res_2d.item_count == 2
        assert res_2d.items[0].face_area_mm2 == 314.16
        assert res_2d.items[0].perimeter_mm == 62.83
        assert res_2d.items[0].surface_area_mm2 == 314.16

        assert res_2d.items[1].face_area_mm2 == 5000.0
        assert res_2d.items[1].perimeter_mm == 300.0
        assert res_2d.items[1].surface_area_mm2 == 5000.0

        # Total face area = 5314.16 mm2 -> 53.14 cm2
        assert res_2d.total_face_area_mm2 == 5314.16
        assert res_2d.total_face_area_cm2 == 53.14

        # Case 2: thickness = 10.0 (3D prism total surface area = 2*A + P*t)
        # Circle: 2*314.159265 + 62.831853*10 = 628.31853 + 628.31853 = 1256.63706... -> 1256.64
        # Rect: 2*5000 + 300*10 = 10000 + 3000 = 13000.0
        args_3d = SurfaceAreaArgs(profiles=[circle, rect], thickness=10.0, decimals=2)
        res_3d = self.handler.execute(args_3d)

        assert res_3d.items[0].surface_area_mm2 == 1256.64
        assert res_3d.items[1].surface_area_mm2 == 13000.0
        # Total surface mm2 = 1256.637... + 13000 = 14256.64
        assert res_3d.total_surface_area_mm2 == 14256.64
        assert res_3d.total_surface_area_cm2 == 142.57

    def test_banker_rounding_parity(self):
        # Test exact half value rounding to even
        # Item 1: A = 2.500000 -> rounds to 2.50
        pts = [Point2D(0, 0), Point2D(2.5, 0), Point2D(2.5, 1.0), Point2D(0, 1.0)]
        args = SurfaceAreaArgs(profiles=[pts], thickness=0.0, decimals=0)
        res = self.handler.execute(args)
        assert res.items[0].face_area_mm2 == 2.0  # 2.5 rounds to even 2

    @pytest.mark.parametrize(
        "kwargs, err_match",
        [
            ({"profiles": []}, "EMPTY_INPUT"),
            ({"profiles": [CircleIR(Point2D(0, 0), 5.0)], "thickness": -2.0}, "INVALID_THICKNESS"),
            ({"profiles": [CircleIR(Point2D(0, 0), 5.0)], "thickness": float("nan")}, "INVALID_THICKNESS"),
            ({"profiles": [CircleIR(Point2D(0, 0), 5.0)], "thickness": float("inf")}, "INVALID_THICKNESS"),
            ({"profiles": [CircleIR(Point2D(0, 0), 5.0)], "decimals": 9}, "INVALID_DECIMALS"),
            ({"profiles": [CircleIR(Point2D(0, 0), 5.0)], "decimals": -1}, "INVALID_DECIMALS"),
        ],
    )
    def test_surface_area_rejections(self, kwargs, err_match):
        with pytest.raises(ValueError, match=err_match):
            self.handler.execute(SurfaceAreaArgs(**kwargs))

    def test_surface_area_default_decimals_contract_parity(self):
        # C# contract default is Decimals = 1
        args = SurfaceAreaArgs(profiles=[CircleIR(Point2D(0, 0), 10.0)])
        assert args.decimals == 1
        res = self.handler.execute(args)
        assert res.total_face_area_mm2 == 314.2  # round(pi * 100, 1) = 314.2
        assert res.total_face_area_cm2 == 3.1


# ============================================================================
# 5. DIVIDE & MEASURE TESTS (cadmind-divide-measure)
# ============================================================================


class TestDivideMeasureHandler:
    def setup_method(self):
        self.handler = DivideMeasureHandler()

    def test_divide_line_segment(self):
        line = LineSegment2D(Point2D(0, 0), Point2D(100, 0))
        # N = 5 -> 4 markers at x = 20, 40, 60, 80
        args = DivideMeasureArgs(curves=[line], mode="divide", n=5)
        res = self.handler.execute(args)

        assert res.status == "SUCCESS"
        assert res.marker_count == 4
        assert res.processed_curves == 1
        assert res.skipped_curves == 0

        expected_x = [20.0, 40.0, 60.0, 80.0]
        for idx, pt in enumerate(res.marker_points):
            assert pt.x == pytest.approx(expected_x[idx])
            assert pt.y == pytest.approx(0.0)

    def test_measure_line_segment(self):
        line = LineSegment2D(Point2D(0, 0), Point2D(0, 95))
        # Distance = 30 -> markers at y = 30, 60, 90 (3 markers, since 95 - 30*3 = 5 > 1e-4)
        args = DivideMeasureArgs(curves=[line], mode="measure", distance=30.0)
        res = self.handler.execute(args)

        assert res.marker_count == 3
        expected_y = [30.0, 60.0, 90.0]
        for idx, pt in enumerate(res.marker_points):
            assert pt.x == pytest.approx(0.0)
            assert pt.y == pytest.approx(expected_y[idx])

    def test_divide_arc_geometry(self):
        # Semicircle radius 10 from 0 to pi (length = 10 * pi = 31.4159...)
        arc = Arc2D(center=Point2D(0, 0), radius=10.0, start_angle_rad=0.0, end_angle_rad=math.pi)
        # N = 2 -> 1 marker at midpoint (angle = pi / 2 -> (0, 10))
        args = DivideMeasureArgs(curves=[arc], mode="divide", n=2)
        res = self.handler.execute(args)

        assert res.marker_count == 1
        pt = res.marker_points[0]
        assert pt.x == pytest.approx(0.0, abs=1e-6)
        assert pt.y == pytest.approx(10.0, abs=1e-6)

    def test_measure_polyline_geometry(self):
        # Polyline with 2 segments: (0,0)->(50,0) and (50,0)->(50,50), total length = 100
        polyline = [Point2D(0, 0), Point2D(50, 0), Point2D(50, 50)]
        # Distance = 40 -> markers at 40 (on seg 1) and 80 (on seg 2 at (50, 30))
        args = DivideMeasureArgs(curves=[polyline], mode="measure", distance=40.0)
        res = self.handler.execute(args)

        assert res.marker_count == 2
        assert res.marker_points[0].x == pytest.approx(40.0)
        assert res.marker_points[0].y == pytest.approx(0.0)
        assert res.marker_points[1].x == pytest.approx(50.0)
        assert res.marker_points[1].y == pytest.approx(30.0)

    @pytest.mark.parametrize(
        "kwargs, err_match",
        [
            ({"curves": []}, "EMPTY_INPUT"),
            ({"curves": [LineSegment2D(Point2D(0, 0), Point2D(10, 0))], "mode": "invalid"}, "INVALID_MODE"),
            ({"curves": [LineSegment2D(Point2D(0, 0), Point2D(10, 0))], "mode": "divide", "n": 1}, "INVALID_N"),
            ({"curves": [LineSegment2D(Point2D(0, 0), Point2D(10, 0))], "mode": "measure", "distance": 0.0}, "INVALID_DISTANCE"),
            ({"curves": [LineSegment2D(Point2D(0, 0), Point2D(10, 0))], "mode": "measure", "distance": -5.0}, "INVALID_DISTANCE"),
            ({"curves": [LineSegment2D(Point2D(0, 0), Point2D(10, 0))], "mode": "measure", "distance": float("inf")}, "INVALID_DISTANCE"),
        ],
    )
    def test_divide_measure_rejections(self, kwargs, err_match):
        with pytest.raises(ValueError, match=err_match):
            self.handler.execute(DivideMeasureArgs(**kwargs))
