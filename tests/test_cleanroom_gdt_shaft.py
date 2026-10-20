"""
Comprehensive Pytest Suite for Cleanroom GD&T and Rotating Machinery Drafting.
Tests include closed-form analytical oracles, geometric validity, and IEEE-754 fuzzing/edge cases.
"""

import math
import pytest

from cad_agent.cleanroom_mechanical import Point2D
from cad_agent.cleanroom_gdt_shaft import (
    GdtFrameHandler,
    DatumFeatureHandler,
    ItemBalloonHandler,
    ShaftStepHandler,
    ShaftStepDefinition,
    BallBearingHandler,
    CleanroomGeometryError,
    CleanroomIEEE754Error,
)


class TestGdtFrameHandler:
    def test_gdt_frame_handler_success(self):
        handler = GdtFrameHandler(
            characteristic="POSITION",
            tolerance=0.05,
            modifier="MMC",
            primary_datum="A",
            secondary_datum="B",
            tertiary_datum="C",
            insertion_point=Point2D(10.0, 20.0),
            cell_width=12.0,
            cell_height=8.0,
        )
        res = handler.execute()
        assert res.characteristic == "POSITION"
        assert res.tolerance == 0.05
        assert res.modifier == "M"
        assert res.datums == ["A", "B", "C"]
        assert len(res.primitives) >= 5
        assert res.frame_width == 5 * 12.0
        assert res.frame_height == 8.0

    @pytest.mark.parametrize(
        "char",
        [
            "STRAIGHTNESS",
            "FLATNESS",
            "CIRCULARITY",
            "CYLINDRICITY",
            "PROFILE_LINE",
            "PROFILE_SURFACE",
            "PERPENDICULARITY",
            "PARALLELISM",
            "ANGULARITY",
            "POSITION",
            "RUNOUT_CIRCULAR",
            "RUNOUT_TOTAL",
        ],
    )
    def test_all_standard_gdt_characteristics(self, char):
        handler = GdtFrameHandler(characteristic=char, tolerance=0.02)
        res = handler.execute()
        assert res.characteristic == char

    @pytest.mark.parametrize(
        "mod,expected", [("MMC", "M"), ("LMC", "L"), ("RFS", None), (None, None)]
    )
    def test_gdt_modifiers(self, mod, expected):
        handler = GdtFrameHandler(characteristic="POSITION", tolerance=0.1, modifier=mod)
        res = handler.execute()
        assert res.modifier == expected

    def test_gdt_frame_handler_validation_failures(self):
        with pytest.raises(CleanroomGeometryError):
            GdtFrameHandler(characteristic="INVALID_CHAR", tolerance=0.1)

        with pytest.raises(CleanroomGeometryError):
            GdtFrameHandler(characteristic="FLATNESS", tolerance=-0.01)

        with pytest.raises(CleanroomGeometryError):
            GdtFrameHandler(characteristic="FLATNESS", tolerance=0.0)

        with pytest.raises(CleanroomIEEE754Error):
            GdtFrameHandler(characteristic="FLATNESS", tolerance=float("nan"))

        with pytest.raises(CleanroomIEEE754Error):
            GdtFrameHandler(characteristic="FLATNESS", tolerance=float("inf"))

        with pytest.raises(CleanroomGeometryError):
            GdtFrameHandler(characteristic="POSITION", tolerance=0.1, modifier="INVALID_MOD")


class TestDatumFeatureHandler:
    def test_datum_feature_handler_success(self):
        handler = DatumFeatureHandler(
            datum_letter="A", insertion_point=Point2D(5.0, 5.0), box_size=8.0, stem_length=12.0
        )
        res = handler.execute()
        assert res.datum_letter == "A"
        assert len(res.primitives) >= 5

    @pytest.mark.parametrize("letter", ["A", "B", "C", "D", "X", "Y", "Z"])
    def test_datum_letters(self, letter):
        handler = DatumFeatureHandler(datum_letter=letter)
        res = handler.execute()
        assert res.datum_letter == letter

    def test_datum_feature_handler_validation(self):
        with pytest.raises(CleanroomGeometryError):
            DatumFeatureHandler(datum_letter="AB")  # Too long

        with pytest.raises(CleanroomGeometryError):
            DatumFeatureHandler(datum_letter="")  # Empty

        with pytest.raises(CleanroomGeometryError):
            DatumFeatureHandler(datum_letter="@")  # Non-alphanumeric

        with pytest.raises(CleanroomGeometryError):
            DatumFeatureHandler(datum_letter="A", box_size=-5.0)

        with pytest.raises(CleanroomGeometryError):
            DatumFeatureHandler(datum_letter="A", stem_length=0.0)

        with pytest.raises(CleanroomIEEE754Error):
            DatumFeatureHandler(datum_letter="A", stem_length=float("nan"))


class TestItemBalloonHandler:
    def test_item_balloon_handler_success(self):
        handler = ItemBalloonHandler(
            item_number=5, center=Point2D(50.0, 50.0), radius=6.0, leader_target=Point2D(30.0, 30.0)
        )
        res = handler.execute()
        assert res.item_number == 5
        assert res.radius == 6.0
        assert len(res.primitives) >= 3

    def test_item_balloon_handler_validation(self):
        with pytest.raises(CleanroomGeometryError):
            ItemBalloonHandler(item_number=0)

        with pytest.raises(CleanroomGeometryError):
            ItemBalloonHandler(item_number=-1)

        with pytest.raises(CleanroomGeometryError):
            ItemBalloonHandler(item_number=1, radius=-5.0)

        with pytest.raises(CleanroomGeometryError):
            ItemBalloonHandler(item_number=1, center=Point2D(10, 10), leader_target=Point2D(10, 10))

        with pytest.raises(CleanroomIEEE754Error):
            ItemBalloonHandler(item_number=1, radius=float("nan"))


class TestShaftStepHandler:
    def test_shaft_step_handler_analytical_oracle(self):
        # Define a three-step shaft:
        # Step 1: d1 = 20.0 (r1 = 10.0), L1 = 40.0
        # Step 2: d2 = 35.0 (r2 = 17.5), L2 = 60.0
        # Step 3: d3 = 25.0 (r3 = 12.5), L3 = 50.0
        steps = [
            ShaftStepDefinition(diameter=20.0, length=40.0),
            ShaftStepDefinition(diameter=35.0, length=60.0),
            ShaftStepDefinition(diameter=25.0, length=50.0),
        ]
        density = 7850.0  # kg/m^3
        handler = ShaftStepHandler(steps=steps, material_density=density)
        res = handler.execute()

        expected_vol = (
            (math.pi * (10.0**2) * 40.0)
            + (math.pi * (17.5**2) * 60.0)
            + (math.pi * (12.5**2) * 50.0)
        )
        assert math.isclose(res.volume, expected_vol, rel_tol=1e-9)
        assert res.total_length == 150.0
        assert res.max_diameter == 35.0
        assert len(res.primitives) >= 4

    def test_shaft_step_handler_validation(self):
        with pytest.raises(CleanroomGeometryError):
            ShaftStepHandler(steps=[])

        with pytest.raises(CleanroomGeometryError):
            ShaftStepHandler(steps=[ShaftStepDefinition(diameter=-10.0, length=50.0)])

        with pytest.raises(CleanroomGeometryError):
            ShaftStepHandler(steps=[ShaftStepDefinition(diameter=20.0, length=-50.0)])

        with pytest.raises(CleanroomIEEE754Error):
            ShaftStepHandler(steps=[ShaftStepDefinition(diameter=float("nan"), length=50.0)])


class TestBallBearingHandler:
    def test_ball_bearing_handler_6205_oracle(self):
        # Deep groove ball bearing 6205: d=25mm, D=52mm, B=15mm, Dw=8.73mm, Z=9
        handler = BallBearingHandler(
            bore_diameter=25.0,
            outer_diameter=52.0,
            width=15.0,
            ball_diameter=8.73,
            ball_count=9,
            center=Point2D(0.0, 0.0),
        )
        res = handler.execute()
        assert res.bore_diameter == 25.0
        assert res.outer_diameter == 52.0
        assert res.width == 15.0
        assert res.ball_count == 9
        assert res.Z == 9
        assert len(res.primitives) == 13

    def test_ball_bearing_handler_validation(self):
        # Bore >= Outer diameter
        with pytest.raises(CleanroomGeometryError):
            BallBearingHandler(
                bore_diameter=50.0, outer_diameter=40.0, width=15.0, ball_diameter=5.0, ball_count=8
            )

        # Bore == Outer diameter
        with pytest.raises(CleanroomGeometryError):
            BallBearingHandler(
                bore_diameter=40.0, outer_diameter=40.0, width=15.0, ball_diameter=5.0, ball_count=8
            )

        # Ball count < 3
        with pytest.raises(CleanroomGeometryError):
            BallBearingHandler(
                bore_diameter=25.0, outer_diameter=52.0, width=15.0, ball_diameter=5.0, ball_count=2
            )

        # Negative ball diameter
        with pytest.raises(CleanroomGeometryError):
            BallBearingHandler(
                bore_diameter=25.0,
                outer_diameter=52.0,
                width=15.0,
                ball_diameter=-5.0,
                ball_count=8,
            )

        with pytest.raises(CleanroomIEEE754Error):
            BallBearingHandler(
                bore_diameter=float("nan"),
                outer_diameter=52.0,
                width=15.0,
                ball_diameter=5.0,
                ball_count=8,
            )
