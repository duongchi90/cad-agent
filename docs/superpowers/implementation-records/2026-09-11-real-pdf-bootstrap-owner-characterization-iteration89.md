# Real PDF page-1 bootstrap-owner characterization — iteration 89

## Scope and authority

SOL authorized one read-only/offline characterization after iteration 88
stopped at `START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED`. This record does
not retry AutoCAD, open the candidate, change production code, or mutate any
source/candidate/DXF/live CAD state.

## Existing owner and exact observed boundary

The existing owner is `WindowsAutoCADStartTabSession` in
`mcp_integration_lib/mcp_client.py`. Its runtime sequence is:

1. launch `acad.exe /nologo /b <temporary-script>` where the script is only
   `_.QNEW`;
2. observe the owned Start-tab window and document-ready title transition;
3. send the existing runtime bootstrap expressions for NETLOAD, dispatcher
   load, and completion-marker write;
4. accept the bindings only when the exact same-root marker file exists and
   contains exactly `CAD_AGENT_START_TAB_BOOTSTRAP_COMPLETE`.

The iteration-88 live epoch reached the owned process and document-ready
boundary, then failed at step 4. The candidate was never opened and
`drawing_setup_audit` was never invoked.

The precise measured missing condition is therefore:

`COMPLETION_MARKER_SUCCESSFUL_CREATE_AND_READBACK=NOT_PROVEN`

The marker writer is conditional on AutoLISP `open` returning a handle and has
no negative/error marker when that handle is unavailable. The historical staged
diagnostic observed the later `completion_marker_writer_return` stage marker
but no completion marker file. That proves expression delivery/order, not
successful completion-file creation or visibility. No narrower filesystem or
AutoCAD root cause is inferred from the available evidence.

## Comparison with the already-proven health owner

The existing demand-load/semantic-health oracle used the same approved
File/.NET IPC owners but a different readiness proof:

- launch one verified AutoCAD Mechanical 2027 DWT with `/t`;
- use a temporary `/b` script containing only `CADAGENT_DISPATCH`;
- pre-create one matching `health` request;
- accept the exact result only when `success=true`, `changed=false`, and
  `errors=[]`, then verify the demand-loaded module path and SHA.

That oracle passed in iteration 76. It did not depend on the unproven
same-root completion marker and did not use a second transport.

## Smallest reuse proposal

`MODIFY NONE / CREATE NONE` for this characterization. The smallest existing
readiness owner to reuse in a future separately-authorized live epoch is the
proven demand-load `CADAGENT_DISPATCH` plus matching read-only `health` result,
followed by the existing `FileIPCLiveMCPClient.drawing_open(...,
read_only=True)` and `DotNetIPCClient.drawing_setup_audit(...)` owners. The
completion marker must not be treated as proven merely because its writer
expression was delivered.

No live retry is authorized by this record. Setup/readback, persistence,
visual, and dimension remain unproven for the exact page-1 candidate.

## Offline evidence

Focused completion-owner characterization passed without a cache provider:

`.venv-py311\Scripts\python.exe -m pytest -p no:cacheprovider -q mcp_integration_lib/tests/test_mcp_client_drawing_open.py -k "completion or stage_localization or timing"`

Result: `8 passed, 32 deselected`.
