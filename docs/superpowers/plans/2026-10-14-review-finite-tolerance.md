# Finite Review Tolerance Admission Implementation Plan

> **For agentic workers:** Execute this approved plan inline, task by task. Keep the five-path write set and PO stop conditions.

**Goal:** Prevent invalid `tolerance_mm` values from letting `review_dxf` report geometric PASS.

**Architecture:** Add a small pre-import/pre-read admission check to the existing reviewer entry point. Use owned regressions to prove invalid policy fails before file access and valid policy preserves current behavior.

**Tech Stack:** Python 3.11, pytest, existing `math.isfinite`, Ruff.

**Spec:** `docs/superpowers/specs/2026-10-14-review-finite-tolerance.md`.

## Global Constraints

- Status: completed.
- Base SHA: `7da1ed42a2168b5c991fc389a4c8155b1e88a387`.
- Completion Head SHA: `6eef0f3f071255f2799f7dd2a3613c225a363232` (implementation/evidence commit before plan-only close).
- Verification command: `scripts/verify.ps1 -PythonExe 'C:\cad-agent\.venv-py311\Scripts\python.exe' -SkipAutoCADDotNet`; PASS, exit 0, completed in 225.57 seconds.
- Required native/private/live gates: AutoCAD .NET, AutoCAD live, M2, real-image, and fidelity private-data gates are NOT RUN/SKIPPED as unavailable and out of scope.
- Preserve signature, default, result/schema, and existing finite comparison behavior; introduce no max tolerance or dependency.
- Do not rerun the completed discriminator; no real/private drawing, AutoCAD/native action, push, PR, CI/review request, merge, or held-PR mutation.

## Review Focus

- NaN or infinity must not turn a mismatch comparison into false PASS.
- Negative tolerance must be rejected before reading a path.
- Boolean must not be accepted through Python's `bool`-is-`int` relationship.
- Nonnumeric input and huge integer overflow must raise descriptive `ValueError` before I/O.
- Default, zero, positive integer and positive float tolerances preserve existing results.

## Exact write set

- `dxf_builder_lib/reviewer.py`
- `dxf_builder_lib/tests/test_review_tolerance_contract.py`
- `dxf_builder_lib/README.md`
- `docs/superpowers/specs/2026-10-14-review-finite-tolerance.md`
- `docs/superpowers/plans/2026-10-14-review-finite-tolerance.md`

## Ordered execution

1. Re-admit exact base/tree/reviewer blob in the isolated branch; preserve receipt #6164170628 and its immutable evidence hash.
2. Add admission-only regression cases using a nonexistent DXF path; run the subset on unchanged production and observe the intended `ValueError` failure.
3. Add pre-import/pre-read validation using `math.isfinite`, rejecting invalid types/values and overflow without string coercion.
4. Run focused GREEN for invalid types/values, default/zero/positive controls, ordinary altered-DXF rejection, and the measured NaN bypass; run affected reviewer/caller contracts, touched Ruff, and `git diff --check`, recording actual exits.
5. After focused/static PASS and exact five-file residual, make one scoped implementation commit.
6. Run the canonical verifier exactly once with the command above. Capture child exit and clean before/after identity; failure or UNKNOWN stops without retry or repair.
7. Only after PASS, close the plan with at most one plan-only commit; prove source/test bytes unchanged, publish/read back one #491 receipt, and return to PO.

## Execution evidence

- Step 1: PASS. GitHub `origin/main` was `7da1ed42a2168b5c991fc389a4c8155b1e88a387`; exact tree was `de41dc0707f695c085f0e40218d240e78cebdb8a`; reviewer blob was `b2f78e7e207bb9586c7a837074f26775dd2fb5ab`. The isolated worktree was clean before the branch `codex/review-finite-tolerance-v1` was created. Authority was published/read back as Issue #491 comment 6164281750.
- Step 2: RED observed. The new admission subset produced 9 failures because invalid values reached `ezdxf.readfile()` and raised `FileNotFoundError` instead of `ValueError`.
- Steps 3–4: focused GREEN: `python -m pytest dxf_builder_lib/tests/test_review_tolerance_contract.py dxf_builder_lib/tests/test_reviewer.py dxf_builder_lib/tests/test_builder.py dxf_builder_lib/tests/test_repair.py agent_lib/tests/test_run.py tests/test_cad_agent_cli_staged_semantic_policy.py tests/test_dimension_pilot_contracts.py -q` — 137 passed. Touched Ruff and `git diff --check` passed.
- Step 6: PASS. Offline verifier reported 3,645 passed, 23 deselected, 77 subtests passed; JUnit 3,722 tests, zero failures/errors/skips. The verifier also ran its separate causal-RED negative oracle, which reported its expected single failing assertion. Unavailable-state probes recorded real-data 2 skipped and AutoCAD 18 skipped; AutoCAD .NET was explicitly NOT RUN. The script ended `Verification complete`, exit 0, with unchanged head/tree and clean status before/after.
- Step 7: implementation commit `6eef0f3f071255f2799f7dd2a3613c225a363232`; plan-only close and GitHub receipt are the remaining actions.

## Stop conditions

Identity drift; unintended RED; numeric compatibility ambiguity; scope expansion; failed/UNKNOWN verification; or 60-minute package budget expiry. Return to PO without retry.
