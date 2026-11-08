# Semantic IR Millimetre Unit Admission

Status: approved for bounded implementation by Local GPT-6.1-Sol on 2026-10-14.

## Supported scope

The existing `semantic_ir_lib.assemble.build_semantic_document` entry point
accepts calibrated Primitive IR only when `calibration.unit` is exactly `mm`.
Semantic geometry summaries and detection tolerances are millimetre based. A
document using `cm`, `m`, or a malformed/unknown unit label must fail with a
descriptive `ValueError` before pattern, constraint, pruning, or compound
helpers run.

The guard does not convert or relabel coordinates. Callers must explicitly
convert coordinates to millimetres before using Semantic IR. Lower-level
helpers accepting bare primitives retain a caller-owned millimetre precondition.
Existing loader approval checks and exact-mm behavior remain unchanged.

## Reuse and ownership

- Existing owner: `semantic_ir_lib.assemble.build_semantic_document`.
- Reused contract: `Calibration.unit`, the existing assembly entry point, and
  existing pattern/constraint/compound helpers.
- Adapter or new capability: none.
- Exact write set: `semantic_ir_lib/assemble.py`,
  `semantic_ir_lib/tests/test_semantic_unit_contract.py`,
  `semantic_ir_lib/README.md`, this specification, and its implementation plan.
- Forbidden duplication: unit conversion, calibration changes, schema changes,
  alternate semantic pipeline, or new unit registry.

## Acceptance

Synthetic regression tests prove non-mm and malformed labels are refused before
semantic helpers execute, inputs remain unchanged, and the existing mm case
still produces the expected 20 mm summary. No real/private drawing or native CAD
action is part of this bounded change.
