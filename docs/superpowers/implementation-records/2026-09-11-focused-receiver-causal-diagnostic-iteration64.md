# Focused-Receiver Causal Diagnostic — Iteration 64

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`
Evidence/docs head before this record: `403492fdad903f90c6f032c075b1e57e3442994c`

## Authority and boundary

SOL's iteration-63 diagnosis was:

```text
VERDICT=MATERIAL_FINDING
MATERIAL_FINDING=FIRST_CAUSAL_BOUNDARY=RECEIVER_TARGET_MISMATCH_HYPOTHESIS_NOW_MEASURED
HUMAN_GATE=NO
```

The authorized single bounded diagnostic was:

```text
fresh disposable QNEW
same-HWND document-ready
capture current owned GUI-thread focus HWND/PID
send only the existing post_qnew_entry marker expression with the same WM_CHAR framing directly to that focused HWND
wait for the exact marker
close/cleanup
```

The diagnostic did not call the production trigger, use a focus workaround,
retry, load NETLOAD or dispatcher, issue FileIPC or Task-6, access
source/candidate/DXF, save, or mutate production CAD state.

## Focused-receiver send result

The disposable session reached document-ready with:

```text
owned_main_hwnd=5181128
owned_pid=29312
owned_gui_thread_id=19756
focus_hwnd=13044028
focus_class=Afx:00007FF77AB10000:28:0000000000000000:0000000000000002:00000000329103CD
focus_pid=29312
focus_visible=true
capture_hwnd=0
```

The existing marker expression was framed exactly as the production trigger
frames text: two ESC UTF-16 code units, the expression, and a terminating CR.
It was sent directly to the captured focus HWND with `PostMessageW`:

```text
code_units=299
target_hwnd=13044028
post_result=all_code_units_posted
post_error=null
marker_present=false
marker_content=null
```

Every `PostMessageW` call returned success, but AutoCAD did not produce the
exact `CAD_AGENT_START_TAB_POST_QNEW_ENTRY` marker. Therefore changing the
receiver from the visible `MDIClient` to the actual focused child is not, by
itself, a sufficient repair. The first causal boundary remains semantic
command consumption/dispatch, not Python-side post-call success.

## Cleanup and safety

- The initial close call reported
  `MCPTimeoutError: START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`.
- Bounded fallback cleanup closed the exact disposable PID `29312` without
  saving; a follow-up process check found PID `29312` absent.
- The proof root
  `C:/temp/cad-agent-task6-live-20260911/focused-receiver-proof-iteration64`
  had no remaining entries.
- No source, candidate, accepted drawing, DXF, FileIPC request, or production
  CAD state changed. No production code changed.
- Fresh SOL diagnosis is required before any further trigger or implementation
  change.
