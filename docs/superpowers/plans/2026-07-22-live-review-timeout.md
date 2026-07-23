# Dense Live-Review Timeout Plan

**Status:** Complete

**Base SHA:** `47e8b93e89095027ccb838168bfe20a7304ea8d9`

1. Add the optional timeout argument and validate it at the CLI boundary.
2. Propagate it to the File IPC client with the existing 10-second default.
3. Add a focused propagation regression and run the full verifier.
4. Re-run the dense staged page through the standard read-only CLI. Completed:
   `--timeout-s 60` passed 485 structural and 485 geometry checks with no
   mismatch, warning, repair, or save.
