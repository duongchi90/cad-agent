"""test_section_hatch_reconstruction_benchmark.py — Multi-Strategy Benchmark Suite.

Compares:
- Strategy A: Current Production Baseline (cad_agent/fidelity.py _observe_hatch_candidates: 100x100 grid binning)
- Strategy B: Naive Convex Hull over Stroke Endpoints
- Strategy C: Raster Morphological Bounding Box
- Strategy D: Angular & Pitch Consensus Clustering, Exact Boundary Loop & Void Island Reconstruction Oracle

Across 8 discriminating benchmark scenarios.
"""

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
    run_strategy_a,
    run_strategy_b,
    run_strategy_c,
)
from test_causal_red_section_hatch_reconstruction import _generate_parallel_hatch


def test_benchmark_scenario_01_standard_rectangular_section_ansi31():
    """Scenario 1: Standard 45° ANSI31 rectangular section (120mm x 80mm)."""
    strokes = _generate_parallel_hatch(50.0, 50.0, 170.0, 130.0, angle_deg=45.0, pitch_mm=5.0)

    # Strategy A: Fractures into 2+ grid boxes
    res_a = run_strategy_a(strokes)
    assert len(res_a) >= 2

    # Strategy B: Convex hull succeeds on convex rectangle
    res_b = run_strategy_b(strokes)
    assert res_b is not None
    assert res_b.outer_boundary.area >= 8000.0

    # Strategy D: Reconstructs exact boundary, identifies ANSI31 pattern, accurate pitch
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(strokes)
    assert len(res_d) == 1
    assert res_d[0].pattern.pattern_name == "ANSI31"
    assert abs(res_d[0].pattern.dominant_angle_deg - 45.0) <= 1.0
    assert abs(res_d[0].pattern.pitch_spacing_mm - 5.0) <= 0.5
    assert len(res_d[0].void_holes) == 0


def test_benchmark_scenario_02_section_with_central_bored_hole():
    """Scenario 2: Flange cutaway section with central bored hole (void)."""
    strokes = _generate_parallel_hatch(
        40.0, 40.0, 160.0, 160.0, angle_deg=45.0, pitch_mm=6.0, hole_bbox=(80.0, 80.0, 120.0, 120.0)
    )

    # Strategy B: Convex hull completely drops the hole (0 void holes)
    res_b = run_strategy_b(strokes)
    assert res_b is not None
    assert len(res_b.void_holes) == 0

    # Strategy D: Detects outer boundary AND inner void hole
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(strokes)
    assert len(res_d) == 1
    assert len(res_d[0].void_holes) == 1
    void_loop = res_d[0].void_holes[0]
    assert void_loop.loop_type == "INNER_VOID"
    assert void_loop.area >= 800.0  # (40 x 40 = 1600 mm^2 approx)


def test_benchmark_scenario_03_stepped_shaft_longitudinal_cutaway():
    """Scenario 3: Stepped shaft cross-section with 2 continuous steps."""
    # Step 1: [50, 120] x [50, 110] (H=60, W=70)
    # Step 2: [120, 200] x [60, 100] (H=40, W=80)
    s1 = _generate_parallel_hatch(50.0, 50.0, 120.0, 110.0, angle_deg=45.0, pitch_mm=5.0)
    s2 = _generate_parallel_hatch(120.0, 60.0, 200.0, 100.0, angle_deg=45.0, pitch_mm=5.0)
    strokes = s1 + s2

    # Strategy D: Unifies both steps under single continuous hatch family
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(strokes)
    assert len(res_d) == 1
    assert res_d[0].pattern.pattern_name == "ANSI31"
    outer = res_d[0].outer_boundary
    assert outer.bbox[0] <= 55.0
    assert outer.bbox[2] >= 195.0


def test_benchmark_scenario_04_steep_angle_60deg_hatch():
    """Scenario 4: Steep angle (60°) material hatching."""
    strokes = _generate_parallel_hatch(50.0, 50.0, 180.0, 140.0, angle_deg=60.0, pitch_mm=7.0)

    # Strategy D: Accurately identifies 60° orientation and 7mm pitch
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(strokes)
    assert len(res_d) == 1
    assert abs(res_d[0].pattern.dominant_angle_deg - 60.0) <= 1.5
    assert abs(res_d[0].pattern.pitch_spacing_mm - 7.0) <= 0.6


def test_benchmark_scenario_05_fine_pitch_cross_section():
    """Scenario 5: Fine pitch (2.5mm) dense mechanical hatching."""
    strokes = _generate_parallel_hatch(50.0, 50.0, 150.0, 120.0, angle_deg=45.0, pitch_mm=2.5)
    assert len(strokes) >= 30  # High density

    # Strategy D: Handles high density without degrading accuracy
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(strokes)
    assert len(res_d) == 1
    assert abs(res_d[0].pattern.pitch_spacing_mm - 2.5) <= 0.3
    assert res_d[0].pattern.stroke_count >= 30


def test_benchmark_scenario_06_concave_l_bracket_section():
    """Scenario 6: Concave L-bracket cross section."""
    s_base = _generate_parallel_hatch(50.0, 50.0, 150.0, 100.0, angle_deg=45.0, pitch_mm=5.0)
    s_upright = _generate_parallel_hatch(50.0, 100.0, 100.0, 150.0, angle_deg=45.0, pitch_mm=5.0)
    strokes = s_base + s_upright

    # Strategy B: Convex hull bridges concave corner, inflating area by ~2,000 mm^2
    res_b = run_strategy_b(strokes)
    assert res_b.outer_boundary.area >= 8500.0

    # Strategy D: Preserves concave perimeter with accurate area
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(strokes)
    assert len(res_d) == 1
    assert res_d[0].outer_boundary.area <= 7600.0
    assert len(res_d[0].outer_boundary.vertices) == 6


def test_benchmark_scenario_07_dual_separated_flange_ribs():
    """Scenario 7: Dual separated flange ribs on the same part."""
    # Rib 1 at X in [50, 100]
    rib1 = _generate_parallel_hatch(50.0, 50.0, 100.0, 120.0, angle_deg=45.0, pitch_mm=5.0)
    # Rib 2 at X in [180, 230] (80mm unhatched web gap between them)
    rib2 = _generate_parallel_hatch(180.0, 50.0, 230.0, 120.0, angle_deg=45.0, pitch_mm=5.0)

    # Strategy B merges both into 1 giant convex hull spanning [50, 230]
    res_b = run_strategy_b(rib1 + rib2)
    assert res_b is not None

    # Strategy D extracts strokes cleanly
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(rib1 + rib2)
    assert len(res_d) >= 1
    assert res_d[0].pattern.dominant_angle_deg >= 40.0


def test_benchmark_scenario_08_dense_diagonal_text_annotation_distractor():
    """Scenario 8: Irregular diagonal notes and text annotation leader strokes."""
    # Diagonal text strokes with dx >= 10 and dy >= 10 (triggers naive Strategy A count >= 5)
    text_strokes = [
        HatchStroke("t_x1", (10.0, 20.0), (25.0, 45.0)),   # dx=15, dy=25 (~59 deg)
        HatchStroke("t_x2", (10.0, 45.0), (25.0, 20.0)),   # dx=15, dy=-25 (~121 deg)
        HatchStroke("t_m1", (30.0, 20.0), (45.0, 50.0)),   # dx=15, dy=30 (~63 deg)
        HatchStroke("t_m2", (45.0, 50.0), (60.0, 20.0)),   # dx=15, dy=-30 (~117 deg)
        HatchStroke("t_w1", (60.0, 50.0), (75.0, 20.0)),   # dx=15, dy=-30 (~117 deg)
        HatchStroke("t_w2", (75.0, 20.0), (90.0, 50.0)),   # dx=15, dy=30 (~63 deg)
    ]

    # Strategy A accepts text strokes as hatch candidate (count >= 5 in cell 0,0)
    res_a = run_strategy_a(text_strokes)
    assert len(res_a) >= 1

    # Strategy D rejects irregular text strokes
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(text_strokes)
    assert len(res_d) == 0
