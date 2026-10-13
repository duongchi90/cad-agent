"""Degenerate and Performance Test Suite for Calibration Candidate Extraction Transfer Architecture.

Verifies mathematical boundary conditions, non-finite handling, extreme scale dynamic ranges,
and strict latency bounds (< 50ms for 100 texts x 500 lines + 50 circles).
"""

import math
import time
import pytest

from .calibration_candidate_transfer_engine import (
    TransferState,
    MethodC_GuardedMultiPrimitiveOracle,
    SimpleLine,
    SimpleText,
    SimpleCircle,
)


def test_degenerate_empty_inputs():
    """Empty inputs must return NO_CANDIDATE_SUPPORTED with no exceptions."""
    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(texts=[], lines=[], circles=[])
    assert res.status == TransferState.NO_CANDIDATE_SUPPORTED
    assert res.estimated_scale is None
    assert len(res.contributing_candidates) == 0
    assert res.is_reviewable is False


def test_degenerate_zero_length_and_zero_radius():
    """Zero-length lines and zero-radius circles must not trigger ZeroDivisionError."""
    t1 = SimpleText("t1", "50", bbox=(10.0, 10.0, 30.0, 20.0), parsed_value=50.0)
    zero_line = SimpleLine("l_zero", (15.0, 15.0), (15.0, 15.0))
    zero_circle = SimpleCircle("c_zero", (20.0, 15.0), radius=0.0)

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=[t1],
        lines=[zero_line],
        circles=[zero_circle],
    )
    assert res.status == TransferState.NO_CANDIDATE_SUPPORTED
    assert res.estimated_scale is None


def test_degenerate_zero_or_negative_parsed_values():
    """Non-positive dimension values (0 or negative) must be safely filtered."""
    t_zero = SimpleText("t0", "0", bbox=(10.0, 10.0, 30.0, 20.0), parsed_value=0.0)
    t_neg = SimpleText("tn", "-10", bbox=(40.0, 10.0, 60.0, 20.0), parsed_value=-10.0)
    line = SimpleLine("l1", (0.0, 15.0), (100.0, 15.0))

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=[t_zero, t_neg],
        lines=[line],
    )
    assert res.status == TransferState.NO_CANDIDATE_SUPPORTED
    assert res.estimated_scale is None


def test_degenerate_non_finite_coordinates():
    """NaN or Inf coordinates must not crash the extractor."""
    t_nan = SimpleText("tnan", "50", bbox=(float("nan"), 10.0, 30.0, 20.0), parsed_value=50.0)
    l_inf = SimpleLine("linf", (0.0, 0.0), (float("inf"), 10.0))
    c_nan = SimpleCircle("cnan", (float("nan"), 0.0), radius=10.0)

    # Valid candidate alongside non-finite ones
    t_valid1 = SimpleText("tv1", "100", bbox=(480.0, 90.0, 520.0, 110.0), parsed_value=100.0)
    l_valid1 = SimpleLine("lv1", (0.0, 100.0), (1000.0, 100.0))
    t_valid2 = SimpleText("tv2", "50", bbox=(90.0, 230.0, 110.0, 270.0), rotation_deg=90.0, parsed_value=50.0)
    l_valid2 = SimpleLine("lv2", (100.0, 0.0), (100.0, 500.0))

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=[t_nan, t_valid1, t_valid2],
        lines=[l_inf, l_valid1, l_valid2],
        circles=[c_nan],
    )

    # The valid candidates must still extract cleanly despite noisy NaN inputs:
    assert res.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res.estimated_scale == pytest.approx(0.100, rel=1e-3)


def test_micro_macro_scale_dynamic_range():
    """Verifies numerical precision across 6 orders of magnitude (micro MEMS to macro Civil)."""
    # 1. Micro Scale: 0.0001 mm/px (0.1 micron per pixel)
    t_micro1 = SimpleText("tm1", "0.05", bbox=(230.0, 90.0, 270.0, 110.0), parsed_value=0.05)
    l_micro1 = SimpleLine("lm1", (0.0, 100.0), (500.0, 100.0))
    t_micro2 = SimpleText("tm2", "0.10", bbox=(480.0, 190.0, 520.0, 210.0), parsed_value=0.10)
    l_micro2 = SimpleLine("lm2", (0.0, 200.0), (1000.0, 200.0))

    res_micro = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=[t_micro1, t_micro2],
        lines=[l_micro1, l_micro2],
    )
    assert res_micro.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res_micro.estimated_scale == pytest.approx(0.0001, rel=1e-3)

    # 2. Macro Scale: 10.0 mm/px (10 meters per 1000px)
    t_macro1 = SimpleText("tM1", "5000", bbox=(230.0, 90.0, 270.0, 110.0), parsed_value=5000.0)
    l_macro1 = SimpleLine("lM1", (0.0, 100.0), (500.0, 100.0))
    t_macro2 = SimpleText("tM2", "10000", bbox=(480.0, 190.0, 520.0, 210.0), parsed_value=10000.0)
    l_macro2 = SimpleLine("lM2", (0.0, 200.0), (1000.0, 200.0))

    res_macro = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=[t_macro1, t_macro2],
        lines=[l_macro1, l_macro2],
    )
    assert res_macro.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res_macro.estimated_scale == pytest.approx(10.0, rel=1e-3)


def test_performance_and_latency_budget():
    """Evaluates throughput on a large drawing: 100 texts x 500 lines + 50 circles.
    Target: < 50ms total execution time on standard CPU."""
    # Build 100 texts
    texts = []
    lines = []
    circles = []

    # 5 true dimension witness pairs (horizontal bridged pairs)
    for i in range(5):
        y = 100.0 * (i + 1)
        texts.append(SimpleText(f"tdim_{i}", "100", bbox=(480.0, y - 10.0, 520.0, y + 10.0), parsed_value=100.0))
        lines.append(SimpleLine(f"ldim_{i}_a", (0.0, y), (450.0, y)))
        lines.append(SimpleLine(f"ldim_{i}_b", (550.0, y), (1000.0, y)))

    # 95 background/clutter texts (notes, title blocks, bill of materials)
    for i in range(95):
        texts.append(SimpleText(f"tclutter_{i}", f"NOTE {i}", bbox=(float(i * 10), 1000.0, float(i * 10 + 20), 1020.0), parsed_value=None, semantic_role="drawing_note"))

    # 490 background/geometry lines
    for i in range(490):
        lines.append(SimpleLine(f"lbg_{i}", (float(i * 5), float(i * 3 + 2000)), (float(i * 5 + 50), float(i * 3 + 2020))))

    # 50 circles
    for i in range(50):
        circles.append(SimpleCircle(f"cbg_{i}", (float(i * 30), 3000.0), radius=float(5 + i % 20)))

    # Measure execution time
    t0 = time.perf_counter()
    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=texts,
        lines=lines,
        circles=circles,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert res.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res.estimated_scale == pytest.approx(0.100, rel=1e-3)
    assert len(res.contributing_candidates) >= 2
    # Latency budget: strictly under 50ms
    assert elapsed_ms < 50.0, f"Expected < 50ms, took {elapsed_ms:.2f}ms"
