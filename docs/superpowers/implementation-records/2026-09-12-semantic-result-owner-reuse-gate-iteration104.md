# Semantic Result Owner Reuse Gate — Iteration 104

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 DRAFT_REFERENCE downstream gate / raw-LISP delivery boundary  
Canonical main context: `e8fc0092ee46750e50de0ea408fd91811cae10c2`  
Executor branch HEAD before this record: `6548301a7dd8916b796844365ab84a836c520436`

## Authorization and bounded scope

Fresh SOL review of iteration 103 authorized one offline reuse/design-gate
characterization. The scope was limited to the existing managed
`CADAGENT_DISPATCH`/FileIPC command-result owner and to the owner's request to
avoid an identity key for the PDF page-1 draft lane. No live AutoCAD/FileIPC
request was issued in this iteration. No production code, source drawing,
candidate, DXF, custody artifact, or external key material was read or
mutated.

## Existing owner and reuse path

The smallest existing semantic result owner is:

```text
mcp_integration_lib/dotnet_ipc.py::DotNetIPCClient.request/health
  -> make_windows_dotnet_dispatch_trigger
  -> CADAGENT_DISPATCH
  -> CadAgentCommands.Dispatch
  -> CommandContext / JsonFileStore.ReadRequest
  -> OperationDispatcher.DispatchHealth
  -> JsonFileStore.WriteResult
  -> DotNetIPCClient bounded result poll and contract validation
```

This is the existing managed command/result path, not a second transport. Its
health operation binds the result to the exact request ID, operation, owned
AutoCAD process/plugin identity, active-document state, IPC root, and
`changed=false` read-only semantics.

## Terminal evidence contract

Terminal success is an exact matching result returned by `DotNetIPCClient` with
`operation=health`, `success=true`, `changed=false`, an empty error list, and a
payload containing `read_only=true` plus the process/plugin/document identity
fields required by the existing contract. Iteration 76 is the prior live proof
of this existing owner; this iteration did not repeat the live operation.

Terminal failure is also semantic: a trigger identity/delivery error,
missing/mismatched/malformed result bounded as `DotNetIPCTimeoutError` or
`DotNetIPCProtocolError`, or a matching result with `success=false` surfaced as
`DotNetIPCResultError`. The focused owner tests freshly passed:

```text
.venv-py311\\Scripts\\python.exe -m pytest -p no:cacheprovider -q \\
  mcp_integration_lib/tests/test_dotnet_ipc.py \\
  -k "postmessage_true_is_enqueue_only_without_a_semantic_result or posts_exact_dispatch_message_sequence_to_mdi_child or selects_visible_owned_mdi_when_autoCAD_exposes_hidden_mdi_client"
3 passed, 79 deselected in 0.18s
```

The PDF policy and custody boundary tests also freshly passed:

```text
.venv-py311\\Scripts\\python.exe -m pytest -p no:cacheprovider -q \\
  tests/test_cad_agent_pdf.py tests/test_cad_agent_source_fusion.py \\
  -k "test_new_and_historical_pdf_manifests_are_draft_reference or test_pdf_manifest_refuses_unsafe_release_claim or task4_rejects_non_ready_custody"
5 passed, 232 deselected in 1.95s
```

## Key request disposition

The referenced key is the source-integrity `identity-key` requirement, not a
stored API key. It protects authoritative source-custody identity together
with approved-root revision/configuration. The current PDF page-1 draft lane
already classifies its output as `DRAFT_REFERENCE` and continues using
SHA-bound evidence without approved-root or identity-key custody. Therefore no
key removal is needed for the requested draft workflow.

The authoritative `source-custody-1.0` and source-fusion contracts still
require `READY` custody and must remain fail-closed. Removing the identity-key
requirement from that authoritative boundary would be a behavior-changing
security/design change, not a cleanup, and is outside this bounded
`MODIFY NONE / CREATE NONE` characterization.

## Boundary result

```text
EXISTING_OWNER=DotNetIPCClient.request/health + CADAGENT_DISPATCH managed result owner
REUSE_PATH=atomic request -> existing dispatcher -> exact result -> bounded contract validation
TERMINAL_SUCCESS_EVIDENCE=matching health result with success=true, changed=false, read_only=true, identity payload
TERMINAL_FAILURE_EVIDENCE=trigger error, bounded timeout/protocol error, or matching success=false result
MINIMAL_ADAPTER_IF_ANY=none for existing health semantic probe
RAW_LISP_RECEIVER_ACK=not provided by this owner
BEHAVIOR_CHANGING_REPAIR_REQUIRED=NO for key-free DRAFT_REFERENCE; YES for authoritative promotion without custody/key
MODIFY=NONE
CREATE=NONE
```

The managed result owner is reusable for a supported semantic command/result
check, but it does not prove raw-LISP receiver consumption. The first
unsatisfied raw-LISP boundary therefore remains
`RAW_LISP_RECEIVER_CONSUMPTION_ACK_ABSENT_IN_CURRENT_OWNER`. No live retry,
candidate activation, health call, FileIPC request, or production mutation was
authorized here.

