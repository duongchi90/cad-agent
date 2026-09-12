# Real PDF page-1 drawing-open stage localization — iteration 91

## Authority and scope

Fresh SOL review of iteration 90 required exactly one offline
stage-localization characterization of the current-main
`FileIPCLiveMCPClient.drawing_open` path. This record is read-only: no live
retry, no source/candidate/DXF mutation, no AutoCAD mutation, and no
production-code change were allowed.

## Ordered observable boundaries

The current raw-LISP path in
`mcp_integration_lib/mcp_client.py::FileIPCLiveMCPClient.drawing_open` has
these boundaries:

1. The raw-LISP COM expression calls `vla-open` when needed and
   `vla-activate`; a successful return from `_raw_lisp_trigger` is only
   command-boundary delivery and does not expose the active document path.
   A read-only trigger error is terminal; the command-boundary fallback is
   only available for the non-read-only Start-tab sentinel branch.
2. After the document settle delay, the client records the expected path in
   `_active_drawing_path`. This is client intent, not an AutoCAD readback.
3. `_load_dispatcher_for_active_document` sends a raw-LISP `(load ...)`
   expression after setting `*cad-agent-file-ipc-root*`. Its return is also
   only expression delivery; the current owner has no semantic load result.
4. `_wait_for_dispatcher` calls `_dispatch("ping", {})`. That creates a
   FileIPC request, triggers `(c:mcp-dispatch)`, and waits for a result. This
   is the first terminal semantic boundary reached in iteration 90, and it
   timed out.
5. Only after a successful ping does `drawing_open` call
   `drawing_get_variables(["DWGPREFIX", "DWGNAME"])`, normalize the
   resulting active path, and compare it with the expected candidate path.
   This is the existing active-document identity readback, but it is
   unreachable when dispatcher readiness fails.

The existing focused tests confirm the ordering and fail-closed behavior:
`test_post_activation_dispatcher_failure_does_not_reenter_open`,
`test_read_only_open_requests_read_only_and_still_verifies_active_document`,
and the remaining 40 tests in
`mcp_integration_lib/tests/test_mcp_client_drawing_open.py`.

## Cheapest existing distinguishing oracle

The smallest reusable read-only oracle is the already-installed .NET
`DotNetIPCClient.health` owner, invoked with `drawing_full_path=None` after
the raw-LISP open/activate expression returns and the document settle delay
elapses, but before the FileIPC bootstrap-load/ping sequence.

`OperationDispatcher.DispatchHealth` reads the active document full path and
returns it as `drawing_full_path`, together with `success=true`,
`changed=false`, `errors=[]`, and `payload.active_document`. Therefore one
future epoch can distinguish the two currently conflated states without a
new owner:

- health returns the candidate path with the read-only invariants: candidate
  activation is proven; a later FileIPC ping timeout is classified as
  `CANDIDATE_OPENED_BUT_FILEIPC_DISPATCHER_NOT_READY`;
- health returns the prior DWT/other path or no active document: candidate
  activation remains `CANDIDATE_OPEN_NOT_PROVEN`, and no candidate-content
  defect is inferred.

Using an explicit candidate path is not the preferred discriminator because
the health contract then performs an active-path match and can collapse the
useful observed path into a mismatch failure. The `None` request preserves
the actual active-path observation.

## Result

`STAGE_LOCALIZATION=PASS`

`FIRST_UNOBSERVED_BOUNDARY=ACTIVE_DOCUMENT_IDENTITY_AFTER_RAW_LISP_ACTIVATION`

`ITERATION_90_CAUSAL_BOUNDARY=POST_OPEN_FILEIPC_DISPATCHER_READINESS`

`PROPOSED_NEXT_ORACLE=ONE_READ_ONLY_DOTNET_HEALTH_NONE_AFTER_ACTIVATION_BEFORE_FILEIPC_LOAD`

`MODIFY=NONE; CREATE=NONE; LIVE_RETRY=NONE`

Focused offline characterization execution passed with the standard library
runner: `40 tests, OK`. The attempted pytest command was not run because the
global Python 3.11 environment has no pytest module; this did not alter the
repository.
