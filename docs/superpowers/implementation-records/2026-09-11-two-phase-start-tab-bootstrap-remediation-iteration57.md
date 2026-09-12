# Two-Phase Start-tab Bootstrap Remediation — Iteration 57

Date: 2026-09-11 (Asia/Saigon)  
Branch: `codex/audit-text-style-compat-20260910`  
Code head: `4bdf197f828737510c1defc39956cf922a3ea28c`  
Docs base before this record: `8389aa6de7e49be6e065e0ca641640e3c6029398`

## Authority and boundary

SOL's fresh iteration-56 diagnosis returned `VERDICT=MATERIAL_FINDING`,
`HUMAN_GATE=NO`, and authorized exactly one non-live bounded remediation:
constrain the owned `/b` startup script to the already-proven `_.QNEW` phase,
then use the existing same-HWND process-bound command/LISP trigger path after
positive document-ready confirmation for plugin load, dispatcher load, and
exact completion acknowledgement. Timeout, source prohibition, claim/readiness
semantics, fail-closed cleanup, and default non-diagnostic behavior had to stay
unchanged. No live retry was authorized.

## Implementation

The owned startup script now contains only:

`_.QNEW\r\n`

Once the same-HWND document-ready probe is positive, the session uses its
process-bound bindings to execute, in order:

1. opt-in `post_qnew_entry` stage marker;
2. NETLOAD and opt-in `netload_return` marker when a plugin is configured;
3. dispatcher LISP load and opt-in `dispatcher_load_return` marker;
4. exact completion marker writer and opt-in
   `completion_marker_writer_return` marker;
5. the existing completion-marker wait.

The final bindings set `dispatcher_preloaded` and
`bootstrap_completion_confirmed` only after the runtime sequence succeeds.
Wrong or missing completion markers still fail closed and clean up the owned
script, marker files, and process. Stage timing remains disabled by default.

## Verification

- TDD RED: the new phase-order test failed before the owner split with
  `START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED`.
- TDD GREEN: focused owner suite passed `40` tests and `6` subtests.
- Ruff passed for the changed implementation and focused test file.
- `git diff --check` passed.
- Authoritative `scripts/verify.ps1` exited `0` on clean code head:
  - .NET: `238` passed;
  - offline Python: `3388` tests, `0` failures, `0` errors, `0` skips;
    `3308` passed, `21` deselected, `80` subtests;
  - offline IPC: `134` tests, clean;
  - causal-RED: one expected negative failure handled;
  - real-data: `2` unavailable skips;
  - AutoCAD Mechanical: `17` unavailable skips;
  - AutoCAD live and M2: `NOT RUN`.

## Review boundary

Code/test commit `4bdf197f828737510c1defc39956cf922a3ea28c` was pushed before
this documentation checkpoint. No AutoCAD live session, source drawing,
candidate drawing, accepted drawing, FileIPC request, extraction, query,
production DXF mutation, or reviewed-HEAD mutation was performed. Fresh SOL
review is required before any live proof or Task-6 action.
