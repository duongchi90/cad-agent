# Master REA Knowledge Base & Anti-Repeat Index

- **Document ID:** `REA_CATALOG_V2`
- **Role:** `ANTIGRAVITY_REA_CATALOG_AUDITOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-13
- **Basis Commit:** `86318afc722939d88f355437e55405d012cba356` (`origin/main`)
- **Research Branch:** `research/antigravity-2026-10-11`
- **Production Status:** `CATALOG_CORRECTION_ONLY = YES`
- **Production Impact:** `PRODUCTION_CODE_CHANGE = NO`, `PR503_CHANGE = NO`, `AUTOCAD_MUTATION = NO`
- **Catalog Status:** `CATALOG_STATUS = ACCEPTED_ANTI_REPEAT_AUTHORITY`

---

## 0. Anti-Repeat Recovery & Fail-Closed Doctrine

### Catalog Freeze & Authority Declaration
- **CATALOG_STATUS:** `ACCEPTED_ANTI_REPEAT_AUTHORITY`

**Authority Principles:**
- Future sessions consult this catalog first.
- Entries remain research evidence, not production acceptance.
- Current GitHub/main must still be fresh-read before material action.
- `READY_TO_TRANSFER` does not authorize production code absent a current measured RED.
- `TRANSFER_EXPERIMENT_REQUIRED` means execute only its bounded oracle when relevant.
- GitHub current state overrides stale owner mappings.

> [!IMPORTANT]
> **ANTI-REPEAT MANDATE:** Before any agent, researcher, or engineer initiates new reverse engineering, decompilation, or external-library benchmarking, consult this catalog to verify:
> 1. *"Has this external implementation or behavioral contract already been audited?"*
> 2. *"What exact algorithmic invariants, failure modes, and licensing constraints were proven?"*
> 3. *"Where are the durable, repository-relative artifacts, specifications, and test oracles located?"*
>
> **FAIL-CLOSED DIRECTIVE:**
> - An entry marked `DO_NOT_REPEAT_REA = YES` is closed; do not re-investigate without a measured production defect that falsifies its finding.
> - An entry marked `DO_NOT_REPEAT_REA = CONDITIONAL` is gated by the specified condition in `RESEARCH_AGAIN_ONLY_IF`.
> - All durable pointers are strictly repository-relative (`research/...` or production paths). Workstation-local paths (`file:///C:/`, `.gemini/`, `scratch/`) are strictly excluded.

---

# QUICK REA LOOKUP

| REA_ID | Capability | External Source | Reuse Class | Current Cad Agent Owner | Owner Status | Current Disposition | Do Not Repeat? |
| :---: | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **`REA-001`** | `THICK_LINE_NORMALIZATION` | `skimage/morphology/_skeletonize.py` (Zhang-Suen) | `ALGORITHM_TRANSFER` | `primitive_ir_lib/geometry_extraction.py` | `VALID` | `READY_TO_TRANSFER` | `YES` |
| **`REA-002`** | `ARC_FITTING` | `AlliedToasters/circle-fit` (Taubin 1991 SVD) | `ALGORITHM_TRANSFER` | `primitive_ir_lib/geometry_extraction.py` | `VALID` | `READY_TO_TRANSFER` | `YES` |
| **`REA-003`** | `ROTATED_TEXT_OCR` | Tesseract 5.x & Strategy D Aspect Pruning | `ALGORITHM_TRANSFER` | `primitive_ir_lib/text_extraction.py` | `VALID` | `READY_TO_TRANSFER` | `YES` |
| **`REA-004`** | `SUBPIXEL_LINE_SEGMENT_DETECTION`| OpenCV `LineSegmentDetectorImpl` (LSD) | `DEPENDENCY_REUSE` | `primitive_ir_lib/geometry_extraction.py` | `VALID` | `RESEARCH_PRIOR` | `YES` |
| **`REA-005`** | `POLYGONAL_SPLINE_VECTORIZATION` | `tatarize/potrace` (Peter Selinger 2003) | `NOT_REUSABLE` | *None* | `VALID` | `REJECTED` | `YES` |
| **`REA-006`** | `LINE_GRAPH_JUNCTION_SNAPPING` | `Vahe1994/Deep-Vectorization` (`snap_junctions`) | `ALGORITHM_TRANSFER` | `cad_agent/source_fusion_proposal.py` | `VALID` | `ALREADY_IMPLEMENTED` | `YES` |
| **`REA-007`** | `REPEATED_COMPONENT_DISCOVERY` | BricsCAD `BLOCKIFY` / AutoCAD Smart Blocks | `CLEAN_ROOM_BEHAVIORAL_CONTRACT` | `UNKNOWN` | `UNKNOWN` | `RESEARCH_PRIOR` | `CONDITIONAL` |
| **`REA-008`** | `CADMIND_TOOLPACKAGE_ARCHITECTURE`| CadMind v1.0.1 (`tools.*.json`, `IPluginPipeServer`) | `CLEAN_ROOM_BEHAVIORAL_CONTRACT` | `cad_agent/mechanical_skills.py` | `VALID` | `RESEARCH_PRIOR` | `YES` |
| **`REA-009`** | `AUTOCAD_MANAGED_ASSEMBLIES` | AutoCAD 2027 (`acdbmgd.dll`, `acdb26.dll`) | `DEPENDENCY_REUSE` | `autocad_plugin/CadAgent.AutoCAD2027` | `VALID` | `ALREADY_IMPLEMENTED` | `YES` |
| **`REA-010`** | `DIMASSOC_NATIVE_RELATIONSHIP` | AutoCAD 2027 Managed Object Graph (`DIMASSOC=2`) | `CLEAN_ROOM_BEHAVIORAL_CONTRACT` | `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs` | `VALID` | `TRANSFER_EXPERIMENT_REQUIRED` | `CONDITIONAL` |
| **`REA-011`** | `DXF_DOCUMENT_CONSTRUCTION` | `ezdxf` (v1.4.x) | `DEPENDENCY_REUSE` | `dxf_builder_lib/builder.py` | `VALID` | `ALREADY_IMPLEMENTED` | `YES` |
| **`REA-012`** | `WCS_SPATIAL_REGISTRATION` | Scan2CAD 2-Point / Umeyama Similarity $[R\|T]$ | `ALGORITHM_TRANSFER` | `primitive_ir_lib/geometry_alignment.py` | `MOVED` | `READY_TO_TRANSFER` | `YES` |
| **`REA-013`** | `NEGATIVE_RASTER_REMOVAL_EVIDENCE`| Scan2CAD / Forge AI Difference Model | `CLEAN_ROOM_BEHAVIORAL_CONTRACT` | `cad_agent/source_fusion_proposal.py` | `VALID` | `ALREADY_IMPLEMENTED` | `YES` |
| **`REA-014`** | `BASE_CAD_DELTA_MASKING` | DraftSight `Draw Compare` / Forge AI Diff Engine | `CLEAN_ROOM_BEHAVIORAL_CONTRACT` | `cad_agent/source_fusion.py` | `VALID` | `RESEARCH_PRIOR` | `CONDITIONAL` |
| **`REA-015`** | `CIRCLE_FALSE_POSITIVE_VALIDATION`| HoughCircles Accumulator & Perimeter Support | `ALGORITHM_TRANSFER` | `primitive_ir_lib/geometry_extraction.py` | `VALID` | `READY_TO_TRANSFER` | `YES` |
| **`REA-016`** | `COLLINEAR_LINE_MERGING` | PCA Line Fitting & Parallel Guard | `ALGORITHM_TRANSFER` | `primitive_ir_lib/line_merging.py` | `VALID` | `READY_TO_TRANSFER` | `YES` |
| **`REA-017`** | `CALIBRATION_CONSENSUS` | `AGENTS.md` Consensus Gate ($\ge 2$ wits, $\le 3\%$) | `ALGORITHM_TRANSFER` | `primitive_ir_lib/calibration.py` | `VALID` | `READY_TO_TRANSFER` | `YES` |
| **`REA-018`** | `PARAMETRIC_CONSTRAINT_SOLVING` | `solvespace/solvespace` (`python-solvespace==3.0.8`)| `DEPENDENCY_REUSE` | `semantic_ir_lib/constraint_solving.py` | `VALID` | `ALREADY_IMPLEMENTED` | `YES` |
| **`REA-019`** | `OPEN_SOURCE_CAD_ENGINES` | FreeCAD, LibreCAD, LibreDWG, QCAD | `RESEARCH_PRIOR_ONLY` | *None* | `VALID` | `UNKNOWN` | `CONDITIONAL` |
| **`REA-020`** | `POLYLINE_BULGE_AND_ARC_RECONSTRUCTION` | Autodesk DXF Spec Group 42 & `ezdxf.math.bulge` | `ALGORITHM_TRANSFER` | `dxf_builder_lib/builder.py` | `VALID` | `RESEARCH_PRIOR` | `YES` |
| **`REA-021`** | `DIMENSION_ARROWHEAD_WITNESS_ASSOCIATION` | ISO 129-1, ASME Y14.5, LibreCAD `RS_DimLinear`, DXF Specs | `ALGORITHM_TRANSFER` | `primitive_ir_lib/cross_validation.py` | `VALID` | `RESEARCH_PRIOR` | `YES` |
| **`REA-022`** | `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION` | OpenCV `cv2.approxPolyDP` (Ramer-Douglas-Peucker) | `DEPENDENCY_REUSE` | `primitive_ir_lib/geometry_comparator.py` | `VALID` | `RESEARCH_PRIOR` | `YES` |
| **`REA-023`** | `NATIVE_DIMENSION_PLACEMENT_COLLISION_AVOIDANCE` | ASME Y14.5, ISO 129-1, Christensen et al. PFLP Discrete Model | `ALGORITHM_TRANSFER` | `dxf_builder_lib/builder.py` | `VALID` | `RESEARCH_PRIOR` | `YES` |

---

# DETAILED REA ENTRIES

---

### REA-001: THICK_LINE_NORMALIZATION
- **CAPABILITY:** Normalization of thick raster engineering line strokes (width $\ge 5\text{ px}$) that produce duplicate parallel Hough edge lines into a single, unbiased CAD centerline.
- **EXTERNAL_SOURCE:** `scikit-image/scikit-image` (`skimage/morphology/_skeletonize.py`, `_skeletonize_zhang_suen`) implementing Zhang & Suen (1984) parallel thinning algorithm.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (BSD 3-Clause).
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `scikit-image 0.24.x / NumPy 2.x`.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (`_skeletonize.py`) + `TESTS_INSPECTED` (`thick_line/`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/geometry_extraction.py` (`_preprocess()`, `extract_lines()`).
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `READY_TO_TRANSFER`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A measured production defect demonstrates centerline bias or topological failure on a new stroke pattern.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **LICENSE:** BSD 3-Clause.
- **LICENSE_SOURCE:** `https://github.com/scikit-image/scikit-image/blob/main/LICENSE.txt`.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `CLEAN_ROOM_ALGORITHM_TRANSFER` (Direct dependency avoided; clean-room 25-line NumPy 2-pass parallel thinning implementation transferred).
- **WHAT_WAS_INSPECTED:** Canny edge detection vs. Zhang-Suen morphological thinning on synthetic strokes of widths 1, 3, 5, 10, 15 px.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Canny generates two parallel lines separated by stroke width when stroke $\ge 5\text{ px}$ (RED A reproduced).
  - Zhang-Suen parallel 2-pass thinning reduces strokes of arbitrary width to 1-pixel medial skeletons.
  - HoughLinesP applied after thinning yields exactly 1 engineering centerline with $0.0\text{ px}$ vertical bias across widths 1–10 px.
- **FAILURE_MODES_AND_LIMITS:**
  - `GLOBAL_THINNING_SAFE = NO`: Thinning cannot be applied globally to full drawing rasters because it erodes solid arrowheads, destroys small OCR glyph loops (`e`, `o`, `8`), and thins concentric circles into irregular rings.
  - Must be gated locally on candidate line regions.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT import full `scikit-image` package into production dependencies.
  - Do NOT invent custom morphological heuristics when standard Zhang-Suen lookup tables are mathematically complete.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `research/antigravity/2026-10-11/thick_line/test_causal_red_thick_line.py` (Asserts `len(merged) == 1` and `abs(merged[0].p1_px[1] - 250.0) <= 0.5`); and `research/antigravity/2026-10-15/line_detection_loss/TRANSFER_ORACLE.py` (Asserts endpoint witness recovery on arrowhead flare without invading intentional text gaps).
- **2026-10-15_AMENDMENT:**
  - **MEASURED_DEFECT:** Measured production RED on CASE01 (`test_case01_hough_witness.py`) under `real_scan_tuned_v1`: HoughLinesP terminates at $y=224\dots 364$ (missing upper/lower witness rectangles $y=198\dots 219$ and $y=369\dots 390$) because Canny edges flare outward around solid arrowheads, leaving a 9-pixel gap in Canny edges along $x=160$.
  - **RULE_VALIDATION:** Increasing `maxLineGap=10` was falsified because it bridges 100% of the 192 px intentional text gap on NIST FTC-11. Endpoint Ink Ray-Marching (`_extend_line_along_ink`) traces along the Hough unit vector through continuous dark ink (recovering $y=208\dots 379$ on CASE01) while halting dead within 1–2 px of background paper (0.0 px invasion into FTC-11 intentional text gap).
  - **STATUS:** `READY_TO_TRANSFER` (Unblocks Luna implementation on `primitive_ir_lib/geometry_extraction.py::extract_lines`).
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/thick_line/thick_line_centerline_normalization_empirical_specification.md`
  - `research/antigravity/2026-10-11/prior_investigations/raster_empirical_red_and_oss_mining.md`
  - `research/antigravity/2026-10-15/line_detection_loss/`

---

### REA-002: ARC_FITTING
- **CAPABILITY:** Algebraic estimation and fitting of circular arcs and full circles from partial, noisy pixel contours.
- **EXTERNAL_SOURCE:** `AlliedToasters/circle-fit` (`circle_fit/circle_fit.py`, `taubinSVD`) implementing Gabriel Taubin (1991), "Estimation of Planar Curves, Surfaces, and Nonplanar Space Curves Defined by Implicit Equations with Applications to Computer Vision".
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (MIT License) / `ALGORITHM_PAPER`.
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `circle-fit 0.3.x`.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (`circle_fit.py`) + `PAPER_ONLY` (Taubin 1991) + `TESTS_INSPECTED` (`arc_extraction/`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/geometry_extraction.py`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `READY_TO_TRANSFER`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A measured production defect demonstrates radius distortion or non-convergence on elliptical arcs.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **LICENSE:** MIT License.
- **LICENSE_SOURCE:** `https://github.com/AlliedToasters/circle-fit/blob/master/LICENSE.txt`.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `CLEAN_ROOM_ALGORITHM_TRANSFER` (Direct dependency avoided; clean-room NumPy Taubin SVD solver transferred).
- **WHAT_WAS_INSPECTED:** Comparative benchmarks across Kåsa, Taubin, Pratt, OpenCV `minEnclosingCircle`, and RANSAC on circular sweeps from $30^\circ$ to $360^\circ$.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Taubin SVD minimizes $\sum (r_i^2 - R^2)^2 / \sum r_i^2$, eliminating radial shrinkage bias on partial sweeps ($< 180^\circ$).
  - Achieves $0.744\text{ px}$ mean center error and $3.13\%$ radius error on partial arcs ($90^\circ, 180^\circ, 270^\circ$).
  - Circularity metric $\sigma_R / R \le 0.05$ separates circular arcs from arbitrary polylines.
  - Pixel (CW, +y down) to CAD WCS (CCW, +y up) angle inversion contract: $\theta_{cad, start} = (-\theta_{px, end}) \pmod{360^\circ}$.
- **FAILURE_MODES_AND_LIMITS:**
  - Collinear points cause radius $R \to \infty$ ($R > 10^5\text{ px}$); must fail closed to `LineGeometry`.
  - Thick strokes generate duplicate concentric edges; requires distance-transform weighting with round-cap overhang compensation.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT use Kåsa algebraic fit (underestimates radius on sweeps $< 180^\circ$).
  - Do NOT invent iterative gradient descent when closed-form SVD Taubin is deterministic and completes in $< 550\ \mu\text{s}$.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `research/antigravity/2026-10-11/arc_extraction/test_causal_red_taubin_arc.py` (Asserts non-zero `ArcGeometry` emission and radius error $\le 3.5\%$).
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/arc_extraction/taubin_arc_extraction_empirical_specification.md`
  - `research/antigravity/2026-10-11/prior_investigations/raster_empirical_red_and_oss_mining.md`

---

### REA-003: ROTATED_TEXT_OCR
- **CAPABILITY:** Optical character recognition of engineering annotations and dimension callouts oriented at cardinal rotations ($0^\circ, 90^\circ, 180^\circ, 270^\circ$).
- **EXTERNAL_SOURCE:** Tesseract 5.x (`tesseract-ocr/tesseract`) + Strategy D Aspect-Ratio Guided Pruning.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (Apache 2.0) + `SPECIFICATION`.
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `pytesseract 0.3.x / Tesseract 5.x`.
- **PROVENANCE:** `TESTS_INSPECTED` + `RUNTIME_OBSERVED` (Tesseract execution on synthetic crops).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/text_extraction.py` (`extract_text_tesseract()`).
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `READY_TO_TRANSFER`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A non-cardinal angle (e.g. $30^\circ, 45^\circ$) produces OCR failure in a measured production drawing.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **LICENSE:** Apache 2.0.
- **LICENSE_SOURCE:** `https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE`.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `ADAPT_EXISTING_OWNER` (Wrap existing `extract_text_tesseract()` with geometric aspect-ratio pre-rotation and confidence evaluation).
- **WHAT_WAS_INSPECTED:** Production OCR failure modes on rotated text crops and comparison across 4 rotation strategies.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Production `extract_text_tesseract()` fails 100% on $90^\circ, 180^\circ, 270^\circ$ text (returns empty or noise).
  - Tesseract OSD (`--psm 0`) fails 100% on short dimension labels ("Too few characters").
  - Strategy D (if bbox height > width, rotate ROI by $90^\circ$ prior to OCR) achieves $100.0\%$ exact match and rotation accuracy while cutting latency from $719.5\text{ ms}$ to $370.1\text{ ms}$.
- **FAILURE_MODES_AND_LIMITS:**
  - Naive "longest non-empty string" heuristic fails 100% on short dimension numbers, selecting hallucinated punctuation over truth.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT run brute-force 4-pass OCR indiscriminately.
  - Do NOT rely on Tesseract OSD on isolated dimension crops.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `research/antigravity/2026-10-11/text_extraction/test_causal_red_text_extraction.py`.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/text_extraction/cardinal_rotated_text_extraction_empirical_specification.md`
  - `research/antigravity/2026-10-11/prior_investigations/raster_empirical_red_and_oss_mining.md`

---

### REA-004: SUBPIXEL_LINE_SEGMENT_DETECTION (LSD)
- **CAPABILITY:** Subpixel linear contour extraction with false alarm control based on the Helmholtz principle.
- **EXTERNAL_SOURCE:** OpenCV `modules/imgproc/src/lsd.cpp` (`LineSegmentDetectorImpl::detect()`) implementing Rafael Grompone von Gioi, Jeremie Jakubowicz, Jean-Michel Morel, Gregory Randall (2010), "LSD: A Fast Line Segment Detector with a False Detection Control", IEEE TPAMI.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (Apache 2.0).
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `OpenCV 4.x (opencv-python)`.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (`lsd.cpp`) + `PAPER_ONLY` (Grompone von Gioi 2010).
- **REUSE_CLASS:** `DEPENDENCY_REUSE`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/geometry_extraction.py`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `RESEARCH_PRIOR`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A future production epic explicitly requires subpixel line endpoints and cannot use standard Hough/thinning pipelines.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **LICENSE:** Apache 2.0.
- **LICENSE_SOURCE:** `https://github.com/opencv/opencv/blob/4.x/LICENSE`.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `RESEARCH_PRIOR_ONLY` (Do NOT present as a solution to thick-line double edges; retain as subpixel line detector fallback only if a future RED demands it).
- **WHAT_WAS_INSPECTED:** Evaluation of OpenCV LSD against HoughLinesP across 10 engineering drawing criteria.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Extracts subpixel floating-point line endpoints without parameter tuning via Helmholtz NFA.
  - Successfully preserves short line segments down to $5\text{ px}$.
- **FAILURE_MODES_AND_LIMITS:**
  - **Does NOT solve thick line centerline extraction:** Like HoughLinesP, LSD extracts outer boundary edges rather than centerlines on thick strokes ($\ge 5\text{ px}$).
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT rewrite custom line detectors when OpenCV provides native LSD bindings.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/prior_investigations/raster_empirical_red_and_oss_mining.md`

---

### REA-005: POLYGONAL_SPLINE_VECTORIZATION (Potrace)
- **CAPABILITY:** Vectorization of 1-bit bitmaps into polygonal paths and cubic Bezier splines.
- **EXTERNAL_SOURCE:** `tatarize/potrace` implementing Peter Selinger (2003), "Potrace: a polygon-based tracing algorithm".
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (GPL v2+).
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `Potrace 1.16 / tatarize-potrace`.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (`src/trans.c`, `src/curve.c`) + `PAPER_ONLY` (Selinger 2003).
- **REUSE_CLASS:** `NOT_REUSABLE`.
- **CURRENT_CAD_AGENT_OWNER:** *None*.
- **OWNER_MAPPING_STATUS:** `VALID` (No owner exists; rejected capability).
- **CURRENT_DISPOSITION:** `REJECTED`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** Never. Potrace is definitively rejected for CAD primitive extraction.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **LICENSE:** GPL v2+.
- **LICENSE_SOURCE:** `https://github.com/tatarize/potrace/blob/master/COPYING`.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `NO` (Copyleft GPL v2+).
- **PROJECT_INTEGRATION_DECISION:** `REJECTED` (GPL licensing barrier + outputting cubic Bezier splines violates CAD ARC/LINE geometry constraints).
- **WHAT_WAS_INSPECTED:** Potrace curve fitting and polygonal path reduction.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Converts pixel clusters into continuous cubic Bezier curves (`process_path()`).
- **FAILURE_MODES_AND_LIMITS:**
  - Violates CAD geometric constraints: produces smooth Bezier splines rather than explicit `LINE`, `ARC`, and `CIRCLE` entities.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - **DO NOT** import, wrap, or port Potrace for CAD vectorization.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/prior_investigations/raster_empirical_red_and_oss_mining.md`

---

### REA-006: LINE_GRAPH_JUNCTION_SNAPPING
- **CAPABILITY:** Snapping open line endpoints into a closed planar topological graph using spatial index nearest-neighbor queries.
- **EXTERNAL_SOURCE:** `Vahe1994/Deep-Vectorization-for-Floorplans` (`src/line_extraction/lsd_extractor.py`, `snap_junctions()`).
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (MIT License).
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `Deep-Vectorization commit d9b4f2c`.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (`lsd_extractor.py`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `cad_agent/source_fusion_proposal.py` (`compile_external_visual_object_proposal`).
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `ALREADY_IMPLEMENTED`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A topological boundary closure failure occurs on complex multi-loop polygons.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **LICENSE:** MIT License.
- **LICENSE_SOURCE:** `https://github.com/Vahe1994/Deep-Vectorization-for-Floorplans/blob/master/LICENSE`.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `ARCHITECTURAL_PATTERN_TRANSFER` (R-tree line graph snapping transferred to `BOUNDARY_CHAIN` validator).
- **WHAT_WAS_INSPECTED:** Multi-scale line segment snapping and junction formation logic.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Snaps open endpoints within $\Delta d \le 5.0\text{ mm}$ into shared topological vertices.
  - Enforces closed polygon topology for `BOUNDARY_CHAIN` objects.
- **FAILURE_MODES_AND_LIMITS:**
  - Unbounded snapping causes accidental T-junction stem collapse.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT write quadratic $O(N^2)$ pairwise searches when spatial bounding box indexes provide $O(N \log N)$ grouping.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/prior_investigations/raster_empirical_red_and_oss_mining.md`
  - `cad_agent/source_fusion_proposal.py`

---

### REA-007: REPEATED_COMPONENT_DISCOVERY (BLOCKIFY)
- **CAPABILITY:** Detecting identical repeating 2D linework clusters across ModelSpace and consolidating them into a single `BlockTableRecord` referenced by multiple `INSERT` entities.
- **EXTERNAL_SOURCE:** BricsCAD `BLOCKIFY` / `PARAMETRICBLOCKIFY` & AutoCAD Smart Blocks (`BDETECT` / `BSEARCH`).
- **SOURCE_TYPE:** `COMMERCIAL_PRODUCT` (`PUBLIC_DOC_VERIFIED`).
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `BricsCAD V24 / AutoCAD 2024-2027 (Not installed on local host)`.
- **PROVENANCE:** `DOCUMENTATION_ONLY` + `COMMERCIAL_BEHAVIORAL_PRIOR` (Vendor command documentation; internal algorithm is `INFERRED`).
- **REUSE_CLASS:** `CLEAN_ROOM_BEHAVIORAL_CONTRACT`.
- **CURRENT_CAD_AGENT_OWNER:** `UNKNOWN` (`semantic_ir_lib/blocks.py` was claimed in prior catalog but does NOT exist on current main).
- **OWNER_MAPPING_STATUS:** `UNKNOWN` (Claimed file does not exist; no current owner on main).
- **CURRENT_DISPOSITION:** `RESEARCH_PRIOR`.
- **DO_NOT_REPEAT_REA:** `CONDITIONAL`.
- **RESEARCH_AGAIN_ONLY_IF:** A product requirement authorizes native blockification and requires runtime benchmarking of commercial tools.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **LICENSE:** Commercial Proprietary (Bricsys / Autodesk).
- **LICENSE_SOURCE:** Vendor documentation.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `NO` (Clean-room specification only).
- **PROJECT_INTEGRATION_DECISION:** `CLEAN_ROOM_BEHAVIORAL_CONTRACT` (Invariant signature hashing: sorted segment lengths, vertex centroids, bounding-box aspect ratios. Commercial internals NOT copied).
- **WHAT_WAS_INSPECTED:** Official documentation, command options (`match existing Blocks`, `Select source entities`, `Find Collections`), system variables (`BLOCKIFYMODE`, `BLOCKIFYTOLERANCE`).
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Grouping preserves relative translation, rotation, and reflection.
  - Scale variants are strictly rejected to prevent altering engineering dimensions.
  - Replaces $N$ loose clusters with $N$ `AcDbBlockReference` entities.
  - Insertion anchor placed deterministically at the geometric centroid of all cluster vertices.
- **FAILURE_MODES_AND_LIMITS:**
  - Touching or intersecting linework cannot be safely auto-partitioned without explicit user bounding.
  - Differing text strings inside identical linework cause rejection of equality.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT copy Bricsys proprietary C3D geometry kernel or Autodesk AI ML clustering.
  - Do NOT infer block equivalence solely from visual raster similarity.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** 12-point behavioral audit in `research/antigravity/2026-10-11/prior_investigations/rea_blockify_behavioral_contract_specification.md`.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/prior_investigations/rea_blockify_behavioral_contract_specification.md`
  - `research/antigravity/2026-10-11/prior_investigations/wave_a_cad_capability_mining_report.md`
  - `research/external-projects/PROJECT_RESEARCH_INDEX.md`

---

### REA-008: CADMIND_TOOLPACKAGE_ARCHITECTURE
- **CAPABILITY:** Catalog of 90 specialized drafting and auditing toolpackages (fasteners, shafts, bearings, GD&T, tables, layers) and MCP plugin architecture.
- **EXTERNAL_SOURCE:** CadMind v1.0.1 (`CadMind.Shared.dll`, `CadMind.Plugin.dll`, `tools.*.json`).
- **SOURCE_TYPE:** `COMMERCIAL_PRODUCT` / `BINARY_PE_MANAGED`.
- **EXACT_VERSION_COMMIT:** `v1.0.1`.
- **KNOWN_VERSION_FAMILY:** `CadMind 1.0.1`.
- **PROVENANCE:** `BINARY_INSPECTED` (.NET assemblies) + `DOCUMENTATION_ONLY` (`tools.*.json`) + `RUNTIME_OBSERVED` (MCP pipe protocol; LISP encrypted in `CadMindTools.enc`).
- **REUSE_CLASS:** `CLEAN_ROOM_BEHAVIORAL_CONTRACT`.
- **CURRENT_CAD_AGENT_OWNER:** `cad_agent/mechanical_skills.py`, `semantic_ir_lib`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `RESEARCH_PRIOR`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** Never. CadMind binary reverse engineering is completed and clean-room specifications are fully captured.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_RUNTIME`.
- **LICENSE:** Commercial Proprietary (CadMind).
- **LICENSE_SOURCE:** Commercial binary distribution.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `NO` (Clean-room only; implementation encrypted behind ECDH licensing).
- **PROJECT_INTEGRATION_DECISION:** `CLEAN_ROOM_SCHEMA_TRANSFER` (Learn drafting standards and schemas; broad query layer is NOT adopted per Issue #291 and `docs/HANDOFF.md`).
- **WHAT_WAS_INSPECTED:** .NET metadata, MCP pipe dispatch (`IPluginPipeServerMcp`), JSON tool schemas, public DIN/ISO fastener/bearing data tables.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - 90 tool descriptors across shared (24), mechanical (22), structural (25), electrical (19).
  - All tools generate true native AutoCAD entities (`LINE`, `ARC`, `LWPOLYLINE`, `HATCH`, `TABLE`, `TOLERANCE`, `MLEADER`).
- **FAILURE_MODES_AND_LIMITS:**
  - Broad CAD query / tool layers must not be built without a demonstrated product bottleneck (`docs/HANDOFF.md`).
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - **Zero proprietary implementation code copied.**
  - Do NOT build 90 standalone toolpackages; implement capabilities into existing Cad Agent owners only when demanded by workflows.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/prior_investigations/cadmind_toolpackage_reconstruction.md`
  - `research/antigravity/2026-10-11/prior_investigations/cadmind_technical_evidence_report.md`
  - `research/external-projects/PROJECT_RESEARCH_INDEX.md`
  - `docs/HANDOFF.md`

---

### REA-009: AUTOCAD_MANAGED_ASSEMBLIES
- **CAPABILITY:** Pure managed .NET database inspection, transaction management, and entity reading in AutoCAD 2027.
- **EXTERNAL_SOURCE:** Autodesk AutoCAD 2027 Managed Assemblies (`acdbmgd.dll`, `accoremgd.dll`, `acmgd.dll`, `acdb26.dll`).
- **SOURCE_TYPE:** `BINARY_PE_MANAGED` / `CLEAN_SPEC`.
- **EXACT_VERSION_COMMIT:** `26.0.0.0`.
- **KNOWN_VERSION_FAMILY:** `AutoCAD 2027 Commercial/Preview 64-bit`.
- **PROVENANCE:** `BINARY_INSPECTED` (`acdbmgd.dll` metadata, `acdb26.dll` PE exports) + `RUNTIME_OBSERVED` (`accoreconsole.exe`).
- **REUSE_CLASS:** `DEPENDENCY_REUSE`.
- **CURRENT_CAD_AGENT_OWNER:** `autocad_plugin/CadAgent.AutoCAD2027`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `ALREADY_IMPLEMENTED`.
- **REJECTED_ALTERNATIVE:** `DIRECT_NATIVE_CPP_PINVOKE`.
- **REJECTED_ALTERNATIVE_DISPOSITION:** `REJECTED`.
- **REJECTED_ALTERNATIVE_REASON:** MSVC C++ ABI / AcDbObjectId by-value marshaling / version coupling is not a supported safe Cad Agent integration route.
- **DO_NOT_REPEAT_NATIVE_PINVOKE_RESEARCH:** `YES`.
- **REOPEN_NATIVE_ROUTE_ONLY_IF:** Autodesk exposes a supported stable managed or C ABI that removes the current ABI boundary, or a measured product RED proves the managed SDK cannot satisfy the required capability.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** AutoCAD version upgrades to 2028+ modifying managed API signatures.
- **EVIDENCE_TIER:** `OBSERVED_MANAGED_METADATA` / `OBSERVED_RUNTIME`.
- **LICENSE:** Commercial SDK / Mixed-mode C++/CLI.
- **LICENSE_SOURCE:** Autodesk AutoCAD 2027 installation.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES` (for official managed assemblies in plugin) / `NO` (for direct C++ P/Invoke).
- **PROJECT_INTEGRATION_DECISION:** `USE_MANAGED_ASSEMBLIES_ONLY__REJECT_PINVOKE` (Pure managed .NET APIs permitted; direct unmanaged P/Invoke strictly rejected).
- **WHAT_WAS_INSPECTED:** Audited all 6,414 types across managed assemblies and PE exports of `acdb26.dll`.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - **Retraction Established:** No managed class `Autodesk.AutoCAD.DatabaseServices.DimAssoc` exists.
  - Native functions (`?acdbUpdateDimension@@YA...`) export MSVC C++ mangled symbols taking `AcDbObjectId` by value.
  - Direct P/Invoke is `REJECTED_UNSAFE` due to ABI incompatibility, struct-by-value marshaling hazards, and tight version coupling.
  - Pure managed inspection via `DBObject.GetPersistentReactorIds()` and `ExtensionDictionary` is 100% stable and supported.
- **FAILURE_MODES_AND_LIMITS:**
  - Calling native P/Invoke on `acdb26.dll` can corrupt heap or crash `accoreconsole.exe`.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT attempt P/Invoke into `acdb26.dll` or `accore.dll`.
  - Do NOT build an unmanaged ObjectARX C++ bridge.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/prior_investigations/rea_evidence_driven_code_avoidance_investigation.md`
  - `autocad_plugin/CadAgent.AutoCAD2027/`

---

### REA-010: DIMASSOC_NATIVE_RELATIONSHIP
- **CAPABILITY:** Reliable read-only discrimination of associative dimension reactors from arbitrary persistent reactors and proof of exact LINE $\leftrightarrow$ DIMENSION pairing in AutoCAD 2027.
- **EXTERNAL_SOURCE:** AutoCAD 2027 Database Engine (`AcDbDimAssoc`, `AcDbAlignedDimension`, `AcDbLine`).
- **SOURCE_TYPE:** `BINARY_PE_MANAGED` / `OBSERVED_AUTOCAD_DATABASE`.
- **EXACT_VERSION_COMMIT:** `26.0.0.0`.
- **KNOWN_VERSION_FAMILY:** `AutoCAD 2027 Commercial/Preview 64-bit`.
- **PROVENANCE:** `BINARY_INSPECTED` (`AcDbDimAssoc` metadata) + `RUNTIME_OBSERVED` (`accoreconsole.exe`) + `TESTS_INSPECTED` (Controls 1..4 in ReactorInspector).
- **REUSE_CLASS:** `CLEAN_ROOM_BEHAVIORAL_CONTRACT`.
- **CURRENT_CAD_AGENT_OWNER:** `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `TRANSFER_EXPERIMENT_REQUIRED`.
- **DO_NOT_REPEAT_REA:** `CONDITIONAL`.
- **RESEARCH_AGAIN_ONLY_IF:** Luna executes the committed causal probe in `dimassoc_reactor_validation/luna_handoff_causal_mutation_probe.md`.
- **EVIDENCE_TIER:** `OBSERVED_RUNTIME` / `OBSERVED_TEST` / `OBSERVED_AUTOCAD_DATABASE`.
- **LICENSE:** Commercial AutoCAD 2027 runtime.
- **LICENSE_SOURCE:** Autodesk AutoCAD 2027 installation.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES` (via managed API).
- **PROJECT_INTEGRATION_DECISION:** `TRANSFER_EXPERIMENT_REQUIRED` (Read-only relationship proven; production policy relaxation strictly gated on future Luna causal probe).
- **WHAT_WAS_INSPECTED:** Differential A/B synthetic DWG fixtures (`FIXTURE_A`, `DIMASSOC=1` vs `FIXTURE_B`, `DIMASSOC=2`) executed headlessly in `accoreconsole.exe`.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Read-only classifier discriminates: `NoReactor`, `KnownDimAssocReactor`, `UnknownOtherReactor`, `MixedReactors` via `ObjectClass.DxfName == "DIMASSOC"`.
  - Exact pairing proven via 3 independent structural invariants:
    1. Symmetric Reactor Intersection: `dim.GetPersistentReactorIds().Contains(lineReactorId) == true`.
    2. Extension Dictionary Anchor: `dim.ExtensionDictionary["ACAD_DIMASSOC"] == lineReactorId`.
    3. Hard Ownership Hierarchy: `AcDbDimAssoc.OwnerId == dim.ExtensionDictionary.ObjectId`.
  - All 4 adversarial controls (Controls 1–4) passed with 100% accuracy.
- **FAILURE_MODES_AND_LIMITS:**
  - Current production `BoundedNativeLineEditPolicy.RequireTargetLine()` rejects all lines where `HasPersistentReactors=true`.
  - Read-only proof does **NOT** prove that mutating the line preserves dimension associativity across transaction commit and save/reopen.
  - `PRODUCTION_CHANGE_AUTHORIZED = NO`.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT modify production policy before Luna completes the causal mutation probe.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `research/antigravity/2026-10-11/dimassoc_reactor_validation/luna_handoff_causal_mutation_probe.md`.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/dimassoc_reactor_validation/dimassoc_reactor_validation_report.md`
  - `research/antigravity/2026-10-11/dimassoc_reactor_validation/luna_handoff_causal_mutation_probe.md`
  - `research/antigravity/2026-10-11/dimassoc_reactor_validation/logs/inspection_result.txt`

---

### REA-011: DXF_DOCUMENT_CONSTRUCTION
- **CAPABILITY:** Headless creation, querying, and serializing of complete DXF R2018 CAD drawings, modelspace geometry, layers, and styles.
- **EXTERNAL_SOURCE:** `mozman/ezdxf` (v1.4.x).
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (MIT License).
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `ezdxf >= 1.4.0 (repo requirements: ezdxf>=1.4.4)`.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` + `TESTS_INSPECTED`.
- **REUSE_CLASS:** `DEPENDENCY_REUSE`.
- **CURRENT_CAD_AGENT_OWNER:** `dxf_builder_lib/builder.py`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `ALREADY_IMPLEMENTED`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A breaking DXF schema change occurs in upstream `ezdxf`.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **LICENSE:** MIT License.
- **LICENSE_SOURCE:** `https://github.com/mozman/ezdxf/blob/master/LICENSE.txt`.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `DIRECT_DEPENDENCY_REUSE` (Core pinned dependency in `requirements/`).
- **WHAT_WAS_INSPECTED:** Construction of `Drawing`, `ModelSpace`, entity tables, and dimension styles.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Generates valid DXF documents conforming to AutoCAD R2018 specifications.
  - Clean headless roundtrip without requiring AutoCAD native runtime.
- **FAILURE_MODES_AND_LIMITS:**
  - `ezdxf` does not evaluate dynamic blocks, associative dimension reactor graphs, or constraint solvers.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT write custom raw DXF ASCII text formatters; always use `ezdxf`.
- **DURABLE_POINTERS:**
  - `requirements/`
  - `dxf_builder_lib/`

---

### REA-012: WCS_SPATIAL_REGISTRATION
- **CAPABILITY:** Rigid similarity transformation $[R | T]$ solving uniform scale $s$, rotation angle $\theta$, and translation $(t_x, t_y)$ to project raster observation coordinates directly into base CAD WCS coordinates.
- **EXTERNAL_SOURCE:** Scan2CAD 2-Point Calibration / Umeyama (1991) / Kabsch algorithm.
- **SOURCE_TYPE:** `ALGORITHM_PAPER` / `COMMERCIAL_PRODUCT`.
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `Scan2CAD V10 (Commercial Prior) / Umeyama 1991`.
- **PROVENANCE:** `PAPER_ONLY` (Umeyama 1991) + `COMMERCIAL_BEHAVIORAL_PRIOR` (Scan2CAD 2-point UX) + `TESTS_INSPECTED` (`orientation/`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/geometry_alignment.py`.
- **OWNER_MAPPING_STATUS:** `MOVED` (Prior catalog named `primitive_ir_lib/alignment.py` which was renamed to `geometry_alignment.py` on main).
- **CURRENT_DISPOSITION:** `READY_TO_TRANSFER`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A non-rigid or non-linear lens distortion model is required.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **LICENSE:** Open literature / Commercial Prior.
- **LICENSE_SOURCE:** Academic literature (Umeyama 1991).
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `CLEAN_ROOM_ALGORITHM_TRANSFER` (Policy D declared orientation envelope + 2-point similarity transform transferred).
- **WHAT_WAS_INSPECTED:** 4 orientation registration policies across rotational symmetries ($0^\circ, 90^\circ, 180^\circ, 270^\circ$).
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Solves exact 2D similarity transform: $\mathbf{p}_{\text{wcs}} = s R(\theta) \mathbf{p}_{\text{px}} + \mathbf{t}$.
  - Policy D eliminates 100% of rotational symmetry traps by requiring caller-declared orientation envelopes.
  - Collinear anchor handling treated as a product-safety policy gate rather than an unsolvable singularity.
- **FAILURE_MODES_AND_LIMITS:**
  - 2-point similarity transform cannot solve non-linear perspective keystone distortion; assumes orthographic scan.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT invent heuristic symmetry tie-breakers; enforce explicit orientation envelopes.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `research/antigravity/2026-10-11/orientation/orientation_policy_benchmark.py`.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/orientation/target_base_orientation_policy_discriminator_specification.md`
  - `research/antigravity/2026-10-11/orientation/raster_base_wcs_registration_empirical_specification.md`
  - `primitive_ir_lib/geometry_alignment.py`

---

### REA-013: NEGATIVE_RASTER_REMOVAL_EVIDENCE
- **CAPABILITY:** Verification of whether an unmatched base CAD entity can be safely removed based on source raster pixel evidence.
- **EXTERNAL_SOURCE:** Scan2CAD Raster Masking / Forge AI Difference Model.
- **SOURCE_TYPE:** `COMMERCIAL_PRODUCT` / `SPECIFICATION`.
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `Clean-room specification SOURCE_NEGATIVE_LINE_SUPPORT_EVIDENCE_V1`.
- **PROVENANCE:** `COMMERCIAL_BEHAVIORAL_PRIOR` (Scan2CAD / Forge AI diff concept) + `TESTS_INSPECTED` (`removal/`).
- **REUSE_CLASS:** `CLEAN_ROOM_BEHAVIORAL_CONTRACT`.
- **CURRENT_CAD_AGENT_OWNER:** `cad_agent/source_fusion_proposal.py`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `ALREADY_IMPLEMENTED`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** Never. The safety doctrine `UNMATCHED_BASE != REMOVE` is frozen across all modes.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **LICENSE:** Clean-room policy doctrine.
- **LICENSE_SOURCE:** Internal project safety invariant.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `ADOPT_SAFETY_DOCTRINE__UNMATCHED_BASE_NEQ_REMOVE`.
- **WHAT_WAS_INSPECTED:** 12 raster dropout failure modes (scanning glare, folds, white-out, text occlusions, hatch collisions).
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - **CORE DOCTRINE:** `UNMATCHED_BASE != REMOVE`. Absence of raster detection is NOT evidence of deletion.
  - Negative source-support evidence must remain observational and cannot directly authorize native entity deletion.
  - Pixel-domain verifier contract closed; native removal blocked behind stronger semantic/identity proofs.
- **FAILURE_MODES_AND_LIMITS:**
  - Naive inversion of positive raster support causes catastrophic deletion of valid chassis geometry obscured by text or dimensions.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - **DO NOT** implement automated native entity deletion based on raster vacancy alone.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/removal/source_negative_line_support_empirical_specification.md`
  - `cad_agent/source_fusion_proposal.py`

---

### REA-014: BASE_CAD_DELTA_MASKING
- **CAPABILITY:** Projecting known base CAD geometry onto the registered target raster image to generate an exclusion mask and isolate the Delta ROI (Region of Interest).
- **EXTERNAL_SOURCE:** DraftSight `Draw Compare` / Forge AI Diff Engine.
- **SOURCE_TYPE:** `COMMERCIAL_PRODUCT` / `SPECIFICATION`.
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `DraftSight 2024 (Commercial Prior)`.
- **PROVENANCE:** `COMMERCIAL_BEHAVIORAL_PRIOR` (DraftSight Draw Compare UX) + `DOCUMENTATION_ONLY`.
- **REUSE_CLASS:** `CLEAN_ROOM_BEHAVIORAL_CONTRACT`.
- **CURRENT_CAD_AGENT_OWNER:** `cad_agent/source_fusion.py`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `RESEARCH_PRIOR`.
- **DO_NOT_REPEAT_REA:** `CONDITIONAL`.
- **RESEARCH_AGAIN_ONLY_IF:** A measured production defect demonstrates unchanged base CAD linework re-vectorization.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **LICENSE:** Commercial Prior.
- **LICENSE_SOURCE:** Vendor documentation.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES` (Concept).
- **PROJECT_INTEGRATION_DECISION:** `RESEARCH_PRIOR__AWAIT_MEASURED_RED` (Clean-room delta bounding box mask architecture designed; production implementation gated on measured delta extraction need).
- **WHAT_WAS_INSPECTED:** Whole-image processing vs. Delta ROI masking on modified vehicle drawings.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Whole-image processing re-vectorizes unchanged base geometry into noisy polylines.
  - Delta masking marks projected base CAD entities `KEEP`, subtracts them from the raster observation, and restricts vectorization/OCR strictly to Delta ROI bounding boxes.
- **FAILURE_MODES_AND_LIMITS:**
  - Requires subpixel accuracy from spatial registration (`REA-012`) to prevent masking offsets.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT re-vectorize untouched base CAD linework.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/prior_investigations/wave_a_cad_capability_mining_report.md`
  - `research/external-projects/PROJECT_RESEARCH_INDEX.md`
  - `cad_agent/source_fusion.py`

---

### REA-015: CIRCLE_FALSE_POSITIVE_VALIDATION
- **CAPABILITY:** Validation of OpenCV Hough circle candidates against source raster perimeter evidence to eliminate ghost circles caused by hatch, text, corners, and noise.
- **EXTERNAL_SOURCE:** OpenCV `cv2.HoughCircles` accumulator analysis + Radial Distance Variance Filter.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` / `SPECIFICATION`.
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `OpenCV 4.x`.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (OpenCV HoughCircles) + `TESTS_INSPECTED` (`circle_validation/`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/geometry_extraction.py` (`extract_circles()`).
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `READY_TO_TRANSFER`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A false-positive circle appears in production on a previously unstudied hatch/noise pattern.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **LICENSE:** Apache 2.0.
- **LICENSE_SOURCE:** `https://github.com/opencv/opencv/blob/4.x/LICENSE`.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `CLEAN_ROOM_ALGORITHM_TRANSFER` (Perimeter support oracle transferred).
- **WHAT_WAS_INSPECTED:** Baseline HoughCircles generating 144 false-positive circles on non-circle patterns (cross-hatch, text, grid crossings) and spurious concentric ghost rings on large circles.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Enforces perimeter support oracle: minimum circumference support $\ge 75\%$, max unsupported angular gap $\le 45^\circ$, radial gradient alignment $\ge 60\%$, and radial distance roundness $\sigma_r \le \max(0.35, 0.04r)$.
  - Achieves $100.0\%$ false-positive elimination rate (0/144 false detections accepted) while retaining $100.0\%$ of true circles across 35 configurations.
- **FAILURE_MODES_AND_LIMITS:**
  - Inside/outside contrast check is unsafe for solid disks and thick strokes.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT accept raw `cv2.HoughCircles` output without perimeter evidence validation.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `research/antigravity/2026-10-11/circle_validation/circle_false_positive_perimeter_validation_empirical_specification.md`.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/circle_validation/circle_false_positive_perimeter_validation_empirical_specification.md`
  - `primitive_ir_lib/geometry_extraction.py`

---

### REA-016: COLLINEAR_LINE_MERGING
- **CAPABILITY:** Merging collinear fragmented line segments while strictly preserving parallel lines, dimension witness chains, and T-junctions.
- **EXTERNAL_SOURCE:** Principal Component Analysis (PCA) line fitting + Parallel Line Separation Guard.
- **SOURCE_TYPE:** `SPECIFICATION` / `ALGORITHM_TRANSFER`.
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `Clean-room specification COLLINEAR_LINE_MERGING_V1`.
- **PROVENANCE:** `TESTS_INSPECTED` (`line_merging/`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/line_merging.py` (`merge_collinear_lines()`).
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `READY_TO_TRANSFER`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A measured production defect demonstrates collinear fragmentation or parallel collapse.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **LICENSE:** Internal project clean-room algorithm.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `CLEAN_ROOM_ALGORITHM_TRANSFER`.
- **WHAT_WAS_INSPECTED:** Production `merge_collinear_lines` causing first-segment angle skew ($2.8^\circ$ error, $20.49\text{ px}$ drift) and parallel line collapse ($79.0\%$ failure on 105 test pairs).
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Strategy D (Weighted PCA + Parallel Guard): achieves $0.004^\circ$ angle error, $0.029\text{ px}$ lateral drift, $100\%$ parallel line preservation, and $100\%$ dimension chain recall.
  - Executes in $35.1\ \mu\text{s}$ per call.
- **FAILURE_MODES_AND_LIMITS:**
  - Naive endpoint-only bounding allows perpendicular endpoint leaks; requires strict bilateral projection bounding.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT anchor line angle solely to the first segment's orientation.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `research/antigravity/2026-10-11/line_merging/collinear_line_merging_empirical_specification.md`.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/line_merging/collinear_line_merging_empirical_specification.md`
  - `primitive_ir_lib/line_merging.py`

---

### REA-017: CALIBRATION_CONSENSUS
- **CAPABILITY:** Multi-candidate automatic scale calibration from text dimension callouts and carrier geometry, enforcing the `AGENTS.md` consensus gate.
- **EXTERNAL_SOURCE:** `AGENTS.md` production invariant ($\ge 2$ independent witnesses, $\le 3.0\%$ median relative error) & carrier collinear gap bridging.
- **SOURCE_TYPE:** `SPECIFICATION` / `ALGORITHM_TRANSFER`.
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `Clean-room specification AUTOMATIC_CALIBRATION_CONSENSUS_V1`.
- **PROVENANCE:** `DOCUMENTATION_ONLY` (`AGENTS.md`) + `TESTS_INSPECTED` (`calibration_consensus/`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/calibration.py`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `READY_TO_TRANSFER`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A multi-scale drawing or unstated unit convention fails consensus in production.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **LICENSE:** Internal project policy specification.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `CLEAN_ROOM_ALGORITHM_TRANSFER`.
- **WHAT_WAS_INSPECTED:** Production `calibration.py` allowing single-candidate scale estimation, permissive $10\%$ error, and sheet-number ("09") hallucination ($99\%$ error).
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Strict enforcement of $\ge 2$ independent candidates with median relative error $\le 3.0\%$.
  - Fails closed on single candidates, $> 3\%$ discrepancies, or conflicting mixed-scale views.
  - Bridges text gap interruptions up to $120\text{ px}$ along collinear carrier lines.
- **FAILURE_MODES_AND_LIMITS:**
  - Unstated units (imperial drawings missing `"in"`) risk 25.4x catastrophic scaling error; requires draft reference mode (`$INSUNITS = 0`).
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT return unverified single-candidate calibrations.
  - Do NOT relax the $\le 3.0\%$ consensus threshold to $10.0\%$.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-11/calibration_consensus/calibration_consensus_empirical_specification.md`
  - `research/antigravity/2026-10-11/calibration_candidate_transfer/calibration_candidate_extraction_transfer_empirical_specification.md`
  - `primitive_ir_lib/calibration.py`

---

### REA-018: PARAMETRIC_CONSTRAINT_SOLVING
- **CAPABILITY:** Analytical geometric 2D constraint solving (coincident, horizontal, vertical, parallel, perpendicular, symmetric, tangent, distance, diameter).
- **EXTERNAL_SOURCE:** `solvespace/solvespace` (`python-solvespace==3.0.8`).
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (GPL v3+ with Python C-extension binding).
- **EXACT_VERSION_COMMIT:** `3.0.8`.
- **KNOWN_VERSION_FAMILY:** `python-solvespace==3.0.8 (Pinned)`.
- **PROVENANCE:** `BINARY_INSPECTED` / `SOURCE_CODE_INSPECTED` (`python-solvespace` C-extension) + `TESTS_INSPECTED`.
- **REUSE_CLASS:** `DEPENDENCY_REUSE`.
- **CURRENT_CAD_AGENT_OWNER:** `semantic_ir_lib/constraint_solving.py` (`solve_constraints()`).
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `ALREADY_IMPLEMENTED`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** Never. SolveSpace is the exclusive pinned constraint solver for Cad Agent.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **LICENSE:** GPL v3+.
- **LICENSE_SOURCE:** `https://github.com/solvespace/solvespace/blob/master/COPYING.txt`.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES` (Already pinned in repository requirements).
- **PROJECT_INTEGRATION_DECISION:** `PINNED_EXCLUSIVE_DEPENDENCY` (Sole pinned solver owner; replacement strictly forbidden).
- **WHAT_WAS_INSPECTED:** SolveSpace constraint solver bindings across mechanical geometry.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Solves complex coupled mechanical constraints with exact numerical convergence ($0.000\text{ mm}$ residual).
  - Handles datum anchoring via `sys.dragged` and parametric symmetry via `sys.symmetric`.
- **FAILURE_MODES_AND_LIMITS:**
  - Over-constrained systems or conflicting redundant constraints cause solver divergence; requires graph-theoretic constraint pruning (`semantic_ir_lib/constraint_pruning.py`).
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - **DO NOT** replace or rewrite `python-solvespace`.
  - **DO NOT** create a parallel constraint solver.
- **DURABLE_POINTERS:**
  - `semantic_ir_lib/constraint_solving.py`
  - `research/antigravity/2026-10-11/symmetry_constraint_detection/symmetry_axis_and_symmetric_feature_constraint_detection_empirical_specification.md`

---

### REA-019: OPEN_SOURCE_CAD_ENGINES (FreeCAD, LibreCAD, LibreDWG, QCAD)
- **CAPABILITY:** Open-source CAD engines, geometry kernels, and DWG file decoding libraries.
- **EXTERNAL_SOURCE:** FreeCAD, LibreCAD, LibreDWG, QCAD.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO`.
- **EXACT_VERSION_COMMIT:** `UNKNOWN`.
- **KNOWN_VERSION_FAMILY:** `UNKNOWN (Uninspected)`.
- **PROVENANCE:** `UNKNOWN`.
- **REUSE_CLASS:** `RESEARCH_PRIOR_ONLY`.
- **CURRENT_CAD_AGENT_OWNER:** *None*.
- **OWNER_MAPPING_STATUS:** `VALID` (No owner exists; uninspected capability).
- **CURRENT_DISPOSITION:** `UNKNOWN`.
- **DO_NOT_REPEAT_REA:** `CONDITIONAL`.
- **RESEARCH_AGAIN_ONLY_IF:** Explicitly commissioned by architecture with a declared target engine and clean-room boundary.
- **EVIDENCE_TIER:** `UNKNOWN`.
- **LICENSE:** Various (GPL v2, GPL v3, LGPL).
- **LICENSE_SOURCE:** Public project repositories.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `UNKNOWN`.
- **PROJECT_INTEGRATION_DECISION:** `UNKNOWN__NOT_INSPECTED` (Explicitly marked as not yet inspected or reverse-engineered; zero claims asserted).
- **WHAT_WAS_INSPECTED:** None. No code, binaries, or documentation from FreeCAD, LibreCAD, LibreDWG, or QCAD have been inspected or decompiled in this research program.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:** None established.
- **FAILURE_MODES_AND_LIMITS:**
  - LibreDWG carries a strict copyleft GPL v3+ license that creates integration barriers for proprietary commercial CAD platforms.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT assume capabilities or algorithms without explicit clean-room commissioning.
- **DURABLE_POINTERS:** `None`.

---

### REA-020: POLYLINE_BULGE_AND_ARC_RECONSTRUCTION
- **CAPABILITY:** Exact reconstruction of curved polyline segments as DXF/AutoCAD LWPOLYLINE vertex entities with mathematical bulge parameters ($b = \tan(\theta/4)$).
- **EXTERNAL_SOURCE:** Autodesk DXF Specification Group Code 42 & `ezdxf.math.bulge` / LibreCAD `RS_Math`.
- **SOURCE_TYPE:** `SPEC_PUBLIC` / `ALGORITHM_OPEN_SOURCE`.
- **EXACT_VERSION_COMMIT:** `dxf-r14-through-2027-spec` / `ezdxf-1.4.x`.
- **KNOWN_VERSION_FAMILY:** Standard AutoCAD LWPOLYLINE Specification.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (`ezdxf/math/bulge.py`) + `DOCUMENTATION_ONLY` (Autodesk DXF Reference) + `TESTS_INSPECTED` (`TRANSFER_ORACLE.md`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `dxf_builder_lib/builder.py` and `primitive_ir_lib/geometry_extraction.py`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `RESEARCH_PRIOR`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A current measured product boundary requires LWPOLYLINE bulge generation, conversion, verification, or persistence and current owners do not already satisfy it.
- **EVIDENCE_TIER:** `VERIFIED_ALGORITHM_AND_ORACLE`.
- **LICENSE:** MIT (ezdxf math) / Copyright Autodesk, Inc. (DXF Reference Documentation).
- **LICENSE_SOURCE:** Autodesk DXF Reference / ezdxf open repository.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES` (for clean-room math formulations; no copying of GPL or proprietary implementations).
- **PROJECT_INTEGRATION_DECISION:** `RETAIN_AS_RESEARCH_PRIOR` (Basic bulge math validated; do not implement in production until a measured product RED requires curved polyline representation).
- **WHAT_WAS_INSPECTED:** Mathematical relationship between 3-point circular arcs, center coordinates, angular traversal direction, and DXF bulge parameter.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - $b = \tan(\theta/4)$ where $\theta$ is the included central angle (Standard invariant).
  - $b > 0$ denotes Counter-Clockwise (CCW) traversal; $b < 0$ denotes Clockwise (CW) traversal (Standard invariant).
  - Singularity threshold $|b| < 10^{-7} \implies b = 0.0$ is an internal `PROJECT_HEURISTIC_UNVALIDATED_FOR_PRODUCTION` used in test fixtures, not an Autodesk normative contract.
- **FAILURE_MODES_AND_LIMITS:**
  - Collinear 3-point inputs produce zero cross-product determinant, yielding division by zero if unshielded. Protected by determinant guard $|\Delta| < 10^{-9}$.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT invent custom multi-segment chord approximation when a native bulge can represent the exact curve.
  - Do NOT build an external C++ native curve-fitting module.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-13/rea_ghidra_maximum_capability/tier4_cad_agent_precompute/`
  - `research/antigravity/2026-10-13/rea_ghidra_maximum_capability_correction/`
  - `dxf_builder_lib/builder.py`
  - `primitive_ir_lib/geometry_extraction.py`

---

### REA-021: DIMENSION_ARROWHEAD_WITNESS_ASSOCIATION
- **CAPABILITY:** Geometric discrimination of dimension lines versus witness/extension lines and robust association with dimension text, preventing false conflict misbinding and establishing arrowhead outward flip thresholds.
- **EXTERNAL_SOURCE:** ISO 129-1:2018 / ASME Y14.5-2018 / LibreCAD `RS_DimLinear` (GPLv2) / Autodesk DXF Linear Dimension Specifications (Group Codes 10, 11, 13, 14, 50).
- **SOURCE_TYPE:** `COPYRIGHTED_SPECIFICATION_OR_DOCUMENTATION_PRIOR` (ISO/ASME) / `OPEN_SOURCE_REPO_GPLV2` (LibreCAD) / `COPYRIGHTED_SPECIFICATION_OR_DOCUMENTATION_PRIOR` (Autodesk DXF Reference).
- **EXACT_VERSION_COMMIT:** `ISO 129-1:2018` / `ASME Y14.5-2018` / LibreCAD 2.2.x (`librecad/src/lib/engine/rs_dimlinear.cpp`).
- **KNOWN_VERSION_FAMILY:** Standard Drafting & CAD Dimension Systems.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (`rs_dimlinear.cpp` — behavioral algorithm only, no GPL expression copied) + `DOCUMENTATION_ONLY` (ISO/ASME/Autodesk DXF Reference — consulted for behavioral understanding only) + `SYNTHETIC_ORACLE_TESTS` (`TRANSFER_ORACLE.py` — standalone clean-room prototype, not wired to production owners).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/cross_validation.py` (nearest-line logic) and `dxf_builder_lib/builder.py` (DXF construction). Both require augmentation; see gap note below.
- **OWNER_MAPPING_STATUS:** `VALID_WITH_GAP` — Current `CrossValidation` schema stores `text_primitive_id`, `geometry_primitive_id`, `status`, `text_value`, `geometry_measured_length`, `delta_percent`, `match_threshold_percent`. It does NOT store feature points $P_1$/$P_2$ or dimension-line offset. Current `cross_validate()` performs no angular discrimination. These are production schema gaps to be filled after a measured product RED.
- **CURRENT_DISPOSITION:** `RESEARCH_PRIOR`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A current measured product boundary or customer holdout exhibits dimension text association failure on non-linear or curved dimensions and current owners do not already satisfy it.
- **EVIDENCE_TIER:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE` — `TRANSFER_ORACLE.py` is a standalone clean-room prototype with synthetic test inputs. It is NOT a call through current production `cross_validate()`, `find_nearest_line()`, or `builder.py`. Passing synthetic tests does NOT constitute a production transfer GREEN. Production transfer requires a `MEASURED_CURRENT_PRODUCT_RED` + integration into actual production owners.
- **LICENSE:** ISO/ASME: `COPYRIGHTED_SPECIFICATION_OR_DOCUMENTATION_PRIOR` (no code-reuse authority). LibreCAD: `GPLv2` (`DIRECT_CODE_REUSE = NO`; Cad Agent is not GPL-licensed). DXF Reference: `COPYRIGHTED_SPECIFICATION_OR_DOCUMENTATION_PRIOR`.
- **LICENSE_SOURCE:** ISO / ASME Standards / `https://github.com/LibreCAD/LibreCAD` / Autodesk DXF Reference.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `NO` for source expression copying. `YES_BOUNDED` for clean-room mathematical algorithm transfer (independently derivable linear algebra, not GPL source).
- **PROJECT_INTEGRATION_DECISION:** `RETAIN_AS_RESEARCH_PRIOR` — Clean-room discriminator algorithm and unit test oracle established; do not implement in production until a measured product RED requires witness line filtering.
- **WHAT_WAS_INSPECTED:** Relationship between dimension line orientation ($\theta_{\text{dim}}$), witness line orientation ($\theta_{\text{wit}}$), text orientation ($\theta_{\text{text}}$), arrowhead flip geometry ($L < 2 \cdot S_{\text{arrow}} + W_{\text{text}}$ — `IMPLEMENTATION_HEURISTIC` from LibreCAD), and DXF definition points.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Dimension line is collinear/parallel to dimension text angle modulo $180^\circ$ (`STANDARD_DEFINED_INVARIANT`, tolerance $\Delta\theta \le 10^\circ$ is `IMPLEMENTATION_HEURISTIC`).
  - Standard extension/witness lines are perpendicular to dimension text angle modulo $180^\circ$ ($|\Delta\theta - 90^\circ| \le 10^\circ$ is `IMPLEMENTATION_HEURISTIC`). Oblique extension lines also exist normatively and are not covered by this discriminator.
  - Arrowheads flip outward when feature span $L < 2 \cdot S_{\text{arrow}} + W_{\text{text}}$ (`IMPLEMENTATION_HEURISTIC` from LibreCAD; not a universal standard invariant).
  - Witness line misbinding trap (naive nearest line selection picking witness line) causes false positive 85% length conflict, avoided by angular pre-filtering.
- **FAILURE_MODES_AND_LIMITS:**
  - Does not cover radial/diametral dimensions (`DIMRADIAL`, `DIMDIAMETER`) or ordinate dimensions (`DIMORDINATE`), which require separate radial ray/datum origin association logic.
  - Does not handle oblique extension lines.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT copy LibreCAD C++ source code (GPLv2 barrier).
  - Do NOT create a new subsystem or daemon for dimension association; existing owner `primitive_ir_lib/cross_validation.py` is the correct home.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `research/antigravity/2026-10-14/dimension_arrowhead_witness_association/TRANSFER_ORACLE.py` (standalone synthetic oracle only; not wired to production).
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-14/dimension_arrowhead_witness_association/`
  - `primitive_ir_lib/cross_validation.py`
  - `dxf_builder_lib/builder.py`

---

### REA-022: IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION
- **CAPABILITY:** Bounded polygon simplification of dense raster boundary contour chains into concise piecewise linear profiles, eliminating 1-pixel staircase aliasing while strictly preventing feature deletion and arc collapse.
- **EXTERNAL_SOURCE:** OpenCV `cv2.approxPolyDP` / Urs Ramer (1972) & David Douglas & Thomas Peucker (1973) algorithm / Visvalingam & Whyatt (1993) algorithm.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (OpenCV Apache 2.0) / `ALGORITHM_PAPER`.
- **EXACT_VERSION_COMMIT:** OpenCV 4.x / 5.x (`cv2.approxPolyDP`).
- **KNOWN_VERSION_FAMILY:** Standard Computational Geometry & Computer Vision.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (`geometry_comparator.py::_contour_points`, `dimension_geometry.py::_contour_arrow_points`) + `SYNTHETIC_ORACLE_TESTS` (`TRANSFER_ORACLE.py`) + `BENCHMARK_OBSERVED` (`benchmark_results.json`).
- **REUSE_CLASS:** `DEPENDENCY_REUSE`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/geometry_comparator.py` (`_contour_points()`).
- **EXISTING_SPECIALIZED_RDP_REUSE:** `primitive_ir_lib/dimension_geometry.py::_contour_arrow_points` (SCOPE: small bounded arrowhead contours).
- **FUTURE_FULL_CONTOUR_CANDIDATE_OWNER:** `primitive_ir_lib/geometry_comparator.py::_contour_points` (CONDITION: only after measured product RED).
- **OWNER_MAPPING_STATUS:** `VALID` (Smallest appropriate owner in current main).
- **CURRENT_DISPOSITION:** `RESEARCH_PRIOR`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A measured production defect demonstrates contour alignment failure or benchmark discrepancy on complex non-manifold or self-intersecting drawing contours.
- **EVIDENCE_TIER:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`.
- **LICENSE:** Apache 2.0 (OpenCV).
- **LICENSE_SOURCE:** `https://github.com/opencv/opencv/blob/4.x/LICENSE`.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES` (OpenCV is already a core project dependency in `requirements/`).
- **PROJECT_INTEGRATION_DECISION:** `RETAIN_AS_RESEARCH_PRIOR` (Evaluated across 7 fixtures / 98 configs; do not alter production `geometry_comparator.py` absent an active measured product RED. PRODUCTION_TRANSFER_AUTHORIZED=NO).
- **WHAT_WAS_INSPECTED:** OpenCV `cv2.approxPolyDP` across absolute ($\epsilon \in [0.75, 6.0]\text{ px}$) and relative ($\epsilon \in [0.002, 0.08] \times P$) tolerances, Clean-Room Direct-Area Visvalingam-Whyatt Variant (direct area without monotonic ladder), and failure modes across 7 canonical engineering fixtures.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - `UNIVERSAL_EPSILON=NOT_PROVEN`. Numerical metrics are fixture-specific synthetic observations.
  - On tested straight/staircase polygons (Fixtures 1, 2, 6, 7), RDP with tested absolute $\epsilon \in [0.75, 1.5]\text{ px}$ achieves 97.3%–99.7% point count reduction ($H \le 1.34\text{ px}$, area error $< 0.01\%$, 100% corner survival). Arcs and holes achieve lower reduction (71.4%–95.3%) to maintain chord fidelity.
  - The evaluated Clean-Room Direct-Area VW Variant (without monotonic hierarchy) collapsed tested discrete raster loops to 3–4 points at tested thresholds $\tau \ge 1.0\text{ px}^2$. Canonical VW with monotonic ladder was not benchmarked.
  - On tested full-part shapes, tested relative settings ($k \ge 0.01$) where $\epsilon = k \cdot P$ exceeded feature depth erased tested keyway notches. Existing arrowhead reuse (`0.08 * P` on $P \approx 30\text{--}50\text{ px}$) is effective in its scope and not defective.
- **FAILURE_MODES_AND_LIMITS:**
  - `FULL_PART_RELATIVE_EPSILON_HAZARD`: Tested $k \cdot P$ settings on full-part contours erased small features when $\epsilon$ exceeded feature depth.
  - `ARC_POLYGONIZATION_ERROR`: Large $\epsilon \ge 6.0\text{ px}$ reduces smooth circles to coarse octagons ($8.89\%$ area error).
  - `HOLE_TOPOLOGY_COLLAPSE`: When $\epsilon \ge R_{\text{hole}}$, small pin holes collapse into 2-point line segments ($Area = 0$).
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT implement custom line simplification algorithms or third-party cartography packages when OpenCV's native C++ `approxPolyDP` is already present.
  - Do NOT create a new contour simplification subsystem or daemon.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `research/antigravity/2026-10-14/image_to_cad_contour_simplification/TRANSFER_ORACLE.py`.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-14/image_to_cad_contour_simplification/`
  - `primitive_ir_lib/geometry_comparator.py`
  - `primitive_ir_lib/dimension_geometry.py`

---

### REA-023: NATIVE_DIMENSION_PLACEMENT_COLLISION_AVOIDANCE
- **CAPABILITY:** Deterministic candidate-evaluation native dimension placement collision avoidance (evaluating dual-side and multi-lane candidates on tested fixtures while preserving prototype measurement truth).
- **EXTERNAL_SOURCE:** ASME Y14.5-2018 / ISO 129-1 / Christensen, Marks, Shieber (1995) Point Feature Label Placement (PFLP) discrete candidate model / AutoCAD baseline stepping behavioral contract / ezdxf LinearDimension API.
- **SOURCE_TYPE:** `SPECIFICATION_ONLY` (ASME/ISO) / `COMMERCIAL_BEHAVIORAL_PRIOR` (AutoCAD) / `ALGORITHM_PAPER` (PFLP) / `DEPENDENCY_API_INSPECTION` (ezdxf).
- **EXACT_VERSION_COMMIT:** `ezdxf==1.4.4` (`add_linear_dim` API), ASME Y14.5-2018 Section 4.3, ISO 129-1:2018.
- **KNOWN_VERSION_FAMILY:** Computational Geometry Label Placement & CAD Dimensioning Standards.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (`dxf_builder_lib/builder.py::_add_confirmed_dimensions`) + `DEPENDENCY_API_INSPECTED` (`ezdxf>=1.4.0 LinearDimension API`) + `SYNTHETIC_ORACLE_TESTS` (`TRANSFER_ORACLE.py`) + `BENCHMARK_OBSERVED` (`benchmark_results.json`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `dxf_builder_lib/builder.py` (`_add_confirmed_dimensions`).
- **EXISTING_PLACEMENT_BEHAVIOR:** Single-side fixed offset `max(length * 0.08, 5.0)` along normal `(-dy/length, dx/length)` with zero obstacle awareness (17 collisions across 7/10 benchmark fixtures).
- **FUTURE_CANDIDATE_OWNER:** `dxf_builder_lib/builder.py` (`_add_confirmed_dimensions`, condition: bounded transfer upon approved production RED).
- **OWNER_MAPPING_STATUS:** `VALID` (Smallest appropriate owner in current main; `written_geometry_by_primitive_id` already contains text primitives so caller interface change is NOT required).
- **CURRENT_DISPOSITION:** `RESEARCH_PRIOR`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** A measured production defect demonstrates dimension placement failure on complex multi-view orthogonal drawing layouts or non-linear dimension entities (radial, angular).
- **EVIDENCE_TIER:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`.
- **LICENSE:** ASME/ISO: Copyrighted Standard (Specification Prior, DIRECT_CODE_REUSE=NO) / AutoCAD: Proprietary Commercial (Behavioral Prior, DIRECT_CODE_REUSE=NO) / ezdxf: MIT License (Dependency Reuse, DIRECT_CODE_REUSE=YES) / PFLP: Academic Algorithmic Prior (No licensed code identified, Clean-Room Transfer only).
- **LICENSE_SOURCE:** ASME Y14.5-2018 Copyright Notice / Autodesk AutoCAD 2027 Documentation / `https://github.com/mozman/ezdxf/blob/master/LICENSE.md` / Jon Christensen, Joe Marks, Stuart M. Shieber (1995), ACM Transactions on Graphics (TOG), 14(3), pp. 203–232.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES` (ezdxf dependency reuse and clean-room algorithmic transfer of discrete scoring pattern; direct third-party code copying prohibited).
- **PROJECT_INTEGRATION_DECISION:** `RETAIN_AS_RESEARCH_PRIOR` (Evaluated across 10 synthetic fixtures / 20 scenes with orientation-aware text footprint and long-text validation; candidate policy avoided collisions across all 10 fixtures with 0.0 mm prototype measurement error, 0 collisions on 52 mm text holdout, and 100% full-field repeatability on tested fixtures; PRODUCTION_TRANSFER_AUTHORIZED=NO).
- **WHAT_WAS_INSPECTED:** `dxf_builder_lib/builder.py::_add_confirmed_dimensions`, `ezdxf.render.dim_linear.LinearDimension` API, ASME Y14.5-2018 spacing rules, AutoCAD `DIMDLI` system variable behavioral contract, and Christensen et al. (1995) discrete candidate evaluation pattern (PFLP algorithmic prior: discrete candidates, overlap objective, candidate prior preferences, heuristic search; Cad Agent heuristics: 2 sides $\times$ 3 lanes, witness geometry modeling, hard-first lexicographic key, penalty weights, lane spacing $\Delta d = \max(7.5, 2 \cdot H_{\text{text}})$ and base floor $\max(L \cdot 0.08, 6.0\text{ mm})$).
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - `PROTOTYPE_MEASUREMENT_ERROR = 0.000000 mm` (Prototype geometric identity: definition points $p_1, p_2$ are immutable in `compute_dimension_geometry`; offset and side selection only change witness line length, never measurement).
  - `PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION = NOT_VERIFIED_BY_THIS_ORACLE` (Native DXF DIMENSION entity rendering and AutoCAD binary database roundtrip were not evaluated by this oracle).
  - `DETERMINISTIC_REPEATABILITY = 100.0%` (Verified as `FULL_FIELD_EQUAL_WITHIN_1E-9_ON_TESTED_FIXTURES` across 2 repeated runs on all 10 synthetic fixtures and 3 runs on Fixture 4; bounded to tested synthetic fixtures under canonical spec sorting).
  - `EXTENSION_UNWANTED_CROSSINGS = 12 (BASELINE) VS 4 (CANDIDATE)` (Evaluated under unified unary count_unary_extension_crossings and pairwise dim/ext soft interaction semantics matching candidate scoring).
  - `PLACEMENT_DISPLACEMENT = NOT_MEASURED` (Displacement relative to unguided baseline is not recorded as an error metric).
  - `ORIENTED_TEXT_FOOTPRINT = PROVEN_ON_TESTED_FIXTURES` (Orientation-aware text rectangle aligned with dimension unit vector $\mathbf{u} = (\Delta x/L, \Delta y/L)$ and unit normal $\mathbf{n}$ resolves false collisions on long text, maintaining 6.25 mm clearance on 52 mm vertical dimension test and 0 collisions across all 10 fixtures under wide text holdouts; resolves C_AABB_ORIENTATION_ARTIFACT).
  - `UNIVERSAL_SPACING_CONSTANT = NOT_PROVEN` (Offset step $\Delta d = \max(7.5, 2 \cdot H_{\text{text}})$ and candidate base floor $\max(L \cdot 0.08, 6.0\text{ mm})$ vs baseline $5.0\text{ mm}$ are empirical research heuristics, not universal physical constants or AutoCAD defaults).
  - `COLLISION_AVOIDANCE_OUTCOME = TESTED_FIXTURE_BOUNDED` (On 10 synthetic fixtures, baseline policy caused 17 collisions across 7 failed scenes. Candidate discrete policy achieved 0 collisions across all 10 fixtures. Collision freedom is not guaranteed under severe geometry saturation or tight pockets where all candidates are blocked).
- **FAILURE_MODES_AND_LIMITS:**
  - `TIGHT_POCKET_SATURATION`: In deeply recessed geometry where both normal directions and all offset lanes intersect obstacles, discrete policy exhausts candidates and selects least-bad option with non-zero penalty.
  - `DRAWING_BORDER_CLIPPING`: High offset lanes can escape the sheet border if the margin is smaller than candidate distance.
  - `NATIVE_FONT_METRIC_UNCERTAINTY`: Live AutoCAD text extent depends on font kerning and DIMSTYLE variables (`DIMTXT`, `DIMSCALE`, `DIMGAP`) requiring native AutoCAD integration testing.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT build an unconstrained global NP-hard optimization engine, spring embedder, or genetic layout algorithm when a discrete 6-candidate evaluation avoids collisions deterministically on tested fixtures.
  - Do NOT modify underlying geometry endpoints ($p_1, p_2$) or scale factors to make dimensions "fit".
  - Do NOT add heavy third-party layout dependencies (e.g. Graphviz, Z3, or Shapely) for dimension placement.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `research/antigravity/2026-10-14/native_dimension_placement_collision_avoidance/TRANSFER_ORACLE.py`.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-14/native_dimension_placement_collision_avoidance/`
  - `dxf_builder_lib/builder.py`

---

# QUALITY AUDIT SUMMARY TABLE

| REA_ID | ENUM_VALID | OWNER_EXISTS | GITHUB_EVIDENCE_COMPLETE | PROVENANCE_CLEAR | DISPOSITION_FAIL_CLOSED | LOCAL_ONLY_GAP | ANTI_REPEAT_SAFE |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `REA-001` | **YES** | **YES** (`primitive_ir_lib.geometry_extraction`) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`, `TESTS_INSPECTED`) | **YES** (`READY_TO_TRANSFER`) | **NO** | **YES** |
| `REA-002` | **YES** | **YES** (`primitive_ir_lib.geometry_extraction`) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`, `PAPER_ONLY`) | **YES** (`READY_TO_TRANSFER`) | **NO** | **YES** |
| `REA-003` | **YES** | **YES** (`primitive_ir_lib.text_extraction`) | **YES** | **YES** (`TESTS_INSPECTED`, `RUNTIME_OBSERVED`) | **YES** (`READY_TO_TRANSFER`) | **NO** | **YES** |
| `REA-004` | **YES** | **YES** (`primitive_ir_lib.geometry_extraction`) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`, `PAPER_ONLY`) | **YES** (`RESEARCH_PRIOR`) | **NO** | **YES** |
| `REA-005` | **YES** | **YES** (*None*) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`, `PAPER_ONLY`) | **YES** (`REJECTED`) | **NO** | **YES** |
| `REA-006` | **YES** | **YES** (`cad_agent.source_fusion_proposal`) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`) | **YES** (`ALREADY_IMPLEMENTED`) | **NO** | **YES** |
| `REA-007` | **YES** | **NO** (`CURRENT_CAD_AGENT_OWNER=UNKNOWN`) | **YES** | **YES** (`DOCUMENTATION_ONLY`, `COMMERCIAL_BEHAVIORAL_PRIOR`) | **YES** (`RESEARCH_PRIOR`) | **YES** | **YES** |
| `REA-008` | **YES** | **YES** (`cad_agent.mechanical_skills`) | **YES** | **YES** (`BINARY_INSPECTED`, `DOCUMENTATION_ONLY`) | **YES** (`RESEARCH_PRIOR`) | **YES** | **YES** |
| `REA-009` | **YES** | **YES** (`autocad_plugin.CadAgent.AutoCAD2027`) | **YES** | **YES** (`BINARY_INSPECTED`, `RUNTIME_OBSERVED`) | **YES** (`ALREADY_IMPLEMENTED`) | **NO** | **YES** |
| `REA-010` | **YES** | **YES** (`autocad_plugin.Commands.CommandContext`) | **YES** | **YES** (`BINARY_INSPECTED`, `RUNTIME_OBSERVED`) | **YES** (`TRANSFER_EXPERIMENT_REQUIRED`) | **YES** | **YES** |
| `REA-011` | **YES** | **YES** (`dxf_builder_lib.builder`) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`, `TESTS_INSPECTED`) | **YES** (`ALREADY_IMPLEMENTED`) | **NO** | **YES** |
| `REA-012` | **YES** | **YES** (`primitive_ir_lib.geometry_alignment`) | **YES** | **YES** (`PAPER_ONLY`, `COMMERCIAL_BEHAVIORAL_PRIOR`) | **YES** (`READY_TO_TRANSFER`) | **NO** | **YES** |
| `REA-013` | **YES** | **YES** (`cad_agent.source_fusion_proposal`) | **YES** | **YES** (`COMMERCIAL_BEHAVIORAL_PRIOR`, `TESTS_INSPECTED`) | **YES** (`ALREADY_IMPLEMENTED`) | **NO** | **YES** |
| `REA-014` | **YES** | **YES** (`cad_agent.source_fusion`) | **YES** | **YES** (`COMMERCIAL_BEHAVIORAL_PRIOR`, `DOCUMENTATION_ONLY`) | **YES** (`RESEARCH_PRIOR`) | **YES** | **YES** |
| `REA-015` | **YES** | **YES** (`primitive_ir_lib.geometry_extraction`) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`, `TESTS_INSPECTED`) | **YES** (`READY_TO_TRANSFER`) | **NO** | **YES** |
| `REA-016` | **YES** | **YES** (`primitive_ir_lib.line_merging`) | **YES** | **YES** (`TESTS_INSPECTED`) | **YES** (`READY_TO_TRANSFER`) | **NO** | **YES** |
| `REA-017` | **YES** | **YES** (`primitive_ir_lib.calibration`) | **YES** | **YES** (`DOCUMENTATION_ONLY`, `TESTS_INSPECTED`) | **YES** (`READY_TO_TRANSFER`) | **NO** | **YES** |
| `REA-018` | **YES** | **YES** (`semantic_ir_lib.constraint_solving`) | **YES** | **YES** (`BINARY_INSPECTED`, `TESTS_INSPECTED`) | **YES** (`ALREADY_IMPLEMENTED`) | **NO** | **YES** |
| `REA-019` | **YES** | **YES** (*None*) | **YES** | **YES** (`UNKNOWN`) | **YES** (`UNKNOWN`) | **YES** | **YES** |
| `REA-020` | **YES** | **YES** (`dxf_builder_lib.builder`) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`, `TESTS_INSPECTED`) | **YES** (`RESEARCH_PRIOR`) | **NO** | **YES** |
| `REA-021` | **YES** | **YES** (`primitive_ir_lib.cross_validation`) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`, `TESTS_INSPECTED`) | **YES** (`RESEARCH_PRIOR`) | **NO** | **YES** |
| `REA-022` | **YES** | **YES** (`primitive_ir_lib.geometry_comparator`) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`, `TESTS_INSPECTED`) | **YES** (`RESEARCH_PRIOR`) | **NO** | **YES** |
| `REA-023` | **YES** | **YES** (`dxf_builder_lib.builder`) | **YES** | **YES** (`SOURCE_CODE_INSPECTED`, `DEPENDENCY_API_INSPECTED`) | **YES** (`RESEARCH_PRIOR`) | **NO** | **YES** |


---

## LOCAL_ONLY_EVIDENCE_GAPS

For each entry where underlying raw evidence was generated locally or relies on workstation state:

### GAP-001: REA-007 (BLOCKIFY Live Binary Execution)
- **REA_ID:** `REA-007`
- **MISSING_ARTIFACT:** Local BricsCAD V24 binary installation and runtime execution traces on live DWG drawings.
- **WHY_NOT_PERSISTED:** BricsCAD is not installed on the local workstation host (`NOT_INSTALLED_ON_LOCAL_HOST`).
- **WHAT_KNOWLEDGE_REMAINS_DURABLE:** Official documentation, command UX contract, system variables (`BLOCKIFYTOLERANCE`), invariant signature hashing design in `research/antigravity/2026-10-11/prior_investigations/rea_blockify_behavioral_contract_specification.md`.
- **WOULD_FUTURE_RESEARCH_NEED_TO_REPEAT:** `PARTIAL` (Only if runtime execution traces or exact numerical distance thresholds must be reverse engineered from proprietary binaries).

### GAP-002: REA-008 (CadMind Encrypted Implementation)
- **REA_ID:** `REA-008`
- **MISSING_ARTIFACT:** Original decrypted AutoLISP/VLX implementation binaries (`CadMindTools.enc`).
- **WHY_NOT_PERSISTED:** Protected by ECDH licensing mechanism; project clean-room policy strictly prohibits cryptographic bypass or implementation copying.
- **WHAT_KNOWLEDGE_REMAINS_DURABLE:** Complete 90 toolpackage schemas, JSON property tables, MCP pipe dispatch architecture, and clean-room specifications in `research/antigravity/2026-10-11/prior_investigations/cadmind_toolpackage_reconstruction.md`.
- **WOULD_FUTURE_RESEARCH_NEED_TO_REPEAT:** `NO` (Clean-room specification is sufficient; broad query layer is intentionally not adopted per Issue #291).

### GAP-003: REA-010 (DIMASSOC Causal Mutation Verification)
- **REA_ID:** `REA-010`
- **MISSING_ARTIFACT:** Native in-place mutation observation across transaction commit, save, and cold reopen in a live AutoCAD session.
- **WHY_NOT_PERSISTED:** Causal mutation experiment requires exclusive mutable CAD lane and is explicitly assigned to Luna; current research session authorized read-only database inspection only.
- **WHAT_KNOWLEDGE_REMAINS_DURABLE:** Synthetic DWG generator scripts, SHA256 hashes (`47c8d9...`, `836abd...`), C# `ReactorInspector` source, 4 adversarial controls PASS log in `research/antigravity/2026-10-11/dimassoc_reactor_validation/`, and complete Luna handoff specification (`luna_handoff_causal_mutation_probe.md`).
- **WOULD_FUTURE_RESEARCH_NEED_TO_REPEAT:** `NO` (Read-only relationship proven; future workstation action is execution of Luna causal probe).

### GAP-004: REA-014 (DraftSight Draw Compare Internal Diff Kernel)
- **REA_ID:** `REA-014`
- **MISSING_ARTIFACT:** DraftSight Draw Compare internal diff kernel binary/source.
- **WHY_NOT_PERSISTED:** Proprietary commercial software; vendor documentation only.
- **WHAT_KNOWLEDGE_REMAINS_DURABLE:** User-facing comparison contract and clean-room delta bounding box mask architecture in `research/antigravity/2026-10-11/prior_investigations/wave_a_cad_capability_mining_report.md`.
- **WOULD_FUTURE_RESEARCH_NEED_TO_REPEAT:** `PARTIAL` (Clean-room implementation is sufficient; no need to reverse engineer DraftSight internals).

### GAP-005: REA-019 (Open Source CAD Engines Source Trees)
- **REA_ID:** `REA-019`
- **MISSING_ARTIFACT:** FreeCAD, LibreCAD, LibreDWG, QCAD source trees, binaries, and AST parsers.
- **WHY_NOT_PERSISTED:** Never inspected or decompiled in this research program.
- **WHAT_KNOWLEDGE_REMAINS_DURABLE:** Known licensing postures (e.g. LibreDWG GPL v3+ copyleft barrier).
- **WOULD_FUTURE_RESEARCH_NEED_TO_REPEAT:** `YES` (If any of these engines are formally selected for capability mining).
