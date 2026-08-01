# Task Card T06 — Commands and Operation Dispatcher

**Role:** Coder  
**Model:** Luna Extra High (`gpt-5.6-luna`, reasoning `xhigh`)  
**Base:** The exact SHA of `integration/autocad-dotnet-option-a` after PO integrates T04 and T05  
**Branch:** `codex/autocad-dotnet-t06-commands`  
**Worktree:** `D:\cad-agent-master\cad-agent\.worktrees\autocad-dotnet-t06-commands`

## Objective

Wire the completed C# components into four registered AutoCAD commands and a safe operation dispatcher.

## Allowed files

- `autocad_plugin/CadAgent.AutoCAD2027/Commands/CadAgentCommands.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/CommandGuardTests.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`

## Forbidden files

All contracts, JSON storage, Drawing, Review, Mechanical, Python, project configuration, scripts, status, and old dispatcher files.

## Requirements

- Register exactly `CADAGENT_HEALTH`, `CADAGENT_DISPATCH`, `CADAGENT_REVIEW`, and `CADAGENT_CLOSE_DISPOSABLE`.
- `CADAGENT_DISPATCH` reads one new request and writes one matching result.
- Health reports plugin version, host/document full path, IPC path, and IPC read/write capability.
- Review is read-only and delegates to the review core.
- Close requires `disposable=true` and `save_changes=false`, then closes without save.
- Reject unsupported repair/mutation operations before any transaction.
- Never call `Save`, `SaveAs`, `Erase`, or mutation APIs in this slice.
- Implement each test as a discoverable xUnit v3 `[Fact]` method; a static `RunAll()` method alone is not a passing test suite.

## Required verification

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64
```

Tests must cover command registration names, health result, request/result id preservation, document mismatch, close guard, unsupported operation, and failure-to-result conversion.

## Completion report

Return commit SHA, changed files, test/build output, and an explicit statement that no save or repair path exists. Do not merge.
