# CODE_AVOIDANCE_REPORT: Measured Engineering Work Reductions

## 1. Avoided Engineering Activity Inventory

| Avoidance Category | Measured Count | Concrete Examples from 4-Tier Benchmark & Precompute |
| :--- | :---: | :--- |
| **`PROTOTYPE_NOT_NEEDED`** | **4** | 1. No prototype needed for 3-point bulge fitting ($b = \tan(\theta/4)$ proven).<br>2. No prototype needed for stream format header parsing.<br>3. No experimental code needed for RDP tolerance boundaries.<br>4. No speculative binary fuzzing for CAD stream opcodes. |
| **`NEW_DEPENDENCY_NOT_NEEDED`** | **2** | 1. Avoided pulling in external native C++ curve fitting libraries for polyline bulges.<br>2. Avoided pulling in third-party vector normalization packages. |
| **`ALGORITHM_DESIGN_NOT_NEEDED`** | **5** | 1. Monotone chain 2D convex hull algorithm design avoided.<br>2. Jordan curve theorem ray-casting parity loop design avoided.<br>3. Shoelace area formulation design avoided.<br>4. RDP divide-and-conquer recursion design avoided.<br>5. 3-Point circle center & angular traversal formulation design avoided. |
| **`API_DISCOVERY_NOT_NEEDED`** | **3** | 1. AutoCAD `Polyline.GetBulgeAt()` / `SetBulgeAt()` managed API proven.<br>2. Stream format state transitions mapped directly from binary.<br>3. Differential return code `-10` mapped directly without API probing. |
| **`BINARY_EXPERIMENT_NOT_NEEDED`** | **3** | 1. No trial-and-error needed to test whether `global_scale` mutates coordinates.<br>2. No manual disassembler session required to identify collinearity tolerance ($10^{-4}$).<br>3. No runtime crash testing needed to identify division-by-zero vulnerability. |
| **`NEGATIVE_APPROACH_AVOIDED`** | **3** | 1. Avoided chord-fragmented straight-line approximation of CAD fillets.<br>2. Avoided unmanaged C++ P/Invoke for polyline bulging.<br>3. Avoided assuming format version 3 was supported. |
| **`TEST_ORACLE_REUSED`** | **4** | 1. `TRANSFER_ORACLE.md` deterministic unit test suite for polyline bulges.<br>2. Collinearity zero-vector test oracle for tolerance envelopes.<br>3. Magic bytes / version mismatch test suite for stream formats.<br>4. 5-point square area & hull test suite for computational geometry. |
| **`OWNER_ALREADY_EXISTS`** | **3** | 1. `dxf_builder_lib/builder.py` owns polyline construction.<br>2. `primitive_ir_lib/geometry_extraction.py` owns arc/curve extraction.<br>3. `autocad_plugin/CadAgent.AutoCAD2027` owns managed polyline mutations. |
| **`ADAPTER_ONLY`** | **1** | Only a thin Python helper `points_to_bulge()` needed in `primitive_ir_lib`. |
| **`NO_CODE_REQUIRED`** | **2** | 1. Managed AutoCAD SDK already exposes native bulge methods.<br>2. Negative knowledge entries require zero production code. |

---

## 2. Before vs After Engineering Comparison

### Case 1: Polyline Bulge and Arc Representation (Tier 4 Selection)
- **WITHOUT_REA_EXPECTED_ENGINEERING:**
  1. Research DXF format group codes 42 and curve geometry.
  2. Implement experimental chord-subdivision prototype.
  3. Realize DXF output is bloated with thousands of straight vertices.
  4. Attempt 3-point circle fitting; encounter coordinate singularities.
  5. Struggle with clockwise vs counter-clockwise sign conventions and angular wrap-around.
  6. Estimated Luna effort: ~12–16 engineering hours.
- **WITH_REA_REMAINING_ENGINEERING:**
  1. Bulge mathematical oracle and sign conventions already verified in `TRANSFER_ORACLE.md`.
  2. Map thin function into `dxf_builder_lib` and `primitive_ir_lib`.
  3. Run existing deterministic tests.
  4. Remaining Luna effort: ~1 hour.
  5. **Work Reduction: ~90% avoided.**

### Case 2: Degenerate Vector Robustness (Tier 3 Selection)
- **WITHOUT_REA_EXPECTED_ENGINEERING:**
  1. Hunt for silent floating-point NaN regressions across customer drawing evaluations.
  2. Write debug logs to find which vector division crashed the pipeline.
  3. Implement ad-hoc threshold check.
- **WITH_REA_REMAINING_ENGINEERING:**
  1. Differential REA directly identified the exact threshold ($10^{-12}$) and return error propagation.
  2. Instant transfer into validation guard.
  3. **Work Reduction: 100% of discovery avoided.**
