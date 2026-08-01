# Task Card T03 — Mechanical Capability Boundary

**Role:** Coder  
**Model:** Luna Extra High (`gpt-5.6-luna`, reasoning `xhigh`)  
**Base:** The exact SHA of `integration/autocad-dotnet-option-a` after PO integrates T01  
**Branch:** `codex/autocad-dotnet-t03-mechanical-boundary`  
**Worktree:** `D:\cad-agent-master\cad-agent\.worktrees\autocad-dotnet-t03-mechanical-boundary`

## Objective

Prepare an extension boundary for future Mechanical operations without adding Mechanical SDK, ActiveX, COM, C++, or native ARX dependencies.

## Allowed files

- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/IMechanicalAdapter.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/MechanicalModels.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/NoOpMechanicalAdapter.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical/NoOpMechanicalAdapterTests.cs`

## Forbidden files

All contract, IPC, command, drawing, review, Python, project configuration, script, and status files. Do not add any Autodesk Mechanical reference or COM interop package.

## Requirements

Implement `IMechanicalAdapter` with `IsAvailable`, `GetCapabilities()`, and `Execute(MechanicalOperationRequest request)`. `NoOpMechanicalAdapter` must return `IsAvailable=false`, an empty supported-operation list, and a `not_supported` result containing the requested operation name.

## Required verification

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
```

Add tests for capability response, unsupported operation, and operation-name preservation. Confirm no COM/native reference appears in the project dependency graph.

## Completion report

Return commit SHA, changed files, test result, and dependency inspection result. Do not merge.
