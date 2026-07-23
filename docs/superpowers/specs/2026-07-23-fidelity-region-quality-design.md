# Fidelity Region Quality Design

## Status

Approved for review-only implementation by the user's 2026-07-23 instruction
to finish the project and authorize AI visual review. This does not authorize
production DXF mutation or AutoCAD Mechanical operations.

## Problem

The private nine-page PDF/DXF overlays show low full-sheet edge F1 (0.065 to
0.289). Existing reconstruction extracts every detected primitive in approved
regions, including OCR glyph strokes, scan noise, and dense illustration
details. A page-level score hides whether a local candidate improved or
degraded the approved region.

## Scope

Add a review-only quality gate to local reconstruction candidates. For each
approved region, the workflow renders a baseline candidate and a filtered
candidate, measures the same tolerant edge F1 used by the fidelity overlays,
and writes only the better candidate as the revisioned private result. It
records both metrics, entity counts, and the chosen profile in the report.

The first profile removes short, near-duplicate, and text-like strokes before
DXF construction. It preserves long horizontal/vertical/diagonal geometry and
circles. A candidate is never accepted merely because it contains fewer
entities: its local F1 must be strictly greater than the unfiltered baseline.

## Safety and non-goals

- All inputs and outputs remain SHA-bound private fidelity artifacts outside
  the Git worktree.
- Geometry remains candidate-only and `needs_review`; it is refused by
  Mechanical review and repair commands.
- The workflow does not create semantic components, dimensions, hatches,
  production drawings, or inferred model geometry.
- A profile that does not improve F1 leaves the baseline candidate selected and
  reports the rejection. It must not degrade the existing private layout.

## Acceptance criteria

- Synthetic regression coverage proves an accepted filtered candidate has
  higher F1 than its baseline and that a non-improving profile is rejected.
- Candidate reports identify baseline F1, filtered F1, selection, and counts.
- Existing fidelity tests, the official verifier, and a private nine-page
  rerun complete without modifying repository-tracked artifacts.
- Visual review uses fresh overlay PNGs. No claim of production readiness is
  made from these candidates.
