# Fidelity Layout Recovery Design

**Status:** Approved by the user's request on 2026-07-22 to execute recovery
steps 1 through 5.

## Problem

The current PDF pipeline creates an analysis DXF, not a faithful drawing-sheet
reconstruction. It applies a model scale to the entire A3 page, emits only
detected line/circle primitives, and overlays inferred semantic components.
On the approved private PDF all nine pages contain zero text primitives and
hundreds of injected `INSERT` entities.

## Goal

Create a separate, non-destructive fidelity path that preserves sheet layout
in paper coordinates, measures missing content against the source, and only
creates model-space views after explicit calibration and view approval.

## Design

### 1. Fidelity layout profile

- Add a separate `fidelity-pdf` command and manifest; it never replaces the
  existing `run-pdf` analysis output.
- Require its output root to resolve outside the Git worktree. Every manifest
  and report is `private_artifact: true` and records only source basename and
  SHA-256, never an absolute source path.
- Render each page at the selected DPI and record its displayed PDF page box,
  rotation, and rendered image size. Map source raster coordinates `(x_px,
  y_px)` to a layout-modelspace coordinate `(x_mm, y_mm)` using
  `x_mm = x_px * page_width_mm / image_width_px` and
  `y_mm = (image_height_px - y_px) * page_height_mm / image_height_px`.
  This is 1:1 paper millimetres in DXF modelspace (not a DXF paperspace layout)
  and handles non-A3 pages/rotation through the recorded displayed page box.
- Extract the fidelity geometry afresh from rendered pixels. It must not reuse
  a Primitive IR already transformed by a page-wide model scale.
- Build a clean layout DXF from detected primitives only: no constraint solving,
  no semantic component blocks, and no inferred `part-*` labels.
- Underlays are deferred and opt-in. If added later, they must use a relative,
  staging-only path on a non-plot reference layer, be SHA-bound, and be
  excluded from every vector metric. A clean DXF without an underlay is always
  produced.

### 2. OCR and layout audit

- Run title-block and detected text ROI OCR for each rendered page and persist
  text, bounding boxes, orientation, confidence, and OCR configuration.
- OCR/table/scale outputs are audit sidecars only. The clean fidelity DXF receives
  geometry primitives only, regardless of OCR confidence.
- Detect table candidates only in a configured lower-sheet band, require at
  least three horizontal and three vertical grid coordinates, reject candidates
  with more than 200 cells, and persist rejection reasons, cell OCR output, and
  confidence as review data. Do not create source text or dimensions
  automatically.
- Record a page completeness report: detected line/circle/text/table counts,
  candidate scale labels, and unresolved content.

### 3. Paper/model separation

- The paper-layout DXF is the visual-fidelity artifact.
- Per-view scale candidates from the restored nightly workflow remain
  `needs_verification` until a reviewer supplies an approved, non-overlapping
  region bound to the source-page SHA.
- A `fidelity-region-proposal` is a private, source/render-SHA-bound sidecar in
  displayed raster pixels (top-left origin). It stores non-overlapping view
  regions, excluded title/table/note regions, and a stable proposal-definition
  hash. It is `needs_human_approval`, permits only region-specific layout
  reconstruction, and never changes the fidelity manifest, DXF, or IR.
- Region inputs are explicitly supplied by the reviewer in private staging;
  their rectangles must be in bounds, have a three-pixel gutter, and cannot
  overlap each other or an excluded region. Reuse verifies the PDF, rendered
  page, page dimensions, and every referenced artifact hash before it writes.
- A changed proposal is a new positive revision (`page_NN-rN.json`), never an
  overwrite. Any area outside its green reconstruction or orange exclusion
  rectangles remains explicitly `needs_classification`.
- This recovery slice exports zero model-space views. A candidate that spans
  most of a page, as on the current private PDF, cannot authorize one.

### 4. Fidelity gate

- Rasterize the clean vector layout with the pinned PyMuPDF renderer at the
  original rendered page dimensions, fixed 0.15-mm vector stroke width and
  white background. Compare Canny edge maps using a 3-pixel dilation tolerance:
  `precision = vector_edges within dilated source_edges / vector_edges` and
  `recall = source_edges within dilated vector_edges / source_edges`.
  Persist an overlay PNG, metric inputs, and a JSON report. OCR/table/title-
  block completeness is reported independently from line coverage.
- The report is `needs_review` until thresholds are baselined on approved
  annotations; it must never be reported as a visual-fidelity pass merely
  because the DXF round-trips. It records source/render/DXF SHA-256, transform,
  DPI, renderer version, component counts, and `not_evaluated` with a reason
  whenever a metric cannot be rendered.
- Report full-page metrics and a content metric that masks the outer frame and
  lower title-block band. Source underlays and DXF `IMAGE` entities are
  forbidden in the vector-score renderer.

## Safety and non-goals

- Existing analysis DXFs, source PDF, and production drawings are untouched.
- Fidelity manifests are rejected by `mechanical-review` and
  `mechanical-repair`; those operations validate generated entities, not source
  fidelity.
- No automatic production repair, no automatic scale approval, and no invented
  dimensions, line styles, or table text.
- The first recovery slice exposes a clean, measurable baseline. Full
  reconstruction of dimensions, linetypes, curves, and tables follows only
  from measured audit results.

## Acceptance criteria

1. A clean fidelity DXF contains no semantic `INSERT` overlay and preserves
   paper-space page dimensions.
2. All pages emit OCR/layout audit sidecars, including an explicit zero/failed
   state where recognition is absent.
3. The private nine-page PDF produces overlay reports and no false fidelity
   pass.
4. Existing analysis pipeline behavior remains regression-tested and intact.
5. Focused tests, the official verifier, and the applicable private PDF gate
   run with recorded evidence.
6. Synthetic tests cover Y-axis flip, a non-A3/rotated page transform,
   OCR-sidecar isolation, table-candidate rejection, and an absent metric.
7. Tests reject an output directory inside the repository and prove that no
   generated metadata contains an absolute private-source path.
