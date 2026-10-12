# Empirical Specification: Section Hatch Pattern and Boundary Reconstruction Engine (V1)

**Topic:** `SECTION_HATCH_PATTERN_AND_BOUNDARY_RECONSTRUCTION_V1`  
**Status:** `READY_FOR_CODEX`  
**Date:** 2026-10-12  
**Branch:** `research/antigravity-2026-10-11`  
**Location:** [`research/antigravity/2026-10-11/section_hatch_reconstruction/`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/section_hatch_reconstruction/)

---

## 1. Role, Mode, and Epic Identification

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `LONG_RUNNING_CONTINUOUS_AUTONOMOUS_RESEARCH`
- **Product Targets:**
  - `RECONSTRUCTION_MODE`: Mechanical section and cutaway primitive extraction $\to$ cross-hatch boundary polygon segmentation $\to$ native `ezdxf.entities.Hatch` representation.
  - `REVISION_MODE`: Cross-section comparison, void hole drift detection, and section wall thickness verification.
  - `NATIVE_EDIT_MODE`: Associative boundary updates without corrupting interior void islands.
- **Epic:** `SECTION_HATCH_PATTERN_AND_BOUNDARY_RECONSTRUCTION_V1`

---

## 2. Current Production Owners & Scope

1. **[`cad_agent/fidelity.py`](file:///C:/cad-agent-antigravity/cad_agent/fidelity.py)**:
   - Primary owner of hatch candidate observation (`_observe_hatch_candidates`) and review-only DXF hatch reconstruction (`run_fidelity_hatch_reconstruct`).
   - Schema: `fidelity-hatch-observation-1.0`, `fidelity-hatch-approval-1.0`.
2. **[`primitive_ir_lib/tick_mark_detection.py`](file:///C:/cad-agent-antigravity/primitive_ir_lib/tick_mark_detection.py)**:
   - Consumer filtering diagonal hatch strokes as noise distractors during dimension witness line analysis.
3. **[`primitive_ir_lib/geometry_extraction.py`](file:///C:/cad-agent-antigravity/primitive_ir_lib/geometry_extraction.py)**:
   - Preset `real_scan_tuned_v1` filtering hatch strokes to avoid emitting hundreds of fragmented CAD lines.

---

## 3. Current Production Behavior & Gap

In current production code:
1. **Rigid 100x100 Pixel Grid Binning Artifacts:**
   `_observe_hatch_candidates` partitions the raster drawing into hardcoded $100\times 100$ pixel square grid bins:
   `key = (int((int(x0) + int(x1)) / 2) // 100, int((int(y0) + int(y1)) / 2) // 100)`
   Any single continuous hatched cross-section that crosses an arbitrary 100-pixel grid line is fractured into multiple disconnected square bounding boxes (`[column * 100, row * 100, (column + 1) * 100, (row + 1) * 100]`), completely losing the true mechanical workpiece perimeter polygon.
2. **Complete Blindness to Internal Void Holes / Bores:**
   When a mechanical cross-section contains bored holes, shafts, or unhatched pockets, the current baseline is completely blind to inner void loops. It either emits solid 100x100 grid tiles over the void, or leaves disjoint holes without topological associations. In DXF, native `HATCH` entities require explicit inner loop paths (`hatch.paths.add_polyline_path(points, is_closed=True)`).
3. **Severe Angle & Pitch Blindness:**
   `_observe_hatch_candidates` filters with:
   `if abs(dx) < 10 or abs(dy) < 10: continue`
   It accepts ANY line that is not strictly horizontal or vertical. Diagonal text strokes (letters X, M, W, V, K), leader lines, and chamfers easily trigger false positive hatch candidates. Furthermore, it cannot estimate the dominant stroke angle or physical pitch spacing, defaulting blindly to hardcoded `ANSI31, angle=45.0, scale=1.0` in `run_fidelity_hatch_reconstruct`.
4. **Boundary Reconstruction Blocker:**
   In `run_fidelity_hatch_reconstruct`, the reconstruction step fails closed if a human does not manually provide `boundary_points` because the observation stage only outputs arbitrary 100x100 square grid tiles.

---

## 4. Public Causal RED Reproduction

The causal RED test suite (`test_causal_red_section_hatch_reconstruction.py`) deterministically reproduces 5 baseline failure modes against current production `cad_agent/fidelity.py`:

| Test ID | Failure Mode | Baseline Behavior (Strategy A) | Expected Empirical Behavior (Strategy D) | Status |
|---|---|---|---|---|
| `RED-01` | Grid Tiling Fractures Workpiece Contour | Slices a continuous $130\times 90\text{mm}$ cross-section into $\ge 2$ disconnected 100x100 square boxes | Emits a single unified boundary polygon spanning $X \in [50, 180]$ | `REPRODUCED & VERIFIED` |
| `RED-02` | Internal Void Hole Blindness | Solid grid boxes emitted over central bored hole ($40\times 40\text{mm}$); `void_holes` = 0 | Extracts outer boundary AND inner void hole loop with non-zero area | `REPRODUCED & VERIFIED` |
| `RED-03` | Concave L-Bracket Corner Distortion | Naive bounding box bridges the concave corner, adding $> 2,000\text{ mm}^2$ phantom material | Preserves true 6-vertex concave perimeter polygon with area $\le 7,600\text{ mm}^2$ | `REPRODUCED & VERIFIED` |
| `RED-04` | Diagonal Text Stroke False Positive Hatch | Accepts 6 irregular diagonal text strokes ($dx \ge 10, dy \ge 10$) as a hatch candidate box | Rejects irregular text strokes due to lack of pitch uniformity and parallel consensus | `REPRODUCED & VERIFIED` |
| `RED-05` | Pitch & Angle Estimation Failure | Blind to actual angle and pitch; defaults to hardcoded 45° and scale 1.0 | Accurately estimates dominant angle ($60^\circ \pm 1.5^\circ$) and pitch ($8.0\text{mm} \pm 0.6\text{mm}$) | `REPRODUCED & VERIFIED` |

---

## 5. Causal Mechanism Analysis

1. **Grid Discretization vs Topological Feature Contours:**
   `_observe_hatch_candidates` performs spatial clustering via discrete integer division (`// 100`). In CAD drafting, cross-sections are bounded planar regions defined by workpiece contour lines, not arbitrary coordinate raster tiles.
2. **Normal Offset Projection Geometry:**
   For a family of parallel hatch lines at orientation angle $\theta$, their normal vector is $\vec{n} = (-\sin \theta, \cos \theta)$. Each line's perpendicular distance from the origin is $d_k = x_m \cdot (-\sin \theta) + y_m \cdot \cos \theta$.
   - True hatching exhibits near-zero angular variance ($\sigma_\theta \le 3.5^\circ$) and uniform consecutive pitch spacing $\Delta d_k = d_{k+1} - d_k \approx \text{const}$ with low jitter ($\sigma_{\Delta d} / \mu_{\Delta d} \le 0.28$).
   - Text annotations have diverse slopes and irregular gaps, yielding high jitter and low stroke counts per angle bin.
3. **Collinear Stroke Splitting at Void Boundaries:**
   When a hatch stroke encounters a void hole (such as a bore or bolt cutout), it is split into two collinear segments along the same normal rail $d_k$, leaving an unhatched gap $[t_{gap,start}, t_{gap,end}]$ along the axial direction. Projecting these gap intervals back to 2D coordinates yields the exact bounding perimeter of the inner void hole.

---

## 6. Empirical Multi-Strategy Comparison Matrix

| Evaluation Dimension | Strategy A: Current Production Baseline (`_observe_hatch_candidates`) | Strategy B: Naive Convex Hull over Stroke Endpoints | Strategy C: Raster Morphological Bounding Box | Strategy D: Consensus Clustering & Void Reconstruction Oracle |
|---|---|---|---|---|
| **Accuracy (8 Scenarios)** | **12.5%** (1/8) | **37.5%** (3/8) | **37.5%** (3/8) | **100.0%** (8/8) |
| **False Positives** | High (accepts diagonal text strokes and leaders) | Moderate | Moderate | **0.0%** (strict angular consensus and pitch jitter filter) |
| **False Negatives** | High (fractures wide or tall cross-sections) | Low | Moderate | **0.0%** (unifies multi-step and large cross-sections) |
| **Internal Void Detection** | **0.0%** (blind to inner holes) | **0.0%** (convex hull covers all voids) | **0.0%** (morphology closes voids) | **100.0%** (exact inner void loops extracted) |
| **Concave Perimeter Recall**| None (square tile fragments) | 0.0% (bridges concave corners, adding 2,000+ mm²) | Poor (distorts corners) | **100.0%** (preserves 6-vertex concave perimeters) |
| **Angle Estimation Error** | Blind (defaults to 45.0°) | Blind (defaults to 45.0°) | Blind (defaults to 45.0°) | **$\le 1.5^\circ$** |
| **Pitch Estimation Error** | Blind (defaults to 1.0) | Blind (defaults to 5.0mm) | Blind (defaults to 5.0mm) | **$\le 0.5\text{ mm}$** |
| **Execution Latency (500 prims)**| 1.25 ms | 2.10 ms | 4.80 ms | **0.85 ms** (> 500,000 strokes/sec) |
| **Implementation Complexity** | Low (30 LOC) | Low (35 LOC) | Medium (60 LOC) | **Medium-Low** (240 LOC, pure math) |
| **Reuse Fit** | Existing owner | Poor | Poor | **Direct drop-in for `_observe_hatch_candidates`** |

---

## 7. Parameter Epistemology

| Parameter | Value | Epistemological Classification | Engineering Rationale |
|---|---|---|---|
| `angle_tolerance_deg` | `3.5°` | `SAFE_DIMENSIONLESS_BOUND` | Absorbs Hough line extraction angular discretization noise while separating distinct hatch families. |
| `pitch_jitter_max_ratio` | `0.28` (28.0%) | `SAFE_DIMENSIONLESS_BOUND` | Upper limit for pitch spacing variation coefficient ($\sigma / \mu$). Separates drafting hatch from random text strokes. |
| `min_strokes_per_family` | `4` | `SAFE_DIMENSIONLESS_BOUND` | Minimum stroke count required to establish an engineering hatch pattern. Rejects isolated parallel line pairs. |
| `void_detection_min_gap_mm` | `8.0 mm` | `SAFE_DIMENSIONLESS_BOUND` | Minimum unhatched axial gap along a stroke rail indicating an intentional internal void hole. |

---

## 8. Reuse-First Architectural Contract

Before production implementation in SOLO_CODEX, verify architectural invariants:

- **CURRENT_OWNER:** `cad_agent/fidelity.py` (`_observe_hatch_candidates`, `run_fidelity_hatch_reconstruct`)
- **SMALLEST_EXISTING_OWNER:** `cad_agent/fidelity.py`
- **NEW_MODULE_REQUIRED:** `NO` (Integrate into `cad_agent/fidelity.py`)
- **NEW_SCHEMA_REQUIRED:** `NO` (Extend `fidelity-hatch-observation-1.0` candidate dictionary with `boundary_points`, `void_holes`, `dominant_angle_deg`, and `pitch_spacing_mm`)
- **NEW_DEPENDENCY_REQUIRED:** `NO` (Pure standard library math and existing OpenCV Hough lines)
- **ASSEMBLY_CHANGE_REQUIRED:** `NO`
- **BUILDER_CHANGE_REQUIRED:** `NO`
- **REPAIR_CHANGE_REQUIRED:** `NO`
- **REVIEWER_CHANGE_REQUIRED:** `NO`

---

## 9. Downstream Consumer Integration

1. **`cad_agent/fidelity.py` (`_observe_hatch_candidates`)**:
   - Replace rigid 100x100 tile binning with `SectionHatchReconstructionEngine.analyze`.
   - Populate `boundary_points` and `void_holes` directly in candidate payloads.
2. **`cad_agent/fidelity.py` (`run_fidelity_hatch_reconstruct`)**:
   - Reconstruct native DXF `HATCH` entities automatically using the extracted `boundary_points` (outer loop) and `void_holes` (inner void loops):
     ```python
     hatch = model.add_hatch(dxfattribs={"layer": "FIDELITY_HATCH"})
     hatch.paths.add_polyline_path(candidate["boundary_points"], is_closed=True)
     for void_loop in candidate.get("void_holes", []):
         hatch.paths.add_polyline_path(void_loop["vertices"], is_closed=True)
     hatch.set_pattern_fill(candidate["pattern_name"], scale=candidate["pitch_spacing_mm"], angle=candidate["dominant_angle_deg"])
     ```
3. **`primitive_ir_lib/geometry_extraction.py`**:
   - Remove verified hatch strokes from raw CAD line primitives before Phase 2 constraint and part assembly.

---

## 10. Checkpoint Status & File Inventory

- **Status:** `SECTION_HATCH_PATTERN_AND_BOUNDARY_RECONSTRUCTION_V1_READY_FOR_CODEX`
- **Verified Test Count:** 28 passed in 0.28s.
- **File Manifest:**

| Filename | Type | Status | SHA-256 Checksum | Description |
|---|---|---|---|---|
| [`__init__.py`](__init__.py) | Package Init | `RESEARCH_ONLY` | `6be9bd1f22de1df95a385e7fedda40c5e2980976a1b810518388c9ab180d49a5` | Package initialization |
| [`section_hatch_reconstruction_engine.py`](section_hatch_reconstruction_engine.py) | Research Engine | `RESEARCH_ONLY` | `e8e2b6718cb884b8e584545dcb5ac07f9b25eca8dd2f1807575ef429462082b6` | Reference engine for hatch clustering, pitch estimation, outer boundaries, and void holes |
| [`test_causal_red_section_hatch_reconstruction.py`](test_causal_red_section_hatch_reconstruction.py) | Causal RED Suite | `RESEARCH_ONLY` | `d9d0d86530cdbc87cac1e29ae9abb7410a609ba8060386a6a07a9733747b66cb` | 5 deterministic failure modes reproduced on production fidelity.py |
| [`test_section_hatch_reconstruction_benchmark.py`](test_section_hatch_reconstruction_benchmark.py) | Benchmark Suite | `RESEARCH_ONLY` | `d2ca5b614cd2ad0b83d6e95ee3ba4ef344ee25a561198f733e573dbdc99275f7` | 8 multi-strategy scenarios comparing Strategies A-D |
| [`test_section_hatch_reconstruction_controls.py`](test_section_hatch_reconstruction_controls.py) | Controls Suite | `RESEARCH_ONLY` | `2c506507531fe7477a3cc37159d250932ea2acb05551f153e9b5251e7916b61d` | 8 positive and negative control scenarios |
| [`test_section_hatch_reconstruction_degenerate_and_perf.py`](test_section_hatch_reconstruction_degenerate_and_perf.py) | Edge Cases & Stress | `RESEARCH_ONLY` | `f02008fba7e10d17d2ed475ae287653e3bbf93c4ab2174c6b993fe878090eb62` | 7 degenerate, non-finite, and large-scale throughput tests |
| [`section_hatch_pattern_and_boundary_reconstruction_empirical_specification.md`](section_hatch_pattern_and_boundary_reconstruction_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `ea89c02d6b7975cf643f88f8d68965022aa2a8439dfbe0642faeb269faea1850` | Formal empirical specification document |
