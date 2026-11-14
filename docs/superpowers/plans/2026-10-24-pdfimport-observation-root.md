# PDFIMPORT Observation Root Implementation Plan

- Status: completed
- Base SHA: `abfb60ea7d9cf2012e0ea30b68b9fef8b5fb0512`
- Completion Head SHA: `7dfabf6f0cca4ac1f6b5663938dec2396a6671ce`
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
   `docs/STATUS.md` without claiming native acceptance. Complete.

## Verification and remaining gates

- RED: the new focused test failed collection because the owner function did not
  yet exist.
- Focused GREEN: `python -m pytest tests/test_pdfimport_observation_root.py tests/test_external_root_visual_run.py -q` — 12 passed.
- Lint: `python -m ruff check cad_agent/visual_evidence.py tests/test_pdfimport_observation_root.py` — passed.
- Whitespace: `git diff --check` — passed.
- Canonical command: `./scripts/verify.ps1 -PythonExe C:\cad-agent\.venv-py311\Scripts\python.exe` — exit 0; .NET 261/261, offline IPC 128/128, Python 3,743 passed / 24 deselected / 86 subtests. The expected causal-RED negative oracle produced its expected failing assertion and was validated by the verifier wrapper.
- B041 separate test on current main: `test_b041_pdf_preserves_three_source_supported_orthographic_circles` — 1 passed with the approved PDF matching the test SHA-256.
- Required native CASE02 observation/readback gate: not run in this package.
- Exact-head Security/Integration review and hosted CI: not run; required before adoption.
- Real-data gates not configured in the canonical run: SKIP. AutoCAD/live/native gates: NOT RUN.
