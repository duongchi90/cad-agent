# Five-Cell Parallel Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate five isolated ChatGPT/Codex work cells for Wave 1 while retaining one Master PO, one writer per write-set, and independent exact-head acceptance.

**Architecture:** Cells 1–3 use existing Issues #70–#72. Cells 4–5 receive new read-only research/red-team Issues. Writer cells use isolated branches; research cells post findings only; the live cell changes no repository files. Master PO owns merge and scope amendments.

**Tech Stack:** GitHub Issues/PRs, Git branches/worktrees, repository canonical docs, hosted CI, AutoCAD Mechanical 2027 evidence lane.

## Global Constraints

- Exact governance base: `d71d0c97e28e03cb430f05589c8381b4ede70e66`.
- No runtime scope is opened by this plan.
- No cell may accept or merge its own work.
- One writer per overlapping file set.
- Chat memory is not authority; GitHub evidence is.
- `PASS`, `FAIL`, `SKIP`, and `NOT RUN` remain distinct.
- No private/source/accepted CAD mutation is authorized.

---

### Task 1: Publish coordinator governance

**Files:**
- Create: `docs/superpowers/specs/2026-08-06-five-cell-parallel-execution-design.md`
- Create: `docs/superpowers/plans/2026-08-06-five-cell-parallel-execution.md`

**Interfaces:**
- Consumes: accepted Master Program at `d71d0c97...`.
- Produces: authoritative five-cell role/write-set model.

- [ ] Verify branch `planning/five-cell-parallel-execution` starts at exact base.
- [ ] Commit design as a bounded commit.
- [ ] Commit this plan as a second bounded commit.
- [ ] Verify final diff contains exactly the two documents.
- [ ] Open a draft PR targeting `main` and retain runtime locks.

### Task 2: Activate Cell 1 and Cell 4 on Issue #70

**Files:** none.

**Interfaces:**
- Consumes: Issue #70 planning authorization.
- Produces: one writer prompt and one read-only red-team prompt.

- [ ] Add a Master PO comment naming Cell 1 as the sole writer for the #70 two-file allowlist.
- [ ] Add Cell 1 self-contained prompt with exact base, branch, tasks, verification, stop conditions, and completion report.
- [ ] Create a separate read-only research/red-team Issue for Cell 4.
- [ ] Cross-link the Cell 4 Issue from #70.
- [ ] State that Cell 4 has no repository write or merge authority.

### Task 3: Activate Cell 2 and Cell 5 on Issue #71

**Files:** none.

**Interfaces:**
- Consumes: Issue #71 planning authorization.
- Produces: one writer prompt and one read-only red-team prompt.

- [ ] Add a Master PO comment naming Cell 2 as the sole writer for the #71 two-file allowlist.
- [ ] Add Cell 2 self-contained prompt with exact base, branch, tasks, verification, stop conditions, and completion report.
- [ ] Create a separate read-only research/red-team Issue for Cell 5.
- [ ] Cross-link the Cell 5 Issue from #71.
- [ ] State that Cell 5 has no repository write or merge authority.

### Task 4: Activate Cell 3 on Issue #72

**Files:** none.

**Interfaces:**
- Consumes: Issue #72 operator/evidence authorization.
- Produces: a self-contained live-operator prompt and evidence packet.

- [ ] Add a Master PO comment naming Cell 3 as the sole live operator coordinator.
- [ ] Restate no-branch/no-repository-write policy.
- [ ] Provide prerequisite inventory, preflight, execution, evidence, and stop-condition checklist.
- [ ] Require independent S2C and S3B acceptance states.
- [ ] Require a separate defect Issue for any code change.

### Task 5: Enforce cross-cell coordination

**Files:** none.

**Interfaces:**
- Consumes: all five cell outputs.
- Produces: consistent cross-review and integration flow.

- [ ] Writer cells open draft PRs and stop.
- [ ] Paired red-team cells post findings before Master PO review.
- [ ] Writers address findings only through bounded follow-up commits.
- [ ] Master PO checks exact heads, allowlists, CI, and unresolved threads.
- [ ] Master PO alone marks ready and merges.
- [ ] When one planning PR merges first, evaluate the other for conflicts without silent rebase.

### Task 6: Verification and handoff

**Files:** none beyond Task 1.

**Interfaces:**
- Consumes: coordinator PR and five Issue prompts.
- Produces: a user-ready five-cell prompt pack and live tracking map.

- [ ] Compare coordinator branch against exact base and verify two-path diff.
- [ ] Confirm Issues #70, #71, and #72 remain open and retain their original locks.
- [ ] Confirm two new research Issues are open and read-only.
- [ ] Confirm all five prompts identify authority, scope, stop conditions, and completion format.
- [ ] Report coordinator Issue, branch, commits, draft PR, and the five cell destinations.

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

- Coordinator PR remains draft for independent PO review.
- Cells may begin only within the authorization recorded on their Issues.
- Runtime implementation remains locked unless a specific existing or future Issue explicitly opens it.
