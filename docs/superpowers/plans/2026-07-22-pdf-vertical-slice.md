# PDF Vertical-Slice Orchestration Implementation Plan

**Status:** Executing

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
