# Native AttachThreadInput Failure — Iteration 136

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-135 clear review and exactly one disposable native-outcome diagnostic  
Executor HEAD before this docs-only record: `2602077`

## Bounded diagnostic

Exactly one disposable AutoCAD session reached `document_ready=True`. A
separate benign harness-owned window was made the verified exact foreground:
HWND `3540730`, PID `26992`, thread `14952`. The owned AutoCAD target was HWND
`9045722`, PID `21928`, thread `24944`.

The unchanged production `_reacquire_windows_foreground` helper was invoked
exactly once. It captured caller thread ID `14952` and foreground thread ID
`14952`, then called `AttachThreadInput(caller, foreground, True)`, which
returned `0`. The helper classified this as `ATTACH_FAILED` and preserved the
public `MCPToolError("WINDOW_FOREGROUND_INVALID")` contract. `ShowWindow`,
`SetForegroundWindow`, and detach were not called. The diagnostic stopped at
this first native failure.

## Cleanup and integrity

- Foreign precondition: verified exact HWND/PID readback.
- Native attach result: `0` (`ATTACH_FAILED`).
- Plugin bootstrap, raw-LISP, candidate open, and health: `NOT RUN`.
- Cleanup warnings: none; owned PID and stage root were absent.
- Default DWT SHA-256 before and after:
  `b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.
- Candidate/PDF/source/DXF/CAD/key-policy state was untouched.

The raw proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration136-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration136-proof.json; exactly one authorized disposable native-outcome diagnostic; document_ready=True; foreign precondition verified HWND 3540730/PID 26992/thread 14952; owned target HWND 9045722/PID 21928/thread 24944; caller_thread_id=14952; foreground_thread_id=14952; AttachThreadInput attach_result=0; stage=ATTACH_FAILED; ShowWindow/SetForegroundWindow/detach NOT CALLED; production helper invoked once; plugin/raw-LISP/candidate/health NOT RUN; cleanup clean; DWT unchanged; no source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=ATTACH_THREAD_INPUT_ATTACH_RESULT_FALSE
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization for one smallest offline TDD repair or diagnostic addressing the AttachThreadInput attach-result failure while preserving the exact-HWND fail-closed contract; no live retry, plugin/raw-LISP/candidate/health, or source/DXF/CAD mutation until authorized
HUMAN_GATE=NO
```
