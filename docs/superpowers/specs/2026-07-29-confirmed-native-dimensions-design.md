# Confirmed Native Dimensions Design

**Status:** Approved under the user's delegated completion authority on
2026-07-29

## Goal

Emit reviewable native DXF `DIMENSION` entities only when an existing
Primitive IR cross-validation has already confirmed that a text dimension and
a line measurement agree. Do not infer dimension semantics from unverified OCR
or geometry.

## Design

- `build_dxf(..., build_dimensions=False)` preserves the existing package API
  default.
- The `cad_agent` staged orchestrator opts into `build_dimensions=True`.
- Only `CrossValidation.status == "confirmed"` with a valid non-zero LINE
  produces a linear native `DIMENSION`.
- The dimension measures the calibrated line geometry; unverified or missing
  cross-validations produce no entity.
- `BuildResult` records dimension count, validation-to-handle mapping, layer,
  measurement, and source primitive IDs.
- Reviewer #1 reopens the DXF and verifies native entity count, handle, type,
  layer, and measurement. Missing or altered dimensions fail headless review.
- Build evidence serializes the dimension records for later staged review.

## Boundaries

- This does not convert unreviewed fidelity OCR candidates into dimensions.
- It does not fabricate leaders, tolerances, symbols, or arbitrary dimension
  placement semantics.
- Font/OCR correction remains deferred as requested.

## Acceptance

1. Confirmed line/text validation emits one native `DIMENSION`.
2. Unverified validation emits none.
3. Reviewer #1 passes the intact result and rejects a tampered dimension.
4. Existing callers keep the opt-in default and the full verifier passes.
