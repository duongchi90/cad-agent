# Raw-LISP delivery-path causal characterization — iteration 103

## Authority and scope

Fresh SOL review of commit `8eb2bbe4bdab88ff03444fbb6a8d7a34fe551630`
required one offline, reuse-only characterization of the existing
`_make_windows_text_trigger` / `make_windows_lisp_trigger` delivery path.
This record does not authorize a live retry, focus workaround, timeout or
code change, candidate activation, health, FileIPC, setup, persistence, visual
or dimension work, or CAD/source/DXF mutation.

## Canonical checkpoint

```text
STATE=EXECUTED
EVIDENCE=source owner mcp_integration_lib/mcp_client.py; focused owner/framing tests 5 passed, 15 deselected; causal-red 1 failed, 19 deselected as expected; historical iteration-63/64 records; reviewed HEAD 8eb2bbe4bdab88ff03444fbb6a8d7a34fe551630
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_CONSUMPTION_ACK_ABSENT_IN_CURRENT_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this offline characterization; keep live retry, candidate activation, health, FileIPC, and production mutation stopped until the next bounded action is authorized
HUMAN_GATE=NO
```

## Exact existing owner

`mcp_integration_lib/mcp_client.py::_make_windows_text_trigger` is the owner;
`make_windows_lisp_trigger` delegates directly to it and
`make_windows_command_trigger` uses the same text owner. The owner:

1. reads the bound top-level HWND PID;
2. enumerates child windows and retains class `MDIClient` children;
3. keeps only children with the owner PID and `IsWindowVisible=True`, requiring
   exactly one visible owned receiver;
4. rechecks top-level/receiver PID identity and top-level foreground HWND;
5. frames the text as `ESC ESC + expression + CR`, encodes it as UTF-16LE, and
   posts one `WM_CHAR` (`0x0102`) per UTF-16 code unit to the selected receiver;
6. rechecks PID and foreground before each post and returns after native
   `PostMessageW` accepts every enqueue.

There is no receiver callback, handler receipt, queue-drain result, or
AutoLISP evaluation result in this owner. The final `CR` is one `WM_CHAR`
code unit (`U+000D`); the owner does not send a separate
`WM_KEYDOWN`/`WM_KEYUP` `VK_RETURN` sequence.

## Causal evidence

The focused offline owner tests passed `5 passed, 15 deselected` on the
reviewed head. They verify the unique visible owned `MDIClient` selection and
the exact `WM_CHAR`/UTF-16 framing. The existing marked causal-red test also
ran as the expected failure (`1 failed, 19 deselected`): all `PostMessageW`
calls can return true while the independent modeled receiver-consumption
acknowledgement is false.

Historical live evidence narrows, but does not close, the receiver branch:

- iteration 63 observed a unique visible owned `MDIClient`, while the actual
  focused child was a different owned visible HWND;
- iteration 64 sent the same 299-code-unit framing directly to that focused
  child and still observed no exact stage marker;
- iteration 102 used the current `MDIClient` owner, reached
  `DOCUMENT_READY=PROVEN`, returned from exactly one trigger, and observed
  neither the exact marker nor the `post_qnew_entry` timing event.

Therefore a simple `MDIClient`-versus-focused-child swap is not a sufficient
causal explanation, and the live evidence cannot prove that either target's
window procedure accepted the command-line sequence.

## Three-way distinction boundary

The existing reusable observables have these limits:

- `WRONG_RECEIVER_OR_CONTROL`: child hierarchy plus active/focus/capture
  inspection can expose a target/control mismatch. Iteration 63 exposed the
  `MDIClient`/focus distinction, but iteration 64 shows that changing to the
  focused child alone did not produce the marker.
- `FRAME_OR_TERMINATOR_NOT_CONSUMED`: the offline `post_calls` trace can prove
  the intended target, `WM_CHAR`, UTF-16 code units, and final `U+000D`. It
  cannot prove that AutoCAD translated or consumed the final terminator; the
  current owner has no live keyboard-translation or queue-consumption
  observable.
- `RECEIVER_ACCEPTED_BUT_AUTOLISP_NOT_EVALUATED`: the exact stage marker is
  the existing semantic evaluation oracle when present. Marker absence does
  not establish receiver acceptance, so it collapses this case with the two
  delivery failures above.

The smallest existing live semantic observable is therefore still the exact
temporary stage-marker token plus its `post_qnew_entry` timing event. It only
distinguishes `CONSUMED_AND_EVALUATED` from `NOT_PROVEN`; it cannot provide a
three-way diagnosis. The independent `receiver_queue`/ACK path exists only in
the offline test double, not as a production AutoCAD protocol.

## Finding and future boundary

`RAW_LISP_RECEIVER_CONSUMPTION_ACK=ABSENT_IN_CURRENT_OWNER` is the first
causal gap after successful enqueue. Under `MODIFY NONE / CREATE NONE`, no
existing live oracle can honestly distinguish all three requested categories.
The next design/review gate must choose an already-supported semantic result
owner or explicitly approve a receiver-side acknowledgement seam; candidate
activation must remain downstream until then. No implementation change is
justified by this characterization.
