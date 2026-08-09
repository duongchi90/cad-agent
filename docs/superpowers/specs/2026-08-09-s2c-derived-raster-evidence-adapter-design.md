# S2C Derived Raster Evidence Adapter Design

**Status:** Planning only. No runtime implementation is authorized.

**Issue:** #144 — `[Acceleration][Planning] S2C Derived Raster Evidence Adapter executable design`

**Activation:** `5227485477`

**Planning base:** `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

**Planning branch:** `planning/issue-144-s2c-derived-raster-evidence`

**Remediation:** PR #145 docs remediation for encrypted-PDF fail-closed behavior and A4 physical-page geometry. This revision supersedes any earlier wording that treated CropBox alone as proof of A4 physical sheet size or allowed encrypted input to reach page rasterization.

## 1. Objective

Plan the smallest safe owner for:

```text
validated AutoCAD-native PDF request/evidence
  + exact native PDF bytes
  -> deterministic bounded PDF-page rasterization
  -> exact PNG bytes + closed derived-raster evidence
```

The new owner begins only after native `DWG -> PDF` rendering has completed and the accepted native render request/evidence pair has validated. It owns no AutoCAD plotting, File IPC, source custody, OCR, Primitive/Semantic IR, calibration, visual verdict, persistence, repair, approval or publication authority.

## 2. Accepted ownership audit

### 2.1 Native render evidence — `REUSE_AS_IS`

Current accepted owner:

```text
mcp_integration_lib/autocad_render_evidence.py
```

Reuse unchanged:

```python
REQUEST_SCHEMA_VERSION = "autocad-native-render-request-1.0"
EVIDENCE_SCHEMA_VERSION = "autocad-native-render-evidence-1.0"

build_render_evidence_request(...)
validate_render_request(payload)
validate_render_evidence(payload, request=None)
```

It remains authoritative for native request/run identity, drawing SHA, latest mutation SHA, Visual Run Manifest SHA, layout, render options, `PNG | PDF`, `AUTOCAD_NATIVE`, artifact SHA, PDF page count/PNG dimensions, `changed=false`, DBMOD stability and native artifact path validation.

S2C consumes this owner unchanged and does not widen `autocad-native-render-evidence-1.0`.

### 2.2 AutoCAD/.NET native renderer — `REUSE_AS_IS`

Only the existing AutoCAD/.NET path may claim:

```text
DWG/layout -> native PDF
```

S2C receives no HWND, AutoCAD document, File IPC directory, PC3/PMP/profile authority, save authority or mutation permission.

### 2.3 Source fusion — `REJECT_DUPLICATE_OWNER`

`cad_agent/source_fusion.py` owns input-source PDF page/render provenance bound to SourceBundle/source custody. Generated native PDF/PNG artifacts do not become source-custody items.

### 2.4 Visual evidence — `REUSE_DOWNSTREAM_ONLY`

`cad_agent/visual_evidence.py` remains downstream packaging/freshness authority. It does not rasterize PDFs.

### 2.5 Primitive PDF runner — `PORT_BOUNDED_LOGIC`

`primitive_ir_lib/run_pdf.py` demonstrates the lower-level PyMuPDF raster mechanic but also owns Primitive IR/OCR/calibration/view-candidate orchestration.

First slice must not import or call `primitive_ir_lib.run_pdf()`.

### 2.6 Dependencies — `REUSE_AS_IS`

The accepted Windows Python 3.11 lock already pins PyMuPDF 1.28.0 and Pillow. First slice adds no dependency/lock change.

## 3. Missing capability result

A new narrow owner is still genuinely missing for:

```text
exact validated native PDF bytes
+ native request/evidence identity
+ encryption refusal
+ PDF page index/page count
+ physical MediaBox geometry
+ selected CropBox geometry
+ rotation
+ UserUnit
+ render DPI/matrix
+ renderer identity/version
+ opaque-white/no-alpha policy
-> exact derived PNG bytes + closed evidence
```

Classification:

```text
NEW_MISSING_CAPABILITY
```

A clean owner exists, so no scope-gap verdict is required at planning time.

## 4. Selected architecture

Preferred future runtime paths:

```text
CREATE mcp_integration_lib/derived_raster_evidence.py
CREATE mcp_integration_lib/tests/test_derived_raster_evidence.py
```

No third path.

The module is pure at its boundary:

```text
validated native request/evidence + immutable pdf_bytes
    -> one-page bounded rasterization
    -> png_bytes + derived evidence
```

No filesystem pathname is accepted for source or output.

## 5. Authority map

```text
DWG/layout -> native PDF
  existing AutoCAD/.NET + autocad_render_evidence

native PDF bytes -> derived PNG bytes
  new S2C derived_raster_evidence module

input-source PDF provenance
  cad_agent.source_fusion

PNG downstream packaging/freshness
  cad_agent.visual_evidence / existing visual owners

Primitive/OCR/calibration
  primitive_ir_lib / existing OCR/calibration owners

approval/verdict/repair/publication
  existing/future dedicated owners, never S2C
```

No second native renderer, source-custody owner, manifest/store, approval owner or visual verdict owner is created.

## 6. Proposed public surface

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

Planning names may receive naming-only adjustment at fresh runtime issuance, but not semantic or authority widening.

## 7. Immutable byte boundary

The first slice accepts `pdf_bytes` only.

Forbidden:

```text
arbitrary pathname open
Path.read_bytes()
root/reparse policy duplication
File IPC discovery
ambient artifact-directory lookup
output/temp artifact persistence
```

This keeps source/path custody outside S2C.

## 8. Native binding and encrypted-PDF fail-closed sequence

Required order:

```text
validate input type and MAX_PDF_BYTES
validate_render_request(native_request)
require request artifact_kind == PDF
validate_render_evidence(native_evidence, request=validated_request)
require evidence artifact_kind == PDF
require AUTOCAD_NATIVE through accepted validator
require sha256(pdf_bytes) == native_evidence.artifact.sha256
open exact bytes with fitz.open(stream=pdf_bytes, filetype="pdf")
check encryption before page_count/page load/rasterization
only then inspect page_count and geometry
```

### 8.1 Encryption rule

**Any PDF encryption is out of scope and fails closed.** S2C never authenticates or decrypts.

Immediately after successful `fitz.open(...)`, and before `page_count`, `load_page()`, `get_pixmap()` or other content access, reject with:

```text
PDF_ENCRYPTED
```

when any of these indicate encryption:

```text
document.needs_pass is True
document.is_encrypted is True
PDF trailer contains /Encrypt
document metadata reports a non-null encryption method
```

The trailer check is normative because `/Encrypt` is the PDF-level declaration of encryption. `needs_pass` / `is_encrypted` are additional fail-closed signals, not permission to continue when false.

Forbidden:

```text
document.authenticate(...)
password parameter
password lookup/store
owner/user password handling
decryption attempt
permission-based fallback rendering
```

If trailer inspection itself cannot be completed safely, fail closed as `PDF_MALFORMED`; do not rasterize.

No partial PNG/evidence may escape an encrypted-input failure.

## 9. Canonical native identity

Canonical hashes of normalized accepted native request/evidence use only:

```python
cad_agent.drawing_contracts.canonical_json_sha256(...)
```

Raw PDF/PNG SHA-256 is ordinary byte integrity, not a second canonical JSON authority.

## 10. Closed derived evidence

The derived record is closed and includes:

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

`media_box` and `physical_page_size_mm` are required by this remediation so A4 physical-sheet identity is evidence-bound rather than inferred from PNG dimensions or native `paper_size` text.

Reject unknown or authority-bearing fields such as approval, verdict, repair, publication, accepted/current state, source-custody identity, absolute path, customer filename, HWND/process/session ID, ambient timestamp or random UUID.

## 11. Physical page geometry policy

### 11.1 MediaBox is physical sheet geometry

For PDF, the physical page is derived from the observed `MediaBox` plus effective `/UserUnit` exactly once.

Normalized evidence:

```text
media_box = {
  coordinates_pt: [x0, y0, x1, y1]
}

physical_page_size_mm = {
  width:  <canonical decimal mm>,
  height: <canonical decimal mm>
}
```

Do not use `CropBox`, `Page.rect`, PNG dimensions or the native request label as the sole proof of physical paper size.

### 11.2 Selected raster extent is CropBox

First slice still rasterizes the effective visible CropBox:

```text
selected_page_box = {
  kind: "CROP_BOX",
  coordinates_pt: [x0, y0, x1, y1]
}
```

CropBox is observed from exact verified PDF bytes and never caller-authoritative.

### 11.3 A4 physical classification

Canonical ISO A4 physical dimensions are:

```text
210.00 mm x 297.00 mm
```

Orientation-neutral classification accepts either ordering before applying page rotation.

To accommodate ordinary PDF point quantization while remaining fail-closed, planning locks:

```text
A4_PHYSICAL_TOLERANCE_MM = 0.10
```

Each unrotated physical MediaBox dimension after UserUnit conversion must be within inclusive ±0.10 mm of the corresponding canonical A4 dimension.

Examples under UserUnit=1:

```text
595 pt x 842 pt -> acceptable A4 physical approximation
612 pt x 792 pt -> not A4
```

Tolerance is for physical-size classification only. It is not permission to crop, stretch or resize arbitrary content.

### 11.4 A4 selected-box rule

For a native request claiming `paper_size == "A4"`:

1. physical MediaBox must classify as A4;
2. effective CropBox must represent the full physical sheet: its four physical edges must coincide with MediaBox within the same ±0.10 mm tolerance after UserUnit conversion;
3. otherwise fail `PAGE_GEOMETRY_MISMATCH` before rasterization.

This prevents a smaller visible crop inside an A4 MediaBox from being falsely treated as a full-sheet A4 raster.

For non-A4 synthetic/custom requests, valid bounded CropBox rasterization remains allowed; the A4 exact-dimension postcondition simply does not apply.

### 11.5 Rotation

Observed rotation is normalized to exactly:

```text
0 | 90 | 180 | 270
```

PyMuPDF returns page box coordinates in unrotated page space while `Page.rect` reflects rotation. S2C therefore records unrotated MediaBox/CropBox and applies the explicit rotation policy exactly once.

Unsupported/ambiguous rotation fails closed.

### 11.6 UserUnit

Rules:

```text
absent /UserUnit -> 1
finite positive value -> may be accepted
zero/negative/non-finite/excessive -> reject
```

UserUnit must not be applied twice. RED must include a non-1 fixture whose physical MediaBox still resolves to A4.

## 12. A4 / 300-DPI raster policy

For an accepted A4 physical page whose selected CropBox is full-sheet A4, target dimensions are derived from canonical A4 physical millimetres, not from a rounded PDF point encoding:

```text
ideal_width_px  = physical_width_mm  / 25.4 * render_dpi
ideal_height_px = physical_height_mm / 25.4 * render_dpi
```

At 300 DPI with deterministic nearest-integer half-up:

```text
portrait  -> 2480 x 3508
landscape -> 3508 x 2480
```

Rotation 90/270 swaps orientation deterministically.

The direct render matrix maps the accepted full-sheet A4 selected box to those canonical target pixels in one rasterization operation.

Forbidden:

```text
render then resize
render then crop to force dimensions
content-dependent fit
arbitrary shear
caller-supplied transform
```

If exact A4 dimensions cannot be produced directly without destructive post-processing, return the scope-gap verdict.

## 13. Non-A4 deterministic pixel policy

For non-A4/custom pages, target pixels are derived from observed physical selected-box dimensions using deterministic decimal/rational arithmetic and nearest-integer half-up:

```text
ideal_px = physical_size_mm / 25.4 * DPI
```

No implicit renderer rounding is authoritative.

## 14. Render matrix

Evidence records exact six coefficients:

```text
[a, b, c, d, e, f]
```

The matrix is recomputed solely from observed selected box, physical geometry/UserUnit, right-angle rotation, DPI and deterministic target dimensions.

Validation reparses exact `pdf_bytes` and recomputes the expected geometry/matrix before accepting evidence.

## 15. Alpha/background policy

Fixed first-slice policy:

```text
alpha_policy      = OPAQUE_NO_ALPHA
background_policy = WHITE
```

Rendering uses no alpha. Returned PNG bytes must independently prove PNG format, exact dimensions and absence of alpha/transparency.

## 16. Renderer identity/version

Evidence records runtime-observed:

```text
renderer = {
  name: "PYMUPDF",
  binding_version: <loaded PyMuPDF binding version>,
  mupdf_version: <loaded MuPDF engine version>
}
```

Caller cannot authorize these values.

Renderer-version drift creates a new evidence generation and is not exact replay-equivalent.

## 17. Replay semantics

With identical immutable inputs and identical renderer identity/version:

```text
PNG bytes identical
PNG SHA identical
normalized evidence identical
derived evidence canonical SHA identical
```

The runtime suite repeats the exact derivation at least five times.

No random ID, ambient clock, cache key, manifest append or current pointer participates.

## 18. Resource policy

First-slice bounds remain:

```text
MAX_PDF_BYTES         = 64 * 1024 * 1024
MAX_PDF_PAGE_COUNT    = 256
MAX_PAGE_EDGE_PX      = 16_384
MAX_PAGE_PIXELS       = 32_000_000
MAX_DERIVED_PNG_BYTES = 64 * 1024 * 1024
MIN_RENDER_DPI        = 72
MAX_RENDER_DPI        = 600
```

Required fail-fast order:

```text
input type / PDF byte length
native request/evidence
native PDF SHA
open bounded exact bytes
encryption/trailer gate
page count
page index
MediaBox/CropBox/UserUnit/rotation
A4 physical classification when claimed
DPI
target dimensions
edge/pixel limits
one-page pixmap
PNG encoding
PNG byte limit
full self-validation
return
```

Never silently lower DPI or switch box/renderer after resource failure.

## 19. Privacy-safe categorical failures

At minimum:

```text
PDF_BYTES_INVALID
NATIVE_RENDER_EVIDENCE_INVALID
NATIVE_ARTIFACT_NOT_PDF
NATIVE_PDF_HASH_MISMATCH
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

Public failures never echo PDF content, caller paths, customer identifiers or upstream exception text.

## 20. No-partial-output rule

The adapter is byte-only and persistence-free.

On any failure, including encrypted input or A4 geometry mismatch:

```text
no PNG bytes returned
no evidence returned
no file written
no manifest/store/cache/current pointer mutated
```

The builder returns only after the generated PNG/evidence pair has self-validated against exact PDF and PNG bytes.

## 21. Mandatory RED-first matrix

### Native/encryption binding

- valid native PDF evidence + matching bytes;
- native request/evidence mismatch;
- wrong native PDF SHA;
- native-vs-parsed page-count mismatch;
- password-protected PDF -> `PDF_ENCRYPTED` before page access;
- encrypted PDF with `/Encrypt` trailer even when no password prompt is needed -> `PDF_ENCRYPTED`;
- prove `authenticate()` is never called;
- prove `load_page()` / `get_pixmap()` are not reached on encrypted input.

### Page/physical geometry

- MediaBox is recorded separately from CropBox;
- `physical_page_size_mm` recomputes from MediaBox + UserUnit;
- A4 210x297 mm portrait;
- A4 297x210 mm landscape;
- common 595x842-point A4 encoding accepted within ±0.10 mm;
- Letter MediaBox rejected when request says A4;
- A4 MediaBox + smaller CropBox rejected for A4 full-sheet path;
- CropBox/MediaBox edge mismatch >0.10 mm rejected;
- rotation 0/90/180/270;
- absent UserUnit -> 1;
- non-1 UserUnit applied exactly once;
- invalid/huge/non-finite geometry rejected.

### A4/300 DPI

- portrait -> exactly `2480 x 3508`;
- landscape -> exactly `3508 x 2480`;
- rotations 90/270 swap exact dimensions;
- forged matrix/dimensions fail;
- one-pixel evidence mismatch fails;
- no post-render resize/crop.

### PNG/replay/resource/security

Preserve all existing planned gates for opaque white/no alpha, renderer fingerprint/version drift, 5x byte-identical replay, PDF/page/pixel/PNG limits, malformed/truncated/resource refusal, privacy-safe errors, no pathname reopen, and forbidden authority imports.

## 22. Verification requirements

Future runtime acceptance requires:

```text
focused S2C pytest: PASS
5x replay/determinism: PASS
encrypted-PDF no-raster gate: PASS
A4 physical-geometry matrix: PASS
existing autocad_render_evidence tests: PASS
relevant Primitive PDF regressions: PASS
Ruff exact paths: PASS
architecture checker: PASS
git diff --check: PASS
exact two-path audit: PASS
canonical verifier: PASS
hosted tests: PASS
reuse-declaration: PASS
```

AutoCAD live and private/customer data remain outside first-slice offline acceptance.

## 23. Future live acceptance — separate authorization only

A later live gate must reuse existing AutoCAD session/open/close/cleanup owners and separately prove native PDF/drawing/DBMOD/PC3/PMP stability. Offline PASS never implies AutoCAD/File IPC/live cleanup PASS.

For live A4 acceptance it must prove both:

```text
physical MediaBox/UserUnit = A4 under this policy
full-sheet CropBox equivalent to MediaBox
```

before requiring exact 300-DPI PNG dimensions.

## 24. Compatibility and rollback

First runtime slice remains additive:

```text
no accepted schema change
no manifest migration
no dependency/lock change
no AutoCAD/plugin change
no Primitive change
no workflow change
no stored-data migration
```

Rollback is removal/revert of exactly the two new runtime paths.

## 25. STOP conditions

Stop and report Master PO instead of widening if:

- native PDF bytes require a new File IPC/path authority;
- accepted native render schema must change;
- exact bytes cannot be bound to native evidence;
- encrypted input can only be handled by password/authentication/decryption;
- physical A4 identity cannot be established from MediaBox/UserUnit without inventing another page-geometry owner;
- A4 exact pixels require post-render destructive resize/crop;
- only viable reuse calls `primitive_ir_lib.run_pdf()` wholesale;
- Primitive/OCR/calibration/Semantic/source-fusion/visual-evidence authority must move;
- a new manifest/store/cache/current pointer is required;
- dependency/lock/workflow/contract change is required;
- a process supervisor is required before bounded offline acceptance;
- renderer version cannot be observed/bound deterministically;
- private/customer CAD is required;
- a third runtime path is required;
- another active writer owns either proposed runtime path.

Architectural failure result:

```text
S2C DERIVED-RASTER SCOPE GAP — MASTER PO DECISION REQUIRED
```

## 26. Conclusion

The clean seam remains:

```text
validated native PDF evidence + exact immutable unencrypted PDF bytes
  -> explicit physical MediaBox/CropBox/UserUnit/rotation policy
  -> deterministic direct raster
  -> exact PNG bytes + closed derived evidence
```

Encrypted PDFs fail closed before page access. A4 is established from physical PDF page geometry, not from a request label or output pixel dimensions. The future first runtime write-set remains exactly:

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```
