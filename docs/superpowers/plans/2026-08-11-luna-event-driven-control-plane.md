# Luna Event-Driven Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Status, authority, and hard scope

- Parent: Issue #187.
- Control contract: `CONTROL_CONTRACT_VERSION=1.3`.
- Planning base: `ff93ddaa2ebb69e21f81baaa4f3dceec1db009ae`.
- Binding inputs: #187 body, V3 delta `5255200043`, approved design spec, newer Human Owner / #131 / SOL control if any.
- This plan is **PLANNING ONLY**. It does not authorize production/runtime implementation.
- Exact #187 planning write-set is only:
  - `docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md`
  - `docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md`
- No third path, workflow, dependency, runtime, persistent store, daemon, webhook, AutoCAD/File-IPC/provider/private/publication/system mutation.
- Current Gate-1G exact-main pin must remain untouched. #187 planning cannot merge while that pin forbids main movement.

## Selected architecture

Default rollout: **GitHub-native observation + existing Luna watchdog, with zero new repository runtime**.

The implementation contract has three separate layers:

```text
MATERIAL_STATE_PROJECTION / MATERIAL_STATE_FINGERPRINT
    => what canonical state changed?

authority resolver
    => what action is actually authorized now?

TASK_FINGERPRINT
    => is equivalent role work already in-flight/current?
```

The material detector MUST be closed under its declared schema: every projected-field difference maps to one or more deterministic transition classes. Unknown/unmapped projected differences fail closed as `UNMAPPED_MATERIAL_DIFF`.

Stable GitHub identities make same-result supersession observable:

```text
CI/reuse terminal_id = workflow_run_id:run_attempt
review terminal_id   = exact GitHub review submission ID/node ID
writer terminal_id   = durable STOP_WRITE/terminal packet/comment ID
```

These identities are currentness evidence only; they create no authority.

---

## Task 1: Freeze Reuse-First Boundaries and Existing Owners

**Files:**
- Planning docs only.

**Consumes:**
- GitHub current-main/PR/actions/review/comment surfaces.
- Existing Luna/SOL orchestration model.
- Existing repository verification owners.

**Produces:**
- Reuse map and explicit no-second-owner proof.

- [ ] **Step 1: Record GitHub authority/state reuse**

Reuse:

```text
refs/heads/main
#131 / Human Owner / SOL authority comments
PR number/base/head/merge-ref/synthetic/state/merge SHA
workflow run ID + run attempt + result for tests/reuse
review submission ID + verdict for Integration/Security
writer STOP_WRITE/terminal comment identity
GitHub timestamps for KPIs
```

- [ ] **Step 2: Record orchestration reuse**

Reuse:

```text
existing Luna watchdog
SOL repository/governance authority
existing correct-role reviewer contexts
STOP_WRITE + terminal handoff
explicit owner/next-trigger/blocker
exact-main pin controls
```

- [ ] **Step 3: Record verifier reuse**

Reuse:

```text
scripts/verify.ps1
scripts/check_architecture_boundaries.py
scripts/check_reuse_declaration.py
scripts/reuse_inventory.py
focused pytest/.NET owner tests
Ruff/static checks
git diff --check
```

- [ ] **Step 4: Verify alternatives remain explicit**

```text
A. GitHub-native + existing Luna watchdog => SELECTED
B. GitHub Actions event dispatcher => future-only under separate authority if measured SLA fails
C. webhook/daemon + persistent store => REJECTED under reuse-first/YAGNI/authority risk
```

Expected: no second scheduler/truth/review/CI/merge/store owner.

---

## Task 2: Define Canonical Observation and Material Projection

**Files:**
- Planning docs only.

**Consumes:**
- Fresh bounded GitHub observations.

**Produces:**
- `MATERIAL_STATE_PROJECTION` and `MATERIAL_STATE_FINGERPRINT`.

- [ ] **Step 1: Normalize the observation schema**

Required material fields:

```text
current_main
authority_epoch
task_or_issue
pr.number
pr.head
pr.synthetic_or_state
pr.state
pr.draft
pr.merged
pr.merge_sha
ci.tests.state
ci.tests.terminal_id
ci.reuse.state
ci.reuse.terminal_id
reviews.REVIEWER_INTEGRATION.state
reviews.REVIEWER_INTEGRATION.terminal_id
reviews.REVIEWER_SECURITY.state
reviews.REVIEWER_SECURITY.terminal_id
writer.state
writer.terminal_id
baton.current_owner
baton.next_trigger
baton.blocker
```

- [ ] **Step 2: Define stable terminal identities**

```text
ci.tests.terminal_id = <workflow_run_id>:<run_attempt> or NONE
ci.reuse.terminal_id = <workflow_run_id>:<run_attempt> or NONE
reviewer.terminal_id = <review submission ID/node ID> or NONE
writer.terminal_id = <durable terminal packet/comment ID> or NONE
```

For an in-progress CI run, the current run/attempt identity may be stored so a fresh run starting after a terminal is itself observable.

- [ ] **Step 3: Exclude observation-only fields**

Explicitly exclude:

```text
observed_at
watchdog scan number
local clock
API/fetch latency
cache path
process ID
free-form chat text
non-controlling repeated comments
log ordering that does not change canonical terminal identity
```

- [ ] **Step 4: Canonicalize deterministically**

Rules:

```text
missing optional value => literal NONE
closed enums where possible
sorted canonical keys
stable UTF-8 serialization
SHA-256 => MATERIAL_STATE_FINGERPRINT
```

- [ ] **Step 5: Prove clock-only stability**

Hold all material fields constant; change only `observed_at`/watchdog time.

Expected:

```text
same MATERIAL_STATE_PROJECTION
same MATERIAL_STATE_FINGERPRINT
NO_MATERIAL_TRANSITION
```

---

## Task 3: Define Exhaustive Field-to-Transition Closure

**Files:**
- Planning docs only.

**Consumes:**
- Previous/current material projections.

**Produces:**
- Stable `TRANSITION_SET`, `PRIMARY_TRANSITION`, or fail-closed schema violation.

- [ ] **Step 1: Freeze transition classes**

```text
UNMAPPED_MATERIAL_DIFF
AUTHORITY_EPOCH_CHANGED
TASK_OR_PR_IDENTITY_CHANGED
ACTUAL_MERGE
PR_HEAD_CHANGED
SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED
WRITER_STOP_WRITE_OR_TERMINAL
HOSTED_CI_TERMINAL_CHANGED
REVIEWER_TERMINAL_CHANGED
BATON_CHANGED
```

- [ ] **Step 2: Map every projected field**

Exact field map:

```text
authority_epoch
  => AUTHORITY_EPOCH_CHANGED

task_or_issue, pr.number
  => TASK_OR_PR_IDENTITY_CHANGED

pr.merged, pr.merge_sha
  => ACTUAL_MERGE when consistent with real merge truth

pr.head
  => PR_HEAD_CHANGED

current_main, pr.synthetic_or_state, pr.state, pr.draft
  => SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED

writer.state, writer.terminal_id
  => WRITER_STOP_WRITE_OR_TERMINAL

ci.tests.state, ci.tests.terminal_id,
ci.reuse.state, ci.reuse.terminal_id
  => HOSTED_CI_TERMINAL_CHANGED

reviews.REVIEWER_INTEGRATION.state,
reviews.REVIEWER_INTEGRATION.terminal_id,
reviews.REVIEWER_SECURITY.state,
reviews.REVIEWER_SECURITY.terminal_id
  => REVIEWER_TERMINAL_CHANGED

baton.current_owner, baton.next_trigger, baton.blocker
  => BATON_CHANGED
```

Any projected key/value change not covered by this map => `UNMAPPED_MATERIAL_DIFF`.

- [ ] **Step 3: Enforce projection-closure invariant**

```text
for every changed projected key:
    mapped_transition_classes(key) must be non-empty
```

Expected violation behavior:

```text
TRANSITION_SET=[UNMAPPED_MATERIAL_DIFF]
ACTIONABILITY=BLOCKED
PRIMARY_NEXT_OWNER=SOL
NO inferred repository/review/merge/live action
```

An empty transition set with changed material fingerprint is forbidden.

- [ ] **Step 4: Define stable precedence**

```text
0 UNMAPPED_MATERIAL_DIFF
1 AUTHORITY_EPOCH_CHANGED
2 TASK_OR_PR_IDENTITY_CHANGED
3 ACTUAL_MERGE
4 PR_HEAD_CHANGED
5 SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED
6 WRITER_STOP_WRITE_OR_TERMINAL
7 HOSTED_CI_TERMINAL_CHANGED
8 REVIEWER_TERMINAL_CHANGED
9 BATON_CHANGED
```

All detected classes remain in `TRANSITION_SET`; precedence controls validation/action ordering only.

- [ ] **Step 5: Define merge inconsistency handling**

Expected merge truth:

```text
merged false -> true and/or merge_sha NONE -> exact SHA => ACTUAL_MERGE
impossible reversal or contradictory merge SHA => UNMAPPED_MATERIAL_DIFF / fail closed
```

---

## Task 4: Close Identity and Same-Result Supersession Semantics

**Files:**
- Planning docs only.

**Consumes:**
- Stable task/PR/run/review identities.

**Produces:**
- Currentness-safe material transitions.

- [ ] **Step 1: Prove task identity-only change**

Hold all fields except `task_or_issue` constant.

Expected:

```text
TASK_OR_PR_IDENTITY_CHANGED
prior task-bound handles/currentness invalidated
fresh authority/actionability resolution
```

- [ ] **Step 2: Prove PR number-only change**

Hold all fields except `pr.number` constant.

Expected:

```text
TASK_OR_PR_IDENTITY_CHANGED
prior PR-bound review/currentness invalidated
fresh authority/actionability resolution
```

- [ ] **Step 3: Prove same-result CI supersession**

Cases:

```text
SUCCESS(runA:1) -> SUCCESS(runB:1)
SUCCESS(runA:1) -> SUCCESS(runA:2)
FAILURE(runA:1) -> FAILURE(runB:1)
```

Expected each:

```text
HOSTED_CI_TERMINAL_CHANGED
fresh run identity consumed
coarse state equality does not hide currentness movement
```

- [ ] **Step 4: Prove same-result reviewer supersession**

Cases:

```text
PASS(reviewA) -> PASS(reviewB)
CHANGES_REQUIRED(reviewA) -> CHANGES_REQUIRED(reviewB)
```

Expected each:

```text
REVIEWER_TERMINAL_CHANGED
fresh exact-current-tuple review identity consumed
prior verdict never promoted by identity equality assumptions
```

- [ ] **Step 5: Prove intermediate scan is not required**

A new run/review may start and finish between watchdog scans. Stable identity movement alone must still expose the supersession even if old/new coarse state tokens are equal.

---

## Task 5: Separate Material Detection from Task De-Duplication

**Files:**
- Planning docs only.

**Consumes:**
- Material transition result.
- Candidate role/task invocation.

**Produces:**
- `TASK_FINGERPRINT` and spawn/rejoin/no-action decision.

- [ ] **Step 1: Freeze task fingerprint tuple**

```text
(role,
 task_or_issue,
 current_main,
 pr_head,
 synthetic_or_state,
 authority_epoch,
 intended_output)
```

Allowed intended outputs include:

```text
WRITE_RED
WRITE_GREEN
REVIEW
MERGE_DECISION
LOCAL_PREFLIGHT
STATUS_ONLY
```

- [ ] **Step 2: Apply material comparison first**

```text
if material changed:
    classify transition
    fresh-resolve authority/actionability
    only then apply task de-dup
```

- [ ] **Step 3: Define de-dup results**

```text
same TASK_FINGERPRINT + valid correct-role in-flight handle => REJOIN_HANDLE
same TASK_FINGERPRINT + equivalent durable current terminal => NO_DUPLICATE_SPAWN
same TASK_FINGERPRINT + no new material state => NO_ACTION
changed TASK_FINGERPRINT + authorized role work => SPAWN_OR_ROUTE_MINIMUM_REQUIRED_ROLE
```

- [ ] **Step 4: Prove same task fingerprint cannot hide fresh terminal state**

Hold task fingerprint constant while changing reviewer or CI terminal identity.

Expected: material transition is emitted before de-dup.

---

## Task 6: Authority Resolution and No-Event/No-Agent

**Files:**
- Repository production files: none.

**Consumes:**
- `TRANSITION_SET`.
- Fresh controlling GitHub authority.

**Produces:**
- `ACTIONABILITY` and exact next owner/trigger.

- [ ] **Step 1: Fresh-validate authority for every material transition**

Read/verify:

```text
Human Owner / #131 / SOL controlling packet
exact main/base
exact task/PR/head/synthetic where bound
writer/write-set locks
required CI/review predicates + exact terminal identities
local/live pin constraints
next owner/trigger
material invalidators
```

- [ ] **Step 2: Fail closed on missing/stale/contradictory authority**

Expected:

```text
ACTIONABILITY=BLOCKED
MISSING=<one exact controlling prerequisite>
PRIMARY_NEXT_OWNER=<owner of missing prerequisite>
NEXT_TRIGGER=<exact trigger>
```

- [ ] **Step 3: Enforce same-cycle action when already authorized**

A material transition plus already-satisfied explicit authority should route/start the bounded action in the same scan unless an equivalent valid in-flight handle exists.

- [ ] **Step 4: Enforce no-event/no-agent**

```text
NO_MATERIAL_TRANSITION + no executable authorized work => NO_ACTION
NO_MATERIAL_TRANSITION + valid equivalent in-flight handle => REJOIN/OBSERVE_ONLY
watchdog tick alone => no spawn
```

Fresh GitHub reads required by a role remain mandatory.

---

## Task 7: ZERO-SILENT-BATON and Deadlock Detection

**Files:**
- Repository production files: none.

**Consumes:**
- Current material state and authority/actionability.

**Produces:**
- Explicit baton or deadlock classification.

- [ ] **Step 1: Normalize baton**

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

Generic repeated `WAIT` is forbidden when a concrete blocker exists.

- [ ] **Step 3: Detect actionable deadlock**

Deadlock requires all:

```text
executable action exists
authority/evidence fresh
no writer/main/live/epoch lock forbids action
action not started/routed
no valid in-flight equivalent task handle
later watchdog scan sees same actionable material state unchanged
```

- [ ] **Step 4: Exclude legitimate waits**

Not deadlocks:

```text
CI in progress
reviewer in progress
pinned-main HOLD
local-machine prerequisite
explicit Human gate
true external dependency
```

Target: actionable `CONTROL_PLANE_DEADLOCK=0`.

---

## Task 8: Reviewer Routing and Fresh Verdict Currentness

**Files:**
- Repository production files: none.

**Consumes:**
- Exact review tuple and canonical reviewer terminal IDs.

**Produces:**
- Paired route/rejoin behavior without stale verdict reuse.

- [ ] **Step 1: Route canonical roles**

```text
REVIEWER_INTEGRATION
REVIEWER_SECURITY
```

When both are required, route in parallel.

- [ ] **Step 2: Rejoin context, never reuse changed-tuple verdict**

A correct-role context may be reused for a bounded repair, but it must fresh-read and post a new verdict for a changed main/head/synthetic/authority/task tuple.

- [ ] **Step 3: Treat reviewer terminal identity as currentness evidence**

A changed review submission ID is material even if verdict token is unchanged.

Expected:

```text
PASS(reviewA) -> PASS(reviewB) => REVIEWER_TERMINAL_CHANGED
```

This does not mean PASS is reusable; the new review must independently bind the exact current tuple.

---

## Task 9: Conditional SOL Preauthorization, N+1, and Public Seams

**Files:**
- Repository production files: none.

- [ ] **Step 1: Require explicit preauthorization packet**

Packet must state:

```text
exact main/base
expected RED/GREEN head conditions
exact allowed write-set/action
required CI/review predicates
exact target action
invalidators
automatic action allowed when predicates become true
```

Detector output never synthesizes authority.

- [ ] **Step 2: Preserve pinned-main/live override**

Generic preauthorization cannot override an exact-main local pin or live gate.

- [ ] **Step 3: Target useful N+1 readiness**

Prefer:

```text
PATCH_READY
ONLY_LATE_BINDINGS_PENDING
```

over planning-only readiness when architecture/owner/public seams can safely be closed.

- [ ] **Step 4: Record REQUIRED_PUBLIC_SEAMS before downstream RED**

```text
REQUIRED_PUBLIC_SEAMS:
- owner/subsystem
- public symbol/contract
- accepted source/merge identity
- downstream use
- missing/ambiguous: YES|NO
```

Private-only, speculative, duplicated, or missing seams block downstream RED.

---

## Task 10: Pre-Push GREEN Owner-Contract Bundle

**Files:**
- Repository production files: none under #187.

Before a future production slice's first GREEN push, compose existing checks only:

```text
focused RED/GREEN tests
focused consumed-owner seam tests
Ruff/static checks where applicable
scripts/check_architecture_boundaries.py
scripts/check_reuse_declaration.py where applicable
git diff --check
exact changed-path audit
canonical hosted verification after push
```

This bundle is a local quality gate only. It never replaces hosted final CI/reuse, independent review, exact-head validation, or live gates.

---

## Task 11: KPI Contract and Resource Policy

**Files:**
- Repository production files: none.

**Consumes:**
- Existing GitHub/action/comment timestamps and trustworthy Luna accounting if available.

**Produces:**
- Full V3 KPI evidence without a second metrics store.

- [ ] **Step 1: Derive core latency metrics**

```text
writer_unlock_to_stop_write
stop_write_to_ci_terminal
stop_write_to_review_start
ci_terminal_to_reviewer_terminal
paired_pass_to_merge
merge_to_successor_activation
```

- [ ] **Step 2: Classify policy HOLD correctly**

If exact-main/epoch policy intentionally blocks merge:

```text
paired_pass_to_merge = HOLD_BY_POLICY
```

Do not count policy HOLD as control-plane idle.

- [ ] **Step 3: Derive quality/efficiency metrics**

```text
actionable_baton_idle_cycles
review_repair_cycles
architecture_blockers_first_discovered_after_green
luna_discovery_token_share
duplicate_ephemeral_spawn_on_unchanged_material_state
zero_silent_baton_violation
control_plane_deadlock
```

Targets:

```text
actionable_baton_idle_cycles = 0
architecture_blockers_first_discovered_after_green = 0
duplicate_ephemeral_spawn_on_unchanged_material_state = 0
zero_silent_baton_violation = 0
control_plane_deadlock = 0
```

If trustworthy Luna token accounting is unavailable:

```text
luna_discovery_token_share = NOT_AVAILABLE
```

Never estimate/invent it.

- [ ] **Step 4: Enforce resource-policy boundary**

Optimization applies ONLY to:

```text
Luna discovery/reconstruction
equivalent ephemeral orchestration spawn de-duplication
duplicate non-material status commentary
```

It MUST NOT reduce:

```text
Master Audit depth
Integration/Security adversarial review depth
persistent R3/R4/R5/R6 specialist reasoning
required fresh GitHub reads
material-transition communication
exact terminal identities/evidence
required architecture/currentness/security reasoning
```

- [ ] **Step 5: Self-review non-token-limited proof**

Explicitly confirm:

```text
MASTER_AUDIT_TOKEN_LIMIT=NONE
REVIEWER_INTEGRATION_DEPTH_REDUCTION=FORBIDDEN
REVIEWER_SECURITY_DEPTH_REDUCTION=FORBIDDEN
R3_R4_R5_R6_SPECIALIST_TOKEN_LIMIT=NONE
```

---

## Task 12: No-Code Operational Trial

**Files:**
- Repository production files: none.

**Consumes:**
- Subsequent eligible real control-plane transitions.

**Produces:**
- Evidence whether zero-new-runtime rollout is sufficient.

- [ ] **Step 1: Apply Tasks 1-11 through the existing watchdog only**

No new workflow/daemon/helper.

- [ ] **Step 2: Measure full KPI set**

Do not use a reduced KPI subset.

- [ ] **Step 3: Verify safety invariants**

```text
no silent baton
no actionable deadlock
no duplicate spawn on unchanged material state
no stale review/run currentness reuse
no unmapped material diff reaching actionability
no token-depth reduction outside Luna/ephemeral de-dup
```

- [ ] **Step 4: Decide helper escalation**

Open a separate implementation issue only if measured evidence shows repeated deterministic-classification failures or an accepted latency SLA cannot be met by existing watchdog semantics.

Convenience alone does not justify code.

---

## Task 13: Conditional Future Pure Helper — RED Matrix

**Files:**
- Future separate implementation issue only.
- Potential create: `scripts/control_plane_state.py`.
- Potential create: `tests/test_control_plane_state.py`.

This task is **NOT AUTHORIZED by #187**. It is a ready blueprint only if Task 12 proves code is needed.

### Step 1: RED — material projection stability

Required cases:

```text
identical projection => NO_MATERIAL_TRANSITION
only observed_at changes => NO_MATERIAL_TRANSITION
```

### Step 2: RED — identity closure

Required cases:

```text
task_or_issue-only change => TASK_OR_PR_IDENTITY_CHANGED
pr.number-only change => TASK_OR_PR_IDENTITY_CHANGED
same PR head change => PR_HEAD_CHANGED
unknown projected key change => UNMAPPED_MATERIAL_DIFF + BLOCKED
changed fingerprint with empty transition set => impossible/test failure
```

### Step 3: RED — CI/reuse currentness

Required cases:

```text
tests PENDING -> SUCCESS => HOSTED_CI_TERMINAL_CHANGED
reuse PENDING -> FAILURE => HOSTED_CI_TERMINAL_CHANGED
SUCCESS(runA:1) -> SUCCESS(runB:1) => HOSTED_CI_TERMINAL_CHANGED
SUCCESS(runA:1) -> SUCCESS(runA:2) => HOSTED_CI_TERMINAL_CHANGED
FAILURE(runA:1) -> FAILURE(runB:1) => HOSTED_CI_TERMINAL_CHANGED
```

### Step 4: RED — reviewer currentness

Required cases:

```text
Integration PENDING -> PASS => REVIEWER_TERMINAL_CHANGED
Security PASS -> CHANGES_REQUIRED => REVIEWER_TERMINAL_CHANGED
PASS(reviewA) -> PASS(reviewB) => REVIEWER_TERMINAL_CHANGED
CHANGES_REQUIRED(reviewA) -> CHANGES_REQUIRED(reviewB) => REVIEWER_TERMINAL_CHANGED
```

### Step 5: RED — writer/merge/authority/baton

Required cases:

```text
writer ACTIVE -> STOP_WRITE => WRITER_STOP_WRITE_OR_TERMINAL
writer terminal ID change => WRITER_STOP_WRITE_OR_TERMINAL
merged false -> true + merge SHA => ACTUAL_MERGE
contradictory/impossible merge identity => UNMAPPED_MATERIAL_DIFF + BLOCKED
authority epoch change => AUTHORITY_EPOCH_CHANGED
baton owner/trigger/blocker change => BATON_CHANGED
```

### Step 6: RED — simultaneous transition ordering

Required cases:

```text
CI + reviewer => preserve both; CI before reviewer
identity + head + reviewer => preserve all; identity before head/reviewer
unmapped diff + any other change => UNMAPPED_MATERIAL_DIFF is primary and actionability blocked
```

### Step 7: RED — task de-dup separation

Required cases:

```text
same task fingerprint + unchanged material => NO_ACTION
same task fingerprint + valid handle => REJOIN_HANDLE
same task fingerprint + reviewer terminal ID change => material event still emitted
same task fingerprint + CI terminal ID change => material event still emitted
changed task fingerprint + authorized role work => SPAWN_OR_ROUTE
```

### Step 8: RED — KPI/resource semantics

Required cases:

```text
policy-held merge => HOLD_BY_POLICY, not idle
missing trustworthy Luna token accounting => NOT_AVAILABLE
Master Audit / Integration / Security / R3-R6 depth cannot be marked optimized/reduced
```

### Step 9: Minimal helper contract if separately authorized

Recommended pure signatures:

```python
def material_state_projection(observation: dict[str, object]) -> dict[str, object]: ...

def material_state_fingerprint(observation: dict[str, object]) -> str: ...

def material_transition_set(previous: dict[str, object], current: dict[str, object]) -> tuple[str, ...]: ...

def task_fingerprint(task: dict[str, object]) -> str: ...

def dedup_decision(*, task_fingerprint_value: str, prior_task_fingerprint: str | None, valid_handle: bool, current_terminal: bool) -> str: ...
```

Helper boundaries:

```text
pure/offline only
already-fetched normalized data in
advisory projection/diff/fingerprints out
no GitHub/network calls
no agent spawn
no comment/write/merge/review authority
no persistent authority store
no dependency/workflow addition unless separately authorized
```

### Step 10: Future RED/GREEN verification commands

Only under a future explicit implementation issue:

```powershell
python -m pytest tests/test_control_plane_state.py -q
python scripts/check_architecture_boundaries.py
python scripts/check_reuse_declaration.py
```

Then run the existing canonical hosted verification after push. No new workflow.

---

## Task 14: Planning Acceptance and HOLD

**Files:**
- Exactly the two #187 planning docs.

**Consumes:**
- Exact current PR tuple.
- Hosted tests/reuse.
- Fresh independent reviewer verdicts.
- Current #131/main pin.

**Produces:**
- `REPOSITORY_ACCEPTED / HOLD` or bounded repair.

- [ ] **Step 1: Verify exact cumulative write-set**

Expected exactly:

```text
docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md
docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md
```

- [ ] **Step 2: Verify hosted evidence literally**

Consume actual tests/reuse conclusions from exact current head/synthetic. AutoCAD/File-IPC/live NOT RUN remains NOT RUN/non-PASS.

- [ ] **Step 3: Obtain fresh paired independent review**

Both reviewers fresh-read current #131, #187, and exact current PR tuple. Any changed-head verdict is stale.

- [ ] **Step 4: Acceptance rule**

```text
Integration PASS
AND Security PASS
AND hosted tests/reuse acceptable
AND exact two-doc write-set
AND main/base/currentness unchanged
AND projection-closure/currentness/resource-policy checks satisfied
    => REPOSITORY_ACCEPTED / HOLD
otherwise
    => bounded CHANGES_REQUIRED repair
```

- [ ] **Step 5: Preserve Gate-1G main pin**

Planning acceptance does not authorize merge while controlling exact-main local gate forbids main movement.

---

## Self-Review Checklist

Before any completion claim, verify all of the following:

- [ ] exact cumulative write-set remains two docs only;
- [ ] `MATERIAL_STATE_FINGERPRINT` and `TASK_FINGERPRINT` remain separate;
- [ ] `observed_at` and watchdog time are excluded from material projection;
- [ ] every projected key has a deterministic field-to-transition mapping;
- [ ] `task_or_issue` and `pr.number` map to `TASK_OR_PR_IDENTITY_CHANGED`;
- [ ] an unmapped projected diff emits `UNMAPPED_MATERIAL_DIFF` and blocks actionability;
- [ ] a changed material fingerprint can never produce an empty transition set;
- [ ] CI/reuse state and `workflow_run_id:run_attempt` identity are material;
- [ ] same-result CI/reuse fresh terminal supersession is observable;
- [ ] reviewer state and review submission ID are material;
- [ ] same-result reviewer fresh terminal supersession is observable;
- [ ] writer STOP_WRITE/terminal state and terminal ID are material;
- [ ] merge/main/head/synthetic/authority/baton changes are mapped;
- [ ] simultaneous changes preserve all classes with stable precedence;
- [ ] same task fingerprint cannot suppress a material transition;
- [ ] transition detection cannot synthesize authority;
- [ ] no-event/no-agent remains explicit;
- [ ] ZERO-SILENT-BATON and CONTROL_PLANE_DEADLOCK remain exact;
- [ ] reuse audit and three alternatives/trade-offs remain present in design;
- [ ] full V3 KPI chain is present;
- [ ] policy-held merge uses `HOLD_BY_POLICY`;
- [ ] unavailable trustworthy Luna token accounting uses `NOT_AVAILABLE`;
- [ ] Master Audit remains non-token-limited;
- [ ] Integration/Security review depth remains non-token-limited;
- [ ] persistent R3/R4/R5/R6 reasoning remains non-token-limited;
- [ ] no production/runtime/workflow/dependency/live/system authority is introduced;
- [ ] no `TODO` or `TBD` placeholder remains;
- [ ] current `main` pin remains unchanged.

## Terminal Planning State

After fresh paired PASS on the exact current tuple:

```text
#187_PLANNING_STATUS=REPOSITORY_ACCEPTED_HOLD
DEFAULT_RUNTIME_IMPLEMENTATION=NONE
MATERIAL_EVENT_OWNER=MATERIAL_STATE_PROJECTION
TASK_DEDUP_OWNER=TASK_FINGERPRINT
IDENTITY_TRANSITION=TASK_OR_PR_IDENTITY_CHANGED
TERMINAL_CURRENTNESS=STABLE_GITHUB_IDENTITIES
UNMAPPED_DIFF_POLICY=FAIL_CLOSED_TO_SOL
CONDITIONAL_FUTURE_HELPER=SEPARATE_ISSUE_REQUIRED
MAIN_MOVEMENT=NOT_AUTHORIZED_WHILE_GATE_PIN_ACTIVE
```
