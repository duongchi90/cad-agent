# Fidelity Linetype Reconstruction Design

## Purpose

Turn reviewed, hash-bound dashed-line observations into a private DXF candidate
that is closer to the approved PDF layout while preserving geometry and the
`needs_review` state.

## Scope

For one page, validate the manifest, rendered-page-bound linetype observation,
and existing private paper-coordinate DXF. Create a fresh DXF and define
`FIDELITY_DASHED` when needed. Apply it only to existing horizontal LINE
entities whose paper-space Y coordinate matches an observed dashed pattern
within a pixel-derived tolerance.

The report records matched patterns, changed entity counts, and source,
observation, and render hashes. It always stays `needs_review`.

## Exclusions and verification

The workflow creates no geometry, model, text, dimension, hatch, or Mechanical
mutation. Tests prove matching horizontal lines change, other lines do not,
and mismatched hashes or non-private paths are rejected. The private nine-page
run is diagnostic evidence, not a visual-fidelity pass.
