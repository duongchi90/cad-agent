# WAVE A CAPABILITY MINING REPORT: LEADING CAD & AI-CAD PRODUCTS (ROADMAP RE-ALIGNED)

**Role:** `ANTIGRAVITY_RESEARCH`  
**Mode:** `ROADMAP_CORRECTION_AND_DEEP_TARGET_SELECTION`  
**Canonical State:** GitHub `duongchi90/cad-agent` at `main` commit `47808851b22472e213c8b8d77b735f9dbb88d699` (PR #493 merged)  
**Active Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), `NO_TOUCH_ARC_CIRCLE_MUTATION_EPIC=ENFORCED`  
**Guiding Production Objective (Issue #291):**  
$$\text{ORIGINAL\_NATIVE\_CAD} + \text{MODIFIED\_IMAGE\_OR\_RASTER\_PDF} \rightarrow \text{REUSE ORIGINAL CAD} \rightarrow \text{INFER ONLY THE CHANGED GEOMETRY} \rightarrow \text{BOUNDED NATIVE DELTA} \rightarrow \text{VERIFIED EDITABLE MODIFIED\_DWG}$$

---

## 1. ROADMAP CORRECTION: REAL PRODUCTION INPUT VS. VECTOR PDF

### The Production Reality
In real vehicle engineering and vehicle modification workflows (Issue #291):
1. **The Primary Input is NOT Clean Vector PDF:** Field modifications, subcontractor proposals, chassis lengthening, and body attachments predominantly arrive as **scanned paper drawings, marked-up raster PDFs, or high-resolution PNG/JPG drawings**.
2. **Redrawing From Scratch Violates Product Invariant 1 ("Reuse First"):** Attempting to vectorize a full document from scratch (whether vector or raster) destroys the original native CAD's block definitions, drawing units, layers, native dimensions, and precision metadata.
3. **The Core Problem is DELTA INFERENCE, Not Document Recreation:**
   $$\text{BASE\_STATE} \rightarrow \text{TARGET\_OBSERVATION} \rightarrow \text{ALIGNMENT / CORRESPONDENCE} \rightarrow \text{BOUNDED DELTA} \rightarrow \text{CANDIDATE\_STATE} \rightarrow \text{VERIFIED DWG}$$
   The system must register the target raster observation against the authoritative base CAD, identify *only* what has physically changed, and apply bounded edits while preserving 100% of the untouched base vehicle structure.

### Explicit Retraction & Demotion of `VectorPdfExtractor`
- **Previous Overclaim / Misalignment:** `VectorPdfExtractor` was previously proposed as P0 Epic 1 under the assumption that modern CAD tools export vector PDFs.
- **Correction:** `VectorPdfExtractor` is **DEMOTED** to Backlog / Optional Fast Path. 
- **Architectural Policy:** When a vector PDF is present, cad-agent should reuse AutoCAD's native `PDFIMPORT` command (via `autocad_plugin` / `mcp_integration_lib`) rather than maintaining a custom standalone Python geometry reconstruction engine.

---

## 2. STRICT EVIDENCE TAXONOMY & AUDIT BOUNDARIES

| Evidence Class | Strict Definition & Reality Boundary |
| :--- | :--- |
| **`PUBLIC_SOURCE_VERIFIED`** | Proven directly by inspectable, open-source repositories or published source code. |
| **`PUBLIC_DOC_VERIFIED`** | Documented in official vendor product documentation, command references, or public developer guides. *Crucial rule: A vendor document describing a user-visible feature proves feature existence and UX contract, but does NOT prove the internal proprietary algorithm.* |
| **`RUNTIME_OBSERVED`** | Empirically measured from live software execution on a licensed, unmodified installation using standard inputs/outputs. |
| **`REA_STATIC_VERIFIED`** | Extracted from static analysis of unencrypted, legitimately available binary structures, metadata, or headers. |
| **`INFERRED_BEHAVIOR`** | Plausible engineering deductions regarding closed-source, proprietary internal mechanics. Never treated as fact. |
| **`PROPOSED_CLEAN_ROOM_BEHAVIOR`** | Mathematical algorithms, data structures, and workflows independently authored for `cad-agent` from first principles. |
| **`UNKNOWN`** | Internal mechanics that cannot be verified without reverse-engineering protected binaries or violating licensing. |

### Corrected Product Capability Classifications

| Target / Feature | Corrected Evidence Class | Justification & Reality Boundary |
| :--- | :--- | :--- |
| **BricsCAD `BLOCKIFY`** | **`PUBLIC_DOC_VERIFIED`** (feature UX, tolerance, replacement); **`INFERRED_BEHAVIOR`** (internal indexing); **`PROPOSED_CLEAN_ROOM_BEHAVIOR`** (CadAgent invariant hashing). | Official documentation confirms recognition of identical 2D/3D entities, replacement with `INSERT`s, tolerance control, and previewing. Bricsys proprietary C3D/geometry kernel is closed source. |
| **AutoCAD Smart Blocks (`BDETECT` / `BSEARCH`)** | **`PUBLIC_DOC_VERIFIED`** (review toolbar, text-to-attribute conversion); **`UNKNOWN`** (Autodesk AI ML clustering weights). | Autodesk AI clustering is proprietary. CadAgent clean-room implementation is strictly deterministic. |
| **Forge AI (SolidWorks)** | **`PUBLIC_DOC_VERIFIED`** (panel UX, 1-click Accept/Reject, diff visualization); **`INFERRED_BEHAVIOR`** (internal constraint diff solver). | SolidWorks add-in workflow is documented; internal geometric constraint solver graph is proprietary. |
| **DraftSight `Draw Compare`** | **`PUBLIC_DOC_VERIFIED`** (visual overlay, color-coded additions/deletions/modifications, comparison DWG export); **`UNKNOWN`** (internal DWG comparison kernel). | User-facing DWG comparison is documented; exact tolerance thresholds and database diff algorithms are closed commercial code. |
| **Scan2CAD** | **`PUBLIC_DOC_VERIFIED`** (2-point calibration, line/arc distinction settings); **`UNKNOWN`** (thinning/skeletonization kernels). | Calibration and thresholding settings are user-facing; underlying image processing kernels are closed source. |

---

## 3. MASTER CAPABILITY RECONCILIATION TABLE (PRODUCTION-ALIGNED)

| RANK | CAPABILITY | SOURCE PRODUCT | EVIDENCE CLASS | WHAT IT DOES (VERIFIED) | PROPOSED CAD-AGENT CLEAN-ROOM MECHANISM | CURRENT CAD-AGENT GAP | RECOMMENDED OWNER | REAL PRIORITY |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **1** | **2-Point WCS Spatial Registration & Alignment** | Scan2CAD / DraftSight | `PUBLIC_DOC_VERIFIED` | Solves affine scale, rotation, translation between source raster and DWG coordinates | 2-point similarity transform $[R \| T]$ matching base tie-points to WCS | Only supports manual scalar `--scale-mm-per-px`; cannot solve rotation $\theta$ or translation $(t_x, t_y)$ | `primitive_ir_lib.alignment` / `cad_agent.base_cad_adapter` | **P0** |
| **2** | **Raster vs. Base CAD Delta Inference** | DraftSight / Forge AI | `PUBLIC_DOC_VERIFIED` | Projects base geometry into raster frame to isolate physical changes | Raster edge difference map + projected base CAD linework mask $\rightarrow$ delta ROI bounding box | `run` processes entire raster image indiscriminately, causing hallucinations on unchanged base CAD | `cad_agent.source_fusion` / `cad_agent.source_fusion_proposal` | **P0** |
| **3** | **Proposed Native Delta Staging (`ProposedCadDelta`)** | Forge AI (SolidWorks) | `PUBLIC_DOC_VERIFIED` | Stages candidate mutations as an immutable diff before native commit | Immutable dataclass capturing `KEEP`, `MUTATE`, `ADD`, `REMOVE` entity sets with handle bindings | FileIPC executes direct write commands without an explicit reviewable delta staging contract | `cad_agent.source_fusion_proposal` / `semantic_ir_lib` | **P1** |
| **4** | **Bounded Native Revision Diff (`BoundedCadDiff`)** | DraftSight `Draw Compare` | `PUBLIC_DOC_VERIFIED` | Compares candidate DWG against base DWG and classifies geometric changes | Spatial bounding-box and endpoint curve matching with $10^{-4}\text{ mm}$ tolerance | No CAD-to-CAD geometric comparison tool in `mcp_integration_lib`; cannot prove untouched entities | `cad_agent.geometry_comparison_run` / `mcp_integration_lib.reviewer2` | **P1** |
| **5** | **Deterministic Blockification & Base Block Reuse** | BricsCAD `BLOCKIFY` | `PUBLIC_DOC_VERIFIED` | Replaces repeated loose linework clusters with native `INSERT` references | Invariant signature hashing (sorted lengths, relative centroids) + base block table reuse | Unblocked entities remain loose primitives; cannot reuse base CAD block table records | `semantic_ir_lib.blocks` / `autocad_plugin` | **P1** |
| **6** | **Text Variation to Block Attributes** | AutoCAD Smart Blocks | `PUBLIC_DOC_VERIFIED` | Converts constant linework to Block and variable text to `ATTRIB` | Cluster boundary text isolation $\rightarrow$ `ATTDEF` definition $\rightarrow$ `ATTRIB` instance | Reads attributes during review, but cannot promote loose text into block attributes | `semantic_ir_lib.attributes` | **P2** |
| **7** | **Multi-Angle Rotated OCR Text Detection** | Scan2CAD | `PUBLIC_DOC_VERIFIED` | Recognizes text oriented at $90^\circ, 180^\circ, 270^\circ$ and aligned angles | Bounding-box orientation detection pass before Tesseract inference | Tesseract runs at default orientation; vertical dimensions frequently fail OCR | `primitive_ir_lib` | **P2** |
| **8** | **Curvature Threshold Vector Fitting** | Scan2CAD | `PUBLIC_DOC_VERIFIED` | Separates raster paths into true `LINE`, `ARC`, and `CIRCLE` primitives | Three-point circle/arc fitting on skeletonized pixel contours | Emits short lines/polylines from raster, violating Issue #491 Axis 5 | `primitive_ir_lib` | **P2** |
| **9** | **Semantic Target Resolution** | Forge AI (SolidWorks) | `PUBLIC_DOC_VERIFIED` | Maps user intent to driving geometry/dimensions | Maps high-level intent to target entity handle via feature relation graph | Relies on manual handle targeting in request payload | `semantic_ir_lib` | **P2** |
| **10** | **Pre-Acceptance Interference Validation** | Forge AI (SolidWorks) | `PUBLIC_DOC_VERIFIED` | Checks geometric collisions before committing candidate edits | Spatial bounding-box intersection detector for new candidate primitives | Reviewer checks endpoints only; cannot detect overlapping illegal linework | `dxf_builder_lib.reviewer` | **P2** |
| **11** | **Native Vector PDF Import (`NativePdfImport`)** | AutoCAD `PDFIMPORT` | `PUBLIC_DOC_VERIFIED` | Imports vector PDF geometry natively into ModelSpace via C++ kernel | Invokes native `_PDFIMPORT` via `autocad_plugin` / `mcp_integration_lib` | Custom Python pipeline rasterizes PDF; no bridge to native AutoCAD PDF importer | `mcp_integration_lib` / `autocad_plugin` | **P3 (Fast Path)** |

---

## 4. TOP 5 PRODUCTION EPICS FOR CAD-AGENT (REAL WORKFLOW FIRST)

### EPIC 1 (P0): 2-POINT WCS SPATIAL REGISTRATION & ALIGNMENT (`WcsSpatialRegistration`)
- **Product References:** Scan2CAD Scale Calibration, DraftSight Image Alignment.
- **Production Problem:** In the real workflow ($\text{BASE CAD} + \text{MODIFIED RASTER}$), the user cannot manually align the raster image to the base DWG WCS. If the raster drawing is slightly rotated, shifted, or at an uncalibrated scale, the agent cannot map raster observations to native base CAD entities.
- **Target State:** Agent identifies 2 tie-points common to Base Native CAD and Modification Raster (e.g. wheelbase axles, chassis front datum, grid marks) and solves the rigid similarity transform $[R | T]$ to project the raster observation directly into base WCS.
- **Smallest Owner:** `primitive_ir_lib/alignment.py` and `cad_agent/base_cad_adapter.py`.
- **Minimum V1 Scope:** 2-point 2D similarity transform (uniform scale $s$, rotation $\theta$, translation $[t_x, t_y]$). Validates distance ratio deviation $\le 0.5\%$.
- **Out of Scope:** Non-linear perspective distortion, 3D camera calibration.
- **Causal RED:** A modified chassis drawing shifted by $(+100, +50)\text{ mm}$ and rotated by $3^\circ$ currently fails all feature binding and contour alignment.
- **Dependency Order:** **1st** (Prerequisite for any base reuse).

---

### EPIC 2 (P0): RASTER VS. BASE CAD DELTA INFERENCE (`RasterBaseDeltaInference`)
- **Product References:** DraftSight `Draw Compare`, Forge AI Diff Engine.
- **Production Problem:** Current pipeline feeds the entire raster image through OCR and vectorization, attempting to regenerate the entire drawing. This regenerates unchanged base geometry (cabin, wheels, engine) with raster noise, violating Product Invariant 1 ("Reuse First").
- **Target State:** Project known base CAD geometry onto the registered raster image, generate a base linework exclusion mask, and isolate the **Delta ROI (Region of Interest)** containing the actual modifications. Only entities within or connected to the Delta ROI are analyzed for mutation or addition.
- **Smallest Owner:** `cad_agent/source_fusion.py` and `cad_agent/source_fusion_proposal.py`.
- **Minimum V1 Scope:** Bounding-box difference isolation. Generates `DeltaRegion` containing modified bounding boxes; untouched base entities are immediately marked `KEEP`.
- **Out of Scope:** Automatic topological merge of non-planar intersections.
- **Causal RED:** An unmodified vehicle cabin currently gets re-vectorized into 200 loose polylines. Target pipeline marks cabin entities `KEEP` and processes only the rear chassis delta.
- **Dependency Order:** **2nd** (Directly depends on Registration).

---

### EPIC 3 (P1): PROPOSED NATIVE DELTA STAGING (`ProposedCadDelta`)
- **Product References:** Forge AI (SolidWorks) Staged Suggestions.
- **Production Problem:** FileIPC currently executes mutations directly or constructs DXFs without a structured, immutable staging schema that separates declared intent from execution.
- **Target State:** Formalize an immutable `ProposedCadDelta` contract:
  ```python
  @dataclass(frozen=True)
  class ProposedCadDelta:
      keep_handles: tuple[str, ...]
      mutations: tuple[EntityMutation, ...]
      additions: tuple[NewEntity, ...]
      deletions: tuple[str, ...]
      required_invariants: tuple[InvariantCheck, ...]
  ```
- **Smallest Owner:** `cad_agent/source_fusion_proposal.py` and `semantic_ir_lib`.
- **Minimum V1 Scope:** Typed representation for LINE mutations, entity additions, and deletions, with pre-execution handle validation.
- **Out of Scope:** Parametric constraint graph solving.
- **Causal RED:** Malformed mutation payload currently causes runtime FileIPC exceptions rather than failing closed at delta staging.
- **Dependency Order:** **3rd**.

---

### EPIC 4 (P1): BOUNDED NATIVE REVISION DIFF (`BoundedCadDiff`)
- **Product References:** DraftSight `Draw Compare`.
- **Production Problem:** After AutoCAD executes candidate mutations, cad-agent cannot verify that untouched base entities remained genuinely untouched and identical.
- **Target State:** In-memory geometric diff comparing candidate DWG against base DWG, asserting:
  - `KEEP` count matches base protected count ($10^{-6}\text{ mm}$ tolerance, identical handles).
  - `MUTATE` count matches declared mutations.
  - `ADD` count matches declared additions.
  - `REMOVE` count matches declared deletions.
- **Smallest Owner:** `cad_agent/geometry_comparison_run.py` and `mcp_integration_lib/reviewer2.py`.
- **Minimum V1 Scope:** Direct ModelSpace curve verification (`LINE`, `ARC`, `CIRCLE`, `LWPOLYLINE`).
- **Out of Scope:** 3D Solid B-Rep comparison, layout paper space.
- **Causal RED:** Accidental deletion of a protected base axle currently passes headless review if remaining candidate linework is valid.
- **Dependency Order:** **4th**.

---

### EPIC 5 (P1): DETERMINISTIC BLOCKIFICATION & BASE BLOCK REUSE (`BlockifyDeterministic`)
- **Product References:** BricsCAD `BLOCKIFY`, AutoCAD Smart Blocks.
- **Production Problem:** When new components (e.g. 8 mounting brackets, 16 wheel lugs) are added from raster, they are drawn as loose lines/arcs, inflating file size and failing professional drafting quality standards (Issue #491 Axis 5).
- **Target State:** Detects repeated geometry clusters; checks if a matching block definition already exists in the Base CAD `BlockTableRecord`; if yes, inserts the existing block; if no, creates a new canonical block definition and replaces instances with `INSERT` references.
- **Smallest Owner:** `semantic_ir_lib/blocks.py` and `autocad_plugin/CadAgent.AutoCAD2027`.
- **Minimum V1 Scope:** Planar 2D clusters of `LINE`, `ARC`, and `CIRCLE` entities with invariant shape signature.
- **Out of Scope:** Dynamic/parametric block generation.
- **Causal RED:** 4 identical mounting brackets are added as 32 loose lines instead of 4 `INSERT` references.
- **Dependency Order:** **5th**.

---

## 5. NEXT DEEP TARGET SELECTION FOR ANTIGRAVITY / REA

### Evaluation of Candidates
1. **Candidate A: DraftSight `Draw Compare` & Image Alignment Contract**
   - *Pros:* Directly addresses Epics 1 & 2 (Alignment and Delta Isolation).
   - *Status:* Clean-room 2-point similarity transform $[R | T]$ and raster masking are well-understood standard mathematics (Horn's method / Procrustes analysis); deep REA is not strictly required to author the clean-room math.
2. **Candidate B: BricsCAD `BLOCKIFY` Observable Tolerance & Replacement Contract**
   - *Pros:* High architectural complexity in CAD databases. Resolves exact industrial behavior for:
     - Anchor point selection (centroid vs. bounding-box corner vs. first-picked vertex).
     - Layer inheritance (original entity layers vs. active layer vs. layer "0").
     - Coincident linework separation (how clusters sharing edges with adjacent non-blocked geometry are isolated).
     - Rejection and failure modes.
   - *Status:* Clean-room blockification is Epic 5 and is critical for native drafting quality.
3. **Candidate C: AutoCAD Native `PDFIMPORT` Operator Contract**
   - *Pros:* Addresses the optional fast-path for vector PDFs by reusing native AutoCAD commands rather than rewriting a custom parser.
   - *Status:* Can be inspected directly via AutoCAD command documentation (`_PDFIMPORT` options: import block, layers, line weights).

### Selected Deep Target: BricsCAD `BLOCKIFY` Observable Contract (Black-Box Behavioral Specification)
- **Target:** BricsCAD `BLOCKIFY` / `PARAMETRICBLOCKIFY` observable runtime contract.
- **Mode:** Strictly black-box runtime input/output observation on licensed/clean installations.
- **Deliverable:** `rea_blockify_behavioral_contract_specification.md` for `SOLO_CODEX`.
- **Strict Boundary:** No binary decompilation, no kernel reverse engineering, zero licensing bypass. Observe only DWG before/after artifacts, anchor placements, and layer inheritance rules.
