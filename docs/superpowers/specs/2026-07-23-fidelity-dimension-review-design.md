# Fidelity Dimension Review Design

**Status:** Approved by the user's 2026-07-23 confirmation to implement the
dimension workflow before linetypes and hatch.

## Scope

Add a private, review-first dimension workflow to the existing paper-coordinate
fidelity pipeline. It detects dimension-like OCR candidates and nearby
extension/leader geometry, records only candidates with their source evidence,
and provides a browser review artifact. It does not infer model dimensions,
modify existing layout DXFs, or invoke AutoCAD Mechanical.

## Design

1. `fidelity-dimension-observe` reads the hash-bound rendered page and existing
   OCR/geometry sidecars. It emits a per-page private JSON sidecar containing
   candidate text, pixel bounding box, nearby horizontal/vertical/diagonal line
   evidence, and a `needs_human_approval` state.
2. The observation identifies dimension-looking values conservatively: numeric
   values, diameter/radius prefixes, and values with basic unit markers. Every
   other text item remains ordinary OCR evidence rather than being relabelled as
   a dimension.
3. A static private review page renders page images with numbered candidate
   boxes and a table of candidate values and associated line evidence. It is
   visual evidence only and cannot write a DXF.
4. A later explicit dimension-approval/reconstruction slice may map selected
   candidates into DXF DIMENSION entities. That mapping is intentionally out of
   scope here because projection, baseline, arrow style, and semantic model
   dimensions remain ambiguous in a raster drawing.

## Safety and acceptance criteria

- All output remains outside Git, SHA-bound to the private PDF/rendered page,
  and marked `needs_review`.
- No candidate is emitted as a DXF DIMENSION, TEXT, or model constraint.
- Existing fidelity DXFs stay refused by Mechanical commands.
- Synthetic tests cover candidate filtering, source binding, duplicate-output
  refusal, and the browser review index. The approved private PDF runs the new
  observation command for all nine pages.

## Non-goals

This slice does not create production geometry, solve dimensions, infer scale,
apply linetype mappings, generate hatch, or mutate a customer drawing.
