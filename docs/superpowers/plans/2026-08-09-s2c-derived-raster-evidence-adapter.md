# S2C Derived Raster Evidence Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one pure, deterministic, bounded adapter that converts exact bytes from an already validated AutoCAD-native PDF artifact into one derived PNG page plus closed hash-bound evidence, while rejecting encrypted PDFs before page access and proving A4 from physical PDF page geometry.

**Architecture:** Create one adjacent `mcp_integration_lib/derived_raster_evidence.py` module and one focused test file. Reuse `mcp_integration_lib.autocad_render_evidence` unchanged for native authority, accept immutable `pdf_bytes`, fail closed on encryption, derive physical sheet identity from MediaBox + UserUnit, use CropBox only as selected visible raster extent, render one page directly with the locked PyMuPDF runtime, validate PNG bytes in memory, and hash closed records only through `cad_agent.drawing_contracts.canonical_json_sha256()`.

**Tech Stack:** Python 3.11; PyMuPDF 1.28.0; existing Pillow runtime dependency; accepted native render contract; canonical JSON hash owner; pytest; Ruff; architecture checker; canonical verifier.

## Global Constraints

- Issue #144 / PR #145 remain planning only until Master PO issues a separate runtime task on a fresh exact current-main SHA.
- Native `DWG -> PDF` authority remains existing AutoCAD/.NET + `mcp_integration_lib.autocad_render_evidence`.
- `cad_agent.source_fusion` remains input-source custody/provenance only.
- `cad_agent.visual_evidence` remains downstream packaging/freshness, not rendering.
- `primitive_ir_lib.run_pdf()` remains Primitive/OCR/calibration orchestration and is not called by S2C.
- First runtime slice adds no dependency, lock, workflow, contract-directory, manifest, File IPC, AutoCAD, PC3/PMP/profile, OCR/model/provider, approval, verdict, repair or publisher change.
- First runtime slice cumulative write-set is exactly:

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```

- Every runtime task is RED-first with a committed meaningful RED before its production edit.
- Forward commits only; no amend/rebase/squash/force-push/main-sync after issuance.
- `PASS`, `FAIL`, `SKIP`, `NOT RUN` remain literal.
- AutoCAD Mechanical live/private data are not required for first-slice offline acceptance.

---

## 0. Mandatory runtime issuance rebaseline — READ ONLY

- [ ] **Step 1: fresh-fetch and record exact current main**

```powershell
git fetch origin
git rev-parse origin/main
```

Master PO must issue that exact SHA before branch creation.

- [ ] **Step 2: remap accepted owners**

Confirm current-main equivalents of:

```python
mcp_integration_lib.autocad_render_evidence.validate_render_request
mcp_integration_lib.autocad_render_evidence.validate_render_evidence
cad_agent.drawing_contracts.canonical_json_sha256
```

Require native PDF evidence still binds artifact SHA/page count, drawing/latest-mutation/Visual-Run-Manifest identity, layout/render options, `AUTOCAD_NATIVE`, `changed=false`, and equal DBMOD.

Material drift -> STOP/rebaseline.

- [ ] **Step 3: verify locked dependencies**

Confirm PyMuPDF and Pillow remain accepted locked dependencies. A dependency/lock edit blocks this slice.

- [ ] **Step 4: verify no overlap**

No active writer may own either exact S2C path.

- [ ] **Step 5: verify byte-only boundary**

First slice receives exact `pdf_bytes`; it does not discover/read a File IPC pathname.

If an additional path/File-IPC owner is required:

```text
S2C DERIVED-RASTER SCOPE GAP — MASTER PO DECISION REQUIRED
```

---

## Runtime file structure

### Exact cumulative write-set

```text
CREATE mcp_integration_lib/derived_raster_evidence.py
CREATE mcp_integration_lib/tests/test_derived_raster_evidence.py
```

Tasks 2–3 may modify only those same two paths.

### Do not modify

```text
mcp_integration_lib/autocad_render_evidence.py
mcp_integration_lib/dotnet_ipc.py
primitive_ir_lib/run_pdf.py
primitive_ir_lib/run_image.py
cad_agent/source_fusion.py
cad_agent/visual_evidence.py
cad_agent/manifest.py
contracts/**
autocad_plugin/**
requirements/**
.github/workflows/**
```

Any third path -> STOP.

---

## Proposed public surface

```python
DERIVED_RASTER_EVIDENCE_SCHEMA_VERSION = "derived-raster-evidence-1.0"
DERIVED_RASTER_POLICY_VERSION = "pymupdf-derived-raster-v1"

class DerivedRasterEvidenceError(ValueError):
    pass


def derive_native_pdf_page(
    *,
    pdf_bytes: bytes,
    native_request: object,
    native_evidence: object,
    page_index: int,
    render_dpi: int = 300,
) -> tuple[bytes, dict[str, object]]:
    ...


def validate_derived_raster_evidence(
    payload: object,
    *,
    pdf_bytes: bytes,
    png_bytes: bytes,
    native_request: object,
    native_evidence: object,
) -> dict[str, object]:
    ...


def derived_raster_evidence_sha256(
    payload: object,
    *,
    pdf_bytes: bytes,
    png_bytes: bytes,
    native_request: object,
    native_evidence: object,
) -> str:
    ...
```

No pathname/output-path/password parameters may be added.

---

### Task 1: Native binding, encryption refusal and closed evidence core

**Files:**
- RED first: `mcp_integration_lib/tests/test_derived_raster_evidence.py`
- Production only after meaningful RED: `mcp_integration_lib/derived_raster_evidence.py`

**Consumes:** accepted native request/evidence validators and canonical JSON SHA owner.

**Produces:** the public surface above.

- [ ] **Step 1: create synthetic in-memory PDF fixtures**

Use PyMuPDF-generated bytes only. Include:

```text
one-page unencrypted custom PDF
one-page password-protected PDF
one encrypted PDF whose trailer contains /Encrypt
multi-page PDF
malformed/truncated byte fixtures
```

No private/customer files.

- [ ] **Step 2: add native-binding RED**

Require:

```text
valid native PDF request/evidence + matching bytes -> accepted
request/evidence kind PNG -> reject
request/evidence identity mismatch -> reject
wrong PDF bytes -> NATIVE_PDF_HASH_MISMATCH
parsed/native page-count mismatch -> PAGE_COUNT_MISMATCH
strict zero-based page index
unknown/approval/verdict/repair/publication/current fields -> reject
unsafe native relative path -> accepted native validator rejects
native request/evidence hash change -> derived identity changes
```

- [ ] **Step 3: add encryption RED before production**

Required tests:

```text
test_password_protected_pdf_fails_pdf_encrypted_before_page_access
test_encrypt_trailer_fails_even_without_password_prompt
test_encrypted_pdf_never_calls_authenticate
test_encrypted_pdf_never_loads_page_or_renders_pixmap
test_encrypted_failure_returns_no_png_or_evidence
```

The production contract must reject if any of:

```text
document.needs_pass is True
document.is_encrypted is True
PDF trailer contains /Encrypt
document metadata reports non-null encryption
```

No `authenticate()` / password / decrypt path is allowed.

- [ ] **Step 4: prove meaningful RED and commit tests only**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
git add mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "test: define encrypted-safe derived raster contract"
```

Expected RED must be due to absent S2C behavior, not fixture/environment failure.

- [ ] **Step 5: create minimal production module**

Native binding order:

```text
validate type/size
validate native request/evidence
require PDF/AUTOCAD_NATIVE
verify sha256(pdf_bytes)
fitz.open(stream=pdf_bytes, filetype="pdf")
ENCRYPTION GATE
page_count
page_index
```

Encryption gate must execute before `page_count`, `load_page()` or `get_pixmap()`.

If trailer inspection cannot be completed safely, map to `PDF_MALFORMED`; do not rasterize.

- [ ] **Step 6: add closed evidence root**

Accept exactly:

```text
schema_version
policy_version
native_render_request_sha256
native_render_evidence_sha256
run_id
drawing_sha256
latest_mutation_sha256
visual_run_manifest_sha256
layout_identity
native_pdf_sha256
native_pdf_page_count
page_index
media_box
selected_page_box
physical_page_size_mm
rotation_degrees
user_unit
render_dpi
render_matrix
renderer
derived_png_sha256
width_px
height_px
alpha_policy
background_policy
```

Use `canonical_json_sha256()` for normalized native and derived record identity.

- [ ] **Step 7: self-validation and GREEN**

Builder returns only after `validate_derived_raster_evidence()` accepts exact PDF + PNG bytes + record.

Run focused + native-contract regressions.

- [ ] **Step 8: commit production Task 1**

Only the exact two S2C paths may be staged.

---

### Task 2: Physical MediaBox A4 geometry, CropBox, rotation, UserUnit and direct raster matrix

**Files:** modify only the two S2C paths; test first.

**Public surface:** unchanged.

**Locked physical policy:**

```text
A4_CANONICAL_WIDTH_MM  = 210.00
A4_CANONICAL_HEIGHT_MM = 297.00
A4_PHYSICAL_TOLERANCE_MM = 0.10
```

- [ ] **Step 1: add RED physical-geometry fixtures**

Cover:

```text
MediaBox == CropBox
A4 MediaBox with smaller CropBox
595x842 point A4 approximation
exact 210x297 mm equivalent
Letter 612x792 points
rotation 0/90/180/270
UserUnit absent
non-1 UserUnit producing A4 physical size
invalid UserUnit
non-A4 custom page
```

- [ ] **Step 2: lock MediaBox vs CropBox semantics**

Tests must prove:

```text
MediaBox + UserUnit = physical sheet identity
CropBox = selected visible raster extent
Page.rect / output pixels / request paper_size alone != physical A4 authority
```

Record both `media_box` and `selected_page_box`, plus recomputed `physical_page_size_mm`.

- [ ] **Step 3: lock A4 physical classification**

Using deterministic Decimal/rational arithmetic, require each unrotated physical MediaBox dimension to be within inclusive ±0.10 mm of canonical A4 dimensions in either orientation.

Tests:

```text
595x842 pt under UserUnit=1 -> A4 physical classification accepted
612x792 pt -> not A4
A4 request + non-A4 MediaBox -> PAGE_GEOMETRY_MISMATCH
```

- [ ] **Step 4: lock full-sheet selected-box rule**

For native `paper_size == "A4"`, require CropBox four physical edges to coincide with MediaBox within the same ±0.10 mm policy.

Tests:

```text
A4 MediaBox + full-sheet CropBox -> accepted
A4 MediaBox + smaller CropBox -> PAGE_GEOMETRY_MISMATCH
edge offset >0.10 mm -> PAGE_GEOMETRY_MISMATCH
```

This check occurs before pixmap creation.

- [ ] **Step 5: lock UserUnit exactly once**

Absent -> 1. Positive finite may be accepted. Zero/negative/non-finite/excessive -> reject.

A non-1 fixture must prove physical A4 size and target pixels are unchanged when the underlying point coordinates scale inversely.

- [ ] **Step 6: lock rotation**

Accept only `0 | 90 | 180 | 270`.

MediaBox/CropBox evidence remains unrotated PDF page-space geometry; orientation is derived after applying rotation exactly once.

- [ ] **Step 7: lock exact A4 300-DPI output**

For accepted full-sheet A4 physical geometry:

```python
assert portrait_record["width_px"] == 2480
assert portrait_record["height_px"] == 3508
assert landscape_record["width_px"] == 3508
assert landscape_record["height_px"] == 2480
```

Target pixels derive from canonical A4 physical millimetres:

```text
pixels = mm / 25.4 * DPI
```

with deterministic nearest-integer half-up.

Do not derive A4 target pixels from integer-rounded PDF points such as 595x842.

- [ ] **Step 8: lock direct render matrix**

Derive exact six coefficients from selected full-sheet box, physical A4 classification, rotation and DPI.

Forbidden:

```text
render then resize
render then crop to force A4
fit-to-content
caller matrix
arbitrary shear
```

If exact A4 cannot be direct-rendered without destructive post-processing, STOP with scope-gap verdict.

- [ ] **Step 9: PNG and renderer identity RED**

Require PNG format, evidence dimensions, no alpha/transparency, `OPAQUE_NO_ALPHA`, `WHITE`, and runtime-observed:

```python
{
    "name": "PYMUPDF",
    "binding_version": str(fitz.VersionBind),
    "mupdf_version": str(fitz.VersionFitz),
}
```

Version drift changes evidence identity.

- [ ] **Step 10: prove RED and commit test-only change**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
git add mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "test: lock physical A4 raster geometry"
```

- [ ] **Step 11: implement minimum geometry/matrix behavior**

Do not widen public surface or paths.

- [ ] **Step 12: 5x focused GREEN**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

- [ ] **Step 13: upstream regressions + Ruff + commit**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  mcp_integration_lib/tests/test_autocad_render_evidence.py `
  primitive_ir_lib/tests/test_run_pdf.py `
  mcp_integration_lib/tests/test_derived_raster_evidence.py `
  -q -p no:cacheprovider

.\.venv-py311\Scripts\python.exe -m ruff check `
  mcp_integration_lib/derived_raster_evidence.py `
  mcp_integration_lib/tests/test_derived_raster_evidence.py

git diff --check
```

Commit only the two S2C paths.

---

### Task 3: Resource containment, malformed/truncated refusal, replay, privacy and ownership

**Files:** modify only the same two S2C paths; test first.

**Locked bounds:**

```text
MAX_PDF_BYTES         = 64 * 1024 * 1024
MAX_PDF_PAGE_COUNT    = 256
MAX_PAGE_EDGE_PX      = 16_384
MAX_PAGE_PIXELS       = 32_000_000
MAX_DERIVED_PNG_BYTES = 64 * 1024 * 1024
MIN_RENDER_DPI        = 72
MAX_RENDER_DPI        = 600
```

- [ ] **Step 1: add resource/error RED**

Require:

```text
PDF_ENCRYPTED
PDF_MALFORMED
PDF_TOO_LARGE
PDF_PAGE_COUNT_LIMIT
PAGE_COUNT_MISMATCH
PAGE_INDEX_OUT_OF_RANGE
PAGE_GEOMETRY_MISMATCH
PAGE_DIMENSION_LIMIT
RENDER_DPI_OUT_OF_RANGE
PNG_SIZE_LIMIT
PNG_INVALID
RENDER_RESOURCE_FAILURE
```

Use fakes/monkeypatches for huge logical values; do not allocate dangerous payloads.

- [ ] **Step 2: add fail-fast ordering RED**

Prove edge/pixel bounds before pixmap creation and encryption before page access.

Required order:

```text
input type/byte length
native request/evidence
native PDF SHA
open exact bounded bytes
encryption/trailer gate
page count
page index
MediaBox/CropBox/UserUnit/rotation
A4 physical classification if claimed
DPI
target dimensions
edge/pixel limits
one pixmap
PNG encode
PNG size
self-validation
return
```

- [ ] **Step 3: privacy RED**

Inject parser/render exceptions containing fake paths/content and assert public exception is only categorical. Do not interpolate upstream messages.

- [ ] **Step 4: no-partial-output RED**

For encrypted, malformed, geometry-mismatch and resource failures require:

```text
no PNG returned
no evidence returned
no file written
no manifest/cache/store/current pointer mutation
```

- [ ] **Step 5: exact replay RED**

Identical native request/evidence/PDF/page/DPI/geometry/runtime versions repeated at least five times must produce byte-identical PNG, identical normalized evidence and identical canonical hash.

Change one input at a time -> identity change or refusal.

- [ ] **Step 6: static authority RED**

Prohibit production imports from:

```text
ctypes
subprocess
socket
requests
httpx
agent_lib
primitive_ir_lib
semantic_ir_lib
autocad_plugin
mcp_integration_lib.dotnet_ipc
cad_agent.source_fusion
cad_agent.visual_evidence
cad_agent.manifest
```

Also prohibit arbitrary filesystem open/read. Allowed PDF open is only:

```python
fitz.open(stream=pdf_bytes, filetype="pdf")
```

- [ ] **Step 7: prove RED and commit test-only**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
git add mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "test: harden derived raster refusal and replay gates"
```

- [ ] **Step 8: implement minimum hardening**

No retry may change DPI, page box, renderer, encryption handling or alpha/background policy.

- [ ] **Step 9: complete focused/upstream GREEN**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

.\.venv-py311\Scripts\python.exe -m pytest `
  mcp_integration_lib/tests/test_autocad_render_evidence.py `
  primitive_ir_lib/tests/test_run_pdf.py `
  mcp_integration_lib/tests/test_derived_raster_evidence.py `
  -q -p no:cacheprovider
```

- [ ] **Step 10: architecture/Ruff/diff**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check `
  mcp_integration_lib/derived_raster_evidence.py `
  mcp_integration_lib/tests/test_derived_raster_evidence.py

.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check `
  --repo-root . `
  --baseline contracts/reuse-integration/architecture-boundaries.json

git diff --check
git diff --name-only "$env:S2C_TASK_BASE_SHA"..HEAD
```

Exact cumulative result must be exactly two S2C paths.

- [ ] **Step 11: canonical verifier**

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Record literal PASS/FAIL/SKIP/NOT RUN. Offline success cannot promote AutoCAD live to PASS.

- [ ] **Step 12: commit hardening**

Forward commit only, exact two paths.

---

## Focused mandatory test inventory

At minimum implement tests semantically equivalent to:

```text
test_exact_native_pdf_bytes_build_closed_derived_evidence
test_wrong_native_pdf_sha_fails_closed
test_native_request_evidence_mismatch_fails_closed
test_native_page_count_mismatch_fails_closed
test_page_index_is_zero_based_strict_and_bounded
test_password_protected_pdf_fails_before_page_access
test_encrypt_trailer_fails_even_without_password_prompt
test_encrypted_pdf_never_authenticates_or_renders
test_media_box_and_crop_box_have_distinct_authority
test_physical_page_size_comes_from_media_box_and_user_unit
test_a4_595x842_point_encoding_is_physical_a4
test_letter_media_box_is_not_a4
test_a4_media_with_smaller_crop_fails_full_sheet_gate
test_a4_portrait_300dpi_is_exact_2480x3508
test_a4_landscape_300dpi_is_exact_3508x2480
test_rotation_90_and_270_are_deterministic
test_user_unit_is_applied_exactly_once
test_forged_matrix_or_dimensions_fail_closed
test_png_is_opaque_white_and_has_no_alpha
test_renderer_identity_is_runtime_observed
test_renderer_version_drift_changes_evidence_identity
test_identical_inputs_replay_byte_identically_five_times
test_truncated_or_malformed_pdf_fails_privately
test_resource_limits_fail_before_pixmap_creation
test_failure_returns_no_partial_output
test_module_has_no_path_reopen_or_forbidden_authority_imports
```

---

## Migration / rollback

Additive only:

```text
no existing schema migration
no manifest migration
no dependency/lock change
no workflow change
no AutoCAD/plugin change
no Primitive change
no stored-data migration
```

Rollback: remove/revert exactly the two new S2C runtime paths.

---

## Hosted verification

After local/offline GREEN:

1. forward commits only;
2. DRAFT PR;
3. hosted `tests = SUCCESS`;
4. hosted `reuse-declaration = SUCCESS`;
5. record exact current-main / runtime-head / hosted-synthetic SHA triple;
6. independent review binds verdict to that exact triple;
7. STOP WRITE at frozen review-ready state.

Runtime PR reuse declaration must state that native renderer, File IPC/path policy, source custody/fusion, Primitive/OCR/calibration, visual verdict, manifest/store, repair, approval and publication remain existing owners and are not duplicated.

---

## Future live acceptance — separate Issue only

Do not add live-harness paths to this slice.

A later separately issued live gate must reuse existing disposable-DWG/session/open/close/cleanup owners and separately prove:

```text
native PDF evidence valid
source DWG SHA unchanged
native changed=false / DBMOD stable
physical MediaBox/UserUnit classifies A4
full-sheet CropBox equivalent to MediaBox
300 DPI exact PNG dimensions
opaque white / no alpha
renderer fingerprint
request/artifact cleanup
zero survivor processes
PC3/PMP unchanged
```

Offline PASS never implies AutoCAD/File IPC/live-cleanup PASS.

---

## Program-level STOP conditions

Stop and return Master PO disposition if:

- any third first-slice path is required;
- native PDF bytes require a new File IPC/path owner;
- native render schema must change;
- accepted native evidence cannot bind exact PDF bytes;
- encrypted PDFs can only be handled by authentication/decryption/password logic;
- physical A4 identity cannot be established from MediaBox + UserUnit under the locked policy;
- exact A4 output requires destructive post-render resize/crop;
- `primitive_ir_lib.run_pdf()` must be called wholesale;
- Primitive/OCR/calibration/Semantic/source-fusion/visual-evidence authority must move;
- new manifest/store/cache/current pointer is required;
- dependency/lock/workflow/contract change is required;
- process supervisor is required for first offline slice;
- renderer identity/version cannot be observed deterministically;
- private/customer CAD is required;
- current main or an active writer overlaps either exact S2C path;
- an accepted regression must be weakened/skipped to obtain GREEN.

Architectural failure result:

```text
S2C DERIVED-RASTER SCOPE GAP — MASTER PO DECISION REQUIRED
```

## Planning handoff

This plan is executable only after fresh runtime issuance. The first slice remains two new pure-Python paths, byte-only, unencrypted-input-only, pathless, persistence-free, no AutoCAD live execution, no private CAD, no dependency migration, and no change to accepted native/Primitive/visual/source-fusion owners.
