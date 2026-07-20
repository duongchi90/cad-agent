# File IPC Live MCP Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-native File IPC client for real AutoCAD Phase 4 review and repair.

**Architecture:** Add an injectable synchronous File IPC transport in `mcp_integration_lib/mcp_client.py`. `FileIPCLiveMCPClient` maps the existing `MCPClient` protocol to dispatcher commands. Tests emulate the dispatcher by writing result files; the optional live test only reads the active drawing.

**Tech Stack:** Python 3.11+, unittest, JSON file IPC, AutoLISP dispatcher.

## Global Constraints

- Default IPC directory is `C:/temp`.
- Every request has a unique ID and removes its own files.
- Production Windows trigger is injectable; tests never need AutoCAD.
- Live smoke test requires `CAD_AGENT_FILE_IPC=1`.
- BLOCK/ATTRIB component creation remains out of scope.

---

### Task 1: Add failing transport/client tests

**Files:**
- Modify: `mcp_integration_lib/tests/test_phase4.py`
- Modify: `mcp_integration_lib/mcp_client.py`

- [ ] Add tests that instantiate `FileIPCLiveMCPClient(ipc_dir, trigger, timeout_s, poll_interval_s)`.
- [ ] In the fake trigger, read the command JSON and write the paired result JSON.
- [ ] Assert `drawing_open`, `entity_list`, and `entity_create_line` map to `drawing-open`, `entity-list`, and `create-line`, preserve arguments, and return normalized payloads.
- [ ] Add timeout and `ok: false` tests expecting `MCPTimeoutError` and `MCPToolError`.
- [ ] Run `python -m unittest mcp_integration_lib.tests.test_phase4 -v` and confirm failure before implementation.

### Task 2: Implement File IPC adapter

**Files:**
- Modify: `mcp_integration_lib/mcp_client.py`

- [ ] Add `FileIPCLiveMCPClient` with constructor:
  `(ipc_dir: str = "C:/temp", trigger: Callable[[], None] | None = None, timeout_s: float = 10.0, poll_interval_s: float = 0.1)`.
- [ ] Implement a private dispatch method that writes `autocad_mcp_cmd_<id>.json`, invokes the trigger, polls `autocad_mcp_result_<id>.json`, maps error states, and cleans up files in `finally`.
- [ ] Implement every existing `MCPClient` method by mapping to the AutoCAD File IPC command names.
- [ ] Run the focused unit suite and then `python -m unittest discover -s mcp_integration_lib/tests -v`.

### Task 3: Add opt-in live smoke verification

**Files:**
- Create: `mcp_integration_lib/tests/test_file_ipc_live.py`

- [ ] Skip unless `CAD_AGENT_FILE_IPC=1`.
- [ ] Instantiate the client with the production Windows dispatcher trigger.
- [ ] Call only `drawing_info` and `entity_list`; assert results are structured and do not modify the drawing.
- [ ] Document the exact Windows command to run the smoke test against an AutoCAD session with `mcp_dispatch.lsp` loaded.

### Task 4: Verify and commit

- [ ] Run the full Python 3.11 suite with Tesseract on PATH.
- [ ] Inspect `git diff`, commit only the adapter, tests, and handoff documentation, then push `agent/live-file-ipc`.
- [ ] Do not merge without an explicit review of the live smoke result.

## Self-review

The plan covers the transport contract, typed adapter, deterministic tests, opt-in live proof, and leaves unsupported component blocks out of scope.

