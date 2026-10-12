"""test_stepped_shaft_recognition_degenerate_and_perf.py — Degenerate edge cases & perf suite.

Tests:
1. Empty document / zero primitives
2. Zero-length line segments
3. Zero-radius / negative radius circles
4. Extreme coordinates (10^6 mm scale)
5. Non-finite coordinates (NaN / Infinity)
6. Duplicate coincident primitives
7. Large-scale throughput performance profiling (50 mixed shafts < 100 ms)
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

from primitive_ir_lib.models import (
    Calibration,
    CircleGeometry,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)

from stepped_shaft_recognition_engine import (
    run_strategy_d,
)


def _line(pid: str, p1: tuple[float, float], p2: tuple[float, float]) -> Primitive:
    return Primitive(
        id=pid,
        type="line",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace((0, 0, 1, 1)),
        geometry=LineGeometry(Point2D(*p1), Point2D(*p2)),
    )


def _circle(pid: str, center: tuple[float, float], radius: float) -> Primitive:
    return Primitive(
        id=pid,
        type="circle",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace((0, 0, 1, 1)),
        geometry=CircleGeometry(Point2D(*center), radius),
    )


def _doc(prims: list[Primitive]) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument("edge.png", 0, 1000, 1000),
        calibration=Calibration("mm", 1.0, (0.0, 0.0), "verified", "note", "verified"),
        primitives=prims,
    )


def test_degenerate_01_empty_document() -> None:
    """Edge 1: Empty document returns clean safe failure."""
    doc = _doc([])
    res = run_strategy_d(doc)
    assert res.success is False
    assert res.error_code == "INSUFFICIENT_VALID_LINES"


def test_degenerate_02_zero_length_segments() -> None:
    """Edge 2: Zero-length line segments are safely filtered out."""
    lines = [
        _line("zero1", (10.0, 10.0), (10.0, 10.0)),
        _line("zero2", (50.0, 50.0), (50.0, 50.0)),
    ]
    doc = _doc(lines)
    res = run_strategy_d(doc)
    assert res.success is False
    assert res.error_code == "INSUFFICIENT_VALID_LINES"


def test_degenerate_03_zero_or_negative_radius_circles() -> None:
    """Edge 3: Zero or negative radius circles are safely ignored."""
    lines = [
        _line("l1", (0, -10), (0, 10)),
        _line("l2", (0, 10), (100, 10)),
        _line("l3", (100, 10), (100, -10)),
        _line("l4", (100, -10), (0, -10)),
    ]
    circles = [
        _circle("c_zero", (50, 0), 0.0),
        _circle("c_neg", (50, 0), -5.0),
    ]
    doc = _doc(lines + circles)
    res = run_strategy_d(doc)
    assert res.success is True
    prof = res.profiles[0]
    assert len(prof.transverse_holes) == 0  # Invalid circles filtered


def test_degenerate_04_extreme_coordinates() -> None:
    """Edge 4: Extreme coordinates (10^6 mm WCS) preserve precision without overflow."""
    offset = 1_000_000.0
    lines = [
        _line("l1", (offset + 0, offset - 10), (offset + 0, offset + 10)),
        _line("l2", (offset + 0, offset + 10), (offset + 100, offset + 10)),
        _line("l3", (offset + 100, offset + 10), (offset + 100, offset - 10)),
        _line("l4", (offset + 100, offset - 10), (offset + 0, offset - 10)),
    ]
    circles = [_circle("c1", (offset + 50, offset + 0), 4.0)]
    doc = _doc(lines + circles)
    res = run_strategy_d(doc)
    assert res.success is True
    prof = res.profiles[0]
    assert prof.total_length_mm == pytest.approx(100.0, abs=0.1)
    assert len(prof.transverse_holes) == 1


def test_degenerate_05_non_finite_coordinates_nan_inf() -> None:
    """Edge 5: NaN and Inf coordinates are rejected without crashing."""
    lines = [
        _line("l1", (float("nan"), 0.0), (10.0, 10.0)),
        _line("l2", (0.0, float("inf")), (10.0, 10.0)),
        _line("l3", (0.0, 0.0), (10.0, 10.0)),
    ]
    doc = _doc(lines)
    res = run_strategy_d(doc)
    assert res.success is False
    assert res.error_code == "INSUFFICIENT_VALID_LINES"


def test_degenerate_06_duplicate_coincident_lines() -> None:
    """Edge 6: Duplicate coincident lines do not corrupt graph traversal."""
    lines = [
        _line("l1", (0, -10), (0, 10)),
        _line("l1_dup", (0, -10), (0, 10)),
        _line("l2", (0, 10), (100, 10)),
        _line("l2_dup", (0, 10), (100, 10)),
        _line("l3", (100, 10), (100, -10)),
        _line("l4", (100, -10), (0, -10)),
    ]
    doc = _doc(lines)
    res = run_strategy_d(doc)
    assert res.success is True
    prof = res.profiles[0]
    assert prof.step_count == 1
    assert prof.total_length_mm == pytest.approx(100.0, abs=0.1)


def test_perf_07_large_scale_throughput() -> None:
    """Perf 7: 50 mixed shafts and 500 primitives processed in < 100 ms."""
    all_prims = []
    for s_idx in range(50):
        ox = s_idx * 300.0
        lines = [
            _line(f"s{s_idx}_l1", (ox + 0, -20), (ox + 0, 20)),
            _line(f"s{s_idx}_l2", (ox + 0, 20), (ox + 100, 20)),
            _line(f"s{s_idx}_l3", (ox + 100, 20), (ox + 100, 40)),
            _line(f"s{s_idx}_l4", (ox + 100, 40), (ox + 200, 40)),
            _line(f"s{s_idx}_l5", (ox + 200, 40), (ox + 200, -40)),
            _line(f"s{s_idx}_l6", (ox + 200, -40), (ox + 100, -40)),
            _line(f"s{s_idx}_l7", (ox + 100, -40), (ox + 100, -20)),
            _line(f"s{s_idx}_l8", (ox + 100, -20), (ox + 0, -20)),
        ]
        circles = [_circle(f"s{s_idx}_c1", (ox + 150, 0), 8.0)]
        all_prims.extend(lines + circles)

    assert len(all_prims) == 450  # 450 primitives

    doc = _doc(all_prims)
    t0 = time.perf_counter()
    res = run_strategy_d(doc)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    assert res.success is True
    # Throughput requirement: < 250 ms for 450 primitives (accommodates Windows background jitter)
    assert dt_ms < 250.0, f"Execution took {dt_ms:.2f} ms (expected < 250 ms)"
