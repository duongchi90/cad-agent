# TECHNICAL SPECIFICATION: ARC, FILLET & CURVED CONSTRAINT DETECTION (`ARC_FILLET_CONSTRAINT_DETECTION_V1`)

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `ARC_FILLET_CONSTRAINT_DETECTION_EMPIRICAL`
- **Target Epic:** `ARC_FILLET_CONSTRAINT_DETECTION_V1`
- **Subagents:** `0` (Disabled per #429 overlay)
- **Repository Checkout:** `C:\cad-agent-antigravity`
- **Base Research Branch / Commit:** `research/antigravity-2026-10-11` (`66a3ea9fe19d015d5a0026a809710048c2471768`)
- **Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), PR #494 (`fix/start-tab-drawing-open-fallback`, DRAFT)
- **Production Impact:** `RESEARCH_ONLY = YES`, `PRODUCTION_FILES_CHANGED = false`

---

## Epistemic Status Legend

Throughout this specification, claims and parameters are explicitly tagged with their epistemic category:
- **`[MEASURED]`**: Direct empirical output from deterministic benchmark scripts in `research/antigravity/2026-10-11/arc_constraint_detection/`.
- **`[SAFE_DIMENSIONLESS_BOUND]`**: Invariant mathematical or topological ratio that does not depend on DPI, scanner hardware, or real scan calibration.
- **`[SYNTHETIC_DISCRIMINATOR]`**: Threshold or boundary derived from synthetic geometry benchmarks that separates positive and negative controls.
- **`[NEEDS_REAL_SCAN_CALIBRATION]`**: Absolute millimeter-domain threshold that must be tuned against physical paper/scanner engineering drawing tolerances.
- **`[INFERENCE]`**: Analytical or geometric deduction from measured evidence and mathematical invariants.
- **`[FUTURE_PRODUCTION_PROPOSAL]`**: Recommended design contract and minimum writeset for future `SOLO_CODEX` implementation (not yet implemented in production).
- **`[UNPROVEN_REAL_SCAN_GENERALIZATION]`**: Behavior on physical paper/scanner engineering drawings that remains unproven because private/customer drawings were lawfully excluded from research runs.

---

## Section 10: Fresh-Read Current Owners (`[MEASURED]`)

| Field | Verified Value |
|---|---|
| `CURRENT_CONSTRAINT_OWNER` | `semantic_ir_lib/constraint_detection.py:1-260` (`detect_constraints`, `detect_circle_constraints`, `_point_to_infinite_line_distance`) |
| `CURRENT_ASSEMBLY_INTEGRATION` | `semantic_ir_lib/assemble.py:52-53` (only gathers `line` and `circle` primitives, completely drops `arc` primitives) |
| `CURRENT_CONSTRAINT_TEST_OWNER`| `tests/semantic_ir/test_constraint_detection.py` (only tests line-line and line-circle pairs) |
| `SMALLEST_EXISTING_OWNER` | `semantic_ir_lib/constraint_detection.py` |
| `NEW_MODULE_REQUIRED` | `NO` (All capabilities integrate directly into `semantic_ir_lib/constraint_detection.py` and `assemble.py`) |
| `NEW_SCHEMA_REQUIRED` | `NO` (Uses existing `Constraint` model with types `tangent`, `concentric`, `coincident_endpoint`, `equal_length`) |
| `NEW_DEPENDENCY_REQUIRED` | `NO` (Pure `math` standard library and existing `Point2D`/`Primitive` models) |
| `ASSEMBLY_CHANGE_REQUIRED` | `YES` (`assemble.py` line 52-53 must include `p.type == "arc"` in curved primitive collection) |

---

## Section 11: Public Causal RED (`[MEASURED]`)

- **Script:** [`test_causal_red_arc_constraints.py`](test_causal_red_arc_constraints.py)
- **Result:** **5/5 Causal Failures Reproducible in Production Main Logic**

| RED Test | Production Flaw Mechanism | Measured Production Failure | Strategy D Behavior |
|---|---|---|---|
| **RED 1: Distant Line Tangent False Positive** | `constraint_detection.py:228`: Uses `_point_to_infinite_line_distance`. Line segment 100mm away collinear with tangent axis has distance=10mm, gap=0.0mm. | Strategy A returns `tangent`: **falsely attaches distant lines to circles**. | Two-stage check evaluates contact point $p_{contact}$ on infinite line; distance to segment is 100mm > 5mm: **correctly rejects**. |
| **RED 2: Line-Arc Fillet Transition Omitted** | `assemble.py:52-53` drops `arc` primitives; `detect_circle_constraints` does not accept `arc`. | Fillet arc connecting horizontal and vertical lines: **Strategy A returns 0 constraints**. | Bounded projection and sweep containment: **detects 2 tangencies and 2 coincident endpoints**. |
| **RED 3: Arc-Arc Tangent S-Curve Omitted** | No pairwise curved-to-curved tangency solver exists in `constraint_detection.py`. | S-curve transition between 2 tangent arcs: **Strategy A returns 0 constraints**. | Circle center distance comparison ($d \approx r_1 + r_2$ or $|r_1 - r_2|$) + sweep verification: **detects external tangency**. |
| **RED 4: Mounting Lug Concentricity Omitted** | `detect_circle_constraints` only tests `circle-circle` pairs; `circle-arc` pairs are skipped. | Bolt hole circle inside concentric semicircular lug arc: **Strategy A returns 0 constraints**. | Multi-primitive curved center distance: **detects concentricity with confidence 1.0**. |
| **RED 5: Out-of-Sweep Contact False Tangency** | Naive Strategy B tests infinite circle contact, ignoring arc sweep $[\theta_{start}, \theta_{end}]$. | Line tangent to underlying circle at $270^\circ$, but arc only exists in $[0^\circ, 90^\circ]$: **Strategy B emits false tangency**. | Angular sweep interval check validates contact point angle: **correctly rejects out-of-sweep tangency**. |

---

## Section 12: Multi-Candidate Empirical Benchmark (`[MEASURED]`)

- **Script:** [`test_arc_constraint_benchmark.py`](test_arc_constraint_benchmark.py)
- **Evaluated Strategies:**
  - **Strategy A:** Current Production Main (`semantic_ir_lib/constraint_detection.py`)
  - **Strategy B:** Naive Infinite Projection Matcher (treats arcs as full circles, unconstrained line extent)
  - **Strategy C:** Endpoint-Only Proximity Matcher (only flags tangency if endpoints touch)
  - **Strategy D:** Bounded Sweep Contact Oracle (Two-stage infinite/segment projection, sweep angle containment, orthogonality guard, multi-primitive concentricity, coincident endpoints, equal radius)

| Scenario # | Description | Strategy A | Strategy B | Strategy C | Strategy D (Selected) |
|---|---|---|---|---|---|
| **Scenario 1** | Corner fillet joining 2 perpendicular lines | FAIL (0 cst) | PASS (2 tan) | PASS (2 tan) | **PASS (2 tan, 2 coinc)** |
| **Scenario 2** | Slotted plate (2 lines + 2 semicircular arcs) | FAIL (0 cst) | PASS (4 tan) | PASS (4 tan) | **PASS (4 tan, 1 eq_len)** |
| **Scenario 3** | Concentric lug with bolt hole | FAIL (0 cst) | PASS (1 conc) | FAIL (0 conc) | **PASS (1 concentric)** |
| **Scenario 4** | Compound S-curve (2 tangent arcs) | FAIL (0 cst) | PASS (1 tan) | PASS (1 tan) | **PASS (1 tangent)** |
| **Scenario 5** | Distant collinear line rejection | FAIL (False Pos) | FAIL (False Pos) | PASS (rejected) | **PASS (0 FP, rejected)** |
| **Scenario 6** | Out-of-sweep contact line rejection | PASS (omitted) | FAIL (False Pos) | PASS (rejected) | **PASS (0 FP, rejected)** |
| **Scenario 7** | Touching non-tangent corner (radial spoke) | PASS (omitted) | PASS (rejected) | FAIL (False Pos) | **PASS (0 tan, 1 coinc)** |
| **Scenario 8** | Equal radius multi-fillet (4 R5 arcs) | FAIL (0 cst) | FAIL (0 cst) | FAIL (0 cst) | **PASS (6 equal_length)** |
| **Scorecard** | **Success Rate** | **1 / 8 (12.5%)** | **4 / 8 (50.0%)** | **5 / 8 (62.5%)** | **8 / 8 (100.0%)** |

---

## Section 13: Positive Fixtures and Strong Negative Controls (`[MEASURED]`)

- **Script:** [`test_arc_constraint_controls.py`](test_arc_constraint_controls.py)
- **Result:** **8/8 Tests Passed Cleanly**

1. **Positive Controls (`[MEASURED]`):**
   - **Closed Rounded Rectangle:** 4 lines + 4 corner arcs $\to$ detects all 8 tangency transitions, all 8 coincident endpoints, and all 6 equal radius constraints.
   - **Keyhole Feature:** Center bore circle + 2 tangent neck lines $\to$ detects both upper and lower neck tangencies.
   - **Triple Concentric Feature:** 1 circle + 2 concentric arcs $\to$ detects all 3 pairwise concentric constraints ($C_1-A_1, C_1-A_2, A_1-A_2$).

2. **Negative Controls (`[MEASURED]`):**
   - **Parallel Line-Arc Offset:** Line parallel to tangent line shifted outward by $12\text{ mm}$ ($> 5\text{ mm}$ tolerance) $\to$ **0 tangencies detected**.
   - **Non-Concentric Offset Lug:** Bolt hole shifted by $8\text{ mm}$ ($> 5\text{ mm}$ tolerance) from lug center $\to$ **0 concentric constraints detected**.
   - **Orthogonal Radial Spoke:** Line points straight toward circle center intersecting perimeter $\to$ **0 tangencies detected**.
   - **Disjoint Arcs with Gap:** 2 facing arcs with $15\text{ mm}$ gap $\to$ **0 tangencies detected**.
   - **Unequal Radii Arcs:** R10 arc vs R25 arc (150% difference $> 3\%$ tolerance) $\to$ **0 equal radius constraints detected**.

---

## Section 14: Degenerate, Non-Finite & Ambiguity Edge Cases (`[MEASURED]`)

- **Script:** [`test_arc_constraint_degenerate_and_perf.py`](test_arc_constraint_degenerate_and_perf.py)
- **Result:** **8/8 Tests Passed Cleanly**

1. **Zero-Radius Arc/Circle:** $R = 0.0$ safely filtered out without division by zero.
2. **Negative-Radius Arc/Circle:** $R < 0$ safely filtered out.
3. **Zero-Length Line Segment:** $p_1 == p_2$ safely filtered out.
4. **Zero-Sweep Arc:** $\theta_{start} == \theta_{end}$ correctly handled without false positives.
5. **Full $360^\circ$ Sweep Arc:** Arc with $[0^\circ, 360^\circ]$ correctly matches like full circle.
6. **Non-Finite Coordinates & Radii:** Primitives containing `NaN`, `+Inf`, `-Inf` are safely skipped via `math.isfinite()` validation; zero crashes and zero corrupted constraints.
7. **Empty and Single Primitive Inputs:** Safely return empty list `[]`.
8. **BBox Extraction Safety:** `_safe_bbox` prevents `ValueError: cannot convert float NaN to integer`.

---

## Section 15: Runtime Performance & Computational Complexity (`[MEASURED]`)

- **100-Primitive Complex Drawing Benchmark:**
  - **Workload:** 40 lines, 30 arcs, 30 circles ($4,950$ pairwise evaluations).
  - **Latency:** **< 15 ms** total wall-clock execution time (measured: $12.4\text{ ms}$), far exceeding the $< 50\text{ ms}$ performance budget.
  - **Per-Pair Throughput:** $\approx 2.5\ \mu\text{s}$ per primitive pair.
- **Algorithmic Complexity:**
  - Line-curved tangency: $O(N_{lines} \times N_{curved})$ with fast scalar projection.
  - Curved-curved relations: $O(N_{curved}^2 / 2)$ with fast center Euclidean distance comparison.
  - Spatial partitioning (future): Can be indexed via bounding box R-tree if $N > 1000$.

---

## Section 16: Parameter & Threshold Epistemic Classification

| Parameter | Value | Epistemic Classification | Rationale & Proof |
|---|---|---|---|
| `angle_tolerance_deg` | $3.5^\circ$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Invariant angular bound: accommodates raster-to-vector Taubin circle fitting discretization slant while rejecting oblique crossings ($> 15^\circ$). |
| `length_tolerance_percent` | $3.0\%$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Project-wide consensus standard: matches CAD Agent standard for dimensional equality and automatic calibration. |
| `sweep_angle_containment_tol` | $3.0^\circ$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Topological invariant: accommodates endpoint pixel rounding at arc terminals without accepting exterior tangent points. |
| `bounded_segment_guard` | $t \in [-0.05, 1.05]$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Invariant ratio: requires the perpendicular tangent projection to lie within the segment corridor or within distance tolerance of an endpoint. |
| `distance_tolerance_mm` | $5.0\text{ mm}$ | **`[SYNTHETIC_DISCRIMINATOR]`** / **`[NEEDS_REAL_SCAN_CALIBRATION]`** | Default assembly tolerance in current main. Must be scaled by drawing calibration factor in production pipelines. |

---

## Section 17: Selected Production Architecture & Minimum Writeset (`[FUTURE_PRODUCTION_PROPOSAL]`)

When promoted to production by `SOLO_CODEX`, the following modifications should be applied:

1. **`semantic_ir_lib/assemble.py`**:
   - Lines 52-53: Expand curved primitive collection from `[p for p in primitives if p.type == "circle"]` to include `p.type == "arc"`.
2. **`semantic_ir_lib/constraint_detection.py`**:
   - Replace naive `_point_to_infinite_line_distance` in `detect_circle_constraints` with two-stage bounded contact projection.
   - Expand `detect_circle_constraints` to `detect_curved_constraints`, supporting `line-arc`, `arc-arc`, and `circle-arc` pairs.
   - Add arc sweep containment check `_is_angle_in_sweep`.
   - Add arc-arc tangency (external $d \approx r_1 + r_2$ and internal $d \approx |r_1 - r_2|$).
   - Add coincident endpoints for `line-arc` connections.
   - Add `equal_length` constraint for arcs and circles sharing identical radii within `length_tolerance_percent`.
3. **`tests/semantic_ir/test_constraint_detection.py`**:
   - Add tests covering line-arc fillet tangency, circular slots, arc-arc S-curves, and concentric lugs.

---

## Section 18: Codex Implementation Contract & Safety Guarantees

- **No Schema Breakage:** Produces standard `semantic_ir_lib.models.Constraint` instances with standard constraint types (`tangent`, `concentric`, `coincident_endpoint`, `equal_length`).
- **Fail-Closed Principle:** Primitives with non-finite values or degenerate geometry are silently dropped, emitting no spurious constraints.
- **Strict Determinism:** Pure 2D analytical geometry; zero nondeterministic floating-point approximations.

---

## Section 19: Risk Analysis & Rollback Plan

- **Risk:** High-density drawing with thousands of small fillet arcs could produce redundant `equal_length` constraints.
- **Mitigation:** Production solver can cluster identical radii into radius groups rather than quadratic pairwise enumeration if $N_{arcs} > 100$.
- **Rollback:** `git revert` on the isolated commit in `semantic_ir_lib/constraint_detection.py` and `semantic_ir_lib/assemble.py`.

---

## Section 20: Verified Status Ledger Update

- `EPIC`: `ARC_FILLET_CONSTRAINT_DETECTION_V1`
- `STATUS`: `READY_FOR_CODEX`
- `TESTS_PASSING`: 29 / 29 research tests
- `BENCHMARK_SCORE`: 100% (8/8 scenarios vs 12.5% in production Strategy A)
- `PERFORMANCE`: < 15 ms across 100 primitives ($4,950$ pairwise evaluations)
- `PRODUCTION_FILES_MUTATED`: 0 (`RESEARCH_ONLY = YES`)
