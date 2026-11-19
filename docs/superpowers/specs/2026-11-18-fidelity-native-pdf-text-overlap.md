# Native PDF Text Observation Compound-Paint Occlusion Refinement

- Approval date: 2026-11-18 (`#429#issuecomment-6966483405` / `#491` Milestone 1 OOB promotion)
- Supported scope: Windows, Python 3.11, PyMuPDF (`fitz`) native PDF text span observation in `cad_agent/fidelity.py` (`_native_pdf_text_span_records` / `has_later_paint_overlap`)
- Status: executing
- Base SHA: `ba5e124e811d6bf47b1890bee23f382b7e3c6ca4`

## Reuse Declaration

- Existing capability inspected: `cad_agent/fidelity.py` (`_native_pdf_text_span_records`, `has_later_paint_overlap`, `is_safe_adjacent_text_overlap`, `run_fidelity_text_observations`) and `tests/test_cad_agent_fidelity.py` native PDF visibility/occlusion suite.
- Existing API reused: `fitz.Page.get_text("dict")`, `fitz.Page.get_texttrace()`, `fitz.Page.get_bboxlog()`, `fitz.Page.get_drawings()`, `fitz.Rect`, and existing `cad_agent.fidelity.run_fidelity_text_observations` / `_native_pdf_text_span_records` observation contracts.
- Adapter required: None; refine `_native_pdf_text_span_records` and `has_later_paint_overlap` inside the existing owner `cad_agent/fidelity.py` by binding `page.get_bboxlog()` sequence indices to per-glyph `get_texttrace()` boxes, connected `fill-path` subpaths, and 1D `stroke-path` primitives from `get_drawings()`, generalizing exact common-style multi-trace span assembly beyond a single hardcoded source hash, and allowing standard `Tz` condensed font subrange binding when glyph boxes match (`>= 0.99`), with fail-closed fallback to raw `paint_bbox` whenever sequence geometry is absent or inconsistent.
- New capability genuinely missing: Operator-level decomposition of ISO 32000-1 compound PDF paint operations (multi-trace `BT ... ET` `fill-text` / cross-margin `texttrace` union boxes, hollow sheet-wide or multi-segment `stroke-path` union boxes, disjoint multi-subpath `fill-path` arrowheads, and non-striking thin dark CAD dimension/leader/table strokes in TrueType metric margins) so unoccluded CAD text spans are not 100% dropped by coarse `bboxlog` union rectangles while real whiteouts, clipping, zero-opacity, hidden OCR (`render_mode=3`), and mid-body strikethroughs remain excluded.
- Files allowed to change: `cad_agent/fidelity.py`, `tests/test_cad_agent_fidelity.py`, `docs/superpowers/specs/2026-11-18-fidelity-native-pdf-text-overlap.md`.
- Files forbidden to duplicate: `cad_agent/fidelity.py`, `primitive_ir_lib/ocr.py`, `dxf_builder_lib/builder.py`, `dxf_builder_lib/reviewer.py`, `scripts/verify.ps1`.
- Compatibility behavior: Preserves the existing `displayed-page-box-v1` schema, `visibility="unverified"`, `semantic_role=None`, hash-bound per-span approval requirement, raster `glyph_render` revalidation, and all existing `test_cad_agent_fidelity.py` fail-closed exclusions (including synthetic mock `get_bboxlog()` entries without matching `get_drawings()` records).
- Migration and rollback path: Single-module refinement in `cad_agent/fidelity.py` with no schema, dependency, or persistence changes; cleanly revertible via `git revert`.

## Thin-stroke preparation limits

The optional below-baseline veto preserves the R7 observation decision on unsupported evidence or exhausted preparation. It validates each matching font-resource alias before sharing a decoded program by stream reference. Distinct references must still supply identical bytes for a trace font name.

Per page, preparation examines at most 16 font-resource rows and attempts at most eight distinct program references. It retains at most 4 MiB of decoded program data and charges up to 10,000 stroke and outline operations before recording or forwarding them. It stops XML tree construction at the existing 10,000-node boundary and preserves the 4 MiB SVG output check, 64 attempted pairs and per-pair/page raster ceilings.

PyMuPDF materializes the full-page SVG and decoded font before their output sizes can be checked. FontTools can perform internal work before it emits metered operations. These in-owner limits bound the work and data they count. The upstream native memory and runtime residual remains Security finding SEC-578-R8-A1-02 pending independent disposition.

## Conservative dark-fill overlap

A verified dark fill is compared against the full glyph metric rectangles. A conflicting fill can be excluded from the overlap decision only when the single later paint sequence binds to an opaque, stroke-free path and every matched SVG and drawing component clears all relevant ink. Full glyph hulls cover control points from both the validated embedded TrueType GID and its uniquely matching SVG use, including supported horizontal and quarter-turn transforms. An empty glyph requires independently empty outlines. Each glyph and fill bound has at least 0.002 pt of padding. Any ambiguous binding, unsupported geometry, touching padded bounds, error, or exhausted budget keeps the metric veto. An unverified decomposition keeps the existing outer paint rectangle fallback.

The stroke and fill checks share one page preparation, program cache, and cumulative attempt and operation limits. Fill proof records no raster pixels and caches unavailable bindings for the current page. A positive fill separation addresses only that fill overlap. The span remains unverified and existing source-bound approval still applies.
