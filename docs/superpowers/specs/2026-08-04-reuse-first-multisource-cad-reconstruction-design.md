# Reuse-First Multisource CAD Reconstruction Design

Status: proposed design for PO review after VS-T3 merge.

Date: 2026-08-04

Base: `main` at VS-T3 merge commit `d3d4eeaa1927ea98d813956c20bd353a355bbe29`.

This document rebaselines the CAD Agent roadmap after VS-T3. It preserves the
working product as the execution engine and adds multisource reconstruction,
independent visual supervision, controlled revisioning, and human approval
through adapters and compatibility layers. It does not authorize
implementation by itself.

## 1. Decision summary

The product will use a reuse-first wrapper architecture.

The existing packages remain authoritative for their current responsibilities:

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

The thin `cad_agent` package continues to own orchestration, manifests,
checkpoints, resumability, evidence routing, and approval gates. New features
must not create a second OCR engine, semantic solver, DXF builder, AutoCAD
transport, repair executor, manifest store, or publication path.

The new layer adds only the capabilities that are genuinely missing:

```text
Source Fusion Adapter
Base CAD Adapter
Component/View Registry
Dimension Evidence Register integration
Visual Supervisor
Codex Repair Planner
Revision Orchestrator
Verified Publisher
```

The governing product principle is:

> The existing CAD Agent remains the engine. The Visual Supervisor becomes the
> independent eyes and controller around that engine.

## 2. Product objective

The first release must support two primary workflows and one mixed workflow.

### 2.1 Image reconstruction

Use when there is no exact reusable base CAD.

```text
Images or photographed/scanned PDF pages
  -> existing Primitive IR and Semantic IR pipeline
  -> multisource evidence fusion
  -> inferred missing construction where necessary
  -> native editable CAD entities
  -> candidate DWG revision with multiple Layouts
  -> independent visual and structural verification
```

This remains a draft-oriented path until its dimensions and critical technical
assumptions satisfy the required evidence and approval gates.

### 2.2 Exact-base CAD transformation

Use when the exact original vehicle CAD is available.

```text
Exact original vehicle CAD
+ overall post-conversion photographs
+ photographed detail and section pages
  -> read-only base Xref
  -> approved extraction of unchanged components
  -> reconstruction of changed/new components
  -> synchronized linked 2D views
  -> candidate DWG revision
  -> independent verification and selective engineer approval
```

The base CAD may be used only when the vehicle/model and critical base
dimensions match the target. The system must not globally stretch, scale, or
warp a merely similar vehicle drawing to force a fit.

### 2.3 Hybrid reconstruction

Use when an exact base CAD supplies only part of the required target or some
components cannot be reused directly. Reusable components follow the exact-base
rules; the remaining components follow the image-reconstruction rules.

## 3. Scope and non-goals

### 3.1 In scope for the first rebaseline release

- one source bundle containing images, photographed/scanned PDF pages, an
  optional exact base CAD, and engineer decisions;
- reconstruction of an overall arrangement and detailed views into one DWG;
- native editable AutoCAD entities;
- one canonical Model Space with multiple Layouts;
- component-level and view-level provenance;
- independent visual review by region;
- candidate revisions, selective approval, promotion, and rollback;
- compatibility with the current `run`, `resume`, `run-pdf`, `resume-pdf`,
  DXF, headless review, and AutoCAD Mechanical review/repair workflows.

### 3.2 Explicitly deferred

- indexing or retrieval from a library of previous converted CAD files;
- replacing the current five implementation packages;
- a 3D-first reconstruction model;
- autonomous final engineering approval;
- automatic publication of critical or inferred geometry without the required
  human gate;
- global deformation of a similar base CAD;
- a second AutoCAD dispatcher or transport;
- unrestricted self-editing by Codex.

The design must leave an extension seam for a future prior-drawing library, but
no library work belongs in the first implementation plan.

## 4. Existing capability ownership

The current package boundaries remain authoritative.

### 4.1 `primitive_ir_lib`

Reused for image/PDF rendering, geometry detection, OCR/text extraction,
tables, source traces, confidence, and calibration. New orchestration may
supply richer source roles and page metadata, but it must call existing
recognition APIs rather than duplicate them in `cad_agent`.

### 4.2 `semantic_ir_lib`

Reused for parts, compounds, constraints, pruning, and solver-ready geometry.
New component/view metadata may be adapted into or around existing semantic
artifacts, but solved geometry must continue through the existing solver
boundary.

### 4.3 `agent_lib`

Reused as an advisory, non-mutating proposal layer. A report and its application
remain separate actions. Multisource ambiguity and synchronization proposals
must preserve this separation.

### 4.4 `dxf_builder_lib`

Reused for native entity generation, semantic layers/components, native
DIMENSION output, headless read-back, headless review, and confirmed repair.
No alternate DXF writer is allowed.

### 4.5 `mcp_integration_lib` and the AutoCAD .NET plugin

Reused for the File IPC boundary, AutoCAD Mechanical review/repair, read-only
setup/evidence operations, backup, reopen, and live safety checks. New AutoCAD
operations must extend the existing closed dispatcher and gateway rather than
introduce a parallel transport.

### 4.6 `cad_agent`

Continues to own run identity, source hashing, manifests, checkpoints,
resumability, evidence lifecycle, approval routing, and CLI composition. It
must not absorb recognition algorithms or CAD geometry algorithms.

## 5. Mandatory Reuse Integration Audit

Before any VS-T4, VS-T5, repair-loop, revision, or publisher implementation,
the coding agent must produce a repository-wide reuse inventory.

Each required capability must be classified as exactly one of:

```text
REUSE_AS_IS
EXTEND_WITH_ADAPTER
EXTEND_WITH_TEST
REFACTOR_BEHIND_COMPATIBILITY_LAYER
NEW_MISSING_CAPABILITY
DEPRECATED_AFTER_MIGRATION
```

The inventory must include:

```text
Capability
Current package/file/API
Current consumer
Classification
Compatibility adapter, if any
Tests and acceptance gate
Migration and rollback path
```

Default classification expectations are:

| Capability | Existing owner | Default decision |
|---|---|---|
| Image/PDF recognition, OCR, calibration | `primitive_ir_lib` | `REUSE_AS_IS` |
| Semantic parts and constraints | `semantic_ir_lib` | `EXTEND_WITH_ADAPTER` |
| Ambiguity proposals and separate apply | `agent_lib` | `EXTEND_WITH_ADAPTER` |
| Native DXF/entity generation | `dxf_builder_lib` | `REUSE_AS_IS` |
| Headless review and repair | `dxf_builder_lib` | `REUSE_AS_IS` |
| AutoCAD File IPC and .NET boundary | `mcp_integration_lib` | `EXTEND_WITH_TEST` |
| Existing AutoCAD repair | current repair APIs | `EXTEND_WITH_ADAPTER` |
| Run manifests/checkpoints/resume | `cad_agent` | `EXTEND_WITH_ADAPTER` |
| Drawing Setup and Dimension Pilot | current contracts/adapters | `REUSE_AS_IS` or `EXTEND_WITH_ADAPTER` |
| VS-T1/VS-T2/VS-T3 evidence | current VS modules | `REUSE_AS_IS` after contract audit |
| Source bundle and evidence fusion | none complete | `NEW_MISSING_CAPABILITY` |
| Exact-base component extraction registry | none complete | `NEW_MISSING_CAPABILITY` |
| Linked component/view graph | none complete | `NEW_MISSING_CAPABILITY` |
| Candidate revision synchronization | none complete | `NEW_MISSING_CAPABILITY` |
| Independent visual verdict runtime | none complete | `NEW_MISSING_CAPABILITY` |
| Verified promotion integration | partial backup/rollback exists | `EXTEND_WITH_ADAPTER` |

A capability may be marked `NEW_MISSING_CAPABILITY` only after the audit names
what was inspected and why the existing API cannot satisfy the requirement.

## 6. Reuse Declaration required for every task

Every implementation issue and PR must contain:

```text
Existing capability inspected:
Existing API reused:
Adapter required:
New capability genuinely missing:
Files allowed to change:
Files forbidden to duplicate:
Compatibility behavior:
Migration and rollback path:
```

A PR is rejected when it introduces any of the following without an approved
architecture amendment:

- a second OCR or dimension-recognition engine;
- a second semantic solver or geometry model for the same concept;
- a second DXF builder;
- a second AutoCAD transport/dispatcher;
- a second repair executor;
- a second manifest, checkpoint, or revision truth store;
- copied legacy logic instead of an adapter call;
- duplicate contracts for the same concept without a versioned migration path;
- visual PASS or publication authority inside Codex or the repair executor.

## 7. Source Bundle and evidence roles

`SourceBundle` is the new orchestration-level description of all evidence for
one reconstruction run. It does not replace Primitive IR or Semantic IR.

A source bundle may contain:

```text
overall post-conversion image/page
detail image/page
section image/page
material/table image/page
exact original CAD
engineer measurement
engineer approval/decision
```

Each item receives a stable source ID, byte hash, page/region identity, source
role, capture metadata, and distortion/quality observations.

Source roles are evaluated per component, view, and dimension. No photographed
page is globally authoritative merely because it is an overall drawing.

### 7.1 Default source priority for unchanged original components

```text
exact matching base CAD
  -> confirmed dimensions
  -> image/detail evidence
  -> derived relationships
  -> AI inference
```

### 7.2 Default source priority for converted/new components

```text
confirmed dimensions
  -> verified detail/section evidence
  -> overall arrangement evidence
  -> geometric/structural relationships
  -> AI inference
```

These are defaults, not unconditional overrides. A conflict is recorded and
resolved per component or region.

## 8. Exact base CAD policy

The original CAD is attached as a read-only Xref and remains the canonical
source for unchanged geometry.

A base CAD is eligible only when:

- vehicle/model identity matches;
- critical wheelbase, track, chassis, cabin, axle, and other controlling base
  dimensions match the target evidence;
- no global deformation is needed to fit the target.

Approved components may be copied into the working model. Every copied
component records:

```text
source file and SHA-256
original handle/layer/block
extraction timestamp
applied local transform
logical component ID
source revision
provenance = REUSED_FROM_BASE_CAD
```

Copied components are frozen to the source hash used at extraction. If the Xref
changes later, the system warns which components are affected. It does not
automatically overwrite them. The engineer chooses to retain the frozen copy
or create a new extraction revision.

The original CAD may optionally appear in a Layout marked:

```text
XE NGUYEN THUY - THAM CHIEU
```

It remains internal/reference material by default.

## 9. Component/View Registry

The registry links CAD entities, logical components, views, layouts,
dimensions, source evidence, and approval state. It is an orchestration
registry, not a replacement CAD database.

A logical component contains at least:

```text
component_id
component_type
component_revision
provenance class
source evidence IDs
view IDs
entity handles/block references
dimension IDs
layout IDs
approval status
conflict status
```

Examples include cabin, chassis, axle/wheels, cargo-body frame, side gates,
canopy frame, bumper, mudguards, and repeated uprights.

### 9.1 Entity/block granularity

- repeated or technical assemblies are blocks/components;
- unique geometry remains ordinary native entities;
- dimensions and annotations stay outside geometry blocks and remain associated
  with the logical component/entity/view;
- AI-generated output uses native editable entities such as LINE, ARC, CIRCLE,
  LWPOLYLINE, SPLINE, HATCH, TEXT, MTEXT, DIMENSION, BLOCK, and INSERT;
- raster evidence is underlay/evidence only, never final geometry.

### 9.2 Multi-view model

Each 2D view is represented as a separate view block linked to one logical
component and shared parameters, revision, and provenance. The first release is
not 3D-first.

A change in one view does not silently mutate other views. The system produces
a synchronization proposal containing:

```text
proposed source view
source evidence and confidence
shared parameter changes
impacted views/entities/dimensions/layouts
expected before/after geometry
new or resolved conflicts
change severity
```

AI evaluates all evidence and proposes the source view. The engineer approves
the source view and the component cluster before a HIGH-impact synchronization
is applied.

## 10. Dimension authority and independent confirmation

An OCR value is an observation, not an authoritative driving dimension.

Dimension states include:

```text
OBSERVED
UNRESOLVED
CONFLICT
CONFIRMED
AI_INFERRED
```

A numeric dimension becomes `CONFIRMED` only when it is supported by one
independent second source or by an auditable engineer confirmation.

The same value repeated on the same page remains one source. Independent
confirmation may come from:

- another independent page/source;
- the exact base CAD;
- a separately derived dimension chain;
- a real measurement;
- an engineer confirmation.

Engineer confirmation records who, when, why, the source crop/hash, the prior
value, and the accepted value.

Dimensions are reviewed in component/region clusters, but the engineer may
modify or reject individual values.

## 11. Inference and provenance

The system must continue reconstructing useful draft geometry when evidence is
incomplete. It may infer occluded shapes, symmetry, repeated patterns,
relationships between views/sections, and plausible local construction.

Every entity or component carries one primary provenance class:

```text
OBSERVED
REUSED_FROM_BASE_CAD
DERIVED
AI_INFERRED
```

An inference record contains:

```text
inference_id
component_id
source evidence IDs and hashes
assumption
confidence
created entities
impacted views/layouts/dimensions
approval status
```

Inference may complete a candidate draft. It may not silently become source
truth. Critical manufacturing, installation, structural, regulatory, or
controlling dimensions derived through inference require engineer review
before promotion.

## 12. DWG, Layout, Xref, and revision model

The target output is one DWG.

### 12.1 Canonical organization

- Model Space contains canonical component/view geometry;
- Layouts present the overall arrangement and detail sheets;
- shared geometry is referenced through viewports/blocks rather than copied as
  unrelated geometry;
- dimensions and annotations remain native and associative where supported;
- every relevant entity, view, and Layout remains linked to provenance.

### 12.2 Candidate revision policy

The system never applies a synchronization or repair directly over the current
accepted DWG.

```text
current revision
  -> create candidate revision
  -> apply approved change
  -> structural/entity checks
  -> dimension association checks
  -> cross-view consistency checks
  -> AutoCAD evidence export
  -> visual review
  -> selective engineer approval
  -> promote or rollback
```

The previous revision remains intact. Promotion changes which revision is
current; it does not erase history.

A copied component remains bound to the base-CAD source revision used at the
time of extraction.

## 13. Visual evidence and visual truth

The design uses two evidence forms with different authority.

### 13.1 Deterministic vector projection

VS-T3 deterministic projection is reused for entity mapping, region identity,
offline diagnostics, geometric correlation, and fail-closed structural
inspection.

It is not automatically the sole visual truth for final sheet appearance.

### 13.2 AutoCAD-native visual evidence

Where final fidelity depends on actual AutoCAD display/plot behavior, the
Visual Supervisor uses read-only AutoCAD-native render/plot evidence through
the approved File IPC boundary. Unsupported or unverifiable rendering fails
closed rather than being replaced by a misleading placeholder.

The final review may combine:

```text
deterministic entity/geometry evidence
+ AutoCAD-native render/plot evidence
+ source image crops
+ measurement and provenance records
```

Only the `visual_review` artifact carries a visual verdict.

## 14. Visual Supervisor, Codex, and repair authority

### 14.1 Visual Supervisor

The Visual Supervisor is independent of the repair implementer. It:

- compares source and CAD evidence by region;
- checks missing/extra geometry, shape, position, layout, and cross-view
  consistency;
- emits findings and a verdict;
- never directly edits the DWG.

### 14.2 Codex Repair Planner

The official Codex Python SDK is the preferred integration once the approved
Windows compatibility spike proves it usable. App Server is considered only
when the SDK lacks a required capability. Bounded `codex exec --json` is the
fallback. A custom production transport is prohibited.

Codex receives bounded evidence and produces a closed Repair or Transformation
Plan. It may name components, entities, operations, affected views/layouts,
expected outcomes, and severity. It may not issue visual PASS, approve its own
repair, promote a revision, or publish.

### 14.3 Repair execution

A `RepairExecutorAdapter` translates an approved plan into existing repair APIs.
It must not implement another repair engine.

Every applied change produces a new candidate revision and new evidence.

## 15. Change severity and human gates

Every change is classified as:

### LOW

Presentation-only changes such as line appearance, hatch, text, and Layout
alignment that do not alter technical meaning.

- AI may iterate up to 3 rounds;
- automatic acceptance is allowed only after all automatic gates pass and the
  change is proven non-technical.

### MEDIUM

Local component geometry or one-view detail changes.

- AI may iterate up to 5 rounds;
- the engineer receives a compact review before promotion.

### HIGH

Driving dimensions, structure, mounting positions, chassis/cabin/axle effects,
or changes spanning multiple views/Layouts.

- AI creates a plan only;
- engineer approval is required before application;
- a second approval is required when the candidate result contains unresolved
  inference or conflict.

Every plan records classification, justification, affected component/view/
Layout, and required gate.

## 16. Controlled iteration and stop conditions

Automatic loops stop early when:

- two consecutive iterations show no meaningful improvement;
- a regression is detected;
- the same repair signature repeats;
- a new dimension conflict appears;
- evidence becomes stale;
- an authority or provenance check fails.

The existing Visual Supervisor state machine remains the governing lifecycle:

```text
CREATED
-> SOURCE_NORMALIZED
-> DIMENSIONS_OBSERVED
-> DIMENSION_GATE_READY
-> DRAFT_GENERATED
-> REGIONS_CHECKING
-> REPAIRING
-> LOCAL_VISUAL_VERIFIED
-> GLOBAL_VERIFIED
-> PUBLISHING
-> POST_SAVE_VERIFYING
-> PUBLISHED
```

Terminal or human-stop states include:

```text
NEEDS_HUMAN
DIMENSION_CONFLICT
NO_VISUAL_IMPROVEMENT
EXECUTION_FAILED
PUBLISH_REFUSED
ROLLED_BACK
```

## 17. Promotion policy

A candidate revision becomes current only when:

- all automatic structural, contract, freshness, and visual gates pass;
- no required blocker remains unresolved;
- HIGH changes are approved;
- `AI_INFERRED` and current/previous `CONFLICT` clusters are approved;
- critical dimension changes are approved;
- the saved file reopens with the expected hash, entities, and evidence;
- rollback remains available.

Unchanged `REUSED_FROM_BASE_CAD` geometry may be accepted automatically.
`DERIVED` geometry may be accepted automatically only when its constraints and
confirmed dimensions prove it and no higher-risk rule applies.

## 18. Unified manifest and compatibility

No separate Visual Supervisor truth store is allowed. The current run manifest
and checkpoint lifecycle is extended with versioned optional fields for:

```text
source_bundle
base_cad_reference
component_registry
dimension_register
candidate_revision
autocad_evidence
visual_review
repair_plan
approval_packages
publication
```

Readers must continue to accept older artifacts with safe defaults. Writers use
new versions. Migration creates new artifacts bound to the old hash; it does
not mutate historical artifacts in place.

The new workflows are opt-in during migration, for example:

```text
--workflow image-reconstruction
--workflow base-cad-transformation
--workflow hybrid-reconstruction
```

Legacy workflows remain available. Failure in a new workflow must not damage a
legacy run, checkpoint, source file, accepted DWG, or backup.

Internal APIs may change behind adapters, but the practical compatibility
contract preserves the commands, workflows, and important outputs already used
by the operator.

## 19. Architecture tests

The implementation plan must include architecture tests proving at least:

- `cad_agent` contains no new OCR or CAD geometry algorithm;
- the Visual Supervisor cannot mutate DWG;
- Codex cannot carry PASS or publish authority;
- repair plans must pass through the existing repair executor boundary;
- AutoCAD access remains inside the approved .NET/File IPC boundary;
- current revisions cannot be overwritten by candidate work;
- base-CAD provenance survives extraction and revisioning;
- legacy CLI fixtures still run;
- old artifacts remain readable;
- failures in new workflows preserve legacy checkpoints and files;
- no second manifest/checkpoint/revision truth store exists;
- conflicting mapped datum handles fail closed;
- deterministic projection is not promoted as final visual truth when an
  AutoCAD-native render is required.

## 20. Pilot and acceptance strategy

### 20.1 Synthetic/disposable pilot

The first pilot proves:

- read-only exact-base Xref;
- component extraction with provenance;
- AI/native component creation;
- linked 2D views and multiple Layouts;
- candidate revision creation;
- Repair Plan routing through existing APIs;
- visual evidence and verdict separation;
- promotion and rollback.

### 20.2 Real engineering-document pilot

The second pilot uses one real multisource set containing:

- photographed overall post-conversion drawing;
- exact original vehicle CAD;
- photographed detail/section pages;
- one editable DWG with multiple Layouts;
- native components and dimensions;
- component-cluster approvals;
- explicit `AI_INFERRED` provenance;
- intact prior revision and rollback.

The rebaseline release is successful only when it:

- preserves at least the output capability of the legacy path;
- reduces manual reconstruction effort;
- preserves or improves editability;
- does not lose source/provenance evidence;
- does not increase cross-view or technical inconsistencies;
- demonstrates rollback;
- does not require a duplicate CAD pipeline.

## 21. Sequencing rule

The sequencing after VS-T3 is:

```text
VS-T3 merged
-> Reuse Integration Audit
-> this design reviewed and merged
-> detailed implementation plan
-> architecture/compatibility gates
-> bounded compatibility spikes
-> source/component/revision adapters
-> Visual Supervisor and repair integration
-> synthetic pilot
-> real pilot
```

VS-T4/VS-T5 work from the old rollout must not start unchanged. Their useful
requirements are retained, but tasks must be reissued from the new plan with a
Reuse Declaration and mapped existing APIs.

M2 Drawing Initialization remains an authoritative product path and must not be
removed or bypassed. The rebaseline integrates with it rather than replacing
it.

## 22. Design acceptance

This design is accepted only when the PO confirms that it matches the approved
product intent. After acceptance and merge, the next artifact is a detailed
implementation plan. No production code or runtime behavior is authorized by
this document alone.
