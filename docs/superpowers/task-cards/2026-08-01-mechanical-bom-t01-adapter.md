# Task Card T01 — Managed Mechanical BOM Adapter

## Role

You are the implementation Coder for T01. Work only in your assigned isolated worktree and branch. Do not merge, do not modify `main`, and do not touch files outside the allowed set.

## Goal

Create the AutoCAD-independent managed adapter boundary for the approved read-only `mechanical_bom` operation. This task does not wire IPC, dispatcher, Python, live AutoCAD, `scripts/verify.ps1`, or `docs/STATUS.md`.

## Required files

Create or modify only:

- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/IMechanicalDrawingGateway.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/MechanicalModels.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/IMechanicalAdapter.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/ManagedMechanicalAdapter.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/NoOpMechanicalAdapter.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical/ManagedMechanicalAdapterTests.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical/NoOpMechanicalAdapterTests.cs`

Forbidden: `Ipc/**`, `Commands/CommandContext.cs`, `OperationDispatcher.cs`, Python, JSON schemas, `scripts/verify.ps1`, `docs/STATUS.md`, and all unrelated files.

## Contract

```csharp
public interface IMechanicalDrawingGateway
{
    IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents();
}

public sealed record MechanicalAttributeSnapshot(string Tag, string Value);

public sealed record MechanicalComponentSnapshot(
    string Handle,
    string BlockName,
    IReadOnlyList<MechanicalAttributeSnapshot> Attributes);
```

`ManagedMechanicalAdapter` must advertise exactly `mechanical_bom`, return `success` with `Changed == false` and gateway snapshots for that operation, and return `not_supported` without reading the gateway for every other operation. `NoOpMechanicalAdapter` remains unavailable and returns empty collections with `Changed == false`.

## TDD and verification

1. Add failing xUnit tests for capability, success payload, rejected operation without gateway read, and unchanged NoOp behavior.
2. Run the Mechanical filter and confirm the failure is caused by the missing implementation.
3. Implement the minimum records, interface, result fields, and adapter.
4. Run:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter FullyQualifiedName~Mechanical
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
```

5. Run `git diff --check`; search changed files for forbidden COM/ActiveX/native/SDK references.
6. Self-review the complete diff and commit with:

```powershell
git add autocad_plugin/CadAgent.AutoCAD2027/Mechanical autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical
git commit -m "feat: add managed mechanical BOM adapter"
```

Report the commit SHA, changed files, RED command/result, GREEN command/result, and any limitation.
