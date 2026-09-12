# Post-Foreground-Diagnostic Live Boundary — Iteration 129

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-128 clear review and exactly one disposable read-only full live epoch  
Executor HEAD before this docs-only record: `c7d7756`

## Epoch classification

Exactly one disposable full live epoch was run against the established
hash-bound candidate `page_01.dxf`. AutoCAD reached the document-ready
boundary and the existing plugin/bootstrap trigger path was entered. The first
foreground-bound command delivery then failed closed with the public
`MCPToolError("WINDOW_FOREGROUND_INVALID")`.

The new internal diagnostic classified the failure as
`EXACT_HWND_READBACK_MISMATCH`. The observed foreground remained HWND `4786026`
/ PID `14048` before the handoff, immediately after the SetForegroundWindow
readback, and after detach. The owned AutoCAD HWND was therefore not observed
as the exact foreground target. No command message was delivered past this
guard; plugin bootstrap did not complete, and no raw-LISP ACK, candidate open,
active-document identity, or health call was obtained.

## Cleanup and integrity

- `candidate_open_call_count=0`.
- `raw_lisp_ack_returned=False` and `health_call_count=0`.
- Cleanup warnings: none.
- Owned AutoCAD PID, IPC root, and script root were absent afterward.
- Candidate SHA-256 before and after:
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.
- Default DWT SHA-256 before and after:
  `b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.

The raw proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration129-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration129-proof.json; exactly one authorized disposable full live epoch; failure=MCPToolError: WINDOW_FOREGROUND_INVALID; internal_stage=EXACT_HWND_READBACK_MISMATCH; foreground_before=HWND 4786026/PID 14048; foreground_after_set=HWND 4786026/PID 14048; foreground_after_detach=HWND 4786026/PID 14048; candidate_open_call_count=0; raw_lisp_ack_returned=False; health_call_count=0; cleanup warnings=none; PID/IPC/scripts cleaned; candidate and DWT unchanged; no source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=EXACT_HWND_READBACK_MISMATCH_DURING_PLUGIN_BOOTSTRAP_TRIGGER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization for one smallest bounded foreground handoff repair or diagnostic addressing the exact readback mismatch; do not retry the full epoch, invoke raw-LISP/candidate/health, or mutate source/DXF/CAD until authorized
HUMAN_GATE=NO
```
