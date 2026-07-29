# Review-only fidelity dimension reconstruction

## Goal

Add an explicit, review-only path that turns a human-approved dimension
observation into a native DXF `DIMENSION` entity while keeping OCR guesses and
production AutoCAD drawings outside the automatic mutation path.

## Scope and boundary

The existing `fidelity-dimension-observe` command remains conservative: it
detects numeric OCR candidates and nearby geometry, but it does not emit CAD
entities. The new reconstruction step consumes a hash-bound approval file and
a hash-bound base fidelity DXF. It writes a new private candidate DXF and a
`needs_review` report; it never overwrites the base DXF, the source PDF, or a
production drawing.

This slice handles linear dimensions supported by two endpoints of an observed
line. Diameter, radius, angular, ordinate, chained, and tolerance dimensions
remain observations until a separate mapping design exists.

## Data flow

1. `fidelity-dimension-observe` stores stable line evidence for every nearby
   candidate: line id, pixel endpoints, bounding box, and pixel length. The
   evidence is part of the source-render-hash-bound observation.
2. A reviewer creates an approval JSON containing the page, candidate id,
   selected line evidence id, approval reference, and the observation hash.
3. `fidelity-dimension-reconstruct` validates source, page render,
   observation, approval, and base-DXF hashes. It rejects unknown candidates,
   mismatched line evidence, non-linear dimension kinds, and duplicate output
   paths.
4. The command converts the approved pixel endpoints using the page's
   paper-coordinate scale and places a native linear `DIMENSION` with a stable
   normal offset derived from the OCR box. It preserves all base entities and
   adds the new entities on `FIDELITY_DIMENSIONS`.
5. The report records all input/output hashes, selected mappings, entity
   count, and the unresolved review boundary.

## Approval contract

```json
{
  "schema_version": "fidelity-dimension-approval-1.0",
  "private_artifact": true,
  "state": "approved-dimension-mappings",
  "source": {"name": "drawing.pdf", "sha256": "...", "kind": "pdf"},
  "page": 1,
  "observation": {"path": "fidelity_dimension_observations/page_01.json", "sha256": "..."},
  "approval_reference": "review-2026-07-29",
  "mappings": [
    {"candidate_id": "dimension-1", "line_evidence_id": "line-1"}
  ]
}
```

The command accepts an approval path only inside the private fidelity output
root. The base DXF must also be inside that root, and the output is revisioned
if a page candidate already exists.

## Error handling and safety

- Any source/render/observation/approval/base-DXF hash mismatch fails before
  reading or writing a DXF result.
- A candidate may map to only one line evidence record, and a line evidence
  record may be used only once per approval.
- Invalid geometry, unsupported dimension kind, missing fields, or an empty
  mapping list raises `FidelityError`.
- The report state is always `needs_review`; the result is not accepted by
  Mechanical production review or repair commands.

## Verification

Focused tests must prove stable evidence is persisted, valid approval emits a
native `DIMENSION` while preserving base entities, and source/observation/
mapping/hash failures refuse reconstruction. The full offline verifier and
Ruff gate must pass after implementation.
