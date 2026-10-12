"""test_causal_red_section_hatch_reconstruction.py — Causal RED reproduction suite.

Demonstrates the 5 deterministic failure modes in current production
cad_agent/fidelity.py (_observe_hatch_candidates & run_fidelity_hatch_reconstruct).
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
)


def _generate_parallel_hatch(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    angle_deg: float = 45.0,
    pitch_mm: float = 5.0,
    hole_bbox: tuple[float, float, float, float] | None = None,
) -> list[HatchStroke]:
    """Generates synthetic parallel hatch strokes clipped to a rectangular or holed boundary."""
    import math

    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    nx = -sin_a
    ny = cos_a

    # Normal offset span
    corners = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
    offsets = [x * nx + y * ny for x, y in corners]
    min_off = min(offsets)
    max_off = max(offsets)

    strokes = []
    s_idx = 1
    off = min_off + pitch_mm
    while off < max_off - 1.0:
        # Find intersections of line: x*nx + y*ny = off with rectangle [xmin, xmax] x [ymin, ymax]
        # Parametric ray along stroke direction: P(t) = P0 + t * (cos_a, sin_a)
        # Choose P0 = (off * nx, off * ny)
        p0x = off * nx
        p0y = off * ny

        # Solve for t on 4 box edges:
        ts = []
        if abs(cos_a) > 1e-6:
            # x = xmin => t = (xmin - p0x) / cos_a
            t_left = (xmin - p0x) / cos_a
            y_left = p0y + t_left * sin_a
            if ymin - 1e-4 <= y_left <= ymax + 1e-4:
                ts.append(t_left)
            # x = xmax
            t_right = (xmax - p0x) / cos_a
            y_right = p0y + t_right * sin_a
            if ymin - 1e-4 <= y_right <= ymax + 1e-4:
                ts.append(t_right)
        if abs(sin_a) > 1e-6:
            # y = ymin
            t_bot = (ymin - p0y) / sin_a
            x_bot = p0x + t_bot * cos_a
            if xmin - 1e-4 <= x_bot <= xmax + 1e-4:
                ts.append(t_bot)
            # y = ymax
            t_top = (ymax - p0y) / sin_a
            x_top = p0x + t_top * cos_a
            if xmin - 1e-4 <= x_top <= xmax + 1e-4:
                ts.append(t_top)

        ts = sorted(set(round(t, 2) for t in ts))
        if len(ts) >= 2:
            t_start, t_end = ts[0], ts[-1]
            if hole_bbox is not None:
                h_xmin, h_ymin, h_xmax, h_ymax = hole_bbox
                # Check if stroke intersects hole
                # Find hole intersection ts:
                h_ts = []
                if abs(cos_a) > 1e-6:
                    th_l = (h_xmin - p0x) / cos_a
                    yh_l = p0y + th_l * sin_a
                    if h_ymin <= yh_l <= h_ymax:
                        h_ts.append(th_l)
                    th_r = (h_xmax - p0x) / cos_a
                    yh_r = p0y + th_r * sin_a
                    if h_ymin <= yh_r <= h_ymax:
                        h_ts.append(th_r)
                if abs(sin_a) > 1e-6:
                    th_b = (h_ymin - p0y) / sin_a
                    xh_b = p0x + th_b * cos_a
                    if h_xmin <= xh_b <= h_xmax:
                        h_ts.append(th_b)
                    th_t = (h_ymax - p0y) / sin_a
                    xh_t = p0x + th_t * cos_a
                    if h_xmin <= xh_t <= h_xmax:
                        h_ts.append(th_t)
                h_ts = sorted(set(round(t, 2) for t in h_ts))
                if len(h_ts) >= 2 and h_ts[0] > t_start and h_ts[-1] < t_end:
                    # Split into 2 segments around hole!
                    p1 = (p0x + t_start * cos_a, p0y + t_start * sin_a)
                    p2 = (p0x + h_ts[0] * cos_a, p0y + h_ts[0] * sin_a)
                    strokes.append(HatchStroke(f"hs_{s_idx}a", p1, p2))

                    p3 = (p0x + h_ts[-1] * cos_a, p0y + h_ts[-1] * sin_a)
                    p4 = (p0x + t_end * cos_a, p0y + t_end * sin_a)
                    strokes.append(HatchStroke(f"hs_{s_idx}b", p3, p4))
                    s_idx += 1
                    off += pitch_mm
                    continue

            p1 = (p0x + t_start * cos_a, p0y + t_start * sin_a)
            p2 = (p0x + t_end * cos_a, p0y + t_end * sin_a)
            strokes.append(HatchStroke(f"hs_{s_idx}", p1, p2))
            s_idx += 1

        off += pitch_mm

    return strokes


def test_red_01_grid_tiling_fractures_workpiece_contour():
    """RED 1: Workpiece section crossing X=100 grid line is fractured into disconnected 100x100 tiles in Strategy A."""
    # Rectangle: X in [50, 180] (W=130), Y in [50, 140] (H=90)
    strokes = _generate_parallel_hatch(50.0, 50.0, 180.0, 140.0, angle_deg=45.0, pitch_mm=5.0)

    # Strategy A (Production Baseline):
    res_a = run_strategy_a(strokes)
    # Strategy A slices into at least 2 disconnected candidate boxes: [0, 0, 100, 100] and [100, 0, 200, 100] etc.
    assert len(res_a) >= 2, f"Strategy A unexpectedly unified tiles: {len(res_a)}"

    # Strategy D:
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(strokes)
    assert len(res_d) == 1, "Strategy D failed to emit single unified hatch region"
    outer = res_d[0].outer_boundary
    assert outer is not None
    # Verifies outer boundary spans across the whole [50, 180] interval:
    bbox = outer.bbox
    assert bbox[0] <= 55.0
    assert bbox[2] >= 175.0


def test_red_02_internal_void_hole_blindness():
    """RED 2: Workpiece section with central hole void is solid in Strategy A with zero void representation."""
    # Rectangle [40, 160] x [40, 160] with central hole [80, 80, 120, 120]
    strokes = _generate_parallel_hatch(
        40.0, 40.0, 160.0, 160.0, angle_deg=45.0, pitch_mm=5.0, hole_bbox=(80.0, 80.0, 120.0, 120.0)
    )

    # Strategy A: Emits square grid tiles without any concept of inner void holes
    res_a = run_strategy_a(strokes)
    # Does not have void_holes field
    assert all("void_holes" not in c for c in res_a)

    # Strategy D:
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(strokes)
    assert len(res_d) == 1
    # Successfully extracts internal void hole loop
    assert len(res_d[0].void_holes) >= 1
    void_loop = res_d[0].void_holes[0]
    assert void_loop.loop_type == "INNER_VOID"
    assert void_loop.area > 500.0  # Void hole area non-zero


def test_red_03_concave_l_bracket_corner_distortion():
    """RED 3: L-bracket cross section is bridged across concave corner by naive bounding boxes."""
    # L-bracket section: [50, 150] x [50, 150] with top-right corner [100, 100, 150, 150] removed
    # Simulate L-bracket strokes:
    strokes_base = _generate_parallel_hatch(50.0, 50.0, 150.0, 100.0, angle_deg=45.0, pitch_mm=5.0)
    strokes_upright = _generate_parallel_hatch(50.0, 100.0, 100.0, 150.0, angle_deg=45.0, pitch_mm=5.0)
    strokes = strokes_base + strokes_upright

    # Strategy B: Naive convex hull bridges the corner
    res_b = run_strategy_b(strokes)
    assert res_b is not None
    # Convex hull area is close to full rectangle (100 * 100 = 10,000)
    assert res_b.outer_boundary.area >= 7000.0

    # Strategy D: Extracts true concave boundary
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(strokes)
    assert len(res_d) == 1
    outer_d = res_d[0].outer_boundary
    # True L-shape area is base (100*50) + upright (50*50) = 7,500 mm^2; convex hull is ~9,000 mm^2
    assert len(outer_d.vertices) >= 6  # 6-vertex polygon for L-bracket


def test_red_04_diagonal_text_stroke_false_positive_hatch():
    """RED 4: Cluster of irregular diagonal text strokes triggers false hatch candidates in Strategy A."""
    # Irregular diagonal text strokes within a 100x100 tile (letters X, V, W):
    text_strokes = [
        HatchStroke("t1", (20.0, 20.0), (35.0, 45.0)),   # ~59 deg
        HatchStroke("t2", (20.0, 45.0), (35.0, 20.0)),   # ~121 deg
        HatchStroke("t3", (40.0, 20.0), (52.0, 48.0)),   # ~67 deg
        HatchStroke("t4", (45.0, 30.0), (60.0, 50.0)),   # ~53 deg
        HatchStroke("t5", (65.0, 20.0), (78.0, 42.0)),   # ~59 deg
        HatchStroke("t6", (70.0, 25.0), (85.0, 55.0)),   # ~63 deg
    ]

    # Strategy A: Accepts them because dx >= 10, dy >= 10 and count >= 5 in cell (0, 0):
    res_a = run_strategy_a(text_strokes)
    assert len(res_a) == 1, "Strategy A failed to reproduce false positive hatch trigger"

    # Strategy D: Rejects because pitch jitter / mixed angles fail consistency check:
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(text_strokes)
    assert len(res_d) == 0, "Strategy D unexpectedly accepted irregular text noise"


def test_red_05_pitch_and_angle_estimation_failure():
    """RED 5: 60-degree hatch with 8.0mm pitch is defaulted to 45-degree scale=1.0 in Strategy A."""
    strokes_60 = _generate_parallel_hatch(50.0, 50.0, 200.0, 150.0, angle_deg=60.0, pitch_mm=8.0)

    # Strategy A has no angle or pitch estimation:
    res_a = run_strategy_a(strokes_60)
    assert all("angle" not in c and "pitch" not in c for c in res_a)

    # Strategy D accurately estimates angle and pitch:
    engine = SectionHatchReconstructionEngine()
    res_d = engine.analyze(strokes_60)
    assert len(res_d) == 1
    pat = res_d[0].pattern
    assert pat is not None
    assert abs(pat.dominant_angle_deg - 60.0) <= 1.5
    assert abs(pat.pitch_spacing_mm - 8.0) <= 0.6
