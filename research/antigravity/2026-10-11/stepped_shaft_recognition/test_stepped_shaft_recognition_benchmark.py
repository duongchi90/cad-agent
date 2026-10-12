"""test_stepped_shaft_recognition_benchmark.py — Empirical benchmark comparing Strategies A-D.

Scenarios:
1. Standard 2-step vertical shaft (positive baseline)
2. Standard 2-step horizontal shaft
3. 3-step symmetrical drive shaft (small-large-small, 12 lines)
4. 4-step progressive spindle shaft (16 lines)
5. Stepped shaft with 0 transverse holes (solid drive shaft)
6. Stepped shaft with 2 transverse cross-holes (pin holes)
7. Stepped shaft with lead-in chamfers at both ends (10 lines)
8. 30-degree rotated angled stepped shaft
"""

from __future__ import annotations

import sys
from pathlib import Path
import math
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
    run_strategy_a,
    run_strategy_b,
    run_strategy_c,
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
        source_document=SourceDocument("bench.png", 0, 1000, 1000),
        calibration=Calibration("mm", 1.0, (0.0, 0.0), "verified", "note", "verified"),
        primitives=prims,
    )


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def test_benchmark_scenario_01_standard_vertical_two_step() -> None:
    """Scenario 1: Standard vertical 2-step shaft with 1 transverse hole."""
    pts = [
        (0.0, 0.0),
        (100.0, 0.0),
        (100.0, 20.0),
        (140.0, 20.0),
        (140.0, 80.0),
        (100.0, 80.0),
        (100.0, 100.0),
        (0.0, 100.0),
        (0.0, 0.0),
    ]
    lines = [
        _line(f"l{i+1}", pts[i], pts[i+1]) for i in range(len(pts) - 1)
    ]
    circles = [_circle("c1", (40.0, 50.0), 5.0)]
    doc = _doc(lines + circles)

    res_a = run_strategy_a(doc)
    res_b = run_strategy_b(doc)
    res_c = run_strategy_c(doc)
    res_d = run_strategy_d(doc)

    assert res_a.success is True
    assert res_b.success is True
    assert res_c.success is True
    assert res_d.success is True

    prof_d = res_d.profiles[0]
    assert prof_d.step_count == 2
    assert len(prof_d.transverse_holes) == 1
    assert prof_d.total_length_mm == pytest.approx(140.0, abs=0.1)


def test_benchmark_scenario_02_standard_horizontal_two_step() -> None:
    """Scenario 2: Standard horizontal 2-step shaft with 1 transverse hole."""
    # Rotated 90 degrees
    lines = [
        _line("l1", (0, -20), (0, 20)),
        _line("l2", (0, 20), (100, 20)),
        _line("l3", (100, 20), (100, 50)),
        _line("l4", (100, 50), (200, 50)),
        _line("l5", (200, 50), (200, -50)),
        _line("l6", (200, -50), (100, -50)),
        _line("l7", (100, -50), (100, -20)),
        _line("l8", (100, -20), (0, -20)),
    ]
    circles = [_circle("c1", (150, 0), 10.0)]
    doc = _doc(lines + circles)

    res_a = run_strategy_a(doc)
    res_b = run_strategy_b(doc)
    res_c = run_strategy_c(doc)
    res_d = run_strategy_d(doc)

    assert res_a.success is False  # Baseline fails on horizontal
    assert res_b.success is True
    assert res_c.success is True
    assert res_d.success is True

    prof_d = res_d.profiles[0]
    assert prof_d.step_count == 2
    assert prof_d.total_length_mm == pytest.approx(200.0, abs=0.1)
    assert len(prof_d.transverse_holes) == 1


def test_benchmark_scenario_03_three_step_symmetrical_shaft() -> None:
    """Scenario 3: 3-step symmetrical drive shaft (small, large, small; 12 lines)."""
    # Step 1: x in [0, 50], y in [-15, 15] (dia 30)
    # Step 2: x in [50, 150], y in [-25, 25] (dia 50)
    # Step 3: x in [150, 200], y in [-15, 15] (dia 30)
    lines = [
        _line("l1", (0, -15), (0, 15)),      # left cap
        _line("l2", (0, 15), (50, 15)),      # top step 1
        _line("l3", (50, 15), (50, 25)),     # rise 1
        _line("l4", (50, 25), (150, 25)),    # top step 2
        _line("l5", (150, 25), (150, 15)),   # fall 2
        _line("l6", (150, 15), (200, 15)),   # top step 3
        _line("l7", (200, 15), (200, -15)),  # right cap
        _line("l8", (200, -15), (150, -15)), # bot step 3
        _line("l9", (150, -15), (150, -25)), # rise 2 bot
        _line("l10", (150, -25), (50, -25)), # bot step 2
        _line("l11", (50, -25), (50, -15)),  # fall 1 bot
        _line("l12", (50, -15), (0, -15)),   # bot step 1
    ]
    circles = [_circle("c1", (100, 0), 8.0)]
    doc = _doc(lines + circles)

    res_a = run_strategy_a(doc)
    res_b = run_strategy_b(doc)
    res_c = run_strategy_c(doc)
    res_d = run_strategy_d(doc)

    assert res_a.success is False  # 12 lines != 8 lines
    assert res_c.success is True
    assert res_d.success is True

    prof_d = res_d.profiles[0]
    assert prof_d.step_count == 3
    assert prof_d.total_length_mm == pytest.approx(200.0, abs=0.1)


def test_benchmark_scenario_04_four_step_progressive_spindle() -> None:
    """Scenario 4: 4-step progressive spindle shaft (16 lines)."""
    # 4 progressive steps along X
    lines = [
        _line("l1", (0, -10), (0, 10)),      # cap
        _line("l2", (0, 10), (40, 10)),      # s1 top
        _line("l3", (40, 10), (40, 15)),     # r1
        _line("l4", (40, 15), (80, 15)),     # s2 top
        _line("l5", (80, 15), (80, 20)),     # r2
        _line("l6", (80, 20), (120, 20)),    # s3 top
        _line("l7", (120, 20), (120, 25)),   # r3
        _line("l8", (120, 25), (160, 25)),   # s4 top
        _line("l9", (160, 25), (160, -25)),  # right cap
        _line("l10", (160, -25), (120, -25)),
        _line("l11", (120, -25), (120, -20)),
        _line("l12", (120, -20), (80, -20)),
        _line("l13", (80, -20), (80, -15)),
        _line("l14", (80, -15), (40, -15)),
        _line("l15", (40, -15), (40, -10)),
        _line("l16", (40, -10), (0, -10)),
    ]
    doc = _doc(lines)

    res_a = run_strategy_a(doc)
    res_c = run_strategy_c(doc)
    res_d = run_strategy_d(doc)

    assert res_a.success is False
    assert res_c.success is True
    assert res_d.success is True

    prof_d = res_d.profiles[0]
    assert prof_d.step_count == 4
    assert prof_d.total_length_mm == pytest.approx(160.0, abs=0.1)


def test_benchmark_scenario_05_solid_shaft_zero_holes() -> None:
    """Scenario 5: Stepped shaft with 0 transverse holes (solid shaft)."""
    lines = [
        _line("l1", (0, -20), (0, 20)),
        _line("l2", (0, 20), (100, 20)),
        _line("l3", (100, 20), (100, 50)),
        _line("l4", (100, 50), (200, 50)),
        _line("l5", (200, 50), (200, -50)),
        _line("l6", (200, -50), (100, -50)),
        _line("l7", (100, -50), (100, -20)),
        _line("l8", (100, -20), (0, -20)),
    ]
    doc = _doc(lines)

    res_a = run_strategy_a(doc)
    res_c = run_strategy_c(doc)
    res_d = run_strategy_d(doc)

    assert res_a.success is False  # 0 circles != 1 circle
    assert res_c.success is True
    assert res_d.success is True

    prof_d = res_d.profiles[0]
    assert len(prof_d.transverse_holes) == 0
    assert prof_d.step_count == 2


def test_benchmark_scenario_06_shaft_with_two_transverse_holes() -> None:
    """Scenario 6: Stepped shaft with 2 transverse cross-holes."""
    lines = [
        _line("l1", (0, -20), (0, 20)),
        _line("l2", (0, 20), (100, 20)),
        _line("l3", (100, 20), (100, 50)),
        _line("l4", (100, 50), (200, 50)),
        _line("l5", (200, 50), (200, -50)),
        _line("l6", (200, -50), (100, -50)),
        _line("l7", (100, -50), (100, -20)),
        _line("l8", (100, -20), (0, -20)),
    ]
    circles = [
        _circle("c1", (50, 0), 6.0),
        _circle("c2", (150, 0), 8.0),
    ]
    doc = _doc(lines + circles)

    res_a = run_strategy_a(doc)
    res_c = run_strategy_c(doc)
    res_d = run_strategy_d(doc)

    assert res_a.success is False  # 2 circles != 1 circle
    assert res_c.success is True
    assert res_d.success is True

    prof_d = res_d.profiles[0]
    assert len(prof_d.transverse_holes) == 2
    assert {h.hole_id for h in prof_d.transverse_holes} == {"c1", "c2"}


def test_benchmark_scenario_07_shaft_with_lead_in_chamfers() -> None:
    """Scenario 7: Stepped shaft with 2 lead-in chamfers at the end caps (10 lines total)."""
    # 5x5 mm 45-deg chamfer at left end: (0, 15) -> (5, 20) and (5, -20) -> (0, -15)
    lines = [
        _line("l1", (0, -15), (0, 15)),      # shortened left cap
        _line("ch1", (0, 15), (5, 20)),      # 45 deg chamfer top-left
        _line("l2", (5, 20), (100, 20)),     # top step 1
        _line("l3", (100, 20), (100, 50)),   # riser
        _line("l4", (100, 50), (200, 50)),   # top step 2
        _line("l5", (200, 50), (200, -50)),  # right cap
        _line("l6", (200, -50), (100, -50)), # bot step 2
        _line("l7", (100, -50), (100, -20)), # fall
        _line("l8", (100, -20), (5, -20)),   # bot step 1
        _line("ch2", (5, -20), (0, -15)),    # 45 deg chamfer bot-left
    ]
    doc = _doc(lines)

    res_a = run_strategy_a(doc)
    res_c = run_strategy_c(doc)
    res_d = run_strategy_d(doc, endpoint_tolerance_mm=1.5)

    assert res_a.success is False  # 10 lines != 8
    assert res_c.success is False  # Strategy C rejects diagonal lines
    assert res_d.success is True

    prof_d = res_d.profiles[0]
    assert prof_d.step_count == 2
    assert len(prof_d.chamfers) == 2


def test_benchmark_scenario_08_rotated_angled_shaft() -> None:
    """Scenario 8: Stepped shaft rotated at 30 degrees to the horizontal."""
    # Rotate standard 2-step shaft by 30 degrees
    angle = math.radians(30.0)
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def rot(p: tuple[float, float]) -> tuple[float, float]:
        return (p[0] * cos_a - p[1] * sin_a, p[0] * sin_a + p[1] * cos_a)

    base_pts = [
        ("l1", (0, -20), (0, 20)),
        ("l2", (0, 20), (100, 20)),
        ("l3", (100, 20), (100, 40)),
        ("l4", (100, 40), (200, 40)),
        ("l5", (200, 40), (200, -40)),
        ("l6", (200, -40), (100, -40)),
        ("l7", (100, -40), (100, -20)),
        ("l8", (100, -20), (0, -20)),
    ]
    lines = [_line(pid, rot(p1), rot(p2)) for pid, p1, p2 in base_pts]
    circles = [_circle("c1", rot((150, 0)), 8.0)]
    doc = _doc(lines + circles)

    res_a = run_strategy_a(doc)
    res_c = run_strategy_c(doc)
    res_d = run_strategy_d(doc)

    assert res_a.success is False  # Not vertical
    assert res_c.success is False  # Not H or V
    assert res_d.success is True

    prof_d = res_d.profiles[0]
    assert prof_d.step_count == 2
    assert prof_d.axis_angle_deg == pytest.approx(30.0, abs=1.5)
    assert len(prof_d.transverse_holes) == 1
