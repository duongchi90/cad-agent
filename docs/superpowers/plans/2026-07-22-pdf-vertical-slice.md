# PDF Vertical-Slice Orchestration Implementation Plan

**Status:** Complete

**Base SHA:** `51259f829f1bbcc5570824356fe0832918781027`

**Verification command:** `scripts/verify.ps1`

**Required gates:** deterministic PDF/CLI tests and the offline verifier. The
PDF slice does not mutate AutoCAD; `autocad_mechanical` and `real_data` are not
affected unless an operator separately invokes them with approved inputs.

## Steps

1. Add red regression tests for multi-page manifest creation, resume, and
   source-hash rejection.
2. Implement `run-pdf` and `resume-pdf` with atomic per-page checkpoints.
3. Run focused PDF tests and the full verifier.
4. Record evidence and close the plan.

## Completion evidence

- Implementation commit: `1669f25e88847b47284219c92769801a5bc81768`
- Focused command: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_pdf.py tests\test_cad_agent_cli.py tests\test_cad_agent_live.py -q -p no:cacheprovider` -> `12 passed`
- Focused Ruff command: `& '.\.venv-py311\Scripts\python.exe' -m ruff check cad_agent tests\test_cad_agent_pdf.py` -> `All checks passed!`
- Authoritative verifier: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` -> exit `0`; offline JUnit `tests=304; failures=0; errors=0; skipped=0`.
- The unavailable-state probes remain intentionally separate: `real_data` `SKIP` (one test) and `autocad_mechanical` `SKIP` (four tests). No private PDF or production drawing was used.
