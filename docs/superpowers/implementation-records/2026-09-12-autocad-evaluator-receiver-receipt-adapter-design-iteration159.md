# AutoCAD Evaluator/Receiver Receipt Adapter Design — Iteration 159

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / raw-LISP startup boundary  
Reviewed executor HEAD: `9d81a09f5f4fe4753fbc444af52412cb2afdfa2c`

## Authorization and boundary

Fresh SOL review accepted one design-only step after the receiver-owner scan.
This record defines the smallest semantic receipt boundary that can be built
from the existing AutoCAD-side primitive. It does not authorize implementation,
live retry, transport substitution, dispatcher/File IPC, viewport, source, DXF,
candidate, drawing, or key-policy mutation.

The design deliberately does not promise an independent Windows queue
consumption signal. The supported boundary is a combined AutoLISP
receiver/evaluator receipt: the exact marker is written only after AutoCAD has
accepted and evaluated the marker form in the expression. Internal queue
transitions remain `NOT_SEPARATELY_OBSERVABLE`.

## Supported existing mechanism

The existing AutoCAD-side primitive is the fixed-token AutoLISP marker writer
`_start_tab_stage_marker_expression`, sent as part of the same owner-built
expression through the existing `raw_lisp_trigger`. The existing observers are
`_wait_for_evaluator_entry_ack`, `_wait_for_completion_ack`, and
`FileIPCLiveMCPClient._send_raw_lisp_with_ack`.

This mechanism is supported by the current AutoCAD/AutoLISP boundary already
used by the repository: `open` the request-owned marker path, `write-line` the
fixed token, and `close` the file. The Python owner observes the exact path and
exact token under the already validated IPC root. It does not require a new
Win32 API, a managed evaluator hook, COM/ROT, a named pipe, or a second
transport.

The existing `PostMessageW` trigger remains an enqueue primitive. Its return
value is retained only as delivery-attempt evidence and can never satisfy this
receipt contract.

## Exact receipt contract

For one known owner-built expression, the private adapter must:

1. accept one already validated request-owned marker path and one fixed token;
2. reject a path conflict, root drift, invalid token, or expression placement
   that cannot preserve the existing `progn` semantics;
3. build one same-expression marker form using the existing marker writer;
4. call the existing `raw_lisp_trigger` exactly once;
5. wait only within the existing timeout for the exact marker path to contain
   exactly the expected ASCII token;
6. return a receipt only for exact marker readback, classified as:

```text
raw_lisp_evaluator_receipt=CONFIRMED
receiver_consumption=NOT_SEPARATELY_OBSERVABLE
```

The receipt must not be called `RECEIVER_CONSUMED` unless a future supported
AutoCAD-side owner supplies a separate receiver signal. A trigger return,
`PostMessageW=TRUE`, foreground/PID identity, or a test-double queue drain is
not a receipt.

## Lifecycle and fail-closed rules

- Allocate one unique marker under the validated request-owned IPC root.
- Refuse pre-existing marker conflicts and keep the root identity bound for the
  full send/wait/cleanup lifecycle.
- Send one expression only. There is no implicit retry, command fallback, or
  second transport after an ambiguous result.
- Do not emit or wait for a downstream completion marker when the evaluator
  receipt is absent.
- On trigger error, missing marker, wrong token, unreadable marker, timeout, or
  root drift, return the existing public fail-closed error
  `RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED` (or the existing specific
  path/root error) and do not construct the client or invoke downstream
  File IPC.
- Remove the marker on every safe terminal path. If root identity is no longer
  safe, refuse cleanup rather than deleting outside the bound root.
- Keep the current `legacy_fixture_mode` compatibility distinction; it must not
  promote fixture callback behavior to live receipt evidence.

## Owner and minimal future write-set

The adapter belongs in the existing Python raw-LISP owner, not in a new
transport or a new public AutoCAD command. The smallest implementation write
set, only after fresh design clearance and a causal RED, is:

```text
MODIFY=mcp_integration_lib/mcp_client.py
  private receipt construction/placement/classification only;
  preserve PostMessageW, public timeout, cleanup, and legacy behavior
MODIFY=mcp_integration_lib/tests/test_mcp_client_drawing_open.py
  one focused adapter contract owner and negative/positive cases
CREATE=one dated evidence/implementation record and the canonical status entry
FORBIDDEN=PostMessageW transport change; SendMessageTimeoutW; second transport;
  C# public schema/dispatcher; mcp_dispatch.lsp operation change; source/DXF/CAD;
  candidate/viewport; SourceCustody key/HMAC policy
```

The current private marker primitives already cover much of this contract.
Implementation is therefore permitted only if the RED identifies one concrete
missing or miswired behavior in their shared lifecycle; a cosmetic refactor or
renaming is not sufficient.

## Required causal RED and GREEN

The causal RED input is the existing owner-local negative case:

```text
all PostMessageW calls = TRUE
receiver observation = absent
required result = POSTMESSAGE_ENQUEUED_BUT_RECEIVER_CONSUMPTION_UNOBSERVED
```

The adapter must remain non-success in that case. The positive offline case may
use an injected marker writer to prove exact path/token and cleanup behavior,
but the test must classify it as `raw_lisp_evaluator_receipt=CONFIRMED`, not as
an independent queue-consumption receipt. No test-double queue drain may stand
in for the production AutoCAD-side marker.

The live acceptance oracle, after separate clearance, is exactly one disposable
hash-bound epoch: process-bound HWND and document-ready; one existing raw-LISP
expression containing one exact marker; exact marker readback; then the
existing startup completion/dispatcher gates. If the marker is absent, stop at
`RAW_LISP_RECEIVER_OR_EVALUATOR_RECEIPT_NOT_PROVEN`; do not retry or enter
File IPC/viewport.

## Design decision

```text
STATE=DESIGN_PROPOSED
SUPPORTED_AUTOCAD_SIDE_OBSERVATION=existing same-expression AutoLISP marker write/readback
RECEIVER_ONLY_ACK=NOT_AVAILABLE_IN_CURRENT_OWNER
RECEIPT_SEMANTICS=combined evaluator receipt; internal queue consumption not separately observable
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_OR_EVALUATOR_RECEIPT_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact-head design; only if clear may one causal RED be added for a concrete shared-lifecycle gap, with no live retry or transport change
HUMAN_GATE=NO
```
