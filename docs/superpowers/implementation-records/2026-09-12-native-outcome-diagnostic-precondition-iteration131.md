# Native Outcome Diagnostic Precondition — Iteration 131

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-130 clear review and one disposable read-only foreground/native-outcome diagnostic  
Executor HEAD before this docs-only record: `d4d91f6`

## Bounded diagnostic

Exactly one disposable AutoCAD Mechanical session was started with the
established `WindowsAutoCADStartTabSession` owner and the existing
`CADAGENT_DISPATCH` startup-script boundary. AutoCAD reached
`document_ready=True`. The owned target was HWND `1115332`, PID `21416`, thread
`23412`; it was already the exact foreground window before the instrumented
helper was called.

The helper therefore returned through its existing exact-foreground early
guard. The captured native call list contains only `GetForegroundWindow`; no
`AttachThreadInput`, `ShowWindow`, `SetForegroundWindow`, or detach call was
made. Consequently, the requested native return outcomes were not observed in
this diagnostic. No plugin bootstrap, raw-LISP, candidate, health, visual, or
dimension path was entered.

## Cleanup and integrity

- Foreground before and after: HWND `1115332`, PID `21416`, thread `23412`.
- `foreground_handoff_succeeded=True` means the exact precondition held; it
  does not mean a handoff was attempted.
- `native_calls=[GetForegroundWindow]`; attach/ShowWindow/SetForegroundWindow/
  detach outcomes: not observed.
- Cleanup warnings: none; owned PID and stage root were absent afterward.
- Default DWT SHA-256 before and after:
  `b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.

The raw proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration131-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration131-proof.json; exactly one authorized disposable live foreground/native-outcome diagnostic; document_ready=True; target=HWND 1115332/PID 21416/thread 23412; foreground_before=HWND 1115332/PID 21416/thread 23412; foreground_after=HWND 1115332/PID 21416/thread 23412; helper returned without handoff; native calls only GetForegroundWindow; attach/ShowWindow/SetForegroundWindow/detach outcomes NOT OBSERVED; plugin/raw-LISP/candidate/health NOT RUN; cleanup clean; DWT unchanged; no source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=FOREGROUND_HANDOFF_NATIVE_OUTCOME_NOT_OBSERVED_BECAUSE_TARGET_ALREADY_FOREGROUND
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization for one bounded disposable diagnostic that establishes a foreign foreground precondition before invoking the instrumented helper, then captures native outcomes; no behavioral repair, full epoch, plugin/raw-LISP/candidate/health, or source/DXF/CAD mutation until authorized
HUMAN_GATE=NO
```
