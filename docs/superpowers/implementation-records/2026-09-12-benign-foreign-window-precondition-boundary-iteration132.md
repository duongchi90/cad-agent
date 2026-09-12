# Benign Foreign-Window Precondition Boundary — Iteration 132

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-131 material finding and one disposable diagnostic with a benign foreign foreground precondition  
Executor HEAD before this docs-only record: `f66857c`

## Epoch classification

Exactly one disposable AutoCAD session reached `document_ready=True`. The
diagnostic created a separate benign top-level window owned by the diagnostic
harness, not by AutoCAD or the production foreground helper. The benign target
was HWND `787684`, PID `28852`, thread `22856`; the owned AutoCAD target was
HWND `722044`, PID `28764`, thread `22612`.

The benign `SetForegroundWindow` call returned `0`, and the verified
foreground remained another window (HWND `4720738`, PID `1740`, thread
`30476`). Because the foreign precondition was not established, the production
`_reacquire_windows_foreground` helper was not invoked. No AttachThreadInput,
ShowWindow, production SetForegroundWindow, detach, plugin, raw-LISP,
candidate, or health outcome was captured.

The disposable window callback also emitted an `OverflowError` from an
incomplete `DefWindowProcW` signature. This is a harness-only defect and does
not justify a production behavioral repair.

## Cleanup and integrity

- `foreign_precondition_verified=False`.
- `production helper invoked=False`.
- Plugin bootstrap, raw-LISP, candidate open, and health: `NOT RUN`.
- Cleanup warnings: none; owned AutoCAD PID and stage root were absent.
- Default DWT SHA-256 before and after:
  `b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.
- No source, PDF, DXF, CAD, or key-policy path was mutated.

The raw proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration132-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration132-proof.json; exactly one authorized disposable native-outcome diagnostic; document_ready=True; owned target=HWND 722044/PID 28764/thread 22612; benign target=HWND 787684/PID 28852/thread 22856; benign SetForegroundWindow result=0; foreign_precondition_verified=False; production helper NOT INVOKED; plugin/raw-LISP/candidate/health NOT RUN; cleanup clean; DWT unchanged; no source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=FOREIGN_FOREGROUND_PRECONDITION_SETFOREGROUNDWINDOW_FAILED_IN_DISPOSABLE_HARNESS
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization to repair the disposable benign-window callback/signature, re-establish and verify the foreign foreground precondition, then invoke the unchanged production helper exactly once; no production behavioral repair or full live epoch until authorized
HUMAN_GATE=NO
```
