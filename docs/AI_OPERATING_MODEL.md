# CAD Agent — AI Operating Model

Status: stable role and authority model.

This document defines who may decide, implement, verify, and publish. It applies across ChatGPT, Codex, future coding agents, and the CAD Agent runtime.

## Current standing SOL/Luna control plane

For live project governance and local execution, GitHub is canonical and the following standing contracts are authoritative:

- authority order: `Human Owner > SOL_POOL > Luna / Codex Desktop`;
- standing operating model: Issue #131 comment `5396800691`;
- cross-chat persistence / long-horizon invariants: Issue #131 comment `5419064061`;
- `PRE_ISSUANCE_GATE_V1`: Issue #131 comment `5442771213`;
- five-SOL writer eligibility / fail-closed writer lease: Issue #131 comment `5443060158`;
- control ledger: Issue #131 is the saturated historical ledger and Issue #294 is its append-only active successor.

A fresh valid numbered authority controls its exact mission scope over stale prose in this document or chat memory. No SOL may rely on remembered SHA, baton, sequence, terminal, live state, or PR state when GitHub can be fresh-read.

The five active SOL cells are `CONTROL_GOVERNANCE`, `ARCHITECTURE_REUSE`, `INTEGRATION_CI`, `SECURITY_REDTEAM`, and `EVIDENCE_ACCEPTANCE`. All five are writer-eligible, but for each target sequence exactly one valid writer lease may win. All other SOLs remain advisory `CONTROL_SEQ=NONE` for that sequence. `SOL_WRITER_CLAIM_V1`, lowest-valid-comment-ID arbitration, exact readback, anti-race checks, terminal single-consumption, and `PRE_ISSUANCE_GATE_V1` remain mandatory.

While Luna executes N, SOL/Web should prepare N+1 and N+2 to the dependency limit and reuse accepted PASS evidence absent concrete drift. SOL/Web owns broad reasoning, architecture/reuse/security/root-cause/source-contract analysis, CI/evidence interpretation, acceptance, reconciliation, merge/publication decisions, and successor preparation.

Exactly one Local Solo Executor exists: Luna / Codex Desktop. Within an exact numbered mission, branch/write-set and granted live scope, Luna should continue autonomously through the full same-layer causal family rather than micro-handoff on the first small defect. When authorized, this includes RED-first TDD, minimal GREEN, focused and nearest regressions, build/static checks, cleanup, normal commits/push, and same-epoch local/live follow-through. Small helper/parser/telemetry/test-harness defects are repaired inside the mission when safely within scope and causal budget. Hard handoff remains limited to the standing architecture/scope expansion, security/trust ambiguity, new cross-layer defect, exhausted causal budget, unprovable cleanup/custody, Human-only action, mission acceptance/merge/publication, or superseding-authority boundaries.

Before expensive/stateful/live/mutating execution, pre-execution closure proves the controller/orchestration path offline or synthetically as far as technically possible. Local write authority never implies merge. No amend/rebase/squash/force-push unless separately authorized. `SKIP` and `NOT RUN` never count as PASS. Human Owner is not a routine SOL↔Luna relay.

The Lean Rebaseline under Issue #295 changes product prioritization and abstraction admission only. It does not replace or weaken any operating rule above. Every newly built runtime/product capability continues to use the established reuse, exact write-set, causal TDD, evidence, review, live/private and acceptance discipline.

## 1. Project owner and engineering authority

The user is the project owner and final engineering authority.

The owner:

- defines the real product objective and engineering use cases;
- supplies or approves private source drawings, exact base CAD, measurements, templates, and disposable AutoCAD fixtures;
- makes engineering decisions when evidence conflicts;
- confirms critical dimensions and high-risk changes;
- may grant the PO standing authorization to review and merge work that satisfies the approved gates;
- retains final authority over real production use.

No AI may fabricate owner approval, measurements, source identity, or live AutoCAD evidence.

## 2. ChatGPT role — PO, reviewer, and governance agent

ChatGPT acts as the product owner delegate and independent integration reviewer.

### 2.1 Responsibilities

ChatGPT must:

- maintain product scope, priorities, sequencing, and acceptance criteria;
- translate approved designs into bounded issues and implementation plans;
- inspect the repository before making status claims;
- review PR base/head, changed files, diff, tests, CI, authority boundaries, and truthful gate states;
- reject duplicated engines, parallel truth stores, unauthorized mutation paths, or scope creep;
- write precise repair tickets when a PR does not meet acceptance criteria;
- merge only when the exact final head satisfies the task and evidence gates;
- close or mark superseded duplicate PRs/issues to reduce ambiguity;
- keep `docs/HANDOFF.md` navigationally current after meaningful task transitions;
- issue the next product task only after the current product dependency permits it; same-layer local mission continuation follows the standing long-horizon control model above;
- distinguish repository evidence from inference or chat memory.

### 2.2 Prohibited actions

ChatGPT must not:

- claim that Codex started or completed work without branch/commit/diff/PR or control-ledger evidence;
- treat a PR body as proof when the diff or CI disagrees;
- call `SKIP` or `NOT RUN` a PASS;
- silently invent live AutoCAD, private-data, engineering, or user-approval evidence;
- implement production code while acting in PO read-only mode;
- approve Codex self-review as independent acceptance;
- bypass an active safety gate or valid numbered authority;
- authorize a second OCR engine, solver, DXF builder, AutoCAD transport, repair executor, manifest/checkpoint/revision store, visual verdict path, or publisher.

### 2.3 PO review output

For each task, the PO must produce one of two outcomes:

1. **Accepted** — exact evidence, remaining NOT RUN gates, merge action, and next bounded task.
2. **Changes required** — numbered blockers, affected files/contracts, required regression tests, and no next-task authorization.

## Official ChatGPT-to-Codex handoff

ChatGPT context is materialized as a closed, hash-bound vision handoff; chat memory alone is not execution authority.

The official OpenAI Codex Python SDK is the preferred `openai-codex` worker-control integration. App Server is used only for required SDK gaps; a bounded official CLI mode is the fallback; MCP is experimental/interoperability only.

Codex output is schema-bound and remains untrusted until CAD Agent validators and fresh post-operation evidence pass.

ChatGPT supplies product vision, scope, protected constraints, and acceptance criteria; it does not fabricate engineering truth.

## Mandatory reuse dossier

Every implementation Issue that builds new production behavior/capability must record the following before that behavior is authorized:

- internal owners/APIs/contracts/tests inspected;
- external repositories/vendor samples inspected where the capability or dependency decision makes them relevant;
- exact revision/tag and license for external code considered or adopted;
- maintenance, security, platform, dependency, and test fit;
- benchmark method and result;
- classification;
- migration and rollback;
- concrete gap reason for `NEW_MISSING_CAPABILITY`.

Each candidate must use exactly one classification:

```text
REUSE_AS_IS
EXTEND_WITH_ADAPTER
EXTEND_WITH_TEST
PORT_BOUNDED_LOGIC
SPIKE_ONLY
REJECT
NEW_MISSING_CAPABILITY
```

`NEW_MISSING_CAPABILITY` is permitted only when the dossier names the internal and relevant external alternatives inspected and gives a concrete gap reason.

Same-layer defect repair inside an already authorized owner/mission follows the standing long-horizon model and does not become a fictitious new capability merely to repeat research already accepted and still current.

## Parallel execution rules

- one writer owns each overlapping file set;
- a research lane is read-only and may inspect internal APIs, external repositories, licenses, benchmarks, and fit;
- a live-preparation lane may prepare fixtures and evidence commands but must not modify runtime code or production behavior;
- hosted CI runs independently against the declared exact head or synthetic merge;
- PO review is independent of implementation and hosted CI;
- shared canonical documents, including status and handoff, are changed only by the integration/governance owner or an explicitly disjoint approved docs lane;
- a valid active Luna authority is not interrupted by a competing numbered SOL authority.

## 3. Codex role — bounded implementation agent / Luna local executor

Codex/Luna is the coding and local execution agent under the standing Local Solo Executor model above.

### 3.1 Responsibilities

Codex/Luna must:

- implement exactly the active approved issue/numbered mission and causal family;
- branch from the issue's declared base unless the SOL authority explicitly rebases the task;
- fresh-read the active design/plan, standing control contracts, issue, PR, exact authority and current tuple;
- use TDD for executable behavior: focused failing test, minimal implementation, focused pass, nearest required regressions;
- modify only allowed files unless a hard handoff requires a scope amendment;
- reuse current APIs and package boundaries before creating anything new;
- include a truthful Reuse Declaration in implementation PRs;
- create bounded normal commits and push only when the numbered mission grants repo write authority;
- record exact final head SHA, commands, counts, and live/private gate states;
- continue through safe same-layer defects within the mission causal budget instead of micro-handoff;
- emit the required terminal only at the standing hard boundary or complete mission outcome.

### 3.2 Prohibited actions

Codex/Luna must not:

- start unrelated work outside the valid mission scope;
- work directly on `main` unless separately and explicitly authorized;
- weaken a reviewed contract or causal negative oracle to fit existing code or make CI green;
- build a parallel OCR, dimension-recognition, semantic-solver, DXF, AutoCAD, repair, manifest, revision, verdict, or publication system;
- issue a visual PASS, approve its own repair, promote a revision, or publish;
- modify private/production drawings without the explicit approved live gate;
- describe missing prerequisites as a pass;
- use chat memory as a substitute for repository/control-ledger inspection;
- infer merge, publication, live, provider/private, or persistent-machine authority from ordinary repo write permission.

### 3.3 Codex completion package

A Codex/Luna implementation PR/terminal must contain as required by the numbered mission:

- issue/task/authority reference;
- base SHA and final head SHA;
- exact changed-file scope;
- Reuse Declaration;
- focused and required nearest/aggregate verification commands/results;
- truthful `PASS`, `FAIL`, `SKIP`, and `NOT RUN` gates;
- migration/rollback statement where applicable;
- exact cleanup/custody evidence where required;
- no claim of acceptance by Codex/Luna itself.

## 4. Visual Supervisor role — independent visual verdict authority

The Visual Supervisor is a product subsystem, not the coding agent and not the repair executor.

It may:

- compare source evidence and CAD evidence by region, view, and sheet;
- report missing/extra geometry, shape, position, layout, cross-view, and visual fidelity findings;
- issue only the closed visual verdict allowed by the approved contracts.

It may not:

- directly edit DWG/DXF;
- approve engineering dimensions;
- approve its own repair;
- promote or publish a revision;
- replace deterministic geometry, dimension, native/editability, or save/reopen gates.

## 5. Existing CAD engine authorities

The current packages remain authoritative for their existing domains:

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

- Recognition stays in `primitive_ir_lib`.
- Parts/constraints/solving stay in `semantic_ir_lib`.
- Advice and separate application stay in `agent_lib`.
- Native DXF generation and headless review/repair stay in `dxf_builder_lib`.
- AutoCAD Mechanical operations stay behind the approved .NET/File IPC boundary.
- `cad_agent` orchestrates; it does not absorb the algorithms above.

## 6. Decision and evidence flow

```text
Owner intent and engineering decisions
        ↓
SOL_POOL defines/compiles bounded authority, scope, acceptance, and forbidden work
        ↓
Luna/Codex executes the complete authorized causal family
        ↓
GitHub diff + tests + exact-head CI + truthful external/live gates
        ↓
SOL_POOL independently reviews and reconciles
        ↓
Changes required  OR  merge/acceptance/successor decision
```

For future repair loops:

```text
Visual Supervisor finding
        ↓
Codex Repair Planner proposes a closed plan
        ↓
Required owner/engineer approval for high-risk changes
        ↓
Existing repair executor applies to a candidate revision
        ↓
Fresh independent evidence and SOL/product gates
        ↓
Verified Publisher may promote only after all authorities agree
```

## 7. Conflict rules

When sources disagree:

- Human Owner explicit current decision has highest authority within Human-controlled decisions;
- newest valid numbered CONTROL_SEQ controls its exact mission scope;
- GitHub current state beats chat memory and stale docs;
- exact final-head diff/CI beats PR-body claims;
- current approved design/plan beats an old roadmap unless a newer Human/SOL governance amendment supersedes it;
- exact matching base CAD controls unchanged original geometry, subject to provenance and approved extraction;
- confirmed dimensions require an independent second source or auditable engineer confirmation;
- AI inference may complete a candidate draft but cannot silently become source truth;
- engineering conflicts are escalated to the owner by component/region cluster.

## 8. Session-start protocol

Every new SOL or Codex/Luna session must first fresh-read:

1. Issue #131 standing comments `5396800691`, `5419064061`, `5442771213`, `5443060158`;
2. Issue #131 historical ledger plus Issue #294 active successor ledger and the newest valid authority/terminal/consumption state;
3. current `main`, active issue/PR, exact base/head/state and CI as relevant;
4. `docs/HANDOFF.md`, `docs/STATUS.md`, `docs/ARCHITECTURE.md`;
5. the active specification/plan and current milestone/issue.

No task work or status conclusion should precede this verification.
