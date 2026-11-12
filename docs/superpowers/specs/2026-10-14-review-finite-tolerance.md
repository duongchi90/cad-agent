# Finite Review Tolerance Admission

Status: PO-approved design, Issue #491 comment 6164281750.

Date: 2026-10-14.

Exact design base: `7da1ed42a2168b5c991fc389a4c8155b1e88a387`.

## Decision

Validate `review_dxf(..., tolerance_mm=...)` before importing `ezdxf` or opening the supplied path. Accept built-in `int` and `float` values that are finite and nonnegative. Reject booleans, other types, negative values, NaN, infinities, and values whose finiteness check overflows with a descriptive `ValueError`.

This closes the demonstrated false-PASS path where NaN makes comparisons such as `difference > tolerance_mm` false. The regression evidence is recorded in [Issue #491 comment 6164170628](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6164170628), with persisted evidence SHA256 `7cffed32fecedbab24138abbc39cfa47110eaec43a3a64bcb16294f816706985`.

## Reuse and compatibility

The existing owner is `dxf_builder_lib.reviewer.review_dxf`; it already imports `math` and uses `math.isfinite` for geometry checks. Add only argument admission at that entry point. Preserve the signature, default `1e-6`, finite nonnegative int/float behavior, result schema, and all existing comparison thresholds. No maximum tolerance is introduced. Invalid policy must fail before dependency import or file I/O.

## Scope and approval

Supported scope is the existing headless DXF reviewer. The five-file work package is authorized by PO comment 6164281750. The measured discriminator is not rerun. No new dependency, schema, builder change, drawing evaluation, AutoCAD/native action, publication, PR, or merge is in scope.
