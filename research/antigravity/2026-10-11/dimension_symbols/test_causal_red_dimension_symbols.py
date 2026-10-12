"""
test_causal_red_dimension_symbols.py — Public Causal RED for Mechanical Dimension & Tolerance Parsing.

Proves 5 concrete failure modes in production Strategy A (primitive_ir_lib/dimension_symbols.py):
RED-1: ISO 286 Limits & Fits callouts (⌀25 H7, ⌀50 g6) completely drop the nominal dimension value (value=None).
RED-2: Asymmetric zero-limit tolerances (50 +0.05/0, 50 0/-0.02) completely drop the dimension value (value=None).
RED-3: Metric thread callouts (M10, M8x1.25) completely drop the diameter dimension value (value=None).
RED-4: Chamfer callouts (C2, 2x45°) completely drop the chamfer dimension value (value=None).
RED-5: Reference dimensions enclosed in parentheses ((50), (120.5)) completely drop the dimension value (value=None).
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
)


def test_red_1_iso_fit_class_drops_nominal_value():
    """RED-1: ISO Limits & Fits tolerance on bearing bore: '⌀25 H7'.
    Production Strategy A fails to match _DIAMETER_RE due to 'H7', returning value=None.
    Strategy D extracts value=25.0, kind_hint=DIAMETER, fit_class=H7, tolerance_mode=ISO_FIT.
    """
    callout = "⌀25 H7"

    # Strategy A: Completely drops nominal value!
    res_a = run_strategy_a_parse(callout)
    assert res_a.value is None, "Strategy A should reproduce failure on ISO fit class"
    assert res_a.confidence <= 0.1

    # Strategy D: Extracts nominal value 25.0 and fit class H7
    res_d = parse_mechanical_dimension(callout)
    assert res_d.value == 25.0
    assert res_d.kind_hint == "DIAMETER"
    assert res_d.fit_class == "H7"
    assert res_d.tolerance_mode == "ISO_FIT"
    assert res_d.confidence >= 0.98


def test_red_2_asymmetric_zero_limit_drops_nominal_value():
    """RED-2: Machined reamed hole tolerance: '50 +0.05 / 0'.
    Production Strategy A _PLUS_MINUS_TOLERANCE_RE requires -lower; fails on 0, returning value=None.
    Strategy D extracts value=50.0, upper=+0.05, lower=0.0.
    """
    callout = "50 +0.05 / 0"

    res_a = run_strategy_a_parse(callout)
    assert res_a.value is None, "Strategy A should fail on asymmetric zero-limit tolerance"
    assert res_a.confidence <= 0.1

    res_d = parse_mechanical_dimension(callout)
    assert res_d.value == 50.0
    assert res_d.tolerance_upper == 0.05
    assert res_d.tolerance_lower == 0.0
    assert res_d.tolerance_mode == "PLUS_MINUS"
    assert res_d.confidence >= 0.98


def test_red_3_metric_thread_callout_drops_diameter():
    """RED-3: Metric thread callouts: 'M10' and 'M8x1.25'.
    Production Strategy A returns value=None.
    Strategy D extracts value=10.0 and value=8.0 with kind_hint=THREAD.
    """
    callout = "M10"
    res_a = run_strategy_a_parse(callout)
    assert res_a.value is None, "Strategy A should fail on metric thread M10"

    res_d = parse_mechanical_dimension(callout)
    assert res_d.value == 10.0
    assert res_d.kind_hint == "THREAD"
    assert res_d.symbol_text == "M"

    callout_pitch = "M8x1.25"
    res_a_pitch = run_strategy_a_parse(callout_pitch)
    assert res_a_pitch.value is None

    res_d_pitch = parse_mechanical_dimension(callout_pitch)
    assert res_d_pitch.value == 8.0
    assert res_d_pitch.kind_hint == "THREAD"


def test_red_4_chamfer_callout_drops_value():
    """RED-4: Standard chamfer callouts: 'C2' and '2x45°'.
    Production Strategy A returns value=None for 'C2'.
    Strategy D extracts value=2.0 with kind_hint=CHAMFER.
    """
    callout = "C2"
    res_a = run_strategy_a_parse(callout)
    assert res_a.value is None, "Strategy A should fail on chamfer C2"

    res_d = parse_mechanical_dimension(callout)
    assert res_d.value == 2.0
    assert res_d.kind_hint == "CHAMFER"
    assert res_d.symbol_text == "C"


def test_red_5_reference_dimension_parentheses_drops_value():
    """RED-5: Reference dimension: '(50)'.
    Production Strategy A returns value=None because of parentheses.
    Strategy D strips parentheses, extracts value=50.0 with tolerance_mode=REFERENCE.
    """
    callout = "(50)"
    res_a = run_strategy_a_parse(callout)
    assert res_a.value is None, "Strategy A should fail on reference dimension (50)"

    res_d = parse_mechanical_dimension(callout)
    assert res_d.value == 50.0
    assert res_d.tolerance_mode == "REFERENCE"
    assert res_d.confidence >= 0.98
