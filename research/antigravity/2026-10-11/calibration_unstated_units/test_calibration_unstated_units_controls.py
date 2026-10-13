"""Comprehensive Positive and Negative Controls for Unstated Units and Scale Calibration.

Tests:
1. test_positive_control_clean_metric_with_paper_corroboration
2. test_positive_control_clean_imperial_with_dxf_insunits
3. test_negative_control_unstated_unit_prohibits_verified_physical_and_dxf
4. test_negative_control_single_witness_refusal
5. test_negative_control_do_not_scale_hard_gate
6. test_negative_control_anisotropic_distortion_rejection
7. test_negative_control_cross_view_contamination_prevention
8. test_negative_control_outlier_dimension_isolation
"""

import pytest

from .calibration_unstated_units_engine import (
    DimensionEvidence,
    CalibrationState,
    UnitType,
    StrategyD_MultiDomainConsensusOracle,
)


def test_positive_control_clean_metric_with_paper_corroboration():
    """Positive Control: 4 concordant dimensions (X and Y), explicit 'mm',
    and matching 1:1 scale on 254 DPI sheet (scale = 0.100 mm/px).
    Must achieve VERIFIED_PHYSICAL, can_generate_dxf=True, dxf_insunits=4."""
    dims = [
        DimensionEvidence("d1", 100.0, 1000.0, axis="X"),
        DimensionEvidence("d2", 200.0, 2000.0, axis="X"),
        DimensionEvidence("d3", 50.0, 500.0, axis="Y"),
        DimensionEvidence("d4", 150.0, 1500.0, axis="Y"),
    ]

    res = StrategyD_MultiDomainConsensusOracle.evaluate(
        dims,
        explicit_unit="mm",
        scale_label_denominator=1,  # 1:1 scale
        page_dpi=254,               # 25.4 / 254 = 0.100 mm/px
    )

    assert res.state == CalibrationState.VERIFIED_PHYSICAL
    assert res.unit == UnitType.MILLIMETER
    assert res.unit_confidence == 1.0
    assert res.scale_x == pytest.approx(0.100, rel=1e-4)
    assert res.scale_y == pytest.approx(0.100, rel=1e-4)
    assert res.anisotropy_ratio == pytest.approx(1.0, rel=1e-4)
    assert res.can_generate_dxf is True
    assert res.dxf_insunits == 4
    assert len(res.contributing_witness_ids) == 4
    assert len(res.outlier_witness_ids) == 0


def test_positive_control_clean_imperial_with_dxf_insunits():
    """Positive Control: Concordant imperial dimensions with explicit 'in'.
    Must produce dxf_insunits=1 (Inches) and verify exact scale."""
    # 4.000 in = 400 px -> scale = 0.010 in/px
    dims = [
        DimensionEvidence("d1", 4.0, 400.0, axis="X"),
        DimensionEvidence("d2", 2.0, 200.0, axis="X"),
        DimensionEvidence("d3", 6.0, 600.0, axis="Y"),
        DimensionEvidence("d4", 1.0, 100.0, axis="Y"),
    ]

    res = StrategyD_MultiDomainConsensusOracle.evaluate(
        dims,
        explicit_unit="in",
        scale_label_denominator=1,
        page_dpi=100,  # 1.0 / 100 = 0.010 in/px
    )

    assert res.unit == UnitType.INCH
    assert res.scale_x == pytest.approx(0.010, rel=1e-4)
    assert res.dxf_insunits == 1


def test_negative_control_unstated_unit_prohibits_verified_physical_and_dxf():
    """Negative Control: Highly concordant dimensions (0.00% error) but UNSTATED unit.
    Must NEVER promote to VERIFIED_PHYSICAL.
    Must produce UNVERIFIED_DRAFT_REFERENCE, can_generate_dxf=False, dxf_insunits=0."""
    dims = [
        DimensionEvidence("d1", 100.0, 1000.0, axis="X"),
        DimensionEvidence("d2", 50.0, 500.0, axis="Y"),
        DimensionEvidence("d3", 200.0, 2000.0, axis="X"),
    ]

    res = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit=None)

    assert res.state == CalibrationState.UNVERIFIED_DRAFT_REFERENCE
    assert res.unit == UnitType.UNKNOWN_UNSTATED
    assert res.unit_confidence == 0.0
    assert res.can_generate_dxf is False
    assert res.dxf_insunits == 0
    assert res.scale_x == pytest.approx(0.100, rel=1e-4)


def test_negative_control_single_witness_refusal():
    """Negative Control: Single dimension candidate cannot satisfy consensus gate.
    Per AGENTS.md: requires >= 2 independent candidates."""
    dims = [
        DimensionEvidence("d1", 100.0, 1000.0, axis="X"),
    ]

    res = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    assert res.state == CalibrationState.UNKNOWN_UNSTATED
    assert res.can_generate_dxf is False
    assert "Fewer than 2 witnesses" in res.notes[0]


def test_negative_control_do_not_scale_hard_gate():
    """Negative Control: 'DO NOT SCALE' drawing must refuse candidate creation even
    with abundant matching dimensions."""
    dims = [
        DimensionEvidence("d1", 100.0, 1000.0, axis="X"),
        DimensionEvidence("d2", 50.0, 500.0, axis="Y"),
        DimensionEvidence("d3", 200.0, 2000.0, axis="X"),
    ]

    res = StrategyD_MultiDomainConsensusOracle.evaluate(
        dims,
        explicit_unit="mm",
        has_do_not_scale=True,
    )

    assert res.state == CalibrationState.DO_NOT_SCALE_RESTRICTED
    assert res.can_generate_dxf is False
    assert res.scale_x == 0.0
    assert res.scale_y == 0.0
    assert "DO NOT SCALE" in res.notes[0]


def test_negative_control_anisotropic_distortion_rejection():
    """Negative Control: 3.5% aspect ratio distortion between X and Y axes.
    Exceeds 1.5% maximum tolerance.
    Must refuse isotropic CAD generation and mark CONFLICTING_AMBIGUOUS."""
    dims = [
        DimensionEvidence("dx1", 100.0, 1000.0, axis="X"),  # scale = 0.1000
        DimensionEvidence("dx2", 50.0, 500.0, axis="X"),    # scale = 0.1000
        DimensionEvidence("dy1", 100.0, 1035.0, axis="Y"),  # scale = 0.0966 (3.5% stretch)
        DimensionEvidence("dy2", 50.0, 517.5, axis="Y"),    # scale = 0.0966
    ]

    res = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    assert res.state == CalibrationState.CONFLICTING_AMBIGUOUS
    assert abs(res.anisotropy_ratio - 1.0) > 0.015
    assert res.can_generate_dxf is False
    assert "Anisotropic scan distortion detected" in res.notes[0]


def test_negative_control_cross_view_contamination_prevention():
    """Negative Control: Sheet with main view (1:1) and detail view (2:1).
    Detail view dimensions must not dilute or bias main view scale."""
    dims = [
        # Main view (scale = 0.100)
        DimensionEvidence("m1", 100.0, 1000.0, axis="X", view_id="main_view"),
        DimensionEvidence("m2", 200.0, 2000.0, axis="X", view_id="main_view"),
        DimensionEvidence("m3", 50.0, 500.0, axis="Y", view_id="main_view"),
        # Detail view (scale = 0.050, 2:1 magnification)
        DimensionEvidence("det1", 10.0, 200.0, axis="X", view_id="detail_view_b"),
        DimensionEvidence("det2", 20.0, 400.0, axis="Y", view_id="detail_view_b"),
    ]

    res = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    # Main view scale must remain exactly 0.100
    assert res.scale_x == pytest.approx(0.100, rel=1e-4)
    # Detail view must be isolated
    assert "detail_view_b" in res.view_scales
    assert res.view_scales["detail_view_b"] == pytest.approx(0.050, rel=1e-4)
    assert res.view_scales["main_view"] == pytest.approx(0.100, rel=1e-4)


def test_negative_control_outlier_dimension_isolation():
    """Negative Control: Single corrupt dimension (e.g. OCR misread or wrong line association)
    must be cleanly placed in outlier_witness_ids without destroying consensus of valid witnesses."""
    dims = [
        DimensionEvidence("d1", 100.0, 1000.0, axis="X"),
        DimensionEvidence("d2", 150.0, 1500.0, axis="X"),
        DimensionEvidence("d3", 200.0, 2000.0, axis="X"),
        DimensionEvidence("d_bad", 10.0, 1000.0, axis="X"),  # scale = 0.010 (10x off)
    ]

    res = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    assert "d_bad" in res.outlier_witness_ids
    assert len(res.contributing_witness_ids) == 3
    assert res.scale_x == pytest.approx(0.100, rel=1e-4)
    assert res.state == CalibrationState.UNVERIFIED_DRAFT_REFERENCE
