# Self-Attach Repair — Iteration 137

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-136 material finding and one offline TDD repair  
Executor HEAD: `8cc9bcf`

## Bounded repair

The existing foreground helper now treats equal caller and foreground thread
IDs as `attach_not_required`. It does not call `AttachThreadInput` for either
attach or detach in that case, then continues through the existing
`ShowWindow`, one `SetForegroundWindow`, and exact-HWND readback path. The
existing attach/detach-in-`finally` path remains unchanged when the thread IDs
differ, and the public `WINDOW_FOREGROUND_INVALID` contract and current stage
taxonomy remain intact.

The causal regression proves the self-attach case does not call
`AttachThreadInput` and still reaches the foreground activation path. No live
retry, plugin/raw-LISP delivery, candidate/health operation, source/DXF/CAD
mutation, or SourceCustody key-policy change occurred.

## Verification

- Focused `test_file_ipc_windows_trigger.py -m "not causal_red"`: 26 passed,
  1 deselected, 3 subtests.
- Focused DotNetIPC gate: 82 passed, 52 subtests passed.
- Ruff passed for the focused and repository scopes.
- `scripts/verify.ps1` exited `0` after clean-tree preflight at `8cc9bcf`.
- .NET gate: 238 passed.
- Offline Python: 3322 passed, 21 deselected, 80 subtests.
- Offline JUnit: 3402 tests, 0 failures, 0 errors, 0 skipped.
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
EVIDENCE=This record; pushed code commit 8cc9bcf; focused Windows-trigger 26 passed/1 deselected/3 subtests; DotNetIPC 82 passed/52 subtests; Ruff passed; scripts/verify.ps1 exit 0; .NET 238 passed; offline Python 3322 passed/21 deselected/80 subtests; offline JUnit tests=3402 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD 17 skipped; live marker/M2 NOT RUN; git diff --check clean; worktree clean; no live retry or source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_SELF_ATTACH_REPAIR_LIVE_FOREGROUND_HANDOFF_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only live epoch against the same hash-bound page_01.dxf, requiring foreground handoff, existing plugin/bootstrap, same-expression raw-LISP ACK, exact active-document identity, one health call, and no-save cleanup; stop at the first causal failure
HUMAN_GATE=NO
```
