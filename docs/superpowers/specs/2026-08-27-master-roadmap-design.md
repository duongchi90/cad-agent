# CAD Agent Master Roadmap Design

Date: 2026-08-27
Status: APPROVED IN CHAT / WRITTEN SPEC FOR OWNER REVIEW
Roadmap issue: #291
Docs-only branch: `governance/master-roadmap-design`
Exact design base: `1263db2f54f505209ba6837b86181af8646b5a58`
Authority effect: NONE

## 1. Purpose

CAD Agent needs one durable roadmap that covers both:

1. how SOL/Web, reviewers, and the single Local Executor work efficiently without stale state, repeated discovery, or unnecessary live AutoCAD epochs; and
2. how the product progresses from source understanding to useful Mechanical CAD intelligence and finally image/PDF -> verified Mechanical CAD.

This document intentionally replaces the idea of maintaining separate competing roadmaps for operating-model enforcement, CADmind-inspired capabilities, Mechanical phases, and historical R0-R8 delivery labels.

Issue #131 remains the sole mutable runtime/control authority. This roadmap and its status references are planning/navigation only.

## 2. North star

```text
Image / PDF / DWG / user intent
  -> AI reads current CAD state
  -> discovers the right typed skill/capability
  -> reasons / solves / creates or repairs a candidate
  -> AutoCAD Mechanical only when machine evidence is genuinely required
  -> read-back + deterministic/visual evidence
  -> bounded repair if required
  -> VERIFIED CAD OUTPUT
```

Every phase runs on the same operating rail:

```text
FRESH STATE
 -> ROUTE TO THE RIGHT OWNER
 -> LONG-HORIZON MISSION
 -> REUSE VALID EVIDENCE
 -> LEARN FROM FAILURE
 -> VERIFY
```

The roadmap is optimized for useful vertical value, not maximum subsystem count.

## 3. Design principles

### 3.1 One roadmap, existing owners

Historical R0-R8 names remain implementation/history vocabulary. They do not become a second roadmap.

New capability should default to:

```text
existing owner + thin adapter
```

A new subsystem is allowed only when a reuse dossier proves a concrete missing capability.

### 3.2 GitHub currentness, not chat memory

Mutable decisions must fresh-read GitHub. Roadmap snapshots, docs, terminals copied into chat, and historical STATUS/HANDOFF text are never current authority.

The staged `control_snapshot` contract may represent already-fresh evidence deterministically, but it may not fetch or mint authority.

### 3.3 Typed capability, not arbitrary execution

The Local Executor must grow as a typed capability ladder. Arbitrary command/script fields are not an extension mechanism.

E1 `OFFLINE_VERIFY` is the first capability pattern. Windows probes, repository mutation, AutoCAD read-only, and AutoCAD mutation/live are separate future capability classes and require their own reviewed boundaries.

### 3.4 Evidence beats repeated reassurance

Exact accepted evidence should be reused when head/artifact/contract identity has not drifted. `SKIP` and `NOT_RUN` never satisfy a PASS gate.

### 3.5 One important failure should teach the system

A materially solved failure should become a failure-family signature, reviewed probe/oracle, regression eval, and safe repair/escalation boundary. Repeated broad rediscovery of a known failure is a process regression.

## 4. Master phases

### Phase 0 — Reliable AI Workforce

Goal: make SOL/Web, independent review, hosted CI, and the single Local Executor efficient and hard to misuse before expanding CAD capability.

Reuse the staged A-D/E1 foundation rather than building a new control plane:

- deterministic fresh-state projection;
- Web/local/Human routing;
- long-horizon mission compilation with causal budget, accepted evidence, cleanup and hard-handoff conditions;
- exact verification receipts and first-unsatisfied-gate logic;
- failure-family -> probe knowledge;
- sealed Local Executor mission consumption beginning with `OFFLINE_VERIFY`.

Operational target:

- a fresh SOL session reconstructs current state without Human recap;
- Web-capable analysis stays with SOL;
- Luna receives one bounded causal mission rather than one command at a time;
- SOL prepares N+1/N+2 read-only while local N executes;
- pre-execution closure catches controller/parser/orchestration defects before expensive/live work;
- review packets are exact-head, read-only, and invalidated by head drift.

Phase 0 is complete when these behaviors are routinely enforceable rather than remembered manually.

### Phase 1 — AI Reads CAD

Goal: give the AI a summary-first, provenance-bound view of current CAD state without dumping the entire drawing into model context.

Start with a thin query façade over existing owners:

```text
read_state(...)
query_entities(...)
```

Initial query needs only high-value capabilities:

- type/layer/component/region filters;
- selected-field projection;
- count/group/basic aggregation;
- batch entity IDs;
- drawing/state/version identity.

Add component/view/dimension/constraint reads or delta-since-version only when a real pilot requires them.

Reuse `mcp_integration_lib`, `primitive_ir_lib`, existing drawing gateways, provenance and currentness contracts. Do not create a shadow DWG database, SQLite mirror, vector database, or second CAD truth store.

Success test: the AI can answer bounded questions such as “what holes are in this front view?” or “what changed since the last state?” with provenance and without whole-drawing context dumps.

### Phase 2 — AI Uses Skills

Goal: let the model discover the right typed capability instead of memorizing a broad raw tool surface.

Minimal interface:

```text
search_skills(intent) -> typed descriptors
invoke_skill(skill_id, validated_parameters) -> existing owner/candidate path
```

Minimal metadata:

- skill id;
- description;
- input schema;
- existing owner;
- risk class;
- required evidence surface.

Skills must map to existing typed code paths. They are not arbitrary prompt fragments, shell commands, downloaded plugins, or a second agent runtime.

Prefer deterministic keyword/metadata discovery first. Embeddings or a skill database are not justified until scale proves simple discovery inadequate.

### Phase 3 — Mechanical CAD Intelligence

Goal: grow useful Mechanical capability in value order rather than attempting complete AutoCAD Mechanical coverage.

#### 3A. Core geometry

Prioritize common, composable features:

- shaft / stepped shaft;
- hole / counterbore / countersink;
- keyway / slot;
- pattern;
- fillet / chamfer.

Reuse `semantic_ir_lib` and `dxf_builder_lib`. Python orchestration must not become a second geometry truth engine.

#### 3B. Standard components

Add only when pilots need them:

- bolts, nuts, washers;
- bearings;
- keys;
- retaining elements.

Preference order is exact component reuse -> reviewed template -> parametric generation.

#### 3C. Drawing intelligence

Then expand into:

- dimensions and tolerances;
- GD&T;
- surface finish;
- center marks and hole callouts;
- section/detail views;
- BOM and hole tables.

Reuse existing dimension/contracts and publication composition owners. Do not create a separate annotation authority or Mechanical database.

### Phase 4 — Image / PDF -> Verified Mechanical CAD

Goal: close one end-to-end vertical slice using the existing R1-R8 candidate/evidence/repair backbone.

```text
source image/PDF
 -> ROI/source understanding + provenance
 -> exact base/component reuse where possible
 -> semantic interpretation + constraints/solve
 -> candidate CAD revision
 -> AutoCAD Mechanical only where required
 -> GLOBAL + REGION + deterministic evidence
 -> bounded repair through the existing repair path
 -> fresh verification
 -> verified candidate
```

The product target is not “looks similar.” Verification should combine the applicable geometry, dimensions, constraints, source provenance, native/editability, save/reopen, and visual evidence gates.

The architectural differentiator is:

```text
image -> reason -> solve -> draw -> read-back -> verify -> repair -> verify
```

rather than stopping at image -> draw.

### Phase 5 — Self-Improving Process / Production Hardening

Phase 5 begins during Phase 0 and runs continuously.

Every important solved incident should move toward:

```text
failure signature
 -> causal family
 -> reviewed probe/oracle
 -> regression eval
 -> safe repair or escalation boundary
```

This phase also accumulates production confidence through pilot-derived evals, currentness checks, evidence reuse, native/read-back gates and failure containment. It does not mean uncontrolled self-modifying production code.

## 5. Five rails across every phase

### Rail A — Currentness

Fresh GitHub evidence -> deterministic derived snapshot -> decision. Never the reverse.

### Rail B — Routing

- Web-capable reasoning/research/review: SOL/Web.
- Unpushed local/Windows/AutoCAD/COM/ROT/UI/NETLOAD/live File-IPC evidence: single Local Executor.
- Real owner decision, private secret, or irreversible approval: Human.

Preferred executor cannot override the required evidence surface.

### Rail C — Mission

Use bounded causal missions with goal, scope, accepted evidence, causal budget, acceptance oracle, cleanup and hard handoff conditions. Do not normalize command-by-command SOL↔Luna relay.

### Rail D — Evidence

Reuse exact satisfying evidence absent identity drift. Current exact-head evidence overrides stale/reused evidence. Conflicts fail closed.

### Rail E — Failure learning

Known failure -> known probe. Unknown failure -> root-cause work -> new reviewed family/eval if material.

## 6. CADmind-derived ideas accepted and rejected

CADmind is an architectural learning input, not a competing product blueprint.

Accepted patterns:

1. summary-first/query-oriented CAD reading;
2. `search_skills -> invoke_skill` instead of exposing a large raw schema surface;
3. image -> reasoning -> CAD execution -> snapshot/read-back loop.

CAD Agent extends the third pattern with provenance, semantic/constraint solving, candidate revisions, independent evidence, repair and verification gates.

Do not import as architecture merely because CADmind has it:

- a second MCP/AutoCAD transport;
- a second geometry/solver truth owner;
- a broad shared-skill dump;
- early embeddings/vector storage;
- a Mechanical shadow database;
- Electrical/Structural expansion before the Mechanical vertical slice proves value;
- any path that bypasses candidate/evidence/publication authority.

Any direct external-code reuse still requires the repository’s normal revision/license/reuse dossier.

## 7. Anti-bloat guardrails

The following are explicitly out by default:

- second control plane or authority store;
- second Local Executor, AutoCAD transport or dispatcher;
- arbitrary shell/PowerShell execution surface;
- new database/message bus/daemon merely for orchestration;
- second OCR/solver/DXF/geometry/repair/publisher owner;
- plugin marketplace or large raw tool catalogue;
- dashboard/project board that only mirrors Issue #291;
- auto-merge until governance explicitly reopens that decision.

A proposed architecture addition must answer: “Which existing owner was inspected, why can a thin adapter not solve it, and what concrete pilot requires this now?”

## 8. Relationship to existing backbone

R0-R8 remains useful delivery/history language only:

- Phase 0 -> governance/runtime/control-plane enforcement;
- Phase 1 -> source/current-CAD read surfaces;
- Phase 2 -> `agent_lib`/orchestration discovery and typed invocation;
- Phase 3 -> semantic IR, DXF, dimension/annotation owners;
- Phase 4 -> R1-R8 end-to-end candidate/evidence/repair/publication backbone;
- Phase 5 -> verification/failure/eval/production hardening.

No existing accepted owner is renamed or moved merely to fit the roadmap.

## 9. Priority order

Do not parallelize the whole roadmap. The preferred sequence is:

```text
stabilize Phase 0 foundation
 -> one thin Phase 1 query vertical slice
 -> minimal Phase 2 skill discovery/invocation
 -> one high-value Phase 3 Mechanical cluster
 -> one Phase 4 image-to-verified vertical slice
```

Phase 5 evidence/failure learning operates throughout.

This ordering intentionally favors 90% of the value with minimum architecture.

## 10. Current staged foundation at design time

Reference only; fresh-read before any mutable decision:

- `main`: `1263db2f54f505209ba6837b86181af8646b5a58`;
- PR #286: A-D verified/DRAFT-HOLD at `729f005b5c1cad6f88245bb134b524be644c4855`;
- PR #289: E1 hosted-green/DRAFT-HOLD at `06ca138a47e854798a22a6671adab81c3b50723b`;
- Issue #290: independent E1 review packet;
- Issue #131: sole mutable runtime authority; newest numbered control at design creation was SEQ292.

These are not roadmap-owned state and may change independently.

## 11. Program Definition of Done

A fresh SOL session, without Human recap, can:

1. determine current authority, main/PR state and first unsatisfied gate;
2. route work to SOL, local, AutoCAD or Human correctly;
3. compile/use bounded long-horizon missions;
4. reuse valid exact evidence instead of rerunning closed gates;
5. recognize known failures and select reviewed probes;
6. prepare N+1/N+2 and independent review packets without manual relay;
7. call AutoCAD/live only for boundaries that require real machine evidence.

The product can then:

8. read bounded CAD state with provenance;
9. discover and invoke typed skills;
10. perform useful Mechanical geometry/drawing operations through existing owners;
11. take an image/PDF through candidate creation, read-back, evidence, bounded repair and fresh verification to a verified Mechanical CAD candidate.

## 12. Next decision after spec approval

After the Owner reviews and approves this written spec, create one implementation plan focused first on **Phase 0 stabilization and Phase 1 query-façade vertical slice**. Do not create implementation plans for all six phases at once.
