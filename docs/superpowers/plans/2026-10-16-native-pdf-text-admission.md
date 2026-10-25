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
- [x] Add unique PDF paint-trace binding; exclude invisible, ambiguous, disabled-layer, later-obscured, or unsupported-writing-mode spans; persist paint and writing-mode evidence for fresh revalidation.
- [x] Run the complete focused fidelity test module: 97 passed.
- [x] Run canonical `scripts/verify.ps1 -SkipAutoCADDotNet`: PASS; offline suite 3,672 passed, 23 deselected, 77 subtests; offline .NET IPC 128 passed; causal-RED oracle produced the expected marked failure; real-data probe skipped 2 and AutoCAD probe skipped 18. A first full attempt had one transient M2 hash-seed subprocess error; seed-0/seed-4 direct reproductions and the focused test passed, then the second full canonical run passed.
- [x] Commit the correction as new commit `280cf61bd26e9f02b547f05ec2e6a6f0163a497b`; history was not rewritten. Push is pending.
- [ ] Rerun terminal hosted checks and obtain new independent exact-head Security and Integration reviews.
- [ ] Apply the current #392 V7 procedure only after hosted checks are terminal and the new review head is stable; keep the PR draft and unmerged.

### Task 5: CASE03 named-layer and replacement-glyph observation

**Decision:** Current PO approved one bounded design/regression package in the existing `cad_agent.fidelity` owner after a read-only CASE03 source diagnosis. This does not approve automatic visibility, semantic associations, Primitive IR wiring, native reconstruction, or merge.

**Frozen input:** CASE03 PDF SHA-256 `8478908f9976480d5c9034de6e3354ac113555c2a6fd55550b6b42d29d78232f`.

- [x] Confirm the enabled `Dimensions` layer and the `639±1` / `415±1` spans from rendered crops, texttrace, embedded-font ToUnicode mapping, and same-baseline geometry.
- [x] Add a failing regression for named-layer observation and unique trace recovery where the text dictionary reports U+FFFD.
- [x] Keep `visibility=unverified`, retain per-span human review, and add a conflicting-character fail-closed control.
- [x] Permit only same-font/color/opacity/layer, same-baseline horizontal adjacent-text spans whose `fill-text` paint operation maps uniquely to its trace; cap the trace-bbox gap or overlap at 0.05 pt and 0.5% of the smaller font size. Exclude `stroke-text` because wide stroke expansion can cover earlier glyphs despite adjacent trace bboxes; cover it with a thick-stroke refusal regression.
- [x] Update this design and plan with the narrowed boundary.
- [x] Focused regressions: thick-stroke red reproduced before the fix; complete fidelity module: 109 passed; Ruff passed; `git diff --check` passed.
- [x] CASE03 source-only observation on the PR worktree yielded separate `639`, `±1`, `415`, `±1` spans, each `visibility=unverified`; source SHA-256 remained `8478908f9976480d5c9034de6e3354ac113555c2a6fd55550b6b42d29d78232f` before and after.
- [x] Inspect exact diff and confirm the only changed paths are the approved owner, test, spec, and plan files.
- [ ] Run canonical repository verification on a clean committed head, then refresh PR/check identities before publication.
- [ ] Keep any follow-up outside this approved boundary (visibility automation, semantic association, Primitive IR, native action) unimplemented pending separate authority.

### Task 6: B041 AIGDT GID 80 source-bound observation

**Decision:** PO approved only the exact embedded B041 font profile and unverified source observation in this owner. This task does not add automatic admission, adjacent-span merging, a visibility exception, Primitive IR emission, or native output.

**Frozen identity:** main `3a94b8a94ac8656d7786a20f0ba85570d9cc0b06` / tree `5d6a223db5f76530fc5252b3fe0d8ce2acfb3cb3`; PR #539 head `d574e6cdfb21f3e05a6a3097cb2d487c8f4af6e0` / tree `40c13a39226e4e9850d0c7901734274cc535dd27` remains untouched. B041 source/font/render identity and design boundary are in the spec amendment above.

**Files:**
- Modify: `cad_agent/fidelity.py`
- Test: `tests/test_cad_agent_fidelity.py`
- Update: this existing design spec and plan only.

**Interfaces:**
- Add an owner-local helper that accepts the actual page font resource bytes, source span, and uniquely matched text trace; returns a typed mapping-evidence record only for the exact approved B041 font SHA, GID 80, glyph `uniF06E`, and Windows Symbol cmap U+F06E. All other or ambiguous inputs return no mapping.
- `_native_pdf_text_span_records` uses that mapping only after its current unique trace, opacity, writing-mode, and later-paint checks. The output remains a separate native span observation with `visibility="unverified"`; selection and output continue through existing explicit review and approval gates.

- [ ] Add a real-data failing regression using `CAD_AGENT_B041_PDF`: prove three raw source spans decode to `⌀`, retain raw `n` and exact source/render/font evidence, while only the trace without later-paint overlap enters the current selectable collection; the other two remain excluded.
- [ ] Add resolver-level negative cases using the actual embedded resources: same declared AIGDT name with different font bytes, ambiguous same-name font resources, wrong GID, missing/duplicate trace, and changed cmap/font identity must not receive the special mapping.
- [ ] Run each focused regression and observe the intended RED before implementation.
- [ ] Implement only the exact profile resolver inside `cad_agent.fidelity`; preserve all existing observation, approval, OCR-conflict, clipping, opacity, paint-order, transform, and fresh-reconstruction rules.
- [ ] Run the focused new tests, then `tests/test_cad_agent_fidelity.py` and Ruff.
- [ ] Run the canonical affected verification on the current-main-reconciled PR branch; report real-data/native gates not run separately.
- [ ] Confirm only the four existing PR #522 owner/test/spec/plan paths differ from current main; confirm #539's published head and files remain untouched.
- [ ] Keep PR #522 Draft; refresh hosted checks and independent exact-head reviews only after the implementation head is stable. No merge or native acceptance is implied.
