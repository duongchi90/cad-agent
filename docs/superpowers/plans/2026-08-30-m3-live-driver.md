# M3 Live Driver and Record Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the smallest stateless, fail-closed M3 live record contract and opt-in composition seam required before any provider or AutoCAD action.

**Architecture:** Add one pure `cad_agent` record oracle that seals and validates a single provider-backed disposable LINE epoch without persisting telemetry or owning transport. Add one integration-only composition driver that calls injected existing-owner callbacks in the fixed pre-R5 → authorization/repair → post-R5 order, counts exactly one repair attempt, and delegates all evidence truth to the existing R4/R5/R6/R7/FileIPC/.NET/provider results. Contract-only mode returns an explicit non-live `NOT_RUN` outcome and cannot produce a live PASS.

**Tech Stack:** Python 3.11, pytest, existing `canonical_json_sha256`, R4 candidate revisions, R5 visual verdicts, R6 repair/authorization results, R7/FileIPC/.NET evidence, and the existing AutoCAD opt-in test marker.

**Spec:** GitHub Issues #305, #301, and current M3 lookahead #311; advisory `5468137092`.

**Status:** executing

## Global Constraints

- Use only the existing R4/R5/R6/R7/FileIPC/.NET/provider owners; the new code is an evidence contract and integration composition seam.
- Do not add a database, telemetry service, retry daemon, transport, repair engine, shadow drawing store, or MECH-1 façade.
- `R5_MODE=contract-only` remains non-live; contract-only, `SKIP`, `NOT_RUN`, timeout, missing provider, or missing runtime identity can never become live PASS.
- A live PASS requires observed current main, exact plugin SHA match, observed PID/HWND/document identity, provider-backed pre-R5 FAIL, one consumed authorization, exactly one semantic R6 attempt, a distinct POST_REPAIR candidate, fresh provider-backed R5 PASS, transport reconciliation, integrity, and cleanup.
- The harness must not perform NETLOAD, UI automation, process control, source/accepted save, or live AutoCAD mutation during offline verification.
- Record validation is closed-key, lowercase-SHA, canonical-hash bound, and raises on any missing, unexpected, stale, rebound, or contradictory evidence.

---

### Task 1: Define the causal RED for the M3 record and composition seam

**Files:**
- Create: `tests/test_m3_live_record.py`
- Create: `mcp_integration_lib/tests/test_m3_live_harness.py`

**Interfaces:**
- Tests will require `cad_agent.m3_live_record.seal_m3_live_record` and `validate_m3_live_record`.
- Tests will require `mcp_integration_lib.m3_live_harness.compose_m3_live_epoch` and `M3LiveEpochNotRun`.

- [x] **Step 1: Write tests for a valid provider-backed record and closed-key/fail-closed cases**

  Build one complete in-memory record fixture with lowercase current-main/plugin hashes, observed PID/HWND, disposable document identity, distinct pre/post candidate hashes, provider-backed pre-Fail/post-Pass R5 identities, exactly one consumed authorization/repair, reconciled FileIPC/.NET/Task6/R6 transport counts, unchanged protected hashes, and zero-survivor close-without-save cleanup. Assert sealing adds a canonical record hash and validation returns the same record. Add failures for missing provider identity, mismatched plugin hashes, contract-only mode marked live, pre/post candidate rebinding, R5 `SKIP`/`NOT_RUN`, repair attempts other than one, transport count mismatch, changed protected hashes, ambiguous cleanup, unexpected keys, and a forged record hash.

- [x] **Step 2: Write tests for the opt-in composition driver**

  Provide callbacks representing the existing observation, R5, authorization/plan, R6 execution, post-candidate, post-R5, transport, and cleanup owners. Assert provider-backed mode invokes pre-R5, repair, and post-R5 in order exactly once and returns a sealed live record. Assert contract-only mode returns `M3LiveEpochNotRun` without invoking any callback. Assert callback R5 `PASS` before repair, stale candidate, replay/uncounted authorization, R6 non-success, post-R5 non-PASS, and cleanup ambiguity are rejected before a live PASS.

- [x] **Step 3: Run the new tests and confirm the causal RED**

  Run:

  ```powershell
  & 'C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe' -m pytest tests/test_m3_live_record.py mcp_integration_lib/tests/test_m3_live_harness.py -q -p no:cacheprovider
  ```

  Expected: collection fails because the two requested modules and interfaces do not yet exist; no production/runtime owner is changed.

### Task 2: Implement the stateless record oracle and injected composition seam

**Files:**
- Create: `cad_agent/m3_live_record.py`
- Create: `mcp_integration_lib/m3_live_harness.py`
- Test: `tests/test_m3_live_record.py`
- Test: `mcp_integration_lib/tests/test_m3_live_harness.py`

**Interfaces:**
- `seal_m3_live_record(payload: Mapping[str, object]) -> dict[str, object]` returns a closed record with `record_sha256`.
- `validate_m3_live_record(record: Mapping[str, object], *, expected_main_sha: str | None = None, expected_plugin_sha256: str | None = None) -> dict[str, object]` returns a deep-copied validated record or raises `M3LiveRecordError`.
- `compose_m3_live_epoch(..., mode: str, observe_runtime: Callable[[], Mapping[str, object]], collect_pre_r5: Callable[[Mapping[str, object]], Mapping[str, object]], authorize_repair: Callable[[Mapping[str, object]], Mapping[str, object]], execute_repair: Callable[[Mapping[str, object]], Mapping[str, object]], collect_post_candidate: Callable[[Mapping[str, object], Mapping[str, object]], Mapping[str, object]], collect_post_r5: Callable[[Mapping[str, object]], Mapping[str, object]], collect_transport: Callable[[], Mapping[str, object]], collect_integrity: Callable[[], Mapping[str, object]], collect_cleanup: Callable[[], Mapping[str, object]], collect_human_events: Callable[[], Mapping[str, object]]) -> dict[str, object]` returns a sealed record in provider-backed mode or raises `M3LiveEpochNotRun` in contract-only mode.

- [x] **Step 1: Add the smallest record validators**

  Implement closed-key validation for top-level mode/status/identity, runtime PID/HWND/document, candidate transition, provider-backed R5 verdict bindings, one authorization/one R6 attempt, transport reconciliation, protected-file integrity, human-event count, cleanup, and the canonical record hash. Require `mode == "LIVE_PROVIDER_BACKED"` and `status == "PASS"` for live acceptance; reject `CONTRACT_ONLY`, `SKIP`, `NOT_RUN`, timeout, provider-missing, or non-success evidence from live PASS. Preserve all evidence fields without raw customer paths.

- [x] **Step 2: Add the fixed-order composition seam**

  Implement the integration function as a thin callback coordinator. In provider-backed mode it must observe runtime first, collect a provider-backed pre-R5 `FAIL`, request one authorization/plan, execute exactly one approved repair, collect a distinct post candidate, collect a fresh provider-backed post-R5 `PASS`, collect transport/integrity/cleanup/human evidence, and seal through the record oracle. Any callback exception or non-accepted result is propagated as a non-PASS error; no retry is performed. In contract-only mode raise `M3LiveEpochNotRun("R5_MODE=contract-only")` before invoking callbacks.

- [x] **Step 3: Run focused GREEN verification and lint**

  Run the two new test modules and Ruff on the two implementation modules. Expected: all new tests pass, including callback order/count and all fail-closed cases.

### Task 3: Integrate documentation and verify the offline boundary

**Files:**
- Modify: `docs/STATUS.md`
- Modify: `docs/superpowers/plans/2026-08-30-m3-live-packet.md`
- Test: `tests/test_documentation_contract.py`

**Interfaces:**
- Documentation records the exact merged main/head, record schema/driver paths, contract-only non-live behavior, and the next manual gate only after the driver is independently verified.

- [ ] **Step 1: Record the observed offline driver state**

  Add the implementation head, focused test result, and explicit `LIVE_REPAIR_ACCEPTANCE=NOT_RUN`. State that the driver is opt-in and callback-injected; it does not itself perform NETLOAD or AutoCAD mutation.

- [ ] **Step 2: Run documentation and nearest regression tests**

  Run:

  ```powershell
  & 'C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe' -m pytest tests/test_documentation_contract.py tests/test_m3_live_record.py mcp_integration_lib/tests/test_m3_live_harness.py -q -p no:cacheprovider
  git diff --check
  ```

- [ ] **Step 3: Run the canonical offline verifier**

  Run `.\scripts\verify.ps1 -SkipAutoCADDotNet` from a clean worktree. Accept only exit 0; real-data and AutoCAD unavailable states remain `SKIP`/`NOT RUN`, never PASS.

- [ ] **Step 4: Commit the bounded implementation and evidence**

  Commit production contract, integration harness, tests, plan, packet, and status in scoped normal commits; do not amend, rebase, squash, or force-push.

### Task 4: Host and merge only the safe offline slice

**Files:**
- No additional runtime files.

**Interfaces:**
- The PR must bind exact base/head, list no live result, and preserve the existing `R5_MODE=contract-only` boundary.

- [ ] **Step 1: Fresh-read GitHub and advisory state before push/PR**

  Verify current `main`, current #301/#311 advisory, active PR overlap, clean worktree, and exact branch head. Do not overlap maintenance #312.

- [ ] **Step 2: Push, run hosted checks, and inspect exact head**

  Hosted checks must pass on the exact PR head. Any failure is diagnosed at the first causal boundary and fixed with a new normal commit.

- [ ] **Step 3: Fresh-read before merge and merge normally if clean**

  Merge only when current main, exact head, checks, advisory disposition, and write-set are clean. After merge, fresh-read main and record `LIVE_REPAIR_ACCEPTANCE=NOT_RUN`.
