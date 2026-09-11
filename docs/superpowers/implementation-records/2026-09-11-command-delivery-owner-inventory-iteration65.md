# Command-Delivery Owner Inventory — Iteration 65

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`
Evidence/docs head before this record: `a464a298791d65648d2b1944b0f4ce27df7e3da1`

## Authority and boundary

SOL's iteration-64 diagnosis was:

```text
VERDICT=MATERIAL_FINDING
MATERIAL_FINDING=POSTMESSAGE_WM_CHAR_IS_NOT_A_PROVEN_SEMANTIC_AUTOCAD_COMMAND_DELIVERY_OWNER
HUMAN_GATE=NO
```

The authorized action was one non-live reuse-first command-delivery owner
inventory. It explicitly forbade production changes, another live retry, a
second transport, a UI-focus workaround, and arbitrary automation surfaces.

## Existing owner map

The inventory found the following existing owner chain:

```text
mcp_integration_lib/dotnet_ipc.py::DotNetIPCClient.request
  -> atomic request file: cadagent_dotnet_request_<request_id>.json
  -> existing CADAGENT_DISPATCH command trigger
  -> autocad_plugin/.../Commands/CadAgentCommands.cs::Dispatch
  -> CommandContext.GetPendingRequestIds / JsonFileStore.ReadRequest
  -> OperationDispatcher.Dispatch
  -> JsonFileStore.WriteResult
  -> atomic result file: cadagent_dotnet_result_<request_id>.json
  -> DotNetIPCClient bounded poll and contract validation
```

Relevant repository evidence:

- `autocad_plugin/CadAgent.AutoCAD2027/Commands/CadAgentCommands.cs:50-86`
  registers `[CommandMethod("CADAGENT_DISPATCH")]`, reads the oldest pending
  request, dispatches it, writes the result, and reports completion. A
  disposable close is scheduled only after result persistence.
- `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs:63-90`
  enumerates and validates pending request IDs; `:92-123` binds the live
  AutoCAD document, `JsonFileStore`, `OperationDispatcher`, and one-shot Idle
  close scheduler.
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/JsonFileStore.cs:53-110` validates
  and atomically writes/reads the request/result pair keyed by the exact
  request ID.
- `mcp_integration_lib/dotnet_ipc.py:142-214` contains the existing bounded
  `CADAGENT_DISPATCH` trigger; `:712-975` contains the request write, trigger,
  exact result poll, timeout preservation, and result validation.
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/CommandGuardTests.cs:118-176`
  verifies that `CADAGENT_DISPATCH` persists the close result before scheduling
  the post-command close. This is an existing semantic ordering oracle.

The search boundary found no existing `SendStringToExecute`,
`ExecuteInCommandContext`, named-pipe, COM/ROT, or FileSystemWatcher command
owner in the inspected `autocad_plugin`, `mcp_integration_lib`, and `scripts`
surfaces. The only existing command-delivery surfaces relevant to this
boundary are the bounded Win32 message trigger and the .NET File IPC owner.

## Smallest reuse proposal

Do not add a new transport, focus workaround, or raw-LISP acknowledgement
protocol. If a future bounded implementation is authorized, keep the existing
owner chain and use:

```text
existing DotNetIPCClient request/result contract
existing CADAGENT_DISPATCH command owner
matching result file with the same request_id as semantic acknowledgement
```

The smallest seam is the existing command-delivery/receipt boundary, not a new
AutoCAD API. The implementation must remain fail-closed on missing, stale,
foreign, malformed, or mismatched result files and must preserve the current
timeout rule that leaves an uncertain request pair available without an
implicit retry.

This proposal is deliberately conditional. The plugin command owner is not
available before NETLOAD, so the inventory does not claim to solve the earlier
pre-plugin QNEW/bootstrap boundary. It only identifies the cheapest existing
owner to reuse once that prerequisite is independently proven.

## Causal RED oracle

The exact existing causal RED oracle is:

```text
pytest -p no:cacheprovider -q \
  mcp_integration_lib/tests/test_file_ipc_windows_trigger.py \
  -k enqueue_true_without_receiver_consumption_is_causal_red
```

Its fixture returns true from every `PostMessageW` call while modeling false
receiver consumption. The current trigger returns without a handler
acknowledgement, so the test intentionally fails:

```text
1 failed, 1 passed, 18 deselected
AssertionError: PostMessageW TRUE must not stand in for receiver/handler consumption ACK
```

The adjacent enqueue-only/result-owner subset was also run without pytest cache
writes:

```text
pytest -p no:cacheprovider -q mcp_integration_lib/tests/test_dotnet_ipc.py \
  -k "postmessage_true_is_enqueue_only_without_a_semantic_result or posts_exact_dispatch_message_sequence_to_mdi_child or selects_visible_owned_mdi_when_autoCAD_exposes_hidden_mdi_client"
3 passed, 79 deselected in 0.15s
```

For a future GREEN oracle, the same one-request epoch must produce one
validated result file whose `request_id` equals the request, whose operation
matches the request, and whose success/error/payload fields are accepted by
the existing `DotNetIPCClient`; `PostMessageW=True` alone must remain
insufficient.

## Safety and next boundary

- No production code changed.
- No live AutoCAD process, source drawing, candidate, DXF, FileIPC request, or
  accepted artifact was touched.
- No retry or second transport was introduced.
- Fresh SOL diagnosis is required before implementation or another live epoch.
