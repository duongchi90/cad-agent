# Startup-Script Health Oracle — Iteration 74

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Implementation head: `9f81d67b10afc86cdfe3fd72010cb91cd7544812`
Evidence/docs head before this record: `5bcbcbad72b82c0c5961790c0f5f6b264456c352`

## Authority and boundary

SOL's iteration-73 diagnosis was:

```text
VERDICT=MATERIAL_FINDING
MATERIAL_FINDING=THE_REMAINING_BOUNDARY_IS_EXTERNAL_COMMAND_ACTIVATION_NOT_PLUGIN_OR_FILEIPC
HUMAN_GATE=NO
```

The authorized action was exactly one fresh reversible semantic health oracle
using the existing AutoCAD startup-script owner:

- pre-create exactly one unique existing .NET/FileIPC `health` request;
- temporarily install the proven bundle;
- launch one disposable AutoCAD with verified local default DWT via `/t` and a
  temporary `/b` script containing only `CADAGENT_DISPATCH`;
- require the matching result JSON;
- close the exact PID without saving, remove only the temporary bundle/script/
  request/result, and verify zero owned survivors.

The epoch excluded QNEW inside the script, WM_CHAR/PostMessageW, focus
manipulation, additional operations, Task-6, source/candidate/DXF access,
registry mutation, production-code changes, and retry.

## Live observation

The verified local default template was:

```text
C:/Program Files/Autodesk/AutoCAD 2027/Acadm/UserDataCache/en-US/Acadm/Template/acad.dwt
sha256=B4F8B4EA726BAB4B50049F4AA54BA6540F52BD14961F851F49DA705CDC292D42
```

The existing `WindowsAutoCADStartTabSession` owner launched:

```text
acad.exe /nologo /t <verified acad.dwt> /b <temporary script>
script=CADAGENT_DISPATCH only; no QNEW
```

The session reached document-ready, but read-only inspection of the exact
owned PID found zero installed CadAgent module matches:

```text
owned_hwnd=6293526
owned_pid=24412
document_ready_observed=true
exact_installed_module_matches=0
module_paths=[]
source_sha256=BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97
installed_sha256=BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97
```

The epoch therefore stopped before waiting for the health result. No semantic
PASS or FileIPC defect is inferred; this is a new negative observation at the
startup-script autoload boundary.

## Cleanup and safety

- PID `24412` was absent after bounded exact-PID cleanup.
- The exact temporary installed bundle was removed and verified absent.
- The exact pre-created request
  `health-cadagent-startup-iter74-20260911` and its result path were cleaned
  and verified absent.
- The temporary script was removed and the default DWT SHA-256 was unchanged.
- Proof is retained at
  `C:/temp/cad-agent-task6-live-20260911/startup-script-health-dispatch-iteration74/startup-health-dispatch-proof.json`.
- No retry was performed; fresh SOL diagnosis is required.
