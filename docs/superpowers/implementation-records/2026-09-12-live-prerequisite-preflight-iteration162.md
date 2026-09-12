# Live Prerequisite Preflight — Iteration 162

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / raw-LISP startup boundary  
Preflight code HEAD: `139e53db2cf697baf3ba24fbd43b688aaf168c24`

## Scope

This was one read-only live-prerequisite preflight cleared by fresh SOL
review. It checked current GitHub/local HEAD, the truthful AutoCAD Mechanical
2027 process/session, process-bound window/document capability, IPC/LISP
configuration, and plugin identity. It did not launch AutoCAD, APPLOAD or
NETLOAD anything, send LISP, create a disposable drawing, invoke File IPC,
touch the viewport, or mutate source/customer/accepted CAD, candidate, DXF,
or key policy.

## Observed state

- Local exact HEAD: `139e53db2cf697baf3ba24fbd43b688aaf168c24`.
- Local `origin/main` and fresh GitHub `main`: both
  `e8fc0092ee46750e50de0ea408fd91811cae10c2`.
- Repository worktree: clean.
- Existing local bridge health: `CADAgentLocalMCP 1.0.0`, `status=ok`.
- AutoCAD executable exists at
  `C:\Program Files\Autodesk\AutoCAD 2027\acad.exe`.
- AutoCAD process: `ABSENT`; therefore no process-bound HWND and no truthful
  document-ready observation are available.
- `CAD_AGENT_FILE_IPC`, `CAD_AGENT_FILE_IPC_DIR`,
  `CAD_AGENT_DOTNET_IPC_DIR`, `CAD_AGENT_AUTOCAD_HWND`,
  `CAD_AGENT_AUTOCAD_LISP_PATH`, `CAD_AGENT_LEAN_DISPOSABLE_DWG`, and
  `CAD_AGENT_AUTOCAD_EXE`: all `UNSET`.
- Repository LISP source exists at
  `mcp_integration_lib\mcp_dispatch.lsp`, but no live LISP-path configuration
  is admitted by the environment.
- The Release x64 plugin build exists at
  `autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll`
  with SHA-256
  `5bc86032c5333749c08756630d6e5059097421acadfc2930bcc2e0a18dce81d5`.
- The bundle-declared module target
  `autocad_plugin\CadAgent.bundle\Contents\Windows\CadAgent.AutoCAD2027.dll`
  is absent, so no loaded/deployed plugin identity can be truthfully claimed.

## Decision

```text
LIVE_ORACLE=NOT_RUN
STATE=LIVE_PREREQUISITES_ABSENT
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=TRUTHFUL_AUTOCAD_PROCESS_HWND_DOCUMENT_AND_PLUGIN_SESSION_NOT_AVAILABLE
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact preflight; if all prerequisites later become truthfully present, rerun only this read-only preflight before any disposable marker oracle; otherwise continue only with the next approved offline boundary
HUMAN_GATE=NO
```

The missing state is recorded as `NOT_RUN`, not `SKIP` or `PASS`, for the live
oracle. No readiness repair is authorized by this preflight.

