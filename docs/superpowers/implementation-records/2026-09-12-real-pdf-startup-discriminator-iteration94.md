# Real PDF page-1 startup discriminator — iteration 94

## Authority and scope

Fresh SOL review authorized exactly one live, read-only startup discriminator
epoch on the executor-branch startup owner at
`e65d245e2d044cf282d690f7bc97a5a45a874bca`. The epoch reused the verified DWT
and demand-load startup pattern, bound the owned PID/HWND, and used the
existing bounded `_wait_for_document_ready` method. No candidate activation,
bootstrap health consumption, FileIPC load/ping, setup audit, retry, timeout
change, code change, or CAD/source/DXF mutation was allowed.

## Measurement

- Startup used `AutoCAD 2027`, the verified DWT, and the exact script
  `CADAGENT_DISPATCH\r\n`; no QNEW and no Start-tab completion marker were
  used.
- The owned startup window was observed at timing delta `14.391s`.
- The existing bounded document-ready wait then observed
  `document_ready_transition` at timing delta `27.031s`.
- The Boolean document-ready predicate therefore returned true within its
  existing 60-second bound. Because it became true, the timeout-only raw-title
  classification branch was not entered and no candidate/health/FileIPC step
  was attempted.

This is the first direct evidence that iteration 92's immediate false sample
was not a bounded timeout: iteration 92 did not call the bounded wait, while
this epoch did and it transitioned to ready.

## Result and cleanup

`DOCUMENT_READY=PROVEN`

`STARTUP_DISCRIMINATOR=PASS`

`CANDIDATE_ACTIVATION=NOT_RUN`

`BOOTSTRAP_HEALTH=NOT_RUN`

`FILEIPC=NOT_RUN`

`SETUP_READBACK=NOT_RUN`

The runner exit was `1` only because the normal window-close confirmation
timed out. Exact fallback cleanup then confirmed owned PID `7640` absent.
The temporary installed bundle and startup script were absent; the candidate
SHA remained
`167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`; and the
DWT SHA remained
`b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.
This is `CLEANUP=SAFE_WITH_CLOSE_WARNING`, not a semantic readiness failure.

Exact private proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\startup-discriminator-iteration94\startup-discriminator-proof.json`.
