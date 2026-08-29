# CAD Agent Lean Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the owner-approved lean roadmap and risk-tiered governance the canonical forward operating model while preserving the five SOL schedules, accepted CAD engine, active PR #285 lane, and all safety invariants.

**Architecture:** This is a documentation/governance-only rebaseline. It adds one approved design, changes the canonical project/architecture/operating/status/handoff documents to route new work through M0-M4, and leaves prior R/P/VS/M/S records as historical evidence rather than the automatic daily queue.

**Tech Stack:** Markdown governance documents, GitHub Issues/PRs, existing repository verification and hosted checks.

**Spec:** `docs/superpowers/specs/2026-08-29-lean-rebaseline-design.md`

## Global Constraints

- Human Owner explicitly requires all five active SOL schedules to remain unchanged.
- Exact base: `1b8b5cd2be0611fc0b3b9f6ffd77b39e58fbc87a`.
- Issue: #295.
- Branch: `governance/lean-rebaseline-2026-08-29`.
- No runtime code, tests, workflows, schemas, dependencies, AutoCAD, File IPC, .NET, provider, private-data, or machine mutation.
- Do not interrupt, supersede, or modify the active #294 / Issue #284 / PR #285 Luna lane.
- Preserve accepted evidence and historical plans; do not delete or rewrite them.
- The new active operational milestones are M0 Stabilize the Pipe, M1 Golden Path, M2 Benchmark, M3 Repair Loop, and M4 Production Hardening.
- New top-level abstractions require measured failure and reuse-first proof.
- `SKIP` and `NOT RUN` remain non-PASS.

---

### Task 1: Record the owner-approved design and execution plan

**Files:**
- Create: `docs/superpowers/specs/2026-08-29-lean-rebaseline-design.md`
- Create: `docs/superpowers/plans/2026-08-29-lean-rebaseline.md`

**Interfaces:**
- Consumes: Human Owner decision, Issue #295, current `docs/PROJECT.md`, `docs/ARCHITECTURE.md`, `docs/AI_OPERATING_MODEL.md`, `docs/STATUS.md`, `docs/HANDOFF.md`, and current #294 control state.
- Produces: the canonical forward design and bounded docs-only execution record.

- [ ] **Step 1: Create the design document**

Record retained invariants, five-SOL preservation, M0-M4 roadmap, historical-roadmap treatment, anti-overengineering rule, conceptual evidence consolidation, risk tiers, success metrics, non-goals, and rollback.

- [ ] **Step 2: Create this implementation plan**

Keep the plan docs-only and restrict changes to the Issue #295 allowlist.

- [ ] **Step 3: Read back both files from the branch**

Expected: both files exist on `governance/lean-rebaseline-2026-08-29`, reference Issue #295, preserve five SOL, and authorize no runtime behavior.

---

### Task 2: Make M0-M4 the project and architecture operating roadmap

**Files:**
- Modify: `docs/PROJECT.md`
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: the lean design and current five-package engine ownership.
- Produces: a concise canonical product roadmap and architecture YAGNI rule.

- [ ] **Step 1: Update `docs/PROJECT.md`**

Replace the old four modernization slices as the active forward roadmap with M0-M4. Keep the original product goal, supported environment, product principles, Drawing Initialization safety boundary, and non-goals. Add explicit text that historical R/P/VS/M/S labels are traceability only unless reactivated by a current Issue/authority.

- [ ] **Step 2: Update `docs/ARCHITECTURE.md`**

Keep the existing package data flow and safety boundaries unchanged. Add a `Lean Rebaseline` section that:

- preserves the five existing package owners;
- states one canonical AutoCAD request/result route;
- freezes new top-level orchestration subsystems absent measured failure;
- prefers existing-owner invariant, then thin adapter/validator, then new subsystem only as last resort;
- treats JobManifest/CandidateArtifact/VerificationEvidence as a conceptual consolidation target only, with no schema migration authorization.

- [ ] **Step 3: Read back both changed files**

Expected: no runtime ownership is moved and no existing accepted contract is declared deleted or invalid.

---

### Task 3: Introduce risk-tiered governance without weakening high-risk gates

**Files:**
- Modify: `docs/AI_OPERATING_MODEL.md`

**Interfaces:**
- Consumes: current Human > SOL > Luna authority, reuse-first rules, and lean design risk tiers.
- Produces: lower process cost for low-risk work while retaining full ceremony for trust/runtime boundaries.

- [ ] **Step 1: Add five-SOL preservation language**

State that the five staggered SOL roles are intentionally retained for low-latency autonomous control when the owner is away, and collision prevention remains the writer-lease/control-ledger protocol.

- [ ] **Step 2: Replace universal reuse-dossier wording with risk-tiered applicability**

Keep full internal/external reuse analysis mandatory when introducing a new dependency/capability, new subsystem, production behavior, transport/protocol, authority store/schema, private-data path, AutoCAD mutation, or publisher/release behavior.

For bounded same-owner bug fixes/test-harness/classification changes that add no dependency or subsystem, require inspection of the existing owner and causal evidence but do not require a performative external-repository survey.

For docs/evidence-only changes, require bounded scope, source-of-truth read, and diff/readback verification.

- [ ] **Step 3: Preserve all hard prohibitions**

Do not weaken no-fabricated-evidence, no duplicate engines/transport, no AI self-approval, no silent `SKIP`/`NOT RUN` promotion, and no unapproved production mutation.

- [ ] **Step 4: Read back the document**

Expected: Tier A remains at least as strict as current production/security rules; Tier B/C only remove ceremony that does not add safety for low-risk scopes.

---

### Task 4: Repoint STATUS and HANDOFF to the lean roadmap without corrupting live control state

**Files:**
- Modify: `docs/STATUS.md`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: current main, #294 successor ledger contract, Issue #295, active #284/#285 lane, and lean design.
- Produces: canonical navigation that distinguishes stable roadmap from rapidly changing control state.

- [ ] **Step 1: Prepend a Lean Rebaseline section to `docs/STATUS.md`**

Record:

- Human Owner approval and Issue #295;
- five SOL preserved;
- M0-M4 as the active forward roadmap once this branch merges;
- old labels retained as historical evidence;
- no runtime capability promoted by this docs change;
- current live state must be read from #131 + #294 and the active Issue/PR rather than cached in STATUS.

Do not rewrite historical verification evidence.

- [ ] **Step 2: Prepend a Lean Rebaseline operational section to `docs/HANDOFF.md`**

Make session startup explicit:

1. read #131 historical standing contracts and #294 active successor ledger;
2. read current main and active Issue/PR;
3. use M0-M4 for product priority;
4. do not reactivate an old R/P/VS/M/S slice merely because it exists in history;
5. preserve five-SOL responsiveness and current Luna authority if active.

Keep the existing historical handoff content below as evidence, clearly marked historical/stale where appropriate.

- [ ] **Step 3: Read back both files**

Expected: the docs do not cache a new numbered control sequence or claim current Luna completion; control ledger remains canonical.

---

### Task 5: Verify scope and open the docs-only PR

**Files:**
- Verify all seven Issue #295 allowlisted paths.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: a reviewable docs-only PR with no runtime effect.

- [ ] **Step 1: Compare branch to exact base**

Expected changed paths are exactly:

```text
docs/PROJECT.md
docs/ARCHITECTURE.md
docs/AI_OPERATING_MODEL.md
docs/STATUS.md
docs/HANDOFF.md
docs/superpowers/specs/2026-08-29-lean-rebaseline-design.md
docs/superpowers/plans/2026-08-29-lean-rebaseline.md
```

No eighth path is permitted.

- [ ] **Step 2: Inspect the cumulative diff**

Verify:

- five SOL are preserved;
- #294 control rules are not weakened;
- PR #285 is not modified;
- no runtime behavior, test, workflow, schema, dependency, or transport changes exist;
- historical evidence remains present;
- M0-M4 and the measured-failure/YAGNI rule are unambiguous.

- [ ] **Step 3: Open a draft PR against `main`**

PR title:

`[Issue #295] Lean rebaseline: five SOL retained, roadmap simplified`

PR body must state exact base, changed paths, no runtime effect, five-SOL preservation, roadmap supersession semantics, verification performed, and that merge must not interrupt the active #294/#284/#285 control lane.

- [ ] **Step 4: Collect hosted checks if any**

If repository checks run on docs-only PRs, require them to complete without unexpected failure before acceptance. A missing live/private gate remains `NOT RUN` and is irrelevant to this docs-only rebaseline.

- [ ] **Step 5: Final readback**

Fresh-read PR metadata, changed paths, and current #294 state. Do not merge if the PR gained a non-doc path or if the active control lane introduced a direct semantic conflict with this rebaseline.
