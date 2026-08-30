# M2 Loaded-Plugin Binary Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact executing-plugin binary identity to the existing AutoCAD Mechanical health response so M2 live evidence can fail closed on stale or spoofed DLL identity.

**Architecture:** Reuse `OperationDispatcher` as the existing health owner and add one internal read-only assembly-file hashing helper. The C# response reports the assembly path and SHA-256; the existing Python M2 harness compares that value with the exact expected Release artifact. No new transport, store, or identity subsystem is introduced.

**Tech Stack:** C#/.NET 10 Windows class library, xUnit v3, existing File IPC result contract, Python 3.11 M2 harness, PowerShell verification.

**Spec:** `docs/superpowers/specs/2026-08-30-m2-loaded-plugin-identity-design.md`

## Global Constraints

- Base SHA: `738dac0b11231a71f91376ebb5ef22b6c709461d`.
- Supported runtime: AutoCAD Mechanical 2027 and the existing C# health/FileIPC owner.
- The helper must hash `typeof(OperationDispatcher).Assembly.Location`, not a request/configured/caller-supplied path or hash.
- Missing, empty, non-file, or unreadable assembly identity must fail closed through the existing dispatcher error boundary.
- Hash output is lowercase 64-character SHA-256; no DLL load, replacement, process control, or drawing mutation is permitted.
- `C:\temp\cad-agent-m2-record.json`, customer drawings, and accepted artifacts remain outside Git.

---

### Task 1: Causal C# identity RED

**Files:**
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/LoadedPluginIdentity.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`

**Interfaces:**
- Produces internal `LoadedPluginIdentitySnapshot Capture(Assembly assembly)` and `CaptureBinary(string binaryPath)` helpers for the existing dispatcher and its tests.

- [ ] **Step 1: Write failing tests**

Add tests that expect the health result to include `plugin_binary_path` and an exact lowercase SHA-256 for `typeof(OperationDispatcher).Assembly`, that a request parameter named `plugin_binary_sha256` cannot override the reported value, and that `CaptureBinary` rejects a missing path.

- [ ] **Step 2: Run RED**

Run:

```powershell
dotnet test autocad_plugin\CadAgent.AutoCAD2027.Tests\CadAgent.AutoCAD2027.Tests.csproj --no-restore --filter FullyQualifiedName~OperationDispatcherTests
```

Expected: the new assertions fail because health has no plugin binary identity and the helper does not yet exist.

### Task 2: Minimal existing-owner GREEN

**Files:**
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/LoadedPluginIdentity.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`

**Interfaces:**
- `LoadedPluginIdentitySnapshot Capture(Assembly assembly)` returns `BinaryPath` and `Sha256`.
- `LoadedPluginIdentitySnapshot CaptureBinary(string binaryPath)` opens the exact path read-only and computes SHA-256.

- [ ] **Step 1: Implement the smallest helper**

Use `typeof(OperationDispatcher).Assembly` at the call site. Reject blank `Assembly.Location`, normalize it with `Path.GetFullPath`, require a regular file, open with `FileAccess.Read`, and return `Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant()`.

- [ ] **Step 2: Add the health fields**

In `DispatchHealth`, capture the executing dispatcher assembly and add:

```csharp
["plugin_binary_path"] = JsonSerializer.SerializeToElement(identity.BinaryPath),
["plugin_binary_sha256"] = JsonSerializer.SerializeToElement(identity.Sha256),
```

Do not read plugin identity from `request.Parameters` or any caller value.

- [ ] **Step 3: Run focused GREEN**

Run the Task 1 command and assert all focused tests pass, including missing-file failure and caller-hash non-authority.

### Task 3: Contract and offline verification

**Files:**
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs` only if the existing result round-trip contract needs an explicit health identity assertion.
- Modify: `docs/STATUS.md` with exact evidence after verification.

- [ ] **Step 1: Run nearest regressions**

```powershell
dotnet test autocad_plugin\CadAgent.AutoCAD2027.Tests\CadAgent.AutoCAD2027.Tests.csproj --no-restore
.\.venv-py311\Scripts\python.exe -m pytest tests\test_m2_benchmark.py mcp_integration_lib\tests\test_m2_mechanical_benchmark_live.py -q -p no:cacheprovider
```

- [ ] **Step 2: Verify build without touching the locked Release DLL**

If `bin\x64\Release` is locked by AutoCAD, use an isolated output root such as `C:\temp\cad-agent-m2-plugin-identity-build\` with the existing SDK project and record the exact command/output. Never kill AutoCAD or copy over its DLL.

- [ ] **Step 3: Run canonical offline verifier and checks**

Run `.\scripts\verify.ps1 -SkipAutoCADDotNet`, `git diff --check`, and the documentation contract. Record skipped/not-run live gates explicitly.

- [ ] **Step 4: Commit and push bounded successor**

```powershell
git add autocad_plugin docs\superpowers\specs\2026-08-30-m2-loaded-plugin-identity-design.md docs\superpowers\plans\2026-08-30-m2-loaded-plugin-identity.md docs\STATUS.md
git commit -m "feat: bind health to loaded plugin binary"
git push origin codex/m2-plugin-identity
```

Open a successor PR that depends on PR #309; do not merge either PR until live M2 acceptance is objectively complete.

## Completion State

Status: executing.

Completion Head SHA: pending fresh verification.

Required live gate: AutoCAD Mechanical/FileIPC M2 live acceptance remains `NOT RUN` until the Human-only NETLOAD/session boundary is available.
