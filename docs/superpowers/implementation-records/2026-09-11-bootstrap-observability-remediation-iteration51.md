# Bootstrap Observability Remediation — Iteration 51

Date: 2026-09-11
Branch: `codex/audit-text-style-compat-20260910`
Implementation head: `4a0d33c02db56a71d99ffe207bc031c5bdfb80c5`

## Authority and boundary

SOL returned `VERDICT=BLOCKED` for the timing reconstruction, with
`HUMAN_GATE=NO`, and authorized exactly one non-live observability-only
remediation. The purpose is to distinguish a completion marker that is late
from one that is never produced on a future bounded proof. This change does
not modify timeout values, bootstrap commands, readiness semantics, FileIPC
behavior, or CAD operations. No AutoCAD session or live FileIPC request was
run for this checkpoint.

## Implementation

`BootstrapTimingRecorder` uses `time.monotonic` by default and exposes an
immutable event tuple containing an event name and monotonic timestamp. The
session records:

- `process_launch`
- `start_window_observed`
- `completion_wait_start`
- `completion_marker_observed`
- `completion_timeout`
- `cleanup_start`
- `cleanup_end`

`FileIPCLiveMCPClient` records `document_ready_transition`. The live harness
passes one recorder through the session factory and client, then emits the
privacy-safe `BOOTSTRAP_TIMING_EVENTS` JSON line in its existing cleanup path.
Recorder failures are best effort and cannot replace or suppress the original
bootstrap error, preserving fail-closed behavior.

## TDD and verification

- RED: the new timing tests failed during collection because
  `BootstrapTimingRecorder` did not exist.
- GREEN focused owner checks: `38 passed`, `6 subtests`; the standalone live
  gate was `SKIP` because the AutoCAD/FileIPC prerequisites were absent.
- Ruff: `PASS`.
- `git diff --check`: `PASS`.
- `scripts/verify.ps1`: exit `0` on the implementation head. C# recorded `238`
  passed; offline Python JUnit recorded `3385` tests with zero
  failures/errors/skips (`3305` passed, `21` deselected, `80` subtests);
  offline IPC recorded `134` clean tests; the causal-RED negative oracle
  recorded its expected one failure and was handled by the verifier;
  real-data recorded `2` unavailable skips; AutoCAD Mechanical recorded `17`
  unavailable skips. AutoCAD live and M2 remain `NOT RUN`.
- One provider-policy test was transiently observed as
  `WORKER_TIMEOUT` during the first full verifier run; it passed on an
  isolated rerun, and the clean authoritative rerun exited `0`. No change was
  made to that unrelated area.

## Review boundary

The timing data is now ready for one future SOL-reviewed live proof. No live
retry is authorized by this checkpoint. The next proof, if SOL authorizes it,
must consume the emitted monotonic event sequence and stop at the first
failure boundary with cleanup evidence.
