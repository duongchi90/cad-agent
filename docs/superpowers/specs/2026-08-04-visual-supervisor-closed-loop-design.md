# Visual Supervisor Closed-Loop Design

Date: 2026-08-04
Status: approved in product discussion; pending repository review before implementation planning
Branch: `docs/visual-supervisor-design`

## 1. Purpose

The current CAD Agent can render, inspect, and repair drawings, but Codex still has too much responsibility for judging whether its own visual result matches the source. In practice this produces false-positive completion claims: the source image and the current CAD drawing can be visibly different while the coding agent reports that the result is acceptable.

This design separates the roles:

- an independent multimodal Visual Supervisor is the visual reviewer and layout/shape reasoner;
- a deterministic geometry comparator measures image and contour differences;
- Codex remains the implementation and repair-planning agent;
- AutoCAD Mechanical 2027 remains the authoritative geometry executor and measurement source;
- an orchestrator controls the review/repair loop and prevents Codex from self-approving;
- a verified publisher may automatically save the production DWG only after every required gate passes.

The initial supported source types are:

1. scanned or photographed drawing images;
2. rendered pages from technical PDF drawings.

The first implementation verifies semantic regions, then complete views, then the whole sheet. It does not rely on one whole-page similarity score.

## 2. Product decisions already approved

The following decisions are fixed for this design:

1. Source input supports both images/scans and PDF pages.
2. Verification runs in this order:
   - semantic region;
   - complete view;
   - complete sheet.
3. The Visual Supervisor normally produces a repair intent rather than raw Model Space coordinates.
4. Coordinates or control points may be proposed only when the source and CAD evidence are aligned through verified datums or geometry mappings.
5. Completion requires visual, geometric, dimensional, and engineering verification. A high average similarity score cannot hide one failed critical region.
6. The system may automatically publish the target DWG after all gates pass, using a run-scoped authorization, verified backup, reopen verification, and automatic rollback.
7. When technical evidence is ambiguous or conflicting, the run stops in `NEEDS_HUMAN`.
8. When only visual improvement stalls, the run restores the best verified candidate, does not overwrite the target, and stops.
9. Every detected source dimension is reported to Codex, but only confirmed `DRIVING` dimensions may control authoritative geometry. `REFERENCE` and `DERIVED` dimensions are verification inputs. Unresolved critical dimensions block the affected scope.

## 3. Relationship to the current architecture

This feature extends the current pipeline and must not create a second CAD pipeline, solver, dispatcher, or mutation system.

Existing architecture remains authoritative:

```text
Image/PDF
  -> primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
  -> AutoCAD Mechanical 2027 through the existing .NET/File IPC boundary
```

The new closed loop is inserted after source interpretation and around the existing render/review/repair boundaries:

```text
Reference source
  -> reference normalization
  -> dimension observation
  -> view/region mapping
  -> draft generation
  -> AutoCAD evidence export
  -> deterministic geometry comparison
  -> independent visual review
  -> Codex repair plan
  -> existing controlled executor
  -> new render and measurement evidence
  -> repeat until verified or stopped
```

The feature depends on stable contracts from the current roadmap:

- M2: Drawing Initialization and `SETUP_VERIFIED`;
- M3: Dimension, Datum, Constraint, and solved model contracts;
- M4: deterministic operation plan, render, measurement, and affected-region invalidation;
- M6: source/CAD region mapping and coverage;
- M7/M8: domain repair, global verification, and release behavior.

A disposable-DWG MVP may be implemented before all release milestones are complete, but it must not be promoted as an authoritative production path until its dependencies and release gates are integrated.

## 4. Non-goals

The first version does not:

- train a new foundation vision model;
- allow a language model to freely operate AutoCAD through mouse coordinates;
- infer authoritative millimetre coordinates directly from pixels;
- replace native AutoCAD dimensions with text that only looks like a dimension;
- permit Codex to assign visual `PASS`;
- allow a single similarity score to determine completion;
- silently choose between conflicting technical interpretations;
- publish when any critical evidence is stale, unresolved, or failed;
- commit private source drawings, generated customer DWGs, screenshots, or API credentials to Git.

## 5. High-level architecture

```text
PDF / scanned image
        |
        v
Reference Ingest and Normalizer
        |
        +--> Dimension Observer
        |
        +--> View and Region Mapper
        |
        v
Reference Evidence Package
        |
        v
Existing CAD generation path
        |
        v
AutoCAD Evidence Exporter
        |
        +--> render evidence
        +--> entity evidence
        +--> dimension measurements
        +--> mutation provenance
        |
        v
Deterministic Geometry Comparator
        |
        v
Visual Supervisor API Adapter
        |
        v
Visual Review Report
        |
        v
Codex Repair Planner
        |
        v
Validated Repair Plan
        |
        v
Existing AutoCAD executor
        |
        +-----------------------------+
        |                             |
        +--> render and measure again-+
```

The orchestrator owns state transitions, iteration limits, best-candidate selection, evidence freshness, stop conditions, and publication eligibility.

## 6. Component boundaries

### 6.1 Reference ingest and normalization

Responsibilities:

- hash and register every source file;
- render PDF pages at controlled DPI;
- normalize scanned or photographed pages;
- preserve original evidence unchanged;
- create separate geometry and annotation representations;
- record every transformation and its parameters.

Image normalization may include:

- crop detection;
- rotation correction;
- limited perspective correction for photographs;
- background cleanup;
- contrast normalization;
- line-width normalization;
- noise removal.

Normalization must not use free-form warping that could hide real geometric differences.

Required outputs per page:

```text
page-original.png
page-normalized.png
page-geometry.png
page-annotation.png
reference-package.json
```

### 6.2 Dimension Observer

The Dimension Observer detects and reports all dimension clusters visible in the source. It combines OCR, line/arrow/extension-line detection, view context, and multimodal reasoning.

For every dimension candidate it attempts to determine:

- display text;
- numeric value and unit;
- dimension kind;
- tolerance or upper/lower limits;
- source view;
- extension geometry;
- attachment candidates;
- semantic `from_ref` and `to_ref`;
- role: `DRIVING`, `REFERENCE`, `DERIVED`, `AMBIGUOUS`, or `CONFLICT`;
- confidence and status.

A numeric OCR result without valid attachments is `UNRESOLVED`.

Minimum supported dimension forms for the first complete release:

- horizontal, vertical, aligned, and angular dimensions;
- radius and diameter;
- baseline, chain, and ordinate dimensions;
- overall length, width, height, wheelbase, and overhangs;
- tolerances such as `+-`, upper/lower limits, and technical symbols;
- repeated-hole notation such as `4x diameter`;
- leader-attached technical values.

The Dimension Observer produces a coverage report. It must never claim that every dimension was read unless every detected cluster has a recorded disposition.

### 6.3 View and Region Mapper

Each page is divided into views such as:

- `SIDE`;
- `TOP`;
- `FRONT`;
- `REAR`;
- sections;
- details;
- title block;
- tables.

Each drawing view is then divided in two parallel ways.

Semantic regions identify meaningful components, for example:

- cabin;
- front wheel;
- chassis;
- rear wheel;
- cargo body;
- mounted equipment;
- front and rear overhang;
- annotation clusters.

A coverage grid spans the complete view. It proves that no area was skipped merely because it was not recognized semantically.

Critical regions include:

- regions with driving dimensions;
- installation and attachment regions;
- modified design regions;
- shared datums;
- reused standard components;
- low-confidence source regions;
- any region that has previously failed.

### 6.4 AutoCAD Evidence Exporter

The existing AutoCAD .NET/File IPC integration gains deterministic, read-only evidence operations before it gains any new mutation operation.

Required evidence capabilities:

1. render a view or region with a fixed Model Space bounding box and pixel size;
2. select controlled layer sets for geometry and annotation renders;
3. export relevant entities with stable semantic identity where available;
4. export entity geometry needed by repair planning;
5. measure dimensions and datum relationships in Model Space;
6. bind every result to drawing hash, operation/mutation hash, viewport parameters, and timestamp.

Evidence examples:

```text
cad-render.png
cad-outline.png
entities.json
measurements.json
render-manifest.json
```

A render produced before the latest affected mutation is `STALE` and cannot support a pass.

### 6.5 Deterministic Geometry Comparator

The comparator measures observable differences before a model is asked for visual judgment.

Alignment priority:

1. approved datums;
2. confirmed driving dimensions;
3. stable CAD component/entity anchors;
4. high-confidence visual features.

Allowed transformations for comparison are controlled translation, small rotation, uniform scale, and source-photograph perspective correction. Free-form deformation is prohibited.

The comparator may compute:

- silhouette intersection over union;
- normalized Chamfer distance;
- normalized percentile Hausdorff distance;
- centroid offsets;
- width and height ratio errors;
- missing and extra edge ratios;
- connected-component differences;
- line orientation and slope differences;
- local curvature-profile differences;
- feature presence and topology checks.

The comparator does not decide the repair and does not issue the final visual verdict.

### 6.6 Visual Supervisor

The Visual Supervisor is an independent multimodal model call. It must not reuse Codex's self-evaluation as evidence.

For each review it receives only the information required for the current scope:

- source original crop;
- source outline;
- latest CAD render;
- latest CAD outline;
- side-by-side image;
- aligned overlay;
- difference masks;
- comparator metrics;
- confirmed dimensions and protected engineering constraints;
- recent repair history for the region.

It evaluates in this order:

1. mandatory feature presence;
2. topology;
3. relative position;
4. proportion;
5. contour and curve shape;
6. missing or extra details;
7. whether the requested visual change conflicts with protected technical constraints.

Its only top-level verdicts are:

- `PASS`;
- `FAIL`;
- `NEEDS_HUMAN`.

It returns a validated structured report. Free-form acceptance text is not a valid result.

### 6.7 Codex Repair Planner

Codex consumes:

- the validated Visual Review;
- the Dimension Register;
- the current entity map;
- measurement evidence;
- allowed business operations;
- preserved datums and constraints.

Codex produces a Repair Plan. It may select entities, components, and approved operations. It may write or update implementation code when a missing capability is required.

Codex may not:

- assign visual `PASS`;
- change a driving value to improve pixel similarity;
- ignore unresolved critical dimensions;
- map pixels directly to Model Space without verified calibration/alignment;
- delete constraints merely because the shape looks different;
- publish or authorize publication.

Initial approved repair operations should be business-level operations such as:

- move or align a component;
- replace a polyline segment;
- adjust an arc or spline control region;
- place a missing approved feature;
- remove an extra feature;
- replace with an approved block;
- create or repair a native AutoCAD dimension.

Primitive `draw_line`/`draw_arc` interfaces are internal executor details, not the main language-model interface.

### 6.8 Closed-loop Orchestrator

The orchestrator owns the run state and all iteration decisions.

Region lifecycle:

```text
PENDING
  -> RENDERED
  -> ALIGNED
  -> COMPARED
  -> VISUAL_REVIEWED
  -> REPAIR_PLANNED
  -> MUTATED
  -> STALE
  -> RENDERED again
```

Terminal region states:

- `VERIFIED`;
- `NEEDS_HUMAN`;
- `ROLLED_BACK_TO_BEST`;
- `FAILED_EXECUTION`.

The orchestrator records all candidates and selects the best candidate by the following strict priority:

1. no engineering violation;
2. no missing mandatory feature;
3. fewer critical and major findings;
4. better deterministic geometry metrics;
5. better visual assessment;
6. fewer mutations.

A visually closer candidate with incorrect technical dimensions is never the best candidate.

### 6.9 Verified Publisher

The publisher implements automatic saving under a run-scoped authorization. This preserves the user's chosen automatic workflow without allowing an unlimited standing permission to overwrite drawings.

Authorization is bound to:

- one run ID;
- one absolute target path;
- the expected initial target hash;
- an approved backup root;
- one publication attempt after all gates pass;
- expiration at the end of the run.

Publication sequence:

1. verify exact target path and expected source hash;
2. create a backup and verify copied hash;
3. save the candidate to a temporary same-volume path;
4. close and reopen the temporary candidate;
5. rerender every critical region;
6. remeasure all driving dimensions;
7. rerun final visual, geometry, engineering, native-entity, and plot checks;
8. atomically replace the target;
9. reopen the target;
10. run post-save verification.

If verification fails before replacement, the target is untouched. If replacement or post-save verification fails, the verified backup is restored and the run ends as `ROLLED_BACK`.

## 7. Evidence package and run layout

Private run artifacts remain outside Git.

Recommended layout:

```text
runs/RUN-ID/
  run-manifest.json
  authorization/
  reference/
  dimensions/
  views/
  iterations/
  verification/
  candidates/
  publication/
```

Each iteration directory contains the exact evidence, metrics, review, and repair plan used for that mutation. Every JSON and image has a SHA-256 entry in an enclosing manifest.

No artifact may be reused after any bound source, drawing, mutation, render configuration, or alignment hash changes.

## 8. Core contracts

### 8.1 Dimension Register

Required top-level fields:

- schema version;
- run ID;
- source and page hashes;
- view ID;
- detection/processing coverage;
- summary counts;
- dimension observations;
- unresolved blockers;
- conflict register.

Required observation fields:

- stable dimension ID;
- display text;
- parsed value and unit;
- kind;
- role;
- source crop and bounding box;
- extension geometry;
- `from_ref` and `to_ref` when resolved;
- text and attachment confidence;
- status;
- provenance.

### 8.2 Visual Review

Required fields:

- schema version;
- run, review, region, and iteration IDs;
- reference package hash;
- CAD render and mutation hashes;
- verdict;
- severity;
- findings;
- evidence references;
- repair intent;
- preserved anchors;
- required measurements;
- requested next evidence when current evidence is insufficient.

### 8.3 Repair Plan

Required fields:

- schema version;
- repair ID and source review ID;
- target drawing hash;
- allowed operations;
- stable targets;
- preserve anchors and constraints;
- affected regions;
- expected improvements;
- metrics that must not worsen;
- rollback candidate reference.

### 8.4 Region Verification Register

Each record binds:

- source crop;
- latest CAD crop;
- alignment record;
- expected features;
- relevant dimensions and entities;
- last mutation and render hashes;
- geometry comparison;
- visual verdict;
- engineering verification;
- current status.

## 9. Dimension workflow

Dimension extraction and verification are separate phases.

### 9.1 Source observation

The system detects all clusters, creates enlarged crops, reads values, recognizes symbols, finds extension and arrow geometry, and attaches each dimension to semantic references where possible.

A dimension becomes `CONFIRMED` only when:

- value and units are valid;
- kind is known;
- view is known;
- attachment references are valid;
- no unresolved conflict exists.

### 9.2 Role policy

- `DRIVING`: may control authoritative geometry after confirmation.
- `REFERENCE`: verifies the result but does not drive geometry.
- `DERIVED`: is recalculated and checked for closure.
- `AMBIGUOUS`: reported but cannot control geometry.
- `CONFLICT`: blocks the related scope until resolved.

### 9.3 CAD verification

After generation or repair, AutoCAD must measure the actual geometry. A dimension is verified only when:

- measured value is within its technical tolerance;
- display text agrees with the measured value unless an approved override exists;
- native dimension type is correct;
- extension lines attach to the intended entities;
- visual placement does not introduce major layout defects.

## 10. Review hierarchy and pass policy

### 10.1 Region pass

A critical region passes only when:

- every mandatory feature is present;
- there are no critical or major findings;
- deterministic geometry metrics are within the region profile;
- all referenced driving dimensions pass;
- all engineering checks pass;
- evidence is newer than the last affected mutation;
- no critical unresolved item remains.

### 10.2 View pass

A view passes only when:

- every critical semantic region passes;
- coverage grid has no unchecked cells;
- inter-region relationships pass;
- shared datums are consistent;
- the Visual Supervisor passes the full view.

### 10.3 Sheet pass

A sheet passes only when:

- all required views pass;
- view placement and overall composition pass;
- annotations and dimensions have no major collisions;
- no evidence is stale;
- the whole-sheet visual review passes.

### 10.4 Final pass

Final completion requires:

```text
Visual Gate PASS
AND Geometry Gate PASS
AND Dimension/Engineering Gate PASS
AND Native/Editability Gate PASS
AND Save/Reopen Gate PASS
```

No average score can override a failed critical gate.

## 11. Initial metric profiles

Thresholds are configurable pilot baselines, not permanent standards.

Suggested critical-region baseline:

- silhouette IoU at least 0.90;
- normalized percentile Hausdorff distance at most 0.04;
- width/height ratio error at most 3 percent;
- centroid offset at most 2 percent;
- zero missing mandatory features;
- zero major or critical visual findings.

Suggested normal-region baseline:

- silhouette IoU at least 0.85;
- normalized percentile Hausdorff distance at most 0.07;
- ratio error at most 5 percent;
- zero major or critical findings.

The pilot must record false positives and false negatives so these profiles can be calibrated per region type.

## 12. Loop limits and stop conditions

Default pilot limits:

- maximum eight repair iterations per region;
- maximum two consecutive regressions;
- maximum two repetitions of the same repair signature;
- no progress after two iterations triggers a stop;
- any technical conflict triggers `NEEDS_HUMAN` immediately.

When only visual improvement stalls:

1. restore the best candidate;
2. mark the incomplete regions;
3. do not publish;
4. stop with `ROLLED_BACK_TO_BEST` or `NEEDS_HUMAN`.

## 13. Reliability and error handling

The system fails closed for:

- missing source or drawing hashes;
- stale render or measurement evidence;
- invalid structured model output;
- ambiguous target entity identity;
- dimension conflicts;
- failed alignment;
- target drawing changed outside the run;
- failed backup verification;
- repeated non-improving repairs;
- API timeout after bounded retry;
- publishing prerequisites not met.

Model retry may repair transport or schema failures. It must not silently reinterpret an engineering conflict.

## 14. Security, privacy, and cost controls

- API keys are loaded from local secret configuration and never written to run artifacts.
- Private source images, customer drawings, and generated outputs remain outside Git.
- Requests send region crops rather than full documents whenever context permits.
- The model is called only at meaningful checkpoints, not continuously by time interval.
- Deterministic comparison runs before expensive visual review.
- Normal regions may use a lower-cost model profile; critical or ambiguous reviews may escalate to the strongest approved model.
- API usage, image count, latency, retries, and estimated cost are recorded per run without logging credentials.
- Retention and deletion policy for uploaded source images must be documented before production use.

## 15. Testing strategy

### 15.1 Contract tests

- strict schema validation;
- hash binding;
- stale-evidence refusal;
- only allowed verdict and state vocabularies;
- unresolved critical dimensions block progression;
- Codex output cannot contain a visual pass authority.

### 15.2 Deterministic image tests

Synthetic fixtures cover:

- translation, rotation, and uniform scale alignment;
- missing and extra edges;
- contour deformation;
- component displacement;
- curve-profile differences;
- noise and line-width variation;
- correct refusal when alignment anchors are insufficient.

### 15.3 Dimension tests

Synthetic and approved private fixtures cover:

- horizontal, vertical, aligned, angular, radius, and diameter dimensions;
- chain and baseline dimensions;
- tolerances and overrides;
- attachment ambiguity;
- conflict detection and chain closure;
- measurement round-trip from AutoCAD.

### 15.4 Structured model tests

Use recorded, non-sensitive fixtures and mock model responses to prove:

- schema retry behavior;
- unsupported free-form result rejection;
- correct pass/fail/needs-human handling;
- protected constraints appear in every repair intent;
- evidence references are valid.

### 15.5 AutoCAD live tests

Operator-controlled disposable-DWG tests prove:

- deterministic region render;
- entity export;
- dimension measurement;
- mutation invalidates prior evidence;
- post-mutation rerender is newer;
- backup/save/reopen/rollback behavior.

Production/customer drawings are not used for automated mutation tests.

### 15.6 Pilot acceptance test

The first pilot uses one approved PDF or scanned page and one side view containing at least cabin, wheels, and chassis.

Pilot success requires:

- every detected dimension cluster has a disposition;
- no critical dimension remains unresolved;
- the independent reviewer finds at least one meaningful visual defect that the previous Codex-only process accepted;
- a repair measurably improves comparator metrics;
- driving dimensions remain within tolerance;
- region, view, and sheet gates operate correctly;
- the first pilot publishes only to a disposable target.

## 16. Implementation decomposition

### VS-T0 — contracts and design integration

Create schemas, state vocabularies, errors, synthetic examples, and architecture/roadmap integration. This is the predecessor for all other work.

### VS-T1 — offline Dimension Observer

Implement cluster detection, OCR/value parsing, attachment candidates, role classification, coverage, and conflicts. No AutoCAD mutation.

### VS-T2 — deterministic Geometry Comparator

Implement alignment, contours, overlay/difference masks, metrics, curve comparison, and iteration improvement tracking.

### VS-T3 — AutoCAD Evidence Exporter

Extend the existing dispatcher with read-only render, entity, and measurement evidence. No repair operation in this task.

### VS-T4 — Visual Supervisor API adapter

Implement multimodal requests, structured result validation, bounded retry, evidence packaging, and usage accounting.

### VS-T5 — Codex Repair Planner

Implement the validated conversion from Visual Review to business-level Repair Plan with protected constraints and affected-region invalidation.

### VS-T6 — closed-loop orchestrator

Implement state transitions, iteration control, best-candidate selection, stale evidence, stop conditions, and run reporting.

### VS-T7 — Verified Publisher

Implement run-level authorization, backup, candidate save, reopen verification, atomic replacement, post-save verification, and rollback. This task requires a dedicated security/operations review.

### VS-T8 — real private pilot

Run one approved page/view through the complete disposable loop. Record real evidence honestly as `PASS`, `FAIL`, `SKIP`, or `NOT RUN`.

## 17. Parallel execution policy

After VS-T0 stabilizes its contracts, the following tasks may run in isolated branches/worktrees with disjoint write sets:

- one agent on VS-T1;
- one agent on VS-T2;
- one agent on VS-T3;
- one agent on VS-T4.

VS-T5 begins after the review and entity contracts are stable. VS-T6 integrates VS-T1 through VS-T5. VS-T7 is isolated and reviewed independently. One designated reviewer reviews the integrated candidate rather than accepting worker self-reviews.

No two agents may concurrently edit the same schema, dispatcher file, orchestrator file, or canonical status record.

## 18. Rollout order

1. Merge the design and implementation plan only.
2. Keep the current M2 execution uninterrupted.
3. Implement VS-T0 as contract-only work when the roadmap owner selects the visual-supervisor slice.
4. Build the offline comparator and dimension observer.
5. Add read-only AutoCAD evidence operations.
6. Add the Visual Supervisor adapter and repair planner.
7. Integrate the disposable closed loop.
8. Run the private pilot and calibrate thresholds.
9. Implement verified automatic publication only after all earlier gates are demonstrated.
10. Integrate into M7/M8 release behavior; do not bypass the existing authoritative release manifest.

## 19. Acceptance criteria for the complete feature

The feature is complete only when all of the following are proven:

1. The system reviews source images and PDF pages through the same normalized evidence contract.
2. Every detected dimension cluster has a recorded disposition.
3. Every authoritative driving dimension has valid attachments and measurement verification.
4. Codex cannot issue a visual pass or publish authority.
5. Every mutation invalidates all affected visual and measurement evidence.
6. A new render and measurement are required after every affected mutation.
7. Deterministic metrics prove whether a candidate improved or regressed.
8. The independent Visual Supervisor reviews semantic regions, complete views, and the complete sheet.
9. Critical failures cannot be hidden by an average score.
10. Ambiguous technical evidence stops for human resolution.
11. Visual stagnation restores the best candidate and does not overwrite the target.
12. Automatic publication requires a valid run-scoped authorization and all gates.
13. The target is backed up, saved, reopened, reverified, and automatically restored on failure.
14. Private data and credentials remain outside Git.
15. The authoritative verifier and applicable private/live gates report fresh, reproducible evidence.

## 20. Spec self-review

- Placeholder scan: no TBD/TODO placeholders remain.
- Consistency: automatic publication is allowed only after all gates; ambiguity still blocks publication.
- Scope: implementation is decomposed into contract, offline, AutoCAD evidence, model adapter, orchestration, publication, and pilot slices.
- Architecture: the design extends existing package and File IPC boundaries and prohibits parallel replacement pipelines.
- Safety: Codex cannot self-approve, stale evidence is rejected, and production rollback is mandatory.
