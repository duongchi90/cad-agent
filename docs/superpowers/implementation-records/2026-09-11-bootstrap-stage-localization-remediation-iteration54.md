# Bootstrap Stage-Localization Remediation — Iteration 54

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Base docs/evidence head: `74e01e4432b400f84d36af29e87602c5c9d3a396`
Completion head: `486e2dd72911c5b67b59216a2877b338e03eddc4`

## Authority and boundary

SOL's iteration-53 review localized the marker-timeout failure to the
post-document-ready startup-script path. It authorized exactly one non-live,
observability-only remediation. The existing bootstrap commands, 30-second
deadline, completion marker contract, readiness/FileIPC semantics, and
fail-closed behavior were required to remain unchanged. No live retry or CAD
operation was authorized.

## Correction

The owned startup script now emits four fixed-token stage markers, each at a
unique path under the exact disposable IPC root derived from the session script
stem:

- `post_qnew_entry`
- `netload_return`
- `dispatcher_load_return`
- `completion_marker_writer_return`

The session best-effort polls those markers during its existing completion wait
and records the first observation on the existing monotonic timing recorder.
Incorrect, missing, unreadable, or observer-failing markers do not change
bootstrap control flow. Cleanup removes every stage marker as well as the
existing completion marker. The markers contain only fixed stage tokens and no
drawing or customer data.

## TDD and verification

- RED: the updated script/order/partial-failure cleanup tests failed because
  `_START_TAB_STAGE_MARKERS` and the stage evidence were absent.
- GREEN: `py -3.11 -m unittest
  mcp_integration_lib.tests.test_mcp_client_drawing_open` — `38` passed.
- Ruff: `All checks passed!`.
- `git diff --check`: `PASS`.
- `scripts/verify.ps1` on clean completion head — .NET `238` passed; offline
  Python JUnit `3386` with zero failures/errors/skips (`3306` passed, `21`
  deselected, `80` subtests); offline IPC JUnit `134` clean; causal-RED
  expected one negative failure handled; real-data `2` unavailable skips;
  AutoCAD Mechanical `17` unavailable skips; AutoCAD live and M2 `NOT RUN`.

## Review boundary

The remediation is pushed at completion head `486e2dd72911c5b67b59216a2877b338e03eddc4`.
Fresh SOL review is required before any live proof. No source, candidate,
accepted drawing, or production CAD state was mutated in this iteration.
