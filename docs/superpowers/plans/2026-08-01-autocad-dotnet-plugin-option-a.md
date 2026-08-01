# AutoCAD .NET Plugin Option A Implementation Plan

**Status:** Completed and integrated into `main`.

**Final evidence:** `scripts/verify.ps1` passed on `f69d6a0` with C# `68/68`,
dotnet IPC `36/0/0/0`, offline `444/0/0/0`, and explicit unavailable-state
probes. The managed disposable AutoCAD smoke is recorded as `PASS` on
`296b3b4`; the legacy AutoLISP aggregate remains a separate historical
`FAIL` and is not part of this managed .NET slice.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Windows-only Managed .NET 10 AutoCAD Mechanical 2027 plugin slice in parallel with the existing Python/File IPC dispatcher, without changing the existing dispatcher or adding Mechanical ActiveX/C++ dependencies.

**Architecture:** The C# plugin owns the AutoCAD-side JSON/File IPC consumer and four commands: `CADAGENT_HEALTH`, `CADAGENT_DISPATCH`, `CADAGENT_REVIEW`, and `CADAGENT_CLOSE_DISPOSABLE`. Python adds a separate `dotnet_ipc` backend with its own filename prefix; both sides share versioned JSON schemas under `contracts/autocad-ipc/`. Mechanical-specific behavior is isolated behind `IMechanicalAdapter` and a no-op implementation.

**Tech Stack:** Windows, Visual Studio 2026, .NET SDK 10.0.301, `net10.0-windows`, x64, AutoCAD Mechanical 2027 Managed API (`AcCoreMgd.dll`, `AcDbMgd.dll`, `AcMgd.dll`), Python 3.11, pytest, existing PowerShell verification.

## Global Constraints

- Supported platform is Windows only; target is AutoCAD Mechanical 2027 only.
- The C# project targets `net10.0-windows`, `PlatformTarget=x64`, and `OutputType=Library`.
- Autodesk Managed DLLs are referenced with `Private=false`/`Copy Local=false` and are never copied into Git or plugin output.
- `ObjectARX` and Mechanical SDK installation paths are local machine configuration; only `Directory.Build.props.example` is committed.
- Do not copy `AutoCAD-Net-Wizards`, VSIX content, Autodesk SDK source, headers, native libraries, COM type libraries, or private drawings into the repository.
- Keep the existing `mcp_integration_lib` File IPC dispatcher and `FileIPCLiveMCPClient` protocol unchanged.
- Do not implement production repair, automatic NETLOAD, named pipe, HTTP, BOM, balloon, Part Reference, Mechanical Structure, or C++/ARX code.
- Do not create `PROJECT_STATUS.md`; use `AGENTS.md`, `docs/STATUS.md`, the approved spec, and this plan.
- Every Coder works from a task-specific branch and worktree, never directly on `main`; every wave's parallel branches start from one recorded integration base SHA.
- No two Coders may edit the same file, project configuration, or verification script.
- Only T07 may edit `scripts/verify.ps1`; only the PO may update `docs/STATUS.md` after the final live review.
- Coders use Luna Extra High (`gpt-5.6-luna`, reasoning `xhigh`), run task-scoped tests, inspect their own diff, and commit; Coders do not merge.
- AutoCAD live evidence is recorded only as `PASS`, `SKIP`, or `NOT RUN`; build/unit-test success never implies live success.
- No task may alter image recognition, Primitive IR, Semantic IR, DXF Builder, or existing live dispatcher behavior.
- The C# test project uses discoverable xUnit v3 tests with `Microsoft.NET.Test.Sdk` `18.6.0`, `xunit.v3` `3.2.2`, and the official VSTest adapter `xunit.runner.visualstudio` `3.1.5`; test files must not rely on uncalled static `RunAll()` methods.

## Base and Integration Policy

The common starting commit is `14fa9fe` (`docs: plan parallel AutoCAD plugin tasks`), which includes the approved spec, implementation plan, and task cards. The PO creates `integration/autocad-dotnet-option-a` from this SHA. T01 starts from that SHA. After the PO reviews and cherry-picks T01, the PO records that integration branch SHA as the single WAVE 2 base and creates both WAVE 2 worktrees from it. The same rule is repeated at every parallel wave: all branches in that wave are created from the integration branch's current SHA before any Coder starts.

The PO performs every cherry-pick into `integration/autocad-dotnet-option-a`, checks the Coder's commit and task tests, and resolves conflicts only by sending the Coder a correction task. The PO does not silently rewrite a Coder's commit.

## Dependency Graph

```text
T01 scaffold
  ├── T02 contracts + IPC primitives ──┐
  ├── T03 Mechanical boundary          ├── T06 commands/dispatcher ── T07 verify integration ── T08 live/review
  └── (after T02) T04 Drawing/Review ──┘
      (after T02) T05 Python dotnet_ipc ────────────────┘
```

Only T02/T03 and T04/T05 are parallel groups. T06, T07, and T08 are sequential integration gates.

## Task-by-Task Execution Details

### Task 1: C# Solution and SDK Boundary

**Files:**

- Create: `autocad_plugin/CadAgent.AutoCAD2027.sln`
- Create: `autocad_plugin/CadAgent.AutoCAD2027/CadAgent.AutoCAD2027.csproj`
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj`
- Create: `autocad_plugin/Directory.Build.props.example`
- Modify: `.gitignore`

**Interfaces:** Produces a buildable plugin/test solution and local `AcadDir`/`ArxSdkDir` properties consumed by every later C# task. It must not produce application behavior.

- [x] Create the solution and two projects with `TargetFramework=net10.0-windows`, x64 platform, library output, nullable and implicit usings.
- [x] Add `Microsoft.NET.Test.Sdk` `18.6.0`, `xunit.v3` `3.2.2`, and `xunit.runner.visualstudio` `3.1.5` only to the test project, with runner assets private to the test project.
- [x] Add only `AcCoreMgd`, `AcDbMgd`, and `AcMgd` references, preferring `$(ArxSdkDir)\inc` and falling back to `$(AcadDir)`, with `<Private>false</Private>`.
- [x] Commit only the example local props file and ignore real `Directory.Build.props`, C# `bin/obj`, and local plugin outputs.
- [x] Run `dotnet restore autocad_plugin/CadAgent.AutoCAD2027.sln`.
- [x] Run `dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64` and inspect that Autodesk DLLs are not copied.
- [x] Review the diff and commit the scoped task.

### Task 2: Shared IPC Contracts and Offline Primitives

**Files:**

- Create: `contracts/autocad-ipc/request.schema.json`, `result.schema.json`, operation schemas, and examples.
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`, `ContractValidator.cs`, `JsonFileStore.cs`.
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`, `JsonFileStoreTests.cs`.

**Interfaces:** Produces schema version `1.0`, C# DTOs/validation, and request-specific atomic file operations consumed by T05/T06.

- [x] Encode the required request/result fields and allow `drawing_full_path=null` only for `health`.
- [x] Reject bad version, empty request id, relative path, unsupported operation, and invalid disposable parameters.
- [x] Implement `cadagent_dotnet_request_<request_id>.json`/`cadagent_dotnet_result_<request_id>.json` naming, atomic writes, bounded reads, and cleanup of only the current request.
- [x] Write failing tests for the invalid and round-trip cases, then implement the minimum passing behavior.
- [x] Mark each test as a discoverable xUnit v3 `[Fact]` method; do not leave a static `RunAll()`-only test suite.
- [x] Run `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64`.
- [x] Review the diff and commit the scoped task.

### Task 3: Mechanical Capability Boundary

**Files:**

- Create: `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/IMechanicalAdapter.cs`, `MechanicalModels.cs`, `NoOpMechanicalAdapter.cs`.
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical/NoOpMechanicalAdapterTests.cs`.

**Interfaces:** Produces `IMechanicalAdapter`, `MechanicalCapabilityResult`, `MechanicalOperationRequest`, and `MechanicalOperationResult` for future adapters; the default implementation is unavailable and non-mutating.

- [x] Write tests proving `IsAvailable=false`, no supported operations, `not_supported`, and operation-name preservation.
- [x] Mark each test as a discoverable xUnit v3 `[Fact]` method; do not leave a static `RunAll()`-only test suite.
- [x] Implement the interface and no-op result without referencing COM, ActiveX, Mechanical SDK, C++, or native ARX.
- [x] Run `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64`.
- [x] Inspect the project dependency graph for absent Mechanical/native references.
- [x] Review the diff and commit the scoped task.

### Task 4: Drawing Reader and Read-only Review Core

**Files:**

- Create: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/ActiveDocumentReader.cs`.
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Review/EntitySnapshot.cs`, `ReviewService.cs`.
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/ActiveDocumentPathTests.cs`, `Review/ReviewMappingTests.cs`.

**Interfaces:** Consumes the contract models from T02 and produces full-path document identity plus read-only entity snapshots for T06.

- [x] Write pure tests for Windows path normalization, LINE/CIRCLE/ARC/TEXT/DIMENSION mapping, missing handle, and unsupported-type warning.
- [x] Mark each test as a discoverable xUnit v3 `[Fact]` method; do not leave a static `RunAll()`-only test suite.
- [x] Implement active-document identity using the full normalized path, never filename-only identity.
- [x] Read entities in a read-only transaction and expose handle/type/layer/basic geometry without save, erase, or mutation calls.
- [x] Run `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64`.
- [x] Review the diff and commit the scoped task.

### Task 5: Python dotnet_ipc Backend

**Files:**

- Create: `mcp_integration_lib/dotnet_ipc.py`.
- Create: `mcp_integration_lib/tests/test_dotnet_ipc.py`.

**Interfaces:** Produces `DotNetIPCClient.request`, `.health`, `.review`, and `.close_disposable` with injected trigger, bounded polling, new file prefix, and request-id preservation.

- [x] Write fake-dispatcher tests for health, review parameters, disposable-close guard, timeout, request-specific cleanup, and old `autocad_mcp_*` coexistence.
- [x] Implement only the new backend; do not modify `mcp_client.py`, `reviewer2.py`, or `repair2.py`.
- [x] Run `python -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -q -p no:cacheprovider`.
- [x] Run `python -m ruff check mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py`.
- [x] Review the diff and commit the scoped task.

### Task 6: Commands and Operation Dispatcher

**Files:**

- Create: `autocad_plugin/CadAgent.AutoCAD2027/Commands/CadAgentCommands.cs`, `CommandContext.cs`.
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`.
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/CommandGuardTests.cs`, `Ipc/OperationDispatcherTests.cs`.

**Interfaces:** Consumes T02–T05 boundaries and produces the four AutoCAD command registrations and operation dispatch behavior.

- [x] Write tests for command names, health result, request/result id preservation, document mismatch, close guard, unsupported operation, and error-to-result conversion.
- [x] Mark each test as a discoverable xUnit v3 `[Fact]` method; do not leave a static `RunAll()`-only test suite.
- [x] Register exactly `CADAGENT_HEALTH`, `CADAGENT_DISPATCH`, `CADAGENT_REVIEW`, and `CADAGENT_CLOSE_DISPOSABLE`.
- [x] Reject unsupported mutation/repair before any transaction; do not call save, save-as, erase, or mutation APIs.
- [x] Run focused C# tests and `dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64`.
- [x] Review the diff and commit the scoped task.

### Task 7: Authoritative Verification Integration

**Files:**

- Modify: `scripts/verify.ps1`.
- Modify: `tests/test_verification_contract.py`.
- Create: `tests/test_autocad_plugin_project.py`.

**Interfaces:** Produces the only authoritative verifier entry point for the C# build/tests plus the existing Python gates; it does not update `docs/STATUS.md`.

- [x] Write contract tests proving C# restore/build/test is owned by `scripts/verify.ps1` and live absence is explicit skip/not pass.
- [x] Add Release x64 restore/build/test without weakening clean-tree, snapshot, Python, live-marker, Ruff, or diff checks.
- [x] Run `dotnet restore`, `dotnet build`, `dotnet test`, and `.\scripts\verify.ps1` from a clean task worktree.
- [x] Review the diff and commit the scoped task.

### Task 8: AutoCAD Live Smoke and Final Review

**Files:**

- Create only when evidence is recorded: `docs/reviews/2026-08-01-autocad-dotnet-live-review.md`.

**Interfaces:** Consumes the T07 integration artifact and produces live evidence; it does not change source, verification, or `docs/STATUS.md`.

- [x] Use manual NETLOAD in AutoCAD Mechanical 2027 and run `CADAGENT_HEALTH`.
- [x] Use a disposable DXF under `C:\temp`, run handle review, and close it without save.
- [x] Record exactly `PASS`, `SKIP`, or `NOT RUN` with prerequisite and evidence details.
- [x] Review the result independently for no production save, no repair path, and no changed old dispatcher.
- [x] Commit only the review record if one is needed.

## Dependency and Ownership Table

| Task ID | Objective | Depends on | Branch | Worktree | Allowed files | Forbidden files | Parallel with | Mandatory tests | Completion condition |
|---|---|---|---|---|---|---|---|---|---|
| T01 | Create solution, projects, SDK path configuration, and ignore rules | None | `codex/autocad-dotnet-t01-scaffold` | `.worktrees/autocad-dotnet-t01-scaffold` | `autocad_plugin/CadAgent.AutoCAD2027.sln`, `autocad_plugin/CadAgent.AutoCAD2027/**`, `autocad_plugin/CadAgent.AutoCAD2027.Tests/**`, `autocad_plugin/Directory.Build.props.example`, `.gitignore` | `contracts/**`, `mcp_integration_lib/**`, `scripts/**`, `docs/**`, existing Python packages | None | `dotnet restore`; `dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64` | Both projects restore/build on the Windows machine, references resolve through local `AcadDir`/`ArxSdkDir`, and no Autodesk DLL is copied to output. |
| T02 | Define shared request/result schemas and offline C# IPC primitives | T01 | `codex/autocad-dotnet-t02-contracts` | `.worktrees/autocad-dotnet-t02-contracts` | `contracts/autocad-ipc/**`, `autocad_plugin/CadAgent.AutoCAD2027/Ipc/Contract*.cs`, `autocad_plugin/CadAgent.AutoCAD2027/Ipc/JsonFileStore.cs`, `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/**` | `autocad_plugin/**/Commands/**`, `Drawing/**`, `Review/**`, `Mechanical/**`, `mcp_integration_lib/**`, `scripts/**`, `docs/STATUS.md`, project files | T03 | `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64` | Schemas, DTO serialization, version/path/operation validation, request-id isolation, atomic read/write, and cleanup tests pass without AutoCAD. |
| T03 | Add Mechanical capability boundary and safe no-op adapter | T01 | `codex/autocad-dotnet-t03-mechanical-boundary` | `.worktrees/autocad-dotnet-t03-mechanical-boundary` | `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/**`, `autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical/**` | `contracts/**`, `Ipc/**`, `Commands/**`, `Drawing/**`, `Review/**`, `mcp_integration_lib/**`, `scripts/**`, `docs/STATUS.md`, project files | T02 | `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64` | `IMechanicalAdapter`, request/result types, and `NoOpMechanicalAdapter` compile and prove `IsAvailable=false`, zero supported operations, and `not_supported` execution. No COM/C++ reference exists. |
| T04 | Implement AutoCAD document reader and read-only entity review mapping | T02 | `codex/autocad-dotnet-t04-review-core` | `.worktrees/autocad-dotnet-t04-review-core` | `autocad_plugin/CadAgent.AutoCAD2027/Drawing/**`, `autocad_plugin/CadAgent.AutoCAD2027/Review/**`, `autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/**`, `autocad_plugin/CadAgent.AutoCAD2027.Tests/Review/**` | `Ipc/Contract*.cs`, `JsonFileStore.cs`, `Mechanical/**`, `Commands/**`, `contracts/**`, `mcp_integration_lib/**`, `scripts/**`, `docs/STATUS.md`, project files | T05 | `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64` | Active-document full-path identity and read-only LINE/CIRCLE/ARC/TEXT/DIMENSION payload mapping compile and pass pure mapping tests; no save or mutation API is called. |
| T05 | Add isolated Python `dotnet_ipc` backend and fake contract tests | T02 | `codex/autocad-dotnet-t05-python-ipc` | `.worktrees/autocad-dotnet-t05-python-ipc` | `mcp_integration_lib/dotnet_ipc.py`, `mcp_integration_lib/tests/test_dotnet_ipc.py` | `mcp_integration_lib/mcp_client.py`, `reviewer2.py`, `repair2.py`, all C# files, `contracts/**`, `scripts/verify.ps1`, `docs/STATUS.md` | T04 | `python -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -q -p no:cacheprovider`; `python -m ruff check mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py` | Backend writes the new filename prefix, triggers an injected command callback, polls by request id, times out deterministically, cleans only its own files, and leaves the old client untouched. |
| T06 | Wire C# commands and operation dispatcher to the completed components | T02, T03, T04, T05 | `codex/autocad-dotnet-t06-commands` | `.worktrees/autocad-dotnet-t06-commands` | `autocad_plugin/CadAgent.AutoCAD2027/Commands/**`, `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`, `autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/**`, `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs` | `contracts/**`, `Ipc/Contract*.cs`, `JsonFileStore.cs`, `Drawing/**`, `Review/**`, `Mechanical/**`, `mcp_integration_lib/**`, `scripts/**`, `docs/STATUS.md`, project files | None | Focused `dotnet test`; `dotnet build ... -c Release -p:Platform=x64` | Four command names are registered, health/review/close-disposable guards are enforced, unsupported mutation is rejected, and command code never saves or repairs a drawing. |
| T07 | Integrate build/test gates into the authoritative verifier | T06 | `codex/autocad-dotnet-t07-verification` | `.worktrees/autocad-dotnet-t07-verification` | `scripts/verify.ps1`, `tests/test_verification_contract.py`, `tests/test_autocad_plugin_project.py` | All C# production code, `mcp_integration_lib/mcp_client.py`, `docs/STATUS.md`, all existing package tests except the explicitly named new contract test | None | `dotnet restore`; `dotnet build ... -c Release -p:Platform=x64`; `dotnet test ... -c Release -p:Platform=x64`; `scripts\verify.ps1` | One authoritative verifier builds/tests C#, runs current Python gates, preserves clean-tree/snapshot rules, and its contract tests pass. |
| T08 | Run live AutoCAD smoke, independent review, and final evidence | T07 | `codex/autocad-dotnet-t08-live-review` | `.worktrees/autocad-dotnet-t08-live-review` | `docs/reviews/2026-08-01-autocad-dotnet-live-review.md` only if evidence is recorded | All source, project config, `scripts/verify.ps1`, `docs/STATUS.md`, existing dispatcher, production drawings | None | AutoCAD live marker `autocad_mechanical`; NETLOAD/manual command checks; result must be `PASS`, `SKIP`, or `NOT RUN` | Live result is evidence-backed, disposable-only, no production save occurs, and the PO records final `docs/STATUS.md` update separately. |

## Wave Schedule

### WAVE 1 — Foundation, sequential

1. PO creates `integration/autocad-dotnet-option-a` from `d41b2fb2e1f4be3b8adbb952d3862c7f0c659162`.
2. Coder T01 creates the solution/project boundary and proves the baseline build.
3. PO reviews T01's diff, runs the focused build independently, and cherry-picks only the approved commit.

### WAVE 2 — Independent foundations, parallel

1. PO records `git rev-parse integration/autocad-dotnet-option-a` as the wave base.
2. T02 and T03 branches/worktrees are both created from that exact SHA.
3. T02 owns only JSON/IPC contract primitives; T03 owns only the Mechanical boundary.
4. PO reviews both commits independently, runs each focused test set, then cherry-picks both in either order.

### WAVE 3 — Review and Python backend, then C# integration

1. From the post-WAVE-2 integration SHA, PO creates T04 and T05 in parallel.
2. T04 owns C# Drawing/Review files; T05 owns only the Python backend/tests.
3. PO reviews and integrates T04/T05 separately.
4. PO creates T06 from the new integration SHA; T06 is sequential because it touches the command/dispatcher boundary and consumes every prior component.

### WAVE 4 — Verification, live test, and final review

1. PO creates T07 after T06 integration; T07 is the only Coder allowed to edit `scripts/verify.ps1`.
2. PO reviews T07 and runs the authoritative verifier on a clean integration worktree.
3. PO creates T08 only after T07 passes; T08 runs the live gate against a disposable DXF.
4. PO reviews T08 evidence, records `PASS`, `SKIP`, or `NOT RUN`, updates `docs/STATUS.md`, and decides whether the integration branch is ready for merge to `main`.

## Coder Review Protocol

For each returned commit, the PO checks:

1. `git show --stat --oneline <commit>` contains only the allowed files.
2. `git diff <parent> <commit> --check` is clean.
3. The task's mandatory commands ran from the task worktree and have fresh output.
4. No forbidden file, private artifact, SDK binary, generated output, or unrequested refactor is present.
5. The Coder's final report names the commit, changed files, test commands/results, live status, and known limitations.
6. Only then does the PO cherry-pick into `integration/autocad-dotnet-option-a`.

If a commit violates its write-set or fails a mandatory test, the PO does not cherry-pick it. The PO sends a bounded correction task to the same Coder branch or requests a new Coder with the exact finding; no silent manual patch is applied.

## Final Acceptance

- T01–T07 task tests pass and the authoritative `scripts\verify.ps1` passes from a clean integration worktree.
- `CADAGENT_HEALTH`, `CADAGENT_REVIEW`, `CADAGENT_DISPATCH`, and `CADAGENT_CLOSE_DISPOSABLE` are present in the built plugin boundary.
- Python `dotnet_ipc` and C# use the same schema version and request/result fields.
- Existing File IPC tests and dispatcher behavior remain unchanged.
- AutoCAD live evidence is explicitly marked `PASS`, `SKIP`, or `NOT RUN`; no missing prerequisite is reported as pass.
- `docs/STATUS.md` is updated only after final review and contains only fresh evidence actually run.
- No unresolved P0/P1 issue remains; any deferred P2 is named with an owner and reason in the final review record.
