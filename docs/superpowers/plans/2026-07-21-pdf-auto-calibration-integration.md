# PDF Auto-Calibration Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add auditable per-page automatic OCR calibration to the PDF Primitive IR CLI without replacing unrelated checkout files.

**Architecture:** `run_pdf` owns PDF rendering, CLI validation, page-specific calibration IDs, and manifest reporting.  It forwards image-level OCR/calibration work to `run_image.run`; candidate ROI detection lives in `text_extraction`, and the registry records automatically inferred scales as unverified.

**Tech Stack:** Python 3, argparse, PyMuPDF (`fitz`), OpenCV/Tesseract, pytest.

## Global Constraints

- Copy only the five approved files from `C:\Users\dkv\Downloads\cad-agent-updated_2.zip`.
- Do not extract or overwrite any other ZIP member.
- Automatic calibration records must use `status="needs_verification"`.
- Manual verified calibration remains supported for the original PDF hash.

---

### Task 1: Add image-level automatic calibration dependencies

**Files:**
- Modify: `primitive_ir_lib/text_extraction.py`
- Modify: `primitive_ir_lib/calibration_registry.py`
- Modify: `primitive_ir_lib/run_image.py`
- Test: `primitive_ir_lib/tests/test_run_image.py`

**Interfaces:**
- Produces: `detect_text_candidate_rois(image)`, `add_record(..., status="needs_verification")`, and `run(..., auto_ocr_roi, auto_calibrate, calibration_registry_path, calibration_id)`.

- [ ] **Step 1: Install ZIP versions of the three dependency files**

Extract only the three named files from the ZIP and compare their diff with the current checkout.

- [ ] **Step 2: Run focused image-level tests**

Run: `python -m pytest primitive_ir_lib/tests/test_run_image.py -q`

Expected: PASS, or a clearly reported optional-runtime skip.

### Task 2: Add PDF flags, page IDs, and regression tests

**Files:**
- Modify: `primitive_ir_lib/run_pdf.py`
- Modify: `primitive_ir_lib/tests/test_run_pdf.py`

**Interfaces:**
- Consumes: `run_image.run` auto-calibration arguments from Task 1.
- Produces: `run_pdf(..., scale_mm_per_px: Optional[float], auto_ocr_roi, auto_calibrate, calibration_registry_path, calibration_id_prefix)` and manifest page calibration fields.

- [ ] **Step 1: Install ZIP regression tests and run the new test selection**

Run: `python -m pytest primitive_ir_lib/tests/test_run_pdf.py -q`

Expected before the implementation: failures caused by the missing optional parameters and page manifest fields.

- [ ] **Step 2: Install the ZIP `run_pdf.py` implementation**

Preserve manual-scale and verified-registry modes; reject absent scale without automatic calibration; generate `<prefix>_pageNN` IDs only for automatic registry records.

- [ ] **Step 3: Re-run PDF regression tests**

Run: `python -m pytest primitive_ir_lib/tests/test_run_pdf.py -q`

Expected: PASS.

### Task 3: Verify, commit, and publish

**Files:**
- Modify: `docs/superpowers/specs/2026-07-21-pdf-auto-calibration-integration-design.md`
- Modify: `docs/superpowers/plans/2026-07-21-pdf-auto-calibration-integration.md`

- [ ] **Step 1: Run all Phase 1 tests**

Run: `python -m pytest primitive_ir_lib/tests -q`

Expected: all collected tests pass; optional dependencies may report skips only where tests explicitly allow them.

- [ ] **Step 2: Inspect the final diff**

Run: `git diff --check` and `git status --short`.

Expected: only the five approved source/test files and the design/plan documents are staged for this change.

- [ ] **Step 3: Commit and push**

Run: `git add ...`, `git commit -m "feat: add per-page PDF auto calibration"`, then `git push origin HEAD:main` after confirming the remote branch is fast-forward compatible.
