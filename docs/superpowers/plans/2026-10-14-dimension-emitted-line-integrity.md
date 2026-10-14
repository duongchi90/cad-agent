# Dimension Emitted-Line Integrity Plan

**Status:** completed
**Base SHA:** `7da1ed42a2168b5c991fc389a4c8155b1e88a387`
**Authority:** [Local GPT-6.1-Sol Phase A, #491 comment 6161862704](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6161862704)
**Admission:** [Step 1 checkpoint, #491 comment 6161926639](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6161926639)
**Completion Head SHA:** `580e82ce97e9e2d1828480411de39413c8b6f094`

## Sequence

- [x] Add focused RED regressions for opt-in capture and a deleted emitted LINE. Initial collection RED identified the absent new API; focused suite passed after implementation.
- [x] Capture a bounded immutable LINE inventory after dimension rendering and before save.
- [x] Add a separate same-document integrity review API; preserve existing review and evidence contracts.
- [x] Cover missing/altered/duplicate/reversed lines, matching ambiguity, unsupported frame/type, malformed or absent evidence, resource limits, zero dimensions, and legacy compatibility.
- [x] Run focused tests, Ruff on touched Python, and `git diff --check`.
- [x] Make one scoped local implementation/evidence commit after focused PASS: `580e82ce97e9e2d1828480411de39413c8b6f094`.
- [x] Run exactly one accepted canonical invocation on the clean implementation commit. The initial default-path attempt exited 1 before Python; the PO-authorized explicit-interpreter invocation below completed successfully. No further verifier run occurred.
- [x] Close this plan in a separate plan-only lifecycle commit, prove source/test files unchanged, and publish/read back one compact #491 receipt.

## Gates and limits

The existing one-time real-drawing smoke is consumed and recorded at #491 comments 6139194448 and 6139634705; no additional drawing run is authorized. No private/live gate is required for this offline helper. AutoCAD/.NET smoke is NOT RUN. No dependency, serializer, public evidence schema, CLI, PDF, pilot, consumer, PR508, native, push, PR, review, CI, or merge action is authorized.

**Exact canonical verification command:** `./scripts/verify.ps1 -PythonExe 'C:\cad-agent\.venv-py311\Scripts\python.exe' -SkipAutoCADDotNet` (PowerShell; one accepted invocation).
**Verification result:** PASS; child exit 0; 213.053 seconds; offline JUnit 3,646 passed plus 77 subtests, zero failures/errors; Ruff passed; unavailable-state probes and retained live/private skips recorded in the log. AutoCAD/.NET gate NOT RUN by explicit flag.
**First invocation admission result:** default `./scripts/verify.ps1 -SkipAutoCADDotNet` exited 1 before Python because the worktree-local venv was absent. A distinct Local Sol package authorized one explicit-interpreter invocation; no bootstrap or environment creation occurred.
**Before/after identity:** HEAD `580e82ce97e9e2d1828480411de39413c8b6f094`; TREE `0e84799e2a7fa9a7151c83a2c4b001328a193edb`; clean before and after.
**Durable verifier evidence:** `D:\Cad agent temp\dimension-graphics-coverage-20261014\canonical-verify-explicit-python.log` and `canonical-verify-explicit-python-receipt.txt`.
**Plan-only closure:** pending commit; source/test paths must remain byte-identical to Completion Head.
