# TECHNICAL SPECIFICATION: AUTOMATIC CALIBRATION MULTI-CANDIDATE CONSENSUS (`AUTOMATIC_CALIBRATION_CONSENSUS_V1`)

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `AUTOMATIC_CALIBRATION_CONSENSUS_EMPIRICAL`
- **Target Epic:** `AUTOMATIC_CALIBRATION_CONSENSUS_V1`
- **Subagents:** `0` (Disabled per #429 overlay)
- **Repository Checkout:** `C:\cad-agent-antigravity`
- **Base Research Branch / Commit:** `research/antigravity-2026-10-11` (`d2ebf5efa451c0d7de8ba98f7cece5b3b269ab2d`)
- **Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), PR #494 (`fix/start-tab-drawing-open-fallback`, DRAFT)
- **Production Impact:** `RESEARCH_ONLY = YES`, `PRODUCTION_FILES_CHANGED = false`

---

## Epistemic Status Legend

Throughout this specification, claims and parameters are explicitly tagged with their epistemic category:
- **`[MEASURED]`**: Direct empirical output from deterministic benchmark scripts in `research/antigravity/2026-10-11/calibration_consensus/`.
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
| `CURRENT_CALIBRATION_SCHEMA` | `primitive_ir.schema.json:208-223` (`Calibration`: required `["unit", "pixel_to_unit_scale", "origin_px", "method"]`, `additionalProperties: false`) |
| `CURRENT_CALIBRATION_MODEL_OWNER` | `primitive_ir_lib/models.py:228-251` (`Calibration`), validated in `primitive_ir_lib/validator.py:18,90-95` |
| `CURRENT_AUTO_CALIBRATION_OWNER` | `primitive_ir_lib/calibration.py:190-304` (`auto_estimate_calibration`, `find_nearest_line`, `estimate_calibration_from_reference`) |
| `CURRENT_CALIBRATION_REGISTRY_OWNER` | `primitive_ir_lib/calibration_registry.py:13-75` (`CalibrationRegistry`, `needs_verification` flag) |
| `CURRENT_ASSEMBLY_INTEGRATION` | `primitive_ir_lib/assemble.py:72-132` (`build_document` accepts pre-calibrated `Calibration` or manual scale) |
| `CURRENT_CALIBRATION_TEST_OWNER` | `primitive_ir_lib/tests/test_calibration.py` (orientation filtering tests) & `test_view_calibration.py` (scale conversion) |
| `NEW_MODULE_REQUIRED` | `NO` (All improvements belong directly inside `primitive_ir_lib/calibration.py`) |

---

## Section 11: Public Causal RED (`[MEASURED]`)

- **Script:** [`test_causal_red_calibration.py`](test_causal_red_calibration.py)
- **Result:** **5/5 Causal Failures Reproducible in Production Main Logic**

| RED Test | Production Flaw Mechanism | Measured Production Failure | Strategy D Behavior |
|---|---|---|---|
| **RED 1: Fragmented Line 60% Scale Error** | `find_nearest_line` relies on Euclidean distance between text center and line midpoint (`np.hypot(mx-tx, my-ty)`). A broken Hough fragment closer to text is preferred over the true full dimension line. | Text "1970" paired with 337px fragment (16px away) instead of true 538px line (46px away): **59.6% scale error** (`scale = 5.8457 mm/px` vs `3.6617 mm/px`). | Rejects isolated fragments via longitudinal span projection and multi-candidate consensus: **100% true scale recovery**. |
| **RED 2: Unverified Single Candidate Return** | `auto_estimate_calibration` defaults to `require_consensus = False`, returning immediately on the very first text encountered. | Two conflicting texts (scale 7.20 vs 3.66): production returns **7.20 mm/px with 0 consensus verification**. | Enforces $N \ge 2$ independent candidates before returning verified calibration. |
| **RED 3: Permissive 10% Consensus Gate** | Production `consensus_tolerance_pct = 10.0%` violates the project `AGENTS.md` invariant: "Automatic calibration's production gate is at least two independent candidates with median relative error at most 3 percent." | Candidates with **8.5% scale discrepancy** are passed as "consensus" by production. | Strictly enforces $\le 3.0\%$ gate: **Fails closed (returns `None`)**. |
| **RED 4: Sheet Number Noise Hallucination** | `classify_semantic_role` classifies any digit string as `dimension_value`. Non-dimension numbers ("09", "1") match title block borders. | Sheet number "09" paired with 200px border line: **hallucinates scale = 0.045 mm/px** (99% error). | Filters out lone small integers without dimension geometry or symbol: **100% noise rejection**. |
| **RED 5: Cross-Axis Aspect Ratio Distortion Blindness** | Production does not compare horizontal candidate scales against vertical candidate scales. | Scanned drawing with 25% non-uniform aspect distortion ($s_x = 4.0\text{ mm/px}, s_y = 5.0\text{ mm/px}$): production blindly outputs scalar scale. | Detects $|s_H - s_V| / \min(s_H, s_V) > 3.0\%$: **Fails closed (returns `None`)**. |

---

## Section 12: Fitting Strategies Empirical Benchmark (`[MEASURED]`)

- **Script:** [`test_calibration_strategies_benchmark.py`](test_calibration_strategies_benchmark.py)
- **Evaluated Strategies:**
  - **Strategy A:** Current Main (`auto_estimate_calibration`, `require_consensus=False`, `tol=10.0%`)
  - **Strategy B:** Naive Consensus (`require_consensus=True`, `tol=10.0%`)
  - **Strategy C:** Strict 3% Median Consensus (`require_consensus=True`, `tol=3.0%`)
  - **Strategy D (Selected):** Robust Multi-Axis Dimension Topology Oracle (Span projection, boundary support, 3% clustering, cross-axis consistency)

### Benchmark Results Table

| Benchmark Metric | Strategy A (Current) | Strategy B (Naive 10%) | Strategy C (Strict 3%) | Strategy D (Selected Oracle) |
|---|---|---|---|---|
| **Resolved Scale (mm/px)** | `0.0450 mm/px` | `4.0000 mm/px` | `4.0000 mm/px` | **`4.0000 mm/px`** |
| **Scale Relative Error (%)** | `98.88%` (Fatal) | `0.00%` | `0.00%` | **`0.00%`** |
| **Fragment Line Pairing Immunity (%)** | `0.0%` (Frag paired) | `80.0%` | `85.0%` | **`100.0%`** (Span checked) |
| **Sheet Number Noise Rejection (%)** | `0.0%` (Hallucinated) | `100.0%` | `100.0%` | **`100.0%`** |
| **AGENTS.md 3% Gate Compliance** | `FAIL` | `FAIL` (Allows 10%) | `PASS` (<= 3%) | **`PASS` (<= 3%)** |
| **Cross-Axis Aspect Verification** | `NO` | `NO` | `NO` | **`YES` (<= 3% check)** |
| **Mean Runtime per Call (µs)** | `19.4 µs` | `230.8 µs` | `228.5 µs` | **`223.4 µs`** |

---

## Section 13: Multi-Candidate Consensus Production Gate (`[SAFE_DIMENSIONLESS_BOUND]` & `[MEASURED]`)

- **Script:** [`test_positive_and_negative_consensus_controls.py`](test_positive_and_negative_consensus_controls.py)
- **Governing Policy (`AGENTS.md`):**
  > "Automatic calibration's production gate is at least two independent candidates with median relative error at most 3 percent."

### Consensus Formulation:
Given candidate pairs $\{(T_k, L_k)\}_{k=1}^K$ with nominal values $V_k$ and pixel lengths $P_k$:
$$s_k = \frac{V_k}{P_k}$$
1. Group sorted scales $\{s_{(1)}, s_{(2)}, \dots, s_{(K)}\}$.
2. A candidate subset $C \subseteq \{s_k\}$ forms a valid consensus cluster iff:
   $$|C| \ge 2 \quad \text{and} \quad \frac{\max_{s \in C} s - \min_{s \in C} s}{\min_{s \in C} s} \times 100\% \le 3.0\%$$
3. If no such subset exists, the pipeline **FAILS CLOSED** and returns `None`. It does not guess, extrapolate, or fall back to an unverified single candidate.

### Measured Control Results:
- `test_positive_two_candidate_horizontal`: 2 independent candidates (0.4% error) $\implies$ **PASS** (`s = 4.00 mm/px`).
- `test_positive_three_candidate_vertical`: 3 vertical candidates with discretization jitter (< 1.5% error) $\implies$ **PASS** (`s = 4.00 mm/px`).
- `test_positive_mixed_horizontal_and_vertical_consistent`: 2 horizontal + 2 vertical candidates all agreeing $\implies$ **PASS** (`s = 4.00 mm/px`).
- `test_negative_single_candidate_fails_closed`: Exactly 1 candidate ($N=1$) $\implies$ **FAILS CLOSED** (`None`).
- `test_negative_relative_error_exceeds_3_percent`: 2 candidates with 3.73% relative error ($> 3.0\%$ gate) $\implies$ **FAILS CLOSED** (`None`).
- `test_negative_mixed_view_conflict_without_majority`: Mixed-scale sheet ($1:40$ vs $1:20$) with 1 candidate each $\implies$ **FAILS CLOSED** (`None`).
- `test_negative_all_noise_numbers`: Only sheet/revision numbers ("09", "1") $\implies$ **FAILS CLOSED** (`None`).

---

## Section 14: Longitudinal Span Projection & Line Extent Matching (`[SYNTHETIC_DISCRIMINATOR]`)

- When searching for the dimension line corresponding to a dimension text $T$:
  1. Let text bounding box center be $(t_{cx}, t_{cy})$.
  2. For candidate segment $L = (p_1, p_2)$ with length $P = \|p_2 - p_1\|$ and unit direction $\vec{u} = (p_2 - p_1) / P$:
     - Longitudinal projection coordinate:
       $$t_{\text{proj}} = (t_{cx} - p_{1x}) u_x + (t_{cy} - p_{1y}) u_y$$
     - Perpendicular distance:
       $$d_\perp = |-(t_{cx} - p_{1x}) u_y + (t_{cy} - p_{1y}) u_x|$$
  3. **Longitudinal Span Constraint:**
     $$-15.0\text{ px} \le t_{\text{proj}} \le P + 15.0\text{ px}$$
     Text must project within the longitudinal extent of the candidate line. This prevents pairing text with adjacent or non-overlapping fragments.
  4. **Perpendicular Proximity Constraint:**
     $$d_\perp \le 40.0\text{ px}$$
  5. **Minimum Segment Length:**
     $$P \ge 15.0\text{ px}$$

---

## Section 15: Cross-Axis Aspect Ratio Consistency Validation (`[SAFE_DIMENSIONLESS_BOUND]`)

- Engineering drawings scanned on flatbed or rotary scanners may suffer from mechanical roller slip or aspect ratio distortion.
- If both horizontal and vertical dimension candidates are present:
  $$\bar{s}_H = \operatorname{median}(\{s_{k,H}\}), \quad \bar{s}_V = \operatorname{median}(\{s_{k,V}\})$$
  $$\Delta_{\text{axis}} = \frac{|\bar{s}_H - \bar{s}_V|}{\min(\bar{s}_H, \bar{s}_V)} \times 100\%$$
- **Cross-Axis Rule:**
  - If $N_H \ge 2$ and $N_V \ge 2$, require $\Delta_{\text{axis}} \le 3.0\%$.
  - If $\Delta_{\text{axis}} > 3.0\%$, the sheet has non-uniform scaling; **FAIL CLOSED** (`None`) to prevent emitting invalid scalar CAD calibration.

---

## Section 16: Degenerate, Non-Finite & Scalability Benchmark (`[MEASURED]`)

- **Script:** [`test_calibration_degenerate_nonfinite_and_perf.py`](test_calibration_degenerate_nonfinite_and_perf.py)

| Test Case | Inputs Provided | Observed Behavior | Status |
|---|---|---|---|
| `test_empty_inputs_safety` | `[]`, `[texts] + []`, `[] + [lines]` | Returns `None` cleanly | **PASS** |
| `test_zero_and_negative_dimension_values` | $V = 0.0\text{ mm}$, $V = -50.0\text{ mm}$ | Returns `None` (zero/negative values rejected) | **PASS** |
| `test_non_finite_coordinates_and_values` | `NaN`, `Inf` in coords or parsed values | Safe execution, non-finite values rejected | **PASS** |
| `test_zero_length_points_and_micro_lines` | $L = 0.0\text{ px}$, $L = 10^{-6}\text{ px}$ | No `ZeroDivisionError`, returns `None` | **PASS** |
| `test_extreme_coordinate_scale` | Coordinates at $10^6\text{ px}$ | Numerical precision preserved ($< 0.0001\text{ mm/px}$ error) | **PASS** |
| `test_large_scale_runtime_profiling` | 50 Texts $\times$ 200 Lines | **7.77 ms execution time** ($< 50\text{ ms}$ budget) | **PASS** |

---

## Section 17: Parameter & Threshold Inventory

| Parameter Name | Value | Epistemic Classification | Rationale & Invariant |
|---|---|---|---|
| `max_relative_error_pct` | `3.0%` | `[SAFE_DIMENSIONLESS_BOUND]` | Invariant gate mandated by `AGENTS.md`. Median relative error must be $\le 3\%$. |
| `min_consensus_candidates` | `2` | `[SAFE_DIMENSIONLESS_BOUND]` | Invariant gate mandated by `AGENTS.md`. At least two independent candidates required. |
| `max_perp_distance_px` | `40.0 px` | `[NEEDS_REAL_SCAN_CALIBRATION]` | Maximum lateral distance between dimension text center and dimension line axis. |
| `min_segment_length_px` | `15.0 px` | `[SYNTHETIC_DISCRIMINATOR]` | Minimum candidate line length to avoid micro-fragment noise and division instability. |
| `span_margin_px` | `15.0 px` | `[SYNTHETIC_DISCRIMINATOR]` | Longitudinal tolerance outside line endpoints within which text may project. |
| `cardinal_angle_tol_deg` | `20.0 deg` | `[SAFE_DIMENSIONLESS_BOUND]` | Orientation tolerance when matching rotated text (90°/270°) to vertical lines. |
| `min_numeric_dimension_val` | `10.0` | `[SYNTHETIC_DISCRIMINATOR]` | Cutoff below which lone 1-2 digit numbers without dimension symbol are deemed sheet/item tags. |
| `cross_axis_tolerance_pct` | `3.0%` | `[SAFE_DIMENSIONLESS_BOUND]` | Maximum permissible aspect ratio discrepancy between horizontal and vertical axes. |

---

## Section 18: Proposed Production Write-Set Contract (`[FUTURE_PRODUCTION_PROPOSAL]`)

The entire empirical calibration consensus mechanism can be integrated into production with **ZERO schema alterations**, **ZERO external dependencies**, and **ZERO new module creations**.

### Target Production Files:
1. `primitive_ir_lib/calibration.py`:
   - Enforce `require_consensus = True` by default in `auto_estimate_calibration`.
   - Update default `consensus_tolerance_pct` from `10.0%` to `3.0%` (matching `AGENTS.md`).
   - Upgrade `find_nearest_line` to validate longitudinal span projection (`-15 <= t_proj <= length + 15`) and filter fragmented lines.
   - Filter sheet numbers ("09", "1") from candidate dimension texts.
   - Add cross-axis aspect ratio consistency validation.
2. `primitive_ir_lib/calibration_registry.py`:
   - Keep unverified records auditable; ensure records failing the 3% gate receive `needs_verification = True`.
3. `primitive_ir_lib/tests/test_calibration.py`:
   - Port the 5 causal RED tests and 14 regression tests into the production test suite.

---

## Section 19: Real-Scan Generalization Limits (`[UNPROVEN_REAL_SCAN_GENERALIZATION]`)

1. **Mixed Scale Sheets (Section Views):** When a sheet contains detail views at $1:5$ and an overall view at $1:40$, the global consensus gate correctly rejects emitting a single page-wide scale. Per-view calibration (`docs/superpowers/specs/2026-07-21-per-view-calibration-design.md`) must be used to partition views before calibration.
2. **Severely Warped Blueprint Folds:** Severe scanner skew or physical paper fold creases may induce localized non-affine distortion ($> 3\%$). Under such conditions, Strategy D safely fails closed.

---

## Section 20: Epistemic Summary & Ready-for-Codex Gate

- **`EPIC`**: `AUTOMATIC_CALIBRATION_CONSENSUS_V1`
- **`STATUS`**: `READY_FOR_CODEX`
- **`TESTS_PASSING`**: **19 / 19 (100.0%)** across 4 test suites
- **`ZERO_PRODUCTION_FILES_MODIFIED`**: **Verified** (`cad_agent/` and `primitive_ir_lib/` untouched)
- **`DURABLE_SPECIFICATION_WRITTEN`**: **Yes** (this document)
- **`BLOCKER`**: None
