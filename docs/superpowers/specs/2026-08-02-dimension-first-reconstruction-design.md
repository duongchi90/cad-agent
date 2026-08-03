# Dimension-First CAD Reconstruction Design

Date: 2026-08-02
Status: design approved by user; written-spec review pending

## Product decision

`cad-agent` will reconstruct engineering CAD from an approved dimension and
constraint model. The PDF/image remains an essential reference layer for
topology, view membership, relative placement, curves, hidden lines, hatch,
and visual comparison, but it is not the authority for engineering scale.

The existing image/PDF, Semantic IR, DXF, File IPC, and AutoCAD .NET
boundaries remain. The new authoritative path inserts two explicit contracts
between recognition and DXF generation:

```text
PDF/image
  -> observations + Dimension IR
  -> approved Datum/Constraint IR
  -> constrained view geometry
  -> DXF + native dimensions + provenance report
  -> headless review + AutoCAD read-only review
```

The current pixel-first path remains available as a draft/reference mode. It
must not silently produce authoritative engineering geometry.

## Generality boundary

The architecture is drawing- and domain-neutral. MẠN is the first private
fixture because it exposes station, elevation, chain, and raised-deck
relationships clearly; it is not the source of the core data model and its
numeric values must not be hard-coded into production code.

The reusable core models generic concepts:

- dimension kinds: linear, aligned, angular, radial, diameter, ordinate,
  baseline, chain, reference, and tolerance-bearing dimensions;
- attachment targets: endpoints, edges, centers, axes, named datums, repeated
  axes, blocks, and view-local entities;
- coordinate frames, transforms, shared datums, geometric relations,
  constraints, provenance, conflicts, and release profiles;
- editable geometry and review evidence independent of whether a drawing is a
  ship, vehicle, machine, building, or another 2D engineering subject.

Domain and drawing conventions belong in profiles, not in the core:

- `DrawingProfile` defines units, annotation conventions, standard blocks,
  domain aliases, and revision rules.
- `ViewProfile` defines view axes, datum semantics, source region, view-local
  entities, and explicitly shared datums.
- A domain term such as `station`, `frame`, `axle`, or `gridline` resolves to a
  generic named-axis or datum type through the selected profile.

The MẠN fixture supplies an approved input register and expected output
coordinates for regression. It must exercise the generic interfaces rather
than add MẠN-specific branches.

## Problem and lessons from the MẠN slice

The MẠN experiment showed that a globally calibrated pixel transform can
produce a visually plausible but dimensionally wrong drawing. Scan scaling,
perspective, crop selection, Hough filtering, and image line thickness all
change pixel distances. A dimension such as 850 mm must therefore override an
image measurement that appears to be 847 mm.

The correct interpretation is not that image tracing is useless. The correct
interpretation is that the order of authority was wrong: geometry was being
measured from pixels and dimensions were used only as a later check.

## Goals

- Read dimension values and their semantic attachment, not values alone.
- Require a human approval boundary for ambiguous dimension interpretation.
- Build a technical coordinate system from datums, stations, centerlines, and
  elevations before tracing view geometry.
- Represent exact dimensions and derived geometric relationships as explicit,
  solver-ready constraints.
- Use image geometry to determine topology, relative shape, and undimensioned
  curves while preserving its lower authority.
- Mark every CAD object as `EXACT`, `CONSTRAINED`, `ESTIMATED`, or
  `UNRESOLVED` with source provenance.
- Emit native editable DXF geometry and native `DIMENSION` entities for
  approved measurements.
- Produce a report showing confirmed dimensions, uncertain observations,
  solver residuals, unresolved regions, and source overlays.
- Make one dimension-complete representative view the first acceptance slice;
  use MẠN as the initial regression fixture.

## Non-goals and safety boundaries

- Do not infer an authoritative dimension from pixel distance alone.
- Do not auto-accept OCR text when its extension lines, endpoints, direction,
  or view membership are unknown.
- Do not treat a global `mm/px` scale as the engineering coordinate system.
- Do not fabricate missing radii, diameters, angles, or material/profile sizes.
- Do not make File IPC, AutoCAD LISP, or the .NET plugin the primary geometry
  engine. They remain application and review boundaries.
- Do not expand immediately to all nine pages before the representative
  dimension-first slice has stable dimension and constraint evidence.
- Do not promote `ESTIMATED` or `UNRESOLVED` model-critical objects into an
  authoritative production result.
- Do not change the existing production-repair approval and backup boundary.

## Authority order

The resolver and review report must use this order:

1. Approved dimensions written on the source drawing.
2. Approved datums: station axes, centerlines, baselines, reference planes,
   and elevations.
3. Approved geometric relations: parallel, perpendicular, concentric,
   symmetric, tangent, coincident, equal, and chain relationships.
4. Known CAD blocks and standard-detail definitions with matching provenance.
5. Image/PDF geometry used to identify topology, relative placement, and
   undimensioned curves.
6. Pixel measurements used only as estimates pending engineering approval.

When two authoritative sources conflict, the run stops with an explicit
`dimension_conflict`; it does not choose the closer pixel measurement.

## Dimension IR

Dimension IR is a versioned, hash-bound observation artifact. It must record
both the measurement and what the measurement means.

Required fields for each observation:

```json
{
  "id": "DIM-001",
  "value": 500.0,
  "unit": "mm",
  "kind": "horizontal_distance",
  "scope": "view:MAN",
  "from": {"datum_or_entity": "station:12", "anchor": [0, 0]},
  "to": {"datum_or_entity": "station:13", "anchor": [0, 0]},
  "extension_geometry": {
    "p1_px": [0, 0],
    "p2_px": [0, 0],
    "dimension_line_px": [[0, 0], [0, 0]]
  },
  "dimension_role": "chain",
  "source": {"file_sha256": "...", "page": 1, "bbox_px": [0, 0, 0, 0]},
  "extraction": "ocr_plus_geometry",
  "confidence": 0.98,
  "status": "candidate",
  "approval": null
}
```

`kind` must distinguish at least `horizontal_distance`, `vertical_distance`,
`aligned_distance`, `radius`, `diameter`, `angle`, `coordinate`, and
`chain_total`. `dimension_role` must distinguish `overall`, `chain`,
`reference`, `derived`, and `changed_design` when the source indicates it.

`from` and `to` may initially contain source anchors, but an observation cannot
become authoritative until those anchors resolve to named entities or datums.
The system must distinguish a dimension's numeric text from its extension-line
attachment. A number without a valid attachment remains `UNRESOLVED`.

Dimension extraction may combine OCR, vector/text extraction, line detection,
and view classification. OCR confidence alone is insufficient for approval.

## Constraint IR

Constraint IR is generated only from approved Dimension IR, approved datums,
known CAD details, or explicitly approved image relationships. It is the input
to solving and geometry reconstruction.

Each constraint must include:

- stable `id` and `kind`;
- referenced datum/entity IDs;
- exact value or relation;
- unit and tolerance policy;
- source Dimension IR IDs or relation approval IDs;
- status and provenance;
- solver residual after solving.

Examples include:

```text
station:13.x - station:12.x = 500 mm
level:1450.y - level:850.y = 600 mm
deck_raised.y - main_deck.y = 450 mm
line:A parallel line:B
circle:hole_1 concentric circle:hole_2
```

The solver must reject underconstrained model-critical geometry, report
overconstraint and conflict sets, and never fill missing values from a pixel
measurement without changing the object's provenance to `ESTIMATED`.

## Datums and view model

Each drawing view gets a named technical coordinate system. It must identify:

- view name and source region;
- unit and axis directions;
- origin/datum references;
- station sequence and numbering;
- station spacing constraints;
- elevation/reference levels;
- shared or view-local entities;
- transformation used only for image overlay.

Repeated-axis and level data are profile inputs, not assumptions in the core.
For any drawing, the profile/register must state whether an axis sequence is
numbered, evenly spaced, chained, ordinate-based, or irregular. A derived
overall value must be reported as derived and must not be confused with a
separately printed overall dimension.

Image rectification and overlay may use an affine or local piecewise transform
fitted from approved anchors. That transform maps CAD to the source image for
review; it does not replace the technical coordinate system.

## Geometry provenance

Every reconstructed geometry entity and component must carry one of these
states:

- `EXACT`: coordinates or size are directly specified by an approved source
  dimension or coordinate.
- `CONSTRAINED`: coordinates are solved from approved dimensions and relations.
- `ESTIMATED`: shape or position is derived from image pixels or an unapproved
  heuristic.
- `UNRESOLVED`: required source information is missing or ambiguous.

The DXF builder will place `ESTIMATED` objects on `AI_ESTIMATED` and
`UNRESOLVED` objects on `AI_UNRESOLVED` or omit them from the authoritative
model layer. Model-critical unresolved objects must block an authoritative
release. The provenance report must link each object to its Dimension IR,
Constraint IR, source crop, or image-trace evidence.

## End-to-end workflow

### 1. Source preparation

Render the PDF at sufficient DPI, preserve the original hash, classify views,
and retain the source crop coordinates. Detect dimension text, extension
lines, arrowheads, station labels, baselines, and title-block scale labels.

### 2. Dimension and datum observation

Create Dimension IR and datum candidates. Group text with its dimension line and
view. Detect chain dimensions and station numbering as a connected structure,
not as independent OCR strings.

### 3. Approval gate

Present the candidate register for confirmation. Approval must be explicit for
numeric value, unit, attachment, view, role, and whether a value is printed or
derived. An ambiguous candidate stays `candidate` or `UNRESOLVED`.

### 4. Constraint solving

Build the view coordinate system and Constraint IR. Solve station positions,
elevations, offsets, and approved geometric relations. Write residuals and
conflict sets before allowing DXF generation.

### 5. Image-guided geometry reconstruction

Trace lines, arcs, polylines, topology, and components against the solved
datums. Use image pixels to choose the correct branch, endpoint, curve shape,
or attachment. Snap dimension-backed endpoints to exact solved coordinates.

### 6. DXF and review

Generate editable LINE, ARC, LWPOLYLINE, block, and native DIMENSION entities.
Emit layer separation and provenance. Produce a source/CAD overlay and a
dimension residual report. Run headless review, then read-only AutoCAD review
through the existing File IPC or .NET boundary.

## Changes to the existing architecture

### `primitive_ir_lib`

Keep image geometry, OCR, source traces, and calibration observations, but add
Dimension IR and datum candidates as separate artifacts. The existing manual
pixel scale becomes an overlay/reference calibration and is no longer allowed
to authorize engineering coordinates.

### `semantic_ir_lib`

Add view models, datum references, Constraint IR generation, constraint status,
and solver residual/conflict reporting. Existing raw line recognition remains
useful for topology and image evidence.

### `dxf_builder_lib`

Consume solved view geometry and provenance. Generate exact and constrained
entities on authoritative layers, estimated entities on `AI_ESTIMATED`, and
native dimensions from approved Dimension IR. The builder must not silently
replace solved coordinates with raw pixel coordinates.

### `cad_agent`

Extend manifests/checkpoints with Dimension IR, Constraint IR, approval hashes,
view-model hashes, solver evidence, and provenance summaries. Resume must reject
changed source or changed approved dimension data.

### `mcp_integration_lib` and AutoCAD integrations

Keep File IPC and the .NET plugin unchanged as transport/application boundaries.
Use them for drawing activation, entity inspection, measurement, zoom, and
read-only review. Primary geometry remains deterministic and reproducible in
the builder.

## Generic acceptance contract

Every dimension-first run is accepted only when all of the following hold:

- every driving dimension has valid value, unit, semantic kind, attachment,
  view membership, and approval status;
- every model-critical degree of freedom is exact or constrained by approved
  evidence;
- all approved dimensions measure back to their source values within the
  configured solver residual tolerance and source tolerance policy;
- dimension chains, baseline/ordinate relations, and derived totals close
  without contradiction;
- shared datums are explicitly declared before cross-view constraints are
  created;
- no model-critical `ESTIMATED` or `UNRESOLVED` entity reaches an
  authoritative release profile;
- source/CAD overlay confirms view membership, topology, and overall shape
  without using pixel residuals as an engineering measurement;
- the report lists every rejected, unresolved, conflicted, estimated, derived,
  and approved observation plus all solver residuals;
- the DXF opens in AutoCAD Mechanical and remains editable without saving or
  mutating a production drawing.

The solver residual tolerance is not the same as the physical accuracy of the
source drawing. For example, a solver may satisfy an approved 850 mm equation
within 0.01 mm while the drawing's unprinted source tolerance remains unknown.

## MẠN regression fixture

The first fixture uses the approved MẠN register, not MẠN-specific production
logic. Its expected checks are:

- axes 0..85 resolve to 86 axes and 85 intervals;
- the approved interval value is 500 mm and the derived span is 42500 mm;
- approved elevations resolve to 0, 850, 1450, and 2100 mm;
- the raised bow/deck relation resolves to 450 mm;
- all of the above are represented through generic repeated-axis, level, and
  linear-distance contracts;
- the fixture proves that manual-register input can run without OCR and that
  a later OCR adapter can produce the same Dimension IR contract.

## Rollout

### P0: contracts and evidence

Define schemas, provenance states, approval records, manifest bindings, and
dimension/constraint residual reports. Add synthetic tests for dimensions,
attachments, conflicts, chain closure, and status transitions.

### P1: representative dimension-first vertical slice

Implement the generic repeated-axis/level/dimension path with a manually
approved register. Use the supplied MẠN view as the first private regression
fixture, while keeping all MẠN values in fixture data outside production logic
and outside Git.

### P2: additional views and cross-view contracts

Apply the generic view/profile model to B-B, C-C, DỌC TÂM, BOONG, and ĐÁY.
Reuse shared datums only when the source or an approval record explicitly
supports that relationship. Add cross-view constraint checks as a reusable
contract, not as MẠN-specific logic.

### P3: advanced fidelity

Return to OCR/font, tables, linetypes, hatch, and detailed components after
dimension-first geometry is stable. These remain review-only until their
provenance and approval contracts are complete.

## Test strategy

- Unit tests validate Dimension IR parsing, attachment resolution, units,
  dimension roles, provenance transitions, and Constraint IR generation.
- Solver tests validate exact station/elevation equations, chain closure,
  underconstraint, overconstraint, and conflict reporting.
- Golden fixture tests validate exact repeated-axis and level coordinates from
  approved registers without depending on global pixel scale; MẠN is the first
  such fixture.
- Overlay tests validate that the solved CAD transform is used only for source
  comparison and does not alter model coordinates.
- DXF tests reopen output and verify native dimensions, layers, provenance
  metadata, and entity types.
- AutoCAD Mechanical tests remain disposable, read-only, and separate from
  ordinary offline verification.

## Definition of done for this design

The design is ready for implementation after the user reviews this written
specification. Implementation begins with P0 contracts and the P1
representative slice, using MẠN as the first fixture;
the current pixel-first path is not deleted until the new path has equivalent
staging, review, and safety evidence.
