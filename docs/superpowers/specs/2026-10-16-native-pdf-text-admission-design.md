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

## AIGDT GID 80 observation amendment (2026-10-25)

**Approval:** bounded design approved by the Local PO for the exact B041 embedded-font profile. This approves an unverified observation mapping in this existing fidelity workflow only; it does not approve automatic admission, span merging, visibility exceptions, or native CAD output.

**Frozen evidence:** B041 PDF SHA-256 `bf853aee4ba9b8381476d5ef1fa930d48a478ea56c3fe097695d41210d3afbe3`; rendered page SHA-256 `48a28aeb82c7e819d04ac0175c0189bceec790ea2f10af99d739c1882f36c7e8`; embedded AIGDT FontFile2 SHA-256 `aac3c6c7451139928755b08a4bc193a63ed93b51df58ed2fdd559c450696029b`. Its unique Windows Symbol cmap format-4 table (platform 3, encoding 0) maps U+F06E to `uniF06E`, which is GID 80; rendered source glyph crops show the diameter symbol. The resolver is specific to these exact embedded bytes and this GID/cmap mapping. Font name, PUA codepoint, or numeric GID alone is not sufficient.

The observation preserves the original raw character (`n`), mapped display content (`⌀`), unique font resource and byte fingerprint, cmap/GID/glyph-name evidence, exact source span and text-trace identity, source/render hashes, transform, and paint sequence. It remains `visibility=unverified` and requires the existing explicit per-span review, fresh reconstruction, and approval gates. Preserve the current later-paint eligibility rule: B041 traces 266 and 336 have later neighboring `fill-text` overlaps of 0.0252 and 0.03492 and remain excluded; trace 321 has no later paint overlap and is the only candidate eligible under the current pipeline. `LATER_PAINT_SCREEN_ELIGIBLE=1 (STATICALLY_ANALYZED)`; `CURRENT_PIPELINE_ELIGIBLE_COUNT=NOT_RUN` until the exact PR branch test runs.

No adjacent spans are joined. No OCR/PDF conflict rule changes; no complete diameter label is synthesized from the symbol plus OCR digits. No `DIMENSION` semantics are inferred. Unknown or ambiguous font resources, changed bytes, missing/duplicate traces, altered glyph IDs, or mismatched cmap fail closed for this special mapping. Other fonts retain existing behavior.

Source rights remain limited to private, noncommercial use. No S2C2 source is copied. Public redistribution rights are not established; the implementation is independent and this profile-specific mapping does not import external code.

Before this profile can be selectable or emitted, use the existing clipping, opacity, optional-content and paint-order controls and add current-head checks for font-resource ambiguity and the real B041 source. Nested-group/non-normal-blend contexts remain unsupported and must not be described as verified by this profile.
