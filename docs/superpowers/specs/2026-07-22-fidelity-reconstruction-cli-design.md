# Fidelity Reconstruction CLI Design

**Status:** Approved by the user's request on 2026-07-22 to complete fidelity
reconstruction through standard CLI integration.

## Scope

Turn the private page-5 experiments into a reproducible, private fidelity
workflow. The output profile is `fidelity-layout`, is paper-coordinate only,
and remains `needs_review`; it is not a model, production, or Mechanical DXF.

## Required safety contract

- Every public fidelity operation validates a single external output root,
  source SHA, manifest location, and relative/hash-valid artifact paths.
- Reconstruction consumes a separate page-region approval record bound to PDF
  SHA, rendered-page SHA, page dimensions/DPI, immutable proposal revision and
  definition SHA. An unapproved, stale, or changed proposal is refused.
- Reconstruction writes a fresh private candidate directory and never mutates
  baseline DXFs, source renders, or prior candidates.
- A candidate consists of region-local raw geometry, a clean DXF, overlay, and
  report. Unselected area remains `needs_classification`.
- OCR, dimensions, linetypes, leaders, hatches, and table cells are sidecar
  observations by default. Text enters a candidate DXF only after per-text
  approval and a Unicode glyph-render test; dimensions/tables/linetypes need
  their own explicit mappings.
- Fidelity provenance is refused by Mechanical review and repair before any
  live client is created. Model export is a separate profile requiring a
  view-specific approved calibration; page-wide paper scale is never model
  scale.

## Delivery stages

1. Enforce integrity/provenance and write SHA-bound region approvals.
2. Implement one-page approved-region geometry candidate command plus report.
3. Add review-only OCR/table/linetype observations and Unicode text validation.
4. Compose approved regions into paper layouts and execute all nine pages.
5. Ship `fidelity-reconstruct` CLI, deterministic tests, private benchmark
   evidence, and corrected status ledger.

## Non-goals

No automatic model generation, production DXF, inferred dimensions, Mechanical
mutation, or visual "pass" claim is part of this slice.
