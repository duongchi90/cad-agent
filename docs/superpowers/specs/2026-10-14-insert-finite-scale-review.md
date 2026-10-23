# INSERT Finite Scale Review

Status: PO-approved by Issue #491 comment 6165085191.

Approval date: 2026-10-14.

Exact base: `7da1ed42a2168b5c991fc389a4c8155b1e88a387`.

Base tree: `de41dc0707f695c085f0e40218d240e78cebdb8a`.

## Problem

The existing `dxf_builder_lib.reviewer.review_dxf` compares each persisted INSERT scale using `abs(actual - expected) > tolerance_mm`. For a NaN operand, that predicate is false, so a nonfinite actual artifact value or expected build record can evade the mismatch result. A saved/reopened synthetic INSERT confirmed actual `xscale=NaN` passes against finite builder evidence; the finite `xscale=5000` control correctly fails. See Issue #491 comment 6165017633.

## Decision

At the existing INSERT scale loop, reuse `_scalar_matches(actual_val, expected_val, tolerance_mm)`. The helper already rejects nonfinite actual and expected scalars while preserving the current absolute tolerance. Apply it to `xscale`, `yscale`, and `zscale` only.

Preserve finite comparison behavior, including current scale-sign semantics, mismatch field/message structure, and candidate read-only review behavior. Do not add a positivity rule or change rotation, tolerance admission, other geometry fields, result schema, dependencies, or architecture.

## Reuse and verification

Reuse the existing `_scalar_matches` helper and `_build_beam_component` fixture in `dxf_builder_lib/tests/test_reviewer.py`. Persist and reopen actual nonfinite values before review. Cover nonfinite expected evidence separately; finite equality, within-tolerance, and outside-tolerance behavior; exact axis mismatch identity; and unchanged candidate bytes. No drawing or AutoCAD session is involved.