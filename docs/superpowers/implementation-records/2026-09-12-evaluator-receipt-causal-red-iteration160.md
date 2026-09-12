# AutoCAD Evaluator Receipt Causal RED — Iteration 160

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / raw-LISP startup boundary  
Verified code HEAD: `ee174db267fc23da6570968eea40865c510ea0de`

## Scope and authorization

Fresh SOL review of iteration 159 authorized one owner-local causal RED only.
This iteration adds that RED, routes the authoritative verifier to it, and
keeps the repository at the intentional failing boundary. No production
behavior, transport, dispatcher, FileIPC, viewport, source, DXF, candidate,
drawing, or key-policy mutation was made.

## Causal RED

`RawLispConsumptionAckTests.test_evaluator_receipt_contract_is_exact_and_fail_closed`
calls the existing private `_send_raw_lisp_with_ack` exactly once for each
missing/wrong marker case and requires the existing fail-closed timeout plus
root-safe cleanup. It then injects one exact marker and requires the explicit
receipt classification:

```text
raw_lisp_evaluator_receipt=CONFIRMED
receiver_consumption=NOT_SEPARATELY_OBSERVABLE
```

The negative cases already satisfy the fail-closed contract. The positive
case is intentionally RED because the current private owner returns the
legacy bare `True` instead of the classified receipt mapping. This isolates
the concrete missing behavior without changing the AutoCAD seam.

The former enqueue-only receiver test remains a normal characterization test
and records `POSTMESSAGE_ENQUEUED_BUT_RECEIVER_CONSUMPTION_UNOBSERVED`; the
authoritative causal gate now has exactly one marked test and one intentional
failure.

## Verification evidence

- Focused normal owner tests: `91 passed, 1 deselected, 9 subtests`.
- Causal RED gate: `1 failed, 49 deselected`; JUnit
  `tests=1 failures=1 errors=0 skipped=0`.
- Ruff on the changed test/contract files: `All checks passed!`.
- Full `scripts/verify.ps1`: exit `0`, `All checks passed!`.
- Full offline Python: `3334 passed, 22 deselected, 80 subtests passed`;
  offline JUnit `tests=3414 failures=0 errors=0 skipped=0`.
- C# tests: `238 succeeded`; .NET IPC JUnit:
  `tests=134 failures=0 errors=0 skipped=0`.
- Real-data unavailable-state probe: `2 skipped`.
- AutoCAD Mechanical unavailable-state probe: `17 skipped`.
- Live/M2: `NOT RUN` because the approved live prerequisites/opt-in are
  absent.
- `git diff --check`: clean; repository was clean before this evidence-only
  record was added.

## Decision and next action

```text
STATE=CAUSAL_RED_CHARACTERIZED
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_EVALUATOR_RECEIPT_CLASSIFICATION_NOT_EXPOSED_BY_CURRENT_PRIVATE_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact-head RED; if clear, implement only the minimal private raw-LISP receipt classification in mcp_integration_lib/mcp_client.py and run the focused GREEN, with no PostMessageW/transport/dispatcher/FileIPC/viewport/live change
HUMAN_GATE=NO
```

