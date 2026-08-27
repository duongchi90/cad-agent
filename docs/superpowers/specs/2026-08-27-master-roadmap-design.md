# CAD Agent Master Roadmap Design

Date: 2026-08-27
Status: OWNER APPROVED
Roadmap issue: #291
Docs-only branch: `governance/master-roadmap-design`
Authority effect: NONE

## 1. Purpose

CAD Agent uses one durable product roadmap, not parallel operating-model, CADmind, Mechanical, and R0-R8 roadmaps.

The roadmap has two jobs only:

1. define the product direction from reliable AI work to verified Mechanical CAD; and
2. define cross-cutting invariants that keep delivery efficient and fail-closed.

It is not runtime authority and not a delivery-state database. Mutable state lives in Issue #131 plus the active delivery Issue/PR/CI/reviewer evidence. The roadmap may point to active delivery owners but must not copy current SHA, baton, CONTROL_SEQ, CI verdicts, terminal details, or first-unsatisfied-gate.

Historical R0-R8 terminology remains valid implementation/history vocabulary under the existing package and contract boundaries.

## 2. North star

> One real Mechanical image/PDF -> AI reads the exact current CAD/source state -> discovers the right typed capability -> creates or repairs real CAD -> reads it back -> proves geometry/editability/evidence -> verified candidate.

```text
Image / PDF / DWG / user intent
 -> provenance-bound source/CAD read
 -> typed capability discovery
 -> semantic reasoning / solve / candidate mutation
 -> AutoCAD Mechanical only when machine evidence is genuinely required
 -> read-back + deterministic / visual evidence
 -> bounded reviewed repair if required
 -> fresh verification
 -> VERIFIED MECHANICAL CAD CANDIDATE
```

The roadmap optimizes for an early real vertical slice, not maximum subsystem coverage.

## 3. Execution strategy — vertical slice driven

Do not complete a broad Mechanical platform before testing product value.

Preferred sequence:

```text
Phase 0 minimum closure
 -> Phase 1 thin query façade
 -> Phase 2 thin skill façade
 -> Phase 3 only 2-3 Mechanical capabilities required by the pilot
 -> Phase 4 real vertical slice as early as possible
 -> pilot failures/evidence drive the next Phase 1/2/3 expansion
```

Phase 5 learning/hardening runs continuously.

Phase 0 is not allowed to become an endless governance program. After its minimum exit oracle is satisfied, it becomes a maintenance rail. New workforce/enforcement slices require a concrete observed failure or missing acceptance boundary; they are not created merely because more optimization is possible.

## 4. Five invariant rails

The rails are invariants across all product phases, not five additional products.

### Rail A — Currentness

Fresh canonical GitHub evidence precedes mutable decisions. Chat memory, roadmap text, historical STATUS/HANDOFF material, or copied terminal text is never current authority.

A derived snapshot may deterministically represent already-fresh evidence but may not fetch, mint, or supersede authority.

### Rail B — Routing

- Web-capable research, architecture, root-cause, hosted evidence and review stay with SOL/Web.
- Unpushed local state, Windows toolchain, AutoCAD/COM/ROT/UI/NETLOAD/live File-IPC evidence goes to the single Local Executor.
- Real owner decisions, private secrets and irreversible approvals stay with the Human Owner.

Preferred executor never overrides the required evidence surface.

### Rail C — Mission

Prefer one bounded causal mission containing goal, scope, accepted evidence, causal/expensive/live budgets, acceptance oracle, cleanup and hard-handoff conditions over command-by-command SOL↔Luna relay.

Mission material never implies merge, publication, Human approval or arbitrary shell authority.

### Rail D — Evidence

Reuse exact satisfying PASS evidence absent relevant head/artifact/contract identity drift. Fresh exact-head evidence overrides reused older-head evidence. Conflicts fail closed. `SKIP` and `NOT_RUN` never satisfy PASS.

### Rail E — Failure learning

A materially solved failure should become reviewed executable knowledge: signature/family, probe/oracle, regression test/eval, and safe repair/escalation boundary.

Known failure -> known probe. Unknown failure -> root-cause work -> reviewed family/eval if material.

## 5. Phase 0 — Reliable AI Workforce / minimum closure

### Goal

Make the existing SOL/Web + independent reviewer + hosted CI + single Local Executor flow reliable enough that workforce/governance work stops being the main project.

### Reuse

Use the existing staged currentness, routing, mission, evidence, failure-family and sealed typed Local Executor contracts. Do not create a second control plane, state store, runner, transport or scheduler.

### Minimum closure

Phase 0 reaches minimum closure when a fresh SOL session can, without Human recap:

- recover current authority and active delivery owner from fresh GitHub;
- route Web/local/Human work correctly;
- reuse valid accepted evidence and identify the next delivery gate;
- recognize known execution failures and select reviewed probes;
- issue/consume bounded missions through typed execution rather than arbitrary command text;
- prepare successor/review packets without manual Human relay;
- satisfy the independent review/acceptance gates required by the currently staged Phase 0 implementation.

### Maintenance rule

After minimum closure, do not create E2/E3/E4 merely to make the process more elegant. Reopen Phase 0 implementation only when a concrete failure, security boundary, or repeated delivery cost proves a missing capability.

### Exit oracle

`ACCEPTED` when the minimum closure above is evidenced on the accepted implementation path. Thereafter workforce changes are failure-driven maintenance.

## 6. Phase 1 — Thin provenance-bound CAD read façade

### Goal

Let AI ask bounded questions about the exact drawing/candidate revision required by the real pilot without whole-drawing context dumps.

The most important property is not query richness but identity:

> Every result must prove exactly which drawing/candidate/state/version was read.

### V1 capability

V1 is deliberately closed:

- type filter;
- layer filter;
- component identity filter when an existing owner exposes it;
- bounded region;
- whitelist field projection;
- count/group over approved fields;
- bounded result count;
- exact drawing/candidate/state/version identity returned with every result.

No arbitrary expressions, joins, SQL-like syntax, user-supplied predicates, executable callbacks or unbounded results.

### Architecture

Implement as a thin read-only façade over existing drawing gateways, provenance/currentness contracts and entity read surfaces. The façade may normalize and project existing typed results; it must not create a shadow DWG database or become a second CAD truth owner.

Explicitly out for V1:

- SQLite/drawing mirror;
- vector database/embeddings;
- generic query language;
- new AutoCAD transport;
- duplicate entity model;
- cache that can be mistaken for current drawing authority.

### Exit oracle

`VERTICAL_SLICE_PASS` when the selected real Phase 4 pilot can retrieve the small exact information set it needs from the bound revision, with stale-state rejection, field/result bounds and provenance/currentness evidence.

## 7. Phase 2 — Thin skill discovery façade

### Goal

Let the model discover the right existing typed capability instead of memorizing a broad raw tool/schema surface.

### Authority boundary

The registry is only:

```text
metadata -> capability_id -> existing typed owner
```

It is not an executor, authority layer, plugin runtime, script store or new tool implementation.

A skill entry contains only the metadata needed for discovery/validation:

- capability id;
- description/tags;
- input schema reference;
- existing owner;
- risk class;
- required evidence surface.

`invoke_skill` resolves the capability id to an existing reviewed typed owner and validates parameters/risk/evidence requirements. Registry content may not contain Python/PowerShell/LISP/shell script bodies or arbitrary argument vectors.

Start with deterministic lexical/tag discovery. Embeddings/vector search are not justified until real scale demonstrates that simple deterministic discovery is inadequate.

### Exit oracle

`VERTICAL_SLICE_PASS` when the pilot intent deterministically resolves to the required existing typed capability and invokes the existing owner through its reviewed contract without introducing arbitrary execution or a new authority owner.

## 8. Phase 3 — Minimum Mechanical capability for the pilot

### Goal

Implement only the 2-3 Mechanical capabilities the first real vertical slice requires. Expand later from observed pilot gaps.

A likely first cluster for a deliberately simple shaft drawing is:

- shaft / stepped shaft;
- keyway;
- the exact hole family present in the selected source.

Reuse `semantic_ir_lib`, `dxf_builder_lib`, existing dimension/contracts and the existing AutoCAD boundary. Orchestration must not become a second solver, geometry/DXF engine, annotation authority or Mechanical database.

Preference for reusable standard content remains:

```text
exact existing component -> reviewed template -> bounded parametric generation
```

A new Mechanical capability needs evidence from the pilot, a failure/acceptance gap, or a concrete user use case. Catalog completeness is not a requirement.

### Exit oracle

`VERTICAL_SLICE_PASS` when the selected pilot's minimum feature set is represented through existing semantic/geometry owners and survives candidate generation/read-back with the expected editability semantics.

## 9. Phase 4 — Real image/PDF -> verified Mechanical CAD vertical slice

### Goal

Prove useful product value as early as possible with one deliberately narrow real Mechanical source.

Example first pilot: a simple shaft drawing using only the minimum supported shaft/keyway/hole features.

```text
real image/PDF
 -> source/ROI understanding + provenance
 -> exact base/component reuse where possible
 -> Phase 1 bounded current-state read
 -> Phase 2 typed capability discovery
 -> Phase 3 minimum Mechanical capability
 -> candidate revision
 -> AutoCAD Mechanical only where genuinely required
 -> read-back
 -> GLOBAL + REGION + deterministic evidence
 -> bounded existing repair path if required
 -> fresh verification
```

The target is not `image -> draw` but:

```text
image -> reason -> solve -> draw -> read-back -> verify -> repair -> verify
```

Verification uses the applicable existing geometry, dimension, constraint, provenance, native/editability, save/reopen and visual evidence gates. It must never call visual similarity alone a product PASS.

### Exit oracle

`ACCEPTED` when one real Mechanical source produces a provenance-bound editable candidate whose applicable approved acceptance gates pass on the accepted candidate identity.

## 10. Phase 5 — Reviewed learning and production hardening

Phase 5 runs continuously and contains two separate knowledge classes. There is no automatic authority transfer between them.

### 10.1 Development Failure Memory

Examples:

- PID/foreground ownership;
- FILEDIA RPC behavior;
- File-IPC bootstrap/readiness;
- controller races;
- terminal/artifact emission.

Flow:

```text
engineering failure
 -> signature/family
 -> reviewed probe/oracle
 -> regression test/eval
 -> safe repair/escalation boundary
```

This improves development/execution reliability only. It does not automatically change CAD Agent runtime/product behavior.

### 10.2 Product Learning

Examples:

- source patterns that reliably imply a shaft/keyway feature;
- a typed capability that performs well on a defined pilot class;
- a reviewed repair that improves a product-level constraint failure.

Product observations become runtime behavior only through the normal design, TDD, evidence, review and authority gates. Product learning is measured by pilot/eval evidence, not uncontrolled online self-modification.

### Exit oracle

`HARDENING` when materially repeated development failures are caught by reviewed probes/evals and product improvements are promoted only through explicit reviewed changes with measurable pilot evidence.

## 11. Phase status vocabulary

Do not use percentages or progress bars.

Where a delivery Issue needs a phase status, use only:

```text
NOT_STARTED
FOUNDATION_EXISTS
ACTIVE
VERTICAL_SLICE_PASS
ACCEPTED
HARDENING
```

The active delivery Issue/PR owns its current capability and next unsatisfied gate. The Master Roadmap stores only the phase definition, exit oracle and pointer to the active delivery owner.

## 12. CADmind-derived ideas retained

CADmind is an architectural learning input, not a competing product blueprint.

Retain only the patterns that fit existing CAD Agent owners:

1. summary-first/query-oriented CAD reading;
2. skill discovery followed by typed capability invocation instead of a large raw schema surface;
3. image -> reasoning -> CAD execution -> snapshot/read-back loop.

CAD Agent deliberately extends the third pattern with source provenance, semantic/constraint solving, candidate revisions, independent evidence, bounded repair and verification.

Do not import merely because another product has it:

- second MCP/AutoCAD transport;
- second geometry/solver truth owner;
- broad shared-skill dump;
- early embedding/vector stack;
- Mechanical shadow database;
- Electrical/Structural scope before Mechanical vertical value is proven;
- paths bypassing candidate/evidence/publication authority.

Any direct external-code reuse still requires the repository's normal revision/license/reuse dossier.

## 13. Anti-bloat guardrails

Default rule:

> **Existing owner + thin adapter beats new subsystem.**

A proposed new architecture component must answer:

1. which existing owner/API was inspected;
2. why a thin adapter cannot solve the concrete gap;
3. which real pilot/failure requires it now;
4. what its authority boundary and rollback are.

Out by default:

- second control plane/currentness/authority store;
- second Local Executor/AutoCAD transport/dispatcher;
- arbitrary shell/PowerShell execution surface;
- orchestration database/message bus/daemon;
- second OCR/solver/DXF/geometry/repair/publisher owner;
- plugin marketplace or broad raw-tool catalogue;
- project board/dashboard that only mirrors Issue #291;
- auto-merge until governance explicitly reopens that decision.

## 14. Relationship to existing backbone

R0-R8 remains implementation/history vocabulary, not a competing roadmap. Existing accepted package/contract boundaries remain authoritative for their domains.

New delivery issues link to the relevant Master Roadmap phase while reusing existing R0-R8/backbone terminology where technically useful. No accepted owner is renamed or moved merely to fit this roadmap.

## 15. Roadmap state rule

> **Issue/PR is where current delivery state lives. Master Roadmap must never become a second state database.**

When a phase becomes active, update only its active delivery link in Issue #291. Do not copy runtime SHA, CONTROL_SEQ, baton, CI verdict, reviewer status, terminal details or first-unsatisfied-gate into the roadmap/spec.

## 16. Program Definition of Done

A fresh SOL session, without Human recap, can:

1. determine current authority and first delivery gate from fresh canonical evidence;
2. route work correctly to SOL, local/AutoCAD or Human;
3. use bounded long-horizon missions rather than routine manual relay;
4. reuse valid evidence instead of rerunning closed gates;
5. recognize known development failures and select reviewed probes;
6. prepare successor/review packets without Human copy-paste relay;
7. reserve expensive/live AutoCAD epochs for genuine machine boundaries.

The product can then:

8. read the exact current CAD/source state through a bounded provenance-bound façade;
9. discover and invoke typed existing capabilities without a new authority/executor layer;
10. perform only the Mechanical operations required by the evidence-driven pilot;
11. take a real image/PDF through candidate creation, read-back, evidence, bounded repair and fresh verification to an editable verified Mechanical CAD candidate.