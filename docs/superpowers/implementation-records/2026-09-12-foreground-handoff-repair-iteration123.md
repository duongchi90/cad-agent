# Foreground Handoff Repair — Iteration 123

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-122 offline TDD foreground-owner repair  
Executor HEAD after implementation: `f4b2b6012af289afc14f4d2dd55bbcd0b8ebbc19`

## Bounded repair

The existing Windows foreground owner now uses a private bounded handoff
helper. If the verified owned AutoCAD HWND is not foreground, the helper
identifies the current foreground thread, attaches the caller/input thread to
it with `AttachThreadInput`, performs the existing
`ShowWindow(owned_hwnd, 9)` and `SetForegroundWindow(owned_hwnd)` sequence once,
then detaches in `finally`. It requires exact owned-HWND readback before
success and preserves `WINDOW_FOREGROUND_INVALID` on attach failure, native
error, detach failure, or any exact-HWND mismatch. The existing per-character
identity and foreground checks remain unchanged.

No plugin bootstrap, raw-LISP transport, FileIPC, candidate/source/DXF/CAD
behavior, key-free `DRAFT_REFERENCE` policy, or SourceCustody HMAC contract was
changed.

## TDD and verification

The new offline tests cover attach-success/reacquire with detach, attach
failure before show, detach on native error, and exact-HWND mismatch after
detach. The pre-change RED run showed all four new helper tests failing because
the helper was absent; the pre-existing causal-red negative oracle also failed
as designed. After the repair, focused Windows-trigger verification passed 23
tests with the causal-red marker excluded, plus 3 subtests; DotNetIPC focused
verification passed 82 tests with 52 subtests; Ruff passed.

Authoritative `scripts/verify.ps1` completed with exit 0:

- .NET: 238 passed, 0 failed.
- Offline Python: 3319 passed, 21 deselected, 80 subtests.
- Offline JUnit: 3399 tests, 0 failures, 0 errors, 0 skipped.
- Causal-red negative oracle: 1 expected failure.
- Real-data: 2 skipped because private inputs were unavailable.
- AutoCAD Mechanical: 17 skipped because live prerequisites were unavailable.
- Live marker and M2 benchmark: `NOT RUN`.
- Repository clean at verification start and end; `git diff --check` clean.

No live epoch was run after this offline repair. The exact page-1 candidate
remains hash-bound at SHA-256
`167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.

## Canonical checkpoint

```text
STATE=VERIFIED
EVIDENCE=This record; pushed code commit f4b2b6012af289afc14f4d2dd55bbcd0b8ebbc19; focused Windows-trigger 23 passed/1 deselected/3 subtests; DotNetIPC 82 passed/52 subtests; Ruff passed; scripts/verify.ps1 exit 0; .NET 238 passed; offline Python 3319 passed/21 deselected/80 subtests; offline JUnit tests=3399 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD 17 skipped; live marker/M2 NOT RUN; clean tree; no live rerun or source/DXF/CAD mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_REPAIR_LIVE_FOREGROUND_HANDOFF_AND_RAW_LISP_ACK_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review, then if clear run exactly one disposable read-only live epoch with the repaired foreground owner against the same hash-bound page_01.dxf; stop at first causal failure and do not infer visual/dimension success
HUMAN_GATE=NO
```
