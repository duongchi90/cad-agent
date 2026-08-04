# Reuse Integration Rebaseline Design

Status: proposed for user review after PR #30 / VS-T3 merge.

## 1. Purpose

This rebaseline defines how CAD Agent expands from its current working pipeline into a multi-source reconstruction and base-CAD transformation system without building a second CAD stack.

The primary product goals are:

1. Reconstruct editable CAD from photographed drawings, scanned pages, or PDFs.
2. Transform an approved original vehicle CAD using photographs and detail evidence from a modified vehicle.
3. Preserve the current usable pipeline while new capabilities are introduced behind adapters, feature flags, compatibility contracts, and reversible revisions.

The rebaseline is intentionally an integration design. It does not authorize implementation of VS-T4, VS-T5, a parallel OCR engine, a parallel CAD builder, or a second state store.

## 2. Approved architecture decision

The project adopts the wrapper-and-adapter approach.

Existing engines remain authoritative for their current responsibilities:

- `primitive_ir_lib`: recognition of lines, text, tables, dimensions, and calibration inputs;
- `semantic_ir_lib`: component meaning, relationships, constraints, and semantic interpretation;
- `agent_lib`: bounded proposals for ambiguous regions;
- `dxf_builder_lib`: editable DXF entities, native dimensions, blocks, and headless review;
- `mcp_integration_lib`: AutoCAD Mechanical access through the approved File IPC and .NET boundary;
- existing CAD repair APIs: execution of approved CAD changes;
- current `cad_agent` manifest, checkpoint, resume, hash, and artifact lifecycle: orchestration state.

The new architecture surrounds those engines with small integration components:

- `SourceFusionAdapter`;
- `BaseCadAdapter`;
- `ComponentRegistryAdapter`;
- `DimensionRegisterAdapter`;
- `VisualSupervisor`;
- `CodexRepairPlanner`;
- `RepairExecutorAdapter`;
- `RevisionOrchestrator`;
- `RevisionStoreAdapter`;
- `VerifiedPublisher`.

No adapter may become a replacement implementation of an existing engine.

## 3. Supported workflows

### 3.1 IMAGE_RECONSTRUCTION

Use when no suitable original CAD exists.

```text
images / photographed pages / PDF
  -> existing image normalization and Primitive IR
  -> Source Fusion
  -> Semantic IR
  -> component and dimension registers
  -> existing DXF/DWG builder
  -> AutoCAD evidence export
  -> Visual Supervisor review
  -> bounded repair loop
  -> candidate revision
```

Observed facts and AI assumptions remain separate. Geometry inferred from incomplete evidence must be marked `AI_INFERRED` and cannot be silently promoted to confirmed source truth.

### 3.2 BASE_CAD_TRANSFORMATION

Use when the correct original CAD for the vehicle is available.

```text
approved base CAD
+ overall photographs after modification
+ detail photographs / drawings
  -> read-only base reference
  -> identify preserved and changed components
  -> reuse approved original geometry
  -> reconstruct only changed components
  -> synchronize affected views and layouts
  -> candidate revision
```

The system must not stretch or freely deform an approximately similar vehicle CAD to fit photographs. Cabin, chassis, axles, wheels, and unchanged original geometry remain protected unless current evidence explicitly proves that they changed.

### 3.3 HYBRID_RECONSTRUCTION

Use when the original CAD is only partially reusable.

Only components with clear provenance may be reused. Missing or unsuitable areas are reconstructed through the image workflow. A near-match CAD must not be treated as an exact base.

## 4. Source authority and provenance

Authority is decided per component, per view, and per dimension. There is no single source that is globally authoritative for the whole drawing.

For unchanged original vehicle components, the default precedence is:

```text
approved exact base CAD
  -> CONFIRMED dimensions
  -> current photographs or detail evidence
  -> AI inference
```

For modified components, the default precedence is:

```text
CONFIRMED dimensions
  -> verified detail evidence
  -> overall modified-vehicle evidence
  -> geometric and structural relationships
  -> AI inference
```

Every derived or inferred entity must retain traceable provenance to its component, evidence, assumptions, revision, and approval state.

## 5. Source Fusion Adapter

`SourceFusionAdapter` accepts one source bundle containing any supported combination of:

- overall photographs;
- detail photographs;
- photographed drawing pages;
- multi-page PDFs;
- exact original CAD;
- engineer decisions and approvals.

It does not perform replacement OCR or geometry extraction. It calls existing recognition APIs and binds their outputs to stable page, crop, view, component, and evidence identities.

Minimum output responsibilities:

- identify page and evidence roles;
- preserve source hashes;
- group evidence by view and component;
- expose ambiguity and conflicts instead of resolving them silently;
- allow repeatable resume without reprocessing unchanged hash-bound sources.

## 6. Base CAD Adapter

`BaseCadAdapter` reuses the approved AutoCAD/DXF reading boundary instead of introducing another parser.

Responsibilities:

- attach or open base CAD through an approved read-only strategy;
- obtain entity, block, layer, dimension, handle, and layout mappings through existing APIs;
- extract only approved reusable components;
- record source drawing hash and entity provenance;
- mark preserved content `REUSED_FROM_BASE_CAD`;
- protect preserved components from unapproved edits.

It must not own a new CAD parser, renderer, transport, or repair executor.

## 7. Component Registry

The component registry is a logical index over existing CAD and semantic artifacts.

Each component record must be able to identify:

- stable `component_id` and component type;
- source and provenance state;
- participating 2D views;
- entity handles or stable entity references;
- relevant blocks and layers;
- related dimensions and constraints;
- layouts in which it appears;
- current revision and approval status;
- conflict and inference status.

One component may span multiple views, sections, details, and layouts. A change to the component must declare every affected projection.

## 8. Dimension and Evidence Register

The existing Dimension Register contract is extended rather than replaced.

Supported dimension states are:

- `OBSERVED`;
- `UNRESOLVED`;
- `CONFLICT`;
- `CONFIRMED`;
- `AI_INFERRED`.

An OCR number is only `OBSERVED`. It may become `CONFIRMED` only when:

1. an independent evidence source confirms it; or
2. an engineer provides a traceable approval.

Two occurrences on the same source page are not independent sources.

A dimension record must retain:

- observed value and unit;
- source crop and source hash;
- technical role;
- component and view scope;
- independent confirmation or engineer approval;
- conflict state;
- affected CAD references;
- revision history.

AI may use an unresolved value to build a draft only when the result remains clearly marked `AI_INFERRED` or unresolved.

## 9. Visual Supervisor boundary

`VisualSupervisor` is an independent evaluator. It does not modify CAD.

Responsibilities:

- compare source evidence with deterministic CAD renders;
- review bounded regions, views, and layouts;
- detect missing detail, incorrect shape, wrong arrangement, or inconsistent projections;
- check cross-view consistency;
- produce structured findings bound to component, region, evidence, and revision;
- classify the severity and review requirement.

VS-T3 remains the approved read-only AutoCAD evidence exporter. Visual Supervisor must consume its bounded render, entity-map, and measurement artifacts rather than adding another AutoCAD capture path.

Visual Supervisor does not own PASS-to-publish authority. Final promotion remains a CAD Agent policy decision after all required gates.

## 10. Codex Repair Planner boundary

`CodexRepairPlanner` converts reviewed findings into a closed, structured Repair Plan.

A Repair Plan must declare:

- affected component;
- affected entities or stable references;
- requested operations;
- dimensions and constraints involved;
- affected views and layouts;
- `LOW`, `MEDIUM`, or `HIGH` change level;
- evidence and provenance basis;
- required approval gate;
- rollback identity.

Codex may propose operations but cannot:

- directly mutate DWG;
- declare final PASS;
- approve its own high-risk plan;
- publish a revision;
- bypass the existing repair API.

`RepairExecutorAdapter` translates an approved plan into calls to the current repair API. It must not contain a second repair engine.

## 11. Change levels and repair-loop policy

### LOW

Examples: presentation-only linework, hatch, text placement, and layout alignment that do not change technical meaning.

- maximum autonomous repair rounds: 3;
- may auto-accept after all automated checks pass;
- escalation occurs if the change affects technical geometry or creates regression.

### MEDIUM

Examples: local geometry or one bounded detail/view.

- maximum autonomous repair rounds: 5;
- requires automated checks and quick engineer review before promotion;
- escalation occurs when the change spreads to another view, dimension, or layout.

### HIGH

Examples: driving dimensions, structure, chassis, cabin, axle relationship, installation position, or changes affecting multiple projections/layouts.

- AI creates a plan only;
- engineer approval is required before mutation;
- affected views and dimensions must be revalidated after execution.

All repair loops stop early when:

- two consecutive rounds show no improvement;
- the same defect repeats;
- a regression appears;
- a new conflict is introduced;
- the plan exceeds its declared component or view scope.

## 12. Conflict Packages

Conflicts are grouped by component or technical area instead of shown as hundreds of isolated alerts.

A Conflict Package contains:

- component identity;
- relevant source crops;
- base CAD evidence when present;
- OCR values and geometric measurements;
- conflicting sources;
- affected views, layouts, and dimensions;
- AI recommendation and assumptions;
- engineer decisions and audit trail.

Engineer approval may be applied to the package while retaining dimension-level editing inside it.

## 13. Revision and publication model

The current DWG is never overwritten by an unverified operation.

```text
current revision
  -> candidate revision
  -> approved repair execution
  -> entity and dimension checks
  -> cross-view and layout checks
  -> VS-T3 evidence export
  -> Visual Supervisor evaluation
  -> required engineer approvals
  -> promote or rollback
```

`VerifiedPublisher` extends the existing backup, reopen, hash, and rollback mechanisms.

A candidate may become current only when:

- required automated checks pass;
- no blocking conflict remains;
- `HIGH`, `AI_INFERRED`, and previously conflicting areas have required approval;
- the saved file reopens and matches expected identity and hashes;
- the previous revision remains available for rollback.

Unchanged `REUSED_FROM_BASE_CAD` content may be auto-accepted when its provenance and hashes remain unchanged.

## 14. One manifest and one artifact lifecycle

Visual Supervisor must not introduce a separate state system.

The current manifest/checkpoint lifecycle is extended with optional fields or linked artifacts for:

- `source_bundle`;
- `base_cad_reference`;
- `component_registry`;
- `dimension_register`;
- `candidate_revision`;
- `autocad_evidence`;
- `visual_review`;
- `repair_plan`;
- `approval_packages`;
- `publication`.

Legacy `run`, `resume`, `run-pdf`, DXF generation, review, and repair flows must continue to work on old fixtures and artifacts.

New readers must read old artifact versions. New writers may emit versioned extensions. Migration creates a new artifact and preserves the old source hash; it must not rewrite old artifacts in place.

## 15. Feature flags and compatibility modes

New workflows are opt-in during transition:

```text
--workflow image-reconstruction
--workflow base-cad-transformation
--workflow hybrid-reconstruction
```

The legacy workflow remains available. Failure in a new workflow must not corrupt legacy checkpoints, artifacts, or current CAD files.

The new workflow may become the default only after both required pilots pass and the user explicitly approves the change.

## 16. Reuse Integration Audit gate

No VS-T4, VS-T5, or downstream implementation begins until a reuse audit is completed.

The audit must inventory current packages, APIs, CLIs, contracts, tests, and live boundaries. Every required capability receives one classification:

- `REUSE_AS_IS`;
- `EXTEND_WITH_ADAPTER`;
- `EXTEND_WITH_TEST`;
- `REFACTOR_BEHIND_COMPATIBILITY_LAYER`;
- `NEW_MISSING_CAPABILITY`;
- `DEPRECATED_AFTER_MIGRATION`.

Expected default decisions include:

| Capability | Existing owner | Default decision |
|---|---|---|
| Image/text/table/dimension recognition | `primitive_ir_lib` | `REUSE_AS_IS` |
| Semantic components and constraints | `semantic_ir_lib` | `EXTEND_WITH_ADAPTER` |
| Ambiguity proposals | `agent_lib` | `EXTEND_WITH_ADAPTER` |
| Editable DXF and native dimensions | `dxf_builder_lib` | `REUSE_AS_IS` |
| Headless CAD review | existing review APIs | `REUSE_AS_IS` |
| AutoCAD Mechanical and File IPC | `mcp_integration_lib` + .NET plugin | `EXTEND_WITH_TEST` |
| AutoCAD evidence export | VS-T3 | `REUSE_AS_IS` |
| CAD repair execution | existing repair API | `EXTEND_WITH_ADAPTER` |
| Manifest/checkpoint/resume | current `cad_agent` | `EXTEND_WITH_ADAPTER` |
| Independent visual review | not yet implemented | `NEW_MISSING_CAPABILITY` |
| Codex SDK transport | official SDK boundary | `NEW_MISSING_CAPABILITY` |
| Revision publish | current backup/rollback base | `EXTEND_WITH_ADAPTER` |

The audit produces a versioned reuse inventory before implementation tasks are created.

## 17. Mandatory Reuse Declaration for every task

Every implementation task must state:

```text
Existing capability inspected:
Existing API reused:
Adapter required:
New capability genuinely missing:
Files allowed to change:
Files forbidden to duplicate:
Migration and rollback path:
```

A task is not ready for implementation without this declaration.

A PR must be rejected when it:

- adds a second OCR or dimension engine;
- adds another DXF/DWG builder;
- adds another AutoCAD transport or dispatcher;
- adds a parallel repair executor;
- adds another manifest/checkpoint store;
- copies old algorithms into a new package instead of calling them;
- introduces a duplicate contract for the same concept without compatibility and migration rules;
- allows Visual Supervisor or Codex to mutate or publish directly.

## 18. Architecture tests

The rebaseline requires architecture tests in addition to functional tests.

Minimum invariants:

- `cad_agent` does not absorb OCR or CAD geometry algorithms;
- Visual Supervisor has no DWG mutation path;
- Codex Planner has no PASS or publish authority;
- repair execution always crosses `RepairExecutorAdapter` into the existing repair API;
- AutoCAD access stays behind the approved File IPC/.NET boundary;
- candidate revisions never overwrite the current revision;
- base-CAD provenance survives extraction and reuse;
- legacy commands continue to pass existing fixtures;
- new readers accept old artifacts;
- new-workflow failure leaves legacy state and files intact.

## 19. Pilot gates

### Pilot 1: synthetic and disposable

Must demonstrate:

- read-only base CAD reference;
- component extraction;
- AI-created component with explicit provenance;
- multiple synchronized views/layouts;
- structured Repair Plan;
- candidate revision;
- VS-T3 evidence and independent review;
- promotion and rollback.

### Pilot 2: approved real project

Must use a representative vehicle-conversion package containing:

- overall modified-vehicle evidence;
- exact original-vehicle CAD;
- detail evidence;
- one editable multi-layout DWG;
- native editable entities;
- component-level engineer approval;
- visible `AI_INFERRED` provenance;
- preserved previous revision.

The new workflow is successful only when it:

- produces at least the current output level;
- reduces manual effort;
- preserves editability;
- preserves provenance;
- does not increase technical errors or cross-view conflicts;
- proves rollback in practice.

## 20. Delivery order after this spec

After user approval of this committed specification:

1. write the Reuse Integration Audit implementation plan;
2. inventory existing assets and produce the reuse inventory;
3. define adapter contracts and architecture tests;
4. implement only the smallest missing integration boundaries;
5. run the synthetic/disposable pilot;
6. run the approved real-project pilot;
7. request explicit approval before changing defaults or beginning broader VS-T4/VS-T5 work.

No implementation plan or downstream code is authorized merely by opening the specification PR.

## 21. Acceptance criteria for the specification

This design is accepted when the user confirms that it:

- reflects the approved wrapper-and-adapter architecture;
- protects the currently working CAD Agent pipeline;
- prevents duplicated OCR, solver, DXF, AutoCAD, repair, and state systems;
- preserves clear source and AI-inference provenance;
- enforces engineer gates for high-risk changes;
- keeps revisions reversible;
- requires a reuse audit and pilot proof before broader implementation.
