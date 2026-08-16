# Luna Event-Driven Control Plane Design

## Status and authority

- Issue: #187
- Control contract: `CONTROL_CONTRACT_VERSION=1.3`
- Planning epoch: `ff93ddaa2ebb69e21f81baaa4f3dceec1db009ae`
- Binding authority: Issue #187, V3 delta comment `5255200043`, Human Owner written-spec approval at #187 comment `5306410590`, with newer #131 / Human Owner / SOL control always taking precedence.
- Scope: PLANNING / DESIGN ONLY.
- Repository production/runtime implementation: NOT AUTHORIZED by #187.
- AutoCAD, File-IPC, provider, private/customer CAD, publication, PC3/PMP, profile, registry, printer/driver/system execution: NOT AUTHORIZED.
- Exact #187 planning write-set is only:
  - `docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md`
  - `docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md`

This design must not move the currently pinned `main`, merge any HOLD PR, or change the current Gate-1G local baton.

## Problem

The project already has repository, CI, exact-tuple review, merge, authority, and live-execution gates. The control-plane inefficiency is orchestration latency and duplicate reconstruction: a material change can become actionable while Luna waits for a later scan, reconstructs too much state, respawns equivalent role work, or fails to distinguish a real transition from an observation-only change.

The design solves two different problems with two different contracts:

1. **Material-transition detection** — determine whether canonical execution-relevant state changed since the last observation.
2. **Ephemeral-task de-duplication** — determine whether equivalent role/task work is already in-flight or already terminal for the exact same work identity.

These contracts MUST NOT be conflated.

## Goals

The design SHALL:

- keep GitHub and accepted contracts as the only authority;
- use the existing Luna watchdog as transport/fallback instead of adding a second scheduler;
- detect bounded material state transitions deterministically;
- ignore observation-only changes such as watchdog time;
- enforce no-material-event/no-duplicate-agent semantics;
- prevent a same task fingerprint from suppressing changed material state;
- route already-authorized actions in the same scan cycle that observes the material transition;
- preserve strict exact-head/exact-synthetic reviewer currentness;
- preserve/rejoin the same correct-role reviewer context where possible while requiring a fresh verdict for a changed tuple;
- detect `ZERO-SILENT-BATON` and `CONTROL_PLANE_DEADLOCK` failures;
- support explicit conditional SOL preauthorization without inventing authority;
- target N+1 readiness as `PATCH_READY` or `ONLY_LATE_BINDINGS_PENDING` where safe;
- require `REQUIRED_PUBLIC_SEAMS` audit before downstream RED;
- derive cycle-time/resource KPIs from existing GitHub/action/comment evidence where possible;
- optimize Luna discovery/reconstruction and equivalent ephemeral spawn duplication only;
- preserve full Master Audit, Integration/Security, and R3/R4/R5/R6 specialist reasoning depth;
- fail closed whenever canonical state reconstruction is incomplete or contradictory.

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
- #131 / Human Owner / SOL issue comments as durable authority epoch and baton bus;
- PR base/head, merge-ref/synthetic, draft/open/merged state, merge SHA and timestamps;
- GitHub Actions tests/reuse workflow states and terminal timestamps;
- exact-head Integration/Security review submissions and timestamps;
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
2. Luna normalizes a canonical material-state projection containing only execution-relevant state.
3. Luna hashes that projection as `MATERIAL_STATE_FINGERPRINT` and compares it with the prior advisory observation.
4. If the projection is identical, there is no material transition even if `observed_at` or watchdog time changed.
5. If the projection changed, Luna computes a deterministic transition set and stable precedence.
6. Luna fresh-validates controlling authority.
7. If an action is already authorized, Luna routes/starts it in the same cycle.
8. Only after actionability is known does Luna use the separate `TASK_FINGERPRINT` to spawn, rejoin, or suppress duplicate role work.
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

`observed_at` is observation-only and excluded from all material comparisons. The observation is advisory/cache-only and SHALL NOT contain secrets, private CAD data, raw evidence payloads, private file contents, or authority not present on GitHub.

## Canonical material-state projection

`MATERIAL_STATE_PROJECTION` contains exactly these normalized fields:

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

Absent optional values normalize to literal `NONE`; closed enums are used wherever possible; keys serialize in canonical sorted order; SHA-256 produces `MATERIAL_STATE_FINGERPRINT`.

## Material-transition comparison

The detector compares previous/current canonical material projections field-by-field before hash equality is used as a compact check.

```text
identical MATERIAL_STATE_PROJECTION
    => NO_MATERIAL_TRANSITION
only observation-only fields changed
    => NO_MATERIAL_TRANSITION
any canonical material field changed
    => MATERIAL_TRANSITION_SET = deterministic changed classes
```

A same task fingerprint MUST NOT suppress changed material state.

### Transition classes

`AUTHORITY_EPOCH_CHANGED`
- `authority_epoch` changed.

`ACTUAL_MERGE`
- `pr.merged` false -> true, or `pr.merge_sha` `NONE` -> exact merge SHA.

`PR_HEAD_CHANGED`
- `pr.head` changed while PR/task identity remains the same.

`SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED`
- `current_main`, `pr.synthetic_or_state`, or PR currentness/draft state changed in a way that changes tuple/currentness classification and is not already represented as `ACTUAL_MERGE`.

`HOSTED_CI_TERMINAL_CHANGED`
- `ci.tests` or `ci.reuse` changes state, including pending -> terminal or a fresh run superseding prior terminal evidence.

`REVIEWER_TERMINAL_CHANGED`
- canonical reviewer state changes, including pending -> PASS/CHANGES_REQUIRED or a fresh exact-head verdict superseding prior verdict.

`WRITER_STOP_WRITE_OR_TERMINAL`
- writer enters `STOP_WRITE`, `TERMINAL_PASS`, or `TERMINAL_BLOCKED`, or `writer.terminal_id` changes.

`BATON_CHANGED`
- baton owner/next-trigger/blocker changes without a newer authority epoch; this is advisory and cannot create authority.

## Multiple simultaneous changes

A scan may observe several transitions. The detector returns a stable ordered transition set:

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

All classes remain in `TRANSITION_SET`; precedence controls validation/action ordering only. If a higher-precedence transition invalidates lower evidence, lower evidence remains observed but cannot authorize stale use.

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

Transition detection never creates authority. For every material transition Luna fresh-validates the controlling Human Owner / #131 / SOL packet, exact main/base, exact head/synthetic where bound, writer lock/write-set, required CI/review predicates, local/live pin constraints, next owner/trigger, and material invalidators. Missing/stale/contradictory authority fails closed.

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

Every material transition ending one role's work leaves exactly one of:

- executable next owner/action;
- concrete blocker owner + missing prerequisite;
- terminal state requiring no further action.

## CONTROL_PLANE_DEADLOCK

A deadlock exists only when all are true:

1. canonical baton identifies an executable action;
2. required authority/evidence is fresh and present;
3. no writer/main/live lock forbids it;
4. action was neither started/routed in the transition cycle nor represented by a valid in-flight equivalent handle;
5. a later watchdog scan sees the same actionable material state unchanged.

Target: `CONTROL_PLANE_DEADLOCK=0`.

True external waits, pinned-main HOLD, CI/reviewer in-flight, local-machine prerequisite, or explicit Human gate are not deadlocks.

## Reviewer routing and handle reuse

Canonical reviewer roles:

- `REVIEWER_INTEGRATION`
- `REVIEWER_SECURITY`

When both are required they are routed in parallel. A bounded repair may rejoin the same correct-role context, but a changed head/synthetic/authority tuple requires a fresh exact-head verdict. Prior PASS/CHANGES_REQUIRED is never promoted to the changed tuple.

A reviewer terminal is part of `MATERIAL_STATE_PROJECTION`, so fresh reviewer state remains observable even when `TASK_FINGERPRINT` itself is unchanged.

## N+1 readiness

Safe off-critical-path phase N+1 preparation targets:

- `PATCH_READY`; or
- `ONLY_LATE_BINDINGS_PENDING`.

`PLANNING_ONLY_READY` is not the target when owner/public-seam/write-set/RED-matrix work can be safely closed further. This does not authorize overlapping writers.

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

Before first GREEN push for a production slice, compose existing owners/checkers only:

1. exact focused RED/GREEN tests;
2. focused tests for consumed public-seam owners;
3. Ruff/static checks for changed Python paths where applicable;
4. `scripts/check_architecture_boundaries.py`;
5. reuse declaration/checker where applicable;
6. `git diff --check` and exact changed-path validation;
7. canonical hosted verification after push.

No second verifier is created by #187.

## Binding KPI derivation contract

This section is binding under Issue #187 and V3 comment `5255200043`. Any narrower KPI list in the implementation plan is illustrative only; Task 9 MUST consume this entire set.

Metrics SHALL be derived from existing GitHub/action/comment timestamps where possible. No second metrics database is allowed.

### Core latency metrics

- `writer_unlock_to_stop_write` = writer `STOP_WRITE` timestamp - production unlock timestamp.
- `stop_write_to_ci_terminal` = final required hosted CI terminal timestamp - `STOP_WRITE` timestamp.
- `stop_write_to_review_start` = first required reviewer-start/routing timestamp - `STOP_WRITE` timestamp.
- `ci_terminal_to_reviewer_terminal` = paired/final required review terminal timestamp - final required CI terminal timestamp.
- `paired_pass_to_merge` = actual merge timestamp - timestamp when final required PASS made the exact tuple merge-eligible.
- `merge_to_successor_activation` = successor issuance/unlock timestamp - actual merge timestamp.

If merge is intentionally blocked by an explicit policy/epoch/main pin, `paired_pass_to_merge` is `HOLD_BY_POLICY`, not control-plane idle time. A held PR MUST NOT be treated as latency debt merely because the hold is long.

### Quality and efficiency metrics

- `actionable_baton_idle_cycles`: watchdog cycles where an unchanged executable baton existed without a valid in-flight action. Target `0`.
- `review_repair_cycles`: count of `CHANGES_REQUIRED -> repair -> fresh-review` loops for the bounded task/tuple lineage.
- `architecture_blockers_first_discovered_after_green`: required-owner/public-seam/architecture blockers first identified only after GREEN. Target `0`.
- `luna_discovery_token_share`: Luna tokens spent reconstructing already-available state divided by Luna orchestration tokens for the sampled cycle/window.
- `duplicate_ephemeral_spawn_on_unchanged_material_state`: equivalent expensive role spawns with unchanged canonical material state. Target `0`.
- `zero_silent_baton_violation`: material role-ending transitions that leave no executable owner/action, concrete blocker, or true terminal. Target `0`.
- `control_plane_deadlock`: actionable baton deadlock as defined above. Target `0`.

For `luna_discovery_token_share`, if trustworthy token accounting is not exposed, report literal `NOT_AVAILABLE`; never invent or estimate a value and present it as evidence.

The KPI chain therefore covers the full required sequence:

```text
writer unlock
-> STOP_WRITE
-> hosted CI terminal
-> reviewer start
-> reviewer terminal
-> paired PASS / merge-eligible
-> actual merge or HOLD_BY_POLICY
-> successor activation
```

## Binding resource policy

Token/resource optimization applies **ONLY** to:

- Luna discovery/reconstruction of already-available state;
- duplicate equivalent Luna routing work;
- equivalent ephemeral orchestration spawn de-duplication.

It SHALL NOT:

- reduce Master Audit depth, adversarial analysis, or lookahead;
- reduce `REVIEWER_INTEGRATION` depth;
- reduce `REVIEWER_SECURITY` depth;
- reduce persistent R3/R4/R5/R6 specialist reasoning;
- replace or skip fresh GitHub reads required by the role;
- suppress material-transition communication;
- suppress exact reviewer/writer terminal evidence;
- omit required evidence merely to save tokens;
- shorten required reasoning/evidence in Audit or specialist Code lanes.

Master Audit and persistent R3/R4/R5/R6 Web Code lanes are explicitly **NOT token-constrained** by #187. Integration/Security review depth is likewise never a target of Luna token optimization.

The optimization mechanism is de-duplication and delta-first reconstruction, not shallower engineering analysis.

## Failure behavior and rollback

- Missing/corrupt cache -> discard and full fresh GitHub reconstruction.
- GitHub/cache disagreement -> GitHub wins; rebuild both projections/fingerprints.
- Incomplete canonical evidence -> `ACTIONABILITY=BLOCKED` with exact missing evidence.
- Material change with same task fingerprint -> process material transition; do not suppress it.
- Clock-only observation change -> no material transition; no duplicate spawn.
- Missed event -> next normal watchdog scan reconstructs current truth.
- Changed main/head/synthetic/authority -> invalidate dependent classification and re-evaluate.
- Conflicting writer or pinned-main lock -> HOLD/BLOCKED even if other predicates pass.
- Reviewer handle unavailable -> use a fresh correct-role reviewer, never substitute wrong role.
- Metrics unavailable -> literal `NOT_AVAILABLE`; no synthetic estimate as evidence.

Planning rollback: close PR unmerged. Operational no-code rollback: discard advisory cache and return to full fresh-read watchdog behavior. Any future helper, if separately authorized, is reverted independently; GitHub authority remains unaffected.

## Adversarial acceptance matrix

The default no-code rollout and any future helper must prove:

| Case | Expected result |
|---|---|
| identical canonical material projection | `NO_MATERIAL_TRANSITION`; no new spawn |
| only `observed_at`/watchdog time changes | `NO_MATERIAL_TRANSITION` |
| CI/reuse pending -> terminal | `HOSTED_CI_TERMINAL_CHANGED` |
| reviewer pending/PASS/CHANGES_REQUIRED changes | `REVIEWER_TERMINAL_CHANGED` |
| writer ACTIVE -> STOP_WRITE or new terminal id | `WRITER_STOP_WRITE_OR_TERMINAL` |
| head changes | `PR_HEAD_CHANGED`; stale verdict invalidated |
| main/synthetic classification changes | `SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED` |
| merged false -> true + merge SHA | `ACTUAL_MERGE` |
| authority epoch changes | `AUTHORITY_EPOCH_CHANGED` |
| simultaneous CI + reviewer changes | stable ordered set preserves both |
| same task fingerprint but material state changes | material transition still processed |
| cache deleted/corrupt | full reconstruction, same canonical result |
| explicit policy HOLD after paired PASS | KPI class `HOLD_BY_POLICY`, not idle |
| token accounting unavailable | `luna_discovery_token_share=NOT_AVAILABLE` |
| attempted Luna optimization reduces Audit/reviewer/R3-R6 depth | FAIL governance acceptance |

## Default rollout and conditional future helper

Default recommendation: **NO NEW REPOSITORY RUNTIME**.

Luna applies:

- canonical material projection + `MATERIAL_STATE_FINGERPRINT` for event detection;
- task tuple + `TASK_FINGERPRINT` for duplicate role-work suppression;
- full binding KPI/resource contracts above during the no-code trial.

If measured evidence proves deterministic local handling insufficient, a future separate implementation issue may authorize exactly:

- `scripts/control_plane_state.py`
- `tests/test_control_plane_state.py`

Any helper must be pure/offline, receive already-fetched normalized data, emit advisory projection/diff/fingerprint results only, add no dependency, call no GitHub/network, spawn no agent, write no comment, merge nothing, and hold no authority.

## Acceptance

#187 planning is acceptable only when independent Integration and Security review confirm all of the following:

- material-state detection and task de-duplication are separate deterministic contracts;
- observation-only time cannot false-trigger a material event;
- CI/reuse/reviewer/writer/merge/authority changes cannot be missed because of same task fingerprint;
- simultaneous material changes have deterministic ordering;
- cache remains advisory and reconstructible;
- GitHub remains sole authority;
- reuse audit and three alternatives/trade-offs are present, with Alternative A selected;
- the full KPI chain and V3 quality/resource metrics are explicit;
- `HOLD_BY_POLICY` is distinguished from control-plane idle;
- `luna_discovery_token_share` uses literal `NOT_AVAILABLE` when trustworthy accounting is absent;
- resource optimization is scoped to Luna discovery/reconstruction and equivalent ephemeral spawn de-duplication only;
- **Master Audit remains non-token-limited and must retain full adversarial/lookahead depth**;
- **REVIEWER_INTEGRATION and REVIEWER_SECURITY remain non-token-limited in required review depth**;
- **persistent R3/R4/R5/R6 specialist lanes remain non-token-limited and retain required detailed fresh analysis**;
- required fresh GitHub reads, material-transition communication, and exact terminal evidence are never suppressed for token savings;
- no runtime/workflow/dependency/live/system scope is introduced;
- exact planning write-set remains the two authorized docs.

The implementation plan's Task 9 and self-review SHALL be interpreted against this full acceptance contract. Any checklist omission in the plan cannot narrow this binding design contract.