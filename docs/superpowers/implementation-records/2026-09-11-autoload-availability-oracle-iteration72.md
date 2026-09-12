# Autoload Availability Oracle After ProductCode Repair — Iteration 72

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Implementation head: `9f81d67b10afc86cdfe3fd72010cb91cd7544812`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`

## Authority and boundary

SOL's iteration-71 diagnosis was:

```text
VERDICT=CLEAR_CONTINUE
MATERIAL_FINDING=NONE
HUMAN_GATE=NO
```

The authorized action was exactly one fresh reversible user-scoped autoload
availability oracle using the repaired `ProductCode` manifest:

- stage the complete `CadAgent.bundle` with the exact current Release DLL;
- record source/staged/installed SHA-256 identity;
- copy only that bundle to the current user's Autodesk `ApplicationPlugins`;
- launch one fresh disposable AutoCAD with QNEW-only `/b` startup;
- wait for same-HWND document-ready;
- read-only inspect the exact owned PID and require exactly one loaded module
  whose path and SHA-256 match the installed bundle/source;
- close without saving, remove only the installed bundle, and verify cleanup.

The epoch did not invoke `CADAGENT_DISPATCH`, WM_CHAR/raw-LISP, FileIPC,
Task-6, source/candidate/DXF access, registry mutation, or a retry.

## Live evidence

The staged and installed DLL remained byte-identical:

```text
source_sha256   = BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97
installed_sha256= BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97
```

The fresh owned process reached document-ready and loaded exactly one module:

```text
owned_hwnd=5047694
owned_pid=32152
document_ready_observed=true
exact_installed_module_matches=1
module_path=C:/Users/dkv/AppData/Roaming/Autodesk/ApplicationPlugins/CadAgent.bundle/Contents/Windows/CadAgent.AutoCAD2027.dll
```

The loaded module path resolved to the installed bundle module, and its hash
matched the staged/source DLL. The oracle exited successfully.

## Cleanup and safety

- The initial close again reported
  `MCPTimeoutError: START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`.
- Bounded exact-PID cleanup completed; PID `32152` was absent afterward.
- The exact temporary installed `CadAgent.bundle` was removed and verified
  absent afterward.
- Proof is retained at
  `C:/temp/cad-agent-task6-live-20260911/autoload-availability-iteration71/availability-proof.json`.
- No source, candidate, accepted drawing, DXF, FileIPC, dispatcher,
  production code, registry, or live drawing state changed.
