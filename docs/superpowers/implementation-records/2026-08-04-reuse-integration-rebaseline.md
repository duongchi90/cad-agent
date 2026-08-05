# Reuse Integration Rebaseline Implementation Record

Status: Accepted for the R0 governance/rebaseline scope; runtime work remains
locked.

## Audit identity and exact heads

- Task: R0-T7, Issue #46.
- Exact Task 7 implementation base: `07a14ce3623024f2df848b2b88ff447980772492`.
- Full-verifier candidate SHA: `a373114c91edd02a6a4dd086b02b2a89433be964`.
- Final record-only SHA: the final head of this documentation commit, recorded
  in the final PR and handoff after commit because a commit cannot embed its
  own object ID without a self-referential hash.
- The canonical verifier was run on the full-verifier candidate only. It was
  not run on this later record-only commit.

## Aggregate verification evidence

Focused R0 suite on the full-verifier candidate:

```text
41 passed, 0 skipped
```

Commands and observed results:

```powershell
C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_inventory_contract.py tests/test_reuse_inventory_repository.py tests/test_reuse_declaration.py tests/test_reuse_legacy_compatibility.py tests/test_reuse_architecture_boundaries.py tests/test_reuse_rebaseline_docs.py -q -p no:cacheprovider
```

Result: exit `0`; `41 passed` and zero skips.

```powershell
C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Results: inventory checker exit `0`; architecture checker `PASS` with no new
unbaselined violation.

Ruff passed on all ten R0 Python files named by the Task 7 command. `git diff
--check` passed on both the candidate and the record-only working tree before
the record-only commit.

## Canonical verifier evidence

Exact command:

```powershell
.\scripts\verify.ps1 -PythonExe C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe -SkipAutoCADDotNet
```

Result: exit `0` on candidate
`a373114c91edd02a6a4dd086b02b2a89433be964`; the repository was clean at
verification start.

- Lock contract: `PASS`, 40 pinned hashed distributions.
- Environment contract: `PASS`, 40 locked distributions.
- Dotnet IPC JUnit: `tests=38`, failures `0`, errors `0`, skipped `0`.
- Python offline JUnit: `tests=808`, failures `0`, errors `0`, skipped `0`.
- Real-data unavailable-state probe: `tests=2`, skipped `2`.
- AutoCAD Mechanical unavailable-state probe: `tests=9`, skipped `9`.
- AutoCAD .NET gate: `NOT RUN` because the .NET SDK was unavailable and
  `-SkipAutoCADDotNet` was used.
- AutoCAD Mechanical live marker: `NOT RUN` because no qualifying session and
  File IPC prerequisites were configured.
- Private real-data acceptance: `NOT RUN`.

The unavailable-state `SKIP` results are not acceptance evidence and are not
reported as passes.

## Final record-only verification

After this record-only commit, rerun the focused R0 suite, both governance
CLIs, the full R0 Ruff command, and `git diff --check` on the clean final head.
The final rerun is required to confirm the record-only tree; it must not be
described as a rerun of the canonical verifier. The observed final rerun is:

- Focused R0 suite: `41 passed, 0 skipped`.
- Inventory checker: exit `0`.
- Architecture checker: `PASS`.
- Ruff: `PASS`.
- `git diff --check`: `PASS`.

The exact final record-only commit SHA is recorded in the final PR provenance
and handoff after commit; the full canonical verifier result above remains
bound only to candidate `a373114c91edd02a6a4dd086b02b2a89433be964`.

## R0 acceptance and locked work

R0 is accepted for its governance/rebaseline scope: the inventory is closed,
complete, path-valid, and SHA-bound; the legacy CLI and historical manifest
compatibility baseline passes; the architecture ratchet reports no new
violation; the Reuse Declaration gate is present; and the old Visual Supervisor
rollout remains superseded after VS-T3 without deleting its history.

This acceptance does not promote runtime behavior or authorize implementation.
S1, S2, S3, and R1 require fresh plans, exact bases, disjoint allowlists where
applicable, tests, Reuse Declarations, review, and their own acceptance gates.
Old VS-T4 through VS-T8 remain locked. M2 Drawing Initialization remains
authoritative. No OCR, solver, DXF, AutoCAD, repair, revision, verdict, or
publisher runtime was added.

## Exact changed-file list

Only these two allowlisted files changed in Task 7:

- `docs/superpowers/implementation-records/2026-08-04-reuse-integration-rebaseline.md`
- `docs/STATUS.md`
