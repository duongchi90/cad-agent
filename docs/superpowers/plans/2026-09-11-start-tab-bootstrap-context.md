# Start-Tab Bootstrap Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the existing File IPC client an explicit, fail-closed Start-tab bootstrap path so the dispatcher is loaded inside a disposable blank AutoCAD document before any approved source is opened read-only.

**Architecture:** Reuse the existing `FileIPCLiveMCPClient`, native command/LISP triggers, and File IPC ping. An opt-in constructor flag activates the path only when an injected native probe positively identifies AutoCAD's `[Start]` state; the path sends `_.QNEW`, loads the existing dispatcher in that new blank document, and requires one successful ping. The client exposes bounded no-save cleanup for the bootstrap document; normal writable/default drawing-open behavior remains unchanged.

**Tech Stack:** Python 3.11, `ctypes` Win32 window inspection, AutoCAD Mechanical 2027 command/LISP boundary, existing File IPC dispatcher, unittest/pytest.

**Spec:** `docs/superpowers/plans/2026-09-10-standalone-dwg-component-extraction-provenance.md` and SOL iteration-32 bounded action recorded in the active C2C session.

## Global Constraints

- Keep the existing File IPC transport, dispatcher, and AutoCAD owners; add no second transport or truth store.
- The bootstrap document is disposable only, is never source/candidate evidence, and is closed with no save.
- `bootstrap_start_tab` is opt-in; the default constructor and all existing writable callers retain their behavior.
- A real active document must not trigger `_.QNEW`; a non-positive or unverified Start state fails closed or leaves the existing real-document path untouched.
- A failed blank-document creation, LISP load, or ping must fail closed and attempt no source open.
- Do not change `S3C_SOURCE_READ_ONLY_REQUIRED`, source/accepted-drawing custody, candidate policy, or reviewed source metadata.
- Run focused tests, `scripts/verify.ps1`, and `git diff --check`; commit and push this remediation separately before live Task-6 rerun.

---

## Iteration 39 claim-binding addendum

SOL found that applying the owned startup-session trigger did not recompute the client's legacy-mode state. The bounded follow-up requires the trigger to advertise claim capability and flips the client to non-legacy mode before the first readiness ping. A non-claim-bound trigger is rejected closed, while explicit legacy fixture callers outside the opt-in bootstrap route retain their existing behavior.

The remediation is pushed at code HEAD 386808924829062613d4658af937b98916a0db08. Focused checks pass (50 passed, 1 skipped, 1 deselected, 9 subtests); authoritative verification exits 0 with C# 238 passed, offline Python JUnit 3378 with zero product failures/errors/skips, offline IPC 134 clean, and unavailable-state probes of real-data 2 skipped and AutoCAD Mechanical 17 skipped. The causal-RED oracle remains an expected diagnostic failure. Live Task 6 is still NOT RUN.

Send this exact pushed state for fresh SOL review; do not run another live gate until a new bounded verdict arrives.

### Task 1: Add the opt-in bootstrap owner and regression coverage

**Files:**
- Modify: `mcp_integration_lib/mcp_client.py`
- Test: `mcp_integration_lib/tests/test_mcp_client_drawing_open.py`

**Interfaces:**
- Add constructor keyword `bootstrap_start_tab: bool = False`.
- Add `FileIPCLiveMCPClient.ensure_start_tab_bootstrap() -> bool`, returning `True` only when it created and successfully pinged a bootstrap document.
- Add `FileIPCLiveMCPClient.close_start_tab_bootstrap() -> None`, which closes only the tracked unsaved bootstrap document with no save and fails closed if active-document identity is not blank.
- Add `make_windows_start_tab_no_document_probe(hwnd: int) -> Callable[[], bool]`, which returns true only for a positive HWND whose main title ends in `[Start]`.
- When `bootstrap_start_tab=True`, `drawing_open()` must call `ensure_start_tab_bootstrap()` before its first source-open LISP expression. The method must not run when the probe says a real document is active.

- [ ] **Step 1: Write failing tests.** Add tests that assert:
  - an opt-in client with a positive Start probe sends exactly `_.QNEW`, loads the configured dispatcher, sends a ping, and records the bootstrap as active;
  - the bootstrap path is not entered when the probe is false for a real document;
  - missing probe/trigger, blank-document command failure, dispatcher-load failure, and ping failure raise without emitting a source-open `vla-open` expression;
  - `close_start_tab_bootstrap()` sends a no-save `_.CLOSE` only after checking the active document has an empty `FullName`;
  - default clients preserve the existing writable VLA/fallback behavior.

- [ ] **Step 2: Run the focused test file and verify RED.**

  Run:

  ```powershell
  .\.venv-py311\Scripts\python.exe -m pytest -q -p no:cacheprovider mcp_integration_lib\tests\test_mcp_client_drawing_open.py
  ```

  Expected: the new bootstrap tests fail because the constructor flag, owner methods, and native Start probe do not yet exist.

- [ ] **Step 3: Implement the smallest owner change.** Validate the strict boolean flag, use the existing `command_trigger('_.QNEW')`, wait for the existing document settle interval, load the existing `bootstrap_lisp_path` through `raw_lisp_trigger`, and call the existing `_wait_for_dispatcher()` exactly once. Track creation only after `QNEW` is delivered, close on load/ping failure, and never call the source-open expression until the method returns successfully.

**Iteration 33 hardening addendum:** the native command trigger's return is only
delivery evidence. After `_.QNEW`, the owner must use an explicit bounded
`bootstrap_document_ready_probe` and timeout to confirm that the window no
longer reports `[Start]` before marking ownership, loading LISP, or pinging.
If readiness is not confirmed, fail before LISP/source-open and do not attempt
cleanup unless bootstrap ownership was positively established. The Windows
adapter supplies the non-`[Start]` readiness probe; existing writable/default
behavior remains unchanged.

- [ ] **Step 4: Run focused GREEN checks.**

  Run the same focused test command and then:

  ```powershell
  .\.venv-py311\Scripts\python.exe -m pytest -q -p no:cacheprovider mcp_integration_lib\tests\test_mcp_client_drawing_open.py mcp_integration_lib\tests\test_file_ipc_windows_trigger.py mcp_integration_lib\tests\test_standalone_dwg_component_live.py -ra
  ```

  Expected: all deterministic tests pass; the live Task-6 test remains an explicit prerequisite skip when no AutoCAD session variables are supplied.

### Task 2: Opt Task-6 into the verified bootstrap context

**Files:**
- Modify: `mcp_integration_lib/tests/test_standalone_dwg_component_live.py`
- Modify: `mcp_integration_lib/mcp_client.py` only if Task 1's public helper needs its documented import/export location

**Interfaces:**
- Task 6 constructs its existing client with `bootstrap_start_tab=True` and a
  factory for an owned disposable AutoCAD startup-script session. The bounded
  script contains `_.QNEW`, the approved plugin `_.NETLOAD`, and a root-bound
  load of the existing dispatcher; it admits no source/save/extraction command.
  All triggers and probes are bound to the HWND of the launched process.
- The session positively confirms the non-`[Start]` document state before the
  client sends the first claim-bound FileIPC ping. Runtime LISP/command
  triggers remain available only after dispatcher readiness is established.
- The test calls `close_start_tab_bootstrap()` in its existing `finally` path; source, candidate, and accepted drawing cleanup remains owned by the existing test/gateway.

- [ ] **Step 1: Add the opt-in wiring and cleanup assertion.** Keep the approved source path, fixture, hashes, `read_only=True`, candidate root, and all existing custody assertions unchanged. Add no new source or candidate input.
- [ ] **Step 2: Run the deterministic Task-6 module tests.** Confirm only the existing live prerequisite skip occurs without the full live environment.

### Task 3: Record and release the remediation

**Files:**
- Modify: `docs/STATUS.md`
- Modify: `docs/superpowers/implementation-records/2026-09-10-standalone-dwg-component-extraction.md`
- Create outside Git: `C:\temp\cad-agent-task6-live-20260911\task6-bootstrap-context-iteration32-evidence.txt` and its matching resume state

- [ ] **Step 1: Run focused Ruff and the authoritative `scripts/verify.ps1` on a clean commit.** Record exact test totals, unavailable live markers, and `git diff --check`; never convert a skip to a pass.
- [ ] **Step 2: Commit and push code/test changes separately from documentation.** Verify local and remote HEAD match.
- [ ] **Step 3: Update the status and implementation record with the bootstrap boundary, exact SHAs, and truthful live state.** Commit and push documentation separately.
- [ ] **Step 4: Record C2C iteration 32, update the recoverable checkpoint, and send SOL the exact pushed HEAD.** Request only `VERDICT`, `MATERIAL_FINDING`, `NEXT_SINGLE_BOUNDED_ACTION`, and `HUMAN_GATE`; do not rerun live Task 6 until SOL reviews.

For the iteration-33 hardening, repeat the same focused/full verification and
record/push/review sequence with the new exact code/documentation SHAs before
any live Task-6 attempt.

## Iteration 36 owner addendum

SOL approved the iteration-35 primitive diagnostic with `VERDICT=PASS`,
`MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO`. The implementation boundary is
now the pushed code head
`8afc7c0494e14cf2711641e4c23b060df4920ef`:
`WindowsAutoCADStartTabSession` owns a fresh disposable `acad.exe` process,
launches a disposable `.scr` containing exactly `_.QNEW`, discovers and binds
the same process's main HWND, and uses the existing readiness probe before any
LISP or source-open action. Task 6 uses the session factory and a setup hook
to load the existing plugin after the blank document is ready; it no longer
relies on a keyboard `_.QNEW` delivery to an unowned `[Start]` window. The
owned session closes through WM_CLOSE and has a best-effort terminate fallback
only for that process after a bounded close timeout. The default client path
and writable behavior are unchanged.

The code commit was focused-tested and pushed separately. The authoritative
verify on the exact code head exited `0`; the causal-RED diagnostic remains an
expected negative oracle, and live Task 6 remains `NOT RUN` pending fresh SOL
review of the pushed owner change.

## Iteration 38 dispatcher-owner addendum

SOL classified the iteration-37 ping timeout as an initial dispatcher-load
owner finding and authorized exactly one non-live remediation. Code HEAD
`669472d2f8c900b58146e23921dab0fc90644d41` extends the owned startup-session
script with only bootstrap content: `_.QNEW`, optional approved-plugin
`_.NETLOAD`, and one AutoLISP expression that sets the exact FileIPC root and
loads the exact `mcp_dispatch.lsp`. The script contains no source path, save,
extraction, candidate, or publication operation. The session binds the same
launched PID/HWND, reports `dispatcher_preloaded`, and the client requires a
claim-bound FileIPC ping after readiness before any runtime setup hook or
source open. Existing runtime triggers and default writable behavior remain
unchanged.

Focused checks pass (`49 passed`, `1 skipped`, `1 deselected`, `9 subtests`)
with Ruff and `git diff --check` passing. The authoritative verify on the
exact code head exited `0`: C# `238 passed`; offline Python `3297 passed`,
`21 deselected`, `80 subtests`; offline IPC JUnit `134` with zero failures or
errors; real-data unavailable probe `2 skipped`; AutoCAD Mechanical
unavailable probe `17 skipped`; live Task 6 `NOT RUN`. Fresh SOL review is
required before another live gate.

---

## Plan self-review

- The plan preserves the existing source-open/read-only and disposable-candidate owners and addresses the exact SOL finding that `[Start]` has no executable document context.
- Tests cover opt-in behavior, real-document refusal, fail-closed failures, no source `vla-open` before readiness, no-save cleanup, and default compatibility.
- The next live action remains separately gated by SOL; this plan does not claim live acceptance.
