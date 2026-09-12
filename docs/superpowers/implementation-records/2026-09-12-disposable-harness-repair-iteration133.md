# Disposable Harness Repair — Iteration 133

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-132 material finding and one offline-only harness repair  
Executor HEAD before this docs-only record: `5dcb357`

## Bounded repair

The disposable benign-window diagnostic harness now configures `DefWindowProcW`
with pointer-width-safe Win32 signatures, preventing the callback's previous
`OverflowError`. Its foreign-foreground setup is factored into a bounded
precondition routine that records the `SetForegroundWindow` result, polls
boundedly, and returns `verified=True` only when `GetForegroundWindow()` reads
back the exact benign HWND. The caller fails closed and does not invoke the
production foreground helper when that proof is absent.

Production `_reacquire_windows_foreground` was not changed. No live session,
plugin/raw-LISP delivery, candidate/health operation, source/DXF/CAD mutation,
or key-policy change occurred.

## Verification

- Disposable harness tests:
  `3 passed in 0.05s`.
- `DefWindowProcW` argument and pointer-width return signatures were verified.
- The precondition gate was verified to reject non-exact foreground readback and
  accept exact foreground readback.
- No live rerun was performed after this repair; the next live action remains
  SOL-gated.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=VERIFIED
EVIDENCE=This record; disposable harness tests 3 passed; DefWindowProcW pointer-width signature verified; bounded foreign precondition gate verified for exact and non-exact readback; production foreground helper unchanged; no live rerun, plugin/raw-LISP/candidate/health, or source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_DISPOSABLE_HARNESS_REPAIR_LIVE_NATIVE_OUTCOME_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only native-outcome diagnostic with the repaired harness, verified benign foreign HWND/PID foreground first, then invoke unchanged production helper exactly once and capture all native outcomes; stop immediately afterward
HUMAN_GATE=NO
```
