# INSERT Finite Scale Review Repair Plan

> Execute only the PO-authorized package in Issue #491 comment 6165085191.

**Goal:** Reject nonfinite INSERT scale operands in the existing headless DXF reviewer while preserving finite scale behavior.

**Architecture:** Reuse `dxf_builder_lib.reviewer._scalar_matches` at the existing x/y/z INSERT scale comparison. No new owner, dependency, schema, or comparison framework.

**Status:** Complete — scoped implementation and qualified-host canonical verification recorded below; native/private gates remain out of scope.

**Base SHA:** `7da1ed42a2168b5c991fc389a4c8155b1e88a387`.

**Base tree:** `de41dc0707f695c085f0e40218d240e78cebdb8a`.

**Branch:** `codex/insert-finite-scale-review-v1`.

## Exact write set

- `dxf_builder_lib/reviewer.py`
- `dxf_builder_lib/tests/test_reviewer.py`
- `dxf_builder_lib/README.md`
- `docs/superpowers/specs/2026-10-14-insert-finite-scale-review.md`
- `docs/superpowers/plans/2026-10-14-insert-finite-scale-review.md`

## Ordered execution

1. Re-admit the exact base/tree/reviewer blob, clean branch/worktree, Windows Python 3.11 and ezdxf 1.4.4. Preserve probe receipt #6165017633 and all held PRs.
2. Record the approved narrow reuse design. Add tests using `_build_beam_component`: persisted/reopened actual NaN and ±infinity for each of x/y/z scale; nonfinite expected values separately; finite equality, within-default-tolerance and outside-default-tolerance cases. Assert exact mismatch field, persisted input, and unchanged DXF bytes after review.
3. Run the new regression selection once before production edit. Require actual NaN cases to fail because review passes incorrectly; serialization/import/dependency/other failures stop.
4. Replace only the INSERT scale-loop predicate with `_scalar_matches(actual_val, expected_val, tolerance_mm)`. Preserve mismatch construction and finite behavior.
5. Run focused `test_reviewer.py`, `test_semantic_components.py`, and `test_builder.py` once; run Ruff on changed Python files and `git diff --check`. Use D: scratch basetemp and durable UTF-8 outputs; require no unavailable-dependency skips and exact five-path scope.
6. After focused/static PASS, create one scoped implementation commit. Resolve and prove the existing PowerShell launcher before invoking `scripts/verify.ps1` exactly once with `-PythonExe 'C:\cad-agent\.venv-py311\Scripts\python.exe' -SkipAutoCADDotNet`. Supervise the child, capture PID, output, actual exit and before/after identity. Require exit 0 and unchanged clean status.
7. Only after canonical PASS, update this plan with completion evidence and make one plan-only closure commit. Prove production/test bytes match the verified implementation. Publish and read back one compact #491 receipt, then return to PO.

## Verification record

- Existing evidence: causal discriminator in #491 comment 6165017633; exact main/tree and reviewer blob were admitted by package authority #6165085191.
- Exact implementation: `d1760030089f5e2e173fd8162af3680d4af72448` (tree `0de69a4109c146bf58f5b3a2e17c48c04d0e3ee7`), parent exact base `7da1ed42a2168b5c991fc389a4c8155b1e88a387`; the five-path scoped implementation commit remained clean and unchanged through canonical verification.
- Prior Windows PowerShell verifier preflight: PID 15280, exit 1, `Get-FileHash` unavailable, no tests ran. Preserved log hashes: stdout `183DBCA813E12F5A7814B794B88E902AB94A67C1608523A34BF40C7317D24EAA`; stderr `61A10F2A9EEA8498FAFA5D20850D5274A5A0108F821C723CB03990A6BADED60A`.
- Distinct existing PowerShell Core qualification: PID 13888, exit 0; PowerShell 7.6.5, PSEdition Core; `Get-FileHash` resolved to the Microsoft.PowerShell.Utility cmdlet; lock hash matched independent Python SHA256 `D4739CC0C3B523AB11069178680F534FA436E4E64E30E07C30D1F07E652D784D`. Core executable SHA256 `362A356CE7F0940EC74F73A8FC2C990A2CC24A38A11C90BBD8ECA947110AD139`; inherited `PSModulePath` was unchanged before canonical verification.
- One qualified-host canonical run: PID 20884, exit 0, completed `2026-10-14T09:33:39.556438+00:00`; `scripts/verify.ps1 -PythonExe C:\cad-agent\.venv-py311\Scripts\python.exe -SkipAutoCADDotNet`. Offline suite: 3657 passed, 23 deselected, 77 subtests passed; JUnit reported 3734 tests, 0 failures/errors/skips. The verifier's intentional causal-RED negative oracle reported its expected one failing assertion and was recognized by the verifier; the overall canonical process exited 0 with `All checks passed!`.
- The real-data unavailable probes reported 2 skipped because their private inputs were not configured. AutoCAD live tests reported 18 skipped and the AutoCAD live marker was NOT RUN. These gates are not passed or implied by the offline run.
- Canonical stdout/stderr and qualification evidence are preserved under `D:\Cad agent temp\insert-scale-canonical-host-qualification-v1`; the prior failed-run evidence remains unchanged.
- Required AutoCAD/.NET/live/private and configured real-data gates: NOT RUN; out of scope for this headless reviewer repair. Return to PO is required before any GitHub receipt or review/promotion action.

## Stop conditions and exclusions

Stop on identity/runtime/blob drift, unexpected RED, failed or unknown focused/static/canonical verification, scope expansion, launcher failure, or budget expiry. No retry of the discriminator or verifier. No rotation/other-field or tolerance-policy repair, dependencies/environment changes, STATUS.md edit, drawing/native action, held-PR mutation, push/PR creation, CI/reviewer polling/resend, ready or merge.