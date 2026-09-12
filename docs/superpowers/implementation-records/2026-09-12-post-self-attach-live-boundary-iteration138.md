# Post-Self-Attach Live Boundary — Iteration 138

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-137 clear review and exactly one disposable full live epoch  
Executor HEAD: `813adb8`

## Bounded live epoch

Exactly one disposable AutoCAD Mechanical 2027 session was started against the
same hash-bound page-1 candidate. `document_ready=True` was reached. The run
then stopped at the existing raw-LISP receiver boundary because the required
same-expression ACK was not confirmed:
`MCPTimeoutError: RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED`.

The candidate open operation was not allowed to proceed to the downstream
active-document identity and health assertions. `health_call_count=0` and
`raw_lisp_ack_returned=False`. This epoch did not retry and did not mutate
source, candidate DXF, customer drawing, CAD state, or the key policy.

## Cleanup and integrity

- Live epoch started: `True`; AutoCAD PID `26444` was absent after cleanup.
- Cleanup warnings: none; disposable scripts and IPC roots were absent after
  cleanup.
- Candidate path:
  `C:\\temp\\cad-agent-real-pdf-current-main-iter80-run\\staged\\dxf\\page_01.dxf`.
- Candidate SHA-256 before and after:
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.
- Default DWT SHA-256 before and after:
  `b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.
- Candidate open call count was recorded as `1` by the harness; the raw-LISP
  ACK boundary remained unsatisfied before downstream assertions.

The raw proof is retained outside Git at
`C:\\temp\\cad-agent-task6-live-20260911\\candidate-activation-iteration138-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\\temp\\cad-agent-task6-live-20260911\\candidate-activation-iteration138-proof.json; exactly one disposable full live epoch; document_ready=True; raw_lisp_ack_returned=False; failure=MCPTimeoutError: RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED; candidate/health downstream NOT RUN; health_call_count=0; cleanup warnings=0; AutoCAD PID 26444 absent; candidate SHA-256 unchanged at 167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714; default DWT SHA-256 unchanged at b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42; no retry or source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED_AFTER_SELF_ATTACH_REPAIR
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one offline characterization of the existing raw-LISP receiver ACK path and its disposable harness, with no production mutation, live retry, plugin/candidate/health, visual/dimension, source/DXF/CAD, or key-policy mutation until the characterization is reviewed
HUMAN_GATE=NO
```
