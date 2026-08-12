# SOL-First Operating Model 10/10

Date: 2026-08-12
Repository: `duongchi90/cad-agent`
Control contract baseline: `CONTROL_CONTRACT_VERSION: 1.3`

## 1. Objective

Minimize wall-clock latency and coordination overhead without weakening authority integrity, TDD discipline, independent audit, security review, or Human/live-system gates.

The default model is:

`SOL PRE-CODE -> SOL RED -> SOL GREEN -> HOSTED CI/REUSE -> REVIEWER_INTEGRATION + REVIEWER_SECURITY -> AUTO-MERGE -> FRESH MAIN -> SUCCESSOR ACTIVE`

SOL is the primary offline executor and governance owner. Luna is no longer the default writer; Luna is reserved for machine-local execution, AutoCAD/File-IPC/live-environment work, or executor failover.

## 2. Design Principles

1. One primary writer per task/branch.
2. SOL self-audit is mandatory but never substitutes for independent review.
3. Hosted CI/reuse and two independent reviewers are separate merge gates.
4. No silent baton: executable authority with no action in flight is a control-plane defect.
5. No duplicate discovery: SOL performs architecture/pre-code discovery once; reviewers perform delta-focused audit; Luna receives bounded execution packets.
6. Architecture/public-seam failures should be found before GREEN.
7. Exact lineage, exact write-set, and exact reviewed head remain mandatory.
8. Human interruption is minimized; Human gates remain for genuinely local, sensitive, irreversible, or production actions.
9. User visibility is signal-only.
10. Normal offline tasks auto-merge once every merge condition is satisfied.

## 3. Roles and Authorities

### 3.1 SOL

SOL owns:

- project architecture and code archaeology;
- public-seam and authority-boundary analysis;
- threat model and security invariants;
- exact base/write-set/TDD oracle freezing;
- primary RED/GREEN implementation for offline GitHub work;
- pre-review self-audit;
- CI/reuse routing and evidence collection;
- blocker classification and bounded remediation;
- merge disposition;
- auto-merge when the full exact-head gate is satisfied;
- fresh-main verification after merge;
- freshness-impact classification;
- immediate successor activation;
- preparation of N+1/N+2 work while N waits on external gates.

SOL self-review is advisory evidence only. It never counts as `REVIEWER_INTEGRATION` or `REVIEWER_SECURITY` PASS.

### 3.2 REVIEWER_INTEGRATION

Read-only independent reviewer responsible for:

- exact base/head/merge-base lineage;
- exact cumulative write-set;
- architecture/reuse constraints;
- dependency/workflow/schema drift;
- affected regressions;
- owner reuse and absence of duplicate owners;
- hosted evidence consistency;
- unresolved review/thread state.

Default method: delta-review against the frozen contract/oracle. Full rediscovery is justified only when a new authority or architecture gap is found.

### 3.3 REVIEWER_SECURITY

Read-only independent reviewer responsible for:

- authority/provenance integrity;
- fail-closed behavior;
- hostile types and malformed structures;
- replay and concurrency;
- integrity/tamper handling;
- privacy-safe failures;
- capability/domain separation;
- no authority minting or leakage;
- mutation/cleanup ambiguity and stale-evidence semantics where relevant.

Default method: adversarial delta-review against the frozen security oracle.

### 3.4 Luna / Codex Desktop

Luna is a bounded execution engine, not the default architecture/discovery owner.

Luna is used only when at least one is true:

1. Windows/local filesystem/process state is required and unavailable to SOL;
2. AutoCAD/File-IPC/live provider/private CAD environment is required;
3. SOL lacks the necessary execution transport for a specific action;
4. SOL execution becomes unavailable and Luna is the safest failover executor.

Every Luna handoff must contain exact SHA/ref, exact action/command scope, expected evidence, allowed write-set, and STOP condition. Luna must not broaden discovery or authority.

### 3.5 Human Owner

Human action is required only for genuine Human/local gates, including as applicable:

- live AutoCAD/system actions requiring the user's machine or interactive environment;
- private/customer CAD;
- credentials/secrets;
- production publication;
- irreversible external actions;
- machine/system mutation not already explicitly authorized.

Routine GitHub/offline execution, review routing, and merge do not require Human relay.

## 4. Canonical Task State Machine

Each implementation task follows:

`RESEARCHED -> CONTRACT_READY -> RED_READY -> RED_ACCEPTED -> GREEN_ACTIVE -> STOP_WRITE -> FINAL_REVIEW -> MERGE_READY -> MERGED -> SUCCESSOR_ACTIVE`

### 4.1 RESEARCHED

Architecture, existing owners, public seams, constraints, and reuse targets have been inspected.

### 4.2 CONTRACT_READY

The task freezes:

- exact current base;
- exact write-set ceiling;
- required public seams;
- authority owner(s);
- hard gates;
- security oracle;
- merge-impact/freshness expectations.

### 4.3 RED_READY

Tests and causal failure oracle are specified. Production edits remain forbidden until meaningful RED is proven and accepted.

### 4.4 RED_ACCEPTED

Causal RED is demonstrated, scope is valid, and required RED review gates have passed where the task contract requires them.

### 4.5 GREEN_ACTIVE

Minimal production repair/implementation is authorized inside the frozen write-set and authority model.

### 4.6 STOP_WRITE

The exact candidate head is frozen pending hosted evidence and independent final review.

### 4.7 FINAL_REVIEW

`REVIEWER_INTEGRATION` and `REVIEWER_SECURITY` run independently and preferably in parallel on the same exact head.

### 4.8 MERGE_READY

Every auto-merge gate in Section 6 is simultaneously true.

### 4.9 MERGED

The PR is merged without destructive history rewriting.

### 4.10 SUCCESSOR_ACTIVE

SOL fresh-fetches `main`, proves the merge landed, classifies freshness impact, and activates the next executable task in the same control cycle.

There must be no normal state in which a completed merge leaves the baton unowned.

## 5. TDD Contract

For implementation and bug-fix work:

1. no production code before a failing test for the intended behavior;
2. RED must fail for the intended missing/incorrect behavior, not setup/environment/live-fixture noise;
3. GREEN must be minimal and stay inside the frozen write-set;
4. refactoring is allowed only after GREEN and only when it preserves scope and behavior;
5. reviewer-discovered defects receive a focused regression before the production repair where feasible;
6. tests must exercise real contract behavior rather than merely mock invocation counts unless mocking is unavoidable for a frozen boundary.

## 6. Auto-Merge Contract

SOL may auto-merge only when all of the following are true at the same time:

- current `main` is consistent with the expected base lineage;
- PR base/head are exactly the expected refs and SHAs;
- cumulative changed paths equal the authorized write-set;
- no unauthorized dependency/workflow/schema/fixture/authority drift exists;
- hosted tests PASS;
- reuse/architecture checks PASS;
- `REVIEWER_INTEGRATION` PASS is bound to the exact head;
- `REVIEWER_SECURITY` PASS is bound to the exact head;
- no unresolved blocking review/thread exists;
- no head drift occurred after the reviewer verdicts;
- no material invalidator from the controlling SOL decision is present.

If any condition is false or unknown, merge is forbidden.

After merge, SOL must:

1. fresh-fetch `main`;
2. prove the expected merge is an ancestor/current integration state;
3. classify whether downstream evidence became stale;
4. update/consume the control terminal as needed;
5. activate the next executable successor immediately.

No amend, rebase, squash, or force-push is permitted when the project contract requires forward-only history.

## 7. Independent Audit Model

Every merge candidate has four distinct quality layers:

`SOL SELF-AUDIT -> HOSTED CI/REUSE -> REVIEWER_INTEGRATION -> REVIEWER_SECURITY`

These layers are additive; none substitutes for another.

### 7.1 SOL Self-Audit

Before independent review, SOL checks at minimum:

- exact diff/write-set;
- public API/owner reuse;
- error privacy;
- hostile/malformed inputs where relevant;
- replay/concurrency where relevant;
- stale/evidence semantics;
- authority leakage/minting;
- deterministic identity/hash requirements;
- local/focused test evidence;
- likely reviewer oracles.

This exists to reduce reviewer iterations, not to self-certify.

### 7.2 Reviewer Independence

The writer cannot convert its own self-review into either independent PASS. Reviewer verdicts must be separate, exact-head-bound evidence.

## 8. Reviewer-Requested Remediation

### 8.1 In-Scope Finding

If `CHANGES_REQUIRED` is fully inside the frozen authority and write-set:

`reviewer finding -> SOL focused RED/regression -> SOL minimal patch -> hosted gates -> same-role delta review`

No Luna relay is required.

### 8.2 Architecture/Authority Finding

If the finding requires any of the following:

- third path outside authorized scope;
- new public seam;
- new authority owner/store;
- workflow/dependency/schema change;
- materially different security model;

then classify:

`BLOCKED — SOL_REASONING_REQUIRED`

The task returns to pre-code design before any broader production write.

## 9. Zero-Latency / Work-Stealing Rules

### 9.1 Zero-Silent-Baton

A control-plane defect exists when:

- executable authority exists; and
- no writer, reviewer, CI job, Human action, or external dependency is actually in flight.

SOL must immediately resume, route, or escalate rather than merely record a waiting state.

### 9.2 Pipeline Concurrency

The preferred pipeline allows:

- N: CI/final review;
- N+1: `PATCH_READY` or equivalent;
- N+2: `CONTRACT_READY`;
- N+3: `RESEARCHED`.

Only one primary writer may modify the same task/branch at a time.

When N waits on a real external gate, SOL prepares N+1/N+2 instead of idle polling.

### 9.3 Immediate Transitions

- hosted terminal -> reviewer route immediately;
- paired exact-head PASS -> merge disposition immediately;
- valid merge gate -> auto-merge immediately;
- merge -> fresh-main + successor activation immediately;
- `CHANGES_REQUIRED` -> bounded SOL remediation immediately when scope permits.

## 10. Failover Contract

### 10.1 Luna Failover

If Luna becomes unavailable or token-constrained during an offline task, SOL resumes from the exact last-good GitHub state/evidence whenever SOL has the required transport.

### 10.2 SOL Transport Boundary

If SOL cannot perform a required machine-local action, SOL must not infer or fabricate local state. It stops at the exact local boundary and issues a bounded Luna/Human execution packet.

### 10.3 No Dual-Writer Race

SOL and Luna must never independently write the same task/branch concurrently. A failover requires an explicit baton transfer bound to the exact last-good head/state.

## 11. AutoCAD / Live Gate

Offline work should advance as far as safely possible before invoking local execution.

When a local gate is reached, the packet must include:

- exact repository/main/task state;
- exact local objective;
- allowed machine surface;
- forbidden surfaces;
- prerequisite process/profile/file hashes where relevant;
- exact evidence to collect;
- rollback/STOP condition;
- whether live flags remain locked or may be set.

R6/R7/R8 semantics and other phase-specific freshness rules remain governed by their existing project contracts; this operating model does not weaken them.

## 12. User Visibility — Signal-Only

The Human Owner is not a routine message bus.

User-visible progress signals are limited to material transitions:

- `✅ MERGED` — task/PR merged, current main, successor;
- `🚧 BLOCKED / CHANGES_REQUIRED` — a material blocker requiring redesign or special attention;
- `🔁 FRONTIER MOVED` — roadmap/frontier materially changed;
- `🖥️ LOCAL/AUTOCAD GATE READY` — local execution is genuinely required;
- `👤 HUMAN ACTION REQUIRED` — only when SOL/Luna cannot safely proceed without the Human Owner.

Normal RED/GREEN/CI start/reviewer-routing events remain internal unless they become material blockers.

## 13. KPI / Self-Audit Targets

The operating model is considered 10/10 only when it continuously targets:

1. **Idle baton = 0** — executable work always has real action in flight.
2. **Duplicate discovery ≈ 0** — SOL discovers once; reviewers audit delta; Luna executes bounded packets.
3. **Post-GREEN architecture surprise ≈ 0** — required public seams and ownership blockers are found before GREEN.
4. **Writer-to-review latency minimized** — reviewer route begins immediately after exact hosted candidate evidence.
5. **Review-to-merge latency minimized** — paired PASS plus all gates causes immediate auto-merge.
6. **Scope integrity = 100%** — any third path/head drift/new authority requirement fails closed.
7. **Independent audit = 100%** — no writer self-certification replaces independent reviewer evidence.
8. **Human interruption minimized** — Human is involved only for true Human/local gates.
9. **Forward-history discipline = 100%** — no destructive history shortcuts.
10. **Freshness correctness = 100%** — every merge/current-main transition re-evaluates stale downstream evidence.

A reviewer finding an architecture/authority seam that SOL reasonably should have identified during pre-code is classified as a SOL pre-code quality defect and feeds back into future pre-code checklists.

## 14. Safety Invariants Preserved

This operating model changes execution ownership and latency, not substantive security semantics.

It does not weaken:

- exact-head review;
- paired independent review;
- STOP_WRITE discipline;
- causal RED-first TDD;
- fresh-main verification;
- privacy-safe failures;
- owner reuse/domain separation;
- stale-evidence/freshness rules;
- Human/live/private/system gates;
- R5 -> R6 -> fresh custody/R3/R4 -> NEW R5 -> R7 -> R8 ordering where applicable.

## 15. Default Operating Policy

Effective default:

- `PRIMARY_OFFLINE_EXECUTOR = SOL`
- `PRIMARY_GOVERNANCE_OWNER = SOL`
- `INDEPENDENT_REVIEW = REVIEWER_INTEGRATION + REVIEWER_SECURITY`
- `LUNA_ROLE = LOCAL_MACHINE_EXECUTOR | AUTOCAD_EXECUTOR | FAILOVER_EXECUTOR`
- `USER_VISIBILITY = SIGNAL_ONLY`
- `MERGE_POLICY = AUTO_MERGE_ON_FULL_EXACT_HEAD_GATE`
- `AUTO_RESUME = YES`
- `ZERO_SILENT_BATON = ENFORCED`

The project should optimize speed by removing idle time, duplicate discovery, and unnecessary handoffs — never by weakening independent audit or authority constraints.
