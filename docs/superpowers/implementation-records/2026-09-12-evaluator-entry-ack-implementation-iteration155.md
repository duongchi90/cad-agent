# Evaluator-Entry ACK Implementation — Iteration 155

Date: 2026-09-12 (Asia/Saigon)
Issue: exact page-1 candidate activation / startup evaluator boundary
Verified code HEAD: `dee0758fafd3b9068cbfb37e6ab8974a4a99d0de`

## Authorization and bounded scope

SOL iteration 154 returned `CLEAR_CONTINUE` for the exact private
same-expression marker seam after the causal RED. This implementation kept
one writer and changed only the existing startup raw-LISP owner plus focused
tests. No AutoCAD process or live epoch was run after the change. No source,
DXF, CAD, candidate, File IPC request, public schema, C# owner, second
transport, provider/M2 state, or SourceCustody key/HMAC/identity policy was
changed.

## Implementation

- `WindowsAutoCADStartTabSession` now allocates one UUID-scoped
  `.evaluator-entry` marker under the validated IPC root.
- The startup dispatcher expression is still sent once through the existing
  raw-LISP trigger, but its first form is the existing fixed-token marker
  writer; the original IPC-root assignment and dispatcher `load` follow it in
  the same outer `progn`.
- The owner waits for the exact entry token and path before sending the
  existing post-load stage/completion markers. Missing, wrong, unreadable, or
  timed-out entry markers raise
  `STARTUP_EVALUATOR_ENTRY_NOT_CONFIRMED`; no completion marker, client,
  File IPC, or retry follows that failure.
- Cleanup removes the entry marker only when its parent remains the validated
  IPC root, and preserves the existing no-save disposable cleanup behavior.
- The existing no-argument `_dispatcher_load_expression()` contract remains
  available for the offline completion oracle; the new marker is opt-in to
  the startup call site.

## RED then GREEN evidence

The new RED test first failed on the old owner because it reached completion
without an evaluator-entry acknowledgement:

```text
MCPTimeoutError STARTUP_EVALUATOR_ENTRY_NOT_CONFIRMED was not raised
```

After the bounded implementation, the focused gate passed:

```text
52 passed, 6 subtests passed
Ruff: PASS
```

The wrong-token and missing-token tests both verify one raw trigger only, no
completion marker emission, exact fail-closed timeout, and marker cleanup.
The positive test verifies entry-token ordering before
`(setq *cad-agent-file-ipc-root* ...)` and cleanup of the entry marker.

## Authoritative verification

`scripts/verify.ps1` completed successfully at the verified code HEAD. It
reported:

```text
offline JUnit: tests=3412 failures=0 errors=0 skipped=0
C# tests: 238 passed
.NET IPC: 134 passed
causal RED: 1 expected failure
real-data unavailable: 2 skipped
AutoCAD Mechanical unavailable: 17 skipped
AutoCAD live: NOT RUN
M2 Mechanical benchmark: NOT RUN
```

The expected causal RED remains intentional evidence that native
`PostMessageW=True` is enqueue-only; it is not a failing verification gate.

## Acceptance boundary and safety

Offline evidence proves the private ordering/timeout/cleanup contract only.
It does not prove the real AutoCAD evaluator or filesystem marker behavior.
The next live oracle, if freshly cleared by SOL, is exactly one disposable
epoch: document-ready; one existing raw-LISP startup trigger; exact entry
marker readback; exact existing dispatcher completion marker readback; then
stop for a separate review before any downstream client/File IPC, candidate
open, or health call. Candidate/DWT hashes must remain unchanged and cleanup
must be clean. No raw fallback, retry, source/DXF/CAD mutation, or key-policy
change is allowed.

## Classification

```text
STATE=OFFLINE_GREEN
EVIDENCE=This record; mcp_integration_lib/mcp_client.py; mcp_integration_lib/tests/test_mcp_client_drawing_open.py; mcp_integration_lib/tests/test_startup_completion_oracle.py; scripts/verify.ps1 PASS at HEAD dee0758fafd3b9068cbfb37e6ab8974a4a99d0de; focused 52 passed + 6 subtests; Ruff PASS; causal RED 1 expected failure
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=REAL_AUTOCAD_STARTUP_EVALUATOR_ENTRY_AND_COMPLETION_NOT_PROVEN_AFTER_PRIVATE_REPAIR
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of offline GREEN; if clear authorize exactly one disposable read-only live diagnostic through the repaired startup owner, stopping at the first entry/completion boundary and forbidding downstream client/File IPC unless both exact markers are observed
HUMAN_GATE=NO
```
