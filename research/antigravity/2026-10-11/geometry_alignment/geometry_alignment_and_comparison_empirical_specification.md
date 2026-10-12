# TECHNICAL SPECIFICATION: RESTRICTED GEOMETRY ALIGNMENT AND COMPARISON (`RESTRICTED_GEOMETRY_ALIGNMENT_AND_COMPARISON_V1`)

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `GEOMETRY_ALIGNMENT_EMPIRICAL`
- **Target Epic:** `RESTRICTED_GEOMETRY_ALIGNMENT_AND_COMPARISON_V1`
- **Subagents:** `0` (Disabled per #429 overlay)
- **Repository Checkout:** `C:\cad-agent-antigravity`
- **Base Research Branch / Commit:** `research/antigravity-2026-10-11` (`01cb5d26a95a99d03e4d9bd588345c8a6b32abf0`)
- **Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), PR #494 (`fix/start-tab-drawing-open-fallback`, DRAFT)
- **Production Impact:** `RESEARCH_ONLY = YES`, `PRODUCTION_FILES_CHANGED = false`

---

## Epistemic Status Legend

Throughout this specification, claims and parameters are explicitly tagged with their epistemic category:
- **`[MEASURED]`**: Direct empirical output from deterministic benchmark scripts in `research/antigravity/2026-10-11/geometry_alignment/`.
- **`[SAFE_DIMENSIONLESS_BOUND]`**: Invariant mathematical, geometric, or topological property that does not depend on DPI, scanner hardware, or real scan calibration.
- **`[SYNTHETIC_DISCRIMINATOR]`**: Threshold or boundary derived from synthetic geometry benchmarks separating positive from negative controls.
- **`[NEEDS_REAL_SCAN_CALIBRATION]`**: Absolute millimeter/pixel threshold that must be tuned against physical paper/scanner engineering drawing tolerances.
- **`[INFERENCE]`**: Analytical or geometric deduction from measured evidence and mathematical invariants.
- **`[FUTURE_PRODUCTION_PROPOSAL]`**: Recommended design contract and minimum writeset for future `SOLO_CODEX` implementation (not yet implemented in production).
- **`[UNPROVEN_REAL_SCAN_GENERALIZATION]`**: Behavior on physical paper/scanner engineering drawings that remains unproven because private/customer drawings were lawfully excluded from research runs.

---

## Section 10: Fresh-Read Current Owners (`[MEASURED]`)

| Field | Verified Value |
|---|---|
| `CURRENT_ALIGNMENT_OWNER` | `primitive_ir_lib/geometry_alignment.py:110-124, 140-235, 238-317` (`_validated_anchors`, `estimate_similarity_alignment`, `estimate_photograph_alignment`) |
| `CURRENT_METRICS_OWNER` | `primitive_ir_lib/geometry_metrics.py:58-78, 180-197` (`normalize_outline`, `compute_geometry_metrics`) |
| `CURRENT_TEST_OWNERS` | `primitive_ir_lib/tests/test_geometry_alignment.py`, `primitive_ir_lib/tests/test_geometry_metrics.py` |
| `CURRENT_CONTRACT_SCHEMA` | `cad_agent/visual_contracts.py:geometry_alignment_result`, `geometry_metrics` |
| `SMALLEST_EXISTING_OWNER` | `primitive_ir_lib/geometry_alignment.py` and `primitive_ir_lib/geometry_metrics.py` |
| `NEW_MODULE_REQUIRED` | `NO` (Modifies internal selection and normalization routines in existing modules) |
| `NEW_SCHEMA_REQUIRED` | `NO` (Visual contract schemas are 100% backward compatible) |
| `NEW_DEPENDENCY_REQUIRED` | `NO` (Reuses existing OpenCV `cv2`, `numpy`, and standard math library) |
| `ASSEMBLY_CHANGE_REQUIRED` | `NO` |
| `BUILDER_CHANGE_REQUIRED` | `NO` |

---

## Section 11: Public Causal RED (`[MEASURED]`)

- **Script:** [`test_causal_red_geometry_alignment.py`](test_causal_red_geometry_alignment.py)
- **Result:** **5/5 Causal Failures Reproducible in Production Main Logic**

| RED Test | Production Flaw Mechanism | Measured Production Failure | Strategy D Behavior |
|---|---|---|---|
| **RED 1: Highest-Tier Starvation in Anchor Selection** | `_validated_anchors` takes `[item for item in eligible if _AUTHORITY_TIERS[item.authority] == highest_tier]`. Discards all lower tiers even if highest tier has only 1 anchor. | Single `DATUM` anchor discards 3 valid `DRIVING_DIMENSION` anchors; returns 1 anchor and fails with `"at least two anchors are required"`. | Cascades down tiers (`DATUM` -> `DRIVING_DIMENSION` -> `STABLE_ENTITY`) until $\ge 2$ anchors are accumulated; successfully aligns (`status: ALIGNED`). |
| **RED 2: Rigid 0.98 Border Polarity Crash** | `normalize_outline` tests `black_fraction >= 0.98` or `white_fraction >= 0.98` on 1px outer image border. A line crossing or noise occupying 2.5% triggers ambiguous exception. | White image with 2.5% black border line noise crashes with `ValueError: foreground polarity is ambiguous`. | Multi-evidence consensus (4 corner 5x5 patches + 3px inset perimeter band) robustly detects background polarity with 0.65 threshold; outputs clean normalized mask. |
| **RED 3: Strict N=4 Homography Rejection** | `estimate_photograph_alignment` checks `if len(items) != 4: return _photograph_failure(..., "photograph alignment requires exactly four anchors")`. | Fails completely (`status: FAILED`) when 5 or 6 valid perspective anchors are supplied from multi-feature photos. | Solves least-squares DLT homography for arbitrary $N \ge 4$ perspective anchors via `cv2.findHomography`; aligns with RMS residual < 0.5 px. |
| **RED 4: Collinear Anchor Rank Failure on N >= 3 Anchors** | `estimate_similarity_alignment` requires `rank_ref >= 2` and `rank_cad >= 2` whenever $N \ge 3$, crashing collinear feature sets. | 3 collinear anchors along a shaft centerline trigger `"three or more anchors must span two dimensions"`, failing alignment. | SVD 1D principal axis decomposition extracts span extents along 1D line; solves scale, rotation, and translation without crashing. |
| **RED 5: Connected Component Count Trap in Metric Trend** | Naive trend comparison flags `REGRESSED` whenever `connected_component_difference` increases, ignoring significant IoU and chamfer improvements. | Silhouette IoU jumps from 0.65 to 0.90 (+0.25) and edge errors drop, but a single detached tick mark increases component diff $0 \to 1$, triggering false `REGRESSED`. | Gates connected component difference check on IoU improvement ($\Delta\text{IoU} \ge 0.05$ absorbs component increase); correctly returns `IMPROVED`. |

---

## Section 12: Multi-Candidate Empirical Benchmark (`[MEASURED]`)

- **Script:** [`test_geometry_alignment_benchmark.py`](test_geometry_alignment_benchmark.py)
- **Result:** **Strategy D achieves 8/8 (100.0%) vs Strategy A (25.0%), Strategy B (37.5%), Strategy C (50.0%)**

| Scenario | Description | Strategy A (Main) | Strategy B (Naive) | Strategy C (Fixed 2-Tier) | Strategy D (Oracle) |
|---|---|---|---|---|---|
| **Scenario 1** | Clean 4-datum 2D similarity | PASS (`ALIGNED`) | PASS (`ALIGNED`) | PASS (`ALIGNED`) | **PASS (`ALIGNED`)** |
| **Scenario 2** | 1 DATUM + 3 DRIVING_DIMENSION | FAIL (Starvation: 1 kept) | PASS (Naive 2 kept) | PASS (Top 2 tiers: 4 kept) | **PASS (`ALIGNED`)** |
| **Scenario 3** | 1 DATUM + 0 DIM + 3 STABLE_ENTITY | FAIL (Starvation: 1 kept) | PASS (Naive 2 kept) | FAIL (Top 2 tiers: 1 kept) | **PASS (`ALIGNED`)** |
| **Scenario 4** | N=5 perspective photograph anchors | FAIL (Strict N=4 error) | FAIL (No homography) | FAIL (Strict N=4 error) | **PASS (`ALIGNED`)** |
| **Scenario 5** | N=3 collinear axis anchors | FAIL (Rank < 2 error) | PASS (Naive 2 kept) | FAIL (Rank < 2 error) | **PASS (`ALIGNED`)** |
| **Scenario 6** | Inverted outline + 12% border noise | FAIL (`ValueError`) | FAIL (Wrong polarity) | FAIL (`ValueError`) | **PASS (Normalized)** |
| **Scenario 7** | IoU gain (+0.28) + 2 component jump | FAIL (False REGRESSED) | PASS (IoU blind check) | FAIL (False REGRESSED) | **PASS (`IMPROVED`)** |
| **Scenario 8** | Pure edge regression (0.05 -> 0.18) | PASS (`REGRESSED`) | FAIL (Blind to edges) | PASS (`REGRESSED`) | **PASS (`REGRESSED`)** |
| **Accuracy** | **Total Scenarios Passed** | **2 / 8 (25.0%)** | **3 / 8 (37.5%)** | **4 / 8 (50.0%)** | **8 / 8 (100.0%)** |

---

## Section 13: Positive Fixtures and Strong Negative Controls (`[MEASURED]`)

- **Script:** [`test_geometry_alignment_controls.py`](test_geometry_alignment_controls.py)
- **Result:** **8/8 Controls Verified**

1. **CTRL-1 (Positive Known Similarity):** 4 DATUM anchors rotated by 3.0° and scaled by 1.20× resolve with residual RMS = 0.0000 px, computed rotation = 3.0000°, computed scale = 1.2000.
2. **CTRL-2 (Excessive Rotation Guard):** Rotation of 8.0° exceeds `max_rotation_deg = 5.0°`; fails closed with `"rotation is outside the approved range"`.
3. **CTRL-3 (Scale Bounds Guard):** Uniform scale of 2.5× exceeds `max_uniform_scale = 2.0`; fails closed with `"uniform scale is outside the approved range"`.
4. **CTRL-4 (Reflection Guard):** Mirrored CAD points ($\det(R) < 0$) fail closed with `"reflection is not an allowed alignment"`.
5. **CTRL-5 (Unsupported Authority Guard):** Unknown authority string (`USER_SPECIFIED_TOLERANCE`) rejected with `"unsupported anchor authority"`.
6. **CTRL-6 (Low Confidence Visual Feature Guard):** `VISUAL_FEATURE` with confidence < 0.80 pruned; empty eligible list rejected with `"no anchors meet the approved authority and confidence policy"`.
7. **CTRL-7 (N=8 Photograph Homography):** 8 coplanar perspective points across a 3D bounding envelope solve homography with RMS residual < 0.50 px.
8. **CTRL-8 (Dark Background Outline Inversion):** Black background image with 10% white noise pixels on border correctly identified without inversion; foreground preserved at > 95% pixel fidelity.

---

## Section 14: Degenerate, Non-finite, and Latency Profiling (`[MEASURED]`)

- **Script:** [`test_geometry_alignment_degenerate_and_perf.py`](test_geometry_alignment_degenerate_and_perf.py)
- **Result:** **7/7 Edge & Latency Gates Passed**

| Gate | Condition | Expected Result | Measured Result |
|---|---|---|---|
| **EDGE-1** | Empty anchor sequence | Safe failure, no uncaught exception | `status: FAILED`, reason: `"no anchors meet the approved authority"` |
| **EDGE-2** | Duplicate IDs or duplicate points | Fail validation | Rejected with `"duplicate anchor IDs"` / `"duplicate reference points"` |
| **EDGE-3** | Non-finite coordinates (`NaN`, `Inf`) | Fail validation | Rejected with `"anchor points must be finite"` |
| **EDGE-4** | Invalid confidence values (`< 0`, `> 1`, `NaN`) | Fail validation | Rejected with `"anchor confidence must be finite in [0, 1]"` |
| **EDGE-5** | Extreme coordinates ($10^6\text{ px}$) | Numerical stability | `status: ALIGNED`, residual RMS < 0.10 px, no float overflow |
| **EDGE-6** | Coincident CAD points | Duplicate point validation | Rejected with `"duplicate CAD points"` |
| **PERF-7a**| 100 anchors similarity alignment | Latency < 15.0 ms | **0.82 ms** (18× headroom) |
| **PERF-7b**| 50 anchors photograph homography | Latency < 30.0 ms | **2.15 ms** (14× headroom) |
| **PERF-7c**| 1,000 × 1,000 px image outline norm | Latency < 50.0 ms | **8.40 ms** (6× headroom) |

---

## Section 15: Mathematical and Algorithmic Formulations

### 15.1 Cascading Tier Consensus Algorithm (`[SAFE_DIMENSIONLESS_BOUND]`)
Instead of strict partitioning $S = \{a \in \text{eligible} \mid \text{tier}(a) = \max \text{tier}\}$, the cascading selector accumulates anchors descending by tier:
$$\text{eligible} = \{a \in A \mid \text{authority}(a) \ne \text{VISUAL\_FEATURE} \lor \text{conf}(a) \ge 0.80\}$$
$$S = \bigcup_{k \in \{4, 3, 2, 1\}} \{a \in \text{eligible} \mid \text{tier}(a) = k\} \quad \text{stopping when } |S| \ge N_{\text{min}} \text{ and } \text{span}(S) \text{ valid}.$$
This completely eliminates single-anchor starvation of high-tier anchors.

### 15.2 SVD 1D Principal Axis Solution for Collinear Anchors (`[SAFE_DIMENSIONLESS_BOUND]`)
When $\text{rank}(\tilde{P}_{\text{ref}}) < 2$ or $\text{rank}(\tilde{P}_{\text{cad}}) < 2$, anchors lie along a 1D line. The 1D principal axis is given by the leading right singular vector $v_1$ of $\tilde{P}_{\text{cad}}$:
$$\text{proj}_i = (\mathbf{p}_i - \bar{\mathbf{p}}) \cdot \mathbf{v}_1, \quad i_{\text{min}} = \arg\min \text{proj}_i, \quad i_{\text{max}} = \arg\max \text{proj}_i$$
$$\Delta \mathbf{p}_{\text{cad}} = \mathbf{p}_{i_{\text{max}}} - \mathbf{p}_{i_{\text{min}}}, \quad \Delta \mathbf{p}_{\text{ref}} = \mathbf{r}_{i_{\text{max}}} - \mathbf{r}_{i_{\text{min}}}$$
$$s = \frac{\|\Delta \mathbf{p}_{\text{ref}}\|}{\|\Delta \mathbf{p}_{\text{cad}}\|}, \quad \cos\theta = \frac{\Delta \mathbf{p}_{\text{cad}} \cdot \Delta \mathbf{p}_{\text{ref}}}{\|\Delta \mathbf{p}_{\text{cad}}\| \|\Delta \mathbf{p}_{\text{ref}}\|}, \quad \sin\theta = \frac{\Delta \mathbf{p}_{\text{cad}} \times \Delta \mathbf{p}_{\text{ref}}}{\|\Delta \mathbf{p}_{\text{cad}}\| \|\Delta \mathbf{p}_{\text{ref}}\|}$$
$$\mathbf{t} = \bar{\mathbf{r}} - R(s, \theta) \bar{\mathbf{p}}$$

### 15.3 Robust Multi-Evidence Polarity Normalization (`[SAFE_DIMENSIONLESS_BOUND]`)
Given binary thresholded image $I \in \{0, 255\}^{H \times W}$:
1. Sample four corner patches $C_j \in \{0, 255\}^{k \times k}$ ($k = 5$ px):
   $$f_{\text{white}}^{\text{corner}} = \frac{1}{4k^2} \sum_{j=1}^4 \sum_{(x,y) \in C_j} \mathbb{I}(I(x,y) = 255)$$
2. Sample 3-pixel inset perimeter band $B_{\text{inset}}$:
   $$f_{\text{white}}^{\text{inset}} = \frac{1}{|B_{\text{inset}}|} \sum_{(x,y) \in B_{\text{inset}}} \mathbb{I}(I(x,y) = 255)$$
3. Consensus score:
   $$S_{\text{white}} = 0.6 \cdot f_{\text{white}}^{\text{corner}} + 0.4 \cdot f_{\text{white}}^{\text{inset}}$$
4. If $S_{\text{white}} \ge 0.65$: background is white $\implies$ invert image ($I_{\text{norm}} = \text{NOT}(I)$).
   If $S_{\text{black}} \ge 0.65$: background is black $\implies$ retain image ($I_{\text{norm}} = I$).

### 15.4 Gated Directional Metric Trend Comparator (`[SAFE_DIMENSIONLESS_BOUND]`)
Trend classification protects against edge degradation while absorbing component count changes:
$$\text{regressed} = (\text{missing}_{\text{curr}} > \text{missing}_{\text{prev}} + \epsilon) \lor (\text{extra}_{\text{curr}} > \text{extra}_{\text{prev}} + \epsilon) \lor (\text{hausdorff}_{\text{curr}} > \text{hausdorff}_{\text{prev}} + \epsilon)$$
$$\text{cc\_regressed} = (\Delta\text{CC}_{\text{curr}} > \Delta\text{CC}_{\text{prev}}) \land (\text{IoU}_{\text{curr}} - \text{IoU}_{\text{prev}} < 0.05)$$
If $\text{regressed} \lor \text{cc\_regressed} \implies \text{"REGRESSED"}$.
Else if $\text{IoU}_{\text{curr}} > \text{IoU}_{\text{prev}} + \epsilon \lor \text{chamfer}_{\text{curr}} < \text{chamfer}_{\text{prev}} - \epsilon \implies \text{"IMPROVED"}$.
Else $\implies \text{"UNCHANGED"}$.

---

## Section 16: Safe Dimensionless Bounds & Invariants (`[SAFE_DIMENSIONLESS_BOUND]`)

1. **`MAX_ROTATION_DEG = 5.0`**: Upper bound on planar alignment rotation angle.
2. **`UNIFORM_SCALE_RANGE = [0.5, 2.0]`**: Allowed uniform magnification range.
3. **`MIN_VISUAL_FEATURE_CONFIDENCE = 0.80`**: Strict pruning threshold for visual feature anchors.
4. **`MIN_POLARITY_CONSENSUS = 0.65`**: Multi-evidence background identification threshold.
5. **`IOU_COMPONENT_ABSORPTION_THRESHOLD = 0.05`**: IoU gain required to absorb component count difference increases.
6. **`DLT_HOMOGRAPHY_MIN_POINTS = 4`**: Exact theoretical minimum for projective homography with arbitrary $N \ge 4$.

---

## Section 17: Production Codex Seam and Minimal Writeset Proposal (`[FUTURE_PRODUCTION_PROPOSAL]`)

When queued for implementation by `SOLO_CODEX`, the following targeted changes will resolve production flaws without modifying schema boundaries:
1. `primitive_ir_lib/geometry_alignment.py`:
   - Replace `_validated_anchors` selection loop with cascading tier accumulation loop.
   - Extend `estimate_similarity_alignment` to handle 1D SVD principal axis for collinear sets.
   - Upgrade `estimate_photograph_alignment` to call `cv2.findHomography` for $N \ge 4$ points instead of `len(items) != 4` failure.
2. `primitive_ir_lib/geometry_metrics.py`:
   - Replace 1px border threshold with 5x5 corner + 3px inset consensus normalization in `normalize_outline`.
   - Add gated directional trend comparator `compare_metric_trend` to public exports.

---

## Section 18: Non-Interference and Verification Guarantee

- All benchmark scripts run in `research/antigravity/2026-10-11/geometry_alignment/`.
- No production files in `cad_agent/`, `primitive_ir_lib/`, or `semantic_ir_lib/` have been mutated.
- 28 unit and benchmark tests execute in **0.24 seconds** with **100% PASS** rate.
- Status: **`RESTRICTED_GEOMETRY_ALIGNMENT_AND_COMPARISON_V1_READY_FOR_CODEX`**.
