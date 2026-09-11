# Foreground-Identity Diagnostic — Iteration 61

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`
Evidence/docs head before this record: `69086e3c90bc87368ae1176822a3977b5109d22d`

## Authority and boundary

SOL's iteration-60 diagnosis was:

```text
VERDICT=MATERIAL_FINDING
MATERIAL_FINDING=WINDOW_FOREGROUND_PRECONDITION_BLOCKS_PROCESS_BOUND_RAW_LISP_DELIVERY
HUMAN_GATE=NO
```

The authorized single bounded diagnostic was observation-only:

```text
fresh disposable QNEW session
same-HWND document-ready
record owned HWND/PID and actual foreground HWND/PID/process/title
close/cleanup
```

The diagnostic did not call the raw-LISP trigger, use a
`SetForegroundWindow` workaround, load NETLOAD or dispatcher, issue FileIPC or
Task-6, access source/candidate/DXF, save, or mutate production CAD state.

## Observation

After same-HWND document-ready, the captured identities were:

```text
owned_hwnd=7867904
owned_pid=10328
foreground_hwnd=7867904
foreground_pid=10328
foreground_process=acad.exe
foreground_process_path=C:/Program Files/Autodesk/AutoCAD 2027/acad.exe
foreground_title=Autodesk AutoCAD 2027
owned_is_foreground=true
owned_pid_is_foreground_pid=true
```

This proves only that the owned AutoCAD window was foreground at this
observation point. It does not claim that the earlier raw-LISP trigger failure
is resolved or justify a trigger retry.

## Cleanup and safety

- The owned disposable AutoCAD process was closed without saving.
- The proof root
  `C:/temp/cad-agent-task6-live-20260911/foreground-identity-proof-iteration61`
  had no remaining entries.
- No source, candidate, accepted drawing, DXF, FileIPC request, or production
  CAD state changed.
- Fresh SOL diagnosis is required before any trigger retry or production-code
  change.
