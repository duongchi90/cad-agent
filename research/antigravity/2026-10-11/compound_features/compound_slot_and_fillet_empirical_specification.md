# TECHNICAL SPECIFICATION: COMPOUND SLOT & FILLET FEATURE ASSEMBLY (`COMPOUND_SLOT_AND_FILLET_FEATURE_ASSEMBLY_V1`)

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `COMPOUND_SLOT_AND_FILLET_FEATURE_EMPIRICAL`
- **Target Epic:** `COMPOUND_SLOT_AND_FILLET_FEATURE_ASSEMBLY_V1`
- **Subagents:** `0` (Disabled per #429 overlay)
- **Repository Checkout:** `C:\cad-agent-antigravity`
- **Base Research Branch / Commit:** `research/antigravity-2026-10-11` (`4bcdc4df1363579617d8e643bcba771f69db486d`)
- **Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), PR #494 (`fix/start-tab-drawing-open-fallback`, DRAFT)
- **Production Impact:** `RESEARCH_ONLY = YES`, `PRODUCTION_FILES_CHANGED = false`

---

## Epistemic Status Legend

Throughout this specification, claims and parameters are explicitly tagged with their epistemic category:
- **`[MEASURED]`**: Direct empirical output from deterministic benchmark scripts in `research/antigravity/2026-10-11/compound_features/`.
- **`[SAFE_DIMENSIONLESS_BOUND]`**: Invariant mathematical or topological ratio that does not depend on DPI, scanner hardware, or real scan calibration.
- **`[SYNTHETIC_DISCRIMINATOR]`**: Threshold or boundary derived from synthetic geometry benchmarks separating positive from negative controls.
- **`[NEEDS_REAL_SCAN_CALIBRATION]`**: Absolute millimeter-domain threshold that must be tuned against physical paper/scanner engineering drawing tolerances.
- **`[INFERENCE]`**: Analytical or geometric deduction from measured evidence and mathematical invariants.
- **`[FUTURE_PRODUCTION_PROPOSAL]`**: Recommended design contract and minimum writeset for future `SOLO_CODEX` implementation (not yet implemented in production).
- **`[UNPROVEN_REAL_SCAN_GENERALIZATION]`**: Behavior on physical paper/scanner engineering drawings that remains unproven because private/customer drawings were lawfully excluded from research runs.

---

## Section 10: Fresh-Read Current Owners (`[MEASURED]`)

| Field | Verified Value |
|---|---|
| `CURRENT_COMPOUND_OWNER` | `semantic_ir_lib/pattern_compound.py:1-496` (`build_compound_parts`, `_find_khung_chu_nhat`, `_find_gia_do`, `_find_ban_le`, `_find_diem_noi`) |
| `CURRENT_ASSEMBLY_INTEGRATION` | `semantic_ir_lib/assemble.py:75-87` (calls `build_compound_parts`, but currently drops `arc` primitives and ignores `tangent`/`concentric` constraints) |
| `CURRENT_COMPOUND_TEST_OWNER` | `semantic_ir_lib/tests/test_pattern_compound.py` (only tests sharp line-only polygons) |
| `SMALLEST_EXISTING_OWNER` | `semantic_ir_lib/pattern_compound.py` |
| `NEW_MODULE_REQUIRED` | `NO` (All improvements integrate directly into `semantic_ir_lib/pattern_compound.py` and `assemble.py`) |
| `NEW_SCHEMA_REQUIRED` | `NO` (Uses existing `semantic_ir.schema.json` vocabulary: `khung_chu_nhat`, `gia_do`, `ban_le`, `mechanical_hole_feature`, `diem_noi`) |
| `NEW_DEPENDENCY_REQUIRED` | `NO` (Pure standard library `math` and existing models) |
| `ASSEMBLY_CHANGE_REQUIRED` | `YES` (`assemble.py` must forward curved primitives and constraints to `build_compound_parts`) |
| `BUILDER_CHANGE_REQUIRED` | `NO` (`dxf_builder_lib/builder.py` already supports `khung_chu_nhat`, `mechanical_hole_feature`, `gia_do`) |

---

## Section 11: Public Causal RED (`[MEASURED]`)

- **Script:** [`test_causal_red_compound_features.py`](test_causal_red_compound_features.py)
- **Result:** **5/5 Causal Failures Reproducible in Production Main Logic**

| RED Test | Production Flaw Mechanism | Measured Production Failure | Strategy D Behavior |
|---|---|---|---|
| **RED 1: Elongated Slot Omission** | `pattern_compound.py:466-473` filters only `line` and `circle` primitives; ignores `arc` and `tangent` constraints. | Slotted plate (2 lines + 2 tangent arcs): **Strategy A returns 0 compound parts**, leaving slot fragmented into single lines. | Evaluates parallel lines joined by twin tangent arcs: **assembles unified `mechanical_hole_feature` (slot)**. |
| **RED 2: Filleted Rectangular Frame Omission** | `_find_khung_chu_nhat` lines 173-183 requires direct line-line `coincident_endpoint` constraints at $\ge 3$ corners. Corner arcs break direct line touching. | Rectangular plate with 4 corner fillets: **Strategy A returns 0 compound parts**. | Binds 4 lines + 4 corner arcs via tangent constraints: **assembles unified 8-primitive `khung_chu_nhat`**. |
| **RED 3: Filleted L-Bracket Omission** | `_find_gia_do` requires direct line-line `coincident_endpoint`. Corner arc breaks line-to-line contact. | L-bracket with corner fillet: **Strategy A returns 0 compound parts**. | Binds perpendicular lines via corner tangent arc: **assembles 3-primitive `gia_do`**. |
| **RED 4: Mounting Lug Omission** | `_find_ban_le` requires 2 parallel lines with small circle bolt holes near endpoints; ignores outer semicircular arc. | Mounting lug tab (outer arc + concentric bolt hole + 2 tangent lines): **Strategy A returns 0 compound parts**. | Binds concentric hole circle and tangent neck lines: **assembles unified `ban_le` (mounting lug)**. |
| **RED 5: Naive Proximity False Merging** | Naive Strategy B groups primitives purely by bounding box overlap, with zero topological validation. | Slot with nearby unattached contour line (1mm gap): **Strategy B merges all 5 into 1 unclassified blob**. | Enforces strict constraint graph connectivity: **correctly isolates 4-primitive slot from adjacent line**. |

---

## Section 12: Multi-Candidate Empirical Benchmark (`[MEASURED]`)

- **Script:** [`test_compound_feature_benchmark.py`](test_compound_feature_benchmark.py)
- **Evaluated Strategies:**
  - **Strategy A:** Current Production Main (`semantic_ir_lib/pattern_compound.py`)
  - **Strategy B:** Naive Bounding Box Overlap Clusterer (proximity only)
  - **Strategy C:** Line-Only Polygon Cycle Matcher (ignores all arcs)
  - **Strategy D:** Constraint-Driven Multi-Primitive Feature Grammar (Selected Oracle)

| Scenario # | Description | Strategy A | Strategy B | Strategy C | Strategy D (Selected) |
|---|---|---|---|---|---|
| **Scenario 1** | Symmetrical oblong slot (2 lines + 2 arcs) | FAIL (0 parts) | FAIL (unclassified) | FAIL (0 parts) | **PASS (`mechanical_hole_feature`)** |
| **Scenario 2** | Filleted rectangular plate (4 lines + 4 arcs) | FAIL (0 parts) | FAIL (unclassified) | FAIL (0 parts) | **PASS (`khung_chu_nhat`, 8 prims)** |
| **Scenario 3** | Standard sharp rectangular frame (4 lines) | PASS (`khung_chu_nhat`) | FAIL (unclassified) | PASS (`khung_chu_nhat`) | **PASS (`khung_chu_nhat`, 4 prims)** |
| **Scenario 4** | Filleted L-bracket (2 lines + 1 arc) | FAIL (0 parts) | FAIL (unclassified) | FAIL (0 parts) | **PASS (`gia_do`, 3 prims)** |
| **Scenario 5** | Mounting tab with concentric hole (4 prims) | FAIL (0 parts) | FAIL (unclassified) | FAIL (0 parts) | **PASS (`ban_le`, 4 prims)** |
| **Scenario 6** | Double slot plate (2 distinct slots) | FAIL (0 parts) | FAIL (merged 1 blob) | FAIL (0 parts) | **PASS (2 separate slots)** |
| **Scenario 7** | Incomplete slot missing 1 arc | PASS (0 parts) | FAIL (false cluster) | PASS (0 parts) | **PASS (0 parts, rejected)** |
| **Scenario 8** | Structural joint `diem_noi` (4-line vertex) | PASS (`diem_noi`) | FAIL (unclassified) | PASS (`diem_noi`) | **PASS (`diem_noi`, 4 prims)** |
| **Scorecard** | **Success Rate** | **2 / 8 (25.0%)** | **0 / 8 (0.0%)** | **2 / 8 (25.0%)** | **8 / 8 (100.0%)** |

---

## Section 13: Positive Fixtures and Strong Negative Controls (`[MEASURED]`)

- **Script:** [`test_compound_feature_controls.py`](test_compound_feature_controls.py)
- **Result:** **8/8 Tests Passed Cleanly**

1. **Positive Controls (`[MEASURED]`):**
   - **Slotted Flange Plate:** 1 filleted rectangular frame (8 prims) + 1 internal slot (4 prims) + 1 mounting tab (4 prims) $\to$ detects all 3 distinct features cleanly without cross-contamination.
   - **Double-Ended Lug Bar:** Horizontal bar with mounting lugs on both ends $\to$ detects mounting tab features cleanly.
   - **Multi-Feature Assembly:** 1 sharp frame + 1 slot + 1 L-bracket $\to$ detects exactly 1 `khung_chu_nhat`, 1 `mechanical_hole_feature`, 1 `gia_do`.

2. **Negative Controls (`[MEASURED]`):**
   - **Dense Cross-Hatch Section Field:** 6 parallel $45^\circ$ lines $\to$ **0 compound parts emitted**.
   - **Open Parallel Rails:** 2 parallel lines with open ends and no arcs $\to$ **0 slots emitted**.
   - **Floating Arc Without Tangency:** Arc positioned near parallel lines without tangent constraints $\to$ **0 slots emitted**.
   - **Non-Concentric Hole Near Lug:** Hole circle displaced from lug arc center $\to$ **0 mounting lugs emitted**.
   - **Single Primitive Inputs:** Individual lines, circles, arcs $\to$ **0 compound parts emitted**.

---

## Section 14: Degenerate, Non-Finite & Ambiguity Edge Cases (`[MEASURED]`)

- **Script:** [`test_compound_feature_degenerate_and_perf.py`](test_compound_feature_degenerate_and_perf.py)
- **Result:** **6/6 Tests Passed Cleanly**

1. **Non-Finite Values:** Primitives containing `NaN`, `+Inf`, `-Inf` handled safely without crashes.
2. **Stale Constraint IDs:** Constraints pointing to non-existent primitive IDs are safely skipped.
3. **Self-Referential Constraints:** Constraints where `id1 == id2` are safely rejected.
4. **Zero-Length & Zero-Radius Primitives:** Degenerate primitives filtered out.
5. **Empty Inputs:** Empty lists return `[]` without error.
6. **Greedy Dedup Robustness:** Primitives are consumed by the largest compound part first (`-len(p.primitive_ids), -p.confidence`), preventing double-counting.

---

## Section 15: Runtime Performance & Computational Complexity (`[MEASURED]`)

- **120-Primitive Complex Assembly Benchmark:**
  - **Workload:** 120 primitives (40 lines, 40 arcs, 40 circles) forming 10 slots and 10 mounting lugs, plus 40 background grid lines.
  - **Latency:** **< 20 ms** total wall-clock execution time (measured: $12.8\text{ ms}$), far exceeding the $< 50\text{ ms}$ performance budget.
- **Algorithmic Complexity:**
  - Constraint index lookup: $O(K)$ where $K$ is the number of constraints (already pruned to $O(N)$ by `constraint_pruning.py`).
  - Feature matching: $O(N_{parallel} \times N_{arcs})$ for slots; $O(N_{parallel}^2 \times N_{arcs})$ for filleted frames.
  - Greedy dedup: $O(M \log M)$ where $M$ is the number of candidate compound parts ($M \ll N$).

---

## Section 16: Parameter & Threshold Epistemic Classification

| Parameter | Value | Epistemic Classification | Rationale & Proof |
|---|---|---|---|
| `slot_twin_arc_tangency_rule` | $N_{arcs} = 2$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Topological invariant: an oblong slot has exactly 2 semicircular ends connecting 2 parallel sides. |
| `filleted_corner_count_rule` | $N_{arcs} = 4$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Invariant geometric bound: a 4-sided rectangular plate has exactly 4 corners. |
| `greedy_part_size_priority` | `-len(primitive_ids)` | **`[SAFE_DIMENSIONLESS_BOUND]`** | Architectural principle: larger compound features (e.g. 8-primitive filleted frame) take precedence over smaller fragments (e.g. 2-primitive brackets). |
| `confidence_weighting_formula` | $\text{base\_conf} \times \text{fit}$ | **`[SAFE_DIMENSIONLESS_BOUND]`** | Invariant score aggregation: matches existing `pattern_compound.py` confidence formulation. |

---

## Section 17: Selected Production Architecture & Minimum Writeset (`[FUTURE_PRODUCTION_PROPOSAL]`)

When promoted to production by `SOLO_CODEX`, the following modifications should be applied:

1. **`semantic_ir_lib/pattern_compound.py`**:
   - In `build_compound_parts`:
     - Add `arc_ids = [p.id for p in primitives if p.type == "arc"]`.
     - Index `tangent` and `concentric` constraint pairs alongside `parallel`, `perpendicular`, `coincident_endpoint`.
     - Add `_find_filleted_khung_chu_nhat` to assemble 4 lines + 4 corner arcs into `khung_chu_nhat`.
     - Add `_find_slot_features` to assemble 2 parallel lines + 2 tangent arcs into `mechanical_hole_feature`.
     - Add `_find_filleted_gia_do` to assemble 2 perpendicular lines + 1 corner arc into `gia_do`.
     - Add `_find_mounting_lugs` to assemble 1 outer arc + 1 concentric circle + 2 tangent lines into `ban_le`.
2. **`semantic_ir_lib/assemble.py`**:
   - Lines 52-53 & 75-87: Forward `arc` primitives and curved constraints into `build_compound_parts`.
3. **`semantic_ir_lib/tests/test_pattern_compound.py`**:
   - Add test coverage for slots, filleted frames, and filleted brackets.

---

## Section 18: Codex Implementation Contract & Safety Guarantees

- **No Schema Breakage:** Produces standard `SemanticPart` items conforming to `semantic_ir.schema.json` using approved vocabulary (`khung_chu_nhat`, `gia_do`, `ban_le`, `mechanical_hole_feature`, `diem_noi`).
- **Strict Disjointness:** Greedily assigns each primitive to at most one compound part. Single-primitive parts remain preserved alongside compound parts as required by Reviewer #2.
- **Fail-Closed Principle:** Primitives that do not satisfy exact geometric constraints remain un-grouped; zero hallucinated parts.

---

## Section 19: Risk Analysis & Rollback Plan

- **Risk:** Degraded scans with broken arcs could miss 1 corner fillet, causing a filleted rectangle to be missed.
- **Mitigation:** In future revisions, allow $3/4$ filleted corners if the 4th corner has a direct line-line coincident endpoint.
- **Rollback:** `git revert` on the isolated commit in `semantic_ir_lib/pattern_compound.py`.

---

## Section 20: Verified Status Ledger Update

- `EPIC`: `COMPOUND_SLOT_AND_FILLET_FEATURE_ASSEMBLY_V1`
- `STATUS`: `READY_FOR_CODEX`
- `TESTS_PASSING`: 27 / 27 research tests
- `BENCHMARK_SCORE`: 100% (8/8 scenarios vs 25.0% in production Strategy A)
- `PERFORMANCE`: < 20 ms across 120 primitives
- `PRODUCTION_FILES_MUTATED`: 0 (`RESEARCH_ONLY = YES`)
