"""tests/test_cleanroom_mechanical_patterns.py.

Batch M6 Test Suite: Mechanical Patterns, Thread Callouts, Tapers & Engineering Calculations.
Validates cleanroom parity against physical C# source:
  - HolePatternHandler (cadmind-hole-pattern)
  - ThreadCalloutHandler (cadmind-thread-callout)
  - TaperSymbolHandler (cadmind-taper-symbol)
  - CutLengthHandler (cadmind-cut-length)
  - MechLayerCheckHandler (cadmind-mech-layer-check)
"""

import pytest

from cad_agent.cleanroom_mechanical import CircleIR, Point2D
from cad_agent.cleanroom_mechanical_patterns import (
    CleanroomError,
    CutLengthArgs,
    CutLengthHandler,
    HolePatternArgs,
    HolePatternHandler,
    MechLayerCheckArgs,
    MechLayerCheckHandler,
    TaperSymbolArgs,
    TaperSymbolHandler,
    ThreadCalloutArgs,
    ThreadCalloutHandler,
)


# ============================================================================
# 1. HolePatternHandler Tests
# ============================================================================


def test_hole_pattern_rectangular_oracle_1() -> None:
    handler = HolePatternHandler()
    args = HolePatternArgs(
        pattern_type="RECTANGULAR",
        origin_x=0.0,
        origin_y=0.0,
        hole_diameter=10.0,
        rows_or_count=3,
        columns=4,
        spacing_x_or_bcd=20.0,
        spacing_y=25.0,
    )
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.hole_count == 12
    assert res.entity_count == 12
    assert len(res.circles) == 12
    assert res.hole_radius == 5.0
    # First hole at (0, 0), last hole at (60, 50)
    assert res.circles[0].center.x == 0.0
    assert res.circles[0].center.y == 0.0
    assert res.circles[-1].center.x == 60.0
    assert res.circles[-1].center.y == 50.0


def test_hole_pattern_circular_oracle_2() -> None:
    handler = HolePatternHandler()
    args = HolePatternArgs(
        pattern_type="CIRCULAR",
        origin_x=100.0,
        origin_y=100.0,
        hole_diameter=10.0,
        rows_or_count=6,
        spacing_x_or_bcd=100.0,
        start_angle_deg=0.0,
    )
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.hole_count == 6
    assert res.entity_count == 7  # 1 BCD reference circle + 6 hole circles
    assert len(res.circles) == 7
    # First circle is BCD reference circle
    assert res.circles[0].center.x == 100.0
    assert res.circles[0].center.y == 100.0
    assert res.circles[0].radius == 50.0  # BCD/2


def test_hole_pattern_overlap_rejected() -> None:
    handler = HolePatternHandler()
    # SpacingX (10.0) is not > 1.1 * HoleDiameter (11.0)
    args = HolePatternArgs(
        pattern_type="RECTANGULAR",
        hole_diameter=10.0,
        rows_or_count=2,
        columns=2,
        spacing_x_or_bcd=10.0,
        spacing_y=20.0,
    )
    res = handler.execute(args)
    assert res.status == "ERROR"
    assert "must exceed 1.1 * HoleDiameter" in res.message


def test_hole_pattern_degenerate_diameter() -> None:
    handler = HolePatternHandler()
    res = handler.execute(HolePatternArgs(hole_diameter=0.0))
    assert res.status == "ERROR"
    assert "DEGENERATE_GEOMETRY" in res.message


# ============================================================================
# 2. ThreadCalloutHandler Tests
# ============================================================================


def test_thread_callout_placement() -> None:
    handler = ThreadCalloutHandler()
    circles = [
        CircleIR(Point2D(0.0, 0.0), 6.0),
        CircleIR(Point2D(50.0, 50.0), 6.0),
    ]
    args = ThreadCalloutArgs(thread_spec="M12x1.75-6H")
    res = handler.execute(args, target_circles=circles)

    assert res.status == "OK"
    assert res.count == 2
    assert len(res.lines) == 4  # 2 segments per callout leader


def test_thread_callout_empty_spec() -> None:
    handler = ThreadCalloutHandler()
    res = handler.execute(ThreadCalloutArgs(thread_spec=""))
    assert res.status == "ERROR"


# ============================================================================
# 3. TaperSymbolHandler Tests
# ============================================================================


def test_taper_symbol_generation() -> None:
    handler = TaperSymbolHandler()
    args = TaperSymbolArgs(
        insertion_point=Point2D(10.0, 20.0),
        ratio="1:10",
        direction="Right",
        symbol_size=10.0,
    )
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.count == 4  # 3 triangle sides + 1 centerline
    assert "Taper symbol '1:10'" in res.message


def test_taper_symbol_degenerate_size() -> None:
    handler = TaperSymbolHandler()
    res = handler.execute(TaperSymbolArgs(symbol_size=0.0))
    assert res.status == "ERROR"


# ============================================================================
# 4. CutLengthHandler Tests
# ============================================================================


def test_cut_length_oracle_3() -> None:
    handler = CutLengthHandler()
    curves = {
        "1A": (50.0, False),
        "1B": (30.0, True),
    }
    args = CutLengthArgs(
        handles=["1A", "1B"],
        labels=["BEAM_1", "PLATE_BORDER"],
        scale=2.5,
        decimals=2,
    )
    res = handler.execute(args, curves)

    assert res.status == "SUCCESS"
    assert res.count == 2
    # 50.0 * 2.5 = 125.00, 30.0 * 2.5 = 75.00 -> Total = 200.00
    assert res.items[0].length == 125.00
    assert res.items[1].length == 75.00
    assert res.total_length == 200.00
    assert len(res.skipped_handles) == 0


def test_cut_length_skipped_handles() -> None:
    handler = CutLengthHandler()
    curves = {"A1": (25.0, False)}
    args = CutLengthArgs(handles=["A1", "NON_EXISTENT", "INVALID_HEX_G!"])
    res = handler.execute(args, curves)

    assert res.status == "SUCCESS"
    assert res.count == 1
    assert len(res.skipped_handles) == 2


def test_cut_length_invalid_scale_raises() -> None:
    handler = CutLengthHandler()
    with pytest.raises(CleanroomError, match="INVALID_SCALE"):
        handler.execute(CutLengthArgs(handles=["1A"], scale=-1.0), {})


# ============================================================================
# 5. MechLayerCheckHandler Tests
# ============================================================================


def test_mech_layer_check_oracle_4() -> None:
    handler = MechLayerCheckHandler()
    drawing_layers = ["0", "Defpoints", "M-PART", "ANNO"]
    res = handler.execute(MechLayerCheckArgs(), drawing_layers)

    assert res.status == "SUCCESS"
    assert res.total_layers == 4
    assert res.standard_layers_count == 3
    assert res.non_standard_layers_count == 1
    # Oracle 4: (3/4) * 100 = 75.00%
    assert res.compliance_rate_percent == 75.00
    assert "ANNO" in res.non_standard_layers
