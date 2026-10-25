# Dimension source LINE overlap policy

Status: approved for additive builder-only implementation on 2026-10-14 by
Local GPT-6.1-Sol; authority is [#491 comment 6161127223](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6161127223),
amending design [#491 comment 6161032166](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6161032166).

## Supported scope

`dxf_builder_lib.builder.build_dxf` may expose an exact opt-in
`avoid_source_line_overlap_v1` policy for placing generated linear DIMENSIONs.
Omitting the policy preserves the current `legacy` placement and existing
callers. The policy tries the current side first and then the opposite side at
the same existing offset. It preserves source LINE endpoints and native
measurement.

The collision predicate is limited to positive-length collinear overlap between
rendered DIMENSION LINE graphics and written source LINE geometry. It uses
1e-6 drawing millimetres only as a numerical comparison tolerance, not as
clearance. Zero-length comparison segments and point-only endpoint contact do
not count as positive overlap. Invalid/nonfinite required LINE geometry,
unreadable enumeration, or both sides blocked fail closed before saving.

Source CIRCLE, ARC, TEXT, SOLID and rendered non-LINE dimension graphics may
coexist but are outside this predicate. The policy does not claim general
collision-free placement, visual legibility, crossing detection, dimension-to-
dimension clearance, or paper-space quality. No CLI/pilot caller is switched by
this design; no schema, result fields, dependency, subsystem, new offset, or
source-geometry movement is allowed.

Candidate renders use isolated in-memory serialized copies of the complete
current DXF drawing/resources. The output drawing receives only one accepted
final DIMENSION render; trial dimensions/anonymous blocks never enter it.
