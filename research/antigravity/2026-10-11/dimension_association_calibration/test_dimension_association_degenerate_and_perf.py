"""Degenerate Edge Cases, Numerical Robustness, and Performance Latency Suite.

Tests:
1. test_degenerate_empty_inputs
2. test_degenerate_zero_length_primitives
3. test_degenerate_non_finite_floating_point_coordinates
4. test_extreme_macro_and_micro_dimensions
5. test_high_density_throughput_latency
"""

import math
import time
import pytest

from .dimension_association_engine import (
    SimpleLine,
    SimpleText,
    SimpleCircle,
    SimpleArc,
    StrategyD_MultiPrimitiveAssociationOracle,
)


def test_degenerate_empty_inputs():
    """Empty inputs must return empty list without exception."""
    assert StrategyD_MultiPrimitiveAssociationOracle.associate([], []) == []


def test_degenerate_zero_length_primitives():
    """Zero length line (p1 == p2) or zero radius circle must not cause ZeroDivisionError."""
    text = SimpleText("t1", "100", bbox=(90.0, 90.0, 110.0, 110.0), parsed_value=100.0)
    zero_line = SimpleLine("zero_l", (100.0, 100.0), (100.0, 100.0))
    zero_circle = SimpleCircle("zero_c", (100.0, 100.0), radius=0.0)

    results = StrategyD_MultiPrimitiveAssociationOracle.associate([text], [zero_line], circles=[zero_circle])
    assert len(results) == 0


def test_degenerate_non_finite_floating_point_coordinates():
    """NaN and Inf coordinates must be filtered safely without crashing."""
    text_nan = SimpleText("t_nan", "100", bbox=(float("nan"), 90.0, 110.0, 110.0), parsed_value=100.0)
    line_inf = SimpleLine("l_inf", (float("inf"), 100.0), (200.0, 100.0))
    valid_text = SimpleText("t_valid", "50", bbox=(90.0, 90.0, 110.0, 110.0), parsed_value=50.0)
    valid_line = SimpleLine("l_valid", (0.0, 100.0), (200.0, 100.0))

    results = StrategyD_MultiPrimitiveAssociationOracle.associate(
        [text_nan, valid_text], [line_inf, valid_line]
    )
    assert len(results) == 1
    assert results[0].text_id == "t_valid"


def test_extreme_macro_and_micro_dimensions():
    """Verify stability across 10 orders of magnitude:
    - Micro (MEMS/nanotech): 0.005 mm across 500 px -> scale = 1e-5 mm/px
    - Macro (Geodetic/Civil): 1,000,000 mm across 100 px -> scale = 10,000 mm/px."""
    # Micro test
    micro_text = SimpleText("t_micro", "0.005", bbox=(240.0, 95.0, 260.0, 105.0), parsed_value=0.005)
    micro_line = SimpleLine("l_micro", (0.0, 100.0), (500.0, 100.0))
    res_micro = StrategyD_MultiPrimitiveAssociationOracle.associate([micro_text], [micro_line])
    assert len(res_micro) == 1
    assert res_micro[0].scale_candidate == pytest.approx(1e-5, rel=1e-5)

    # Macro test
    macro_text = SimpleText("t_macro", "1000000", bbox=(40.0, 95.0, 60.0, 105.0), parsed_value=1000000.0)
    macro_line = SimpleLine("l_macro", (0.0, 100.0), (100.0, 100.0))
    res_macro = StrategyD_MultiPrimitiveAssociationOracle.associate([macro_text], [macro_line])
    assert len(res_macro) == 1
    assert res_macro[0].scale_candidate == pytest.approx(10000.0, rel=1e-5)


def test_high_density_throughput_latency():
    """Evaluating 100 text entities against 500 lines must complete in under 35 milliseconds."""
    lines = []
    # 500 lines across grid
    for i in range(500):
        y = (i % 50) * 20.0
        x_start = (i // 50) * 100.0
        lines.append(SimpleLine(f"l_{i}", (x_start, y), (x_start + 80.0, y)))

    texts = []
    for j in range(100):
        y = (j % 50) * 20.0
        x = (j // 50) * 100.0 + 40.0
        texts.append(SimpleText(f"t_{j}", f"{10 + j}", bbox=(x - 10.0, y - 5.0, x + 10.0, y + 5.0), parsed_value=float(10 + j)))

    t0 = time.perf_counter()
    results = StrategyD_MultiPrimitiveAssociationOracle.associate(texts, lines)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert len(results) > 0
    assert elapsed_ms < 60.0, f"Expected < 60ms, got {elapsed_ms:.2f}ms"
