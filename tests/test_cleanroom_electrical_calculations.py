"""tests/test_cleanroom_electrical_calculations.py.

Comprehensive adversarial cleanroom test suite for Batch E3:
  - VoltageDropHandler (cadmind-voltage-drop)
  - WireSizingHandler (cadmind-wire-sizing)
  - BreakerSelectHandler (cadmind-breaker-select)
  - RacewayRunHandler (cadmind-raceway-run)
  - HomeRunHandler (cadmind-home-run)
  - WireTagHandler (cadmind-wire-tag)
  - SymbolLegendHandler (cadmind-symbol-legend)
"""

import math
import pytest

from cad_agent.cleanroom_electrical_calculations import (
    BreakerSelectArgs,
    BreakerSelectHandler,
    DegenerateGeometryError,
    HomeRunArgs,
    HomeRunHandler,
    HomeRunItem,
    RacewayRunArgs,
    RacewayRunHandler,
    SymbolLegendArgs,
    SymbolLegendEntry,
    SymbolLegendHandler,
    VoltageDropArgs,
    VoltageDropHandler,
    WireAmpacityItem,
    WireSizingArgs,
    WireSizingHandler,
    WireTagArgs,
    WireTagHandler,
    WireTagItem,
)


# ============================================================================
# 1. VOLTAGE DROP TESTS
# ============================================================================


def test_voltage_drop_single_and_three_phase():
    handler = VoltageDropHandler()

    # Single-phase copper
    res1 = handler.execute(
        VoltageDropArgs(
            current=10.0,
            length=50.0,
            area=2.5,
            phase=1,
            voltage=230.0,
            material="copper",
            limit=5.0,
        )
    )
    assert res1.status == "SUCCESS"
    # Vdrop = 2.0 * 10 * 50 * 0.0214 / 2.5 = 8.56 V
    assert math.isclose(res1.drop_volts, 8.56, abs_tol=1e-3)
    # Drop % = (8.56 / 230) * 100 = 3.72 %
    assert math.isclose(res1.drop_percent, 3.72, abs_tol=1e-2)
    assert res1.pass_
    assert math.isclose(res1.resistance, 0.428, abs_tol=1e-4)

    # Three-phase aluminium
    res3 = handler.execute(
        VoltageDropArgs(
            current=100.0,
            length=100.0,
            area=70.0,
            phase=3,
            voltage=400.0,
            material="aluminium",
            limit=3.0,
        )
    )
    assert res3.status == "SUCCESS"
    # Vdrop = sqrt(3) * 100 * 100 * 0.0353 / 70 = 8.735 V
    expected_vdrop = math.sqrt(3.0) * 100.0 * 100.0 * 0.0353 / 70.0
    assert math.isclose(res3.drop_volts, round(expected_vdrop, 3), abs_tol=1e-3)
    assert res3.pass_


def test_voltage_drop_validation_failures():
    handler = VoltageDropHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_CURRENT"):
        handler.execute(VoltageDropArgs(current=0.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_LENGTH"):
        handler.execute(VoltageDropArgs(length=-10.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_PHASE"):
        handler.execute(VoltageDropArgs(phase=2))

    with pytest.raises(DegenerateGeometryError, match="UNSUPPORTED_MATERIAL"):
        handler.execute(VoltageDropArgs(material="silver"))


# ============================================================================
# 2. WIRE SIZING TESTS
# ============================================================================


def test_wire_sizing_selection():
    handler = WireSizingHandler()

    # 2 loaded conductors (Table B.52.2), I=16A, derating=1.0 -> required 16A -> selected 1.5 mm² (19.5A)
    res2 = handler.execute(WireSizingArgs(current=16.0, derating=1.0, loaded_conductors=2))
    assert res2.status == "SUCCESS"
    assert res2.required_ampacity == 16.0
    assert res2.selected_size == 1.5
    assert res2.selected_ampacity == 19.5
    assert res2.spare_margin == 3.5
    assert res2.next_size_up == 2.5
    assert res2.next_ampacity == 27.0

    # 3 loaded conductors (Table B.52.4), I=20A, derating=0.8 -> required 25A -> selected 4.0 mm² (32.0A)
    res3 = handler.execute(WireSizingArgs(current=20.0, derating=0.8, loaded_conductors=3))
    assert res3.status == "SUCCESS"
    assert math.isclose(res3.required_ampacity, 25.0, abs_tol=1e-2)
    assert res3.selected_size == 4.0
    assert res3.selected_ampacity == 32.0
    assert res3.spare_margin == 7.0

    # Custom table sizing
    custom_table = [
        WireAmpacityItem(size=1.0, ampacity=10.0),
        WireAmpacityItem(size=2.0, ampacity=25.0),
    ]
    res_custom = handler.execute(WireSizingArgs(current=15.0, table=custom_table))
    assert res_custom.status == "SUCCESS"
    assert res_custom.selected_size == 2.0


def test_wire_sizing_validation_failures():
    handler = WireSizingHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_CURRENT"):
        handler.execute(WireSizingArgs(current=-5.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_DERATING"):
        handler.execute(WireSizingArgs(derating=1.5))

    with pytest.raises(DegenerateGeometryError, match="INVALID_LOADED_CONDUCTORS"):
        handler.execute(WireSizingArgs(loaded_conductors=1))

    with pytest.raises(DegenerateGeometryError, match="EXCEEDS_MAX_CAPACITY"):
        handler.execute(WireSizingArgs(current=1000.0))


# ============================================================================
# 3. BREAKER SELECT TESTS
# ============================================================================


def test_breaker_select_coordination():
    handler = BreakerSelectHandler()

    # Direct current: load=18A, safety=1.0 -> selected 20A
    res_dir = handler.execute(BreakerSelectArgs(current=18.0, safety=1.0, cable_ampacity=25.0))
    assert res_dir.status == "SUCCESS"
    assert res_dir.load_current == 18.0
    assert res_dir.selected_rating == 20.0
    assert res_dir.cable_protected
    assert res_dir.coordination_warning is None

    # Power based: P=15kW, 3-phase, 400V, PF=0.85
    # I = 15000 / (sqrt(3) * 400 * 0.85) = 25.47A
    # Design = 25.47 * 1.25 = 31.84A -> selected 32A
    res_pwr = handler.execute(
        BreakerSelectArgs(
            power=15000.0,
            voltage=400.0,
            phase=3,
            power_factor=0.85,
            safety=1.25,
        )
    )
    assert res_pwr.status == "SUCCESS"
    assert math.isclose(res_pwr.load_current, 25.47, abs_tol=1e-2)
    assert res_pwr.selected_rating == 32.0


def test_breaker_select_validation_failures():
    handler = BreakerSelectHandler()

    with pytest.raises(DegenerateGeometryError, match="MISSING_LOAD"):
        handler.execute(BreakerSelectArgs())

    with pytest.raises(DegenerateGeometryError, match="INVALID_SAFETY_FACTOR"):
        handler.execute(BreakerSelectArgs(current=10.0, safety=0.9))

    with pytest.raises(DegenerateGeometryError, match="CONDUCTOR_UNDERSIZED"):
        # load 30A > cable ampacity 25A
        handler.execute(BreakerSelectArgs(current=30.0, cable_ampacity=25.0))


# ============================================================================
# 4. RACEWAY RUN TESTS
# ============================================================================


def test_raceway_run_geometry():
    handler = RacewayRunHandler()
    points = [[0.0, 0.0], [500.0, 0.0], [500.0, 500.0]]
    args = RacewayRunArgs(
        points=points,
        width=300.0,
        type="tray",
        rung=200.0,
        layer="E-TRAY-TEST",
    )
    res = handler.execute(args)

    assert res.status == "SUCCESS"
    assert res.vertex_count == 3
    assert res.width == 300.0
    assert res.type == "tray"
    assert res.rung_spacing == 200.0
    assert res.rung_count > 0
    assert res.entity_count > 2  # 2 rails + rungs
    assert len(res.lines) > 2


def test_raceway_run_validation_failures():
    handler = RacewayRunHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_POINTS"):
        handler.execute(RacewayRunArgs(points=[[0.0, 0.0]]))

    with pytest.raises(DegenerateGeometryError, match="INVALID_WIDTH"):
        handler.execute(RacewayRunArgs(points=[[0.0, 0.0], [100.0, 0.0]], width=-50.0))


# ============================================================================
# 5. HOME RUN TESTS
# ============================================================================


def test_home_run_elements():
    handler = HomeRunHandler()
    runs = [
        HomeRunItem(point=[100.0, 100.0], angle=45.0, circuit="P1-1,3", wires=2, ground=True),
        HomeRunItem(point=[200.0, 200.0], angle=90.0, circuit="P1-5", wires=3, ground=False),
    ]
    args = HomeRunArgs(runs=runs, length=40.0, height=3.0, layer="E-HOMERUN-TEST")
    res = handler.execute(args)

    assert res.status == "SUCCESS"
    assert res.runs_count == 2
    assert res.length == 40.0
    assert res.height == 3.0
    assert res.entity_count > 0
    assert len(res.lines) > 0


def test_home_run_validation_failures():
    handler = HomeRunHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_RUNS"):
        handler.execute(HomeRunArgs(runs=[]))

    with pytest.raises(DegenerateGeometryError, match="INVALID_LENGTH"):
        handler.execute(HomeRunArgs(runs=[HomeRunItem()], length=0.0))


# ============================================================================
# 6. WIRE TAG TESTS
# ============================================================================


def test_wire_tag_placement():
    handler = WireTagHandler()
    tags = [
        WireTagItem(point=[10.0, 10.0], id="W-101", from_node="PANEL-A", to_node="MTR-1", size="3x2.5"),
        WireTagItem(point=[20.0, 20.0], id="W-102"),
    ]
    args = WireTagArgs(tags=tags, height=3.0, underline=True)
    res = handler.execute(args)

    assert res.status == "SUCCESS"
    assert res.tag_count == 2
    assert res.processed_count == 4  # 2 texts + 2 underline lines
    assert len(res.lines) == 2


def test_wire_tag_validation_failures():
    handler = WireTagHandler()

    with pytest.raises(DegenerateGeometryError, match="DEGENERATE_GEOMETRY"):
        handler.execute(WireTagArgs(tags=[]))

    with pytest.raises(DegenerateGeometryError, match="DEGENERATE_GEOMETRY"):
        handler.execute(WireTagArgs(tags=[WireTagItem(point=[0.0, 0.0], id="")]))


# ============================================================================
# 7. SYMBOL LEGEND TESTS
# ============================================================================


def test_symbol_legend_generation():
    handler = SymbolLegendHandler()
    entries = [
        SymbolLegendEntry(type="receptacle", description="Duplex Receptacle 16A"),
        SymbolLegendEntry(type="switch", description="Single Pole Switch 10A"),
        SymbolLegendEntry(type="light", description="LED Troffer Fixture"),
        SymbolLegendEntry(type="ground", description="Safety Ground Connection"),
    ]
    args = SymbolLegendArgs(origin=[0.0, 0.0], title="ELECTRICAL LEGEND", entries=entries, size=3.0, height=2.5)
    res = handler.execute(args)

    assert res.status == "SUCCESS"
    assert res.entry_count == 4
    assert res.processed_count > 0
    assert len(res.lines) > 0
    assert len(res.circles) > 0


def test_symbol_legend_validation_failures():
    handler = SymbolLegendHandler()

    with pytest.raises(DegenerateGeometryError, match="DEGENERATE_GEOMETRY"):
        handler.execute(SymbolLegendArgs(entries=[]))

    with pytest.raises(DegenerateGeometryError, match="Invalid symbol type"):
        handler.execute(SymbolLegendArgs(entries=[SymbolLegendEntry(type="transformer", description="Substation")]))
