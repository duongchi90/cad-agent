# Page-1 Acceptance Matrix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freshly assess the real approved Page-1 acceptance boundary using existing owners and disposable evidence, then perform at most one bounded causal action at the first actual product failure.

**Architecture:** Read-only evidence composition across the existing source/provenance, geometry/visual, dimension, duplicate/overmerge/missing-geometry, editable/readback, and save/reopen/deterministic-equivalence owners. No new control plane, governance runtime, registry/store, authority mapping, or GitHub runtime dependency. No artifact is promoted to product acceptance by this plan.

**Tech Stack:** Windows, Python 3.11, existing CAD Agent libraries and verification scripts, AutoCAD Mechanical 2027 read-only evidence where available, Git/GitHub, and disposable private-drawing artifacts outside the repository.

## Global Constraints

- Fresh base is `origin/main` as observed immediately before branch creation; exact HEAD must be recorded before every boundary decision.
- This branch starts from current `main`; cherry-pick nothing from `5941e868a62309b773a3621ce69497b5113c3026` or its ancestry.
- Retire `FULL_SEMANTIC_OCCURRENCE_COVERAGE` as a universal Page-1 acceptance requirement. Treat source/provenance identity as its own gate and admit semantic occurrence coverage only when a concrete product failure proves it necessary.
- Existing owners only. Reuse existing APIs, manifests, renderers, geometry/dimension comparators, readback, and save/reopen evidence.
- No source drawing or accepted drawing mutation. Disposable copies may be inspected only; unavailable prerequisites remain `SKIP` or `NOT RUN`.
- One writer, one bounded action, one relevant SOL review per completed boundary. No tuning, alternative implementation, Page-2 work, merge, or candidate promotion while review is pending.

---

### Task 1: Fresh baseline and owner/reuse attribution

**Files:** No production files. Create only this execution plan.

- [ ] Fresh-read GitHub `main`, Issue #409, active branch HEAD, ancestry, worktree diff, and latest relevant SOL verdict.
- [ ] Record `FIRST_UNSATISFIED_BOUNDARY`, `CAUSAL_PATH`, `CURRENT_REACHABILITY`, `MATERIAL_CONSEQUENCE`, `EXISTING_OWNER`, and `CHEAPEST_ORACLE` from observed state.
- [ ] Inspect existing owner APIs/tests/artifacts for every matrix row before any mutation.

### Task 2: One read-only Page-1 acceptance matrix

**Files:** No repository production files; evidence remains disposable/outside the repository.

- [ ] Evaluate exactly these rows in order: source/provenance identity; geometry/visual; dimensions; duplicate/overmerge/missing geometry; editable/readback; save/reopen/deterministic equivalence.
- [ ] For each row record `PASS`, `FAIL`, `SKIP`, or `NOT RUN`, exact artifact identity, owner/oracle, and the reason a state is not stronger.
- [ ] Stop at the first actual product acceptance failure or first required unavailable gate; do not infer PASS from a metric or from semantic occurrence coverage alone.

### Task 3: One bounded causal action at the first failure

**Files:** Only the smallest existing-owner test/oracle/evidence location if a causal defect is proven and a production delta is necessary; otherwise no production files.

- [ ] If needed, establish the smallest causal RED that reproduces the observed failure using the real Page-1 path, not a synthetic approximation.
- [ ] Apply only the smallest causal repair within the existing owner, or perform one read-only oracle if the failure is evidence/prerequisite-only.
- [ ] Run the focused owner check and the narrow relevant regression. Do not broaden scope or tune in the same step.

### Task 4: Review handshake and checkpoint

**Files:** GitHub Issue #409 comment only, after exact state is fresh-read.

- [ ] Record the canonical checkpoint with base, exact HEAD, boundary, evidence state, action, tests, and candidate state.
- [ ] Route the completed bounded unit to exactly one SOL selected by primary risk; for geometry/visual/dimension/evidence risk use Evidence/Acceptance SOL.
- [ ] Send the exact-head review request, set `REVIEW_PENDING`, wait for its verdict, and consume `CLEAR_CONTINUE`, `MATERIAL_FINDING`, or `BLOCKED` before any next mutation.

## Verification

- `git diff --check` and worktree status remain clean apart from this plan unless a bounded production delta is explicitly required.
- Focused owner checks run for any changed behavior.
- `scripts/verify.ps1` is the broader repository gate when a production delta exists; unavailable live/private prerequisites are reported truthfully.
- No Page-1 product PASS or candidate promotion is claimed without real approved-source evidence and all applicable gates.

## Rollback

This plan has no runtime rollback requirement because the default path is read-only. Any disposable artifacts are outside the repository and are not promoted. A production delta, if causally authorized, remains isolated on this fresh branch and is not merged without exact-head review and the required material merge gates.
