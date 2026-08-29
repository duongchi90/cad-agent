# CAD Agent Lean Rebaseline Design

Status: Human Owner approved on 2026-08-29 under Issue #295.

Exact base: `1b8b5cd2be0611fc0b3b9f6ffd77b39e58fbc87a`.

Branch: `governance/lean-rebaseline-2026-08-29`.

## 1. Decision

CAD Agent keeps its existing deterministic CAD engine, fail-closed safety invariants, and established Human Owner → SOL_POOL → Luna/Codex Desktop operating model. The only intended simplification is product sequencing and abstraction admission: build fewer speculative subsystems, reach a verified end-to-end product loop earlier, and let measured failures justify later architecture.

The rebaseline is forward-looking. It does not delete accepted contracts, erase evidence, rewrite history, invalidate completed tests, or replace standing governance. Existing R*, P*, VS-T*, M*, S* and related labels remain historical traceability and may be reactivated only by a fresh current Issue or valid control authority.

## 2. Non-negotiable operating-model preservation

The following standing GitHub contracts remain authoritative and are not superseded by this design:

- standing operating model: Issue #131 comment `5396800691`;
- cross-chat persistence/long-horizon invariants: comment `5419064061`;
- `PRE_ISSUANCE_GATE_V1`: comment `5442771213`;
- five-SOL writer eligibility / fail-closed lease: comment `5443060158`;
- #131 historical + #294 successor-ledger rollover contract.

Lean Rebaseline simplifies **what the project chooses to build**, not **how the parties are required to work when building it**.

### Human Owner

- remains the highest product and engineering authority;
- supplies or approves real engineering truth, private inputs, measurements, fixtures, and Human-only decisions;
- is not a routine relay hop between SOL and Luna;
- is asked only for genuine HUMAN_ONLY, product, secret/account-consent, safety, or irreversible decisions.

### Five SOL / Web control plane

The five active roles remain enabled at their existing staggered cadence:

- CONTROL_GOVERNANCE;
- ARCHITECTURE_REUSE;
- INTEGRATION_CI;
- SECURITY_REDTEAM;
- EVIDENCE_ACCEPTANCE.

All five remain writer-eligible, but never concurrently for one target sequence. Exactly one valid writer lease may mint the next numbered authority; all other cells are advisory `CONTROL_SEQ=NONE` for that sequence.

Every SOL governance/runtime action continues to require fresh GitHub state. `SOL_WRITER_CLAIM_V1`, lowest-valid-comment-ID arbitration, exact readback, anti-race checks, terminal single-consumption, current main/PR tuple verification, and `PRE_ISSUANCE_GATE_V1` remain mandatory.

While Luna executes N, SOLs should prepare N+1 and N+2 to the dependency limit: causal risks, reuse/owner map, RED/GREEN, write-set, security, evidence, acceptance, and pre-execution closure. Accepted PASS evidence is reused absent concrete drift.

SOL/Web continues to own broad reasoning, architecture/reuse/security/root-cause/source-contract analysis, CI/evidence interpretation, acceptance, reconciliation, merge/publication decisions, and successor issuance.

### Luna / Codex Desktop — sole Local Solo Executor

Exactly one Local Solo Executor remains: Luna / Codex Desktop. No second machine writer/executor is introduced.

Within an explicitly issued numbered mission, exact branch/write-set, and granted live scope, Luna should continue autonomously through the complete same-layer causal family rather than returning baton after every small defect. This includes, when authorized:

- fresh-read and exact tuple verification;
- local source/reuse/root-cause inspection;
- temp-only probes and harnesses;
- RED-first TDD for executable behavior;
- minimal GREEN;
- focused and nearest relevant regressions;
- build/static checks, cleanup, normal commits and push;
- authorized AutoCAD/COM/ROT/File-IPC/.NET-live execution and same-epoch follow-through.

Small parser/script/helper/telemetry/serialization/import/test-harness defects are not automatic handoff boundaries when safely repairable within the issued scope and causal budget.

Hard handoff remains limited to the established boundaries: required architecture/interface/dependency/workflow/schema/write-set expansion; security/authority/trust/privacy ambiguity; genuine new cross-layer defect; exhausted causal budget; unprovable cleanup/parity/custody; Human-only action; mission completion requiring acceptance/merge/publication governance; or superseding numbered authority.

Repo write authority never implies merge. No amend/rebase/squash/force-push unless separately authorized.

### Pre-execution closure

Before expensive, stateful, live, mutating, publishing, provider, or pilot execution, the controller/orchestration path must be proved offline/synthetically as far as technically possible. Live execution should target a genuinely new business/evidence boundary, not discover controller defects that can reasonably be closed offline.

`SKIP` and `NOT RUN` remain non-PASS.

## 3. Product objective

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

## 4. Architecture retained

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

Every newly built capability required by M1 still follows the full standing operating model and exact numbered authority process above.

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
- stronger audit/security where real production risk justifies it.

## 6. Historical roadmap treatment

P0-P10, R1-R8, VS-T*, M*, S* and prior plans remain valid evidence records for what was designed, tested, accepted, rejected, or left `NOT RUN`.

They no longer act as the default daily product queue after this rebaseline. A historical slice becomes active again only when:

1. a current milestone needs it;
2. a measured failure or dependency identifies it as the smallest correct owner;
3. a fresh Issue/authority names the exact scope and evidence gate.

This changes prioritization only. It does not waive any standing execution/governance contract when that slice is reactivated.

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

This is a conceptual consolidation target only. It does not authorize schema migration or deletion of existing accepted contracts. Existing types remain until a separately authorized, measured simplification task proves a safe migration is worthwhile.

## 9. Success metrics

The rebaseline is successful if it reduces architecture and coordination waste without weakening evidence or the standing operating model.

Track:

- terminal-to-next-valid-authority latency;
- time from issue start to first causal evidence;
- Golden Path completion rate;
- benchmark end-to-end success rate;
- Human intervention per run;
- number of new top-level abstractions added per measured failure;
- duplicate-owner/transport findings;
- regressions escaping focused tests;
- stale roadmap/status claims discovered during fresh-read startup.

The desired direction is fewer speculative abstractions and fewer unnecessary roadmap hops per accepted capability, while long-horizon mission execution and fail-closed safety remain intact.

## 10. Explicit non-goals

This rebaseline does not:

- change or reduce the five SOL schedules;
- replace or weaken comments `5396800691`, `5419064061`, `5442771213`, or `5443060158`;
- change the #131/#294 control protocol;
- create a new risk-tier or substitute governance model;
- supersede the active Luna authority or PR #285 lane;
- change runtime code, tests, workflows, schemas, dependencies, File IPC, .NET, AutoCAD, or provider behavior;
- merge or close existing runtime Issues/PRs;
- claim any `NOT RUN` live/private gate is now passed;
- authorize production publication or private drawing mutation.

## 11. Rollback

Because this rebaseline is documentation/governance only, rollback is a normal revert of its documentation commits/merge. Accepted runtime evidence, standing governance comments, and historical plans remain intact either way.
