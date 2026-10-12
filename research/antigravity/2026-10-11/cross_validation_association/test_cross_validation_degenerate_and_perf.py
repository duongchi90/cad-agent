"""Degenerate, numeric safety, edge cases, and performance profiling for Cross-Validation.

Covers 7 tests:
1. Edge 1: Empty inputs safe handling.
2. Edge 2: Zero parsed value safe handling (status='unverified').
3. Edge 3: Micro / zero-length line and zero-radius circle filtering.
4. Edge 4: Non-finite coordinate (NaN / Inf) safety.
5. Edge 5: Extreme coordinate magnitude (10^6 px) numerical stability.
6. Edge 6: Negative dimension value handling.
7. Perf 7: Large-scale latency and throughput profiling (50 texts x 250 primitives in < 25 ms).
"""

import sys
from pathlib import Path
import pytest
import math
import time

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from cross_validation_engine import (
    RawLine,
    RawCircle,
    RawArc,
    RawText,
    Calibration,
    strategy_d_cross_validate,
)


def _cal(scale: float = 1.0) -> Calibration:
    return Calibration(pixel_to_unit_scale=scale)


def test_edge_1_empty_inputs_safe_handling():
    """Edge 1: Empty texts return empty list; empty geometry returns unverified."""
    res_empty = strategy_d_cross_validate([], raw_lines=[], calibration=_cal())
    assert res_empty == []

    text = RawText("t1", "100", (10.0, 10.0, 20.0, 20.0), rotation_deg=0.0, parsed_value=100.0)
    res_no_geom = strategy_d_cross_validate([text], raw_lines=[], raw_circles=[], calibration=_cal())
    assert len(res_no_geom) == 1
    assert res_no_geom[0].status == "unverified"
    assert res_no_geom[0].geometry_id == ""


def test_edge_2_zero_parsed_value_unverified():
    """Edge 2: Zero parsed value (e.g. OCR hallucination '00') must produce status='unverified'."""
    line = RawLine("l1", (100.0, 100.0), (200.0, 100.0))
    text_zero = RawText("t_zero", "00", (140.0, 85.0, 160.0, 95.0), rotation_deg=0.0, parsed_value=0.0)

    results = strategy_d_cross_validate([text_zero], raw_lines=[line], calibration=_cal())
    assert len(results) == 1
    assert results[0].status == "unverified"
    assert results[0].geometry_id == ""


def test_edge_3_micro_and_zero_length_primitives():
    """Edge 3: Zero-length line or zero-radius circle must not trigger ZeroDivisionError."""
    zero_line = RawLine("l_zero", (100.0, 100.0), (100.0, 100.0))
    zero_circ = RawCircle("c_zero", (200.0, 200.0), 0.0)
    text = RawText("t1", "100", (90.0, 85.0, 110.0, 95.0), rotation_deg=0.0, parsed_value=100.0)

    results = strategy_d_cross_validate([text], raw_lines=[zero_line], raw_circles=[zero_circ], calibration=_cal())
    assert len(results) == 1
    assert results[0].status == "unverified"


def test_edge_4_non_finite_coordinate_nan_inf_safety():
    """Edge 4: NaN and Inf coordinates in geometry or text must fail safe without crashing."""
    nan_line = RawLine("l_nan", (float("nan"), 100.0), (200.0, 100.0))
    inf_line = RawLine("l_inf", (100.0, float("inf")), (200.0, 100.0))
    valid_line = RawLine("l_valid", (100.0, 100.0), (250.0, 100.0))

    text_nan = RawText("t_nan", "150", (float("nan"), 85.0, 160.0, 95.0), rotation_deg=0.0, parsed_value=150.0)
    text_valid = RawText("t_valid", "150", (165.0, 85.0, 185.0, 95.0), rotation_deg=0.0, parsed_value=150.0)

    results = strategy_d_cross_validate(
        [text_nan, text_valid],
        raw_lines=[nan_line, inf_line, valid_line],
        calibration=_cal(),
    )
    assert len(results) == 2
    assert results[0].status == "unverified"
    assert results[1].status == "confirmed"
    assert results[1].geometry_id == "l_valid"


def test_edge_5_extreme_large_scale_coordinates():
    """Edge 5: Extreme coordinates (10^6 px) maintain numerical precision and confirm."""
    offset = 1_000_000.0
    line = RawLine("l_huge", (offset + 100.0, offset + 100.0), (offset + 300.0, offset + 100.0))  # 200px
    text = RawText("t_huge", "200", (offset + 190.0, offset + 85.0, offset + 210.0, offset + 95.0), rotation_deg=0.0, parsed_value=200.0)

    results = strategy_d_cross_validate([text], raw_lines=[line], calibration=_cal())
    assert len(results) == 1
    assert results[0].geometry_id == "l_huge"
    assert results[0].status == "confirmed"


def test_edge_6_negative_dimension_value_handling():
    """Edge 6: Negative parsed values must fail safe to unverified."""
    line = RawLine("l1", (100.0, 100.0), (200.0, 100.0))
    text_neg = RawText("t_neg", "-50", (140.0, 85.0, 160.0, 95.0), rotation_deg=0.0, parsed_value=-50.0)

    results = strategy_d_cross_validate([text_neg], raw_lines=[line], calibration=_cal())
    assert len(results) == 1
    assert results[0].status == "unverified"


def test_perf_7_large_drawing_latency_and_scalability():
    """Perf 7: Dense drawing with 50 texts, 200 lines, 30 circles, 20 arcs."""
    lines = []
    texts = []
    circles = []
    arcs = []

    # Generate 40 horizontal and vertical true dimensions
    for i in range(40):
        y = 100.0 + i * 50.0
        line = RawLine(f"l_{i}", (100.0, y), (300.0, y))  # 200px
        text = RawText(f"t_{i}", "200", (190.0, y - 15.0, 210.0, y - 5.0), rotation_deg=0.0, parsed_value=200.0)
        lines.append(line)
        texts.append(text)

    # Generate 10 circular dimensions
    for i in range(10):
        cx = 500.0 + (i % 5) * 100.0
        cy = 500.0 + (i // 5) * 100.0
        circle = RawCircle(f"c_{i}", (cx, cy), 25.0)  # diam 50
        text = RawText(f"t_circ_{i}", "Ø50", (cx - 10.0, cy - 35.0, cx + 10.0, cy - 25.0), rotation_deg=0.0, parsed_value=50.0, callout_type="diameter")
        circles.append(circle)
        texts.append(text)

    # Add 160 distractor lines
    for i in range(160):
        x = 50.0 + (i % 20) * 40.0
        y = 50.0 + (i // 20) * 100.0
        lines.append(RawLine(f"distractor_l_{i}", (x, y), (x + 30.0, y + 20.0)))

    # Add 20 distractor circles and 20 arcs
    for i in range(20):
        circles.append(RawCircle(f"distractor_c_{i}", (800.0 + i * 20.0, 800.0), 10.0))
        arcs.append(RawArc(f"distractor_a_{i}", (800.0, 800.0 + i * 20.0), 15.0, 0.0, 90.0))

    assert len(texts) == 50
    assert len(lines) == 200
    assert len(circles) == 30
    assert len(arcs) == 20

    # Warm-up run
    strategy_d_cross_validate(texts[:5], raw_lines=lines[:20], calibration=_cal())

    t0 = time.perf_counter()
    results = strategy_d_cross_validate(
        texts,
        raw_lines=lines,
        raw_circles=circles,
        raw_arcs=arcs,
        calibration=_cal(),
    )
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000.0

    assert len(results) == 50
    # All 50 intended dimensions must be confirmed
    confirmed_count = sum(1 for r in results if r.status == "confirmed")
    assert confirmed_count == 50

    # Latency budget: < 40 ms for 50 texts x 250 primitives
    assert latency_ms < 40.0, f"Expected < 40ms, got {latency_ms:.2f}ms"
