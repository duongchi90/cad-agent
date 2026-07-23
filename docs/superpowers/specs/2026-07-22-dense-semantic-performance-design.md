# Dense Semantic Compound Performance Design

**Status:** Approved by the user's optimization request on 2026-07-22

## Evidence

The approved nine-page PDF `202607092308.pdf` produced 1,170 primitives on
page 1 (1,116 lines) and 538,983 detected constraints. Its Semantic IR without
compound inference is 175 MB. The current rectangle recognizer compares every
parallel pair with every other parallel pair, so it does not reach a checkpoint
on this page after the constraint stage completes.

## Goal

Make compound recognition scale with the topology that can actually satisfy a
compound rule, while preserving the rule outputs for existing drawings.

## Design

- Index each constraint type into unique unordered primitive pairs once.
- For a rectangle, the opposite pair can only consist of lines coincident with
  one of the first pair. Enumerate those local neighbors rather than the full
  Cartesian product of all parallel pairs.
- For an L-bracket, inspect only pairs that are both perpendicular and
  endpoint-coincident.
- For a hinge, inspect only already-detected parallel pairs.
- Do not change constraint detection, calibration, confidence calculations,
  compound selection, or DXF output schemas.

## Acceptance criteria

1. Existing compound-recognition regressions preserve their expected parts.
2. A dense set of unrelated parallel lines completes compound recognition
   quickly and produces no false compound parts.
3. The approved PDF page 1 reaches a Semantic checkpoint with compound
   inference enabled.
