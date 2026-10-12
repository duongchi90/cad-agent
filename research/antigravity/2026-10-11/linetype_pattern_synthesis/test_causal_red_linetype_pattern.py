"""Causal RED tests demonstrating current production deficiencies in linetype pattern detection.

Exercises:
1. cad_agent/fidelity.py: strictly filters out vertical dashed lines (abs(start.y - end.y) > tol).
2. cad_agent/fidelity.py: strictly filters out inclined 45° centerlines.
3. cad_agent/fidelity.py: lacks automated run_fidelity_linetype_observations generator.
4. cad_agent/fidelity.py: retains 10 individual dash strokes as separate disjoint entities with 0 stroke synthesis.
5. cad_agent/fidelity.py: has 0 cadence analysis to distinguish CENTER from DASHED from raw geometry.
"""

import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from primitive_ir_lib.models import Point2D, LineGeometry, Primitive, Trace
from cad_agent import fidelity
from linetype_pattern_engine import (
    LinetypeKind,
    synthesize_linetypes_strategy_a,
    extract_linetypes_strategy_d,
)


def _make_line(id_: str, x0: float, y0: float, x1: float, y1: float) -> Primitive:
    return Primitive(
        id=id_,
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


def test_red_01_vertical_dashed_line_rejected_by_production():
    """RED 1: Production run_fidelity_linetype_reconstruct checks abs(start.y - end.y) <= tol.
    A vertical dashed line (x = 50.0, dy = 10.0mm) is 100% skipped, leaving it unmerged and unclassified."""
    v_stroke1 = _make_line("vs1", 50.0, 10.0, 50.0, 14.0)
    v_stroke2 = _make_line("vs2", 50.0, 16.0, 50.0, 20.0)
    v_stroke3 = _make_line("vs3", 50.0, 22.0, 50.0, 26.0)

    # Strategy A (production baseline)
    res_a = synthesize_linetypes_strategy_a([v_stroke1, v_stroke2, v_stroke3])
    # 0 lines synthesized because vertical lines are rejected!
    assert len(res_a.synthesized_lines) == 0
    assert len(res_a.unmerged_primitives) == 3


def test_red_02_inclined_45deg_centerline_rejected_by_production():
    """RED 2: Production strictly filters out inclined non-horizontal centerlines (e.g. 45° angle)."""
    # 45° line strokes
    inc1 = _make_line("inc1", 10.0, 10.0, 18.0, 18.0)
    inc2 = _make_line("inc2", 20.0, 20.0, 22.0, 22.0)
    inc3 = _make_line("inc3", 24.0, 24.0, 32.0, 32.0)

    res_a = synthesize_linetypes_strategy_a([inc1, inc2, inc3])
    assert len(res_a.synthesized_lines) == 0
    assert len(res_a.unmerged_primitives) == 3


def test_red_03_production_fidelity_lacks_automated_linetype_observer():
    """RED 3: cad_agent/fidelity defines observers for hatch, text, table, and dimensions,
    but has NO run_fidelity_linetype_observations function!"""
    assert hasattr(fidelity, "run_fidelity_hatch_observations")
    assert hasattr(fidelity, "run_fidelity_text_observations")
    assert hasattr(fidelity, "run_fidelity_dimension_observations")
    # Linetype observer is completely absent from production!
    assert not hasattr(fidelity, "run_fidelity_linetype_observations")


def test_red_04_collinear_dash_strokes_not_synthesized():
    """RED 4: In production, 8 dash strokes of a horizontal hidden line remain 8 fragmented lines.
    Strategy A does not merge strokes (stroke_count == 1 for individual fragments, 0 continuous line)."""
    strokes = []
    for i in range(8):
        x_start = 10.0 + i * 6.0
        strokes.append(_make_line(f"h_stroke_{i}", x_start, 50.0, x_start + 4.0, 50.0))

    mock_obs = {
        "patterns": [{"axis": "horizontal", "coordinate_px": 50.0, "suggested_linetype": "DASHED"}]
    }
    res_a = synthesize_linetypes_strategy_a(strokes, mock_observation=mock_obs)
    # Strategy A tags each fragment individually, emitting 8 separate lines instead of 1 continuous line!
    assert len(res_a.synthesized_lines) == 8
    assert all(item.stroke_count == 1 for item in res_a.synthesized_lines)
    # None of them spans the full 46mm extent
    assert max(item.total_length_mm for item in res_a.synthesized_lines) == 4.0


def test_red_05_production_cannot_distinguish_centerline_from_hidden_without_mock():
    """RED 5: Without an external mock JSON specifying 'suggested_linetype',
    production cannot inspect stroke length cadence to distinguish CENTER from DASHED."""
    # Alternating long-short-long strokes (centerline: 12mm, 2mm, 12mm, 2mm, 12mm)
    s1 = _make_line("c1", 10.0, 50.0, 22.0, 50.0)
    s2 = _make_line("c2", 24.0, 50.0, 26.0, 50.0)
    s3 = _make_line("c3", 28.0, 50.0, 40.0, 50.0)

    # Strategy A with no mock JSON observation
    res_a = synthesize_linetypes_strategy_a([s1, s2, s3], mock_observation=None)
    # Completely misses the centerline, leaving all 3 as unmerged/continuous!
    assert len(res_a.synthesized_lines) == 0
    assert len(res_a.unmerged_primitives) == 3
