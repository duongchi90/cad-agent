# TECHNICAL SPECIFICATION: SEMANTIC VIEW REGION PARTITIONING (`SEMANTIC_VIEW_REGION_PARTITIONING_V1`)

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `VIEW_PARTITIONING_EMPIRICAL`
- **Target Epic:** `SEMANTIC_VIEW_REGION_PARTITIONING_V1`
- **Subagents:** `0` (Disabled per #429 overlay)
- **Repository Checkout:** `C:\cad-agent-antigravity`
- **Base Research Branch / Commit:** `research/antigravity-2026-10-11` (`e33754d058ab459c6a04bd37e8497ae1f8a64ede`)
- **Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), PR #494 (`fix/start-tab-drawing-open-fallback`, DRAFT)
- **Production Impact:** `RESEARCH_ONLY = YES`, `PRODUCTION_FILES_CHANGED = false`

---

## Epistemic Status Legend

Throughout this specification, claims and parameters are explicitly tagged with their epistemic category:
- **`[MEASURED]`**: Direct empirical output from deterministic benchmark scripts in `research/antigravity/2026-10-11/view_partitioning/`.
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
| `CURRENT_VIEW_CALIBRATION_OWNER` | `primitive_ir_lib/view_calibration.py:1-116` (`detect_view_candidates`, `_line_regions`, `parse_scale_label`, `mm_per_px_for_scale`) |
| `CURRENT_PRIMITIVE_IR_INTEGRATION` | `primitive_ir_lib/crops.py` (crops multi-view drawings into independent view envelopes) |
| `CURRENT_VIEW_TEST_OWNER` | `primitive_ir_lib/tests/test_view_calibration.py:1-107` (tests basic single-label binding) |
| `CURRENT_SEMANTIC_INTEGRATION` | `semantic_ir_lib/title_block_extractor.py` and `semantic_ir_lib/constraint_detection.py` (require view-localized coordinate frames) |
| `NEW_MODULE_REQUIRED` | `NO` (All improvements belong directly inside `primitive_ir_lib/view_calibration.py`) |

---

## Section 11: Public Causal RED (`[MEASURED]`)

- **Script:** [`test_causal_red_view_partitioning.py`](test_causal_red_view_partitioning.py)
- **Result:** **5/5 Causal Failures Reproducible in Production Main Logic**

| RED Test | Production Flaw Mechanism | Measured Production Failure | Strategy D Behavior |
|---|---|---|---|
| **RED 1: Single-Linkage Chaining Bridge Collapse** | Line 42: `_bbox_distance(bbox, region) <= gap_px`. Chaining merges two views when an intermediate dimension or small projection corridor $\le 30\text{ px}$ connects them. | Two separate views at $x \in [100, 300]$ and $[325, 525]$: **merged into 1 giant bounding box $[100, 100, 525, 300]$**, assigning conflicting scales (1:10 and 1:5) to the exact same region. | Disjoint Set Union with local clustering radius ($20\text{ px}$) preserves both view boundaries: **extracts 2 distinct non-overlapping views with correct respective scales**. |
| **RED 2: Sheet Border Assimilation & Dimension Bailout** | Lines 84-88: `if region_area / page_area >= 0.80: continue`. Outer sheet border margin lines assimilate views into a 95% area cluster, forcing immediate bailout. | Sheet border frame with connecting margin line: **forces Strategy A to bail out and drop all dimension verification evidence**. | Margin peeling isolates sheet border lines into `border_bbox_px` before view clustering: **cleanly retains view geometry and enables localized dimension verification**. |
| **RED 3: Centerline / Projection Crossing Trap** | Line 42: Single bridging line between views causes transitive union. | Thin alignment centerline connecting View 1 and View 2 across $y=200$: **collapses both views into 1 region $[100, 100, 700, 300]$**. | Suppresses inter-view bridging lines lacking lateral density: **preserves separate view entities**. |
| **RED 4: Equidistant Scale Label Dropping** | Line 73: `if len(distances) > 1 and abs(distances[0][0] - distances[1][0]) < 1e-6: continue`. Discards label if distances to two views are identical. | Label placed symmetrically between views: **0 view candidates emitted (`unassigned_text_ids` contains label)**. | Evaluates directional alignment and horizontal heading penalty: **robustly binds label to the intended view**. |
| **RED 5: Title Block Metadata Table Conflation** | Strategy A lacks table awareness; lines in title blocks are treated as drawing view regions. | Title block grid in bottom-right corner ($x \in [900, 1350]$): **emitted as a drawing view region candidate**. | Isolates bottom-right rectangular grids into `table_bboxes_px`: **0 false views emitted from title block metadata**. |

---

## Section 12: Multi-Candidate Empirical Benchmark (`[MEASURED]`)

- **Script:** [`test_view_partitioning_benchmark.py`](test_view_partitioning_benchmark.py)
- **Evaluated Strategies:**
  - **Strategy A:** Current Production Main (`primitive_ir_lib/view_calibration.py`)
  - **Strategy B:** Bounding Box Chaining with Max Distance
  - **Strategy C:** Projection Gutter Slicing (1D occupancy histograms)
  - **Strategy D:** Semantic View Partitioning Oracle (Border/table peeling, directional title binding)

| Case # | Description | Strategy A | Strategy B | Strategy C | Strategy D (Selected) |
|---|---|---|---|---|---|
| **Case 1** | Two-view orthographic (Front + Top) | PASS (2 views) | PASS (2 views) | PASS (2 views) | **PASS (2 views)** |
| **Case 2** | Three-view first-angle (Front, Top, Right) | PASS (3 views) | PASS (3 views) | PASS (3 views) | **PASS (3 views)** |
| **Case 3** | Mixed-scale views (1:10 general + 1:2 detail) | PASS (2 views) | PASS (2 views) | PASS (2 views) | **PASS (2 views, correct scales)** |
| **Case 4** | Sheet with margin border and title block | FAIL (border collapse) | FAIL (border collapse) | FAIL (sliced border) | **PASS (clean views + peeled border)** |
| **Case 5** | Inter-view gutter whitespace separation | PASS (2 views) | PASS (2 views) | PASS (2 views) | **PASS (2 views)** |
| **Case 6** | Directional heading alignment under asymmetry | FAIL (wrong view) | FAIL (wrong view) | FAIL (wrong view) | **PASS (aligned to correct view)** |
| **Scorecard** | **Success Rate** | **3 / 6 (50.0%)** | **3 / 6 (50.0%)** | **3 / 6 (50.0%)** | **6 / 6 (100.0%)** |

---

## Section 13: Positive Fixtures and Strong Negative Controls (`[MEASURED]`)

- **Script:** [`test_view_partitioning_controls.py`](test_view_partitioning_controls.py)
- **Result:** **6/6 Tests Passed Cleanly**

1. **Negative Controls (`[MEASURED]`):**
   - **Isolated Drawing Border Frame:** 4 perimeter margin lines: `has_valid_partition = False`, `len(views) == 0`, `border_bbox_px` detected.
   - **General Notes Column Text:** Text notes on left margin with no geometry lines: `has_valid_partition = False`, `len(views) == 0`.
   - **Scattered Registration Marks:** Small alignment ticks ($< 15\text{ px}$): `has_valid_partition = False`, `len(views) == 0`.
   - **Title Block Only Sheet:** Bottom-right title block grid alone: `has_valid_partition = False`, `len(views) == 0`, `table_bboxes_px` detected.

2. **Positive Fixtures (`[MEASURED]`):**
   - **Standard Two-View A3 Drawing:** 1600x1000 sheet with margin border, title block, and 2 orthographic views: `has_valid_partition = True`, `confidence >= 0.90`, 2 views extracted with correct scales, title block isolated.
   - **Section & Detail Views:** 3-view assembly with General View (1:10), Section A-A (1:5), and Detail B (1:2): accurately binds all 3 scales (`{10, 5, 2}`), zero unassigned scale labels.

---

## Section 14: Degenerate, Non-Finite & Ambiguity Edge Cases (`[MEASURED]`)

- **Script:** [`test_view_partitioning_degenerate_and_perf.py`](test_view_partitioning_degenerate_and_perf.py)
- **Result:** **7/7 Tests Passed Cleanly**

1. **Empty Inputs:** Safely returns `has_valid_partition = False`, `views = ()`.
2. **Zero-Length Lines:** $p_1 == p_2$ ignored without divide-by-zero or math errors.
3. **Non-Finite Coordinates:** NaN and Inf in coordinates, image dimensions, or DPI safely handled.
4. **Non-Positive Dimensions / DPI:** `width <= 0`, `height <= 0`, `dpi <= 0` safely return `has_valid_partition = False`.
5. **Micro-Segments Dust:** Segments $< 5\text{ px}$ safely ignored, producing 0 phantom views.

---

## Section 15: Runtime Performance & Computational Complexity (`[MEASURED]`)

- **Large-Format 50-View Assembly Benchmark (50 views, 200 lines):**
  - **Latency:** **< 8.5 ms** (Target: $< 30.0\text{ ms}$).
- **Batch Processing Throughput:**
  - **Latency:** **0.32 ms / drawing** across 100 drawing runs (Target: $< 5.0\text{ ms} / \text{drawing}$).
- **Memory Overhead:** Negligible (< 1 MB ephemeral buffers).
- **Algorithmic Complexity:**
  - Border/margin peeling: $O(N_l)$.
  - Connected component clustering: $O(N_l^2)$ for small $N_l \le 500$, reducible to $O(N_l \log N_l)$ with R-tree/spatial hash grid.
  - Directional scale label binding: $O(N_t \cdot N_v)$ where $N_t$ is scale labels ($N_t \le 10$) and $N_v$ is views ($N_v \le 10$).

---

## Section 16: Parameter & Threshold Epistemic Classification

| Parameter | Value | Epistemic Classification | Rationale & Proof |
|---|---|---|---|
| `page_border_perimeter_ratio` | $\ge 0.70$ dimension | **`[SAFE_DIMENSIONLESS_BOUND]`** | Invariant ratio: a sheet border margin line spans $\ge 70\%$ of the page width or height. |
| `margin_envelope_ratio` | $0.05$ ($5\%$ page margin) | **`[SAFE_DIMENSIONLESS_BOUND]`** | Invariant ratio: outer sheet borders lie within the outer $5\%$ margin of the physical sheet. |
| `directional_horizontal_penalty` | $2.0 \times$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Directional heading invariant: drawing view titles and scales are placed vertically adjacent to their view, not horizontally across gutters. |
| `local_cluster_radius_px` | $20.0\text{ px}$ | **`[SYNTHETIC_DISCRIMINATOR]`** | Binds adjacent line strokes of a single component while separating projection corridors ($\ge 40\text{ px}$). |
| `min_gutter_px` | $30.0\text{ px}$ | **`[SYNTHETIC_DISCRIMINATOR]`** | Distinguishes inter-view projection corridors from internal drawing geometry. |
| `min_view_dimension_px` | $15.0\text{ px}$ | **`[SYNTHETIC_DISCRIMINATOR]`** | Rejects registration crosses and noise dust from being promoted to drawing view envelopes. |
| `max_label_distance_mm` | $35.0\text{ mm}$ | **`[NEEDS_REAL_SCAN_CALIBRATION]`** | Maximum physical distance between a view title/scale label and the view boundary. |
| `dimension_proximity_px` | $120.0\text{ px}$ | **`[NEEDS_REAL_SCAN_CALIBRATION]`** | Maximum distance for localizing dimension text to witness lines within the same view. |

---

## Section 17: Selected Production Architecture & Minimum Writeset (`[FUTURE_PRODUCTION_PROPOSAL]`)

When promoted to production by `SOLO_CODEX`, the following modifications should be applied:

1. **`primitive_ir_lib/view_calibration.py`**:
   - Add sheet margin and title block table peeling before invoking `_line_regions`:
     - Detect lines within $5\%$ page margin spanning $\ge 70\%$ of page dimension; isolate into `border_bbox`.
     - Detect bottom-right table blocks; isolate into `table_bboxes`.
   - Replace unconstrained `_bbox_distance` clustering with local cluster radius ($20\text{ px}$) to prevent single-linkage bridge collapse.
   - Upgrade scale label binding in `detect_view_candidates`:
     - Apply directional proximity weighting: `score = dist + 2.0 * dx_center`.
     - Eliminate arbitrary `1e-6` equidistant drop filter; select the vertically aligned view candidate.
2. **`primitive_ir_lib/tests/test_view_calibration.py`**:
   - Add multi-view orthographic tests, sheet border isolation tests, and title block separation tests.

---

## Section 18: Codex Implementation Contract & Safety Guarantees

- **No Schema Breakage:** Returns standard dictionary candidates matching `detect_view_candidates` signature, plus added optional metadata `border_bbox_px` and `table_bboxes_px`.
- **Fail-Closed Principle:** Sheets with only border lines or general notes return empty candidates (`status = "unresolved"`), preventing false scale calibration from corrupting DXF generation.
- **Strict Determinism:** Pure geometry and directional distance metrics, completely free of heuristic state or external network calls.

---

## Section 19: Risk Analysis & Rollback Plan

- **Risk:** Unusually positioned scale labels (e.g. inside the view body rather than below) might incur higher directional penalty.
- **Mitigation:** If no candidate label is below the view, the algorithm falls back to nearest internal label.
- **Rollback:** `git revert` on the isolated commit in `primitive_ir_lib/view_calibration.py`.

---

## Section 20: Verified Status Ledger Update

- `EPIC`: `SEMANTIC_VIEW_REGION_PARTITIONING_V1`
- `STATUS`: `READY_FOR_CODEX`
- `TESTS_PASSING`: 24 / 24 research tests
- `BENCHMARK_SCORE`: 100% (6/6 cases vs 50% in production Strategy A)
- `PERFORMANCE`: < 8.5 ms for 50-view assembly, 0.32 ms / drawing batch (< 5.0 ms target)
- `PRODUCTION_FILES_MUTATED`: 0 (`RESEARCH_ONLY = YES`)
