# Post-Harness Live Foreground Boundary — Iteration 120

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-119 clear review  
Executor HEAD before this docs-only record: `369d8e38180e9aa3f6e23ed8e338b7f844092af5`

## Epoch classification

Exactly one new disposable read-only live epoch was executed with the
corrected harness and the existing `WindowsAutoCADStartTabSession` owner. The
session reached `document-ready=True`, but the existing command-bound plugin
bootstrap raised `MCPToolError: WINDOW_FOREGROUND_INVALID`. The failure
occurred before the production `drawing_open` call (`candidate_open_call_count=0`),
so the post-repair raw-LISP ACK placement was not exercised in this epoch.

`DotNetIPCClient.health` was not called. This is a foreground/bootstrap
boundary classification, not candidate activation evidence and not a product
PASS.

## Cleanup and integrity

The owned AutoCAD PID was absent after no-save cleanup. Disposable IPC and
startup-script roots were absent after cleanup with no warnings. The exact
page-1 candidate remained unchanged at SHA-256
`167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`; the
verified DWT remained unchanged at SHA-256
`b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.

The raw proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration120-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane. No key
bytes were read, changed, or removed. The authoritative SourceCustody HMAC
contract was not changed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration120-proof.json; document-ready=True; failure=WINDOW_FOREGROUND_INVALID during plugin bootstrap; candidate_open_call_count=0; health_call_count=0; PID/IPC/scripts cleaned; candidate and DWT hashes unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=WINDOW_FOREGROUND_INVALID_DURING_PLUGIN_BOOTSTRAP
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and one bounded foreground/bootstrap diagnostic or corrective action; do not retry candidate activation, call health, or mutate source/DXF/CAD until authorized
HUMAN_GATE=NO
```
