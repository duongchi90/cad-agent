"""
test_causal_red_constraint_pruning.py — Public Causal RED for Transitive and Conflicting Constraint Pruning.

Proves 5 concrete failure modes in production Strategy A (semantic_ir_lib/constraint_pruning.py):
RED-1: Concentric constraints are excluded from _TRANSITIVE_TYPES, keeping redundant cycles in 3 concentric circles.
RED-2: Intra-group perpendicular contradiction (ga == gb) is preserved, outputting mutually contradictory parallel and perpendicular constraints.
RED-3: Collinear-parallel subsumption is ignored, retaining redundant parallel constraints when collinear already exists.
RED-4: Concentric-tangent mutual exclusion contradiction is preserved, outputting geometrically impossible simultaneous concentric and tangent constraints.
RED-5: 4-circle concentric clique retains all 6 pairwise constraints instead of a 3-edge spanning tree.
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

from constraint_pruning_engine import prune_constraints_strategy_d


def _c(type_: str, a: str, b: str, confidence: float = 0.9, cid: str | None = None) -> Constraint:
    c = Constraint(type=type_, primitive_ids=[a, b], confidence=confidence, tolerance={})
    if cid:
        c.id = cid
    return c


def test_red_1_concentric_cycle_redundancy():
    """RED-1: Concentric cycle redundancy.

    3 concentric circles (A, B, C) generate pairwise:
    (A, B, 0.95), (B, C, 0.90), (A, C, 0.85).
    Strategy A retains all 3 (drops 0 transitive redundant).
    Strategy D retains spanning tree (2 constraints) and drops (A, C).
    """
    ab = _c("concentric", "A", "B", confidence=0.95, cid="c-ab")
    bc = _c("concentric", "B", "C", confidence=0.90, cid="c-bc")
    ac = _c("concentric", "A", "C", confidence=0.85, cid="c-ac")

    res_a = run_strategy_a_prune([ab, bc, ac])
    # Strategy A flaw: concentric not in _TRANSITIVE_TYPES -> keeps all 3!
    assert len(res_a.kept) == 3, "Production Strategy A retains all 3 redundant concentric constraints"
    assert len(res_a.dropped_transitive_redundant) == 0

    res_d = prune_constraints_strategy_d([ab, bc, ac])
    # Strategy D fix: treats concentric as transitive, keeps 2 spanning tree edges
    assert len(res_d.kept) == 2
    assert "c-ac" in res_d.dropped_transitive_redundant
    kept_ids = {c.id for c in res_d.kept}
    assert kept_ids == {"c-ab", "c-bc"}


def test_red_2_intra_group_perpendicular_contradiction():
    """RED-2: Intra-group perpendicular contradiction.

    Line L1 and L2 are parallel (conf=0.95). Noise generates perpendicular between L1 and L2 (conf=0.80).
    Strategy A keeps BOTH parallel and perpendicular!
    Strategy D drops the contradictory perpendicular constraint.
    """
    par = _c("parallel", "L1", "L2", confidence=0.95, cid="c-par")
    perp = _c("perpendicular", "L1", "L2", confidence=0.80, cid="c-perp")

    res_a = run_strategy_a_prune([par, perp])
    # Strategy A flaw: keeps perpendicular because pair_key=(G, G) was not previously seen!
    kept_types_a = {c.type for c in res_a.kept}
    assert "parallel" in kept_types_a and "perpendicular" in kept_types_a, (
        "Production Strategy A retains mutually contradictory parallel AND perpendicular on the same pair"
    )

    res_d = prune_constraints_strategy_d([par, perp])
    # Strategy D fix: recognizes contradiction, keeps higher-confidence parallel and drops perp
    kept_types_d = {c.type for c in res_d.kept}
    assert kept_types_d == {"parallel"}
    assert "c-perp" in res_d.dropped_contradictory


def test_red_3_collinear_parallel_subsumption():
    """RED-3: Collinear-parallel subsumption redundancy.

    Line L1 and L2 are detected as collinear (conf=0.95) AND parallel (conf=0.90).
    Collinear strictly subsumes parallel.
    Strategy A retains both collinear and parallel.
    Strategy D drops parallel as subsumed.
    """
    col = _c("collinear", "L1", "L2", confidence=0.95, cid="c-col")
    par = _c("parallel", "L1", "L2", confidence=0.90, cid="c-par")

    res_a = run_strategy_a_prune([col, par])
    # Strategy A flaw: retains both collinear and parallel on same pair
    assert len(res_a.kept) == 2, "Production Strategy A retains redundant parallel when collinear is present"

    res_d = prune_constraints_strategy_d([col, par])
    # Strategy D fix: drops parallel as subsumed by collinear
    assert len(res_d.kept) == 1
    assert res_d.kept[0].type == "collinear"
    assert "c-par" in res_d.dropped_subsumed


def test_red_4_concentric_tangent_mutual_exclusion():
    """RED-4: Concentric-tangent mutual exclusion contradiction.

    Two circles C1 and C2 cannot be simultaneously concentric and tangent (unless radii equal, i.e. identical).
    Noisy detection emits concentric (conf=0.92) and tangent (conf=0.70).
    Strategy A retains both.
    Strategy D retains concentric and drops tangent as contradictory.
    """
    con = _c("concentric", "C1", "C2", confidence=0.92, cid="c-con")
    tan = _c("tangent", "C1", "C2", confidence=0.70, cid="c-tan")

    res_a = run_strategy_a_prune([con, tan])
    # Strategy A flaw: keeps both concentric and tangent on same circle pair
    assert len(res_a.kept) == 2, "Production Strategy A keeps conflicting concentric and tangent"

    res_d = prune_constraints_strategy_d([con, tan])
    # Strategy D fix: resolves conflict by keeping higher-confidence concentric
    assert len(res_d.kept) == 1
    assert res_d.kept[0].type == "concentric"
    assert "c-tan" in res_d.dropped_contradictory


def test_red_5_four_circle_concentric_clique():
    """RED-5: 4-circle concentric clique redundancy.

    4 concentric features (e.g. multi-step bore: C1, C2, C3, C4).
    Generates 6 pairwise concentric constraints.
    Strategy A keeps all 6 constraints (complete graph K4).
    Strategy D keeps exactly 3 spanning tree constraints.
    """
    clique = [
        _c("concentric", "C1", "C2", 0.95, "c-12"),
        _c("concentric", "C2", "C3", 0.94, "c-23"),
        _c("concentric", "C3", "C4", 0.93, "c-34"),
        _c("concentric", "C1", "C3", 0.90, "c-13"),
        _c("concentric", "C1", "C4", 0.88, "c-14"),
        _c("concentric", "C2", "C4", 0.87, "c-24"),
    ]

    res_a = run_strategy_a_prune(clique)
    assert len(res_a.kept) == 6, "Production Strategy A retains all 6 pairwise concentric constraints"

    res_d = prune_constraints_strategy_d(clique)
    assert len(res_d.kept) == 3, f"Expected 3 spanning tree constraints, got {len(res_d.kept)}"
    assert len(res_d.dropped_transitive_redundant) == 3
