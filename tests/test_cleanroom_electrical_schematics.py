"""tests/test_cleanroom_electrical_schematics.py.

Comprehensive adversarial cleanroom test suite for Batch E2:
  - LadderDiagramHandler (cadmind-ladder-diagram)
  - LightingGridHandler (cadmind-lighting-grid)
  - PanelLayoutHandler (cadmind-panel-layout)
  - SldFeederHandler (cadmind-sld-feeder)
  - PanelScheduleHandler (cadmind-panel-schedule)
  - DeviceSymbolHandler (cadmind-device-symbol)
"""

import math
import pytest

from cad_agent.cleanroom_electrical_schematics import (
    CircuitScheduleItem,
    DegenerateGeometryError,
    DeviceSymbolArgs,
    DeviceSymbolHandler,
    LadderDiagramArgs,
    LadderDiagramHandler,
    LightingGridArgs,
    LightingGridHandler,
    PanelLayoutArgs,
    PanelLayoutHandler,
    PanelScheduleArgs,
    PanelScheduleHandler,
    SldFeederArgs,
    SldFeederHandler,
    SldFeederLoad,
)


# ============================================================================
# 1. LADDER DIAGRAM TESTS
# ============================================================================


def test_ladder_diagram_geometry_and_counts():
    handler = LadderDiagramHandler()
    args = LadderDiagramArgs(
        origin=[10.0, 20.0],
        width=150.0,
        rungs=3,
        spacing=25.0,
        numbers=True,
        layer="E-SLD-TEST",
    )
    res = handler.execute(args)

    assert res.status == "SUCCESS"
    assert res.rung_count == 3
    assert res.width == 150.0
    assert res.spacing == 25.0
    assert res.has_numbers
    assert res.layer == "E-SLD-TEST"

    # Entity count = 2 rails + 3 rungs + 3 numbers = 8
    assert res.entity_count == 8
    assert len(res.lines) == 5  # 2 rails + 3 rungs

    # Left rail: from (10, 20) to (10, 20 + 4*25) = (10, 120)
    left_rail = res.lines[0]
    assert (left_rail.start.x, left_rail.start.y) == (10.0, 20.0)
    assert (left_rail.end.x, left_rail.end.y) == (10.0, 120.0)

    # Right rail: from (160, 20) to (160, 120)
    right_rail = res.lines[1]
    assert (right_rail.start.x, right_rail.start.y) == (160.0, 20.0)
    assert (right_rail.end.x, right_rail.end.y) == (160.0, 120.0)


def test_ladder_diagram_validation_failures():
    handler = LadderDiagramHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_RUNGS"):
        handler.execute(LadderDiagramArgs(rungs=0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_WIDTH"):
        handler.execute(LadderDiagramArgs(width=-10.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_SPACING"):
        handler.execute(LadderDiagramArgs(spacing=0.0))


# ============================================================================
# 2. LIGHTING GRID TESTS
# ============================================================================


def test_lighting_grid_troffer_and_downlight():
    handler = LightingGridHandler()

    # Troffer grid: 2 rows x 3 cols = 6 fixtures
    res_troffer = handler.execute(
        LightingGridArgs(
            origin=[0.0, 0.0],
            width=6000.0,
            height=4000.0,
            rows=2,
            cols=3,
            fixture="troffer",
            size=300.0,
        )
    )
    assert res_troffer.status == "SUCCESS"
    assert res_troffer.fixture_count == 6
    assert len(res_troffer.centers) == 6
    # Centers check: dx=2000, dy=2000.
    # r=0, c=0: cx=1000, cy=1000
    assert res_troffer.centers[0] == [1000.0, 1000.0]
    # Each troffer fixture creates 1 box (4 lines) + 2 diagonals = 6 line segments
    assert len(res_troffer.lines) == 6 * 6
    assert res_troffer.entity_count == 6 * 3  # 1 pline + 2 diagonals per fixture

    # Downlight grid: 1 row x 2 cols = 2 fixtures
    res_downlight = handler.execute(
        LightingGridArgs(
            origin=[0.0, 0.0],
            width=3000.0,
            height=2000.0,
            rows=1,
            cols=2,
            fixture="downlight",
            size=200.0,
        )
    )
    assert res_downlight.status == "SUCCESS"
    assert res_downlight.fixture_count == 2
    assert len(res_downlight.circles) == 2
    assert res_downlight.centers == [[750.0, 1000.0], [2250.0, 1000.0]]
    assert len(res_downlight.lines) == 2 * 2  # 2 crosshair lines per fixture
    assert res_downlight.entity_count == 6  # 1 circle + 2 lines per fixture = 3 * 2


def test_lighting_grid_validation_failures():
    handler = LightingGridHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_WIDTH"):
        handler.execute(LightingGridArgs(width=0.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_ROWS"):
        handler.execute(LightingGridArgs(rows=0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_FIXTURE"):
        handler.execute(LightingGridArgs(fixture="sconce"))


# ============================================================================
# 3. PANEL LAYOUT TESTS
# ============================================================================


def test_panel_layout_with_and_without_label():
    handler = PanelLayoutHandler()

    # With label
    res_lbl = handler.execute(
        PanelLayoutArgs(
            origin=[0.0, 0.0],
            width=600.0,
            height=800.0,
            rows=6,
            cols=2,
            label="LP-1",
        )
    )
    assert res_lbl.status == "SUCCESS"
    assert res_lbl.total_slots == 12
    assert res_lbl.label == "LP-1"
    # Entity count: 1 enclosure + 2 title (divider + text) + 12 slots = 15
    assert res_lbl.entity_count == 15
    # Lines: 4 (enclosure) + 1 (divider) + 12*4 (slots) = 53 lines
    assert len(res_lbl.lines) == 4 + 1 + 12 * 4

    # Without label
    res_no_lbl = handler.execute(
        PanelLayoutArgs(
            origin=[0.0, 0.0],
            width=600.0,
            height=800.0,
            rows=4,
            cols=2,
            label=None,
        )
    )
    assert res_no_lbl.status == "SUCCESS"
    assert res_no_lbl.total_slots == 8
    assert res_no_lbl.label is None
    # Entity count: 1 enclosure + 8 slots = 9
    assert res_no_lbl.entity_count == 9


def test_panel_layout_validation_failures():
    handler = PanelLayoutHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_WIDTH"):
        handler.execute(PanelLayoutArgs(width=-100.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_HEIGHT"):
        handler.execute(PanelLayoutArgs(height=0.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_COLS"):
        handler.execute(PanelLayoutArgs(cols=0))


# ============================================================================
# 4. SLD FEEDER TESTS
# ============================================================================


def test_sld_feeder_generation():
    handler = SldFeederHandler()
    loads = [
        SldFeederLoad(tag="M-1", rating="30A"),
        SldFeederLoad(tag="M-2", rating="50A"),
        SldFeederLoad(tag="LP-1"),
    ]
    args = SldFeederArgs(
        origin=[0.0, 0.0],
        loads=loads,
        spacing=300.0,
        drop=400.0,
        layer="E-SLD-TEST",
    )
    res = handler.execute(args)

    assert res.status == "SUCCESS"
    assert res.feeder_count == 3
    assert res.spacing == 300.0
    assert res.drop == 400.0
    assert res.layer == "E-SLD-TEST"

    # Entities: 1 bus + (drop + box + tag + rating) for load 1 & 2 (4 each) + (drop + box + tag) for load 3 (3) = 1 + 4 + 4 + 3 = 12
    assert res.entity_count == 12


def test_sld_feeder_validation_failures():
    handler = SldFeederHandler()

    with pytest.raises(DegenerateGeometryError, match="MISSING_LOADS"):
        handler.execute(SldFeederArgs(loads=[]))

    with pytest.raises(DegenerateGeometryError, match="INVALID_LOAD_TAG"):
        handler.execute(SldFeederArgs(loads=[SldFeederLoad(tag="")]))

    with pytest.raises(DegenerateGeometryError, match="INVALID_SPACING"):
        handler.execute(SldFeederArgs(loads=[SldFeederLoad(tag="M1")], spacing=0.0))


# ============================================================================
# 5. PANEL SCHEDULE TESTS
# ============================================================================


def test_panel_schedule_totals_and_structure():
    handler = PanelScheduleHandler()
    circuits = [
        CircuitScheduleItem(desc="Receptacles Room 101", load=1800.0, trip="20A", phase="A"),
        CircuitScheduleItem(desc="Lighting Hallway", load=1200.0, trip="20A", phase="B"),
        CircuitScheduleItem(desc="HVAC Unit 1", load=3500.0, trip="30A", phase="C"),
    ]
    args = PanelScheduleArgs(
        origin=[50.0, 50.0],
        title="MAIN DISTRIBUTION PANEL",
        circuits=circuits,
        phases=3,
        height=2.5,
    )
    res = handler.execute(args)

    assert res.status == "SUCCESS"
    assert res.title == "MAIN DISTRIBUTION PANEL"
    assert res.circuit_count == 3
    assert math.isclose(res.total_load_va, 6500.0, abs_tol=1e-5)
    assert res.processed_count > 0
    assert len(res.lines) > 0


def test_panel_schedule_validation_failures():
    handler = PanelScheduleHandler()

    with pytest.raises(DegenerateGeometryError, match="DEGENERATE_GEOMETRY"):
        handler.execute(PanelScheduleArgs(circuits=[]))

    with pytest.raises(DegenerateGeometryError, match="DEGENERATE_GEOMETRY"):
        handler.execute(PanelScheduleArgs(circuits=[CircuitScheduleItem(desc="Test")], height=0.0))


# ============================================================================
# 6. DEVICE SYMBOL TESTS
# ============================================================================


def test_device_symbol_all_glyph_types():
    handler = DeviceSymbolHandler()
    points = [[10.0, 20.0], [30.0, 40.0]]

    for glyph in ["receptacle", "switch", "light", "motor", "junction", "ground"]:
        res = handler.execute(
            DeviceSymbolArgs(
                points=points,
                type=glyph,
                size=3.0,
                rotation=45.0,
                layer="E-POWER-TEST",
            )
        )
        assert res.status == "SUCCESS"
        assert res.symbol_type == glyph
        assert res.placed_count == 2
        assert res.processed_count > 0


def test_device_symbol_validation_failures():
    handler = DeviceSymbolHandler()

    with pytest.raises(DegenerateGeometryError, match="DEGENERATE_GEOMETRY"):
        handler.execute(DeviceSymbolArgs(points=[]))

    with pytest.raises(DegenerateGeometryError, match="DEGENERATE_GEOMETRY"):
        handler.execute(DeviceSymbolArgs(points=[[0.0, 0.0]], size=0.0))

    with pytest.raises(DegenerateGeometryError, match="Invalid symbol type"):
        handler.execute(DeviceSymbolArgs(points=[[0.0, 0.0]], type="chandelier"))
