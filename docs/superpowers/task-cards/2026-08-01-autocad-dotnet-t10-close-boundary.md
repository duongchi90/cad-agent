# T10 — Defer disposable AutoCAD close after command boundary

## Assignment

Fix the live `close_disposable` failure found on the new disposable DXF. The
root cause is synchronous `Document.CloseAndDiscard()` inside
`CADAGENT_DISPATCH`, which returns `Drawing is busy`. Use the documented
asynchronous command boundary; do not modify Python or the old dispatcher.

## Allowed write-set

- `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/CommandGuardTests.cs`

## Forbidden write-set

Everything else, especially Python IPC files, C# dispatcher files, project
configuration, `scripts/verify.ps1`, `docs/STATUS.md`, and drawings.

## Contract

In `CommandContext.CreateLive`, the injected close action must queue exactly:

```csharp
document.SendStringToExecute("_.CLOSE _N ", true, false, false);
```

It must not synchronously call `document.CloseAndDiscard()` from the dispatch
command. Preserve path matching and disposable/save guards. Add a pure test for
the exact close command contract or equivalent helper; no offline test may
claim live AutoCAD success.

## Required checks

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --no-restore
git diff --check
```

Commit the scoped fix and do not merge. The PO will run live only on the
disposable AutoCAD session after review.
