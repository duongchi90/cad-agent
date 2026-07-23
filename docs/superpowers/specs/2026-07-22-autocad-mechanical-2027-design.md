# AutoCAD Mechanical 2027 Target Design

**Status:** Approved by the user on 2026-07-22

**Target:** Windows, Python 3.11, AutoCAD Mechanical 2027

## Decision

Replace the supported live-CAD target, previously AutoCAD LT, with AutoCAD
Mechanical 2027. The available AutoCAD Mechanical 2027 session has passed the
existing File IPC smoke suite, while no AutoCAD LT session is available.

## Scope

- Update the supported-environment metadata and canonical documentation to
  AutoCAD Mechanical 2027.
- Rename the pytest live marker from `autocad_lt` to `autocad_mechanical` and
  update the authoritative verifier, live tests, and contract tests together.
- Preserve the File IPC protocol and test semantics: a live smoke run still
  uses only disposable DXFs under `C:\temp`, verifies review/repair, and never
  saves a production drawing.
- Retain historical records verbatim where they name the prior `autocad_lt`
  unavailable-state probe; new status evidence distinguishes those records from
  the current AutoCAD Mechanical gate.

## Out of scope

- No recognition, calibration, geometry, DXF, File IPC protocol, or AutoCAD
  mutation algorithm changes.
- No support claim for AutoCAD LT, other full AutoCAD editions, or a broader
  version range than the observed AutoCAD Mechanical 2027 session.

## Acceptance criteria

1. Every current canonical environment document and the project metadata name
   AutoCAD Mechanical 2027.
2. `autocad_mechanical` is the only registered live marker and the verifier
   probes it safely when prerequisites are removed.
3. The four live File IPC tests pass against AutoCAD Mechanical 2027.
4. The full offline verification gate passes, with the renamed live marker's
   unavailable-state probe reported as `SKIP` when its variables are removed.
