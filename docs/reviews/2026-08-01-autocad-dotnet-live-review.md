# AutoCAD .NET T08 Live Review

- Date: 2026-08-01
- Branch: `codex/autocad-dotnet-t08-live-review`
- Reviewed base/HEAD: `26c70ec2989901d00d2e80641255cc298037148f`
- Live status: **NOT RUN**

## Live prerequisite and safety result

The AutoCAD process was present and responding:

- `acad.exe`: `C:\Program Files\Autodesk\AutoCAD 2027\acad.exe`
- PID: `9396`; window: `AutoCAD Mechanical 2027 - [Drawing1.dwg]`
- Main window handle: `1246340`

A read-only COM/ROT probe detected `AutoCAD.Application`, but did not establish
that the active `Drawing1.dwg` was disposable or safe to operate on. Versioned
ProgIDs `AutoCAD.Application.25.2` and `.25.1` were not detected. No COM
document command, keystroke, NETLOAD, or AutoCAD command was sent.

Therefore the required live sequence was not run: manual `NETLOAD`,
`CADAGENT_HEALTH`, disposable-DXF handle review, and
`CADAGENT_CLOSE_DISPOSABLE` all remain **NOT RUN**. No disposable DXF was
opened, no production/active drawing was touched, and no save or repair was
performed.

Exact prerequisite to rerun: an operator-controlled AutoCAD Mechanical 2027
session with a known disposable DXF under `C:\temp` active, a known review
handle, and a safe manual NETLOAD/command path that does not operate on the
current `Drawing1.dwg`.

## Independent integration-artifact evidence

Commands run from this worktree:

```powershell
dotnet restore autocad_plugin/CadAgent.AutoCAD2027.sln
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --no-restore
dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --no-build --no-restore
```

Results:

- Restore: exit `0`.
- Release x64 build: exit `0`, `3` MSB3277 reference-conflict warnings,
  `0` errors.
- C# tests: **49 passed, 0 failed, 0 skipped, 49 total**.
- Plugin output:
  `autocad_plugin/CadAgent.AutoCAD2027/bin/x64/Release/net10.0-windows/CadAgent.AutoCAD2027.dll`
  SHA-256 `4F52AB11E9850849350AB03438C75BE3EE57CD96770579B53E60DFC7D9DB2CA9`.
  The plugin output contained only the DLL, PDB, and deps JSON; no Autodesk
  `Ac*`, `Ad*`, `Aec*`, or `Autodesk*` DLL was copied to plugin/test output.
- Project review: only `AcCoreMgd`, `AcDbMgd`, and `AcMgd` are direct references,
  each with `Private=false`.
- Production-safety scan: no production `Save`, `SaveAs`, `Erase`, repair, or
  mutation call was found. The only close path is `CloseAndDiscard`, guarded by
  `disposable=true` and `save_changes=false`.
- Existing dispatcher review: `git diff --stat 14fa9fe HEAD --
  mcp_integration_lib/mcp_client.py mcp_integration_lib/reviewer2.py
  mcp_integration_lib/repair2.py mcp_integration_lib/tests/test_file_ipc_live.py`
  was empty, and `git log --oneline 14fa9fe..HEAD --` over those files returned
  no commits.

## Authoritative verifier result

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Result: exit `1`, explicit blocker:
`Python environment not found: .venv-py311\Scripts\python.exe. Run
scripts/bootstrap.ps1 first.` The verifier's Python gates and its live-marker
gate therefore did not run. This blocker does not downgrade or upgrade the
independent C# `49/49` evidence, and build/test success is not live PASS.

## Review disposition

The offline C# artifact evidence is reproducible for the reviewed HEAD. The
AutoCAD live gate is **NOT RUN** because safe disposable-only automation and
manual NETLOAD evidence were not available without touching the active
`Drawing1.dwg`. No production drawing mutation, repair, or save occurred.
