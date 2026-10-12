"""
test_constraint_pruning_degenerate_and_perf.py — Degenerate, Non-Finite & Performance Tests.

Epic: TRANSITIVE_AND_CONFLICTING_CONSTRAINT_PRUNING_V1
Role: ANTIGRAVITY_RESEARCH
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from semantic_ir_lib.models import Constraint
from constraint_pruning_engine import (
    prune_constraints_strategy_d,
    EnhancedPruneResult,
)


def _c(type_: str, a: str, b: str, confidence: float = 0.9, cid: str | None = None) -> Constraint:
    c = Constraint(type=type_, primitive_ids=[a, b], confidence=confidence, tolerance={})
    if cid:
        c.id = cid
    return c


def test_degenerate_empty_list():
    """Verify empty constraint list produces clean empty result."""
    res = prune_constraints_strategy_d([])
    assert isinstance(res, EnhancedPruneResult)
    assert len(res.kept) == 0
    assert len(res.dropped_low_confidence) == 0


def test_degenerate_single_constraint():
    """Verify single valid constraint is retained directly."""
    c = _c("parallel", "L1", "L2", 0.95, "c-single")
    res = prune_constraints_strategy_d([c])
    assert len(res.kept) == 1
    assert res.kept[0].id == "c-single"


def test_degenerate_self_referential_constraint():
    """Verify self-referential constraint where primitive_ids=[A, A] is rejected."""
    c_self = _c("parallel", "A", "A", 0.95, "c-self")
    res = prune_constraints_strategy_d([c_self])
    # Self-referential parallel is an identity/tautology and dropped
    assert len(res.kept) == 0 or res.kept[0].id != "c-self"


def test_nonfinite_and_extreme_confidences():
    """Verify Constraint dataclass enforces 0 <= conf <= 1 and safe filtering works."""
    with pytest.raises(ValueError):
        _c("parallel", "L1", "L2", float("nan"))

    with pytest.raises(ValueError):
        _c("parallel", "L1", "L2", float("inf"))

    with pytest.raises(ValueError):
        _c("parallel", "L1", "L2", -0.1)

    with pytest.raises(ValueError):
        _c("parallel", "L1", "L2", 1.5)

    # Valid boundary confidences: 0.0 and 1.0
    c_zero = _c("parallel", "L1", "L2", 0.0, "c-zero")
    c_one = _c("parallel", "L2", "L3", 1.0, "c-one")

    res = prune_constraints_strategy_d([c_zero, c_one], min_confidence=0.6)
    assert "c-zero" in res.dropped_low_confidence
    assert any(c.id == "c-one" for c in res.kept)


def test_disconnected_subgraphs():
    """Verify disjoint components across multiple independent mechanical parts."""
    part1_parallels = [_c("parallel", f"P1_{i}", f"P1_{i+1}", 0.9) for i in range(5)]
    part2_concentric = [_c("concentric", f"C2_{i}", f"C2_{i+1}", 0.9) for i in range(5)]
    part3_collinear = [_c("collinear", f"S3_{i}", f"S3_{i+1}", 0.9) for i in range(5)]

    all_c = part1_parallels + part2_concentric + part3_collinear
    res = prune_constraints_strategy_d(all_c)
    assert len(res.kept) == 15
    assert len(res.dropped_contradictory) == 0


def test_performance_1000_constraints_budget():
    """Verify pruning latency on a large mechanical drawing with 1,000+ pairwise constraints is < 50ms."""
    # Build 15 groups of 10 parallel lines (each complete graph K10 = 45 edges -> 675 parallel edges)
    # Plus 8 groups of 10 concentric circles (each complete graph K10 = 45 edges -> 360 concentric edges)
    # Plus 100 cross-group perpendiculars
    # Total > 1,100 constraints
    workload: list[Constraint] = []
    idx = 1

    # Parallel groups
    for g in range(15):
        members = [f"L_g{g}_{i}" for i in range(10)]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                workload.append(_c("parallel", members[i], members[j], 0.90, f"par-{idx}"))
                idx += 1

    # Concentric groups
    for g in range(8):
        members = [f"C_g{g}_{i}" for i in range(10)]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                workload.append(_c("concentric", members[i], members[j], 0.90, f"con-{idx}"))
                idx += 1

    # Cross perpendiculars
    for g in range(0, 14, 2):
        for i in range(4):
            for j in range(4):
                workload.append(_c("perpendicular", f"L_g{g}_{i}", f"L_g{g+1}_{j}", 0.85, f"perp-{idx}"))
                idx += 1

    assert len(workload) >= 1000, f"Expected >= 1000 constraints, got {len(workload)}"

    start_time = time.perf_counter()
    res = prune_constraints_strategy_d(workload)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Measured latency budget: 1,147 constraints pruned in < 50ms
    assert elapsed_ms < 50.0, f"Expected < 50ms for {len(workload)} constraints, got {elapsed_ms:.2f}ms"
    # Result must be vastly reduced and solver-ready
    assert len(res.kept) < len(workload) / 3
