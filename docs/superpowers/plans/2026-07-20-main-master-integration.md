# Main/Master Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish an integration branch that preserves the current `main` implementation, restores the independent benchmark and vision-readiness work from `master`, and fixes the `gia_do` integration regression.

**Architecture:** `main` is the behavioral base because its HEAD matches the handoff and includes the current tick-mark and INSERT work. Since `master` and `main` have unrelated Git histories, transfer only master-only artifacts into the integration branch; never overwrite files that main has advanced. Reproduce the semantic regression with its existing integration test before changing production logic.

**Tech Stack:** Python, pytest, Git.

## Global Constraints

- Do not alter `master` or `main`; work only on `integration/main-master`.
- Preserve `main` versions where a file exists in both histories.
- Restore master-only benchmark modules and their tests as a coherent unit.
- Do not claim a fix without fresh test evidence.

---

### Task 1: Integrate master-only artifacts

**Files:**
- Modify: `requirements.txt`
- Create: master-only benchmark and vision-preflight files under `primitive_ir_lib/` and `docs/benchmarks/`

- [ ] Copy the files that exist on `master` but not on `main`, excluding documentation snapshots superseded by `main`.
- [ ] Keep the `main` version of files present in both histories; add only the `anthropic` dependency line from master's requirements file.
- [ ] Run the restored primitive benchmark and vision-preflight tests.

### Task 2: Fix compound-pattern integration regression

**Files:**
- Modify: `semantic_ir_lib/tests/test_pattern_compound.py`
- Modify: `semantic_ir_lib/pattern_compound.py`

- [ ] Run `test_integration_via_assemble` and record its failure.
- [ ] Add a focused assertion that the isolated `g1`/`g2` pair reaches compound recognition through `build_semantic_document`.
- [ ] Implement the smallest correction in compound assembly/constraint handling required for that assertion.
- [ ] Run the focused test, then the full semantic suite.

### Task 3: Verify integration branch

**Files:**
- Verify only

- [ ] Run the complete test suites for primitive, semantic, DXF builder, MCP integration, and agent libraries.
- [ ] Inspect the final diff and branch status before handoff.
