# Thin Vertical-Slice CLI Implementation Plan

**Status:** Executing

**Base SHA:** `accb2cf`

**Verification command:** `scripts/verify.ps1`

**Required specialized gates:** `real_data` and `autocad_lt` are not affected
by this deterministic orchestrator slice; their unavailable-state probes must
remain `SKIP` and live execution remains `NOT RUN`.

## Steps

1. Add regression tests for deterministic run/resume, source-hash rejection,
   and prerequisite reporting.
2. Add a thin `cad_agent` package with atomic manifests and the `doctor`,
   `run`, and `resume` commands.
3. Run focused tests, then the authoritative verification script and
   whitespace checks.
4. Record fresh evidence in the status ledger, complete this plan lifecycle,
   and commit the implementation and evidence separately.
