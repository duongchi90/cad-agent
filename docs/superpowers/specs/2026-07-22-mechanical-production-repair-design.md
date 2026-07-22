# AutoCAD Mechanical Production Review/Repair Design

**Status:** Approved by the user on 2026-07-22

**Target:** Windows, Python 3.11, AutoCAD Mechanical 2027

## Goal

Extend the thin orchestrator with a safe, reviewable route from a staged DXF
to an explicitly approved AutoCAD Mechanical repair. It must reuse the existing
Builder, Reviewer #2, and Repair #2 APIs without duplicating CAD algorithms.

## Design

- The ordinary `run` command persists `build-evidence.json`: the exact
  `BuildResult` handles, layers, written primitive geometry, component evidence,
  and original staged-DXF SHA-256 needed for later live review.
- `mechanical-review` opens the named DXF through File IPC, compares it to the
  saved build evidence, and writes an atomic JSON report. It never mutates the
  drawing.
- `mechanical-repair` requires a non-empty approval reference and the literal
  `--confirm-repair APPLY`. Before it asks AutoCAD to repair anything, it copies
  both the DXF and build evidence to a timestamped backup directory and records
  their SHA-256 hashes.
- A repair is saved only after live review finds mismatches, Repair #2 reports
  at least one repair, and a second live review passes. A failed second review
  is not saved; the command reopens the backup as the active document as a
  best-effort rollback and reports failure.
- Every report records the operator approval reference, backup paths/hashes,
  before/after review results, and save state. No credentials, raw IPC payloads,
  or customer geometry are committed.

## Boundaries

- This slice handles only primitive Repair #2 mismatches; component INSERT
  repair remains subject to the existing Repair #1 path and is reported rather
  than silently changed.
- The source DXF must be a staged artifact with matching build evidence. A
  customer drawing is never mutated merely because it is open in AutoCAD.
- Real-data validation still requires an operator-approved private input and
  remains outside Git.

## Acceptance criteria

1. A staged run writes integrity-bound build evidence.
2. Fake-MCP regression tests prove approval refusal, backup creation, repair,
   post-repair review, and no save after a failed repair.
3. A live `mechanical-review` succeeds against a disposable AutoCAD Mechanical
   DXF using File IPC.
4. Focused tests and `scripts/verify.ps1` pass; production execution requires
   separate operator approval even after this implementation ships.
