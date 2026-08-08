# S2C Derived Raster Evidence Adapter Design

**Status:** Planning only. No runtime implementation is authorized.

**Issue:** #144 — `[Acceleration][Planning] S2C Derived Raster Evidence Adapter executable design`

**Activation:** `5227485477`

**Planning base:** `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

**Planning branch:** `planning/issue-144-s2c-derived-raster-evidence`

## 1. Objective

Plan the smallest safe owner for:

```text
validated AutoCAD-native PDF request/evidence
  + exact native PDF bytes
  -> deterministic bounded PDF-page rasterization
  -> exact PNG bytes + closed derived-raster evidence
```

The new owner begins **after** native `DWG -> PDF` rendering has completed and been validated. It does not own AutoCAD plotting, source custody, OCR, Primitive/Semantic IR, calibration, visual verdicts, persistence, repair, approval or publication.

## 2. Accepted ownership audit

### 2.1 `mcp_integration_lib.autocad_render_evidence` — `REUSE_AS_IS`

Accepted current-main owner:

```text
mcp_integration_lib/autocad_render_evidence.py
```

Stable surface:

```python
REQUEST_SCHEMA_VERSION = "autocad-native-render-request-1.0"
EVIDENCE_SCHEMA_VERSION = "autocad-native-render-evidence-1.0"

build_render_evidence_request(...)
validate_render_request(payload)
validate_render_evidence(payload, request=None)
```

It already binds native render identity to request/run, drawing SHA, latest mutation SHA, Visual Run Manifest SHA, layout, render options, `PNG | PDF`, `AUTOCAD_NATIVE`, artifact hash, PDF page count/PNG dimensions, read-only `changed=false`, equal DBMOD and warnings.

It also rejects unsafe artifact paths and approval/verdict/repair/publication fields.

**Decision:** consume unchanged. Do not widen `autocad-native-render-evidence-1.0` for derived evidence.

### 2.2 AutoCAD/.NET native rendering — `REUSE_AS_IS`

The existing AutoCAD/.NET path remains the only owner that may claim:

```text
DWG/layout -> native PDF
```

S2C gets no HWND, AutoCAD document, File IPC directory, PC3/PMP/profile authority, save authority or mutation permission.

Boundary:

```text
native owner ends: validated native PDF evidence + exact artifact bytes
S2C begins: exact validated PDF bytes -> derived PNG
```

### 2.3 `cad_agent.source_fusion` — `REJECT_DUPLICATE_OWNER`

`cad_agent/source_fusion.py` owns **input-source** PDF page/render provenance tied to SourceBundle/source custody.

Generated candidate/native render artifacts are not SourceBundle input sources. S2C must not mint source IDs, custody hashes or source-fusion records for them.

The module is only a design precedent for explicit page-box/rotation/UserUnit/DPI/matrix binding.

### 2.4 `cad_agent.visual_evidence` — `REUSE_DOWNSTREAM_ONLY`

`cad_agent/visual_evidence.py` packages/freshness-checks downstream visual evidence. It is not a renderer.

S2C may later hand PNG bytes/evidence to that downstream flow, but it does not move rendering into `cad_agent.visual_evidence`.

### 2.5 `primitive_ir_lib.run_pdf()` — `PORT_BOUNDED_LOGIC`

`primitive_ir_lib/run_pdf.py` currently uses PyMuPDF:

```text
fitz.open(...)
page.get_pixmap(..., alpha=False)
```

but the same callable immediately performs Primitive IR, OCR ROI, calibration, scale-label/view-candidate processing and child-IR materialization.

**Decision:** do not call `run_pdf()` from S2C. Reuse only the narrow PyMuPDF raster mechanic under a new narrower contract. No Primitive/OCR/calibration import is allowed.

### 2.6 PyMuPDF dependency — `REUSE_AS_IS`

The repository already depends on PyMuPDF. The accepted Windows Python 3.11 lock pins:

```text
pymupdf==1.28.0
```

No dependency or lock change belongs in the first runtime slice.

## 3. Missing capability result

No existing owner can truthfully bind all of:

```text
exact validated native PDF bytes
native request identity
native evidence identity
page index/page count
selected page box
rotation
UserUnit
render DPI
exact render matrix
renderer identity/version
opaque-white/no-alpha policy
PNG SHA
PNG width/height
```

without also importing unrelated authority.

Classification:

```text
NEW_MISSING_CAPABILITY
```

A clean owner exists, so this planning lane does **not** return the scope-gap verdict.

## 4. Alternatives

### A. Reuse `primitive_ir_lib.run_pdf()` wholesale

Rejected because it moves Primitive/OCR/calibration/view-candidate authority into S2C and writes unrelated artifacts.

### B. Add derived fields to `autocad_render_evidence.py`

Rejected for the first slice because it blurs native and derived renderer authority and silently widens an accepted schema.

### C. New narrow pure derived-raster module

Selected.

Preferred future paths:

```text
CREATE mcp_integration_lib/derived_raster_evidence.py
CREATE mcp_integration_lib/tests/test_derived_raster_evidence.py
```

No third path.

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

No second renderer/store/custody/verdict authority is created.

## 6. Selected module responsibility

Proposed module:

```text
mcp_integration_lib/derived_raster_evidence.py
```

It owns exactly:

1. validation/binding of an already accepted native PDF request/evidence pair;
2. verification that supplied PDF bytes match the native artifact SHA;
3. bounded rasterization of exactly one page;
4. validation of exact PNG bytes and closed derived evidence.

It does not own artifact discovery, transport, persistence, current pointers, caches, visual interpretation or live AutoCAD operations.

## 7. Proposed public surface

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

These are planning names. A future runtime Issue may make naming-only changes while preserving the exact semantics and authority boundary.

### Why bytes, not pathname

The first slice takes immutable `pdf_bytes` and returns `png_bytes` in memory.

This deliberately avoids:

- a second path/root/reparse policy;
- pathname TOCTOU;
- arbitrary caller file reads;
- duplicating File IPC artifact ownership.

Existing native evidence still validates its own safe relative artifact path. A later separately issued handoff may supply verified bytes from the existing artifact owner.

## 8. Native binding sequence

The sequence is fixed:

```text
validate_render_request(native_request)
require artifact_kind == PDF
validate_render_evidence(native_evidence, request=validated_request)
require artifact_kind == PDF
require AUTOCAD_NATIVE through existing validator
require sha256(pdf_bytes) == native_evidence.artifact.sha256
open exact verified bytes with PyMuPDF
require parsed page_count == native_evidence.artifact.page_count
```

S2C computes canonical digests of the validated native request/evidence with the existing:

```python
cad_agent.drawing_contracts.canonical_json_sha256()
```

No second canonical JSON serializer/hash owner is introduced.

Raw PDF/PNG SHA-256 remains ordinary content integrity, not canonical-record ownership.

## 9. Closed derived evidence

Root concepts:

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

Forbidden evidence material includes:

```text
absolute path
customer/source filename
HWND/process/session ID
ambient timestamp/random UUID
approval/verdict/pass
repair/publication
accepted/current/release state
source-custody identity
```

## 10. Page geometry policy

### 10.1 Selected page box

First slice uses the effective visible crop box:

```text
selected_page_box = {
  kind: "CROP_BOX",
  coordinates_pt: [x0, y0, x1, y1]
}
```

It is observed from verified PDF bytes, never supplied as caller authority.

If crop box is canonically equal to media box, that equality is accepted. Invalid/empty/non-finite geometry fails closed.

### 10.2 Rotation

Observed page rotation is normalized to exactly:

```text
0 | 90 | 180 | 270
```

Unsupported rotation representation fails closed.

### 10.3 UserUnit

The record contains a finite positive canonical UserUnit.

Rules:

- absent `/UserUnit` => `1`;
- zero/negative/non-finite/excessive values fail;
- UserUnit is observed, not inferred from pixels;
- implementation must use PyMuPDF's page geometry consistently so UserUnit is not applied twice.

Runtime RED must include a non-1 UserUnit fixture.

## 11. Deterministic pixel-dimension policy

Implicit renderer integer rounding is not authority.

Given effective physical page dimensions in points after accepted UserUnit semantics:

```text
ideal_width_px  = width_pt  * render_dpi / 72
ideal_height_px = height_pt * render_dpi / 72
```

S2C uses one explicitly locked nearest-integer rule with deterministic decimal/rational arithmetic for each dimension.

The exact raster matrix maps the selected box to those target integer dimensions. Any sub-pixel scale difference caused solely by integer pixel sampling is raster evidence behavior, not CAD geometry deformation.

No post-render resize is allowed.

### A4 at 300 DPI

Accepted exact postconditions:

```text
portrait  = 2480 x 3508
landscape = 3508 x 2480
```

Orientation is determined from effective page geometry plus page rotation.

If native request says `paper_size = A4` but observed PDF geometry is not A4 under the selected box/UserUnit policy, fail categorically. Do not force non-A4 content into A4 pixels.

## 12. Render matrix

Evidence stores the exact six coefficients:

```text
[a, b, c, d, e, f]
```

The matrix is derived only from:

- observed selected box;
- observed right-angle rotation;
- accepted UserUnit/page geometry semantics;
- requested DPI;
- deterministic integer-dimension policy.

Forbidden:

- caller-provided matrix;
- arbitrary shear/reflection;
- content-dependent crop;
- fit-to-content;
- post-render resize.

Validation reparses the exact `pdf_bytes` and recomputes the expected geometry/matrix before accepting evidence.

## 13. Alpha/background policy

First slice is fixed:

```text
alpha_policy      = OPAQUE_NO_ALPHA
background_policy = WHITE
```

Rendering uses a no-alpha PyMuPDF pixmap. Returned `png_bytes` must be inspected sufficiently to prove the encoded image has no alpha channel and its dimensions equal evidence.

Transparent output, arbitrary compositing and caller-selected background are out of scope.

## 14. Renderer identity/version

Closed renderer identity:

```text
renderer = {
  name: "PYMUPDF",
  binding_version: <loaded PyMuPDF binding version>,
  mupdf_version: <loaded MuPDF engine version>
}
```

These values are observed from the loaded renderer. Caller values never authorize them.

The first runtime slice uses the already locked PyMuPDF 1.28.0 dependency; no dependency change.

### Version drift

Exact-byte replay equivalence requires the same:

```text
native request hash
native evidence hash
native PDF hash
page index/count
box/rotation/UserUnit
DPI/matrix
alpha/background policy
PyMuPDF binding version
MuPDF engine version
```

A renderer-version change creates a new evidence generation. It may not be silently treated as byte-replay equivalent even if visual output looks similar.

## 15. Replay/duplicate semantics

With identical immutable inputs and identical renderer identity/version:

```text
PNG bytes identical
PNG SHA identical
normalized derived evidence identical
derived evidence SHA identical
```

No random ID, ambient clock, cache key, manifest append or current pointer exists.

Repeated calls on the same evidence do not mint new logical identity.

Two different native request/evidence records that happen to contain the same PDF bytes remain distinguishable through `native_render_request_sha256` and `native_render_evidence_sha256`.

## 16. Resource policy

Proposed first-slice bounds:

```text
MAX_PDF_BYTES         = 64 MiB
MAX_PDF_PAGE_COUNT    = 256
MAX_PAGE_EDGE_PX      = 16,384
MAX_PAGE_PIXELS       = 32,000,000
MAX_DERIVED_PNG_BYTES = 64 MiB
MIN_RENDER_DPI        = 72
MAX_RENDER_DPI        = 600
```

A4/300 DPI is ~8.7M pixels and remains well below the pixel ceiling.

Rules:

1. reject oversized PDF bytes before parse;
2. verify native PDF hash before parse;
3. parse page count before page selection;
4. render only one page per call;
5. compute/check edge and pixel limits before pixmap materialization;
6. bound encoded PNG size before return;
7. never silently lower DPI or switch page box after a resource failure.

Categorical errors include:

```text
PDF_TOO_LARGE
PDF_PAGE_COUNT_LIMIT
PAGE_INDEX_OUT_OF_RANGE
PAGE_DIMENSION_LIMIT
RENDER_DPI_OUT_OF_RANGE
PNG_SIZE_LIMIT
PDF_MALFORMED
RENDER_RESOURCE_FAILURE
```

If acceptable containment later requires a worker-process supervisor, STOP/rebaseline. The first slice must not create one.

## 17. Validation behavior

`validate_derived_raster_evidence()` receives both exact PDF and PNG bytes so it can independently verify evidence rather than merely shape-check it.

It must fail when any of these diverges:

- existing native request/evidence contract;
- native artifact kind;
- native PDF byte SHA;
- parsed/native page count;
- page index;
- observed crop box;
- rotation;
- UserUnit;
- DPI;
- recomputed matrix;
- renderer identity/version shape;
- PNG byte SHA;
- PNG width/height;
- alpha/background policy;
- A4 request vs observed geometry;
- any unknown/forbidden field.

`derive_native_pdf_page()` builds evidence and then validates the returned evidence against the exact PDF and PNG bytes before returning.

## 18. Malformed/decompression behavior

The adapter opens only already hash-verified bounded bytes.

It must catch PyMuPDF parse/render exceptions, `MemoryError` and equivalent resource failures and expose privacy-safe categorical errors.

No error string may echo PDF content or caller filesystem paths.

No retry path may silently change DPI, renderer, box, alpha or page.

## 19. Relationship to native evidence

Correct provenance:

```text
AUTOCAD_NATIVE PDF evidence
  -> PYMUPDF derived-raster evidence
```

Incorrect provenance:

```text
AUTOCAD_NATIVE PNG evidence
```

for a PNG actually created from the PDF by PyMuPDF.

The derived record references canonical native request/evidence hashes and required scope fields; the native schema remains unchanged.

## 20. Relationship to source fusion

Generated native PDF/PNG artifacts never become SourceBundle/source-custody items.

S2C may copy the **concept** of explicit page geometry and render provenance but not source-custody fields or authority.

## 21. Relationship to visual evidence

S2C returns PNG bytes + derived evidence only.

It does not compare images, issue PASS/FAIL, build repair instructions, authorize publication or persist a visual evidence package.

## 22. Relationship to `run_pdf()`

First runtime slice does not modify or call `primitive_ir_lib/run_pdf.py`.

A later separately issued compatibility refactor may extract a lower-level helper only if it is renderer-mechanical, preserves Primitive behavior and is proven necessary. It is not a first-slice dependency.

## 23. Preferred first runtime write-set

```text
CREATE ONLY:
  mcp_integration_lib/derived_raster_evidence.py
  mcp_integration_lib/tests/test_derived_raster_evidence.py
```

Explicitly do not modify:

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

A need for a third path is a STOP/rebaseline condition.

## 24. Mandatory RED-first matrix

### Native binding

- valid PDF request/evidence + matching bytes;
- request/evidence kind PNG -> reject;
- request/evidence scope mismatch -> existing validator reject;
- stale/substituted evidence -> reject;
- wrong native PDF SHA -> reject;
- native vs parsed page-count mismatch -> reject;
- unsafe native artifact relative path -> existing validator reject.

### Page/geometry

- negative/bool/non-int/out-of-range page index -> reject;
- malformed PDF -> categorical reject;
- invalid/huge page box -> reject;
- deterministic crop/media equivalence behavior;
- rotations 0/90/180/270;
- unsupported rotation -> reject;
- absent UserUnit -> 1;
- non-1 UserUnit -> deterministic geometry;
- invalid UserUnit -> reject.

### A4/300 DPI

- portrait -> exactly `2480 x 3508`;
- landscape -> exactly `3508 x 2480`;
- A4 request with non-A4 observed geometry -> reject;
- forged DPI/matrix -> reject;
- one-pixel evidence mismatch -> reject.

### PNG policy

- output has no alpha;
- white background policy recorded;
- forged alpha/background -> reject;
- PNG SHA mismatch -> reject;
- PNG decoded dimensions mismatch -> reject.

### Replay/version

- same immutable inputs repeated at least 5x -> byte-identical PNG/evidence;
- mapping key/input order changes -> same normalized evidence;
- PyMuPDF binding version drift -> not replay-equivalent;
- MuPDF engine version drift -> not replay-equivalent;
- same PDF bytes with different native request/evidence identity -> different derived evidence.

### Resource/security

- PDF byte limit;
- page-count limit;
- DPI range;
- edge/pixel limit before render;
- PNG byte limit;
- parser/decompression/resource failure privacy;
- no arbitrary pathname open;
- static no network/subprocess/ctypes/AutoCAD/File IPC import;
- static no Primitive/OCR/calibration/model/provider import;
- static no manifest/store/approval/verdict/repair/publisher import.

## 25. Verification requirements

Future runtime acceptance requires:

```text
focused S2C pytest: PASS
5x replay/determinism: PASS
existing autocad_render_evidence tests: PASS
relevant Primitive PDF regressions: PASS
Ruff exact paths: PASS
architecture checker: PASS
git diff --check: PASS
exact write-set audit: PASS
canonical verifier: PASS
hosted tests: PASS
reuse-declaration: PASS
```

AutoCAD live and private/customer data are not required for first-slice offline acceptance.

## 26. Future live acceptance — not authorized here

A later separately authorized live gate should:

1. use only the existing accepted isolated AutoCAD profile/media configuration owner;
2. use a disposable synthetic drawing/layout;
3. create native PDF through the existing AutoCAD/.NET owner;
4. validate native PDF request/evidence;
5. obtain exact PDF bytes through the existing approved artifact handoff;
6. derive page 0 at 300 DPI;
7. require exact A4 portrait/landscape dimensions from observed geometry;
8. repeat derivation and require byte-identical PNG/evidence;
9. prove native PDF bytes, drawing hash and DBMOD remain unchanged;
10. hand PNG downstream read-only;
11. use existing cleanup owner.

Status semantics:

```text
native PDF/profile/media prerequisite unavailable -> NOT RUN
synthetic live derivation executed and all exact gates pass -> PASS
private/customer CAD -> not required
```

An unavailable-state SKIP never becomes live PASS.

## 27. Compatibility / rollback

First runtime slice is additive:

- no existing schema change;
- no manifest migration;
- no dependency/lock change;
- no AutoCAD/plugin change;
- no Primitive pipeline change;
- no stored-data migration.

Rollback is removal of the two new runtime paths. Existing owners remain unchanged.

## 28. Overlap matrix

| Owner/lane | Overlap | Rule |
|---|---:|---|
| native render contract | import/read only | reuse unchanged |
| AutoCAD/.NET native renderer | none | no live owner move |
| local PC3/PMP/profile lane | none | future live prerequisite only |
| source fusion | none | generated artifacts stay outside source custody |
| Primitive `run_pdf` | none first slice | bounded mechanic reference only |
| visual evidence | none | downstream only |
| manifest/checkpoint | none | no persistence |
| R1/R2/R3/R4 | none | disjoint paths and authority |
| deps/contracts/workflows | none | locked |

## 29. STOP conditions

Stop and report to Master PO instead of widening if:

- native PDF bytes cannot be obtained through an existing approved handoff without a new File IPC/path owner;
- native evidence cannot safely bind the exact bytes;
- derived raster requires modifying native render schema;
- only viable reuse is calling `primitive_ir_lib.run_pdf()` wholesale;
- Primitive/OCR/calibration/Semantic behavior becomes required;
- generated artifacts must be forced into SourceBundle/source custody;
- visual evidence would need to become the renderer;
- a new store/cache/manifest/current pointer is required;
- first slice requires dependency/lock/workflow/contract changes;
- a process supervisor is required before bounded offline tests can pass;
- deterministic page-box/UserUnit/matrix policy cannot achieve the required A4/300-DPI dimensions without content-destructive post-processing;
- renderer version cannot be observed/bound deterministically;
- private/customer CAD is required;
- a third runtime path is required;
- another active writer owns either proposed runtime path.

If clean ownership is no longer possible, return:

```text
S2C DERIVED-RASTER SCOPE GAP — MASTER PO DECISION REQUIRED
```

## 30. Conclusion

A clean ownership seam exists.

S2C is one narrow pure adapter from **validated native PDF evidence + exact PDF bytes** to **derived PNG bytes + closed derived-raster evidence**. It reuses the existing native contract, canonical hash owner and already pinned PyMuPDF dependency without moving Primitive/OCR/calibration/source-custody/visual-verdict authority.

Preferred first runtime files:

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```
