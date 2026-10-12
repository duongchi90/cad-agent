"""
test_constraint_pruning_benchmark.py — Multi-Strategy Benchmark Suite for Constraint Pruning.

Epic: TRANSITIVE_AND_CONFLICTING_CONSTRAINT_PRUNING_V1
Role: ANTIGRAVITY_RESEARCH

Benchmarks Strategies A, B, C, D across 8 mechanical engineering scenarios:
1. Scenario 1: Multi-Step Shaft Bore Concentricity (5 circles, K5=10 constraints)
2. Scenario 2: Frame Edge Parallel Intra-Group Perpendicular Noise Contradiction
3. Scenario 3: Segment Collinear Subsumption of Parallel Constraint
4. Scenario 4: Bearing Bushing Concentric vs Tangent Contradiction
5. Scenario 5: Transitive Parallel Chain (4 parallel lines)
6. Scenario 6: Transitive Equal Length Set (5 equal length lines)
7. Scenario 7: Cross-Group Perpendiculars (4 horiz x 2 vert = 8 perpendiculars)
8. Scenario 8: Complex Mixed Mechanical Assembly
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

from semantic_ir_lib.constraint_pruning import prune_constraints as run_strategy_a_prune
from semantic_ir_lib.models import Constraint

from constraint_pruning_engine import (
    prune_constraints_strategy_d,
    run_strategy_b_prune,
    run_strategy_c_prune,
)


def _c(type_: str, a: str, b: str, confidence: float = 0.9, cid: str | None = None) -> Constraint:
    c = Constraint(type=type_, primitive_ids=[a, b], confidence=confidence, tolerance={})
    if cid:
        c.id = cid
    return c


def test_scenario_1_five_circle_concentric_bore():
    """Scenario 1: 5 concentric circles (K5 complete graph = 10 constraints)."""
    # 5 circles: C1, C2, C3, C4, C5
    circles = ["C1", "C2", "C3", "C4", "C5"]
    constraints = []
    idx = 1
    for i in range(len(circles)):
        for j in range(i + 1, len(circles)):
            constraints.append(_c("concentric", circles[i], circles[j], 0.95 - 0.01 * idx, f"c-{idx}"))
            idx += 1

    res_a = run_strategy_a_prune(constraints)
    res_b = run_strategy_b_prune(constraints)
    res_c = run_strategy_c_prune(constraints)
    res_d = prune_constraints_strategy_d(constraints)

    # Strategy A keeps all 10 (fails to prune transitive concentric)
    assert len(res_a.kept) == 10
    # Strategy C and D reduce to spanning tree: N-1 = 4 edges
    assert len(res_c.kept) == 4
    assert len(res_d.kept) == 4
    assert len(res_d.dropped_transitive_redundant) == 6


def test_scenario_2_intra_group_perpendicular_noise():
    """Scenario 2: Intra-group perpendicular contradiction within 4 parallel lines."""
    # 4 parallel lines: H1, H2, H3, H4
    parallels = [
        _c("parallel", "H1", "H2", 0.95),
        _c("parallel", "H2", "H3", 0.94),
        _c("parallel", "H3", "H4", 0.93),
    ]
    # Noise: H1 and H4 also marked perpendicular (0.75)
    noise_perp = _c("perpendicular", "H1", "H4", 0.75, "noise-perp")

    all_c = parallels + [noise_perp]

    res_a = run_strategy_a_prune(all_c)
    res_d = prune_constraints_strategy_d(all_c)

    # Strategy A fails: keeps perpendicular inside the parallel group!
    assert any(c.id == "noise-perp" for c in res_a.kept)
    # Strategy D drops the impossible perpendicular contradiction
    assert not any(c.id == "noise-perp" for c in res_d.kept)
    assert "noise-perp" in res_d.dropped_contradictory


def test_scenario_3_collinear_subsumption_of_parallel():
    """Scenario 3: Collinear constraint on same pair as parallel."""
    c_col = _c("collinear", "S1", "S2", 0.95, "c-col")
    c_par = _c("parallel", "S1", "S2", 0.90, "c-par")

    res_a = run_strategy_a_prune([c_col, c_par])
    res_d = prune_constraints_strategy_d([c_col, c_par])

    # Strategy A keeps both
    assert len(res_a.kept) == 2
    # Strategy D keeps only collinear, dropping parallel as subsumed
    assert len(res_d.kept) == 1
    assert res_d.kept[0].id == "c-col"
    assert "c-par" in res_d.dropped_subsumed


def test_scenario_4_bushing_concentric_vs_tangent():
    """Scenario 4: Concentric vs tangent conflict on same circle pair."""
    c_con = _c("concentric", "B1", "B2", 0.96, "c-con")
    c_tan = _c("tangent", "B1", "B2", 0.72, "c-tan")

    res_a = run_strategy_a_prune([c_con, c_tan])
    res_d = prune_constraints_strategy_d([c_con, c_tan])

    # Strategy A keeps both impossible constraints
    assert len(res_a.kept) == 2
    # Strategy D drops tangent as contradictory
    assert len(res_d.kept) == 1
    assert res_d.kept[0].id == "c-con"
    assert "c-tan" in res_d.dropped_contradictory


def test_scenario_5_transitive_parallel_chain():
    """Scenario 5: 4 parallel lines forming full cycle graph."""
    # 4 lines: 6 pairwise parallel constraints
    lines = ["P1", "P2", "P3", "P4"]
    constraints = []
    idx = 1
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            constraints.append(_c("parallel", lines[i], lines[j], 0.95 - 0.01 * idx, f"p-{idx}"))
            idx += 1

    res_a = run_strategy_a_prune(constraints)
    res_d = prune_constraints_strategy_d(constraints)

    # Both Strategy A and D should reduce 6 edges to 3 spanning tree edges
    assert len(res_a.kept) == 3
    assert len(res_d.kept) == 3


def test_scenario_6_transitive_equal_length_set():
    """Scenario 6: 5 equal length segments."""
    # 5 segments: 10 pairwise constraints
    segs = ["E1", "E2", "E3", "E4", "E5"]
    constraints = []
    idx = 1
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            constraints.append(_c("equal_length", segs[i], segs[j], 0.95 - 0.01 * idx, f"e-{idx}"))
            idx += 1

    res_a = run_strategy_a_prune(constraints)
    res_d = prune_constraints_strategy_d(constraints)

    # Both Strategy A and D reduce 10 edges to 4 spanning tree edges
    assert len(res_a.kept) == 4
    assert len(res_d.kept) == 4


def test_scenario_7_cross_group_perpendicular_reduction():
    """Scenario 7: 4 horizontal x 2 vertical lines -> 8 perpendicular constraints."""
    parallels = [
        _c("parallel", "H1", "H2", 0.95),
        _c("parallel", "H2", "H3", 0.94),
        _c("parallel", "H3", "H4", 0.93),
        _c("parallel", "V1", "V2", 0.95),
    ]
    perps = [
        _c("perpendicular", h, v, 0.90 - 0.01 * i, f"perp-{h}-{v}")
        for i, (h, v) in enumerate(
            [("H1", "V1"), ("H1", "V2"), ("H2", "V1"), ("H2", "V2"),
             ("H3", "V1"), ("H3", "V2"), ("H4", "V1"), ("H4", "V2")]
        )
    ]

    res_a = run_strategy_a_prune(parallels + perps)
    res_d = prune_constraints_strategy_d(parallels + perps)

    # Both A and D keep exactly 1 representative perpendicular + 4 parallel spanning edges = 5 total
    assert len(res_a.kept) == 5
    assert len(res_d.kept) == 5
    kept_perp_d = [c for c in res_d.kept if c.type == "perpendicular"]
    assert len(kept_perp_d) == 1
    assert kept_perp_d[0].id == "perp-H1-V1"


def test_scenario_8_complex_mechanical_assembly():
    """Scenario 8: Complex assembly combining concentric bore, frame, collinear segments, and noise."""
    # 3 concentric circles (3 constraints -> 2 spanning tree)
    c12 = _c("concentric", "C1", "C2", 0.95, "c-12")
    c23 = _c("concentric", "C2", "C3", 0.94, "c-23")
    c13 = _c("concentric", "C1", "C3", 0.90, "c-13")

    # 2 collinear segments with duplicate parallel (subsumption)
    col = _c("collinear", "L1", "L2", 0.96, "col-12")
    par_dup = _c("parallel", "L1", "L2", 0.91, "par-dup")

    # Frame lines: L1 parallel to L3, L3 parallel to L4 (3 parallel spanning tree)
    par_13 = _c("parallel", "L1", "L3", 0.93, "par-13")
    par_34 = _c("parallel", "L3", "L4", 0.92, "par-34")

    # Intra-group noise perpendicular between L1 and L4 (contradiction)
    perp_noise = _c("perpendicular", "L1", "L4", 0.70, "perp-noise")

    # Valid perpendicular between L1 and V1
    perp_valid = _c("perpendicular", "L1", "V1", 0.89, "perp-valid")

    all_constraints = [c12, c23, c13, col, par_dup, par_13, par_34, perp_noise, perp_valid]

    res_a = run_strategy_a_prune(all_constraints)
    res_d = prune_constraints_strategy_d(all_constraints)

    # Strategy A keeps: c12, c23, c13 (all 3 concentric!), col, par_dup (both!), par_13, par_34, perp_noise (contradiction!), perp_valid -> 9 constraints!
    assert len(res_a.kept) == 9

    # Strategy D keeps:
    # 2 concentric (c12, c23)
    # 1 collinear (col)
    # 2 parallel (par_13, par_34)
    # 1 valid perpendicular (perp_valid)
    # Total = 6 clean constraints!
    assert len(res_d.kept) == 6
    kept_ids_d = {c.id for c in res_d.kept}
    assert kept_ids_d == {"c-12", "c-23", "col-12", "par-13", "par-34", "perp-valid"}
    assert "c-13" in res_d.dropped_transitive_redundant
    assert "par-dup" in res_d.dropped_subsumed
    assert "perp-noise" in res_d.dropped_contradictory
