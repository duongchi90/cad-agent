"""Degenerate, non-finite, and performance test suite for dimension symbol parsing.

Epic: MECHANICAL_DIMENSION_AND_TOLERANCE_PARSING_V1
Role: ANTIGRAVITY_RESEARCH
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from dimension_symbol_engine import (
    parse_mechanical_dimension,
    EnhancedParsedDimension,
)


def test_degenerate_empty_and_whitespace():
    """Verify empty and whitespace strings return safe default results."""
    for empty_input in ["", "   ", "\t\n", "\r\n  \t"]:
        res = parse_mechanical_dimension(empty_input)
        assert isinstance(res, EnhancedParsedDimension)
        assert res.value is None
        assert res.confidence == 0.0
        assert res.kind_hint is None


def test_degenerate_lone_symbols():
    """Verify standalone symbol tokens without numeric payloads do not crash or emit bogus values."""
    lone_symbols = ["⌀", "R", "M", "C", "±", "°", "SR", "S⌀", "THRU", "↧", "H7", "g6", "(", ")", "[", "]"]
    for sym in lone_symbols:
        res = parse_mechanical_dimension(sym)
        assert isinstance(res, EnhancedParsedDimension)
        assert res.value is None
        assert res.confidence <= 0.1


def test_degenerate_multiple_punctuation_and_noise():
    """Verify multiple dots, commas, colons, or garbage characters do not crash."""
    garbage_inputs = [
        "....",
        ",,,,",
        "::::",
        "10.20.30",
        "±±±0.1",
        "⌀⌀50",
        "M x 1.5",
        "C x 45",
        "((50))",
        "[[25]]",
    ]
    for garb in garbage_inputs:
        res = parse_mechanical_dimension(garb)
        assert isinstance(res, EnhancedParsedDimension)
        if res.value is not None:
            assert isinstance(res.value, float)
            assert not math.isnan(res.value)
            assert not math.isinf(res.value)


def test_nonfinite_and_extreme_numeric_strings():
    """Verify NaN, Inf, and extreme exponent strings do not produce non-finite floats."""
    extremes = ["NaN", "Inf", "+Infinity", "-Infinity", "1e309", "-1e309"]
    for ext in extremes:
        res = parse_mechanical_dimension(ext)
        assert isinstance(res, EnhancedParsedDimension)
        if res.value is not None:
            assert not math.isnan(res.value)
            assert not math.isinf(res.value)


def test_ambiguity_mixed_symbols():
    """Verify compound/ambiguous expressions are resolved deterministically."""
    # S⌀20 is spherical diameter, value 20.0, kind SPHERICAL_DIAMETER
    res1 = parse_mechanical_dimension("S⌀20")
    assert res1.value == 20.0
    assert res1.kind_hint == "SPHERICAL_DIAMETER"

    # SR15 is spherical radius, value 15.0, kind SPHERICAL_RADIUS
    res2 = parse_mechanical_dimension("SR15")
    assert res2.value == 15.0
    assert res2.kind_hint == "SPHERICAL_RADIUS"

    # 4x ⌀12 THRU
    res3 = parse_mechanical_dimension("4x ⌀12 THRU")
    assert res3.value == 12.0
    assert res3.repeat_count == 4
    assert res3.is_thru is True
    assert res3.kind_hint == "DIAMETER"


def test_performance_1000_parses_budget():
    """Verify parser throughput on 1000 real-world engineering callouts completes in < 60ms."""
    workload = [
        "⌀25 H7",
        "M10x1.5",
        "50 ±0.1",
        "C2",
        "(40)",
        "⌀10 ↧ 15",
        "50 +0.05 / 0",
        "R12.5",
        "4x ⌀8 THRU",
        "120° ±0.5°",
        "SR15",
        "25,4 +0,1 / -0,2",
    ] * 100  # 1200 parses

    start_time = time.perf_counter()
    for text in workload:
        res = parse_mechanical_dimension(text)
        assert res.value is not None
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Measured latency budget: 1200 calls in < 60ms (< 0.05ms per call)
    assert elapsed_ms < 60.0, f"Expected < 60ms for 1200 parses, got {elapsed_ms:.2f}ms"
