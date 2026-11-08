# DXF Millimetre Unit Admission

**Status:** Approved for implementation 2026-10-14 by Local Sol; GitHub authority receipt: [#491 comment 6162442781](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6162442781).

## Problem

`PrimitiveIRDocument.calibration` supports `mm`, `cm`, and `m`, and assembly preserves coordinates in the calibration's declared unit. `build_dxf()` writes those coordinates unchanged while declaring `$INSUNITS=4` (millimetres). A source line measuring 20 mm was therefore emitted as 2 mm when represented by a 0.1 cm/px calibration. The existing reviewer passes because it checks written coordinates against the builder's own coordinate evidence, not physical units.

## Approved behavior

- Keep the existing `calibration.status != "verified"` rejection first.
- Before DXF construction, filesystem writes, or handle assignment, accept only the exact unit string `"mm"`.
- Reject `cm`, `m`, malformed values, and unknown labels with a descriptive `ValueError` that requires explicit canonical-mm conversion before calling this sink.
- Keep `$INSUNITS=4` and existing millimetre behavior unchanged.
- Do not convert coordinates, change calibration/assembly/solver/semantic behavior, add aliases, or claim cm/m output support.

## Reuse and ownership

The existing `dxf_builder_lib.builder.build_dxf` function owns this DXF sink, already rejects unverified calibration before construction, and writes primitive handles back to the input document. Reuse that early guard and current `Calibration.unit`; add no adapter or new pipeline. Reuse existing builder, dimension, solved-primitive, component, and reviewer tests. The approved write set is `builder.py`, one focused unit-contract test module, the builder README, and this spec/plan pair.

## Acceptance

1. Verified cm and m inputs, malformed values, and unknown labels are rejected before the destination directory/file or source handles change.
2. The existing unverified-calibration error retains precedence over the unit error.
3. A representative mm line still emits the same coordinates and `$INSUNITS=4`; existing dimension, solved-primitive, and component callers remain compatible.
4. Focused checks, touched Ruff, and `git diff --check` pass; one canonical verification invocation completes with exit 0 and unchanged clean identity/status.
5. Evidence says **wrong-scale emission prevented; conversion not implemented**. AutoCAD/.NET and real-data/native acceptance remain not run.

## Out of scope

Coordinate normalization or conversion, more unit support, schema/dependency changes, other production/test files, drawing replay, AutoCAD/native work, PR creation or mutation, reviewer/CI polling, ready transition, and merge.
