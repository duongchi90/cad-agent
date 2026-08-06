# Official Vision Handoff and Codex Worker Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` only after a future implementation Issue separately authorizes this plan. Issue #70 itself is planning-only.

**Goal:** Define a closed, hash-bound ChatGPT-to-Codex handoff and a fail-closed official SDK worker-control boundary without enabling runtime, dependency, model, private-data, or AutoCAD behavior.

**Architecture:** CAD Agent validates a versioned `vision-handoff`, owns source/evidence identity, scope, protected constraints, approval, expiry, and stale rejection, then calls a thin official Codex Python SDK adapter. The adapter owns only worker lifecycle and bounded turn events; Codex returns an untrusted schema-bound drawing/repair plan that existing CAD validators must accept before any later executor is called.

**Tech Stack:** Python 3.11 on Windows, existing `cad_agent`/`agent_lib` APIs, JSON Schema contracts, pytest/Ruff, canonical `scripts/verify.ps1`, official OpenAI Codex Python SDK first, official App Server only for proven SDK gaps, and bounded `codex exec --json` fallback only for disposable compatibility work.

## Global Constraints

- Issue #70 implementation begins only from exact base `d71d0c97e28e03cb430f05589c8381b4ede70e66`.
- Issue #70 planning PR changes exactly the two documents named in the Issue; no runtime or dependency change is allowed.
- `openai-codex==0.144.4` is historical compatibility evidence only; it is not a production pin from this plan.
- Codex has no visual PASS, CAD truth, engineering approval, AutoCAD mutation, or publication authority.
- The first future runtime slice uses a fake adapter and disposable repository tests; no real model call or AutoCAD mutation.
- Source CAD, accepted CAD, private data, existing manifests/checkpoints, File IPC/.NET, OCR, solver, registry, revision, repair, verdict, publisher, STATUS, and HANDOFF remain out of scope.
- All output is untrusted until strict schema, scope, protected-target, hash, freshness, and approval checks pass.
- Every future implementation Issue must restate its exact base, allowlist, reuse dossier, verification commands, unavailable gates, and rollback.

---

## Future implementation map

The following tasks are an execution-ready plan for a later authorized runtime
Issue. They are not implementation instructions for the current Wave 1A
planning PR.

### Task 1: Freeze the closed vision-handoff contract

**Files:**
- Create: `contracts/vision-handoff/vision-handoff.schema.json`
- Create: `cad_agent/vision_handoff.py`
- Test: `tests/test_vision_handoff.py`
- Test: `tests/test_vision_handoff_contract.py`

**Interfaces:**
- Consumes: PO-provided intent/scope/evidence references and existing run,
  source, IR, manifest, and visual-contract identities.
- Produces: `ValidatedVisionHandoff` with canonical JSON bytes, SHA-256,
  normalized scope, effective write roots, expiry/single-use status, and
  immutable input identities.

- [ ] **Step 1: Write contract tests for the closed object.** Cover required
  identity, scope, allowed/forbidden operation classes, protected constraints,
  expected output schema, approval, expiry, and single-use fields. Assert that
  missing fields, extra keys, malformed SHA-256 values, non-finite values,
  conflicting identities, and unknown enums fail closed.
- [ ] **Step 2: Run the contract tests before implementation.**

  Run: `python -m pytest tests/test_vision_handoff.py tests/test_vision_handoff_contract.py -q`

  Expected: FAIL because the future contract and validator do not yet exist.
- [ ] **Step 3: Implement only the validator and canonical identity builder.**
  Reuse `cad_agent.visual_contracts` validation primitives and existing
  manifest/evidence hash functions. Do not add a second manifest store or read
  private file contents into the contract.
- [ ] **Step 4: Run the focused contract tests.**

  Run: `python -m pytest tests/test_vision_handoff.py tests/test_vision_handoff_contract.py -q`

  Expected: all focused handoff tests pass with no skipped safety cases.
- [ ] **Step 5: Commit the bounded contract.**

  Run: `git add contracts/vision-handoff/vision-handoff.schema.json cad_agent/vision_handoff.py tests/test_vision_handoff.py tests/test_vision_handoff_contract.py; git commit -m "feat: add closed vision handoff contract"`

### Task 2: Add the optional official SDK worker seam

**Files:**
- Create: `agent_lib/codex_worker.py`
- Test: `agent_lib/tests/test_codex_worker.py`
- Reuse without behavior change: `agent_lib/codex_sdk_compat.py`

**Interfaces:**
- Consumes: `ValidatedVisionHandoff`, a disposable workspace policy, an
  allowlisted output contract, and explicit bounded limits.
- Produces: `WorkerThreadIdentity`, ordered `WorkerEvent` records,
  `WorkerResult`, normalized failure codes, and cleanup status.

- [ ] **Step 1: Write fake-adapter tests for the stable seam.** Define tests
  for `start_thread`, `resume_thread`, `fork_thread`,
  `run_bounded_turn`, `steer_turn`, `interrupt_turn`, `cancel_turn`, and
  `close_worker`. The fake must prove no real SDK import, auth, or model call is
  needed for the tests.
- [ ] **Step 2: Run the focused worker tests before implementation.**

  Run: `python -m pytest agent_lib/tests/test_codex_worker.py -q`

  Expected: FAIL because the future worker boundary does not yet exist.
- [ ] **Step 3: Implement the thinnest lazy SDK adapter.** Use the existing S1
  compatibility inspection as a prerequisite. Keep provider-specific method
  names inside the adapter. Reject missing/unsupported/malformed SDK state;
  never silently fall back to a broader permission or custom transport.
- [ ] **Step 4: Run focused worker tests and S1 compatibility tests.**

  Run: `python -m pytest agent_lib/tests/test_codex_worker.py agent_lib/tests/test_codex_sdk_compat.py -q`

  Expected: fake lifecycle tests pass; unavailable SDK states remain explicit
  failures or skips and do not invoke authentication/model APIs.
- [ ] **Step 5: Commit the adapter boundary.**

  Run: `git add agent_lib/codex_worker.py agent_lib/tests/test_codex_worker.py; git commit -m "feat: add bounded Codex worker seam"`

### Task 3: Implement bounded lifecycle and event safety

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Test: `agent_lib/tests/test_codex_worker_events.py`

**Interfaces:**
- Consumes: provider events from the official SDK, explicit limits, and the
  validated handoff/thread identity.
- Produces: redacted ordered events and one of the closed lifecycle outcomes:
  completed, interrupted, cancelled, timed out, partial, failed, or cleaned
  up with failure.

- [ ] **Step 1: Write event/failure tests.** Cover event ordering, duplicate
  and missing sequences, unknown event types, event/output byte limits, missing
  terminal events, malformed payloads, timeout, interrupt, cancellation,
  cleanup timeout, orphan-process detection, and provider error normalization.
- [ ] **Step 2: Run the event tests before implementation.**

  Run: `python -m pytest agent_lib/tests/test_codex_worker_events.py -q`

  Expected: FAIL for the unimplemented event and failure policy.
- [ ] **Step 3: Implement the bounded state machine.** Send only the official
  SDK lifecycle operations. On timeout/interrupt/cancel, stop accepting output,
  request official cleanup, enforce a second bounded cleanup budget, and mark
  partial evidence unusable. Preserve no raw secret-bearing payload.
- [ ] **Step 4: Run event and worker tests.**

  Run: `python -m pytest agent_lib/tests/test_codex_worker.py agent_lib/tests/test_codex_worker_events.py -q`

  Expected: all fake lifecycle, event, timeout, cancellation, and cleanup
  tests pass.
- [ ] **Step 5: Commit lifecycle safety.**

  Run: `git add agent_lib/codex_worker.py agent_lib/tests/test_codex_worker_events.py; git commit -m "feat: bound Codex worker lifecycle"`

### Task 4: Enforce workspace and protected-scope policy

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Modify: `cad_agent/vision_handoff.py`
- Test: `tests/test_vision_handoff_workspace.py`

**Interfaces:**
- Consumes: normalized workspace roots, source/accepted-base identities,
  protected constraints, operation allowlist, and disposable candidate root.
- Produces: a worker policy accepted only when canonical containment and
  read-only source/accepted roots are proven.

- [ ] **Step 1: Write workspace and scope tests.** Cover disposable writes,
  source/accepted-root refusal, path traversal, junction/reparse/symlink escape,
  existing artifact no-overwrite, forbidden operation classes, protected
  entity/datum/constraint targets, and missing root identity.
- [ ] **Step 2: Run the policy tests before implementation.**

  Run: `python -m pytest tests/test_vision_handoff_workspace.py -q`

  Expected: FAIL until root and protected-scope enforcement exists.
- [ ] **Step 3: Implement canonical containment and policy checks.** Keep all
  writes inside a disposable root; do not pass production or private roots to
  the SDK. Reject ambiguity rather than normalizing an unsafe path.
- [ ] **Step 4: Run the policy suite with the existing visual-contract suite.**

  Run: `python -m pytest tests/test_vision_handoff_workspace.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py -q`

  Expected: all safety and existing contract tests pass.
- [ ] **Step 5: Commit workspace policy.**

  Run: `git add agent_lib/codex_worker.py cad_agent/vision_handoff.py tests/test_vision_handoff_workspace.py; git commit -m "feat: enforce Codex workspace policy"`

### Task 5: Validate schema-bound drawing and repair plans

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Modify: `cad_agent/vision_handoff.py`
- Test: `tests/test_codex_worker_output.py`

**Interfaces:**
- Consumes: a completed worker result, the handoff's expected output contract,
  fresh evidence hashes, protected target set, and allowed operation classes.
- Produces: `ValidatedWorkerPlan` or a closed `INVALID_OUTPUT`/
  `SCHEMA_MISMATCH` result with no executor call.

- [ ] **Step 1: Write output tests.** Cover valid existing `repair-plan` output,
  unknown schema, extra key, missing field, malformed JSON, invalid operation,
  stale input, protected-target mutation, verdict/publication field, arbitrary
  path, and output emitted after timeout/partial events.
- [ ] **Step 2: Run the output tests before implementation.**

  Run: `python -m pytest tests/test_codex_worker_output.py -q`

  Expected: FAIL until output validation is wired to the worker result.
- [ ] **Step 3: Implement output validation.** Reuse the existing repair-plan
  and visual-contract validators. Do not add visual PASS or publication fields;
  do not create a second repair executor or verdict authority.
- [ ] **Step 4: Run focused output and authority tests.**

  Run: `python -m pytest tests/test_codex_worker_output.py tests/test_visual_supervisor_contracts.py tests/test_reuse_architecture_boundaries.py -q`

  Expected: valid plans are accepted only when all identity, scope, freshness,
  and protected-target gates pass.
- [ ] **Step 5: Commit output authority checks.**

  Run: `git add agent_lib/codex_worker.py cad_agent/vision_handoff.py tests/test_codex_worker_output.py; git commit -m "feat: validate Codex plan authority"`

### Task 6: Run the disposable compatibility matrix

**Files:**
- Create outside the repository: disposable SDK environment and candidate
  repository root.
- Reuse: `scripts/probe_codex_sdk_windows.py` and the official SDK/App Server/
  CLI version metadata.
- Test record: future implementation Issue evidence packet, not a production
  dependency file.

**Interfaces:**
- Consumes: exact Windows/Python host, candidate package/runtime revision, and
  fake/disposable fixtures.
- Produces: a matrix with exact versions/tags/commits, license, maintenance,
  platform, tests, security, dependency cost, benchmark, migration, rollback,
  and truthful `PASS`/`FAIL`/`SKIP`/`NOT RUN` values.

- [ ] **Step 1: Record historical S1 evidence separately.** Preserve
  `openai-codex==0.144.4` as compatibility evidence; do not infer that it is a
  permanent pin.
- [ ] **Step 2: Probe SDK-first capabilities in a disposable repository.**
  Prove clean start/close, thread start/resume/fork, bounded turn, structured
  output, events, steering if supported, interrupt, timeout, workspace-write
  containment, and cleanup. Do not use private or production inputs.
- [ ] **Step 3: Probe App Server only for a named SDK gap.** Record the exact
  JSON-RPC/generated-schema revision and prove the same safety properties. If
  no gap exists, mark App Server `NOT RUN`.
- [ ] **Step 4: Probe `codex exec --json` only as bounded fallback.** Record
  event completeness, schema output, sandbox, timeout/cancel, and cleanup. If
  not needed, mark it `NOT RUN`.
- [ ] **Step 5: Apply the pinning gate.** A production dependency change is
  rejected until the matrix, security review, benchmark, migration, rollback,
  focused tests, hosted checks, and PO approval are all present.

### Task 7: Verify the synthetic first slice and hand off for PO review

**Files:**
- Modify only the exact future implementation allowlist approved by the new
  Issue.
- Do not modify: `docs/STATUS.md`, `docs/HANDOFF.md`, source/accepted CAD,
  private fixtures, or Wave 1B/Wave 1C paths.

**Interfaces:**
- Consumes: the validated handoff, fake/disposable worker, schema-bound output,
  evidence packet, and compatibility matrix.
- Produces: a draft PR evidence packet proving no real model, private data,
  AutoCAD mutation, source mutation, or publication occurred.

- [ ] **Step 1: Run focused tests.**

  Run: `python -m pytest agent_lib/tests/test_codex_sdk_compat.py agent_lib/tests/test_codex_worker.py agent_lib/tests/test_codex_worker_events.py tests/test_vision_handoff.py tests/test_vision_handoff_contract.py tests/test_vision_handoff_workspace.py tests/test_codex_worker_output.py -ra -p no:cacheprovider`

  Expected: all focused tests pass; unavailable SDK/App Server/CLI states are
  explicit and no real model gate is claimed.
- [ ] **Step 2: Run Reuse Declaration and architecture checks.**

  Run: `python scripts/check_reuse_declaration.py`

  Expected: no undeclared implementation or duplicate authority.
- [ ] **Step 3: Run the canonical verifier on a clean committed candidate.**

  Run: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`

  Expected: exit `0`; unavailable private/AutoCAD/model gates remain truthful
  `SKIP` or `NOT RUN`.
- [ ] **Step 4: Inspect final diff and exact base.**

  Run: `git diff --check; git diff --name-only d71d0c97e28e03cb430f05589c8381b4ede70e66...HEAD; git merge-base --is-ancestor d71d0c97e28e03cb430f05589c8381b4ede70e66 HEAD`

  Expected: only the separately approved future allowlist appears; base
  ancestry is exact; no Wave 1B/Wave 1C overlap exists.
- [ ] **Step 5: Open a draft PR and stop.** Include the exact base/head,
  focused results, canonical verifier, compatibility matrix, Reuse Declaration,
  no-runtime/no-AutoCAD evidence, migration/rollback, and truthful unavailable
  gates. Leave the PR open for PO review; do not mark ready or merge.

## Rollback

The future worker adapter is optional and fail-closed. Disablement removes its
selection/configuration and returns to the existing deterministic/advisory
path. Revert only the bounded future commits; existing manifests, checkpoints,
IR, DXF, AutoCAD, review, and publication behavior remain readable and
unchanged. No planning document in Issue #70 creates a dependency that must be
rolled back.
