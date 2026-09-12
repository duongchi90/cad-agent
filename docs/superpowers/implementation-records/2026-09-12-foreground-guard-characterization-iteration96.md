# Raw-LISP foreground guard characterization — iteration 96

## Authority and scope

Fresh SOL review of iteration 95 required one offline characterization of the
executor-branch foreground guard. This record does not authorize a live retry,
focus workaround, timeout/code change, candidate activation, health, FileIPC,
setup, persistence, or CAD/source/DXF mutation.

Reviewed owner: `make_windows_lisp_trigger`, which delegates to the existing
`_make_windows_text_trigger` at branch head
`8712134538b70a28ca29e5bd2bf5c205db84d938`.

## Exact guard predicates and inputs

The existing trigger performs these checks before and during `PostMessageW`:

1. `GetWindowThreadProcessId(hwnd)` must return a non-zero `owner_pid`.
2. `EnumChildWindows(hwnd, ...)` plus `GetClassNameW` identifies the child
   windows named `MDIClient`. Exactly one such child must both belong to
   `owner_pid` and satisfy `IsWindowVisible`; otherwise the trigger fails with
   `WINDOW_RECEIVER_AMBIGUOUS`.
3. `GetWindowThreadProcessId(hwnd)` and the selected receiver must still both
   equal `owner_pid`; otherwise the trigger fails with
   `WINDOW_IDENTITY_CHANGED`.
4. `GetForegroundWindow()` must equal the bound top-level `hwnd`. If it does
   not, the owner calls `ShowWindow(hwnd, 9)` and `SetForegroundWindow(hwnd)`
   once, then reads `GetForegroundWindow()` again. A mismatch fails with
   `WINDOW_FOREGROUND_INVALID` before any character is posted.
5. For every UTF-16 code unit in the framed expression, the owner repeats the
   top-level and receiver PID checks and requires
   `GetForegroundWindow() == hwnd` before `PostMessageW(target, 0x0102, ...)`.

Therefore `WINDOW_FOREGROUND_INVALID` has two possible locations in the
existing owner: the post-`SetForegroundWindow` readback, or a per-character
foreground readback. The predicate compares foreground HWND equality; it does
not independently compare foreground PID, process path, or title. The
document-ready Boolean proves the same owned HWND reached a non-`[start]`
title, but it does not prove that HWND remained foreground at the later raw
trigger call.

## Evidence comparison

Iteration 95 recorded `DOCUMENT_READY=PROVEN` on owned HWND `460582` / PID
`1748`, followed by `MCPToolError: WINDOW_FOREGROUND_INVALID`. The proof has no
foreground HWND/PID sample at the trigger readback and no phase marker, so it
cannot distinguish an actually non-foreground owner from a foreground change
between an external observation and the guard's readback. Candidate
activation and health therefore remain `NOT_PROVEN`/`NOT_RUN`.

Existing runtime evidence is consistent with this unresolved distinction:

- iteration 61 observed the owned HWND/PID also as foreground after
  document-ready, but only at that observation point;
- iteration 62 sampled a stable foreground identity around one trigger and the
  trigger returned, yet the post-QNEW marker was absent;
- iteration 73 again stopped at `WINDOW_FOREGROUND_INVALID` before
  `PostMessageW` delivery.

The existing offline guard tests cover both the true-owner reacquisition path
and fail-closed foreign-foreground/PID drift paths. The focused run passed
`8 passed, 12 deselected, 3 subtests passed`. The complete module was
`19 passed, 1 failed`: the one failure is the intentionally marked
`causal_red` test proving that `PostMessageW=True` is not a receiver ACK; it is
not a foreground-guard failure.

## Cheapest future read-only oracle

Reuse the existing `_make_windows_text_trigger` owner and one fresh disposable
session. Capture a high-frequency, read-only identity trace around the single
existing raw-LISP trigger on the exact bound HWND: foreground HWND,
`GetWindowThreadProcessId` PID, process identity/title, and the trigger's
returned error. Classify only:

- foreground remains a different HWND/PID at the trigger boundary and the
  guard returns `WINDOW_FOREGROUND_INVALID`:
  `OWNED_HWND_NOT_FOREGROUND`;
- the owned HWND/PID is observed foreground immediately before or throughout
  the trace, yet the guard returns `WINDOW_FOREGROUND_INVALID`, or the trace
  shows a transition during the call:
  `FOREGROUND_GUARD_FALSE_NEGATIVE_OR_RACE`.

This oracle adds observation only; it does not force focus, retry delivery, or
change the production owner. No implementation change is justified by the
current evidence.
