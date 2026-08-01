# Task Card T07 — Authoritative Verification Integration

**Role:** Coder  
**Model:** Luna Extra High (`gpt-5.6-luna`, reasoning `xhigh`)  
**Base:** The exact SHA of `integration/autocad-dotnet-option-a` after PO integrates T06  
**Branch:** `codex/autocad-dotnet-t07-verification`  
**Worktree:** `D:\cad-agent-master\cad-agent\.worktrees\autocad-dotnet-t07-verification`

## Objective

Extend the one authoritative verifier so the C# build/tests and project boundary are checked together with the existing Python gates.

## Allowed files

- `scripts/verify.ps1`
- `tests/test_verification_contract.py`
- `tests/test_autocad_plugin_project.py`

## Forbidden files

All C# production files, Python production files, existing MCP client files, contracts, `docs/STATUS.md`, and all other scripts/tests/docs.

## Requirements

- Restore and build the solution Release x64.
- Run C# unit tests.
- Preserve the current clean-tree provenance and repository snapshot checks.
- Preserve the current Python offline, real-data unavailable, AutoCAD unavailable, Ruff, and diff checks.
- Add contract tests proving the verifier owns the C# commands and does not silently pass a missing live gate.

## Required verification

```powershell
dotnet restore autocad_plugin/CadAgent.AutoCAD2027.sln
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
.\scripts\verify.ps1
```

Run from a clean worktree after committing the task change. The live AutoCAD unavailable probe must remain an explicit skip when variables are removed.

## Completion report

Return commit SHA, verifier output, JUnit totals, and contract-test output. Do not modify `docs/STATUS.md` and do not merge.
