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
- Off-page/clipped spans and unsupported page frames must not be emitted; hidden or illegible spans require the reviewer to reject the exact source-render-span item.
- Unsupported glyphs or invalid source baseline/font-size metadata must fail before output staging.

**Status:** awaiting exact-head review and applicable gates

**Base SHA:** `6c50a4b6a8690692b9d77d1401329ebe44ebac28`

**Implementation Head SHA before security correction:** `b083815ba5c46a332b7f1c3dbe584ace7c357a50` (tree `893a5e37fa35387caefc9e646c53f25a16f24bfa`).

**Verification:** `scripts/verify.ps1 -SkipAutoCADDotNet` passed at the implementation head; 3,665 Python tests passed, 23 deselected, 77 subtests passed; .NET IPC offline set 128 passed; required causal-RED negative oracle reported its expected marked failure; unavailable real-data probe skipped 2 and AutoCAD live probe skipped 18. Focused fidelity module: 90 passed. `git diff --check` passed.
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
- [x] Commit the task.

### Task 2: Revalidate and reconstruct only approved native spans

**Files:**
- Modify: `cad_agent/fidelity.py`
- Test: `tests/test_cad_agent_fidelity.py`

**Interfaces:**
- Consumes: Task 1's typed native span approval records and canonical source/render/span binding.
- Produces: `run_fidelity_text_reconstruct` emits one plain `TEXT` entity per approved OCR/native item using existing private layout output, after fresh source/render/audit/span and glyph checks.

- [x] Write failing tests for selected-only emission, native baseline/rotation/height mapping, distinct equal-text spans, stale source/render, unselected evidence, invalid transform, and glyph evidence; assert failures happen before output creation. Visibility remains an explicit human review decision, not an inferred detector result.
- [x] Run the focused tests and confirm the expected missing-path failures.
- [x] Implement source-page re-render/re-extraction checks and deterministic PDF baseline-to-paper mapping; retain the existing OCR branch and checks unchanged.
- [x] Run the full fidelity test module, then the focused CASE06 source observation/provenance tests without emitting the real CASE06 spans.
- [x] Run `scripts/verify.ps1 -SkipAutoCADDotNet`, inspect status/diff, and commit the task.

### Task 3: Final verification and review package

**Files:**
- Review only: all changed files.

- [x] Run `git diff --check` and confirm the write set is only the two production/test files plus the approved spec and plan.
- [x] Perform one cheap self-check for false approval/emission paths; preserve exact base/head/tree.
- [ ] Request independent exact-head `SECURITY_REDTEAM` and `INTEGRATION_CI` reviews for the material runtime PR; keep first-pass evidence independent.
- [ ] Apply current #392 V7 procedure only after hosted required checks are terminal and the review head is stable.
- [ ] Record completion head, exact verification results, and live gates in this plan; route durable acceptance to `docs/STATUS.md` only after product acceptance.
- [ ] Do not mark the PR ready or merge it until all current merge gates pass.

### Task 4: Close exact-head Security findings

**Files:**
- Modify: `cad_agent/fidelity.py`
- Test: `tests/test_cad_agent_fidelity.py`
- Update: this approved design spec and plan to record the paint-visibility boundary.

**Security findings at prior exact head `b083815ba5c46a332b7f1c3dbe584ace7c357a50`:**
- Hidden/native OCR-layer spans could enter the separately reviewed native collection and be emitted over coincident visible raster text.
- Vertical PDF writing mode was not recorded and could be emitted as ordinary rotated DXF `TEXT`.

- [x] Add failing regressions for hidden OCR over visible raster text, zero opacity, clipping-only text, later paint overlap, disabled optional-content text, and nonzero writing mode.
- [x] Run those regressions and observe failures at the affected admission boundary.
- [x] Add unique PDF paint-trace binding; exclude invisible, ambiguous, layered, later-obscured, or unsupported-writing-mode spans; persist paint and writing-mode evidence for fresh revalidation.
- [x] Run the complete focused fidelity test module: 97 passed.
- [x] Run canonical `scripts/verify.ps1 -SkipAutoCADDotNet`: PASS; offline suite 3,672 passed, 23 deselected, 77 subtests; offline .NET IPC 128 passed; causal-RED oracle produced the expected marked failure; real-data probe skipped 2 and AutoCAD probe skipped 18. A first full attempt had one transient M2 hash-seed subprocess error; seed-0/seed-4 direct reproductions and the focused test passed, then the second full canonical run passed.
- [x] Commit the correction as new commit `280cf61bd26e9f02b547f05ec2e6a6f0163a497b`; history was not rewritten. Push is pending.
- [ ] Rerun terminal hosted checks and obtain new independent exact-head Security and Integration reviews.
- [ ] Apply the current #392 V7 procedure only after hosted checks are terminal and the new review head is stable; keep the PR draft and unmerged.
