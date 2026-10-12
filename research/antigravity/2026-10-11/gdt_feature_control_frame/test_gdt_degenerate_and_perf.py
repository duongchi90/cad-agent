"""Degenerate cases, stress scenarios, and performance tests for GD&T FCF parsing."""

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

from gdt_engine import (
    GeometricCharacteristic,
    MaterialCondition,
    ToleranceZoneShape,
    run_strategy_d,
)


def test_perf_1000_fcf_strings_under_150ms():
    """Performance test: 1,000 FCF candidates parsed in < 150ms."""
    sample_fcfs = [
        "[⌖ | ⌀0.05 Ⓜ | A | B | C]",
        "[⟂ | 0.02 | A | B]",
        "[⏥ | 0.03]",
        "[⌭ | 0.015]",
        "[⌓ | 0.1 | A-B | C]",
        "[◎ | ⌀0.02 | A]",
        "[↗ | 0.04 | A]",
        "POS DIA 0.08 MMC A B",
        "100.0 ± 0.05",  # Noise (rejected)
        "HEAT TREAT NOTE",  # Noise (rejected)
    ]
    test_batch = sample_fcfs * 100  # 1,000 items

    t0 = time.perf_counter()
    parsed_count = 0
    for text in test_batch:
        res = run_strategy_d(text)
        if res is not None:
            parsed_count += 1
    elapsed = time.perf_counter() - t0

    assert parsed_count == 800  # Exactly 800 valid FCFs, 200 non-FCF noise rejected
    assert elapsed < 0.15, f"Expected runtime < 150ms, took {elapsed * 1000:.2f}ms"


def test_micro_scale_tolerances():
    """Micro-scale precision tolerances: 0.0005 mm (0.5 micrometer)."""
    text = "[⏥ | 0.0005]"
    res = run_strategy_d(text)
    assert res is not None
    assert math.isclose(res.tolerance_zone.value, 0.0005)


def test_macro_scale_tolerances():
    """Macro-scale structural tolerances: 15.0 mm."""
    text = "[⌖ | ⌀15.0 | A | B]"
    res = run_strategy_d(text)
    assert res is not None
    assert res.tolerance_zone.value == 15.0


def test_compound_multiple_datums():
    """Compound datums 'A-B' and 'C-D'."""
    text = "[⌖ | ⌀0.05 | A-B | C-D]"
    res = run_strategy_d(text)
    assert res is not None
    assert len(res.datums) == 2
    assert res.datums[0].letter == "A-B"
    assert res.datums[1].letter == "C-D"


def test_ocr_noise_resilience():
    """OCR artifacts: double pipes, irregular spacing, mixed brackets."""
    noisy_text = " [ | ⌖ || ⌀ 0.05 (M) | A | B (M) | C | ] "
    res = run_strategy_d(noisy_text)
    assert res is not None
    assert res.characteristic == GeometricCharacteristic.POSITION
    assert res.tolerance_zone.value == 0.05
    assert res.tolerance_zone.material_condition == MaterialCondition.MMC
    assert len(res.datums) == 3


def test_single_symbol_noise_rejected():
    """Single standalone GD&T symbols without numbers return None."""
    standalone = ["⌖", "⏥", "⫽", "⟂", "◎", "↗", "POS", "FLAT"]
    for s in standalone:
        assert run_strategy_d(s) is None


def test_stability_repeated_execution():
    """Verify deterministic repeatability over 50 iterations."""
    text = "[⌖ | ⌀0.02 Ⓜ | A | B]"
    for _ in range(50):
        res = run_strategy_d(text)
        assert res is not None
        assert res.tolerance_zone.value == 0.02
        assert res.confidence == 0.99
