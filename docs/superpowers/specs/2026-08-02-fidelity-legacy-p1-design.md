# Fidelity, stable component identity, and real-image P1 design

Date: 2026-08-02
Status: approved for implementation in the isolated `codex/fidelity-legacy-p1` worktree

## Context

The Windows AutoCAD Mechanical 2027 run on 2026-08-02 exposed two independent
gaps:

1. AutoCAD Mechanical can renumber `INSERT` handles after save/reopen. The
   reviewer and repair path currently treats the build-time handle as the only
   identity, so a valid component is reported missing and repair can append a
   duplicate.
2. The advanced visual-fidelity outputs are deliberately review-only, but the
   static review queue does not expose the text, table-text, dimension, hatch,
   and linetype sidecars/candidates together with their current hash-bound
   states.
3. The private real drawing benchmark is available locally as
   `C:\Users\duong\OneDrive\Desktop\Workspake\xe cai tao\pdf_pages_review\hires\bv (1)_p01.png`.
   The current full `merge_collinear_lines()` run with real OCR produces one
   continuous dimension-chain segment, so the internal 2760/1525 boundary still
   needs a regression fix and fresh evidence.

## Goals

- Make `PART_ID` the stable semantic fallback for component `INSERT` identity,
  while retaining the handle as the fast path.
- Make the fallback safe: zero or multiple matching `PART_ID` values is an
  explicit mismatch/skip, never an arbitrary selection.
- Make component repair remove the resolved old `INSERT` before creating its
  replacement, preventing duplicates after a Mechanical round trip.
- Extend the private fidelity review queue/index with hash-bound advanced
  artifact states, without promoting any candidate to production or Mechanical
  mutation.
- Preserve internal witness boundaries detected on the longest fused raw line
  when overlapping Hough segments would otherwise bridge them.
- Run the full P1 pipeline on the private image with Tesseract OCR and record
  PASS/FAIL/NOT RUN honestly.

## Non-goals and safety boundary

- No production drawing, `Drawing1.dwg`, or customer DXF is opened, saved, or
  mutated.
- No AutoCAD/LISP/.NET configuration changes.
- No model-view export or authoritative dimension/hatch/linetype claim.
- No private image or generated private DXF is committed.
- Existing fidelity candidates remain `needs_review`; the review queue grants no
  `mechanical-review`, `mechanical-repair`, or `production-save` action.

## Contracts

### Stable component identity

For each `part_id` in `BuildResult`:

1. Resolve `component_handle_by_part_id[part_id]` first.
2. If that handle is absent, scan ModelSpace `INSERT` entities for an exact
   `PART_ID` attribute match. The expected block name is an additional filter
   when available.
3. Exactly one match rebinds the BuildResult handle to the current entity and
   continues normal block/layer/geometry/attribute checks.
4. Zero matches records the existing missing-entity mismatch. More than one
   match records an explicit ambiguous-identity mismatch and does not select an
   entity.

The repair path uses the same resolver. A stale build handle therefore removes
the one `PART_ID`-matching old entity before inserting the corrected component.

### Advanced fidelity review queue

`fidelity-review-queue` keeps the existing top-level `state: needs_review` and
adds one `advanced_reviews` list per page. Each entry contains:

- a stable kind (`text`, `table_text`, `dimension`, `hatch`, or `linetype`);
- the observed/approved/candidate state read from the private sidecar/report;
- only paths inside the private output root;
- SHA-256 metadata for every listed artifact;
- a human next action.

The HTML review index shows the same statuses and links. Missing sidecars are
reported as `not_run`; they are not inferred to be passed. Existing promotion
logic remains unchanged and only the already-approved paper-layout/primary-line
scope can reach `approved_for_mechanical_review`.

### P1 line merging

When `split_internal_witness_lines=True`, the merge stage records internal
witness offsets found on the longest original line in each collinear cluster.
All overlapping pieces are clipped at those offsets and the grouping step is
not allowed to join across an offset. This retains a boundary even when a
second Hough detection overlaps both sides of it. Existing gap/text/tick rules
remain unchanged for clusters without an internal witness barrier.

## Dependency graph and file ownership

| Task | Depends on | Files allowed to change | Required evidence |
|---|---|---|---|
| L1 stable identity | spec | `dxf_builder_lib/reviewer.py`, `dxf_builder_lib/repair.py`, their tests, live E2E helper | focused RED/GREEN tests; live disposable component round trip |
| F1 advanced review queue | spec | `cad_agent/fidelity.py`, `tests/test_cad_agent_fidelity.py` | focused queue/index tests; verifier |
| P1 witness barrier | spec | `primitive_ir_lib/line_merging.py`, `primitive_ir_lib/tests/test_line_merging.py`, benchmark docs | RED/GREEN synthetic regression; real private image run |
| Integration/status | L1/F1/P1 | `docs/STATUS.md` only after evidence | diff review, verifier, fresh status check |

No task may change the same production file as another task concurrently. The
isolated worktree is the integration boundary for this turn.

## Acceptance criteria

- Legacy component tests no longer fail solely because Mechanical renumbered an
  `INSERT` handle; ambiguous identity remains a hard failure.
- Repair with a stale handle leaves one component with the expected `PART_ID`.
- Queue/index tests prove advanced artifacts and SHA-256 values are visible and
  the queue remains review-only.
- The synthetic line-merging regression passes without changing existing line,
  tick-mark, or text-anchor tests.
- The private real-image P1 run reports a fresh, reproducible result. A failure
  remains a documented failure and is not promoted to PASS.
- `scripts/verify.ps1`, `git diff --check`, and the applicable live/offline
  gates are run before integration.
