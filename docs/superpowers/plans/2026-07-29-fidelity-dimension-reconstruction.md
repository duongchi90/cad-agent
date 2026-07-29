# Review-only fidelity dimension reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn explicitly approved linear dimension observations into native DXF `DIMENSION` entities in private review candidates without mutating production drawings.

**Architecture:** Extend the existing fidelity observation with stable, hash-bound line endpoint evidence. Add a focused reconstruction function in `cad_agent.fidelity` and a thin CLI command that validates source/observation/approval/base-DXF provenance, clones the base DXF, and appends only approved linear dimensions on `FIDELITY_DIMENSIONS`. The result remains a revisioned `needs_review` artifact and is refused by production Mechanical paths.

**Tech Stack:** Python 3.11, OpenCV, ezdxf, JSON sidecars, pytest, existing fidelity SHA-bound artifact helpers.

## Global Constraints

- Fidelity output must remain outside the Git worktree.
- The source PDF, rendered page, observation, approval, and base DXF must be hash-bound before reconstruction.
- Only explicit `approved-dimension-mappings` may emit native dimensions.
- Only linear dimensions with two observed line endpoints are supported.
- The output report must remain `needs_review`; no production AutoCAD save or repair is authorized.

---

### Task 1: Persist stable line evidence in dimension observations

**Files:**
- Modify: `cad_agent/fidelity.py:run_fidelity_dimension_observations`
- Test: `tests/test_cad_agent_fidelity.py`

**Interfaces:**
- Consumes: existing rendered page, OCR text observations, `extract_raw_geometry()` output.
- Produces: each dimension candidate's `nearby_lines` list with `id`, `p1_px`, `p2_px`, `bbox_px`, and `length_px`; retain `nearby_line_ids` for compatibility.

- [ ] **Step 1: Write the failing test**

```python
def test_dimension_observation_persists_stable_line_endpoint_evidence(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())
    observation = run_fidelity_dimension_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    payload = json.loads(observation.read_text(encoding="utf-8"))
    candidate = payload["candidates"][0]
    assert candidate["nearby_lines"]
    assert set(candidate["nearby_lines"][0]) >= {"id", "p1_px", "p2_px", "bbox_px", "length_px"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv-py311\\Scripts\\python.exe -m pytest tests/test_cad_agent_fidelity.py::test_dimension_observation_persists_stable_line_endpoint_evidence -q -p no:cacheprovider`

Expected: FAIL with `KeyError: 'nearby_lines'` because the current observation only persists line ids.

- [ ] **Step 3: Implement the minimal evidence serialization**

Replace the list of ids with a bounded list of JSON-safe records while keeping
`nearby_line_ids` as the compatibility projection:

```python
nearby_lines = [
    {
        "id": line.id,
        "p1_px": [line.p1_px[0], line.p1_px[1]],
        "p2_px": [line.p2_px[0], line.p2_px[1]],
        "bbox_px": list(line.bbox_px),
        "length_px": line.length_px(),
    }
    for line in raw.lines
    if line.bbox_px[0] <= x1 + 30 and line.bbox_px[2] >= x0 - 30
    and line.bbox_px[1] <= y1 + 30 and line.bbox_px[3] >= y0 - 30
][:12]
candidate = {"text": text, "nearby_line_ids": [line["id"] for line in nearby_lines], "nearby_lines": nearby_lines, "state": "needs_human_approval"}
```

- [ ] **Step 4: Run the focused test**

Run the command from Step 2. Expected: PASS.

### Task 2: Add an approval validator and native linear dimension reconstruction

**Files:**
- Modify: `cad_agent/fidelity.py`
- Test: `tests/test_cad_agent_fidelity.py`

**Interfaces:**
- Produces: `run_fidelity_dimension_reconstruct(source, output_root, manifest, approval_path, base_dxf, *, workspace_root) -> Path`.
- Consumes: schema `fidelity-dimension-approval-1.0`, dimension observation candidates, page scale and render height, base DXF.

- [ ] **Step 1: Write the failing valid-approval test**

```python
def test_dimension_reconstruction_emits_approved_native_dimension(tmp_path: Path) -> None:
    # Build the standard private fixture, run observation, then construct an
    # approval using the first candidate's first nearby_lines entry.
    # Assert the output report is needs_review, the base entity count is kept,
    # and the output DXF contains one DIMENSION on FIDELITY_DIMENSIONS.
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv-py311\\Scripts\\python.exe -m pytest tests/test_cad_agent_fidelity.py::test_dimension_reconstruction_emits_approved_native_dimension -q -p no:cacheprovider`

Expected: FAIL because `run_fidelity_dimension_reconstruct` does not exist.

- [ ] **Step 3: Implement validation and reconstruction**

Validate `private_artifact`, schema, state, source, page, observation hash,
approval reference, mapping uniqueness, and candidate/evidence membership.
Convert pixel endpoints to paper coordinates with:

```python
def paper_point(point_px: list[float]) -> tuple[float, float]:
    return (point_px[0] * scale, (height_px - point_px[1]) * scale)
```

Use `ezdxf` `add_linear_dim(base=..., p1=..., p2=..., location=..., angle=...)`,
render it, save the revisioned output, and write a SHA-bound report with the
selected mappings and `emitted_dimension_entities`.

- [ ] **Step 4: Run the valid-approval test**

Expected: PASS and the reopened DXF contains one native `DIMENSION`.

- [ ] **Step 5: Add failing refusal tests for provenance and mappings**

Cover a changed observation hash, an unknown candidate id, an unknown line
evidence id, duplicate line evidence, and an unsupported dimension kind. Each
must raise `FidelityError` before an output directory is created.

- [ ] **Step 6: Run refusal tests**

Run the focused test selection. Expected: all pass.

### Task 3: Expose the command and preserve production safety

**Files:**
- Modify: `cad_agent/cli.py`
- Modify: `cad_agent/fidelity.py:_refuse_fidelity_dxf` or its existing fidelity provenance check
- Modify: `tests/test_cad_agent_fidelity.py`
- Modify: `README.md`
- Modify: `docs/STATUS.md`

**Interfaces:**
- CLI: `fidelity-dimension-reconstruct --input --manifest --approval --base-dxf`.
- Production review/repair: continue refusing fidelity artifacts.

- [ ] **Step 1: Write the failing CLI test**

```python
def test_dimension_reconstruction_cli_writes_private_candidate(tmp_path: Path) -> None:
    # Prepare the same valid private fixture and invoke main([...]).
    # Assert the printed/output path exists and report state is needs_review.
```

- [ ] **Step 2: Run it to verify it fails**

Expected: argparse rejects the missing `fidelity-dimension-reconstruct` command.

- [ ] **Step 3: Add the parser branch and documentation**

Wire the command to `run_fidelity_dimension_reconstruct`, document the approval
contract and unsupported dimension classes, and state that the result cannot
enter Mechanical production review/repair.

- [ ] **Step 4: Run the CLI and safety tests**

Run: `.venv-py311\\Scripts\\python.exe -m pytest tests/test_cad_agent_fidelity.py -q -p no:cacheprovider`

Expected: all fidelity tests pass.

### Task 4: Regression and delivery

**Files:**
- Modify: `docs/superpowers/specs/2026-07-29-fidelity-dimension-reconstruction-design.md`
- Modify: `docs/superpowers/plans/2026-07-29-fidelity-dimension-reconstruction.md`

- [ ] **Step 1: Run focused suites**

Run: `.venv-py311\\Scripts\\python.exe -m pytest tests/test_cad_agent_fidelity.py dxf_builder_lib/tests/test_builder.py -q -p no:cacheprovider`

Expected: all pass.

- [ ] **Step 2: Run Ruff and the authoritative verifier**

Run: `.venv-py311\\Scripts\\python.exe -m ruff check cad_agent tests scripts` then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1`.

Expected: Ruff passes; offline tests have zero failures/errors/skips; unavailable-state probes skip only their guarded tests.

- [ ] **Step 3: Inspect output and commit**

Reopen the private candidate DXF with `ezdxf`, verify its native entity count
and report hashes, check `git diff --check`, then commit the feature and push
the current branch. Do not add private PDFs or generated fidelity output to Git.
