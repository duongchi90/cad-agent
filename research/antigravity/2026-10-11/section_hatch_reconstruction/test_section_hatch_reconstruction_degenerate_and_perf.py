"""test_section_hatch_reconstruction_degenerate_and_perf.py — Degenerate cases and performance stress suite."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

import pytest

from section_hatch_reconstruction_engine import (
    BoundaryLoop,
    HatchPattern,
    HatchRegionResult,
    HatchStroke,
    SectionHatchReconstructionEngine,
)
from test_causal_red_section_hatch_reconstruction import _generate_parallel_hatch


def test_degenerate_01_empty_strokes_list():
    """Degenerate 1: Empty input list returns empty results."""
    engine = SectionHatchReconstructionEngine()
    res = engine.analyze([])
    assert len(res) == 0


def test_degenerate_02_zero_length_strokes():
    """Degenerate 2: Point strokes (start == end) are filtered safely without zero division."""
    zero_len_strokes = [
        HatchStroke("z1", (10.0, 10.0), (10.0, 10.0)),
        HatchStroke("z2", (20.0, 20.0), (20.0, 20.0)),
    ]

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(zero_len_strokes)
    assert len(res) == 0


def test_degenerate_03_non_finite_coordinates_nan_inf():
    """Degenerate 3: NaN and Infinity coordinates do not trigger unhandled exceptions."""
    nan_strokes = [
        HatchStroke("nan1", (float("nan"), 10.0), (20.0, 20.0)),
        HatchStroke("inf1", (10.0, float("inf")), (20.0, 20.0)),
        HatchStroke("ok1", (10.0, 10.0), (30.0, 30.0)),
    ]

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(nan_strokes)
    assert len(res) == 0


def test_degenerate_04_astronomical_coordinates():
    """Degenerate 4: Large coordinates (10^7 mm) process with full numeric stability."""
    offset = 10_000_000.0
    strokes = _generate_parallel_hatch(
        offset + 50.0, offset + 50.0, offset + 150.0, offset + 150.0, angle_deg=45.0, pitch_mm=5.0
    )

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(strokes)
    assert len(res) == 1
    assert abs(res[0].pattern.pitch_spacing_mm - 5.0) <= 0.5


def test_degenerate_05_sub_millimeter_micro_hatch():
    """Degenerate 5: Micro-scale features (pitch 0.05 mm) handled safely without crash."""
    strokes = [
        HatchStroke(f"m_{i}", (i * 0.05, 0.0), (i * 0.05 + 0.1, 0.1))
        for i in range(10)
    ]

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(strokes)
    # Filtered by length threshold or processed cleanly
    assert isinstance(res, list)


def test_degenerate_06_duplicate_coincident_strokes():
    """Degenerate 6: Coincident duplicate strokes do not cause zero-division in pitch diffs."""
    strokes = [
        HatchStroke("s1", (10.0, 10.0), (30.0, 30.0)),
        HatchStroke("s1_dup", (10.0, 10.0), (30.0, 30.0)),  # exact duplicate
        HatchStroke("s2", (15.0, 10.0), (35.0, 30.0)),
        HatchStroke("s3", (20.0, 10.0), (40.0, 30.0)),
        HatchStroke("s4", (25.0, 10.0), (45.0, 30.0)),
    ]

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(strokes)
    assert len(res) == 1
    assert res[0].pattern.pitch_spacing_mm > 0.0


def test_perf_07_large_scale_hatch_throughput():
    """Performance Stress 7: 500 hatch strokes across multiple sections process in < 100ms."""
    strokes = []
    # Generate 5 separate hatched regions each having 100 strokes
    for r in range(5):
        y_off = r * 150.0
        r_strokes = _generate_parallel_hatch(
            50.0, y_off + 20.0, 300.0, y_off + 120.0, angle_deg=45.0, pitch_mm=2.5
        )
        strokes.extend(r_strokes)

    assert len(strokes) >= 300  # High stroke count

    engine = SectionHatchReconstructionEngine()

    start_time = time.perf_counter()
    res = engine.analyze(strokes)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    assert len(res) >= 1
    # Latency budget: < 100 ms
    assert elapsed_ms < 100.0, f"Analysis took {elapsed_ms:.2f} ms (budget: 100.0 ms)"
