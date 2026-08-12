# SOL-First Operating Model 10/10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the approved SOL-first operating model as canonical project governance, migrate the active frontier safely, and remove routine Luna handoff latency without weakening independent audit or live/Human gates.

**Architecture:** This is a governance/control-plane rollout, not a new runtime subsystem. The repository stores the approved design and this implementation plan; canonical operational authority is then activated through the existing GitHub control plane (#131) and applied to each active task by fresh re-epoch. Runtime code continues to change only under its own bounded Issue/PR contracts.

**Tech Stack:** GitHub Issues/PRs, GitHub Actions hosted tests/reuse checks, Markdown governance artifacts, existing `CONTROL_CONTRACT_VERSION: 1.3` control plane.

## Global Constraints

- Approved operating model version: `1.0`.
- Existing control contract baseline remains `CONTROL_CONTRACT_VERSION: 1.3`; this rollout is an overlay, not an implicit version rewrite.
- `PRIMARY_OFFLINE_EXECUTOR = SOL` only after canonical adoption; existing stricter task-specific decisions continue to control until individually re-epoched.
- `INDEPENDENT_REVIEW = REVIEWER_INTEGRATION + REVIEWER_SECURITY`; SOL self-review never substitutes for either PASS.
- `USER_VISIBILITY = SIGNAL_ONLY`.
- `MERGE_POLICY = AUTO_MERGE_ON_FULL_EXACT_HEAD_GATE` only after canonical adoption and only when the controlling task contract does not prohibit it.
- `AUTO_RESUME = YES` and `ZERO_SILENT_BATON = ENFORCED` after canonical adoption.
- One primary writer per task/branch; never dual-write the same task with SOL and Luna.
- No production/runtime/test/workflow/dependency/schema change is authorized by this governance rollout itself.
- No amend, rebase, squash, or force-push where forward-only project history is required.
- Live AutoCAD/File-IPC/provider/private/customer CAD, production publication, secrets, machine/system mutation, and irreversible external action remain governed by their existing Human/local gates.
- R5 -> R6 -> fresh custody/currentness -> fresh R3 -> proper R4 new/final candidate -> NEW independent R5 PASS -> R7 -> R8 remains unchanged.

---

### Task 1: Publish the approved governance artifacts as a docs-only PR

**Files:**
- Existing approved design: `docs/superpowers/specs/2026-08-12-sol-first-operating-model-design.md`
- Create: `docs/superpowers/plans/2026-08-12-sol-first-operating-model.md`
- Modify runtime/tests/workflows/dependencies: none

**Interfaces:**
- Consumes: Human-approved design, `CONTROL_CONTRACT_VERSION: 1.3`, current repository `main`.
- Produces: one reviewed docs-only PR containing exactly the design + implementation plan.

- [ ] **Step 1: Fresh-read current main and the planning branch before opening the PR**

Run:

```bash
git fetch origin main docs/sol-first-operating-model-spec
git rev-parse origin/main
git merge-base origin/main origin/docs/sol-first-operating-model-spec
git diff --name-status origin/main...origin/docs/sol-first-operating-model-spec
```

Expected:
- record the exact current `main` SHA;
- merge-base is the branch's issuance base if `main` has not moved;
- cumulative diff contains only:
  - `docs/superpowers/specs/2026-08-12-sol-first-operating-model-design.md`
  - `docs/superpowers/plans/2026-08-12-sol-first-operating-model.md`.

If current `main` moved, do not silently rewrite history. Freshly classify whether a clean new docs branch from current `main` is required; the final PR must still contain only the two approved governance docs.

- [ ] **Step 2: Run the planning-artifact integrity checks**

Run:

```bash
python - <<'PY'
from pathlib import Path
paths = [
    Path('docs/superpowers/specs/2026-08-12-sol-first-operating-model-design.md'),
    Path('docs/superpowers/plans/2026-08-12-sol-first-operating-model.md'),
]
forbidden = (
    'T' + 'BD',
    'TO' + 'DO',
    'implement' + ' later',
    'fill' + ' in details',
)
for path in paths:
    text = path.read_text(encoding='utf-8')
    for marker in forbidden:
        assert marker not in text, (path, marker)
print('planning-marker-scan: PASS')
PY

git diff --check origin/main...HEAD
```

Expected: marker scan PASS and `git diff --check` exits 0.

- [ ] **Step 3: Open a DRAFT docs-only PR**

Use a PR body that freezes:

```text
Reuse Declaration
Existing capability inspected: current #131 control-plane governance, paired reviewer model, hosted tests/reuse gates, existing task-specific SOL_DECISION contracts.
Existing API/process reused: GitHub Issues/PRs/comments + existing reviewer roles + hosted checks; no new workflow or runtime owner.
Adapter required: governance overlay only.
New capability genuinely missing: canonical SOL-first offline execution ownership and zero-silent-baton operating policy.
Files allowed to change: exactly the two governance docs in this PR.
Files forbidden to change: runtime, tests, workflows, dependencies, schemas, fixtures, live/local surfaces.
Compatibility behavior: existing stricter task-specific decisions remain controlling until fresh re-epoch.
Migration/rollback: adoption is activated separately through #131 after this docs PR is accepted; a later canonical decision can supersede the operating model without destructive history.
```

Expected: PR is DRAFT and changed files remain exactly two docs.

- [ ] **Step 4: Require hosted checks and independent docs review**

Verify on the exact PR head:

```text
hosted tests/repository verification: PASS
reuse-declaration: PASS
REVIEWER_INTEGRATION: PASS — exact two-doc scope, no runtime/workflow/dependency drift
REVIEWER_SECURITY: PASS — no weakening of independent audit, Human/live gates, or task-specific authority
```

If any reviewer requests a substantive governance change, modify only the two docs, create a forward commit, rerun hosted checks, and return the exact new head to both reviewers.

- [ ] **Step 5: Merge the docs PR under the governance that is canonical at merge time**

Before merge, fresh-check:

```bash
git fetch origin main
git diff --name-only origin/main...HEAD
```

Expected: exactly two docs. Do not assume the new auto-merge policy is active merely because the PR describes it; use the pre-existing canonical merge authority for this adoption PR unless a fresh canonical decision explicitly says otherwise.

---

### Task 2: Activate Operating Model 1.0 through the canonical #131 control plane

**Files:** none

**Interfaces:**
- Consumes: merged governance-doc commit/merge SHA, fresh current `main`, existing #131 control-plane comments.
- Produces: one canonical adoption decision making Operating Model 1.0 effective prospectively.

- [ ] **Step 1: Prove the docs are integrated before activation**

Fresh-read:

```text
current main exact SHA
merged governance PR number
merged governance PR head and merge SHA
exact two-doc cumulative diff
```

Expected: both approved governance docs are reachable from current `main`.

- [ ] **Step 2: Anti-race the adoption decision**

Search #131 for the exact prospective marker:

```text
SOL_OPERATING_MODEL: 1.0
ADOPTION_KEY: SOL-OPERATING-MODEL-1.0:<merge-sha>
```

Expected: no prior canonical adoption comment with that exact key.

- [ ] **Step 3: Post one canonical adoption decision to #131**

Post a comment with this exact semantic payload, substituting fresh SHAs/PR IDs:

```text
CONTROL_CONTRACT_VERSION: 1.3
SOL_OPERATING_MODEL: 1.0
ADOPTION_KEY: SOL-OPERATING-MODEL-1.0:<governance-merge-sha>
CURRENT_MAIN: <fresh-main-sha>
GOVERNANCE_SPEC: docs/superpowers/specs/2026-08-12-sol-first-operating-model-design.md
GOVERNANCE_PLAN: docs/superpowers/plans/2026-08-12-sol-first-operating-model.md

DECISION: ADOPT_SOL_FIRST_OPERATING_MODEL_PROSPECTIVELY
PRIMARY_OFFLINE_EXECUTOR: SOL
PRIMARY_GOVERNANCE_OWNER: SOL
INDEPENDENT_REVIEW: REVIEWER_INTEGRATION + REVIEWER_SECURITY
LUNA_ROLE: LOCAL_MACHINE_EXECUTOR | AUTOCAD_EXECUTOR | FAILOVER_EXECUTOR
USER_VISIBILITY: SIGNAL_ONLY
MERGE_POLICY: AUTO_MERGE_ON_FULL_EXACT_HEAD_GATE
AUTO_RESUME: YES
ZERO_SILENT_BATON: ENFORCED

RETROACTIVITY: NONE. Existing active task-specific decisions remain controlling until each task is fresh-read and explicitly re-epoched. No existing write authority, merge authority, live authority, or Human gate is broadened by this adoption comment alone.

AUTO_MERGE_GATE: exact lineage/base rule satisfied + exact reviewed head + exact authorized write-set + hosted tests PASS + reuse/architecture PASS + REVIEWER_INTEGRATION PASS + REVIEWER_SECURITY PASS + no unresolved blocking thread + no head drift + no controlling material invalidator.

MAIN_MOVEMENT: never silently tolerated. Exact-base tasks require exact equality; lineage-compatible tasks require fresh re-epoch proving intervening commits do not invalidate named owners/seams/authority/freshness assumptions.

HARD_GATES: live AutoCAD/File-IPC/provider/private/customer CAD, production publication, secrets, machine/system mutation, destructive history and irreversible external action remain under existing stricter contracts/Human gates.
```

- [ ] **Step 4: Verify canonical adoption exactly once**

Fresh-read #131 and prove:
- the posted comment exists unchanged;
- the `ADOPTION_KEY` appears exactly once among canonical adoption comments;
- no later comment already supersedes Operating Model 1.0.

---

### Task 3: Migrate the active frontier without retroactive authority leakage

**Files:** none under this governance task; runtime files remain owned by their active Issues/PRs.

**Interfaces:**
- Consumes: Operating Model 1.0 adoption, fresh #131 state, fresh active Issue/PR states.
- Produces: explicit per-task re-epoch decisions assigning SOL as writer only where safe and preserving every task-specific write-set/security/live gate.

- [ ] **Step 1: Inventory only genuinely active frontier tasks**

Fresh-read at minimum:

```text
current main
#131 latest canonical decisions/terminals
PR #213 + Issue #212
PR #206 + Issue #204
any newer successor that supersedes either task
```

Do not migrate stale/closed/superseded tasks merely because they appear in history.

- [ ] **Step 2: For each active task, prove no dual-writer race before baton transfer**

Required evidence:

```text
exact current PR head
exact authorized write-set
current write phase: RED / GREEN / STOP_WRITE / review / merge-ready
whether any Luna/Codex writer action is actually in flight
whether the current task-specific SOL_DECISION names Luna as writer
```

If a writer is actively mutating the branch, do not transfer concurrently. Wait for that exact bounded terminal or explicitly freeze/transfer at a known head.

- [ ] **Step 3: Re-epoch one active task at a time**

For a safe transfer, post a fresh task-specific SOL decision containing:

```text
CONTROL_CONTRACT_VERSION: 1.3
SOL_OPERATING_MODEL: 1.0
CURRENT_MAIN: <fresh-main>
ACTIVE_ISSUE: <issue>
ACTIVE_PR: <pr>
EXACT_HEAD: <head>
AUTHORIZED_WRITE_SET: <unchanged task-specific write-set>
PRIMARY_NEXT_OWNER: SOL
WRITE_TRANSPORT: SOL/GitHub
INDEPENDENT_REVIEW: REVIEWER_INTEGRATION + REVIEWER_SECURITY
AUTO_RESUME: YES
AUTO_MERGE: allowed only if this task's full exact-head gate is satisfied and no stricter earlier decision forbids it
LUNA: no write authority unless separately handed a local/failover packet
HARD_GATES: unchanged
```

The re-epoch must not broaden runtime scope, third paths, schemas, dependencies, live access, or review exemptions.

- [ ] **Step 4: Preserve task-specific causal TDD and remediation rules**

If the active task receives `CHANGES_REQUIRED`:

```text
finding inside frozen write-set/authority -> SOL focused regression RED -> minimal forward patch -> hosted gates -> same-role delta review
finding requires third path/new public seam/new owner/workflow/dependency/schema -> BLOCKED — SOL_REASONING_REQUIRED
```

No Luna relay is required for the first case; no scope improvisation is allowed for the second.

---

### Task 4: Operationalize exact-head auto-merge and immediate successor activation

**Files:** none

**Interfaces:**
- Consumes: one re-epoched task at STOP_WRITE/FINAL_REVIEW, exact hosted evidence, paired reviewer verdicts.
- Produces: deterministic merge/no-merge decision plus immediate fresh-main successor activation.

- [ ] **Step 1: Build the exact merge tuple from fresh evidence**

For each merge candidate collect:

```text
current main
expected base or allowed lineage rule
PR base ref/SHA
PR head ref/SHA
merge-base
cumulative changed paths
hosted tests conclusion
reuse/architecture conclusion
REVIEWER_INTEGRATION exact-head verdict
REVIEWER_SECURITY exact-head verdict
unresolved blocking thread count
head SHA after the latest reviewer verdict
material invalidators from the controlling task decision
```

- [ ] **Step 2: Apply the gate as an all-of predicate**

Merge is permitted only if every statement is true:

```text
base/lineage rule satisfied
exact head == both reviewed heads
changed paths == authorized write-set
hosted tests == PASS
reuse/architecture == PASS
REVIEWER_INTEGRATION == PASS
REVIEWER_SECURITY == PASS
unresolved blockers == 0
head drift after reviews == false
material invalidator == false
```

Any false/unknown value means `NO_MERGE`.

- [ ] **Step 3: Auto-merge without a Human relay only after the full gate**

Use the repository's authorized normal merge method. Do not squash/rebase/force-push where prohibited.

- [ ] **Step 4: Fresh-read main immediately after merge**

Verify:

```text
expected merge is integrated/reachable
fresh current main exact SHA
no unexpected competing merge invalidates downstream assumptions
```

- [ ] **Step 5: Classify downstream freshness before activating the successor**

Apply task/domain-specific rules. In particular, never weaken:

```text
R5 FAIL -> R6 mutation -> post-repair custody/currentness -> fresh R3 -> proper R4 new/final candidate/current selection -> NEW independent R5 PASS -> R7 -> R8
```

Then activate the next executable successor in the same control cycle. A successful merge with no next owner/action is a `ZERO_SILENT_BATON` defect.

---

### Task 5: Enforce independent audit when SOL is also the writer

**Files:** none

**Interfaces:**
- Consumes: exact STOP_WRITE head, frozen task oracle, hosted evidence.
- Produces: two independent exact-head reviewer terminals that cannot be replaced by SOL self-review.

- [ ] **Step 1: Run SOL pre-review self-audit without granting it independent authority**

Minimum checklist:

```text
exact cumulative diff/write-set
owner/public-seam reuse
hostile/malformed input coverage where relevant
replay/concurrency where relevant
privacy-safe categorical failures
deterministic identity/hash requirements
stale/freshness semantics
no authority minting/leakage
focused/affected tests
likely reviewer oracle failures
```

Record self-audit only as writer evidence.

- [ ] **Step 2: Route REVIEWER_INTEGRATION and REVIEWER_SECURITY in parallel**

Both reviewers receive the same exact head and frozen oracle. Neither receives write authority.

Integration reviewer focuses on:

```text
lineage + write-set + architecture/reuse + dependency/workflow/schema/fixture drift + affected regressions + hosted evidence + unresolved threads
```

Security reviewer focuses on:

```text
authority/provenance + fail-closed semantics + hostile structures + replay/concurrency + tamper + privacy + capability separation + stale evidence + mutation/cleanup ambiguity
```

- [ ] **Step 3: Reject self-certification explicitly**

A merge packet is invalid if either independent reviewer verdict is absent, stale, bound to a different head, or authored as a replacement by the task writer itself.

---

### Task 6: Enforce signal-only Human visibility and zero-silent-baton behavior

**Files:** none

**Interfaces:**
- Consumes: internal project transitions.
- Produces: compact Human-visible signals only for material transitions; continuous internal progression otherwise.

- [ ] **Step 1: Use exactly the material signal classes**

User-visible messages are limited to:

```text
✅ MERGED — <task/PR>, current main <sha>, successor <task>
🚧 BLOCKED / CHANGES_REQUIRED — <material blocker>, current owner <owner>
🔁 FRONTIER MOVED — <old frontier> -> <new frontier>
🖥️ LOCAL/AUTOCAD GATE READY — <exact local objective>
👤 HUMAN ACTION REQUIRED — <specific action that cannot be delegated>
```

Routine RED/GREEN/CI-start/reviewer-routing transitions remain internal unless they become material blockers.

- [ ] **Step 2: Detect zero-silent-baton as a defect, not a waiting state**

On every control transition ask:

```text
Does executable authority exist?
If yes, is a writer, reviewer, CI job, Human action, or genuine external dependency actually in flight?
```

If the first answer is yes and the second is no, immediately resume, route, or escalate; do not report a passive waiting state.

- [ ] **Step 3: Work-steal N+1/N+2 only across independent boundaries**

While N waits on real CI/reviewer/external gates:

```text
N   = CI/final review
N+1 = PATCH_READY or equivalent
N+2 = CONTRACT_READY
N+3 = RESEARCHED
```

Never use work-stealing to create two writers on the same task/branch.

---

### Task 7: Validate the rollout on the first two frontier transitions and keep rollback explicit

**Files:** none under this governance task

**Interfaces:**
- Consumes: first two active-task transitions performed under Operating Model 1.0.
- Produces: evidence that the model reduced handoff latency without weakening audit; a deterministic rollback path if it did not.

- [ ] **Step 1: For each of the first two migrated tasks, record the control-plane timestamps/ordering**

Record only governance timing/evidence:

```text
hosted-terminal observed
reviewers routed
paired reviewer terminal observed
merge disposition
merge completed
successor activated
number of Luna relays used for offline GitHub work
number of Human relays used for routine GitHub work
```

Do not add a persistent production telemetry subsystem.

- [ ] **Step 2: Apply the 10/10 KPI audit**

Both transitions should satisfy:

```text
idle baton = 0 observed control gaps
duplicate architecture discovery = 0 unnecessary Luna rediscovery rounds
independent audit = 100%
scope integrity = 100%
forward-history discipline = 100%
freshness classification performed after every merge
Human relay for routine offline GitHub work = 0
```

A reviewer finding an authority/public-seam blocker that SOL reasonably should have found pre-GREEN is recorded as a SOL pre-code quality defect and fed into the next task's pre-code checklist.

- [ ] **Step 3: Roll back governance prospectively if audit independence or authority integrity regresses**

Rollback mechanism:

```text
post a new canonical #131 decision superseding Operating Model 1.0 for new work;
freeze auto-merge;
restore Luna or another bounded executor as primary writer where needed;
retain all historical docs/comments/commits;
do not rewrite history;
do not retroactively reinterpret already-authorized task decisions.
```

The repository design/plan remain historical evidence; authority changes only through a later canonical control-plane decision.

---

## Plan Self-Review Coverage Matrix

| Approved design requirement | Implemented by |
|---|---|
| SOL primary offline executor | Tasks 2–3 |
| Independent integration + security review | Task 5 |
| Signal-only visibility | Task 6 |
| Full exact-head auto-merge | Task 4 |
| Main movement / re-epoch | Tasks 1–4 |
| No retroactive authority broadening | Tasks 2–3 |
| Luna local/failover only | Tasks 2–3 |
| Zero-silent-baton | Tasks 4, 6 |
| Work stealing N+1/N+2 | Task 6 |
| Human/live gates preserved | Global Constraints, Tasks 2–4 |
| R5/R6/R7/R8 freshness ordering preserved | Global Constraints, Task 4 |
| 10/10 KPI/self-audit | Task 7 |
| Forward-only rollback | Tasks 1, 7 |

## Rollout Completion Oracle

Operating Model 1.0 is considered operationally adopted only when all are true:

```text
governance design + implementation plan merged to main
canonical #131 adoption decision exists exactly once and is not superseded
at least one active task has been explicitly re-epoched under Operating Model 1.0
no dual-writer race occurred during migration
independent reviewer gates remain mandatory and exact-head-bound
a full-gate eligible task auto-merges without routine Human/Luna relay
post-merge fresh-main + freshness classification + successor activation happen in the same control cycle
```

A docs merge alone is not sufficient to claim operational adoption.