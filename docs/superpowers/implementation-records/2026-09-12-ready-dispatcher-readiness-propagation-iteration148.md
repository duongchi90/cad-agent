# Ready-dispatcher readiness propagation — iteration 148

## Result

- **Status:** offline GREEN; live execution intentionally not run.
- **Code head before this record:** `b02586b` (`test: cover bootstrap readiness propagation`).
- **RED oracle:** `C:\temp\cad-agent-task6-live-20260911\readiness-propagation-iteration148.py`.
- **Authorization:** exactly the SOL-authorized offline readiness characterization and causal repair after iteration 147.

The causal RED reproduced the live boundary: startup bindings reported
`dispatcher_preloaded=True`, while a newly constructed
`FileIPCLiveMCPClient` still had `_bootstrap_dispatcher_preloaded=False`.
The smallest existing-owner repair was to apply the already-owned
`_apply_start_tab_bootstrap_bindings(bindings)` wiring before the client call.
After that wiring, the client reported readiness, routed one read-only
`drawing-open` through the existing claim-bound File IPC dispatcher, and made
no raw-LISP call.

## Exact offline evidence

```text
RED: 1 failed at client._bootstrap_dispatcher_preloaded is False while startup bindings were True
GREEN readiness oracle: 1 passed in 0.13s
focused phase4: 39 passed
focused drawing-open: 46 passed, 6 subtests
Ruff: PASS on changed Python files
semantic request: command=drawing-open; read_only=True; exact path payload returned
raw-LISP calls: 0
production drawing/source/DXF/CAD/provider/M2 state changed: False
```

The focused regression is
`mcp_integration_lib/tests/test_phase4.py::test_apply_bindings_propagates_ready_state_and_routes_one_semantic_open`.
The production owner is unchanged in scope: the existing bootstrap-binding
application method now has a regression proving that it propagates readiness
and preserves the existing semantic File IPC route.

## Authoritative verification

`scripts/verify.ps1` completed on the clean code head and produced:

```text
offline JUnit: tests=3405; failures=0; errors=0; skipped=0
dotnet IPC: tests=134; failures=0; errors=0; skipped=0
causal-red: tests=1; failures=1 (expected causal RED)
real-data unavailable probe: tests=2; skipped=2
AutoCAD Mechanical unavailable probe: tests=17; skipped=17
live/M2: NOT RUN
```

The expected causal RED is retained as a diagnostic contract; it is not
reported as a product-test pass. The working tree remained clean after
verification.

## Safety and next review

No live retry followed iteration 147. No candidate, health, visual,
dimension, persistence, source, DXF, CAD, provider, M2, or plugin state was
changed. The page-1 PDF remains key-free `DRAFT_REFERENCE` / `MODIFY NONE`.
The authoritative SourceCustody HMAC/identity-key contract remains fail-closed
and unchanged; this iteration did not remove or bypass any key.

The next action requires fresh SOL review: if clear, run exactly one
disposable read-only live epoch through the repaired binding path, require the
exact File IPC request/result/active-path evidence, and stop at the first
unsatisfied boundary. No raw fallback and no retry are allowed.

```text
STATE=OFFLINE_GREEN
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-ready-dispatcher-readiness-propagation-iteration148.md; C:\temp\cad-agent-task6-live-20260911\readiness-propagation-iteration148.py; commit b02586b; focused tests; scripts/verify.ps1 artifacts
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=LIVE_DISPATCHER_FILE_IPC_DRAWING_OPEN_RESULT_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable live epoch through the repaired bootstrap-binding path, requiring exact request/result/active-path evidence and no retry/raw fallback
HUMAN_GATE=NO
```
