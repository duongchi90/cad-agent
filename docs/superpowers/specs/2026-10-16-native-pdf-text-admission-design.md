# Native PDF Text Admission Through Fidelity Review

**Approval date:** 2026-10-16 (delegated Local PO decision, same CASE06 decision chain)
**Supported scope:** private fidelity reconstruction output; explicitly selected, source-verified PDF text spans may be emitted as editable plain DXF `TEXT` through the existing fidelity approval and reconstruction owner.
**Decision:** Option B approved with the clarifications below. Implementation approval does not approve emission of any CASE06 source span.

## Goal

Let a reviewer select exact native PDF text spans after inspecting their source render, approve them individually, and reconstruct those approved spans as editable plain `TEXT` in the private fidelity DXF. Preserve the current OCR path and keep all unselected or unsupported text out of the DXF.

## Existing owner and boundary

Extend `cad_agent.fidelity`'s existing observation, review-selection, per-item approval, glyph-check, and `run_fidelity_text_reconstruct` flow. Native spans remain a separately typed collection in the existing private sidecar. Do not create a second approval/reconstruction workflow or alter Primitive IR, public schemas, or AutoCAD integration.

The approval action is the existing explicit per-item approval operation. Identity, author, timestamp, or visibility fields by themselves do not create authority. Each approved span's provenance must bind the exact source PDF, rendered page, stable span ID, content, bbox, and mapping. A selection is not approval until passed through the existing approval writer.

## Review and approval

- The review page presents the source render and visibly marks native span bboxes, with each exact span's content, stable ID, bbox, source font metadata, and separate selection control.
- A span enters that selectable collection only when normalized text and bbox overlap of at least 90% uniquely match one PDF paint trace that is actually painted, has nonzero opacity, uses horizontal writing mode, and is not overlapped by later page paint. Named or optional-content layers may be observed, but their layer name/state never proves user-visible legibility; every native span remains `visibility=unverified` until explicit per-span human review. Disabled optional-content spans omitted by the PDF backend remain excluded.
- If the text dictionary contains U+FFFD but the uniquely matched paint trace supplies a printable character at exactly the same compact-text position, the observation may use the trace-decoded character only when all other characters agree and the trace bbox still meets the 90% overlap rule. Record whether agreement was exact or recovered. Conflicting, ambiguous, differently sized, or unresolved mappings remain excluded; never infer semantic roles or join adjacent spans.
- Exported selection keeps OCR candidate IDs and native span IDs in distinct typed fields. Native selections carry the reviewed source/render identity and exact span snapshot.
- The approval writer rebinds each selected native span to the canonical current observation. It rejects an absent ID, duplicate ID, changed content/bbox/frame, stale source/render, or selection from another source/page.
- The exact span snapshot includes source writing mode and paint-trace type, opacity, layer, sequence number, and bbox. Fresh reconstruction re-extraction must reproduce that evidence.
- OCR approvals retain their current format and behavior. A mixed approval can contain both typed lists without treating native text as OCR.

## Reconstruction and mapping

Before output staging, reconstruction verifies the canonical observation and approval, freshly renders the hash-verified source page, checks the render pixels and audit frame, re-extracts native spans, and requires each approved span to match the exact reviewed snapshot. Selection records the human review of visibility for that exact source/render/span; bbox intersection and raster ink alone cannot promote visibility. The PDF paint trace is an independent eligibility check, so a hidden OCR text layer over visible raster lettering is not selectable as native text.

Map the PDF text baseline origin and direction into paper coordinates using the existing displayed-page transform and page scale. Map source font size through the same page scale and use the existing fidelity Unicode style/glyph-check owner. Record source font metadata and the deterministic output mapping in the reconstruction report. Reject invalid or unsupported values before creating the output directory. Do not claim source CAD style equivalence.

Emit one `TEXT` per approved span. Keep equal strings at distinct source positions as separate entities. Do not infer semantic role, dimension/component association, calibration approval, or higher CAD entity types. The existing OCR candidate list and OCR freshness checks remain unchanged.

## Failure behavior

Fail closed before output creation for stale or substituted source/render/span/paint evidence; unselected or duplicate span IDs; missing explicit item approval; hidden, ambiguous, later-obscured, clipped, off-page, zero-area, conflicting text mappings, or invalid spans; vertical writing mode; unsupported page transforms; invalid coordinate/font-size values; unsupported glyphs; or mismatched audit frame. A named layer is not itself grounds to infer visibility or reject an otherwise supported observation. Do not infer visibility from layer names, OCG state, or pixel content. Preserve existing output-root containment and no-overwrite checks.

## Verification

Focused regressions cover separate selection/approval provenance, selected-only native `TEXT` emission, baseline/direction/height mapping, duplicate strings at distinct positions, stale/forged/hidden/clipped/unselected evidence, zero opacity, invisible and clipping-only render modes, disabled optional-content layers where supported, later paint overlap, vertical writing mode, invalid transforms and glyph failures before output creation, and unchanged OCR behavior. Use synthetic private fixtures for tests; CASE06 emission remains unavailable until an authorized per-item source review occurs. AutoCAD/.NET and the context A/B benchmark are not prerequisites for this bounded private DXF owner change and must not be reported as run unless they are.

## Explicit exclusions

No automatic visibility inference, OCR relabeling, semantic-role inference, dimension or component association, `DIMENSION`/`MLEADER`/`MTEXT` generation, new trust/approval service, source/reference DWG access, candidate promotion, AutoCAD mutation, or change to PR #521's pinned head.

## CASE03 diagnosis clarification (2026-10-23)

The CASE03 source-only diagnosis established recoverable `639±1` and `415±1` text using rendered crops, texttrace glyphs, embedded-font ToUnicode mapping, and adjacent same-baseline span geometry. The existing observation path excluded these spans because it rejected named paint layers and treated the broader `get_bboxlog()` bounds of the following text operation as occlusion, even though the corresponding text-trace glyph bounds were merely adjacent. This clarification permits only uniquely mapped adjacent text-paint exceptions under the strict geometry/style limits below and records named-layer spans as unverified observations. A separate synthetic control covers U+FFFD recovery when the unique trace supplies the missing printable character. This does not assert OCG visibility, join tolerance spans, approve them, create semantic dimension associations, or connect them to Primitive IR.

The adjacent-paint exception is limited to a unique later `fill-text` operation bound by sequence number and a corroborating trace/paint bbox overlap of at least 85%. Stroke-text is excluded because paint bounds may expand far beyond glyph-trace bounds according to line width. The adjacent traces must share font, color, opacity, layer, horizontal direction, and baseline; font sizes may differ. Their trace bboxes may have a small horizontal gap or overlap, bounded by both 0.05 pt and 0.5% of the smaller font size, with no more than 0.5% relative area overlap and at least 95% vertical overlap. Any other overlapping paint, ambiguous operation mapping, mismatched style, substantial overlap, or degenerate bounds remains a refusal. The text spans remain separate and unverified.
