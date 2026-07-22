# AutoCAD Mechanical Production Review/Repair Implementation Plan

**Status:** Executing

**Base SHA:** `68713d593a9ae8d24711586f74b44b5163bd542c`

**Verification command:** `scripts/verify.ps1`

**Required gates:** the deterministic offline suite and `autocad_mechanical`
live review smoke must pass. `real_data` is not affected unless the operator
supplies and approves a private drawing.

## Steps

1. Add focused tests for persisted build evidence and approval/backup/rollback
   behavior using the Fake MCP client.
2. Add evidence serialization and `mechanical-review` / `mechanical-repair`
   commands without changing domain algorithms.
3. Run focused checks, a disposable AutoCAD Mechanical review, and the full
   verifier.
4. Record evidence and close the plan.
