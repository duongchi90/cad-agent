"""tests/test_cleanroom_electrical_routing.py.

Comprehensive adversarial cleanroom test suite for Batch E1:
  - BusbarHandler (cadmind-busbar)
  - CableRunHandler (cadmind-cable-run)
  - CableTrenchHandler (cadmind-cable-trench)
  - CircuitNumberHandler (cadmind-circuit-number)
  - CircuitAuditHandler (cadmind-circuit-audit)
  - ElecLayerCheckHandler (cadmind-elec-layer-check)
"""

import math
import pytest

from cad_agent.cleanroom_electrical_routing import (
    BusbarArgs,
    BusbarHandler,
    CableRunArgs,
    CableRunHandler,
    CableTrenchArgs,
    CableTrenchHandler,
    CircuitAuditArgs,
    CircuitAuditHandler,
    CircuitNumberArgs,
    CircuitNumberHandler,
    DegenerateGeometryError,
    ElecLayerCheckArgs,
    ElecLayerCheckHandler,
)


# ============================================================================
# 1. BUSBAR TESTS
# ============================================================================


def test_busbar_default_geometry():
    handler = BusbarHandler()
    args = BusbarArgs(
        origin=[100.0, 200.0],
        length=1200.0,
        bars=4,
        spacing=50.0,
        thickness=10.0,
        labels=["L1", "L2", "L3", "N"],
        layer="E-BUS-TEST",
    )
    res = handler.execute(args)

    assert res.status == "SUCCESS"
    assert res.bar_count == 4
    assert res.length == 1200.0
    assert res.thickness == 10.0
    assert res.spacing == 50.0
    assert res.layer == "E-BUS-TEST"
    assert res.entity_count == 8  # 4 bars + 4 labels
    assert len(res.lines) == 16  # 4 segments per bar * 4 bars
    assert res.labels == ["L1", "L2", "L3", "N"]

    # Verify first bar coordinates
    # p0=(100, 200), p1=(1300, 200), p2=(1300, 210), p3=(100, 210)
    seg0 = res.lines[0]
    assert (seg0.start.x, seg0.start.y) == (100.0, 200.0)
    assert (seg0.end.x, seg0.end.y) == (1300.0, 200.0)


def test_busbar_validation_failures():
    handler = BusbarHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_BARS"):
        handler.execute(BusbarArgs(bars=0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_LENGTH"):
        handler.execute(BusbarArgs(length=0.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_THICKNESS"):
        handler.execute(BusbarArgs(thickness=-5.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_SPACING"):
        handler.execute(BusbarArgs(spacing=0.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_SPACING"):
        # spacing < thickness
        handler.execute(BusbarArgs(thickness=20.0, spacing=15.0))


# ============================================================================
# 2. CABLE RUN TESTS
# ============================================================================


def test_cable_run_open_and_closed():
    handler = CableRunHandler()
    points = [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0]]

    # Open route
    res_open = handler.execute(CableRunArgs(points=points, closed=False))
    assert res_open.status == "SUCCESS"
    assert res_open.point_count == 3
    assert math.isclose(res_open.total_length, 200.0, rel_tol=1e-7)
    assert not res_open.is_closed
    assert len(res_open.lines) == 2

    # Closed route (adds segment (100, 100) -> (0, 0) = sqrt(20000) ~ 141.421356)
    res_closed = handler.execute(CableRunArgs(points=points, closed=True))
    assert res_closed.status == "SUCCESS"
    assert res_closed.is_closed
    expected_len = 200.0 + math.sqrt(100.0**2 + 100.0**2)
    assert math.isclose(res_closed.total_length, expected_len, rel_tol=1e-7)
    assert len(res_closed.lines) == 3


def test_cable_run_homerun_ticks():
    handler = CableRunHandler()
    points = [[0.0, 0.0], [100.0, 0.0], [100.0, 50.0]]
    res = handler.execute(CableRunArgs(points=points, homerun=True))

    assert res.status == "SUCCESS"
    assert res.has_homerun
    assert res.entity_count == 4  # 1 polyline + 3 ticks
    assert len(res.lines) == 2 + 3  # 2 route segments + 3 tick segments

    # First segment: (0,0) -> (100,0). ux=1, uy=0, normal: nx=0, ny=1
    # baseOffset = min(15.0, 25.0) = 15.0
    # tick 0: cx = 15, cy = 0; tick from (15, -4) to (15, 4)
    tick0 = res.lines[2]
    assert math.isclose(tick0.start.x, 15.0, abs_tol=1e-5)
    assert math.isclose(tick0.start.y, -4.0, abs_tol=1e-5)
    assert math.isclose(tick0.end.x, 15.0, abs_tol=1e-5)
    assert math.isclose(tick0.end.y, 4.0, abs_tol=1e-5)


def test_cable_run_validation_failures():
    handler = CableRunHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_POINTS"):
        handler.execute(CableRunArgs(points=[[0.0, 0.0]]))

    with pytest.raises(DegenerateGeometryError, match="INVALID_COORDINATES"):
        handler.execute(CableRunArgs(points=[[0.0, 0.0], [float("nan"), 10.0]]))


# ============================================================================
# 3. CABLE TRENCH TESTS
# ============================================================================


def test_cable_trench_single_and_multi_cable():
    handler = CableTrenchHandler()

    # Single cable
    res1 = handler.execute(
        CableTrenchArgs(
            origin=[0.0, 0.0],
            width=600.0,
            depth=900.0,
            cables=1,
            cable_dia=50.0,
            cable_depth=600.0,
        )
    )
    assert res1.status == "SUCCESS"
    assert res1.cable_count == 1
    assert res1.cable_depth == 600.0
    assert len(res1.circles) == 1
    assert math.isclose(res1.circles[0].center.x, 0.0, abs_tol=1e-5)
    assert math.isclose(res1.circles[0].center.y, -600.0, abs_tol=1e-5)
    assert math.isclose(res1.circles[0].radius, 25.0, abs_tol=1e-5)
    assert res1.entity_count == 5  # Grade, Trench, Sand, Tape, 1 Cable

    # Multiple cables (3 cables across width 800)
    res3 = handler.execute(
        CableTrenchArgs(
            origin=[100.0, 50.0],
            width=800.0,
            depth=1200.0,
            cables=3,
            cable_dia=60.0,
        )
    )
    assert res3.status == "SUCCESS"
    assert res3.cable_count == 3
    # Default cable depth = 0.75 * 1200 = 900
    assert math.isclose(res3.cable_depth, 900.0, abs_tol=1e-5)
    assert len(res3.circles) == 3
    # Centers: width/(3+1) = 200. ox=100, hw=400.
    # c=0: 100 - 400 + 200*1 = -100
    # c=1: 100 - 400 + 200*2 = 100
    # c=2: 100 - 400 + 200*3 = 300
    assert math.isclose(res3.circles[0].center.x, -100.0, abs_tol=1e-5)
    assert math.isclose(res3.circles[1].center.x, 100.0, abs_tol=1e-5)
    assert math.isclose(res3.circles[2].center.x, 300.0, abs_tol=1e-5)
    assert all(math.isclose(c.center.y, 50.0 - 900.0, abs_tol=1e-5) for c in res3.circles)


def test_cable_trench_validation_failures():
    handler = CableTrenchHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_WIDTH"):
        handler.execute(CableTrenchArgs(width=0.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_DEPTH"):
        handler.execute(CableTrenchArgs(depth=-100.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_CABLES"):
        handler.execute(CableTrenchArgs(cables=0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_CABLE_DEPTH"):
        # cable_depth >= depth
        handler.execute(CableTrenchArgs(depth=800.0, cable_depth=850.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_CABLE_DEPTH"):
        handler.execute(CableTrenchArgs(depth=800.0, cable_depth=-10.0))


# ============================================================================
# 4. CIRCUIT NUMBER TESTS
# ============================================================================


def test_circuit_number_generation():
    handler = CircuitNumberHandler()
    points = [[10.0, 20.0], [30.0, 40.0], [50.0, 60.0]]
    args = CircuitNumberArgs(
        points=points,
        prefix="PANEL2-",
        start=5,
        pad=3,
        height=3.5,
        layer="E-CIRCUIT-TEST",
    )
    res = handler.execute(args)

    assert res.status == "SUCCESS"
    assert res.tags_created == 3
    assert res.layer == "E-CIRCUIT-TEST"
    assert res.generated_labels == ["PANEL2-005", "PANEL2-006", "PANEL2-007"]
    assert res.entity_count == 3
    assert len(res.positions) == 3


def test_circuit_number_validation_failures():
    handler = CircuitNumberHandler()

    with pytest.raises(DegenerateGeometryError, match="INVALID_POINTS"):
        handler.execute(CircuitNumberArgs(points=[]))

    with pytest.raises(DegenerateGeometryError, match="INVALID_HEIGHT"):
        handler.execute(CircuitNumberArgs(points=[[0.0, 0.0]], height=0.0))

    with pytest.raises(DegenerateGeometryError, match="INVALID_PAD"):
        handler.execute(CircuitNumberArgs(points=[[0.0, 0.0]], pad=-1))


# ============================================================================
# 5. CIRCUIT AUDIT TESTS
# ============================================================================


def test_circuit_audit_duplicate_detection():
    handler = CircuitAuditHandler()
    mock_entities = [
        {"layer": "E-CIRCUIT", "text": "P1-01", "handle": "H1"},
        {"layer": "E-CIRCUIT", "text": "P1-02", "handle": "H2"},
        {"layer": "E-CIRCUIT", "text": "P1-01", "handle": "H3"},
        {"layer": "E-CIRCUIT", "text": "P1-05", "handle": "H4"},
        {"layer": "E-CIRCUIT", "text": "P1-01", "handle": "H5"},
        {"layer": "E-CIRCUIT", "text": "P1-05", "handle": "H6"},
        {"layer": "E-OTHER", "text": "P1-01", "handle": "H7"},  # Wrong layer
        {"layer": "E-CIRCUIT", "text": "P2-01", "handle": "H8"},  # Different prefix
    ]

    args = CircuitAuditArgs(layer="E-CIRCUIT", prefix="P1-")
    res = handler.execute(args, entities=mock_entities)

    assert res.status == "SUCCESS"
    assert res.layer == "E-CIRCUIT"
    assert res.prefix == "P1-"
    assert res.total_tags_scanned == 6
    assert res.unique_tags_count == 3  # P1-01, P1-02, P1-05
    assert res.duplicate_tags_count == 2  # P1-01 (count 3), P1-05 (count 2)

    # First duplicate should be P1-01 (count 3)
    assert res.duplicates[0].tag == "P1-01"
    assert res.duplicates[0].count == 3
    assert res.duplicates[0].handles == ["H1", "H3", "H5"]

    # Second duplicate should be P1-05 (count 2)
    assert res.duplicates[1].tag == "P1-05"
    assert res.duplicates[1].count == 2
    assert res.duplicates[1].handles == ["H4", "H6"]


# ============================================================================
# 6. ELEC LAYER CHECK TESTS
# ============================================================================


def test_elec_layer_check_compliance():
    handler = ElecLayerCheckHandler()
    drawing_layers = ["0", "E-POWER", "Defpoints", "M-HVAC", "S-REBAR"]
    layer_counts = {"0": 5, "E-POWER": 20, "Defpoints": 0, "M-HVAC": 12, "S-REBAR": 5}

    args = ElecLayerCheckArgs(
        allowed_layers=["0", "E-POWER", "Defpoints"],
        allowed_prefixes=["E-", "0", "Defpoints"],
    )
    res = handler.execute(args, drawing_layers=drawing_layers, layer_counts=layer_counts)

    assert res.status == "SUCCESS"
    assert res.total_layers == 5
    assert res.standard_layers_count == 3
    assert res.non_standard_layers_count == 2
    assert math.isclose(res.compliance_rate_percent, 60.0, abs_tol=1e-2)
    assert res.standard_layers == ["0", "E-POWER", "Defpoints"]

    # Non-standard layers sorted descending by count: M-HVAC (12), then S-REBAR (5)
    assert len(res.non_standard_layers) == 2
    assert res.non_standard_layers[0].layer_name == "M-HVAC"
    assert res.non_standard_layers[0].entity_count == 12
    assert res.non_standard_layers[1].layer_name == "S-REBAR"
    assert res.non_standard_layers[1].entity_count == 5
