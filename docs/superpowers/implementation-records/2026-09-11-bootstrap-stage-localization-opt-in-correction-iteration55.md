# Bootstrap Stage-Localization Opt-In Correction — Iteration 55

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Base code head: `486e2dd72911c5b67b59216a2877b338e03eddc4`
Completion code head: `b4c8776191b353921944fc4feba3a264bcf39d3e`

## Authority and boundary

SOL's iteration-54 review found that stage localization was unconditional
whenever an IPC root was configured. SOL authorized exactly one non-live scope
correction: make stage localization explicitly opt-in and keep normal bootstrap
script bytes unchanged. No live retry, source open, FileIPC request, or CAD
operation was authorized.

## Correction

`WindowsAutoCADStartTabSession` and
`make_windows_start_tab_session_factory` now accept
`stage_timing_enabled=False`. The default path creates no stage paths and adds
no stage expressions or filesystem writes. Only the standalone Task-6
diagnostic harness that emits `BOOTSTRAP_TIMING_EVENTS` enables the flag.

Opt-in mode preserves iteration-54 behavior: unique same-root fixed-token
markers for `post_qnew_entry`, `netload_return`, `dispatcher_load_return`, and
`completion_marker_writer_return`; best-effort monotonic observation; cleanup;
unchanged timeout, marker, readiness/FileIPC, and fail-closed semantics.

## TDD and verification

- RED: the new default-script regression failed because stage expressions were
  unconditional; opt-in tests also failed because the new parameter was absent.
- GREEN: `py -3.11 -m unittest
  mcp_integration_lib.tests.test_mcp_client_drawing_open` — `39` passed.
- Ruff: `All checks passed!`.
- `git diff --check`: `PASS`.
- `scripts/verify.ps1` on clean completion code head — .NET `238` passed;
  offline Python JUnit `3387` with zero failures/errors/skips (`3307` passed,
  `21` deselected, `80` subtests); offline IPC JUnit `134` clean; causal-RED
  expected one negative failure handled; real-data `2` unavailable skips;
  AutoCAD Mechanical `17` unavailable skips; AutoCAD live and M2 `NOT RUN`.

## Review boundary

The opt-in correction is pushed at code head
`b4c8776191b353921944fc4feba3a264bcf39d3e`. Fresh SOL review is required
before any live proof. No source, candidate, accepted drawing, or production
CAD state was mutated in this iteration.
