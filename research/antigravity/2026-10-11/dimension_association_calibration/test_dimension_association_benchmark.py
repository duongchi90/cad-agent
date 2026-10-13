"""Empirical Strategy Benchmark comparing Strategies A-D across 8 adversarial dimension association scenarios.

Scenarios:
1. Split Dimension Line with Centered Text Gap (Standard CAD layout)
2. Horizontal Text Near Vertical Witness Line (Orientation hijacking)
3. Diameter Borehole Callout ('Ø50' on Circle)
4. Radial Fillet Callout ('R15' on Arc)
5. Narrow Dimension with Outside Text
6. Closely Spaced Parallel Dimension Chains (Crosstalk immunity)
7. Aligned 45-degree Diagonal Dimension
8. Unrelated Text Note Near Part Body Line (Semantic role protection)
"""

import pytest

from .dimension_association_engine import (
    SimpleLine,
    SimpleText,
    SimpleCircle,
    SimpleArc,
    DimensionType,
    StrategyA_ProductionBaseline,
    StrategyB_OrientedRayProjection,
    StrategyC_WitnessLinePairMatching,
    StrategyD_MultiPrimitiveAssociationOracle,
)


def test_scenario_1_split_dimension_line_centered_text_gap():
    """Scenario 1: 200px dimension line split into two 85px segments by 30px text gap.
    Text '100' is at (185, 95, 215, 105), center (200, 100).
    Seg 1: (100, 100) -> (185, 100) [length 85px]
    Seg 2: (215, 100) -> (300, 100) [length 85px]
    True span = 200px -> True scale = 100 / 200 = 0.50 mm/px."""
    text = SimpleText(id="t1", content="100", bbox=(185.0, 95.0, 215.0, 105.0), parsed_value=100.0)
    lines = [
        SimpleLine("s1", (100.0, 100.0), (185.0, 100.0)),
        SimpleLine("s2", (215.0, 100.0), (300.0, 100.0)),
    ]

    res_a = StrategyA_ProductionBaseline.associate([text], lines)
    res_d = StrategyD_MultiPrimitiveAssociationOracle.associate([text], lines)

    # Strategy A pairs with single segment: length 85px -> scale 1.176 mm/px (+135% error!)
    assert len(res_a) == 1
    assert res_a[0].measured_pixel_span == 85.0
    assert abs(res_a[0].scale_candidate - 0.50) / 0.50 > 1.0

    # Strategy D bridges the gap: length 200px -> scale 0.50 mm/px (exact!)
    assert len(res_d) == 1
    assert res_d[0].measured_pixel_span == pytest.approx(200.0, rel=1e-3)
    assert res_d[0].scale_candidate == pytest.approx(0.50, rel=1e-3)
    assert res_d[0].geometry_type == "line_pair_bridged"
    assert set(res_d[0].contributing_segment_ids) == {"s1", "s2"}


def test_scenario_2_horizontal_text_near_vertical_witness_line():
    """Scenario 2: Horizontal text '50' sits near a vertical witness line.
    Vertical witness line midpoint is 8px from text center;
    Horizontal dimension line midpoint is 25px from text center.
    Strategy A picks the vertical line.
    Strategy D rejects the vertical line and binds to the horizontal line."""
    text = SimpleText(id="t_h", content="50", bbox=(190.0, 95.0, 210.0, 105.0), rotation_deg=0.0, parsed_value=50.0)
    vert_witness = SimpleLine("vert", (208.0, 40.0), (208.0, 160.0))  # Midpoint (208, 100), dist=8px
    horiz_dim = SimpleLine("horiz", (150.0, 125.0), (250.0, 125.0))   # Midpoint (200, 125), dist=25px

    res_a = StrategyA_ProductionBaseline.associate([text], [vert_witness, horiz_dim])
    res_d = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [vert_witness, horiz_dim])

    # Strategy A hijacked by vertical line:
    assert res_a[0].geometry_id == "vert"

    # Strategy D strictly enforces orientation alignment:
    assert res_d[0].geometry_id == "horiz"
    assert res_d[0].dimension_type == DimensionType.LINEAR_HORIZONTAL


def test_scenario_3_diameter_borehole_callout():
    """Scenario 3: Text 'Ø50' near a circular borehole of radius 100px (diameter 200px).
    True scale = 50 / 200 = 0.25 mm/px.
    Strategies A, B, C fail to associate (0 results).
    Strategy D snaps to circle diameter and produces exact 0.25 scale."""
    text = SimpleText(id="t_dia", content="Ø50", bbox=(280.0, 190.0, 320.0, 210.0), parsed_value=50.0)
    circle = SimpleCircle(id="c1", center=(300.0, 200.0), radius=100.0)

    res_a = StrategyA_ProductionBaseline.associate([text], [], circles=[circle])
    res_b = StrategyB_OrientedRayProjection.associate([text], [], circles=[circle])
    res_c = StrategyC_WitnessLinePairMatching.associate([text], [], circles=[circle])
    res_d = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [], circles=[circle])

    assert len(res_a) == 0
    assert len(res_b) == 0
    assert len(res_c) == 0

    assert len(res_d) == 1
    assert res_d[0].dimension_type == DimensionType.DIAMETER
    assert res_d[0].measured_pixel_span == 200.0
    assert res_d[0].scale_candidate == pytest.approx(0.25, rel=1e-3)
    assert res_d[0].geometry_id == "c1"


def test_scenario_4_radial_fillet_callout():
    """Scenario 4: Text 'R15' near a rounded fillet corner arc of radius 60px.
    True scale = 15 / 60 = 0.25 mm/px.
    Strategies A-C return nothing.
    Strategy D snaps to arc radius and produces exact 0.25 scale."""
    text = SimpleText(id="t_rad", content="R15", bbox=(90.0, 90.0, 120.0, 110.0), parsed_value=15.0)
    arc = SimpleArc(id="arc1", center=(100.0, 100.0), radius=60.0, start_angle_deg=0.0, end_angle_deg=90.0)

    res_a = StrategyA_ProductionBaseline.associate([text], [], arcs=[arc])
    res_d = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [], arcs=[arc])

    assert len(res_a) == 0
    assert len(res_d) == 1
    assert res_d[0].dimension_type == DimensionType.RADIUS
    assert res_d[0].measured_pixel_span == 60.0
    assert res_d[0].scale_candidate == pytest.approx(0.25, rel=1e-3)


def test_scenario_5_narrow_dimension_outside_text():
    """Scenario 5: 30px narrow span with text '5' placed slightly outside the carrier.
    Lines: (100, 100) -> (130, 100). Text at (145, 95, 165, 105)."""
    text = SimpleText(id="t_narrow", content="5", bbox=(145.0, 95.0, 165.0, 105.0), parsed_value=5.0)
    line = SimpleLine("l_narrow", (100.0, 100.0), (130.0, 100.0))

    res_d = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [line])

    assert len(res_d) == 1
    assert res_d[0].measured_pixel_span == 30.0
    assert res_d[0].scale_candidate == pytest.approx(5.0 / 30.0, rel=1e-3)


def test_scenario_6_parallel_stacked_dimension_chains():
    """Scenario 6: Two parallel stacked dimension lines at y=100 and y=160.
    Text 1 '100' is at y=100 (span 400px).
    Text 2 '50' is at y=160 (span 200px).
    Strategy D must not crosstalk between stacked chains."""
    t1 = SimpleText(id="t1", content="100", bbox=(190.0, 95.0, 210.0, 105.0), parsed_value=100.0)
    t2 = SimpleText(id="t2", content="50", bbox=(190.0, 155.0, 210.0, 165.0), parsed_value=50.0)

    l1 = SimpleLine("chain1", (0.0, 100.0), (400.0, 100.0))
    l2 = SimpleLine("chain2", (100.0, 160.0), (300.0, 160.0))

    res_d = StrategyD_MultiPrimitiveAssociationOracle.associate([t1, t2], [l1, l2])

    assert len(res_d) == 2
    by_text = {r.text_id: r for r in res_d}
    assert by_text["t1"].geometry_id == "chain1"
    assert by_text["t1"].measured_pixel_span == 400.0
    assert by_text["t2"].geometry_id == "chain2"
    assert by_text["t2"].measured_pixel_span == 200.0


def test_scenario_7_aligned_diagonal_dimension_45_deg():
    """Scenario 7: 45-degree aligned dimension with text rotated 45 degrees.
    Segment 1: (0, 0) -> (70.71, 70.71)
    Segment 2: (106.07, 106.07) -> (176.78, 176.78)
    Text '50' at center (88.39, 88.39), rotation 45 deg. True span = 250px."""
    # (0, 0) to (176.78, 176.78) has distance = sqrt(2 * 176.78^2) = 250.0px
    s1 = SimpleLine("d_seg1", (0.0, 0.0), (70.71, 70.71))
    s2 = SimpleLine("d_seg2", (106.07, 106.07), (176.78, 176.78))
    text = SimpleText(id="t_diag", content="50", bbox=(80.0, 80.0, 96.78, 96.78), rotation_deg=45.0, parsed_value=50.0)

    res_d = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [s1, s2])

    assert len(res_d) == 1
    assert res_d[0].dimension_type == DimensionType.LINEAR_ALIGNED
    assert res_d[0].measured_pixel_span == pytest.approx(250.0, rel=1e-2)
    assert res_d[0].scale_candidate == pytest.approx(50.0 / 250.0, rel=1e-2)


def test_scenario_8_unrelated_text_note_near_part_body_contour():
    """Scenario 8: Non-dimension text 'MATERIAL: STEEL' near a 500px body line.
    semantic_role='general_note' and parsed_value=None.
    Must produce ZERO associations."""
    note = SimpleText(id="note1", content="MATERIAL: STEEL", bbox=(100.0, 100.0, 200.0, 120.0), parsed_value=None, semantic_role="general_note")
    body_line = SimpleLine("body", (50.0, 105.0), (550.0, 105.0))

    res_d = StrategyD_MultiPrimitiveAssociationOracle.associate([note], [body_line])
    assert len(res_d) == 0
