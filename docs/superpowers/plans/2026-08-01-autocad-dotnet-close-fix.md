# AutoCAD .NET Disposable Close Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `close_disposable` so it queues close after `CADAGENT_DISPATCH` returns instead of closing a busy document synchronously.

**Architecture:** Preserve the dispatcher contract and guards. Replace only the live `CommandContext` close delegate with `Document.SendStringToExecute("_.CLOSE _N ", true, false, false)`, which AutoCAD executes after the current .NET command ends. Offline tests continue to inject a close action.

**Tech Stack:** C#/.NET 10 Windows, AutoCAD Mechanical 2027 managed API, xUnit.

## Global Constraints

- Windows only; AutoCAD Mechanical 2027 only.
- The requested full path must equal the active normalized full path.
- `close_disposable` must require `disposable=true` and `save_changes=false`.
- The live close must queue `Document.SendStringToExecute("_.CLOSE _N ", true, false, false)` and must not call `CloseAndDiscard()` synchronously from the dispatcher command.
- Do not modify the old File IPC dispatcher, Python IPC files, production workflows, or `scripts/verify.ps1`.
- Do not claim live PASS from C# or offline tests.

### Task 10: Defer disposable close past the .NET command boundary

**Files:**

- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs` (live close delegate only).
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/CommandGuardTests.cs` (pure close-command contract assertion or equivalent helper test).

**Interfaces:**

- Consumes: existing `OperationDispatcher` close guard and injected `Action closeWithoutSaving` boundary.
- Produces: a live close action that queues `_.CLOSE _N ` after `CADAGENT_DISPATCH` returns.

- [ ] **Step 1: Add a failing pure contract test**

  Add a deterministic assertion that the live-close command contract is exactly
  `_.CLOSE _N ` or test an internal helper returning this exact string and
  flags. The assertion must not invoke AutoCAD or claim a live result.

- [ ] **Step 2: Implement the smallest live boundary change**

  In `CommandContext.CreateLive`, replace synchronous `document.CloseAndDiscard()`
  with:

  ```csharp
  document.SendStringToExecute("_.CLOSE _N ", true, false, false);
  ```

  Keep all request guards and the injected action shape unchanged.

- [ ] **Step 3: Run focused C# verification**

  ```powershell
  dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
  dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --no-restore
  ```

- [ ] **Step 4: Self-review and commit**

  Verify only the two allowed files changed, run `git diff --check`, and commit
  with `fix: defer disposable AutoCAD close after command`.

## Dependency and ownership table

| Task ID | Objective | Depends on | Branch | Allowed files | Forbidden files | Parallel with | Mandatory tests | Completion condition |
|---|---|---|---|---|---|---|---|---|
| T10 | Defer disposable close after current .NET command | Integrated T09 head recorded immediately before dispatch | `codex/autocad-dotnet-t10-close-boundary` | `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`, `autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/CommandGuardTests.cs` | All Python files, old dispatcher, `scripts/verify.ps1`, `docs/STATUS.md`, contracts, production drawings | None; sequential after T09 live finding | Focused C# test/build; live sequence is PO-only and must be PASS/SKIP/NOT RUN | Busy close is removed from live path, C# tests/build pass, exact write-set/review clean. |
