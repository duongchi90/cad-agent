# Evaluator-Entry ACK Reuse Decision — Iteration 154

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / startup evaluator boundary  
Reviewed executor HEAD before this record: `79ccb910fcf251254669f8d5cab801f878796069`

## Authorization and scope

Fresh GitHub state was read before this analysis. This was one offline-only
reuse/design step authorized by the iteration-153 frontier. The step inspected
the current startup, native trigger, AutoCAD plugin, marker, and File IPC
owners, and reran the existing causal-red oracle. No production code,
AutoCAD process, candidate, File IPC request, source, DXF, CAD state, or
SourceCustody policy was changed.

## Existing-owner map

| Boundary | Existing owner | What it proves |
| --- | --- | --- |
| Startup orchestration | `WindowsAutoCADStartTabSession._run_process_bound_runtime_bootstrap` in `mcp_integration_lib/mcp_client.py` | Orders document-ready, optional NETLOAD, dispatcher-load expression, completion marker, and fail-closed wait. |
| Native text delivery | `_make_windows_text_trigger` and `make_windows_lisp_trigger` in `mcp_integration_lib/mcp_client.py` | Targets the owned AutoCAD window and posts UTF-16LE `WM_CHAR` units. Its return is enqueue-only. |
| Startup expression | `_dispatcher_load_expression` in `mcp_integration_lib/mcp_client.py` | Builds the existing `(progn (setq *cad-agent-file-ipc-root* ...) (load ...))` expression. |
| Marker write/observation | `_start_tab_stage_marker_expression`, `_observe_stage_markers`, and `_wait_for_completion_ack` in `mcp_integration_lib/mcp_client.py` | Writes and reads fixed tokens under the request-owned IPC root. |
| Managed AutoCAD commands | `CadAgentCommands` in `autocad_plugin/CadAgent.AutoCAD2027/Commands/CadAgentCommands.cs` | Owns `CADAGENT_HEALTH`, `CADAGENT_DISPATCH`, `CADAGENT_REVIEW`, and `CADAGENT_CLOSE_DISPOSABLE` after the plugin is loaded. |
| File IPC semantics | `mcp_integration_lib/mcp_dispatch.lsp` and the managed `OperationDispatcher` | Owns request/result dispatch only after the dispatcher/plugin prerequisites exist. |

The plugin has no `IExtensionApplication`, evaluator callback, queue-drain
receipt, or receiver hook. `PackageContents.xml` also declares
`LoadOnCommandInvocation=True` and maps only `CADAGENT_DISPATCH`; therefore
the managed command owner cannot honestly acknowledge entry into the initial
raw-LISP load expression before that dispatcher exists.

## Causal RED

The existing marked test was rerun with the authoritative Python 3.11
environment:

```text
FAILED mcp_integration_lib/tests/test_file_ipc_windows_trigger.py::
WindowsTriggerExecutionRedTests::test_enqueue_true_without_receiver_consumption_is_causal_red
1 failed, 26 deselected
```

The test injects `PostMessageW=TRUE` for every framed code unit while the
modeled receiver consumes none. The current trigger returns `None`; there is
no receiver/evaluator ACK field or callback. This remains the first
unsatisfied live boundary:

```text
REAL_AUTOCAD_EVALUATOR_ENTRY_NOT_PROVEN
```

The result does not claim AutoCAD failed to evaluate; it only rejects the
false inference from enqueue success or trigger return.

## Smallest honest reuse seam

Use the existing marker writer and observer in the existing raw-LISP startup
owner. For the startup expression only, prepend one unique, fixed-token
`evaluator_entry` marker form to the same expression that already sets the IPC
root and loads `mcp_dispatch.lsp`:

```text
(progn <existing evaluator-entry marker writer>
       (setq *cad-agent-file-ipc-root* <exact root>)
       (load <exact dispatcher path>))
```

The observer must require the exact token and exact path before treating the
evaluator-entry seam as proven. This is a combined AutoLISP evaluator-entry
receipt, not a new receiver hook and not proof of native queue consumption.
The existing post-load completion marker remains separate and still has to be
observed before client construction.

Do not use the managed `CADAGENT_*` commands for this pre-dispatch ACK, do not
introduce `SendMessageW`, COM/ROT, a named pipe, a second marker transport, or
an evaluator hook, and do not reinterpret `PostMessageW=True` as execution.

## Exact future write-set (not authorized by this record)

```text
MODIFY=
  mcp_integration_lib/mcp_client.py
    private startup expression/marker ordering and bounded classification only
  mcp_integration_lib/tests/test_mcp_client_drawing_open.py
    deterministic ordering, missing/wrong-token, timeout, and cleanup contracts
  docs/STATUS.md and one implementation record
CREATE=none outside the listed test/record paths
FORBIDDEN=
  C# public schema/dispatcher changes; new transport/control plane;
  SourceCustody key/HMAC/identity changes; source/DXF/CAD/candidate/provider/M2 mutation
```

No production write is made in iteration 154. Any implementation would first
need a failing regression test, then the smallest private owner change, full
offline verification, and a fresh SOL decision before a live epoch.

## Verification

After committing this record and the canonical status update at
`fc4683c19f97849eaea995a967ce39645289cd62`, `scripts/verify.ps1` completed
successfully. It reported offline JUnit `3410` with zero failures/errors,
C# `238` passed, .NET IPC `134` passed, the expected causal RED `1` failed,
real-data `2` skipped, and AutoCAD Mechanical `17` skipped because live
prerequisites were absent. AutoCAD live and M2 were `NOT RUN`.

## Fail-closed, rollback, and acceptance oracle

- Allocate and remove the unique entry marker under the already validated
  request-owned IPC root; reject path conflicts and root changes.
- A trigger exception, missing marker, wrong token, unreadable marker, or
  timeout yields `STARTUP_EVALUATOR_ENTRY_NOT_CONFIRMED`; do not emit or wait
  on the completion marker, construct the client, invoke File IPC, or retry.
- Rollback is limited to reverting the private startup-owner/test commit;
  disposable AutoCAD cleanup remains no-save and the candidate/DWT hashes must
  remain unchanged.
- The future live oracle is exactly one disposable epoch: document-ready;
  one existing raw-LISP trigger; exact evaluator-entry marker readback; exact
  dispatcher completion marker readback; only then existing client/File IPC
  checks as separately authorized; cleanup clean; no source/DXF/CAD mutation.

## Classification

```text
STATE=DESIGNED
EVIDENCE=This record; mcp_integration_lib/mcp_client.py; mcp_integration_lib/mcp_dispatch.lsp; autocad_plugin/CadAgent.AutoCAD2027/Commands/CadAgentCommands.cs; autocad_plugin/CadAgent.bundle/PackageContents.xml; mcp_integration_lib/tests/test_file_ipc_windows_trigger.py causal RED (1 failed, 26 deselected); scripts/verify.ps1 PASS (offline JUnit 3410, C# 238, .NET IPC 134; real-data 2 SKIP; AutoCAD 17 SKIP; live/M2 NOT RUN); HEAD fc4683c19f97849eaea995a967ce39645289cd62
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=REAL_AUTOCAD_EVALUATOR_ENTRY_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this existing-marker same-expression seam; authorize implementation only if the exact owner, write-set, fail-closed contract, and live oracle are accepted
HUMAN_GATE=NO
```
