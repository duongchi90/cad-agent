# Accelerated Reuse-First ChatGPT-to-Codex CAD Program Design

Status: PO-approved program design under Issue #68; governance/planning only.

Date: 2026-08-06

Exact planning base: `d00b24e4853d2bfa6bd94873d3014e37575e2718`.

## 1. Decision summary

CAD Agent will be developed as one evidence-driven system with four separate authorities:

1. The owner supplies engineering intent, approved inputs, measurements, fixtures, and final real-world authorization.
2. ChatGPT acts as PO, context/vision synthesizer, program controller, and independent integration reviewer.
3. Codex acts as the bounded coding and CAD-work planning agent through official OpenAI Codex interfaces.
4. CAD Agent and AutoCAD Mechanical remain the deterministic execution and evidence system.

The program will not build a replacement CAD engine or a custom production Codex transport. It will preserve and compose the accepted implementation already in the repository.

The target loop is:

```text
Owner evidence and engineering intent
  -> ChatGPT PO and vision/context synthesis
  -> closed, hash-bound vision handoff
  -> CAD Agent authority validation
  -> official OpenAI Codex SDK
  -> schema-bound drawing/repair plan
  -> CAD Agent contract and approval validation
  -> existing deterministic CAD engines
  -> existing AutoCAD .NET/File IPC boundary
  -> disposable candidate drawing
  -> fresh render, entity, measurement, geometry, and dimension evidence
  -> independent visual and engineering gates
  -> owner approval where required
  -> later verified promotion with backup and rollback
```

ChatGPT provides the vision and program intent. Codex converts approved intent into bounded technical work. Neither ChatGPT nor Codex becomes the source of CAD truth merely by producing text.

## 2. Chosen approach

Three approaches were considered.

### 2.1 Continue isolated slices without a program layer

This preserves local correctness but repeats planning, hides cross-slice dependencies, delays live-prerequisite discovery, and causes status drift after merges.

### 2.2 Replace the current project with a new integrated AI-CAD platform

This appears simpler conceptually but would duplicate OCR, solving, DXF generation, AutoCAD transport, manifests, repair, and evidence logic that already exists and has accepted tests.

### 2.3 Reuse-first program with official agent control — selected

The accepted CAD Agent packages remain the engine. New work is limited to missing adapters, registries, orchestration, evidence aggregation, and verified promotion. Official Codex interfaces provide worker control. Work is divided into waves and parallel lanes with disjoint write sets.

This option gives the fastest path to a useful product while retaining fail-closed engineering behavior.

## 3. Product objective

The product should accept one approved source package containing any supported combination of:

- drawing images;
- photographed or scanned PDF pages;
- an optional exact matching base CAD;
- engineering measurements;
- approved templates and setup definitions;
- explicit owner or engineer decisions.

It should produce native editable CAD candidates with provenance, dimensions, linked views, visual comparison, revision evidence, and a controlled route to a verified DWG.

The first complete product proof is not autonomous publication. It is one disposable end-to-end pilot in which:

- source identities and hashes are stable;
- critical dimensions are confirmed or explicitly unresolved;
- unchanged exact-base components are reused with provenance;
- new or changed components are generated through existing geometry boundaries;
- the candidate can be rendered and measured through AutoCAD Mechanical;
- independent evidence detects defects and confirms bounded improvement;
- no source or accepted drawing is overwritten;
- final promotion remains separately authorized.

## 4. Non-goals

This program does not authorize:

- a second OCR or dimension-recognition engine;
- a second semantic solver;
- a second DXF or DWG writer;
- a second AutoCAD dispatcher, transport, or mutation protocol;
- a second manifest, checkpoint, registry, revision, verdict, or publication truth store;
- unrestricted Codex file or AutoCAD mutation;
- ChatGPT or Codex self-approval of visual fidelity;
- automatic engineering approval;
- global deformation of a merely similar base drawing;
- production publication before live, private-data, backup, reopen, and rollback gates run.

## 5. Accepted baseline to reuse

The planning base already contains the following accepted or partially verified capabilities.

### 5.1 Repository and governance foundation

- Windows/Python 3.11 locked environment and bootstrap.
- Canonical `scripts/verify.ps1` offline and unavailable-state gates.
- R0 reuse inventory, compatibility baseline, architecture ratchet, and Reuse Declaration checks.
- Exact-base branch, allowlist, bounded-commit, PR, CI, and PO review conventions.
- `docs/STATUS.md`, `docs/HANDOFF.md`, `docs/ARCHITECTURE.md`, `docs/QUALITY.md`, `docs/AI_OPERATING_MODEL.md`, and `AGENTS.md` as repository-controlled context.

### 5.2 Existing CAD execution engine

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

- `primitive_ir_lib`: image/PDF rendering, geometry detection, OCR, table evidence, source traces, and calibration.
- `semantic_ir_lib`: parts, compounds, constraints, pruning, and solving.
- `agent_lib`: advisory proposals and separate approved application.
- `dxf_builder_lib`: native editable DXF generation, headless review, and confirmed repair.
- `mcp_integration_lib` and the .NET plugin: AutoCAD Mechanical File IPC, drawing gateway, read-only evidence, approved repair boundaries, and live harnesses.
- `cad_agent`: thin orchestration, manifests, checkpoints, resumability, evidence routing, and approval gates.

### 5.3 Drawing and dimension foundations

- Drawing Initialization and Setup contracts.
- Dimension Pilot contracts and solver adapter.
- Native editable `DIMENSION` generation and read-back.
- Safe `DRAFT_REFERENCE` classification for legacy image/PDF paths.

### 5.4 Visual Supervisor foundations

- VS-T0 closed contracts for dimension register, geometry comparison, visual review, repair plan, region verification, run manifest, and publication authorization.
- VS-T1 offline dimension observation.
- VS-T2 deterministic geometry comparison.
- VS-T3 read-only AutoCAD evidence export.

### 5.5 Official Codex foundation

- The approved Codex bridge decision prefers official Codex Python SDK, then App Server for missing SDK capabilities, then a bounded CLI fallback.
- S1 proved Windows/Python compatibility, package inspection, bundled runtime discovery, and disposable startup without enabling production turns.
- No production thread runner or drawing/repair bridge is integrated yet.

### 5.6 AutoCAD evidence and exact-base foundations

- S2C read-only AutoCAD-native layout capture.
- S3A exact-base inspection and extraction-plan contracts.
- S3B standalone live inspection routing and approved exact-base component extraction into new disposable candidates.
- Source Xref and accepted drawing immutability.
- Translation, rotation, and positive uniform scale only.
- `REUSED_FROM_BASE_CAD` provenance.

### 5.7 Source package foundations

- R1A SourceBundle offline contract.
- R1B run-manifest binding.
- Full source-fusion authority and byte-integrity lifecycle remain missing.

## 6. Authority model

### 6.1 Owner

The owner controls real engineering truth, approved private inputs, critical measurements, accepted fixtures, high-risk decisions, and real production use.

### 6.2 ChatGPT PO and vision synthesizer

ChatGPT may:

- inspect source images, PDFs, render evidence, measurements, and repository state;
- translate owner intent into component-, view-, region-, and dimension-scoped requirements;
- create the vision handoff and acceptance criteria;
- create Issues, plans, allowlists, stop conditions, and verification gates;
- independently review Codex work and GitHub evidence;
- authorize merges under standing owner authority when all approved gates are satisfied.

ChatGPT may not invent measurements, owner approvals, private evidence, AutoCAD live results, visual PASS, or publication authority.

### 6.3 Codex worker

Codex may:

- inspect the approved repository context;
- execute one bounded task at a time;
- use official Codex threads, turns, events, sandbox, and structured output;
- write tests and implementation within exact allowlists;
- produce schema-bound drawing or repair plans;
- run approved commands and create candidate artifacts in disposable locations.

Codex may not self-approve, bypass validators, alter source/accepted CAD, widen its scope, create duplicate authorities, or publish.

### 6.4 Visual Supervisor

The Visual Supervisor is independent of Codex and the repair executor. It evaluates evidence by region, view, and sheet and returns only its closed verdict contract. It does not edit CAD or authorize publication.

### 6.5 Deterministic CAD system

CAD Agent validators, existing engines, File IPC/.NET, AutoCAD read-back, hashes, manifests, and fresh evidence remain authoritative for executed behavior.

## 7. ChatGPT-to-Codex vision handoff

ChatGPT context must be materialized rather than assumed to transfer from a chat session.

The future handoff should bind at minimum:

```text
handoff schema version
program/run/request identity
source bundle and source hashes
approved exact-base identity and revision, if present
component/view/region scope
owner intent and engineering objective
confirmed, reference, derived, conflicting, and unresolved dimensions
protected datums, geometry, constraints, layers, blocks, and handles
source crops/render/evidence references
allowed operation classes
forbidden mutations
candidate/disposable roots
expected output contracts
acceptance criteria
required verification gates
approval references
expiry and stale-evidence rules
```

The handoff does not contain a visual PASS. It is validated before Codex receives it. Codex output is validated against a closed drawing-plan or repair-plan schema before any executor is called.

## 8. Official Codex integration boundary

The production priority is:

1. Official OpenAI Codex Python SDK.
2. Official Codex App Server only for required capabilities absent from the Python SDK.
3. Bounded official CLI JSON mode only as a compatibility fallback.
4. MCP only for experimental interoperability, not the primary closed-loop transport.

The official integration should own:

- authentication and session reuse;
- process/runtime lifecycle;
- thread start, resume, and fork;
- turn execution, progress events, steering, interrupt, and completion;
- sandbox and workspace access settings;
- command and file-change events;
- supported local image attachments;
- structured output binding;
- protocol framing and transport retries.

CAD Agent should own:

- CAD-specific prompts and evidence assembly;
- hash and authority validation;
- drawing-plan and repair-plan contracts;
- target resolution and protected geometry;
- AutoCAD execution requests;
- evidence invalidation after mutation;
- region/view/sheet state;
- best-candidate selection;
- promotion, backup, reopen, and rollback policy.

SDK/package versions must be pinned only after an execution-time compatibility matrix. The previous S1 version is evidence, not a permanent dependency choice.

## 9. Mandatory internal and external reuse dossier

Every future implementation Issue must include a reuse dossier before production code is authorized.

### 9.1 Internal inspection

Record the existing package, file, API, consumer, contract, test, and acceptance gate for the requested capability.

### 9.2 External search

Search official vendor samples and reputable public repositories. For each candidate, record:

- repository and exact revision/tag;
- license and attribution requirements;
- maintenance/activity state;
- supported Windows, Python, .NET, AutoCAD, and data formats;
- test coverage and security posture;
- dependency and deployment cost;
- API/architecture fit;
- expected benefit and benchmark method;
- migration and rollback path.

### 9.3 Classification

Each candidate must be classified as one of:

```text
REUSE_AS_IS
EXTEND_WITH_ADAPTER
EXTEND_WITH_TEST
PORT_BOUNDED_LOGIC
SPIKE_ONLY
REJECT
NEW_MISSING_CAPABILITY
```

`NEW_MISSING_CAPABILITY` is forbidden unless the dossier names the internal and external alternatives inspected and gives a concrete gap reason.

### 9.4 Selection order

Prefer:

1. Existing CAD Agent API.
2. Thin compatibility adapter.
3. Official vendor library or sample through an adapter.
4. Bounded attributed port with regression tests.
5. New implementation only when the prior options are proven insufficient.

No third-party installer, binary, macro, arbitrary AutoLISP, network service, or dependency enters the supported environment without a separate security, license, reproducibility, and benchmark decision.

## 10. Program workstreams

### P0 — Program governance and acceleration

Owns program docs, task templates, reuse dossiers, impact maps, CI evidence routing, and status/handoff freshness. It changes no CAD runtime.

### P1 — Live evidence readiness and closure

Prepares approved disposable fixtures, environment doctor output, AutoCAD HWND/session identity, File IPC directory, plugin state, path/hash configuration, and exact run commands for accepted S2C/S3B live gates.

This lane is operator-controlled and read-heavy. It does not modify runtime unless a separate defect Issue is opened from live evidence.

### P2 — Official vision handoff and Codex worker control

Adds the closed ChatGPT/Visual Supervisor handoff, official SDK thread/turn adapter, structured drawing/repair-plan output, event capture, interrupt/resume, disposable workspace tests, and fail-closed production seam.

It does not execute AutoCAD mutation in its first slice.

### P3 — Source integrity and fusion

Completes SourceBundle byte custody, source roles, page/region identity, distortion/quality observations, conflict records, and deterministic fusion inputs while reusing Primitive/Semantic IR and existing manifests.

### P4 — Base CAD adapter

Composes R1 source evidence with S3A/S3B exact-base inspection/extraction. It does not create a new extractor or AutoCAD transport.

### P5 — Component/View Registry

Adds one orchestration graph linking logical components, views, entity handles/blocks, dimensions, sources, layouts, revisions, conflicts, and approvals. It is not a CAD database or second manifest store.

### P6 — Candidate Revision Orchestrator

Reuses manifests and checkpoints to manage immutable candidates, supersession, stale-evidence invalidation, synchronization proposals, best-candidate restoration, and rollback metadata.

### P7 — Independent Visual Supervisor runtime

Composes VS-T1 dimensions, VS-T2 geometry comparison, S2C/VS-T3 native evidence, and a multimodal reviewer adapter. Critical findings cannot be averaged away. The reviewer does not mutate CAD.

### P8 — Codex repair planning and existing executor adapter

Converts validated visual/engineering findings into a protected, schema-bound repair plan. Existing repair executors apply only approved operations to a disposable candidate.

### P9 — Verified publisher

Composes existing backup, save/reopen, rerender, remeasurement, verification, atomic replacement, and rollback primitives. It remains last in the dependency order.

### P10 — Synthetic, disposable, and private pilots

Runs in order:

1. Synthetic contract and orchestration pilot.
2. Disposable AutoCAD Mechanical pilot.
3. Approved private real-drawing pilot.
4. Separately authorized production readiness review.

## 11. Dependency waves

### Wave 0 — current program planning

- Merge this docs-only program design and plan.
- Keep all runtime scopes locked.

### Wave 1 — three parallel lanes after fresh Issues

A. P2 official vision handoff and Codex worker-control slice.

B. P3 R1C source-integrity/fusion slice.

C. P1 operator-controlled S2C/S3B live-readiness and acceptance attempt.

These lanes may execute in parallel only with disjoint write sets. A live-discovered runtime defect creates a separate bounded Issue and may pause the affected lane without blocking unrelated offline work.

### Wave 2

- P4 Base CAD Adapter.
- P5 Component/View Registry design may begin after P3 contract stabilization; implementation begins after P4/P3 ownership is clear.

### Wave 3

- P6 Candidate Revision Orchestrator.
- P7 Visual Supervisor runtime adapters may be developed in disjoint offline/read-only slices.

### Wave 4

- P8 Codex repair planning and executor adapter.
- Integrated closed-loop disposable candidate flow.

### Wave 5

- P9 Verified Publisher.
- P10 pilots and release evidence.

## 12. Parallel execution policy

One writer owns every overlapping file set.

Safe parallel roles include:

- Worker A: one approved implementation slice.
- Worker B: read-only internal/external reuse research and benchmark preparation.
- Worker C: live environment and disposable-fixture preparation outside production code.
- Hosted CI: synthetic merge verification.
- ChatGPT PO: requirements, architecture, diff, evidence, and integration review.

The following remain single-writer shared boundaries:

- contract aggregators and shared schemas;
- `cad_agent` orchestration state and manifests;
- AutoCAD dispatcher/gateway files;
- component/view registry;
- revision orchestrator;
- canonical status/handoff docs;
- publisher and release policy.

## 13. Speed controls

To increase throughput without weakening evidence:

- Discover missing live/private prerequisites at task start, not Task 6 or final review.
- Open a draft checkpoint PR after the first coherent tested boundary when later commits are expected.
- Run the smallest focused tests during edits.
- Run the full required verifier before a bounded completion/checkpoint claim and on the final exact head.
- Let hosted CI review checkpoint commits while Codex continues disjoint later tasks on the same approved branch.
- Use bounded follow-up commits; do not rewrite reviewed history.
- Generate PR bodies and implementation records from one evidence packet to reduce transcription drift.
- Update `STATUS` and `HANDOFF` in a small integration/governance step after accepted merges rather than leaving stale claims.
- Separate unavailable live gates from offline progress so missing AutoCAD prerequisites do not block safe offline adapters.

## 14. Quality and safety gates

Every implementation slice requires:

- fresh exact base and branch;
- approved design/plan or bounded Issue specification;
- internal/external reuse dossier;
- exact create/modify/do-not-modify allowlist;
- tests first for changed behavior;
- focused tests and canonical verification;
- changed-file and architecture-ratchet audit;
- truthful `PASS`, `FAIL`, `SKIP`, and `NOT RUN` states;
- migration and rollback;
- independent PO review on the exact final head.

Additional gates apply to:

- OCR/calibration/geometry/constraints: approved private-data benchmark when affected.
- File IPC/AutoCAD/handles/render/extraction/repair: operator-controlled AutoCAD Mechanical gate when affected.
- external SDK/API/model: pinned compatibility and structured-output tests.
- mutation: disposable target, source/accepted immutability, backup, identity recheck, cleanup, and fresh post-mutation evidence.
- publication: run-scoped authorization, exact target, verified backup, reopen, rerender, remeasure, reverify, and rollback.

## 15. Error handling and stop rules

All unknown or stale authority states fail closed.

Codex and operators stop when:

- the branch/base/parent is wrong;
- a file outside the allowlist is required;
- a source or accepted drawing could be modified;
- a caller supplies server-owned observed evidence;
- source, candidate, target, or approval identity does not match;
- a required dimension, datum, component, or view is unresolved;
- an external license or provenance is unclear;
- a dependency cannot be pinned/reproduced;
- a second authority or transport would be created;
- a required live/private prerequisite is absent;
- fresh evidence contradicts the proposed operation.

Missing prerequisites are recorded as `SKIP` or `NOT RUN`; they do not become simulated PASS results.

## 16. Program metrics

The PO tracks:

- issue-to-first-checkpoint lead time;
- first-pass CI success rate;
- focused/full verifier duration;
- percentage of new behavior implemented by reuse or adapters;
- count of duplicate-authority findings;
- live-prerequisite readiness discovered at task start;
- defect escape from focused tests to hosted CI or live gate;
- stale-evidence rejection rate;
- private/live gates actually run versus NOT RUN;
- candidate improvement without critical-dimension regression;
- rollback success in disposable pilots.

Velocity is not measured by commit count. It is measured by accepted, reusable, evidence-backed capability per integration cycle.

## 17. Immediate program decision

After this program planning PR merges, the PO should create three separate Wave 1 Issues against the fresh integrated `main`:

1. Official vision handoff and Codex SDK worker-control contract/adapter.
2. R1C SourceBundle byte-integrity and deterministic source-fusion boundary.
3. S2C/S3B AutoCAD live-readiness and disposable acceptance operation.

Only the first two authorize repository implementation, each with disjoint write sets. The third is an operator/evidence task unless a live defect justifies a separate code Issue.

No S3C, registry, revision, repair, verdict, publication, or OCR expansion is implicitly authorized by this program document.

## 18. Rollback

This design changes no runtime. Before merge, delete the planning branch. After merge, revert the planning merge commit. Future runtime slices retain their own independent rollback plans.
