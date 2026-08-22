# CAD Agent — AI Operating Model

Status: stable role and authority model.

This document defines who may decide, implement, verify, and publish. It applies across ChatGPT, Codex, future coding agents, and the CAD Agent runtime.

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
- issue the next task only after the current task is accepted and merged;
- distinguish repository evidence from inference or chat memory.

### 2.2 Prohibited actions

ChatGPT must not:

- claim that Codex started or completed work without branch/commit/diff/PR evidence;
- treat a PR body as proof when the diff or CI disagrees;
- call `SKIP` or `NOT RUN` a PASS;
- silently invent live AutoCAD, private-data, engineering, or user-approval evidence;
- implement production code while acting in PO read-only mode;
- approve Codex self-review as independent acceptance;
- bypass M2 Drawing Initialization or the active reuse-first sequencing;
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

Every implementation Issue must record the following before production behavior is authorized:

- internal owners/APIs/contracts/tests inspected;
- external repositories/vendor samples inspected;
- exact revision/tag and license;
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

`NEW_MISSING_CAPABILITY` is permitted only when the dossier names the internal and external alternatives inspected and gives a concrete gap reason.

## Parallel execution rules

- one writer owns each overlapping file set.
- A research lane is read-only and may inspect internal APIs, external repositories, licenses, benchmarks, and fit.
- A live-preparation lane may prepare fixtures and evidence commands but must not modify runtime code or production behavior.
- Hosted CI runs independently against the declared exact head or synthetic merge.
- PO review is independent of implementation and hosted CI.
- Shared canonical documents, including status and handoff, are changed only by the integration owner.

## 3. Codex role — bounded implementation agent

Codex is the coding and execution agent.

### 3.1 Responsibilities

Codex must:

- implement exactly one approved issue/task at a time;
- branch from the issue's declared base unless the PO explicitly rebases the task;
- read the active design, implementation plan, architecture, handoff, and issue;
- use TDD: focused failing test, minimal implementation, focused pass, aggregate verification;
- modify only allowed files unless it stops and requests a scope amendment;
- reuse current APIs and package boundaries before creating anything new;
- include a truthful Reuse Declaration in implementation PRs;
- create bounded commits and a non-draft PR only when the task is complete;
- record exact final head SHA, commands, counts, and live/private gate states;
- stop after opening the task PR and wait for PO review.

### 3.2 Prohibited actions

Codex must not:

- start the next task without PO acceptance and merge;
- work directly on `main`;
- weaken a reviewed contract to fit existing code;
- build a parallel OCR, dimension-recognition, semantic-solver, DXF, AutoCAD, repair, manifest, revision, verdict, or publication system;
- issue a visual PASS, approve its own repair, promote a revision, or publish;
- modify private/production drawings without the explicit approved live gate;
- describe missing prerequisites as a pass;
- use chat memory as a substitute for repository inspection.

### 3.3 Codex completion package

A Codex PR must contain:

- issue/task reference;
- base SHA and final head SHA;
- exact changed-file scope;
- Reuse Declaration;
- focused and aggregate verification commands/results;
- truthful `PASS`, `FAIL`, `SKIP`, and `NOT RUN` gates;
- migration/rollback statement;
- no claim of acceptance by Codex itself.

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
ChatGPT PO defines issue, scope, acceptance, and forbidden work
        ↓
Codex implements one bounded task and opens PR
        ↓
GitHub diff + tests + exact-head CI + truthful external gates
        ↓
ChatGPT PO independently reviews
        ↓
Changes required  OR  merge and issue next task
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
Fresh independent evidence and PO/product gates
        ↓
Verified Publisher may promote only after all authorities agree
```

## 7. Conflict rules

When sources disagree:

- GitHub current state beats chat memory.
- Exact final-head diff/CI beats PR-body claims.
- Approved design/plan beats an old roadmap.
- Exact matching base CAD controls unchanged original geometry, subject to provenance and approved extraction.
- Confirmed dimensions require an independent second source or auditable engineer confirmation.
- AI inference may complete a candidate draft but cannot silently become source truth.
- Engineering conflicts are escalated to the owner by component/region cluster.

## 8. Session-start protocol

Every new PO or Codex session must first read:

1. `docs/HANDOFF.md`
2. `docs/STATUS.md`
3. `docs/ARCHITECTURE.md`
4. the active specification and plan named in the handoff
5. the active issue and current PR, if any
6. `docs/CONTROL_PROTOCOL.md` when the session participates in SOL/Luna baton, Audit, local/live execution, or control-plane governance

Then verify current `main`, issue state, branch/PR, exact head, changed files, diff, and CI.

No task work or status conclusion should precede this verification.

## 9. SOL / Luna baton and Audit control plane

For SOL/Luna orchestration, `docs/CONTROL_PROTOCOL.md` is the normative control-plane contract.

### 9.1 Baton ownership

`NEXT_OWNER` is exactly one of `SOL` or `Luna / Codex Desktop`. SOL owns governance, architecture/audit/security disposition, evidence reconciliation, and action authorization. Luna / Codex Desktop owns bounded local Windows/AutoCAD execution and approved repository implementation work. Human Owner is not used as a relay between the two agents.

Every wake begins with fresh GitHub state and follows:

`fresh main -> canonical HOT STATE -> newest terminal/action -> NEXT_OWNER -> act only for that owner`.

If there is no material delta and Luna is executing the correct packet, SOL/Audit creates no new work or comment.

### 9.2 Explicit action authority

New packets do not use standalone `STOP_WRITE`. They separately declare repository-write, live-execution, and persistent-mutation authority with:

```text
LIVE_AUTHORITY=YES|NO
ATTEMPT_BUDGET=<integer>
STOP_REPO_WRITE=YES|NO
STOP_LIVE=YES|NO
STOP_PERSISTENT_MUTATION=YES|NO
```

Live carve-outs must explicitly identify any superseded older live lock and are valid only for the named action. No live carve-out implicitly unlocks camera/render/File-IPC business execution, R6/R7, merge, or retry.

### 9.3 Exactly-once control

A technical terminal has one controlling SOL consumer. The earliest valid consumer controls; later consumers of the same terminal are `VOID_FOR_CONTROL` and cannot open a parallel execution branch. Audit resolves duplicates without unioning authorities from void paths.

Control chronology uses explicit predecessor/consumer links, monotonic `CONTROL_SEQ`, canonical HOT STATE, and exact SHA/artifact identity. Connector timestamps are not sufficient authority ordering because they can be absent.

### 9.4 Audit anti-churn and evidence truthfulness

`NO_MATERIAL_DELTA => NO_COMMENT`.

Audit does not regenerate packets solely to restate the same contract. `PASS`, `BLOCKED`, `PRECONDITION_BLOCKED`, and `EVIDENCE_INSUFFICIENT` remain distinct. Missing or unretained causal evidence must not be inferred and cannot be promoted to a defect conclusion.

Accepted local artifact epochs remain retained until SOL accepts a successor or the owning task explicitly releases retention. Artifact authority is literal path + length + SHA-256, never a path guessed or reconstructed from a commit SHA.

### 9.5 Live acknowledgement and terminal completeness

Before live or persistent-mutation execution, Luna records an ACK bound to the exact authority, control sequence, attempt budget, and relevant literal artifact identities. Contradictory authority fails closed as `PACKET_CONTRADICTION`.

Local/live terminals retain the first causal boundary plus relevant requested/observed document identity, artifact hashes, process/session identity, trace integrity, cleanup/survivor state, repository parity, and material `NOT_RUN` gates.

### 9.6 Independent dual review

Issue #131 standing rule comment `5308943608` remains binding. When SOL requires two independent reviews, SOL freezes one canonical evidence set, completes Pass A, then completes Pass B without exposing Pass A verdict/findings to B before B is final. Reconciliation occurs only after both are independently complete. Evidence drift re-epochs both. Luna is not reviewer #2 merely to manufacture independence.
