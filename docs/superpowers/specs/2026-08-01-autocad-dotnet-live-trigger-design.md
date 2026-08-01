# AutoCAD .NET Live Trigger Design

## Goal

Make the isolated Python `DotNetIPCClient` usable against a manually loaded
AutoCAD Mechanical 2027 .NET plugin on Windows, and add an opt-in live smoke
test that uses only a disposable drawing.

## Scope and safety boundary

- Windows only; target AutoCAD Mechanical 2027 and Python 3.11.
- Add a Windows message trigger for the exact AutoCAD command
  `CADAGENT_DISPATCH`.
- The trigger may clear pending command input with two Escape keystrokes, type
  the command, and submit Enter to the AutoCAD MDI client window.
- The trigger must accept an explicit AutoCAD top-level window handle and must
  not discover, activate, or close an arbitrary AutoCAD window.
- The live test requires the operator to NETLOAD the built plugin and provide
  the AutoCAD/File IPC environment variables. It must create/open only a DXF
  below `C:\temp`, review one or more handles, and close it without saving.
- Do not modify the existing `FileIPCLiveMCPClient`, its AutoLISP dispatcher,
  the existing dispatcher behavior, production-drawing workflows, or
  `scripts/verify.ps1`.
- Live absence remains explicit `SKIP`/`NOT RUN`; build and offline tests never
  imply live `PASS`.

## Approaches considered

### A — Windows message command trigger (selected)

Reuse the proven MDI-child lookup and `PostMessageW` pattern already present in
`mcp_client.py`, but expose a .NET-specific trigger that sends only
`CADAGENT_DISPATCH`. This keeps the new backend independent from the old
AutoLISP dispatcher and avoids COM/version coupling.

### B — AutoCAD COM/ROT `SendCommand`

Send the command through the running AutoCAD COM object. This avoids simulated
keystrokes but depends on ProgID/ROT availability, focus/state behavior, and
AutoCAD COM version details. It is not selected for the first live gate.

### C — Manual-only operation

Keep the backend test-only and require the operator to run every command by
hand. This has the lowest code risk but leaves the new JSON/File IPC path
without a reproducible live smoke harness. It is not selected.

## Interfaces and data flow

The Python module shall expose:

```python
def make_windows_dotnet_dispatch_trigger(hwnd: int) -> Callable[[], None]: ...
```

The returned callback sends `CADAGENT_DISPATCH` to the MDI client associated
with the supplied top-level `hwnd`. `DotNetIPCClient` remains unchanged at the
transport boundary: it writes `cadagent_dotnet_request_<id>.json`, calls the
injected callback, polls the matching result, validates the request id, and
cleans only its own files.

The live test uses the existing legacy File IPC client only to open a generated
disposable DXF and obtain a real entity handle. It uses the new client for:

1. `health` with no drawing path;
2. `review` with the disposable DXF full path and the real handle; and
3. `close_disposable` with `disposable=true` and `save_changes=false`.

The test must assert the plugin version `1.0.0`, the returned full path,
`changed == false`, a successful review, and that the request/result files are
gone after each request. Cleanup must attempt close-without-save and remove
only the test's temporary DXF directory.

## Error handling

- Reject invalid/non-positive window handles before calling Win32 APIs.
- Preserve the existing bounded timeout and protocol validation behavior.
- Surface a missing or unusable AutoCAD trigger as the existing
  `DotNetIPCError`/timeout path; do not silently fall back to the old
  dispatcher.
- The live test must skip when `CAD_AGENT_FILE_IPC != "1"`, when the AutoCAD
  HWND is absent, or when the legacy LISP path is absent. It must never turn an
  unavailable live prerequisite into a passing result.

## Verification

- Offline unit tests cover trigger input validation and the exact command
  string/Win32 message sequence through an injected Win32 seam or equivalent
  deterministic seam.
- Existing `mcp_integration_lib/tests/test_dotnet_ipc.py` remains green.
- The opt-in live test is marked `autocad_mechanical` and is run directly with
  the operator-provided environment after manual NETLOAD.
- No source, configuration, or output file outside the task write-set is
  changed.
