# Demand-Load Semantic Health Oracle — Iteration 76

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Implementation commit: `4de93998b546bf2b4cfd4c9943bea8fd34efdcb3`
Prior evidence/docs commit: `b7e6f958cc4ab923c05db28c49cf1c031b17e195`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`

## Authority and boundary

SOL's iteration-75 diagnosis was:

```text
VERDICT=CLEAR_CONTINUE
MATERIAL_FINDING=NONE
HUMAN_GATE=NO
```

The authorized action was exactly one fresh reversible demand-load semantic
health oracle through the existing startup-script and .NET/FileIPC owners:

- pre-create exactly one unique existing `health` request;
- stage/install the proven `CadAgent.bundle` with the current Release DLL;
- launch one disposable AutoCAD with the verified default DWT via `/t` and a
  temporary `/b` script containing only `CADAGENT_DISPATCH`;
- do not require CadAgent to be loaded before command invocation;
- require the matching health result and then verify exactly one demand-loaded
  installed module with matching path/SHA-256;
- close the exact PID without saving, remove only temporary state, and verify
  zero owned survivors.

No WM_CHAR/PostMessageW, focus manipulation, additional operation, Task-6,
source/candidate/DXF, registry mutation, production-code change, or retry was
performed.

## Oracle evidence

- Request ID: `health-cadagent-demandload-iter76-20260911`.
- Startup script bytes were exactly `CADAGENT_DISPATCH\r\n`; no QNEW was in
  the script.
- Verified DWT:
  `C:/Program Files/Autodesk/AutoCAD 2027/Acadm/UserDataCache/en-US/Acadm/Template/acad.dwt`.
- DWT SHA-256 before and after:
  `B4F8B4EA726BAB4B50049F4AA54BA6540F52BD14961F851F49DA705CDC292D42`.
- Document-ready was observed on HWND `6295198` / PID `31780`.
- The matching result reported `schema_version=1.0`, `operation=health`,
  `success=true`, `changed=false`, and `errors=[]`, with
  `request_id=health-cadagent-demandload-iter76-20260911`.
- The result payload identified AutoCAD Mechanical 2027 and the installed
  `CadAgent.AutoCAD2027.dll` binary. It was read-only and reported IPC
  readable/writable.
- Post-result owned-PID inspection found exactly one installed module at
  `C:/Users/dkv/AppData/Roaming/Autodesk/ApplicationPlugins/CadAgent.bundle/Contents/Windows/CadAgent.AutoCAD2027.dll`.
- Source/staged/installed SHA-256 matched:
  `BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97`.
- `demand_load_identity_verified=true` and the oracle exited `0`.

## Cleanup and disposition

Cleanup verified the exact PID, temporary installed bundle, request/result
pair, and startup script absent. The retained proof is:

`C:/temp/cad-agent-task6-live-20260911/demandload-semantic-health-iteration76/demandload-health-proof.json`

This closes the command-demand activation and semantic health boundary for the
reviewed scope. Fresh SOL review is required before any Task-6 or
source/candidate/DXF action.
