"""Degenerate Edge Cases, Robustness, and Performance Latency Test Suite.

Tests:
1. test_degenerate_empty_inputs
2. test_degenerate_zero_and_negative_dimensions
3. test_degenerate_non_finite_floating_point_values
4. test_extreme_micro_and_macro_scales
5. test_performance_latency_large_batch
"""

import math
import time
import pytest

from .calibration_unstated_units_engine import (
    DimensionEvidence,
    CalibrationState,
    UnitType,
    StrategyD_MultiDomainConsensusOracle,
)


def test_degenerate_empty_inputs():
    """Empty dimensions list must gracefully return UNKNOWN_UNSTATED without exception."""
    res = StrategyD_MultiDomainConsensusOracle.evaluate([])

    assert res.state == CalibrationState.UNKNOWN_UNSTATED
    assert res.scale_x == 0.0
    assert res.scale_y == 0.0
    assert res.unit == UnitType.UNKNOWN_UNSTATED
    assert res.can_generate_dxf is False


def test_degenerate_zero_and_negative_dimensions():
    """Zero or negative stated values and pixel lengths must be filtered safely."""
    dims = [
        DimensionEvidence("d_zero_val", 0.0, 100.0, axis="X"),
        DimensionEvidence("d_zero_px", 50.0, 0.0, axis="X"),
        DimensionEvidence("d_neg_val", -10.0, 100.0, axis="X"),
        DimensionEvidence("d_neg_px", 50.0, -500.0, axis="X"),
    ]

    res = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    assert res.state == CalibrationState.UNKNOWN_UNSTATED
    assert res.can_generate_dxf is False
    assert len(res.contributing_witness_ids) == 0


def test_degenerate_non_finite_floating_point_values():
    """NaN and Infinite values must not crash consensus computation."""
    dims = [
        DimensionEvidence("d_nan_val", float("nan"), 100.0, axis="X"),
        DimensionEvidence("d_inf_val", float("inf"), 100.0, axis="X"),
        DimensionEvidence("d_nan_px", 50.0, float("nan"), axis="X"),
        DimensionEvidence("d_inf_px", 50.0, float("inf"), axis="X"),
        # Valid dimensions to see if consensus can still proceed
        DimensionEvidence("d_valid1", 100.0, 1000.0, axis="X"),
        DimensionEvidence("d_valid2", 50.0, 500.0, axis="X"),
    ]

    res = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")

    assert res.state == CalibrationState.UNVERIFIED_DRAFT_REFERENCE
    assert res.scale_x == pytest.approx(0.100, rel=1e-4)
    assert set(res.contributing_witness_ids) == {"d_valid1", "d_valid2"}


def test_extreme_micro_and_macro_scales():
    """Extreme dynamic range:
    - Micro-scale (MEMS/nanotech): 0.001 mm across 10,000 px -> 1e-7 mm/px
    - Macro-scale (Civil/Geodetic): 100,000 mm across 100 px -> 1000.0 mm/px
    Numerical precision must remain stable without underflow or roundoff distortion."""
    # Micro test
    micro_dims = [
        DimensionEvidence("m1", 0.001, 10000.0, axis="X"),
        DimensionEvidence("m2", 0.002, 20000.0, axis="X"),
    ]
    res_micro = StrategyD_MultiDomainConsensusOracle.evaluate(micro_dims, explicit_unit="mm")
    assert res_micro.state == CalibrationState.UNVERIFIED_DRAFT_REFERENCE
    assert res_micro.scale_x == pytest.approx(1e-7, rel=1e-5)

    # Macro test
    macro_dims = [
        DimensionEvidence("c1", 100000.0, 100.0, axis="X"),
        DimensionEvidence("c2", 50000.0, 50.0, axis="X"),
    ]
    res_macro = StrategyD_MultiDomainConsensusOracle.evaluate(macro_dims, explicit_unit="mm")
    assert res_macro.state == CalibrationState.UNVERIFIED_DRAFT_REFERENCE
    assert res_macro.scale_x == pytest.approx(1000.0, rel=1e-5)


def test_performance_latency_large_batch():
    """Evaluating 500 dimension candidates must complete in under 25 milliseconds."""
    dims = []
    for i in range(500):
        axis = "X" if i % 2 == 0 else "Y"
        val = 10.0 + (i % 20) * 5.0
        # Add slight noise within +/- 0.5%
        noise = 1.0 + ((i % 10) - 5) * 0.001
        px = (val / 0.100) * noise
        dims.append(DimensionEvidence(f"d_{i}", val, px, axis=axis))

    t0 = time.perf_counter()
    res = StrategyD_MultiDomainConsensusOracle.evaluate(dims, explicit_unit="mm")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert res.state == CalibrationState.UNVERIFIED_DRAFT_REFERENCE
    assert res.scale_x == pytest.approx(0.100, rel=0.01)
    assert len(res.contributing_witness_ids) == 500
    assert elapsed_ms < 25.0, f"Expected < 25ms, got {elapsed_ms:.2f}ms"
