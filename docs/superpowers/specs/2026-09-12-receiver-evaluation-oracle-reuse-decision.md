# Receiver/evaluation oracle reuse decision — iteration 145

## Status and scope

- **Status:** proposed; pending fresh SOL review.
- **Proposed date:** 2026-09-12.
- **Base SHA:** `abdbf61e3daf5557cd91b542dbb01100f8915d17`.
- **Supported scope:** one disposable, read-only live `drawing_open` acceptance
  seam for the exact page-1 candidate workflow. This record does not authorize
  implementation, a live retry, candidate/health work, visual or dimension
  acceptance, persistence, source/DXF/CAD mutation, provider/M2 work, or any
  key-policy change.

## Decision question

Iteration 144 proved that the current native owner enqueued all `997` WM_CHAR
units with `PostMessageW=1`, but it could not prove that AutoCAD consumed or
evaluated the frame. The marker was not observed and the public ACK remained
fail-closed. The decision must therefore reuse an existing owner and produce a
semantic receiver/evaluation oracle without adding a second transport or
control plane.

## Existing-owner and reuse map

| Concern | Existing owner | What it proves now | Reuse decision |
| --- | --- | --- | --- |
| Native raw-LISP framing | `mcp_integration_lib/mcp_client.py`, `_make_windows_text_trigger` / `make_windows_lisp_trigger` | Exact target identity and WM_CHAR enqueue only | Keep unchanged for bootstrap and legacy paths; do not promote enqueue to evaluation evidence |
| Python ACK wait/cleanup | `FileIPCLiveMCPClient._send_raw_lisp_with_ack` | Exact marker token observation or fail-closed timeout | Keep unchanged; no retry after an ambiguous timeout |
| AutoLISP operation execution | `mcp_integration_lib/mcp_dispatch.lsp`, `c:mcp-dispatch` and `mcp-op-drawing-open` | Existing request/result envelope after the AutoLISP operation returns | Preferred owner for the bounded oracle |
| File IPC transport | Existing `autocad_mcp_cmd_*.json` / `autocad_mcp_result_*.json` exchange and claim binding | Semantic terminal result, not just native enqueue | Reuse unchanged |
| Managed .NET path | `CADAGENT_DISPATCH`, `OperationDispatcher`, `DotNetIPCClient` | Managed command/dispatcher result | Inspect-only alternative; do not duplicate `drawing-open` in .NET for this seam |

The current live client selects the raw-LISP branch whenever a raw trigger and
bootstrap LISP path are present. Consequently, even a confirmed preloaded
dispatcher is bypassed for `drawing_open`. The existing AutoLISP dispatcher
already has the operation, but it currently ignores the client `read_only`
argument; that is the measured compatibility gap preventing direct reuse for
the hash-bound read-only candidate epoch.

## Proposed smallest seam

After the existing dispatcher is positively ready and claim-bound, route the
candidate's `drawing_open(path, read_only=True)` through the existing File IPC
`drawing-open` request/result exchange. Extend only the existing AutoLISP
`mcp-op-drawing-open` parameter handling so `read_only` is a validated Boolean
and is passed to the existing `vla-open` call. Preserve the current
`vla-activate` behavior and the existing result envelope. The default legacy
behavior remains `read_only=False` when the parameter is absent only where the
existing client contract requires that compatibility.

The raw-LISP path remains the bootstrap path when no dispatcher is ready. The
seam must not turn an ACK timeout into an automatic fallback or retry: routing
selection is made before dispatch, and every uncertain execution remains a
fail-closed terminal result.

This is a supported evaluation oracle, not a claim that the old WM_CHAR frame
was consumed. A validated File IPC result proves that the existing AutoLISP
dispatcher received, parsed, evaluated, and completed the requested operation.

## Exact prospective write-set

Only after design approval and a causal RED may implementation touch:

1. `mcp_integration_lib/mcp_client.py` — route only when the existing
   dispatcher-ready/claim-bound precondition is true; include `read_only` in the
   existing `drawing-open` request; preserve raw-LISP bootstrap and all
   fail-closed timeout/cleanup behavior.
2. `mcp_integration_lib/mcp_dispatch.lsp` — validate/read the optional Boolean
   and pass it to the existing `vla-open`; no new command, transport, result
   store, or control plane.
3. Focused existing-owner tests, principally
   `mcp_integration_lib/tests/test_phase4.py` and the File IPC end-to-end
   contract tests, plus any contract fixture needed to prove exact request
   shape.
4. One dated implementation record and `docs/STATUS.md` checkpoint after
   verification.

No C# production file, public schema family, DXF, drawing, customer source,
plugin binary, or key/custody implementation is in scope.

## Causal RED oracle

Before production edits, add one offline test using an injected claim-bound
dispatcher trigger and a recording raw-LISP trigger. With dispatcher readiness
true, call `drawing_open(exact_path, read_only=True)` and require:

- the current implementation fails the test because it calls raw-LISP instead
  of the existing File IPC dispatcher, or emits the old request shape;
- after the minimal change, exactly one existing `drawing-open` request is
  created with the exact path and `read_only=true`;
- the raw-LISP trigger is not called for that already-ready dispatcher path;
- a valid existing result is returned and the request/result files are cleaned;
- injected result timeout, claim mismatch, and terminal error remain non-PASS
  and do not trigger a second transport or retry.

The AutoLISP-focused offline test must also prove that `read_only=true` reaches
the existing `vla-open` call and that the false/default compatibility path is
unchanged. These tests never execute AutoCAD and never mutate a drawing.

## Prospective live acceptance oracle

After implementation review and fresh authorization, run exactly one disposable
epoch against the same hash-bound page-1 candidate and stop at the first
unsatisfied boundary. Record, in causal order:

1. exact AutoCAD/plugin/dispatcher identity and dispatcher-ready proof;
2. one claim-bound `drawing-open` request with exact path and
   `read_only=true`;
3. one existing File IPC terminal result with matching request id and claim,
   `ok=true`, and the expected opened path;
4. active-document path readback through the existing query owner;
5. candidate identity and one health call only if all preceding observations
   pass and SOL separately clears those downstream gates.

The File IPC terminal result is the accepted evaluator-entry/operation-complete
oracle. A missing result, timeout, claim mismatch, path mismatch, or ambiguous
cleanup is `NOT_RUN`/`FAIL` as applicable, never a pass inferred from
`PostMessageW=1`. No visual/dimension verdict or save/persistence claim is
allowed from this seam.

## Rollback and safety

- Keep the raw-LISP route and current public timeout error intact until the new
  path has a fresh independent live acceptance result.
- Roll back by reverting only the bounded client/AutoLISP/test commit; no
  drawing or source rollback is required because the epoch is disposable and
  opens read-only.
- Preserve the existing IPC-root validation, claim binding, exact path
  checks, result cleanup, and no-save cleanup.
- Do not remove or bypass SourceCustody HMAC/identity-key enforcement. The
  page-1 PDF remains key-free `DRAFT_REFERENCE` / `MODIFY NONE`, while the
  authoritative source identity-key contract remains fail-closed and
  unchanged.

## Why the other existing capability is insufficient

The raw-LISP marker is already the smallest direct evaluator marker, but the
current live owner exposes no receiver-consumption or queue-drain receipt and
iteration 144 observed no marker. The managed .NET path can prove a managed
command result, but adding a parallel managed `drawing-open` operation would
duplicate the already-existing AutoLISP owner and would not prove AutoLISP
evaluation. Reusing the existing File IPC dispatcher closes the measured gap
with one bounded parameter/selection repair and no second transport.

## Review checkpoint

```text
STATE=DESIGN_PROPOSED
EVIDENCE=iteration 144 live proof and docs/superpowers/implementation-records/2026-09-12-live-receiver-observability-boundary-iteration144.md; existing-owner inspection of mcp_client.py, mcp_dispatch.lsp, dotnet_ipc.py, and CadAgent.AutoCAD2027 command/dispatcher owners
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RECEIVER_CONSUMPTION_OBSERVABLE_ABSENT_IN_CURRENT_LIVE_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this reuse decision; if clear authorize the causal RED and only the bounded client/AutoLISP/test write-set above
HUMAN_GATE=NO
```
