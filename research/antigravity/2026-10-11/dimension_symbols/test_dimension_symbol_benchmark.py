"""
test_dimension_symbol_benchmark.py — Multi-Strategy Benchmark Suite for Dimension Symbol Parsing.

Benchmarks Strategies A, B, C, D across 8 mechanical engineering callouts:
1. Scenario 1: Shaft Fit with Tolerance (⌀50 g6)
2. Scenario 2: Reamed Hole Fit (⌀25 H7)
3. Scenario 3: Blind Hole with Depth (4x ⌀10.5 ↧ 18)
4. Scenario 4: Through Hole Callout (⌀9 THRU)
5. Scenario 5: Fine Metric Thread (M16x1.5)
6. Scenario 6: Metric Chamfer (C1.5)
7. Scenario 7: Reference Dimension ((125.0))
8. Scenario 8: Asymmetric Zero-Limit Tolerance (45 +0.02 / 0)
"""

from __future__ import annotations

import sys
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
    run_strategy_a_parse,
    run_strategy_b_parse,
    run_strategy_c_parse,
)


def test_scenario_1_shaft_fit():
    """Scenario 1: Shaft Fit '⌀50 g6'."""
    callout = "⌀50 g6"
    res_a = run_strategy_a_parse(callout)
    res_d = parse_mechanical_dimension(callout)

    assert res_a.value is None, "Strategy A drops nominal on shaft fit"
    assert res_d.value == 50.0
    assert res_d.kind_hint == "DIAMETER"
    assert res_d.fit_class == "g6"


def test_scenario_2_reamed_hole_fit():
    """Scenario 2: Reamed Hole Fit '⌀25 H7'."""
    callout = "⌀25 H7"
    res_a = run_strategy_a_parse(callout)
    res_d = parse_mechanical_dimension(callout)

    assert res_a.value is None
    assert res_d.value == 25.0
    assert res_d.kind_hint == "DIAMETER"
    assert res_d.fit_class == "H7"


def test_scenario_3_blind_hole_with_depth():
    """Scenario 3: Blind Hole Pattern '4x ⌀10.5 ↧ 18'."""
    callout = "4x ⌀10.5 ↧ 18"
    res_a = run_strategy_a_parse(callout)
    res_d = parse_mechanical_dimension(callout)

    assert res_a.value is None
    assert res_d.value == 10.5
    assert res_d.repeat_count == 4
    assert res_d.depth_mm == 18.0
    assert res_d.kind_hint == "DIAMETER"


def test_scenario_4_through_hole_callout():
    """Scenario 4: Through Hole Callout '⌀9 THRU'."""
    callout = "⌀9 THRU"
    res_a = run_strategy_a_parse(callout)
    res_d = parse_mechanical_dimension(callout)

    assert res_a.value is None
    assert res_d.value == 9.0
    assert res_d.is_thru is True
    assert res_d.kind_hint == "DIAMETER"


def test_scenario_5_fine_metric_thread():
    """Scenario 5: Fine Metric Thread 'M16x1.5'."""
    callout = "M16x1.5"
    res_a = run_strategy_a_parse(callout)
    res_d = parse_mechanical_dimension(callout)

    assert res_a.value is None
    assert res_d.value == 16.0
    assert res_d.kind_hint == "THREAD"
    assert res_d.symbol_text == "M"


def test_scenario_6_metric_chamfer():
    """Scenario 6: Metric Chamfer 'C1.5'."""
    callout = "C1.5"
    res_a = run_strategy_a_parse(callout)
    res_d = parse_mechanical_dimension(callout)

    assert res_a.value is None
    assert res_d.value == 1.5
    assert res_d.kind_hint == "CHAMFER"


def test_scenario_7_reference_dimension():
    """Scenario 7: Reference Dimension '(125.0)'."""
    callout = "(125.0)"
    res_a = run_strategy_a_parse(callout)
    res_d = parse_mechanical_dimension(callout)

    assert res_a.value is None
    assert res_d.value == 125.0
    assert res_d.tolerance_mode == "REFERENCE"


def test_scenario_8_asymmetric_zero_limit_tolerance():
    """Scenario 8: Asymmetric Zero-Limit Tolerance '45 +0.02 / 0'."""
    callout = "45 +0.02 / 0"
    res_a = run_strategy_a_parse(callout)
    res_d = parse_mechanical_dimension(callout)

    assert res_a.value is None
    assert res_d.value == 45.0
    assert res_d.tolerance_upper == 0.02
    assert res_d.tolerance_lower == 0.0
    assert res_d.tolerance_mode == "PLUS_MINUS"
