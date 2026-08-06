# Five-Cell Parallel Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate five isolated ChatGPT cells for all GitHub/cloud work and one Codex Local operator for AutoCAD Mechanical 2027 machine-local work while retaining one Master PO, one writer per write-set, and independent exact-head acceptance.

**Architecture:** ChatGPT Cells 1–2 own writer lanes, Cell 3 owns read-only integration/CI audit, and Cells 4–5 own paired red-team lanes. Codex Local alone owns Issue #72 machine-local AutoCAD Mechanical preparation and evidence execution. Master PO owns all scope amendments, final acceptance, and merge.

**Tech Stack:** GitHub Issues/PRs, Git branches/worktrees, repository canonical docs, hosted CI, Windows/Python 3.11, AutoCAD Mechanical 2027, accepted .NET/File IPC boundaries.

## Global Constraints

- Exact governance base: `d71d0c97e28e03cb430f05589c8381b4ede70e66`.
- No runtime scope is opened by this plan.
- No ChatGPT cell or Codex Local may accept or merge its own work.
- One writer per overlapping repository file set.
- Chat memory is not authority; GitHub, repository, AutoCAD state, hashes, and captured evidence are.
- `PASS`, `FAIL`, `SKIP`, and `NOT RUN` remain distinct.
- No private/source/accepted CAD mutation is authorized.
- Codex Local has no repository write authority under Issue #72.

---

### Task 1: Amend coordinator governance

**Files:**
- Modify: `docs/superpowers/specs/2026-08-06-five-cell-parallel-execution-design.md`
- Modify: `docs/superpowers/plans/2026-08-06-five-cell-parallel-execution.md`

**Interfaces:**
- Consumes: accepted Master Program at `d71d0c97...` and owner approval to separate ChatGPT/cloud work from machine-local CAD work.
- Produces: authoritative five-ChatGPT-plus-Codex-Local role/write-set model.

- [ ] Verify branch `planning/five-cell-parallel-execution` starts at exact base.
- [ ] Replace Cell 3 live-operator assignment with read-only integration/CI/evidence coordination.
- [ ] Assign AutoCAD Mechanical 2027 work exclusively to Codex Local under Issue #72.
- [ ] Preserve Cells 1–2 writer and Cells 4–5 red-team ownership.
- [ ] Commit design amendment as a bounded commit.
- [ ] Commit plan amendment as a second bounded commit.
- [ ] Verify cumulative diff still contains exactly the two coordinator documents.
- [ ] Keep PR #75 draft and retain all runtime locks.

### Task 2: Preserve Cell 1 and Cell 4 on Wave 1A

**Files:** none.

**Interfaces:**
- Consumes: Issue #70, PR #73, and Issue #76.
- Produces: one writer/local-PO lane and one independent official-interface red-team lane.

- [ ] Keep Cell 1 as sole writer for the #70 allowlist.
- [ ] Keep Cell 4 read-only on Issue #76.
- [ ] Require Cell 4 verdict before final PR #73 integration.
- [ ] Require Cell 3 to audit PR #73 exact head, CI, allowlist, review state, and PR-body consistency.
- [ ] Preserve Master PO as the only ready/merge authority.

### Task 3: Preserve Cell 2 and Cell 5 on Wave 1B

**Files:** none.

**Interfaces:**
- Consumes: Issue #71 and Issue #77.
- Produces: one R1C writer/local-PO lane and one independent reuse/determinism red-team lane.

- [ ] Keep Cell 2 as sole writer for the #71 allowlist.
- [ ] Keep Cell 5 read-only on Issue #77.
- [ ] Require Cell 5 verdict before final Wave 1B planning integration.
- [ ] Require Cell 3 to audit the Wave 1B PR exact head, CI, allowlist, review state, and PR-body consistency.
- [ ] Preserve Master PO as the only ready/merge authority.

### Task 4: Activate ChatGPT Cell 3 as integration/CI coordinator

**Files:** none.

**Interfaces:**
- Consumes: all Wave 1 Issues, PRs, workflow runs, patches, and review states.
- Produces: read-only exact-head audits and Wave 1 roll-up reports.

- [ ] Create a dedicated read-only Issue for Cell 3.
- [ ] Record accepted `main`, active Issue/PR map, and coordinator links.
- [ ] Require exact base/head/ancestry and ahead/behind checks.
- [ ] Require changed-file allowlist and write-set overlap checks.
- [ ] Require hosted workflow IDs, logs, exact test counts, skips, and `NOT RUN` markers.
- [ ] Require review-thread, paired-red-team, PR-body-consistency, stale-base, and merge-order checks.
- [ ] Forbid branch creation, repository edits, ready/merge actions, AutoCAD operation, and live-evidence claims.
- [ ] Require advisory verdict and `Repository writes: NONE`.

### Task 5: Assign AutoCAD Mechanical to Codex Local

**Files:** none.

**Interfaces:**
- Consumes: Issue #72 accepted live-evidence authorization, local Windows environment, accepted S2C/S3B implementations, approved disposable fixtures.
- Produces: machine-local readiness and live evidence packet without repository changes.

- [ ] Post Master PO amendment on Issue #72 naming Codex Local as sole machine-local operator.
- [ ] Supersede the earlier ChatGPT Cell 3 operator assignment.
- [ ] Require canonical document and Issue read before local work.
- [ ] Require clean repository/worktree and accepted-commit verification.
- [ ] Require AutoCAD version/build, process, HWND, document, plugin, File IPC, LISP, roots, and timeout inventory.
- [ ] Require repository-supported local .NET build/test results without committing changes.
- [ ] Require approved disposable S2C fixture and S3B source/candidate identity.
- [ ] Require pre/post hashes, byte sizes, timestamps, revision identity, DBMOD/state, artifacts, and cleanup.
- [ ] Require fresh preflight before every live operation; prior inspection/run IDs do not authorize later mutation.
- [ ] Require independent S2C and S3B `PASS`/`FAIL`/`SKIP`/`NOT RUN` states.
- [ ] Require source/accepted CAD immutability and `Repository writes: NONE`.
- [ ] Require any reproducible code defect to become a separate bounded Issue before code changes.

### Task 6: Enforce cross-cell and Codex coordination

**Files:** none.

**Interfaces:**
- Consumes: five ChatGPT cell outputs and Codex Local evidence.
- Produces: consistent review, integration, and live-acceptance flow.

- [ ] Writer cells open draft PRs and stop.
- [ ] Paired red-team cells post findings before Master PO acceptance.
- [ ] Writers address findings only through bounded follow-up commits.
- [ ] Cell 3 audits exact heads, allowlists, CI, unresolved threads, overlap, PR-body claims, and stale-base risk.
- [ ] Codex Local posts #72 evidence without repository writes.
- [ ] Cell 3 checks #72 evidence consistency without claiming machine-local execution.
- [ ] Master PO alone assigns acceptance, marks PRs ready, merges, or opens defect/rebaseline Issues.
- [ ] When one planning PR merges first, evaluate the other for conflicts without silent rebase.

### Task 7: Update coordinator Issue and PR metadata

**Files:** none.

**Interfaces:**
- Consumes: amended design/plan and new Issue assignments.
- Produces: durable GitHub navigation to the current model.

- [ ] Update Issue #74 wording to say five ChatGPT cells plus Codex Local.
- [ ] Cross-link Cell 3 Issue #79.
- [ ] Cross-link Codex Local assignment comment on Issue #72.
- [ ] Update PR #75 summary/body to reflect the new role split.
- [ ] Keep PR #75 `OPEN/DRAFT`.

### Task 8: Verification and handoff

**Files:** none beyond Task 1.

**Interfaces:**
- Consumes: coordinator PR and six actor assignments.
- Produces: verified operating map and prompt destinations.

- [ ] Compare coordinator branch against exact base and verify cumulative two-path diff.
- [ ] Confirm #70, #71, #72, #76, #77, and #79 remain open with their intended authority.
- [ ] Confirm Cell 3 is read-only and Codex Local owns #72 machine-local work.
- [ ] Confirm all prompts identify authority, scope, stop conditions, and completion format.
- [ ] Run or inspect fresh hosted `tests` and `reuse-declaration` on the final coordinator head/synthetic merge.
- [ ] Confirm no runtime, dependency, private-data, AutoCAD mutation, or downstream promotion is introduced by PR #75.
- [ ] Report coordinator Issue, branch, bounded commits, draft PR, exact head, hosted evidence, and actor destinations.

## Verification Commands

```powershell
git fetch origin
git merge-base origin/planning/five-cell-parallel-execution d71d0c97e28e03cb430f05589c8381b4ede70e66
git diff --name-only d71d0c97e28e03cb430f05589c8381b4ede70e66...origin/planning/five-cell-parallel-execution
git diff --check d71d0c97e28e03cb430f05589c8381b4ede70e66...origin/planning/five-cell-parallel-execution
```

Expected changed paths:

```text
docs/superpowers/plans/2026-08-06-five-cell-parallel-execution.md
docs/superpowers/specs/2026-08-06-five-cell-parallel-execution-design.md
```

## Completion State

- Coordinator PR #75 remains draft for exact-head PO review.
- ChatGPT Cells 1–5 may operate only within #70, #71, #79, #76, and #77.
- Codex Local may operate AutoCAD Mechanical only within Issue #72 and has no repository write authority there.
- Runtime implementation remains locked unless a specific existing or future Issue explicitly opens it.
