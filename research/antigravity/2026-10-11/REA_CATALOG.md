# Master REA Knowledge Base & Anti-Repeat Index

- **Document ID:** `REA_CATALOG_V1`
- **Role:** `ANTIGRAVITY_REA_KNOWLEDGE_CURATOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-13
- **Basis Commit:** `86318afc722939d88f355437e55405d012cba356` (`origin/main`)
- **Research Branch:** `research/antigravity-2026-10-11` (`41f34c7963010e5abc425aa4cbb31b13f25d2eb3`)
- **Production Status:** `RESEARCH_DOCUMENTATION_ONLY = YES`
- **Production Impact:** `PRODUCTION_CODE_CHANGE = NO`, `PR503_CHANGE = NO`, `AUTOCAD_MUTATION = NO`

---

## Purpose & Recovery Doctrine

> [!IMPORTANT]
> **ANTI-REPEAT MANDATE:** A future agent, researcher, or architect must consult this catalog to answer:
> 1. *"Have we already researched this capability or external source?"*
> 2. *"What exact behavioral invariants, failure modes, or license barriers were proven?"*
> 3. *"Where is the durable code, specification, or test oracle located?"*
>
> **DO NOT** re-run reverse engineering, re-decompile assemblies, or re-benchmark solved problems when a durable entry exists below.

---

# QUICK REA LOOKUP

| REA_ID | Capability | External Source | Reuse Class | Current Cad Agent Owner | Disposition | Research Again? | Evidence Tier |
| :---: | :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| **`REA-001`** | `THICK_LINE_NORMALIZATION` | `skimage/morphology/_skeletonize.py` (Zhang-Suen) | `ALGORITHM_TRANSFER` | `primitive_ir_lib.geometry_extraction` | `TRANSFERRED_READY_FOR_CODEX` | **NO** | `DURABLE_GITHUB` / `OBSERVED_TEST` |
| **`REA-002`** | `ARC_FITTING` | `AlliedToasters/circle-fit` (Taubin 1991 SVD) | `ALGORITHM_TRANSFER` | `primitive_ir_lib.geometry_extraction` | `TRANSFERRED_READY_FOR_CODEX` | **NO** | `DURABLE_GITHUB` / `OBSERVED_TEST` |
| **`REA-003`** | `ROTATED_TEXT_OCR` | Tesseract 5.x & Strategy D Aspect Pruning | `ARCHITECTURAL_PATTERN` | `primitive_ir_lib.text_extraction` | `TRANSFERRED_READY_FOR_CODEX` | **NO** | `DURABLE_GITHUB` / `OBSERVED_TEST` |
| **`REA-004`** | `SUBPIXEL_LINE_SEGMENT_DETECTION`| OpenCV `LineSegmentDetectorImpl` (LSD) | `DIRECT_IMPORT` | `primitive_ir_lib.geometry_extraction` | `CANDIDATE_FUTURE` | **NO** | `DURABLE_GITHUB` |
| **`REA-005`** | `POLYGONAL_SPLINE_VECTORIZATION` | `tatarize/potrace` (Peter Selinger 2003) | `REJECTED` | *None* | `REJECTED_UNSAFE` | **NO** | `DURABLE_GITHUB` |
| **`REA-006`** | `LINE_GRAPH_JUNCTION_SNAPPING` | `Vahe1994/Deep-Vectorization` (`snap_junctions`)| `ARCHITECTURAL_PATTERN` | `cad_agent.source_fusion_proposal` | `ADOPTED` | **NO** | `DURABLE_GITHUB` |
| **`REA-007`** | `REPEATED_COMPONENT_DISCOVERY` | BricsCAD `BLOCKIFY` / AutoCAD Smart Blocks | `BEHAVIORAL_SPEC_CLEAN_ROOM` | `semantic_ir_lib.blocks` / `autocad_plugin` | `TRANSFERRED_READY_FOR_CODEX` | **NO** | `DURABLE_GITHUB` |
| **`REA-008`** | `CADMIND_TOOLPACKAGE_ARCHITECTURE`| CadMind v1.0.1 (`tools.*.json`, `IPluginPipeServer`) | `BEHAVIORAL_SPEC_CLEAN_ROOM` | `cad_agent.mechanical_skills` | `GATED_ON_EVIDENCE` | **NO** | `DURABLE_GITHUB` / `OBSERVED_RUNTIME` |
| **`REA-009`** | `AUTOCAD_MANAGED_ASSEMBLIES` | AutoCAD 2027 (`acdbmgd.dll`, `acdb26.dll`) | `DIRECT_IMPORT` / `CLEAN_SPEC` | `autocad_plugin.CadAgent.AutoCAD2027` | `ADOPTED` | **NO** | `OBSERVED_MANAGED_METADATA` |
| **`REA-010`** | `DIMASSOC_NATIVE_RELATIONSHIP` | AutoCAD 2027 Managed Object Graph (`DIMASSOC=2`) | `ARCHITECTURAL_PATTERN` | `autocad_plugin.Commands.CommandContext` | `TRANSFERRED_READY_FOR_CODEX` | **GATED_BY_LUNA_PROBE** | `OBSERVED_RUNTIME` / `OBSERVED_TEST` |
| **`REA-011`** | `DXF_DOCUMENT_CONSTRUCTION` | `ezdxf` (v1.4.x) | `DIRECT_IMPORT` | `dxf_builder_lib.builder` | `ADOPTED` | **NO** | `DURABLE_GITHUB` |
| **`REA-012`** | `WCS_SPATIAL_REGISTRATION` | Scan2CAD 2-Point / Umeyama Similarity $[R\|T]$ | `ALGORITHM_TRANSFER` | `primitive_ir_lib.alignment` | `TRANSFERRED_READY_FOR_CODEX` | **NO** | `DURABLE_GITHUB` / `OBSERVED_TEST` |
| **`REA-013`** | `NEGATIVE_RASTER_REMOVAL_EVIDENCE`| Scan2CAD / Forge AI Difference Model | `NEGATIVE_CONTROL` | `cad_agent.source_fusion_proposal` | `ADOPTED` | **NO** | `DURABLE_GITHUB` / `OBSERVED_TEST` |
| **`REA-014`** | `BASE_CAD_DELTA_MASKING` | DraftSight `Draw Compare` / Forge AI Diff Engine | `ARCHITECTURAL_PATTERN` | `cad_agent.source_fusion` | `TRANSFERRED_READY_FOR_CODEX` | **NO** | `DURABLE_GITHUB` |
| **`REA-015`** | `CIRCLE_FALSE_POSITIVE_VALIDATION`| HoughCircles Accumulator & Perimeter Support | `ALGORITHM_TRANSFER` | `primitive_ir_lib.geometry_extraction` | `TRANSFERRED_READY_FOR_CODEX` | **NO** | `DURABLE_GITHUB` / `OBSERVED_TEST` |
| **`REA-016`** | `COLLINEAR_LINE_MERGING` | PCA Line Fitting & Parallel Guard | `ALGORITHM_TRANSFER` | `primitive_ir_lib.line_merging` | `TRANSFERRED_READY_FOR_CODEX` | **NO** | `DURABLE_GITHUB` / `OBSERVED_TEST` |
| **`REA-017`** | `CALIBRATION_CONSENSUS` | `AGENTS.md` Consensus Gate ($\ge 2$ wits, $\le 3\%$) | `ALGORITHM_TRANSFER` | `primitive_ir_lib.calibration` | `TRANSFERRED_READY_FOR_CODEX` | **NO** | `DURABLE_GITHUB` / `OBSERVED_TEST` |
| **`REA-018`** | `PARAMETRIC_CONSTRAINT_SOLVING` | `solvespace/solvespace` (`python-solvespace==3.0.8`)| `DIRECT_IMPORT` (Pinned) | `semantic_ir_lib.constraint_solving` | `ADOPTED` (Exclusive) | **NO** | `DURABLE_GITHUB` / `OBSERVED_TEST` |
| **`REA-019`** | `OPEN_SOURCE_CAD_ENGINES` | FreeCAD, LibreCAD, LibreDWG, QCAD | `UNKNOWN` | *None* | `UNKNOWN` | **ONLY_IF_COMMISSIONED** | `UNKNOWN` |

---

# DETAILED REA ENTRIES

---

### REA-001: THICK_LINE_NORMALIZATION
- **CAPABILITY:** Normalization of thick raster engineering line strokes (width $\ge 5\text{ px}$) that produce duplicate parallel Hough edge lines into a single, unbiased CAD centerline.
- **EXTERNAL_SOURCE:** `scikit-image/scikit-image` (`skimage/morphology/_skeletonize.py`, `_skeletonize_zhang_suen`) based on Zhang & Suen (1984) parallel thinning algorithm.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (BSD 3-Clause).
- **EXACT_VERSION_OR_COMMIT:** `scikit-image v0.24+`.
- **REUSE_CLASS:** `ALGORITHM_TRANSFER` (Clean-room 25-line NumPy 2-pass parallel medial axis thinning).
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/geometry_extraction.py` (`_preprocess()`, `extract_lines()`).
- **DISPOSITION:** `TRANSFERRED_READY_FOR_CODEX`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **WHAT_WAS_INSPECTED:** Canny edge detection vs. Zhang-Suen morphological thinning on synthetic strokes of widths 1, 3, 5, 10, 15 px.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Canny generates two parallel lines separated by the stroke width when stroke $\ge 5\text{ px}$ (RED A reproduced).
  - Zhang-Suen parallel 2-pass thinning reduces strokes of any width to exactly 1-pixel medial skeletons.
  - HoughLinesP applied after thinning yields exactly 1 engineering centerline with $0.0\text{ px}$ vertical bias across widths 1–10 px.
- **FAILURE_MODES_AND_LIMITS:**
  - `GLOBAL_THINNING_SAFE = NO`: Thinning cannot be applied globally to whole drawing rasters because it erodes solid arrowheads, destroys small OCR character loops (`e`, `o`, `8`), and thins concentric circles into irregular rings.
  - Must be gated locally on candidate line regions.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT import full `scikit-image` dependency into production runtime.
  - Do NOT invent custom morphological heuristics when standard Zhang-Suen lookup tables are mathematically complete.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `test_thick_line_double_edge_red.py` (Asserts `len(merged) == 1` and `abs(merged[0].p1_px[1] - 250.0) <= 0.5`).
- **DURABLE_POINTERS:** [`research/antigravity/2026-10-11/thick_line/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/thick_line/), [`raster_empirical_red_and_oss_mining.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/raster_empirical_red_and_oss_mining.md).

---

### REA-002: ARC_FITTING
- **CAPABILITY:** Direct algebraic extraction and fitting of circular arcs and full circles from partial, noisy pixel contours.
- **EXTERNAL_SOURCE:** `AlliedToasters/circle-fit` (`circle_fit/circle_fit.py`, `taubinSVD`) implementing Gabriel Taubin (1991), "Estimation of Planar Curves, Surfaces, and Nonplanar Space Curves Defined by Implicit Equations with Applications to Computer Vision".
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (MIT License) / `ALGORITHM_PAPER`.
- **EXACT_VERSION_OR_COMMIT:** `circle-fit v0.3.3`.
- **REUSE_CLASS:** `ALGORITHM_TRANSFER` (Clean-room NumPy algebraic distance minimization via SVD).
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/geometry_extraction.py` (`extract_arcs()`, `extract_raw_geometry()`).
- **DISPOSITION:** `TRANSFERRED_READY_FOR_CODEX`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **WHAT_WAS_INSPECTED:** Comparative benchmarks across Kåsa, Taubin, Pratt, OpenCV `minEnclosingCircle`, and RANSAC on circular sweeps from $30^\circ$ to $360^\circ$.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Taubin SVD minimizes $\sum (r_i^2 - R^2)^2 / \sum r_i^2$, eliminating the severe radial shrinkage bias inherent in Kåsa's algorithm on partial arcs.
  - Achieves $0.744\text{ px}$ mean center error and $3.13\%$ radius error on partial arcs ($90^\circ, 180^\circ, 270^\circ$).
  - Circularity metric $\sigma_R / R \le 0.05$ reliably separates circular arcs from arbitrary polylines.
  - Exact angular mapping: Pixel (CW, +y down) to CAD WCS (CCW, +y up) endpoint inversion contract ($\theta_{cad, start} = (-\theta_{px, end}) \pmod{360^\circ}$).
- **FAILURE_MODES_AND_LIMITS:**
  - Collinear degenerate points cause radius $R \to \infty$ ($R > 10^5\text{ px}$); must be trapped and classified as `LINE` rather than raising divide-by-zero.
  - Thick strokes produce dual inner/outer concentric edge arcs; requires distance-transform weighting with round-cap overhang compensation.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT use Kåsa algebraic fit (severely underestimates radius on sweeps $< 180^\circ$).
  - Do NOT invent iterative gradient descent when closed-form SVD Taubin is deterministic and runs in $< 550\ \mu\text{s}$.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `test_causal_red_taubin_arc.py` (Asserts non-zero `ArcGeometry` emission and radius error $\le 3.5\%$).
- **DURABLE_POINTERS:** [`research/antigravity/2026-10-11/arc_extraction/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/arc_extraction/), [`raster_arc_recognition_specification.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/raster_arc_recognition_specification.md).

---

### REA-003: ROTATED_TEXT_OCR
- **CAPABILITY:** Robust optical character recognition of text and dimension labels oriented at cardinal rotations ($0^\circ, 90^\circ, 180^\circ, 270^\circ$).
- **EXTERNAL_SOURCE:** Tesseract 5.x (`tesseract-ocr/tesseract`) + Strategy D Aspect-Ratio Guided Pruning.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (Apache 2.0) + `ARCHITECTURAL_PATTERN`.
- **EXACT_VERSION_OR_COMMIT:** `pytesseract v0.3.10` / Tesseract 5.3+.
- **REUSE_CLASS:** `ARCHITECTURAL_PATTERN` (Geometric aspect-ratio rotation heuristic + composite confidence scoring).
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/text_extraction.py` (`extract_text_tesseract()`).
- **DISPOSITION:** `TRANSFERRED_READY_FOR_CODEX`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **WHAT_WAS_INSPECTED:** Production `extract_text_tesseract()` vs. 4 rotation handling strategies across font sizes 12–48px at $0^\circ, 90^\circ, 180^\circ, 270^\circ$.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Current production OCR fails 100% on $90^\circ, 180^\circ, 270^\circ$ text (returns empty or hallucinated punctuation fragments).
  - Tesseract OSD (`--psm 0`) fails 100% on dimension/short crops ("Too few characters").
  - Strategy D (geometry-assisted aspect ratio pruning: if height > width, rotate ROI by $90^\circ$ before OCR) achieves $100.0\%$ exact match and $100.0\%$ rotation classification while halving latency ($370.1\text{ ms}$ vs $719.5\text{ ms}$).
  - Numeric dimension safety: 40/40 exact dimension values recovered, zero numeric substitutions.
- **FAILURE_MODES_AND_LIMITS:**
  - Naive "longest non-empty string" heuristic fails 100% on short labels, selecting hallucinated garbage over truth.
  - Highly non-cardinal rotated text (e.g. $45^\circ$) requires explicit carrier line alignment.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT run 4-pass brute-force OCR ($0^\circ, 90^\circ, 180^\circ, 270^\circ$) indiscriminately.
  - Do NOT rely on Tesseract OSD for engineering drawing crops.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `test_causal_red_text_extraction.py` (Asserts exact string match for vertical `"WHEELBASE 4200"` at $90^\circ$ and $270^\circ$).
- **DURABLE_POINTERS:** [`research/antigravity/2026-10-11/text_extraction/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/text_extraction/), [`rotated_engineering_text_specification.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/rotated_engineering_text_specification.md).

---

### REA-004: SUBPIXEL_LINE_SEGMENT_DETECTION (LSD)
- **CAPABILITY:** Parameter-free subpixel linear contour extraction with false alarm control based on the Helmholtz principle.
- **EXTERNAL_SOURCE:** OpenCV `modules/imgproc/src/lsd.cpp` (`LineSegmentDetectorImpl::detect()`) implementing Rafael Grompone von Gioi, Jeremie Jakubowicz, Jean-Michel Morel, Gregory Randall (2010), "LSD: A Fast Line Segment Detector with a False Detection Control", IEEE TPAMI.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (Apache 2.0).
- **EXACT_VERSION_OR_COMMIT:** OpenCV 4.8.0+.
- **REUSE_CLASS:** `DIRECT_IMPORT` (Available via built-in `cv2.createLineSegmentDetector()`).
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/geometry_extraction.py`.
- **DISPOSITION:** `CANDIDATE_FUTURE`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **WHAT_WAS_INSPECTED:** Evaluation of OpenCV LSD against HoughLinesP across 10 engineering drawing criteria.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Produces subpixel floating-point endpoints $[x_1, y_1, x_2, y_2]$.
  - Parameter-free with Helmholtz Number of False Alarms (NFA) thresholding.
  - Successfully preserves short segments down to $5\text{ px}$ without parameter tuning.
- **FAILURE_MODES_AND_LIMITS:**
  - Like HoughLinesP, LSD extracts outer boundary edges rather than centerlines on thick strokes ($\ge 5\text{ px}$) unless preceded by medial axis thinning.
  - Slightly higher runtime ($\approx 15\text{ ms}$ vs $\approx 5\text{ ms}$).
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT write custom C++ line detectors when OpenCV provides an optimized native implementation.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** Comparison matrix in `raster_empirical_red_and_oss_mining.md`.
- **DURABLE_POINTERS:** [`raster_empirical_red_and_oss_mining.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/raster_empirical_red_and_oss_mining.md).

---

### REA-005: POLYGONAL_SPLINE_VECTORIZATION (Potrace)
- **CAPABILITY:** Vectorization of 1-bit bitmaps into smooth polygonal paths and cubic Bezier splines.
- **EXTERNAL_SOURCE:** `tatarize/potrace` implementing Peter Selinger (2003), "Potrace: a polygon-based tracing algorithm".
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (GPL v2+).
- **EXACT_VERSION_OR_COMMIT:** `potrace 1.16`.
- **REUSE_CLASS:** `REJECTED` (GPL v2+ license barrier; outputs cubic Bezier splines that destroy CAD arc/line constraints).
- **CURRENT_CAD_AGENT_OWNER:** *None*.
- **DISPOSITION:** `REJECTED_UNSAFE`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **WHAT_WAS_INSPECTED:** Potrace curve fitting and polygonal path reduction.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Converts pixel clusters into continuous cubic Bezier curves (`process_path()`).
  - Excellent for organic graphical artwork, logos, and fonts.
- **FAILURE_MODES_AND_LIMITS:**
  - CAD Invariant Violation: Engineering drawings require explicit `LINE`, `ARC`, and `CIRCLE` primitives, not approximate spline segments.
  - License Contamination: Potrace is strictly GPL v2+; incorporating it into Cad Agent would compromise proprietary licensing.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - **DO NOT** import, link, or wrap Potrace for CAD vectorization.
- **DURABLE_POINTERS:** [`raster_empirical_red_and_oss_mining.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/raster_empirical_red_and_oss_mining.md).

---

### REA-006: LINE_GRAPH_JUNCTION_SNAPPING
- **CAPABILITY:** Snapping disjoint raw line segments into a closed planar topological graph using spatial index nearest-neighbor queries.
- **EXTERNAL_SOURCE:** `Vahe1994/Deep-Vectorization-for-Floorplans` (`src/line_extraction/lsd_extractor.py`, `snap_junctions()`).
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (MIT License).
- **EXACT_VERSION_OR_COMMIT:** GitHub repository commit `d9b4f2c`.
- **REUSE_CLASS:** `ARCHITECTURAL_PATTERN` (R-tree spatial boundary indexing + Disjoint Set Union clustering).
- **CURRENT_CAD_AGENT_OWNER:** `cad_agent/source_fusion_proposal.py` (`compile_external_visual_object_proposal`).
- **DISPOSITION:** `ADOPTED`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **WHAT_WAS_INSPECTED:** Multi-scale line segment snapping and junction formation logic.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Snaps open line endpoints within $\Delta d \le 5.0\text{ mm}$ and angular tolerance $\le 10^\circ$ into shared topological vertices.
  - Forms closed planar loops matching Cad Agent's `BOUNDARY_CHAIN` requirement.
- **FAILURE_MODES_AND_LIMITS:**
  - Blind snapping without feature angle checks causes accidental T-junction stem collapse.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT invent quadratic $O(N^2)$ pairwise proximity searches when spatial bounding box indexes provide $O(N \log N)$ grouping.
- **DURABLE_POINTERS:** [`raster_empirical_red_and_oss_mining.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/raster_empirical_red_and_oss_mining.md).

---

### REA-007: REPEATED_COMPONENT_DISCOVERY (BLOCKIFY)
- **CAPABILITY:** Detecting identical repeating 2D linework clusters across ModelSpace and consolidating them into a single `BlockTableRecord` referenced by multiple `INSERT` entities.
- **EXTERNAL_SOURCE:** BricsCAD `BLOCKIFY` / `PARAMETRICBLOCKIFY` & AutoCAD Smart Blocks (`BDETECT` / `BSEARCH`).
- **SOURCE_TYPE:** `COMMERCIAL_PRODUCT` (`PUBLIC_DOC_VERIFIED`).
- **EXACT_VERSION_OR_COMMIT:** BricsCAD V24 / AutoCAD 2024–2027.
- **REUSE_CLASS:** `BEHAVIORAL_SPEC_CLEAN_ROOM` (Invariant signature hashing: sorted segment lengths, vertex centroids, bounding-box aspect ratios).
- **CURRENT_CAD_AGENT_OWNER:** `semantic_ir_lib/blocks.py` / `autocad_plugin`.
- **DISPOSITION:** `TRANSFERRED_READY_FOR_CODEX`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **WHAT_WAS_INSPECTED:** Official documentation, command options (`match existing Blocks`, `Select source entities`, `Find Collections`), system variables (`BLOCKIFYMODE`, `BLOCKIFYTOLERANCE`).
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Grouping preserves relative translation, rotation, and reflection.
  - Scale variants are strictly rejected to prevent altering engineering dimensions.
  - Replaces $N$ loose clusters with $N$ `AcDbBlockReference` entities.
  - Insertion anchor placed deterministically at the geometric centroid of all cluster vertices.
  - Reuses existing drawing blocks via `match existing Blocks` without duplicating definitions.
- **FAILURE_MODES_AND_LIMITS:**
  - Touching or intersecting linework cannot be safely auto-partitioned without explicit user bounding.
  - Differing text strings inside identical linework cause rejection of equality.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT copy Bricsys proprietary C3D geometry kernel or Autodesk AI ML clustering.
  - Do NOT infer block equivalence solely from visual raster similarity.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** 12-point behavioral audit in `rea_blockify_behavioral_contract_specification.md`.
- **DURABLE_POINTERS:** [`rea_blockify_behavioral_contract_specification.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/rea_blockify_behavioral_contract_specification.md), [`wave_a_cad_capability_mining_report.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/wave_a_cad_capability_mining_report.md).

---

### REA-008: CADMIND_TOOLPACKAGE_ARCHITECTURE
- **CAPABILITY:** Catalog of 90 specialized drafting and auditing toolpackages (fasteners, shafts, bearings, GD&T, tables, layers) and MCP plugin architecture.
- **EXTERNAL_SOURCE:** CadMind v1.0.1 (`CadMind.Shared.dll`, `CadMind.Plugin.dll`, `tools.*.json`).
- **SOURCE_TYPE:** `COMMERCIAL_PRODUCT` / `BINARY_PE_MANAGED`.
- **EXACT_VERSION_OR_COMMIT:** CadMind v1.0.1.
- **REUSE_CLASS:** `BEHAVIORAL_SPEC_CLEAN_ROOM` (Clean-room specification of schemas and ISO/DIN data tables; zero copied proprietary implementation).
- **CURRENT_CAD_AGENT_OWNER:** `cad_agent/mechanical_skills.py`, `semantic_ir_lib`.
- **DISPOSITION:** `GATED_ON_EVIDENCE`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_RUNTIME`.
- **WHAT_WAS_INSPECTED:** .NET metadata, MCP pipe dispatch (`IPluginPipeServerMcp`), JSON tool schemas, public DIN/ISO fastener/bearing data tables.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - 90 tool descriptors across shared (24), mechanical (22), structural (25), electrical (19).
  - All tools generate true native AutoCAD entities (`LINE`, `ARC`, `LWPOLYLINE`, `HATCH`, `TABLE`, `TOLERANCE`, `MLEADER`).
  - Underlying LISP implementation (`CadMindTools.enc`) is protected via cryptographic licensing (ECDH/licensing mechanism).
- **FAILURE_MODES_AND_LIMITS:**
  - Broad CAD query / tool layers must not be built in Cad Agent without a demonstrated product need (Issue #291 & `docs/HANDOFF.md`).
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Zero proprietary implementation code copied.
  - Do NOT build 90 standalone toolpackages; implement capabilities into existing Cad Agent owners only when demanded by workflows.
- **DURABLE_POINTERS:** [`cadmind_toolpackage_reconstruction.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/cadmind_toolpackage_reconstruction.md), [`cadmind_technical_evidence_report.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/cadmind_technical_evidence_report.md), [`PROJECT_RESEARCH_INDEX.md`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/external-projects/PROJECT_RESEARCH_INDEX.md).

---

### REA-009: AUTOCAD_MANAGED_ASSEMBLIES
- **CAPABILITY:** Pure managed .NET database inspection, transaction management, and entity reading in AutoCAD 2027.
- **EXTERNAL_SOURCE:** Autodesk AutoCAD 2027 Managed Assemblies (`acdbmgd.dll`, `accoremgd.dll`, `acmgd.dll`, `acdb26.dll`).
- **SOURCE_TYPE:** `BINARY_PE_MANAGED` / `CLEAN_SPEC`.
- **EXACT_VERSION_OR_COMMIT:** AutoCAD 2027 / Database Engine 26.0.0.0 (SHA256: `acdbmgd.dll` `4b8bb5ed...`, `acdb26.dll` `5bb96f5f...`).
- **REUSE_CLASS:** `DIRECT_IMPORT` (.NET SDK reference) + `CLEAN_SPEC`.
- **CURRENT_CAD_AGENT_OWNER:** `autocad_plugin/CadAgent.AutoCAD2027`.
- **DISPOSITION:** `ADOPTED`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `OBSERVED_MANAGED_METADATA` / `OBSERVED_RUNTIME`.
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
- **DURABLE_POINTERS:** [`rea_evidence_driven_code_avoidance_investigation.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/rea_evidence_driven_code_avoidance_investigation.md).

---

### REA-010: DIMASSOC_NATIVE_RELATIONSHIP
- **CAPABILITY:** Reliable read-only discrimination of associative dimension reactors from arbitrary persistent reactors and proof of exact LINE $\leftrightarrow$ DIMENSION pairing in AutoCAD 2027.
- **EXTERNAL_SOURCE:** AutoCAD 2027 Database Engine (`AcDbDimAssoc`, `AcDbAlignedDimension`, `AcDbLine`).
- **SOURCE_TYPE:** `BINARY_PE_MANAGED` / `OBSERVED_AUTOCAD_DATABASE`.
- **EXACT_VERSION_OR_COMMIT:** AutoCAD 2027 commercial/preview (`accoreconsole.exe`).
- **REUSE_CLASS:** `ARCHITECTURAL_PATTERN` (3 structural invariants + 4-way reactor classification).
- **CURRENT_CAD_AGENT_OWNER:** `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`.
- **DISPOSITION:** `TRANSFERRED_READY_FOR_CODEX`.
- **RESEARCH_AGAIN:** **`GATED_BY_LUNA_PROBE`** (Read-only settled; in-place mutation probe gated on Luna workstation experiment).
- **EVIDENCE_TIER:** `OBSERVED_RUNTIME` / `OBSERVED_TEST` / `OBSERVED_AUTOCAD_DATABASE`.
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
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `luna_handoff_causal_mutation_probe.md` (`DIMASSOC_ASSOCIATIVE_LINE_MUTATION_CAUSAL_PROBE_V1`).
- **DURABLE_POINTERS:** [`research/antigravity/2026-10-11/dimassoc_reactor_validation/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/dimassoc_reactor_validation/), [`rea_dimassoc_differential_validation_report.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/rea_dimassoc_differential_validation_report.md).

---

### REA-011: DXF_DOCUMENT_CONSTRUCTION
- **CAPABILITY:** Headless, multi-platform creation, querying, and serializing of complete DXF R2018 CAD drawings, modelspace geometry, layers, and styles.
- **EXTERNAL_SOURCE:** `mozman/ezdxf` (v1.4.x).
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (MIT License).
- **EXACT_VERSION_OR_COMMIT:** `ezdxf >= 1.4.0`.
- **REUSE_CLASS:** `DIRECT_IMPORT`.
- **CURRENT_CAD_AGENT_OWNER:** `dxf_builder_lib/builder.py`.
- **DISPOSITION:** `ADOPTED`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **WHAT_WAS_INSPECTED:** Construction of `Drawing`, `ModelSpace`, entity tables, and dimension styles.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Generates valid DXF documents conforming to AutoCAD R2018 specifications.
  - Clean headless roundtrip without requiring AutoCAD native runtime.
- **FAILURE_MODES_AND_LIMITS:**
  - `ezdxf` does not evaluate dynamic blocks, associative dimension reactor graphs, or constraint solvers.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT write custom raw DXF ASCII text formatters; always use `ezdxf`.
- **DURABLE_POINTERS:** [`requirements/`](file:///C:/Users/duong/ZCodeProject/cad-agent/requirements/), [`dxf_builder_lib/`](file:///C:/Users/duong/ZCodeProject/cad-agent/dxf_builder_lib/).

---

### REA-012: WCS_SPATIAL_REGISTRATION
- **CAPABILITY:** Rigid similarity transformation $[R | T]$ solving uniform scale $s$, rotation angle $\theta$, and translation $(t_x, t_y)$ to project raster observation coordinates directly into base CAD WCS coordinates.
- **EXTERNAL_SOURCE:** Scan2CAD 2-Point Calibration / Umeyama (1991) / Kabsch algorithm.
- **SOURCE_TYPE:** `ALGORITHM_PAPER` / `COMMERCIAL_PRODUCT`.
- **EXACT_VERSION_OR_COMMIT:** Shinji Umeyama (1991), "Least-squares estimation of transformation parameters between two point patterns".
- **REUSE_CLASS:** `ALGORITHM_TRANSFER` (Policy D: Caller-declared orientation envelope + 2-point similarity transform).
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/alignment.py`, `cad_agent/base_cad_adapter.py`.
- **DISPOSITION:** `TRANSFERRED_READY_FOR_CODEX`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **WHAT_WAS_INSPECTED:** 4 orientation registration policies (A: Unconstrained, B: Axis-aligned, C: Bounding box, D: Declared orientation envelope) across rotational symmetries ($0^\circ, 90^\circ, 180^\circ, 270^\circ$).
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Solves exact 2D similarity transform: $\mathbf{p}_{\text{wcs}} = s R(\theta) \mathbf{p}_{\text{px}} + \mathbf{t}$.
  - Policy D eliminates 100% of rotational symmetry traps by requiring caller-declared orientation envelopes.
  - Collinear anchor handling treated as a product-safety policy gate rather than an unsolvable singularity.
- **FAILURE_MODES_AND_LIMITS:**
  - 2-point similarity transform cannot solve non-linear perspective keystone distortion; assumes orthographic scan.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT invent heuristic symmetry tie-breakers; enforce explicit orientation envelopes.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `orientation_policy_benchmark.py` (Asserts zero rotation errors and distance ratio deviation $\le 0.5\%$).
- **DURABLE_POINTERS:** [`research/antigravity/2026-10-11/orientation/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/orientation/), [`target_base_orientation_policy_discriminator_specification.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/target_base_orientation_policy_discriminator_specification.md).

---

### REA-013: NEGATIVE_RASTER_REMOVAL_EVIDENCE
- **CAPABILITY:** Verification of whether an unmatched base CAD entity can be safely removed based on source raster pixel evidence.
- **EXTERNAL_SOURCE:** Scan2CAD Raster Masking / Forge AI Difference Model.
- **SOURCE_TYPE:** `COMMERCIAL_PRODUCT` / `ARCHITECTURAL_PATTERN`.
- **EXACT_VERSION_OR_COMMIT:** Clean-room specification (`SOURCE_NEGATIVE_LINE_SUPPORT_EVIDENCE_V1`).
- **REUSE_CLASS:** `NEGATIVE_CONTROL` / `ARCHITECTURAL_PATTERN`.
- **CURRENT_CAD_AGENT_OWNER:** `cad_agent/source_fusion.py`, `cad_agent/source_fusion_proposal.py`.
- **DISPOSITION:** `ADOPTED` (Core safety doctrine).
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **WHAT_WAS_INSPECTED:** 12 raster dropout failure modes (scanning glare, folds, white-out, text occlusions, hatch collisions).
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - **CORE DOCTRINE:** `UNMATCHED_BASE != REMOVE`. Absence of raster detection is NOT evidence of deletion.
  - Negative source-support evidence must remain observational and cannot directly authorize native entity deletion.
  - Pixel-domain verifier contract closed; native removal blocked behind stronger semantic/identity proofs.
- **FAILURE_MODES_AND_LIMITS:**
  - Naive inversion of positive raster support causes catastrophic deletion of valid vehicle chassis geometry obscured by text or dimensions.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - **DO NOT** implement automated native entity deletion based on raster vacancy alone.
- **DURABLE_POINTERS:** [`research/antigravity/2026-10-11/removal/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/removal/), [`source_negative_line_support_empirical_specification.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/source_negative_line_support_empirical_specification.md).

---

### REA-014: BASE_CAD_DELTA_MASKING
- **CAPABILITY:** Projecting known base CAD geometry onto the registered target raster image to generate an exclusion mask and isolate the Delta ROI (Region of Interest).
- **EXTERNAL_SOURCE:** DraftSight `Draw Compare` / Forge AI Diff Engine.
- **SOURCE_TYPE:** `COMMERCIAL_PRODUCT` / `ARCHITECTURAL_PATTERN`.
- **EXACT_VERSION_OR_COMMIT:** Clean-room specification (`RasterBaseDeltaInference`).
- **REUSE_CLASS:** `ARCHITECTURAL_PATTERN`.
- **CURRENT_CAD_AGENT_OWNER:** `cad_agent/source_fusion.py`.
- **DISPOSITION:** `TRANSFERRED_READY_FOR_CODEX`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB`.
- **WHAT_WAS_INSPECTED:** Whole-image processing vs. Delta ROI masking on modified vehicle drawings.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Whole-image processing re-vectorizes unchanged base geometry (cabin, wheels) into hundreds of noisy polylines.
  - Delta masking marks all projected base CAD entities `KEEP`, subtracts them from the raster observation, and restricts vectorization/OCR strictly to the modified Delta ROI bounding boxes.
- **FAILURE_MODES_AND_LIMITS:**
  - Requires subpixel accuracy from 2-point spatial registration (`REA-012`) to prevent masking offsets.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT re-vectorize untouched base CAD linework.
- **DURABLE_POINTERS:** [`wave_a_cad_capability_mining_report.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/wave_a_cad_capability_mining_report.md), [`PROJECT_RESEARCH_INDEX.md`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/external-projects/PROJECT_RESEARCH_INDEX.md).

---

### REA-015: CIRCLE_FALSE_POSITIVE_VALIDATION
- **CAPABILITY:** Validation of OpenCV Hough circle candidates against source raster perimeter evidence to eliminate ghost circles caused by hatch, text, corners, and noise.
- **EXTERNAL_SOURCE:** OpenCV `cv2.HoughCircles` accumulator analysis + Radial Distance Variance Filter.
- **SOURCE_TYPE:** `ALGORITHM_TRANSFER` / `OPEN_SOURCE_REPO`.
- **EXACT_VERSION_OR_COMMIT:** OpenCV 4.8.0+.
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/geometry_extraction.py` (`extract_circles()`).
- **DISPOSITION:** `TRANSFERRED_READY_FOR_CODEX`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **WHAT_WAS_INSPECTED:** Baseline HoughCircles generating 144 false-positive circles on non-circle patterns (cross-hatch, text, grid crossings) and spurious concentric ghost rings on large circles.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Enforces perimeter support oracle: minimum circumference support $\ge 75\%$, max unsupported angular gap $\le 45^\circ$, radial gradient alignment $\ge 60\%$, and radial distance roundness $\sigma_r \le \max(0.35, 0.04r)$.
  - Achieves $100.0\%$ false-positive elimination rate (0/144 false detections accepted) while retaining $100.0\%$ of true circles across 35 configurations.
- **FAILURE_MODES_AND_LIMITS:**
  - Inside/outside contrast check is unsafe for solid disks and thick strokes.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT accept raw `cv2.HoughCircles` output without perimeter evidence validation.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** `test_circle_false_positives_red.py` (Asserts 0/144 false circles accepted).
- **DURABLE_POINTERS:** [`research/antigravity/2026-10-11/circle_validation/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/circle_validation/), [`circle_recognition_hardening_specification.md`](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/circle_recognition_hardening_specification.md).

---

### REA-016: COLLINEAR_LINE_MERGING
- **CAPABILITY:** Merging collinear fragmented line segments while strictly preserving parallel lines, dimension witness chains, and T-junctions.
- **EXTERNAL_SOURCE:** Principal Component Analysis (PCA) line fitting + Parallel Line Separation Guard.
- **SOURCE_TYPE:** `ALGORITHM_TRANSFER`.
- **EXACT_VERSION_OR_COMMIT:** Clean-room specification (`COLLINEAR_LINE_MERGING_V1`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/line_merging.py` (`merge_collinear_lines()`).
- **DISPOSITION:** `TRANSFERRED_READY_FOR_CODEX`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **WHAT_WAS_INSPECTED:** Production `merge_collinear_lines` causing first-segment angle skew ($2.8^\circ$ error, $20.49\text{ px}$ drift) and parallel line collapse ($79.0\%$ failure on 105 test pairs).
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Strategy D (Weighted PCA + Parallel Guard): achieves $0.004^\circ$ angle error, $0.029\text{ px}$ lateral drift, $100\%$ parallel line preservation, and $100\%$ dimension chain recall.
  - Executes in $35.1\ \mu\text{s}$ per call.
- **FAILURE_MODES_AND_LIMITS:**
  - Naive endpoint-only bounding allows perpendicular endpoint leaks; requires strict bilateral projection bounding.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT anchor line angle solely to the first segment's orientation.
- **SMALLEST_TRANSFER_ORACLE_OR_TEST:** 105-pair parallel matrix in `line_merging/test_causal_red_line_merging.py`.
- **DURABLE_POINTERS:** [`research/antigravity/2026-10-11/line_merging/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/line_merging/).

---

### REA-017: CALIBRATION_CONSENSUS
- **CAPABILITY:** Multi-candidate automatic scale calibration from text dimension callouts and carrier geometry, enforcing the `AGENTS.md` consensus gate.
- **EXTERNAL_SOURCE:** `AGENTS.md` production invariant ($\ge 2$ independent witnesses, $\le 3.0\%$ median relative error) & carrier collinear gap bridging.
- **SOURCE_TYPE:** `ALGORITHM_TRANSFER` / `SPECIFICATION`.
- **EXACT_VERSION_OR_COMMIT:** Clean-room specification (`AUTOMATIC_CALIBRATION_CONSENSUS_V1`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `primitive_ir_lib/calibration.py`.
- **DISPOSITION:** `TRANSFERRED_READY_FOR_CODEX`.
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
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
- **DURABLE_POINTERS:** [`research/antigravity/2026-10-11/calibration_consensus/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/calibration_consensus/), [`research/antigravity/2026-10-11/calibration_candidate_transfer/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/calibration_candidate_transfer/).

---

### REA-018: PARAMETRIC_CONSTRAINT_SOLVING
- **CAPABILITY:** Analytical geometric 2D constraint solving (coincident, horizontal, vertical, parallel, perpendicular, symmetric, tangent, distance, diameter).
- **EXTERNAL_SOURCE:** `solvespace/solvespace` (`python-solvespace==3.0.8`).
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (GPL v3+ with Python C-extension binding).
- **EXACT_VERSION_OR_COMMIT:** `python-solvespace==3.0.8` (Pinned).
- **REUSE_CLASS:** `DIRECT_IMPORT` (Exclusive solver owner).
- **CURRENT_CAD_AGENT_OWNER:** `semantic_ir_lib/constraint_solving.py` (`solve_constraints()`).
- **DISPOSITION:** `ADOPTED` (Sole pinned solver owner; replacement strictly forbidden).
- **RESEARCH_AGAIN:** **`NO`**.
- **EVIDENCE_TIER:** `DURABLE_GITHUB` / `OBSERVED_TEST`.
- **WHAT_WAS_INSPECTED:** SolveSpace constraint solver bindings across mechanical geometry.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - Solves complex coupled mechanical constraints with exact numerical convergence ($0.000\text{ mm}$ residual).
  - Handles datum anchoring via `sys.dragged` and parametric symmetry via `sys.symmetric`.
- **FAILURE_MODES_AND_LIMITS:**
  - Over-constrained systems or conflicting redundant constraints cause solver divergence; requires graph-theoretic constraint pruning (`semantic_ir_lib/constraint_pruning.py`).
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - **DO NOT** replace or rewrite `python-solvespace`.
  - **DO NOT** create a parallel constraint solver.
- **DURABLE_POINTERS:** [`semantic_ir_lib/constraint_solving.py`](file:///C:/Users/duong/ZCodeProject/cad-agent/semantic_ir_lib/constraint_solving.py), [`research/antigravity/2026-10-11/symmetry_constraint_detection/`](file:///C:/Users/duong/ZCodeProject/cad-agent/research/antigravity/2026-10-11/symmetry_constraint_detection/).

---

### REA-019: OPEN_SOURCE_CAD_ENGINES (FreeCAD, LibreCAD, LibreDWG, QCAD)
- **CAPABILITY:** Open-source CAD engines, geometry kernels, and DWG file decoding libraries.
- **EXTERNAL_SOURCE:** FreeCAD, LibreCAD, LibreDWG, QCAD.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO`.
- **EXACT_VERSION_OR_COMMIT:** `UNINSPECTED`.
- **REUSE_CLASS:** `UNKNOWN` / `NOT_INSPECTED`.
- **CURRENT_CAD_AGENT_OWNER:** *None*.
- **DISPOSITION:** `UNKNOWN` (Explicitly marked as not yet inspected; no claims made).
- **RESEARCH_AGAIN:** **`ONLY_IF_EXPLICITLY_COMMISSIONED`**.
- **EVIDENCE_TIER:** `UNKNOWN`.
- **WHAT_WAS_INSPECTED:** None. No code, binaries, or documentation from FreeCAD, LibreCAD, LibreDWG, or QCAD have been inspected or decompiled in this research program.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:** None established.
- **FAILURE_MODES_AND_LIMITS:**
  - LibreDWG is GPL v3+ (strict copyleft barrier for proprietary CAD integrations).
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT assume capabilities or algorithms without explicit clean-room commissioning.
- **DURABLE_POINTERS:** `None`.
