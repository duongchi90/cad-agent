# DXF Millimetre Unit Admission — Execution Plan

**Status:** Package complete (canonical offline verifier PASS; specialized gates NOT RUN)
**Approval date:** 2026-10-14
**Approval:** Local Sol, [#491 comment 6162442781](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6162442781)
**Base SHA:** `7da1ed42a2168b5c991fc389a4c8155b1e88a387`
**Completion Head SHA:** `ca0cdbf5288b23d59abf3f5231366e7b15bce1a3`

## Current execution checkpoint

The focused standalone GREEN command remains **UNKNOWN** because its original invocation did not retain an exit code or completion artifact. It was not repeated. The later canonical verifier independently executed all eight unit-contract regressions successfully; record `FOCUSED_STANDALONE=UNKNOWN` and `REQUIRED_REGRESSIONS_VIA_CANONICAL=PASS`.

The frozen five-file change is at implementation checkpoint `ca0cdbf5288b23d59abf3f5231366e7b15bce1a3` (tree `71437da956b433959ede1f7a852733624ea0e64e`). Ruff exit was 0; the plan whitespace correction passed cached `git diff --check` with exit 0.

Canonical verifier ran once under PID 6760 and exited 0 after 201.3 seconds. Offline suite: 3,638 passed, 23 deselected, 77 subtests passed; JUnit summary: 3,715 tests, 0 failures/errors/skips. The XML contains 3,638 testcases, including all 8 unit-contract regressions and cases from `tests`, `primitive_ir_lib`, `semantic_ir_lib`, `dxf_builder_lib`, `mcp_integration_lib`, and `agent_lib`.

Evidence: `D:\Cad agent temp\dxf-mm-canonical-qualified-20261014-140424` (durable START, stdout/stderr, and COMPLETION exit record). HEAD/tree/status were unchanged and clean after verification.

AutoCAD/.NET was explicitly skipped. Real-data, AutoCAD live, and native gates remain NOT RUN; this package does not claim release acceptance.

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

**Canonical verifier result:** PASS (exit 0; 3,638 passed, 23 deselected, 77 subtests passed; offline JUnit summary 3,715 tests, 0 failures/errors/skips).
**AutoCAD/.NET:** NOT RUN (explicitly skipped by verifier invocation).
**Real-data/native:** NOT RUN; no such gate authorized by this package.
**Merge/ready:** not authorized.
