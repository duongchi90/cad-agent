# Mechanical BOM Live Gate and Legacy Close Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the disposable Mechanical BOM live gate, then fix and verify the legacy no-save close command boundary before merging.

**Architecture:** The live BOM path remains in the existing opt-in test and uses the managed .NET client. The legacy fix is isolated to `FileIPCLiveMCPClient.drawing_close` and its focused tests; it replaces direct COM close with a queued AutoCAD command expression.

**Tech Stack:** Windows PowerShell, Python 3.11, pytest, AutoCAD Mechanical 2027, existing Win32 command-line trigger.

## Global Constraints

- Use only disposable DXF files under `C:\temp`.
- Do not open, close, save, or modify `Drawing1.dwg`.
- Live state is exactly `PASS`, `SKIP`, or `NOT RUN`; offline tests never imply live PASS.
- Do not change the external `mcp_dispatch.lsp` file.
- Do not change the .NET plugin, `scripts/verify.ps1`, or production repair code.

## Task 1: Mechanical BOM live gate

**Files:** Existing live test plus its ordering assertion; no production source changes.

- [x] Confirm AutoCAD is on `[Start]`, not a production drawing, and use the discovered window handle only if it remains unchanged.
- [x] NETLOAD the current managed plugin DLL and load the external legacy LISP dispatcher only as the disposable-DXF bootstrap.
- [x] Run the opt-in BOM live test with `CAD_AGENT_FILE_IPC=1`, `CAD_AGENT_AUTOCAD_HWND`, and `CAD_AGENT_AUTOCAD_LISP_PATH`.
- [x] Record `PASS`: the live test passed health, review, BOM payload, unchanged `DBMOD`, unchanged DXF hash, request cleanup, and close-without-save. The test's sorted expected block-name assertion was corrected from `FRAME, EMPTY` to `EMPTY, FRAME`.

## Task 2: Legacy close regression (TDD)

**Files:**

- Modify: `mcp_integration_lib/mcp_client.py` (`FileIPCLiveMCPClient.drawing_close`).
- Test: `mcp_integration_lib/tests/test_phase4.py` or a focused existing client test file.

- [x] Write a failing test with an injected raw-LISP trigger proving the no-save path sends exactly `(command-s "_.CLOSE" "_N")` and does not send `vla-close`.
- [x] Run the focused test and observe the expected failure against the current COM expression.
- [x] Replace only the raw no-save close expression with `(command-s "_.CLOSE" "_N")`; preserve the save-enabled branch and settle wait.
- [x] Run the focused test, the .NET/legacy IPC tests, Ruff, and `git diff --check`.
- [x] Review and commit the production fix (`2d26986`); the focused live close smoke also passed on a disposable DXF with an unchanged hash.

## Task 3: Integration

- [x] Run `scripts/verify.ps1` with the lock-matching Python 3.11 interpreter.
- [ ] Review the final diff and merge the reviewed branch into `main`.
- [ ] Push `main` and verify `HEAD == origin/main`.
- [ ] Update `docs/STATUS.md` only with evidence actually obtained after integration.
