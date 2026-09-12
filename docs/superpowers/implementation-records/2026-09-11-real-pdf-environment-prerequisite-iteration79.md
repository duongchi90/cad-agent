# Current-Main Real-PDF Environment Prerequisite — Iteration 79

Date: 2026-09-11 (Asia/Saigon)
Canonical main SHA: `e8fc0092ee46750e50de0ea408fd91811cae10c2`
Executor branch: `codex/audit-text-style-compat-20260910`

## Authority and exact scope

SOL's iteration-78 diagnosis localized the previous fail-closed result to
environment preparation. It authorized one bounded action:

```text
Run the existing scripts/bootstrap.ps1 owner with Python 3.11 in one clean
detached worktree at exact main, require bootstrap terminal success and
check_environment.py success, then perform only a read-only import fitz probe.
Do not rerun run-pdf or any downstream gate.
HUMAN_GATE=NO
```

The exact identity used for this action was:

- clean detached worktree:
  `C:/temp/cad-agent-real-pdf-current-main-iter78`;
- worktree HEAD:
  `e8fc0092ee46750e50de0ea408fd91811cae10c2`;
- worktree status before and after: clean;
- Python 3.11 owner:
  `C:/Program Files/Python311/python.exe`;
- lock file:
  `requirements/windows-py311.lock`;
- lock SHA-256:
  `d4739cc0c3b523ab11069178680f534fa436e4e64e30e07c30d1f07e652d784d`.

## Actions and results

1. Ran the existing repository owner:
   `scripts/bootstrap.ps1 -PythonExe C:/Program Files/Python311/python.exe`.
   The terminal reported lock contract PASS, installed the locked
   distributions, reported environment contract PASS, and completed with the
   repository-owned interpreter:
   `C:/temp/cad-agent-real-pdf-current-main-iter78/.venv-py311/Scripts/python.exe`.
2. Ran `scripts/check_environment.py` against
   `requirements/windows-py311.lock`. It reported lock contract PASS and
   environment contract PASS for all 40 locked distributions.
3. Using only the exact `.venv-py311/Scripts/python.exe`, imported `fitz`.
   The resolved binding version is `1.28.0`; both the module and import spec
   resolve to:
   `C:/temp/cad-agent-real-pdf-current-main-iter78/.venv-py311/Lib/site-packages/fitz/__init__.py`.
4. Rechecked the approved source after the bounded action. Its SHA-256 is
   still `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.

## Fail-closed disposition

- `ENVIRONMENT_PREREQUISITE_ON_CURRENT_MAIN=PROVEN_CURRENT` for the exact
  detached worktree, lock, bootstrap owner, environment contract, and `fitz`
  import probe.
- The previous `run-pdf` failure was not retried. No `run-pdf` render/page
  stage, candidate/build, DARA/R3/R4, AutoCAD/FileIPC, persistence/reopen,
  visual, dimension, provider, M2, source/candidate/DXF, or production-code
  action was performed.
- Therefore
  `SOURCE_SHA_BOUND_RUN_PDF_MANIFEST_STAGE_ON_CURRENT_MAIN` remains
  `NOT_PROVEN`; this record proves only the missing prerequisite, not PDF
  processing or any downstream acceptance gate.
- No repository code, source bytes, candidate, DXF, or historical evidence was
  changed. The exact machine-readable context is outside Git at:
  `C:/temp/cad-agent-real-pdf-current-main-iter78-run/environment-probe-iteration79.json`.
