"""tests/test_cleanroom_structural_rebar.py.

Pytest test suite for Batch M4: Structural Rebar & Civil Concrete Drafting + Quantity Takeoff.
Strict 1:1 parity with CadMind cleanroom contracts & physical C# handlers:
  - RebarBeamHandler (TierBWave12Handlers.cs)
  - RebarHookHandler (TierBWave12Handlers.cs)
  - RebarMeshHandler (TierBWave12Handlers.cs)
  - FoundationFootingHandler (TierBWave12Handlers.cs)
  - SteelWeightHandler (TierBWave15Handlers.cs)
"""

import math
import pytest

from cad_agent.cleanroom_mechanical import Point2D
from cad_agent.cleanroom_structural_rebar import (
    ContainmentError,
    DegenerateGeometryError,
    FoundationFootingHandler,
    FoundationFootingResult,
    InvalidRebarParameterError,
    RebarBeamHandler,
    RebarBeamResult,
    RebarHookHandler,
    RebarHookResult,
    RebarMeshHandler,
    RebarMeshResult,
    SteelWeightHandler,
    SteelWeightResult,
)


# ============================================================================
# 1. REBAR BEAM TESTS (RebarBeamHandler)
# ============================================================================


def test_rebar_beam_defaults():
    res = RebarBeamHandler.execute()
    assert isinstance(res, RebarBeamResult)
    assert res.status == "OK"
    assert res.entity_count == 8
    assert res.width == 300.0
    assert res.depth == 500.0
    assert res.mark == "B1-4T20"
    assert res.layer == "S-CONC-REBR"
    assert len(res.stirrup_lines) == 4
    assert len(res.corner_bars) == 4
    assert res.text_height == 15.0


def test_rebar_beam_minimum_boundary():
    # Minimum valid dimensions: width 100, depth 150, cover 15, rebar 6, stirrup 6
    res = RebarBeamHandler.execute(
        width=100.0,
        depth=150.0,
        cover=15.0,
        rebar_dia=6.0,
        stirrup_dia=6.0,
        mark="B-MIN",
    )
    assert res.status == "OK"
    assert res.width == 100.0
    assert res.depth == 150.0
    assert res.corner_bars[0].radius == 3.0


def test_rebar_beam_large_section():
    # Heavy civil section: 1200x2400, cover 50, rebar 40, stirrup 16
    res = RebarBeamHandler.execute(
        origin_x=-500.0,
        origin_y=-1000.0,
        width=1200.0,
        depth=2400.0,
        cover=50.0,
        rebar_dia=40.0,
        stirrup_dia=16.0,
        mark="B-HEAVY",
    )
    assert res.status == "OK"
    assert res.corner_bars[0].radius == 20.0
    assert res.stirrup_lines[0].start == Point2D(-450.0, -950.0)


def test_rebar_beam_geometry_coordinates():
    origin_x = 100.0
    origin_y = 200.0
    width = 400.0
    depth = 600.0
    cover = 40.0
    rebar_dia = 25.0
    stirrup_dia = 10.0

    res = RebarBeamHandler.execute(
        origin_x=origin_x,
        origin_y=origin_y,
        width=width,
        depth=depth,
        cover=cover,
        rebar_dia=rebar_dia,
        stirrup_dia=stirrup_dia,
        mark="B-CUSTOM",
    )

    # Stirrup bounds
    assert res.stirrup_lines[0].start == Point2D(origin_x + cover, origin_y + cover)
    assert res.stirrup_lines[0].end == Point2D(origin_x + width - cover, origin_y + cover)
    assert res.stirrup_lines[1].end == Point2D(origin_x + width - cover, origin_y + depth - cover)
    assert res.stirrup_lines[2].end == Point2D(origin_x + cover, origin_y + depth - cover)
    assert res.stirrup_lines[3].end == Point2D(origin_x + cover, origin_y + cover)

    # Longitudinal bars
    expected_top_y = origin_y + depth - cover - stirrup_dia / 2.0
    assert res.top_bar_line.start.y == expected_top_y
    assert res.top_bar_line.end.y == expected_top_y

    expected_bot_y = origin_y + cover + stirrup_dia / 2.0
    assert res.bottom_bar_line.start.y == expected_bot_y
    assert res.bottom_bar_line.end.y == expected_bot_y

    # Corner circles
    bar_rad = rebar_dia / 2.0
    inset = cover + stirrup_dia + bar_rad
    assert res.corner_bars[0].center == Point2D(origin_x + inset, origin_y + inset)
    assert res.corner_bars[0].radius == bar_rad
    assert res.corner_bars[1].center == Point2D(origin_x + width - inset, origin_y + inset)
    assert res.corner_bars[2].center == Point2D(origin_x + width - inset, origin_y + depth - inset)
    assert res.corner_bars[3].center == Point2D(origin_x + inset, origin_y + depth - inset)

    # Label position
    assert res.label_position == Point2D(origin_x + width / 2.0, origin_y + depth + 25.0)


def test_rebar_beam_invalid_dimensions():
    with pytest.raises(DegenerateGeometryError, match="Beam width must be at least 100"):
        RebarBeamHandler.execute(width=99.0)

    with pytest.raises(DegenerateGeometryError, match="Beam depth must be at least 150"):
        RebarBeamHandler.execute(depth=149.0)

    # Cover < 15
    with pytest.raises(DegenerateGeometryError, match="Concrete cover must be between 15"):
        RebarBeamHandler.execute(cover=14.0)

    # Cover >= minDim / 3 (minDim = 300 => cover >= 100)
    with pytest.raises(DegenerateGeometryError, match="Concrete cover must be between 15"):
        RebarBeamHandler.execute(width=300.0, depth=500.0, cover=100.0)

    # Rebar diameter out of [6, 50]
    with pytest.raises(DegenerateGeometryError, match="Rebar diameter"):
        RebarBeamHandler.execute(rebar_dia=5.0)
    with pytest.raises(DegenerateGeometryError, match="Rebar diameter"):
        RebarBeamHandler.execute(rebar_dia=51.0)

    # Stirrup diameter out of [6, 16]
    with pytest.raises(DegenerateGeometryError, match="Stirrup diameter"):
        RebarBeamHandler.execute(stirrup_dia=5.0)
    with pytest.raises(DegenerateGeometryError, match="Stirrup diameter"):
        RebarBeamHandler.execute(stirrup_dia=17.0)

    # Bar counts
    with pytest.raises(DegenerateGeometryError, match="Bar count"):
        RebarBeamHandler.execute(bar_count_top=1)
    with pytest.raises(DegenerateGeometryError, match="Bar count"):
        RebarBeamHandler.execute(bar_count_bot=0)

    # Empty mark
    with pytest.raises(DegenerateGeometryError, match="Beam mark cannot be empty"):
        RebarBeamHandler.execute(mark="")
    with pytest.raises(DegenerateGeometryError, match="Beam mark cannot be empty"):
        RebarBeamHandler.execute(mark="   ")

    # NaN / Inf
    with pytest.raises(DegenerateGeometryError, match="finite numbers"):
        RebarBeamHandler.execute(width=float("nan"))
    with pytest.raises(DegenerateGeometryError, match="finite numbers"):
        RebarBeamHandler.execute(depth=float("inf"))


@pytest.mark.parametrize("param", ["origin_x", "origin_y", "cover", "rebar_dia", "stirrup_dia"])
def test_rebar_beam_nan_inf_all_params(param):
    kwargs = {param: float("nan")}
    with pytest.raises(DegenerateGeometryError, match="finite numbers"):
        RebarBeamHandler.execute(**kwargs)


# ============================================================================
# 2. REBAR HOOK TESTS (RebarHookHandler)
# ============================================================================


def test_rebar_hook_defaults():
    res = RebarHookHandler.execute()
    assert isinstance(res, RebarHookResult)
    assert res.status == "OK"
    assert res.entity_count == 3
    assert res.bend_angle_deg == 90.0
    assert res.bend_radius == 30.0
    assert res.tag == "H-T20"
    assert res.layer == "S-CONC-REBR"
    assert math.isclose(res.bulge, math.tan(math.radians(90.0) / 4.0), rel_tol=1e-6)
    assert res.mandrel_circle.radius == 30.0


def test_rebar_hook_angles_and_handedness():
    # 90 degrees left bend
    res90_l = RebarHookHandler.execute(bend_angle_deg=90.0, bend_left=True)
    assert res90_l.bulge > 0.0

    # 90 degrees right bend
    res90_r = RebarHookHandler.execute(bend_angle_deg=90.0, bend_left=False)
    assert res90_r.bulge < 0.0
    assert math.isclose(res90_l.bulge, -res90_r.bulge)

    # 135 degrees
    res135 = RebarHookHandler.execute(bend_angle_deg=135.0)
    expected_b135 = math.tan(math.radians(135.0) / 4.0)
    assert math.isclose(res135.bulge, expected_b135, rel_tol=1e-6)

    # 180 degrees (standard return bend)
    res180 = RebarHookHandler.execute(bend_angle_deg=180.0)
    expected_b180 = math.tan(math.radians(180.0) / 4.0)  # tan(45 deg) = 1.0
    assert math.isclose(res180.bulge, 1.0, rel_tol=1e-6)


def test_rebar_hook_geometry_continuity():
    res = RebarHookHandler.execute(
        start_x=10.0,
        start_y=20.0,
        leg_length=120.0,
        bend_angle_deg=90.0,
        bend_radius=25.0,
        tail_length=60.0,
        direction_x=0.0,
        direction_y=1.0,  # Vertical upward leg
        bend_left=True,
    )

    # Leg starts at (10, 20) and goes up 120 -> ends at (10, 140)
    assert res.leg_line.start == Point2D(10.0, 20.0)
    assert res.leg_line.end == Point2D(10.0, 140.0)

    # Left bend from vertical up: normal is (-1, 0) -> mandrel center at (10 - 25, 140) = (-15, 140)
    assert res.mandrel_circle.center == Point2D(-15.0, 140.0)
    assert res.mandrel_circle.radius == 25.0

    # Hook arc connects to mandrel center
    assert res.hook_arc.center == Point2D(-15.0, 140.0)
    assert res.hook_arc.radius == 25.0


def test_rebar_hook_arbitrary_direction():
    # Diagonal 45-degree direction vector (3.0, 3.0) - unnormalized input
    res = RebarHookHandler.execute(
        direction_x=3.0,
        direction_y=3.0,
        leg_length=100.0,
        bend_angle_deg=90.0,
        bend_radius=20.0,
        tail_length=40.0,
    )
    assert res.status == "OK"
    u = 1.0 / math.sqrt(2.0)
    assert math.isclose(res.leg_line.end.x, 100.0 * u, abs_tol=1e-6)
    assert math.isclose(res.leg_line.end.y, 100.0 * u, abs_tol=1e-6)


def test_rebar_hook_invalid_inputs():
    with pytest.raises(DegenerateGeometryError, match="Leg length must be at least 50"):
        RebarHookHandler.execute(leg_length=49.0)

    with pytest.raises(DegenerateGeometryError, match="Tail length must be at least 30"):
        RebarHookHandler.execute(tail_length=29.0)

    with pytest.raises(DegenerateGeometryError, match="Bend radius must be at least 12"):
        RebarHookHandler.execute(bend_radius=11.0)

    with pytest.raises(DegenerateGeometryError, match="Direction vector cannot be degenerate"):
        RebarHookHandler.execute(direction_x=0.0, direction_y=0.0)

    # Unsupported bend angles
    with pytest.raises(DegenerateGeometryError, match="exactly 90, 135, or 180 degrees"):
        RebarHookHandler.execute(bend_angle_deg=45.0)
    with pytest.raises(DegenerateGeometryError, match="exactly 90, 135, or 180 degrees"):
        RebarHookHandler.execute(bend_angle_deg=60.0)
    with pytest.raises(DegenerateGeometryError, match="exactly 90, 135, or 180 degrees"):
        RebarHookHandler.execute(bend_angle_deg=120.0)

    with pytest.raises(DegenerateGeometryError, match="Hook tag cannot be empty"):
        RebarHookHandler.execute(tag="")


@pytest.mark.parametrize(
    "param", ["start_x", "start_y", "leg_length", "bend_radius", "tail_length"]
)
def test_rebar_hook_nan_inf(param):
    kwargs = {param: float("inf")}
    with pytest.raises(DegenerateGeometryError, match="finite numbers"):
        RebarHookHandler.execute(**kwargs)


# ============================================================================
# 3. REBAR MESH TESTS (RebarMeshHandler)
# ============================================================================


def test_rebar_mesh_defaults():
    res = RebarMeshHandler.execute()
    assert isinstance(res, RebarMeshResult)
    assert res.status == "OK"
    assert res.entity_count == 8
    assert res.length == 600.0
    assert res.width == 400.0
    assert res.mesh_code == "A252"
    assert res.layer == "S-CONC-REBR"
    assert len(res.boundary_lines) == 4
    assert len(res.longitudinal_lines) == 3
    assert len(res.transverse_lines) == 3
    assert res.centroid == Point2D(300.0, 200.0)


def test_rebar_mesh_wire_positions():
    ox, oy = 50.0, 80.0
    length, width = 800.0, 600.0
    res = RebarMeshHandler.execute(
        origin_x=ox, origin_y=oy, length=length, width=width, mesh_code="BRC-65"
    )

    # 3 Longitudinal lines at 25%, 50%, 75% of width
    expected_y = [oy + f * width for f in (0.25, 0.50, 0.75)]
    for i, line in enumerate(res.longitudinal_lines):
        assert math.isclose(line.start.y, expected_y[i])
        assert math.isclose(line.end.y, expected_y[i])
        assert math.isclose(line.start.x, ox)
        assert math.isclose(line.end.x, ox + length)

    # 3 Transverse lines at 25%, 50%, 75% of length
    expected_x = [ox + f * length for f in (0.25, 0.50, 0.75)]
    for i, line in enumerate(res.transverse_lines):
        assert math.isclose(line.start.x, expected_x[i])
        assert math.isclose(line.end.x, expected_x[i])
        assert math.isclose(line.start.y, oy)
        assert math.isclose(line.end.y, oy + width)


def test_rebar_mesh_non_square_aspect_ratios():
    # Long panel: 2000x300
    res = RebarMeshHandler.execute(length=2000.0, width=300.0)
    assert res.status == "OK"
    assert res.centroid == Point2D(1000.0, 150.0)

    # Wide panel: 300x1500
    res2 = RebarMeshHandler.execute(length=300.0, width=1500.0)
    assert res2.status == "OK"
    assert res2.centroid == Point2D(150.0, 750.0)


def test_rebar_mesh_invalid_dimensions():
    with pytest.raises(DegenerateGeometryError, match="Mesh length must be at least 200"):
        RebarMeshHandler.execute(length=199.0)

    with pytest.raises(DegenerateGeometryError, match="Mesh width must be at least 200"):
        RebarMeshHandler.execute(width=199.0)

    with pytest.raises(DegenerateGeometryError, match="Wire spacing must be positive"):
        RebarMeshHandler.execute(spacing_x=0.0)

    with pytest.raises(DegenerateGeometryError, match="Wire spacing must be positive"):
        RebarMeshHandler.execute(spacing_y=-10.0)

    with pytest.raises(DegenerateGeometryError, match="Mesh code cannot be empty"):
        RebarMeshHandler.execute(mesh_code="   ")


@pytest.mark.parametrize(
    "param", ["origin_x", "origin_y", "length", "width", "spacing_x", "spacing_y"]
)
def test_rebar_mesh_nan_inf(param):
    kwargs = {param: float("nan")}
    with pytest.raises(DegenerateGeometryError, match="finite numbers"):
        RebarMeshHandler.execute(**kwargs)


# ============================================================================
# 4. FOUNDATION FOOTING TESTS (FoundationFootingHandler)
# ============================================================================


def test_foundation_footing_defaults():
    res = FoundationFootingHandler.execute()
    assert isinstance(res, FoundationFootingResult)
    assert res.status == "OK"
    assert res.entity_count == 5
    assert res.pad_length == 1200.0
    assert res.pad_width == 1200.0
    assert res.footing_id == "F1"
    assert res.layer == "S-STRC-FNDN"
    assert len(res.pad_lines) == 4
    assert len(res.pedestal_lines) == 4

    # Centerlines extend 10% beyond 1200 / 2 = 600 -> 660
    assert res.centerline_x.start == Point2D(-660.0, 0.0)
    assert res.centerline_x.end == Point2D(660.0, 0.0)
    assert res.centerline_y.start == Point2D(0.0, -660.0)
    assert res.centerline_y.end == Point2D(0.0, 660.0)


def test_foundation_footing_pedestal_offset():
    # Offset within valid bounds
    res = FoundationFootingHandler.execute(
        center_x=500.0,
        center_y=500.0,
        pad_length=1500.0,
        pad_width=1500.0,
        col_length=500.0,
        col_width=500.0,
        offset_x=100.0,
        offset_y=-100.0,
        footing_id="F2",
    )
    assert res.status == "OK"
    ped_cx = 500.0 + 100.0
    ped_cy = 500.0 - 100.0
    assert res.pedestal_lines[0].start == Point2D(ped_cx - 250.0, ped_cy - 250.0)
    assert res.pedestal_lines[0].end == Point2D(ped_cx + 250.0, ped_cy - 250.0)


def test_foundation_footing_containment_boundary_tolerance():
    # Pad half = 600, Col half = 200.
    # Max offset before violation = 400.
    # Offset = 399.9 -> strictly contained (PASS)
    res = FoundationFootingHandler.execute(
        pad_length=1200.0, pad_width=1200.0, col_length=400.0, col_width=400.0, offset_x=399.9
    )
    assert res.status == "OK"

    # Offset = 400.0 -> touches boundary (VIOLATION)
    with pytest.raises(ContainmentError, match="strictly contained"):
        FoundationFootingHandler.execute(
            pad_length=1200.0, pad_width=1200.0, col_length=400.0, col_width=400.0, offset_x=400.0
        )


def test_foundation_footing_containment_violations():
    # Pad half = 600, Col half = 200. Offset = 400 => 400 + 200 = 600 >= 600 (violation!)
    with pytest.raises(ContainmentError, match="strictly contained"):
        FoundationFootingHandler.execute(
            pad_length=1200.0, pad_width=1200.0, col_length=400.0, col_width=400.0, offset_x=400.0
        )

    # Negative offset violation
    with pytest.raises(ContainmentError, match="strictly contained"):
        FoundationFootingHandler.execute(
            pad_length=1200.0, pad_width=1200.0, col_length=400.0, col_width=400.0, offset_y=-401.0
        )

    # Pedestal larger than pad
    with pytest.raises(ContainmentError, match="strictly contained"):
        FoundationFootingHandler.execute(
            pad_length=1200.0, pad_width=1200.0, col_length=1300.0, col_width=400.0
        )


def test_foundation_footing_invalid_dimensions():
    with pytest.raises(
        DegenerateGeometryError, match="Footing pad length and width must be at least 300"
    ):
        FoundationFootingHandler.execute(pad_length=299.0)

    with pytest.raises(
        DegenerateGeometryError, match="Column pedestal length and width must be at least 100"
    ):
        FoundationFootingHandler.execute(col_length=99.0)

    with pytest.raises(DegenerateGeometryError, match="Footing identifier cannot be empty"):
        FoundationFootingHandler.execute(footing_id="")


@pytest.mark.parametrize(
    "param",
    [
        "center_x",
        "center_y",
        "pad_length",
        "pad_width",
        "col_length",
        "col_width",
        "offset_x",
        "offset_y",
    ],
)
def test_foundation_footing_nan_inf(param):
    kwargs = {param: float("nan")}
    with pytest.raises(DegenerateGeometryError, match="finite numbers"):
        FoundationFootingHandler.execute(**kwargs)


# ============================================================================
# 5. STEEL WEIGHT TESTS (SteelWeightHandler)
# ============================================================================


def test_steel_weight_csharp_contract_oracle():
    """Exact oracle test matching CadMind C# TierBWave15ContractTests."""
    rows = [
        ("01", 16.0, 4500.0, 4),  # 4 * 4.5m = 18m; 16^2/162 = 1.5802 kg/m; 18 * 1.5802 = 28.44 kg
        ("02", 20.0, 5000.0, 2),  # 2 * 5.0m = 10m; 20^2/162 = 2.4691 kg/m; 10 * 2.4691 = 24.69 kg
    ]

    res = SteelWeightHandler.execute(rows, decimals=2)
    assert isinstance(res, SteelWeightResult)
    assert res.status == "SUCCESS"
    assert res.row_count == 2
    assert res.total_length_m == 28.0
    # In C# TierBWave15Handlers.cs, grandTotalWeightKg sums unrounded row weights:
    # 18.0 * (256/162) + 10.0 * (400/162) = 53.1358... -> rounded to 2 decimals gives 53.14.
    assert math.isclose(res.total_weight_kg, 53.14, abs_tol=0.02)

    # Row 1
    r1 = res.rows[0]
    assert r1.mark == "01"
    assert r1.dia_mm == 16.0
    assert r1.length_mm == 4500.0
    assert r1.count == 4
    assert r1.total_length_m == 18.0
    assert r1.unit_weight_kg_per_m == 1.5802
    assert r1.total_weight_kg == 28.44

    # Row 2
    r2 = res.rows[1]
    assert r2.mark == "02"
    assert r2.dia_mm == 20.0
    assert r2.length_mm == 5000.0
    assert r2.count == 2
    assert r2.total_length_m == 10.0
    assert r2.unit_weight_kg_per_m == 2.4691
    assert r2.total_weight_kg == 24.69


def test_steel_weight_various_diameters():
    # ISO standard rebar sizes: 8, 10, 12, 25, 32
    rows = [
        ("T8", 8.0, 3000.0, 10),  # 30m, 8^2/162 = 0.3951 kg/m, 11.85 kg
        ("T10", 10.0, 4000.0, 5),  # 20m, 100/162 = 0.6173 kg/m, 12.35 kg
        ("T12", 12.0, 6000.0, 8),  # 48m, 144/162 = 0.8889 kg/m, 42.67 kg
        ("T25", 25.0, 12000.0, 2),  # 24m, 625/162 = 3.8580 kg/m, 92.59 kg
        ("T32", 32.0, 12000.0, 1),  # 12m, 1024/162 = 6.3210 kg/m, 75.85 kg
    ]
    res = SteelWeightHandler.execute(rows, decimals=2)
    assert res.row_count == 5
    assert res.total_length_m == 134.0
    expected_total_wt = round(11.85 + 12.35 + 42.67 + 92.59 + 75.85, 2)
    assert math.isclose(res.total_weight_kg, expected_total_wt, abs_tol=0.05)


def test_steel_weight_decimals_precision():
    rows = [("D1", 10.0, 1000.0, 1)]  # 1m, 100/162 = 0.61728395...
    # Decimals = 0
    res0 = SteelWeightHandler.execute(rows, decimals=0)
    assert res0.total_weight_kg == 1.0

    # Decimals = 4
    res4 = SteelWeightHandler.execute(rows, decimals=4)
    assert res4.total_weight_kg == 0.6173


def test_steel_weight_invalid_inputs():
    with pytest.raises(InvalidRebarParameterError, match="Rows cannot be empty"):
        SteelWeightHandler.execute([])

    with pytest.raises(InvalidRebarParameterError, match="Decimals must be between 0 and 8"):
        SteelWeightHandler.execute([("T1", 12.0, 1000.0, 1)], decimals=-1)

    with pytest.raises(InvalidRebarParameterError, match="Decimals must be between 0 and 8"):
        SteelWeightHandler.execute([("T1", 12.0, 1000.0, 1)], decimals=9)

    with pytest.raises(InvalidRebarParameterError, match="Bar diameter must be positive"):
        SteelWeightHandler.execute([("T1", 0.0, 1000.0, 1)])

    with pytest.raises(InvalidRebarParameterError, match="Bar diameter must be positive"):
        SteelWeightHandler.execute([("T1", -12.0, 1000.0, 1)])

    with pytest.raises(InvalidRebarParameterError, match="Bar cut length must be positive"):
        SteelWeightHandler.execute([("T1", 12.0, 0.0, 1)])

    with pytest.raises(InvalidRebarParameterError, match="Bar count must be greater than zero"):
        SteelWeightHandler.execute([("T1", 12.0, 1000.0, 0)])

    with pytest.raises(DegenerateGeometryError, match="finite numbers"):
        SteelWeightHandler.execute([("T1", float("nan"), 1000.0, 1)])

    with pytest.raises(DegenerateGeometryError, match="finite numbers"):
        SteelWeightHandler.execute([("T1", 12.0, float("inf"), 1)])
