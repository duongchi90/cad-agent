# Post-Kernel32 Live Boundary — Iteration 126

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-125 clear review and one disposable live epoch  
Executor HEAD before this docs-only record: `c408ab7afe3692a5e75b5bfe967fa5f9ef161b45`

## Epoch classification

Exactly one disposable read-only live epoch was executed against the same
hash-bound page-1 candidate with the corrected foreground owner. AutoCAD
reached `document-ready=True`; the first foreground-bound trigger then failed
closed with `MCPToolError: WINDOW_FOREGROUND_INVALID`.

The epoch therefore stopped before plugin bootstrap completion, same-expression
raw-LISP ACK, candidate `drawing_open`, active-document identity, and
`DotNetIPCClient.health`. No retry was made. This confirms the wrong-DLL
boundary from iteration 124 is gone, but does not prove that the new
`AttachThreadInput` handoff can acquire stable exact foreground in the live
desktop session.

## Cleanup and integrity

Cleanup completed without warnings. The owned AutoCAD PID and disposable IPC
and script roots were absent afterward. The exact page-1 candidate remained
unchanged at SHA-256
`167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`; the
verified DWT remained unchanged at SHA-256
`b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.

The raw proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration126-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane. No key
bytes were read, changed, or removed. The authoritative SourceCustody HMAC
contract was not changed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration126-proof.json; document-ready=True; failure=MCPToolError: WINDOW_FOREGROUND_INVALID after corrected kernel32 binding; candidate_open_call_count=0; raw_lisp_ack_returned=False; health_call_count=0; cleanup warnings=none; PID/IPC/scripts cleaned; candidate and DWT hashes unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=WINDOW_FOREGROUND_INVALID_AFTER_KERNEL32_FOREGROUND_HANDOFF
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and one smallest bounded foreground diagnostic or repair preserving the exact-HWND fail-closed contract; do not retry candidate activation, invoke plugin bootstrap, call health, or mutate source/DXF/CAD until authorized
HUMAN_GATE=NO
```
