# Real PDF page-1 demand-load/setup live oracle — iteration 90

## Authority and scope

SOL authorized exactly one fresh read-only live epoch using the already-proven
iteration-76 demand-load pattern. The epoch was required to use a verified
AutoCAD Mechanical 2027 DWT, one pre-created matching `health` request, a
`/b CADAGENT_DISPATCH` script, then the existing read-only candidate-open path
and one `drawing_setup_audit`. The Start-tab completion marker was not used.

Candidate identity was bound before execution:

`167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`

## Results

- AutoCAD 2027 reached document-ready on the owned PID/HWND.
- Demand-load semantic health passed: matching `health` result had
  `success=true`, `changed=false`, `errors=[]`, host `AutoCAD Mechanical 2027`,
  and the expected installed CadAgent module was present exactly once with
  the expected source SHA.
- The existing `FileIPCLiveMCPClient.drawing_open(..., read_only=True)` path
  was then invoked for the exact candidate. It stopped before returning because
  the existing FileIPC dispatcher readiness ping timed out:
  `MCPTimeoutError: AutoCAD dispatcher did not become ready: Timeout waiting
  for result (request_id=23afdf5ebdeb)`.
- Candidate-open semantic success was not established. The existing
  `drawing_setup_audit` operation was not invoked, so no setup payload or
  DBMOD verdict exists.

## Cleanup and invariants

- AutoCAD owned PID was absent after cleanup.
- Temporary installed bundle, health request/result, setup request/result, and
  unique FileIPC root were absent after cleanup.
- Verified DWT SHA-256 was unchanged.
- Exact candidate SHA-256 was unchanged:
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.
- No source, candidate/DXF, production code, or accepted drawing was saved or
  mutated. No retry was performed.

## Classification

`SEMANTIC_HEALTH=PASS`;
`CANDIDATE_READ_ONLY_OPEN=NOT_PROVEN`;
`SETUP_READBACK=NOT_RUN`;
`PERSISTENCE_REOPEN=NOT_PROVEN`;
`VISUAL=NOT_PROVEN`;
`DIMENSION=NOT_PROVEN`.

This is a fail-closed live result, not a candidate-content or geometry
verdict. Exact private proof is retained outside Git at the iteration-90 proof
path recorded in the resume state.
