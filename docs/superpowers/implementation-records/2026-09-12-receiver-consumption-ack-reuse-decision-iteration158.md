# Receiver-Consumption ACK Reuse Decision — Iteration 158

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / raw-LISP delivery boundary  
Reviewed executor HEAD: `e66a7d74a78e93dce425049427a6e4b3784cd21f`

## Authority and scope

Fresh SOL review of the test-only causal characterization required one
read-only owner/history inspection. This step inventories the existing
Windows/raw-LISP delivery and receipt owners and decides whether a
receiver-consumption acknowledgement can be reused. It does not authorize
production code, a live retry, dispatcher/File IPC, viewport, source, DXF,
candidate, drawing, or key-policy mutation.

## Existing owner and receipt map

| Boundary | Existing owner | What it proves | Decision |
| --- | --- | --- | --- |
| Native raw-LISP framing and delivery | `mcp_integration_lib/mcp_client.py::_make_windows_text_trigger`; `make_windows_lisp_trigger` delegates directly | Exact owned visible `MDIClient`, PID/foreground checks, UTF-16LE `ESC ESC + text + CR`, and per-unit `PostMessageW` enqueue | Keep unchanged; return/enqueue success is not a receipt |
| Native managed dispatcher delivery | `mcp_integration_lib/dotnet_ipc.py::make_windows_dotnet_dispatch_trigger` | The same bounded `WM_CHAR`/`PostMessageW` enqueue discipline for `CADAGENT_DISPATCH` | Keep unchanged; no receiver ACK is exposed |
| Raw-LISP evaluator marker | `FileIPCLiveMCPClient._send_raw_lisp_with_ack`; existing marker writer/observer | Exact request-owned path/token readback when the AutoLISP expression reaches the marker form | Reuse only as a combined evaluator receipt; it cannot expose queue consumption separately |
| Dispatcher operation result | `FileIPCLiveMCPClient._dispatch` + `make_windows_dispatch_trigger` + existing `mcp_dispatch.lsp` result envelope | Claim-bound terminal operation result after the dispatcher has received/evaluated the request | Reuse unchanged downstream; it cannot acknowledge pre-dispatch bootstrap receipt |
| Offline receiver model | `RecordingUser32.receiver_queue` / `drain_receiver_queue` in `test_file_ipc_windows_trigger.py` | A test-only distinction between enqueue and supplied receiver consumption | Keep as characterization only; it is not a production protocol |

The production inventory contains no receiver callback, window-procedure hook,
queue-drain API, `GetMessage`/`PeekMessage`/`DispatchMessage` observation,
AutoCAD evaluator callback, or other semantic receipt attached to the
`PostMessageW -> AutoCAD command receiver` seam. The only production
`PostMessageW` uses are the raw-LISP/text trigger, the managed dispatch trigger,
and disposable top-level close request.

The current `mcp_dispatch.lsp::mcp-op-drawing-open` already validates the
optional `read_only` Boolean and forwards `true` to `vla-Open`; no dispatcher
compatibility repair is identified by this inspection. The current live
failure occurs earlier, at the raw-LISP startup evaluator-entry boundary.

## Historical owner decision

Commit `a0910a5` intentionally replaced `SendMessageTimeoutW` with
`PostMessageW` and restored asynchronous enqueue semantics. Its history and
the current causal RED establish that `PostMessageW=TRUE` is not semantic
execution. Reverting to synchronous delivery, adding COM/ROT, adding a second
transport, or switching to a new managed opening operation would be a
speculative transport/architecture change, not reuse of an existing owner.

The existing marker ACK implemented in the raw-LISP opening owner is the
smallest supported semantic oracle currently available: an exact marker proves
that AutoCAD reached and evaluated the marker form. It does not prove the
internal Windows queue transition independently. Therefore it cannot be
renamed or classified as a receiver-consumption ACK.

## Causal evidence

At the reviewed HEAD, the focused Windows-trigger characterization has:

```text
PostMessageW result: TRUE for every framed WM_CHAR
supplied receiver-consumption observation: absent/false
classification: POSTMESSAGE_ENQUEUED_BUT_RECEIVER_CONSUMPTION_UNOBSERVED
```

The intentional causal RED
`test_enqueue_true_without_receiver_consumption_is_causal_red` fails exactly
because enqueue-only evidence is not accepted as `RECEIVER_CONSUMED`. The
positive `receiver_consumption_ack` case is explicitly injected by the test
double and is not evidence that the production owner has such an ACK.

The marker-only characterization separately proves that the same expression
and exact frame can be classified as `ENQUEUED_ONLY` or `RECEIVER_CONSUMED`
only when a receiver-consumption observation is supplied by the model. It does
not create that observation in AutoCAD.

Focused non-RED evidence is `31 passed, 1 deselected, 3 subtests`; ruff passed.
The authoritative `scripts/verify.ps1` completed with exit code 0 at this
HEAD: offline JUnit `3413` with zero failures/errors, C# `238` passed, .NET IPC
`134` passed, one intentional causal RED, real-data `2 SKIP`, AutoCAD `17 SKIP`,
and live/M2 `NOT RUN`. `git diff --check` was clean before this documentation
step.

## Decision

```text
RECEIVER_CONSUMPTION_ACK_GENUINELY_MISSING=YES
EXISTING_SEMANTIC_ORACLE=exact same-expression AutoLISP marker readback
EXISTING_OPERATION_ORACLE=claim-bound File IPC result after dispatcher readiness
RECEIVER_ONLY_ORACLE=NONE_IN_CURRENT_PRODUCTION_OWNER
```

No specific missing or miswired existing-owner acknowledgement was found that
could be fixed by a safe local patch. The true receiver-only ACK would require
an approved AutoCAD-side receiver/evaluator observation mechanism; that is a
new design/owner boundary, not an existing capability to wire in. Until such a
design is approved, the honest state remains
`RAW_LISP_RECEIVER_OR_EVALUATOR_RECEIPT_NOT_PROVEN` and no live retry or
downstream operation is justified.

## Minimal future write-set and RED, if separately approved

The smallest future write-set is limited to the existing raw-LISP owner,
one receiver/evaluator observation adapter owned by the supported AutoCAD
boundary, its focused contract tests, and one dated evidence record. It must
not change public IPC schemas, add a second transport, restore
`SendMessageTimeoutW`, alter SourceCustody, or touch source/DXF/CAD state.

The required causal RED is the existing negative contract: all
`PostMessageW` calls return `TRUE` while the receiver observation is absent,
and the adapter must remain non-success. GREEN may be claimed only from an
actual owner-supplied receiver/evaluator receipt; a test-double queue drain or
the native enqueue return cannot satisfy it. No implementation is made by
this record.

## Canonical checkpoint

```text
STATE=CHARACTERIZED
HEAD=e66a7d74a78e93dce425049427a6e4b3784cd21f
EVIDENCE=This record; mcp_integration_lib/mcp_client.py; mcp_integration_lib/dotnet_ipc.py; mcp_integration_lib/mcp_dispatch.lsp; test_file_ipc_windows_trigger.py causal RED; focused 31 passed/1 deselected/3 subtests; scripts/verify.ps1 exit 0; historical commit a0910a5; no production/live/dispatcher/FileIPC/viewport/source/DXF/CAD/key mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RECEIVER_CONSUMPTION_ACK_GENUINELY_MISSING_IN_CURRENT_PRODUCTION_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact-head reuse decision; if accepted, choose one approved semantic boundary and its owner before any production patch or live epoch
HUMAN_GATE=NO
```
