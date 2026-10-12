"""test_causal_red_stepped_shaft_recognition.py — Causal RED reproduction suite.

Demonstrates the 5 deterministic failure modes in current production
cad_agent/mechanical_pilot.py (_phase4_profile_bindings).
"""

from __future__ import annotations

import pytest
from cad_agent.mechanical_pilot import _phase4_profile_bindings
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


def _make_line(pid: str, start: tuple[float, float], end: tuple[float, float]) -> Primitive:
    return Primitive(
        id=pid,
        type="line",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace((0, 0, 1, 1)),
        geometry=LineGeometry(Point2D(*start), Point2D(*end)),
    )


def _make_circle(pid: str, center: tuple[float, float], radius: float) -> Primitive:
    return Primitive(
        id=pid,
        type="circle",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace((0, 0, 1, 1)),
        geometry=CircleGeometry(Point2D(*center), radius),
    )


def _make_doc(lines: list[Primitive], circles: list[Primitive]) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument("test.png", 0, 1000, 1000),
        calibration=Calibration("mm", 1.0, (0.0, 0.0), "verified", "note", "verified"),
        primitives=lines + circles,
    )


def test_red_01_horizontal_stepped_shaft_fails() -> None:
    """Mode 1: Horizontal orientation (standard drafting convention) fails with
    PILOT_SHAFT_PROFILE_AMBIGUOUS because expected_x/y hardcodes vertical shaft coordinates.
    """
    # 8-line horizontal stepped shaft with 1 circle
    lines = [
        _make_line("l1", (0, -20), (0, 20)),
        _make_line("l2", (0, 20), (100, 20)),
        _make_line("l3", (100, 20), (100, 50)),
        _make_line("l4", (100, 50), (200, 50)),
        _make_line("l5", (200, 50), (200, -50)),
        _make_line("l6", (200, -50), (100, -50)),
        _make_line("l7", (100, -50), (100, -20)),
        _make_line("l8", (100, -20), (0, -20)),
    ]
    circles = [_make_circle("c1", (150, 0), 10.0)]
    doc = _make_doc(lines, circles)

    with pytest.raises(ValueError) as excinfo:
        _phase4_profile_bindings(doc)
    assert "PILOT_SHAFT_PROFILE_AMBIGUOUS" in str(excinfo.value)


def test_red_02_three_step_shaft_fails_primitive_count() -> None:
    """Mode 2: 3-step shaft (12 lines) fails with PILOT_SHAFT_PROFILE_INVALID
    because current code enforces strict len(lines) == 8.
    """
    lines = [
        _make_line(f"l{i}", (0, i * 20), (20, i * 20))
        for i in range(12)
    ]
    circles = [_make_circle("c1", (10, 10), 5.0)]
    doc = _make_doc(lines, circles)

    with pytest.raises(ValueError) as excinfo:
        _phase4_profile_bindings(doc)
    assert "PILOT_SHAFT_PROFILE_INVALID" in str(excinfo.value)


def test_red_03_zero_transverse_holes_fails() -> None:
    """Mode 3: Solid stepped shaft with 0 transverse holes fails with PILOT_SHAFT_PROFILE_INVALID
    because current code enforces strict len(circles) == 1.
    """
    lines = [
        _make_line(f"l{i}", (0, i * 20), (20, i * 20))
        for i in range(8)
    ]
    doc = _make_doc(lines, [])

    with pytest.raises(ValueError) as excinfo:
        _phase4_profile_bindings(doc)
    assert "PILOT_SHAFT_PROFILE_INVALID" in str(excinfo.value)


def test_red_04_multiple_transverse_holes_fails() -> None:
    """Mode 4: Stepped shaft with 2 transverse holes fails with PILOT_SHAFT_PROFILE_INVALID
    because current code enforces strict len(circles) == 1.
    """
    lines = [
        _make_line(f"l{i}", (0, i * 20), (20, i * 20))
        for i in range(8)
    ]
    circles = [
        _make_circle("c1", (10, 10), 5.0),
        _make_circle("c2", (10, 50), 5.0),
    ]
    doc = _make_doc(lines, circles)

    with pytest.raises(ValueError) as excinfo:
        _phase4_profile_bindings(doc)
    assert "PILOT_SHAFT_PROFILE_INVALID" in str(excinfo.value)


def test_red_05_chamfered_stepped_shaft_fails() -> None:
    """Mode 5: Stepped shaft with lead-in chamfers (10 lines total) fails with PILOT_SHAFT_PROFILE_INVALID
    because len(lines) != 8 and chamfers are non-axis-aligned.
    """
    lines = [
        _make_line(f"l{i}", (0, i * 20), (20, i * 20))
        for i in range(10)
    ]
    circles = [_make_circle("c1", (10, 10), 5.0)]
    doc = _make_doc(lines, circles)

    with pytest.raises(ValueError) as excinfo:
        _phase4_profile_bindings(doc)
    assert "PILOT_SHAFT_PROFILE_INVALID" in str(excinfo.value)
