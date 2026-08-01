# AutoCAD .NET Live Trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe Windows command trigger and an opt-in disposable live smoke test for the AutoCAD .NET JSON/File IPC path.

**Architecture:** The existing injected `DotNetIPCClient.trigger` seam gains a Windows implementation that posts the exact `CADAGENT_DISPATCH` command to a caller-supplied AutoCAD MDI client. The live test uses the old File IPC client only for disposable DXF open/handle discovery, then exercises the new .NET client for health, read-only review, and close-without-save.

**Tech Stack:** Python 3.11, ctypes/winuser32, pytest/unittest, ezdxf, AutoCAD Mechanical 2027, existing JSON/File IPC contract.

## Global Constraints

- Windows only; target AutoCAD Mechanical 2027 and Python 3.11.
- The exact new public factory is `make_windows_dotnet_dispatch_trigger(hwnd: int) -> Callable[[], None]`.
- The trigger sends only `CADAGENT_DISPATCH` to the supplied AutoCAD window; it does not use COM, inspect arbitrary windows, or fall back to the old AutoLISP dispatcher.
- The live test uses only a DXF under `C:\temp`, performs no production save/repair/mutation, and closes the disposable drawing without saving.
- Do not modify `mcp_integration_lib/mcp_client.py`, any C# file, `scripts/verify.ps1`, `docs/STATUS.md`, or the old dispatcher.
- Live prerequisites are explicit skip/not-run; offline evidence never implies live PASS.

### Task 9: Windows .NET dispatch trigger and disposable live smoke

**Files:**

- Modify: `mcp_integration_lib/dotnet_ipc.py` (trigger factory and its small Win32 seam only).
- Modify: `mcp_integration_lib/tests/test_dotnet_ipc.py` (offline trigger validation/message tests).
- Create: `mcp_integration_lib/tests/test_dotnet_ipc_live.py` (opt-in AutoCAD Mechanical live smoke only).

**Interfaces:**

- Consumes: `DotNetIPCClient`, `health`, `review`, and `close_disposable` from the existing module; `FileIPCLiveMCPClient` and its existing open/handle helpers only for disposable setup.
- Produces: `make_windows_dotnet_dispatch_trigger(hwnd: int) -> Callable[[], None]` and an opt-in live test marked `autocad_mechanical`.

- [ ] **Step 1: Write failing offline tests**

  Add tests that reject `hwnd <= 0` and verify the trigger sends two Escape
  key messages, the exact `CADAGENT_DISPATCH` characters, and Enter through a
  deterministic injected Win32 seam. Keep existing fake-dispatcher contract
  tests unchanged.

- [ ] **Step 2: Run the focused tests and confirm the new tests fail**

  Run:

  ```powershell
  & .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -q -p no:cacheprovider
  ```

  Expected: the existing tests pass and the new trigger tests fail because the
  factory/seam is not implemented.

- [ ] **Step 3: Implement the minimal Windows trigger**

  Add the exact public factory in `dotnet_ipc.py`. Validate the integer handle,
  locate the MDI child of the supplied top-level window using the same Win32
  class lookup convention as the existing client, and post UTF-16 character
  messages for `\x1b\x1bCADAGENT_DISPATCH\r`. Keep Win32 access isolated behind
  a small injectable seam so the offline tests never need AutoCAD.

- [ ] **Step 4: Run focused offline tests and lint**

  Run:

  ```powershell
  & .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -q -p no:cacheprovider
  & .\.venv-py311\Scripts\python.exe -m ruff check mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc_live.py
  ```

  Expected: all focused tests pass and Ruff reports no violations.

- [ ] **Step 5: Add the opt-in live smoke test**

  Create `test_dotnet_ipc_live.py` with the `autocad_mechanical` marker and
  skip guard on `CAD_AGENT_FILE_IPC == "1"`. Require
  `CAD_AGENT_AUTOCAD_HWND` and `CAD_AGENT_AUTOCAD_LISP_PATH`; use the existing
  legacy client to open one generated DXF below `C:\temp` and discover one
  handle, then use `DotNetIPCClient` with the new trigger for health, review,
  and close-disposable. Assert plugin version `1.0.0`, successful read-only
  results, exact active full path, no changes, and cleanup of request/result
  files. The `finally` path must close without saving if the drawing is still
  open and remove only the test directory.

- [ ] **Step 6: Run the live test only when prerequisites are explicitly ready**

  Manual prerequisite: start AutoCAD Mechanical 2027, open a disposable DXF
  below `C:\temp`, manually NETLOAD the built plugin, and set the existing
  File IPC environment variables. Then run:

  ```powershell
  $env:CAD_AGENT_FILE_IPC = '1'
  & .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc_live.py -q -p no:cacheprovider
  ```

  If any prerequisite is absent, record `SKIP`/`NOT RUN`; do not send commands
  to a non-disposable active drawing.

- [ ] **Step 7: Self-review and commit**

  Run `git diff --check`, verify only the three allowed files changed, and
  commit with:

  ```powershell
  git add mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc_live.py
  git commit -m "feat: add Windows trigger for dotnet IPC live smoke"
  ```

## Dependency graph and ownership

| Task ID | Objective | Depends on | Branch | Allowed files | Forbidden files | Parallel with | Mandatory tests | Completion condition |
|---|---|---|---|---|---|---|---|---|
| T09 | Trigger `CADAGENT_DISPATCH` from Windows and test the .NET path on a disposable drawing | Current integration head recorded by PO immediately before dispatch | `codex/autocad-dotnet-t09-live-trigger` | `mcp_integration_lib/dotnet_ipc.py`, `mcp_integration_lib/tests/test_dotnet_ipc.py`, `mcp_integration_lib/tests/test_dotnet_ipc_live.py` | All C# files, `mcp_client.py`, `reviewer2.py`, `repair2.py`, `scripts/verify.ps1`, `docs/STATUS.md`, contracts, production drawings | None; sequential after the integration head | Focused pytest + Ruff; opt-in live test must be PASS, SKIP, or NOT RUN | Offline trigger tests and existing contract/review gates pass, live test is safe/disposable and explicitly marked, write-set/review clean. |

## Wave schedule

- **WAVE 5A:** PO writes this spec, plan, and task card; Coder T09 starts from
  the exact integration HEAD recorded immediately before dispatch in its own
  branch/worktree.
- **WAVE 5B:** PO reviews T09 commit and runs focused offline verification.
- **WAVE 5C:** If an operator-controlled disposable AutoCAD session is
  available, run the opt-in live test; otherwise record `NOT RUN` and keep the
  candidate partially verified.
- **WAVE 5D:** PO updates `docs/STATUS.md` only after review and fresh tests.
