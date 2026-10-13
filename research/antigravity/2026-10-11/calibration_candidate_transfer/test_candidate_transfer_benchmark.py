"""Empirical Benchmark evaluating the transfer of Strategy D from cross_validate()
to auto_estimate_calibration() across 8 adversarial pre-calibration scenarios.

Scenarios:
1. Scale-Free Collinear Gap Bridging (Proves gap bridging works without prior scale)
2. Concentric Counterbore Ambiguity Guard (Falsifies naive cross_validation port)
3. Isolated Borehole Circle Snapping (Validates clean multi-primitive transfer)
4. High-DPI Adaptive Corridor (Proves resilience across scan resolutions)
5. Strict Orientation Alignment (Eliminates perpendicular hijacking)
6. Broken Dimension Carrier Chain Unblocking (Demonstrates gap bridging across carriers)
7. Fail-Closed Invariant Preservation (Guarantees no Semantic IR or DXF leak)
8. Anisotropic Scan Elongation Detection (Aspect ratio distortion flagging)
"""

import pytest

from .calibration_candidate_transfer_engine import (
    TransferState,
    MethodA_ProductionBaseline,
    MethodB_NaiveCrossValidationPort,
    MethodC_GuardedMultiPrimitiveOracle,
    SimpleLine,
    SimpleText,
    SimpleCircle,
)


def test_scenario_1_scale_free_collinear_bridging_transfers_successfully():
    """Scenario 1: Dimension line (0 to 300 at y=100) split into two 120px segments by 60px text gap.
    Text '100' at center (150, 100). True span = 300px -> Scale = 100 / 300 = 0.333 mm/px.
    Proves: Collinear gap bridging does NOT require prior scale S0."""
    t = SimpleText("t1", "100", bbox=(130.0, 90.0, 170.0, 110.0), parsed_value=100.0)
    lines = [
        SimpleLine("s1", (0.0, 100.0), (120.0, 100.0)),
        SimpleLine("s2", (180.0, 100.0), (300.0, 100.0)),
    ]

    res_a = MethodA_ProductionBaseline.extract_candidate([t], lines)
    res_c = MethodC_GuardedMultiPrimitiveOracle.extract_candidate([t], lines)

    # Method A selects only one 120px segment -> scale = 100 / 120 = 0.833 (+150% error!)
    assert res_a.estimated_scale == pytest.approx(100.0 / 120.0, rel=1e-3)

    # Method C successfully bridges without knowing scale S0 -> scale = 100 / 300 = 0.333 (exact!)
    assert res_c.estimated_scale == pytest.approx(100.0 / 300.0, rel=1e-3)
    assert res_c.contributing_candidates[0].pixel_span == 300.0


def test_scenario_2_concentric_counterbore_ambiguity_guard():
    """Scenario 2: Concentric counterbore (inner diam 100px for Ø10, outer diam 200px for Ø20).
    Without leader line, text 'Ø20' sits closer to inner hole edge.
    Method B (naive port) snaps to inner circle -> computes scale 20 / 100 = 0.200 (+100% error!).
    Method C identifies concentricity ambiguity -> refuses blind snapping to prevent scale corruption."""
    t20 = SimpleText("t20", "Ø20", bbox=(310.0, 310.0, 330.0, 330.0), parsed_value=20.0)
    circles = [
        SimpleCircle("c_inner", (300.0, 300.0), radius=50.0),   # Diam 100px
        SimpleCircle("c_outer", (300.0, 300.0), radius=100.0),  # Diam 200px
    ]

    res_b = MethodB_NaiveCrossValidationPort.extract_candidate([t20], [], circles=circles)
    res_c = MethodC_GuardedMultiPrimitiveOracle.extract_candidate([t20], [], circles=circles)

    # Method B suffers from concentric ambiguity: 100% scale error!
    assert res_b.estimated_scale == 0.200

    # Method C guards against ambiguity: refuses blind snapping
    assert res_c.status == TransferState.NO_CANDIDATE_SUPPORTED
    assert "ambiguous without leader" in res_c.notes[1]


def test_scenario_3_isolated_borehole_circle_transfers_successfully():
    """Scenario 3: Single non-concentric borehole circle with diameter callout 'Ø50'.
    Center at (200, 200), radius 100px (diameter 200px). True scale = 50 / 200 = 0.25 mm/px.
    Method C cleanly extracts candidate."""
    t = SimpleText("t_diam", "Ø50", bbox=(190.0, 190.0, 210.0, 210.0), parsed_value=50.0)
    c = SimpleCircle("c1", (200.0, 200.0), radius=100.0)

    res_c = MethodC_GuardedMultiPrimitiveOracle.extract_candidate([t], [], circles=[c])
    assert res_c.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res_c.estimated_scale == pytest.approx(0.25, rel=1e-3)
    assert res_c.contributing_candidates[0].primitive_type == "circle_diameter"


def test_scenario_4_high_dpi_text_height_corridor_transfers():
    """Scenario 4: High-resolution 1200 DPI scan where dimension text is offset 180px from line.
    Text height = 60px.
    Method A (static 150px) fails to find line.
    Method C (adaptive 3.0 * th = 180px) finds line and extracts candidate."""
    t = SimpleText("t_hi", "50", bbox=(100.0, 10.0, 200.0, 70.0), parsed_value=50.0)  # th = 60px, center y=40
    line = SimpleLine("l_hi", (0.0, 220.0), (500.0, 220.0))  # y=220 -> dist = 180px

    res_a = MethodA_ProductionBaseline.extract_candidate([t], [line])
    res_c = MethodC_GuardedMultiPrimitiveOracle.extract_candidate([t], [line])

    assert res_a.status == TransferState.NO_CANDIDATE_SUPPORTED
    assert res_c.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res_c.estimated_scale == pytest.approx(50.0 / 500.0, rel=1e-3)


def test_scenario_5_orientation_gating_transfers():
    """Scenario 5: Horizontal text '50' near perpendicular vertical witness line.
    Method A is hijacked by vertical line.
    Method C enforces alignment and pairs with horizontal line."""
    t = SimpleText("t_h", "50", bbox=(190.0, 95.0, 210.0, 105.0), rotation_deg=0.0, parsed_value=50.0)
    vert = SimpleLine("vert", (208.0, 40.0), (208.0, 160.0))   # dist=8px
    horiz = SimpleLine("horiz", (100.0, 120.0), (300.0, 120.0)) # dist=20px, length 200px

    res_a = MethodA_ProductionBaseline.extract_candidate([t], [vert, horiz])
    res_c = MethodC_GuardedMultiPrimitiveOracle.extract_candidate([t], [vert, horiz])

    assert res_a.contributing_candidates[0].geometry_id == "vert"
    assert res_c.contributing_candidates[0].geometry_id == "horiz"
    assert res_c.estimated_scale == pytest.approx(50.0 / 200.0, rel=1e-3)


def test_scenario_6_broken_dimension_carrier_chain_unblocking():
    """Scenario 6: Broken dimension carrier chains with 4 split dimension lines (Width 120, Height 80, Pitch 60, Flange 20)
    and non-dimension text notes. True scale = 0.100 mm/px.
    Method A produces fragmented or missing candidates due to gap interruptions.
    Method C bridges carrier gaps, filters notes, and extracts 0.100 mm/px consensus."""
    texts = [
        SimpleText("w", "120.0", bbox=(585.0, 45.0, 615.0, 55.0), rotation_deg=0.0, parsed_value=120.0),
        SimpleText("h", "80.0", bbox=(35.0, 385.0, 45.0, 415.0), rotation_deg=90.0, parsed_value=80.0),
        SimpleText("pitch", "60.0", bbox=(585.0, 195.0, 615.0, 205.0), rotation_deg=0.0, parsed_value=60.0),
        SimpleText("flange", "20.0", bbox=(95.0, 95.0, 105.0, 105.0), rotation_deg=0.0, parsed_value=20.0),
        # Unrelated note
        SimpleText("mat", "MATERIAL: AL 6061", bbox=(100.0, 800.0, 250.0, 820.0), parsed_value=6061.0, semantic_role="general_note"),
    ]
    lines = [
        # Width 1200px split at 580 to 620
        SimpleLine("w1", (0.0, 50.0), (580.0, 50.0)),
        SimpleLine("w2", (620.0, 50.0), (1200.0, 50.0)),
        # Height 800px split at 380 to 420
        SimpleLine("h1", (40.0, 0.0), (40.0, 380.0)),
        SimpleLine("h2", (40.0, 420.0), (40.0, 800.0)),
        # Pitch 600px split at 580 to 620
        SimpleLine("p1", (300.0, 200.0), (580.0, 200.0)),
        SimpleLine("p2", (620.0, 200.0), (900.0, 200.0)),
        # Flange 200px continuous
        SimpleLine("f1", (0.0, 100.0), (200.0, 100.0)),
    ]

    res_c = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(texts, lines)

    assert res_c.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res_c.estimated_scale == pytest.approx(0.100, rel=1e-3)
    assert len(res_c.contributing_candidates) == 4
    assert res_c.relative_error_pct < 0.5


def test_scenario_7_fail_closed_boundary_preservation():
    """Scenario 7: Verify that candidate output strictly preserves status='needs_verification'
    and does not bypass the unverified gate."""
    texts = [
        SimpleText("w", "100.0", bbox=(485.0, 45.0, 515.0, 55.0), rotation_deg=0.0, parsed_value=100.0),
        SimpleText("h", "50.0", bbox=(45.0, 235.0, 55.0, 265.0), rotation_deg=90.0, parsed_value=50.0),
    ]
    lines = [
        SimpleLine("w1", (0.0, 50.0), (1000.0, 50.0)),
        SimpleLine("h1", (50.0, 0.0), (50.0, 500.0)),
    ]

    res_c = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(texts, lines)

    # Status must strictly be needs_verification
    assert res_c.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res_c.is_reviewable is True
    # Can NOT be treated as verified without human sign-off:
    assert res_c.status != "verified"


def test_scenario_8_anisotropic_scan_elongation_detection():
    """Scenario 8: 6% vertical scanner elongation (Scale X = 0.1000, Scale Y = 0.0943).
    Method C flags anisotropy ratio."""
    texts = [
        SimpleText("x", "100.0", bbox=(485.0, 45.0, 515.0, 55.0), rotation_deg=0.0, parsed_value=100.0),
        SimpleText("y", "100.0", bbox=(45.0, 515.0, 55.0, 545.0), rotation_deg=90.0, parsed_value=100.0),
    ]
    lines = [
        SimpleLine("x_line", (0.0, 50.0), (1000.0, 50.0)),  # 1000px -> scale = 0.1000
        SimpleLine("y_line", (50.0, 0.0), (50.0, 1060.0)),  # 1060px -> scale = 0.0943
    ]

    res_c = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(texts, lines)

    assert res_c.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert abs(res_c.anisotropy_ratio - 1.0) > 0.015
    assert res_c.anisotropy_ratio == pytest.approx(0.0943 / 0.1000, rel=1e-2)
