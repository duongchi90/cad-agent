"""tests/test_cleanroom_mechanical_tables.py.

Batch M7 Test Suite: Mechanical Part Hatch, Hole Table & BOM Table.
Validates cleanroom parity against physical C# source:
  - PartHatchHandler (cadmind-part-hatch)
  - HoleTableHandler (cadmind-hole-table)
  - BomTableHandler (cadmind-bom-table)

Completes Domain 2 (MECHANICAL: 22/22 registered tools).
"""

import pytest

from cad_agent.cleanroom_mechanical_tables import (
    BomItem,
    BomTableArgs,
    BomTableHandler,
    DegenerateGeometryError,
    HoleRow,
    HoleTableArgs,
    HoleTableHandler,
    PartHatchArgs,
    PartHatchHandler,
)


# ============================================================================
# 1. PartHatchHandler Tests
# ============================================================================


def test_part_hatch_valid() -> None:
    handler = PartHatchHandler()
    boundaries = {"1A": True, "1B": True}
    args = PartHatchArgs(handles=["1A", "1B"], pattern="ANSI31", scale=1.0)
    res = handler.execute(args, boundary_database=boundaries)

    assert res.status == "OK"
    assert res.hatched_count == 2
    assert res.processed_count == 2


def test_part_hatch_open_boundary_rejected() -> None:
    handler = PartHatchHandler()
    boundaries = {"1A": False}  # Open curve!
    args = PartHatchArgs(handles=["1A"])
    res = handler.execute(args, boundary_database=boundaries)

    assert res.status == "ERROR"
    assert "OPEN_BOUNDARY_LOOP" in res.message


def test_part_hatch_micro_scale_rejected() -> None:
    handler = PartHatchHandler()
    res = handler.execute(PartHatchArgs(handles=["1A"], scale=1e-5))
    assert res.status == "ERROR"
    assert "DEGENERATE_GEOMETRY" in res.message


def test_part_hatch_locked_layer_abort() -> None:
    handler = PartHatchHandler()
    locks = {"m-hatch": True}
    res = handler.execute(PartHatchArgs(handles=["1A"], layer="M-HATCH"), layer_locks=locks)
    assert res.status == "ERROR"
    assert "LOCKED_LAYER" in res.message


# ============================================================================
# 2. HoleTableHandler Tests
# ============================================================================


def test_hole_table_valid_oracle_2() -> None:
    handler = HoleTableHandler()
    rows = [
        HoleRow(tag="H1", x=12.5, y=18.2, dia=6.0),
        HoleRow(tag="H2", x=30.0, y=45.0, dia=10.0),
    ]
    args = HoleTableArgs(rows=rows, origin=[10.0, 20.0], row_height=8.0, text_height=3.0)
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.row_count == 2
    # Oracle: 1 + 4 + 1 + (2 * (1 + 4 + 1)) + 5 = 6 + 12 + 5 = 23
    assert res.processed_count == 23
    assert len(res.grid_lines) > 0


def test_hole_table_inverted_height_rejected() -> None:
    handler = HoleTableHandler()
    rows = [HoleRow(tag="H1", x=0.0, y=0.0, dia=5.0)]
    # RowHeight (3.0) <= TextHeight (3.5)
    args = HoleTableArgs(rows=rows, row_height=3.0, text_height=3.5)
    res = handler.execute(args)

    assert res.status == "ERROR"
    assert "RowHeight must be strictly greater than TextHeight" in res.message


def test_hole_table_empty_rows_rejected() -> None:
    handler = HoleTableHandler()
    res = handler.execute(HoleTableArgs(rows=[]))
    assert res.status == "ERROR"
    assert "requires at least one row" in res.message


# ============================================================================
# 3. BomTableHandler Tests
# ============================================================================


def test_bom_table_oracle_3_weight() -> None:
    handler = BomTableHandler()
    items = [
        BomItem(item_no=1, description="SHAFT", part_no="S-01", material="4140", quantity=5, unit_weight_kg=2.5),
        BomItem(item_no=2, description="GEAR", part_no="G-02", material="8620", quantity=10, unit_weight_kg=1.2),
    ]
    args = BomTableArgs(items=items, insertion_point=[50.0, 100.0])
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.item_count == 2
    # Oracle 3: (5 * 2.5) + (10 * 1.2) = 12.5 + 12.0 = 24.50 kg!
    assert res.total_weight_kg == 24.50
    # Processed count: 1 + 7 + (2 * 7) + 2 + 1 + 2 + 6 = 33
    assert res.processed_count == 33
    assert len(res.grid_lines) > 0


def test_bom_table_invalid_item_quantity_raises() -> None:
    with pytest.raises(DegenerateGeometryError, match="Item quantity and item number must be positive"):
        BomItem(item_no=1, description="BAD", part_no="P", material="M", quantity=0)


def test_bom_table_locked_layer_abort() -> None:
    handler = BomTableHandler()
    items = [BomItem(item_no=1, description="A", part_no="B", material="C", quantity=1)]
    locks = {"text": True}
    res = handler.execute(BomTableArgs(items=items, insertion_point=[0, 0], text_layer="TEXT"), layer_locks=locks)
    assert res.status == "ERROR"
    assert "LOCKED_LAYER" in res.message
