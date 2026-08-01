# Task Card T02 — Mechanical BOM IPC Integration

## Role

You are the implementation Coder for T02. Work in a fresh isolated worktree based on the reviewed T01 commit. Do not merge, do not modify `main`, and do not touch files outside the allowed set.

## Goal

Wire the reviewed managed adapter into the AutoCAD live gateway and existing JSON file IPC, add the Python client helper, update the strict contract schemas, and add offline plus opt-in live tests for `mechanical_bom`.

## Dependency

T01's adapter commit must already be review-clean and present in this worktree before T02 begins. Consume the exact types from T01:

```csharp
IMechanicalDrawingGateway
MechanicalAttributeSnapshot
MechanicalComponentSnapshot
ManagedMechanicalAdapter
```

## Required files

Create or modify only:

- `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`
- `contracts/autocad-ipc/request.schema.json`
- `contracts/autocad-ipc/result.schema.json`
- `contracts/autocad-ipc/operations/mechanical-bom.schema.json`
- `contracts/autocad-ipc/examples/mechanical-bom-request.json`
- `contracts/autocad-ipc/examples/mechanical-bom-result.json`
- `mcp_integration_lib/dotnet_ipc.py`
- `mcp_integration_lib/tests/test_dotnet_ipc.py`
- `mcp_integration_lib/tests/test_dotnet_ipc_live.py`

Forbidden: Mechanical implementation files owned by T01, `scripts/verify.ps1`, `docs/STATUS.md`, drawings, and unrelated source files.

## Contract and behavior

- Operation: exactly `mechanical_bom`.
- Schema: remains `1.0`.
- Request path is required and must match the active document after existing normalization.
- Parameters must be exactly `{}`.
- Result is the existing envelope with `changed=false`; `entity_handles` equals the sorted component handles.
- Payload contains `component_count` and `components`; each component has `handle`, `block_name`, and `attributes` with `tag` and `value`.
- Live extraction reads only direct ModelSpace `BlockReference` inserts and direct attributes through a read-only transaction.
- No COM/ActiveX/native/Mechanical SDK references; no save or mutation.

## TDD and verification

1. Add failing C# dispatcher/contract tests and Python client tests before production changes.
2. Run and observe RED:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter FullyQualifiedName~MechanicalBom
& .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -k mechanical_bom -q -p no:cacheprovider
```

3. Implement the live gateway, supported-operation validation, dispatcher mapping, JSON schemas/examples, Python helper, and tests.
4. Run GREEN:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
& .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -q -p no:cacheprovider
```

5. Run the opt-in live marker only when AutoCAD prerequisites are present. It must produce PASS, SKIP, or NOT RUN and must use only a disposable DXF under `C:\temp`.
6. Run `git diff --check`, inspect the complete allowed-file diff, confirm `scripts/verify.ps1` and `docs/STATUS.md` are untouched, then commit:

```powershell
git add autocad_plugin contracts mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc_live.py
git commit -m "feat: expose read-only mechanical BOM over IPC"
```

Report the commit SHA, files changed, RED evidence, GREEN evidence, live marker, and any limitation.
