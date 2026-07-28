# Semantic Constraint Compaction Design

**Status:** Approved under the user's delegated completion authority on
2026-07-28

## Problem

The approved private PDF page 1 contains 1,170 primitives and produces 538,983
raw pairwise constraints. Compound inference needs those detections during the
run, but persisting them makes one Semantic IR artifact about 175 MB and carries
large amounts of transitive solver noise into every downstream consumer.

## Design

- Detect raw constraints exactly as before.
- Feed the raw set to compound recognition so part inference keeps the evidence
  it already uses.
- Before constructing `SemanticIRDocument`, run the existing deterministic
  `prune_constraints()` function and persist only its solver-ready `kept` set.
- Keep `PruneResult` and `SolveResult` as separate runtime values. Solved
  coordinates are not written into Semantic IR.
- Do not change constraint confidence rules, compound rules, schema structure,
  calibration, Primitive IR, or DXF generation.
- Treat raw pairwise constraints as transient derivation data rather than the
  stable cross-phase contract.

## Safety and compatibility

- Existing compound regression tests must retain their expected parts.
- Downstream callers already prune before solving, so applying pruning again is
  idempotent.
- The compact document preserves the same `constraints` JSON field and
  `Constraint` schema; only redundant members are removed.
- Local AutoCAD crash reports remain outside Git through `ErrorReports/` in
  `.gitignore`.

## Acceptance criteria

1. A regression proves assembly does not persist the Cartesian product for
   dense parallel lines.
2. Existing Semantic IR, compound, pruning, solving, Agent, and orchestration
   tests pass.
3. Approved private page 1 retains fewer than 5,000 constraints and completes
   Semantic assembly in under 60 seconds on the release machine.
4. Approved private page 5 retains the previously measured 1,392 pruned
   constraints.
5. The complete offline, private-data, and AutoCAD Mechanical gates pass on the
   integrated candidate.
