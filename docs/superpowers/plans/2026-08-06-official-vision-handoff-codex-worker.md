# Official Vision Handoff and Codex Worker Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`
> only after a future implementation Issue separately authorizes this plan.
> Issue #70 itself is planning-only.

**Goal:** Build a closed, hash-bound ChatGPT-to-Codex handoff and an isolated,
fail-closed official SDK worker-control seam without granting Codex CAD truth,
approval, AutoCAD mutation, or publication authority.

**Architecture:** CAD Agent owns the handoff, server-observed hashes, scope,
approval, immutable output-schema snapshot, provider policy, instruction
sources, and local validation. The official Python SDK runs inside a sanitized
supervised worker subprocess with deny-all approval, `experimental_api=False`,
explicit sandboxing, and Windows process-tree cleanup. Codex returns only
redacted events and an untrusted schema-bound plan.

**Tech Stack:** Python 3.11 on Windows, existing `cad_agent` and `agent_lib`
APIs, JSON Schema, pytest, Ruff, PowerShell verifier, official OpenAI Codex
Python SDK first, direct App Server only for a proven SDK gap, and bounded
`codex exec --json` only for disposable compatibility fallback.

## Global Constraints

- Issue #70 planning base is `d71d0c97e28e03cb430f05589c8381b4ede70e66`.
- This planning PR changes exactly the two Issue #70 documents.
- Future runtime requires a new exact-base Issue and exact allowlist.
- `openai-codex==0.144.4` is historical evidence, not a production pin.
- Codex has no visual PASS, CAD truth, approval, AutoCAD mutation, repair
  application, scope expansion, or publication authority.
- Provider approval is explicitly deny-all; no auto-review or escalation.
- `experimental_api=False` is mandatory in first runtime/compatibility slices.
- Real compatibility work defaults to read-only and uses an allowlisted worker
  environment, isolated disposable `CODEX_HOME`, and controlled cwd.
- `Sandbox.full_access` and unsafe CLI/App Server surfaces are forbidden.
- Output schema ID/version alone is insufficient: exact canonical bytes,
  SHA-256, and validator version must be server-owned and immutable per run.
- First runtime slice uses fakes and disposable repositories; no real model,
  private data, AutoCAD, File IPC, source CAD, or accepted CAD.
- All provider output is untrusted until identity, scope, freshness, policy,
  instruction, immutable-schema, protected-target, terminal-event, and cleanup
  checks pass.

---

## Proposed future implementation file map

This map is a proposal, not authorization:

- Create `contracts/vision-handoff/vision-handoff.schema.json`.
- Create `cad_agent/vision_handoff.py`.
- Create `agent_lib/codex_worker.py`.
- Create `agent_lib/codex_worker_process.py`.
- Create focused tests under `agent_lib/tests/` and `tests/`.
- Modify `agent_lib/codex_sdk_compat.py` or
  `cad_agent/visual_contracts.py` only when a future Issue names exact lines and
  proves necessity.

No task may add a second transport, proposal/apply authority, evidence store,
executor, registry, publisher, or AutoCAD route.

---

### Task 1: Freeze the closed handoff and immutable output-schema contract

**Files:**
- Create: `contracts/vision-handoff/vision-handoff.schema.json`
- Create: `cad_agent/vision_handoff.py`
- Test: `tests/test_vision_handoff.py`
- Test: `tests/test_vision_handoff_contract.py`
- Test: `tests/test_vision_handoff_schema_binding.py`

**Interfaces:**
- Consumes: PO-approved intent/scope/evidence references; existing manifest,
  visual-evidence, IR, drawing, approval, and allowlisted contract identities.
- Produces: `ValidatedVisionHandoff` with canonical handoff bytes/hash,
  normalized scope, protected constraints, provider policy, instruction-source
  identity, expiry/single-use state, and immutable schema snapshot metadata.

- [ ] **Step 1: Write failing closed-contract tests.** Cover required identity,
  scope, protected constraints, allowed/forbidden operations, provider policy,
  approval, expiry, single-use, instruction sources, and these server-owned
  fields:

  ```text
  output_schema_id
  output_schema_version
  output_schema_sha256
  output_validator_version
  ```

- [ ] **Step 2: Write failing schema-integrity tests.** Cover same ID/version
  with changed bytes, schema-path replacement, symlink/reparse replacement,
  changed canonicalization, validator-version drift, and TOCTOU mutation
  between provider invocation and local validation.
- [ ] **Step 3: Run tests and confirm failure.**

  ```powershell
  python -m pytest tests/test_vision_handoff.py tests/test_vision_handoff_contract.py tests/test_vision_handoff_schema_binding.py -q
  ```

- [ ] **Step 4: Implement the smallest validator and snapshot builder.** Reuse
  `cad_agent.visual_contracts`, `cad_agent.manifest`, and
  `cad_agent.visual_evidence`. Resolve the allowlisted schema once, canonicalize
  exact bytes, hash them, bind the validator version, and persist an immutable
  run-scoped snapshot. Do not claim or create an unverified
  `cad_agent.checkpoint` owner.
- [ ] **Step 5: Run focused tests.** Expected: all pass; no safety skip.
- [ ] **Step 6: Commit.**

  ```powershell
  git add contracts/vision-handoff/vision-handoff.schema.json cad_agent/vision_handoff.py tests/test_vision_handoff.py tests/test_vision_handoff_contract.py tests/test_vision_handoff_schema_binding.py
  git commit -m "feat: add closed vision handoff and schema binding"
  ```

### Task 2: Bind provider threads to server-owned handoff and schema identity

**Files:**
- Modify: `cad_agent/vision_handoff.py`
- Test: `tests/test_vision_handoff_thread_binding.py`

**Interfaces:**
- Consumes: handoff, provider thread ID, adapter/model/config identity,
  instruction-source identity, sandbox policy, schema hash, and validator
  version.
- Produces: `BoundWorkerThread` that rejects foreign, stale, caller-selected,
  or silently widened history.

- [ ] **Step 1: Write failing tests.** Cover start/resume/fork; thread ID without
  server binding; stale handoff; foreign run; changed model/config,
  instructions, sandbox/cwd, schema bytes/hash, or validator; inherited
  approval; fork without fresh approval.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement binding across:**

  ```text
  handoff_id + handoff_hash + run_id + thread_id + adapter_version
  + model/config identity + instruction-source identity + sandbox policy
  + output_schema_sha256 + output_validator_version
  ```

- [ ] **Step 4: Run contract/binding tests.** Expected: all pass.
- [ ] **Step 5: Commit.**

  ```powershell
  git add cad_agent/vision_handoff.py tests/test_vision_handoff_thread_binding.py
  git commit -m "feat: bind Codex threads to approved handoffs"
  ```

### Task 3: Build the sanitized worker process boundary

**Files:**
- Create: `agent_lib/codex_worker_process.py`
- Test: `agent_lib/tests/test_codex_worker_process.py`

**Interfaces:**
- Consumes: environment allowlist, disposable `CODEX_HOME`, controlled cwd,
  runtime path, process limits, and cleanup deadline.
- Produces: `WorkerProcessHandle`, environment attestation, process-tree
  identity, and `WorkerCleanupResult`.

- [ ] **Step 1: Write failing environment tests.** Cover inherited API keys,
  tokens, proxy/telemetry/MCP variables, uncontrolled cwd, non-disposable
  `CODEX_HOME`, unrelated writable roots, and secret leakage.
- [ ] **Step 2: Write failing Windows process-tree tests.** Spawn disposable
  child/grandchild fixtures and reject cleanup while any descendant survives.
- [ ] **Step 3: Run and confirm failure.**
- [ ] **Step 4: Implement allowlisted environment and a Windows Job Object or
  equivalent tested supervisor.** The SDK runs inside this sanitized process,
  so its internal environment copy cannot inherit the user session.
- [ ] **Step 5: Run tests.** Expected: isolation and cleanup pass.
- [ ] **Step 6: Commit.**

  ```powershell
  git add agent_lib/codex_worker_process.py agent_lib/tests/test_codex_worker_process.py
  git commit -m "feat: isolate and supervise Codex worker process"
  ```

### Task 4: Add the provider-independent official SDK worker seam

**Files:**
- Create: `agent_lib/codex_worker.py`
- Test: `agent_lib/tests/test_codex_worker.py`
- Reuse without behavior change: `agent_lib/codex_sdk_compat.py`

**Interfaces:**
- Consumes: `ValidatedVisionHandoff`, `BoundWorkerThread`, sanitized process,
  immutable schema bytes/hash, explicit limits, and sandbox.
- Produces: normalized thread/turn IDs, events, candidate output, failure code,
  and cleanup status.

- [ ] **Step 1: Write fake-adapter tests** for start/resume/fork, bounded turn,
  steer, interrupt, normalized local cancel, and close. No SDK import, auth, or
  real model call.
- [ ] **Step 2: Add policy tests** requiring on every lifecycle call:
  `ApprovalMode.deny_all`, `experimental_api=False`, explicit cwd/sandbox,
  isolated environment, exact instruction identity, no inherited writable
  roots, and exact immutable schema snapshot.
- [ ] **Step 3: Run and confirm failure.**
- [ ] **Step 4: Implement the thinnest lazy SDK adapter.** Never silently choose
  App Server, CLI, broader permissions, auto-review, experimental API, or a
  mutable schema path.
- [ ] **Step 5: Implement local cancellation:**

  ```text
  mark CANCELLED -> official interrupt -> reject all output -> bounded cleanup
  ```

- [ ] **Step 6: Run worker and S1 tests.**
- [ ] **Step 7: Commit.**

  ```powershell
  git add agent_lib/codex_worker.py agent_lib/tests/test_codex_worker.py
  git commit -m "feat: add bounded official Codex worker seam"
  ```

### Task 5: Attest instructions and effective provider policy

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Modify: `cad_agent/vision_handoff.py`
- Test: `tests/test_codex_worker_instruction_policy.py`

- [ ] **Step 1: Write failing tests.** Cover unexpected user/project
  instructions, rules, MCP/global config, changed instruction hashes,
  inherited writable roots, model/config drift, and resume/fork policy drift.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement exact source-list/hash and policy re-attestation.** If
  the SDK cannot expose sufficient evidence, return a named SDK gap and stop;
  do not authorize App Server automatically.
- [ ] **Step 4: Run tests.** Expected: all drift fails closed.
- [ ] **Step 5: Commit.**

### Task 6: Bound lifecycle, events, timeout, local cancel, and cleanup

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Modify: `agent_lib/codex_worker_process.py`
- Test: `agent_lib/tests/test_codex_worker_events.py`

- [ ] **Step 1: Write failing tests.** Cover ordering, duplicate/gap, unknown
  event, malformed payload, byte/count limits, missing terminal event, timeout,
  interrupt, local cancel, cleanup timeout, provider failure, and late output.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement fail-closed state machine and redaction.** Partial or
  terminal-failure output is unusable. Exclude raw reasoning, prompts, private
  bytes, paths, tokens, credentials, and secret command output.
- [ ] **Step 4: Require process-tree verification after SDK close.** Surviving
  descendants yield `CLEANUP_FAILED`.
- [ ] **Step 5: Run tests and commit.**

### Task 7: Enforce workspace and sandbox policy

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Modify: `cad_agent/vision_handoff.py`
- Test: `tests/test_vision_handoff_workspace.py`

- [ ] **Step 1: Write failing tests.** Cover explicit sandbox on every call,
  full-access rejection, read-only default, disposable-only workspace-write,
  inherited roots, source/accepted access, traversal, reparse/symlink escape,
  existing artifact/schema overwrite, and protected-target mutation.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement canonical containment plus effective-policy checks.**
  CAD Agent path validation alone is insufficient.
- [ ] **Step 4: Run workspace and visual-contract tests, then commit.**

### Task 8: Validate output against the exact immutable schema snapshot

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Modify: `cad_agent/vision_handoff.py`
- Test: `tests/test_codex_worker_output.py`
- Test: `tests/test_codex_worker_schema_toctou.py`

**Interfaces:**
- Consumes: completed worker result, immutable schema bytes/hash, validator
  version, bound identities, protected targets, provider policy, and cleanup.
- Produces: `ValidatedWorkerPlan` or a closed failure with no executor call.

- [ ] **Step 1: Write failing output tests.** Cover valid repair plan, unknown
  schema, extra/missing key, invalid JSON/operation, stale input, protected
  target, arbitrary path, verdict/publication field, partial-event output, and
  cleanup failure.
- [ ] **Step 2: Write failing schema TOCTOU tests.** Cover same ID/version with
  changed bytes, schema registry/path replacement, changed canonical hash,
  changed validator version, snapshot mutation, and provider/local validation
  using different bytes.
- [ ] **Step 3: Run and confirm failure.**
- [ ] **Step 4: Implement exact-snapshot flow.** CAD Agent snapshots canonical
  bytes before the turn, passes those exact bytes to SDK/App Server/CLI, and
  locally validates against the same immutable snapshot and validator.
  Any byte/hash/path/validator drift returns `SCHEMA_MISMATCH`.
- [ ] **Step 5: Run output/authority/TOCTOU tests.** Expected: all pass.
- [ ] **Step 6: Commit.**

  ```powershell
  git add agent_lib/codex_worker.py cad_agent/vision_handoff.py tests/test_codex_worker_output.py tests/test_codex_worker_schema_toctou.py
  git commit -m "feat: validate Codex output against immutable schema"
  ```

### Task 9: Run the disposable SDK compatibility/security matrix

**Files:**
- Create outside repository: disposable Python environment, `CODEX_HOME`,
  candidate repository, and immutable schema snapshot.
- Reuse: `scripts/probe_codex_sdk_windows.py`.

- [ ] **Step 1: Record exact Windows/Python/package/runtime/tag/schema/validator
  identities, account mode, and license.**
- [ ] **Step 2: Prove sanitized startup/shutdown** with deny-all approval,
  `experimental_api=False`, controlled cwd, isolated `CODEX_HOME`, no inherited
  MCP/writable roots, immutable output schema, and process-tree cleanup.
- [ ] **Step 3: Prove ephemeral lifecycle** for start/resume/fork, output,
  streaming, steer if supported, interrupt, local cancel, timeout, policy and
  schema re-attestation, and repeatability. No private or production input.
- [ ] **Step 4: Record unsupported capabilities honestly.** Missing effective
  policy or schema evidence is a named SDK gap, not PASS.
- [ ] **Step 5: Apply dependency gate.** No pin until security, benchmark,
  migration, rollback, focused tests, hosted checks, and PO approval exist.

### Task 10: Gate App Server and CLI fallback separately

**Files:**
- No repository change without a separate exact Issue.

- [ ] **Step 1: Keep App Server `NOT RUN` unless Task 9 records a named SDK
  gap.** If approved, use local disposable stdio only and forbid remote,
  WebSocket/unix listeners, direct commands/process/MCP, full access, remote
  code mode, and unrelated experimental APIs.
- [ ] **Step 2: Keep CLI fallback `NOT RUN` unless explicitly required.** If
  approved, require:

  ```text
  --ephemeral
  --ignore-user-config
  --strict-config
  explicit read-only sandbox
  exact --output-schema pointing to the immutable run snapshot
  ```

  Forbid bypass flags, ignored rules, skipped git checks, `--last`, and
  arbitrary sessions. Treat timeout/cancel as process-level only.

### Task 11: Add telemetry/privacy evidence gate

- [ ] **Step 1: Record account mode, client identity, telemetry/compliance
  configuration, data class, transmission assumptions, and retention/access
  assumptions.**
- [ ] **Step 2: Test local evidence redaction independently from upstream
  service behavior.**
- [ ] **Step 3: Keep private data `NOT RUN` until Master PO acceptance.**

### Task 12: Verify the synthetic first slice and hand off

- [ ] **Step 1: Run focused suites.**

  ```powershell
  python -m pytest agent_lib/tests/test_codex_sdk_compat.py agent_lib/tests/test_codex_worker.py agent_lib/tests/test_codex_worker_process.py agent_lib/tests/test_codex_worker_events.py tests/test_vision_handoff.py tests/test_vision_handoff_contract.py tests/test_vision_handoff_schema_binding.py tests/test_vision_handoff_thread_binding.py tests/test_codex_worker_instruction_policy.py tests/test_vision_handoff_workspace.py tests/test_codex_worker_output.py tests/test_codex_worker_schema_toctou.py -ra -p no:cacheprovider
  ```

- [ ] **Step 2: Run Reuse Declaration using fail-closed exact-base input.**

  ```powershell
  $wave1aBase = $env:WAVE1A_EXACT_BASE
  if ([string]::IsNullOrWhiteSpace($wave1aBase)) {
    throw "WAVE1A_EXACT_BASE must equal the exact base authorized by the future runtime Issue."
  }
  $wave1aPrNumber = (gh pr view --json number --jq .number).Trim()
  $wave1aTemp = Join-Path $env:TEMP "cad-agent-wave1a-reuse-check"
  New-Item -ItemType Directory -Path $wave1aTemp -Force | Out-Null
  $wave1aBodyFile = Join-Path $wave1aTemp "final-pr-body.md"
  $wave1aChangedFiles = Join-Path $wave1aTemp "changed-files.txt"
  gh pr view $wave1aPrNumber --json body --jq .body | Set-Content -LiteralPath $wave1aBodyFile -Encoding utf8
  git diff --name-only "$wave1aBase...HEAD" | Set-Content -LiteralPath $wave1aChangedFiles -Encoding utf8
  python scripts/check_reuse_declaration.py --body-file $wave1aBodyFile --changed-files $wave1aChangedFiles
  if ($LASTEXITCODE -ne 0) { throw "Reuse Declaration failed." }
  Remove-Item -LiteralPath $wave1aTemp -Recurse -Force
  ```

- [ ] **Step 3: Run canonical verifier and exact diff audit.**

  ```powershell
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
  git diff --check
  git diff --name-only "$wave1aBase...HEAD"
  git merge-base --is-ancestor $wave1aBase HEAD
  git status --short
  ```

- [ ] **Step 4: Open a draft PR and stop.** Include exact base/head, tests,
  compatibility/security matrix, immutable-schema evidence, process-tree and
  telemetry gates, migration/rollback, truthful external gate states, and
  proof of zero AutoCAD/source/accepted/private/publication mutation.

## Current Issue #70 planning verification

Run on the final planning head:

```powershell
python -m pytest tests/test_documentation_contract.py tests/test_reuse_rebaseline_docs.py tests/test_reuse_declaration.py -q -p no:cacheprovider
git diff --check d71d0c97e28e03cb430f05589c8381b4ede70e66...HEAD
git diff --name-only d71d0c97e28e03cb430f05589c8381b4ede70e66...HEAD
```

Expected changed paths:

```text
docs/superpowers/specs/2026-08-06-official-vision-handoff-codex-worker-design.md
docs/superpowers/plans/2026-08-06-official-vision-handoff-codex-worker.md
```

Then require hosted `tests` and `reuse-declaration` on the final exact head.
AutoCAD, hosted AutoCAD .NET, real model, private data, and publication remain
`NOT RUN`.

## Rollback

The future adapter is optional and fail-closed. Disable/remove its selection
and revert only bounded commits. Existing manifests, evidence, IR, DXF,
AutoCAD, review, and publication behavior remain readable and unchanged. No
provider thread, authentication, or output is required to recover project
truth.
