# Raw-LISP Consumption ACK Design Characterization — Iteration 109

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / raw-LISP delivery boundary  
Reviewed executor HEAD before this record: `78b5f5b09554cce6442b05adc11650c5dd2c17bc`

## Authorization and scope

Fresh SOL review authorized exactly one offline TDD/design characterization
inside the existing raw-LISP/opening owner. The task was to define the
smallest receiver/evaluation acknowledgement seam without a second
transport. No implementation was authorized. No AutoCAD process, candidate,
FileIPC request, source, DXF, or CAD state was touched.

## Current causal RED

The current low-level owner is
`mcp_integration_lib/mcp_client.py::_make_windows_text_trigger` and its
`make_windows_lisp_trigger` wrapper. It returns after the per-character
`PostMessageW` calls. `PostMessageW=TRUE` proves only native enqueue. The
existing causal-red oracle demonstrates the missing terminal result:

```text
enqueue result: TRUE for every WM_CHAR
receiver/evaluation acknowledgement: absent
current classification: NOT_PROVEN
```

The existing raw opening owner then performs later dispatcher/path checks, but
those checks cannot prove that the specific preceding raw-LISP expression was
consumed. A trigger return must not be accepted as the expression's terminal
success.

## Smallest reuse seam

Do not change the low-level Windows trigger's return type, add a second
transport, or introduce a managed `drawing_open` operation. Add a private
high-level acknowledgement wrapper in the existing opening owner for the
known owner-built `progn` expressions:

```text
allocate one unique request-owned marker path under the existing IPC root
choose one fixed operation-specific ACK token
append the existing marker-writer primitive as the final form of the same progn
send the complete expression once through the existing raw_lisp_trigger
wait within the existing bound for the exact token and exact path
return a terminal consumed/evaluated receipt only on exact marker readback
cleanup the marker on every terminal branch; never retry implicitly
```

The marker writer is already present as
`_start_tab_stage_marker_expression`; the observer is already present as
`_observe_stage_markers`/`_wait_for_completion_ack`. Reusing those primitives
keeps the proposal on the existing raw-LISP transport and makes the ACK mean
that AutoCAD accepted and evaluated the expression through its final marker
form. It does not claim that the business operation itself succeeded; the
existing active-document path readback and managed `health(candidate_path)`
remain the semantic operation/identity checks.

The seam is intentionally at `FileIPCLiveMCPClient.drawing_open` (and the
known bootstrap expression owner), not at arbitrary public raw-LISP callers:
arbitrary expressions do not have a safe syntax-preserving place to append a
marker. The low-level trigger remains an enqueue primitive.

## TDD/design outputs

```text
EXACT_WRITE_SET=
  mcp_integration_lib/mcp_client.py (private ACK wrapper and receipt/cleanup only)
  mcp_integration_lib/tests/test_mcp_client_drawing_open.py (contract/regression tests)
  documentation/status record
  no C# dispatcher, public IPC schema, second transport, source/DXF/CAD change

RED_TEST=
  current trigger returns None and all PostMessageW calls return TRUE while
  the exact ACK marker is absent; the wrapper must refuse terminal success and
  classify RAW_LISP_CONSUMPTION=NOT_PROVEN within the existing bound

GREEN_CONTRACT=
  exact marker token + exact request-owned marker path readback yields a
  receipt with transport_enqueued=true and receiver_evaluation_ack=true;
  missing/wrong-token/trigger-error yields a bounded failure or
  RAW_LISP_CONSUMPTION=NOT_PROVEN; PostMessageW=TRUE alone never yields ACK;
  the receipt is separate from active-document/business-operation success

REGRESSION_GATE=
  focused opening-owner tests, existing windows-trigger causal-red test,
  complete scripts/verify.ps1 from a clean tracked tree, then one separately
  authorized disposable live epoch with exact marker and cleanup evidence

LIVE_ACCEPTANCE_ORACLE=
  verified disposable DWT -> bounded document-ready -> one existing read-only
  candidate_open expression with the same-expression ACK marker -> exact marker
  readback => RAW_LISP_CONSUMPTION=PROVEN -> existing health(candidate_path)
  exact active-document identity result -> no-save disposable cleanup;
  no retry, source/DXF mutation, production save, or promotion
```

## Limits and write-set decision

The marker proves receiver/evaluation reached the marker form; it cannot split
the native window's internal queue consumption from AutoLISP evaluation into
two independent observations. That combined terminal ACK is the smallest
honest semantic result available without a new transport. `SendMessageW`, a
window-procedure hook, COM/ROT, named pipe, or a new managed open operation
would be a broader transport/architecture change and is rejected for this
characterization.

The exact write set above is a future implementation boundary only. Under this
decision the actual write set is:

```text
MODIFY=NONE
CREATE=NONE
```

## Classification

```text
STATE=DESIGNED
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_EVALUATION_ACK_ABSENT_IN_CURRENT_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this ACK design; authorize implementation only if the same-expression marker contract and exact write set are accepted, otherwise keep live retry/candidate activation/health/FileIPC and production mutation stopped
HUMAN_GATE=NO
```

