"""
Comprehensive pytest suite targeting every corrected oracle, orientation,
split balloon, bearing catalog lookup, and shaft validation error.
"""

import pytest
from cad_agent.cleanroom_gdt_shaft import (
    GdtFrameHandler,
    DatumFeatureHandler,
    ItemBalloonHandler,
    BallBearingHandler,
    ShaftStepHandler,
    CleanroomError,
    STANDARD_BEARINGS,
)


def test_gdt_frame_valid():
    result = GdtFrameHandler.generate("⌖", "0.05", ["A", "B"], text_height=3.5)
    assert result["total_width"] > 0
    assert result["frame_height"] >= 1.3 * 3.5
    assert len(result["entities"]) > 0


def test_gdt_frame_invalid_height():
    with pytest.raises(CleanroomError) as exc_info:
        GdtFrameHandler.generate("⌖", "0.05", text_height=5.0, frame_height=4.0)
    assert exc_info.value.code == "INVALID_FRAME_DIMENSIONS"


@pytest.mark.parametrize("orientation", ["UP", "DOWN", "LEFT", "RIGHT"])
def test_datum_feature_orientations(orientation):
    result = DatumFeatureHandler.generate("A", (0, 0), orientation=orientation)
    assert result["datum"] == "A"
    assert result["orientation"] == orientation
    assert len(result["entities"]) >= 3


def test_datum_feature_invalid_orientation():
    with pytest.raises(CleanroomError) as exc_info:
        DatumFeatureHandler.generate("A", orientation="DIAGONAL")
    assert exc_info.value.code == "INVALID_ORIENTATION"


def test_item_balloon_standard():
    result = ItemBalloonHandler.generate("5", (10, 10))
    assert result["entity_count"] == 4
    assert result["quantity"] is None


def test_item_balloon_split_quantity():
    result = ItemBalloonHandler.generate("5", (10, 10), quantity=3)
    assert result["entity_count"] == 6
    assert result["quantity"] == 3


@pytest.mark.parametrize("designation", list(STANDARD_BEARINGS.keys()))
def test_ball_bearing_catalog_lookup(designation):
    result = BallBearingHandler.generate(designation=designation)
    expected_d, expected_D, expected_B = STANDARD_BEARINGS[designation]
    assert result["d"] == expected_d
    assert result["D"] == expected_D
    assert result["B"] == expected_B


def test_ball_bearing_unknown_designation():
    with pytest.raises(CleanroomError) as exc_info:
        BallBearingHandler.generate(designation="9999")
    assert exc_info.value.code == "UNKNOWN_BEARING_DESIGNATION"


def test_ball_bearing_invalid_custom_dimensions():
    with pytest.raises(CleanroomError) as exc_info:
        BallBearingHandler.generate(d=50.0, D=30.0, B=10.0)  # D <= d
    assert exc_info.value.code == "INVALID_BEARING_DIMENSIONS"


def test_shaft_step_valid():
    steps = [{"diameter": 20.0, "length": 50.0}, {"diameter": 30.0, "length": 80.0}]
    result = ShaftStepHandler.generate_steps(steps)
    assert result["total_length"] == 130.0
    assert result["step_count"] == 2


def test_shaft_step_invalid_diameter():
    steps = [{"diameter": -10.0, "length": 50.0}]
    with pytest.raises(CleanroomError) as exc_info:
        ShaftStepHandler.generate_steps(steps)
    assert exc_info.value.code == "INVALID_DIAMETER"


def test_shaft_step_invalid_length():
    steps = [{"diameter": 20.0, "length": 0.0}]
    with pytest.raises(CleanroomError) as exc_info:
        ShaftStepHandler.generate_steps(steps)
    assert exc_info.value.code == "INVALID_LENGTH"
