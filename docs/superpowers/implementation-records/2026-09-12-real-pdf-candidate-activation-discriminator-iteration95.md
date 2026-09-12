# Real PDF page-1 candidate-activation discriminator — iteration 95

## Authority and scope

Fresh SOL review authorized exactly one live, read-only candidate-activation
discriminator epoch using the executor-branch startup owner, the verified DWT,
and the `CADAGENT_DISPATCH` startup pattern. After the existing bounded
document-ready wait, the epoch was allowed to send one existing raw-LISP
COM open/activate request for the exact page-1 candidate, settle, and invoke
one existing `DotNetIPCClient.health(drawing_full_path=None)`. No FileIPC
bootstrap load/ping, setup audit, persistence, retry, timeout/code change, or
CAD/source/DXF mutation was allowed.

## Measurement

- The owned AutoCAD session reached `DOCUMENT_READY=PROVEN` using the existing
  bounded wait and verified DWT.
- The existing raw-LISP trigger refused delivery with
  `MCPToolError: WINDOW_FOREGROUND_INVALID`.
- Consequently the raw-LISP COM open/activate request was not delivered and
  the single health call was not reached: `health_call_count=0`.
- This epoch therefore cannot infer candidate activation or candidate content.

## Result and cleanup

`LIVE_EPOCH=FAIL_CLOSED`

`DOCUMENT_READY=PROVEN`

`CANDIDATE_ACTIVATION=NOT_PROVEN`

`DISCRIMINATOR_HEALTH=NOT_RUN`

`FILEIPC_BOOTSTRAP_LOAD_OR_PING=NOT_RUN`

`SETUP_READBACK=NOT_RUN`

The exact owned PID was absent after cleanup. The temporary installed bundle,
startup script, and health request/result pair were absent. The exact page-1
candidate SHA remained
`167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`; the
verified DWT SHA remained
`b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.
Normal close confirmation produced the same cleanup warning seen previously;
exact-PID fallback cleanup succeeded. No retry was made.

The private proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration95\candidate-activation-proof.json`.
