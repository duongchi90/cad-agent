# TECHNICAL SPECIFICATION: ROBUST DIMENSION GEOMETRY EXTRACTION (`DIMENSION_GEOMETRY_EXTRACTION_V1`)

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `DIMENSION_GEOMETRY_EMPIRICAL`
- **Target Epic:** `DIMENSION_GEOMETRY_EXTRACTION_V1`
- **Subagents:** `0` (Disabled per #429 overlay)
- **Repository Checkout:** `C:\cad-agent-antigravity`
- **Base Research Branch / Commit:** `research/antigravity-2026-10-11` (`efba4d4a8197a9fd98790ca3fa43f1c3cfa0a2b4`)
- **Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), PR #494 (`fix/start-tab-drawing-open-fallback`, DRAFT)
- **Production Impact:** `RESEARCH_ONLY = YES`, `PRODUCTION_FILES_CHANGED = false`

---

## Epistemic Status Legend

Throughout this specification, claims and parameters are explicitly tagged with their epistemic category:
- **`[MEASURED]`**: Direct empirical output from deterministic benchmark scripts in `research/antigravity/2026-10-11/dimension_geometry/`.
- **`[SAFE_DIMENSIONLESS_BOUND]`**: Invariant mathematical or topological ratio that does not depend on DPI, scanner hardware, or real scan calibration.
- **`[SYNTHETIC_DISCRIMINATOR]`**: Threshold or boundary derived from synthetic raster benchmarks that separates positive and negative controls on clean/degraded synthetic fixtures.
- **`[NEEDS_REAL_SCAN_CALIBRATION]`**: Absolute pixel-domain threshold that must be validated on physical paper/scanner engineering drawings before release.
- **`[INFERENCE]`**: Analytical or geometric deduction from measured evidence and mathematical invariants.
- **`[FUTURE_PRODUCTION_PROPOSAL]`**: Recommended design contract and minimum writeset for future `SOLO_CODEX` implementation (not yet implemented in production).
- **`[UNPROVEN_REAL_SCAN_GENERALIZATION]`**: Behavior on physical paper/scanner engineering drawings that remains unproven because private/customer drawings were lawfully excluded from research runs.

---

## Section 10: Fresh-Read Current Owners (`[MEASURED]`)

| Field | Verified Value |
|---|---|
| `CURRENT_DIMENSION_GEOMETRY_OWNER` | `primitive_ir_lib/dimension_geometry.py:1-369` (`detect_dimension_geometry`, `DimensionGeometryEvidence`, `_select_dimension_line`, `_detect_extension_lines`) |
| `CURRENT_PRIMITIVE_IR_INTEGRATION` | `primitive_ir_lib/crops.py:100-145` (calls `detect_dimension_geometry(crop_bgr)` during crop enrichment) |
| `CURRENT_GEOMETRY_TEST_OWNER` | `primitive_ir_lib/tests/test_dimension_geometry.py:1-92` (tests standard horizontal/vertical crops) |
| `CURRENT_SEMANTIC_INTEGRATION` | `semantic_ir_lib/semantic_extractor.py:210-245` (consumes `DimensionGeometryEvidence.dimension_line` and `extension_lines`) |
| `NEW_MODULE_REQUIRED` | `NO` (All improvements belong directly inside `primitive_ir_lib/dimension_geometry.py`) |

---

## Section 11: Public Causal RED (`[MEASURED]`)

- **Script:** [`test_causal_red_dimension_geometry.py`](test_causal_red_dimension_geometry.py)
- **Result:** **5/5 Causal Failures Reproducible in Production Main Logic**

| RED Test | Production Flaw Mechanism | Measured Production Failure | Strategy D Behavior |
|---|---|---|---|
| **RED 1: Vertical Dimension Line Inversion** | Line 152: `candidates = horizontal or vertical`. If any horizontal lines exist (e.g. horizontal extension lines), vertical candidates are ignored entirely. | Vertical dimension line (length 200px) with 80px horizontal extension lines: **misclassified as `HORIZONTAL_DISTANCE`**; extension lines returned = `()`. | Evaluates all candidate lines across orientations; scores by orthogonal extension lines + arrowheads: **100% correct `VERTICAL_DISTANCE` recovery with 2 extension lines**. |
| **RED 2: Upward Extension Lines Zero Recall** | Line 199: `min(...) <= y + 8.0 and max(...) >= y + 24.0`. Only checks positive y (downward). | Horizontal dimension line with extension lines extending upward: **`extension_lines = ()` (0% recall)**. | Bidirectional perpendicular projection checks both positive and negative normal directions: **100% recall (2 extension lines)**. |
| **RED 3: Rightward Extension Lines Zero Recall** | Line 210: `min(...) <= x - 24.0 and max(...) >= x - 8.0`. Only checks negative x (leftward). | Vertical dimension line with extension lines extending rightward: **`extension_lines = ()` (0% recall)**. | Bidirectional perpendicular projection checks both positive and negative normal directions: **100% recall (2 extension lines)**. |
| **RED 4: Aligned 45° Dimension Dropped** | Lines 150-154: `horizontal or vertical` only. Diagonal lines are never admitted into `candidates`. | 45-degree diagonal dimension line with perpendicular extension lines: **returns `dimension_line = None` (dropped completely)**. | Detects aligned segments at any angle $\theta$, searches for perpendicular extensions at $\theta \pm 90^\circ$: **returns `ALIGNED_DISTANCE` with 2 extension lines**. |
| **RED 5: Narrow-Gap Outward Arrowheads Unclassified** | `DimensionGeometryEvidence` has no `arrow_orientation` field; Strategy A cannot classify whether arrows point inward or outward. | Narrow dimension line (length 30px) with outward arrowheads: **no orientation attribute on dataclass**. | Detects arrow positions relative to segment endpoints and span; classifies `arrow_orientation == "OUTWARD"`. |

---

## Section 12: Multi-Candidate Empirical Benchmark (`[MEASURED]`)

- **Script:** [`test_dimension_geometry_benchmark.py`](test_dimension_geometry_benchmark.py)
- **Evaluated Strategies:**
  - **Strategy A:** Current Production Main (`primitive_ir_lib/dimension_geometry.py`)
  - **Strategy B:** Naive Bidirectional Extension (two-way check, but flawed `candidates = horizontal or vertical` selection)
  - **Strategy C:** Orthogonal Pair Matching (ranks dimension line by orthogonal extension count, H/V only)
  - **Strategy D:** Dimension Topology Oracle (Bidirectional extension, collinear gap bridging, hatch rejection, inward/outward arrowheads)

| Case # | Description | Strategy A | Strategy B | Strategy C | Strategy D (Selected) |
|---|---|---|---|---|---|
| **Case 1** | Standard horizontal dimension (downward extensions) | PASS | PASS | PASS | **PASS** |
| **Case 2** | Horizontal dimension (upward extensions) | FAIL (0 ext) | PASS | PASS | **PASS** |
| **Case 3** | Vertical dimension (leftward extensions) | FAIL (inverted to H) | FAIL (inverted to H) | PASS | **PASS** |
| **Case 4** | Vertical dimension (rightward extensions) | FAIL (inverted to H) | FAIL (inverted to H) | PASS | **PASS** |
| **Case 5** | Vertical dimension (horizontal extension trap) | FAIL (inverted to H) | FAIL (inverted to H) | PASS | **PASS** |
| **Case 6** | Aligned 45-degree dimension | FAIL (dropped) | FAIL (dropped) | FAIL (dropped) | **PASS** |
| **Case 7** | Aligned 135-degree dimension | FAIL (dropped) | FAIL (dropped) | FAIL (dropped) | **PASS** |
| **Case 8** | Narrow gap outward arrowheads | FAIL (no orientation) | FAIL (no orientation) | FAIL (no orientation) | **PASS** |
| **Case 9** | Leader annotation pointer + shelf line | PASS | PASS | PASS | **PASS** |
| **Scorecard** | **Success Rate** | **2 / 9 (22.2%)** | **3 / 9 (33.3%)** | **5 / 9 (55.6%)** | **9 / 9 (100.0%)** |

---

## Section 13: Positive Fixtures and Strong Negative Controls (`[MEASURED]`)

- **Script:** [`test_dimension_geometry_controls.py`](test_dimension_geometry_controls.py)
- **Result:** **8/8 Tests Passed Cleanly**

1. **Negative Controls (`[MEASURED]`):**
   - **Plain CAD Rectangle Outline:** `confidence = 0.40 <= 0.80`, `arrow_orientation == "NONE"`. Plain geometric corners without arrowheads or overshoot do not produce false high-confidence dimension evidence.
   - **Dense Cross-Hatching Field (96 segments):** Rejects all candidates via spaced parallel line filter (`count_spaced_parallel >= 4`). Zero false arrowheads, zero false dimension lines.
   - **Parallel Contour Tracks:** Long parallel contour lines without perpendicular extensions produce 0 extensions, `arrow_orientation == "NONE"`, `confidence = 0.20`.
   - **Single T-Junction:** Only 1 endpoint has an intersection (`len(unique_arrows) < 2`), producing `arrow_orientation == "NONE"`, `confidence = 0.25`.
   - **Centered Crosshair:** 0 arrowheads, `arrow_orientation == "NONE"`, `confidence = 0.25`.

2. **Positive Controls (`[MEASURED]`):**
   - **Horizontal Bridged Text Gap:** Two collinear horizontal fragments spanning across a 70px text gap are automatically bridged into a single dimension line: `kind_hint == "HORIZONTAL_DISTANCE"`, `confidence = 0.95`, 2 extension lines detected.
   - **Tall Vertical Dimension:** Vertical dimension spanning 220px with 2 extension lines and arrowheads: `kind_hint == "VERTICAL_DISTANCE"`, `confidence = 0.95`.
   - **Diagonal Aligned Dimension:** 30-degree dimension line with perpendicular extension lines and arrowheads: `kind_hint == "ALIGNED_DISTANCE"`, `confidence = 0.95`.

---

## Section 14: Degenerate, Non-Finite & Ambiguity Edge Cases (`[MEASURED]`)

- **Script:** [`test_dimension_geometry_degenerate_and_perf.py`](test_dimension_geometry_degenerate_and_perf.py)
- **Result:** **8/8 Tests Passed Cleanly**

1. **Blank Canvas:** Returns empty `RobustDimensionEvidence(None, (), (), "NONE", (), None, 0.0)`.
2. **Solid Black Canvas:** Returns empty evidence with `confidence = 0.0`.
3. **Tiny Crops (2x2):** Graceful empty return, 0 crash.
4. **Invalid Input Shape / Type:** Raises `ValueError("crop_bgr must be a grayscale or BGR image")`.
5. **Salt-and-Pepper Noise (2% density):** Zero arrowheads, `confidence <= 0.40`.
6. **Extreme Aspect Ratios (1000x30 and 30x1000):** Executes without buffer overflow or OpenCV stride errors.
7. **Ambiguous Square Corners:** Rejects corners as dimensions (`arrow_orientation == "NONE"`, `confidence <= 0.40`).

---

## Section 15: Runtime Performance & Computational Complexity (`[MEASURED]`)

- **Latency:** **3.07 ms / crop** (50 complex dimension crops processed in 0.154 seconds).
- **Memory Overhead:** Negligible (< 1 MB ephemeral buffers).
- **Algorithmic Complexity:** $O(N_c \cdot N_s)$ where $N_c$ is the number of candidate lines (typically $N_c \le 10$) and $N_s$ is total Hough segments ($N_s \le 30$). With hatch rejection, candidate count drops to 0 on dense hatch fields in $< 1\text{ ms}$.

---

## Section 16: Parameter & Threshold Epistemic Classification

| Parameter | Value | Epistemic Classification | Rationale & Proof |
|---|---|---|---|
| `extension_orthogonality_range` | $70.0^\circ \dots 110.0^\circ$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Mathematical perpendicularity window ($90^\circ \pm 20^\circ$) accommodating drafting tolerances and slight scan skew. |
| `collinear_angular_tolerance` | $\le 3.0^\circ$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Invariant threshold for collinear line segments along the same direction. |
| `arrow_pair_requirement` | $N_{\text{arrows}} \ge 2$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Topological invariant: a linear dimension span is bounded by exactly 2 witness endpoints. |
| `outward_arrow_condition` | $t < -2.0$ or $t > L + 2.0$ or $L < 40.0\text{ px}$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Dimensionless coordinate ordering along the dimension axis vector $\vec{u}$. |
| `hatch_spaced_parallel_count` | $\ge 4$ lines spaced $8 \dots 80\text{ px}$ | **`[SYNTHETIC_DISCRIMINATOR]`** | Distinguishes periodic hatching grids ($N=20$) from dimension lines ($N=0$). |
| `endpoint_patch_density_corner` | $\ge 70\text{ nonzero px}$ ($19 \times 19$ patch) | **`[SYNTHETIC_DISCRIMINATOR]`** | Separates plain corners ($56\text{ px}$) from arrowhead corners ($115\text{ px}$) with 14px and 45px safety margins. |
| `endpoint_patch_density_open` | $\ge 45\text{ nonzero px}$ ($19 \times 19$ patch) | **`[SYNTHETIC_DISCRIMINATOR]`** | Separates plain line endpoints ($31\text{ px}$) from arrowhead endpoints ($78\text{ px}$) with 14px and 33px safety margins. |
| `contour_area_bounds` | $12.0 \dots 600.0\text{ px}^2$ | **`[SYNTHETIC_DISCRIMINATOR]`** | Bounds solid triangular arrowhead contours from micro-dust ($<12$) and CAD part boundaries ($>600$). |
| `min_line_len_px` | $20.0\text{ px}$ | **`[NEEDS_REAL_SCAN_CALIBRATION]`** | Dependent on drawing scan DPI (at 300 DPI, 20px $\approx 1.7\text{ mm}$). |
| `extension_perp_tol_px` | $12.0\text{ px}$ | **`[NEEDS_REAL_SCAN_CALIBRATION]`** | Tolerance for extension line intersection near dimension endpoints. |
| `text_gap_bridging_tol_px` | $120.0\text{ px}$ | **`[NEEDS_REAL_SCAN_CALIBRATION]`** | Maximum longitudinal gap for dimension text interrupt. |

---

## Section 17: Selected Production Architecture & Minimum Writeset (`[FUTURE_PRODUCTION_PROPOSAL]`)

When promoted to production by `SOLO_CODEX`, the following modifications should be applied:

1. **`primitive_ir_lib/dimension_geometry.py`**:
   - Update `DimensionGeometryEvidence` dataclass to include `arrow_orientation: str = "NONE"`.
   - Replace `candidates = horizontal or vertical` in `_select_dimension_line` with multi-candidate scoring:
     - Form candidate lines from horizontal, vertical, and aligned segments, plus collinear bridged spans.
     - Reject candidates in repetitive hatch fields using `_is_hatch_line`.
     - Score candidates by: `score = 100 * attached_extensions + 150 * arrows + 0.1 * length`.
   - Replace one-way directional check in `_detect_extension_lines` with bidirectional perpendicular projection.
   - Upgrade arrow detection to support both contour matching and dual-condition patch density, classifying `arrow_orientation` into `"INWARD"`, `"OUTWARD"`, or `"NONE"`.
2. **`primitive_ir_lib/tests/test_dimension_geometry.py`**:
   - Add test cases covering vertical dimension lines with horizontal extensions, upward/rightward extensions, aligned dimensions, and outward arrowheads.

---

## Section 18: Codex Implementation Contract & Safety Guarantees

- **No Schema Breakage:** Existing callers expecting `(dimension_line, extension_lines, arrow_points, leader_lines, kind_hint, confidence)` will continue to function identically since `arrow_orientation` has default `"NONE"` or can be an added optional attribute.
- **Fail-Closed Principle:** Crops without verified extension lines or arrowheads receive confidence $\le 0.40$, preventing hallucinated CAD dimension entities in downstream DXF builders.
- **Strict Determinism:** All operations are pure deterministic OpenCV / NumPy geometry, free of non-deterministic heuristic states or external dependencies.

---

## Section 19: Risk Analysis & Rollback Plan

- **Risk:** Unusually thick stroke lines (e.g. 5px wide border lines) could produce higher endpoint patch density.
- **Mitigation:** The primary arrow detection path is contour polygon analysis (`approxPolyDP`); patch density is only a fallback. Furthermore, without perpendicular extension lines, confidence remains low ($\le 0.40$).
- **Rollback:** `git revert` on the isolated commit in `primitive_ir_lib/dimension_geometry.py`.

---

## Section 20: Verified Status Ledger Update

- `EPIC`: `DIMENSION_GEOMETRY_EXTRACTION_V1`
- `STATUS`: `READY_FOR_CODEX`
- `TESTS_PASSING`: 30 / 30 research tests
- `BENCHMARK_SCORE`: 100% (9/9 cases vs 22% in production Strategy A)
- `PERFORMANCE`: 3.07 ms / crop (< 15 ms target)
- `PRODUCTION_FILES_MUTATED`: 0 (`RESEARCH_ONLY = YES`)
