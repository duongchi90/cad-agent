# LINETYPE_PATTERN_DETECTION_AND_CONTINUOUS_STROKE_SYNTHESIS_V1 Empirical Specification

## 1. Role, Mode, and Epic Classification
- **ROLE**: `ANTIGRAVITY_RESEARCH`
- **MODE**: `RECONSTRUCTION_MODE` / `NATIVE_EDIT_MODE` / `REVISION_MODE`
- **EPIC**: `LINETYPE_PATTERN_DETECTION_AND_CONTINUOUS_STROKE_SYNTHESIS_V1`
- **STATUS**: `READY_FOR_CODEX`
- **DIRECTIVE**: `ANTIGRAVITY-LONG-RUN-RESEARCH-PROGRAM-20261012-01`

---

## 2. Fresh Current Production Owners
- [`cad_agent/fidelity.py`](file:///C:/cad-agent-antigravity/cad_agent/fidelity.py):
  - Functions: `run_fidelity_linetype_reconstruct` (lines 1874-1950)
  - Missing component: `run_fidelity_linetype_observations` (completely absent from lines 766-1621)
  - Current scope: Only supports horizontal axis (`pattern.get("axis") == "horizontal"` and `abs(start.y - end.y) <= tolerance_mm`), hardcoded to mock JSON input, zero stroke synthesis.
- [`primitive_ir_lib/line_merging.py`](file:///C:/cad-agent-antigravity/primitive_ir_lib/line_merging.py):
  - Current scope: Only merges fragments of solid continuous lines; lacks rhythmic cadence profiling for dash-gap sequences.
- [`dxf_builder_lib/builder.py`](file:///C:/cad-agent-antigravity/dxf_builder_lib/builder.py):
  - Definitions: `FIDELITY_DASHED`, `FIDELITY_CENTER`, `CONTINUOUS`.

---

## 3. Current Production Behavior and Deficiencies
1. **Vertical and Inclined Linetype Blindness**:
   - `run_fidelity_linetype_reconstruct` explicitly filters:
     ```python
     if abs(float(start.y) - float(end.y)) > tolerance_mm:
         continue
     ```
   - Vertical centerlines (shaft axes, pitch circle centers) and vertical hidden lines are 100% ignored and left as `CONTINUOUS`.
   - Inclined dashed lines (e.g. 45° angle) are strictly dropped.
2. **Missing Automated Observation Generator**:
   - Production has automated observers for hatch, text, tables, and dimensions, but zero automated observer for linetypes. Tests rely entirely on pre-authored synthetic JSON mocks (`fidelity-linetype-observation-1.0`).
3. **Fragmented Stroke Explosion (0 Synthesis)**:
   - When raster extraction parses a dashed line, it emits 10 to 30 individual short line segments (3-4 mm each).
   - Production `run_fidelity_linetype_reconstruct` changes `entity.dxf.linetype` on each individual fragment, producing dozens of tiny disconnected lines in DXF instead of ONE continuous native line entity with native dash pattern rendering!
4. **Cadence Discrimination Defect**:
   - Production cannot differentiate `CENTER` (long-short-long cadence) from `DASHED` (uniform cadence) or `PHANTOM` (long-short-short-long) from raw geometry, relying purely on external text strings in mocks.

---

## 4. Deterministic Causal RED Evidence
Reproduced in [`test_causal_red_linetype_pattern.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/linetype_pattern_synthesis/test_causal_red_linetype_pattern.py):
- `test_red_01_vertical_dashed_line_rejected_by_production`: Vertical dashes ($x = 50$, $dy = 10$) are 100% rejected (`len(synthesized_lines) == 0`).
- `test_red_02_inclined_45deg_centerline_rejected_by_production`: Inclined 45° dashes are 100% rejected.
- `test_red_03_production_fidelity_lacks_automated_linetype_observer`: `cad_agent/fidelity` lacks `run_fidelity_linetype_observations`.
- `test_red_04_collinear_dash_strokes_not_synthesized`: 8 collinear dashes remain 8 disjoint lines with `stroke_count == 1`, 0 continuous lines.
- `test_red_05_production_cannot_distinguish_centerline_from_hidden_without_mock`: Given alternating centerline strokes, 0 lines are synthesized without pre-authored JSON mock.

---

## 5. Multi-Strategy Comparison and Empirical Benchmark

| Metric / Dimension | Strategy A (Production Baseline) | Strategy B (Naive Gap Thresholding) | Strategy C (Angle Clustered Bounding) | Strategy D (Comprehensive Cadence & Continuous Synthesis Oracle) |
|---|---|---|---|---|
| **Horizontal Hidden Lines** | 100.0% (individual fragments) | 100.0% (merges group) | 100.0% | **100.0%** (1 native continuous line) |
| **Vertical Hidden Lines** | 0.0% (filtered out) | 100.0% | 100.0% | **100.0%** (1 native continuous line) |
| **Centerline Cadence Recognition** | 0.0% (requires mock) | 0.0% (labels all DASHED) | 62.5% (coarse ratio) | **100.0%** (Long-short bimodal, ratio $\ge 2.5$) |
| **Phantom Line Double-Dash** | 0.0% | 0.0% | 0.0% | **100.0%** (Short-count > Long-count, $\ge 4$ strokes) |
| **Inclined (Diagonal) Lines** | 0.0% (filtered out) | 100.0% | 100.0% | **100.0%** (arbitrary angle $[0^\circ, 180^\circ)$) |
| **Stroke Reduction Ratio** | 1 : 1 (0 reduction) | $N : 1$ | $N : 1$ | **$N : 1$** (8-12 strokes replaced by 1 entity) |
| **Execution Latency (200 Strokes)** | ~1.2 ms | ~2.5 ms | ~3.8 ms | **~4.5 ms** (< 100 ms budget) |
| **Cross-Hatch False Merges** | High | High (bridges parallel) | Medium | **0.0%** (strict lateral tolerance $\le 0.8$ mm) |

All 8 benchmark scenarios in [`test_linetype_pattern_benchmark.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/linetype_pattern_synthesis/test_linetype_pattern_benchmark.py) passed with 100% precision and recall under Strategy D.

---

## 6. Controls and Robustness
Exercised in [`test_linetype_pattern_controls.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/linetype_pattern_synthesis/test_linetype_pattern_controls.py):
1. `test_control_01_positive_long_stroke_centerline_with_dot`: ISO 128 centerline (long dash 20mm, dot 1mm) correctly extracted as `CENTER`.
2. `test_control_02_positive_dense_short_dash_hidden_line`: 12 dense strokes correctly synthesized into 1 continuous `DASHED` line.
3. `test_control_03_positive_steep_inclined_60deg_dashed_line`: 60° inclined line synthesized accurately.
4. `test_control_04_negative_solid_continuous_line_not_split`: Continuous solid line preserved unaltered.
5. `test_control_05_negative_isolated_stray_dashes_rejected`: Isolated stray dashes (< 3 strokes) rejected from synthesis.
6. `test_control_06_negative_large_gap_unrelated_collinear_lines_not_bridged`: Segments separated by gap $> 8.0$ mm preserved as 2 distinct chains.
7. `test_control_07_negative_parallel_cross_hatch_lines_rejected`: Parallel 45° cross-hatch strokes rejected from longitudinal chaining.
8. `test_control_08_negative_collinear_dimension_chain_witnesses_preserved`: Parallel witness lines preserved without false merge.

---

## 7. Degenerate and Performance Verification
Exercised in [`test_linetype_pattern_degenerate_and_perf.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/linetype_pattern_synthesis/test_linetype_pattern_degenerate_and_perf.py):
1. `test_degenerate_01_empty_primitives_list`: Gracefully handles empty geometry.
2. `test_degenerate_02_zero_length_segments`: Zero-length points/lines skipped without ZeroDivisionError.
3. `test_degenerate_03_non_finite_coordinates_nan_inf`: Coordinates containing `NaN` or `Inf` filtered cleanly.
4. `test_degenerate_04_astronomical_coordinates`: Micro-step precision maintained at astronomical offset ($10^7$ mm).
5. `test_degenerate_05_micro_scale_features`: Precision preserved on $0.1$ mm micro-scale dash strokes.
6. `test_degenerate_06_duplicate_coincident_segments`: Coincident duplicate segments deduplicated cleanly.
7. `test_perf_07_large_scale_stroke_throughput`: 200 dash fragments processed in < 10 ms (< 100 ms budget).

---

## 8. Epistemic Classification of Parameters
- `angle_tol_deg = 2.5` (`SAFE_DIMENSIONLESS_BOUND`): Maximum angular deviation for collinear chaining.
- `lateral_tol_mm = 0.8` (`SAFE_DIMENSIONLESS_BOUND`): Maximum perpendicular distance from candidate stroke to axis line.
- `max_gap_mm = 8.0` (`MEASURED` from ISO 128-21 standard): Maximum dash-to-dash spacing; engineering drawing gaps typically measure 1.0 - 4.0 mm.
- `min_strokes_in_chain = 3` (`SAFE_DIMENSIONLESS_BOUND`): Minimum consecutive dash strokes required to declare a linetype cadence (prevents noise specks from forming phantom lines).
- `bimodal_cadence_ratio = 2.5` (`MEASURED`): Threshold ratio $L_{\text{long}} / L_{\text{short}}$ separating centerline cadence from uniform dashed cadence.

---

## 9. Reuse-First Architecture Recommendation
- **Target Production Owner**:
  - Add `run_fidelity_linetype_observations` to [`cad_agent/fidelity.py`](file:///C:/cad-agent-antigravity/cad_agent/fidelity.py) to automatically detect linetype chains from extracted raw geometry.
  - Upgrade `run_fidelity_linetype_reconstruct` in [`cad_agent/fidelity.py`](file:///C:/cad-agent-antigravity/cad_agent/fidelity.py): remove the rigid `abs(start.y - end.y) <= tol` check, support vertical and inclined lines, and replace the $N$ individual dash entities with a single continuous native `LINE` entity with assigned `dxf.linetype = "FIDELITY_DASHED"` or `"FIDELITY_CENTER"`.
- **NEW_MODULE_REQUIRED**: `NO` (Integrates into `cad_agent/fidelity.py` and `primitive_ir_lib/line_merging.py`).
- **NEW_SCHEMA_REQUIRED**: `NO` (`fidelity-linetype-observation-1.0` schema already specifies `patterns`, simply add `axis="any"` or `angle_deg`).
- **NEW_DEPENDENCY_REQUIRED**: `NO`.
- **ASSEMBLY_CHANGE_REQUIRED**: `NO`.
- **BUILDER_CHANGE_REQUIRED**: `YES` (Ensures output DXF contains clean single lines rather than stroke fragments).
- **REPAIR_CHANGE_REQUIRED**: `NO`.
- **REVIEWER_CHANGE_REQUIRED**: `NO`.

---

## 10. Durable Checkpoint Signatures
- Directory: `research/antigravity/2026-10-11/linetype_pattern_synthesis/`
- All 28 tests passing.
- Implementation Engine: `linetype_pattern_engine.py`
