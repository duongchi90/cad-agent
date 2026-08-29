# CAD Agent Lean Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the owner-approved lean product roadmap canonical while preserving the complete established Human Owner → SOL_POOL → Luna/Codex Desktop operating model, five SOL schedules, accepted CAD engine, active PR #285 lane, and all safety/evidence invariants.

**Architecture:** This is a documentation/governance-only rebaseline. It changes product prioritization and abstraction admission, not the execution/governance protocol. It routes future product work through M0-M4 and leaves prior R/P/VS/M/S records as historical evidence rather than the automatic daily queue. `docs/STATUS.md` remains byte-unchanged as the long evidence history; live operational navigation is updated in `docs/HANDOFF.md`.

**Tech Stack:** Markdown governance documents, GitHub Issues/PRs, existing repository verification and hosted checks.

**Spec:** `docs/superpowers/specs/2026-08-29-lean-rebaseline-design.md`

## Global Constraints

- Human Owner explicitly requires all five active SOL schedules to remain unchanged.
- Preserve standing operating model comments `5396800691`, `5419064061`, `5442771213`, and `5443060158`; this plan may reference but must not supersede or weaken them.
- Every newly built runtime/product capability continues to use the established fresh-read, writer-lease, PRE_ISSUANCE_GATE_V1, long-horizon Luna mission, reuse, RED-first TDD, exact write-set, evidence, review, live/private, terminal, and acceptance discipline.
- Exact base: `1b8b5cd2be0611fc0b3b9f6ffd77b39e58fbc87a`.
- Issue: #295.
- Branch: `governance/lean-rebaseline-2026-08-29`.
- No runtime code, tests, workflows, schemas, dependencies, AutoCAD, File IPC, .NET, provider, private-data, or machine mutation.
- Do not interrupt, supersede, or modify the active #294 / Issue #284 / PR #285 Luna lane.
- Preserve accepted evidence and historical plans; do not delete or rewrite them.
- Keep `docs/STATUS.md` byte-unchanged.
- The new active product milestones are M0 Stabilize the Pipe, M1 Golden Path, M2 Benchmark, M3 Repair Loop, and M4 Production Hardening.
- New top-level abstractions require measured failure and reuse-first proof.
- `SKIP` and `NOT RUN` remain non-PASS.
- Do not create a new risk-tier/substitute governance model.

---

### Task 1: Record the owner-approved design and execution plan

**Files:**
- Create: `docs/superpowers/specs/2026-08-29-lean-rebaseline-design.md`
- Create: `docs/superpowers/plans/2026-08-29-lean-rebaseline.md`

**Interfaces:**
- Consumes: Human Owner decision, Issue #295, standing comments `5396800691` / `5419064061` / `5442771213` / `5443060158`, current `docs/PROJECT.md`, `docs/ARCHITECTURE.md`, `docs/AI_OPERATING_MODEL.md`, `docs/STATUS.md`, `docs/HANDOFF.md`, and current #131/#294 control state.
- Produces: the canonical forward product design and bounded docs-only execution record.

- [ ] **Step 1: Create the design document**

Record retained operating contracts, Human/SOL/Luna responsibility split, five-SOL preservation, long-horizon Luna autonomy, M0-M4 roadmap, historical-roadmap treatment, anti-overengineering rule, conceptual evidence consolidation, success metrics, non-goals, and rollback.

- [ ] **Step 2: Create this implementation plan**

Keep the plan docs-only and restrict changes to the Issue #295 allowlist.

- [ ] **Step 3: Read back both files from the branch**

Expected: both files exist on `governance/lean-rebaseline-2026-08-29`, reference Issue #295, explicitly preserve the four standing contracts and five SOL, and authorize no runtime behavior.

---

### Task 2: Make M0-M4 the project and architecture product roadmap

**Files:**
- Modify: `docs/PROJECT.md`
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: the lean design and current five-package engine ownership.
- Produces: a concise canonical product roadmap and architecture YAGNI rule without changing execution protocol.

- [ ] **Step 1: Update `docs/PROJECT.md`**

Replace the old modernization slices as the active forward product roadmap with M0-M4. Keep the original product goal, supported environment, product principles, Drawing Initialization safety boundary, and non-goals. Add explicit text that historical R/P/VS/M/S labels are traceability only unless reactivated by a current Issue/authority.

State that M0-M4 changes product priority only; every new capability within any milestone still follows the standing Human/SOL/Luna operating model.

- [ ] **Step 2: Update `docs/ARCHITECTURE.md`**

Keep the existing package data flow and safety boundaries unchanged. Add a `Lean Rebaseline` section that:

- preserves the five existing package owners;
- states one canonical AutoCAD request/result route;
- freezes new top-level orchestration subsystems absent measured failure;
- prefers existing-owner invariant, then thin adapter/validator, then new subsystem only as last resort;
- treats JobManifest/CandidateArtifact/VerificationEvidence as a conceptual consolidation target only, with no schema migration authorization;
- explicitly states that architecture simplification does not relax standing writer-lease, pre-issuance, TDD/evidence, long-horizon Luna, or live/private rules.

- [ ] **Step 3: Read back both changed files**

Expected: no runtime ownership is moved, no accepted contract is declared deleted/invalid, and no new process doctrine is introduced.

---

### Task 3: Make `AI_OPERATING_MODEL.md` point to the standing control contracts without replacing them

**Files:**
- Modify: `docs/AI_OPERATING_MODEL.md`

**Interfaces:**
- Consumes: current Human/PO/Codex principles plus standing GitHub comments `5396800691`, `5419064061`, `5442771213`, `5443060158` and #131/#294 rollover state.
- Produces: durable navigation that preserves the actual operating model across new chats and future newly built work.

- [ ] **Step 1: Record the live standing-contract hierarchy**

Add a concise section stating:

```text
Human Owner > SOL_POOL > Luna / Codex Desktop
GitHub canonical
Standing model: #131 comment 5396800691
Persistence/long horizon: #131 comment 5419064061
PRE_ISSUANCE_GATE_V1: #131 comment 5442771213
Five-SOL writer lease: #131 comment 5443060158
Control ledger: #131 historical + #294 active successor
```

State that the current valid numbered authority overrides stale docs/chat state within its exact scope.

- [ ] **Step 2: Preserve the five-SOL rules exactly**

Record that all five cells are writer-eligible, but one valid writer lease owns a target sequence; losers/advisors use `CONTROL_SEQ=NONE`. Keep exact-read, lowest-comment-ID arbitration, anti-race, terminal single-consumption, CURRENT/N+1/N+2, reused PASS evidence, pre-execution closure, and first-unsatisfied-gate requirements.

- [ ] **Step 3: Preserve Luna long-horizon execution exactly**

Record one Local Solo Executor only. Within exact authority, Luna owns machine-local edit/test/build/commit/push and authorized live execution; small same-layer defects are repaired inside the causal family; hard handoff occurs only at the standing boundaries. Repo write authority never implies merge.

- [ ] **Step 4: Preserve new-capability engineering discipline**

Do not replace the existing reuse dossier, TDD, exact write-set, focused/aggregate evidence, independent acceptance, privacy/live gates, or no-duplicate-owner rules with a new tier system. Clarify only that docs-only maintenance and same-layer defect handling already have their bounded treatment under the standing model.

- [ ] **Step 5: Read back the document**

Expected: the document points to and preserves the GitHub standing contracts; it does not claim the Lean Rebaseline supersedes them.

---

### Task 4: Repoint HANDOFF to the lean product roadmap without rewriting the evidence history

**Files:**
- Modify: `docs/HANDOFF.md`
- Preserve byte-identical: `docs/STATUS.md`

**Interfaces:**
- Consumes: current main, #131/#294 ledger contract, Issue #295, active #284/#285 lane, and lean design.
- Produces: current session-start navigation while leaving the long verification ledger untouched.

- [ ] **Step 1: Update `docs/HANDOFF.md`**

Make session startup explicit:

1. read standing comments `5396800691`, `5419064061`, `5442771213`, `5443060158`;
2. read #131 historical + #294 active successor ledger and reconstruct current numbered authority/terminal/baton;
3. read current main and active Issue/PR;
4. use M0-M4 for product priority;
5. do not reactivate an old R/P/VS/M/S slice merely because it exists in history;
6. preserve current Luna authority if active and use the five-SOL lease protocol at the next hard handoff.

Preserve the former 2026-08-06 handoff as clearly labeled historical evidence rather than deleting its accepted implementation facts.

- [ ] **Step 2: Prove `docs/STATUS.md` is unchanged**

Compare the branch blob to exact base `1b8b5cd2...` and require byte identity.

- [ ] **Step 3: Read back HANDOFF**

Expected: it does not cache a new numbered sequence or claim current Luna completion; control ledger remains canonical.

---

### Task 5: Verify scope and open the docs-only PR

**Files:**
- Verify all six Issue #295 changed paths.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: a reviewable docs-only PR with no runtime/control effect.

- [ ] **Step 1: Compare branch to exact base**

Expected changed paths are exactly:

```text
docs/PROJECT.md
docs/ARCHITECTURE.md
docs/AI_OPERATING_MODEL.md
docs/HANDOFF.md
docs/superpowers/specs/2026-08-29-lean-rebaseline-design.md
docs/superpowers/plans/2026-08-29-lean-rebaseline.md
```

No seventh path is permitted. `docs/STATUS.md` must remain byte-identical to base.

- [ ] **Step 2: Inspect the cumulative diff**

Verify:

- five SOL schedules/roles are preserved;
- all five remain writer-eligible under one-valid-lease arbitration;
- long-horizon Luna autonomy and hard-handoff boundaries are preserved;
- PRE_ISSUANCE_GATE_V1 and N+1/N+2 are preserved;
- #131/#294 control rules are not weakened;
- PR #285 is not modified;
- no runtime behavior, test, workflow, schema, dependency, or transport changes exist;
- historical evidence remains present;
- M0-M4 and the measured-failure/YAGNI rule are unambiguous;
- no new risk-tier/substitute governance model remains.

- [ ] **Step 3: Open a draft PR against `main`**

PR title:

`[Issue #295] Lean rebaseline: preserve operating model, simplify roadmap`

PR body must state exact base, changed paths, no runtime effect, five-SOL + standing-contract preservation, roadmap supersession semantics, verification performed, and that merge must not interrupt the active #294/#284/#285 control lane.

- [ ] **Step 4: Collect hosted checks if any**

If repository checks run on docs-only PRs, require them to complete without unexpected failure before acceptance. A missing live/private gate remains `NOT RUN` and is irrelevant to this docs-only rebaseline.

- [ ] **Step 5: Final readback**

Fresh-read PR metadata, changed paths, standing comments, current #294 state, current main, and active PR tuple. Do not merge if the PR gained a non-doc path, weakens a standing contract, or if the active control lane introduced a direct semantic conflict with this rebaseline.
