# Raw-LISP command-consumption characterization — iteration 99

## Authority and scope

Fresh SOL review of the iteration-98 foreground oracle required one offline
characterization of the existing raw-LISP command-consumption/receiver-ACK
boundary at branch head
`a1b79f9f59511830dba56636dffbfbcf2884ad99`. No live retry, candidate
activation, health, FileIPC, setup, persistence, timeout/code change, focus
workaround, or CAD/source/DXF mutation was authorized.

## Existing owner and terminal evidence

`make_windows_lisp_trigger` delegates to `_make_windows_text_trigger`. After
the existing ownership and foreground guards, it frames the expression as
UTF-16 and calls `PostMessageW` once per code unit on the exact visible owned
`MDIClient`. A native `PostMessageW` return of `TRUE` proves only enqueue-path
success. It does not prove that AutoCAD's receiver consumed, evaluated, or
completed the expression.

The existing causal-red test makes this boundary explicit:
`test_enqueue_true_without_receiver_consumption_is_causal_red` models every
`PostMessageW` call returning `TRUE` while receiver consumption is false, and
rejects treating that enqueue result as an ACK. The positive
`receiver_consumption_ack` path is only a test-double model; it is not a live
receiver protocol or production result channel.

## Existing semantic oracles

The smallest reusable semantic observable in the current owner is the exact
temporary stage-marker mechanism:

- `_start_tab_stage_marker_expression(path, token)` sends an AutoLISP
  expression that opens one exact same-root temporary marker, writes one fixed
  token, and closes it;
- `_observe_stage_markers` accepts only the exact token and records the
  corresponding `BootstrapTimingRecorder` event, such as `post_qnew_entry`;
- the completion-marker variant uses the same writer and
  `_wait_for_completion_ack` to observe the exact
  `CAD_AGENT_START_TAB_BOOTSTRAP_COMPLETE` token.

Presence of the exact marker after a successful trigger return is terminal
evidence that AutoCAD consumed/evaluated that marker-writing expression. It is
side-effect-free with respect to the CAD drawing, but it intentionally writes
one disposable evidence file. If “side-effect-free” is taken to prohibit even
that temporary file, the current production owner has no semantic command-
consumption oracle; the trigger return alone is insufficient.

The completion marker is a larger oracle: it proves a later bootstrap
milestone and is coupled to dispatcher/bootstrap sequencing. It is not the
cheapest isolated command-consumption check. FileIPC health/results are also
downstream and do not belong in this boundary.

## Future single-epoch placement

In one future disposable read-only epoch, after the existing bounded
document-ready transition and before candidate activation or any health/FileIPC
operation, reuse the existing stage-marker writer and exact-token observer for
one `post_qnew_entry` raw-LISP trigger. Record only:

- trigger terminal result/error;
- exact marker presence/content and the existing
  `post_qnew_entry` timing event;
- cleanup of the temporary marker and the owned AutoCAD process.

Exact marker observed => `RAW_LISP_CONSUMPTION=PROVEN` for that marker
expression. Marker absent after the bounded wait, or a trigger error =>
`RAW_LISP_CONSUMPTION=NOT_PROVEN`. Do not treat `PostMessageW=True` or a
trigger return without the marker as semantic success. No implementation
change is justified by this characterization.
