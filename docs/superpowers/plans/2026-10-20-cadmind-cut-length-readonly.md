# CadMind Cut Length Read-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded read-only LINE/CIRCLE length measurement through the existing CAD read facade.

**Architecture:** Reuse the identity-bound `CadReadClient` and facade validation. Read only caller-selected handles, calculate lengths in raw drawing units, and fail closed on incomplete or invalid coverage.

**Tech Stack:** Python 3.11, pytest, existing CAD read facade.

**Spec:** `docs/superpowers/specs/2026-10-20-cadmind-cut-length-readonly-design.md` (Local PO approved 2026-10-20; bounded LINE/CIRCLE read-only scope).

## Global Constraints

- Existing owner: `cad_agent.cad_read_facade`.
- No drawing mutation, new transport, CadMind DTO/binary reuse, unit conversion, or physical-scale assertion.
- Keep exact drawing/candidate identity checks and the non-atomic observation limitation.
- Repository canonical main at start: `5979b1813a27dbc7435c64c6cf3c220f5f8e09ad`.

## Review Focus

- Duplicate or missing selected handles must not produce a partial successful total.
- Malformed/nonfinite geometry or arithmetic overflow must not be reported as a valid measurement.
- A changed active drawing or stale candidate binding must fail closed.
- Caller labels must remain declarative and must not affect measured values.
- Unsupported entity types must remain explicit failures, not be silently omitted.

---

**Status:** implementation complete; offline canonical verification passed; live/.NET gates unavailable
**Base SHA:** `5979b1813a27dbc7435c64c6cf3c220f5f8e09ad`
**Completion Head SHA:** pending

### Task 1: Pin the facade contract with failing tests

**Files:**
- Modify: `tests/test_cad_agent_cad_read_facade.py`

- [x] Add 3-4-5 LINE and radius-2 CIRCLE independent-oracle assertions, including mixed total and raw drawing units.
- [x] Add explicit rejection assertions for empty/duplicate/missing/unsupported handles, invalid/nonfinite geometry, identity drift and overflow.
- [x] Run the focused test file before production code; the new operation was absent and the regression cases failed as expected.

### Task 2: Implement the minimal existing-owner operation

**Files:**
- Modify: `cad_agent/cad_read_facade.py`

- [x] Add `measure_entity_lengths` using the existing binding and active-drawing identity checks; preserve caller handle order and require complete coverage.
- [x] Return bounded deterministic evidence in drawing units; never convert from caller labels.
- [x] Focused verification: `pytest tests/test_cad_agent_cad_read_facade.py -q` — 36 passed; Ruff on facade and test — passed; `git diff --check` — passed.

### Task 3: Verify and hand off

- [x] Run canonical `scripts/verify.ps1` offline on `1acc24c44410d39a2acc32bb966a6542f5ecabb9` using `-SkipAutoCADDotNet`: 3,692 passed, 23 deselected, 77 subtests passed; expected causal-RED negative oracle reproduced its known failure; real-data and AutoCAD/FileIPC gates reported unavailable-state skips. The full invocation without the skip switch stopped before tests because no .NET SDK is installed.
- [x] AutoCAD/handle smoke was `NOT RUN`: no live AutoCAD Mechanical/FileIPC session or disposable handle fixture was configured.
- [x] Confirmed only the spec, plan, facade and focused test file changed.
- [ ] Create/update one Draft PR; obtain terminal hosted checks and independent exact-head Security/Integration reviews before any adoption claim. Do not mark ready or merge while gates remain pending.

**Required private/live gates:** AutoCAD/handle smoke applicability to be checked; no private drawing data is required by the offline oracle.
**Verification:** focused pytest (36 passed), Ruff and `git diff --check` passed. Offline canonical verifier passed on the implementation commit. .NET/AutoCAD, live handle smoke, hosted checks, and independent reviews remain pending. The verifier requires a clean tree, so this recorded-result-only plan update is committed separately; production/test source was unchanged after the verified commit.
