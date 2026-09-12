# Bootstrap Timing Anchor Correction — Iteration 52

Date: 2026-09-11
Branch: `codex/audit-text-style-compat-20260910`
Implementation head: `871db5fb29e944d894ff83d12a6fb4a4695f82bc`

## Authority and boundary

SOL's iteration-51 review identified one material evidence gap: the session
waited for completion-marker acknowledgement before the client reached its
normal document-ready probe, so the exact marker-timeout path could not emit a
document-ready anchor. SOL authorized exactly one non-live, observability-only
correction. No live retry or CAD/FileIPC/source/candidate operation was run.

## Correction

`WindowsAutoCADStartTabSession` now creates the existing document-ready probe
for the observed, owned HWND and best-effort polls it while waiting for the
completion marker. The first positive result records
`document_ready_transition` on the shared `BootstrapTimingRecorder`.

This observation is non-gating: it does not return success, change the
completion deadline, change timeout values, modify the startup script, alter
readiness/FileIPC behavior, or perform a CAD operation. The normal client
readiness check remains in place. `record_once` deduplicates the shared
transition when that later check sees the same already-observed state.
Probe and recorder exceptions remain swallowed so the original fail-closed
bootstrap result is preserved.

## TDD and verification

- RED: the new deduplication test failed because `record_once` was absent, and
  the success/timeout ordering assertions lacked the in-wait transition.
- GREEN focused owner checks: `39 passed`, `6 subtests`; the standalone live
  gate was `SKIP` because AutoCAD/FileIPC prerequisites were absent.
- Ruff: `PASS`.
- `git diff --check`: `PASS`.
- `scripts/verify.ps1`: exit `0` on the implementation head. C# recorded `238`
  passed; offline Python JUnit recorded `3386` tests with zero
  failures/errors/skips (`3306` passed, `21` deselected, `80` subtests);
  offline IPC recorded `134` clean tests; the causal-RED negative oracle
  recorded its expected one failure and was handled by the verifier;
  real-data recorded `2` unavailable skips; AutoCAD Mechanical recorded `17`
  unavailable skips. AutoCAD live and M2 remain `NOT RUN`.

## Review boundary

The next bounded action requires SOL review of this exact implementation and
must consume the new timing event on a future proof before any live retry is
considered. No live authorization is implied by this record.
