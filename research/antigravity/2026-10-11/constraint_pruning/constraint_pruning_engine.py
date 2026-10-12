"""
constraint_pruning_engine.py — Reference Engine for Transitive and Conflicting Constraint Pruning.

Epic: TRANSITIVE_AND_CONFLICTING_CONSTRAINT_PRUNING_V1
Role: ANTIGRAVITY_RESEARCH

Benchmarks and compares constraint pruning strategies:
- Strategy A: Current Production Main (semantic_ir_lib/constraint_pruning.py)
- Strategy B: Naive Greedy Filter (drops already-seen primitive pairs blindly)
- Strategy C: Extended Transitive Only (adds concentric to union-find, but lacks conflict pruning)
- Strategy D: Comprehensive Graph-Theoretic Constraint Normalization Engine (Selected Oracle)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from semantic_ir_lib.constraint_pruning import (
    PruneResult as ProductionPruneResult,
    prune_constraints as run_strategy_a_prune,
)
from semantic_ir_lib.models import Constraint


class _UnionFind:
    def __init__(self) -> None:
        self._parent: Dict[str, str] = {}

    def find(self, x: str) -> str:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self._parent[ra] = rb
        return True


@dataclass
class EnhancedPruneResult:
    kept: List[Constraint] = field(default_factory=list)
    dropped_low_confidence: List[str] = field(default_factory=list)
    dropped_duplicate: List[str] = field(default_factory=list)
    dropped_transitive_redundant: List[str] = field(default_factory=list)
    dropped_group_redundant: List[str] = field(default_factory=list)
    dropped_subsumed: List[str] = field(default_factory=list)
    dropped_contradictory: List[str] = field(default_factory=list)


def _pair_key(c: Constraint) -> Tuple[str, str, str]:
    a, b = c.primitive_ids
    return (c.type, a, b) if a <= b else (c.type, b, a)


def _unordered_pair(c: Constraint) -> Tuple[str, str]:
    a, b = c.primitive_ids
    return (a, b) if a <= b else (b, a)


# ---------------------------------------------------------------------------
# Strategy B: Naive Greedy Filter
# ---------------------------------------------------------------------------

def run_strategy_b_prune(
    constraints: List[Constraint],
    min_confidence: float = 0.6,
) -> EnhancedPruneResult:
    """Strategy B: Greedily retains the first constraint per primitive pair, dropping all others."""
    result = EnhancedPruneResult()
    seen_pairs: Set[Tuple[str, str]] = set()

    for c in sorted(constraints, key=lambda x: x.confidence, reverse=True):
        if c.confidence < min_confidence:
            result.dropped_low_confidence.append(c.id)
            continue
        pair = _unordered_pair(c)
        if pair in seen_pairs:
            result.dropped_duplicate.append(c.id)
        else:
            seen_pairs.add(pair)
            result.kept.append(c)

    return result


# ---------------------------------------------------------------------------
# Strategy C: Extended Transitive Only (No Conflict / Subsumption Logic)
# ---------------------------------------------------------------------------

def run_strategy_c_prune(
    constraints: List[Constraint],
    min_confidence: float = 0.6,
) -> EnhancedPruneResult:
    """Strategy C: Adds concentric to transitive types and prevents ga == gb in perp, but lacks subsumption."""
    result = EnhancedPruneResult()
    transitive_types = {"parallel", "equal_length", "collinear", "concentric"}

    survivors = [c for c in constraints if c.confidence >= min_confidence]
    for c in constraints:
        if c.confidence < min_confidence:
            result.dropped_low_confidence.append(c.id)

    best_by_key: Dict[Tuple[str, str, str], Constraint] = {}
    for c in survivors:
        k = _pair_key(c)
        existing = best_by_key.get(k)
        if existing is None:
            best_by_key[k] = c
        elif c.confidence > existing.confidence:
            result.dropped_duplicate.append(existing.id)
            best_by_key[k] = c
        else:
            result.dropped_duplicate.append(c.id)

    deduped = list(best_by_key.values())
    non_transitive = [c for c in deduped if c.type not in transitive_types]
    transitive = [c for c in deduped if c.type in transitive_types]

    by_type: Dict[str, List[Constraint]] = {}
    for c in transitive:
        by_type.setdefault(c.type, []).append(c)

    for ctype, group in by_type.items():
        group_sorted = sorted(group, key=lambda c: c.confidence, reverse=True)
        uf = _UnionFind()
        for c in group_sorted:
            a, b = c.primitive_ids
            if uf.union(a, b):
                result.kept.append(c)
            else:
                result.dropped_transitive_redundant.append(c.id)

    orientation_groups = _UnionFind()
    for c in result.kept:
        if c.type in ("parallel", "collinear"):
            a, b = c.primitive_ids
            orientation_groups.union(a, b)

    perpendicular = [c for c in non_transitive if c.type == "perpendicular"]
    other_non_transitive = [c for c in non_transitive if c.type != "perpendicular"]

    seen_group_pairs: Set[Tuple[str, str]] = set()
    for c in sorted(perpendicular, key=lambda x: x.confidence, reverse=True):
        a, b = c.primitive_ids
        ga, gb = orientation_groups.find(a), orientation_groups.find(b)
        if ga == gb:
            result.dropped_contradictory.append(c.id)
            continue
        pair_key = (ga, gb) if ga <= gb else (gb, ga)
        if pair_key in seen_group_pairs:
            result.dropped_group_redundant.append(c.id)
        else:
            seen_group_pairs.add(pair_key)
            result.kept.append(c)

    result.kept.extend(other_non_transitive)
    return result


# ---------------------------------------------------------------------------
# Strategy D: Comprehensive Graph-Theoretic Constraint Normalization Engine (Oracle)
# ---------------------------------------------------------------------------

_ORACLE_TRANSITIVE_TYPES = {"parallel", "equal_length", "collinear", "concentric"}


def prune_constraints_strategy_d(
    constraints: List[Constraint],
    min_confidence: float = 0.6,
) -> EnhancedPruneResult:
    """Strategy D: Comprehensive Graph-Theoretic Constraint Normalization Engine.

    Eliminates:
    1. Low-confidence noise (< min_confidence).
    2. Subsumed constraints on same pair (e.g. collinear subsumes parallel).
    3. Mutually contradictory constraints on same pair:
       - parallel vs perpendicular
       - collinear vs perpendicular
       - concentric vs tangent
    4. Exact duplicates on same (type, pair), preserving highest confidence.
    5. Transitive cycles across parallel, collinear, equal_length, concentric.
    6. Intra-group self-perpendicular contradictions (ga == gb).
    7. Cross-group redundant perpendiculars (keeping 1 representative edge per group pair).
    """
    result = EnhancedPruneResult()

    # 1. Filter by minimum confidence
    survivors: List[Constraint] = []
    for c in constraints:
        if c.confidence < min_confidence:
            result.dropped_low_confidence.append(c.id)
        else:
            survivors.append(c)

    # 2. Group by unordered primitive pair to detect subsumption & direct contradictions
    by_pair: Dict[Tuple[str, str], List[Constraint]] = {}
    for c in survivors:
        pair = _unordered_pair(c)
        by_pair.setdefault(pair, []).append(c)

    cleaned_pair_constraints: List[Constraint] = []

    for pair, pair_constraints in by_pair.items():
        # A. Check Collinear vs Parallel Subsumption
        has_collinear = any(c.type == "collinear" for c in pair_constraints)
        has_parallel = any(c.type == "parallel" for c in pair_constraints)

        retained_for_pair: List[Constraint] = []
        for c in pair_constraints:
            if c.type == "parallel" and has_collinear:
                # Collinear strictly subsumes parallel on the same line pair!
                result.dropped_subsumed.append(c.id)
            else:
                retained_for_pair.append(c)

        # B. Check Direct Pair Contradictions
        # (parallel/collinear vs perpendicular)
        types_in_pair = {c.type for c in retained_for_pair}
        if ("parallel" in types_in_pair or "collinear" in types_in_pair) and "perpendicular" in types_in_pair:
            # Sort by confidence descending
            retained_for_pair.sort(key=lambda x: x.confidence, reverse=True)
            winner = retained_for_pair[0]
            for loser in retained_for_pair[1:]:
                if (winner.type in ("parallel", "collinear") and loser.type == "perpendicular") or \
                   (winner.type == "perpendicular" and loser.type in ("parallel", "collinear")):
                    result.dropped_contradictory.append(loser.id)
                else:
                    retained_for_pair = [winner]
            retained_for_pair = [winner]

        # (concentric vs tangent)
        types_in_pair = {c.type for c in retained_for_pair}
        if "concentric" in types_in_pair and "tangent" in types_in_pair:
            retained_for_pair.sort(key=lambda x: x.confidence, reverse=True)
            winner = retained_for_pair[0]
            for loser in retained_for_pair[1:]:
                if (winner.type == "concentric" and loser.type == "tangent") or \
                   (winner.type == "tangent" and loser.type == "concentric"):
                    result.dropped_contradictory.append(loser.id)
            retained_for_pair = [winner]

        cleaned_pair_constraints.extend(retained_for_pair)

    # 3. Exact Duplicate Deduplication (same type + same pair)
    best_by_key: Dict[Tuple[str, str, str], Constraint] = {}
    for c in cleaned_pair_constraints:
        key = _pair_key(c)
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = c
        elif c.confidence > existing.confidence:
            result.dropped_duplicate.append(existing.id)
            best_by_key[key] = c
        else:
            result.dropped_duplicate.append(c.id)

    deduped = list(best_by_key.values())

    # 4. Transitive Reduction via Union-Find Spanning Trees
    transitive = [c for c in deduped if c.type in _ORACLE_TRANSITIVE_TYPES]
    non_transitive = [c for c in deduped if c.type not in _ORACLE_TRANSITIVE_TYPES]

    by_type: Dict[str, List[Constraint]] = {}
    for c in transitive:
        by_type.setdefault(c.type, []).append(c)

    for ctype, group in by_type.items():
        group_sorted = sorted(group, key=lambda c: c.confidence, reverse=True)
        uf = _UnionFind()
        for c in group_sorted:
            a, b = c.primitive_ids
            if uf.union(a, b):
                result.kept.append(c)
            else:
                result.dropped_transitive_redundant.append(c.id)

    # 5. Build Orientation Groups from kept parallel and collinear constraints
    orientation_groups = _UnionFind()
    for c in result.kept:
        if c.type in ("parallel", "collinear"):
            a, b = c.primitive_ids
            orientation_groups.union(a, b)

    perpendicular = [c for c in non_transitive if c.type == "perpendicular"]
    other_non_transitive = [c for c in non_transitive if c.type != "perpendicular"]

    # 6. Group Perpendicular Redundancy and Intra-Group Contradiction Pruning
    perpendicular_sorted = sorted(perpendicular, key=lambda c: c.confidence, reverse=True)
    seen_group_pairs: Set[Tuple[str, str]] = set()

    for c in perpendicular_sorted:
        a, b = c.primitive_ids
        ga, gb = orientation_groups.find(a), orientation_groups.find(b)
        if ga == gb:
            # Intra-group contradiction: primitive marked perpendicular to its own parallel group!
            result.dropped_contradictory.append(c.id)
            continue

        pair_key = (ga, gb) if ga <= gb else (gb, ga)
        if pair_key in seen_group_pairs:
            result.dropped_group_redundant.append(c.id)
        else:
            seen_group_pairs.add(pair_key)
            result.kept.append(c)

    # 7. Retain other non-transitive constraints (coincident_endpoint, tangent)
    result.kept.extend(other_non_transitive)

    return result
