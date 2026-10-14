# Dimension Emitted-Line Integrity Plan

**Status:** executing
**Base SHA:** `7da1ed42a2168b5c991fc389a4c8155b1e88a387`
**Authority:** [Local GPT-6.1-Sol Phase A, #491 comment 6161862704](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6161862704)
**Admission:** [Step 1 checkpoint, #491 comment 6161926639](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6161926639)

## Sequence

- [ ] Add focused RED regressions for opt-in capture and a deleted emitted LINE.
- [ ] Capture a bounded immutable LINE inventory after dimension rendering and before save.
- [ ] Add a separate same-document integrity review API; preserve existing review and evidence contracts.
- [ ] Cover missing/altered/duplicate/reversed lines, matching ambiguity, unsupported frame/type, malformed or absent evidence, resource limits, zero dimensions, and legacy compatibility.
- [ ] Run focused tests, Ruff on touched Python, and `git diff --check`.
- [ ] Make one scoped local implementation/evidence commit after focused PASS.
- [ ] Run exactly one canonical `scripts/verify.ps1` on the clean implementation commit using the existing supported Windows Python; `-SkipAutoCADDotNet` is allowed and must be recorded as NOT RUN. Capture real child exit and durable logs/completion plus before/after identity/status.
- [ ] If verification passes, close this plan in a separate plan-only lifecycle commit and prove source/test bytes are unchanged; publish one compact #491 receipt and return to PO.

## Gates and limits

The existing one-time real-drawing smoke is consumed and recorded at #491 comments 6139194448 and 6139634705; no additional drawing run is authorized. No private/live gate is required for this offline helper. AutoCAD/.NET smoke is NOT RUN. No dependency, serializer, public evidence schema, CLI, PDF, pilot, consumer, PR508, native, push, PR, review, CI, or merge action is authorized.

**Exact canonical verification command:** `./scripts/verify.ps1 -SkipAutoCADDotNet` (PowerShell; one run only).
**Completion Head SHA:** pending.
**Verification result:** pending.
