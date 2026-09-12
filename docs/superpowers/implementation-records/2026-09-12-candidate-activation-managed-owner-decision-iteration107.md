# Candidate Activation Managed-Owner Decision — Iteration 107

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / active-document identity discriminator  
Canonical main context: `e8fc0092ee46750e50de0ea408fd91811cae10c2`  
Executor HEAD before this record: `73225159b72dfc92d50fb2a69605a892be34e508`

## Authorization and bounded scope

Fresh SOL review authorized exactly one offline architecture decision. The
decision compares the existing raw-LISP candidate-open dependency with the
managed `DotNetIPCClient`/`CADAGENT_DISPATCH` owner. The scope is limited to
owner inventory, contract behavior, and existing focused tests. No AutoCAD
process was launched, no candidate was opened or activated, no FileIPC request
was issued, and no production/source/DXF/CAD state was mutated.

## Existing operation inventory

The managed `OperationDispatcher.Dispatch` currently supports `health`,
`review`, `close_disposable`, `mechanical_bom`, `drawing_setup_audit`, visual
and native evidence operations, viewport query, exact-base Xref operations,
and standalone-DWG operations. There is no managed `drawing_open` or
`candidate_activate` operation.

Every managed drawing operation is receiver-side work against the already
active document. `TryMatchActiveDocument` compares the requested path with
`IDrawingGateway.ActiveDocumentFullPath` and returns a failure when they do not
match. `CommandContext.CreateLive` also binds its gateway to
`MdiActiveDocument` at command invocation. `IDrawingGateway` exposes no
open/activate capability.

The existing opening owner is instead:

```text
FileIPCLiveMCPClient.drawing_open
  -> raw-LISP VLA Documents lookup/open/activate
  -> existing dispatcher bootstrap/ping when needed
  -> drawing-get-variables active-path readback
  -> exact requested-path comparison
```

It has a narrowly guarded writable `_.OPEN` fallback only after a positive
Start-tab/no-document proof; read-only open fails closed instead of using that
fallback. This is not an operation that can be replaced by the current managed
dispatcher without adding behavior and contract surface.

## Decision outputs

```text
EXISTING_OPERATION_IF_ANY=health is an active-document identity discriminator only; no existing managed operation opens or activates a candidate
MINIMAL_ADAPTER_IF_REQUIRED=none under MODIFY NONE; an exact managed replacement would require a new result-bearing open/activate capability on the existing dispatcher owner
EXACT_WRITE_SET_IF_BEHAVIOR_CHANGE_REQUIRED=SUPPORTED_OPERATIONS and ContractValidator request/result contract; OperationDispatcher; IDrawingGateway/AutoCadDrawingGateway; DotNetIPCClient wrapper; focused lifecycle/identity tests
```

The proposed write set is a future design boundary only; none of those files
was changed. Reusing `health(candidate_path)` after an external open is valid
for identity confirmation, but it cannot repair or replace the open/activate
step.

## Causal RED and current evidence

The causal red is:

```text
active_document != candidate_path
  -> health(candidate_path) -> active-document mismatch, changed=false
  -> no existing managed operation transitions to candidate_path
```

The focused existing opening-owner tests passed:

```text
.venv-py311\\Scripts\\python.exe -m pytest -p no:cacheprovider -q \\
  mcp_integration_lib/tests/test_mcp_client_drawing_open.py \\
  -k "already_open_active_target_is_not_reopened or read_only_open_requests_read_only_and_still_verifies_active_document or default_open_preserves_writable_vla_open_signature or com_activation_failure_falls_back_only_with_positive_start_tab_proof or read_only_open_fails_closed_instead_of_using_writable_open_fallback"
5 passed, 35 deselected in 0.08s
```

The focused managed identity tests passed:

```text
dotnet test autocad_plugin\\CadAgent.AutoCAD2027.Tests\\CadAgent.AutoCAD2027.Tests.csproj --no-restore --filter "FullyQualifiedName~OperationDispatcherTests.HealthReturnsTheActiveDocumentAndPreservesRequestId|FullyQualifiedName~OperationDispatcherTests.HealthRejectsARequestedPathThatIsNotTheActiveDocument" --verbosity minimal
Passed: 2, Failed: 0, Skipped: 0
```

These tests establish the current split: raw-LISP owner performs opening and
activation; managed health performs terminal path/identity confirmation only.
They do not prove a live candidate activation.

## Future live acceptance oracle (not run)

After a separately authorized bounded live action, the existing owners could
be composed as one discriminator: use the existing read-only
`FileIPCLiveMCPClient.drawing_open(candidate_path, read_only=true)`, then call
`DotNetIPCClient.health(candidate_path)`. Acceptance requires the exact
candidate path in the result, `success=true`, `changed=false`, active-document
identity true, and the existing plugin/process identity payload; cleanup must
use the existing no-save disposable close owner. This would validate the
post-open boundary, not add a second transport or claim that managed health
opened the file.

No live retry, candidate activation, health/FileIPC call, production code,
source, candidate, DXF, or CAD mutation was performed in this decision.

## Classification

```text
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=MANAGED_CANDIDATE_OPEN_ACTIVATE_OPERATION_ABSENT
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this decision; preserve the current key-free DRAFT_REFERENCE lane and keep live candidate activation, health/FileIPC, raw-LISP retry, and production mutation stopped until a separate bounded live or design action is authorized
HUMAN_GATE=NO
MODIFY=NONE
CREATE=NONE
```

