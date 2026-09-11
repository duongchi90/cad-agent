# Real PDF page-1 drawing-open discriminator live epoch — iteration 92

## Authority and scope

Fresh SOL review authorized exactly one live, read-only discriminator epoch
for candidate SHA
`167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.
The epoch was required to reuse the demand-load health/bootstrap pattern,
perform the raw-LISP COM open/activate request, then issue exactly one
read-only `.NET` health observation before any FileIPC dispatcher load/ping.
No FileIPC bootstrap, setup audit, persistence, visual/dimension work, retry,
source mutation, candidate/DXF mutation, or production-code change was
allowed.

## Result

The owned AutoCAD process and startup script were launched with the verified
DWT and the temporary ApplicationPlugins bundle. The session found an owned
window, but the existing document-ready probe did not become true within the
bounded startup window:

`RuntimeError: document-ready was not observed on the owned HWND`

Therefore the epoch stopped before the pre-created bootstrap health result
was consumed, before raw-LISP candidate activation, and before the one
discriminator `DotNetIPCClient.health(drawing_full_path=None)` call.

The following operations were not invoked:

- raw-LISP candidate open/activate;
- discriminator health;
- FileIPC dispatcher load or ping;
- `drawing_setup_audit`.

This epoch cannot distinguish candidate activation from FileIPC readiness.
The only valid candidate classification remains
`CANDIDATE_OPEN_NOT_PROVEN`; no candidate-content defect is inferred.

## Cleanup and invariants

- Owned AutoCAD PID `6312` was absent after cleanup.
- The temporary installed bundle was absent after cleanup.
- Both health request/result pairs were absent after cleanup.
- The startup script was absent after cleanup.
- Candidate SHA before/after remained
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.
- Verified DWT SHA before/after remained
  `b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.
- The normal close confirmation timed out, but the exact owned PID was absent
  after fallback cleanup. This is recorded as a cleanup warning, not as a
  semantic pass.
- `file_ipc_invoked=false` and `drawing_setup_audit_invoked=false`.

## Classification

`LIVE_EPOCH=FAIL`

`DOCUMENT_READY=NOT_PROVEN`

`BOOTSTRAP_HEALTH=NOT_READ`

`DISCRIMINATOR_HEALTH=NOT_RUN`

`CANDIDATE_OPEN_NOT_PROVEN`

`FILEIPC_LOAD_PING=NOT_RUN`

`SETUP_READBACK=NOT_RUN`

Exact private proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\discriminator-iteration92\discriminator-proof.json`.
