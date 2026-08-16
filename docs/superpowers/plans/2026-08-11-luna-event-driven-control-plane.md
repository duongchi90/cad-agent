# Luna Event-Driven Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Luna orchestration latency, duplicate role work, silent actionable batons, and post-GREEN architecture surprises while keeping GitHub as the sole source of truth and preserving every existing repository, review, merge, live, and authority gate.

**Architecture:** Use the existing Luna watchdog and GitHub control bus. Each scan builds a canonical `MATERIAL_STATE_PROJECTION` for event detection and a separate `TASK_FINGERPRINT` for duplicate role-work suppression. Material changes are classified before de-duplication; a same task fingerprint can never hide a CI, reviewer, writer, merge, main/head/synthetic, baton, or authority transition.

**Tech Stack:** Existing GitHub issue/PR/actions/review APIs and Luna orchestration; existing repository verification surfaces (`scripts/verify.ps1`, `scripts/check_architecture_boundaries.py`, `scripts/check_reuse_declaration.py`, `scripts/reuse_inventory.py`, focused pytest/.NET tests, Ruff, `git diff --check`). Conditional future helper, only under a separate issue: Python 3.11 + pytest, no new dependency.

## Global Constraints

- Issue #187 is **PLANNING ONLY**. This plan does not authorize production/runtime implementation.
- Planning epoch is `ff93ddaa2ebb69e21f81baaa4f3dceec1db009ae`; newer #131 / Human Owner / SOL control always wins.
- Human Owner written-spec approval is recorded at #187 comment `5306410590`.
- Exact #187 planning write-set is only:
  - `docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md`
  - `docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md`
- No third planning path, workflow, dependency, runtime, schema, database, queue, daemon, webhook service, AutoCAD/File-IPC/provider/private/customer/publication/system mutation.
- GitHub remains the sole source of truth and authority. Luna observation/cache/fingerprints are advisory only.
- Human Owner > SOL > Luna/Codex Desktop authority remains unchanged.
- `REVIEWER_INTEGRATION` and `REVIEWER_SECURITY` remain independent STRICT READ ONLY reviewer roles.
- Existing exact-main pins, STOP_WRITE, RED-first, hosted CI/reuse, independent review, merge, live, and publication gates remain binding.
- A material transition may accelerate an already-authorized action; it never creates authority.
- `MATERIAL_STATE_FINGERPRINT` and `TASK_FINGERPRINT` are separate contracts and SHALL NOT be overloaded into one hash.

---

## File Structure and Rollout Boundary

### Current #187 deliverables

- `docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md` — authoritative planning design.
- `docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md` — this rollout/conditional-implementation plan.

### Default rollout

Repository production files changed: **NONE**.

Luna applies the design behavior inside the existing watchdog/orchestration flow. No repository cache file, workflow, daemon, database, persistent truth record, or new scheduler is added.

### Conditional future helper

Only if Task 9's measured trial meets the escalation condition, SOL creates a **separate implementation issue** before code writes. Recommended exact future write-set:

- Create: `scripts/control_plane_state.py`
- Create: `tests/test_control_plane_state.py`

The helper must be pure/offline and advisory. It may receive normalized data and return projections, fingerprints, transition sets, and de-dup decisions. It must not call GitHub/network, spawn agents, write comments, merge, mutate repository state, or authorize anything.

---

### Task 1: Fresh Observation Contract

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: current main; newest controlling authority packet; active issue/PR identity; exact PR head/synthetic/current state; hosted CI/reuse; reviewer terminals; writer state/terminal; baton.
- Produces: one advisory observation with `observed_at`, canonical `material_state`, `material_state_fingerprint`, and optional task fingerprints.

- [ ] **Step 1: Fresh-read authority and currentness in fixed order**

```text
1. actual refs/heads/main
2. newest controlling #131 / Human Owner / SOL decision
3. active issue/PR implicated by that decision
4. exact PR head + synthetic-or-state + merged/merge-SHA
5. hosted tests/reuse current terminal state when applicable
6. Integration/Security current exact-head terminal state when applicable
7. writer STOP_WRITE/terminal state when applicable
8. baton owner/next-trigger/blocker
```

Chat memory, prior summaries, cached SHA, and cached verdict are not authority.

- [ ] **Step 2: Normalize observation-only versus material state**

Use this shape conceptually:

```json
{
  "observed_at": "2026-08-16T08:00:00Z",
  "material_state": {
    "current_main": "<sha>",
    "authority_epoch": "<issue/comment>",
    "task_or_issue": "<stable-id>",
    "pr": {
      "number": 263,
      "head": "<sha-or-NONE>",
      "synthetic_or_state": "<sha-or-state>",
      "draft": true,
      "merged": false,
      "merge_sha": "NONE"
    },
    "ci": {"tests": "SUCCESS", "reuse": "SUCCESS"},
    "reviews": {
      "REVIEWER_INTEGRATION": "PENDING",
      "REVIEWER_SECURITY": "PENDING"
    },
    "writer": {"state": "NONE", "terminal_id": "NONE"},
    "baton": {
      "current_owner": "Luna",
      "next_trigger": "CURRENT_EPOCH_TRANSPORT_PREFLIGHT",
      "blocker": "NONE"
    }
  }
}
```

`observed_at` is never copied into the canonical material projection.

- [ ] **Step 3: Fail closed on missing canonical evidence**

```text
OBSERVATION_INCOMPLETE
ACTIONABILITY=BLOCKED
MISSING=<exact missing canonical evidence>
```

Do not backfill from memory.

- [ ] **Step 4: Rebuild with cache deleted**

Ignore/delete the advisory observation and perform a fresh reconstruction. Every actionability field must be recoverable from GitHub/current delegated local authority.

---

### Task 2: Canonical Material-State Projection

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: Task 1 `material_state`.
- Produces: `MATERIAL_STATE_PROJECTION`, `MATERIAL_STATE_FINGERPRINT`, field-level diff.

- [ ] **Step 1: Project exactly these fields**

```text
current_main
authority_epoch
task_or_issue
pr.number
pr.head
pr.synthetic_or_state
pr.draft
pr.merged
pr.merge_sha
ci.tests
ci.reuse
reviews.REVIEWER_INTEGRATION
reviews.REVIEWER_SECURITY
writer.state
writer.terminal_id
baton.current_owner
baton.next_trigger
baton.blocker
```

- [ ] **Step 2: Explicitly exclude observation-only fields**

```text
observed_at
watchdog_scan_number
local clock
API latency
fetch duration
process id
cache path
non-controlling repeated comment timestamps
log ordering without terminal-identity change
```

- [ ] **Step 3: Canonicalize**

Rules:

```text
missing optional value -> literal NONE
enums -> closed canonical uppercase tokens
SHA -> exact lowercase Git SHA string as returned by canonical source
keys -> sorted deterministic order
serialization -> stable UTF-8 JSON/text form
hash -> SHA-256
```

- [ ] **Step 4: Apply material equality rule**

```text
old projection == new projection
    => NO_MATERIAL_TRANSITION
only excluded observation fields changed
    => NO_MATERIAL_TRANSITION
any projected field changed
    => build MATERIAL_TRANSITION_SET
```

- [ ] **Step 5: Verify clock-only adversary**

Use two observations identical except `observed_at`.

Expected:

```text
old MATERIAL_STATE_FINGERPRINT == new MATERIAL_STATE_FINGERPRINT
NO_MATERIAL_TRANSITION
```

---

### Task 3: Separate Ephemeral Task De-Dup Fingerprint

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: fresh exact tuple + intended role output.
- Produces: `TASK_FINGERPRINT` and `REJOIN_HANDLE | NO_DUPLICATE_SPAWN | SPAWN_OR_ROUTE`.

- [ ] **Step 1: Use exactly this task tuple**

```text
(role,
 task_or_issue,
 current_main,
 pr_head,
 synthetic_or_state,
 authority_epoch,
 intended_output)
```

Allowed `intended_output` values:

```text
WRITE_RED
WRITE_GREEN
REVIEW
MERGE_DECISION
LOCAL_PREFLIGHT
STATUS_ONLY
```

- [ ] **Step 2: Canonicalize and hash**

Use literal `NONE` for absent values, canonical role names, stable key order, SHA-256.

- [ ] **Step 3: Enforce ordering relative to material detection**

The required flow is:

```text
FIRST: compare MATERIAL_STATE_PROJECTION
THEN: classify material transition and authority
ONLY THEN: apply TASK_FINGERPRINT de-dup to role work
```

- [ ] **Step 4: Apply de-dup rules**

```text
same TASK_FINGERPRINT + valid correct-role in-flight handle
    => REJOIN_HANDLE
same TASK_FINGERPRINT + equivalent current terminal already durable
    => NO_DUPLICATE_SPAWN
same TASK_FINGERPRINT + no material change
    => NO_ACTION
changed TASK_FINGERPRINT + authorized role work required
    => SPAWN_OR_ROUTE
```

- [ ] **Step 5: Verify same-task/new-review adversary**

Keep all task tuple fields identical; change `reviews.REVIEWER_SECURITY` from `PENDING` to `CHANGES_REQUIRED` in material state.

Expected:

```text
TASK_FINGERPRINT unchanged
MATERIAL_STATE_FINGERPRINT changed
REVIEWER_TERMINAL_CHANGED detected
new security verdict consumed/currentness resolved
```

This proves task de-dup cannot hide an event.

---

### Task 4: Deterministic Material Transition Set

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: field-level diff between old/new material projections.
- Produces: ordered `TRANSITION_SET`, `PRIMARY_TRANSITION`.

- [ ] **Step 1: Use closed transition classes**

```text
AUTHORITY_EPOCH_CHANGED
ACTUAL_MERGE
PR_HEAD_CHANGED
SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED
WRITER_STOP_WRITE_OR_TERMINAL
HOSTED_CI_TERMINAL_CHANGED
REVIEWER_TERMINAL_CHANGED
BATON_CHANGED
```

- [ ] **Step 2: Map fields to classes**

```text
authority_epoch change
    -> AUTHORITY_EPOCH_CHANGED

pr.merged false->true OR merge_sha NONE->sha
    -> ACTUAL_MERGE

pr.head change
    -> PR_HEAD_CHANGED

current_main / synthetic_or_state / draft-state classification change
    -> SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED

writer.state enters STOP_WRITE/TERMINAL_* OR writer.terminal_id changes
    -> WRITER_STOP_WRITE_OR_TERMINAL

ci.tests OR ci.reuse state changes
    -> HOSTED_CI_TERMINAL_CHANGED

Integration OR Security canonical reviewer state changes
    -> REVIEWER_TERMINAL_CHANGED

baton owner / next_trigger / blocker changes
    -> BATON_CHANGED
```

- [ ] **Step 3: Apply stable precedence**

```text
1 AUTHORITY_EPOCH_CHANGED
2 ACTUAL_MERGE
3 PR_HEAD_CHANGED
4 SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED
5 WRITER_STOP_WRITE_OR_TERMINAL
6 HOSTED_CI_TERMINAL_CHANGED
7 REVIEWER_TERMINAL_CHANGED
8 BATON_CHANGED
```

All changed classes remain in `TRANSITION_SET`; precedence chooses processing order only.

- [ ] **Step 4: Verify simultaneous-change adversary**

Input change:

```text
ci.tests: PENDING -> SUCCESS
review_security: PENDING -> PASS
```

Expected:

```text
TRANSITION_SET=[HOSTED_CI_TERMINAL_CHANGED, REVIEWER_TERMINAL_CHANGED]
PRIMARY_TRANSITION=HOSTED_CI_TERMINAL_CHANGED
```

- [ ] **Step 5: Verify invalidating higher-precedence change**

Input change:

```text
pr.head changes
review_security changes to PASS
```

Expected:

```text
PR_HEAD_CHANGED processed first
prior/new review currentness checked against changed head
no stale PASS promotion
```

---

### Task 5: Authority Resolver and Same-Cycle Action

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: transition set, fresh controlling GitHub packet.
- Produces: `AUTHORIZED | BLOCKED | OBSERVE_ONLY`, next owner/action/trigger.

- [ ] **Step 1: Fresh-validate authority for every material transition**

Check:

```text
actual main/base
bound head/synthetic
writer lock/write-set
CI/review predicates
exact-main/local-live pin
explicit next owner/trigger
invalidators
```

- [ ] **Step 2: Produce compact decision**

```text
TRANSITION_SET=<ordered-set>
PRIMARY_TRANSITION=<class>
OLD_MATERIAL_FINGERPRINT=<hash>
NEW_MATERIAL_FINGERPRINT=<hash>
AUTHORITY_EPOCH=<issue/comment>
ACTIONABILITY=AUTHORIZED|BLOCKED|OBSERVE_ONLY
PRIMARY_NEXT_OWNER=<role>
NEXT_TRIGGER=<exact-trigger>
```

- [ ] **Step 3: Act in same cycle when already authorized**

If `AUTHORIZED`, route/start the bounded action in the same watchdog cycle unless a valid equivalent in-flight task handle exists.

- [ ] **Step 4: Fail closed on stale/missing packet**

If expected SHA/state moved, authority packet is absent, or a local/main pin forbids action:

```text
ACTIONABILITY=BLOCKED
BLOCKER=<one exact controlling prerequisite>
```

No detector output can override this.

---

### Task 6: Conditional SOL Preauthorization

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: explicit SOL/Human Owner control packet.
- Produces: bounded same-cycle successor action only when all predicates match.

- [ ] **Step 1: Require complete preauthorization packet**

It must state:

```text
exact current main/base
expected head condition
allowed action/write-set
required CI/review predicates
target action
material invalidators
action permitted when predicates become true
```

- [ ] **Step 2: Verify detector cannot synthesize authority**

Delete the preauthorization packet while keeping identical material state.

Expected:

```text
transition may still be detected
ACTIONABILITY=BLOCKED
```

- [ ] **Step 3: Verify pinned-main override**

Use paired PASS with a current exact-main pin forbidding merge.

Expected:

```text
review transition detected
repository acceptance may be recorded
merge remains HOLD
```

---

### Task 7: ZERO-SILENT-BATON and Deadlock Detection

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: fresh baton + transition/actionability state.
- Produces: explicit baton or `CONTROL_PLANE_DEADLOCK`.

- [ ] **Step 1: Require full baton state**

```text
BATON_STATE=(
  current_owner,
  executable_action_or_blocker,
  next_trigger,
  authority_epoch
)
```

- [ ] **Step 2: Enforce ZERO-SILENT-BATON**

Every role-ending material transition leaves exactly one of:

```text
executable next owner/action
concrete blocker owner + missing prerequisite
terminal no-further-action state
```

- [ ] **Step 3: Detect actionable deadlock**

Deadlock requires all:

```text
executable action exists
authority/evidence fresh
no writer/main/live lock forbids action
action not started/routed
no valid in-flight equivalent task handle
later watchdog scan sees same actionable material state unchanged
```

- [ ] **Step 4: Exclude legitimate waits**

These are not deadlocks:

```text
CI in progress
reviewer in progress
pinned-main HOLD
local-machine prerequisite
explicit Human gate
true external dependency
```

---

### Task 8: Reviewer Routing and Fresh Verdict Currentness

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: exact current review tuple and material reviewer state.
- Produces: paired reviewer route/rejoin behavior.

- [ ] **Step 1: Route canonical roles**

```text
REVIEWER_INTEGRATION
REVIEWER_SECURITY
```

When both required, route in parallel.

- [ ] **Step 2: Rejoin context, never reuse changed-tuple verdict**

A correct-role context may be reused for a repair, but must fresh-read and post a new verdict for a changed head/synthetic/authority tuple.

- [ ] **Step 3: Verify reviewer transition is material**

Cases:

```text
PENDING -> PASS
PENDING -> CHANGES_REQUIRED
PASS -> CHANGES_REQUIRED
CHANGES_REQUIRED -> PASS
```

All => `REVIEWER_TERMINAL_CHANGED`.

- [ ] **Step 4: Verify reviewer transition survives same task fingerprint**

Hold task tuple constant. Change reviewer state only.

Expected:

```text
material transition detected
same TASK_FINGERPRINT does not suppress it
```

---

### Task 9: No-Code Operational Trial and KPI Gate

**Files:**
- Repository production files: none.

**Interfaces:**
- Consumes: existing GitHub timestamps and Luna scan observations.
- Produces: evidence whether zero-new-runtime rollout is sufficient.

- [ ] **Step 1: Measure current baselines**

Collect from existing canonical timestamps:

```text
STOP_WRITE -> review route latency
paired PASS -> SOL merge-decision latency
actual merge -> successor activation latency
duplicate role spawns on unchanged material state
ZERO-SILENT-BATON violations
actionable CONTROL_PLANE_DEADLOCK count
post-GREEN public-seam/architecture blocker leakage
```

- [ ] **Step 2: Run bounded no-code trial**

For subsequent eligible transitions, apply Tasks 1-8 using existing watchdog only.

- [ ] **Step 3: Enforce hard quality targets**

```text
CONTROL_PLANE_DEADLOCK = 0
ZERO_SILENT_BATON_VIOLATION = 0
DUPLICATE_EPHEMERAL_SPAWN_ON_UNCHANGED_MATERIAL_STATE = 0
POST_GREEN_ARCHITECTURE_BLOCKER_LEAKAGE = 0
```

- [ ] **Step 4: Decide helper escalation**

Create a separate implementation issue only if the no-code trial shows repeated deterministic-classification errors or accepted latency SLA cannot be met by existing watchdog semantics.

Do not justify code merely because a helper is convenient.

---

### Task 10: Conditional Future Pure Helper — RED Matrix

**Files:**
- Future separate issue only.
- Create: `scripts/control_plane_state.py`
- Create: `tests/test_control_plane_state.py`

**Interfaces:**
- Consumes: already-fetched normalized dictionaries only.
- Produces: pure material projection/hash/diff, transition set, task fingerprint/de-dup classification.

This task is **NOT AUTHORIZED by #187**. It is a ready implementation blueprint if Task 9 requires escalation.

- [ ] **Step 1: Write failing material-projection tests**

Required test cases:

```text
identical projection -> NO_MATERIAL_TRANSITION
only observed_at changes -> NO_MATERIAL_TRANSITION
CI tests PENDING -> SUCCESS -> HOSTED_CI_TERMINAL_CHANGED
reuse PENDING -> FAILURE -> HOSTED_CI_TERMINAL_CHANGED
Integration PENDING -> PASS -> REVIEWER_TERMINAL_CHANGED
Security PASS -> CHANGES_REQUIRED -> REVIEWER_TERMINAL_CHANGED
writer ACTIVE -> STOP_WRITE -> WRITER_STOP_WRITE_OR_TERMINAL
writer terminal id changes -> WRITER_STOP_WRITE_OR_TERMINAL
head changes -> PR_HEAD_CHANGED
main/synthetic classification changes -> SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED
merged false -> true + merge SHA -> ACTUAL_MERGE
authority epoch changes -> AUTHORITY_EPOCH_CHANGED
baton owner/trigger/blocker changes -> BATON_CHANGED
CI + reviewer simultaneous -> stable ordered set
```

- [ ] **Step 2: Write failing task-de-dup separation tests**

Required cases:

```text
same task fingerprint + unchanged material -> NO_ACTION
same task fingerprint + valid handle -> REJOIN_HANDLE
same task fingerprint + reviewer changed -> material transition still emitted
same task fingerprint + CI changed -> material transition still emitted
changed task fingerprint + authorized role work -> SPAWN_OR_ROUTE
```

- [ ] **Step 3: Run RED and require causal failures**

Run:

```powershell
python -m pytest tests/test_control_plane_state.py -q
```

Expected before implementation: failures because helper symbols do not exist; existing unrelated tests remain unaffected.

- [ ] **Step 4: Implement minimal pure functions**

Recommended signatures:

```python
def material_state_projection(observation: dict[str, object]) -> dict[str, object]: ...

def material_state_fingerprint(observation: dict[str, object]) -> str: ...

def material_transition_set(previous: dict[str, object], current: dict[str, object]) -> tuple[str, ...]: ...

def task_fingerprint(task: dict[str, object]) -> str: ...

def dedup_decision(*, task_fingerprint_value: str, prior_task_fingerprint: str | None, valid_handle: bool, current_terminal: bool) -> str: ...
```

The helper does not resolve authority.

- [ ] **Step 5: Run focused GREEN**

```powershell
python -m pytest tests/test_control_plane_state.py -q
python scripts/check_architecture_boundaries.py
python scripts/check_reuse_declaration.py
```

Expected: zero failures.

- [ ] **Step 6: Run canonical hosted verification after push**

Use existing workflow only. Do not add a workflow.

---

### Task 11: N+1 and REQUIRED_PUBLIC_SEAMS Discipline

**Files:**
- Repository production files: none under #187.

**Interfaces:**
- Consumes: active phase N and candidate phase N+1.
- Produces: `PATCH_READY`, `ONLY_LATE_BINDINGS_PENDING`, or concrete blocker.

- [ ] **Step 1: Record required public seams before downstream RED**

```text
REQUIRED_PUBLIC_SEAMS:
- owner/subsystem
- public symbol/contract
- accepted source/merge identity
- downstream use
- missing/ambiguous: YES|NO
```

- [ ] **Step 2: Block speculative/private-only dependency**

If a seam is private-only, missing, duplicated, or speculative, downstream RED remains blocked until the correct owner resolves it.

- [ ] **Step 3: Target useful readiness**

Prefer:

```text
PATCH_READY
ONLY_LATE_BINDINGS_PENDING
```

over planning-only readiness where more safe preparation is possible.

---

### Task 12: Planning Acceptance and Hold

**Files:**
- Only the two #187 planning docs.

**Interfaces:**
- Consumes: exact current PR tuple, hosted CI/reuse, independent reviewer verdicts, current #131/main pin.
- Produces: `REPOSITORY_ACCEPTED / HOLD` or bounded repair.

- [ ] **Step 1: Verify exact cumulative write-set**

Expected exactly:

```text
docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md
docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md
```

- [ ] **Step 2: Verify hosted evidence literally**

Consume actual tests/reuse conclusions from the current head/synthetic. Do not promote AutoCAD/live NOT RUN.

- [ ] **Step 3: Obtain fresh paired independent review**

Both reviewers must fresh-read current #131, #187, and exact current PR head/synthetic. Prior changed-head verdicts are stale.

- [ ] **Step 4: Acceptance rule**

```text
Integration PASS
AND Security PASS
AND hosted tests/reuse acceptable
AND exact two-doc write-set
AND main/base/currentness unchanged
    => REPOSITORY_ACCEPTED / HOLD
otherwise
    => bounded CHANGES_REQUIRED repair
```

- [ ] **Step 5: Preserve current Gate-1G main pin**

Planning acceptance does not authorize merge while the controlling exact-main local gate forbids main movement.

## Self-Review Checklist

Before any completion claim:

- [ ] spec and plan both distinguish `MATERIAL_STATE_FINGERPRINT` from `TASK_FINGERPRINT`;
- [ ] `observed_at` is explicitly excluded from material projection;
- [ ] CI + reuse terminal changes are material;
- [ ] reviewer terminal changes are material;
- [ ] writer STOP_WRITE/terminal changes are material;
- [ ] merge/main/head/synthetic/authority changes are material;
- [ ] simultaneous changes have stable precedence and preserve all classes;
- [ ] same task fingerprint cannot suppress a material change;
- [ ] exact planning write-set remains two docs;
- [ ] no production/runtime/workflow/dependency/live authority is introduced;
- [ ] no `TODO` or `TBD` placeholder remains;
- [ ] current `main` pin remains unchanged.

## Terminal Planning State

After fresh paired PASS on the repaired exact tuple:

```text
#187_PLANNING_STATUS=REPOSITORY_ACCEPTED_HOLD
DEFAULT_RUNTIME_IMPLEMENTATION=NONE
MATERIAL_EVENT_OWNER=MATERIAL_STATE_PROJECTION
TASK_DEDUP_OWNER=TASK_FINGERPRINT
CONDITIONAL_FUTURE_HELPER=SEPARATE_ISSUE_REQUIRED
MAIN_MOVEMENT=NOT_AUTHORIZED_WHILE_GATE_PIN_ACTIVE
```
