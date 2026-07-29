# Review-only fidelity hatch reconstruction

## Goal

Turn only explicitly approved hatch polygons into native DXF `HATCH`
entities while keeping automatic diagonal-stroke observations and production
drawings outside the mutation path.

## Scope and boundary

`fidelity-hatch-observe` remains observation-only. Approval records identify a
candidate, provide a polygon inside that candidate's observed bounding box,
and bind both the observation and the chosen base DXF by SHA-256.
Reconstruction clones the base DXF, appends ANSI31 entities on
`FIDELITY_HATCH`, writes a revisioned private candidate, and records
`needs_review`.

Automatic flood fill, inferred closed regions, production drawing mutation,
and text/font reconstruction are outside this slice.

## Data flow

1. Observation assigns stable `hatch-NNN` candidate identifiers and records
   render-bound candidate boxes.
2. Approval validates numeric, non-degenerate polygons against the rendered
   page and candidate boxes; it records the observation and base-DXF hashes.
3. Reconstruction revalidates the complete approval contract, including all
   polygon geometry and both bound artifacts, before opening the DXF.
4. Pixel points are converted to paper coordinates using the page scale and
   render height. Only approved polygons are emitted.
5. A revisioned report records input/output hashes, emitted handles, and the
   unresolved visual-review boundary.

## Safety contract

- All inputs and outputs reside inside the private fidelity root, which must
  remain outside the Git worktree.
- Source, render, observation, and base DXF hashes must match.
- Candidate ids are unique and every point remains inside the corresponding
  observed bounding box.
- Approval reference, angle, and positive pattern scale are mandatory.
- Reconstruction never overwrites the base DXF and never produces a
  production-approved state.

## Verification

Focused tests cover valid reconstruction, the CLI path, base-DXF mismatch,
tampered observations, duplicate candidates, and modified approval polygons.
Full offline, private-PDF, and live Mechanical gates must pass before release
documentation is closed.
