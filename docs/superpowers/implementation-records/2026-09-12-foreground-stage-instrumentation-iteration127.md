# Foreground Stage Instrumentation — Iteration 127

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-126 material finding and one offline diagnostic instrumentation repair  
Executor HEAD: `0e18218`

## Bounded repair

The production foreground handoff helper now keeps the external
`MCPToolError("WINDOW_FOREGROUND_INVALID")` contract unchanged while attaching
a bounded internal diagnostic to the exception. The diagnostic records the
first failing stage among `ATTACH_FAILED`, `SHOW_OR_SET_NATIVE_ERROR`,
`EXACT_HWND_READBACK_MISMATCH`, and `DETACH_FAILED`, together with the
foreground HWND/PID before the handoff and immediately after the SetForegroundWindow
readback and detach attempt. A secondary detach failure is retained without
overwriting an earlier primary stage.

No source-custody key, PDF, DXF, drawing, plugin, raw-LISP, FileIPC, or live
desktop state was changed.

## Verification

- Focused `test_file_ipc_windows_trigger.py -m "not causal_red"`: 24 passed,
  1 deselected, 3 subtests.
- Focused DotNetIPC gate: 82 passed, 52 subtests passed.
- Ruff passed for the focused and repository scopes.
- `scripts/verify.ps1` completed successfully.
- Offline JUnit: 3400 tests, 0 failures, 0 errors, 0 skipped.
- Causal-RED oracle: 1 test, 1 expected failure.
- Real-data unavailable-state probe: 2 skipped.
- AutoCAD Mechanical unavailable-state probe: 17 skipped.
- AutoCAD live marker and M2 marker: `NOT RUN` because no live prerequisites
  were supplied.
- `git diff --check` passed and the worktree remained clean after verification.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed. This request does not
require or authorize weakening that integrity boundary.

## Canonical checkpoint

```text
STATE=VERIFIED
EVIDENCE=This record; pushed code commit 0e18218; focused Windows-trigger 24 passed/1 deselected/3 subtests; DotNetIPC 82 passed/52 subtests; Ruff passed; scripts/verify.ps1 completed; offline JUnit tests=3400 failures=0 errors=0 skipped=0; causal-red tests=1 failures=1 expected; real-data tests=2 skipped; AutoCAD tests=17 skipped; live marker/M2 NOT RUN; git diff --check clean; worktree clean; no live rerun or source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_FOREGROUND_STAGE_INSTRUMENTATION_LIVE_DIAGNOSTIC_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review, then if clear run exactly one disposable read-only live diagnostic or live epoch with the internal foreground stage exposed in proof; do not infer raw-LISP ACK, candidate identity, health, visual fidelity, or dimensions and do not mutate source/DXF/CAD
HUMAN_GATE=NO
```
