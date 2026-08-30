# M3 Disposable LINE Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** completed

**Base SHA:** `aaa90e6aeaa31feec0b9e9e6eec42f0051ee0d80`

**Completion Head SHA:** `3c60460baa998651008758702c1f6dc5bde06e59`

**Goal:** Add one explicit contract-only M3 acceptance epoch that composes the existing R4/R5/R6 owners for a candidate-only LINE repair and records a fresh post-repair R5 PASS without claiming live AutoCAD evidence.

**Architecture:** Reuse all existing production owners and add one acceptance test module that imports the existing R4 fixture builders, mints an owner-validated R5 FAIL bound to a disposable candidate, calls the existing repair planner, authorization, `DotNetIPCClient` disposable-workspace owner, and `execute_approved_repair`, then builds a real POST_REPAIR R4 child and independently validates a new R5 PASS. A causal RED exposed that the existing R6 planner could not consume an owner-valid v1.1 root because that root intentionally has no legacy latest-mutation field; the only production change is a fail-closed owner-derived fallback in the existing R6 adapter for `ROOT_PRE_REPAIR`. The test records only bounded evidence in memory and asserts source/base/accepted files remain byte-identical.

**Tech Stack:** Python 3.11, pytest, existing `cad_agent` R4/R5/R6/R7 contracts, existing `mcp_integration_lib` repair executor, `DotNetIPCClient` offline dispatcher seam, temporary filesystem candidates.

**Spec:** GitHub Issue #308, current `SOL_M3_REUSE_DOSSIER_V1`, with explicit owner authorization `R5_MODE=contract-only` from the Human Owner.

## Global Constraints

- Use existing R4/R5/R6/R7 owners; permit only the causal, fail-closed v1.1 root compatibility repair in the existing R6 adapter; do not add a Repair Loop service, persistence store, retry daemon, transport, mutation engine, or new production API.
- Use one LINE operation and one single-use authorization; any failure, stale binding, or cleanup ambiguity is non-acceptance.
- Use only disposable temporary files; source, base, and accepted drawings must be created as immutable sentinel files and remain unchanged.
- Label the result `CONTRACT_ONLY`; it is not live AutoCAD/R5 visual evidence and cannot promote M3 live acceptance.
- Keep `BVTL.dwg` and the active AutoCAD process untouched; no NETLOAD, process control, save, or UI automation.
- Run focused tests first, then the canonical offline verifier and `git diff --check` before commit or completion claim.

### Task 1: Close the v1.1 root seam and add the causal contract-only acceptance harness

**Files:**
- Create: `mcp_integration_lib/tests/test_m3_disposable_repair_acceptance.py`
- Modify: `cad_agent/approved_repair_adapter.py` in the existing R5-to-R6 candidate binding helper
- Test: `mcp_integration_lib/tests/test_m3_disposable_repair_acceptance.py`

**Interfaces:**
- Consumes: `cad_agent.candidate_revision`, `cad_agent.visual_supervisor_adapter`, `cad_agent.approved_repair_adapter`, `cad_agent.repair_authorization`, `cad_agent.repair_operation_contract`, `cad_agent.drawing_artifact_reference`, and the existing test-only offline workspace/executor seams.
- Produces: `run_contract_only_line_epoch(tmp_path) -> dict[str, object]` local acceptance composition with explicit `acceptance_mode`, `pre_repair_r5`, `r6_result`, `post_repair_candidate`, `post_repair_r5`, `repair_attempts`, and integrity/cleanup evidence.

- [x] **Step 1: Write the failing test**

  Add one test named `test_m3_contract_only_line_epoch_composes_fresh_r5_after_one_r6_mutation` that imports the existing accepted R4 fixture builder, constructs a root candidate and source/base/accepted sentinels, and calls the wished-for `run_contract_only_line_epoch(tmp_path)`. Assert the returned record contains `acceptance_mode == "CONTRACT_ONLY"`, `pre_repair_r5["verdict"] == "FAIL"`, `r6_result["mutation_outcome"] == "SUCCESS"`, `r6_result["requires_new_r5_cycle"] is True`, `post_repair_r5["verdict"] == "PASS"`, `repair_attempts == 1`, `executor_calls == 2` for one erase plus one LINE create, `closure.cleanup_outcome == "zero_survivors"`, `closure.save_changes is False`, and all three protected sentinel hashes are unchanged.

- [x] **Step 2: Run the new test to verify the causal RED**

  Run:

  ```powershell
  & 'C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe' -m pytest -q mcp_integration_lib/tests/test_m3_disposable_repair_acceptance.py
  ```

  Expected: FAIL because the new acceptance composition function does not exist; no existing live or production owner is altered.

- [x] **Step 3: Implement the smallest owner repair and test-only composition**

  Implement the helper in the same test module. It must:

  1. build the v1.1 `ROOT_PRE_REPAIR` candidate through the accepted R4 fixture builder and validate its candidate state;
  2. write only disposable candidate/source/base/accepted sentinel files and hash them before execution;
  3. create a closed R5 result with literal `FAIL`, exact root candidate/state/registry/latest-mutation bindings, and `R5_MODE=contract-only` metadata kept outside the R5 owner result;
  4. build a visual-contract repair plan bound to the root artifact, normalize one `REPAIR_DXF_PRIMITIVE` LINE operation, and call `prepare_repair_plan`;
  5. issue one exact `RepairAuthorization`, issue one existing `DotNetIPCClient` disposable lease, and call `execute_approved_repair` with the existing offline dispatcher and executor seam;
  6. validate the R6 result with all exact candidate/R5/plan/operation bindings and assert the executor observed exactly one erase and one create;
  7. construct actual POST_REPAIR DARA child reference, transition evidence containing the validated R6 result, refreshed current observation/correspondence, and a v1.1 `POST_REPAIR` candidate using `build_candidate_revision`;
  8. build a new candidate state and a separate owner-validated R5 `PASS` with a new request/observation identity and the post-repair mutation hash;
  9. close/verify the temporary workspace through the existing owner and return only explicit bounded evidence, including pre/post candidate artifact hashes, old/new handles, one repair attempt, cleanup, and unchanged protected-file hashes.

  In `cad_agent/approved_repair_adapter.py`, add only the existing-owner helper required by the causal RED: when a validated candidate is exactly `candidate-revision-1.1` with `candidate_kind == "ROOT_PRE_REPAIR"` and has no legacy latest-mutation field, derive the expected latest mutation identity from `canonical_json_sha256(candidate["mutation_evidence"])`; preserve the explicit field requirement for all other candidates and use this helper at the existing R5 mutation-binding check.

  The helper must not call `finalize_visual_verdict` because this mode has no real visual provider; the contract-only R5 FAIL is explicitly owner-validated contract evidence and the returned record must never be labelled live or representative.

- [x] **Step 4: Run the focused GREEN test**

  Run the same pytest command from Step 2.

  Expected: one passing contract-only acceptance test with no AutoCAD marker and no skipped test.

- [x] **Step 5: Add focused negative assertions and run them**

  Add assertions in the same test module that a pre-repair R5 PASS cannot be passed to `prepare_repair_plan`, that mutating the R5 candidate SHA causes R6 refusal before executor calls, that replaying the consumed authorization fails, and that changing the post-repair R5 candidate/state binding is rejected. Run:

  ```powershell
  & 'C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe' -m pytest -q mcp_integration_lib/tests/test_m3_disposable_repair_acceptance.py tests/test_cad_agent_r8_synthetic_pilot.py tests/test_cad_agent_approved_repair_adapter.py tests/test_cad_agent_repair_authorization.py tests/test_cad_agent_repair_operation_contract.py
  ```

  Expected: all focused tests pass and the negative assertions prove fail-closed behavior without mutation on rejected paths.

- [x] **Step 6: Commit the bounded slice before canonical verification**

  The repository verifier requires a clean worktree before it starts, so commit the already-verified bounded slice first:

  ```powershell
  git add cad_agent/approved_repair_adapter.py docs/superpowers/plans/2026-08-30-m3-disposable-line-acceptance.md mcp_integration_lib/tests/test_m3_disposable_repair_acceptance.py
  git commit -m "test: compose contract-only M3 line repair acceptance"
  ```

- [x] **Step 7: Run canonical verification and inspect the clean tree**

  Run:

  ```powershell
  .\scripts\verify.ps1 -SkipAutoCADDotNet
  git diff --check
  git status --short
  ```

  Expected: canonical offline verifier exits 0 with zero failures/errors, the intentional existing causal RED remains handled by the verifier, `git diff --check` is clean, and only the plan, acceptance test, and the single existing-owner compatibility helper are changed.

### Task 2: Record truthful M3 offline status

**Files:**
- Modify: `docs/STATUS.md` in the M3/repair-loop status section

**Interfaces:**
- Consumes: the committed contract-only test result and canonical verifier output from Task 1.
- Produces: a status entry that distinguishes contract-only M3 composition from live AutoCAD M3 acceptance and records the exact commit/commands.

- [x] **Step 1: Write the status assertion first**

  Add a documentation-contract assertion only if the existing status contract lacks a stable M3 section; otherwise keep the change documentation-only and assert through the existing documentation tests that the text includes `CONTRACT_ONLY`, `live AutoCAD M3: NOT RUN`, one repair attempt, and the exact verification command.

- [x] **Step 2: Run the documentation-focused test and update the status**

  Run:

  ```powershell
  & 'C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe' -m pytest -q tests/test_documentation_contract.py
  ```

  Update `docs/STATUS.md` only with observed facts. Do not claim live R5, live R6, production mutation, or M3 milestone closure.

- [x] **Step 3: Re-run the canonical verifier and commit**

  ```powershell
  .\scripts\verify.ps1 -SkipAutoCADDotNet
  git diff --check
  git add docs/STATUS.md
  git commit -m "docs: record contract-only M3 acceptance boundary"
  ```
