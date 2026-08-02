# Hosted CI AutoCAD Gate Design

**Date:** 2026-08-03  
**Status:** Approved for implementation

## Context

The `tests` workflow runs `scripts/verify.ps1` on a GitHub-hosted Windows runner. Commit `26c70ec` later made that verifier build and test `autocad_plugin/CadAgent.AutoCAD2027.sln` unconditionally. The AutoCAD project resolves `AcCoreMgd.dll`, `AcDbMgd.dll`, and `AcMgd.dll` from a local AutoCAD 2027 installation, which the hosted runner does not have.

As a result, pull requests now fail before the Python/offline verification starts. PR #6 only adds documentation, but it exposes this existing CI configuration mismatch.

## Goals

- Keep the complete AutoCAD .NET restore/build/test gate enabled by default.
- Let GitHub-hosted CI run every verification gate it can actually satisfy.
- Report the hosted AutoCAD .NET gate as explicit `NOT RUN`, never as a pass.
- Preserve the existing pinned GitHub Actions and least-privilege permissions.
- Produce a green hosted CI result only after the Python/offline suite, unavailable-state probes, Ruff, repository checks, and verification-contract tests pass.

## Non-goals

- Installing or redistributing Autodesk binaries on GitHub-hosted runners.
- Creating fake Autodesk assemblies or weakening the AutoCAD project boundary.
- Skipping CI based only on documentation paths.
- Replacing the full local verification required on an AutoCAD-capable Windows machine.

## Approaches considered

### 1. Explicit hosted-runner skip switch — selected

Add `-SkipAutoCADDotNet` to `scripts/verify.ps1`. Its default is false, so the existing local command remains a full verifier. The hosted workflow passes the switch and the script prints an explicit `AutoCAD .NET gate: NOT RUN` marker before continuing with all remaining gates.

This is the smallest change that preserves the strong local gate while making hosted CI truthful and useful.

### 2. Ignore documentation-only pull requests — rejected

A `paths-ignore` rule would unblock PR #6 but leave every later code pull request broken. It would hide the configuration defect instead of fixing it.

### 3. Self-hosted AutoCAD runner — deferred

A self-hosted Windows runner could execute the full verifier, but it requires an administered machine, AutoCAD/SDK installation, licensing, hardening, and availability management. That operational project is outside this fix.

## Detailed design

### Verification script

`scripts/verify.ps1` gains one switch parameter:

```powershell
[switch]$SkipAutoCADDotNet
```

When the switch is absent, behavior remains unchanged:

1. Require the .NET SDK.
2. Restore the solution.
3. Build Release/x64.
4. reject copied Autodesk managed DLLs.
5. Run the .NET tests.
6. Continue with Python/offline verification.

When the switch is present, steps 1–5 are not executed. The script prints exactly:

```text
AutoCAD .NET gate: NOT RUN (explicit -SkipAutoCADDotNet).
```

The skip must never be inferred from missing files or a failed build.

### GitHub workflow

`.github/workflows/tests.yml` keeps the same runner, permissions, pinned action SHAs, bootstrap step, and artifact upload. Its verification step is renamed to describe hosted scope and invokes:

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

The job remains `offline-tests` so existing check names and branch protection expectations do not change.

### Contract tests

`tests/test_verification_contract.py` will first receive a failing regression test that requires:

- the explicit switch in the verifier;
- the exact `NOT RUN` marker;
- a workflow invocation that supplies the switch;
- no unqualified workflow invocation that could reintroduce the failure;
- unchanged pinned actions and least-privilege assertions.

After observing this test fail on the branch, the script and workflow receive the minimal implementation. The hosted workflow itself is the integration test: it must reach and pass the full Python/offline suite on a runner without Autodesk binaries.

## Failure behavior

- Default/local mode still fails closed if `dotnet` or Autodesk references are unavailable.
- Hosted mode can skip only through the explicit workflow argument.
- Any Python, environment-lock, Tesseract, test, lint, repository-integrity, or artifact failure remains a CI failure.
- The log distinguishes `NOT RUN` from `PASS`.

## Delivery sequence

1. Commit the failing regression test and confirm the expected CI failure.
2. Commit the minimal verifier/workflow implementation.
3. Confirm the regression test and complete hosted workflow pass.
4. Open and merge a focused CI-fix pull request.
5. Refresh PR #6 from the repaired `main`, rerun checks, and squash-merge it only when green.

## Acceptance criteria

- Invoking `scripts/verify.ps1` without the switch still contains and executes the AutoCAD .NET gates.
- Hosted workflow logs the exact explicit `NOT RUN` marker.
- Hosted workflow passes all remaining gates and uploads evidence.
- CI-fix PR contains no Autodesk binaries, stubs, or unrelated refactors.
- PR #6 becomes green after it is refreshed from the repaired `main`.
