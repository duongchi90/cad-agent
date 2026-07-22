# PDF Vertical-Slice Orchestration Design

**Status:** Approved by the user on 2026-07-22

**Target:** Windows, Python 3.11, AutoCAD Mechanical 2027

## Goal

Make an approved multi-page PDF a first-class `cad_agent` input. The CLI must
render each page, create Primitive and Semantic IR, build/review a staged DXF,
persist per-page build evidence, and resume safely without reprocessing verified
pages.

## Design

- `run-pdf` requires the same positive verified manual scale and explicit
  calibration approval reference as image `run`.
- It delegates rendering and Primitive IR creation to `primitive_ir_lib.run_pdf`.
  It then delegates Semantic IR, constraint solving, DXF build, and headless
  review to the existing orchestration functions for each page.
- `pdf-run-manifest.json` SHA-binds the input PDF and records the render
  manifest plus an atomic state/hash for every page's Primitive IR, Semantic IR,
  staged DXF, and build evidence.
- `resume-pdf` verifies the original PDF hash before it reuses checkpoints. A
  page with a missing or changed artifact is recomputed; a missing Primitive IR
  is regenerated from its SHA-verified rendered page. Intact completed pages
  are not touched.
- The output is staging-only. AutoCAD Mechanical review/repair remains a
  separate explicit operation using each page's build evidence.

## Out of scope

- Automatic calibration, production drawing mutation, Agent action application,
  and private benchmark approval are unchanged.
- The slice does not alter PDF rendering, OCR, semantic, DXF, or AutoCAD
  algorithms.

## Acceptance criteria

1. A two-page synthetic PDF completes to per-page Primitive IR, Semantic IR,
   DXF, and build evidence.
2. Resume leaves intact page checkpoints byte-identical.
3. Replacing the input PDF is rejected before any resume stage runs.
4. Focused tests and `scripts/verify.ps1` pass.
