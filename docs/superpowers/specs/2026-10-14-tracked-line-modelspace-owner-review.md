# Tracked LINE ModelSpace Owner Review

**Approval date:** 2026-10-14  
**Supported scope:** Offline DXF review of raw LINE primitives emitted and tracked by the current builder. This does not establish native, private-input, or general PaperSpace support.

## Approved contract

`dxf_builder_lib.builder` emits tracked Primitive IR LINE entities directly into the DXF ModelSpace block record. `dxf_builder_lib.reviewer.review_dxf` must therefore reject a tracked raw LINE unless the saved and reopened entity is both owned by the current document's ModelSpace block record and present in that ModelSpace layout.

The check applies only to tracked raw LINE primitives, after the reviewer resolves the tracked handle and confirms the expected DXF type. An absent, unreadable, or mismatching owner fails closed with a normal mismatch naming the primitive, handle, expected ModelSpace owner, and actual owner. Existing handle, type, layer, geometry, finite tolerance, report fields, and signatures remain unchanged.

`strict_primitive_inventory=False` remains the default. Optional strict inventory retains its whole-ModelSpace semantics: default review may accept an unrelated extra ModelSpace entity, while strict inventory rejects it. No other entity type or layout behavior changes.

## Evidence and reuse

- Main/tree: `c80303aa841980138c18b170162386f6d5eb3a5a` / `d47db24cb8a809eda1efbe75d10d4209409e6c9f`.
- Measured discriminator: #491 comment `6167999535`; the same saved/reopened tracked LINE retained its handle and geometry after moving to PaperSpace, default review passed, and the existing strict inventory failed.
- Source/caller audit: #491 dossier `6168079243`, scratch design SHA256 `21aa511072d00f46eb8fea994809c0894a8cf7bff6fd9f2c03ff7850eb0b744b`.
- PO approval and execution authority: #491 comment `6168129019`.
- Reuse existing ezdxf layout membership and DXF owner APIs plus the reviewer's existing owner-aware contour/dimension patterns. Do not add a DXF parser, schema, flag, CLI policy, or activate whole-inventory validation by default.

## Verification and limits

Use saved/reopened PaperSpace and owned-block layout LINE regressions, plus a narrowly controlled readback seam for absent/unknown owner references that DXF serialization cannot reliably preserve. Preserve candidate bytes during review. Verify ordinary ModelSpace acceptance, existing missing-handle/type/layer/endpoint checks, default acceptance of an unrelated extra ModelSpace entity, and strict rejection of that extra entity.

This scope is offline candidate acceptance only. AutoCAD, native, private drawing, and live-promotion gates are not authorized and remain NOT RUN.
