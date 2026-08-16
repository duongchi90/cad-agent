# Luna Event-Driven Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Luna orchestration latency, duplicate agent work, silent actionable batons, and post-GREEN architecture surprises while preserving GitHub as the sole source of truth and preserving every existing repository, review, merge, live, and authority gate.

**Architecture:** Use GitHub-native observation through the existing Luna watchdog. Each scan fresh-reads canonical GitHub state, derives a non-authoritative normalized observation and deterministic fingerprint, and reacts only to material state transitions. Default rollout requires zero new runtime/workflow/database code; a tiny pure-Python classifier is permitted only under a future separately authorized issue if measured operational rollout proves deterministic local logic is insufficient.

**Tech Stack:** Existing GitHub issue/PR/actions/review APIs and Luna orchestration; existing repository verification surfaces (`scripts/verify.ps1`, `scripts/check_architecture_boundaries.py`, `scripts/check_reuse_declaration.py`, `scripts/reuse_inventory.py`, focused pytest/.NET tests, Ruff, `git diff --check`). Conditional future helper, if separately authorized: Python 3.11 + pytest only, no new dependency.

## Global Constraints

- Issue #187 is **PLANNING ONLY**. This document does not authorize production/runtime implementation.
- Current planning epoch is `ff93ddaa2ebb69e21f81baaa4f3dceec1db009ae`; newer #131/Owner/SOL control always wins.
- Exact #187 planning write-set is only:
  - `docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md`
  - `docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md`
- No third planning path, workflow, dependency, runtime, schema, database, queue, daemon, webhook service, AutoCAD/File-IPC/provider/private/customer/publication/system mutation.
- GitHub remains the sole source of truth and authority. Luna cache/fingerprints are advisory indexes only.
- Human Owner > SOL > Luna/Codex Desktop authority remains unchanged.
- `REVIEWER_INTEGRATION` and `REVIEWER_SECURITY` remain independent STRICT READ ONLY reviewer roles.
- Token optimization applies to Luna discovery/reconstruction and duplicate ephemeral spawns, not to required transition communication, Master Audit depth, or persistent R3/R4/R5/R6 specialist analysis.
- One active production writer remains required for overlapping write-sets.
- Existing exact-main pins, STOP_WRITE, RED-first, hosted CI/reuse, independent review, merge, live, and publication gates remain binding.
- A material transition may accelerate an already-authorized action; it never creates authority.
- No implementation or merge from this plan may occur while an exact-main local gate forbids main movement.

---

## File Structure and Rollout Boundary

### Current #187 planning deliverables

- `docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md` — selected architecture, state model, authority boundaries, algorithms, KPI definitions, failure behavior.
- `docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md` — this executable rollout/conditional-implementation plan.

### Default operational rollout

Repository production files changed: **NONE**.

The first implementation is behavioral/orchestration-only: Luna applies the design while continuing to fresh-read GitHub and using the existing watchdog. No repository cache file, workflow, daemon, database, or persistent truth record is added.

### Conditional future helper write-set

A repository helper is **not required by default**. If the KPI trial in Task 9 meets the escalation condition, SOL must create a new bounded implementation issue before any code write. The recommended exact two-path future write-set is:

- Create: `scripts/control_plane_state.py`
- Create: `tests/test_control_plane_state.py`

No workflow/dependency/schema/store file is allowed in that future first slice. The helper must remain pure/offline: it receives already-fetched normalized data and emits advisory classification only. It must not call GitHub, spawn agents, write comments, merge, or authorize anything.

---

### Task 1: Establish the Fresh Observation Contract

**Files:**
- Repository production files: none.
- Durable authority/evidence remains GitHub issues/PRs/actions/reviews.

**Interfaces:**
- Consumes: actual `main`; newest controlling #131/Owner/SOL decision; active issue/PR metadata; exact PR head/synthetic-or-state; hosted CI/reuse terminal states; independent reviewer terminal states; current baton fields.
- Produces: one in-memory normalized observation with `current_main`, `authority_epoch`, task/PR identity, CI/review state, blocker, next owner, next trigger, and material fingerprint input fields.

- [ ] **Step 1: Fresh-read authority first**

For each normal Luna scan, read in this order:

```text
1. actual refs/heads/main
2. newest controlling #131 / Owner / SOL packet
3. only active task/issue/PR objects implicated by that packet
4. exact current PR head + synthetic-or-state
5. hosted CI/reuse terminal state when applicable
6. independent review terminal state when applicable
```

Do not use chat memory, prior summaries, cached SHAs, or cached verdicts as authority.

- [ ] **Step 2: Normalize the observation**

Construct only this advisory shape in Luna workspace/session memory:

```json
{
  "current_main": "<fresh-sha>",
  "authority_epoch": "<issue/comment-id>",
  "task_or_issue": "<stable-id>",
  "pr_number": 0,
  "pr_head": "<sha-or-NONE>",
  "synthetic_or_state": "<sha-or-closed-token>",
  "ci_tests": "PENDING|SUCCESS|FAILURE|NOT_APPLICABLE",
  "ci_reuse": "PENDING|SUCCESS|FAILURE|NOT_APPLICABLE",
  "review_integration": "PENDING|PASS|CHANGES_REQUIRED|NOT_REQUIRED",
  "review_security": "PENDING|PASS|CHANGES_REQUIRED|NOT_REQUIRED",
  "current_owner": "<canonical-role>",
  "next_trigger": "<normalized-trigger>",
  "blocker": null
}
```

No private CAD data, secrets, raw evidence payloads, or authority claims belong in this object.

- [ ] **Step 3: Fail closed on reconstruction uncertainty**

If a required field cannot be fresh-resolved, classify the scan as:

```text
OBSERVATION_INCOMPLETE
ACTIONABILITY=BLOCKED
MISSING=<exact missing GitHub evidence>
```

Do not fill the field from memory.

- [ ] **Step 4: Verify the observation can be rebuilt with cache deleted**

Delete/ignore the advisory observation and perform one fresh reconstruction. Success means every field used for actionability is recoverable from GitHub/current local authority without a second truth store.

---

### Task 2: Enforce Deterministic Fingerprints and No-Event/No-Agent

**Files:**
- Repository production files: none in default rollout.

**Interfaces:**
- Consumes: normalized observation from Task 1.
- Produces: deterministic ephemeral-task fingerprint and decision `NO_ACTION`, `REJOIN_HANDLE`, or `MATERIAL_TRANSITION`.

- [ ] **Step 1: Build the canonical task tuple**

Use exactly:

```text
(role,
 task_or_issue,
 current_main,
 pr_head,
 synthetic_or_state,
 authority_epoch,
 intended_output)
```

Allowed `intended_output` classes:

```text
WRITE_RED
WRITE_GREEN
REVIEW
MERGE_DECISION
LOCAL_PREFLIGHT
STATUS_ONLY
```

- [ ] **Step 2: Canonically serialize**

Normalize absent values as literal `NONE`; normalize role labels to canonical names; normalize object keys/order before hashing. Hash with SHA-256 when a compact identifier is useful.

- [ ] **Step 3: Apply no-event/no-agent**

Decision table:

```text
same fingerprint + valid correct-role in-flight handle -> REJOIN_HANDLE
same fingerprint + equivalent terminal already durable on GitHub -> NO_ACTION
same fingerprint + no new material evidence -> NO_ACTION
changed fingerprint -> MATERIAL_TRANSITION
```

A scheduler tick or elapsed time alone must never spawn a fresh expensive ephemeral role.

- [ ] **Step 4: Verify stale evidence is not promoted**

Take an unchanged role/task but change only `current_main`, `pr_head`, or `authority_epoch`. Expected result: fingerprint changes; prior verdict/terminal cannot be treated as current.

---

### Task 3: Classify Material Transitions and Act in the Same Cycle

**Files:**
- Repository production files: none in default rollout.

**Interfaces:**
- Consumes: previous advisory observation, fresh current observation, controlling GitHub authority.
- Produces: one transition class and one actionability result.

- [ ] **Step 1: Restrict transition classes**

Use only:

```text
PR_HEAD_CHANGED
SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED
HOSTED_CI_TERMINAL_CHANGED
WRITER_STOP_WRITE_OR_TERMINAL
REVIEWER_TERMINAL_CHANGED
ACTUAL_MERGE
AUTHORITY_EPOCH_CHANGED
```

A new class requires explicit SOL design delta; do not grow the set opportunistically.

- [ ] **Step 2: Produce compact transition classification**

For every material change, derive:

```text
TRANSITION=<class>
OLD_FINGERPRINT=<hash-or-NONE>
NEW_FINGERPRINT=<hash>
AUTHORITY_EPOCH=<issue/comment>
ACTIONABILITY=AUTHORIZED|BLOCKED|OBSERVE_ONLY
PRIMARY_NEXT_OWNER=<role>
NEXT_TRIGGER=<exact trigger>
```

- [ ] **Step 3: Execute already-authorized work immediately**

If `ACTIONABILITY=AUTHORIZED`, route/start the exact bounded action in the same scan. Do not wait for another scheduled scan merely to rediscover the same transition.

Examples:

```text
hosted GREEN + explicit review route -> start/rejoin reviewers
paired PASS + explicit expected-head merge preauthorization + no pin -> SOL merge decision in same cycle
actual merge -> capture merge SHA and re-epoch/activate eligible successor in same cycle
```

- [ ] **Step 4: Persist one exact blocker when not authorized**

If action is blocked, durable control communication must name:

```text
BLOCKER_OWNER
MISSING_PREREQUISITE
NEXT_TRIGGER
AUTHORITY_EPOCH
```

Do not post generic repeated `WAIT` messages.

---

### Task 4: Enforce ZERO-SILENT-BATON and Detect CONTROL_PLANE_DEADLOCK

**Files:**
- Repository production files: none in default rollout.

**Interfaces:**
- Consumes: transition result and current control packet.
- Produces: explicit baton state or deadlock classification.

- [ ] **Step 1: Require the four-field baton**

Every role-ending material transition must resolve:

```text
BATON_STATE=(current_owner, executable_action_or_blocker, next_trigger, authority_epoch)
```

- [ ] **Step 2: Reject silent terminal transitions**

A writer `STOP_WRITE`, reviewer terminal, CI terminal, merge, or local terminal without an explicit next owner/action or blocker is a `ZERO_SILENT_BATON_VIOLATION`.

- [ ] **Step 3: Detect actionable deadlock**

Classify `CONTROL_PLANE_DEADLOCK` only when all are true:

```text
1. baton names an executable action
2. required authority/evidence is fresh and already present
3. no writer/main/epoch/live lock forbids action
4. action is neither started/routed nor represented by a valid in-flight handle
5. next watchdog scan sees the same actionable baton unchanged
```

- [ ] **Step 4: Recover within the watchdog scan**

On confirmed deadlock, report the defect compactly and perform the already-authorized action in that same scan.

Do not classify true external waits, exact-main HOLDs, CI/reviewer in-flight states, Luna local-machine prerequisites, or explicit Human gates as deadlock.

---

### Task 5: Route Independent Review Without Duplicate Contexts

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: exact review-required tuple and existing correct-role reviewer handle state.
- Produces: fresh `REVIEWER_INTEGRATION` and/or `REVIEWER_SECURITY` review starts or re-joins.

- [ ] **Step 1: Use canonical reviewer labels**

Do not route legacy `Cell3`/`Cell5` labels in new control packets. Use:

```text
REVIEWER_INTEGRATION
REVIEWER_SECURITY
```

- [ ] **Step 2: Parallelize paired review**

When both are required and exact tuple is ready, route both in the same transition cycle.

- [ ] **Step 3: Rejoin bounded repair review**

For a repair on the same task, reuse the existing correct-role reviewer context when available, but require a fresh read and a fresh verdict for the new tuple.

- [ ] **Step 4: Refuse verdict reuse across tuple change**

A prior PASS is historical if head, main, synthetic, or controlling authority epoch moved in a way that invalidates the review contract.

---

### Task 6: Make N+1 `PATCH_READY` and Audit REQUIRED_PUBLIC_SEAMS Before RED

**Files:**
- Repository production files: none unless a separately authorized phase writer later acts.

**Interfaces:**
- Consumes: current phase N accepted/public owner seams and next phase N+1 requirements.
- Produces: `PATCH_READY`, `ONLY_LATE_BINDINGS_PENDING`, or an exact architecture blocker before downstream RED.

- [ ] **Step 1: Record REQUIRED_PUBLIC_SEAMS**

Before authorizing downstream RED, record each consumed seam as:

```text
REQUIRED_PUBLIC_SEAMS:
- owner/subsystem: <canonical owner>
  public_symbol_or_contract: <exact public seam>
  accepted_source_or_merge_identity: <sha/issue/contract>
  downstream_use: <one bounded use>
  missing_or_ambiguous: NO
```

If any item is private-only, speculative, duplicated, or missing, set `missing_or_ambiguous: YES` and block downstream RED.

- [ ] **Step 2: Prepare N+1 without speculative symbol binding**

Close write-set, adversarial matrix, owner boundaries, migration/rollback, and test shape while upstream exact symbols/SHA are still moving.

- [ ] **Step 3: Use only the two readiness terminals**

```text
PATCH_READY
ONLY_LATE_BINDINGS_PENDING
```

Do not call dependency preparation complete at a merely generic planning state when more safe work is possible.

- [ ] **Step 4: Measure architecture leakage**

Any owner/public-seam blocker first discovered after GREEN increments `post_green_architecture_blocker_leakage`. Target: zero.

---

### Task 7: Compose the Pre-Push GREEN Owner-Contract Bundle From Existing Checks

**Files:**
- No new verifier file by default.
- Reuse existing repository scripts/tests.

**Interfaces:**
- Consumes: changed-path allowlist and REQUIRED_PUBLIC_SEAMS list.
- Produces: local pre-push evidence only; hosted CI/reuse remains mandatory final evidence.

- [ ] **Step 1: Run focused slice tests**

Run the exact RED/GREEN tests owned by the slice. Expected before first GREEN push: all intended GREEN tests pass locally.

- [ ] **Step 2: Run upstream owner contract tests**

For each REQUIRED_PUBLIC_SEAMS owner, run the focused accepted tests that exercise the consumed public seam.

- [ ] **Step 3: Run static/architecture/reuse checks**

Where applicable:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check <changed-python-paths>
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
.\.venv-py311\Scripts\python.exe scripts/check_reuse_declaration.py <appropriate-arguments-from-current-repo-contract>
git diff --check
```

Use current repository-supported arguments; do not invent a second checker.

- [ ] **Step 4: Run canonical verifier when the slice requires it**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

- [ ] **Step 5: Preserve hosted final gates**

Local GREEN bundle success never substitutes for hosted tests/reuse or independent review.

---

### Task 8: Derive Cycle-Time KPIs From Existing GitHub Evidence

**Files:**
- No project database or metrics store.

**Interfaces:**
- Consumes: GitHub issue/PR/review/action timestamps and Luna routing metadata.
- Produces: per-cycle metric values or literal unavailable values.

- [ ] **Step 1: Derive required durations**

Compute when timestamps exist:

```text
writer_unlock_to_STOP_WRITE
STOP_WRITE_to_CI_terminal
STOP_WRITE_to_review_start
CI_terminal_to_reviewer_terminal
paired_PASS_to_merge
merge_to_successor_activation
```

- [ ] **Step 2: Count quality/control defects**

Track:

```text
actionable_baton_idle_cycles
control_plane_deadlocks
post_GREEN_architecture_blockers
review_repair_cycles
duplicate_ephemeral_spawns
```

- [ ] **Step 3: Track Luna discovery-token share without constraining other roles**

Record Luna discovery/reconstruction token or context share only when the product surface exposes a reliable value. If unavailable, report `NOT_MEASURABLE` rather than estimate.

Do not apply token caps to Master Audit or persistent R3/R4/R5/R6 specialist reasoning.

- [ ] **Step 4: Use GitHub comments for bounded summaries only**

Post compact KPI summaries at meaningful cycle boundaries when useful. Do not create a second long-lived KPI database.

Targets:

```text
control_plane_deadlocks = 0
post_GREEN_architecture_blockers = 0
actionable_baton_idle_cycles = 0 when action was already authorized
```

Other latency metrics are trend metrics: improve without weakening gates.

---

### Task 9: Run a No-Code Operational Trial Before Authorizing Any Helper

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: three or more real material transitions observed under the selected architecture.
- Produces: `NO_CODE_SUFFICIENT` or `HELPER_JUSTIFIED` decision evidence.

- [ ] **Step 1: Observe at least three transition classes**

Use naturally occurring project transitions; do not create synthetic repository churn. The sample should include at least three distinct classes from Task 3 when available.

- [ ] **Step 2: For each sampled transition record**

```text
transition class
fresh authority epoch
old/new fingerprint identity
whether duplicate agent spawn was avoided
actionability classification
whether same-cycle action occurred
baton completeness
deadlock result
```

- [ ] **Step 3: Declare no-code sufficient when all are true**

```text
material transition classification is deterministic
no duplicate equivalent spawn occurs
no actionable baton remains idle for a later scan
no authority is inferred from cache
cache loss is recovered by fresh-read
control_plane_deadlocks = 0
```

Terminal:

```text
#187 OPERATIONAL TRIAL — NO_CODE_SUFFICIENT
```

- [ ] **Step 4: Justify a helper only on reproducible deterministic-logic failure**

A future helper may be proposed only when the trial records a reproducible ambiguity/duplication/deadlock caused by repeated local fingerprint/transition logic that a pure deterministic helper would remove. Latency caused solely by the normal watchdog interval is not enough by itself to justify a new repository helper or workflow.

Terminal:

```text
#187 OPERATIONAL TRIAL — HELPER_JUSTIFIED
REPRODUCIBLE_CLASS=<exact class>
WHY_EXISTING_LUNA_LOGIC_IS_INSUFFICIENT=<bounded reason>
```

---

### Task 10: Conditional Future RED-First Pure Helper — Only After a New Issue Authorizes It

**Files:**
- Create: `tests/test_control_plane_state.py`
- Create after meaningful RED: `scripts/control_plane_state.py`

**Interfaces:**
- Consumes: already-fetched plain dictionaries; no network/API/service access.
- Produces: pure normalized observation/fingerprint/transition/deadlock results only.

This task is **not authorized by #187 itself**. Execute only after `HELPER_JUSTIFIED` plus a separately issued SOL/Owner implementation issue with exact base, writer, two-path allowlist, RED-first and review requirements.

- [ ] **Step 1: Write the RED tests first**

Tests must import these proposed pure functions:

```python
normalize_observation(payload: object) -> dict[str, object]
task_fingerprint(*, role: str, task_or_issue: str, current_main: str,
                 pr_head: str, synthetic_or_state: str,
                 authority_epoch: str, intended_output: str) -> str
classify_material_transition(previous: dict[str, object],
                             current: dict[str, object]) -> str | None
detect_control_plane_deadlock(payload: object) -> bool
```

Cover at minimum:

```text
identical observation -> no transition
main change -> SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED or authority-valid specific class
PR head change -> PR_HEAD_CHANGED
authority epoch-only change -> AUTHORITY_EPOCH_CHANGED
CI pending->success/failure -> HOSTED_CI_TERMINAL_CHANGED
review terminal change -> REVIEWER_TERMINAL_CHANGED
actual merge -> ACTUAL_MERGE
malformed/unknown fields -> fail closed
canonical fingerprint stable across input dict key order
fingerprint changes on main/head/synthetic/authority/intended-output change
true actionable idle baton -> deadlock True
pinned-main hold / CI in-flight / reviewer in-flight / local prerequisite -> deadlock False
```

- [ ] **Step 2: Run RED and prove causal failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_control_plane_state.py -q -p no:cacheprovider
```

Expected RED: collection/import or function-missing failures attributable only to the absent helper implementation. Existing production files remain untouched.

- [ ] **Step 3: Route RED evidence if the future issue requires pre-GREEN review**

Freeze production after meaningful RED and obtain the exact independent RED gate required by that future issue. No GREEN write before authorization.

- [ ] **Step 4: Implement the minimum pure helper**

`scripts/control_plane_state.py` must use only Python standard library functionality such as `json`, `hashlib`, `dataclasses`/typing where useful. It must not import GitHub clients, subprocess, AutoCAD/File IPC, network, filesystem persistence, agent APIs, or merge/review/write functionality.

Unknown fields and malformed enums fail closed with a dedicated value/error; the helper never returns authorization.

- [ ] **Step 5: Run focused GREEN**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_control_plane_state.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check scripts/control_plane_state.py tests/test_control_plane_state.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
```

Expected: all focused tests PASS, Ruff PASS, architecture PASS, diff-check PASS.

- [ ] **Step 6: Verify exact two-path write-set**

```text
scripts/control_plane_state.py
tests/test_control_plane_state.py
```

Any third path requires STOP/REBASELINE.

- [ ] **Step 7: Push once after local owner-contract bundle**

Hosted tests/reuse and independent Integration/Security review remain required by the future implementation issue. Do not infer acceptance from local GREEN.

---

### Task 11: Review, Rollout, and Rollback Rules

**Files:**
- Current #187: two planning docs only.
- Conditional future helper: only the two paths in Task 10 after separate authority.

**Interfaces:**
- Consumes: planning review or future implementation review evidence.
- Produces: accepted planning, operational rollout, or safe rollback.

- [ ] **Step 1: Independently review #187 planning**

Reviewers verify:

```text
reuse-first architecture
no second truth/authority/store/scheduler
no workflow/dependency/runtime scope creep
exact fingerprint and material transition semantics
ZERO-SILENT-BATON/deadlock definitions
reviewer role/handle behavior
preauthorization cannot invent authority
N+1/public-seam rules
KPI derivation and token-policy boundary
future RED-first helper is conditional and separately gated
```

- [ ] **Step 2: Keep planning PR unmerged while exact-main pin forbids movement**

A planning PASS does not override the current local Gate-1G main pin. Merge only after fresh SOL anti-race/re-epoch authority explicitly permits main movement.

- [ ] **Step 3: Operational rollback is cache discard**

If event/fingerprint logic becomes inconsistent:

```text
discard advisory observation/cache
perform full fresh GitHub reconstruction
fall back to normal watchdog behavior
spawn no action until authority is freshly resolved
```

No repository rollback is needed for the default no-code rollout.

- [ ] **Step 4: Conditional helper rollback is forward revert**

If a future pure helper is merged and later fails, revert its bounded commit under normal repository governance. Luna falls back to fresh-read watchdog semantics; no authority data is lost because the helper owns no authoritative state.

---

## Acceptance Matrix

The #187 planning output is complete only when all rows are satisfied:

```text
Reuse map of GitHub/Luna/repository checks               REQUIRED
2-3 alternatives + selected minimal architecture         REQUIRED
Exact observation/fingerprint/transition schema          REQUIRED
Authority boundary / no-second-truth proof               REQUIRED
No-event/no-agent algorithm                              REQUIRED
ZERO-SILENT-BATON + CONTROL_PLANE_DEADLOCK               REQUIRED
Reviewer role + bounded handle reuse                      REQUIRED
Conditional SOL preauthorization constraints             REQUIRED
N+1 PATCH_READY / ONLY_LATE_BINDINGS_PENDING              REQUIRED
REQUIRED_PUBLIC_SEAMS pre-RED audit                       REQUIRED
Pre-push GREEN owner-contract bundle                      REQUIRED
KPI derivation rules                                      REQUIRED
Master Audit + R3-R6 explicitly not token-limited         REQUIRED
No-code operational trial before helper                   REQUIRED
Conditional RED-first exact future write-set              REQUIRED
Rollback/fallback                                         REQUIRED
AutoCAD/File-IPC/private/provider/system                   NOT AUTHORIZED
Workflow/dependency/daemon/database                       NOT AUTHORIZED
Production implementation under #187                     NOT AUTHORIZED
```

## Planning Completion Terminal

When this exact two-doc planning branch has hosted evidence and independent planning review, SOL should record:

```text
#187 PLANNING — REPOSITORY_ACCEPTED / HOLD
DESIGN=<exact path/head>
PLAN=<exact path/head>
SELECTED_ARCHITECTURE=GITHUB_NATIVE_PLUS_EXISTING_LUNA_WATCHDOG
DEFAULT_IMPLEMENTATION=NO_NEW_REPOSITORY_RUNTIME
CONDITIONAL_FUTURE_HELPER=SEPARATE_ISSUE_REQUIRED
MAIN_MOVEMENT=NOT_AUTHORIZED_WHILE_GATE_PIN_ACTIVE
```

Planning acceptance does not itself authorize Task 10, any runtime implementation, or a merge while a controlling exact-main pin is active.