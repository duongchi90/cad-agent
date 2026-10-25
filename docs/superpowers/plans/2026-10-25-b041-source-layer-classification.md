# B041 Source-Layer Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Carry only fully visible, exact-matched B041 `Oculto (ISO)` / `Linha de centro (ISO)` strokes through the existing PDF → Primitive IR → DXF owners without changing geometry.

**Status:** executing
**Base SHA:** `ade737f75ec214377e2e015a4a44ca4d9d42df42`
**Required private/live gates:** B041 real-data source run and DXF review (executed); native AutoCAD save/reopen (not run; remains a separate acceptance gate).

**Architecture:** Reuse the existing PDF renderer and raster LINE detections. A source-layer witness is eligible only after the current PDF render proves visible pixel contribution over its full span, source properties are supported, and one existing raster LINE uniquely matches both endpoints. Keep classification metadata alongside the PDF witness rather than adding it to shared `RawLine`; apply the verified label to the matching Primitive IR line in the existing `run_image` owner. The DXF builder accepts only the two exact canonical values as fallback when semantic ownership is absent.

**Tech Stack:** Python 3.11, PyMuPDF, OpenCV/NumPy, ezdxf, pytest.

**Spec:** Current #491 checkpoint and bounded PO disposition; source input is B041 SHA-256 `bf853aee4ba9b8381476d5ef1fa930d48a478ea56c3fe097695d41210d3afbe3`.

## Global Constraints

- Do not create geometry, split/merge lines, infer centerlines or hatch, or change public schemas.
- Exact source labels only: `Oculto (ISO) → HIDDEN`, `Linha de centro (ISO) → CENTERLINE`.
- Reject partial support, ambiguous correspondence, unsupported opacity/blend, clipping or later-paint loss.
- Preserve semantic DXF layer precedence; named output layers remain `CONTINUOUS`.
- Keep PR #522 untouched; do not claim native DWG acceptance.

## Review Focus

- Partial source support or a raster line spanning a source gap: it remains `UNCLASSIFIED`.
- Two source paths competing for one raster line: it remains `UNCLASSIFIED`.
- SemanticIR layer assignment overrides source classification: preserve semantic layer and emit the approved diagnostic.
- OCG state fails to change the rendered stroke: no classification.
- Unsupported layer labels or arbitrary `Primitive.layer`: DXF fallback remains `UNCLASSIFIED`.

---

### Task 1: Fail-closed layer witness and DXF fallback

**Files:** Modify `primitive_ir_lib/run_pdf.py`, `primitive_ir_lib/run_image.py`, `dxf_builder_lib/builder.py`; test the existing PDF/image and builder suites.

- [ ] Write tests for full-span unique matching, partial-support rejection, ambiguous witnesses, exact canonical builder fallback, arbitrary-label rejection, semantic precedence logging, and unchanged geometry/entity inventory.
- [ ] Run focused tests and confirm the new assertions fail before implementation.
- [ ] Implement pixel-backed source-layer witnesses, classification transfer through existing `RawLine`/`Primitive.layer`, and exact DXF fallback with standard logging for semantic precedence.
- [ ] Run focused tests and B041 real-data → Primitive IR → DXF → strict reviewer checks on the frozen source.
- [ ] Run the canonical verifier, record native DWG save/reopen as `NOT RUN`, and open the separate exact-head review gates; do not merge until required gates pass.

## Verification checkpoint

Code commit verified: `79c488e202de07fa7593d7d0d11b62de317aefdd`.

- Focused owners and B041 real-data after the ownership-safe witness refactor: the same command — 78 passed.
- Ruff on all eight changed Python files — PASS.
- `git diff --check` — PASS.
- `scripts/verify.ps1 -PythonExe 'C:\Users\t3407d\.codex\worktrees\b041-gdt-text-observation\cad-agent\.venv-py311\Scripts\python.exe'` — exit 0; .NET restore/build PASS (existing `MSB3277` WindowsBase warning), .NET tests 261 PASS, IPC offline 128 PASS, Python offline 3,882 PASS / 29 deselected / 88 subtests; the separate causal-RED oracle emitted its expected single marked failure. The verifier reported the private/live probes as unavailable-state SKIP and did not count them as PASS.
- Native AutoCAD save/close/reopen/readback — NOT RUN.
- Exact-head hosted CI, Security and Integration — pending PR creation.
