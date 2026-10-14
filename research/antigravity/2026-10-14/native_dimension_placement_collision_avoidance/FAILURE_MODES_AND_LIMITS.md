# FAILURE_MODES_AND_LIMITS: Native Dimension Placement Hazards (REA-023)

- **Document ID:** `REA_DIM_PLACEMENT_FAILURES_V2`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Capability:** `NATIVE_DIMENSION_PLACEMENT_COLLISION_AVOIDANCE` (REA-023)
- **Evidence Tier:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`

---

## 1. Overview of Placement Hazards

While the discrete multi-lane dual-side candidate policy successfully avoids collisions on the 10 evaluated synthetic fixtures, automated CAD dimension placement possesses inherent limitations. 0 collisions is strictly an empirical outcome on these tested scenes, not a universal guarantee. This document details each structural failure mode, boundary conditions, and explicit scope limits.

---

## 2. Structural Failure Modes

### Failure Mode 1: Both Sides Blocked (Symmetric Entrapment / Pocket Saturation)
- **Hazard:** When a measured segment lies inside a confined internal channel or pocket where obstacles exist at distances $\le d_{\text{max}}$ on *both* normal sides $+n$ and $-n$.
- **Behavior:** All 6 candidate positions accumulate hard collisions ($\text{hard\_collision\_count} \ge 1$).
- **Handling in Candidate Policy:** The policy selects the least-penalized candidate using the lexicographic candidate key $(\text{hard\_collision\_count}, \text{soft\_penalty\_score}, \text{lane\_idx}, \text{side\_preference})$. Because every candidate incurs at least one hard collision ($\text{hard\_collision\_count} \ge 1$), the dimension is marked unresolved and cannot be placed collision-free.
- **Limitation:** In dense mechanical views, automated placement without leader lines or view clipping cannot eliminate all collisions when clearance is physically unavailable.

### Failure Mode 2: Lane Escape from Local Context (Excessive Offset)
- **Hazard:** To avoid obstacles, candidate lanes step outward: $d_k = d_0 + k \cdot \Delta d$. At $k = 2$, offset can reach $25\text{--}35\text{ mm}$.
- **Behavior:** In dense drawings with neighboring views, an excessively high lane offset may place the dimension closer to an unrelated component than to the measured feature.
- **Drafting Standard Conflict:** ASME Y14.5 states dimensions should be placed near the view that shows the feature in true shape. Moving dimensions too far into outer lanes compromises visual association.

### Failure Mode 3: Greedy Order-Dependence
- **Hazard:** The candidate policy places dimensions sequentially in a greedy order (sorted by length ascending).
- **Behavior:** Dimension $A$ placed first consumes a preferred lane, forcing subsequent Dimension $B$ into an outer lane or opposite side, even if placing $B$ first would have yielded a lower overall composite penalty.
- **Scope Limit:** Resolving order-dependence would require a global combinatorial search (NP-hard in general graph layout). The greedy heuristic was deliberately chosen to avoid complex solver bloat, accepting that globally optimal stacking is not achieved.

### Failure Mode 4: Text Footprint Geometry and Native Font Extents
- **Hazard:** Approximation of dimension text clearance footprint.
- **Orientation-Aware Resolution (REA-023 Upgrade):**
  - REA-023 has resolved the unrotated AABB limitation (`C_AABB_ORIENTATION_ARTIFACT`).
  - Candidate scoring and scene evaluation now use an **orientation-aware text rectangle** aligned with the dimension line vector $\mathbf{u} = (\Delta x/L, \Delta y/L)$ and unit normal $\mathbf{n} = ((-\Delta y/L)\cdot s, (\Delta x/L)\cdot s)$.
  - This eliminates false collision artifacts for long dimension text on vertical and oblique dimensions (verified in Test 10 with 52 mm text maintaining 6.25 mm clearance from measured geometry).
- **Residual Native Font Uncertainty:**
  - In AutoCAD, exact text bounding extents depend on font metrics, style definitions (`STANDARD` vs `ROMANS`), character kerning, and DIMSTYLE variables (`DIMTXT`, `DIMSCALE`, `DIMGAP`) that require native CAD render evaluation (`NATIVE_AUTOCAD_RESULT = NOT_EVALUATED_BY_THIS_RESEARCH`).
  - Synthetic benchmark uses `DEFAULT_SYNTHETIC_TEXT_WIDTH_MM = 12.0` and `DEFAULT_SYNTHETIC_TEXT_HEIGHT_MM = 3.5` explicitly labeled `SYNTHETIC_RESEARCH_STYLE_PROXY`.

### Failure Mode 5: Boundary Containment Failure in Narrow Sheet Margins
- **Hazard:** A drawing sheet has small title block margins ($\le 5\text{ mm}$).
- **Behavior:** If a measured line is $3\text{ mm}$ from the border, placing a dimension on the outer side triggers a sheet out-of-bounds hard collision ($\text{hard\_collision\_count} \ge 1$). If the inner side is also blocked by part geometry, every candidate falls into the hard collision class, preventing collision-free placement.

### Failure Mode 6: Segment Orientation Canonicalization Gap (H1)
- **Hazard:** Measured segments $(P_1, P_2)$ vs $(P_2, P_1)$ define opposite intrinsic normal directions.
- **Classification:** `REPRESENTATION_CANONICALIZATION_GAP`.
- **Property:** When side preference is correspondingly matched ($s = +1$ for $(P_1, P_2)$ vs $s = -1$ for $(P_2, P_1)$), the physical text rectangle corner points are strictly identical modulo cyclic vertex ordering (verified in Test 10.D).

---

## 3. Explicit Disclaimers and Non-Generalization

> [!IMPORTANT]
> **RESULT CLASSIFICATION TIERS:**
> - **`CANONICAL_SYNTHETIC_RESULT`:** 0 collisions across 10 fixtures with default synthetic proxy text ($12.0\times 3.5\text{ mm}$).
> - **`ADVERSARIAL_LONG_TEXT_RESULT`:** 0 collisions across all 10 fixtures under wide text ($19.5\text{ mm}$ and $52.0\text{ mm}$).
> - **`NATIVE_AUTOCAD_RESULT`:** `NOT_EVALUATED_BY_THIS_RESEARCH` (native CAD rendering, font kerning, and binary DIMENSION roundtrip require future integration testing).
>
> **UNIVERSAL_SPACING_CONSTANT = NOT_PROVEN.**
> The lane step increment $\Delta d = \max(7.5\text{ mm}, 2 \cdot H_{\text{text}})$ and candidate base offset formula $d_0 = \max(L \cdot 0.08, 6.0\text{ mm})$ (vs baseline $5.0\text{ mm}$) are **research heuristics** chosen for the synthetic benchmark. They do NOT constitute an all-scale universal drafting constant or AutoCAD vendor default.
>
> **COLLISION_FREE_GUARANTEE = NOT_PROVEN.**
> Zero collisions is the measured result across the 10 synthetic fixtures evaluated. The discrete policy cannot guarantee collision-free placement when physical clearance is absent on both sides across all lanes.
>
> **PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION = NOT_VERIFIED_BY_THIS_ORACLE.**
> Prototype measurement error = 0.000 mm is verified strictly within the standalone prototype geometry model by algebraic construction. Native AutoCAD/ezdxf DIMENSION entity rendering and roundtrip were not executed by this research oracle.
>
> **SYNTHETIC_SUCCESS != PROFESSIONAL_DRAFTING_QUALITY.**
> Zero collisions on the 10 synthetic fixtures demonstrates that dual-side search and multi-lane stepping eliminate trivial fixed-offset collisions. It does NOT prove that generated drawings meet full professional human drafting aesthetics across arbitrary multi-view complex assemblies.
>
> **PRODUCTION_TRANSFER_AUTHORIZED = NO.**
> This capability remains a `RESEARCH_PRIOR`. No modification to `dxf_builder_lib/builder.py` is authorized absent a measured product RED on real drawing comparisons.
