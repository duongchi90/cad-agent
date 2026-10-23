# PDFIMPORT Observation Root Implementation Plan

- Status: executing
- Base SHA: `abfb60ea7d9cf2012e0ea30b68b9fef8b5fb0512`
- Completion Head SHA: pending
- Design: `docs/superpowers/specs/2026-10-24-pdfimport-observation-root-design.md`

## Bounded write set

- `cad_agent/visual_evidence.py`
- `tests/test_pdfimport_observation_root.py`
- this design and plan record
- `docs/STATUS.md` only when verified implementation evidence is ready to
  record

No AutoCAD/native action, candidate mutation, manifest/schema change, IPC or
dispatcher change, production PDF import, or PR review/merge action is part of
this package.

## Steps

1. Add fail-closed tests for the closed packet, canonical digest, and invalid
   values; observe the expected missing-owner failure.
2. Add the separate typed digest helper in the existing visual-evidence owner.
3. Run focused tests, lint, and `git diff --check`.
4. Run the authoritative `scripts/verify.ps1` if the focused implementation is
   green; retain explicit outcomes for missing private/live gates.
5. Record the final implementation head and verification results here and in
   `docs/STATUS.md` without claiming native acceptance.

## Verification and remaining gates

- Exact focused command: `python -m pytest tests/test_pdfimport_observation_root.py -q`
- Canonical command: `./scripts/verify.ps1`
- Required native CASE02 observation/readback gate: not run in this package.
- Exact-head Security/Integration review and hosted CI: not run in this package.
