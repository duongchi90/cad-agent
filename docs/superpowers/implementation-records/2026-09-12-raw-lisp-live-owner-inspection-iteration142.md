# Raw-LISP Live Owner Inspection — Iteration 142

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-141 material finding and exactly one offline-only owner inspection  
Executor HEAD before this docs-only record: `661dc63`

## Inspection scope

The disposable inspection read the existing Python client, canonical AutoLISP
dispatcher, and approved live harness. It did not start AutoCAD, invoke the
plugin, open a candidate, call health, modify production files, or change the
key policy.

## Owner map

- Native receiver window and text delivery: `mcp_client._make_windows_text_trigger`
  (source lines 1556–1655), exposed to raw-LISP through
  `make_windows_lisp_trigger`. It discovers exactly one visible owned
  `MDIClient`, verifies window identity and foreground, then posts `WM_CHAR`
  code units to that receiver. The framing assignment is at line 1646 and the
  `PostMessageW` call is at line 1653; a zero result is the existing
  `WINDOW_DELIVERY_FAILED` oracle.
- Generated raw-LISP expression and marker: `FileIPCLiveMCPClient.drawing_open`
  (lines 998–1061) delegates to `_send_raw_lisp_with_ack` (lines 1253–1322).
  Python creates the exact token
  `CAD_AGENT_DRAWING_OPEN_RECEIVER_EVALUATED`, marker prefix
  `autocad_mcp_drawing_open_ack_`, validated-root path, and marker-before-
  activation placement.
- AutoCAD evaluation and marker write: the AutoCAD AutoLISP evaluator receives
  the framed expression through the MDIClient input path and executes the
  `open "w"`, `write-line`, and `close` marker expression. This is the first
  owner capable of proving evaluation and marker-write execution; Python only
  constructs the expression and later observes the file.
- ACK observation: `_send_raw_lisp_with_ack` polls `Path.is_file()` and exact
  ASCII `read_text().strip()` until a monotonic deadline, returns the existing
  `RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED` timeout when absent, and
  unlinks the marker in `finally`.
- Live harness forwarding: the approved
  `candidate-activation-iteration116.py` passes
  `bindings.raw_lisp_trigger` directly into `FileIPCLiveMCPClient`, calls
  `drawing_open(..., read_only=True)` once, and observes the ACK sender return.
  It does not independently observe receiver consumption, evaluator entry, or
  marker-write success.
- Dispatcher boundary after ACK: canonical `mcp_dispatch.lsp` owns the later
  File IPC command path (`mcp-read-bounded-file` line 157,
  `mcp-write-result` line 675, and `c:mcp-dispatch` line 1330). It reads
  `autocad_mcp_cmd_*.json`, executes the operation, and writes
  `autocad_mcp_result_*.json`; it is subsequent to the raw-LISP ACK and is not
  the receiver ACK owner.

## Cheapest single causal oracle

Use one offline receiver/evaluator/observer seam double with the exact generated
`drawing_open` expression and exact `ESC ESC + UTF-16LE WM_CHAR + CR` frame.
Record four independent observables:

1. `receiver_consumed_full_frame`;
2. `evaluator_entered_expression`;
3. `marker_write_attempted_and_succeeded`;
4. `python_ack_observer_read_exact_token`.

The classification is:

- `NOT_CONSUMED`: observable 1 is false.
- `CONSUMED_NOT_EVALUATED`: observable 1 is true and observable 2 is false.
- `EVALUATED_MARKER_NOT_WRITTEN_OR_NOT_OBSERVED`: observable 2 is true and
  observable 4 is false, split by observable 3.
- `EVALUATED_AND_OBSERVED`: all four observables are true.

This oracle reuses the existing text-trigger recording owner and bounded Python
observer, but separates receiver consumption and evaluator entry instead of
using the final timeout as a proxy for either. It is the cheapest next causal
test and requires no AutoCAD/live transport.

## Evidence and safety

- Disposable proof:
  `C:\\temp\\cad-agent-task6-live-20260911\\raw-lisp-live-owner-inspection-iteration142-proof.json`.
- `production_files_modified=False`; `live_epoch_started=False`.
- No production mutation, live retry, plugin/candidate/health execution,
  visual/dimension work, persistence, source/DXF/CAD mutation, provider/M2
  work, or key-policy change occurred.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=VERIFIED_OWNER_INSPECTION
EVIDENCE=This record; proof C:\\temp\\cad-agent-task6-live-20260911\\raw-lisp-live-owner-inspection-iteration142-proof.json; owners and source lines mapped for native receiver/framing, drawing_open ACK expression, AutoCAD evaluator/marker write, Python ACK observation, live harness forwarding, and post-ACK File IPC dispatcher; four-observable offline classification oracle defined; production_files_modified=False; live_epoch_started=False; no production/live/plugin/candidate/health/source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=LIVE_RECEIVER_CONSUMPTION_VS_EVALUATION_VS_MARKER_OBSERVATION_NOT_DISTINGUISHED
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one offline-only receiver/evaluator/observer seam oracle using the four independent observables and exact existing expression/framing, then stop for review
HUMAN_GATE=NO
```
