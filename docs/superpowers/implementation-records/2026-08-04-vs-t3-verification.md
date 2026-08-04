# VS-T3 AutoCAD Evidence Exporter Verification Record

Status: verified offline; AutoCAD Mechanical live gate not run.

Verification commit:

`9d8201a8d814d1a521590d71ef43b89dbf5f920f`

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -PythonExe 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -SkipAutoCADDotNet
```

Observed result:

- Exit code: `0`
- Lock contract: PASS, 40 pinned and hashed distributions.
- Environment contract: PASS, 40 locked distributions.
- IPC contract suite: 20 passed, 18 subtests passed.
- Python IPC JUnit: 38 tests, 0 failures, 0 errors, 0 skipped.
- Offline suite: 731 passed, 11 deselected, 18 subtests passed.
- Real-data unavailable probe: 2 skipped because private inputs were not configured.
- AutoCAD Mechanical unavailable probe: 9 skipped because no live File IPC session was configured.
- AutoCAD .NET gate: `NOT RUN` because `-SkipAutoCADDotNet` was explicit.
- AutoCAD live marker: `NOT RUN`; no AutoCAD Mechanical File IPC prerequisites were available.
- Ruff: PASS on the affected Python files.
- `git diff --check`: PASS.

Authority-boundary review:

- `latest_mutation_sha256` is only echoed from the request; VS-T3 does not update mutation state.
- The exact manifest byte hash is checked before promotion; mutation-field equality alone is insufficient.
- Accepted evidence requires `success=true`, `changed=false`, empty entity handles, equal DWG hashes, equal DBMOD, equal session-state fingerprints, and `transient_state_restored=true`.
- Failure results do not invent an accepted visual-evidence payload.
- Artifact transfer is request-owned, bounded, hash-verified, lease-protected, and cleaned by Python after handoff.
- No visual verdict, repair plan, Codex authority, save, publish, or mutation executor is present in VS-T3.

This record does not claim private-drawing or AutoCAD live acceptance.
