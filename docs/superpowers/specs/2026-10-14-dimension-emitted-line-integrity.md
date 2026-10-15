# Dimension Emitted-Line Integrity

**Approval:** Local GPT-6.1-Sol, 2026-10-14; Phase A authority is recorded in [#491 comment 6161862704](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6161862704).

## Supported scope

Add an opt-in, ephemeral integrity capture for builder-generated linear DIMENSION entities. It verifies that each emitted dimension's anonymous block retains the exact LINE inventory captured immediately after `render()` and before saving. It supplements existing semantic/dimension review; it does not replace or upgrade the existing review result.

`build_dxf(..., capture_dimension_line_integrity=True)` requires `build_dimensions=True`. Capture is bounded to 256 dimensions and 64 LINE entities per dimension. Unsupported, malformed, incomplete, or over-limit capture fails before save. A zero-dimension result cannot qualify.

The separate `review_dxf_with_dimension_line_integrity(build_result)` reports `QUALIFIED`, `FAILED`, or `UNKNOWN`. Qualification requires both the unchanged existing semantic/graphics review and complete line-inventory equality on the same loaded DXF document. Expectations are immutable, in-memory evidence and are excluded from existing evidence serializers. Serialized/reconstructed or legacy results cannot qualify.

Supported frame: builder-generated linear DIMENSION base type 0, default +Z extrusion, zero anonymous-block base point, and no dimension insertion transform. Compare 3D endpoints in the anonymous-block frame using 1e-6 mm Euclidean tolerance. Endpoint order is irrelevant; line multiplicity is preserved with deterministic one-to-one matching. Unsupported frame/type or ambiguous/missing identity is UNKNOWN. A missing, extra, or altered LINE is FAILED.

No public schema, evidence version, legacy `review_dxf` behavior, `ReviewResult`, consumer activation, persistence qualification, or DXF production policy changes are in scope. No real/private drawing, AutoCAD/native action, tolerance tuning, second renderer, or unrelated owner is authorized.
