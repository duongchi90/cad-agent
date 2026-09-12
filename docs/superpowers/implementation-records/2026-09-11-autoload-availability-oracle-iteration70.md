# Autoload Availability Oracle — Iteration 70

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`
Evidence/docs head before this record: `35929618258ecb248d41e2604fd544878317d6d6`

## Authority and boundary

SOL's iteration-69 diagnosis was:

```text
VERDICT=CLEAR_CONTINUE
MATERIAL_FINDING=NONE
HUMAN_GATE=NO
```

The authorized action was exactly one reversible user-scoped autoload
availability oracle:

- stage `CadAgent.bundle` with the existing Release DLL under
  `Contents/Windows`;
- copy the complete staged bundle to the current user's Autodesk
  `ApplicationPlugins` directory;
- launch one fresh disposable AutoCAD with the existing `/b` owner and a
  `_.QNEW`-only startup script;
- wait for same-HWND document-ready;
- read-only inspect the exact owned PID for the installed bundle module and
  matching SHA-256;
- close the exact PID without saving, remove only the installed bundle, and
  verify cleanup.

The epoch did not invoke `CADAGENT_DISPATCH`, WM_CHAR/raw-LISP, FileIPC,
Task-6, source, candidate, DXF, registry mutation, or a retry.

## Staging and identity

The temporary staged bundle contained only the repository manifest and the
approved existing Release DLL. The source and staged/installed file hash was:

```text
source=autocad_plugin/CadAgent.AutoCAD2027/bin/x64/Release/net10.0-windows/CadAgent.AutoCAD2027.dll
sha256=BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97
installed_module=C:/Users/dkv/AppData/Roaming/Autodesk/ApplicationPlugins/CadAgent.bundle/Contents/Windows/CadAgent.AutoCAD2027.dll
```

The installed target did not exist before the epoch and was created only for
this proof.

## Live observation

The fresh owned AutoCAD session reached document-ready on the same owned
window:

```text
owned_hwnd=3280488
owned_pid=33640
document_ready_observed=true
script_order=_.QNEW only
```

Read-only `Get-Process -Id 33640 -Module` completed, but returned zero exact
matches for the installed bundle module and no CadAgent module paths:

```text
exact_installed_module_matches=0
module_paths=[]
```

This is a material negative finding for the availability boundary. It does
not distinguish bundle discovery, manifest/runtime compatibility, trust/load
policy, or another AutoCAD autoload cause. No downstream dispatcher/FileIPC
conclusion is inferred.

## Cleanup and safety

- The initial window close reported
  `MCPTimeoutError: START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`.
- Bounded exact-PID cleanup completed; PID `33640` was absent afterward.
- The exact temporary `CadAgent.bundle` was removed from the current user's
  `ApplicationPlugins`; the installed target was absent afterward.
- The proof is retained at
  `C:/temp/cad-agent-task6-live-20260911/autoload-availability-iteration70/availability-proof.json`.
- No source, candidate, accepted drawing, DXF, FileIPC, dispatcher, or
  production code changed.
- No retry is authorized by this epoch; fresh SOL diagnosis is required.
