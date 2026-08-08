# S2C Derived Raster Evidence Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one pure, deterministic, bounded adapter that converts exact bytes from an already validated AutoCAD-native PDF artifact into one derived PNG page plus closed hash-bound evidence, without creating a second native renderer, source-custody owner, Primitive/OCR path, visual verdict owner, or persistence store.

**Architecture:** Create one adjacent `mcp_integration_lib/derived_raster_evidence.py` module and one focused test file. The module reuses `mcp_integration_lib.autocad_render_evidence` unchanged for native request/evidence authority, verifies exact PDF bytes, rasterizes one page with the already locked PyMuPDF runtime, validates PNG bytes in memory, and hashes closed records only through `cad_agent.drawing_contracts.canonical_json_sha256()`. No AutoCAD/File IPC integration or persistence belongs in the first slice.

**Tech Stack:** Python 3.11; PyMuPDF 1.28.0 from the accepted Windows lock; existing Pillow runtime dependency for PNG structural inspection; `mcp_integration_lib.autocad_render_evidence`; `cad_agent.drawing_contracts.canonical_json_sha256`; pytest; Ruff; repository architecture checker; canonical verifier.

## Global Constraints

- Runtime is not authorized by Issue #144; every future runtime child Issue needs a fresh exact current-main SHA and explicit Master PO authorization.
- Native `DWG -> PDF` authority remains the existing AutoCAD/.NET path plus `mcp_integration_lib.autocad_render_evidence`.
- `cad_agent.source_fusion` remains input-source PDF custody/render provenance only.
- `cad_agent.visual_evidence` remains downstream packaging/freshness, not rendering.
- `primitive_ir_lib.run_pdf()` remains Primitive/OCR/calibration orchestration and is not called by S2C.
- First runtime slice adds no dependency, lock, workflow, contract-schema-directory, manifest, File IPC, AutoCAD, PC3/PMP/profile, OCR/model/provider, approval, verdict, repair or publisher change.
- First runtime slice cumulative write-set is exactly:

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```

- Every task is RED-first with a committed meaningful RED before its production edit.
- Use forward commits only; no amend, rebase, squash, force-push or main-sync after a child branch is issued.
- `PASS`, `FAIL`, `SKIP`, and `NOT RUN` remain literal.
- AutoCAD Mechanical live and private/customer data are not required for first-slice offline acceptance.

---

## 0. Mandatory runtime issuance rebaseline — READ ONLY

No repository write occurs in this gate.

- [ ] **Step 1: record exact current main**

```powershell
git fetch origin
git rev-parse origin/main
```

Use that exact SHA as the runtime issuance base.

- [ ] **Step 2: map accepted native symbols**

Record the exact current-main paths/symbols semantically equivalent to:

```python
mcp_integration_lib.autocad_render_evidence.validate_render_request
mcp_integration_lib.autocad_render_evidence.validate_render_evidence
cad_agent.drawing_contracts.canonical_json_sha256
```

Require the accepted native PDF evidence to still bind native artifact SHA-256, PDF page count, drawing/latest-mutation/Visual-Run-Manifest identity, layout, render options, `AUTOCAD_NATIVE`, read-only `changed=false`, and equal DBMOD.

Material contract drift blocks branch creation and requires Master PO rebaseline.

- [ ] **Step 3: verify accepted renderer dependencies**

Confirm the current accepted lock supplies PyMuPDF and Pillow without dependency changes. Record exact versions.

A new dependency or lock edit blocks first-slice issuance.

- [ ] **Step 4: verify path overlap**

Require no active writer on:

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```

- [ ] **Step 5: verify clean bytes boundary**

The first slice accepts `pdf_bytes` directly and does not change File IPC/artifact transport.

If the system cannot obtain exact native PDF bytes through an existing approved handoff without adding a second path/File-IPC owner, return:

```text
S2C DERIVED-RASTER SCOPE GAP — MASTER PO DECISION REQUIRED
```

- [ ] **Step 6: create isolated runtime branch from exact issuance SHA**

Do this only after Steps 1–5 pass.

---

## Runtime file structure

### Task 1 creates

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```

### Tasks 2–3 modify

Only the same two paths.

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

Any third path is a STOP condition.

---

### Task 1: Native PDF binding and closed evidence core

**Files:**
- Create first for RED: `mcp_integration_lib/tests/test_derived_raster_evidence.py`
- Create after meaningful RED: `mcp_integration_lib/derived_raster_evidence.py`

**Interfaces:**

Consumes:

```python
validate_render_request(payload: object) -> dict[str, object]
validate_render_evidence(payload: object, request: object | None = None) -> dict[str, object]
canonical_json_sha256(payload: Mapping[str, object]) -> str
```

Produces:

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
) -> tuple[bytes, dict[str, object]]: ...


def validate_derived_raster_evidence(
    payload: object,
    *,
    pdf_bytes: bytes,
    png_bytes: bytes,
    native_request: object,
    native_evidence: object,
) -> dict[str, object]: ...


def derived_raster_evidence_sha256(
    payload: object,
    *,
    pdf_bytes: bytes,
    png_bytes: bytes,
    native_request: object,
    native_evidence: object,
) -> str: ...
```

The `...` above denotes Python return-type notation for the future public API only; production implementation must contain no placeholder body.

- [ ] **Step 1: write synthetic native fixtures in the RED-only test file**

Use in-memory PyMuPDF PDFs. The basic non-A4 fixture must declare a neutral paper label so later A4 geometry enforcement does not invalidate Task-1 tests:

```python
import hashlib
import fitz


def make_pdf_bytes(width_pt: float = 200.0, height_pt: float = 100.0) -> bytes:
    document = fitz.open()
    page = document.new_page(width=width_pt, height=height_pt)
    page.draw_line((10, 10), (190, 90), color=(0, 0, 0), width=1)
    result = document.tobytes()
    document.close()
    return result


def native_pair(pdf_bytes: bytes) -> tuple[dict[str, object], dict[str, object]]:
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    request = {
        "schema_version": "autocad-native-render-request-1.0",
        "request_id": "native-pdf-001",
        "run_id": "run-001",
        "drawing_sha256": "a" * 64,
        "latest_mutation_sha256": "b" * 64,
        "visual_run_manifest_sha256": "c" * 64,
        "layout": {"identity": "layout-001", "name": "Layout1"},
        "artifact_kind": "PDF",
        "render_options": {
            "background": "white",
            "dpi": 300,
            "fit_to_paper": True,
            "paper_size": "SYNTHETIC_CUSTOM",
            "plot_style": "monochrome.ctb",
        },
        "requested_at": "2026-08-09T00:00:00Z",
    }
    evidence = {
        "schema_version": "autocad-native-render-evidence-1.0",
        "request_id": request["request_id"],
        "run_id": request["run_id"],
        "drawing_sha256": request["drawing_sha256"],
        "latest_mutation_sha256": request["latest_mutation_sha256"],
        "visual_run_manifest_sha256": request["visual_run_manifest_sha256"],
        "layout": request["layout"],
        "artifact_kind": "PDF",
        "render_options": request["render_options"],
        "renderer": "AUTOCAD_NATIVE",
        "artifact": {"relative_path": "artifacts/layout.pdf", "sha256": digest, "page_count": 1},
        "capture_timestamp": "2026-08-09T00:00:01Z",
        "changed": False,
        "dbmod_before": 0,
        "dbmod_after": 0,
        "warnings": [],
    }
    return request, evidence
```

- [ ] **Step 2: add Task-1 RED matrix**

Cover:

```text
missing module/public surface -> meaningful RED
valid PDF pair + exact bytes -> PNG bytes + closed evidence
request kind PNG -> reject
evidence kind PNG -> reject
request/evidence identity mismatch -> existing validator reject
wrong PDF bytes -> NATIVE_PDF_HASH_MISMATCH
parsed/native page-count mismatch -> PAGE_COUNT_MISMATCH
negative/bool/non-int/out-of-range page index -> reject
unknown derived field -> reject
approval/verdict/repair/publication/current fields -> reject
unsafe native relative path -> existing validator reject
native request/evidence digest change -> derived identity change
```

- [ ] **Step 3: run RED and commit tests only**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
```

Expected: import/public-surface failures caused by the absent S2C module.

```powershell
git add mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "test: define derived raster evidence contract"
```

- [ ] **Step 4: implement native binding and privacy-safe errors**

Create the production module with this exact ownership pattern:

```python
import hashlib
import fitz

from cad_agent.drawing_contracts import canonical_json_sha256
from mcp_integration_lib.autocad_render_evidence import (
    AutoCADRenderEvidenceError,
    validate_render_evidence,
    validate_render_request,
)


def _fail(code: str) -> None:
    raise DerivedRasterEvidenceError(code)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validated_native_pdf(
    *,
    pdf_bytes: bytes,
    native_request: object,
    native_evidence: object,
) -> tuple[dict[str, object], dict[str, object]]:
    if type(pdf_bytes) is not bytes:
        _fail("PDF_BYTES_INVALID")
    try:
        request = validate_render_request(native_request)
        evidence = validate_render_evidence(native_evidence, request=request)
    except AutoCADRenderEvidenceError:
        _fail("NATIVE_RENDER_EVIDENCE_INVALID")
    if request["artifact_kind"] != "PDF" or evidence["artifact_kind"] != "PDF":
        _fail("NATIVE_ARTIFACT_NOT_PDF")
    if _sha256_bytes(pdf_bytes) != evidence["artifact"]["sha256"]:
        _fail("NATIVE_PDF_HASH_MISMATCH")
    return request, evidence
```

Do not interpolate upstream exception strings.

- [ ] **Step 5: implement closed evidence root and canonical native digests**

The validator accepts exactly:

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
selected_page_box
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

Canonical native digests must be computed only with `canonical_json_sha256()` over the accepted normalized native request/evidence mappings.

- [ ] **Step 6: implement one-page byte-only parsing**

```python
with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
    if document.page_count != evidence["artifact"]["page_count"]:
        _fail("PAGE_COUNT_MISMATCH")
    if type(page_index) is not int or not 0 <= page_index < document.page_count:
        _fail("PAGE_INDEX_OUT_OF_RANGE")
    page = document.load_page(page_index)
```

Render only the selected page. No filesystem open and no call to `primitive_ir_lib.run_pdf()`.

- [ ] **Step 7: make builder self-validate**

Before return, call `validate_derived_raster_evidence()` with exact PDF and produced PNG bytes.

`derived_raster_evidence_sha256()` must return `canonical_json_sha256()` of that validated record.

- [ ] **Step 8: focused GREEN + native regressions**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest \
  mcp_integration_lib/tests/test_derived_raster_evidence.py \
  mcp_integration_lib/tests/test_autocad_render_evidence.py \
  -q -p no:cacheprovider
```

- [ ] **Step 9: Ruff/diff/commit**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check \
  mcp_integration_lib/derived_raster_evidence.py \
  mcp_integration_lib/tests/test_derived_raster_evidence.py

git diff --check
git diff --name-only "$env:S2C_TASK_BASE_SHA"..HEAD
```

Exact cumulative paths: two S2C paths only.

```powershell
git add mcp_integration_lib/derived_raster_evidence.py mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "feat: bind native PDF to derived raster evidence"
```

**Reviewer:** native-evidence/provenance + architecture/reuse.

---

### Task 2: Page geometry, exact A4/300 DPI, matrix, alpha and renderer identity

**Files:** modify only the same two S2C paths; test first.

**Public surface:** unchanged.

- [ ] **Step 1: add RED fixtures**

Synthetic in-memory PDFs must cover:

```text
crop == media
crop != media
rotation 0/90/180/270
UserUnit absent
UserUnit 2
A4 portrait
A4 landscape
non-A4 while native request claims A4
```

- [ ] **Step 2: lock exact A4 assertions**

```python
assert portrait_record["width_px"] == 2480
assert portrait_record["height_px"] == 3508
assert landscape_record["width_px"] == 3508
assert landscape_record["height_px"] == 2480
```

A forged one-pixel difference must fail validation.

- [ ] **Step 3: lock decimal dimension policy**

Use an explicit nearest-integer half-up rule:

```python
from decimal import Decimal, ROUND_HALF_UP


def expected_pixels(points: str, dpi: int) -> int:
    value = Decimal(points) * Decimal(dpi) / Decimal(72)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
```

Tests require deterministic matrix recomputation, deterministic rotation/orientation, UserUnit applied exactly once, and `PAGE_GEOMETRY_MISMATCH` for A4 claim vs non-A4 observed geometry.

- [ ] **Step 4: add alpha/background RED**

Decode returned PNG with existing Pillow and require:

```text
format = PNG
size = evidence width/height
mode has no alpha/transparency
alpha_policy = OPAQUE_NO_ALPHA
background_policy = WHITE
```

Forged alpha/background must fail.

- [ ] **Step 5: add renderer identity RED**

Evidence must record runtime-observed:

```python
{
    "name": "PYMUPDF",
    "binding_version": str(fitz.VersionBind),
    "mupdf_version": str(fitz.VersionFitz),
}
```

Version drift must change evidence identity and cannot count as exact replay.

- [ ] **Step 6: prove RED and commit test-only change**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
git add mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "test: lock derived raster geometry and renderer policy"
```

- [ ] **Step 7: implement page geometry**

Production helpers must return closed normalized values for:

```text
effective crop-box coordinates in points
rotation in {0,90,180,270}
canonical UserUnit
physical width/height after accepted PyMuPDF UserUnit semantics
target integer width/height using Decimal + ROUND_HALF_UP
```

Use PyMuPDF page geometry consistently; do not multiply UserUnit twice.

- [ ] **Step 8: implement direct target raster matrix**

Derive the six coefficients from observed box/rotation, requested DPI and target integer dimensions. Render directly to that target raster with `alpha=False`.

Do **not** render at an implicit size and then resize/crop to force A4.

If exact A4 dimensions require content-destructive post-processing, stop with the scope-gap verdict.

- [ ] **Step 9: implement exact PNG validation**

`validate_derived_raster_evidence()` must verify PNG SHA, decoded size, PNG format and no-alpha policy from `png_bytes` rather than trusting the record.

- [ ] **Step 10: 5x deterministic GREEN**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

- [ ] **Step 11: upstream regressions and commit**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest \
  mcp_integration_lib/tests/test_autocad_render_evidence.py \
  primitive_ir_lib/tests/test_run_pdf.py \
  mcp_integration_lib/tests/test_derived_raster_evidence.py \
  -q -p no:cacheprovider

.\.venv-py311\Scripts\python.exe -m ruff check \
  mcp_integration_lib/derived_raster_evidence.py \
  mcp_integration_lib/tests/test_derived_raster_evidence.py

git diff --check

git add mcp_integration_lib/derived_raster_evidence.py mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "feat: lock deterministic PDF raster geometry"
```

**Reviewer:** raster determinism/page geometry + no-second-renderer authority.

---

### Task 3: Resource containment, replay, privacy and final ownership gates

**Files:** modify only the same two paths; test first.

**Locked proposed bounds:**

```text
MAX_PDF_BYTES         = 64 * 1024 * 1024
MAX_PDF_PAGE_COUNT    = 256
MAX_PAGE_EDGE_PX      = 16_384
MAX_PAGE_PIXELS       = 32_000_000
MAX_DERIVED_PNG_BYTES = 64 * 1024 * 1024
MIN_RENDER_DPI        = 72
MAX_RENDER_DPI        = 600
```

A future runtime Issue may tighten these before RED from synthetic evidence; it may not widen them implicitly during implementation.

- [ ] **Step 1: add RED resource tests**

Require categorical failures:

```text
PDF_TOO_LARGE
PDF_PAGE_COUNT_LIMIT
PAGE_INDEX_OUT_OF_RANGE
PAGE_DIMENSION_LIMIT
RENDER_DPI_OUT_OF_RANGE
PNG_SIZE_LIMIT
PDF_MALFORMED
RENDER_RESOURCE_FAILURE
PNG_INVALID
```

Use fakes/monkeypatching for logically huge values instead of allocating dangerous payloads. Prove edge/pixel limits run before pixmap creation.

- [ ] **Step 2: add privacy RED**

Inject parser/render exceptions containing fake paths/content and assert public S2C exceptions contain only categorical codes, never upstream message/path/content.

- [ ] **Step 3: add exact replay RED**

For identical native request/evidence/PDF/page/DPI/runtime version, run derivation at least five times and require identical PNG bytes, normalized record and canonical record hash.

Change one input at a time and require identity change or refusal:

```text
native request digest
native evidence digest
PDF digest
page index/page count
box/rotation/UserUnit
DPI/matrix
PyMuPDF binding version
MuPDF engine version
alpha/background policy
```

- [ ] **Step 4: add static authority RED**

Parse production AST and prohibit imports from:

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

Also prohibit arbitrary filesystem `open()`/`Path.read_bytes()` in S2C. `fitz.open(stream=pdf_bytes, filetype="pdf")` is allowed.

- [ ] **Step 5: prove RED and commit test-only change**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
git add mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "test: harden derived raster resource and replay gates"
```

- [ ] **Step 6: implement fail-fast resource order**

Required order:

```text
validate input type/byte length
validate native request/evidence
verify native PDF SHA
open bounded bytes
validate page count
validate page index
observe geometry
validate DPI
compute target dimensions
validate edge/pixel limits
render one pixmap
encode PNG
validate PNG byte length
self-validate PDF+PNG+evidence
return
```

No retry may change DPI, page box, renderer or alpha policy.

- [ ] **Step 7: implement privacy-safe exception mapping**

Catch expected PyMuPDF/Pillow/resource exceptions and map to categorical S2C codes without interpolating source exceptions. Do not hide programmer assertions/type bugs or process-control exceptions.

- [ ] **Step 8: complete GREEN**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

.\.venv-py311\Scripts\python.exe -m pytest \
  mcp_integration_lib/tests/test_autocad_render_evidence.py \
  primitive_ir_lib/tests/test_run_pdf.py \
  mcp_integration_lib/tests/test_derived_raster_evidence.py \
  -q -p no:cacheprovider
```

- [ ] **Step 9: architecture/Ruff/diff**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check \
  mcp_integration_lib/derived_raster_evidence.py \
  mcp_integration_lib/tests/test_derived_raster_evidence.py

.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check \
  --repo-root . \
  --baseline contracts/reuse-integration/architecture-boundaries.json

git diff --check
git diff --name-only "$env:S2C_TASK_BASE_SHA"..HEAD
```

Exact cumulative path set remains the two S2C paths.

- [ ] **Step 10: canonical verifier**

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Record exact PASS/FAIL/SKIP/NOT RUN. AutoCAD live remains `NOT RUN` in first-slice offline acceptance.

- [ ] **Step 11: commit hardening**

```powershell
git add mcp_integration_lib/derived_raster_evidence.py mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "feat: harden derived raster replay and limits"
```

- [ ] **Step 12: hosted/current-main synthetic**

Open/retain a DRAFT PR only after focused GREEN and require:

```text
tests = PASS
reuse-declaration = PASS
```

Independent review binds verdict to exact main/head/synthetic SHA triple.

**Reviewer:** security/resource/privacy + integration/CI/write-set.

---

## Future integration task — separate Issue only

After the pure slice is accepted, a separate Master PO Issue may connect exact verified native PDF artifact bytes to S2C.

It must first identify the existing artifact-byte handoff owner. Do not assume `mcp_integration_lib/dotnet_ipc.py` must change.

Any need to modify:

```text
mcp_integration_lib/dotnet_ipc.py
cad_agent.visual_evidence.py
contracts/**
autocad_plugin/**
```

requires a fresh exact write-set and overlap review.

## Future live acceptance — separate authorization only

Use synthetic disposable data:

```text
accepted isolated AutoCAD profile/media configuration
-> existing AutoCAD/.NET native A4 PDF
-> validate native request/evidence
-> obtain exact verified PDF bytes through existing owner
-> S2C derive page 0 at 300 DPI
-> require 2480x3508 portrait OR 3508x2480 landscape from observed geometry
-> repeat and require byte-identical PNG/evidence
-> prove native PDF/drawing/DBMOD unchanged
-> downstream read-only evidence handoff
-> existing cleanup owner
```

Truthful status:

```text
missing profile/PC3/PMP/native PDF prerequisite = NOT RUN
unavailable-state probe = SKIP only, never PASS
executed synthetic live gate satisfying exact postconditions = PASS
private/customer CAD = not required
```

S2C never mutates PC3/PMP/profile configuration.

## Future runtime PR reuse declaration

**Existing capability inspected:** native render contract/tests, AutoCAD/.NET native path, source-fusion provenance, visual packaging, Primitive `run_pdf`, canonical hashing, current PyMuPDF/Pillow lock.

**Existing API reused:** `validate_render_request`, `validate_render_evidence`, `canonical_json_sha256`, existing PyMuPDF/Pillow dependencies.

**Adapter required:** one pure native-PDF-bytes -> PNG/evidence module.

**New capability genuinely missing:** deterministic derived-raster evidence for generated native PDF artifacts.

**Files allowed to change:** exact two S2C paths.

**Files forbidden to duplicate:** native renderer, File IPC/path policy, source custody/fusion, Primitive/OCR/calibration, visual verdict, manifest/store, repair, approval, publisher.

**Compatibility behavior:** existing owners and `run_pdf()` remain unchanged.

**Migration/rollback:** additive two-path feature; remove/revert it with no schema/store migration.

## Program-level STOP conditions

Stop and request Master PO disposition if:

- native PDF bytes need a new File IPC/path authority;
- native evidence cannot safely bind exact bytes;
- native render schema must change;
- `primitive_ir_lib.run_pdf()` must be called wholesale;
- source custody, OCR, calibration, Primitive/Semantic, model/provider, visual verdict, approval, repair or publication behavior is required;
- a new manifest/store/cache/current pointer is required;
- dependency/lock/workflow/contract change is required;
- wall-clock containment requires a new process supervisor;
- exact A4 dimensions require destructive post-render resize/crop;
- renderer version identity cannot be captured/replayed deterministically;
- private/customer CAD is required for first-slice acceptance;
- any third first-slice path is required;
- current main or an active writer overlaps the two-path write-set.

Architectural ownership failure result:

```text
S2C DERIVED-RASTER SCOPE GAP — MASTER PO DECISION REQUIRED
```

## Planning handoff

The plan is executable after a fresh runtime issuance rebaseline. First slice remains two new pure-Python paths, no AutoCAD live execution, no private CAD, no dependency migration, and no modification of existing native/Primitive/visual/source-fusion owners.
