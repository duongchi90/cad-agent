# Native Outcome Instrumentation — Iteration 130

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-129 material finding and one offline diagnostic-instrumentation extension  
Executor HEAD: `bcbb88b`

## Bounded change

The existing foreground helper now includes the exact target owned HWND/PID,
caller thread ID, foreground thread ID, raw `AttachThreadInput` attach and
detach results, `ShowWindow` return, and `SetForegroundWindow` return in its
bounded internal diagnostic. The existing stage taxonomy, detach-in-`finally`
behavior, exact-HWND fail-closed readback, and public
`MCPToolError("WINDOW_FOREGROUND_INVALID")` contract are unchanged.

The focused regression exercises `EXACT_HWND_READBACK_MISMATCH` and verifies
all requested native outcomes and target identity. No live retry, plugin/raw-
LISP delivery, candidate/health operation, source/DXF/CAD mutation, or
SourceCustody key-policy change occurred.

## Verification

- Focused `test_file_ipc_windows_trigger.py -m "not causal_red"`: 25 passed,
  1 deselected, 3 subtests.
- Focused DotNetIPC gate: 82 passed, 52 subtests passed.
- Ruff passed for the focused and repository scopes.
- `scripts/verify.ps1` exited `0` after clean-tree preflight.
- .NET gate: 238 passed.
- Offline Python: 3321 passed, 21 deselected, 80 subtests.
- Offline JUnit: 3401 tests, 0 failures, 0 errors, 0 skipped.
- Causal-RED oracle: 1 test, 1 expected failure.
- Real-data unavailable-state probe: 2 skipped.
- AutoCAD Mechanical unavailable-state probe: 17 skipped.
- AutoCAD live marker and M2 marker: `NOT RUN` because prerequisites were not
  supplied.
- `git diff --check` passed and the worktree remained clean after verification.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=VERIFIED
EVIDENCE=This record; pushed code commit bcbb88b; focused Windows-trigger 25 passed/1 deselected/3 subtests; DotNetIPC 82 passed/52 subtests; Ruff passed; scripts/verify.ps1 exit 0; .NET 238 passed; offline Python 3321 passed/21 deselected/80 subtests; offline JUnit tests=3401 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD 17 skipped; live marker/M2 NOT RUN; git diff --check clean; worktree clean; no live retry or source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_NATIVE_OUTCOME_INSTRUMENTATION_LIVE_REVIEW_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of the verified native-outcome evidence; await authorization for any live rerun and do not retry the full epoch or mutate source/DXF/CAD/key policy until authorized
HUMAN_GATE=NO
```
