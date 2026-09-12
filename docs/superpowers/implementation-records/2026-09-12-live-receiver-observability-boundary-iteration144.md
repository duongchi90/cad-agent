# Live Receiver Observability Boundary — Iteration 144

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-143 clear review and exactly one disposable read-only live diagnostic epoch  
Executor HEAD before this docs-only record: `57664e1`

## Bounded diagnostic epoch

Exactly one disposable AutoCAD Mechanical 2027 epoch was run against the same
hash-bound page-1 candidate. AutoCAD reached `document_ready=True`. The
diagnostic wrapped only the disposable harness binding and recorded the native
`PostMessageW` calls, raw-LISP callback lifecycle, marker-path observation, and
the existing Python ACK result. It did not change production code or the
candidate and did not run downstream candidate identity or health.

## Causal evidence

- The raw-LISP callback was invoked exactly once with the generated expression
  (`raw_expression_length=994`) and returned to the Python caller.
- The disposable native probe recorded `997` `WM_CHAR` (`0x0102`) posts to
  receiver HWND `1377516`; every `PostMessageW` result was `1`.
- The existing Python ACK observer finished with
  `MCPTimeoutError: RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED`.
- No marker file was observed during the bounded wait. Because the current
  native trigger exposes enqueue success but no receiver callback/queue-drain
  receipt, `receiver_consumed_full_frame`, `evaluator_entered_expression`, and
  `marker_write_attempted_and_succeeded` remain `NOT_PROVEN`; they are not
  collapsed into `False`.
- `python_ack_observer_read_exact_token=False`; downstream candidate identity
  and health were not run (`health_call_count=0`).

This is the first unsatisfied boundary: the existing live owner has no direct
receiver-consumption observable. The live timeout still cannot be honestly
classified as `NOT_CONSUMED`, `CONSUMED_NOT_EVALUATED`, or
`EVALUATED_MARKER_NOT_WRITTEN_OR_NOT_OBSERVED` from this run alone.

## Cleanup and integrity

- AutoCAD PID `25644` was absent after cleanup; cleanup warnings were empty.
- Disposable scripts and IPC roots were absent after cleanup.
- Candidate SHA-256 before and after:
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.
- Default DWT SHA-256 before and after:
  `b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.

The raw proof is retained outside Git at
`C:\\temp\\cad-agent-task6-live-20260911\\candidate-activation-diagnostic-iteration144-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\\temp\\cad-agent-task6-live-20260911\\candidate-activation-diagnostic-iteration144-proof.json; exactly one authorized disposable live diagnostic; document_ready=True; one raw-LISP callback; 997 WM_CHAR posts to receiver HWND 1377516; all PostMessageW results=1; receiver/evaluator/marker observables NOT_PROVEN because current owner exposes enqueue only; python_ack_observer_read_exact_token=False; failure=MCPTimeoutError: RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED; candidate identity/health NOT RUN; health_call_count=0; cleanup clean; candidate/DWT unchanged; no retry or source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RECEIVER_CONSUMPTION_OBSERVABLE_ABSENT_IN_CURRENT_LIVE_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize one bounded design/reuse decision for an approved receiver-side acknowledgement seam or supported evaluation oracle, with no production mutation or live retry until that seam is approved
HUMAN_GATE=NO
```
