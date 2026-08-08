# S2C Derived Raster Evidence Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one pure, deterministic, bounded adapter that converts exact bytes from an already validated AutoCAD-native PDF artifact into one derived PNG page plus closed hash-bound evidence, without creating a second native renderer, source-custody owner, Primitive/OCR path, visual verdict owner, or persistence store.

**Architecture:** Create one adjacent `mcp_integration_lib/derived_raster_evidence.py` module and one focused test file. The module reuses `mcp_integration_lib.autocad_render_evidence` unchanged for native request/evidence authority, verifies exact PDF bytes, rasterizes one page with the already locked PyMuPDF runtime, validates PNG bytes in memory, and hashes closed records only through `cad_agent.drawing_contracts.canonical_json_sha256()`. No AutoCAD/File IPC integration or persistence belongs in the first slice.

**Tech Stack:** Python 3.11; PyMuPDF 1.28.0 from the accepted Windows lock; existing Pillow runtime dependency for PNG structural inspection if needed; `mcp_integration_lib.autocad_render_evidence`; `cad_agent.drawing_contracts.canonical_json_sha256`; pytest; Ruff; repository architecture checker; canonical verifier.

## Global Constraints

- Runtime is not authorized by Issue #144; every future runtime child Issue needs a fresh exact current-main SHA and explicit Master PO authorization.
- The accepted native `DWG -> PDF` owner remains the AutoCAD/.NET path plus `mcp_integration_lib.autocad_render_evidence`.
- `cad_agent.source_fusion` remains input-source PDF custody/render provenance only.
- `cad_agent.visual_evidence` remains downstream packaging/freshness, not rendering.
- `primitive_ir_lib.run_pdf()` remains Primitive/OCR/calibration orchestration and is not called by S2C.
- First runtime slice adds no dependency, lock, workflow, contract-schema-directory, manifest, File IPC, AutoCAD, PC3/PMP/profile, OCR/model/provider, approval, verdict, repair or publisher change.
- First runtime slice cumulative write-set is exactly two paths:

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```

- Every task is RED-first with a committed meaningful RED before its production edit.
- Use normal forward commits only; no amend, rebase, squash, force-push or main-sync after a child branch is issued.
- `PASS`, `FAIL`, `SKIP`, and `NOT RUN` remain literal.
- AutoCAD Mechanical live and private/customer data are not required for first-slice offline acceptance.

---

## 0. Mandatory runtime issuance rebaseline — READ ONLY

No repository write occurs in this gate.

- [ ] **Step 1: record exact current main**

Record:

```powershell
git fetch origin
git rev-parse origin/main
```

The runtime Issue must use that exact SHA as its issuance base.

- [ ] **Step 2: map accepted native owner symbols**

Read current main and record the exact paths/symbols equivalent to:

```python
mcp_integration_lib.autocad_render_evidence.validate_render_request
mcp_integration_lib.autocad_render_evidence.validate_render_evidence
cad_agent.drawing_contracts.canonical_json_sha256
```

Require the native PDF evidence to still bind native artifact SHA-256, PDF page count, drawing/latest-mutation/Visual-Run-Manifest identity, layout, render options, `AUTOCAD_NATIVE`, read-only `changed=false`, and equal DBMOD.

Material contract drift => stop and return to Master PO before branch creation.

- [ ] **Step 3: verify renderer dependencies remain accepted**

Confirm the current accepted lock still supplies PyMuPDF and Pillow without a dependency change. Record the exact PyMuPDF version.

If first-slice behavior requires a new dependency or lock edit, STOP.

- [ ] **Step 4: verify no active writer overlap**

Proposed runtime paths must be absent or unowned:

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```

Any active writer overlap blocks issuance.

- [ ] **Step 5: verify the clean bytes boundary**

The first slice accepts `pdf_bytes` directly. It does not require a repository change to File IPC or artifact transport.

If the actual consumer cannot ever obtain exact native PDF bytes through an existing approved handoff without adding a second path/File-IPC owner, report:

```text
S2C DERIVED-RASTER SCOPE GAP — MASTER PO DECISION REQUIRED
```

- [ ] **Step 6: create one isolated runtime branch from the exact issuance SHA**

Only after Steps 1–5 pass.

---

## Runtime file structure

### Create in Task 1

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```

### Modify in Tasks 2–3

Only the same two paths.

### Explicitly do not modify

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

A third path is a STOP condition, not implicit permission to widen scope.

---

### Task 1: Native PDF binding and closed derived-evidence core

**Purpose:** Establish the S2C owner with exact native request/evidence binding, exact PDF-byte hash verification, a complete public surface, closed record validation and one simple deterministic page render.

**Files:**
- Create first for RED: `mcp_integration_lib/tests/test_derived_raster_evidence.py`
- Create only after meaningful RED: `mcp_integration_lib/derived_raster_evidence.py`
- Modify: none

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

class DerivedRasterEvidenceError(ValueError): ...

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

- [ ] **Step 1: create the RED-only test file with synthetic native fixtures**

Use the accepted `autocad-native-render-request-1.0` / `autocad-native-render-evidence-1.0` shapes. Build a one-page PDF entirely in memory with PyMuPDF and use its SHA in the native evidence fixture.

Add a helper similar to:

```python
import hashlib
import fitz


def _pdf_bytes(*, width_pt: float = 200, height_pt: float = 100) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=width_pt, height=height_pt)
    page.draw_line((10, 10), (190, 90), color=(0, 0, 0), width=1)
    data = doc.tobytes()
    doc.close()
    return data


def _native_pair(pdf: bytes) -> tuple[dict[str, object], dict[str, object]]:
    digest = hashlib.sha256(pdf).hexdigest()
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
            "paper_size": "A4",
            "plot_style": "monochrome.ctb",
        },
        "requested_at": "2026-08-09T00:00:00Z",
    }
    evidence = {
        **{key: request[key] for key in (
            "request_id", "run_id", "drawing_sha256",
            "latest_mutation_sha256", "visual_run_manifest_sha256",
            "layout", "artifact_kind", "render_options"
        )},
        "schema_version": "autocad-native-render-evidence-1.0",
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

The exact fixture may use helper builders already available in the accepted tests; do not modify those owners.

- [ ] **Step 2: add Task-1 RED tests**

Cover:

```text
module/public surface missing -> meaningful RED
valid native PDF pair + exact bytes -> PNG bytes + valid closed evidence
native request artifact_kind PNG -> fail
native evidence artifact_kind PNG -> fail
request/evidence mismatch -> fail through existing native validator
wrong PDF byte SHA -> NATIVE_PDF_HASH_MISMATCH
parsed page count != native page_count -> PAGE_COUNT_MISMATCH
page_index negative/bool/non-int/out-of-range -> fail
unknown derived root field -> fail
forbidden approval/verdict/repair/publication/current fields -> fail
native unsafe relative path -> fail through existing native validator
native request/evidence canonical hash changes -> derived evidence identity changes
```

- [ ] **Step 3: prove meaningful RED**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
```

Expected: collection/import/public-surface failures caused by the absent S2C module.

Commit RED only:

```powershell
git add mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "test: define derived raster evidence contract"
```

No production file may exist in this commit.

- [ ] **Step 4: implement native binding helpers and closed validators**

Create only `mcp_integration_lib/derived_raster_evidence.py`.

Use a structure equivalent to:

```python
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from copy import deepcopy

import fitz

from cad_agent.drawing_contracts import canonical_json_sha256
from mcp_integration_lib.autocad_render_evidence import (
    AutoCADRenderEvidenceError,
    validate_render_evidence,
    validate_render_request,
)

DERIVED_RASTER_EVIDENCE_SCHEMA_VERSION = "derived-raster-evidence-1.0"
DERIVED_RASTER_POLICY_VERSION = "pymupdf-derived-raster-v1"


class DerivedRasterEvidenceError(ValueError):
    pass


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
    if not isinstance(pdf_bytes, bytes):
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

Do not echo the upstream exception text because it may contain path/context detail; expose categorical S2C errors.

- [ ] **Step 5: implement the complete closed root shape**

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

For Task 1, basic synthetic pages may use crop=media, rotation 0, UserUnit 1. Tasks 2–3 harden every page-geometry/resource invariant without changing this public shape.

- [ ] **Step 6: implement one basic page rasterization path**

The implementation must already open verified bytes, not a path:

```python
with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
    if document.page_count != evidence["artifact"]["page_count"]:
        _fail("PAGE_COUNT_MISMATCH")
    if type(page_index) is not int or not 0 <= page_index < document.page_count:
        _fail("PAGE_INDEX_OUT_OF_RANGE")
    page = document.load_page(page_index)
    # Task 2 locks exact geometry/matrix computation before final acceptance.
```

Do not render all pages and do not call `primitive_ir_lib.run_pdf()`.

- [ ] **Step 7: make the builder self-validate**

`derive_native_pdf_page()` must finish by calling `validate_derived_raster_evidence()` with the exact PDF and produced PNG bytes before returning.

`derived_raster_evidence_sha256()` returns:

```python
canonical_json_sha256(
    validate_derived_raster_evidence(
        payload,
        pdf_bytes=pdf_bytes,
        png_bytes=png_bytes,
        native_request=native_request,
        native_evidence=native_evidence,
    )
)
```

- [ ] **Step 8: run focused GREEN and native regressions**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest \
  mcp_integration_lib/tests/test_derived_raster_evidence.py \
  mcp_integration_lib/tests/test_autocad_render_evidence.py \
  -q -p no:cacheprovider
```

Expected: PASS, zero S2C skips.

- [ ] **Step 9: run Ruff/diff and commit**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check \
  mcp_integration_lib/derived_raster_evidence.py \
  mcp_integration_lib/tests/test_derived_raster_evidence.py

git diff --check
git diff --name-only "$env:S2C_TASK_BASE_SHA"..HEAD
```

Cumulative path output must be exactly the two S2C paths.

Commit:

```powershell
git add mcp_integration_lib/derived_raster_evidence.py mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "feat: bind native PDF to derived raster evidence"
```

**Paired independent reviewer:** native-evidence/provenance + architecture/reuse.

**STOP:** any need to change native schema, File IPC, Primitive/OCR/calibration, source fusion, persistence or a third path.

---

### Task 2: Deterministic geometry, exact A4/300-DPI matrix, alpha policy and renderer identity

**Purpose:** Lock page-box/rotation/UserUnit semantics, exact integer pixel dimensions, explicit matrix, opaque-white PNG policy and renderer-version evidence.

**Files:**
- Modify first for RED: `mcp_integration_lib/tests/test_derived_raster_evidence.py`
- Modify only after meaningful RED: `mcp_integration_lib/derived_raster_evidence.py`
- Create: none

**Interfaces:** Public surface is unchanged from Task 1.

- [ ] **Step 1: add Task-2 RED geometry fixtures**

Create in-memory PDFs covering:

```text
crop == media
crop != media
rotation 0
rotation 90
rotation 180
rotation 270
UserUnit absent
UserUnit 2
A4 portrait
A4 landscape
non-A4 while native request claims A4
```

All fixtures remain synthetic and in-memory.

- [ ] **Step 2: add exact A4 RED assertions**

Require:

```python
assert portrait_evidence["width_px"] == 2480
assert portrait_evidence["height_px"] == 3508
assert landscape_evidence["width_px"] == 3508
assert landscape_evidence["height_px"] == 2480
```

Also require a one-pixel forged evidence dimension to fail validation.

- [ ] **Step 3: add deterministic dimension/matrix RED tests**

Lock the pixel rounding helper to explicit decimal half-up behavior:

```python
from decimal import Decimal, ROUND_HALF_UP


def expected_pixels(points: str, dpi: int) -> int:
    value = Decimal(points) * Decimal(dpi) / Decimal(72)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
```

Production may use an equivalent private helper. It must not use caller/binary-float-dependent `round()` as identity authority.

Tests must prove:

```text
matrix recomputation is deterministic
forged matrix fails
wrong DPI changes matrix/dimensions or fails policy
crop-box change changes evidence
rotation changes orientation deterministically
UserUnit changes physical geometry exactly once
A4 request + non-A4 observed geometry fails PAGE_GEOMETRY_MISMATCH
```

- [ ] **Step 4: add alpha/background RED tests**

Decode returned PNG bytes using the already available Pillow runtime or an equivalent existing image decoder and assert:

```text
format == PNG
size == evidence width/height
no alpha/transparency channel
background_policy == WHITE
alpha_policy == OPAQUE_NO_ALPHA
```

Forged transparency/background fields must fail.

No post-render resize/composite is allowed.

- [ ] **Step 5: add renderer-version RED tests**

Evidence must record runtime-observed values equivalent to:

```python
{
    "name": "PYMUPDF",
    "binding_version": str(fitz.VersionBind),
    "mupdf_version": str(fitz.VersionFitz),
}
```

Tests monkeypatch/private-inject the renderer identity boundary and prove version drift changes evidence identity and is not replay-equivalent.

Caller-provided version strings must never authorize the renderer identity.

- [ ] **Step 6: prove Task-2 meaningful RED and commit tests only**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
```

Expected: failures caused by missing exact geometry/matrix/A4/alpha/version behavior.

Commit test-only forward change:

```powershell
git add mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "test: lock derived raster geometry and renderer policy"
```

- [ ] **Step 7: implement exact geometry normalization**

Add private helpers with closed output, for example:

```python
def _page_geometry(page: fitz.Page) -> dict[str, object]:
    # Observe effective crop/media geometry and right-angle rotation.
    # Resolve absent UserUnit to canonical "1".
    # Reject non-finite/empty/excessive geometry.
    ...


def _target_pixels(*, width_pt: str, height_pt: str, dpi: int) -> tuple[int, int]:
    ...


def _render_matrix(*, geometry: Mapping[str, object], dpi: int) -> list[str]:
    ...
```

The actual implementation must replace the ellipses with closed logic before commit; the public plan names these helpers to lock responsibility, not to authorize placeholders in production.

Critical rule: use PyMuPDF page geometry consistently so `/UserUnit` is not multiplied twice.

- [ ] **Step 8: implement exact pixel rasterization**

Construct the PyMuPDF matrix from the deterministic target dimensions and observed geometry. Render directly to the target integer raster with `alpha=False`.

Do not render at an implicit size and then resize/crop the PNG to force A4 dimensions.

If direct deterministic rasterization cannot produce the locked A4 postcondition without content-destructive post-processing, STOP and report:

```text
S2C DERIVED-RASTER SCOPE GAP — MASTER PO DECISION REQUIRED
```

- [ ] **Step 9: implement PNG structural validation**

`validate_derived_raster_evidence()` must verify exact `png_bytes` SHA, decoded dimensions and no-alpha policy rather than trusting evidence fields.

Any malformed PNG => categorical `PNG_INVALID`.

- [ ] **Step 10: run Task-2 GREEN five times**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

All five runs must have identical PASS counts and zero S2C skips.

- [ ] **Step 11: run regressions and commit**

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
```

Commit:

```powershell
git add mcp_integration_lib/derived_raster_evidence.py mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "feat: lock deterministic PDF raster geometry"
```

**Paired independent reviewer:** raster determinism/page geometry + no-second-renderer authority.

**STOP:** UserUnit/rotation semantics cannot be made deterministic, A4 exact dimensions require destructive resize/crop, or Primitive/native owner changes are needed.

---

### Task 3: Resource containment, replay hardening, privacy and final authority gates

**Purpose:** Make the first slice fail closed under malformed/oversized PDFs, replay/version drift, spoofed evidence and forbidden authority imports, then produce final hosted-ready evidence.

**Files:**
- Modify first for RED: `mcp_integration_lib/tests/test_derived_raster_evidence.py`
- Modify only after meaningful RED: `mcp_integration_lib/derived_raster_evidence.py`
- Create: none

**Interfaces:** Public surface remains unchanged.

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

The runtime Issue may tighten these before RED if synthetic evidence supports smaller values; it may not widen them implicitly during implementation.

- [ ] **Step 1: add Task-3 RED resource tests**

Cover each categorical failure:

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

Use monkeypatch/fakes for huge logical sizes when allocating the real payload would be wasteful. Tests must prove limits are checked before materializing huge pixmaps.

- [ ] **Step 2: add decompression/parser failure privacy RED**

Inject malformed/truncated PDF bytes and mocked PyMuPDF exceptions containing fake private paths/content.

Assert the public exception is only a categorical code and does not contain:

```text
input bytes/content
native artifact path
filesystem path
upstream exception message
```

- [ ] **Step 3: add exact replay RED**

For identical native request/evidence/PDF/page/DPI/runtime version, call `derive_native_pdf_page()` repeatedly and assert:

```python
png_1 == png_2 == png_3
record_1 == record_2 == record_3
hash_1 == hash_2 == hash_3
```

Run at least five repetitions in the focused suite.

Change one factor at a time and require evidence identity change or categorical refusal:

```text
native request hash
native evidence hash
PDF hash
page index
page count
box
rotation
UserUnit
DPI
matrix
PyMuPDF binding version
MuPDF engine version
alpha/background policy
```

- [ ] **Step 4: add static ownership RED**

Parse the production module AST and require no imports from:

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

Also assert there is no call to `Path.read_bytes`, `open`, `fitz.open` with a filesystem pathname, or any manifest/cache/database writer API.

`fitz.open(stream=pdf_bytes, filetype="pdf")` is allowed.

- [ ] **Step 5: prove Task-3 meaningful RED and commit tests only**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_derived_raster_evidence.py -q -p no:cacheprovider
```

Commit only the test modification after failures are attributable to missing Task-3 hardening:

```powershell
git add mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "test: harden derived raster resource and replay gates"
```

- [ ] **Step 6: implement resource checks before expensive work**

Required order:

```text
validate type/byte length
validate native request/evidence
verify PDF SHA
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
self-validate exact PNG/evidence
return
```

No retry with changed DPI/box/renderer.

- [ ] **Step 7: implement privacy-safe exception mapping**

Catch expected PyMuPDF/Pillow/resource exceptions and map them to S2C categorical codes without interpolating the source exception.

Unexpected programmer errors should still fail the test/run; do not broadly hide `AssertionError`, `TypeError` caused by internal bugs, or `KeyboardInterrupt`/`SystemExit`.

- [ ] **Step 8: run complete focused and upstream GREEN**

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

- [ ] **Step 9: run architecture/Ruff/diff gates**

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

Exact cumulative paths must remain:

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```

- [ ] **Step 10: run canonical verifier**

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Record exact PASS/FAIL/SKIP/NOT RUN output. AutoCAD live remains NOT RUN in this offline first slice.

- [ ] **Step 11: commit production hardening**

```powershell
git add mcp_integration_lib/derived_raster_evidence.py mcp_integration_lib/tests/test_derived_raster_evidence.py
git commit -m "feat: harden derived raster replay and limits"
```

- [ ] **Step 12: hosted/current-main synthetic gate**

Open/retain a DRAFT PR only after local/focused GREEN. Require hosted:

```text
tests = PASS
reuse-declaration = PASS
```

Independent reviewer must bind verdict to exact current-main/head/synthetic SHA triple.

**Paired independent reviewer:** security/resource/privacy + integration/CI/write-set.

**STOP:** third path, process supervisor, new transport/store, private data, live AutoCAD, dependency change, or weakening accepted native/Primitive tests.

---

## Future integration task — intentionally not in first slice

After first-slice acceptance, a separate Master PO Issue may connect verified native PDF artifact bytes to the pure S2C adapter.

It must first prove which existing artifact consumer owns byte handoff. Do not assume `dotnet_ipc.py` must change.

If integration needs:

```text
mcp_integration_lib/dotnet_ipc.py
cad_agent.visual_evidence.py
contracts/**
autocad_plugin/**
```

that exact path must be separately authorized with fresh overlap review.

No integration task may make S2C the native renderer or visual verdict owner.

## Future live acceptance — separately authorized only

Use synthetic disposable data only.

Required sequence:

```text
accepted isolated AutoCAD profile/media configuration
-> existing AutoCAD/.NET native A4 PDF
-> validate native request/evidence
-> obtain exact verified PDF bytes through existing owner
-> S2C derive page 0 at 300 DPI
-> require portrait 2480x3508 OR landscape 3508x2480 based on observed geometry
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

No PC3/PMP/profile mutation is authorized by S2C.

## Reuse declaration for future runtime PR

The runtime PR must state separately:

**Existing capability inspected:** native render contract/tests, AutoCAD/.NET native path, source-fusion provenance, visual-evidence packaging, Primitive `run_pdf`, canonical hashing, current PyMuPDF lock.

**Existing API reused:** `validate_render_request`, `validate_render_evidence`, `canonical_json_sha256`, existing PyMuPDF dependency.

**Adapter required:** one pure native-PDF-bytes -> PNG/evidence module.

**New capability genuinely missing:** deterministic derived-raster evidence owner for generated candidate native PDF artifacts.

**Files allowed to change:** exact two S2C paths only.

**Files forbidden to duplicate:** native renderer, File IPC/path policy, source custody/fusion, Primitive/OCR/calibration, visual verdict, manifest/store, repair, approval, publisher.

**Compatibility behavior:** existing owners byte/behavior unchanged; `run_pdf()` unchanged.

**Migration/rollback:** additive two-path feature; revert/remove it with no schema/store migration.

## Program-level STOP conditions

Stop and request Master PO disposition if any task discovers:

- native PDF bytes cannot be handed to the pure seam without a new File IPC/path authority;
- native evidence cannot bind the actual bytes;
- native render schema must change for derived evidence;
- `primitive_ir_lib.run_pdf()` must be called wholesale;
- source custody, OCR, calibration, Primitive/Semantic, model/provider, visual verdict, approval, repair or publication behavior is required;
- a new manifest/store/cache/current pointer is required;
- a dependency/lock/workflow/contract change is required;
- wall-clock containment requires a new process supervisor;
- A4 exact dimensions require destructive post-render resize/crop rather than deterministic direct rasterization;
- renderer version identity cannot be captured/replayed deterministically;
- private/customer CAD is required for first-slice acceptance;
- any third first-slice path is required;
- current main or an active writer overlaps the exact two-path write-set.

Architectural ownership failure result:

```text
S2C DERIVED-RASTER SCOPE GAP — MASTER PO DECISION REQUIRED
```

## Planning handoff

The plan is executable after a fresh runtime issuance rebaseline. The first slice remains two new pure-Python paths and requires no AutoCAD live execution, source/private CAD, dependency migration or modification of existing native/Primitive/visual/source-fusion owners.
