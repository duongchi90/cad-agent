# Luna Event-Driven Control Plane Design

## Status and authority

- Issue: #187.
- Control contract: `CONTROL_CONTRACT_VERSION=1.3`.
- Planning epoch/base: `ff93ddaa2ebb69e21f81baaa4f3dceec1db009ae`.
- Binding authority: Issue #187, V3 delta comment `5255200043`, Human Owner written-spec approval recorded at #187 comment `5306410590`, with newer Human Owner / #131 / SOL control always taking precedence.
- Scope: PLANNING / DESIGN ONLY.
- Repository production/runtime implementation: NOT AUTHORIZED by #187.
- AutoCAD, File-IPC, provider, private/customer CAD, publication, PC3/PMP, profile, registry, printer/driver/system execution: NOT AUTHORIZED.
- Exact #187 planning write-set is only:
  - `docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md`
  - `docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md`

This design must not move the currently pinned `main`, merge any HOLD PR, or change the Gate-1G local baton.

## Problem

The project already has repository, CI, exact-tuple review, merge, authority, and live-execution gates. The control-plane inefficiency is orchestration latency and duplicate reconstruction: a material change can become actionable while Luna waits for a later scan, reconstructs too much state, respawns equivalent role work, or fails to distinguish a real transition from an observation-only change.

The design solves two separate problems with two separate contracts:

1. **Material-transition detection** — determine whether canonical execution-relevant state changed since the prior observation.
2. **Ephemeral-task de-duplication** — determine whether equivalent role/task work is already in-flight or already terminal for the exact same work identity.

These contracts MUST NOT be conflated.

## Goals

The design SHALL:

- keep GitHub and accepted contracts as the only authority;
- use the existing Luna watchdog as transport/fallback instead of adding a second scheduler;
- detect bounded material-state transitions deterministically;
- explicitly ignore observation-only changes such as watchdog time;
- guarantee that every projected-field difference maps to a deterministic transition class or a fail-closed schema-violation class;
- observe same-result CI/reuse and reviewer-terminal supersession using stable GitHub identities rather than coarse result tokens alone;
- enforce no-material-event/no-duplicate-agent semantics;
- prevent a same task fingerprint from suppressing changed material state;
- route already-authorized actions in the same scan cycle that observes the material transition;
- preserve strict exact-main/exact-head/exact-synthetic reviewer currentness;
- preserve/rejoin the same correct-role reviewer context where possible while requiring a fresh verdict for a changed tuple;
- detect `ZERO-SILENT-BATON` and `CONTROL_PLANE_DEADLOCK` failures;
- support explicit conditional SOL preauthorization without inventing authority;
- target N+1 readiness as `PATCH_READY` or `ONLY_LATE_BINDINGS_PENDING` where safe;
- require `REQUIRED_PUBLIC_SEAMS` audit before downstream RED;
- derive cycle-time/resource KPIs from existing GitHub/action/comment evidence where possible;
- optimize Luna discovery/reconstruction and equivalent ephemeral-spawn duplication only;
- preserve full Master Audit, Integration/Security, and R3/R4/R5/R6 specialist reasoning depth;
- fail closed whenever canonical state reconstruction is incomplete, contradictory, or outside the declared material schema.

## Non-goals

This design SHALL NOT:

- create a second scheduler, merge authority, review authority, CI authority, store, database, queue, daemon, webhook service, or truth source;
- add or modify a GitHub Actions workflow under #187;
- infer repository-write, merge, live, repair, approval, publication, or system authority from detector output;
- treat cache state, model memory, chat history, stale SHA, stale synthetic, or stale reviewer verdict as authority;
- weaken STOP_WRITE, RED-first, hosted CI/reuse, paired independent review, exact-main pin, or live gates;
- touch AutoCAD/File-IPC/provider/private/customer/publication/system surfaces;
- alter the R0-R8 functional architecture;
- apply token/resource suppression to Master Audit, Integration/Security review, persistent R3/R4/R5/R6 Web Code lanes, required fresh GitHub reads, material-transition communication, or exact terminal evidence.

## Reuse audit

The selected design reuses existing owners and surfaces rather than adding infrastructure.

### Existing GitHub authority/state surfaces

Reuse directly:

- actual `refs/heads/main` and commit identity;
- #131 / Human Owner / SOL comments as durable authority epoch and baton bus;
- PR number/base/head, merge-ref/synthetic, draft/open/closed/merged state, merge SHA, and timestamps;
- GitHub Actions workflow run ID, run attempt, state/result, and terminal timestamps for tests/reuse;
- exact-head Integration/Security review submission IDs, verdicts, and timestamps;
- writer STOP_WRITE/terminal comment identities;
- issue/PR/comment/action timestamps for KPI derivation.

No second project database, event store, approval store, review store, or merge-state store is required.

### Existing Luna/SOL orchestration mechanisms

Reuse directly:

- existing periodic Luna watchdog/scan as transport and missed-event fallback;
- SOL as repository/governance/integration authority;
- Luna as bounded local executor/scheduler within delegated authority;
- existing correct-role reviewer handles for bounded context reuse, while still requiring a fresh exact-tuple verdict after tuple changes;
- existing `STOP_WRITE`, terminal handoff, explicit owner/next-trigger/blocker, and exact-main pin controls.

The missing capability is not a new scheduler. It is a deterministic contract for deciding whether canonical material state changed and whether equivalent role work already exists.

### Existing repository verification mechanisms

Reuse directly:

- `scripts/verify.ps1` as canonical hosted/offline verification owner;
- `scripts/check_architecture_boundaries.py` for architecture boundaries;
- `scripts/check_reuse_declaration.py` plus the reuse-declaration workflow;
- `scripts/reuse_inventory.py` for reuse ownership/completeness;
- existing focused pytest/.NET owner tests, Ruff/static checks, and `git diff --check`.

#187 creates no second verifier.

### Reuse conclusion

Current GitHub + Luna + existing verification surfaces are sufficient for the default rollout. The genuinely missing capability is a documented material-state projection/transition contract plus a separate task de-dup contract. Therefore the default recommendation remains **no new repository runtime**.

## Alternatives and trade-offs

### Alternative A — GitHub-native observation + existing Luna watchdog

Each normal Luna scan fresh-reads bounded canonical GitHub state, builds `MATERIAL_STATE_PROJECTION`, classifies changes, resolves authority, then applies separate task de-duplication.

Advantages:

- reuses current GitHub authority and Luna scheduler/watchdog;
- no workflow, daemon, secret-bearing service, database, queue, or second authority;
- missed/corrupt local cache falls back to full fresh-read on the next watchdog scan;
- preserves exact-main, exact-head, reviewer-currentness, and live gates.

Trade-off:

- event-to-action latency is bounded by normal watchdog cadence rather than instantaneous push delivery.

**Selection:** chosen as the cheapest safe architecture.

### Alternative B — GitHub Actions event dispatcher

A future GitHub Actions workflow could react to PR/check/review/merge events and emit a compact transition packet for Luna/SOL consumption.

Advantages:

- potentially lower event-to-detection latency;
- remains GitHub-hosted rather than adding an external daemon.

Trade-offs:

- requires workflow mutation outside #187 authority;
- introduces event-ordering, duplicate-delivery, and missed-event reconciliation concerns;
- risks drifting into a second scheduler/control authority unless tightly constrained;
- still requires fresh authority validation and watchdog fallback.

This is a future fallback only if measured KPI evidence shows Alternative A cannot meet the accepted SLA and a separate implementation issue explicitly authorizes it.

### Alternative C — dedicated webhook/daemon + persistent state store

A long-running service could receive GitHub webhooks, persist state, and drive orchestration transitions.

Advantages:

- lowest theoretical event latency;
- flexible event aggregation.

Trade-offs:

- creates service/deployment/availability, secret-handling, and persistent-store surfaces;
- duplicates state recoverable from GitHub;
- materially increases risk of a second truth/scheduler/authority plane;
- adds recovery, ordering, and migration complexity without evidence it is needed.

**Decision:** rejected under reuse-first/YAGNI and current #187 authority.

## Selected architecture

Select **GitHub-native observation plus the existing Luna watchdog**.

The system is **edge-triggered in semantics, watchdog-driven in transport**:

1. Luna fresh-reads canonical GitHub state required by the current baton.
2. Luna normalizes a canonical material-state projection containing only execution-relevant state and stable terminal identities.
3. Luna hashes that projection as `MATERIAL_STATE_FINGERPRINT` and compares it with the prior advisory observation.
4. If the projection is identical, there is no material transition even if `observed_at` or watchdog time changed.
5. If the projection changed, Luna computes a deterministic transition set from an exhaustive field-to-class map.
6. If any projected difference is not mapped by the declared schema, Luna emits `UNMAPPED_MATERIAL_DIFF` and fails closed.
7. Luna fresh-validates controlling authority.
8. If an action is already authorized, Luna routes/starts it in the same cycle.
9. Only after actionability is known does Luna use the separate `TASK_FINGERPRINT` to spawn, rejoin, or suppress duplicate role work.
10. Missing/corrupt cache causes full reconstruction from GitHub; it never fails open.

The detector decides **what changed**. The authority resolver decides **what may happen**. The task de-dup layer decides **whether equivalent role work already exists**.

## Canonical observation schema

A Luna observation MAY contain:

```json
{
  "schema_version": "luna-control-observation-1.2",
  "observed_at": "2026-08-16T09:00:00Z",
  "material_state": {
    "current_main": "<sha>",
    "authority_epoch": "<issue/comment-id>",
    "task_or_issue": "<stable-id>",
    "pr": {
      "number": 263,
      "head": "<sha-or-NONE>",
      "synthetic_or_state": "<sha-or-normalized-state>",
      "state": "OPEN|CLOSED|NONE",
      "draft": true,
      "merged": false,
      "merge_sha": "NONE"
    },
    "ci": {
      "tests": {
        "state": "PENDING|SUCCESS|FAILURE|NOT_APPLICABLE",
        "terminal_id": "<run-id:attempt-or-NONE>"
      },
      "reuse": {
        "state": "PENDING|SUCCESS|FAILURE|NOT_APPLICABLE",
        "terminal_id": "<run-id:attempt-or-NONE>"
      }
    },
    "reviews": {
      "REVIEWER_INTEGRATION": {
        "state": "PENDING|PASS|CHANGES_REQUIRED|NOT_REQUIRED",
        "terminal_id": "<review-id-or-NONE>"
      },
      "REVIEWER_SECURITY": {
        "state": "PENDING|PASS|CHANGES_REQUIRED|NOT_REQUIRED",
        "terminal_id": "<review-id-or-NONE>"
      }
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

### Stable terminal identity rules

Stable terminal identities come only from already-existing GitHub evidence:

- tests/reuse CI terminal identity: `workflow_run_id:run_attempt`;
- Integration/Security reviewer terminal identity: exact GitHub review submission ID/node ID for the current exact tuple;
- writer terminal identity: durable STOP_WRITE/terminal comment or accepted terminal packet ID.

For an in-progress CI run, `terminal_id` MAY identify the current run/attempt even before terminal so a newly started run is observable. `NONE` is used when no applicable run/review/terminal exists.

These IDs are **currentness evidence only**. They are not authority and cannot promote a result by themselves.

`observed_at` is observation-only and excluded from material comparison. The observation is advisory/cache-only and SHALL NOT contain secrets, private CAD data, raw evidence payloads, private file contents, or authority not present on GitHub.

## Canonical material-state projection

`MATERIAL_STATE_PROJECTION` contains exactly these normalized fields:

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

It explicitly excludes:

```text
observed_at
watchdog_scan_number
local clock
API latency
fetch duration
cache path
process id
free-form chat text
non-controlling repeated comments
log ordering that does not change a canonical terminal identity
```

Absent optional values normalize to literal `NONE`; closed enums are used wherever possible; keys serialize in canonical sorted order; SHA-256 produces `MATERIAL_STATE_FINGERPRINT`.

## Material-transition comparison

The detector compares previous/current canonical material projections field-by-field before hash equality is used as a compact check.

```text
identical MATERIAL_STATE_PROJECTION
    => NO_MATERIAL_TRANSITION
only observation-only fields changed
    => NO_MATERIAL_TRANSITION
one or more declared material fields changed
    => MATERIAL_TRANSITION_SET = deterministic mapped classes
any projected difference lacks a declared mapping
    => TRANSITION_SET=[UNMAPPED_MATERIAL_DIFF]
       ACTIONABILITY=BLOCKED
       PRIMARY_NEXT_OWNER=SOL
```

A same task fingerprint MUST NOT suppress changed material state.

## Exhaustive field-to-transition map

Every field in `MATERIAL_STATE_PROJECTION` is closed under this map.

### `UNMAPPED_MATERIAL_DIFF`

Trigger:

- a projected key exists or changes but is not covered by this declared map;
- projection schema/version changes without an explicitly accepted migration rule;
- a supposedly impossible normalized value appears.

Behavior:

- highest precedence;
- fail closed;
- no role spawn/merge/live/repository action is inferred;
- SOL must classify/update the contract before action continues.

### `AUTHORITY_EPOCH_CHANGED`

Fields:

- `authority_epoch`.

Trigger: controlling authority comment/packet identity changes.

### `TASK_OR_PR_IDENTITY_CHANGED`

Fields:

- `task_or_issue`;
- `pr.number`.

Trigger: either stable task/issue identity or PR number changes, including `NONE` <-> concrete PR identity.

Behavior: prior task handles, exact-PR review currentness, and task-bound cache classifications are invalidated and reconstructed before downstream actionability is considered.

### `ACTUAL_MERGE`

Fields:

- `pr.merged`;
- `pr.merge_sha`.

Trigger: `pr.merged` changes `false -> true` or `pr.merge_sha` changes `NONE -> <exact merge SHA>` consistently with GitHub merge truth.

Any impossible reversal or contradictory merge identity is `UNMAPPED_MATERIAL_DIFF`/schema violation and fails closed.

### `PR_HEAD_CHANGED`

Field:

- `pr.head`.

Trigger: head changes while task/PR identity remains the same. If task/PR identity also changes, `TASK_OR_PR_IDENTITY_CHANGED` is emitted as well.

### `SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED`

Fields:

- `current_main`;
- `pr.synthetic_or_state`;
- `pr.state`;
- `pr.draft`.

Trigger: any of those fields changes, except a merge-specific state change already represented by `ACTUAL_MERGE`; all applicable classes remain in the transition set.

### `HOSTED_CI_TERMINAL_CHANGED`

Fields:

- `ci.tests.state`;
- `ci.tests.terminal_id`;
- `ci.reuse.state`;
- `ci.reuse.terminal_id`.

Trigger examples:

- `PENDING -> SUCCESS`;
- `PENDING -> FAILURE`;
- `SUCCESS -> PENDING` because a newer run starts;
- `SUCCESS(runA:1) -> SUCCESS(runB:1)` when a fresh terminal run supersedes prior evidence before an intermediate scan;
- `SUCCESS(runA:1) -> SUCCESS(runA:2)` after a rerun attempt;
- any current run/attempt identity change.

A terminal identity change is material even when the coarse state token is unchanged. This makes same-result supersession observable rather than inferred.

### `REVIEWER_TERMINAL_CHANGED`

Fields:

- `reviews.REVIEWER_INTEGRATION.state`;
- `reviews.REVIEWER_INTEGRATION.terminal_id`;
- `reviews.REVIEWER_SECURITY.state`;
- `reviews.REVIEWER_SECURITY.terminal_id`.

Trigger examples:

- `PENDING -> PASS`;
- `PENDING -> CHANGES_REQUIRED`;
- `PASS -> CHANGES_REQUIRED`;
- `CHANGES_REQUIRED -> PASS`;
- `PASS(reviewA) -> PASS(reviewB)` when a fresh exact-current-tuple review supersedes prior review evidence;
- any current reviewer terminal identity change.

A review ID change is material even when the verdict token is unchanged. A new review must still be checked for exact tuple/currentness and does not inherit authority from the old review.

### `WRITER_STOP_WRITE_OR_TERMINAL`

Fields:

- `writer.state`;
- `writer.terminal_id`.

Trigger: writer enters `STOP_WRITE`, `TERMINAL_PASS`, or `TERMINAL_BLOCKED`; leaves/changes an active state; or terminal identity changes.

### `BATON_CHANGED`

Fields:

- `baton.current_owner`;
- `baton.next_trigger`;
- `baton.blocker`.

Trigger: any baton field changes. This class is advisory and cannot create authority.

## Multiple simultaneous changes and precedence

A scan may observe several transitions. The detector returns all mapped classes as a stable ordered set.

Canonical precedence:

```text
0. UNMAPPED_MATERIAL_DIFF
1. AUTHORITY_EPOCH_CHANGED
2. TASK_OR_PR_IDENTITY_CHANGED
3. ACTUAL_MERGE
4. PR_HEAD_CHANGED
5. SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED
6. WRITER_STOP_WRITE_OR_TERMINAL
7. HOSTED_CI_TERMINAL_CHANGED
8. REVIEWER_TERMINAL_CHANGED
9. BATON_CHANGED
```

All detected classes remain in `TRANSITION_SET`; precedence controls validation/action ordering only. If a higher-precedence transition invalidates lower evidence, lower evidence remains observed but cannot authorize stale use.

Example:

```text
TRANSITION_SET=[TASK_OR_PR_IDENTITY_CHANGED, PR_HEAD_CHANGED, REVIEWER_TERMINAL_CHANGED]
PRIMARY_TRANSITION=TASK_OR_PR_IDENTITY_CHANGED
```

## Projection-closure invariant

The material detector has one hard invariant:

```text
for every changed key in MATERIAL_STATE_PROJECTION:
    mapped_transition_classes(changed_key) is non-empty
```

If the invariant is violated, the detector MUST emit `UNMAPPED_MATERIAL_DIFF`, fail closed, discard actionability derived from the incomplete classification, and route contract repair to SOL. An empty transition set with a changed material fingerprint is forbidden.

## Ephemeral task fingerprint and de-duplication

`TASK_FINGERPRINT` is separate from `MATERIAL_STATE_FINGERPRINT` and identifies one unit of role work:

```text
(role,
 task_or_issue,
 current_main,
 pr_head,
 synthetic_or_state,
 authority_epoch,
 intended_output)
```

Canonical `intended_output` values include `WRITE_RED`, `WRITE_GREEN`, `REVIEW`, `MERGE_DECISION`, `LOCAL_PREFLIGHT`, and `STATUS_ONLY`.

Decision order:

```text
material state changed
    => classify transition and resolve actionability first
same TASK_FINGERPRINT + valid correct-role in-flight handle
    => REJOIN_HANDLE
same TASK_FINGERPRINT + equivalent durable current terminal
    => NO_DUPLICATE_SPAWN
same TASK_FINGERPRINT + no new material state
    => NO_ACTION
changed TASK_FINGERPRINT + authorized work required
    => SPAWN_OR_ROUTE_MINIMUM_REQUIRED_ROLE
```

A same task fingerprint is never evidence that CI/review/writer/material state did not change.

## No-event / no-agent rule

A watchdog tick, fresh read, timestamp movement, or unchanged material fingerprint alone MUST NOT spawn an expensive ephemeral agent.

```text
NO_MATERIAL_TRANSITION + valid in-flight equivalent handle => REJOIN/OBSERVE_ONLY
NO_MATERIAL_TRANSITION + no executable authorized work => NO_ACTION
MATERIAL_TRANSITION => resolve authority/actionability first
```

Fresh GitHub reads required by a role are not suppressed by this rule.

## Material transition handling and authority resolution

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

If `ACTIONABILITY=AUTHORIZED`, route/start the bounded action in the same watchdog cycle unless an equivalent valid in-flight task handle exists.

If `ACTIONABILITY=BLOCKED`, persist exactly one controlling missing prerequisite/authority and next trigger. Generic `WAIT` is insufficient where a concrete blocker can be named.

Transition detection never creates authority. For every material transition Luna fresh-validates:

- controlling Human Owner / #131 / SOL packet;
- exact main/base;
- exact task/PR/head/synthetic where bound;
- writer lock/write-set;
- required CI/review predicates and exact terminal identities;
- local/live pin constraints;
- next owner/trigger;
- material invalidators.

Missing/stale/contradictory authority fails closed.

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
- paired final PASS on exact unchanged tuple -> merge-eligibility decision;
- actual merge -> capture merge SHA, re-epoch affected successors, activate next eligible bounded gate.

The detector SHALL NOT synthesize preauthorization. Pinned-main/local-live constraints override generic preauthorization.

## ZERO-SILENT-BATON

A baton is explicit only when all are known:

```text
BATON_STATE=(
  current_owner,
  executable_action_or_blocker,
  next_trigger,
  authority_epoch
)
```

Every material transition ending one role's work leaves exactly one of:

- executable next owner/action;
- concrete blocker owner + missing prerequisite;
- terminal no-further-action state.

Repeated generic `WAIT` states are forbidden when a concrete blocker can be named.

## CONTROL_PLANE_DEADLOCK

A control-plane deadlock exists only when all are true:

1. current baton identifies an executable action;
2. required authority/evidence is already present and fresh;
3. no conflicting writer/main/live/epoch lock forbids the action;
4. action was neither started/routed in the transition cycle nor represented by a valid in-flight equivalent task handle;
5. a later watchdog scan sees the same actionable material state unchanged.

On detection Luna SHALL report the deadlock and perform the already-authorized action in that scan. Target: `0` actionable control-plane deadlocks.

CI/reviewer in-flight state, pinned-main HOLD, local-machine prerequisite, explicit Human gate, or true external wait is not a deadlock.

## Reviewer routing and currentness

Canonical reviewer roles:

```text
REVIEWER_INTEGRATION
REVIEWER_SECURITY
```

When paired review is required, route both in parallel. For a bounded repair, Luna SHOULD rejoin existing correct-role reviewer contexts where available.

Handle reuse is context reuse only. A changed head/synthetic/main/authority/task tuple requires a fresh review. Prior PASS/CHANGES_REQUIRED is never promoted to a changed tuple.

Reviewer `terminal_id` exists only to observe fresh review submission/currentness, including same-result supersession. It never allows stale verdict reuse.

## N+1 readiness

While phase N executes, safe off-critical-path preparation for N+1 should target:

- `PATCH_READY`; or
- `ONLY_LATE_BINDINGS_PENDING`.

`PLANNING_ONLY_READY` is not the target when architecture, owner, public seam, write-set, and RED matrix can safely be closed further.

This does not authorize overlapping production writers.

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

Before first GREEN push for a production slice, compose only existing checks:

1. exact focused RED/GREEN tests;
2. focused tests for consumed public-seam owners;
3. Ruff/static checks for changed Python paths where applicable;
4. `scripts/check_architecture_boundaries.py`;
5. reuse declaration/checker where applicable;
6. `git diff --check` and exact changed-path validation;
7. canonical hosted verification after push.

This local bundle never replaces hosted final CI/reuse, independent review, exact-head validation, or live gates. No new workflow is required by #187.

## KPI derivation

Metrics derive from existing GitHub/action/comment timestamps whenever possible. A separate metrics database is forbidden.

### Core latency metrics

```text
writer_unlock_to_stop_write
    = writer STOP_WRITE timestamp - production unlock timestamp

stop_write_to_ci_terminal
    = final required hosted CI terminal timestamp - STOP_WRITE timestamp

stop_write_to_review_start
    = first required reviewer route/start timestamp - STOP_WRITE timestamp

ci_terminal_to_reviewer_terminal
    = final required reviewer terminal timestamp - final required CI terminal timestamp

paired_pass_to_merge
    = actual merge timestamp - timestamp when final required PASS made exact tuple merge-eligible

merge_to_successor_activation
    = successor issue/unlock timestamp - actual merge timestamp
```

If merge is intentionally blocked by an explicit epoch/main pin or other accepted policy lock, `paired_pass_to_merge` is classified `HOLD_BY_POLICY`, not control-plane idle time.

### Quality/efficiency metrics

- `actionable_baton_idle_cycles`: watchdog cycles where an unchanged executable baton existed without valid in-flight action. Target `0`.
- `review_repair_cycles`: CHANGES_REQUIRED -> repair -> fresh-review loops for the final task/PR lineage.
- `architecture_blockers_first_discovered_after_green`: required-owner/public-seam/architecture blockers first identified only after GREEN. Target `0`.
- `luna_discovery_token_share`: Luna tokens spent reconstructing already-available state divided by Luna orchestration tokens for the sampled cycle/window. If trustworthy token accounting is unavailable, report literal `NOT_AVAILABLE`.
- `duplicate_ephemeral_spawn_on_unchanged_material_state`: equivalent role spawns where material projection and task identity were unchanged. Target `0`.
- `zero_silent_baton_violation`: material transitions ending without explicit next owner/blocker/terminal. Target `0`.
- `control_plane_deadlock`: actionable deadlock count. Target `0`.

The no-code trial/helper-escalation decision must use this full KPI set, not a narrower substitute.

## Resource policy

Token/resource optimization applies ONLY to:

- Luna discovery/reconstruction of already-available state;
- equivalent ephemeral orchestration spawn de-duplication;
- duplicate non-material GitHub status commentary where the durable canonical state is already present.

It SHALL NOT:

- reduce Master Audit depth;
- reduce Integration/Security adversarial review depth;
- reduce persistent R3/R4/R5/R6 specialist reasoning;
- suppress fresh GitHub reads required by a role;
- suppress material-transition communication;
- omit exact terminal identities/evidence;
- shorten required architecture/currentness/security reasoning to meet a token target.

Master Audit, Integration/Security reviewers, and persistent R3/R4/R5/R6 lanes are explicitly **non-token-limited**. The optimization is de-duplication and delta-first reconstruction, not shallower engineering analysis.

## Failure and rollback

The design is fail-closed and cache-discardable.

- Missing cache -> full fresh GitHub reconstruction.
- Corrupt/unparseable cache -> discard cache and full fresh reconstruction.
- GitHub/cache disagreement -> GitHub wins and cache is replaced.
- Missed event -> next normal watchdog scan reconstructs current truth.
- Duplicate/out-of-order observation -> exact identities + authority epoch prevent stale promotion.
- Changed main/head/task/PR/synthetic/authority epoch -> dependent currentness is invalidated and re-evaluated.
- Changed CI/reviewer terminal identity -> currentness is re-evaluated even when result token is unchanged.
- Unmapped projected diff -> `UNMAPPED_MATERIAL_DIFF`, ACTIONABILITY=BLOCKED, SOL contract repair.
- Conflicting active writer or pinned-main lock -> HOLD/BLOCKED even if other predicates pass.
- Reviewer handle unavailable -> spawn fresh correct-role reviewer; never substitute wrong role.
- Metrics unavailable -> literal `NOT_AVAILABLE`; never invent evidence.

Rollback of any future implementation is removal/disablement of the advisory detector/cache path; the periodic full fresh-read watchdog remains the safe baseline.

## Security and authority boundaries

Detector/cache outputs have no independent authority to:

- write production repository code;
- merge a PR;
- mark a review PASS;
- authorize AutoCAD/File-IPC/live execution;
- mutate private/customer/source/accepted CAD;
- authorize repair, approval, publication, or production acceptance;
- change system/profile/printer/registry state.

Stable run/review/comment IDs are currentness evidence only. They must not be interpreted as approval or authority.

Secrets, credentials, private evidence, private paths, raw CAD contents, and provider payloads must never enter the observation snapshot.

## Adversarial acceptance matrix

The default no-code rollout and any future helper must prove at least:

| Case | Expected material result | Expected orchestration result |
|---|---|---|
| identical canonical projection | `NO_MATERIAL_TRANSITION` | `NO_ACTION` or valid-handle reuse only |
| only `observed_at` changes | `NO_MATERIAL_TRANSITION` | no spawn |
| `task_or_issue` changes only | `TASK_OR_PR_IDENTITY_CHANGED` | invalidate task-bound currentness; fresh authority/actionability |
| `pr.number` changes only | `TASK_OR_PR_IDENTITY_CHANGED` | invalidate PR-bound currentness; fresh authority/actionability |
| head changes on same PR | `PR_HEAD_CHANGED` | prior exact-head review/currentness invalidated |
| main/synthetic/draft/state changes | `SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED` | re-epoch/revalidation as required |
| tests PENDING -> SUCCESS | `HOSTED_CI_TERMINAL_CHANGED` | fresh authority/actionability |
| reuse PENDING -> FAILURE | `HOSTED_CI_TERMINAL_CHANGED` | fail closed / route blocker |
| tests SUCCESS(run A) -> SUCCESS(run B) | `HOSTED_CI_TERMINAL_CHANGED` | consume fresh run identity; no stale reuse |
| reuse SUCCESS(run A:1) -> SUCCESS(run A:2) | `HOSTED_CI_TERMINAL_CHANGED` | consume rerun attempt identity |
| Integration PENDING -> PASS | `REVIEWER_TERMINAL_CHANGED` | consume only if exact current tuple |
| Security PASS -> CHANGES_REQUIRED | `REVIEWER_TERMINAL_CHANGED` | stale actionability invalidated |
| Integration PASS(review A) -> PASS(review B) | `REVIEWER_TERMINAL_CHANGED` | consume fresh review identity/currentness |
| writer ACTIVE -> STOP_WRITE | `WRITER_STOP_WRITE_OR_TERMINAL` | review/successor routing considered same cycle |
| writer terminal ID changes | `WRITER_STOP_WRITE_OR_TERMINAL` | consume exact new terminal |
| merged false -> true + merge SHA appears | `ACTUAL_MERGE` | capture merge/re-epoch successors |
| authority comment changes | `AUTHORITY_EPOCH_CHANGED` | fresh authority dominates lower events |
| baton owner/trigger/blocker changes | `BATON_CHANGED` | advisory baton reconciliation |
| CI + reviewer change in one scan | stable ordered transition set | preserve/process both |
| task identity + head + reviewer change | stable ordered transition set | identity invalidation before head/review use |
| same task fingerprint but reviewer identity changes | reviewer transition still detected | no suppression by task de-dup |
| unknown projected key changes | `UNMAPPED_MATERIAL_DIFF` | fail closed; SOL contract repair |
| cache deleted/corrupt | full reconstruction | same canonical material result |

## RED-first future implementation strategy

No production implementation is authorized under #187. If a later explicit implementation issue proves repository code is genuinely needed, the cheapest bounded fallback may be a pure control-plane helper such as:

- `scripts/control_plane_state.py`
- `tests/test_control_plane_state.py`

A future RED must prove:

- canonical material projection normalization;
- exhaustive field-to-transition closure;
- unknown projected diffs fail closed;
- task/PR identity-only changes are material;
- CI/reuse same-result fresh terminal identities are material;
- reviewer same-result fresh terminal identities are material;
- observation-only time is non-material;
- stable simultaneous-transition ordering;
- same task fingerprint cannot suppress material change;
- deadlock vs legitimate HOLD distinction;
- missing/corrupt cache fallback;
- stale reviewer PASS cannot survive changed tuple/currentness;
- KPI derivation including `HOLD_BY_POLICY` and `NOT_AVAILABLE` semantics;
- no secret/private/live/system fields accepted into snapshot.

The helper, if separately authorized, must be pure/offline: already-fetched normalized dictionaries in, advisory projection/diff/fingerprints out. It must call no GitHub/network, spawn no agent, persist no authority store, write no comment, merge nothing, and authorize nothing.

Preferred first rollout remains **no repository production code**: encode these rules in Luna/SOL orchestration instructions and use existing GitHub connector reads. Repository code is justified only by measured evidence that deterministic handling cannot be maintained safely without it.

## Acceptance criteria

#187 planning is acceptable only when independent Integration and Security review confirm all of the following:

- GitHub remains sole truth/authority;
- selected architecture is GitHub-native observation + existing Luna watchdog;
- no-event/no-agent is explicit;
- `MATERIAL_STATE_FINGERPRINT` and `TASK_FINGERPRINT` are separate;
- every projected field is deterministically mapped;
- task/PR identity changes cannot create an empty transition set;
- same-result CI/reuse supersession is observable by run/attempt identity;
- same-result reviewer supersession is observable by review identity;
- unknown/unmapped material diffs fail closed;
- simultaneous changes have stable precedence while preserving all classes;
- transition detection cannot create authority;
- same-cycle action occurs only when already authorized;
- `ZERO-SILENT-BATON` and `CONTROL_PLANE_DEADLOCK` are exact;
- reviewer handle reuse never reuses stale verdicts;
- conditional SOL preauthorization is supported but never inferred;
- N+1 targets `PATCH_READY` / `ONLY_LATE_BINDINGS_PENDING`;
- `REQUIRED_PUBLIC_SEAMS` precedes downstream RED;
- existing verifier/reuse/architecture owners compose the pre-push GREEN bundle;
- full V3 KPI chain and `HOLD_BY_POLICY` are explicit;
- `luna_discovery_token_share` reports `NOT_AVAILABLE` when trustworthy accounting is unavailable;
- Master Audit, Integration/Security, and persistent R3/R4/R5/R6 lanes remain explicitly non-token-limited;
- actionable deadlock target is zero;
- post-GREEN architecture-blocker leakage target is zero;
- cache failure falls back to periodic full fresh-read watchdog;
- exact planning write-set remains two docs;
- no production/runtime/workflow/dependency/persistent authority store/AutoCAD/live/system mutation is introduced.

## Terminal planning state

After fresh paired PASS on an exact current tuple:

```text
#187_PLANNING_STATUS=REPOSITORY_ACCEPTED_HOLD
DEFAULT_RUNTIME_IMPLEMENTATION=NONE
MATERIAL_EVENT_OWNER=MATERIAL_STATE_PROJECTION
TASK_DEDUP_OWNER=TASK_FINGERPRINT
UNMAPPED_DIFF_POLICY=FAIL_CLOSED_TO_SOL
TERMINAL_CURRENTNESS=STABLE_GITHUB_IDENTITIES
CONDITIONAL_FUTURE_HELPER=SEPARATE_ISSUE_REQUIRED
MAIN_MOVEMENT=NOT_AUTHORIZED_WHILE_GATE_PIN_ACTIVE
```
