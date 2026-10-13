"""Formal Positive Fixtures and Strong Negative Controls for Dimension-Geometry Association.

Tests:
1. test_positive_control_complete_mechanical_part_callouts
2. test_negative_control_orthogonal_line_rejection
3. test_negative_control_unparseable_dimension_text
4. test_negative_control_non_dimension_role_rejection
5. test_negative_control_excessive_perpendicular_offset
6. test_negative_control_non_collinear_segment_pair_rejection
7. test_negative_control_circle_without_diameter_prefix
8. test_positive_control_confidence_scoring_provenance
"""

import pytest

from .dimension_association_engine import (
    SimpleLine,
    SimpleText,
    SimpleCircle,
    SimpleArc,
    DimensionType,
    StrategyD_MultiPrimitiveAssociationOracle,
)


def test_positive_control_complete_mechanical_part_callouts():
    """Positive Control: Complete mechanical part with 4 callouts:
    - Overall width 100mm (400px horizontal span) -> scale 0.25 mm/px
    - Overall height 50mm (200px vertical span) -> scale 0.25 mm/px
    - Borehole Ø20mm (80px circle diameter) -> scale 0.25 mm/px
    - Corner fillet R10mm (40px arc radius) -> scale 0.25 mm/px
    All 4 features must associate cleanly and agree with 0.00% scale variance!"""
    texts = [
        # Horizontal width (split line across text)
        SimpleText("t_w", "100", bbox=(185.0, 45.0, 215.0, 55.0), rotation_deg=0.0, parsed_value=100.0),
        # Vertical height (split line across text)
        SimpleText("t_h", "50", bbox=(35.0, 135.0, 45.0, 165.0), rotation_deg=90.0, parsed_value=50.0),
        # Borehole diameter
        SimpleText("t_bore", "Ø20", bbox=(190.0, 140.0, 210.0, 160.0), parsed_value=20.0),
        # Fillet radius
        SimpleText("t_fillet", "R10", bbox=(340.0, 60.0, 360.0, 80.0), parsed_value=10.0),
    ]

    lines = [
        # Width dimension segments
        SimpleLine("w_s1", (0.0, 50.0), (180.0, 50.0)),
        SimpleLine("w_s2", (220.0, 50.0), (400.0, 50.0)),
        # Height dimension segments
        SimpleLine("h_s1", (40.0, 50.0), (40.0, 130.0)),
        SimpleLine("h_s2", (40.0, 170.0), (40.0, 250.0)),
    ]

    circles = [SimpleCircle("bore_hole", (200.0, 150.0), radius=40.0)]
    arcs = [SimpleArc("fillet_arc", (350.0, 70.0), radius=40.0, start_angle_deg=0.0, end_angle_deg=90.0)]

    results = StrategyD_MultiPrimitiveAssociationOracle.associate(texts, lines, circles, arcs)

    assert len(results) == 4
    by_text = {r.text_id: r for r in results}

    assert by_text["t_w"].scale_candidate == pytest.approx(0.25, rel=1e-3)
    assert by_text["t_h"].scale_candidate == pytest.approx(0.25, rel=1e-3)
    assert by_text["t_bore"].scale_candidate == pytest.approx(0.25, rel=1e-3)
    assert by_text["t_fillet"].scale_candidate == pytest.approx(0.25, rel=1e-3)


def test_negative_control_orthogonal_line_rejection():
    """Negative Control: Strictly reject pairing horizontal text with orthogonal vertical line."""
    text = SimpleText("t_h", "100", bbox=(90.0, 95.0, 110.0, 105.0), rotation_deg=0.0, parsed_value=100.0)
    vert_line = SimpleLine("vert", (100.0, 20.0), (100.0, 180.0))

    results = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [vert_line])
    assert len(results) == 0


def test_negative_control_unparseable_dimension_text():
    """Negative Control: Text with parsed_value=None must be rejected."""
    text = SimpleText("t_bad", "???", bbox=(90.0, 95.0, 110.0, 105.0), rotation_deg=0.0, parsed_value=None)
    line = SimpleLine("l1", (0.0, 100.0), (200.0, 100.0))

    results = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [line])
    assert len(results) == 0


def test_negative_control_non_dimension_role_rejection():
    """Negative Control: Text with semantic_role != 'dimension_value' must be rejected."""
    text = SimpleText("t_part", "12345", bbox=(90.0, 95.0, 110.0, 105.0), parsed_value=12345.0, semantic_role="part_number")
    line = SimpleLine("l1", (0.0, 100.0), (200.0, 100.0))

    results = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [line])
    assert len(results) == 0


def test_negative_control_excessive_perpendicular_offset():
    """Negative Control: Parallel line located 80px away (exceeding 30px carrier limit) must be rejected."""
    text = SimpleText("t_far", "100", bbox=(90.0, 95.0, 110.0, 105.0), rotation_deg=0.0, parsed_value=100.0)
    far_line = SimpleLine("l_far", (0.0, 180.0), (200.0, 180.0))  # y=180 vs y=100 -> delta y = 80px

    results = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [far_line])
    assert len(results) == 0


def test_negative_control_non_collinear_segment_pair_rejection():
    """Negative Control: Two segments with 25-degree angular discrepancy must NOT be bridged into a span."""
    text = SimpleText("t_kink", "100", bbox=(90.0, 95.0, 110.0, 105.0), rotation_deg=0.0, parsed_value=100.0)
    # Seg 1 horizontal at y=100
    s1 = SimpleLine("s1", (0.0, 100.0), (80.0, 100.0))
    # Seg 2 inclined at 25 degrees
    s2 = SimpleLine("s2", (120.0, 100.0), (200.0, 137.0))

    results = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [s1, s2])
    # Must NOT bridge into a pair
    assert len(results) == 1
    assert results[0].geometry_type == "line"  # evaluated as single segment only
    assert results[0].measured_pixel_span == 80.0


def test_negative_control_circle_without_diameter_prefix():
    """Negative Control: Plain numeric text '50' without diameter prefix ('Ø', '%%c', 'DIA')
    must not falsely snap to adjacent circle."""
    text = SimpleText("t_num", "50", bbox=(190.0, 140.0, 210.0, 160.0), parsed_value=50.0)
    circle = SimpleCircle("c1", (200.0, 150.0), radius=50.0)

    results = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [], circles=[circle])
    assert len(results) == 0


def test_positive_control_confidence_scoring_provenance():
    """Positive Control: Verify that bridged lines record complete provenance and confidence >= 0.95."""
    text = SimpleText("t1", "100", bbox=(90.0, 95.0, 110.0, 105.0), parsed_value=100.0)
    s1 = SimpleLine("s1", (0.0, 100.0), (80.0, 100.0))
    s2 = SimpleLine("s2", (120.0, 100.0), (200.0, 100.0))

    results = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [s1, s2])
    assert len(results) == 1
    assoc = results[0]
    assert assoc.confidence >= 0.95
    assert assoc.association_method == "collinear_gap_bridging"
    assert "s1" in assoc.contributing_segment_ids
    assert "s2" in assoc.contributing_segment_ids
    assert "Bridged 2 segments" in assoc.notes[0]
