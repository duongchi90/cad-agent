# Authoritative Receipt Contract GREEN — Iteration 161

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / raw-LISP startup boundary  
Verified code HEAD: `19debd00b63dc1483659993280bcd1facc9893ac`

## Scope and authorization

Fresh SOL review cleared the minimal private receipt classification at
`de578bbb`. A second bounded action then cleared reconciliation of the
authoritative verifier. This iteration changes only the verification contract
and its contract test after the production GREEN. It does not modify
production again and does not touch PostMessageW, transport, dispatcher,
FileIPC, viewport, live CAD, source, DXF, candidate, drawing, or key policy.

## Resolved receipt invariant

The existing private
`FileIPCLiveMCPClient._send_raw_lisp_with_ack` owner now returns the explicit
combined receipt only after one exact request-owned marker readback:

```text
raw_lisp_evaluator_receipt=CONFIRMED
receiver_consumption=NOT_SEPARATELY_OBSERVABLE
```

Missing, wrong, unreadable, timeout, trigger-error, and unsafe-root paths
remain fail-closed with the existing error/cleanup behavior. The native
`PostMessageW` return remains enqueue-only evidence, and no receiver-only ACK
is claimed.

## Verification contract reconciliation

The previous verifier expected the receipt owner test to fail as an
intentional RED. That expectation became stale after the approved GREEN. The
authoritative script now runs the same independent owner contract as a
passing receipt gate and requires exactly one test with zero failures, errors,
or skips. The owner test still proves both halves of the invariant in one
bounded case: exact positive classification and negative fail-closed cleanup.

## Verification evidence

- Focused owner suite: `78 passed, 9 subtests`.
- Focused verifier/project contract tests: `17 passed`.
- Ruff on the affected Python files: `All checks passed!`.
- Full `scripts/verify.ps1`: exit `0`, `All checks passed!`.
- Offline Python: `3334 passed, 22 deselected, 80 subtests passed`;
  JUnit `tests=3414 failures=0 errors=0 skipped=0`.
- Receipt contract owner gate: `1 passed, 49 deselected`;
  JUnit `tests=1 failures=0 errors=0 skipped=0`.
- C# tests: `238 succeeded`.
- .NET IPC JUnit: `tests=134 failures=0 errors=0 skipped=0`.
- Real-data unavailable-state probe: `2 skipped`.
- AutoCAD Mechanical unavailable-state probe: `17 skipped`.
- Live/M2: `NOT RUN` because the approved live prerequisites/opt-in are
  absent.
- The verifier started from a clean tree and completed without changing
  tracked or non-ignored repository state; `git diff --check` passed.

## Decision and next boundary

```text
STATE=OFFLINE_GREEN_VERIFIED
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=REAL_AUTOCAD_EVALUATOR_RECEIPT_AND_STARTUP_COMPLETION_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact verified HEAD; if clear, authorize at most one disposable read-only live marker oracle through the existing startup owner, stopping at the first absent/wrong marker and forbidding retry, downstream FileIPC, viewport, source, DXF, or CAD mutation
HUMAN_GATE=NO
```

