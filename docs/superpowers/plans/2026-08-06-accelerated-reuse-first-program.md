# Accelerated Reuse-First ChatGPT-to-Codex CAD Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one repository-controlled program roadmap that lets ChatGPT direct official Codex workers and the existing CAD Agent engine through fast, parallel, evidence-backed delivery without duplicating accepted capabilities.

**Architecture:** This plan changes governance and operating documentation only. It records the official ChatGPT-to-Codex handoff model, mandatory internal/external reuse dossiers, parallel workstream rules, and the exact process for issuing future Wave 1 runtime tasks. Each runtime subsystem receives its own fresh Issue, design/plan, base, allowlist, tests, and PO review.

**Tech Stack:** Markdown governance documents, Git/GitHub Issues and PRs, existing Windows/Python 3.11 verification, official OpenAI Codex SDK/App Server interfaces as future dependencies, existing CAD Agent packages, AutoCAD Mechanical 2027 .NET/File IPC, pytest, .NET tests, and GitHub Actions.

## Global Constraints

- Exact planning base: `d00b24e4853d2bfa6bd94873d3014e37575e2718`.
- Issue: #68.
- Branch: `planning/accelerated-reuse-first-program`.
- This plan is docs/governance only and changes exactly the six Issue #68 allowlisted paths.
- Preserve `primitive_ir_lib -> semantic_ir_lib -> agent_lib -> dxf_builder_lib -> mcp_integration_lib` as the execution engine.
- `cad_agent` remains thin orchestration and the sole manifest/checkpoint owner.
- Use official OpenAI Codex Python SDK first, App Server only for SDK gaps, bounded official CLI fallback only if required, and MCP only for experiments/interoperability.
- Do not add dependencies, schemas, runtime code, tests, fixtures, workflows, or AutoCAD behavior in this plan.
- Do not promote `SKIP` or `NOT RUN` to `PASS`.
- S3B AutoCAD live and hosted AutoCAD .NET remain `NOT RUN`.
- S3C, R1C implementation, registry, revision, repair, verdict, publication, OCR expansion, private-data use, and production mutation remain locked.
- No duplicate roadmap authority is created. `docs/STATUS.md` remains the evidence ledger and `docs/HANDOFF.md` remains the operational entry point.
- `AGENTS.md` remains a short navigation map; detailed rules live in linked documents.

## File structure locked by this plan

```text
Create:
  docs/superpowers/specs/2026-08-06-accelerated-reuse-first-program-design.md
  docs/superpowers/plans/2026-08-06-accelerated-reuse-first-program.md

Modify:
  docs/AI_OPERATING_MODEL.md
  AGENTS.md
  docs/HANDOFF.md
  docs/STATUS.md
```

---

### Task 1: Program design and planning baseline

**Files:**
- Create: `docs/superpowers/specs/2026-08-06-accelerated-reuse-first-program-design.md`
- Create: `docs/superpowers/plans/2026-08-06-accelerated-reuse-first-program.md`

**Interfaces:**
- Consumes: Issue #68, `docs/PROJECT.md`, `docs/ARCHITECTURE.md`, `docs/STATUS.md`, `docs/HANDOFF.md`, `docs/QUALITY.md`, `docs/AI_OPERATING_MODEL.md`, `AGENTS.md`, the R0 reuse audit, Codex bridge decision, S1 implementation record, S2C/S3B accepted evidence, R1A/R1B records, and official OpenAI Codex documentation.
- Produces: one program design and one dependency-ordered program plan that later Issues cite without treating them as runtime authorization.

- [x] **Step 1: Create Issue #68 against exact base**

Record exact base `d00b24e4853d2bfa6bd94873d3014e37575e2718`, branch, six-path allowlist, current locks, and owner standing PO authorization.

- [x] **Step 2: Create the planning branch from the exact base**

Branch:

```text
planning/accelerated-reuse-first-program
```

- [x] **Step 3: Add the program design**

The design must include:

- selected reuse-first official-agent architecture;
- accepted-capability inventory;
- ChatGPT, Codex, Visual Supervisor, owner, and deterministic-engine authorities;
- closed vision handoff boundary;
- official Codex integration order;
- internal/external reuse dossier;
- P0-P10 workstreams;
- dependency waves;
- safe parallelization;
- speed controls;
- quality, stop, and rollback gates;
- immediate Wave 1 decision.

- [x] **Step 4: Add this implementation plan**

This plan must not contain runtime implementation steps. It prepares the canonical operating documents and post-merge Issue sequence only.

- [ ] **Step 5: Inspect Task 1 diff**

Run:

```powershell
git diff --check `
  d00b24e4853d2bfa6bd94873d3014e37575e2718...HEAD -- `
  docs/superpowers/specs/2026-08-06-accelerated-reuse-first-program-design.md `
  docs/superpowers/plans/2026-08-06-accelerated-reuse-first-program.md
```

Expected: exit `0`; only the two created planning documents are present at this checkpoint.

---

### Task 2: Update the AI authority and handoff model

**Files:**
- Modify: `docs/AI_OPERATING_MODEL.md`

**Interfaces:**
- Consumes: the program design sections for authority, official Codex integration, vision handoff, reuse dossier, parallel roles, and stop conditions.
- Produces: stable role rules that every ChatGPT, Codex, reviewer, and operator session must follow.

- [ ] **Step 1: Add an `Official ChatGPT-to-Codex handoff` section**

Add these required statements without changing the existing owner/PO/Codex prohibitions:

```text
ChatGPT context is materialized as a closed, hash-bound vision handoff; chat memory alone is not execution authority.
The official OpenAI Codex Python SDK is the preferred worker-control integration.
App Server is used only for required SDK gaps; a bounded official CLI mode is the fallback; MCP is experimental/interoperability only.
Codex output is schema-bound and remains untrusted until CAD Agent validators and fresh post-operation evidence pass.
ChatGPT supplies product vision, scope, protected constraints, and acceptance criteria; it does not fabricate engineering truth.
```

- [ ] **Step 2: Add a `Mandatory reuse dossier` section**

Require every implementation Issue to record:

```text
internal owners/APIs/contracts/tests inspected
external repositories/vendor samples inspected
exact revision/tag and license
maintenance, security, platform, dependency, and test fit
benchmark method and result
classification
migration and rollback
concrete gap reason for NEW_MISSING_CAPABILITY
```

Use the exact classifications:

```text
REUSE_AS_IS
EXTEND_WITH_ADAPTER
EXTEND_WITH_TEST
PORT_BOUNDED_LOGIC
SPIKE_ONLY
REJECT
NEW_MISSING_CAPABILITY
```

- [ ] **Step 3: Add parallel execution authority rules**

Record one writer per overlapping file set and allow separate read-only research, live-environment preparation, hosted CI, and PO review lanes.

- [ ] **Step 4: Verify required markers**

Run:

```powershell
$operating = Get-Content -Raw docs/AI_OPERATING_MODEL.md
@(
  'Official ChatGPT-to-Codex handoff',
  'openai-codex',
  'Mandatory reuse dossier',
  'PORT_BOUNDED_LOGIC',
  'one writer'
) | ForEach-Object {
  if (-not $operating.Contains($_)) { throw "Missing AI operating marker: $_" }
}
```

Expected: exit `0`.

- [ ] **Step 5: Commit the operating-model update**

```powershell
git add docs/AI_OPERATING_MODEL.md
git commit -m "docs: define official ChatGPT Codex operating model"
```

---

### Task 3: Keep AGENTS.md as the concise Codex navigation map

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: `docs/AI_OPERATING_MODEL.md`, the program design, and existing canonical document routes.
- Produces: short session-start and change-workflow pointers for Codex without duplicating the full program manual.

- [ ] **Step 1: Add two canonical references**

Under canonical sources, add:

```text
- AI roles and authority: `docs/AI_OPERATING_MODEL.md`
- Active accelerated reuse-first program: `docs/superpowers/specs/2026-08-06-accelerated-reuse-first-program-design.md` and `docs/superpowers/plans/2026-08-06-accelerated-reuse-first-program.md`
```

- [ ] **Step 2: Extend the change workflow with the reuse gate**

Add one compact rule after repository inspection:

```text
Before new production behavior, complete the Issue's internal/external reuse dossier and prefer existing APIs or a thin adapter; stop for PO review when licensing, reproducibility, architecture ownership, or benchmark benefit is unclear.
```

- [ ] **Step 3: Add official Codex transport routing**

Add one compact safety rule:

```text
Do not build a custom production Codex transport: use the approved official SDK/App Server/fallback order from the operating model.
```

- [ ] **Step 4: Enforce concise-map size**

Run:

```powershell
$lines = (Get-Content AGENTS.md).Count
if ($lines -gt 130) { throw "AGENTS.md grew beyond concise-map limit: $lines lines" }
```

Expected: exit `0`, with `AGENTS.md` at most 130 lines.

- [ ] **Step 5: Commit the AGENTS map update**

```powershell
git add AGENTS.md
git commit -m "docs: route Codex through the reuse-first program"
```

---

### Task 4: Rebaseline STATUS and HANDOFF to the active program

**Files:**
- Modify: `docs/STATUS.md`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: accepted main at `d00b24e4...`, Issue #68, the program design/plan, and all retained locks.
- Produces: truthful current program state and the next operational entry point.

- [ ] **Step 1: Add the planning state to STATUS**

Add a top-level section with the exact meaning:

```text
Accelerated reuse-first program: PLANNING/GOVERNANCE ONLY
Exact planning base: d00b24e4853d2bfa6bd94873d3014e37575e2718
Issue: #68
No runtime capability is promoted by this program PR.
Immediate post-merge wave requires three fresh Issues: official vision handoff, R1C source integrity/fusion, and S2C/S3B live readiness.
S3B AutoCAD live: NOT RUN.
Hosted AutoCAD .NET: NOT RUN.
All current future-runtime locks remain in force.
```

Do not delete historical evidence sections.

- [ ] **Step 2: Add the active program to HANDOFF**

Update the current `Next action` section so it points to:

```text
Issue #68
program design path
program plan path
planning branch and exact base
no runtime authorization until the program PR merges and fresh child Issues are created
```

Keep PR #65/S3B as the latest accepted implementation state and PR #67/d00b24e4 as the latest governance merge.

- [ ] **Step 3: Verify retained locks and truthful gates**

Run:

```powershell
$status = Get-Content -Raw docs/STATUS.md
$handoff = Get-Content -Raw docs/HANDOFF.md
@(
  'PLANNING/GOVERNANCE ONLY',
  'd00b24e4853d2bfa6bd94873d3014e37575e2718',
  'S3B AutoCAD live',
  'NOT RUN',
  'official vision handoff',
  'R1C source integrity/fusion'
) | ForEach-Object {
  if (-not ($status.Contains($_) -or $handoff.Contains($_))) {
    throw "Missing program status/handoff marker: $_"
  }
}
```

Expected: exit `0`.

- [ ] **Step 4: Confirm no runtime promotion language**

Run:

```powershell
$combined = (Get-Content -Raw docs/STATUS.md) + (Get-Content -Raw docs/HANDOFF.md)
@(
  'S3C.*AUTHORIZED',
  'R1C.*ACCEPTED',
  'AutoCAD live.*PASS',
  'Hosted AutoCAD .NET.*PASS'
) | ForEach-Object {
  if ($combined -match $_) { throw "Unauthorized promotion marker matched: $_" }
}
```

Expected: exit `0`.

- [ ] **Step 5: Commit the status/handoff update**

```powershell
git add docs/STATUS.md docs/HANDOFF.md
git commit -m "docs: activate the accelerated reuse-first program"
```

---

### Task 5: Final program verification and draft PR

**Files:**
- Verify exactly the six Issue #68 allowlisted paths.
- Do not create or modify any other repository path.

**Interfaces:**
- Consumes: Tasks 1-4 exact branch state.
- Produces: one reviewable docs-only PR with a complete Reuse Declaration and truthful evidence.

- [ ] **Step 1: Audit branch ancestry**

Run:

```powershell
git merge-base HEAD d00b24e4853d2bfa6bd94873d3014e37575e2718
git log --oneline --reverse d00b24e4853d2bfa6bd94873d3014e37575e2718..HEAD
```

Expected: merge base equals the exact planning base; bounded docs commits only.

- [ ] **Step 2: Audit final paths**

Run:

```powershell
$expected = @(
  'AGENTS.md',
  'docs/AI_OPERATING_MODEL.md',
  'docs/HANDOFF.md',
  'docs/STATUS.md',
  'docs/superpowers/plans/2026-08-06-accelerated-reuse-first-program.md',
  'docs/superpowers/specs/2026-08-06-accelerated-reuse-first-program-design.md'
) | Sort-Object
$actual = git diff --name-only d00b24e4853d2bfa6bd94873d3014e37575e2718...HEAD | Sort-Object
if (Compare-Object $expected $actual) { throw 'Final changed-file allowlist mismatch' }
```

Expected: exit `0`.

- [ ] **Step 3: Run documentation-focused tests**

Run the existing documentation and reuse governance tests discovered on the branch. At minimum:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_documentation_contract.py `
  tests/test_reuse_rebaseline_docs.py `
  tests/test_reuse_declaration.py `
  -q -p no:cacheprovider
```

Expected: exit `0` with no failed test.

- [ ] **Step 4: Run canonical verification**

```powershell
.\scripts\verify.ps1
```

If the environment explicitly lacks the AutoCAD .NET prerequisite, use only the repository-supported skip switch and record hosted AutoCAD .NET as `NOT RUN`. Never convert unavailable-state probes to acceptance.

- [ ] **Step 5: Inspect whitespace and worktree**

```powershell
git diff --check d00b24e4853d2bfa6bd94873d3014e37575e2718...HEAD
git status --short
```

Expected: diff check exit `0`; worktree clean after the final commit.

- [ ] **Step 6: Push normally and open a draft PR**

PR title:

```text
[Program] Accelerated reuse-first ChatGPT-to-Codex CAD roadmap
```

The PR body must include all eight Reuse Declaration labels as same-line non-empty values, exact base/head, six changed paths, test counts, truthful live/private states, and retained runtime locks.

- [ ] **Step 7: Stop for PO review**

Do not mark ready or merge until hosted checks pass on the final synthetic merge and the PO verifies exact head, ancestry, diff, document consistency, and retained locks.

---

### Task 6: Post-merge Wave 1 Issue issuance

**Files:**
- No repository file changes in this task.
- Create three GitHub Issues only after the program PR merges and fresh `main` is verified.

**Interfaces:**
- Consumes: the program merge SHA and design/plan.
- Produces: three independent Wave 1 work items with exact fresh bases and non-overlapping ownership.

- [ ] **Step 1: Verify fresh main**

Fetch `main` after the program merge and record the exact merge SHA. Use that SHA as the planning base for all three child Issues unless one Issue is created after another merge, in which case record its actual fresh base.

- [ ] **Step 2: Create Wave 1A — official vision handoff and Codex worker control**

Required scope:

```text
closed vision-handoff contract and validator
official openai-codex SDK adapter
thread start/resume and bounded turn execution
structured drawing/repair-plan output
event capture, interrupt, timeout, and fail-closed behavior
disposable repository tests
no AutoCAD mutation in the first slice
```

Primary ownership should remain in `agent_lib`, a dedicated closed contract area, focused tests, and one implementation record. It must not modify SourceBundle runtime, AutoCAD dispatcher/gateway, registry, revision, publisher, or dependencies until an execution-time SDK pin decision is separately accepted.

- [ ] **Step 3: Create Wave 1B — R1C SourceBundle byte integrity and fusion boundary**

Required scope:

```text
source byte custody and stable hashes
source roles and page/region identity
quality/distortion observations
conflict records and deterministic fusion inputs
reuse existing Primitive/Semantic IR and manifests
no model call, registry, repair, verdict, publication, or AutoCAD mutation
```

Primary ownership should remain in `cad_agent` source orchestration and dedicated contracts/tests. It must not overlap Wave 1A `agent_lib` worker-control files.

- [ ] **Step 4: Create Wave 1C — S2C/S3B live readiness and acceptance**

Required scope:

```text
operator-approved disposable fixture inventory
AutoCAD Mechanical 2027 session/HWND/plugin/File IPC checks
server-owned path/hash/revision configuration
environment doctor report
exact commands and cleanup/immutability assertions
truthful PASS/FAIL/SKIP/NOT RUN evidence
```

This is an operator/evidence Issue. Repository code changes are forbidden unless a reproducible live defect is isolated and a separate bounded defect Issue is approved.

- [ ] **Step 5: Record overlap matrix**

The three Issues must explicitly show:

```text
Wave 1A owns official Codex worker-control and handoff files.
Wave 1B owns SourceBundle/fusion orchestration files.
Wave 1C owns no production code by default.
Shared canonical docs are integration-owner only.
```

- [ ] **Step 6: Authorize only approved child scope**

Issue creation and planning do not automatically authorize production implementation. Each child Issue requires its own design/plan or complete bounded specification, exact allowlist, reuse dossier, verification gates, and PO authorization.

---

### Task 7: Later-wave issuance rules

**Files:**
- No direct repository changes from this master plan.

**Interfaces:**
- Consumes: accepted Wave 1 contracts and evidence.
- Produces: dependency-correct later Issues.

- [ ] **Step 1: Issue P4 Base CAD Adapter only after P3 contract stability**

Require reuse of S3A/S3B and R1C; forbid a new extractor or transport.

- [ ] **Step 2: Issue P5 Component/View Registry after ownership is stable**

Require one orchestration graph; forbid CAD database and second manifest/revision truth stores.

- [ ] **Step 3: Issue P6 and P7 in disjoint slices**

P6 owns candidate revision lifecycle. P7 owns independent review adapters and read-only evidence aggregation. Shared state contracts require one integration owner.

- [ ] **Step 4: Issue P8 only after fresh visual and engineering contracts exist**

Codex produces a plan; existing executors apply approved operations. No self-approval.

- [ ] **Step 5: Issue P9 publisher last**

Require run-scoped authorization, exact target identity, verified backup, save/reopen, rerender, remeasure, reverify, atomic promotion, and rollback.

- [ ] **Step 6: Run P10 pilots in fixed order**

```text
synthetic -> disposable AutoCAD -> approved private real drawing -> production readiness review
```

No earlier result may be described as later-stage acceptance.

## Plan self-review

- Spec coverage: program architecture, official integration, reuse dossier, roles, workstreams, waves, parallelism, speed, safety, metrics, and immediate Wave 1 issuance are covered.
- Placeholder scan: no TBD/TODO or undefined implementation placeholder remains.
- Scope consistency: this master plan changes governance documents only; all runtime work is delegated to fresh child plans.
- Authority consistency: ChatGPT directs and reviews, Codex implements bounded work, Visual Supervisor reviews independently, CAD Agent executes deterministically, and the owner retains engineering authority.
- Gate consistency: all existing live/private/runtime locks remain unchanged until child Issues are accepted.
