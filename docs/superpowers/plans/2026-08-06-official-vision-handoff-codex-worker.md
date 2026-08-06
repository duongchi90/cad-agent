# Official Vision Handoff and Codex Worker Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`
> only after a future implementation Issue separately authorizes this plan.
> Issue #70 itself is planning-only.

**Goal:** Build a closed, hash-bound ChatGPT-to-Codex handoff and an isolated,
fail-closed official SDK worker-control seam without granting Codex CAD truth,
approval, AutoCAD mutation, or publication authority.

**Architecture:** CAD Agent creates and validates a versioned
`vision-handoff`, binds it to server-observed hashes, scope, approvals,
instruction sources, provider policy, and a disposable workspace, then calls a
thin provider-independent interface. The official Python SDK runs inside a
sanitized supervised worker subprocess with deny-all approvals,
`experimental_api=False`, explicit sandboxing, and Windows process-tree
cleanup. Codex returns only redacted events and an untrusted schema-bound plan.

**Tech Stack:** Python 3.11 on Windows, existing `cad_agent` and `agent_lib`
APIs, JSON Schema, pytest, Ruff, PowerShell verifier, official OpenAI Codex
Python SDK first, direct App Server only for a proven SDK gap, and bounded
`codex exec --json` only for disposable compatibility fallback.

## Global Constraints

- Issue #70 planning base is `d71d0c97e28e03cb430f05589c8381b4ede70e66`.
- This planning PR changes exactly the two Issue #70 documents.
- Future runtime begins only through a new exact-base Issue and allowlist.
- `openai-codex==0.144.4` is historical evidence, not a production pin.
- Codex has no visual PASS, CAD truth, approval, AutoCAD mutation, repair
  application, or publication authority.
- Provider approval is explicitly deny-all; no auto-review or escalation.
- `experimental_api=False` is mandatory in first runtime/compatibility slices.
- Real compatibility work defaults to read-only and uses a sanitized worker
  environment with isolated disposable `CODEX_HOME` and controlled cwd.
- `Sandbox.full_access` and unsafe CLI/App Server surfaces are forbidden.
- First runtime slice uses fakes and disposable repositories; no real model,
  private data, AutoCAD, File IPC, source CAD, or accepted CAD.
- All provider output is untrusted until strict identity, scope, freshness,
  policy, instruction, schema, protected-target, terminal-event, and cleanup
  checks pass.
- Every task ends in a bounded commit and fresh verification.

---

## Proposed future implementation file map

The following is a proposal for a later runtime Issue, not authorization:

- Create `contracts/vision-handoff/vision-handoff.schema.json` — closed handoff
  contract.
- Create `cad_agent/vision_handoff.py` — canonical identity, policy, freshness,
  thread binding, and output validation coordination.
- Create `agent_lib/codex_worker.py` — provider-independent worker seam and
  normalized results/failures.
- Create `agent_lib/codex_worker_process.py` — sanitized subprocess,
  `CODEX_HOME`, environment, and Windows process-tree supervision.
- Create focused tests under `agent_lib/tests/` and `tests/`.
- Modify `agent_lib/codex_sdk_compat.py` or
  `cad_agent/visual_contracts.py` only if the future Issue names exact lines and
  proves reuse necessity.

No future task may silently add a transport, executor, manifest store,
registry, publisher, or AutoCAD route.

---

### Task 1: Freeze the closed vision-handoff contract

**Files:**
- Create: `contracts/vision-handoff/vision-handoff.schema.json`
- Create: `cad_agent/vision_handoff.py`
- Test: `tests/test_vision_handoff.py`
- Test: `tests/test_vision_handoff_contract.py`

**Interfaces:**
- Consumes: PO-approved intent/scope/evidence references and existing manifest,
  visual-evidence, IR, drawing, and approval identities.
- Produces: `ValidatedVisionHandoff` containing canonical bytes/hash,
  normalized scope, protected constraints, effective provider policy,
  instruction-source identity, expiry/single-use status, and immutable input
  identities.

- [ ] **Step 1: Write failing closed-contract tests.** Cover required identity,
  scope, protected constraints, allowed/forbidden operations, provider policy,
  expected output contract, approval, expiry, single-use, and instruction
  source fields. Assert rejection of extra keys, missing fields, malformed
  SHA-256, non-finite values, conflicting identities, unknown enums, and
  caller-supplied authority fields.
- [ ] **Step 2: Run the tests and confirm failure.**

  ```powershell
  python -m pytest tests/test_vision_handoff.py tests/test_vision_handoff_contract.py -q
  ```

  Expected: FAIL because the contract and validator do not exist.
- [ ] **Step 3: Implement the smallest validator and canonical hasher.** Reuse
  `cad_agent.visual_contracts`, `cad_agent.manifest`, and
  `cad_agent.visual_evidence`. Do not claim or create an unverified
  `cad_agent.checkpoint` owner.
- [ ] **Step 4: Run the focused tests.** Expected: all pass with no skipped
  safety cases.
- [ ] **Step 5: Commit.**

  ```powershell
  git add contracts/vision-handoff/vision-handoff.schema.json cad_agent/vision_handoff.py tests/test_vision_handoff.py tests/test_vision_handoff_contract.py
  git commit -m "feat: add closed vision handoff contract"
  ```

### Task 2: Add server-owned thread and policy binding

**Files:**
- Modify: `cad_agent/vision_handoff.py`
- Test: `tests/test_vision_handoff_thread_binding.py`

**Interfaces:**
- Consumes: validated handoff, provider thread ID, adapter/model/config identity,
  instruction-source identity, cwd, and sandbox policy.
- Produces: `BoundWorkerThread` whose identity binds all authority fields and
  rejects foreign, stale, caller-selected, or silently widened history.

- [ ] **Step 1: Write failing binding tests.** Cover start, resume, and fork;
  caller-supplied thread ID without binding; stale handoff; foreign run;
  changed model/config; changed instruction sources; changed sandbox/cwd;
  inherited approval; and fork without fresh approval.
- [ ] **Step 2: Run tests and confirm failure.**

  ```powershell
  python -m pytest tests/test_vision_handoff_thread_binding.py -q
  ```
- [ ] **Step 3: Implement the binding:**

  ```text
  handoff_id + handoff_hash + run_id + thread_id + adapter_version
  + model/config identity + instruction-source identity + sandbox policy
  ```

  Resume/fork must revalidate all fields. Fork creates a new handoff and
  approval. First real probes remain ephemeral.
- [ ] **Step 4: Run contract and binding tests.** Expected: all pass.
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
- Consumes: allowlisted environment keys, disposable `CODEX_HOME`, controlled
  cwd, exact runtime path, process limits, and cleanup deadline.
- Produces: `WorkerProcessHandle`, effective-environment attestation, process
  tree identity, and `WorkerCleanupResult`.

- [ ] **Step 1: Write failing process-isolation tests.** Cover inherited API
  keys/tokens/proxy/telemetry/MCP variables, uncontrolled cwd, non-disposable
  `CODEX_HOME`, unrelated writable roots, reparse/symlink escape, and secret
  leakage into evidence.
- [ ] **Step 2: Write failing Windows process-tree tests.** Spawn a disposable
  child/grandchild fixture and prove cleanup fails while any descendant
  survives.
- [ ] **Step 3: Run tests and confirm failure.**

  ```powershell
  python -m pytest agent_lib/tests/test_codex_worker_process.py -q
  ```
- [ ] **Step 4: Implement an allowlisted subprocess environment.** The SDK runs
  inside this supervised process so its internal `os.environ.copy()` sees only
  the sanitized environment. Use a fresh disposable `CODEX_HOME`, controlled
  cwd, no unrelated credentials, and a Windows Job Object or equivalent tested
  process-tree supervisor.
- [ ] **Step 5: Implement bounded cleanup.** SDK close/terminate is followed by
  process-tree verification. Any surviving descendant yields
  `CLEANUP_FAILED`.
- [ ] **Step 6: Run tests.** Expected: all process isolation and cleanup tests
  pass.
- [ ] **Step 7: Commit.**

  ```powershell
  git add agent_lib/codex_worker_process.py agent_lib/tests/test_codex_worker_process.py
  git commit -m "feat: isolate and supervise Codex worker process"
  ```

### Task 4: Add the provider-independent SDK worker seam

**Files:**
- Create: `agent_lib/codex_worker.py`
- Test: `agent_lib/tests/test_codex_worker.py`
- Reuse without behavior change: `agent_lib/codex_sdk_compat.py`

**Interfaces:**
- Consumes: `ValidatedVisionHandoff`, `BoundWorkerThread`, sanitized process
  handle, explicit limits, sandbox, and output contract.
- Produces: normalized thread/turn identities, events, candidate output,
  failure code, and cleanup status.

- [ ] **Step 1: Write fake-adapter tests** for `start_thread`, `resume_thread`,
  `fork_thread`, `run_bounded_turn`, `steer_turn`, `interrupt_turn`, normalized
  `cancel_turn`, and `close_worker`. No SDK import, auth, or real model call is
  permitted in these tests.
- [ ] **Step 2: Add policy tests** requiring on every start/resume/fork/turn:
  - `ApprovalMode.deny_all`;
  - `experimental_api=False`;
  - explicit cwd and sandbox;
  - isolated `CODEX_HOME` and environment attestation;
  - exact instruction-source identity;
  - no inherited writable roots.
- [ ] **Step 3: Run tests and confirm failure.**

  ```powershell
  python -m pytest agent_lib/tests/test_codex_worker.py -q
  ```
- [ ] **Step 4: Implement the thinnest lazy SDK adapter.** Keep all provider
  names inside the adapter. Reject unavailable, unsupported, malformed, or
  policy-mismatched SDK state. Never silently choose App Server, CLI, broader
  permissions, auto-review, or experimental API.
- [ ] **Step 5: Implement local cancellation semantics.**

  ```text
  mark CANCELLED -> official interrupt -> reject all output -> bounded cleanup
  ```

  Do not claim a distinct official provider cancel primitive.
- [ ] **Step 6: Run worker and S1 tests.**

  ```powershell
  python -m pytest agent_lib/tests/test_codex_worker.py agent_lib/tests/test_codex_sdk_compat.py -q
  ```
- [ ] **Step 7: Commit.**

  ```powershell
  git add agent_lib/codex_worker.py agent_lib/tests/test_codex_worker.py
  git commit -m "feat: add bounded official Codex worker seam"
  ```

### Task 5: Enforce instruction-source and effective-policy attestation

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Modify: `cad_agent/vision_handoff.py`
- Test: `tests/test_codex_worker_instruction_policy.py`

**Interfaces:**
- Consumes: expected global/project instruction files, hashes, model/config,
  approval, cwd, and sandbox.
- Produces: `EffectiveWorkerPolicy` or a closed
  `INSTRUCTION_SOURCE_MISMATCH`/`PROVIDER_POLICY_MISMATCH` failure.

- [ ] **Step 1: Write failing tests.** Cover unexpected user/project
  `AGENTS.md`, rules, MCP configuration, global config, changed instruction
  hash, inherited writable roots, changed model/config, and resume/fork policy
  drift.
- [ ] **Step 2: Run tests and confirm failure.**
- [ ] **Step 3: Implement exact source-list/hash attestation and policy
  re-attestation** after resume/fork and before each turn. If the exact SDK
  version cannot expose sufficient effective evidence, return a named SDK gap
  and stop; do not authorize App Server automatically.
- [ ] **Step 4: Run tests.** Expected: all policy-drift cases fail closed.
- [ ] **Step 5: Commit.**

  ```powershell
  git add agent_lib/codex_worker.py cad_agent/vision_handoff.py tests/test_codex_worker_instruction_policy.py
  git commit -m "feat: attest Codex instruction and provider policy"
  ```

### Task 6: Bound lifecycle, events, timeout, and cleanup

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Modify: `agent_lib/codex_worker_process.py`
- Test: `agent_lib/tests/test_codex_worker_events.py`

**Interfaces:**
- Consumes: provider events, explicit resource limits, bound thread identity,
  and process supervisor.
- Produces: ordered redacted events and a closed terminal outcome.

- [ ] **Step 1: Write failing event tests.** Cover ordering, duplicate/gap,
  unknown event, malformed payload, event/output byte limits, missing terminal
  event, timeout, interrupt, local cancel, cleanup timeout, provider failure,
  and output arriving after a terminal failure.
- [ ] **Step 2: Run tests and confirm failure.**
- [ ] **Step 3: Implement the state machine.** Partial events and any output
  after timeout/interrupt/cancel are unusable. Cleanup has a second bounded
  budget and process-tree verification.
- [ ] **Step 4: Implement redaction.** Exclude raw reasoning, prompts, private
  source bytes, customer paths, tokens, credentials, and secret-bearing
  command output.
- [ ] **Step 5: Run worker/event/process tests.** Expected: all pass.
- [ ] **Step 6: Commit.**

  ```powershell
  git add agent_lib/codex_worker.py agent_lib/codex_worker_process.py agent_lib/tests/test_codex_worker_events.py
  git commit -m "feat: bound Codex lifecycle and event evidence"
  ```

### Task 7: Enforce workspace and sandbox policy

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Modify: `cad_agent/vision_handoff.py`
- Test: `tests/test_vision_handoff_workspace.py`

**Interfaces:**
- Consumes: normalized roots, immutable source/accepted identities, disposable
  candidate root, protected targets, and operation allowlist.
- Produces: a policy accepted only when exact containment and effective sandbox
  are proven.

- [ ] **Step 1: Write failing tests.** Cover read-only default, explicit sandbox
  on every lifecycle operation, complete rejection of `Sandbox.full_access`,
  workspace-write only in an empty disposable root, inherited writable roots,
  source/accepted-root access, traversal, junction/reparse/symlink escape,
  existing-artifact overwrite, and protected-target mutation.
- [ ] **Step 2: Run tests and confirm failure.**
- [ ] **Step 3: Implement canonical containment plus provider effective-policy
  checks.** CAD Agent path validation alone is not sufficient.
- [ ] **Step 4: Run workspace and existing visual-contract tests.**
- [ ] **Step 5: Commit.**

  ```powershell
  git add agent_lib/codex_worker.py cad_agent/vision_handoff.py tests/test_vision_handoff_workspace.py
  git commit -m "feat: enforce Codex sandbox and workspace policy"
  ```

### Task 8: Validate schema-bound drawing and repair plans

**Files:**
- Modify: `agent_lib/codex_worker.py`
- Modify: `cad_agent/vision_handoff.py`
- Test: `tests/test_codex_worker_output.py`

**Interfaces:**
- Consumes: completed worker result, expected contract, bound identities,
  protected targets, provider policy, and cleanup result.
- Produces: `ValidatedWorkerPlan` or a closed failure with no executor call.

- [ ] **Step 1: Write failing tests.** Cover valid repair plan, unknown schema,
  extra/missing key, malformed JSON, invalid operation, stale input,
  instruction/provider-policy drift, protected-target mutation, arbitrary path,
  verdict/publication field, output after partial events, and cleanup failure.
- [ ] **Step 2: Run tests and confirm failure.**
- [ ] **Step 3: Implement output validation** by reusing existing repair-plan
  and visual-contract validators. Do not add a second executor or verdict.
- [ ] **Step 4: Run focused output/authority tests.** Expected: valid plans are
  accepted only when every identity and policy gate passes.
- [ ] **Step 5: Commit.**

  ```powershell
  git add agent_lib/codex_worker.py cad_agent/vision_handoff.py tests/test_codex_worker_output.py
  git commit -m "feat: validate Codex plan authority"
  ```

### Task 9: Run the disposable SDK compatibility/security matrix

**Files:**
- Create outside repository: disposable Python environment, `CODEX_HOME`, and
  candidate repository.
- Reuse: `scripts/probe_codex_sdk_windows.py`.
- Evidence: future Issue/PR packet, not a dependency file.

- [ ] **Step 1: Record exact environment.** Include Windows build, Python,
  package/wheel hashes, CLI runtime, OpenAI tag/commit, generated schemas,
  account mode, and license.
- [ ] **Step 2: Prove sanitized startup and shutdown** with deny-all approval,
  `experimental_api=False`, controlled cwd, isolated `CODEX_HOME`, allowlisted
  environment, no inherited MCP/writable roots, and Windows process-tree
  cleanup.
- [ ] **Step 3: Prove lifecycle in an ephemeral disposable repository.** Test
  start/resume/fork, structured output, streaming, steer if supported,
  interrupt, normalized local cancel, timeout, policy re-attestation, and
  repeatability. No private or production input.
- [ ] **Step 4: Record unsupported capabilities honestly.** A missing
  instruction/effective-policy evidence surface is a named SDK gap, not PASS.
- [ ] **Step 5: Apply the dependency gate.** No production pin until security,
  benchmark, migration, rollback, focused tests, hosted checks, and PO approval
  are present.

### Task 10: Gate App Server and CLI fallback separately

**Files:**
- No repository change unless a separate exact Issue authorizes it.

- [ ] **Step 1: Keep direct App Server `NOT RUN`** unless Task 9 records a named
  SDK gap.
- [ ] **Step 2: When separately approved, use local disposable stdio only.**
  Forbid remote/WebSocket/unix listeners, direct commands, process spawning,
  MCP invocation, full access, remote code-mode hosts, and unrelated
  experimental APIs. Bind generated schemas to the tested runtime.
- [ ] **Step 3: Keep CLI fallback `NOT RUN`** unless explicitly required.
- [ ] **Step 4: When separately approved, require:**

  ```text
  --ephemeral
  --ignore-user-config
  --strict-config
  explicit read-only sandbox
  exact --output-schema
  ```

  Forbid bypass flags, ignored rules, skipped git checks, `--last`, and
  arbitrary sessions. Treat timeout/cancel as process-level only and redact
  JSONL aggressively.

### Task 11: Add telemetry/privacy evidence gate

**Files:**
- Test/evidence paths only when separately authorized.

- [ ] **Step 1: Record account mode, client identity, telemetry/compliance
  configuration, data class, transmission assumptions, and retention/access
  assumptions.**
- [ ] **Step 2: Test local evidence redaction independently** from upstream
  service behavior.
- [ ] **Step 3: Keep private data `NOT RUN`** until Master PO accepts this gate.

### Task 12: Verify the synthetic first slice and hand off

**Files:**
- Modify only the future runtime allowlist approved by its new Issue.
- Never modify `STATUS.md`, `HANDOFF.md`, source/accepted CAD, AutoCAD/File IPC,
  Wave 1B, or Wave 1C paths.

- [ ] **Step 1: Run focused suites.**

  ```powershell
  python -m pytest agent_lib/tests/test_codex_sdk_compat.py agent_lib/tests/test_codex_worker.py agent_lib/tests/test_codex_worker_process.py agent_lib/tests/test_codex_worker_events.py tests/test_vision_handoff.py tests/test_vision_handoff_contract.py tests/test_vision_handoff_thread_binding.py tests/test_codex_worker_instruction_policy.py tests/test_vision_handoff_workspace.py tests/test_codex_worker_output.py -ra -p no:cacheprovider
  ```

  Expected: all authorized synthetic tests pass; unavailable external gates are
  explicit; no real model or AutoCAD result is claimed.
- [ ] **Step 2: Run Reuse Declaration using real inputs.**

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
- [ ] **Step 3: Run canonical verifier.**

  ```powershell
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
  ```

- [ ] **Step 4: Audit exact base, allowlist, and clean worktree.**

  ```powershell
  git diff --check
  git diff --name-only "$wave1aBase...HEAD"
  git merge-base --is-ancestor $wave1aBase HEAD
  git status --short
  ```
- [ ] **Step 5: Open a draft PR and stop.** Include exact base/head, tests,
  compatibility/security matrix, process-tree evidence, telemetry gate,
  migration/rollback, truthful `PASS`/`FAIL`/`SKIP`/`NOT RUN`, and explicit
  proof that no AutoCAD, source, accepted, private-data, or publication
  mutation occurred.

## Current Issue #70 planning verification

For this docs-only planning PR, run:

```powershell
python -m pytest tests/test_documentation_contract.py tests/test_reuse_rebaseline_docs.py tests/test_reuse_declaration.py -q -p no:cacheprovider
git diff --check d71d0c97e28e03cb430f05589c8381b4ede70e66...HEAD
git diff --name-only d71d0c97e28e03cb430f05589c8381b4ede70e66...HEAD
```

Expected changed paths are exactly:

```text
docs/superpowers/specs/2026-08-06-official-vision-handoff-codex-worker-design.md
docs/superpowers/plans/2026-08-06-official-vision-handoff-codex-worker.md
```

Then run the hosted `tests` and `reuse-declaration` workflows on the final
exact head. AutoCAD, hosted AutoCAD .NET, real model, private data, and
publication remain `NOT RUN`.

## Rollback

The future adapter is optional and fail-closed. Disable/remove its selection
and revert only its bounded commits. Existing manifests, evidence, IR, DXF,
AutoCAD, review, and publication behavior remain readable and unchanged. No
provider thread, authentication, or output is required to recover project
truth.
