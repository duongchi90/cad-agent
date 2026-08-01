# Task Card T05 — Python dotnet_ipc Backend

**Role:** Coder  
**Model:** Luna Extra High (`gpt-5.6-luna`, reasoning `xhigh`)  
**Base:** The exact SHA of `integration/autocad-dotnet-option-a` after PO integrates WAVE 2  
**Branch:** `codex/autocad-dotnet-t05-python-ipc`  
**Worktree:** `D:\cad-agent-master\cad-agent\.worktrees\autocad-dotnet-t05-python-ipc`

## Objective

Add a separate Python client for the C# plugin while leaving the existing `FileIPCLiveMCPClient` and AutoLISP dispatcher untouched.

## Allowed files

- `mcp_integration_lib/dotnet_ipc.py`
- `mcp_integration_lib/tests/test_dotnet_ipc.py`

## Forbidden files

`mcp_integration_lib/mcp_client.py`, `reviewer2.py`, `repair2.py`, existing tests, all C# files, contracts, scripts, and status files.

## Required interface

Expose a `DotNetIPCClient` with injected trigger and bounded polling. It must provide `request(...)`, `health(...)`, `review(...)`, and `close_disposable(...)`, use the new filename prefix, preserve request ids, and accept a default `C:\temp`-equivalent IPC directory without hardcoding a user-specific path.

## Required verification

```powershell
python -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -q -p no:cacheprovider
python -m ruff check mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py
```

Tests must cover injected trigger, health round-trip, review parameters, disposable-close guard, timeout, request-specific cleanup, and coexistence with old `autocad_mcp_*` files.

## Completion report

Return commit SHA, changed files, test output, and proof that `mcp_client.py` is byte-for-byte untouched. Do not merge.
