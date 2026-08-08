# S2C Derived Raster Evidence Adapter Design

**Status:** Planning only. No runtime implementation is authorized by this document.

**Issue:** #144 — `[Acceleration][Planning] S2C Derived Raster Evidence Adapter executable design`

**Activation:** `5227485477`

**Planning base:** `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

**Planning branch:** `planning/issue-144-s2c-derived-raster-evidence`

## 1. Objective

Close the smallest missing boundary between accepted AutoCAD-native PDF evidence and deterministic derived PNG evidence:

```text
validated AutoCAD-native PDF request/evidence
  + exact native PDF bytes
  -> bounded deterministic PDF-page rasterization
  -> PNG bytes + closed derived-raster evidence
```

This design does **not** create or move ownership for:

- `DWG -> PDF` native rendering;
- AutoCAD plotting, File IPC, .NET dispatch, PC3/PMP/profile policy;
- source PDF custody or source-image render provenance;
- OCR, Primitive IR, Semantic IR, calibration, view-candidate inference;
- Visual Supervisor verdicts or visual comparison;
- manifest/checkpoint persistence;
- approval, repair, publication, or current/accepted promotion.

The only new runtime capability proposed is a **pure generated-candidate PDF -> PNG derived-raster seam** that starts after an already validated native PDF artifact exists.

## 2. Accepted current-main ownership audit

### 2.1 Native AutoCAD render evidence — `REUSE_AS_IS`

Current owner:

```text
mcp_integration_lib/autocad_render_evidence.py
```

Stable accepted surface on the planning base:

```python
REQUEST_SCHEMA_VERSION = "autocad-native-render-request-1.0"
EVIDENCE_SCHEMA_VERSION = "autocad-native-render-evidence-1.0"

build_render_evidence_request(...)
validate_render_request(payload)
validate_render_evidence(payload, request=None)
```

The existing contract already binds:

- request ID and run ID;
- drawing SHA-256;
- latest mutation SHA-256;
- Visual Run Manifest SHA-256;
- layout identity/name;
- artifact kind `PNG | PDF`;
- render options including DPI, paper size, background, plot style and fit-to-paper;
- renderer = `AUTOCAD_NATIVE`;
- artifact SHA-256;
- PDF page count or PNG dimensions;
- read-only `changed=false`;
- equal DBMOD before/after;
- capture timestamp and warnings.

It also rejects absolute/traversal artifact paths and approval/verdict/repair/publication fields.

**Decision:** S2C does not modify this schema and does not redefine native render identity. It validates and consumes it.

### 2.2 Native `DWG -> PDF` execution — `REUSE_AS_IS`

The existing AutoCAD/.NET path remains the only authority that can claim a PDF was rendered natively from a DWG/layout.

S2C receives no AutoCAD document, HWND, File IPC directory, plot device, PC3/PMP/profile, drawing mutation permission, or save authority.

**Boundary:**

```text
AutoCAD/.NET native owner ends at validated PDF evidence + artifact bytes.
S2C derived-raster owner begins there.
```

### 2.3 Input-source PDF fusion provenance — `REJECT_DUPLICATE_OWNER`

Current owner:

```text
cad_agent/source_fusion.py
```

That module explicitly binds **input-source** PDF page/render provenance to SourceBundle and source-custody evidence. Its records include source IDs, custody hashes, PDF page locators, selected boxes, render DPI/matrix and raster hashes.

It does not inspect/render source media itself and it is intentionally scoped to source-fusion identity.

**Decision:** do not reuse or widen it for generated candidate renders. A candidate-native PDF is not a SourceBundle input source, and pretending otherwise would create false custody semantics.

### 2.4 Downstream visual evidence — `REUSE_DOWNSTREAM_ONLY`

Current owner:

```text
cad_agent/visual_evidence.py
```

It snapshots/freshness-checks visual run evidence and packages verified artifacts. It is not a renderer.

**Decision:** S2C may later hand derived PNG evidence downstream, but `cad_agent.visual_evidence` receives rather than creates the raster.

### 2.5 Existing PDF raster mechanics in Primitive IR — `PORT_BOUNDED_LOGIC`

Current owner:

```text
primitive_ir_lib/run_pdf.py
```

`run_pdf()` currently:

1. opens a PDF with PyMuPDF (`fitz`);
2. renders each page with `page.get_pixmap(...)` and `alpha=False`;
3. writes page PNGs;
4. immediately runs `run_image.run()`;
5. performs Primitive IR generation, OCR ROI behavior, calibration, scale-label/view-candidate processing, and child-IR materialization.

The lower-level raster mechanic is useful, but the callable is not reusable as S2C because its ownership is inseparable from Primitive/OCR/calibration orchestration.

**Decision:** do not call `primitive_ir_lib.run_pdf()` from S2C. Reuse only the bounded rendering concept with the repository's existing PyMuPDF dependency. No Primitive/OCR/calibration import is allowed in the S2C module.

### 2.6 PyMuPDF dependency — `REUSE_AS_IS`

Repository runtime requirements already include PyMuPDF, and the Windows Python 3.11 lock on the planning base pins:

```text
pymupdf==1.28.0
```

**Decision:** first runtime slice adds no dependency or lock change.

## 3. Missing capability classification

The repository has:

- a native render contract;
- a native AutoCAD renderer path;
- source-PDF provenance contracts;
- a Primitive pipeline that happens to rasterize PDFs;
- a downstream visual evidence packager.

It does **not** have a narrow owner that can truthfully say:

> These exact bytes are the validated native PDF artifact from this native request/evidence, this exact page was rasterized under this exact page-box/rotation/UserUnit/DPI/matrix/renderer policy, and these are the exact derived PNG bytes and dimensions.

Classification:

```text
NEW_MISSING_CAPABILITY
```

A clean owner can be established without duplicating an existing authority, so this design does **not** return the scope-gap verdict.

## 4. Approaches considered

### Approach A — reuse `primitive_ir_lib.run_pdf()` wholesale

**Rejected.**

Pros:

- existing PyMuPDF rendering already works;
- minimal new rendering code.

Cons:

- imports and executes Primitive IR/OCR/calibration/view-candidate behavior;
- writes multiple pipeline artifacts and manifests;
- requires scale/calibration semantics irrelevant to S2C;
- would make Primitive pipeline behavior part of visual-derived evidence authority.

This violates the Issue authority boundary.

### Approach B — widen `mcp_integration_lib.autocad_render_evidence`

**Rejected for the first slice.**

Pros:

- adjacent to the native evidence contract.

Cons:

- existing schema is specifically `autocad-native-render-evidence-1.0`;
- adding PDF-derived-raster fields would blur native and derived evidence;
- risks making one contract claim two renderer authorities;
- would turn a stable accepted boundary into a moving schema for an additive capability.

The existing module should be consumed unchanged.

### Approach C — add one adjacent pure derived-raster module

**Selected.**

Preferred future paths:

```text
CREATE mcp_integration_lib/derived_raster_evidence.py
CREATE mcp_integration_lib/tests/test_derived_raster_evidence.py
```

The module:

- validates existing native request/evidence through the accepted owner;
- requires `artifact_kind == PDF`;
- verifies exact supplied PDF bytes against the native artifact SHA-256;
- renders exactly one requested page with bounded PyMuPDF mechanics;
- emits PNG bytes in memory plus a closed derived evidence mapping;
- performs no AutoCAD/File IPC/Primitive/OCR/calibration/visual verdict work;
- persists nothing.

This is the smallest clean ownership boundary.

## 5. Authority map

```text
DWG/layout -> native PDF
  owner: existing AutoCAD/.NET + autocad_render_evidence contract

native PDF bytes -> derived PNG bytes
  owner: new S2C derived_raster_evidence module

input-source PDF -> source raster provenance
  owner: cad_agent.source_fusion

PNG visual packaging/freshness
  owner: cad_agent.visual_evidence / existing downstream visual owners

Primitive extraction/OCR/calibration
  owner: primitive_ir_lib and existing OCR/calibration owners

approval/verdict/repair/publication
  owner: existing/future dedicated authorities, never S2C
```

No owner above is replaced or wrapped in a second truth store.

## 6. Selected runtime module responsibility

Proposed module:

```text
mcp_integration_lib/derived_raster_evidence.py
```

It owns exactly three concerns:

1. **native evidence binding** — prove the supplied request/evidence is valid native PDF evidence;
2. **bounded page rasterization** — render one PDF page under one closed renderer policy;
3. **derived evidence validation** — prove exact output identity, dimensions and renderer inputs.

It does not own:

- obtaining the PDF from AutoCAD;
- choosing the drawing/layout to render;
- source custody;
- visual interpretation;
- deciding whether the drawing passes;
- artifact persistence or cleanup outside its returned bytes;
- choosing or mutating system printer configuration.

## 7. Proposed public surface

Planning names are executable candidates for the future runtime Issue; the runtime Issue may make naming-only adjustments if current-main conventions require them without changing semantics.

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
    native_request: object,
    native_evidence: object,
) -> dict[str, object]: ...

def derived_raster_evidence_sha256(
    payload: object,
    *,
    native_request: object,
    native_evidence: object,
) -> str: ...
```

### Why `pdf_bytes`, not a pathname

The first slice deliberately accepts immutable bytes rather than opening an arbitrary caller pathname.

Benefits:

- no second path/root/reparse policy;
- no pathname TOCTOU authority;
- no need to duplicate File IPC artifact-root ownership;
- exact byte hash can be checked before PyMuPDF sees the document;
- synthetic tests are pure and portable.

A later transport/handoff task may obtain those bytes from an existing verified artifact consumer. That integration is not required to prove the derived-raster core.

## 8. Native request/evidence binding

The derivation sequence is fixed:

```text
validate_render_request(native_request)
  -> require artifact_kind == PDF
validate_render_evidence(native_evidence, request=validated_request)
  -> require artifact_kind == PDF
  -> require renderer == AUTOCAD_NATIVE through existing validator
  -> extract native artifact SHA/page_count
verify sha256(pdf_bytes) == native evidence artifact.sha256
compute canonical native_request_sha256
compute canonical native_evidence_sha256
open exact verified bytes with PyMuPDF
```

The canonical native request/evidence hashes use the repository's existing:

```python
cad_agent.drawing_contracts.canonical_json_sha256()
```

No second JSON canonicalizer is introduced.

Raw PDF/PNG byte SHA-256 is a content-integrity operation, not a second canonical JSON identity owner.

## 9. Closed derived evidence shape

Proposed normalized root:

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

No absolute path, source filename, customer identifier, approval, verdict, repair, publish, accepted/current state, HWND, process ID, timestamp generated by S2C, or ambient random identifier is part of the record.

### 9.1 `selected_page_box`

Closed shape:

```text
kind = CROP_BOX
coordinates_pt = [x0, y0, x1, y1]
```

The first slice always renders the effective visible crop box. The box is observed from the verified PDF bytes, not supplied as caller authority.

If the PDF does not provide a valid crop box, the renderer may use a crop box canonically equal to the media box as exposed by PyMuPDF. It must not silently switch between different physical extents across replay.

### 9.2 Rotation

`rotation_degrees` is observed from the selected PDF page and normalized to:

```text
0 | 90 | 180 | 270
```

Any unsupported/non-right-angle page rotation representation fails closed.

### 9.3 UserUnit

The adapter records the effective PDF page UserUnit as a finite positive canonical decimal.

Rules:

- absent `/UserUnit` means `1`;
- zero, negative, non-finite or excessively large values fail closed;
- UserUnit is evidence, never inferred from output pixels;
- physical page-size calculations use the renderer's post-UserUnit page geometry consistently; the implementation must not multiply UserUnit twice.

The future RED suite must contain an explicit non-1 UserUnit fixture to prove this invariant.

## 10. Pixel-dimension policy

Implicit renderer rounding is not accepted as S2C authority.

For an effective physical page width/height in points after the renderer's accepted UserUnit semantics:

```text
ideal_width_px  = width_pt  * render_dpi / 72
ideal_height_px = height_pt * render_dpi / 72
```

S2C uses one explicit nearest-integer policy for each physical dimension and records the exact render matrix that maps the effective page box to those integer dimensions.

The policy must be implemented with deterministic decimal/rational arithmetic rather than binary-float-dependent caller rounding.

The resulting matrix is an image rasterization matrix only. It is not a CAD/global-deformation transform and grants no geometry authority.

### 10.1 A4 / 300-DPI proof

For an accepted A4 page under the selected page-box semantics:

```text
portrait:  2480 x 3508
landscape: 3508 x 2480
```

Orientation is determined by effective page geometry after page rotation.

The runtime test suite must prove both orientations exactly.

If native PDF geometry does not represent A4 under the accepted crop-box/UserUnit semantics, the adapter must not force the page to A4 merely because `render_options.paper_size == "A4"`.

Instead it returns a categorical dimension/geometry mismatch. The native `paper_size` claim and observed PDF geometry must agree for A4 acceptance.

## 11. Render matrix policy

The evidence records the exact six-coefficient affine matrix used for rasterization:

```text
[a, b, c, d, e, f]
```

First-slice policy:

- only scale + the page's existing right-angle rotation semantics;
- no arbitrary shear;
- no caller-provided transform;
- no fit-to-content or content-dependent crop;
- no image post-resize after rasterization;
- translation only as required to map the selected page box to raster origin.

The matrix must be derived solely from:

- selected page box;
- page rotation;
- effective UserUnit semantics;
- requested `render_dpi`;
- deterministic pixel-dimension rounding policy.

A supplied or forged matrix is never accepted as input authority.

## 12. Alpha and background policy

First-slice output is always:

```text
alpha_policy      = OPAQUE_NO_ALPHA
background_policy = WHITE
```

PyMuPDF rendering must produce a non-alpha raster. The PNG output must be verified to contain no alpha channel before evidence is returned.

Caller requests for transparent output, arbitrary background, color-key transparency or post-render compositing are rejected in the first slice.

This matches the intended white-paper engineering drawing evidence path and avoids a second compositing owner.

## 13. Renderer identity and version handling

Closed renderer evidence:

```text
renderer = {
  name: "PYMUPDF",
  binding_version: <PyMuPDF binding version>,
  mupdf_version: <MuPDF engine version>
}
```

The runtime implementation obtains these from the loaded PyMuPDF runtime; the caller cannot provide them.

The repository lock currently pins PyMuPDF 1.28.0, so the first runtime slice requires no dependency change.

### Replay rule

Exact-byte replay equivalence requires all of these to match:

- native request hash;
- native evidence hash;
- native PDF bytes hash;
- page index/count;
- selected box;
- rotation;
- UserUnit;
- DPI;
- render matrix;
- alpha/background policy;
- PyMuPDF binding version;
- MuPDF engine version.

If renderer identity/version changes, old and new outputs are **different evidence generations** even if dimensions happen to match.

No code may silently bless a different-version PNG as replay-equivalent.

## 14. Determinism and duplicate/replay semantics

For identical validated inputs and identical renderer identity/version:

```text
PNG bytes must be byte-identical
PNG SHA-256 must be identical
derived evidence normalization must be identical
derived evidence SHA-256 must be identical
```

The function is idempotent over immutable inputs. It has no internal cache, global current pointer, manifest append, random identifier or ambient timestamp.

If the same native artifact is derived twice, both calls return the same evidence rather than minting two logical identities.

Different native evidence records with the same PDF bytes remain distinguishable because the native request/evidence hashes are part of the derived evidence.

## 15. Resource limits

The runtime Issue must lock concrete constants before production write. The proposed first-slice policy is:

```text
MAX_PDF_BYTES        = 64 MiB
MAX_PDF_PAGE_COUNT   = 256
MAX_PAGE_EDGE_PX     = 16,384
MAX_PAGE_PIXELS      = 32,000,000
MAX_DERIVED_PNG_BYTES = 64 MiB
MIN_RENDER_DPI       = 72
MAX_RENDER_DPI       = 600
```

Rationale:

- A4 at 300 DPI is ~8.7 million pixels, comfortably below the pixel ceiling;
- only one page is rendered per call;
- page count is validated before selecting the page;
- edge and total-pixel limits are checked before materializing a pixmap;
- output byte length is checked before return;
- the adapter never iterates/render-all-pages by default.

The exact constants may be tightened at runtime issuance if synthetic benchmarks justify a smaller safe bound. Widening them requires explicit evidence, not caller input.

### Resource failure behavior

Categorical failures only, such as:

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

No exception may echo private PDF content or arbitrary filesystem paths.

## 16. Malformed/decompression behavior

The adapter must:

1. reject oversized input before opening it;
2. verify the expected SHA before parsing;
3. open from verified bytes, not pathname;
4. read page count before page selection;
5. pre-compute bounded output dimensions before pixmap creation;
6. catch parser/render exceptions and expose categorical privacy-safe errors;
7. catch `MemoryError`/equivalent bounded-resource failure and fail closed;
8. never retry with lower DPI or alternate boxes silently.

If robust wall-clock containment is later shown to require a worker process, that is a separate scope decision. The first pure seam must not create a process supervisor.

## 17. Validation rules

`validate_derived_raster_evidence()` must fail closed when any of the following is inconsistent:

- native request/evidence invalid under existing owner;
- native artifact kind not PDF;
- native request/evidence mismatch;
- native PDF SHA mismatch;
- native evidence page count vs parsed PDF page count mismatch;
- page index outside parsed/native page count;
- page box differs from observed selected box;
- rotation differs from observed page rotation;
- UserUnit differs from observed value;
- DPI differs from policy/request;
- render matrix differs from deterministic recomputation;
- renderer identity/version malformed;
- alpha/background policy differs;
- PNG hash or dimensions malformed;
- A4 native claim and observed A4 geometry disagree;
- unknown root/nested fields;
- forbidden approval/verdict/repair/publication/current-state fields.

## 18. Relationship to `autocad-native-render-evidence-1.0`

The existing native schema is an **input authority**, not a schema to extend.

S2C references it by canonical digest and copies only stable scope fields required for traceability:

```text
run_id
drawing_sha256
latest_mutation_sha256
visual_run_manifest_sha256
layout identity
native PDF SHA/page count
```

S2C never changes native evidence to say that AutoCAD created the PNG.

The correct provenance chain is:

```text
AUTOCAD_NATIVE PDF evidence
  -> PYMUPDF derived-raster evidence
```

not:

```text
AUTOCAD_NATIVE PNG evidence
```

for the derived path.

## 19. Relationship to `cad_agent.source_fusion`

No generated candidate PDF/PNG is inserted into SourceBundle or source custody.

The source-fusion module remains reusable as a **design precedent** for explicit page box, UserUnit, rotation, DPI and render-matrix binding, but its source IDs/custody hashes are not copied into S2C.

This prevents a second source-custody interpretation for generated artifacts.

## 20. Relationship to `cad_agent.visual_evidence`

S2C returns PNG bytes + evidence.

A later consumer may package those bytes through existing visual evidence flows, but S2C does not:

- issue visual PASS/FAIL;
- compare images;
- create region measurements;
- create repair suggestions;
- persist the visual package.

## 21. Relationship to `primitive_ir_lib.run_pdf()`

First runtime slice makes **no modification** to `primitive_ir_lib/run_pdf.py`.

The bounded reusable concept is only:

```python
fitz.open(...)
page.get_pixmap(..., alpha=False)
```

The S2C implementation must independently use PyMuPDF under its narrower contract rather than call the broader Primitive pipeline.

A later compatibility task may refactor a lower-level private helper shared by both modules **only if**:

- the helper is renderer-mechanical only;
- Primitive behavior remains byte/behavior compatible;
- write-set overlap is separately issued;
- tests prove no OCR/calibration ownership moved;
- the change is actually needed.

It is not a prerequisite for S2C first-slice runtime.

## 22. Proposed first runtime write-set

Exact preferred first slice:

```text
CREATE ONLY:
  mcp_integration_lib/derived_raster_evidence.py
  mcp_integration_lib/tests/test_derived_raster_evidence.py
```

No third path.

Explicit do-not-modify list:

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

If the first runtime task requires any listed path, STOP and rebaseline rather than widening the issue.

## 23. RED-first adversarial matrix

The runtime plan must begin with the test file only and prove meaningful RED before production creation.

Minimum RED coverage:

### Native identity

- valid native PDF request/evidence + matching bytes;
- native request says PNG -> reject;
- evidence says PNG -> reject;
- request/evidence ID mismatch -> existing validator reject;
- drawing/latest-mutation/manifest/layout mismatch -> existing validator reject;
- stale substituted native evidence -> reject;
- wrong native PDF hash -> reject;
- parsed page count differs from native evidence page count -> reject.

### PDF/page geometry

- page index `-1`, bool, non-int, `>= page_count` -> reject;
- malformed PDF -> reject categorically;
- invalid/huge page box -> reject;
- crop/media mismatch under selected-box policy -> deterministic expected behavior;
- rotations 0/90/180/270 -> deterministic;
- unsupported rotation -> reject;
- UserUnit absent -> canonical 1;
- non-1 UserUnit -> deterministic dimension/matrix binding;
- invalid UserUnit -> reject.

### A4 / 300 DPI

- A4 portrait -> exactly `2480 x 3508`;
- A4 landscape -> exactly `3508 x 2480`;
- A4 claim with non-A4 observed geometry -> reject;
- wrong DPI -> different deterministic matrix/dimensions or policy rejection;
- forged matrix -> reject validation;
- one-pixel dimension mismatch -> reject validation.

### Alpha/background

- returned PNG has no alpha;
- white background policy recorded;
- transparency request/claim -> reject;
- forged alpha/background evidence -> reject.

### Replay/version

- same bytes/evidence/page/DPI/version repeated >=5 times -> identical PNG bytes/hash/evidence;
- input mapping key order changes -> identical normalized evidence;
- renderer binding version change -> not replay-equivalent;
- MuPDF engine version change -> not replay-equivalent;
- native request/evidence hash changes even when PDF bytes are same -> derived evidence changes.

### Resource/security

- PDF bytes above limit -> reject before parse;
- page count above limit -> reject;
- requested DPI above/below policy -> reject;
- pixel edge/count limit -> reject before render;
- oversized PNG -> reject;
- parser decompression/resource exception -> privacy-safe categorical failure;
- native artifact relative path traversal/absolute/UNC -> rejected through existing validator;
- no arbitrary pathname open by S2C;
- no network/subprocess/ctypes/AutoCAD/File IPC import;
- no Primitive/OCR/calibration/model/provider import;
- no manifest/store/publisher/approval/verdict import.

## 24. Verification requirements

Future runtime tasks must include:

```text
focused pytest: PASS
5x deterministic replay suite: PASS
existing autocad_render_evidence tests: PASS
Primitive run_pdf compatibility smoke/tests: PASS where available
Ruff exact paths: PASS
architecture boundary checker: PASS
git diff --check: PASS
exact write-set audit: PASS
canonical verifier: PASS
hosted tests: PASS
reuse-declaration: PASS
```

AutoCAD Mechanical live and private/customer data are not required for first-slice offline acceptance.

## 25. Live acceptance plan — not authorized by this planning lane

A later separately authorized live gate should:

1. use the existing isolated AutoCAD profile/media configuration lane; S2C does not alter it;
2. use only a disposable synthetic drawing/layout;
3. create one native PDF through the existing AutoCAD/.NET native owner;
4. validate its native request/evidence under `autocad_render_evidence`;
5. snapshot/copy the exact native PDF bytes through the existing approved artifact handoff;
6. run S2C derivation at 300 DPI;
7. require exact A4 portrait or landscape dimensions under observed PDF geometry;
8. run repeated derivation and require byte-identical PNGs;
9. prove native PDF bytes/evidence and drawing DBMOD are unchanged;
10. pass the PNG only to downstream read-only evidence packaging;
11. clean disposable artifacts through their existing owner.

Required status semantics:

```text
native AutoCAD PDF generation unavailable -> NOT RUN
profile/PC3/PMP prerequisite unavailable -> NOT RUN
private/customer drawing -> not required
synthetic live derivation executed and exact gates pass -> PASS
```

No unavailable-state SKIP may be promoted to live PASS.

## 26. Compatibility and migration

The first runtime slice is additive:

- no schema migration;
- no manifest migration;
- no dependency migration;
- no AutoCAD/plugin migration;
- no Primitive pipeline migration;
- no stored-data migration.

Rollback is removing the two new runtime paths. Existing native render, source fusion, Primitive, visual evidence and live paths remain unchanged.

## 27. Overlap matrix

| Lane/owner | Proposed overlap | Decision |
|---|---:|---|
| native render contract | imports/read only | REUSE_AS_IS; do not modify |
| AutoCAD/.NET native renderer | none | no live/runtime owner change |
| local PC3/PMP/profile lane | none | environment-only dependency for future live gate |
| `cad_agent.source_fusion` | none | generated artifacts remain outside source custody |
| `primitive_ir_lib.run_pdf` | none first slice | mechanics reference only |
| `cad_agent.visual_evidence` | none | downstream only |
| R1/R2/R3/R4 lanes | none | separate files/authority |
| manifest/checkpoint | none | no persistence |
| dependencies/workflows/contracts | none | locked |

## 28. STOP conditions

Stop and return to Master PO instead of widening the first runtime task if any of these is discovered:

- native PDF bytes cannot be obtained through an existing approved artifact handoff without inventing a second File IPC/path owner;
- native request/evidence cannot bind the actual PDF bytes safely;
- deterministic PDF-page rasterization requires changing the native render schema;
- the only viable implementation requires calling `primitive_ir_lib.run_pdf()` wholesale;
- OCR/calibration/Primitive/Semantic behavior becomes required;
- candidate-generated render must be forced into SourceBundle/source custody;
- `cad_agent.visual_evidence` would need to become a renderer;
- a new manifest/store/cache/current pointer is required;
- dependency or lock change is required for the first slice;
- a process supervisor is required merely to contain PyMuPDF before bounded offline tests can pass;
- exact A4/300-DPI dimensions cannot be produced under a deterministic page-box/UserUnit/matrix policy without content-destructive post-processing;
- renderer version cannot be captured deterministically;
- private/customer CAD is required for first-slice acceptance;
- first-slice implementation needs a third repository path;
- another active writer owns either proposed runtime path.

If clean ownership becomes impossible because of one of these architectural conflicts, report:

```text
S2C DERIVED-RASTER SCOPE GAP — MASTER PO DECISION REQUIRED
```

## 29. Design conclusion

A clean authority boundary exists.

The missing capability is **not** another AutoCAD/native renderer and **not** another source-PDF provenance system. It is one narrow, pure, deterministic adapter from **validated native PDF evidence + exact PDF bytes** to **derived PNG bytes + closed derived-raster evidence**.

Selected future first-slice ownership:

```text
mcp_integration_lib/derived_raster_evidence.py
mcp_integration_lib/tests/test_derived_raster_evidence.py
```

The existing PyMuPDF dependency is reused; `primitive_ir_lib.run_pdf()` remains unchanged; native render, source fusion, visual packaging, approval/verdict/repair/publication authorities remain separate.
