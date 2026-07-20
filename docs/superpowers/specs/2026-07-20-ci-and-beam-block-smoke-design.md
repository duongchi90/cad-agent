# CI and Beam Block Smoke Design

## Goal

Continuously verify all offline phases on GitHub and prove that a semantic
`COMP_FRAME_BEAM` block with attributes survives a real AutoCAD File IPC
round trip.

## Scope

- Add one GitHub Actions workflow for Python 3.11. It installs project and
  optional solver dependencies, exposes Tesseract on Windows runners, and
  runs the existing full pytest command. Tests requiring AutoCAD remain
  skipped because `CAD_AGENT_FILE_IPC` is not set in CI.
- Extend the opt-in real-AutoCAD smoke test with one beam component built by
  the existing semantic-component builder. The test opens the DXF through
  `FileIPCLiveMCPClient`, verifies the inserted block name, layer, transform
  and attributes, deliberately damages one attribute, then repairs/reviews it
  through the existing component repair path.

## Boundaries

- The first real component is `COMP_FRAME_BEAM` only. Bracket, panel, hinge,
  and other block families are deferred to later independent smoke tests.
- CI has no AutoCAD, desktop HWND, or external vision/API credentials. It is
  a regression guard for offline code only.
- The smoke test stays opt-in and preserves the current File IPC bootstrap
  behavior for opening a fresh document.

## Verification

1. The workflow is syntactically valid and runs the offline pytest suite.
2. Unit tests cover any File IPC block/attribute mapping added for the smoke.
3. With AutoCAD, `CAD_AGENT_FILE_IPC=1`, a valid HWND and dispatcher path,
   the beam smoke runs build -> open -> review -> attribute mismatch -> repair
   -> final review successfully.
