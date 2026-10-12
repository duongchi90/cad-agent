# TECHNICAL SPECIFICATION: OFFLINE DIMENSION CLUSTER TOPOLOGY AND ATTACHMENT (`OFFLINE_DIMENSION_CLUSTER_TOPOLOGY_AND_ATTACHMENT_V1`)

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `DIMENSION_ATTACHMENT_EMPIRICAL`
- **Target Epic:** `OFFLINE_DIMENSION_CLUSTER_TOPOLOGY_AND_ATTACHMENT_V1`
- **Subagents:** `0` (Disabled per #429 overlay)
- **Repository Checkout:** `C:\cad-agent-antigravity`
- **Base Research Branch / Commit:** `research/antigravity-2026-10-11` (`38bf8db958050b049b71efb6f0248e560f0c32c0`)
- **Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), PR #494 (`fix/start-tab-drawing-open-fallback`, DRAFT)
- **Production Impact:** `RESEARCH_ONLY = YES`, `PRODUCTION_FILES_CHANGED = false`

---

## Epistemic Status Legend

Throughout this specification, claims and parameters are explicitly tagged with their epistemic category:
- **`[MEASURED]`**: Direct empirical output from deterministic benchmark scripts in `research/antigravity/2026-10-11/dimension_attachment/`.
- **`[SAFE_DIMENSIONLESS_BOUND]`**: Invariant mathematical, geometric, or topological property that does not depend on DPI, scanner hardware, or real scan calibration.
- **`[SYNTHETIC_DISCRIMINATOR]`**: Threshold or boundary derived from synthetic geometry benchmarks separating positive from negative controls.
- **`[NEEDS_REAL_SCAN_CALIBRATION]`**: Absolute millimeter-domain threshold that must be tuned against physical paper/scanner engineering drawing tolerances.
- **`[INFERENCE]`**: Analytical or geometric deduction from measured evidence and mathematical invariants.
- **`[FUTURE_PRODUCTION_PROPOSAL]`**: Recommended design contract and minimum writeset for future `SOLO_CODEX` implementation (not yet implemented in production).
- **`[UNPROVEN_REAL_SCAN_GENERALIZATION]`**: Behavior on physical paper/scanner engineering drawings that remains unproven because private/customer drawings were lawfully excluded from research runs.

---

## Section 10: Fresh-Read Current Owners (`[MEASURED]`)

| Field | Verified Value |
|---|---|
| `CURRENT_OBSERVER_OWNER` | `primitive_ir_lib/dimension_observer.py:69-83, 231-301, 358-375` (`_merge_boxes`, `_outer_extension_points`, `_attachment_candidates`, `observe_dimension_cluster`) |
| `CURRENT_TEST_OWNER` | `primitive_ir_lib/tests/test_dimension_observer.py:1-418` |
| `CURRENT_CONTRACT_SCHEMA` | `cad_agent/visual_contracts.py:dimension_register` (requires `status in ["CONFIRMED", "UNRESOLVED", "CONFLICT"]`, `confidence >= 0.85` for confirmed) |
| `SMALLEST_EXISTING_OWNER` | `primitive_ir_lib/dimension_observer.py` |
| `NEW_MODULE_REQUIRED` | `NO` (Modifies private helpers in `primitive_ir_lib/dimension_observer.py`) |
| `NEW_SCHEMA_REQUIRED` | `NO` (Visual contract schema `dimension_register` is completely preserved) |
| `NEW_DEPENDENCY_REQUIRED` | `NO` (Uses existing standard library and math tools) |
| `ASSEMBLY_CHANGE_REQUIRED` | `NO` |
| `BUILDER_CHANGE_REQUIRED` | `NO` |

---

## Section 11: Public Causal RED (`[MEASURED]`)

- **Script:** [`test_causal_red_dimension_attachment.py`](test_causal_red_dimension_attachment.py)
- **Result:** **5/5 Causal Failures Reproducible in Production Main Logic**

| RED Test | Production Flaw Mechanism | Measured Production Failure | Strategy D Behavior |
|---|---|---|---|
| **RED 1: Slanted Extension Line Overshoot Selection** | `_outer_extension_points` measures distance to `line[0]` instead of segment distance. A slight 8px raster slant causes overshoot endpoint to be farther from `line[0]` than workpiece end. | Strategy A picks overshoot point `(348, 20)` into empty space instead of workpiece point `(338, 100)`. | Computes Euclidean distance to dimension line segment via `point_to_segment_distance()`, correctly selecting workpiece point `(338, 100)`. |
| **RED 2: Standard 300 DPI Drafting Gap Rejection** | `proximity = math.exp(-sum(distances) / 20.0)` hardcodes 20px divisor without scale awareness. ASME/ISO standard 1.5mm gap (18px) decays proximity to 0.165. | Confidence drops to **0.624 < 0.85**, falsely marking valid dimension as `status: UNRESOLVED` / `attachment_unresolved`. | Scale-aware tolerance `max_gap_px = 2.0 * px_per_mm` absorbs drafting gap, yielding proximity **1.0** and confidence **0.95 >= 0.85**. |
| **RED 3: Single-Pass Greedy Cluster Merge Failure** | `_merge_boxes` executes a single greedy loop with `break` upon finding an overlap. Lacks transitive closure. | Merging 3 transitive boxes `[(10, 10, 30, 30), (50, 10, 70, 30), (25, 15, 55, 35)]` leaves **2 overlapping boxes** `[(10, 10, 55, 35), (50, 10, 70, 30)]`. | Disjoint Set Union (DSU) connected components merges all transitive boxes into **1 tight bounding box** `[(10, 10, 70, 35)]`. |
| **RED 4: Non-Zero Page Crop Offset Mismatch** | `observe_dimension_cluster` compares crop-local geometry coordinates `[0..w, 0..h]` directly against page-global anchor coordinates without adding cluster bbox offset `(x0, y0)`. | Anchor distances exceed 200px; confidence collapses to ~0.0; attachment fails to resolve. | Translates crop-local endpoints by `(x0, y0)` into page coordinates before anchor distance matching, resolving attachment with confidence >= 0.85. |
| **RED 5: Inverted Anchor Ordering Blind Acceptance** | `orientation_compatibility` uses `abs(dot)` between line direction and anchor vector, making reversed anchor vectors score identically to forward vectors. | Inverted anchor pair (`DATUM_B -> DATUM_A`) receives identical 1.0 orientation score. | Enforces positive topological alignment along dimension line direction vector, rejecting inverted permutations. |

---

## Section 12: Multi-Candidate Empirical Benchmark (`[MEASURED]`)

- **Script:** [`test_dimension_attachment_benchmark.py`](test_dimension_attachment_benchmark.py)
- **Evaluated Strategies:**
  - **Strategy A:** Current Production Main (`primitive_ir_lib/dimension_observer.py`)
  - **Strategy B:** Naive Distance Snapping (Euclidean distance only, no orientation or view check)
  - **Strategy C:** Fixed Pixel Radius Filter (50px cutoff, 2-pass merge)
  - **Strategy D:** Connected Components DSU Merging, Segment-Distance Endpoints, Crop Offset Translation & Scale-Aware Consensus Oracle (Selected Oracle)

| Scenario # | Description | Strategy A | Strategy B | Strategy C | Strategy D (Selected) |
|---|---|---|---|---|---|
| **Scenario 1** | Clean Horizontal Dimension (0 gap, no slant, origin) | **PASS** | **PASS** | **PASS** | **PASS (conf >= 0.95)** |
| **Scenario 2** | Slanted Extension Overshoot (8px slant on 2nd witness line) | FAIL (overshoot pick) | **PASS** (max y) | **PASS** (midpoint dist) | **PASS (segment dist)** |
| **Scenario 3** | Standard 300 DPI Drafting Gap (1.5mm / 18px ASME gap) | FAIL (conf 0.624 < 0.85) | FAIL (conf < 0.85) | FAIL (conf < 0.85) | **PASS (scale-aware gap)** |
| **Scenario 4** | Page Crop Offset (cluster at `(250, 400)`) | FAIL (coords mismatch) | **PASS** (offset passed) | **PASS** (offset passed) | **PASS (offset translated)** |
| **Scenario 5** | Transitive 3-Box Cluster Topology (`y0=15` bridge) | FAIL (2 boxes left) | **PASS** (global union) | **PASS** (global union) | **PASS (1 DSU merged box)** |
| **Scenario 6** | Multi-Anchor Disambiguation (4 datums: 2 target, 2 distractors)| **PASS** | FAIL (distractor pick)| FAIL (distractor pick)| **PASS (view + orient filter)**|
| **Scenario 7** | Angled 45-degree Dimension with Overshoot | **PASS** | **PASS** | **PASS** | **PASS (segment dist)** |
| **Scenario 8** | Vertical Dimension with Overshoot & 18px Gap | FAIL (gap + overshoot) | FAIL (conf < 0.85) | FAIL (conf < 0.85) | **PASS (conf >= 0.85)** |
| **Scorecard** | **Success Rate** | **3 / 8 (37.5%)** | **5 / 8 (62.5%)** | **5 / 8 (62.5%)** | **8 / 8 (100.0%)** |

---

## Section 13: Positive Fixtures and Strong Negative Controls (`[MEASURED]`)

- **Script:** [`test_dimension_attachment_controls.py`](test_dimension_attachment_controls.py)
- **Result:** **8/8 Tests Passed Cleanly**

1. **Positive Controls (`[MEASURED]`):**
   - **CTRL-1 (Unambiguous Horizontal Attachment):** Dimension line spanning between two circle centers with standard drafting gap resolves cleanly with confidence `>= 0.90`.
   - **CTRL-2 (Orthogonal Shaft Diameter):** Vertical dimension line across cylindrical shaft with horizontal witness lines resolves with confidence `>= 0.85`.

2. **Negative Controls (`[MEASURED]`):**
   - **CTRL-3 (Cross-View Contamination):** Anchors belonging to different views (e.g. `FRONT` and `SECTION_A`) fail-closed (`view_membership = 0.0`, confidence `< 0.85`).
   - **CTRL-4 (Excessive Gap Rejection):** Workpiece datums located > 100px away from extension line ends fail-closed with `attachment_confidence_below_threshold`.
   - **CTRL-5 (Parallel Distractor Disambiguation):** True feature at 15px gap is preferred over parallel feature at 75px gap with confidence separation margin `margin >= 0.10`.
   - **CTRL-6 (Invalid Anchor Rejection):** Anchors with confidence `<= 0.0` or malformed point coordinates are safely filtered out, preventing garbage pairing.
   - **CTRL-7 (Self-Referential Anchor Rejection):** Cannot attach both ends of a linear dimension to the same anchor entity (`from_ref != to_ref`).
   - **CTRL-8 (Low-Confidence Geometry Gate):** Geometry with `confidence < 0.70` fails-closed as unresolved, even if anchor match is high.

---

## Section 14: Degenerate, Non-Finite & Ambiguity Edge Cases (`[MEASURED]`)

- **Script:** [`test_dimension_attachment_degenerate_and_perf.py`](test_dimension_attachment_degenerate_and_perf.py)
- **Result:** **7/7 Tests Passed Cleanly**

1. **Empty Inputs Safe No-Op:** Empty boxes and empty anchors return clean empty results without error or exception.
2. **Zero-Length Dimension Line:** Segment with `dx=0, dy=0` safely handled without `ZeroDivisionError`.
3. **Single Extension Line:** Geometry with `< 2` extension lines safely returns without candidates.
4. **Non-Finite Coordinates (NaN, Inf):** Anchors containing `NaN` or `Inf` are safely filtered out.
5. **Extreme Coordinates ($10^6\text{ px}$):** Coordinates at $1,000,000\text{ px}$ operate without numerical overflow or precision collapse.
6. **Collinear Extension Lines:** Extension lines parallel to or coincident with dimension line evaluate safely.
7. **Scalability & Latency:** 100 cluster boxes merged via DSU and 50 anchors matched in **~1.5 ms** (< 25 ms budget).

---

## Section 15: Runtime Performance & Computational Complexity (`[MEASURED]`)

- **Box Merging Complexity:** $O(B^2 \cdot \alpha(B))$ where $B$ is the number of bounding boxes and $\alpha$ is the inverse Ackermann function. For typical drawings ($B \le 200$), runtime is **< 1.0 ms**.
- **Anchor Matching Complexity:** $O(A^2)$ where $A$ is the number of valid anchors in the view. For typical views ($A \le 50$), pairs $= 2500$, evaluating in **< 3.0 ms**.
- **Total Latency:** Single cluster resolution executes in **~0.2 ms - 1.5 ms** wall-clock time (< 25 ms budget).

---

## Section 16: Parameter & Threshold Epistemic Classification

| Parameter / Rule | Formulation | Epistemic Classification | Rationale & Proof |
|---|---|---|---|
| `BOX_MERGE_MARGIN_PX` | `8 px` | **`[SYNTHETIC_DISCRIMINATOR]`** | Pixel clustering margin for grouping adjacent text words and dimension line fragments. |
| `MIN_ATTACHMENT_CONFIDENCE` | `0.85` | **`[SAFE_DIMENSIONLESS_BOUND]`** | Invariant threshold defined by visual contract schema `dimension_register`. |
| `MIN_CONFIDENCE_MARGIN` | `0.10` | **`[SAFE_DIMENSIONLESS_BOUND]`** | Minimum confidence separation between 1st and 2nd best candidate to prevent ambiguous attachments. |
| `MIN_GEOMETRY_CONFIDENCE` | `0.70` | **`[SAFE_DIMENSIONLESS_BOUND]`** | Upstream geometry detector confidence gate from visual contracts. |
| `DRAFTING_GAP_TOLERANCE_MM` | `2.0 mm` | **`[NEEDS_REAL_SCAN_CALIBRATION]`** | Physical drafting origin offset defined in ASME Y14.5 / ISO 129-1 (typically 1.0 mm to 2.5 mm). |
| `DEFAULT_PX_PER_MM` | `11.81 px/mm` | **`[MEASURED]`** | Equivalent to standard 300 DPI rasterization ($300 / 25.4$). Absorbs scan resolution when calibration is available. |

---

## Section 17: Selected Production Architecture & Minimum Writeset (`[FUTURE_PRODUCTION_PROPOSAL]`)

When promoted to production by `SOLO_CODEX`, the following modifications should be applied to `primitive_ir_lib/dimension_observer.py`:

1. **Replace `_merge_boxes` with DSU Transitive Connected Components:**
   ```python
   def _merge_boxes(boxes: Sequence[Bbox], margin_px: int = 8) -> list[Bbox]:
       if not boxes:
           return []
       n = len(boxes)
       parent = list(range(n))
       def find(i: int) -> int:
           if parent[i] == i:
               return i
           parent[i] = find(parent[i])
           return parent[i]
       def union(i: int, j: int) -> None:
           ri, rj = find(i), find(j)
           if ri != rj:
               parent[ri] = rj
       for i in range(n):
           x0_i, y0_i, x1_i, y1_i = boxes[i]
           for j in range(i + 1, n):
               x0_j, y0_j, x1_j, y1_j = boxes[j]
               if not (x1_i < x0_j - margin_px or x0_i > x1_j + margin_px or
                       y1_i < y0_j - margin_px or y0_i > y1_j + margin_px):
                   union(i, j)
       components: dict[int, list[Bbox]] = {}
       for i in range(n):
           components.setdefault(find(i), []).append(boxes[i])
       merged: list[Bbox] = []
       for group in components.values():
           merged.append((min(b[0] for b in group), min(b[1] for b in group),
                          max(b[2] for b in group), max(b[3] for b in group)))
       return sorted(merged, key=lambda b: (b[1], b[0], b[3], b[2]))
   ```

2. **Fix `_outer_extension_points` using Segment Distance:**
   ```python
   def _point_to_segment_distance(pt: tuple[float, float], seg: tuple[tuple[float, float], tuple[float, float]]) -> float:
       p0, p1 = seg
       dx, dy = p1[0] - p0[0], p1[1] - p0[1]
       lsq = dx * dx + dy * dy
       if lsq == 0.0:
           return math.hypot(pt[0] - p0[0], pt[1] - p0[1])
       t = max(0.0, min(1.0, ((pt[0] - p0[0]) * dx + (pt[1] - p0[1]) * dy) / lsq))
       return math.hypot(pt[0] - (p0[0] + t * dx), pt[1] - (p0[1] + t * dy))

   def _outer_extension_points(geometry: DimensionGeometryEvidence) -> list[tuple[float, float]]:
       if geometry.dimension_line is None:
           return []
       line = geometry.dimension_line
       points: list[tuple[float, float]] = []
       for extension in geometry.extension_lines:
           candidate = max(extension, key=lambda pt: _point_to_segment_distance(pt, line))
           points.append(candidate)
       return points
   ```

3. **Update `_attachment_candidates` with Crop Offset Translation and Scale-Aware Drafting Gap:**
   - Add `crop_offset_px: tuple[float, float] = (0.0, 0.0)` parameter to `_attachment_candidates`.
   - In `observe_dimension_cluster()`, call `_attachment_candidates(..., crop_offset_px=(float(x0), float(y0)))`.
   - Map extension endpoints: `endpoints = [(p[0] + x0, p[1] + y0) for p in endpoints]`.
   - Compute `excess_dist = max(0.0, dist - max_drafting_gap_px)`.

---

## Section 18: Non-Interference & Verification Protocol

- **Zero Mutations to Production Source:** `primitive_ir_lib/dimension_observer.py` has not been modified.
- **Existing Tests Intact:** All 12 existing tests in `primitive_ir_lib/tests/test_dimension_observer.py` pass without regressions.
- **Durable Research Location:** All research artifacts reside strictly within `research/antigravity/2026-10-11/dimension_attachment/`.

---

## Section 19: Durable Sign-Off & Status Declaration

- **Epic Status:** `READY_FOR_CODEX`
- **Reviewed Strategy:** Strategy D (Transitive DSU Box Clustering, Segment-Distance Workpiece Endpoints, Crop-to-Page Translation & Scale-Aware Consensus Oracle)
- **Empirical Proof Scripts:**
  1. [`dimension_attachment_engine.py`](dimension_attachment_engine.py)
  2. [`test_causal_red_dimension_attachment.py`](test_causal_red_dimension_attachment.py)
  3. [`test_dimension_attachment_benchmark.py`](test_dimension_attachment_benchmark.py)
  4. [`test_dimension_attachment_controls.py`](test_dimension_attachment_controls.py)
  5. [`test_dimension_attachment_degenerate_and_perf.py`](test_dimension_attachment_degenerate_and_perf.py)
  6. [`dimension_attachment_and_clustering_empirical_specification.md`](dimension_attachment_and_clustering_empirical_specification.md)
