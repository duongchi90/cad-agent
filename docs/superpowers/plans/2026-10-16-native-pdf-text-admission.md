# Native PDF Text Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicitly reviewed native PDF text spans to the existing fidelity approval/reconstruction path as editable plain DXF `TEXT`.

**Architecture:** Extend the private fidelity sidecar and review/selection UI with a typed native-span path separate from OCR. Reuse the existing per-item approval writer, Unicode glyph check, page transform, and text reconstruction owner; revalidate source/render/span evidence before staging output.

**Tech Stack:** Python 3.11, PyMuPDF, OpenCV, Pillow, ezdxf, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-native-pdf-text-admission-design.md`

## Global Constraints

- PR #521 remains unchanged at base `6c50a4b6a8690692b9d77d1401329ebe44ebac28`, head `ef8c7eee1c778d19957a0c7ba9bb2e9e6362f49e`, tree `ba0cdf234ddc70bc804d9ee98bf250206ebaef3c`.
- Keep native spans separate from OCR candidates and approvals.
- Emit only individually approved, source/render/span-bound plain `TEXT` records.
- Fail closed before output staging when identity, visibility review, transform, placement, or glyph support is unresolved.
- Do not read reference DWG bytes or perform AutoCAD/native mutation.
- Keep production and test code changes to `cad_agent/fidelity.py` and `tests/test_cad_agent_fidelity.py`; design and plan records are the approved documentation artifacts.

## Review Focus

- A stale selection from a prior render must fail before output creation.
- A hand-crafted approval must not relabel a native span as OCR or bypass the typed native selection path.
- Same-text spans at different positions must produce separate `TEXT` entities.
- Off-page/hidden/clipped spans or unsupported page frames must not be emitted.
- Unsupported glyphs or invalid source baseline/font-size metadata must fail before output staging.

**Status:** executing  
**Base SHA:** `ef8c7eee1c778d19957a0c7ba9bb2e9e6362f49e`  
**Completion Head SHA:** pending  
**Verification:** pending; required final command `scripts/verify.ps1 -SkipAutoCADDotNet` plus focused fidelity regressions.  
**Required private/live gates:** CASE06 source span emission `NOT RUN` pending per-item approval; AutoCAD/.NET `NOT RUN`; no reference DWG access; exact-head Security/Integration and #392 V7 required before any merge; context A/B benchmark `NOT RUN`.

---

### Task 1: Bind native span selection to existing per-item approval

**Files:**
- Modify: `cad_agent/fidelity.py`
- Test: `tests/test_cad_agent_fidelity.py`

**Interfaces:**
- Consumes: canonical `fidelity-text-observation-1.0` with `native_pdf_spans` and the existing `fidelity-text-selection-1.0` file.
- Produces: typed native span selection and approval records bound to the exact current source, page, render, span ID, content, and bbox; OCR fields remain unchanged.

- [x] Write a failing test for a browser selection that approves native spans while leaving OCR candidates untouched.
- [x] Run the focused test and confirm it fails because native spans are currently rejected as unknown OCR IDs.
- [x] Extend the review page and selection reader/writer to expose a separately typed native span list and bind its exact snapshot to the current observation/render.
- [x] Run focused selection, duplicate-ID, stale-render, and unchanged OCR tests.
- [ ] Commit the task.

### Task 2: Revalidate and reconstruct only approved native spans

**Files:**
- Modify: `cad_agent/fidelity.py`
- Test: `tests/test_cad_agent_fidelity.py`

**Interfaces:**
- Consumes: Task 1's typed native span approval records and canonical source/render/span binding.
- Produces: `run_fidelity_text_reconstruct` emits one plain `TEXT` entity per approved OCR/native item using existing private layout output, after fresh source/render/audit/span and glyph checks.

- [ ] Write failing tests for selected-only emission, native baseline/rotation/height mapping, distinct equal-text spans, stale/substituted/hidden/clipped/unselected evidence, invalid transform, and unsupported glyph; assert failures happen before output creation.
- [ ] Run the focused tests and confirm the expected missing-path failures.
- [ ] Implement source-page re-render/re-extraction checks and deterministic PDF baseline-to-paper mapping; retain the existing OCR branch and checks unchanged.
- [ ] Run the full fidelity test module, then the focused CASE06 source observation/provenance tests without emitting the real CASE06 spans.
- [ ] Run `scripts/verify.ps1 -SkipAutoCADDotNet`, inspect status/diff, and commit the task.

### Task 3: Final verification and review package

**Files:**
- Review only: all changed files.

- [ ] Run `git diff --check` and confirm the write set is only the two production/test files plus the approved spec and plan.
- [ ] Perform one cheap self-check for false approval/emission paths; preserve exact base/head/tree.
- [ ] Request independent exact-head `SECURITY_REDTEAM` and `INTEGRATION_CI` reviews for the material runtime PR; keep first-pass evidence independent.
- [ ] Apply current #392 V7 procedure only after hosted required checks are terminal and the review head is stable.
- [ ] Record completion head, exact verification results, and live gates in this plan; route durable acceptance to `docs/STATUS.md` only after product acceptance.
- [ ] Do not mark the PR ready or merge it until all current merge gates pass.
