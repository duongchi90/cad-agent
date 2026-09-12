# Kernel32 Binding Correction — Iteration 125

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-124 native-binding correction  
Executor HEAD after implementation: `8967722f6a502d7a4a31b28ddbba30e88879bbff`

## Bounded correction

The foreground helper now obtains `GetCurrentThreadId` from
`ctypes.windll.kernel32`. `GetWindowThreadProcessId`, `AttachThreadInput`,
`ShowWindow`, `SetForegroundWindow`, and `GetForegroundWindow` remain on
`user32`. The exact-HWND fail-closed readback and detach-in-`finally` behavior
are unchanged.

The causal regression uses a `user32` test double that deliberately does not
expose `GetCurrentThreadId`; only its `kernel32` double exposes that API. The
pre-correction focused run therefore failed at the wrong-DLL lookup, while the
post-correction run passed. No plugin bootstrap, raw-LISP transport, FileIPC,
candidate/source/DXF/CAD behavior, key-free `DRAFT_REFERENCE` policy, or
SourceCustody HMAC contract was changed.

## Verification

- Focused Windows-trigger verification: 23 passed, 1 causal-red deselected,
  3 subtests.
- Focused DotNetIPC verification: 82 passed, 52 subtests.
- Ruff: passed.
- Authoritative `scripts/verify.ps1`: exit 0.
- .NET: 238 passed, 0 failed.
- Offline Python: 3319 passed, 21 deselected, 80 subtests.
- Offline JUnit: 3399 tests, 0 failures, 0 errors, 0 skipped.
- Causal-red negative oracle: 1 expected failure.
- Real-data: 2 skipped because private inputs were unavailable.
- AutoCAD Mechanical: 17 skipped because live prerequisites were unavailable.
- Live marker and M2 benchmark: `NOT RUN`.
- Repository clean at verification start and end; `git diff --check` clean.

No live epoch was run after this correction. The exact page-1 candidate remains
hash-bound at SHA-256
`167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.

## Canonical checkpoint

```text
STATE=VERIFIED
EVIDENCE=This record; pushed code commit 8967722f6a502d7a4a31b28ddbba30e88879bbff; focused Windows-trigger 23 passed/1 deselected/3 subtests; DotNetIPC 82 passed/52 subtests; Ruff passed; scripts/verify.ps1 exit 0; .NET 238 passed; offline Python 3319 passed/21 deselected/80 subtests; offline JUnit tests=3399 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD 17 skipped; live marker/M2 NOT RUN; clean tree; no live rerun or source/DXF/CAD mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_KERNEL32_BINDING_LIVE_FOREGROUND_HANDOFF_AND_RAW_LISP_ACK_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review, then if clear run exactly one disposable read-only live epoch against the same hash-bound page_01.dxf with the corrected owner; require exact foreground handoff, same-expression ACK before activation, exact active-document identity, one health call, no-save cleanup, and stop at first causal failure
HUMAN_GATE=NO
```
