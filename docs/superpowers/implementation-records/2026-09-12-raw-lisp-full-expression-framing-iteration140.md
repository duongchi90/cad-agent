# Raw-LISP Full-Expression Framing Oracle — Iteration 140

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-139 clear review and exactly one offline-only end-to-end causal oracle  
Executor HEAD before this docs-only record: `706b9a3`

## Bounded oracle

The disposable oracle generated the actual ACK-wrapped expression produced by
`FileIPCLiveMCPClient.drawing_open(..., read_only=True)` for the realistic
hash-bound candidate path, then passed that exact string through the existing
`make_windows_lisp_trigger()` / `_make_windows_text_trigger()` owner using the
offline `RecordingUser32` double. It did not start AutoCAD, invoke the plugin,
open a candidate, call health, or modify production files.

## Positive full-expression path

- The callback received exactly one `str` expression of length `949`.
- The expression had the existing single outer `progn` shape and contained the
  unchanged ACK token `CAD_AGENT_DRAWING_OPEN_RECEIVER_EVALUATED`.
- The generated marker path was under the validated IPC root and the marker
  token occurred before `(vla-activate mcp-open-doc)` in the same expression.
- The exact emitted native code units reconstructed to
  `ESC ESC + exact_generated_expression + CR`.
- The reconstructed UTF-16LE bytes matched the expected framed expression
  byte-for-byte across all `952` code units.
- Every emitted message was `WM_CHAR` (`0x0102`), targeted the one discovered
  receiver HWND `4353`, and returned `PostMessageW=1`.
- The disposable ACK marker was removed and the IPC root was empty after the
  success path.

## Injected enqueue failure

The same full-expression route was run through a native double configured with
one successful enqueue followed by one failed enqueue. The observed sequence
was `post_results=[1,0]`, followed by the existing
`WINDOW_DELIVERY_FAILED` error. No File IPC dispatch occurred after the
injected failure and the marker/IPC root cleanup remained clean. This confirms
that a per-unit enqueue failure is an independent causal oracle and cannot be
confused with the later receiver ACK timeout.

## Boundary conclusion

The complete generated `drawing_open` ACK-wrapped expression survives the
existing text-trigger encoding/framing owner byte-for-byte in the offline
boundary. The previous live timeout therefore remains unresolved among actual
receiver non-consumption/evaluation, live native receiver behavior, marker
write/observation, or another live-only condition; this oracle does not infer a
single cause from the timeout.

## Evidence and safety

- Disposable proof:
  `C:\\temp\\cad-agent-task6-live-20260911\\raw-lisp-full-expression-framing-iteration140-proof.json`.
- `production_files_modified=False`; `live_epoch_started=False`.
- No production mutation, live retry, plugin/bootstrap execution, candidate or
  health operation, visual/dimension work, source/DXF/CAD mutation, provider/M2
  work, or key-policy change occurred.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=VERIFIED_CAUSAL_ORACLE
EVIDENCE=This record; proof C:\\temp\\cad-agent-task6-live-20260911\\raw-lisp-full-expression-framing-iteration140-proof.json; actual drawing_open ACK-wrapped expression length 949; 952 UTF-16LE WM_CHAR code units reconstructed byte-for-byte as ESC ESC + expression + CR; marker/token/path/order verified; all positive PostMessageW results=1; injected [1,0] branch returned WINDOW_DELIVERY_FAILED; no dispatch after failure; cleanup clean; production_files_modified=False; live_epoch_started=False; no production/live/plugin/candidate/health/source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=LIVE_RAW_LISP_RECEIVER_CONSUMPTION_OR_EVALUATION_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only live epoch against the same hash-bound page_01.dxf, requiring the existing live raw-LISP receiver ACK and then exact candidate identity plus one health call, with no retry and no visual/dimension/persistence/source/DXF/CAD/key-policy mutation
HUMAN_GATE=NO
```
