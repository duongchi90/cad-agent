# Ready-dispatcher live boundary — iteration 147

## Result

- **Status:** classified; stopped at the first unsatisfied boundary.
- **Code head:** `9e5773f53aebae39c75a1bce89d9de6c3748756a`.
- **Oracle:** `C:\temp\cad-agent-task6-live-20260911\candidate-activation-dispatcher-live-iteration147-proof.json`.
- **Authorization:** exactly one disposable read-only live epoch from SOL.

The epoch started with the approved startup owner and reached
`document_ready=True`. The harness required the existing claim-bound,
dispatcher-ready File IPC path and explicitly forbade raw-LISP fallback. The
client instance did not have its dispatcher-ready state propagated from the
startup bindings, so `drawing_open(read_only=True)` entered the raw-LISP branch
and the harness stopped it with
`RAW_LISP_FALLBACK_FORBIDDEN_IN_ITERATION147`.

No File IPC `drawing-open` request or terminal result was observed; therefore
the semantic open/evaluator oracle and active-document path readback were not
run, and health/candidate identity were not run. This is a wiring/readiness
propagation finding, not evidence that the candidate failed to open.

## Exact live evidence

```text
document_ready=True
startup owner=WindowsAutoCADStartTabSession
dispatcher_preloaded=True in startup bindings
client dispatcher-ready state=not propagated in the existing direct-binding harness
raw-LISP fallback calls=1 (forbidden by this oracle; length=999)
drawing-open File IPC requests=0
terminal results=0
health_call_count=0
status=CLASSIFIED
classification=FIRST_CAUSAL_BOUNDARY_NOT_PROVEN
failure=RuntimeError: RAW_LISP_FALLBACK_FORBIDDEN_IN_ITERATION147
candidate SHA before=167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714
candidate SHA after =167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714
default DWT SHA before=b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42
default DWT SHA after =b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42
cleanup_warnings=[]
pid_absent_after_cleanup=True
ipc_root_absent_after_cleanup=True
scripts_root_absent_after_cleanup=True
```

## Safety and next review

This was exactly one live epoch. There was no retry, no raw-LISP fallback
execution after the guard, no candidate/health, no visual/dimension or
persistence work, and no source/DXF/CAD/provider/M2/plugin/key-policy
mutation. The page-1 PDF remains key-free `DRAFT_REFERENCE` / `MODIFY NONE`;
the authoritative SourceCustody HMAC/identity-key contract remains fail-closed
and unchanged.

The next action requires fresh SOL review: one bounded offline characterization
of readiness propagation from `WindowsStartTabBootstrapBindings` into
`FileIPCLiveMCPClient`, followed by a minimal repair only if the characterization
produces a causal RED. Do not run another live epoch until that repair is
reviewed and explicitly cleared.

```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-ready-dispatcher-live-boundary-iteration147.md; C:\temp\cad-agent-task6-live-20260911\candidate-activation-dispatcher-live-iteration147-proof.json; HEAD 9e5773f53aebae39c75a1bce89d9de6c3748756a
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=DISPATCHER_READY_STATE_NOT_PROPAGATED_TO_LIVE_CLIENT
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize one offline readiness-propagation characterization and causal RED, with no live retry until reviewed
HUMAN_GATE=NO
```
