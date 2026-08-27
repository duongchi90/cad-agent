# R5 Canonical Viewport / Camera Slice A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add closed, pure-Python `visual_capture_plan-1.0` and `visual_capture_receipt-1.0` contracts under the existing R5 visual-contract owner, with causal RED-first coverage and no AutoCAD/runtime execution.

**Architecture:** Extend only `cad_agent.visual_contracts`, reusing its identifier/SHA/numeric/closed-object helpers and server-owned validation model. `visual_capture_plan` is validated against the accepted server-owned `visual_review_scope`; `visual_capture_receipt` is validated against the accepted server-owned plan. No new store, renderer, transport, supervisor, mutation, publication, or live AutoCAD owner is introduced.

**Tech Stack:** Python 3.11+, pytest, existing `cad_agent.visual_contracts` helpers, canonical JSON/SHA conventions already used by the repository.

## Global Constraints

- Base design: `docs/superpowers/specs/2026-08-14-r5-canonical-viewport-camera-contract-design.md`.
- Current canonical main at issuance: `4f705a62965620c84f063d868b059a3f5b02e2a8`.
- Do not modify `main` while the current R8-D local acceptance epoch depends on that exact SHA.
- Slice A write-set is limited to this plan, `tests/test_visual_supervisor_contracts.py`, and `cad_agent/visual_contracts.py`.
- No AutoCAD/File-IPC execution, provider/model call, R6 repair, R7 publication, private/customer CAD, workflow, dependency, schema-directory, store, transport, or renderer changes.
- `GLOBAL` uses `EXTENTS`; `REGION` and `DETAIL` use `WINDOW` with finite non-degenerate WCS bboxes.
- Canonical required coverage is one GLOBAL per `(view_id, sheet_id, layout_id)` tuple represented by required scope regions, plus one REGION per required `region_id`.
- DETAIL is optional, must carry `parent_region_id`, and cannot substitute for required GLOBAL/REGION coverage.
- Unknown properties fail closed. Duplicate capture IDs and duplicate required coverage fail closed.
- `SKIP` / `NOT_RUN` remain non-PASS outside this Slice-A contract validator; Slice A must not weaken existing status semantics.

---

### Task 1: RED-first camera contract surface

**Files:**
- Modify: `tests/test_visual_supervisor_contracts.py`
- Modify after RED is observed: `cad_agent/visual_contracts.py`

**Interfaces:**
- Consumes: `validate_visual_contract(payload, contract=..., server_scope=...)` and the existing `visual_review_scope` normalized shape.
- Produces: `validate_visual_contract(..., contract="visual_capture_plan", server_scope=<visual_review_scope>)` and `validate_visual_contract(..., contract="visual_capture_receipt", server_scope=<visual_capture_plan>)`.

- [ ] **Step 1: Add causal RED fixtures and tests**

Append focused fixtures `_valid_visual_capture_plan()` and `_valid_visual_capture_receipt()` plus tests that require the two new contracts. The first RED set must cover: supported-contract registry membership; valid plan/receipt; missing/duplicate GLOBAL coverage; missing/duplicate REGION coverage; invalid GLOBAL `WINDOW`; invalid REGION without bbox; degenerate/non-finite bbox; invalid margin; DETAIL without/with foreign parent; plan substitution against server scope; receipt plan SHA mismatch; receipt candidate/mutation/view/layout/camera mismatch; bad artifact dimensions; transient-state-not-restored; and unknown fields.

The valid plan fixture must bind the existing two-region scope and contain exactly two GLOBAL captures because the current scope uses two distinct `(view_id, sheet_id, layout_id)` tuples, plus two REGION captures.

- [ ] **Step 2: Verify RED on the exact PR head**

Run:

```bash
python -m pytest tests/test_visual_supervisor_contracts.py -q
```

Expected causal failure: at least one new test fails because `visual_capture_plan` / `visual_capture_receipt` are not present in `SUPPORTED_VISUAL_CONTRACTS` or are reported as unsupported contract kinds. Existing visual-contract tests must remain otherwise unchanged.

- [ ] **Step 3: Implement the minimal closed validators**

In `cad_agent/visual_contracts.py`:

1. Add constants for capture classes, zoom modes, accepted view/UCS/style policies, bounded class-default margins, and receipt timestamp validation.
2. Add helpers that validate nullable identifiers, WCS bbox shape/order/finite values, capture-policy records, and server-owned coverage.
3. Add `_normalize_visual_capture_plan(payload, *, server_scope)` and `_validate_visual_capture_plan(...)`.
4. Add `_normalize_visual_capture_receipt(payload, *, server_plan)` and `_validate_visual_capture_receipt(...)`.
5. Register both contract kinds in `_VALIDATORS`.
6. Extend `validate_visual_contract` so `visual_capture_plan` requires `server_scope` as the accepted visual-review scope and `visual_capture_receipt` requires `server_scope` as the accepted visual-capture plan. Do not add another public authority parameter or validator module.

Plan invariants implemented by GREEN:

```text
schema_version == visual-capture-plan-1.0
exact run/scope/registry/candidate/state binding to server-owned visual_review_scope
latest_mutation_sha256 is a valid SHA-256
every required scope tuple -> exactly one GLOBAL EXTENTS capture
every required region -> exactly one REGION WINDOW capture
DETAIL parent_region_id exists in required region set
REGION/DETAIL bbox finite and xmax>xmin, ymax>ymin
GLOBAL bbox is null
margin_ratio equals server policy default (GLOBAL=.05, REGION=.10, DETAIL=.05)
closed keys; unique capture_id
```

Receipt invariants implemented by GREEN:

```text
schema_version == visual-capture-receipt-1.0
exact accepted-plan capture lookup by capture_id
exact run/scope/candidate/state/mutation/plan SHA/camera identity match
GLOBAL -> EXTENTS and requested/observed bbox are null
REGION/DETAIL -> requested bbox exactly equals plan bbox and observed bbox matches within validator-owned tolerance
view center/width/height finite and positive
artifact SHA valid; width/height positive integers
captured_at_utc RFC3339 UTC
transient_state_restored is true
closed keys
```

- [ ] **Step 4: Verify GREEN and regression**

Run:

```bash
python -m pytest tests/test_visual_supervisor_contracts.py -q
python -m pytest tests/test_visual_evidence.py tests/test_cad_agent_visual_supervisor_adapter.py -q
```

Expected: all selected tests PASS with no SKIP used to satisfy the new contract behavior.

- [ ] **Step 5: Run hosted verification on the exact GREEN head**

Push the GREEN commit to the implementation PR and require hosted `tests` + `reuse-declaration` PASS on that exact head before any reviewer PASS claim.

- [ ] **Step 6: Independent review gate**

Request independent Integration and Security review of the exact GREEN head. Review must confirm: existing R5 owner retained; no second renderer/transport/store; server-owned scope/plan cannot be substituted; numeric NaN/Infinity rejected; stale candidate/mutation/plan replay rejected; no live AutoCAD or R8 glue added.

- [ ] **Step 7: Hold merge while R8-D exact-main epoch is active**

Even after all Slice-A gates PASS, keep the PR unmerged until SOL fresh-reads #239/main and determines merging will not invalidate an authorized local AutoCAD epoch. If local epoch is active, leave the reviewed PR ready-but-held.
