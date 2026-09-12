# Raw-LISP ACK Characterization — Iteration 139

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-138 material finding and exactly one offline-only characterization  
Executor HEAD before this docs-only record: `3491d59`

## Characterization scope

The disposable oracle traced the existing raw-LISP ACK owner and its harness
without starting AutoCAD, invoking the plugin, opening a candidate, calling
health, or changing production files. The oracle captured the generated
expression, marker construction, ACK placement, callback forwarding, bounded
wait/cleanup behavior, and the existing native text framing through the offline
`RecordingUser32` boundary.

## Observed owner behavior

- `FileIPCLiveMCPClient.drawing_open()` builds the existing read-only COM
  expression and calls `_send_raw_lisp_with_ack()` once for the ACK boundary.
- `_send_raw_lisp_with_ack()` wraps the expression in one `progn`, creates one
  marker path under the validated IPC root, and places the exact token marker
  before `(vla-activate mcp-open-doc)` in the same expression.
- The callback receives exactly one `str` argument. When the disposable
  callback writes the exact ASCII token to the captured marker path, the
  bounded ACK wait returns and the existing dispatcher/identity path proceeds.
- When the callback does not write the marker, the result is exactly
  `RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED`; no dispatcher call occurs
  before the failure and the marker is removed by the existing `finally`
  cleanup.
- `make_windows_lisp_trigger()` delegates to the existing
  `_make_windows_text_trigger()`. The offline native double observed message
  `0x0102` (`WM_CHAR`) for each UTF-16LE code unit, with exact framing
  `ESC ESC + expression + CR`, and every message targeted the one discovered
  owned MDI receiver.
- The disposable live harness forwards `bindings.raw_lisp_trigger` directly
  into `FileIPCLiveMCPClient`, calls `drawing_open(..., read_only=True)` once,
  and observes the ACK sender return; it does not provide an independent
  receiver-consumption signal.

## Causal boundary map

| Observable boundary | Existing owner | Cheapest causal oracle |
| --- | --- | --- |
| Receiver discovery, foreground, and `WM_CHAR` enqueue/framing | `_make_windows_text_trigger()` | `RecordingUser32` capture of receiver, message IDs, UTF-16LE units, and framing |
| Expression marker construction, callback argument, ACK wait, and cleanup | `_send_raw_lisp_with_ack()` | disposable callback capture with exact-marker and missing-marker branches |
| Marker position relative to activation | `drawing_open()` plus `_send_raw_lisp_with_ack()` | assert token position precedes `(vla-activate mcp-open-doc)` |
| Live callback forwarding and ACK observation | `candidate-activation-iteration116.py` | static harness inventory plus callback capture; no live retry |

The live timeout remains intentionally unresolved among receiver
non-consumption, text delivery/framing, marker construction/path, marker write,
and harness observation. The characterization does not infer one cause from
the timeout alone.

## Evidence and safety

- Disposable proof:
  `C:\\temp\\cad-agent-task6-live-20260911\\raw-lisp-ack-characterization-iteration139-proof.json`.
- `production_files_modified=False`; `live_epoch_started=False`.
- Positive marker branch: callback argument count `1`, type `str`; marker was
  under the IPC root; marker preceded activation; callback occurred before the
  dispatcher ping; IPC root was empty after cleanup.
- Missing-marker branch: exact timeout; one callback; no dispatches before
  failure; IPC root empty after cleanup.
- Text framing branch: `WM_CHAR` message ID `0x0102`; 24 code units; framing
  matched exactly and ended in carriage return; all posts targeted receiver
  HWND `4353` in the native double.
- Harness inventory confirmed direct `bindings.raw_lisp_trigger` forwarding,
  one `drawing_open` call site, and ACK-sender observation.
- No production mutation, live retry, plugin/bootstrap execution, candidate or
  health operation, source/DXF/CAD mutation, visual/dimension work, or
  key-policy change occurred.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=VERIFIED_CHARACTERIZATION
EVIDENCE=This record; proof C:\\temp\\cad-agent-task6-live-20260911\\raw-lisp-ack-characterization-iteration139-proof.json; production_files_modified=False; live_epoch_started=False; exact callback/marker/order/wait-cleanup characterization; exact WM_CHAR/UTF-16LE framing characterization; direct live-harness forwarding inventory; no production/live/plugin/candidate/health/source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_ACK_CAUSAL_OWNER_NOT_DISTINGUISHED
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one offline-only causal oracle for the cheapest unresolved ACK owner identified by this characterization, preserving the existing public timeout contract and forbidding live retry or production/source/DXF/CAD/key-policy mutation
HUMAN_GATE=NO
```
