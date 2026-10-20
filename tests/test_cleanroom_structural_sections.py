"""tests/test_cleanroom_structural_sections.py.

Batch ST1 Test Suite: Structural Sections, Foundations, Slabs & Connections.
Validates cleanroom parity against physical C# source:
  - SteelSectionHandler (cadmind-steel-section)
  - ConcreteSectionHandler (cadmind-concrete-section)
  - FoundationFootingHandler (cadmind-foundation)
  - WallSlabSectionHandler (cadmind-wall-slab-section)
  - MaterialHatchHandler (cadmind-material-hatch)
  - SteelConnectionHandler (cadmind-steel-connection)
"""

import pytest

from cad_agent.cleanroom_mechanical import Point2D
from cad_agent.cleanroom_structural_sections import (
    CleanroomError,
    ConcreteSectionArgs,
    ConcreteSectionHandler,
    FoundationFootingArgs,
    FoundationFootingHandler,
    MaterialHatchArgs,
    MaterialHatchHandler,
    SteelConnectionArgs,
    SteelConnectionHandler,
    SteelSectionArgs,
    SteelSectionHandler,
    WallSlabSectionArgs,
    WallSlabSectionHandler,
)


# ============================================================================
# 1. SteelSectionHandler Tests
# ============================================================================


def test_steel_section_nominal_i_beam_and_rhs() -> None:
    handler = SteelSectionHandler()
    # I-Beam
    args_i = SteelSectionArgs(profile_type="I_BEAM", depth=300.0, width=150.0, web_thickness=7.1, flange_thickness=10.7)
    res_i = handler.execute(args_i)
    assert res_i.status == "OK"
    assert len(res_i.lines) == 12

    # RHS Box
    args_rhs = SteelSectionArgs(profile_type="RHS", depth=200.0, width=100.0, web_thickness=6.0, flange_thickness=6.0)
    res_rhs = handler.execute(args_rhs)
    assert res_rhs.status == "OK"
    assert len(res_rhs.lines) == 8  # 4 outer + 4 inner


def test_steel_section_flange_thickness_exceeded_rejected() -> None:
    handler = SteelSectionHandler()
    # 2 * tf (2 * 60 = 120) >= depth (100)
    args = SteelSectionArgs(depth=100.0, width=100.0, web_thickness=5.0, flange_thickness=60.0)
    res = handler.execute(args)
    assert res.status == "ERROR"
    assert "Combined flange thickness must be strictly less than overall depth" in res.message


# ============================================================================
# 2. ConcreteSectionHandler Tests
# ============================================================================


def test_concrete_section_nominal_oracle_1() -> None:
    handler = ConcreteSectionHandler()
    args = ConcreteSectionArgs(
        width=300.0,
        depth=500.0,
        cover=35.0,
        top_rebar_count=2,
        bottom_rebar_count=3,
    )
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.section_area_mm2 == 150000.0  # 300 * 500
    assert res.total_rebar_count == 5         # 2 + 3
    assert len(res.rebar_circles) == 5


def test_concrete_section_cover_boundary_rejected() -> None:
    handler = ConcreteSectionHandler()
    # Cover (150) >= min(300, 300)/2 (150)
    args = ConcreteSectionArgs(width=300.0, depth=300.0, cover=150.0)
    res = handler.execute(args)
    assert res.status == "ERROR"
    assert "Concrete cover exceeds section boundary" in res.message


# ============================================================================
# 3. FoundationFootingHandler Tests
# ============================================================================


def test_foundation_footing_nominal_oracle_2() -> None:
    handler = FoundationFootingHandler()
    args = FoundationFootingArgs(
        pad_length=1200.0,
        pad_width=1200.0,
        col_length=400.0,
        col_width=400.0,
        offset_x=0.0,
        offset_y=0.0,
        footing_id="F1",
    )
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.entity_count == 5
    assert len(res.lines) >= 8  # Pad + Col + Centerlines


def test_foundation_footing_containment_violation_rejected() -> None:
    handler = FoundationFootingHandler()
    # abs(offset_x) + col_length/2 = 500 + 200 = 700 >= pad_length/2 (600)
    args = FoundationFootingArgs(
        pad_length=1200.0,
        pad_width=1200.0,
        col_length=400.0,
        col_width=400.0,
        offset_x=500.0,
    )
    res = handler.execute(args)
    assert res.status == "ERROR"
    assert "Column pedestal exceeds or touches pad boundary" in res.message


# ============================================================================
# 4. WallSlabSectionHandler Tests
# ============================================================================


def test_wall_slab_section_valid_and_typo() -> None:
    handler = WallSlabSectionHandler()
    res_slab = handler.execute(WallSlabSectionArgs(element="slab", length=3000.0, thickness=200.0))
    assert res_slab.status == "OK"
    assert res_slab.area == 600000.0  # 3000 * 200

    res_typo = handler.execute(WallSlabSectionArgs(element="column"))
    assert res_typo.status == "ERROR"
    assert "Element must be 'wall' or 'slab'" in res_typo.message


# ============================================================================
# 5. MaterialHatchHandler Tests
# ============================================================================


def test_material_hatch_valid_and_missing_boundary() -> None:
    handler = MaterialHatchHandler()
    pts = [Point2D(0, 0), Point2D(100, 0), Point2D(100, 100)]
    res = handler.execute(MaterialHatchArgs(boundary_points=pts, pattern_scale=1.5))
    assert res.status == "OK"

    res_err = handler.execute(MaterialHatchArgs(boundary_points=[]))
    assert res_err.status == "ERROR"
    assert "requires at least 3 BoundaryPoints" in res_err.message


# ============================================================================
# 6. SteelConnectionHandler Tests
# ============================================================================


def test_steel_connection_nominal_and_invalid_rows() -> None:
    handler = SteelConnectionHandler()
    args = SteelConnectionArgs(bolt_rows=2, bolt_cols=3, bolt_dia=20.0)
    res = handler.execute(args)

    assert res.status == "SUCCESS"
    assert res.bolt_count == 6  # 2 * 3
    assert len(res.bolt_circles) == 6

    with pytest.raises(CleanroomError, match="INVALID_BOLT_ROWS"):
        handler.execute(SteelConnectionArgs(bolt_rows=0))
