# Raw-LISP foreground oracle — iteration 98

## Authority and scope

Fresh SOL review authorized exactly one fresh disposable, live, read-only
foreground-oracle epoch. The epoch reused the executor-branch startup owner,
the verified DWT, and the existing bounded document-ready wait. It captured a
high-frequency read-only foreground identity trace around exactly one existing
raw-LISP trigger on the bound HWND. No manual focus forcing/workaround, retry,
code or timeout change, candidate open/activation, health, FileIPC, setup,
persistence, or CAD/source/DXF mutation was allowed.

## Measurement

- `DOCUMENT_READY=PROVEN` on the owned AutoCAD session.
- Bound owner: HWND `1312424`, PID `4356`.
- The trace captured three samples immediately before/during/after the
  trigger. Every sample reported foreground HWND `1312424` and foreground PID
  `4356`; no distinct foreground identity or transition was observed.
- The foreground process identity was `acad.exe` at the approved AutoCAD 2027
  path, with title `Autodesk AutoCAD 2027 - [Drawing1.dwg]`.
- The existing raw-LISP trigger was invoked exactly once with a side-effect
  free expression. It returned without an exception; no execution or receiver
  ACK is inferred from that return.

## Result and boundary

`FOREGROUND_BOUNDARY_UNRESOLVED`

The restricted SOL classification is unresolved because this epoch did not
produce `WINDOW_FOREGROUND_INVALID`, and the trigger's return does not prove
receiver/AutoCAD command consumption. The trace does show the owner foreground
at the sampled trigger boundary, but it does not establish a candidate or
FileIPC result. The earlier iteration-95 foreground failure is therefore not
reproduced in this epoch, without inferring that it is permanently resolved.

`CANDIDATE=NOT_TOUCHED`

`HEALTH=NOT_RUN`

`FILEIPC=NOT_RUN`

`SETUP_READBACK=NOT_RUN`

## Cleanup and safety

Cleanup completed without warnings. The exact owned PID, temporary installed
bundle, and startup script were absent after cleanup. The verified DWT SHA
remained
`b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.
No candidate, source drawing, DXF, or production CAD state was changed.

The private proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\foreground-oracle-iteration98\foreground-oracle-proof.json`.
