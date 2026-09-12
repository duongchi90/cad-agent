# Post-Handoff Live Boundary — Iteration 124

Date: 2026-09-12 (Asia Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-123 clear review and one disposable live epoch  
Executor HEAD before this docs-only record: `3ead699c7040b1d2f826cca600253b7b285f2288`

## Epoch classification

Exactly one disposable read-only live epoch was started against the same
hash-bound page-1 candidate using the repaired foreground owner. AutoCAD
reached `document-ready=True`, but the first trigger/bootstrap call stopped at
the production helper's native binding lookup with
`AttributeError: function 'GetCurrentThreadId' not found`.

The failure is a production repair defect: `GetCurrentThreadId` is a
`kernel32` API, while the new helper looked it up on `user32`. The epoch did
not reach plugin bootstrap completion, raw-LISP ACK, candidate `drawing_open`,
active-document identity, or `DotNetIPCClient.health`. No retry was made.

## Cleanup and integrity

Cleanup completed without warnings. The owned AutoCAD PID and disposable IPC
and script roots were absent afterward. The exact page-1 candidate remained
unchanged at SHA-256
`167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`; the
verified DWT remained unchanged at SHA-256
`b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.

The raw proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration124-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane. No key
bytes were read, changed, or removed. The authoritative SourceCustody HMAC
contract was not changed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration124-proof.json; document-ready=True; failure=AttributeError: function 'GetCurrentThreadId' not found; candidate_open_call_count=0; raw_lisp_ack_returned=False; health_call_count=0; cleanup warnings=none; PID/IPC/scripts cleaned; candidate and DWT hashes unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=GETCURRENTTHREADID_BOUND_TO_WRONG_WIN32_DLL
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization for one offline TDD correction that obtains GetCurrentThreadId from kernel32 while keeping user32 AttachThreadInput/ShowWindow/SetForegroundWindow, exact-HWND fail-closed readback, and no live retry until offline verification passes
HUMAN_GATE=NO
```
