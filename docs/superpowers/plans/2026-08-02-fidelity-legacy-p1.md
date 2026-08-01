# Implementation plan: fidelity, stable identity, and real-image P1

Worktree: `D:\cad-agent-master\cad-agent\.worktrees\fidelity-legacy-p1`  
Branch: `codex/fidelity-legacy-p1`  
Base: `d06da76`

## 1. Record design and baseline

- Read `AGENTS.md`, `docs/STATUS.md`, the design above, and the current test
  contracts.
- Record the already observed P1 real-image result as RED evidence: the full
  pipeline with Tesseract produced one merged segment for the 2760/1525 chain.
- Commit the spec and this plan before production-code edits.

Commands:

```powershell
git diff --check
git add docs/superpowers/specs/2026-08-02-fidelity-legacy-p1-design.md docs/superpowers/plans/2026-08-02-fidelity-legacy-p1.md
git commit -m "docs: specify fidelity legacy identity and real-image P1"
```

## 2. L1 stable `PART_ID` identity (TDD)

- Add offline reviewer coverage that replaces a component handle with a stale
  value while the exact `PART_ID` entity remains in ModelSpace.
- Add repair coverage that uses the stale handle and asserts no duplicate
  `INSERT` remains.
- Add explicit ambiguous-`PART_ID` coverage that refuses to choose.
- Run the focused tests and observe RED before touching reviewer/repair code.
- Implement one shared resolver in the reviewer/repair boundary (or a small
  private helper module if the existing package structure requires it).
- Update the live E2E helper to rebind the build handle after AutoCAD reopen by
  reading `PART_ID`; do not alter the external dispatcher.

Commands:

```powershell
& .\.venv-py311\Scripts\python.exe -m pytest dxf_builder_lib/tests/test_reviewer.py dxf_builder_lib/tests/test_repair.py -q -p no:cacheprovider
& .\.venv-py311\Scripts\python.exe -m ruff check dxf_builder_lib/reviewer.py dxf_builder_lib/repair.py dxf_builder_lib/tests/test_reviewer.py dxf_builder_lib/tests/test_repair.py
```

## 3. F1 advanced fidelity review queue/index

- Add tests that create private observation, approval, and reconstruction
  report artifacts for advanced kinds and assert queue entries expose their
  state, paths, and hashes.
- Assert missing advanced artifacts are `not_run` and the top-level queue
  remains `needs_review`.
- Implement a bounded helper in `cad_agent/fidelity.py` that reads only known
  private paths and uses `_artifact()` for hash-bound records.
- Extend the existing HTML index with compact advanced status rows. Keep all
  output private and retain current production-refusal behavior.

Commands:

```powershell
& .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_fidelity.py -q -p no:cacheprovider
& .\.venv-py311\Scripts\python.exe -m ruff check cad_agent/fidelity.py tests/test_cad_agent_fidelity.py
```

## 4. P1 witness-barrier regression (TDD)

- Add a deterministic OpenCV fixture with an overlapping long Hough segment,
  two shorter overlapping segments, and an internal perpendicular witness.
- Assert the merged result preserves exactly two chain segments at the witness
  offset. Run the new test RED.
- Implement barrier preservation in `merge_collinear_lines()` while keeping
  the existing public parameters and default safety behavior.
- Run all `primitive_ir_lib` line-merging/tick-mark tests GREEN.
- Run the actual private image with the repository's Tesseract executable and
  `extract_text_tesseract`, `extract_raw_geometry`,
  `merge_collinear_lines`, and `cross_validate`; record the measured boundary
  in an ignored `C:\temp` report only.

Commands:

```powershell
& .\.venv-py311\Scripts\python.exe -m pytest primitive_ir_lib/tests/test_line_merging.py primitive_ir_lib/tests/test_tick_mark_detection.py -q -p no:cacheprovider
& .\.venv-py311\Scripts\python.exe -m pytest primitive_ir_lib/tests/test_real_image_benchmark.py -q -m real_data -p no:cacheprovider
```

The existing real-image test expects the original 1600×900 capture. The local
source located during this turn is the 2382×1685 page scan, so the P1 runner
must use a small private-data adapter with coordinates discovered from OCR; it
must not modify the committed test to fake the old dimensions.

## 5. Integrated verification and status

- Run focused L1/F1/P1 tests, full offline verifier, Ruff, and `git diff
  --check`.
- If the AutoCAD session is available, run the affected disposable
  `autocad_mechanical` component round-trip tests. Every live result is PASS,
  SKIP, or NOT RUN; never infer live PASS from offline tests.
- Review the diff for private-path leaks, production-mutation authorization,
  duplicate resolution, and status vocabulary.
- Update `docs/STATUS.md` only with fresh evidence, then commit.
- Fast-forward merge to `main`, push `main`, verify local `main == origin/main`,
  and leave the primary worktree clean.

## 6. Final review checklist

- No `PROJECT_STATUS.md` created.
- No private image, PDF, DXF, or OCR output tracked.
- Stable identity is exact and unique, never fuzzy.
- Fidelity queue/index does not promote advanced candidates.
- P1 result is explicitly PASS/FAIL/NOT RUN with source hash and dimensions.
- No unresolved P1 finding is hidden by a summary percentage.
