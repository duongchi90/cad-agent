# Ready-dispatcher drawing-open reuse — iteration 146

## Result and supported scope

- **Status:** completed offline; live acceptance pending fresh SOL review.
- **Base SHA:** `796180dc2061feb387de914d07295cc45f265679`.
- **Completion head:** `9c868af7870c18dfd3cc5302a3b7f77e7e227ab9`.
- **Scope:** route a read-only `drawing_open` through the already-ready,
  claim-bound existing File IPC/AutoLISP dispatcher and make the existing
  AutoLISP owner honor `read_only`. No new transport or .NET duplicate was
  added.

## Causal RED

The new offline regression was run before production edits:

```text
.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_phase4.py -k "ready_claim_bound_dispatcher_routes_read_only_open_through_file_ipc or dispatcher_drawing_open_honors_read_only_boolean" -q -p no:cacheprovider
```

Result: `2 failed, 36 deselected`. The ready dispatcher was not used; the
client called the raw-LISP path and terminated with
`RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED`, and the dispatcher source
did not yet consume the Boolean.

## Minimal GREEN

The bounded implementation changed only:

- `mcp_integration_lib/mcp_client.py` — when the existing dispatcher is
  preloaded and its trigger is claim-bound, use the existing File IPC
  `drawing-open`; include `read_only=true` only for the read-only request and
  preserve the old raw-LISP/bootstrap path otherwise.
- `mcp_integration_lib/mcp_dispatch.lsp` — validate the optional Boolean and
  pass `:vlax-true` to the existing `vla-Open` owner; absent/false keeps the
  existing default call and `vla-Activate` behavior.
- `mcp_integration_lib/tests/test_phase4.py` — route/request and owner-source
  regressions.
- `mcp_integration_lib/tests/test_mcp_client_drawing_open.py` — corrected the
  existing dispatcher fixture to return the semantic `drawing-open` payload.

Focused results:

```text
phase4: 38 passed
test_mcp_client_drawing_open.py: 46 passed, 6 subtests passed
test_file_ipc_windows_trigger.py -m "not causal_red": 26 passed, 3 subtests passed
ruff (changed Python files): All checks passed
```

## Authoritative verification

Command:

```powershell
.\scripts\verify.ps1
```

Result: completed with a clean repository at verification start and no
tracked-file snapshot drift. The recorded gates were:

- C# Release x64: `238 passed, 0 failed`;
- `dotnet_ipc`: `134 passed, 0 failures, 0 errors`;
- offline JUnit: `3404 tests, 0 failures, 0 errors, 0 skipped`;
- causal RED: `1 test, 1 expected failure, 0 errors, 0 skipped`;
- real-data unavailable probe: `2 skipped`;
- AutoCAD Mechanical unavailable probe: `17 skipped`;
- live AutoCAD and M2 gates: `NOT RUN` because the required opt-in live
  session/variables were absent.

Existing causal RED remains intentionally red: `PostMessageW=1` still proves
enqueue only. No live retry was run and no candidate, source, accepted drawing,
DXF, CAD, provider/M2, or plugin runtime state was mutated.

## Next bounded action

Fresh SOL review of this offline implementation is required. If clear, run
exactly one disposable live epoch against the same hash-bound page-1 candidate,
using the existing claim-bound dispatcher-ready path and accepting only a
matching semantic File IPC result plus exact active-path readback. Stop at the
first failure; do not retry the prior raw-LISP epoch or run downstream
candidate/health unless the new opening boundary passes.

The page-1 PDF remains key-free `DRAFT_REFERENCE` / `MODIFY NONE`. The
authoritative SourceCustody HMAC/identity-key contract remains fail-closed and
unchanged.

```text
STATE=OFFLINE_GREEN
EVIDENCE=commit 9c868af7870c18dfd3cc5302a3b7f77e7e227ab9; focused tests above; .artifacts/test-results/junit.xml; .artifacts/test-results/dotnet-ipc.xml; .artifacts/test-results/causal-red.xml; .artifacts/test-results/real-data-unavailable.xml; .artifacts/test-results/autocad-mechanical-unavailable.xml
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=LIVE_FILE_IPC_DRAWING_OPEN_SEMANTIC_RESULT_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable live epoch through the ready claim-bound dispatcher, then stop at the first unsatisfied boundary
HUMAN_GATE=NO
```
