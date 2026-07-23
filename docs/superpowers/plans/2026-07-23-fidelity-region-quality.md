# Fidelity Region Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement task-by-task.

**Goal:** Select only locally improved, private geometry reconstruction candidates using a reproducible edge-F1 comparison.

**Architecture:** `cad_agent.fidelity` will render both raw and filtered geometry from one approved crop, score each with the existing tolerant edge metric, and save the better DXF plus a report. The CLI contract stays unchanged because reconstruction remains driven by the existing approval artifact.

**Tech Stack:** Python 3.11, OpenCV, ezdxf, pytest.

## Global Constraints

- Fidelity output remains outside the worktree and cannot enter Mechanical commands.
- A filtered candidate is selected only when local F1 is strictly higher than baseline.
- No semantic model, dimension, hatch, or production DXF mutation is added.

---

### Task 1: Prove profile selection with a failing regression test

**Files:**

- Modify: `tests/test_cad_agent_fidelity.py`
- Modify: `cad_agent/fidelity.py`

**Interfaces:**

- Produces: `_select_fidelity_geometry(raw, crop, scale) -> tuple[RawGeometry, dict]`
- Consumes: `RawGeometry` and `_edge_metrics`.

- [ ] Write a failing test for filtered-profile selection.
- [ ] Run it to prove the helper is absent.
- [ ] Implement the smallest scoring/filtering helper.
- [ ] Re-run the focused test and commit.

### Task 2: Persist quality evidence in reconstruction candidates

**Files:**

- Modify: `cad_agent/fidelity.py`
- Modify: `tests/test_cad_agent_fidelity.py`
- Modify: `docs/STATUS.md`

**Interfaces:**

- Consumes: `_select_fidelity_geometry` from Task 1.
- Produces: candidate `report.json` with baseline and filtered local metrics.

- [ ] Write a failing report-content test.
- [ ] Add selected geometry and metrics to the candidate report.
- [ ] Run focused fidelity tests and `scripts/verify.ps1`.
- [ ] Re-run the private nine-page evidence, inspect fresh overlays, record only actual metrics, and commit.
