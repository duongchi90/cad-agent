# Luna Event-Driven Control Plane Design

## Status and authority

- Issue: #187
- Control contract: `CONTROL_CONTRACT_VERSION=1.3`
- Planning epoch: `ff93ddaa2ebb69e21f81baaa4f3dceec1db009ae`
- Authority: Issue #187 plus its V3 delta comment `5255200043`, Human Owner written-spec approval recorded at #187 comment `5306410590`, with newer #131 / Human Owner / SOL control always taking precedence.
- Scope: PLANNING / DESIGN ONLY.
- Repository production/runtime implementation: NOT AUTHORIZED by #187.
- AutoCAD, File-IPC, provider, private/customer CAD, publication, PC3/PMP, profile, registry, printer/driver/system execution: NOT AUTHORIZED.
- Exact #187 planning write-set is only:
  - `docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md`
  - `docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md`

This design must not move the currently pinned `main`, merge any HOLD PR, or change the current Gate-1G local baton.

## Problem

The project already has repository, CI, exact-tuple review, merge, authority, and live-execution gates. The control-plane inefficiency is orchestration latency and duplicate reconstruction: a material change can become actionable while Luna waits for a later scan, reconstructs too much state, respawns an equivalent role, or fails to distinguish a real transition from a clock-only observation change.

The design must solve two different problems without conflating them:

1. **Material-transition detection** — determine whether canonical execution-relevant state changed since the last observation.
2. **Ephemeral-task de-duplication** — determine whether a role/task invocation is already in-flight or already terminal for the exact same work identity.

These are separate contracts and therefore use separate canonical projections and fingerprints.

## Goals

The design SHALL:

- keep GitHub and accepted contracts as the only authority;
- use the existing Luna watchdog as transport/fallback rather than add a second scheduler;
- detect bounded material state transitions deterministically;
- explicitly ignore observation-only changes such as watchdog time;
- enforce no-material-event/no-duplicate-agent semantics;
- prevent a same task fingerprint from suppressing a changed material state;
- route already-authorized actions in the same scan cycle that observes the material transition;
- preserve strict exact-head/exact-synthetic reviewer currentness;
- preserve/rejoin the same correct-role reviewer context where possible while requiring a fresh verdict for a changed tuple;
- detect `ZERO-SILENT-BATON` and `CONTROL_PLANE_DEADLOCK` failures;
- support explicit conditional SOL preauthorization without inventing authority;
- target N+1 readiness as `PATCH_READY` or `ONLY_LATE_BINDINGS_PENDING` where safe;
- require `REQUIRED_PUBLIC_SEAMS` audit before downstream RED;
- derive cycle-time KPIs from existing GitHub/action/comment timestamps where possible;
- fail closed whenever canonical state reconstruction is incomplete or contradictory.

## Non-goals

This design SHALL NOT:

- create a second scheduler, merge authority, review authority, CI authority, store, database, queue, daemon, webhook service, or truth source;
- add or modify a GitHub Actions workflow under #187;
- infer repository-write, merge, live, repair, approval, publication, or system authority from detector output;
- treat cache state, model memory, chat history, stale SHA, stale synthetic, or stale reviewer verdict as authority;
- weaken STOP_WRITE, RED-first, hosted CI/reuse, paired independent review, exact-main pin, or live gates;
- touch AutoCAD/File-IPC/provider/private/customer/publication/system surfaces;
- alter the R0-R8 functional architecture.

## Selected architecture

Select **GitHub-native observation plus the existing Luna watchdog**.

The system is **edge-triggered in semantics, watchdog-driven in transport**:

1. Luna fresh-reads canonical GitHub state required by the current baton.
2. Luna normalizes a canonical **material-state projection** containing only execution-relevant state.
3. Luna hashes that projection as `MATERIAL_STATE_FINGERPRINT` and compares it with the prior advisory observation.
4. If the material projection is identical, there is no material transition even if `observed_at` or watchdog time changed.
5. If the material projection changed, Luna computes a deterministic transition set and applies stable precedence.
6. Luna fresh-validates the controlling authority packet.
7. If an action is already authorized, Luna routes/starts it in the same cycle.
8. Only after actionability is known does Luna use the separate **task fingerprint** to decide whether to spawn, rejoin, or suppress duplicate role work.
9. Missing/corrupt cache causes full reconstruction from GitHub; it never fails open.

The detector decides **what changed**. The authority resolver decides **what may happen**. The task de-dup layer decides **whether equivalent role work already exists**.

## Canonical observation

A Luna observation MAY contain:

```json
{
  "schema_version": "luna-control-observation-1.1",
  "observed_at": "2026-08-16T08:00:00Z",
  "material_state": {
    "current_main": "<sha>",
    "authority_epoch": "<issue/comment-id>",
    "task_or_issue": "<stable-id>",
    "pr": {
      "number": 263,
      "head": "<sha-or-NONE>",
      "synthetic_or_state": "<sha-or-normalized-state>",
      "draft": true,
      "merged": false,
      "merge_sha": "NONE"
    },
    "ci": {
      "tests": "PENDING|SUCCESS|FAILURE|NOT_APPLICABLE",
      "reuse": "PENDING|SUCCESS|FAILURE|NOT_APPLICABLE"
    },
    "reviews": {
      "REVIEWER_INTEGRATION": "PENDING|PASS|CHANGES_REQUIRED|NOT_REQUIRED",
      "REVIEWER_SECURITY": "PENDING|PASS|CHANGES_REQUIRED|NOT_REQUIRED"
    },
    "writer": {
      "state": "NONE|ACTIVE|STOP_WRITE|TERMINAL_PASS|TERMINAL_BLOCKED",
      "terminal_id": "<stable-id-or-NONE>"
    },
    "baton": {
      "current_owner": "<canonical-role>",
      "next_trigger": "<normalized-trigger>",
      "blocker": "<normalized-blocker-or-NONE>"
    }
  },
  "material_state_fingerprint": "<sha256>",
  "task_fingerprints": []
}
```

`observed_at` is explicitly **observation-only** and is excluded from all material-transition comparisons.

The observation is an advisory cache/index only. It SHALL NOT contain secrets, private CAD data, raw evidence payloads, private file contents, or authority not present on GitHub.

## Canonical material-state projection

`MATERIAL_STATE_PROJECTION` is the exact canonical projection used for event detection.

It contains exactly these normalized fields:

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

It explicitly excludes:

```text
observed_at
watchdog_scan_number
local clock
API latency
fetch duration
cache path
process id
log ordering that does not change canonical terminal identity
free-form chat text
non-controlling repeated comments
```

Absent optional values are normalized to literal `NONE`. Closed enums are used wherever possible. Keys are serialized in canonical sorted order and hashed with SHA-256.

The result is `MATERIAL_STATE_FINGERPRINT`.

## Material-transition comparison

The event detector compares the previous and current canonical material-state projections field-by-field before hashing is used as a compact equality check.

Rules:

```text
identical MATERIAL_STATE_PROJECTION
    => NO_MATERIAL_TRANSITION
only observation-only fields changed
    => NO_MATERIAL_TRANSITION
any canonical material field changed
    => MATERIAL_TRANSITION_SET = deterministic changed classes
```

A same task fingerprint MUST NOT suppress a changed material projection.

### Transition classes and exact triggers

`AUTHORITY_EPOCH_CHANGED`
- trigger: `authority_epoch` changed.

`ACTUAL_MERGE`
- trigger: `pr.merged` changes false -> true, or `pr.merge_sha` changes `NONE` -> exact merge SHA.

`PR_HEAD_CHANGED`
- trigger: `pr.head` changed while the PR/task identity remains the same.

`SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED`
- trigger: `current_main`, `pr.synthetic_or_state`, or PR draft/open/closed state changed in a way that changes tuple/currentness classification and is not already represented as `ACTUAL_MERGE`.

`HOSTED_CI_TERMINAL_CHANGED`
- trigger: either `ci.tests` or `ci.reuse` changes state, including `PENDING -> SUCCESS`, `PENDING -> FAILURE`, or a terminal state changing because a fresh run superseded the prior run.

`REVIEWER_TERMINAL_CHANGED`
- trigger: either canonical reviewer state changes, including `PENDING -> PASS`, `PENDING -> CHANGES_REQUIRED`, `PASS -> CHANGES_REQUIRED`, `CHANGES_REQUIRED -> PASS`, or a fresh exact-head verdict supersedes a prior verdict.

`WRITER_STOP_WRITE_OR_TERMINAL`
- trigger: `writer.state` enters `STOP_WRITE`, `TERMINAL_PASS`, or `TERMINAL_BLOCKED`, or `writer.terminal_id` changes to a new stable terminal identity.

`BATON_CHANGED`
- trigger: `baton.current_owner`, `baton.next_trigger`, or `baton.blocker` changes without a newer authority epoch. This class is advisory and cannot create authority.

`BATON_CHANGED` is intentionally separated from `AUTHORITY_EPOCH_CHANGED` so a canonical transition packet can update owner/action semantics even when represented outside #131, while the authority resolver still fresh-checks the controlling packet.

## Multiple simultaneous changes

A single watchdog scan can observe several material changes since the previous observation. The detector SHALL return a stable transition set, not an implementation-dependent single winner.

Canonical precedence for processing is:

```text
1. AUTHORITY_EPOCH_CHANGED
2. ACTUAL_MERGE
3. PR_HEAD_CHANGED
4. SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED
5. WRITER_STOP_WRITE_OR_TERMINAL
6. HOSTED_CI_TERMINAL_CHANGED
7. REVIEWER_TERMINAL_CHANGED
8. BATON_CHANGED
```

All detected classes remain recorded in `TRANSITION_SET`; precedence only controls validation/action ordering.

Example:

```text
TRANSITION_SET=[HOSTED_CI_TERMINAL_CHANGED, REVIEWER_TERMINAL_CHANGED]
PRIMARY_TRANSITION=HOSTED_CI_TERMINAL_CHANGED
```

If a higher-precedence transition invalidates a lower one — for example main/head movement makes a reviewer verdict stale — the lower event is observed but cannot authorize use of stale evidence.

## Ephemeral task fingerprint and de-duplication

`TASK_FINGERPRINT` is separate from `MATERIAL_STATE_FINGERPRINT`.

It identifies one unit of role work:

```text
(role,
 task_or_issue,
 current_main,
 pr_head,
 synthetic_or_state,
 authority_epoch,
 intended_output)
```

Allowed `intended_output` values include:

```text
WRITE_RED
WRITE_GREEN
REVIEW
MERGE_DECISION
LOCAL_PREFLIGHT
STATUS_ONLY
```

Canonicalization:

- role uses closed canonical role names;
- missing values use literal `NONE`;
- exact current main/head/synthetic/authority epoch are included;
- serialization uses canonical sorted keys;
- SHA-256 may be used for compact identity.

Decision rule is applied **after material-state comparison**:

```text
material state changed
    => classify and resolve actionability first

same TASK_FINGERPRINT + valid correct-role in-flight handle
    => REJOIN_HANDLE
same TASK_FINGERPRINT + equivalent terminal already durable and still current
    => NO_DUPLICATE_SPAWN
same TASK_FINGERPRINT + no new material state
    => NO_ACTION
changed TASK_FINGERPRINT + authorized work required
    => SPAWN_OR_ROUTE_MINIMUM_REQUIRED_ROLE
```

A same task fingerprint is never evidence that CI/review/writer state did not change.

## Material transition handling

For every material transition Luna derives:

```text
TRANSITION_SET=<ordered-set>
PRIMARY_TRANSITION=<highest-precedence-class>
OLD_MATERIAL_FINGERPRINT=<hash-or-NONE>
NEW_MATERIAL_FINGERPRINT=<hash>
AUTHORITY_EPOCH=<issue/comment>
ACTIONABILITY=AUTHORIZED | BLOCKED | OBSERVE_ONLY
PRIMARY_NEXT_OWNER=<role>
NEXT_TRIGGER=<exact trigger>
```

If `ACTIONABILITY=AUTHORIZED`, the bounded action is routed/started in the same watchdog cycle unless an equivalent valid in-flight task handle exists.

If `ACTIONABILITY=BLOCKED`, exactly one controlling missing prerequisite/authority and next trigger are persisted. Generic `WAIT` is not sufficient where a concrete blocker can be named.

## Authority resolution

Transition detection never creates authority.

For every material transition Luna SHALL fresh-read the controlling Human Owner / #131 / SOL packet and validate:

- exact current main/base where bound;
- exact head/synthetic where bound;
- current writer lock/write-set;
- required CI/review predicates;
- local/live main-pin constraints;
- explicit next owner and next trigger;
- material invalidators.

If the packet is absent, stale, contradictory, or does not authorize the action, `ACTIONABILITY=BLOCKED`.

## Conditional SOL preauthorization

Conditional preauthorization is valid only when an explicit GitHub control packet states:

- exact current main/base;
- expected RED/GREEN head conditions;
- exact allowed action/write-set;
- required CI/review predicates;
- exact target action;
- invalidators;
- the action that may occur automatically when predicates become true.

Examples:

- expected RED evidence -> bounded GREEN write;
- paired PASS on exact unchanged tuple -> merge-eligibility decision;
- actual merge -> capture merge SHA, re-epoch affected successors, activate next eligible gate.

Pinned-main/local-live constraints override generic preauthorization.

## ZERO-SILENT-BATON

A baton is explicit only when all are known:

```text
BATON_STATE = (
  current_owner,
  executable_action_or_blocker,
  next_trigger,
  authority_epoch
)
```

Every material transition ending one role's work must leave one of:

- executable next owner/action;
- concrete blocker owner + missing prerequisite;
- terminal state requiring no further action.

## CONTROL_PLANE_DEADLOCK

A deadlock exists only if all are true:

1. canonical baton identifies an executable action;
2. required authority/evidence is fresh and already present;
3. no writer/main/live lock forbids it;
4. action was neither started/routed in the transition cycle nor represented by a valid in-flight task handle;
5. a later watchdog scan sees the same actionable material state unchanged.

On detection Luna reports the deadlock and performs/routes the already-authorized action in that scan.

True external waits, pinned-main HOLD, CI/reviewer in-flight, local-machine prerequisite, or explicit Human gate are not deadlocks.

## Reviewer routing and handle reuse

Canonical reviewer roles:

- `REVIEWER_INTEGRATION`
- `REVIEWER_SECURITY`

When both are required they are routed in parallel. A bounded repair may rejoin the same correct-role context, but a changed head/synthetic/material authority tuple requires a fresh exact-head verdict. Prior PASS/CHANGES_REQUIRED is never promoted to the new tuple.

A reviewer terminal is part of `MATERIAL_STATE_PROJECTION`, so a fresh reviewer verdict is observable even when `TASK_FINGERPRINT` itself is unchanged.

## N+1 readiness

While phase N executes, safe off-critical-path preparation for phase N+1 should target:

- `PATCH_READY`; or
- `ONLY_LATE_BINDINGS_PENDING`.

`PLANNING_ONLY_READY` is not the target when architecture, owner, public seam, write-set, and RED matrix can safely be closed further.

This does not authorize overlapping writers.

## REQUIRED_PUBLIC_SEAMS audit

Before downstream RED, record:

```text
REQUIRED_PUBLIC_SEAMS:
- owner/subsystem
- public symbol or contract
- accepted source/merge identity
- downstream use
- missing/ambiguous: YES|NO
```

A private-only, speculative, duplicated, or missing seam blocks downstream RED until resolved by the correct owner.

## Pre-push GREEN owner-contract bundle

Before first GREEN push for a production slice, use only existing owners/checkers:

1. exact focused RED/GREEN tests;
2. focused tests for consumed public-seam owners;
3. Ruff/static checks for changed Python paths where applicable;
4. `scripts/check_architecture_boundaries.py`;
5. reuse declaration/checker where applicable;
6. `git diff --check` and exact changed-path validation;
7. canonical hosted verification after push.

No second verifier is created by #187.

## Failure behavior

### Missing or corrupt observation cache

- discard cache;
- fresh-reconstruct from GitHub;
- do not fail open.

### GitHub/cache disagreement

- GitHub wins;
- rebuild projection and both fingerprints;
- invalidate stale task handles as required.

### Incomplete canonical evidence

```text
OBSERVATION_INCOMPLETE
ACTIONABILITY=BLOCKED
MISSING=<exact missing canonical evidence>
```

### Material change with same task fingerprint

- process material transition;
- do not suppress it;
- rejoin existing role only if still correct/current.

### Clock-only observation change

- no material transition;
- no duplicate role spawn.

## Adversarial acceptance matrix

The default no-code rollout and any future helper must prove all of these semantics:

| Case | Expected material result | Expected orchestration result |
|---|---|---|
| identical canonical projection | `NO_MATERIAL_TRANSITION` | `NO_ACTION` or valid-handle reuse only |
| only `observed_at` changes | `NO_MATERIAL_TRANSITION` | no spawn |
| CI tests PENDING -> SUCCESS | `HOSTED_CI_TERMINAL_CHANGED` | fresh authority/actionability resolution |
| reuse PENDING -> FAILURE | `HOSTED_CI_TERMINAL_CHANGED` | fail closed / route blocker |
| Integration PENDING -> PASS | `REVIEWER_TERMINAL_CHANGED` | consume fresh verdict if current |
| Security PASS -> CHANGES_REQUIRED | `REVIEWER_TERMINAL_CHANGED` | stale actionability invalidated |
| writer ACTIVE -> STOP_WRITE | `WRITER_STOP_WRITE_OR_TERMINAL` | successor/review routing considered same cycle |
| writer terminal id changes | `WRITER_STOP_WRITE_OR_TERMINAL` | consume exact new terminal |
| head changes | `PR_HEAD_CHANGED` | prior reviews/currentness invalidated |
| main/synthetic classification changes | `SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED` | re-epoch/revalidation required |
| merged false -> true + merge SHA appears | `ACTUAL_MERGE` | capture merge/re-epoch successors |
| authority comment changes | `AUTHORITY_EPOCH_CHANGED` | fresh authority dominates all lower events |
| CI + reviewer change in one scan | stable ordered transition set | process CI before reviewer, preserve both |
| same task fingerprint but reviewer changes | reviewer transition still detected | no suppression by task de-dup |
| cache deleted | full reconstruction | same canonical material result |

## KPI definitions

Measure from existing timestamps where possible:

- `STOP_WRITE -> review route latency`;
- `paired PASS -> SOL merge-decision latency`;
- `actual merge -> successor activation latency`;
- duplicate ephemeral role spawns per unchanged material state;
- actionable `CONTROL_PLANE_DEADLOCK` count;
- `ZERO-SILENT-BATON` violation count;
- post-GREEN architecture/public-seam blocker leakage count;
- full-state reconstruction scans avoided through safe bounded delta handling.

Targets:

```text
CONTROL_PLANE_DEADLOCK = 0
ZERO_SILENT_BATON_VIOLATION = 0
DUPLICATE_EPHEMERAL_SPAWN_ON_UNCHANGED_MATERIAL_STATE = 0
POST_GREEN_ARCHITECTURE_BLOCKER_LEAKAGE = 0
```

Latency targets are measured first; no workflow/daemon/helper is justified without evidence that the existing watchdog cannot meet the accepted target.

## Default rollout and conditional future helper

Default recommendation: **NO NEW REPOSITORY RUNTIME**.

Luna applies the two-projection semantics within the existing orchestration/watchdog process:

- canonical material projection + `MATERIAL_STATE_FINGERPRINT` for event detection;
- task tuple + `TASK_FINGERPRINT` for duplicate role-work suppression.

If a measured trial proves deterministic local handling is insufficient, a future separate implementation issue may authorize exactly:

- `scripts/control_plane_state.py`
- `tests/test_control_plane_state.py`

That helper must be pure/offline, receive already-fetched normalized data, emit advisory projection/diff/fingerprints only, add no dependency, call no GitHub/network, spawn no agent, write no comment, merge nothing, and hold no authority.

## Rollback

Planning rollback: close PR unmerged.

Operational no-code rollout rollback: discard advisory cache and return to full fresh-read watchdog behavior.

Future helper rollback, if separately authorized: revert the bounded helper commit; GitHub authority remains unaffected.

## Acceptance

#187 planning is acceptable only when independent Integration and Security review confirm that:

- material-state detection and task de-duplication are separate deterministic contracts;
- observation-only time cannot false-trigger a material event;
- CI/reuse/reviewer/writer/merge/authority changes cannot be missed because of same task fingerprint;
- simultaneous material changes have deterministic ordering;
- cache remains advisory and reconstructible;
- GitHub remains sole authority;
- no runtime/workflow/dependency/live/system scope is introduced;
- exact planning write-set remains the two authorized docs.
