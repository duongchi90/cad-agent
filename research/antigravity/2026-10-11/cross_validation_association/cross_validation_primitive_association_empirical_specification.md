# Cross-Validation Primitive Association Empirical Specification (V1)

**Status:** `READY_FOR_CODEX`  
**Epic Identifier:** `CROSS_VALIDATION_PRIMITIVE_ASSOCIATION_V1`  
**Topic Group:** `24`  
**Target Subsystem:** `primitive_ir_lib` / `cad_agent`  
**Author:** Antigravity Autonomous Research  
**Evaluated Branch:** `research/antigravity-2026-10-11`  

---

## 1. Role, Mode, and Epic Identification

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `LONG_RUNNING_CONTINUOUS_AUTONOMOUS_RESEARCH`
- **Epic:** `CROSS_VALIDATION_PRIMITIVE_ASSOCIATION_V1`
- **Execution Policy:** Read-only production inspection; empirical research scripts exclusively under `research/antigravity/2026-10-11/cross_validation_association/`. Zero native AutoCAD mutation.

---

## 2. Current Production Owners

1. **Primary Consumer & Logic Owner:**
   - [`primitive_ir_lib/cross_validation.py:35-111`](file:///C:/cad-agent-antigravity/primitive_ir_lib/cross_validation.py#L35-L111): `cross_validate()`
2. **Upstream Nearest-Line Selector:**
   - [`primitive_ir_lib/calibration.py:73-145`](file:///C:/cad-agent-antigravity/primitive_ir_lib/calibration.py#L73-L145): `find_nearest_line()`
3. **Data Contracts & Models:**
   - [`primitive_ir_lib/models.py:188-216`](file:///C:/cad-agent-antigravity/primitive_ir_lib/models.py#L188-L216): `CrossValidation`
   - [`primitive_ir_lib/models.py:218-246`](file:///C:/cad-agent-antigravity/primitive_ir_lib/models.py#L218-L246): `Calibration`
   - [`primitive_ir_lib/geometry_extraction.py:37-57`](file:///C:/cad-agent-antigravity/primitive_ir_lib/geometry_extraction.py#L37-L57): `RawLine`, `RawCircle`
   - [`primitive_ir_lib/text_extraction.py:38-49`](file:///C:/cad-agent-antigravity/primitive_ir_lib/text_extraction.py#L38-L49): `RawText`

---

## 3. Current Behavior & Architectural Gap

In the CadAgent two-source cross-verification architecture ("use Vision to obtain dimension values, use OpenCV to confirm geometry positions and lengths"), `cross_validate()` in [`primitive_ir_lib/cross_validation.py`](file:///C:/cad-agent-antigravity/primitive_ir_lib/cross_validation.py) is responsible for finding the supporting geometry for each `dimension_value` text and flagging `confirmed`, `conflict`, or `unverified`.

However, the production implementation suffers from 5 critical mathematical and topological defects:
1. **0° Text Angle Bypass:** [`primitive_ir_lib/calibration.py:114`](file:///C:/cad-agent-antigravity/primitive_ir_lib/calibration.py#L114) explicitly defines `apply_angle_filter = text.rotation_deg % 180.0 != 0.0`. When `text.rotation_deg == 0.0` (standard horizontal text, representing > 90% of drafting annotations), angular filtering is **completely disabled**, permitting orthogonal vertical lines (90°) to compete.
2. **Midpoint Euclidean Distance Trap:** Candidates are ranked by $\sqrt{(m_x - t_x)^2 + (m_y - t_y)^2}$. When dimension text is placed near one end of a span (staggered dimensioning), the true line's midpoint is far away, allowing nearby orthogonal witness lines or adjacent short feature edges to win.
3. **150px Radius Starvation:** A hardcoded `max_distance_px = 150.0` midpoint threshold silently discards long dimension lines (> 300px) when text is staggered near an extremity.
4. **Non-Exclusive Greedy Stealing:** In chained dimensions, `cross_validate()` matches each text independently. If a true dimension line is missing or broken, subsequent texts steal the preceding text's line, causing duplicate associations and false conflicts.
5. **Circular & Curved Primitive Blindness:** `cross_validate()` accepts only `raw_lines: List[RawLine]`. Diameter (`Ø`) and radius (`R`) callouts cannot be cross-validated against `RawCircle` or `RawArc`, resulting in 100% loss of curved dimension verification.

---

## 4. Deterministic Causal RED Reproduction

The failure modes are deterministically reproduced in [`test_causal_red_cross_validation.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/cross_validation_association/test_causal_red_cross_validation.py):

| RED Test | Trigger Condition | Current Production Outcome | Ground Truth & Strategy D Outcome |
|---|---|---|---|
| **RED-1** | Horizontal text "200" (0°) near 60px vertical witness line (90°) and 200px horizontal dim line | Picks vertical witness line (`witness_vert_60`), reports false `conflict` (delta = 70.0%) | Binds to `dim_line_200`, reports `confirmed` (delta = 0.0%) |
| **RED-2** | Staggered text "500" at x=160 on 500px line [100, 600]; short 60px feature line at x=150 | Discards 500px line (> 150px midpoint dist); picks short line, reports `conflict` | Evaluates perpendicular corridor (15px), binds to `long_dim_500`, reports `confirmed` |
| **RED-3** | Chained dimensions: Span 1 (100px) and Span 2 (60px, missing geometry) | Assigns Span 1 line to **both** Text 1 and Text 2, triggering false conflict for Text 2 | Optimal bipartite assignment enforces 1-to-1: Text 1 confirmed, Text 2 `unverified` |
| **RED-4** | Circular callout "Ø50" on circle (r=25px) with nearby 40px centerline | Ignores circle completely; pairs with 40px centerline, reports `conflict` | Multi-geometry pool matches circle, measures diameter 50mm, reports `confirmed` |
| **RED-5** | Stacked baseline rails (lower 200px at y=120, upper 300px at y=150); text "300" between rails | Midpoint distance picks lower rail (26.9px vs 71.0px), reports `conflict` | Multi-objective corridor + length score picks upper rail, reports `confirmed` |

---

## 5. Causal Mechanisms

1. **Angular Modulo Trap (`calibration.py:114`):**
   ```python
   apply_angle_filter = text.rotation_deg % 180.0 != 0.0
   ```
   For $0^\circ$, `0.0 != 0.0` evaluates to `False`. For $180^\circ$, `0.0 != 0.0` evaluates to `False`. The filter is only active for strictly diagonal or vertical text, leaving horizontal text completely vulnerable to orthogonal line capture.
2. **Conflation of Perpendicular and Axial Distance:**
   A dimension text belongs to a line if its perpendicular offset is small ($d_\perp \le 40\text{ px}$) and its axial projection falls within the span ($s \in [-30, L+30]\text{ px}$). The Euclidean distance to the line's midpoint is $\sqrt{d_\perp^2 + (s - L/2)^2}$. For large $L$, $(s - L/2)^2$ dominates, penalizing valid staggered text.
3. **Independent Local Greedy Search:**
   `[find_nearest_line(t, raw_lines) for t in raw_texts]` lacks global mutual exclusion. The search space is a bipartite graph between texts and geometric primitives; independent argmin allows many-to-one degenerate mappings.
4. **Homogeneous Geometry Signature:**
   `def cross_validate(raw_texts, raw_lines)` takes only lines, hardcoding an assumption that mechanical drawings only contain linear dimensions.

---

## 6. Product Impact

1. **Catastrophic False Conflicts:** Completely valid drawings trigger reviewer alarms because horizontal dimensions pair with witness lines, producing false conflict rates exceeding 60% on staggered layouts.
2. **Reviewer Overhead:** Human reviewers are forced to manually inspect and override false conflicts.
3. **Curved Geometry Blindness:** Shaft diameters, bore holes, bolt pitches, and fillets are completely unverified by the IR pipeline.

---

## 7. Evaluated Candidate Strategies

- **Strategy A (Current Production Baseline):**
  - Midpoint Euclidean distance $\le 150\text{ px}$.
  - Angle filter disabled on $0^\circ$ text.
  - Greedy independent per-text matching.
  - Lines only.
- **Strategy B (Angle-Enforced Midpoint):**
  - Fixes $0^\circ$ bypass by enforcing angle tolerance on all texts.
  - Retains midpoint Euclidean distance and greedy line-only search.
- **Strategy C (Perpendicular-Axial Corridor Matcher):**
  - Computes perpendicular distance $d_\perp = |(\mathbf{t} - \mathbf{p}_1) \cdot \mathbf{n}|$ and axial projection $s = (\mathbf{t} - \mathbf{p}_1) \cdot \mathbf{u}$.
  - Enforces $d_\perp \le 40\text{ px}$ and $s \in [-30, L+30]\text{ px}$.
  - Retains greedy 1-pass matching and line-only candidate pool.
- **Strategy D (Multimodal Bipartite Association Oracle):**
  - **Multimodal Candidates:** Unifies `RawLine`, `RawCircle`, and `RawArc`.
  - **Symbol Awareness:** Callout prefixes (`Ø`, `R`) steer matching to diameters ($2R$) and radii ($R$).
  - **Multi-Objective Cost:** Combines normalized perpendicular offset, axial centering, angular alignment, and dimension value consistency:
    $$\text{Cost} = 1.0 \cdot \frac{d_\perp}{D_{\text{perp\_max}}} + 0.3 \cdot \frac{|s - L/2|}{L/2 + \delta} + 0.2 \cdot \frac{\Delta\theta}{\theta_{\text{tol}}} + 0.05 \cdot \min(\text{delta\_pct}, 100)$$
  - **Global Optimal Bipartite Matching:** Solves minimum weight bipartite assignment ($\min \sum \text{Cost}_{ij}$) guaranteeing 1-to-1 association without line stealing.
  - **Ambiguity Guard:** Flags `ambiguous` if two conflicting candidates have near-identical cost ($\Delta_{\text{cost}} \le 0.05$).

---

## 8. Empirical Benchmark Comparison

Measured across 8 comprehensive drawing scenarios in [`test_cross_validation_benchmark.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/cross_validation_association/test_cross_validation_benchmark.py):

| Scenario | Strategy A (Baseline) | Strategy B (Angle-Enforced) | Strategy C (Corridor) | Strategy D (Oracle) |
|---|---|---|---|---|
| **1. Standard Centered Horizontal** | 100% (Confirmed) | 100% (Confirmed) | 100% (Confirmed) | **100% (Confirmed)** |
| **2. Staggered Near Witness Line** | 0% (Conflict on Witness) | 100% (Confirmed) | 100% (Confirmed) | **100% (Confirmed)** |
| **3. Staggered Long Line (400px)** | 0% (Stolen by Short Line) | 0% (Stolen by Short Line) | 0% (Stolen by Short Line) | **100% (Confirmed)** |
| **4. Chained Dimensions (Mutual Exclusion)** | 0% (Duplicate Stealing) | 0% (Duplicate Stealing) | 0% (Duplicate Stealing) | **100% (Exclusive / Unverified)** |
| **5. Circular Diameter Callout (Ø40)** | 0% (Blind to Circle) | 0% (Blind to Circle) | 0% (Blind to Circle) | **100% (Confirmed Ø40)** |
| **6. Radial Callout on Fillet Arc (R15)** | 0% (Blind to Arc) | 0% (Blind to Arc) | 0% (Blind to Arc) | **100% (Confirmed R15)** |
| **7. Stacked Baseline Rails** | 0% (Conflict on Lower) | 0% (Conflict on Lower) | 100% (Confirmed) | **100% (Confirmed)** |
| **8. Aligned Diagonal Dimension (45°)** | 100% (Confirmed) | 100% (Confirmed) | 100% (Confirmed) | **100% (Confirmed)** |
| **Overall Accuracy (8 Scenarios)** | **25.0% (2/8)** | **37.5% (3/8)** | **50.0% (4/8)** | **100.0% (8/8)** |

---

## 9. Boundary Controls Matrix

Verified in [`test_cross_validation_controls.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/cross_validation_association/test_cross_validation_controls.py):

1. **CTRL-1 (Positive Orthogonal H & V Pair):** Simultaneous horizontal and vertical dimensions confirm without cross-talk.
2. **CTRL-2 (Negative Distractor Distance):** Text placed $> 40\text{ px}$ from any line fails safe to `unverified`.
3. **CTRL-3 (Negative Perpendicular Line Rejection):** Horizontal text (0°) near an isolated vertical line (90°) returns `unverified`, rejecting false association.
4. **CTRL-4 (Positive Circle Diameter with Scale):** Circle with radius 25px, scale 2.5 mm/px confirms against text "Ø125".
5. **CTRL-5 (Positive Arc Radius with Scale):** Arc with radius 40px, scale 1.25 mm/px confirms against text "R50".
6. **CTRL-6 (Negative Conflicting Diameter):** Text "Ø75" on circle with diameter 50mm reports `conflict` (delta = 33.3%).
7. **CTRL-7 (Ambiguity Guard):** Text positioned symmetrically between two conflicting rails (100mm vs 200mm) reports `ambiguous`.
8. **CTRL-8 (Tolerance Threshold Boundary):** Line length 100px: text 102.8mm (delta = 2.72%) confirms; text 103.5mm (delta = 3.38%) reports conflict.

---

## 10. Degenerate, Numeric Safety & Performance

Verified in [`test_cross_validation_degenerate_and_perf.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/cross_validation_association/test_cross_validation_degenerate_and_perf.py):

1. **EDGE-1 (Empty Inputs):** Empty collections return empty results; geometry starvation returns `unverified`.
2. **EDGE-2 (Zero Parsed Value):** Hallucinated OCR "00" or 0.0 values return `unverified` with `geometry_id=""`.
3. **EDGE-3 (Micro & Zero-Length Primitives):** Micro-segments ($L < 1.0\text{ px}$) and zero-radius circles ($R < 1.0\text{ px}$) are filtered, preventing division by zero.
4. **EDGE-4 (Non-Finite Coordinates):** `NaN` and `Inf` coordinates in geometry or text fail safe to `unverified` without unhandled exceptions.
5. **EDGE-5 (Extreme Coordinate Magnitudes):** $10^6\text{ px}$ coordinate values maintain IEEE 754 float precision.
6. **EDGE-6 (Negative Dimension Values):** Negative values (e.g. -50.0) fail safe to `unverified`.
7. **PERF-7 (Scalability & Throughput):** 50 dimension texts against 200 lines, 30 circles, and 20 arcs execute in **< 15 ms** (well within the 40 ms budget).

---

## 11. Parameter Epistemics

| Parameter | Value | Classification | Justification |
|---|---|---|---|
| `MAX_PERP_DIST_PX` | `40.0 px` | `SAFE_DIMENSIONLESS_BOUND` | Covers standard drafting text offset (5–25px) with margin for font height. |
| `AXIAL_MARGIN_PX` | `30.0 px` | `SAFE_DIMENSIONLESS_BOUND` | Accommodates text placement outside narrow dimension spans. |
| `MAX_RADIAL_DIST_PX` | `60.0 px` | `SAFE_DIMENSIONLESS_BOUND` | Accommodates leader lines and radius callout text placement. |
| `ANGLE_TOLERANCE_DEG` | `20.0 deg` | `SAFE_DIMENSIONLESS_BOUND` | Accommodates slight raster skew and slanted lettering while rejecting orthogonal lines. |
| `MATCH_THRESHOLD_PERCENT` | `3.0 %` | `SAFE_DIMENSIONLESS_BOUND` | Fixed production gate defined in `AGENTS.md` and Phase 1 specifications. |
| `AMBIGUITY_MARGIN` | `0.02` | `SYNTHETIC_DISCRIMINATOR` | Bounded cost separation between dual candidates representing conflicting spans. |

---

## 12. Reuse-First Architecture Recommendation for Codex

- **Target Production Owners:**
  - Update [`primitive_ir_lib/calibration.py:73-145`](file:///C:/cad-agent-antigravity/primitive_ir_lib/calibration.py#L73-L145): Replace midpoint Euclidean distance with perpendicular-axial corridor calculation and fix `apply_angle_filter = True` for all texts.
  - Extend [`primitive_ir_lib/cross_validation.py:35-111`](file:///C:/cad-agent-antigravity/primitive_ir_lib/cross_validation.py#L35-L111): Accept optional `raw_circles: Optional[List[RawCircle]] = None` and `raw_arcs: Optional[List[RawArc]] = None`, and integrate bipartite matching.
- **Architecture Requirements:**
  - `NEW_MODULE_REQUIRED = NO` (extends existing `cross_validation.py` and `calibration.py`).
  - `NEW_SCHEMA_REQUIRED = NO` (compatible with `CrossValidation` and `primitive_ir.schema.json`).
  - `NEW_DEPENDENCY_REQUIRED = NO` (uses standard library and existing `scipy.optimize.linear_sum_assignment` or pure-Python greedy fallback).
  - `ASSEMBLY_CHANGE_REQUIRED = YES` (pass circles and arcs from `RawGeometry` into `cross_validate`).
  - `BUILDER_CHANGE_REQUIRED = NO`.
  - `REPAIR_CHANGE_REQUIRED = NO`.
  - `REVIEWER_CHANGE_REQUIRED = NO`.

---

## 13. Research File Inventory & SHA-256 Signatures

| Filename | Type | Status | SHA-256 Checksum | Description |
|---|---|---|---|---|
| [`cross_validation_engine.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/cross_validation_association/cross_validation_engine.py) | Engine / Oracle | `RESEARCH_ONLY` | `33ef57f51af2a903afe01da2b6f4dd62d952e2010280abacab6eef69b4f3d90c` | Shared reference implementation of Strategies A-D for cross-validation primitive association |
| [`test_causal_red_cross_validation.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/cross_validation_association/test_causal_red_cross_validation.py) | Causal RED Test | `RESEARCH_ONLY` | `3ddb4e40114e3715a3b5ec202ca81f84af2e63ea1bfe511d96df116e1902ac64` | Public causal RED reproducing 5 baseline failure modes on production cross_validation.py and calibration.py |
| [`test_cross_validation_benchmark.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/cross_validation_association/test_cross_validation_benchmark.py) | Strategy Benchmark | `RESEARCH_ONLY` | `a002cc6c6c1352c3dd953717c0379aa1c67095e7bd5411b0f47227a69fcc742f` | Empirical benchmark comparing Strategies A-D across 8 realistic drawing scenarios |
| [`test_cross_validation_controls.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/cross_validation_association/test_cross_validation_controls.py) | Controls Test | `RESEARCH_ONLY` | `8419bd83351b36f2ceae4e8e2d4b66a385b9352be008d664d93c506ff3f1069f` | 8 positive and negative boundary controls (orthogonal, distractor, circle, arc, ambiguity) |
| [`test_cross_validation_degenerate_and_perf.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/cross_validation_association/test_cross_validation_degenerate_and_perf.py) | Edge & Perf Benchmark | `RESEARCH_ONLY` | `7f064f9f71d40a58261e758ea237d9bf396d4227e6799bc3c7dfd19bd76dfd4b` | Empty, zero-value, micro, non-finite coords, 10^6 px scale, and latency profiling (< 15ms) |
| [`cross_validation_primitive_association_empirical_specification.md`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/cross_validation_association/cross_validation_primitive_association_empirical_specification.md) | Specification | `RESEARCH_ONLY` | Authoritative in `MANIFEST.md` | Complete empirical specification for Cross-Validation Primitive Association (`CROSS_VALIDATION_PRIMITIVE_ASSOCIATION_V1`) |

---

## 14. Next Ranked Research Boundary Recommendation

Following completion of `CROSS_VALIDATION_PRIMITIVE_ASSOCIATION_V1`, the next highest-priority boundary is:
- **`SOURCE_SUPPORT_CURVED_PRIMITIVE_VERIFIER_V1`** in [`cad_agent/source_support_verifier.py`](file:///C:/cad-agent-antigravity/cad_agent/source_support_verifier.py): External visual proposal verifier hard-rejects all non-LINE primitives (`type != "LINE"` fails at line 189), has rigid fail-closed ValueError on individual primitive failure rather than per-primitive result schema, lacks arc-length circle/arc raster sampling, and uses fixed 220 threshold that fails dashed/hidden lines.
