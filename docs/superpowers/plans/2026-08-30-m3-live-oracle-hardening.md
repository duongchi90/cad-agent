# M3 Live Oracle Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:test-driven-development. This bounded correction addresses the current red-team advisory before any provider or AutoCAD action.

**Goal:** Remove the critical false-PASS paths identified by advisory `5468292161` while preserving the existing M3 callback seam and `R5_MODE=contract-only` boundary.

**Architecture:** Reuse the current-main R5/R6 validators as exact sealed-result gates inside the stateless M3 record oracle and callback coordinator. Add only the evidence fields needed to distinguish zero transport failure/retry and to bind the repair executor to the single R6 attempt. Preserve empty Human-event capture as an explicit valid state.

**Spec:** GitHub #305, #301, #311; advisory `5468292161`.

**Status:** executing

## Constraints

- No provider adapter, repair engine, retry manager, transport, database, telemetry, NETLOAD, UI automation, process control, or live AutoCAD mutation.
- Existing `validate_visual_verdict_result`, `validate_approved_repair_result`, R4/R5/R6/R7/FileIPC/.NET owners remain authoritative.
- `R5_MODE=contract-only` remains non-live and `LIVE_REPAIR_ACCEPTANCE=NOT_RUN`.

## Tasks

- [x] Write causal REDs for transport failure/retry, reduced R5/R6 mappings, executor-attempt rebinding, and zero Human events.
- [x] Add canonical R5/R6 result identities and owner-validator checks to the record oracle.
- [x] Reject transport failure/retry and cross-bind `repair_executor` attempts to one R6 attempt.
- [x] Allow `human_intervention.events=[]` when capture is explicit.
- [x] Verify focused and nearest regressions, lint, and diff hygiene.
- [ ] Push, hosted-verify, and merge only the bounded hardening slice.

## Evidence

- Focused hardening suite: `18 passed`.
- Nearest M3/R4/R5/R6/R7 regression: `230 passed`.
- Ruff and `git diff --check`: passed.
- Live/provider/AutoCAD: `NOT RUN` by policy.
