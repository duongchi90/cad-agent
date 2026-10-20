"""tests/test_cleanroom_structural_annotations.py.

Batch ST2 Test Suite: Structural Schedules, Material Tags, Rebar Callouts & Area Takeoffs.
Validates cleanroom parity against physical C# source:
  - BarScheduleHandler (cadmind-bar-schedule)
  - MaterialTagHandler (cadmind-material-tag)
  - RebarCalloutHandler (cadmind-rebar-callout)
  - CoordLabelHandler (cadmind-coord-label)
  - AreaTakeoffHandler (cadmind-area-takeoff)
  - LayerStandardCheckHandler (cadmind-layer-standard-check)

Completes Domain 3 (STRUCTURAL: 25/25 registered tools).
"""

import pytest

from cad_agent.cleanroom_structural_annotations import (
    AreaTakeoffArgs,
    AreaTakeoffHandler,
    BarScheduleArgs,
    BarScheduleHandler,
    BarScheduleRow,
    CleanroomError,
    CoordLabelArgs,
    CoordLabelHandler,
    DegenerateGeometryError,
    LayerStandardCheckArgs,
    LayerStandardCheckHandler,
    MaterialTagArgs,
    MaterialTagHandler,
    RebarCalloutArgs,
    RebarCalloutHandler,
)


# ============================================================================
# 1. BarScheduleHandler Tests
# ============================================================================


def test_bar_schedule_oracle_1_weight() -> None:
    handler = BarScheduleHandler()
    # d = 16 mm, L = 3000 mm, NumMembers = 2, BarsPerMember = 4 (total 8 bars)
    # Oracle 1: (16^2 / 162.0) * 3.0 * 8 = (256 / 162.0) * 24 = 37.93 kg
    rows = [
        BarScheduleRow(bar_mark="01", diameter=16.0, num_members=2, bars_per_member=4, length_mm=3000.0),
    ]
    args = BarScheduleArgs(rows=rows, insertion_point=[0.0, 0.0])
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.row_count == 1
    assert res.total_weight_kg == 37.93
    assert len(res.grid_lines) > 0


def test_bar_schedule_negative_diameter_raises() -> None:
    with pytest.raises(DegenerateGeometryError):
        BarScheduleRow(bar_mark="01", diameter=-10.0, num_members=1, bars_per_member=1, length_mm=1000.0)


def test_bar_schedule_empty_rows_rejected() -> None:
    handler = BarScheduleHandler()
    res = handler.execute(BarScheduleArgs(rows=[]))
    assert res.status == "ERROR"
    assert "requires at least one row" in res.message


# ============================================================================
# 2. MaterialTagHandler Tests
# ============================================================================


def test_material_tag_valid_with_frame() -> None:
    handler = MaterialTagHandler()
    args = MaterialTagArgs(
        target_point=[10.0, 10.0],
        text_point=[50.0, 50.0],
        material_code="C30/37",
        has_frame=True,
    )
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.count == 5  # 1 leader line + 4 frame lines


def test_material_tag_coincident_points_rejected() -> None:
    handler = MaterialTagHandler()
    args = MaterialTagArgs(
        target_point=[10.0, 10.0],
        text_point=[10.0, 10.0],
        material_code="STEEL",
    )
    res = handler.execute(args)
    assert res.status == "ERROR"
    assert "TargetPoint and TextPoint are coincident" in res.message


# ============================================================================
# 3. RebarCalloutHandler Tests
# ============================================================================


def test_rebar_callout_formatting() -> None:
    handler = RebarCalloutHandler()
    args = RebarCalloutArgs(count=3, dia=16.0, spacing=200.0, bar="D")
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.callout_note == "3D16@200"


def test_rebar_callout_coincident_leader_rejected() -> None:
    handler = RebarCalloutHandler()
    args = RebarCalloutArgs(point=[10.0, 20.0], leader_to=[10.0, 20.0])
    res = handler.execute(args)
    assert res.status == "ERROR"
    assert "coincident" in res.message


# ============================================================================
# 4. CoordLabelHandler Tests
# ============================================================================


def test_coord_label_formatting() -> None:
    handler = CoordLabelHandler()
    args = CoordLabelArgs(x=123.456, y=789.012, prefix="PT1: ")
    res = handler.execute(args)

    assert res.status == "OK"
    assert "123.46, 789.01" in res.message


# ============================================================================
# 5. AreaTakeoffHandler Tests
# ============================================================================


def test_area_takeoff_oracle_2_scaling() -> None:
    handler = AreaTakeoffHandler()
    entity_areas = {
        "H1": 50.0,
        "H2": 25.0,
    }
    # Oracle 2: raw 50.0 with scale 1.2 -> 60.00
    args = AreaTakeoffArgs(handles=["H1", "H2"], labels=["ZONE_A", "ZONE_B"], scale=1.2, decimals=2)
    res = handler.execute(args, entity_areas)

    assert res.status == "SUCCESS"
    assert res.items[0].scaled_area == 60.00
    assert res.items[1].scaled_area == 30.00
    assert res.grand_total_area == 90.00
    assert res.per_label_totals["ZONE_A"] == 60.00
    assert res.per_label_totals["ZONE_B"] == 30.00


def test_area_takeoff_invalid_scale_raises() -> None:
    handler = AreaTakeoffHandler()
    with pytest.raises(CleanroomError, match="INVALID_SCALE"):
        handler.execute(AreaTakeoffArgs(handles=["H1"], scale=-1.0), {})


# ============================================================================
# 6. LayerStandardCheckHandler Tests
# ============================================================================


def test_layer_standard_check_oracle_3() -> None:
    handler = LayerStandardCheckHandler()
    # 10 layers: 8 compliant (start with S- or 0), 2 non-compliant (ELEC, ARCH)
    layers = [
        "0", "Defpoints", "S-GRID", "S-COLS", "S-BEAMS", "S-SLAB", "S-REBAR", "S-WALL",
        "ELEC-POWER", "ARCH-WALL"
    ]
    res = handler.execute(LayerStandardCheckArgs(), layers)

    assert res.status == "SUCCESS"
    assert res.total_layers == 10
    assert res.standard_layers_count == 8
    assert res.non_standard_layers_count == 2
    # Oracle 3: (8/10) * 100 = 80.00%
    assert res.compliance_rate_percent == 80.00
