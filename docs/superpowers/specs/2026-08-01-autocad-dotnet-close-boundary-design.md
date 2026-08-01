# AutoCAD .NET Disposable Close Boundary Design

## Finding

The T09 live run proved that `health` and read-only `review` work through the
new Windows trigger, but `close_disposable` returned `Drawing is busy`. The
live stack calls `Document.CloseAndDiscard()` synchronously from inside the
`CADAGENT_DISPATCH` command. AutoCAD does not permit that document-close action
while the current command is still executing.

Autodesk's managed .NET guidance states that `Document.SendStringToExecute`
queues commands asynchronously and they are not invoked until the current .NET
command has ended. This is the selected root-cause fix boundary.

## Design

- Keep request validation, full-path identity, `disposable=true`, and
  `save_changes=false` guards unchanged.
- Change only the live close action in `CommandContext.CreateLive` to queue the
  native command `_.CLOSE _N ` through `Document.SendStringToExecute`.
- Keep the injected `Action closeWithoutSaving` in offline tests.
- Do not call `CloseAndDiscard` synchronously from `CADAGENT_DISPATCH`.
- The result is written before the queued AutoCAD command executes; the live
  smoke test must wait for the active window to leave the disposable DXF and
  assert the file remains on disk.

## Safety and verification

- The operation still requires matching active full path and explicit
  `disposable=true`, `save_changes=false`.
- T10 must not alter the old File IPC dispatcher or close non-disposable
  `Drawing1.dwg`.
- Existing C# tests remain green; add a pure close-command contract assertion.
- Re-run the live disposable sequence: health PASS, review PASS, queued close
  PASS, active document leaves `dotnet_live.dxf`, and the file remains.
- Missing live prerequisites remain `NOT RUN`; offline tests never imply live
  PASS.
