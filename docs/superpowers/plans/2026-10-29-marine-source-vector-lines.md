# Marine Source Vector LINE Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add directly supported visible PDF LINE strokes to the existing Primitive IR path without inferring text, drawing semantics, calibration, or dimension meaning.

**Architecture:** Reuse `run_pdf` for PDF visibility and coordinate validation, then pass source-bound lines through the existing `run_image`/assembly path only after raster merging. Emit them with the existing `geometry_pdfvector` source and `Trace` fields; keep them out of raster merging, calibration, dimension association, and cross-validation. Use the frozen Gunnerus PDF only as a local real-data regression, not as a production identity rule.

**Tech Stack:** Python 3.11, PyMuPDF, existing Primitive IR models/schema, pytest, existing DXF builder/reviewer.

**Spec:** #491 checkpoint comment 6488871696 and the bounded PO disposition for generic source-stroke candidate admission (2026-10-29).

## Global Constraints

- Existing owners only: `primitive_ir_lib/run_pdf.py`, `run_image.py`, `geometry_extraction.py`, `assemble.py`, and their focused tests.
- No drawing name, layer name, or `seqno` may grant admission; preserve layer as uninterpreted provenance only.
- Unknown ancestry, clipping, OCG, opacity, blend, paint order, source/render visibility, multiplicity, or raster overlap fails closed for the affected path.
- Source LINEs do not become TEXT, DIMENSION, centerline, constraint, calibration, or feature semantics.
- PR #507 remains unchanged; serialize the overlapping writer lane and do not edit its branch.
- Private Marine input remains local, personal/non-commercial; do not upload it or include it in the repository.

## Review Focus

- Nested/grouped or clipped stroke with unresolved context — refuse the affected path.
- Later opaque paint or changed OCG state — refuse when visible source support is uncertain.
- PDF text outlines or coincident text/LINE geometry — do not claim text recovery; refuse unresolved duplication.
- Raster/source exact or partial overlap — do not duplicate or merge ambiguously.
- Manual/unverified scale — geometry comparison only; no production calibration or native acceptance claim.

---

### Task 1: Pin the source-line regression and refusal boundaries

**Files:**
- Test: `primitive_ir_lib/tests/test_run_pdf.py`
- Test: `primitive_ir_lib/tests/test_run_image.py`
- Test: `primitive_ir_lib/tests/test_marine_source_vector_lines.py`

**Interfaces:**
- Consume current `run_pdf`, `run_image`, `RawLine`, `PrimitiveIRDocument`, and existing source visibility helpers.
- Add an internal `RawPdfLine` record extending pixel LINE geometry with source PDF SHA-256, page index, six-value transform, render SHA-256, DPI, and render origin.
- Add `_page_vector_lines(page, baseline_pixmap, pixel_scale, source_pdf_sha256, source_page_index, render_dpi) -> list[RawPdfLine]` in `run_pdf.py`; no layer/seqno selector parameter.
- Add `pdf_vector_lines: Optional[List[RawPdfLine]] = None` to `run_image.run` and `assemble.build_document`; these lines are serialized separately from raster lines.
- Require PDF vector output to use `source="geometry_pdfvector"` and the existing `Trace` source PDF/page/transform/render fields.
- Keep the opt-in real-data case gated by `CAD_AGENT_GUNNERUS_MARINE_PDF` and the frozen SHA-256 `c4ec405ff866bbec40cdc15a86a1165f255d583af4e0c592767d5f6d65cd7ae3`.

- [x] Write the frozen-source test that proves the current pipeline omits the fully visible seqno-1445 source stroke, while preserving the exact source/render identity and rotation-270 transform. Baseline at main `69415762`: expected 796 source LINE primitives, actual 0 (`pytest`: 1 failed in 85.61 s).
- [x] Extend direct source-LINE refusal coverage for grouped/clipped ancestry, OCG text and stroked-text outline conflicts, later opaque paint, and a separate visible-line positive control. The tests exercise the vector-LINE candidate admission path itself.
- [x] Add a run-image contract test showing source lines do not enter raster merge, calibration, or cross-validation inputs.
- [x] Run focused tests and record the expected current-main baseline failure before implementation; exact-source candidate reached the ordinary run-image owner and DXF on the same render.

### Task 2: Implement the smallest existing-owner source LINE path

**Files:**
- Modify: `primitive_ir_lib/run_pdf.py`
- Modify: `primitive_ir_lib/run_image.py`
- Modify: `primitive_ir_lib/geometry_extraction.py`
- Modify: `primitive_ir_lib/assemble.py`
- Test: files from Task 1

**Interfaces:**
- `run_pdf` returns only source LINE segments whose complete source/render context is validated.
- `run_image` accepts those lines separately from raster `RawLine` values and appends them after raster merging.
- Assembly emits the existing `LineGeometry` with `geometry_pdfvector` and existing source-bound `Trace`; no schema change.

- [x] Implement a local candidate using existing PDF visibility/context admission and preserve source segment endpoints/order.
- [x] Keep source lines separate through raster merge, calibration, and cross-validation; preserve provenance in output IDs/traces.
- [x] Run focused controls and the real-source regression through run-image; same-source 72-DPI baseline omitted the source LINE path and the candidate emitted 751 source-bound LINE primitives.

### Task 3: Verify downstream usefulness and close the bounded package

**Files:**
- Test: `primitive_ir_lib/tests/test_marine_source_vector_lines.py`

- [x] Build DXF from the actual candidate IR; all IR LINE entities emitted, no skipped primitives, and the source LINE path had no raster/text overlap under the existing refusal screen.
- [x] Run the frozen Gunnerus `real_data` regression: 1 passed; exact PDF SHA matched. Focused PDF/image/geometry suite: 135 passed, 2 B041-gated skips; added outline-control test passed in a later targeted run. Ruff and `git diff --check` passed.
- [ ] Run canonical `scripts/verify.ps1` after the final implementation on a clean candidate commit; the script refuses to run with the current uncommitted worktree.
- [ ] Record native DWG save/close/reopen/readback as NOT RUN unless its dedicated authorized gate is available; never infer it from IR/DXF success.
- [ ] Recheck current main, exact PR head/tree, hosted CI, independent Security/Integration receipts, and any required native gate before readiness or merge.
