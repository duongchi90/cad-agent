# T09 — Windows .NET dispatch trigger and disposable live smoke

## Assignment

Implement the approved live-gate bridge for the AutoCAD .NET plugin. Work only
in branch `codex/autocad-dotnet-t09-live-trigger` and its dedicated worktree.
Start from base commit `e57f48b` on
`integration/autocad-dotnet-option-a`.

## Allowed write-set

- `mcp_integration_lib/dotnet_ipc.py`
- `mcp_integration_lib/tests/test_dotnet_ipc.py`
- `mcp_integration_lib/tests/test_dotnet_ipc_live.py`

## Forbidden write-set

All other files, especially C# plugin files, `mcp_integration_lib/mcp_client.py`,
the legacy AutoLISP dispatcher, `scripts/verify.ps1`, `docs/STATUS.md`, and any
production drawing or generated artifact.

## Contract

Expose:

```python
make_windows_dotnet_dispatch_trigger(hwnd: int) -> Callable[[], None]
```

It validates a positive integer top-level AutoCAD window handle, finds its MDI
client, and posts only `\x1b\x1bCADAGENT_DISPATCH\r`. Keep the Win32 calls behind
an offline-testable seam. Do not use COM or fall back to the old dispatcher.

The opt-in live test must use only a generated DXF below `C:\temp`; manually
NETLOAD is an operator prerequisite. Use the old client only to open the
disposable drawing and obtain a handle. Use `DotNetIPCClient` for health,
review, and `close_disposable(disposable=True, save_changes=False)`. Assert
plugin version `1.0.0`, full-path identity, `changed == false`, request-id
cleanup, and close-without-save. Missing prerequisites are explicit SKIP/NOT
RUN, never inferred PASS.

## Required checks

```powershell
& .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -q -p no:cacheprovider
& .\.venv-py311\Scripts\python.exe -m ruff check mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc_live.py
git diff --check
```

If live prerequisites are supplied, also run the opt-in live test and report
exactly PASS, SKIP, or NOT RUN. Self-review the diff and commit it; do not
merge.
