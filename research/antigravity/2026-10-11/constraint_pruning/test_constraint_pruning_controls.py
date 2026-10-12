"""
test_constraint_pruning_controls.py — Positive Fixtures and Strong Negative Controls for Constraint Pruning.

Epic: TRANSITIVE_AND_CONFLICTING_CONSTRAINT_PRUNING_V1
Role: ANTIGRAVITY_RESEARCH
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

from semantic_ir_lib.models import Constraint
from constraint_pruning_engine import prune_constraints_strategy_d


def _c(type_: str, a: str, b: str, confidence: float = 0.9, cid: str | None = None) -> Constraint:
    c = Constraint(type=type_, primitive_ids=[a, b], confidence=confidence, tolerance={})
    if cid:
        c.id = cid
    return c


# ---------------------------------------------------------------------------
# Positive Controls
# ---------------------------------------------------------------------------

def test_positive_1_flange_bore_with_tangents():
    """Positive 1: Flange bore with 3 concentric circles and 2 tangent keyway lines."""
    # 3 concentric circles: C1, C2, C3 (3 pairwise -> 2 spanning tree)
    c12 = _c("concentric", "C1", "C2", 0.95, "c-12")
    c23 = _c("concentric", "C2", "C3", 0.94, "c-23")
    c13 = _c("concentric", "C1", "C3", 0.89, "c-13")

    # 2 distinct keyway lines tangent to C1 (L1 tangent C1, L2 tangent C1)
    tan1 = _c("tangent", "L1", "C1", 0.92, "tan-1")
    tan2 = _c("tangent", "L2", "C1", 0.91, "tan-2")

    res = prune_constraints_strategy_d([c12, c23, c13, tan1, tan2])
    assert len(res.kept) == 4
    kept_ids = {c.id for c in res.kept}
    assert kept_ids == {"c-12", "c-23", "tan-1", "tan-2"}
    assert "c-13" in res.dropped_transitive_redundant


def test_positive_2_closed_rectangular_frame():
    """Positive 2: 4-segment closed rectangle (2 parallel pairs, 4 coincident corners, 1 perp)."""
    # H1 // H2, V1 // V2
    par_h = _c("parallel", "H1", "H2", 0.95, "par-h")
    par_v = _c("parallel", "V1", "V2", 0.95, "par-v")

    # 4 corners
    coinc = [
        _c("coincident_endpoint", "H1", "V1", 0.92, "c-c1"),
        _c("coincident_endpoint", "V1", "H2", 0.91, "c-c2"),
        _c("coincident_endpoint", "H2", "V2", 0.90, "c-c3"),
        _c("coincident_endpoint", "V2", "H1", 0.89, "c-c4"),
    ]

    # Perpendicular between H1 and V1
    perp = _c("perpendicular", "H1", "V1", 0.94, "perp-hv")

    res = prune_constraints_strategy_d([par_h, par_v, perp] + coinc)
    assert len(res.kept) == 7
    kept_ids = {c.id for c in res.kept}
    assert kept_ids == {"par-h", "par-v", "perp-hv", "c-c1", "c-c2", "c-c3", "c-c4"}


def test_positive_3_slotted_plate():
    """Positive 3: Slotted plate (2 parallel lines, 2 tangent arcs, 2 concentric bolt holes)."""
    par_lines = _c("parallel", "L1", "L2", 0.95, "par-slot")
    tan_arc1 = _c("tangent", "L1", "A1", 0.92, "tan-a1")
    tan_arc2 = _c("tangent", "L2", "A2", 0.91, "tan-a2")
    con_holes = _c("concentric", "H1", "H2", 0.90, "con-holes")

    res = prune_constraints_strategy_d([par_lines, tan_arc1, tan_arc2, con_holes])
    assert len(res.kept) == 4
    assert len(res.dropped_contradictory) == 0
    assert len(res.dropped_transitive_redundant) == 0


def test_positive_4_multi_segment_collinear_split():
    """Positive 4: 3 collinear segments (S1, S2, S3) with 3 pairwise collinear constraints."""
    c12 = _c("collinear", "S1", "S2", 0.95, "col-12")
    c23 = _c("collinear", "S2", "S3", 0.93, "col-23")
    c13 = _c("collinear", "S1", "S3", 0.88, "col-13")

    res = prune_constraints_strategy_d([c12, c23, c13])
    assert len(res.kept) == 2
    kept_ids = {c.id for c in res.kept}
    assert kept_ids == {"col-12", "col-23"}
    assert "col-13" in res.dropped_transitive_redundant


# ---------------------------------------------------------------------------
# Strong Negative Controls
# ---------------------------------------------------------------------------

def test_negative_5_low_confidence_noise():
    """Negative 5: Entirely low-confidence noise field (< 0.6) is rejected."""
    noise = [
        _c("parallel", "N1", "N2", 0.45, "n1"),
        _c("perpendicular", "N2", "N3", 0.55, "n2"),
        _c("concentric", "C1", "C2", 0.30, "n3"),
        _c("collinear", "S1", "S2", 0.59, "n4"),
    ]
    res = prune_constraints_strategy_d(noise, min_confidence=0.6)
    assert len(res.kept) == 0
    assert len(res.dropped_low_confidence) == 4


def test_negative_6_self_perpendicular_in_triad():
    """Negative 6: 3 lines in a parallel triad (P1//P2, P2//P3). Noise marks P1 perp P3."""
    p12 = _c("parallel", "P1", "P2", 0.95, "p12")
    p23 = _c("parallel", "P2", "P3", 0.94, "p23")
    noise_perp = _c("perpendicular", "P1", "P3", 0.72, "perp-noise")

    res = prune_constraints_strategy_d([p12, p23, noise_perp])
    assert len(res.kept) == 2
    assert "perp-noise" in res.dropped_contradictory
    kept_ids = {c.id for c in res.kept}
    assert kept_ids == {"p12", "p23"}


def test_negative_7_concentric_tangent_clash():
    """Negative 7: Concentric circles clash with tangent noise."""
    c12 = _c("concentric", "C1", "C2", 0.95, "con-12")
    t12 = _c("tangent", "C1", "C2", 0.65, "tan-12")

    res = prune_constraints_strategy_d([c12, t12])
    assert len(res.kept) == 1
    assert res.kept[0].id == "con-12"
    assert "tan-12" in res.dropped_contradictory


def test_negative_8_dense_false_perpendicular_matrix():
    """Negative 8: 3 parallel horizontal lines and 3 parallel vertical lines."""
    # 3 horizontal: H1//H2, H2//H3 (2 spanning edges)
    # 3 vertical: V1//V2, V2//V3 (2 spanning edges)
    # 9 pairwise perpendiculars (every Hi perp Vj)
    h_parallels = [_c("parallel", "H1", "H2", 0.95, "h12"), _c("parallel", "H2", "H3", 0.94, "h23")]
    v_parallels = [_c("parallel", "V1", "V2", 0.95, "v12"), _c("parallel", "V2", "V3", 0.94, "v23")]

    perps = [
        _c("perpendicular", f"H{i}", f"V{j}", 0.90 - 0.01 * (i * 3 + j), f"p-h{i}-v{j}")
        for i in [1, 2, 3] for j in [1, 2, 3]
    ]

    res = prune_constraints_strategy_d(h_parallels + v_parallels + perps)
    # Exactly 2 H-parallels + 2 V-parallels + 1 representative perpendicular = 5 kept!
    assert len(res.kept) == 5
    assert len(res.dropped_group_redundant) == 8
    kept_perp = [c for c in res.kept if c.type == "perpendicular"]
    assert len(kept_perp) == 1
    assert kept_perp[0].id == "p-h1-v1"
