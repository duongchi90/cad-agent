# PLACEMENT_POLICY_COMPARISON: Native Dimension Placement Benchmark (REA-023)

- **Document ID:** `REA_DIM_PLACEMENT_COMPARISON_V2`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Capability:** `NATIVE_DIMENSION_PLACEMENT_COLLISION_AVOIDANCE` (REA-023)
- **Evidence Tier:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`

---

## 1. Executive Summary & Benchmark Design

This benchmark compares the current production baseline against a lightweight, deterministic multi-lane dual-side candidate policy across 10 canonical synthetic engineering fixtures.

### Algorithms Compared
1. **Baseline (`Baseline_Fixed_Offset`):**
   - Single left-hand normal: $\mathbf{n} = (-\Delta y/L, \Delta x/L)$
   - Fixed proportional offset: $d = \max(L \cdot 0.08, 5.0\text{ mm})$
   - No obstacle evaluation, no alternative side, no lane stacking.
2. **Candidate Policy (`Candidate_Deterministic_MultiLane`):**
   - Canonical spec sorting: length ascending, tie-broken by endpoints and spec_id ($\text{spec\_sort\_key}$, independent of input list order)
   - Evaluates both normal sides ($s \in \{+1, -1\}$)
   - Evaluates 3 discrete offset lanes ($k \in \{0, 1, 2\}$, with empirical research heuristic step $\Delta d = \max(7.5\text{ mm}, 2 \cdot H_{\text{text}})$ and base floor $\max(L \cdot 0.08, 6.0\text{ mm})$)
   - Evaluates 6 discrete candidates per dimension via two-level deterministic scoring:
     $$\text{Candidate Key} = (\text{hard\_collision\_count}, \text{soft\_penalty\_score}, \text{lane\_idx}, \text{side\_preference})$$
   - Primary key = $\text{hard\_collision\_count}$ strictly prioritizes zero hard collisions over non-zero hard collisions, regardless of soft crossings (resolving H20).

---

## 2. Quantitative Results by Fixture

All values in this table match `benchmark_results.json` exactly (regenerated from code):

| Fixture Name | Dims | Baseline Collisions | Candidate Collisions | Dim $\times$ Geom Crossings (Base / Cand) | Dim $\times$ Annot Overlaps (Base / Cand) | Extension Crossings (Base / Cand) | Min Clearance (Base / Cand) | Prototype Meas Error | Unresolved Dims (Base / Cand) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **F1: Isolated Horizontal** | 1 | **0** | **0** | 0 / 0 | 0 / 0 | 0 / 0 | 8.0 / 8.0 mm | **0.000 mm** | 0 / 0 |
| **F2: Isolated Vertical** | 1 | **0** | **0** | 0 / 0 | 0 / 0 | 0 / 0 | 6.4 / 6.4 mm | **0.000 mm** | 0 / 0 |
| **F3: Rotated Oblique (45°)** | 1 | **1** | **0** | 0 / 0 | 1 / 0 | 0 / 0 | 5.0 / 6.0 mm | **0.000 mm** | 1 / 0 |
| **F4: Two Nearby Parallel** | 2 | **1** | **0** | 1 / 0 | 0 / 0 | 2 / 0 | 6.4 / 6.4 mm | **0.000 mm** | 1 / 0 |
| **F5: Multiple Sharing Geometry** | 3 | **1** | **0** | 1 / 0 | 0 / 0 | 0 / 0 | 5.0 / 6.0 mm | **0.000 mm** | 2 / 0 |
| **F6: One Side Blocked (Geometry)** | 1 | **2** | **0** | 2 / 0 | 0 / 0 | 0 / 0 | 3.0 / 8.0 mm | **0.000 mm** | 1 / 0 |
| **F7: One Side Blocked (Text Note)** | 1 | **2** | **0** | 0 / 0 | 2 / 0 | 0 / 0 | 8.0 / 8.0 mm | **0.000 mm** | 1 / 0 |
| **F8: Crowded Short Segments** | 2 | **7** | **0** | 3 / 0 | 4 / 0 | 2 / 1 | 5.0 / 6.0 mm | **0.000 mm** | 2 / 0 |
| **F9: Close to Sheet Boundary** | 1 | **1** | **0** | 0 / 0 | 1 / 0 | 0 / 0 | 8.0 / 8.0 mm | **0.000 mm** | 1 / 0 |
| **F10: Mixed Local Orientations** | 2 | **2** | **0** | 2 / 0 | 0 / 0 | 2 / 0 | 6.4 / 6.4 mm | **0.000 mm** | 1 / 0 |
| **TOTALS / SUMMARY** | **15** | **17** | **0** | **9 / 0** | **8 / 0** | **6 / 1** | **3.0 / 6.0 mm** | **0.000 mm** | **10 / 0** |

- **Baseline Unresolved Scenes:** 8 / 10 failed (F3, F4, F5, F6, F7, F8, F9, F10).
- **Candidate Unresolved Scenes:** 0 / 10 failed (all 10 synthetic scenes resolved with 0 hard collisions).

> [!IMPORTANT]
> `PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION = NOT_VERIFIED_BY_THIS_ORACLE`
> The 0.000 mm prototype measurement error is verified strictly within the standalone prototype geometry model by mathematical construction. Native AutoCAD/ezdxf DIMENSION entity rendering and roundtrip were not executed by this research oracle.

---

## 3. Analysis of Metric Distinctions: Formal Properties vs Research Heuristics

### Formally Defined Geometric Properties
1. **`MEASUREMENT_ERROR (PROTOTYPE)`:**
   Defined as $|L_{\text{dim}} - L_{\text{true}}|$, where $L_{\text{dim}} = \|\vec{P}_2 - \vec{P}_1\|$.
   Because definition points $p_1$ and $p_2$ are strictly immutable in `compute_dimension_geometry`, this error is **formally identical to 0.0 by construction**. Moving the dimension line `base` along the normal vector does not and cannot alter the prototype measurement. Native production preservation remains `NOT_VERIFIED_BY_THIS_ORACLE`.
2. **`DIMENSION_TO_GEOMETRY_CROSSINGS`:**
   Formally defined via 2D segment-segment intersection using exact orientation tests.
3. **`DIMENSION_TO_ANNOTATION_OVERLAPS`:**
   Formally defined via axis-aligned bounding box and segment-box intersection.
4. **`EXTENSION_UNWANTED_CROSSINGS`:**
   Formally defined via segment-segment intersection between extension witness lines and non-measured model geometry or other dimension lines.
5. **`DETERMINISTIC_REPEATABILITY (TESTED FIXTURES)`:**
   Formally verified as bitwise/full-field identical output across all `PlacedDimension` fields across 2 repeated runs on all 10 synthetic fixtures (15/15 dimensions matching) and 3 runs on Fixture 4 in the oracle ($100.0\%$). Repeatability is bounded to tested synthetic fixtures under canonical spec sorting.

### Research Heuristics
1. **Actual Scoring Penalties from Code:**
   Candidate scoring classifies violations into hard collisions and soft penalties:
   - **Hard Collisions:**
     - Sheet out-of-bounds: $P_{\text{out\_of\_bounds}} = \text{Hard}$
     - Dimension line crossing geometry: $P_{\text{geom\_cross}} = \text{Hard}$
     - Dimension text overlapping geometry: $P_{\text{text\_geom}} = \text{Hard}$
     - Dimension line or text overlapping annotation obstacles: $P_{\text{annot\_overlap}} = \text{Hard}$
     - Dimension line crossing placed dimension line: $P_{\text{dim\_dim}} = \text{Hard}$
     - Text overlapping placed text or dimension line: $P_{\text{text\_overlap}} = \text{Hard}$
   - **Soft Penalties:**
     - Extension lines crossing non-measured geometry: $P_{\text{ext\_geom}} = 150.0$ each
     - Extension lines crossing placed dimension lines: $P_{\text{ext\_dim}} = 300.0$ each
     - Dimension line crossing placed extension lines (symmetric): $P_{\text{dim\_ext}} = 300.0$ each
     - Lane stacking penalty: $P_{\text{lane}} = 15.0 \cdot k$
     - Normal side tie-breaker: $P_{\text{side}} = 1.0$ (when $s = -1$)
   - **Selection Ordering:** $(\text{hard\_count}, \text{soft\_score}, \text{lane\_idx}, \text{side\_preference})$.
2. **Base Floor and Lane Offset Increment ($\Delta d$):**
   - Candidate prototype uses base offset $d_0 = \max(L \cdot 0.08, 6.0\text{ mm})$ and lane step $\Delta d = \max(7.5\text{ mm}, 2 \cdot H_{\text{text}})$.
   - Production baseline uses base offset $d_0 = \max(L \cdot 0.08, 5.0\text{ mm})$ and zero alternative lanes.
   - The increase in floor from $5.0\text{ mm}$ to $6.0\text{ mm}$ is an **empirical research heuristic model change**, not an AutoCAD or ASME standard.
3. **Canonical Spec Sorting:**
   Specs are sorted by $\text{spec\_sort\_key} = (\text{length}, \min(p_1, p_2), \max(p_1, p_2), \text{spec\_id})$ to achieve input-list order independence.

---

## 4. Key Empirical Takeaways

1. **Dual-Side Search Resolves Single-Side Obstacles on Tested Fixtures:**
   On Fixtures 6, 7, and 9, simply evaluating side $s = -1$ avoided all obstacle collisions in the test scenes without requiring complex layout solvers.
2. **Multi-Lane Stepping Resolves Parallel Dimension Stacking on Tested Fixtures:**
   On Fixtures 4, 5, 8, and 10, assigning parallel dimensions to non-conflicting sides ($s = \pm 1$) or successive lanes ($k = 0, 1, 2$) eliminated text-on-line and text-on-text overlaps.
3. **Bounded Candidate Space:**
   Evaluating 6 discrete candidates per dimension takes under $25\ \mu\text{s}$ per dimension in pure Python, maintaining lightweight performance without new dependencies.
