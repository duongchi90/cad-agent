# CAD Agent Lean Rebaseline Design

Status: Human Owner approved on 2026-08-29 under Issue #295.

Exact base: `1b8b5cd2be0611fc0b3b9f6ffd77b39e58fbc87a`.

Branch: `governance/lean-rebaseline-2026-08-29`.

## 1. Decision

CAD Agent keeps its existing deterministic CAD engine and its fail-closed safety invariants, but simplifies the program around a small number of product milestones and measured failures.

The rebaseline is forward-looking. It does not delete accepted contracts, erase evidence, rewrite history, or invalidate completed tests. Existing R*, P*, VS-T*, M*, S* and related labels remain historical traceability and may be reactivated only by a fresh current Issue or valid control authority.

The five active SOL schedules are explicitly retained. Their purpose is low-latency autonomous governance when the Human Owner is away from the machine. This rebaseline does not reduce their cadence, roles, writer-lease rules, control-ledger protocol, or SOL↔Luna handoff safety.

## 2. Product objective

The shortest useful product loop is:

```text
approved inputs
  -> existing CAD reconstruction engine
  -> disposable/native CAD candidate
  -> one canonical AutoCAD request/result route
  -> deterministic + visual/engineering verification
  -> PASS output or bounded repair
```

The first priority is a reproducible Golden Path that works end to end on one disposable drawing, then on a small benchmark set. New abstraction is justified by measured failure, not by hypothetical future complexity.

## 3. Architecture retained

The authoritative execution engine remains:

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

`cad_agent` remains orchestration only. It must not absorb OCR, solving, DXF generation, AutoCAD transport, or repair execution already owned elsewhere.

The following invariants remain mandatory:

- dimension-first engineering authority;
- approved datum/constraint authority over pixel estimates;
- immutable source and accepted CAD;
- disposable candidate mutation by default;
- exact target/source identity before mutation;
- one canonical AutoCAD request/result route;
- deterministic validation before trust;
- truthful `PASS`, `FAIL`, `SKIP`, and `NOT RUN` states;
- explicit approval before risky production mutation;
- verified backup, reopen, post-operation verification, and rollback where production mutation is allowed;
- no fabricated private-data, AutoCAD-live, engineering, or Human approval evidence.

## 4. Five SOL control model retained

The five active SOL roles remain enabled at their existing staggered hourly cadence:

- CONTROL_GOVERNANCE;
- ARCHITECTURE_REUSE;
- INTEGRATION_CI;
- SECURITY_REDTEAM;
- EVIDENCE_ACCEPTANCE.

This is an intentional responsiveness design, not a product subsystem. The existing writer-lease and control-ledger rules remain the collision-prevention mechanism. A valid active Luna authority is not interrupted by a competing SOL authority.

The rebaseline simplifies what the SOLs ask Luna to build; it does not reduce SOL availability.

## 5. Active operational roadmap

### M0 — Stabilize the Pipe

Goal: make the control and execution pipe boring and dependable before adding product abstractions.

Exit criteria:

- the active PR #285 causal layer is resolved and integrated through its valid control process;
- successor ledger #294 routes local-executor dispatch, ACK, and terminal to the source ledger on default `main`;
- one canonical AutoCAD request/result path is selected and positively verified before later live CAD work;
- hosted CI/reuse are green except for explicitly separated negative-oracle jobs;
- no second executor, transport, dispatcher, ACK protocol, or result store exists.

### M1 — Golden Path

Goal: one approved disposable drawing completes the shortest end-to-end product loop.

Required outcome:

- approved source/input identity;
- approved critical dimensions/datums or explicit unresolved blockers;
- reuse of accepted exact-base/native assets where applicable;
- native editable candidate generation through existing engines;
- AutoCAD Mechanical 2027 open/render/inspect through the canonical route;
- deterministic geometry/dimension/native-editability checks;
- review evidence and a truthful final candidate state;
- no source or accepted drawing overwritten.

No generic publisher, registry expansion, revision framework, or autonomous repair platform is a prerequisite unless the Golden Path exposes a concrete missing capability.

### M2 — Benchmark

Goal: learn from a small but varied set of disposable/approved cases before generalizing architecture.

Track at minimum:

- end-to-end success rate;
- median wall-clock per run;
- Human intervention count;
- unresolved dimension/datum count;
- geometry/dimension/visual defect counts;
- AutoCAD transport/timeout failures;
- repair attempts required;
- stale-evidence and wrong-target rejection events.

A new top-level subsystem or contract requires a named benchmark failure or measured operational bottleneck that an existing owner cannot represent safely.

### M3 — Repair Loop

Goal: add bounded repair only after Golden Path and benchmark evidence identify repeatable repair needs.

Required behavior:

- verifier finding -> bounded repair plan -> approved executor -> fresh verification;
- source/accepted CAD remains immutable;
- risky changes require Human/engineering approval;
- post-repair evidence is fresh;
- rollback remains available;
- repair cannot self-approve visual or engineering correctness.

### M4 — Production Hardening

Goal: private-data and production readiness after disposable reliability is demonstrated.

Includes only evidence-justified work such as:

- private benchmark normalization;
- production save/reopen/rollback evidence;
- verified publication/promotion if actually required;
- multi-job recovery and operational diagnostics;
- stronger audit/security only where real production risk justifies it.

## 6. Historical roadmap treatment

P0-P10, R1-R8, VS-T*, M*, S* and prior plans remain valid evidence records for what was designed, tested, accepted, rejected, or left `NOT RUN`.

They no longer act as the default daily execution queue after this rebaseline. A historical slice becomes active again only when:

1. a current milestone needs it;
2. a measured failure or dependency identifies it as the smallest correct owner;
3. a fresh Issue/authority names the exact scope and evidence gate.

This prevents roadmap labels from becoming automatic implementation authority.

## 7. Anti-overengineering rule

Before creating any new top-level contract, registry, state machine, authority store, transport, executor, publisher, or long-lived artifact type, answer in order:

1. Can the invariant be enforced by an existing owner/API?
2. Can a thin adapter or validator close the gap?
3. Is there a deterministic failing test or benchmark case proving the gap?
4. Does the new abstraction remove more complexity than it adds?

If the first two answers can solve the problem, do not create the new subsystem.

Accepted existing artifacts are not deleted merely to make the design look smaller. Freeze/defer is preferred over migration churn.

## 8. Conceptual evidence simplification

For product reasoning, future work should prefer three conceptual durable groups rather than inventing a new top-level authority for every concern:

```text
JobManifest
  - source/input identities
  - approved engineering inputs
  - configuration and run state

CandidateArtifact
  - candidate identity/path/hash/revision
  - provenance and changed scope

VerificationEvidence
  - deterministic checks
  - AutoCAD evidence
  - visual/engineering findings
  - approval/rollback references
```

This is a conceptual consolidation target only. It does not authorize schema migration or deletion of existing accepted contracts. Existing types remain until a measured simplification task proves a safe migration is worthwhile.

## 9. Risk-tiered governance

### Tier A — full governance required

Use the full design/reuse/security/write-set/review process for:

- new production behavior or mutation authority;
- security/trust boundary changes;
- new transport/protocol/executor/dispatcher/result store;
- schema or authoritative state-store changes;
- AutoCAD mutation or save behavior;
- private/customer data handling;
- publisher/release/promotion behavior;
- new dependency or external component;
- irreversible or difficult-to-rollback changes.

Tier A requires a current design or explicit equivalent Issue specification, internal/external reuse analysis where relevant, causal TDD, exact write-set, focused and nearest regressions, hosted verification, independent review, migration/rollback, and truthful live/private gates.

### Tier B — bounded engineering

Use for same-owner bug fixes, test-harness/classification defects, small adapters, and non-authority tooling changes that do not create a new subsystem or trust boundary.

Required minimum:

- current Issue/authority;
- exact base/head and write-set;
- causal RED where behavior changes;
- minimal GREEN;
- focused + nearest relevant regressions;
- hosted CI/reuse when repository behavior is affected;
- no external-reuse survey unless a new dependency/capability is proposed.

### Tier C — documentation/evidence maintenance

Use for docs-only status, handoff, roadmap, wording, or evidence-index changes with no runtime behavior.

Required minimum:

- bounded Issue or Human Owner instruction;
- exact write-set;
- source-of-truth fresh-read;
- diff/readback verification;
- normal PR/integration path when canonical docs change.

## 10. Acceptance and success metrics

The rebaseline is successful if it reduces engineering coordination cost without weakening product evidence.

Track:

- terminal-to-next-valid-authority latency;
- time from issue start to first causal evidence;
- Golden Path completion rate;
- benchmark end-to-end success rate;
- Human intervention per run;
- number of new top-level abstractions added per measured failure;
- duplicate-owner/transport findings;
- regressions escaping focused tests;
- number of stale roadmap/status claims discovered during session start.

The desired direction is fewer abstractions and fewer governance hops per accepted capability, while exact safety failures remain fail-closed.

## 11. Explicit non-goals

This rebaseline does not:

- change the five SOL schedules;
- change the #131/#294 control protocol;
- supersede the active Luna authority or PR #285 lane;
- change runtime code, tests, workflows, schemas, dependencies, File IPC, .NET, AutoCAD, or provider behavior;
- merge or close existing runtime Issues/PRs;
- claim any `NOT RUN` live/private gate is now passed;
- authorize production publication or private drawing mutation.

## 12. Rollback

Because this rebaseline is documentation/governance only, rollback is a normal revert of its documentation commits/merge. Accepted runtime evidence and historical plans remain intact either way.
