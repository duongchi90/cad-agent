# Task Card T04 — Drawing Reader and Read-only Review Core

**Role:** Coder  
**Model:** Luna Extra High (`gpt-5.6-luna`, reasoning `xhigh`)  
**Base:** The exact SHA of `integration/autocad-dotnet-option-a` after PO integrates WAVE 2  
**Branch:** `codex/autocad-dotnet-t04-review-core`  
**Worktree:** `D:\cad-agent-master\cad-agent\.worktrees\autocad-dotnet-t04-review-core`

## Objective

Add the AutoCAD Managed API adapter that identifies the active document by full path and maps read-only entities to stable review payloads.

## Allowed files

- `autocad_plugin/CadAgent.AutoCAD2027/Drawing/ActiveDocumentReader.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Review/EntitySnapshot.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Review/ReviewService.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/ActiveDocumentPathTests.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Review/ReviewMappingTests.cs`

## Forbidden files

Contracts, JSON storage, Mechanical, Commands, Python, existing MCP code, project configuration, scripts, and status files.

## Requirements

- Normalize and compare the active document full path; never identify a drawing by filename alone.
- Use read-only transaction access for LINE, CIRCLE, ARC, TEXT, and DIMENSION.
- Return handle, AutoCAD type, layer, and supported geometry fields.
- Return warnings for unsupported or missing entities without saving, erasing, or changing the document.
- Keep pure payload mapping testable without launching AutoCAD.

## Required verification

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
```

Tests must cover path normalization, supported entity mapping, missing handle, unsupported type warning, and the absence of save/mutation calls in the review service boundary.

## Completion report

Return commit SHA, changed files, tests, and an explicit statement that no mutation/save API is used. Do not merge.
