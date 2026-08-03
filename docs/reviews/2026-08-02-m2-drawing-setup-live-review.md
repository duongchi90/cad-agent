# M2 Drawing Setup Live Review

Date: 2026-08-03

Candidate implementation head: `2ed26474059814068334074f3e1f6a9429ae13dd`

## Scope

This review covers the read-only `drawing_setup_audit` boundary, its Python
artifact normalization, the setup comparison/evidence gate, and the opt-in
AutoCAD Mechanical live test. No DWT, DWG, DXF, raw audit, customer data, or
profile metadata was added to Git.

The normalizer also excludes Model Space layouts without paper viewports from
the viewport-only audit contract; this keeps the recorded layout list valid for
comparison against approved paper-layout profile expectations.

## Offline evidence

- Release x64 .NET build completed with 0 errors. Existing Autodesk reference
  conflict warnings (`MSB3277`) remain; no Autodesk DLL was copied to output.
- C# tests: 73 passed, 0 failed, 0 skipped.
- `dotnet_ipc` JUnit: 37 tests, 0 failures, 0 errors, 0 skipped.
- Offline JUnit: 515 tests, 0 failures, 0 errors, 0 skipped; 18 subtests also
  passed.
- Private-data unavailable probe: 2 skipped as expected.
- AutoCAD Mechanical unavailable probe: 8 skipped as expected.
- The authoritative verifier completed successfully and preserved a clean
  repository snapshot.
- The live prerequisite contract now requires an existing
  `CAD_AGENT_M2_DISPOSABLE_DWG`, so a missing or removed disposable drawing is
  reported as an unavailable-state skip rather than a runtime `KeyError`.

## Live gate state

**NOT RUN.** The required operator-controlled File IPC variables and disposable
drawing were not supplied in this session. The opt-in live collection ran as
the explicit unavailable-state probe: 2 selected live tests, both skipped.

Consequently, no `SETUP_VERIFIED` evidence, approved template/profile metadata,
or eleven-drawing candidate audit was claimed. A future operator run must
provide the approved DWT, open a disposable drawing in AutoCAD Mechanical 2027,
run the setup audit, verify unchanged source SHA-256 and DBMOD, and close
without saving before this gate can become PASS.
