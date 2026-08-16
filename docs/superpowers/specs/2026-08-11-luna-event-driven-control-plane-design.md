# Luna Event-Driven Control Plane Design

## Status and authority

- Issue: #187
- Control contract: `CONTROL_CONTRACT_VERSION=1.3`
- Planning epoch: `ff93ddaa2ebb69e21f81baaa4f3dceec1db009ae`
- Authority: Issue #187 plus its V3 delta comment `5255200043`, with newer #131 control decisions taking precedence.
- Scope: planning/design only.
- Repository production implementation: NOT AUTHORIZED.
- AutoCAD/File-IPC/provider/private/customer/publication/system execution: NOT AUTHORIZED.
- Exact #187 planning write-set remains two documentation paths only:
  - `docs/superpowers/specs/2026-08-11-luna-event-driven-control-plane-design.md`
  - `docs/superpowers/plans/2026-08-11-luna-event-driven-control-plane.md`

This design must not move the currently pinned `main`, merge any HOLD PR, or change the current Gate-1G local baton.

## Problem

The project already has strong repository, CI, review, merge, authority, and live-execution gates. The remaining control-plane inefficiency is orchestration latency: an already-material transition can require a later scan to reconstruct state, rediscover the same evidence, respawn an equivalent agent, or notice that a baton became actionable.

The goal is not to weaken gates or replace GitHub. The goal is to make Luna react to material state changes with the minimum reconstruction work while preserving every existing authority boundary.

The target failure classes are:

1. duplicate expensive agent work on an unchanged state;
2. silent or idle actionable baton after a material transition;
3. repeated full discovery when only a bounded delta changed;
4. review and successor activation started later than necessary;
5. architecture/public-seam blockers first discovered after GREEN when they could have been found before RED;
6. control-plane state becoming an accidental second source of truth.

## Goals

The design SHALL:

- optimize Luna discovery/reconstruction tokens, not required transition communication;
- detect only bounded material state transitions;
- enforce a no-event/no-agent rule for expensive ephemeral work;
- deduplicate work with a deterministic task fingerprint;
- preserve/rejoin the same correct-role reviewer handle for bounded delta re-review when available;
- route `REVIEWER_INTEGRATION` and `REVIEWER_SECURITY` in parallel when both are required;
- make a material transition produce compact communication plus same-cycle action whenever authority already exists;
- detect `ZERO-SILENT-BATON` violations and `CONTROL_PLANE_DEADLOCK` conditions;
- support explicit conditional SOL preauthorization without inventing authority;
- target N+1 readiness as `PATCH_READY` or `ONLY_LATE_BINDINGS_PENDING` rather than planning-only readiness;
- require a `REQUIRED_PUBLIC_SEAMS` audit before downstream RED;
- derive cycle-time KPIs from existing GitHub/action/comment timestamps where possible;
- keep the periodic Luna scan as a safe watchdog/fallback;
- keep GitHub and accepted contracts as the only authority.

## Non-goals

This design SHALL NOT:

- create a second scheduler, merge authority, review authority, CI authority, store, database, queue, or truth source;
- introduce a long-running daemon or webhook service;
- add or modify a GitHub Actions workflow under #187;
- infer merge/live/repository-write authority from detector output;
- allow a cache hit, model memory, prior chat, stale SHA, stale synthetic, or stale reviewer verdict to override fresh GitHub state;
- shorten Master Audit or persistent R3/R4/R5/R6 reasoning for token savings;
- touch AutoCAD, File IPC, private/customer CAD, providers, publication, PC3/PMP, profiles, registry, drivers, printers, or system settings;
- alter the current R0-R8 functional architecture.

## Reuse audit

The selected design reuses the existing control surfaces rather than adding infrastructure.

### GitHub authority surfaces

GitHub already provides the authoritative inputs needed for transition detection:

- actual `main` ref and commit SHA;
- issue comments and control packets, especially #131;
- PR base/head and merge-ref/synthetic state;
- PR open/draft/merged state;
- hosted workflow terminal states for tests and reuse declaration;
- independent reviewer terminal verdicts;
- merge SHA and merge timestamp;
- issue/PR timestamps sufficient for most cycle-time metrics.

No separate canonical control database is required.

### Existing repository verification surfaces

The repository already contains reusable local/pre-push gates:

- `scripts/verify.ps1` for the canonical verifier;
- `scripts/check_architecture_boundaries.py` for architecture boundary checks;
- `scripts/check_reuse_declaration.py` and the hosted reuse declaration workflow;
- `scripts/reuse_inventory.py` for reuse ownership/completeness checks;
- focused pytest/.NET tests selected by the owning slice;
- `git diff --check`, exact changed-path checks, and Ruff/static checks already used by current lanes.

The design therefore requires composition of accepted checks, not a second verifier.

### Existing Luna/SOL operating model

The current operating model already has:

- a periodic Luna scan/watchdog;
- SOL as repository/governance/integration authority;
- Luna as bounded local executor/scheduler within delegated scope;
- GitHub comments as the durable handoff/control bus;
- strict exact-tuple review;
- `STOP_WRITE`, terminal handoff, and explicit next-owner/next-trigger semantics;
- paired `REVIEWER_INTEGRATION` and `REVIEWER_SECURITY` review where required.

The missing capability is a cheap deterministic way to decide whether a scan observed a new material state and what bounded action, if any, became executable.

## Alternatives

### Alternative A — GitHub-native observation plus existing Luna watchdog

Luna continues to read GitHub through the existing connector/watchdog. Each scan builds a normalized observation fingerprint and compares it with the last non-authoritative cached observation. An unchanged material fingerprint means `NO_ACTION`; a changed material fingerprint is classified and routed in the same cycle.

Advantages:

- no daemon, webhook, workflow, database, or new authority;
- cheapest safe change;
- failure naturally falls back to full fresh-read on the next watchdog scan;
- works with the current Human Owner > SOL > Luna model;
- preserves exact-main/authority-epoch invalidation.

Trade-off:

- reaction latency is bounded by the normal Luna scan rather than instant webhook delivery.

### Alternative B — GitHub Actions event dispatcher

A future workflow could react to pull-request, check-suite, review, or merge events and emit a compact transition packet.

Advantages:

- lower event-to-detection latency;
- GitHub-hosted rather than a separate machine daemon.

Trade-offs:

- requires workflow mutation and a new automation surface;
- can drift toward becoming a second scheduler;
- must solve event ordering, duplicate delivery, authority epoch, and missed-event fallback anyway;
- not authorized under #187's planning-only write-set.

This is a future fallback only if measured watchdog latency fails the required SLA.

### Alternative C — Dedicated webhook/daemon and persistent state store

Advantages:

- lowest theoretical latency and rich event processing.

Trade-offs:

- creates a new service and persistent store;
- increases secret, availability, deployment, and authority risks;
- duplicates capabilities already available from GitHub plus the Luna watchdog;
- contradicts reuse-first/YAGNI requirements.

This alternative is rejected.

## Selected architecture

Select Alternative A.

The system is **edge-triggered in semantics, watchdog-driven in transport**:

1. Luna performs its normal bounded fresh-read of canonical GitHub state.
2. The observation layer normalizes only fields capable of changing execution eligibility.
3. A deterministic material-state fingerprint is compared with the prior local/cache fingerprint.
4. If unchanged, the scan may update a local observation timestamp but SHALL NOT spawn an expensive ephemeral agent merely because time passed.
5. If changed, the transition classifier identifies the smallest material transition.
6. The authority resolver fresh-reads the relevant controlling packet and determines whether an action is already authorized.
7. If authorized, Luna communicates the transition compactly and performs/routes the action in the same cycle.
8. If not authorized, Luna persists one exact blocker/owner/next-trigger packet to the canonical GitHub bus when a durable handoff is required.
9. The next scan always remains capable of reconstructing everything from GitHub if the cache is missing or corrupt.

The detector is advisory. It decides **what changed**, never **what authority exists**.

## Material transition set

The default bounded transition classes are:

- `PR_HEAD_CHANGED`
- `SYNTHETIC_OR_MAIN_CLASSIFICATION_CHANGED`
- `HOSTED_CI_TERMINAL_CHANGED`
- `WRITER_STOP_WRITE_OR_TERMINAL`
- `REVIEWER_TERMINAL_CHANGED`
- `ACTUAL_MERGE`
- `AUTHORITY_EPOCH_CHANGED`

`AUTHORITY_EPOCH_CHANGED` is included because a newer #131/SOL/Owner control packet can invalidate an otherwise identical PR/main tuple. It is not an extra production event source; it is a direct GitHub control-bus change.

A scheduler tick, elapsed time alone, a repeated identical comment, an unchanged CI terminal, or an unchanged fingerprint is not a material transition.

## Observation snapshot

The Luna cache MAY hold a compact observation object such as:

```json
{
  "schema_version": "luna-control-observation-1.0",
  "observed_at": "2026-08-16T07:41:00Z",
  "current_main": "<sha>",
  "authority_epoch": {
    "issue": 131,
    "comment_id": 5306365374
  },
  "active_task": {
    "issue": 187,
    "owner_role": "SOL",
    "next_owner_role": "Luna",
    "next_trigger": "<normalized-trigger>"
  },
  "pull_request": {
    "number": 261,
    "head": "<sha>",
    "synthetic_or_state": "<sha-or-state>",
    "draft": true,
    "merged": false
  },
  "ci": {
    "tests": "SUCCESS",
    "reuse": "SUCCESS"
  },
  "reviews": {
    "REVIEWER_INTEGRATION": "PASS",
    "REVIEWER_SECURITY": "PASS"
  },
  "blocker": null,
  "material_fingerprint": "<deterministic-hash>"
}
```

Rules:

- this object is a cache/index only;
- it SHALL NOT contain secrets, private CAD data, raw evidence payloads, or authority not present on GitHub;
- a missing/corrupt snapshot causes a full fresh-read, not failure-open;
- any action still requires fresh authority validation against GitHub;
- mutable state in this snapshot SHALL NOT be cited as proof when GitHub can be cited directly.

No repository file or project database is required for this snapshot. A process/session-local or existing Luna workspace cache is sufficient.

## Task fingerprint and de-duplication

The required task fingerprint is:

```text
(role,
 task_or_issue,
 current_main,
 pr_head,
 synthetic_or_state,
 authority_epoch,
 intended_output)
```

Normalization rules:

- `role` uses canonical role labels such as `SOL`, `Luna`, `REVIEWER_INTEGRATION`, `REVIEWER_SECURITY`;
- `task_or_issue` is a stable issue/PR identifier, never free-form chat text;
- `current_main` is the fresh actual main SHA;
- `pr_head` is the exact current head or literal `NONE` when no PR exists;
- `synthetic_or_state` is the exact current synthetic/merge ref when meaningful, otherwise a closed normalized state token;
- `authority_epoch` is the newest controlling GitHub comment/decision identifier plus any explicitly bound expected tuple;
- `intended_output` is a closed output class such as `WRITE_RED`, `WRITE_GREEN`, `REVIEW`, `MERGE_DECISION`, `LOCAL_PREFLIGHT`, or `STATUS_ONLY`.

The fingerprint is serialized with canonical key ordering and hashed with SHA-256 for compact comparison.

Decision rule:

```text
same fingerprint + correct-role handle still valid
    => rejoin/reuse handle or NO_ACTION
same fingerprint + terminal already posted
    => NO_ACTION
changed fingerprint
    => classify delta and create/rejoin only the minimum required role
```

A duplicate fingerprint never grants permission to reuse stale evidence. It only prevents duplicate orchestration work; the receiving role still performs the fresh reads required by its contract.

## Material transition handling

For every material transition, Luna SHALL produce a compact internal classification:

```text
TRANSITION=<class>
OLD_FINGERPRINT=<hash-or-NONE>
NEW_FINGERPRINT=<hash>
AUTHORITY_EPOCH=<issue/comment>
ACTIONABILITY=AUTHORIZED | BLOCKED | OBSERVE_ONLY
PRIMARY_NEXT_OWNER=<role>
NEXT_TRIGGER=<exact trigger>
```

If `ACTIONABILITY=AUTHORIZED`, the bounded action is started/routed in the same cycle. A second normal scan is not required merely to notice the already-authorized action.

If `ACTIONABILITY=BLOCKED`, one exact missing authority/evidence prerequisite and next trigger are persisted. Repeated generic `WAIT` states are not allowed when a concrete blocker can be named.

## ZERO-SILENT-BATON and deadlock detection

A baton is considered explicit only when all four fields are known:

```text
BATON_STATE = (current_owner, executable_action_or_blocker, next_trigger, authority_epoch)
```

`ZERO-SILENT-BATON` requires that every material transition ending a role's work leaves one of:

- an executable next owner/action;
- a concrete blocker owner plus missing prerequisite;
- a terminal state requiring no further action.

A `CONTROL_PLANE_DEADLOCK` exists when all of the following are true:

1. the current baton identifies an executable action;
2. required authority/evidence is already present and fresh;
3. no conflicting writer/epoch lock forbids the action;
4. the action was neither started/routed in the transition cycle nor represented by a valid in-flight handle;
5. a later watchdog scan sees the same actionable baton unchanged.

On detection Luna SHALL report the deadlock and perform the already-authorized action in that scan. The target count is zero actionable control-plane deadlocks.

A true external wait, pinned-main hold, local-machine prerequisite, reviewer in-flight state, CI in-flight state, or explicit Human gate is not a deadlock.

## Reviewer routing and handle reuse

Canonical reviewer roles are:

- `REVIEWER_INTEGRATION`
- `REVIEWER_SECURITY`

When paired review is required they are routed in parallel. For a bounded repair on the same task, Luna SHOULD rejoin the existing correct-role reviewer handles when available rather than spawn equivalent new reviewer contexts.

A prior verdict is never reused as a verdict for a changed tuple. Handle reuse means the same reviewer context performs a fresh exact-head review.

## Conditional SOL preauthorization

Conditional preauthorization is permitted only when an explicit SOL/Owner GitHub control packet states:

- exact current main/base;
- expected RED or GREEN head conditions;
- exact allowed write-set/action;
- required CI/reviewer predicates;
- exact merge or next-step target where applicable;
- material invalidators;
- the action that may occur automatically after predicates become true.

Examples of allowable conditions include:

- RED PASS -> bounded GREEN write on an exact allowlist;
- paired final PASS on the expected unchanged head/synthetic -> merge eligibility decision;
- actual merge -> capture merge SHA, re-epoch affected successors, and activate the next eligible bounded gate.

The detector SHALL NOT synthesize this preauthorization. If the packet is absent or any expected SHA/state moved, actionability becomes `BLOCKED` and SOL must decide.

Pinned-main/local-live constraints override generic preauthorization. For example, a repo-accepted PR remains HOLD when the controlling Gate-1G epoch forbids main movement.

## N+1 readiness

When phase N is executing, off-critical-path preparation for phase N+1 should aim for one of:

- `PATCH_READY`: exact bounded patch/tests can start immediately once the late binding becomes available;
- `ONLY_LATE_BINDINGS_PENDING`: all architecture, owner, public-seam, test-matrix, and write-set questions are closed, with only exact upstream symbols/SHA/evidence missing.

`PLANNING_ONLY_READY` is not the target for a dependency that can safely be prepared further without speculative production binding.

This does not authorize overlapping writers. One active production writer remains required for overlapping write-sets.

## REQUIRED_PUBLIC_SEAMS audit

Before a downstream RED begins, its owner SHALL record the exact accepted public seams it expects to consume.

Minimum record:

```text
REQUIRED_PUBLIC_SEAMS:
- owner/subsystem
- public symbol or contract
- accepted source/merge identity
- downstream use
- missing/ambiguous: YES|NO
```

If a required seam is private-only, speculative, duplicated, or missing, the downstream RED is blocked and the architecture owner must resolve it first.

This audit is intended to drive post-GREEN architecture blocker leakage to zero.

## Pre-push GREEN owner-contract bundle

Before the first GREEN push for a production slice, the writer should run a focused owner-contract bundle composed only from existing tools:

1. exact focused RED/GREEN tests for the slice;
2. focused tests for every `REQUIRED_PUBLIC_SEAMS` owner consumed by the slice;
3. Ruff/static checks for changed Python paths where applicable;
4. `scripts/check_architecture_boundaries.py`;
5. reuse declaration/checker where applicable;
6. `git diff --check`;
7. exact changed-path/allowlist audit;
8. the canonical verifier or the largest safe supported subset required by the slice.

This bundle is a local pre-push quality gate only. It never replaces hosted final CI/reuse, independent review, exact-head validation, or live gates.

No new workflow is required by this design.

## KPI derivation

Metrics should be derived from existing GitHub/action/comment timestamps whenever possible. A separate metrics database is forbidden.

### Core latency metrics

- `writer_unlock_to_stop_write` = writer `STOP_WRITE` timestamp - production unlock timestamp.
- `stop_write_to_ci_terminal` = final required hosted CI terminal timestamp - `STOP_WRITE` timestamp.
- `stop_write_to_review_start` = first required reviewer-start/routing timestamp - `STOP_WRITE` timestamp.
- `ci_terminal_to_reviewer_terminal` = paired/final required review terminal timestamp - final required CI terminal timestamp.
- `paired_pass_to_merge` = actual merge timestamp - timestamp when the final required PASS made the exact tuple merge-eligible.
- `merge_to_successor_activation` = successor issuance/unlock timestamp - actual merge timestamp.

When merge is intentionally HOLD because of an explicit epoch lock, `paired_pass_to_merge` is classified `HOLD_BY_POLICY` rather than treated as control-plane idle time.

### Quality/efficiency metrics

- `actionable_baton_idle_cycles`: count of watchdog cycles where an unchanged executable baton existed without a valid in-flight action. Target: `0`.
- `review_repair_cycles`: number of CHANGES_REQUIRED -> repair -> fresh-review loops for a final production tuple.
- `architecture_blockers_first_discovered_after_green`: count of required-owner/public-seam/architecture blockers first identified only after GREEN. Target: `0`.
- `luna_discovery_token_share`: Luna tokens spent reconstructing already-available state divided by Luna tokens spent on orchestration for the sampled cycle/window. This metric applies to Luna only. If the runtime cannot expose trustworthy token accounting, report `NOT_AVAILABLE`; do not invent a value.

Master Audit and persistent R3/R4/R5/R6 Web Code lanes are explicitly excluded from token-reduction targets.

## Resource policy

Token/resource optimization is scoped to Luna discovery and equivalent ephemeral orchestration spawns.

It SHALL NOT:

- reduce Master Audit depth;
- reduce adversarial/security/integration review depth;
- reduce R3/R4/R5/R6 specialist reasoning;
- replace fresh GitHub reads required by a role;
- suppress material transition communication;
- omit exact evidence needed for a terminal or decision.

The optimization is de-duplication and delta-first reconstruction, not shallower engineering analysis.

## Failure and rollback

The design is fail-closed and cache-discardable.

- Missing cache -> full fresh GitHub read.
- Corrupt/unparseable cache -> discard cache and full fresh read.
- GitHub read disagreement with cache -> GitHub wins and cache is replaced.
- Missed event -> next normal watchdog scan reconstructs current truth.
- Duplicate/out-of-order observation -> fingerprint/authority epoch prevents stale promotion.
- Changed main/head/synthetic/authority epoch -> invalidate dependent cached classification and re-evaluate.
- Conflicting active writer or pinned-main lock -> action becomes HOLD/BLOCKED even if other predicates pass.
- Reviewer handle unavailable -> spawn a fresh correct-role reviewer; never substitute a wrong role.
- Metrics unavailable -> literal `NOT_AVAILABLE`; no synthetic estimate presented as evidence.

Rollback of any future implementation is simply removal/disablement of the advisory detector/cache path; the periodic full fresh-read watchdog remains the safe baseline.

## Security and authority boundaries

Detector and cache outputs have no independent authority to:

- write repository production code;
- merge a PR;
- mark a review PASS;
- authorize AutoCAD/File-IPC/live execution;
- mutate private/customer/source/accepted CAD;
- authorize repair, approval, publication, or production acceptance;
- change system/profile/printer/registry state.

All such actions continue to require the existing controlling GitHub packet and subsystem contract.

Secrets, credentials, private evidence, private paths, raw CAD contents, and provider payloads must never be placed in the observation snapshot.

## RED-first future implementation strategy

No production implementation is authorized under #187. If a later explicit implementation issue determines repository code is genuinely needed, the cheapest bounded fallback should be a pure control-plane helper with no workflow or runtime authority, for example:

- `scripts/control_plane_state.py`
- `tests/test_control_plane_state.py`

A future RED should prove at minimum:

- unchanged fingerprint -> `NO_ACTION`;
- PR head/main/synthetic/authority movement -> material transition;
- stale reviewer PASS cannot survive a changed tuple;
- duplicate reviewer/writer fingerprint is deduplicated;
- explicit authority epoch movement invalidates an otherwise unchanged tuple;
- actionable baton without in-flight action is classified as deadlock;
- explicit HOLD/pinned-main state is not classified as deadlock;
- missing/corrupt cache falls back to fresh reconstruction;
- `REQUIRED_PUBLIC_SEAMS` missing/ambiguous blocks downstream RED;
- KPI derivation is deterministic and does not count policy HOLD as idle;
- no secret/private/live/system fields are accepted into the snapshot.

However, the preferred first implementation remains **no repository production code**: encode these rules in the Luna/SOL orchestration instructions and use existing GitHub connector reads. Repository code should be created only if measured evidence shows the orchestration layer cannot implement the deterministic normalization safely without it.

Any future implementation issue must define its own exact base, writer, write-set, RED evidence, reviewers, and merge/live authority. #187 itself grants none of these.

## Acceptance criteria for this design

The design is acceptable when reviewers can verify all of the following:

- GitHub remains the sole source of truth and authority;
- the selected architecture is GitHub-native observation plus existing Luna watchdog;
- no event/no agent is explicit;
- task fingerprints and invalidators are deterministic;
- material transitions are bounded and authority is rechecked separately;
- same-cycle action occurs only when already authorized;
- `ZERO-SILENT-BATON` and `CONTROL_PLANE_DEADLOCK` have exact definitions;
- paired reviewer routing and handle reuse do not reuse stale verdicts;
- explicit SOL conditional preauthorization is supported but never inferred;
- N+1 targets `PATCH_READY` / `ONLY_LATE_BINDINGS_PENDING`;
- `REQUIRED_PUBLIC_SEAMS` precedes downstream RED;
- existing verifier/reuse/architecture tools compose the pre-push GREEN bundle;
- KPI formulas and exclusions are explicit;
- actionable deadlock target is zero;
- post-GREEN architecture blocker leakage target is zero;
- Luna-only token optimization does not reduce Audit/R3-R6 detail;
- cache failure falls back to the periodic watchdog;
- no third planning path, workflow, dependency, persistent authority store, AutoCAD/live/system action, or production implementation is introduced.
