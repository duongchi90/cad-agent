# Solver Capacity Guard Design

**Status:** Approved by the user's optimization request on 2026-07-22

## Evidence

After compound-recognition optimization, page 5 of the approved private PDF
reaches the DXF stage. It has 478 relevant line primitives. Solving their two
endpoints creates approximately 1,912 coordinate unknowns. Although constraint
pruning reduces 109,399 detected constraints to 1,392, the underlying solver
performs three order-dependent attempts and does not reach a timely result.

## Goal

Bound constraint solving before expensive solver-system construction, while
preserving all detected geometry and making the fallback explicit.

## Design

- Define a documented capacity of 1,000 coordinate unknowns (250 line
  primitives, four coordinates each) for one SolveSpace call.
- Compute the relevant line count before constructing the solver system.
- When the capacity is exceeded, return the existing `too_many_unknowns`
  result with no solved primitives and no applied constraints.
- The DXF stage already uses original calibrated primitive geometry when a
  solve result is not `okay`; retain that behavior. It must not silently alter
  or discard entities.
- Keep the existing three solve attempts and all behavior unchanged at or
  below the capacity.

## Acceptance criteria

1. A 251-line constrained document returns `too_many_unknowns` without
   constructing a solver system.
2. Existing small constraint-solving regressions remain unchanged.
3. The approved PDF page 5 resumes through DXF generation without a long
   solver run, with its unmodified calibrated geometry represented in the DXF.
