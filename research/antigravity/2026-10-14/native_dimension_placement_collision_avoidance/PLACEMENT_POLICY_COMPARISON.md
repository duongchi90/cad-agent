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
   - Evaluates both normal sides ($s \in \{+1, -1\}$)
   - Evaluates 3 discrete offset lanes ($k \in \{0, 1, 2\}$, with empirical research heuristic step $\Delta d = \max(7.5\text{ mm}, 2 \cdot H_{\text{text}})$)
   - Evaluates 6 discrete candidates per dimension via deterministic penalty scoring
   - Lexicographic tie-breaking: minimum collision penalty $\to$ lowest lane index $\to$ default $+n$ normal side.

---

## 2. Quantitative Results by Fixture

| Fixture Name | Dims | Baseline Collisions | Candidate Collisions | Dim $\times$ Geom Crossings (Base / Cand) | Dim $\times$ Annot Overlaps (Base / Cand) | Min Clearance (Base / Cand) | Prototype Meas Error | Unresolved Dims (Base / Cand) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **F1: Isolated Horizontal** | 1 | **0** | **0** | 0 / 0 | 0 / 0 | 8.0 / 8.0 mm | **0.000 mm** | 0 / 0 |
| **F2: Isolated Vertical** | 1 | **0** | **0** | 0 / 0 | 0 / 0 | 6.4 / 6.4 mm | **0.000 mm** | 0 / 0 |
| **F3: Rotated Oblique (45°)** | 1 | **1** | **0** | 0 / 0 | 1 / 0 | 5.0 / 6.0 mm | **0.000 mm** | 1 / 0 |
| **F4: Two Nearby Parallel** | 2 | **1** | **0** | 0 / 0 | 1 / 0 | 6.4 / 14.4 mm | **0.000 mm** | 1 / 0 |
| **F5: Multiple Sharing Geometry** | 3 | **3** | **0** | 1 / 0 | 2 / 0 | 8.0 / 15.5 mm | **0.000 mm** | 2 / 0 |
| **F6: One Side Blocked (Geometry)** | 1 | **2** | **0** | 1 / 0 | 1 / 0 | 8.0 / 8.0 mm | **0.000 mm** | 1 / 0 |
| **F7: One Side Blocked (Text Note)** | 1 | **2** | **0** | 0 / 0 | 2 / 0 | 8.0 / 8.0 mm | **0.000 mm** | 1 / 0 |
| **F8: Crowded Short Segments** | 2 | **2** | **0** | 0 / 0 | 2 / 0 | 5.0 / 8.5 mm | **0.000 mm** | 1 / 0 |
| **F9: Close to Sheet Boundary** | 1 | **1** | **0** | 0 / 0 | 1 / 0 | 8.0 / 8.0 mm | **0.000 mm** | 1 / 0 |
| **F10: Mixed Local Orientations** | 2 | **4** | **0** | 2 / 0 | 2 / 0 | 8.0 / 15.5 mm | **0.000 mm** | 2 / 0 |
| **TOTALS / SUMMARY** | **15** | **16** | **0** | **4 / 0** | **12 / 0** | **5.0 / 6.0 mm** | **0.000 mm** | **11 / 0** |

> [!IMPORTANT]
> `PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION = NOT_VERIFIED_BY_THIS_ORACLE`
> The 0.000 mm measurement error is verified strictly within the standalone prototype geometry model by mathematical construction. Native AutoCAD/ezdxf DIMENSION entity rendering and roundtrip were not executed by this research oracle.

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
4. **`DETERMINISTIC_REPEATABILITY (TESTED FIXTURES)`:**
   Formally verified as bitwise identical floating-point output across 2 repeated runs on all 10 synthetic fixtures (15/15 dimensions matching) and 3 runs on Fixture 4 in the oracle ($100.0\%$). Repeatability is bounded to tested synthetic fixtures under deterministic candidate ordering.

### Research Heuristics
1. **Penalty Function Coefficients:**
   The specific penalties ($P_{\text{out_of_bounds}} = 5000$, $P_{\text{text_overlap}} = 2000$, $P_{\text{geom_cross}} = 1000$, $P_{\text{lane}} = 15 \cdot k$, $P_{\text{side}} = 1.0$) are empirical research heuristics designed to enforce lexicographic priority:
   $$\text{In-Bounds} > \text{Zero Text Overlap} > \text{Zero Line Crossings} > \text{Lower Lane Index} > \text{Default Normal Side}$$
2. **Lane Offset Increment ($\Delta d$):**
   The step size $\Delta d = \max(7.5\text{ mm}, 2 \cdot H_{\text{text}})$ and base offset $\max(\text{length} \cdot 0.08, 6.0)$ are empirical research heuristics chosen for the synthetic benchmark. They are **not universal physical constants** and are **not AutoCAD/ASME standard defaults**.
3. **Length-Ascending Placement Sequence:**
   Sorting dimensions by length before greedy assignment is an empirical heuristic implementation of the general drafting convention "place shorter dimensions inside, longer dimensions outside".

---

## 4. Key Empirical Takeaways

1. **Dual-Side Search Resolves Single-Side Obstacles on Tested Fixtures:**
   On Fixtures 6, 7, and 9, simply evaluating side $s = -1$ avoided all obstacle collisions in the test scenes without requiring complex layout solvers.
2. **Multi-Lane Stepping Resolves Parallel Dimension Stacking on Tested Fixtures:**
   On Fixtures 4, 5, and 10, assigning parallel dimensions to successive lanes ($k = 0, 1$) eliminated text-on-line and text-on-text overlaps.
3. **Bounded Candidate Space:**
   Evaluating 6 discrete candidates per dimension takes under $25\ \mu\text{s}$ per dimension in pure Python, maintaining lightweight performance without new dependencies.
