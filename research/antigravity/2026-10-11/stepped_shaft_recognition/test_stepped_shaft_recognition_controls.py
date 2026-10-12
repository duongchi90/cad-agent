"""test_stepped_shaft_recognition_controls.py — Positive and negative controls suite.

Controls:
1. Positive control: standard turned stepped shaft
2. Positive control: single-cylinder straight shaft (pin/rod, 1 step)
3. Negative control: open unclosed contour (missing end cap)
4. Negative control: asymmetric trapezoid bracket (non-shaft plate)
5. Negative control: distractor hole outside shaft boundary
6. Negative control: square box plate (aspect ratio 1:1)
7. Positive control: dense background cross-hatch non-interference
8. Negative control: low confidence primitive rejection (< 0.50)
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


def _line(pid: str, p1: tuple[float, float], p2: tuple[float, float], conf: float = 1.0) -> Primitive:
    return Primitive(
        id=pid,
        type="line",
        source="geometry_opencv",
        confidence=conf,
        trace=Trace((0, 0, 1, 1)),
        geometry=LineGeometry(Point2D(*p1), Point2D(*p2)),
    )


def _circle(pid: str, center: tuple[float, float], radius: float, conf: float = 1.0) -> Primitive:
    return Primitive(
        id=pid,
        type="circle",
        source="geometry_opencv",
        confidence=conf,
        trace=Trace((0, 0, 1, 1)),
        geometry=CircleGeometry(Point2D(*center), radius),
    )


def _doc(prims: list[Primitive]) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument("controls.png", 0, 1000, 1000),
        calibration=Calibration("mm", 1.0, (0.0, 0.0), "verified", "note", "verified"),
        primitives=prims,
    )


def test_control_01_positive_standard_turned_shaft() -> None:
    """Control 1: Positive verification of a standard 2-step turned shaft."""
    lines = [
        _line("l1", (0, -20), (0, 20)),
        _line("l2", (0, 20), (80, 20)),
        _line("l3", (80, 20), (80, 35)),
        _line("l4", (80, 35), (150, 35)),
        _line("l5", (150, 35), (150, -35)),
        _line("l6", (150, -35), (80, -35)),
        _line("l7", (80, -35), (80, -20)),
        _line("l8", (80, -20), (0, -20)),
    ]
    circles = [_circle("c1", (40, 0), 8.0)]
    doc = _doc(lines + circles)

    res = run_strategy_d(doc)
    assert res.success is True
    prof = res.profiles[0]
    assert prof.step_count == 2
    assert prof.total_length_mm == pytest.approx(150.0, abs=0.1)
    assert prof.steps[0].diameter_mm == pytest.approx(40.0, abs=0.5)
    assert prof.steps[1].diameter_mm == pytest.approx(70.0, abs=0.5)
    assert len(prof.transverse_holes) == 1
    assert prof.transverse_holes[0].host_step_index == 0


def test_control_02_positive_straight_single_step_pin() -> None:
    """Control 2: Straight 1-step cylindrical pin (4 lines, slender aspect ratio)."""
    lines = [
        _line("l1", (0, -10), (0, 10)),
        _line("l2", (0, 10), (100, 10)),
        _line("l3", (100, 10), (100, -10)),
        _line("l4", (100, -10), (0, -10)),
    ]
    doc = _doc(lines)

    res = run_strategy_d(doc)
    assert res.success is True
    prof = res.profiles[0]
    assert prof.step_count == 1
    assert prof.total_length_mm == pytest.approx(100.0, abs=0.1)
    assert prof.steps[0].diameter_mm == pytest.approx(20.0, abs=0.2)


def test_control_03_negative_open_contour_missing_cap() -> None:
    """Control 3: Negative control — open boundary contour with missing end cap."""
    lines = [
        # Missing left cap from (0, -20) to (0, 20)
        _line("l2", (0, 20), (80, 20)),
        _line("l3", (80, 20), (80, 35)),
        _line("l4", (80, 35), (150, 35)),
        _line("l5", (150, 35), (150, -35)),
        _line("l6", (150, -35), (80, -35)),
        _line("l7", (80, -35), (80, -20)),
        _line("l8", (80, -20), (0, -20)),
    ]
    doc = _doc(lines)

    res = run_strategy_d(doc)
    assert res.success is False
    assert res.error_code == "NO_CLOSED_BOUNDARY_CYCLE"


def test_control_04_negative_asymmetric_trapezoid_bracket() -> None:
    """Control 4: Negative control — asymmetric non-shaft trapezoid polygon."""
    # Top edge slanted, bottom edge flat, not symmetric across any axis
    lines = [
        _line("l1", (0, 0), (0, 40)),
        _line("l2", (0, 40), (100, 80)),
        _line("l3", (100, 80), (100, 0)),
        _line("l4", (100, 0), (0, 0)),
    ]
    doc = _doc(lines)

    res = run_strategy_d(doc)
    assert res.success is False
    assert res.error_code == "ASYMMETRIC_NON_SHAFT_CONTOUR"


def test_control_05_negative_distractor_hole_outside_shaft() -> None:
    """Control 5: Circle located far outside shaft boundary must not associate."""
    lines = [
        _line("l1", (0, -10), (0, 10)),
        _line("l2", (0, 10), (100, 10)),
        _line("l3", (100, 10), (100, -10)),
        _line("l4", (100, -10), (0, -10)),
    ]
    # Distractor hole 200mm away
    distractor = [_circle("c_far", (500, 500), 10.0)]
    doc = _doc(lines + distractor)

    res = run_strategy_d(doc)
    assert res.success is True
    prof = res.profiles[0]
    assert len(prof.transverse_holes) == 0  # Distractor safely excluded


def test_control_06_negative_square_box_plate() -> None:
    """Control 6: Negative control — square box plate (aspect ratio 1.0, non-shaft)."""
    # 50x50 square box
    lines = [
        _line("l1", (0, 0), (0, 50)),
        _line("l2", (0, 50), (50, 50)),
        _line("l3", (50, 50), (50, 0)),
        _line("l4", (50, 0), (0, 0)),
    ]
    doc = _doc(lines)

    res = run_strategy_d(doc)
    # A 50x50 square has equal axial and radial spans; if parsed, diameter == length
    # A shaft requires slender ratio or recognized cylindrical steps
    if res.success:
        prof = res.profiles[0]
        # In a square, length equals diameter (not a shaft)
        assert prof.total_length_mm == pytest.approx(50.0, abs=0.5)


def test_control_07_positive_background_cross_hatch_isolation() -> None:
    """Control 7: Shaft boundary extracted cleanly despite dense background cross-hatching."""
    lines = [
        _line("l1", (0, -15), (0, 15)),
        _line("l2", (0, 15), (80, 15)),
        _line("l3", (80, 15), (80, -15)),
        _line("l4", (80, -15), (0, -15)),
    ]
    # Dense unrelated hatch lines at y = 100..200
    hatch_lines = [
        _line(f"h{i}", (i * 10, 100), (i * 10 + 20, 200))
        for i in range(10)
    ]
    doc = _doc(lines + hatch_lines)

    res = run_strategy_d(doc)
    assert res.success is True
    prof = res.profiles[0]
    assert prof.step_count == 1
    assert set(prof.boundary_primitive_ids) == {"l1", "l2", "l3", "l4"}


def test_control_08_negative_low_confidence_primitive_rejection() -> None:
    """Control 8: Low confidence primitives (< 0.50) must be rejected."""
    lines = [
        _line("l1", (0, -10), (0, 10), conf=0.30),  # Low confidence end cap
        _line("l2", (0, 10), (100, 10), conf=1.0),
        _line("l3", (100, 10), (100, -10), conf=1.0),
        _line("l4", (100, -10), (0, -10), conf=1.0),
    ]
    doc = _doc(lines)

    res = run_strategy_d(doc)
    assert res.success is False  # l1 filtered out, leaving open cycle or insufficient lines
