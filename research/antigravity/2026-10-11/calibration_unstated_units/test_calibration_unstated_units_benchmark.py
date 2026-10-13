"""Empirical Strategy Benchmark comparing Strategies A-D across 8 adversarial scenarios.

Scenarios:
1. Clean Metric Drawing (Baseline standard)
2. Unstated Units on Imperial Drawing (Catastrophic 25.4x silent corruption risk)
3. Anisotropic Roller Scanner Stretching (Aspect ratio distortion)
4. Single Dimension Witness (AGENTS.md consensus violation)
5. One Corrupted OCR Dimension (Outlier resilience)
6. DO NOT SCALE Explicit Constraint (Non-proportional CAD safety)
7. Multi-View Sheet with Detail View (Cross-view scale isolation)
8. Conflicting Dimension Consensus (Unresolvable source ambiguity)
"""

import pytest

from .calibration_unstated_units_engine import (
    DimensionEvidence,
    CalibrationState,
    UnitType,
    StrategyA_ProductionBaseline,
    StrategyB_StrictClosedWorld,
    StrategyC_TwoPhaseDiscovery,
    StrategyD_MultiDomainConsensusOracle,
)


def test_scenario_1_clean_metric_drawing():
    """Scenario 1: Clean drawing with explicit 'mm' and 3 agreeing dimensions."""
    dims = [
        DimensionEvidence("d1", 100.0, 1000.0, axis="X"),
        DimensionEvidence("d2", 50.0, 501.0, axis="Y"),
        DimensionEvidence("d3", 200.0, 1998.0, axis="X"),
    ]

    res_a = StrategyA_ProductionBaseline.evaluate(dims, explicit_unit="mm")
    res_b = StrategyB_StrictClosedWorld.evaluate(dims, manual_verified_scale=0.10, calibration_approval="ENG-01", explicit_unit="mm")
    res_c = StrategyC_TwoPhaseDiscovery.evaluate(dims, explicit_unit="mm")
    res_d = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm", scale_label_denominator=1, page_dpi=254)

    # Strategy D confirms consensus within 0.2%
    assert res_d.state == CalibrationState.VERIFIED_PHYSICAL
    assert res_d.unit == UnitType.MILLIMETER
    assert res_d.relative_error_pct < 1.0
    assert len(res_d.contributing_witness_ids) == 3


def test_scenario_2_unstated_units_imperial_drawing():
    """Scenario 2: American inch drawing with unstated units.
    Strategy A silently assumes mm (catastrophic failure).
    Strategy D refuses to guess physical unit and locks state to UNVERIFIED_DRAFT_REFERENCE."""
    # 2.000", 4.000", 1.500" measuring 200px, 400px, 150px -> scale = 0.010 in/px
    dims = [
        DimensionEvidence("d1", 2.0, 200.0, axis="X"),
        DimensionEvidence("d2", 4.0, 400.0, axis="Y"),
        DimensionEvidence("d3", 1.5, 150.0, axis="X"),
    ]

    res_a = StrategyA_ProductionBaseline.evaluate(dims)
    res_d = StrategyD_MultiDomainConsensusOracle.evaluate(dims)

    # Strategy A falsely assigns mm
    assert res_a.unit == UnitType.MILLIMETER
    assert res_a.can_generate_dxf is True

    # Strategy D isolates unit from scale:
    assert res_d.unit == UnitType.UNKNOWN_UNSTATED
    assert res_d.unit_confidence == 0.0
    assert res_d.scale_x == pytest.approx(0.010, rel=1e-3)
    # Physical DXF is strictly refused!
    assert res_d.can_generate_dxf is False
    assert res_d.state == CalibrationState.UNVERIFIED_DRAFT_REFERENCE


def test_scenario_3_anisotropic_roller_scan_distortion():
    """Scenario 3: 10% vertical elongation caused by roller scanner slipping.
    Scale X = 0.100, Scale Y = 0.0909 (anisotropy = 0.909, error ~ 9.5%)."""
    dims = [
        DimensionEvidence("dx1", 100.0, 1000.0, axis="X"),
        DimensionEvidence("dx2", 50.0, 500.0, axis="X"),
        DimensionEvidence("dy1", 100.0, 1100.0, axis="Y"),
        DimensionEvidence("dy2", 50.0, 550.0, axis="Y"),
    ]

    res_a = StrategyA_ProductionBaseline.evaluate(dims, explicit_unit="mm")
    res_d = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    # Strategy A is blind to anisotropy
    assert res_a.anisotropy_ratio == 1.0

    # Strategy D detects anisotropy > 1.5% and flags conflict
    assert res_d.state == CalibrationState.CONFLICTING_AMBIGUOUS
    assert abs(res_d.anisotropy_ratio - 1.0) > 0.015
    assert "Anisotropic scan distortion detected" in res_d.notes[0]
    assert res_d.can_generate_dxf is False


def test_scenario_4_single_dimension_witness():
    """Scenario 4: Only 1 dimension found on sheet.
    Strategy A accepts single candidate.
    Strategy D refuses per AGENTS.md invariant (requires >= 2 independent witnesses)."""
    dims = [
        DimensionEvidence("d1", 100.0, 1000.0, axis="X"),
    ]

    res_a = StrategyA_ProductionBaseline.evaluate(dims, explicit_unit="mm")
    res_d = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    # Strategy A produces draft candidate
    assert res_a.state == CalibrationState.UNVERIFIED_DRAFT_REFERENCE

    # Strategy D refuses:
    assert res_d.state == CalibrationState.UNKNOWN_UNSTATED
    assert "Fewer than 2 witnesses" in res_d.notes[0]
    assert res_d.can_generate_dxf is False


def test_scenario_5_one_corrupted_ocr_dimension():
    """Scenario 5: 2 true dimensions at 0.100 mm/px, and 1 corrupted OCR dimension at 0.54 mm/px."""
    dims = [
        DimensionEvidence("d1", 100.0, 1000.0, axis="X"),
        DimensionEvidence("d2", 50.0, 500.0, axis="X"),
        DimensionEvidence("d_bad", 108.0, 200.0, axis="X"),  # OCR error: 0.54 mm/px
    ]

    res_d = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    # Strategy D filters out d_bad and establishes consensus on d1 and d2
    assert "d_bad" in res_d.outlier_witness_ids
    assert set(res_d.contributing_witness_ids) == {"d1", "d2"}
    assert res_d.scale_x == pytest.approx(0.100, rel=1e-3)


def test_scenario_6_do_not_scale_constraint():
    """Scenario 6: Sheet explicitly carries 'DO NOT SCALE DRAWING' note."""
    dims = [
        DimensionEvidence("d1", 100.0, 1000.0, axis="X"),
        DimensionEvidence("d2", 50.0, 500.0, axis="Y"),
    ]

    res_a = StrategyA_ProductionBaseline.evaluate(dims, explicit_unit="mm")
    res_d = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm", has_do_not_scale=True)

    # Strategy A ignores constraint and produces scale
    assert res_a.can_generate_dxf is True

    # Strategy D strictly enforces constraint:
    assert res_d.state == CalibrationState.DO_NOT_SCALE_RESTRICTED
    assert res_d.can_generate_dxf is False
    assert "DO NOT SCALE" in res_d.notes[0]


def test_scenario_7_multiview_sheet_detail_view_isolation():
    """Scenario 7: Sheet has main view (1:1, scale 0.100) and detail view (5:1, scale 0.020).
    Strategy D isolates detail view scale and does not corrupt main sheet scale."""
    dims = [
        # Main view dimensions
        DimensionEvidence("main_1", 100.0, 1000.0, axis="X", view_id="main_view"),
        DimensionEvidence("main_2", 80.0, 800.0, axis="Y", view_id="main_view"),
        # Detail view dimensions (enlarged 5x)
        DimensionEvidence("det_1", 10.0, 500.0, axis="X", view_id="detail_view_a"),
        DimensionEvidence("det_2", 5.0, 250.0, axis="Y", view_id="detail_view_a"),
    ]

    res_d = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    # Main view scale must be 0.100 mm/px
    assert res_d.scale_x == pytest.approx(0.100, rel=1e-3)
    # Detail view scale must be isolated and stored in view_scales:
    assert res_d.view_scales["detail_view_a"] == pytest.approx(0.020, rel=1e-3)
    assert res_d.view_scales["main_view"] == pytest.approx(0.100, rel=1e-3)


def test_scenario_8_conflicting_dimensions_unresolvable():
    """Scenario 8: Sheet has conflicting dimensions with 15% discrepancy (no majority consensus)."""
    dims = [
        DimensionEvidence("d1", 100.0, 1000.0, axis="X"),  # 0.100
        DimensionEvidence("d2", 100.0, 850.0, axis="X"),   # 0.117 (17% delta)
    ]

    res_d = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    # Fails consensus -> CONFLICTING_AMBIGUOUS
    assert res_d.state == CalibrationState.CONFLICTING_AMBIGUOUS
    assert res_d.can_generate_dxf is False
    assert "Witness consensus failed" in res_d.notes[0]
