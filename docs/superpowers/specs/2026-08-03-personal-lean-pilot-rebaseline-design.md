# Personal Lean Pilot Rebaseline Design

- Date: 2026-08-03
- Owner: project owner
- Base SHA: `8c168ce411ed2948a5db99c043327f715916e74e`
- Status: draft written record; approved section-by-section in conversation and
  awaiting owner review of this file

## Context

The complete M0-M8 roadmap is a valid expansion target, but its multi-drawing,
multi-view, search, production-repair, and authoritative-release requirements
are disproportionate for the current personal project.

The original `master` branch already supplied the five implementation packages:
`primitive_ir_lib`, `semantic_ir_lib`, `agent_lib`, `dxf_builder_lib`, and
`mcp_integration_lib`. At this design base, all 96 files from those package trees
are still present on `main`; 58 have been extended and 38 remain byte-identical.
The current repository also contains the managed AutoCAD plugin, the thin
`cad_agent` orchestrator, Drawing Setup contracts, and private fidelity review
tools. The lean design therefore reuses existing boundaries instead of creating
a second pipeline.

## Decision

Adopt a **Personal Lean Pilot** as a strict subset of the full roadmap. The lean
pilot may report `PERSONAL_VERIFIED`, but it must never report `RELEASED` or
claim the full authoritative M0-M8 acceptance gate.

Deferred capabilities remain expansion points. They are not deleted, and lean
records keep versioned identifiers, hashes, and collection-shaped fields so a
future full-roadmap implementation can extend them without replacing the core
pipeline.

## Goals

- Produce one technically reviewable personal pilot DXF from approved input and
  configuration.
- Preserve the existing solver, DXF builder, review, repair-safety, File IPC,
  and managed .NET boundaries.
- Require fresh, hash-bound setup, dimension, measurement, region, and owner
  approval evidence before `PERSONAL_VERIFIED`.
- Reduce the remaining implementation and live-test burden by roughly 60-70
  percent compared with completing every full-roadmap acceptance criterion now.
- Keep an additive path from the lean pilot to the full M0-M8 design.

## Non-goals

- A ten-DWG standards corpus or automatic legacy drawing audit.
- Automatic similarity search or a SQLite knowledge base.
- Automatic view segmentation or cross-view datum inference.
- Multiple vehicle configurations or proof of domain completeness.
- Production drawing mutation, production save, or authoritative release.
- A second solver, builder, dispatcher, or image/PDF pipeline.

## Architectural boundaries

The lean flow is:

```text
approved input and personal configuration
  -> Setup Lite / SETUP_VERIFIED
  -> approved linear dimension and datum records
  -> existing semantic_ir_lib solver
  -> existing dxf_builder_lib native DXF generation
  -> existing headless review
  -> read-only disposable AutoCAD review
  -> fresh region and measurement evidence
  -> owner approval / PERSONAL_VERIFIED
```

Package ownership remains unchanged:

- `cad_agent` owns orchestration, manifests, evidence, and refusal behavior.
- `semantic_ir_lib` remains the only constraint-pruning and solving boundary.
- `dxf_builder_lib` remains the only headless DXF build/review/repair boundary.
- `mcp_integration_lib` and `autocad_plugin` remain the AutoCAD audit and review
  boundary.
- The current image/PDF path remains `DRAFT_REFERENCE`; it may propose evidence
  but cannot bypass approved dimensions, setup verification, or owner approval.

Pilot-specific values stay in the Drawing Definition, Drawing Profile, Domain
Pack, template manifest, and private evidence. No vehicle type, drawing name,
template path, or workstation path is hard-coded into a core package.

## Reduced M0-M8 scope

| Milestone | Reuse | Lean acceptance | Deferred full-roadmap work |
|---|---|---|---|
| M0 | Existing manifests, hashes, approvals, resume refusal, backup policy, and `scripts/verify.ps1` | Accept the verified safety foundation and add no parallel global state machine | Unified enterprise release vocabulary beyond the lean record |
| M1 | Existing managed .NET/File IPC health, dispatch, review, and disposable close | Accept the current read-only/disposable transport boundary | Generic measure/render/change-summary operation family not needed by the pilot |
| M2 | Drawing Setup contracts, validators, provenance builder, and CLI boundary | One approved DWT, one profile, one domain pack, and one disposable DWG produce `SETUP_VERIFIED` | Ten-DWG corpus, automatic candidate audit, and full legacy/new font matrix |
| M3 | Existing constraints, pruning, solver, cross-validation, and approval behavior | Approved linear dimensions, one explicit datum frame, attachment, residual/refusal evidence for one pilot view | General chain/baseline/ordinate coverage and broad datum inference |
| M4 | Existing DXF builder, native dimensions/components, headless review, and handle evidence | Deterministically build one view with the native entity types required by the pilot and measure it back | Generic business Operation Plan engine and broad render invalidation system |
| M5 | Existing semantic components, block attributes, and Mechanical BOM read-only evidence | Optional versioned JSON registry with exact IDs and hashes only | SQLite, feature extraction, similarity ranking, and automatic legacy search |
| M6 | Existing private region proposals, crops, overlays, approvals, and review queues | Owner-defined critical regions for one view using the existing hash-bound evidence pattern | Automatic segmentation, coverage inference, and cross-view mapping |
| M7 | Existing fidelity reconstruction, component repair, live review, backup, and rollback boundaries | One pilot configuration; repair is limited to staged/disposable DXF | Second configuration proof, domain completeness, and production repair |
| M8 | Existing promotion, checkpoints, review evidence, and stale-hash checks | All selected critical regions pass, dimensions measure back within tolerance, evidence is fresh, and the owner approves `PERSONAL_VERIFIED` | Authoritative release manifest, production save, full plot/global coverage gate |

## Execution gates

### Gate A: Setup Lite

- Complete the current M2 CLI boundary work.
- Audit exactly one disposable DWG created from the approved external DWT.
- Compare its setup snapshot with the approved profile and template hashes.
- Emit `SETUP_VERIFIED` only when there are no blockers.
- Do not audit a ten-DWG corpus in the lean profile.

### Gate B: Dimension Pilot

- Define the smallest versioned dimension/datum record needed for approved
  linear dimensions in one view.
- The pilot datum is explicit and owner-approved: one origin, one X-axis
  direction, and one Y-axis direction. The pilot does not infer this frame.
- Measurement tolerance in millimetres is a required positive, hash-bound pilot
  configuration value. There is no implicit default.
- Adapt that record to the existing constraints and solver; do not create a
  second solve model.
- Generate native editable DXF entities through `dxf_builder_lib`.
- Read the generated dimensions and critical geometry back and enforce the
  approved tolerance.

### Gate C: Personal Verification

- Reuse the existing region proposal/crop/overlay pattern with manually selected
  critical regions.
- Run headless review and one read-only disposable AutoCAD review.
- Bind the final source, setup, DXF, measurement, region, and review hashes.
- Require explicit owner approval before emitting `PERSONAL_VERIFIED`.
- Never save or mutate a production/customer drawing.

M5's full search subsystem is not an execution gate for the lean pilot.

## Personal verification record

`PERSONAL_VERIFIED` is represented by a versioned JSON evidence record rather
than by relabeling an existing full-roadmap release record. It contains at
least:

- `schema_version`, `status`, and a stable pilot/run identifier;
- source, Drawing Setup evidence, dimension/datum evidence, DXF, measurement,
  region evidence, and AutoCAD review SHA-256 values;
- the configured measurement tolerance;
- `blockers`, which must be an empty list for `PERSONAL_VERIFIED`;
- `verified_by` and a non-empty owner `approval_reference`.

Every referenced artifact is re-hashed when the record is evaluated. A missing,
changed, or inaccessible artifact refuses verification.

## State and refusal behavior

The lean product recognizes three outcome levels:

- `DRAFT_REFERENCE`: recognition or fidelity evidence that is not authoritative.
- `SETUP_VERIFIED`: the disposable drawing matches the approved setup plan.
- `PERSONAL_VERIFIED`: the lean pilot gates passed with fresh evidence and owner
  approval.

The run fails closed for at least these conditions:

- missing or mismatched source, template, profile, setup, DXF, or evidence hash;
- missing owner approval;
- unsupported dimension kind or ambiguous attachment;
- under-constrained, over-constrained, conflicting, or unacceptable solver result;
- measurement outside the approved tolerance;
- stale region/render/review evidence;
- wrong active drawing or unavailable AutoCAD prerequisite when a live gate is
  required;
- any request to promote the lean result to `RELEASED` or mutate production.

## Verification policy

- Add a focused failing regression test before each behavior change.
- Run focused tests after each bounded task.
- Run `scripts/verify.ps1` once when closing each of Gates A, B, and C rather
  than repeating the full suite for documentation-only microsteps.
- Run the private `real_data` benchmark only when calibration, OCR, geometry,
  line merging, pattern recognition, or constraints are changed.
- Run a disposable AutoCAD Mechanical gate at the end of Gate A and Gate C.
- Keep the pilot input, DWT, DWG, annotations, and generated artifacts outside
  Git and bind them by SHA-256.
- Preserve the full repository rule that `SKIP` and `NOT RUN` are never passes.

## Expansion path to the full roadmap

Expansion is additive:

1. one profile/template becomes a registry of profiles/templates;
2. exact JSON lookup gains a SQLite persistence and similarity adapter;
3. manual regions gain automatic segmentation while keeping the same region
   identifiers and evidence contracts;
4. one-view collections gain cross-view mappings and shared-datum checks;
5. one pilot configuration gains additional Domain Packs and a second
   configuration proof;
6. `PERSONAL_VERIFIED` evidence becomes an input to, not a substitute for, the
   full authoritative region register and release gate.

No lean artifact is silently relabeled as authoritative. Full M0-M8 acceptance
requires the deferred gates to run on a fresh candidate.

## Expected planning effect

The rebaseline removes the ten-DWG audit, full M5 search subsystem, automatic
segmentation, cross-view inference, multi-configuration proof, production
repair, and authoritative release automation from the current critical path.
It consolidates the remaining work into three gates and raises the planning
estimate from roughly 30 percent of the full roadmap to roughly 50-60 percent of
the lean pilot. These percentages are planning estimates, not verification
evidence.

## Design acceptance

This design is ready for implementation planning when the owner confirms that
this written record matches the approved conversation. Execution is decomposed
into one bounded plan per gate, in order: Gate A, Gate B, then Gate C. The first
plan must begin from fresh `main`, account for the open M2 CLI pull request, and
classify every task as reuse-as-is, extend-with-test, or new-missing-capability.
