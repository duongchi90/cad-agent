# Review-only fidelity hatch reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit native DXF HATCH entities only from hash-bound, explicitly approved private fidelity polygons.

**Architecture:** Stable hatch observations feed a dedicated approval contract that binds the observation and base DXF. Thin CLI commands normalize approval JSON and revalidate it before cloning the base DXF into a revisioned `needs_review` candidate.

**Tech Stack:** Python 3.11, OpenCV, ezdxf, JSON SHA-256 sidecars, argparse, pytest.

## Global Constraints

- Fidelity artifacts remain outside the Git worktree.
- Source PDF, rendered page, observation, and base DXF are hash-bound.
- Only explicit polygons inside observed candidate boxes may emit HATCH.
- Outputs are revisioned and `needs_review`; no production mutation is authorized.
- Font/OCR work remains deferred.

---

### Task 1: Define stable observations and the approval contract

**Files:**
- Modify: `cad_agent/fidelity.py`
- Test: `tests/test_cad_agent_fidelity.py`

**Interfaces:**
- Consumes: `fidelity-hatch-observation-1.0`, manifest page render, private base DXF.
- Produces: `write_fidelity_hatch_approval(source, output_root, manifest, page_number, observation_path, base_dxf, mappings, approval_reference, *, workspace_root) -> dict[str, Any]`.

- [x] **Step 1: Write failing stable-id and valid-approval tests**

```python
assert _observe_hatch_candidates(image)[0]["id"] == "hatch-001"
approval = write_fidelity_hatch_approval(
    source, output, manifest, 1, observation, base_dxf, mappings,
    "review-1", workspace_root=Path.cwd(),
)
assert approval["base_dxf"]["sha256"] == sha256_file(base_dxf)
```

- [x] **Step 2: Implement normalized approval validation**

Validate private-root containment, source/render/observation/base hashes,
approval reference, unique known candidate ids, numeric points within both
page and candidate box, polygon area, numeric angle, and positive scale.

- [x] **Step 3: Run the focused tests**

Run: `.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_fidelity.py -k "hatch and (approval or reconstruct or stable)" -q -p no:cacheprovider`

Result: `7 passed, 31 deselected`.

### Task 2: Reconstruct only approved polygons

**Files:**
- Modify: `cad_agent/fidelity.py`
- Test: `tests/test_cad_agent_fidelity.py`

**Interfaces:**
- Produces: `run_fidelity_hatch_reconstruct(source, output_root, manifest, approval_path, base_dxf, *, workspace_root) -> Path`.
- Consumes: complete `fidelity-hatch-approval-1.0` records from Task 1.

- [x] **Step 1: Implement defensive reconstruction**

Revalidate the full approval contract and bound artifacts before reading the
DXF. Convert `(x_px, y_px)` to `(x_px * scale, (height_px - y_px) * scale)`,
add closed ANSI31 paths on `FIDELITY_HATCH`, save under
`hatch_reconstruction[-rN]/page_NN/layout.dxf`, and write the hash audit report.

- [x] **Step 2: Add refusal tests**

Tests reject a changed base DXF, tampered observation, duplicate candidate,
and a modified out-of-bounds approved polygon before candidate output.

- [x] **Step 3: Run the fidelity suite**

Run: `.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_fidelity.py -q -p no:cacheprovider`

Result: `38 passed`.

### Task 3: Add CLI coverage

**Files:**
- Modify: `cad_agent/cli.py`
- Test: `tests/test_cad_agent_fidelity.py`

**Interfaces:**
- Produces: `fidelity-hatch-approve --input --manifest --page --observation --base-dxf --mappings --approval-reference`.
- Produces: `fidelity-hatch-reconstruct --input --manifest --approval --base-dxf`.

- [x] **Step 1: Add thin handlers and parsers**

Read `--mappings` as a JSON list, translate JSON errors to `CommandError`, call
the fidelity functions, and print the created private artifact path.

- [x] **Step 2: Exercise both commands**

The CLI regression approves a mapping file and reconstructs the revisioned
private DXF.

### Task 4: Verify and close the slice

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/STATUS.md`
- Modify: this plan

**Interfaces:**
- Produces: release evidence for implementation commit `75b5b80`.

- [x] **Step 1: Run focused fidelity tests and Ruff**

Result: `38 passed`; Ruff reports `All checks passed!`.

- [x] **Step 2: Commit the implementation**

Commit: `75b5b80 fix: bind hatch approvals to base drawings`.

- [ ] **Step 3: Run offline, private-PDF, and live Mechanical gates**

Record exact commit SHA, counts, and JUnit SHA-256 values. The private gate
requires reconstruction, and the live gate uses disposable DXF files only.

- [ ] **Step 4: Close documentation and final independent review**

Mark remaining checkboxes complete, update release evidence without private
paths, and verify the final tree with `git diff --check` and
`scripts/verify.ps1`.
