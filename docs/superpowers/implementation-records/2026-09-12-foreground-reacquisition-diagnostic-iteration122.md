# Foreground Reacquisition Diagnostic — Iteration 122

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-121 bounded foreground-reacquisition diagnostic  
Executor HEAD before this docs-only record: `fd1e248a7214795db528079138263c37490850ce`

## Diagnostic classification

Exactly one disposable foreground-reacquisition diagnostic was executed with
the existing `WindowsAutoCADStartTabSession` owner. The session reached
`document-ready=True`. The owned AutoCAD top-level window was HWND `1771118`,
PID `8740`, class `AfxMDIFrame140u`, title
`Autodesk AutoCAD 2027 - [Start]`.

The initial foreground was HWND `591914`, PID `3208`, class
`Chrome_WidgetWin_1`, title `ChatGPT`. Because the foreground was foreign, the
diagnostic invoked exactly one existing bounded sequence:
`ShowWindow(1771118, 9)` followed by `SetForegroundWindow(1771118)`. The former
returned `true`; the latter returned `false`. Ten immediate 200-ms-spaced
samples then continued to observe the same ChatGPT HWND/PID/class/title. The
result is classified as `FOREGROUND_REACQUIRE_DENIED`.

No plugin bootstrap, command delivery, raw-LISP, FileIPC, candidate open, or
health call was invoked. This is a session-level foreground acquisition
finding, not candidate activation evidence and not a product PASS.

## Cleanup and integrity

The owned AutoCAD PID was absent after no-save cleanup and the disposable
scripts root was absent. Cleanup reported
`START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`, which is secondary to the
foreground finding; no owned AutoCAD process remained after the bounded cleanup
check. The exact page-1 candidate remained unchanged at SHA-256
`167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.

The raw proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\foreground-reacquisition-diagnostic-iteration122-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane. No key
bytes were read, changed, or removed. The authoritative SourceCustody HMAC
contract was not changed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\temp\cad-agent-task6-live-20260911\foreground-reacquisition-diagnostic-iteration122-proof.json; document-ready=True; owned AutoCAD HWND=1771118/PID=8740; initial foreground HWND=591914/PID=3208/class=Chrome_WidgetWin_1/title=ChatGPT; exactly one ShowWindow invocation returned true; exactly one SetForegroundWindow invocation returned false; ten post-attempt samples remained ChatGPT; classification=FOREGROUND_REACQUIRE_DENIED; plugin/raw-LISP/FileIPC/candidate/health not invoked; owned PID absent after cleanup; candidate unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=FOREGROUND_REACQUIRE_DENIED_DURING_BOOTSTRAP
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and one smallest bounded session-level foreground repair or diagnostic that preserves the fail-closed exact-HWND guard; do not retry candidate activation, invoke plugin bootstrap, call health, or mutate source/DXF/CAD until authorized
HUMAN_GATE=NO
```
