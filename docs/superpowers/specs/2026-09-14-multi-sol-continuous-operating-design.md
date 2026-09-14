# Multi-SOL Continuous Operating V1

## Status

Design approved by Human Owner on 2026-09-14.

This contract overlays the useful coordination semantics from #305 and the independent-review correction from #392 onto the current Luna ↔ SOL_PO22 closed loop used for the active Phase-4 acceptance work in #409.

It does not create a new product subsystem, runtime dependency, bridge, daemon, queue, registry, approval authority, identity-authority service, or transport.

## Goal

Keep product execution continuous while preserving strong independent SOL review quality.

The operating model is:

```text
OBJECTIVE EVIDENCE
GitHub + CI + AutoCAD/FileIPC/runtime artifacts
        ↑
HOT EXECUTION LOOP
Luna ↔ SOL_PO22
        ↑
PARALLEL INDEPENDENT WATCHDOGS
Control / Architecture / Security / Integration / Evidence
        ↑
PRODUCT AUTHORITY
ChatGPT_PO
        ↑
Human only for genuine Human Gate
```

## Canonical principles

```text
CONTINUOUS_LUNA_SOL_LOOP=YES
NO_HUMAN_RELAY=YES
LUNA_MAX_SOLO=YES
PRODUCT_FIRST=YES
REUSE_FIRST=YES
EXISTING_OWNER_FIRST=YES
GITHUB_CANONICAL=YES
NO_NEW_CONTROL_PLANE=YES
NO_ALL_SOL_QUORUM_FOR_EXECUTION=YES
NO_WAIT_FOR_OPTIONAL_REVIEW=YES
UNIQUE_DECISION_SIGNAL_OVER_COMMENT_COUNT=YES
```

## Roles

### LUNA_CODEX

Primary local executor. Owns Windows, private/local-only data, AutoCAD Mechanical, FileIPC/live runtime, candidate mutation, production code/test changes, Git branch/commit/PR execution, save/reopen, and final live acceptance.

### SOL_PO22

Hot-loop cloud forensic worker + causal reviewer. Owns cloud/read-only source/diff/evidence reasoning, residual triage, causal falsification, owner/reuse discrimination, decision-grade RED/GREEN review, and the exact next-owner/next-action decision.

SOL_PO22 is not a sixth approval vote. It is attached to the active causal thread.

### CONTROL_GOVERNANCE

Independent watchdog for currentness, first-unsatisfied-boundary correctness, ownership/authority, race/process drift, scope creep, invented Human Gates, and complexity-brake enforcement.

### ARCHITECTURE_REUSE

Independent watchdog for existing-owner/API reuse, write-set minimization, adapter/subsystem pressure, architecture expansion, and N+1 cheapest causal oracle.

### SECURITY_REDTEAM

Independent adversarial watchdog for fail-open paths, false PASS, trust/currentness, live FileIPC/AutoCAD/COM/ROT risks, cleanup/rollback gaps, and unsafe promotion semantics.

### INTEGRATION_CI

Independent watchdog for exact BASE/HEAD/diff, CI/check state, evidence-to-commit binding, integration contradictions, stale proof, and merge currentness.

### EVIDENCE_ACCEPTANCE

Independent watchdog for product acceptance semantics and proof quality: provenance, geometry/visual, dimension/text where applicable, editability/readback, save/reopen, deterministic verification, and false-green prevention.

### CHATGPT_PO

Product/architecture/governance authority for material product-boundary or architectural ambiguity. Not in the normal micro-step path.

### Human

Only for genuine Human Gates: credentials/private authority/billing, source/customer/accepted-drawing mutation permission, destructive/irreversible action, unknown executable/trust expansion, materially high cost, or genuine product ambiguity.

## Hot loop

The only continuous execution loop is:

```text
Luna local/runtime action
→ publish bounded decision-grade evidence
→ SOL_PO22_REQUEST
→ SOL_PO22 performs all safe cloud/read-only work for that causal question
→ SOL_PO22_VERDICT
→ exactly one NEXT_OWNER + NEXT_SINGLE_BOUNDED_ACTION
→ Luna or SOL_PO22 continues
```

No mandatory five-SOL quorum exists for ordinary execution.

SOL_PO22 continues internally through cheap read-only sub-oracles until one of:

```text
CAUSAL_RED_READY
MATERIAL_FINDING
HYPOTHESIS_FALSIFIED
OWNER_RESOLVED
LOCAL_ACTION_REQUIRED
ACCEPTANCE_BOUNDARY_CHANGED
BLOCKED
```

One measurement is not a review event.

## Parallel watchdog model

The five specialist SOLs run independently in parallel with the hot loop.

Primary trigger model: event-driven review of current GitHub state.

Secondary safety model: staggered periodic sweeps, once per hour each, offset across the hour.

Recommended stagger:

```text
:00 CONTROL_GOVERNANCE
:12 ARCHITECTURE_REUSE
:24 SECURITY_REDTEAM
:36 INTEGRATION_CI
:48 EVIDENCE_ACCEPTANCE
```

The stagger is a safety sweep, not Luna's clock. Luna never waits for the next scheduled watchdog run.

Every watchdog must fresh-read mutable GitHub state before a verdict.

## Independent-review protocol

Each watchdog must form an `INITIAL_VERDICT` from fresh source/evidence before consuming same-round conclusions from other SOL roles.

Only after the initial verdict may results converge.

Converged public output classifies the role's contribution as one of:

```text
UNIQUE_FINDING
CONFIRMATION
NO_MATERIAL_DELTA
```

`NO_MATERIAL_DELTA` produces no GitHub comment and no user notification.

Five labels or comments do not prove five independent reviews.

## Interruption rule

A watchdog may interrupt the hot loop only for:

```text
1. CURRENT_MATERIAL_FINDING
2. MANDATORY_PRE_MERGE_OR_HIGH_RISK_GATE
3. MATERIAL_PRODUCT_OR_ARCHITECTURE_ESCALATION
```

The following never block Luna:

```text
watchdog has not run yet
watchdog has no comment
finding=NONE
next scheduled sweep has not arrived
one measurement just completed
one JSON packet was produced
optional specialist has not confirmed
```

## Mandatory vs conditional specialists

During normal development, all five specialists are advisory/lookahead and do not form a quorum.

For a material runtime/safety/currentness/live-promotion/persistence/acceptance PR preparing to merge:

```text
SECURITY_REDTEAM=MANDATORY_INDEPENDENT_CLEAR
INTEGRATION_CI=MANDATORY_INDEPENDENT_CLEAR
```

`CONTROL_GOVERNANCE`, `ARCHITECTURE_REUSE`, and `EVIDENCE_ACCEPTANCE` become merge-relevant only when they have a current material finding affecting the change or acceptance claim.

Routine docs/typo/non-behavior changes do not require five-role ceremony.

## Merge gate

A material runtime PR may merge only when all are current for the exact frozen HEAD:

```text
exact BASE/HEAD known
required CI terminal PASS
causal/focused changed-boundary evidence PASS
SECURITY_REDTEAM has no unresolved material finding
INTEGRATION_CI has no unresolved material finding
any current Control/Architecture/Evidence material finding dispositioned
SKIP/NOT_RUN/submission/stale/mock-only/cleanup-only evidence not promoted to PASS
```

Execution gate and merge gate are intentionally different.

## Lookahead behavior

The five watchdogs should remove Web-capable uncertainty ahead of Luna rather than repeatedly review the same active micro-step.

Target lookahead depth:

```text
approximately 1 to 1.5 product boundaries ahead
```

Examples:

- Control: verify boundary N is still the real first unsatisfied boundary.
- Architecture: prepare existing-owner/reuse map and cheapest oracle for N or N+1.
- Security: prepare adversarial tests for the likely bounded production change.
- Integration: prepare exact regression/CI/merge-currentness checks.
- Evidence: prepare the proof contract required to declare N PASS.

Do not build speculative N+2/N+3 subsystems.

## Product-first and complexity brakes

Every investigative thread must answer:

```text
REQUIRED_FOR_CURRENT_PRODUCT_GATE=YES
CURRENT_REACHABILITY=YES
EXISTING_OWNER_IDENTIFIED_OR_BEING_FALSIFIED=YES
```

If not, retire it.

Hot-loop complexity brake:

- 3 meaningful Luna/SOL cycles without causal-status movement; or
- 5 meaningful commits without product-boundary movement

→ escalate `PRODUCT_FIRST_SCOPE_REVIEW` to ChatGPT_PO.

Watchdog brake:

```text
DOES_THIS_CHANGE_A_PRODUCT_DECISION?
```

If no, stop investigating and remain silent.

## Evidence and GitHub discipline

GitHub remains canonical durable source/checkpoint.

Use existing C2C/bridge routing when available and #409 as the durable recovery/evidence plane for the active Phase-4 mission.

Do not revive historical plumbing merely because its semantics were useful. Reuse workflow wisdom, not obsolete machinery.

Do not create:

- a new watcher service;
- a new daemon;
- a new queue;
- a new bridge;
- a new registry/store;
- a new control plane;
- universal semantic-occurrence authority;
- GitHub runtime approval readers/issuers;
- identity-authority subsystems.

Do not create docs/status PR churn for transient mutable state.

## Active Phase-4 compatibility

For #409, the acceptance direction remains:

```text
source/provenance
→ GEOMETRY_VISUAL
→ dimensions/text as applicable
→ editability/readback
→ save/reopen
→ deterministic verification
```

The five watchdogs may falsify, prepare lookahead, or surface a material defect, but they must not silently replace this product sequence with an architecture-derived gate.

## Watchdog output contract

Each scheduled/event-driven role emits only when material:

```text
SOL_WATCHDOG_FINDING_V1
ROLE=<role>
BASIS_MAIN=<fresh sha>
BASIS_PR=<n|NONE>
BASIS_HEAD=<sha|NONE>
BOUNDARY=<current first unsatisfied boundary>
SIGNAL=UNIQUE_FINDING|CONFIRMATION
SEVERITY=MATERIAL|ADVISORY
FINDING=<compact decision-changing finding>
EVIDENCE=<minimal GitHub/SHA pointers>
IMPACT=<what decision changes>
NEXT_OWNER=LUNA|SOL_PO22|CHATGPT_PO
NEXT_SINGLE_BOUNDED_ACTION=<exactly one action>
BLOCKS_HOT_LOOP=YES|NO
BLOCKS_MERGE=YES|NO
HUMAN_GATE=YES|NO
```

If there is no unique decision-changing signal, emit nothing.

## Success criteria

This operating model is functioning correctly when:

1. Luna ↔ SOL_PO22 can continue without waiting for optional specialists.
2. Five specialist SOLs continuously fresh-read and independently falsify/look ahead.
3. No duplicate no-op review spam appears.
4. Material runtime merges still receive mandatory Security + Integration independent review.
5. Specialist findings interrupt only when decision-changing.
6. Product boundary movement, not review/comment count, is the optimization target.
7. Human is never used as the message bus.
8. No new coordination subsystem is created.

## Golden rule

**Luna executes what requires the workstation. SOL_PO22 owns the hot causal review loop. Five independent SOL watchdogs falsify and look ahead in parallel. GitHub/CI/runtime evidence proves. ChatGPT_PO handles only material product/architecture escalation. Human is not the message bus.**
