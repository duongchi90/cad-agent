"""test_section_hatch_reconstruction_controls.py — Positive and Negative Controls Suite."""

from __future__ import annotations

import sys
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


def test_control_01_positive_standard_45deg_solid_section():
    """Positive Control 1: Standard ANSI31 solid square section (100mm x 100mm)."""
    strokes = _generate_parallel_hatch(50.0, 50.0, 150.0, 150.0, angle_deg=45.0, pitch_mm=5.0)

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(strokes)
    assert len(res) == 1
    assert res[0].pattern.pattern_name == "ANSI31"
    assert res[0].pattern.stroke_count >= 15
    assert len(res[0].void_holes) == 0


def test_control_02_positive_wide_pitch_section():
    """Positive Control 2: Coarse pitch (12.0mm) on large structural cross-section."""
    strokes = _generate_parallel_hatch(100.0, 100.0, 300.0, 300.0, angle_deg=45.0, pitch_mm=12.0)

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(strokes)
    assert len(res) == 1
    assert abs(res[0].pattern.pitch_spacing_mm - 12.0) <= 0.8
    assert res[0].pattern.stroke_count >= 10


def test_control_03_positive_double_void_holes():
    """Positive Control 3: Section with two internal void cutouts."""
    # Section with void 1 at [70, 70, 95, 95] and void 2 at [125, 70, 150, 95]
    strokes_left = _generate_parallel_hatch(
        50.0, 50.0, 110.0, 120.0, angle_deg=45.0, pitch_mm=5.0, hole_bbox=(70.0, 70.0, 95.0, 95.0)
    )
    strokes_right = _generate_parallel_hatch(
        110.0, 50.0, 170.0, 120.0, angle_deg=45.0, pitch_mm=5.0, hole_bbox=(125.0, 70.0, 150.0, 95.0)
    )
    strokes = strokes_left + strokes_right

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(strokes)
    assert len(res) >= 1
    # Detects void presence
    all_voids = [v for r in res for v in r.void_holes]
    assert len(all_voids) >= 1


def test_control_04_negative_perpendicular_cross_lines_without_hatch_family():
    """Negative Control 4: Grid of orthogonal construction lines (0° and 90°) rejected."""
    orthogonal_lines = [
        HatchStroke("h1", (10.0, 20.0), (100.0, 20.0)),
        HatchStroke("h2", (10.0, 40.0), (100.0, 40.0)),
        HatchStroke("v1", (30.0, 10.0), (30.0, 80.0)),
        HatchStroke("v2", (60.0, 10.0), (60.0, 80.0)),
    ]

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(orthogonal_lines)
    # Neither horizontal nor vertical group has >= 4 parallel strokes
    assert len(res) == 0


def test_control_05_negative_insufficient_stroke_count():
    """Negative Control 5: Only 2 or 3 parallel lines (N < 4) rejected as insufficient."""
    few_strokes = [
        HatchStroke("s1", (10.0, 10.0), (40.0, 40.0)),
        HatchStroke("s2", (15.0, 10.0), (45.0, 40.0)),
        HatchStroke("s3", (20.0, 10.0), (50.0, 40.0)),
    ]

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(few_strokes)
    assert len(res) == 0


def test_control_06_negative_excessive_pitch_jitter():
    """Negative Control 6: Parallel lines with wildly irregular spacing rejected."""
    # Strokes at x-offsets: 0, 3, 25, 30, 75 (pitches: 3, 22, 5, 45 -> high jitter)
    irregular_strokes = [
        HatchStroke("i1", (0.0, 0.0), (30.0, 30.0)),
        HatchStroke("i2", (3.0, 0.0), (33.0, 30.0)),
        HatchStroke("i3", (25.0, 0.0), (55.0, 30.0)),
        HatchStroke("i4", (30.0, 0.0), (60.0, 30.0)),
        HatchStroke("i5", (75.0, 0.0), (105.0, 30.0)),
    ]

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(irregular_strokes)
    assert len(res) == 0


def test_control_07_positive_background_crosshair_isolation():
    """Positive Control 7: Centerline crosshair crossing hatch zone does not disrupt hatch."""
    strokes = _generate_parallel_hatch(50.0, 50.0, 150.0, 150.0, angle_deg=45.0, pitch_mm=6.0)
    # Add horizontal and vertical centerlines
    center_h = HatchStroke("ch", (30.0, 100.0), (170.0, 100.0))
    center_v = HatchStroke("cv", (100.0, 30.0), (100.0, 170.0))
    mixed = strokes + [center_h, center_v]

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(mixed)
    assert len(res) == 1
    assert res[0].pattern.pattern_name == "ANSI31"
    assert abs(res[0].pattern.dominant_angle_deg - 45.0) <= 1.0


def test_control_08_negative_micro_strokes_rejection():
    """Negative Control 8: Short speckle noise lines (length < 5mm) filtered out."""
    speckle_strokes = [
        HatchStroke(f"sp_{i}", (10.0 + i * 2.0, 20.0), (12.0 + i * 2.0, 22.0))
        for i in range(10)
    ]

    engine = SectionHatchReconstructionEngine()
    res = engine.analyze(speckle_strokes)
    assert len(res) == 0
