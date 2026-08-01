# Task 2 Report — Shared IPC Contracts and Offline Primitives

## Status

IMPLEMENTED / PARTIALLY VERIFIED. The requested schemas, DTOs, validation, atomic request/result file store, and discoverable xUnit v3 tests are committed on the assigned branch. The mandatory focused test command cannot currently compile because the T01 test project has no xUnit v3 or test SDK package reference; the PO’s stated T01 foundation fix is required before test discovery can run.

Worktree: `D:\cad-agent-master\cad-agent\.worktrees\autocad-dotnet-t02-contracts`

Branch: `codex/autocad-dotnet-t02-contracts`

## Commits

- `15887b0` — `feat: add AutoCAD .NET IPC contracts and file store`
- This report is a separate task-evidence commit following the implementation commit.

## Changed files

- `contracts/autocad-ipc/request.schema.json`
- `contracts/autocad-ipc/result.schema.json`
- `contracts/autocad-ipc/operations/health.schema.json`
- `contracts/autocad-ipc/operations/review.schema.json`
- `contracts/autocad-ipc/operations/close-disposable.schema.json`
- `contracts/autocad-ipc/examples/health-request.json`
- `contracts/autocad-ipc/examples/health-result.json`
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/JsonFileStore.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/JsonFileStoreTests.cs`

No project files, commands, drawing/review/mechanical files, Python, scripts, status files, old dispatcher, or other task-owned files were changed.

## Verification

- `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64` — exit 1 in the current T01 scaffold. Compilation stops with `CS0246` for `Xunit`, `FactAttribute`, and `Fact` because the untouched test project has no xUnit v3/test SDK package reference. Tests were converted to 11 public instance `[Fact]` methods as required; no static `RunAll` harness remains.
- `dotnet build autocad_plugin/CadAgent.AutoCAD2027 -c Release -p:Platform=x64 --no-restore -v:minimal` — exit 0, with 3 pre-existing AutoCAD reference-conflict warnings from the scaffold.
- PowerShell JSON parse over all `contracts/autocad-ipc/**/*.json` — exit 0; all 7 schema/example files parsed.
- `git diff --check` — exit 0.

## Correction appended

The initial test files used static `RunAll` methods because the T01 scaffold did not yet expose a test framework. Per the T02 correction, both files now use discoverable xUnit v3 `[Fact]` methods and xUnit assertions. Project configuration was not modified. The current compile failure is therefore accurately reported as an environment/foundation dependency, not hidden or converted into a false pass.

## Concerns

The PO must integrate the T01 shared xUnit v3/test SDK foundation fix and rerun the exact focused `dotnet test` command. No AutoCAD live gate was requested or run. Do not merge from this worktree.
