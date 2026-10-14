# DXF Millimetre Unit Admission — Execution Plan

**Status:** Executing
**Approval date:** 2026-10-14
**Approval:** Local Sol, [#491 comment 6162442781](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6162442781)
**Base SHA:** `7da1ed42a2168b5c991fc389a4c8155b1e88a387`
**Completion Head SHA:** pending implementation commit

## Current execution checkpoint

Steps 1–3 are recorded in GitHub authority comment #491/6162442781; the
causal RED was observed against the unchanged base. The first focused GREEN
command reached pytest's 100% progress display, but its command session ended
without a captured summary or exit code. A bounded process check confirmed the
pytest process is no longer live. Result is **UNKNOWN**, not PASS or FAIL; do
not repeat the same test oracle without a new Local Sol decision.

## Approved scope and reuse

Only these paths may change:

- `dxf_builder_lib/builder.py`
- `dxf_builder_lib/tests/test_builder_unit_contract.py`
- `dxf_builder_lib/README.md`
- `docs/superpowers/specs/2026-10-14-dxf-mm-unit-admission.md`
- `docs/superpowers/plans/2026-10-14-dxf-mm-unit-admission.md`

Reuse the existing `build_dxf()` status gate, `$INSUNITS=4` contract, and tests for builder, dimensions, solved geometry, and semantic components. Add one exact-mm admission guard. Do not normalize coordinates: solved and semantic inputs can carry mm-valued contracts independent of the calibration label. No adapter, schema, dependency, or owner-boundary change.

## Ordered execution

1. **Admission and authority:** clean detached exact-main workspace, exact base/tree and source blobs; create `codex/dxf-mm-unit-admission-v1`; publish/read back the Local Sol design and reuse authority.
2. **Causal RED:** add cm/m and malformed/unknown rejection tests. Require rejection before output directory/file creation, preserve an owned scratch sentinel and input primitive handle, and preserve unverified-calibration error precedence. Run the new test module on current code and record the expected red result.
3. **Minimal guard:** after the existing status check and before construction/mutation, require `primitive_doc.calibration.unit == "mm"`; use a descriptive explicit-conversion error. Preserve `$INSUNITS=4` and mm output.
4. **Focused GREEN:** run the new unit-contract tests plus existing builder/dimension/solved/component tests. Run Ruff for touched Python and `git diff --check`.
5. **Implementation commit:** commit only the approved five paths after focused checks pass.
6. **Canonical verification:** run exactly once on the clean implementation commit:

   ```powershell
   .\scripts\verify.ps1 -PythonExe 'C:\cad-agent\.venv-py311\Scripts\python.exe' -SkipAutoCADDotNet
   ```

   Record actual child exit and durable completion/output. Require unchanged clean HEAD/tree/status before and after. Failure or unknown stops this package; no repair or retry.
7. **Close and receipt:** only after verifier PASS, update this plan with the implementation completion SHA and exact result; make at most one plan-only lifecycle commit. Publish/read back one compact #491 receipt. Do not push or open a PR.

## Stop conditions and gates

Stop on identity drift, an unintended RED, failed focused compatibility, unexpected source mutation, canonical failure/unknown, or the 60-minute package budget. Coordinate conversion is forbidden. No real-data, AutoCAD, or native run is authorized; record those as not run. PR509 and its pending reviews/checks remain untouched.

**Canonical verifier result:** not run yet.
**AutoCAD/.NET:** not run (explicit skip planned).
**Real-data/native:** not run; no such gate authorized.
**Merge/ready:** not authorized.
