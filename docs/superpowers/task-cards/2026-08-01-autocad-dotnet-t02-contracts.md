# Task Card T02 — Shared IPC Contracts and Offline Primitives

**Role:** Coder  
**Model:** Luna Extra High (`gpt-5.6-luna`, reasoning `xhigh`)  
**Base:** The exact SHA of `integration/autocad-dotnet-option-a` after PO integrates T01  
**Branch:** `codex/autocad-dotnet-t02-contracts`  
**Worktree:** `D:\cad-agent-master\cad-agent\.worktrees\autocad-dotnet-t02-contracts`

## Objective

Define the versioned Python/C# JSON contract and testable C# request/result, validation, atomic file, and request-id primitives.

## Allowed files

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

## Forbidden files

Commands, Drawing, Review, Mechanical, Python backend, existing MCP client, scripts, status, project files, and all existing package code.

## Requirements

- Use schema version `1.0` and full absolute Windows drawing paths.
- Require `request_id`, `schema_version`, `operation`, `drawing_full_path`, `drawing_sha256`, `parameters`, and `approval` in requests; allow `drawing_full_path=null` only for `health`.
- Require result fields `request_id`, `success`, `operation`, `drawing_full_path`, `changed`, `entity_handles`, `warnings`, `errors`, `started_at`, and `completed_at`.
- Allow only `health`, `review`, and `close_disposable` operations; reject mutation/repair operations.
- Use new filenames `cadagent_dotnet_request_<request_id>.json` and `cadagent_dotnet_result_<request_id>.json`.
- Atomic writes and cleanup must be request-specific and deterministic.

## Required verification

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
```

The tests must cover invalid version, relative path, missing id, unsupported operation, JSON round-trip, atomic result replacement, request-id isolation, and cleanup.

## Completion report

Return commit SHA, schema list, test command/result, and confirmation that no other task-owned file changed. Do not merge.
