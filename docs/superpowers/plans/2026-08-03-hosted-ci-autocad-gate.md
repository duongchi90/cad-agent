# Hosted CI AutoCAD Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Make the hosted Windows CI truthful and green without weakening the default local AutoCAD verification gate.

**Architecture:** Add an explicit `-SkipAutoCADDotNet` switch to `scripts/verify.ps1`. The switch is opt-in and bypasses only the Autodesk-dependent restore/build/test block; local invocation without it remains fail-closed. Update the existing hosted workflow to pass the switch and update its contract test so the behavior cannot silently regress.

**Tech Stack:** PowerShell 7/Windows PowerShell script, GitHub Actions YAML, Python `unittest`, GitHub connector.

## Global Constraints

- The default `scripts/verify.ps1` invocation must still execute .NET restore, Release/x64 build, Autodesk DLL-copy check, and .NET tests.
- Hosted mode must emit `AutoCAD .NET gate: NOT RUN (explicit -SkipAutoCADDotNet).`.
- Do not add Autodesk binaries, fake assemblies, path-based CI skips, or unrelated refactors.
- Keep the job name `offline-tests`, pinned action SHAs, `contents: read`, and artifact upload unchanged.
- Every implementation step must have a failing test or observable red check before the corresponding code change.

## Files

- Modify: `tests/test_verification_contract.py` — regression contract for the explicit switch and workflow invocation.
- Modify: `scripts/verify.ps1` — opt-in switch and explicit hosted marker.
- Modify: `.github/workflows/tests.yml` — pass the switch and label the verification scope.
- Create: `docs/superpowers/specs/2026-08-03-hosted-ci-autocad-gate-design.md` — approved design (already committed).
- Create: `docs/superpowers/plans/2026-08-03-hosted-ci-autocad-gate.md` — this plan.

### Task 1: Add the failing regression contract

**Files:**
- Modify: `tests/test_verification_contract.py`

**Interfaces:**
- Consumes: current verifier and workflow text.
- Produces: a contract that fails until both the switch and explicit workflow invocation exist.

- [ ] **Step 1: Add one test**

Add this method to `VerificationContractTests`:

```python
    def test_hosted_mode_explicitly_skips_only_autocad_dotnet_gate(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")

        self.assertIn("[switch]$SkipAutoCADDotNet", script)
        self.assertIn(
            "AutoCAD .NET gate: NOT RUN (explicit -SkipAutoCADDotNet).",
            script,
        )
        self.assertIn(".\\scripts\\verify.ps1 -SkipAutoCADDotNet", workflow)
        self.assertNotIn(
            ".\\scripts\\verify.ps1\n",
            workflow.replace(".\\scripts\\verify.ps1 -SkipAutoCADDotNet", ""),
        )

        dotnet_gate = script.index('Invoke-DotNetGate -Name "dotnet restore"')
        skip_marker = script.index(
            "AutoCAD .NET gate: NOT RUN (explicit -SkipAutoCADDotNet)."
        )
        self.assertLess(skip_marker, dotnet_gate)
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run on a checkout containing the branch:

```bash
python -m unittest tests.test_verification_contract.VerificationContractTests.test_hosted_mode_explicitly_skips_only_autocad_dotnet_gate -v
```

Expected: FAIL because the current verifier has no `SkipAutoCADDotNet` switch and the workflow invokes `verify.ps1` without it.

- [ ] **Step 3: Commit the red test**

```bash
git add tests/test_verification_contract.py
git commit -m "test: require explicit hosted AutoCAD gate mode"
```

### Task 2: Implement the opt-in verifier switch

**Files:**
- Modify: `scripts/verify.ps1`

**Interfaces:**
- Consumes: `-SkipAutoCADDotNet` from the workflow or local command.
- Produces: unchanged full local gate by default and a truthful hosted marker when explicitly requested.

- [ ] **Step 1: Add the switch parameter**

Extend the existing parameter block with:

```powershell
[switch]$SkipAutoCADDotNet
```

Keep the default false.

- [ ] **Step 2: Guard only the Autodesk-dependent block**

Wrap the existing solution existence check, `Get-Command dotnet` check, `Invoke-DotNetGate` restore/build/test calls, and DLL-copy check in:

```powershell
if ($SkipAutoCADDotNet) {
    Write-Host "AutoCAD .NET gate: NOT RUN (explicit -SkipAutoCADDotNet)."
} else {
    # existing full AutoCAD .NET gate, unchanged
}
```

Do not move or skip Python lock, Tesseract, pytest, Ruff, repository-integrity, or artifact checks.

- [ ] **Step 3: Run the focused contract test**

Expected: still FAIL because the workflow has not yet been updated with the switch.

- [ ] **Step 4: Commit the verifier implementation**

```bash
git add scripts/verify.ps1
git commit -m "fix: make hosted AutoCAD gate explicitly opt-in"
```

### Task 3: Update the hosted workflow

**Files:**
- Modify: `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: the verifier switch from Task 2.
- Produces: hosted CI that reaches all non-AutoCAD gates on GitHub-hosted Windows.

- [ ] **Step 1: Rename the step**

Change the step label to:

```yaml
- name: Run hosted verification (AutoCAD .NET gate not run)
```

- [ ] **Step 2: Pass the explicit switch**

Change only the command to:

```yaml
run: .\scripts\verify.ps1 -SkipAutoCADDotNet
```

Keep the job name, runner, permissions, pinned actions, bootstrap command, and artifact settings unchanged.

- [ ] **Step 3: Run the focused contract test**

Expected: PASS.

- [ ] **Step 4: Commit the workflow change**

```bash
git add .github/workflows/tests.yml
git commit -m "ci: run hosted verification without AutoCAD SDK"
```

### Task 4: Verify and deliver

**Files:** no additional source files.

- [ ] **Step 1: Run all local contract tests**

```bash
python -m unittest tests.test_verification_contract -v
```

Expected: all verification-contract tests PASS.

- [ ] **Step 2: Inspect the branch diff**

Confirm only the plan/spec, contract test, verifier, and workflow changed; no Autodesk DLLs or unrelated files are present.

- [ ] **Step 3: Open a focused draft PR**

Base: `main`; head: `fix/hosted-ci-autocad-gate`. Keep it separate from documentation PR #6.

- [ ] **Step 4: Wait for Actions and inspect logs**

The hosted job must reach the Python/offline gates, print the exact `NOT RUN` marker, pass the contract test, and upload `.artifacts/test-results/`.

- [ ] **Step 5: Merge the CI fix only after green checks**

Use squash merge with the expected head SHA. Do not bypass a failing check.

- [ ] **Step 6: Refresh PR #6**

Rebase or recreate the documentation branch from the repaired `main`, verify its three documentation commits are unchanged, wait for green checks, and squash-merge PR #6.

## Verification checkpoints

- RED: Task 1 focused test fails before implementation.
- GREEN: Task 3 focused test and all contract tests pass.
- CI GREEN: hosted workflow passes without Autodesk managed DLLs.
- Final GREEN: PR #6 is based on repaired `main` and has successful checks before merge.
