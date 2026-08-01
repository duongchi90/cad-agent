# AutoCAD .NET T10 Close Live Review

- Date: 2026-08-01
- Candidate commit: `00797d997424309766a386db3dce6797e04aab1c`
- Branch: `integration/autocad-dotnet-option-a`
- Host: AutoCAD Mechanical 2027 on Windows
- Scope: disposable DXF only; no production drawing mutation

## Test fixture

- Drawing: `C:\temp\cadagent_dotnet_live_20260801\dotnet_live.dxf`
- Stable entity handle: `2F`
- Expected entity: `LINE`, layer `0`, start `(0, 0)`, end `(100, 0)`
- DLL loaded with AutoCAD's one-time unsigned-file prompt accepted using
  **Load Once**. No permanent trusted-folder or publisher setting was added.

## Direct .NET IPC smoke

The Windows `CADAGENT_DISPATCH` trigger was used against the newly loaded DLL.

| Request | Result | Evidence |
|---|---|---|
| `t10-live-health-5` | PASS | `success=true`, `active_document=true`, `read_only=true`, `changed=false`, IPC directory readable/writable |
| `t10-live-review-1` | PASS | `success=true`, handle `2F`, LINE geometry matched, no warnings/errors, `changed=false` |
| `t10-live-close-1` | PASS | `success=true`, `closed_without_saving=true`, `changed=false` |

Postcondition: AutoCAD returned to the `Start` screen, and the disposable DXF
remained on disk. The existing non-disposable `Drawing1.dwg` session was not
closed, loaded, modified, or saved.

## Repository verification

Authoritative command:

```powershell
$env:MSBUILDDISABLENODEREUSE='1'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 `
  -PythonExe 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe'
```

Result: exit `0`.

- C# Release x64 tests: `50 passed, 0 failed, 0 skipped`
- .NET IPC JUnit: `34/0/0/0`
- Offline JUnit: `439/0/0/0`
- Real-data unavailable probe: `2 skipped`
- AutoCAD Mechanical unavailable probe: `7 skipped`
- AutoCAD automated live marker: `NOT RUN` because the repository's full live
  harness prerequisites (`CAD_AGENT_FILE_IPC` and legacy LISP path) were not
  available. The direct .NET smoke above is independently recorded as PASS.

## Review decision

**APPROVED.** T10's deferred `_.CLOSE _N ` boundary removes the synchronous
document-close failure observed in T09 while preserving the disposable and
no-save guards. No production drawing was changed.
