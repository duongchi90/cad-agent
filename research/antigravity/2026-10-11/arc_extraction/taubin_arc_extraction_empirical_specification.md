# TECHNICAL SPECIFICATION: TAUBIN CIRCULAR ARC EXTRACTION (`TAUBIN_ARC_EXTRACTION_V1`)

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `TAUBIN_ARC_EXTRACTION_EMPIRICAL`
- **Target Epic:** `TAUBIN_ARC_EXTRACTION_V1`
- **Subagents:** `0` (Disabled)
- **Repository Checkout:** `C:\cad-agent-antigravity`
- **Base Research Branch / Commit:** `research/antigravity-2026-10-11` (`b730776b419d11cdf8f4bac9375925810dd06b3c`)
- **Evaluated Main SHA:** `47808851b22472e213c8b8d77b735f9dbb88d699` (merged PR #493)
- **Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), PR #494 (`fix/start-tab-drawing-open-fallback`, DRAFT)
- **Production Impact:** `RESEARCH_ONLY = YES`, `PRODUCTION_FILES_CHANGED = false`

---

## Epistemic Status Legend

Throughout this specification, claims and parameters are explicitly tagged with their epistemic category:
- **`[MEASURED]`**: Direct empirical output from deterministic benchmark scripts in `research/antigravity/2026-10-11/arc_extraction/`.
- **`[SYNTHETIC_DISCRIMINATOR]`**: Threshold or boundary derived from synthetic raster benchmarks that separates positive and negative controls on clean/degraded synthetic fixtures.
- **`[INFERENCE]`**: Analytical or geometric deduction from measured evidence and mathematical invariants.
- **`[FUTURE_PRODUCTION_PROPOSAL]`**: Recommended design contract and minimum writeset for future `SOLO_CODEX` implementation (not yet implemented in production).
- **`[UNPROVEN_REAL_SCAN_GENERALIZATION]`**: Behavior on physical paper/scanner engineering drawings that remains unproven because private/customer drawings were lawfully excluded from research runs.

---

## Section 10: Fresh-Read Current Owners (`[MEASURED]`)

| Field | Verified Value |
|---|---|
| `CURRENT_ARC_SCHEMA` | `primitive_ir.schema.json:183-193` (`ArcGeometry`: required `["center", "radius", "start_angle_deg", "end_angle_deg"]`, `additionalProperties: false`; included in `Primitive.geometry` `oneOf` at line 120) |
| `CURRENT_ARC_MODEL_OWNER` | `primitive_ir_lib/models.py:77-89` (`ArcGeometry`), validated in `Primitive.__post_init__` (line 164) and `primitive_ir_lib/validator.py:17,83-85`, deserialized in `semantic_ir_lib/io_utils.py:50-54` |
| `CURRENT_ARC_EXTRACTION_OWNER` | `NONE` in `primitive_ir_lib/geometry_extraction.py` (currently exposes `extract_lines`, `extract_circles`, `extract_raw_geometry`) |
| `CURRENT_RAW_ARC_TYPE` | `NONE` (`geometry_extraction.py:37-56` defines only `RawLine` and `RawCircle`) |
| `CURRENT_RAW_GEOMETRY_ARC_SUPPORT` | `NONE` (`RawGeometry` in `geometry_extraction.py:59-62` has only `lines: list[RawLine]` and `circles: list[RawCircle]`) |
| `CURRENT_ARC_ASSEMBLY_OWNER` | `NONE` in `primitive_ir_lib/assemble.py` (`build_document` only processes `raw_lines`, `raw_circles`, `raw_texts`) |
| `CURRENT_DXF_ARC_WRITER` | `dxf_builder_lib/builder.py:347-356` (`msp.add_arc(center=..., radius=geom.radius, start_angle=geom.start_angle_deg, end_angle=geom.end_angle_deg)`), plus `dxf_builder_lib/reviewer.py:171-199` and `dxf_builder_lib/repair.py:151` |
| `CURRENT_ARC_TEST_OWNER` | `dxf_builder_lib/tests/test_reviewer.py` & `dxf_builder_lib/tests/dxf_test_support.py` (DXF ARC write/review); `NONE` in `primitive_ir_lib/tests/` (`primitive_ir_lib/tests/test_basic.py` is the natural test owner) |
| `NEW_MODULE_REQUIRED` | `NO` (`RawArc` and `extract_arcs` belong in `primitive_ir_lib/geometry_extraction.py`; calibration/assembly plumbing belongs in `primitive_ir_lib/assemble.py`) |

---

## Section 11: Public Causal RED (`[MEASURED]`)

- **Script:** [`test_causal_red_arc_extraction.py`](test_causal_red_arc_extraction.py)
- **Fixture:** Deterministic $800 \times 260\text{ px}$ raster containing `arc_90` ($90^\circ$), `arc_180` ($180^\circ$), `arc_270` ($270^\circ$), `circle_360` ($360^\circ$) at $R=50\text{ px}$, and `line_horiz` ($240\text{ px}$), stroke width $2\text{ px}$.
- **Measured Output:**
  - `EXPECTED_ARCS = 3`
  - `CURRENT_RAW_ARCS = 0` (`RawGeometry.has_arcs_field = False`, `CURRENT_DOC_ARC_PRIMITIVES = 0`)
  - `CURRENT_LINES = 2` (double-edge Hough lines on the $2\text{ px}$ horizontal line; `arc_90` is completely lost)
  - `CURRENT_CIRCLES = 3` (`default` preset) / `1` (`accurate` preset)
  - `FAILURE_MECHANISM`:
    1. `primitive_ir_lib/geometry_extraction.py` has no `RawArc` type, no `extract_arcs()` stage, and no `arcs` field on `RawGeometry`.
    2. `extract_circles()` relies exclusively on `cv2.HoughCircles` without angular coverage or gap verification. Under `preset="default"` (`param2=28`), `arc_180` and `arc_270` are falsely conflated into full $360^\circ$ `RawCircle` detections (`center_err=0.71px, r=51.0px`) while `arc_90` is dropped. Under `preset="accurate"` (`param2=38`), all three partial arcs are silently dropped.
    3. `primitive_ir_lib/assemble.py:build_document()` has no `raw_arcs` parameter or `ArcGeometry` assembly path.

---

## Section 12: Fitting Strategies Benchmark (`[MEASURED]`)

- **Script:** [`test_fitting_strategies_benchmark.py`](test_fitting_strategies_benchmark.py)
- **Matrix:** 40 clean raster arc configurations ($R \in \{8, 12, 20, 40, 80\}\text{ px}$, $\Delta\theta \in \{30^\circ, 45^\circ, 60^\circ, 90^\circ, 120^\circ, 180^\circ, 240^\circ, 300^\circ\}$, stroke width $2\text{ px}$) plus 40 spur-contaminated configurations (15% attached outlier spur pixels).

### 12.1 Clean Raster Arcs Summary (40 Configurations, `[MEASURED]`)

| Strategy | Mean Ctr Err (px) | Med Ctr Err (px) | P95 Ctr Err (px) | Mean Rad Err (%) | Med Rad Err (%) | Mean RMS (px) | Runtime (us/fit) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `STRATEGY_A = KASA_ALGEBRAIC_FIT` | `6.047` | `0.625` | `32.495` | `17.29%` | `2.60%` | `0.587` | `1059.5` |
| **`STRATEGY_B = TAUBIN_ALGEBRAIC_FIT`** | **`0.744`** | **`0.226`** | **`2.617`** | **`3.13%`** | **`0.78%`** | **`0.621`** | **`522.5`** |
| `STRATEGY_C = PRATT_FIT` | `0.777` | `0.226` | `2.619` | `3.37%` | `0.79%` | `0.621` | `602.6` |
| `STRATEGY_D = OPENCV_MIN_ENCLOSING_CIRCLE_CONTROL` | `27.332` | `19.631` | `78.579` | `28.62%` | `29.43%` | `2.587` | `848.8` |
| `STRATEGY_E = RANSAC_TAUBIN_FIT` | `2.563` | `0.506` | `9.299` | `10.17%` | `1.39%` | `0.630` | `30481.9` |

### 12.2 Breakdown by Sweep Angle (Clean Arcs, Mean Center Error px / Mean Radius Error %, `[MEASURED]`)

| Sweep | `KASA` | `TAUBIN` | `PRATT` | `MIN_ENC_CTRL` |
|---:|---:|---:|---:|---:|
| `30°` | `26.828px / 68.18%` | **`2.543px / 11.49%`** | `2.768px / 12.66%` | `52.492px / 73.96%` |
| `45°` | `13.457px / 44.36%` | **`1.454px / 6.72%`** | `1.484px / 7.45%` | `48.620px / 61.60%` |
| `60°` | `5.862px / 19.60%` | **`0.761px / 3.24%`** | `0.762px / 3.24%` | `46.501px / 49.40%` |
| `90°` | `1.728px / 4.94%` | **`0.444px / 1.44%`** | `0.438px / 1.42%` | `38.467px / 28.43%` |
| `120°` | `0.388px / 0.87%` | **`0.312px / 0.77%`** | `0.315px / 0.78%` | `25.814px / 12.11%` |
| `180°` | `0.072px / 0.30%` | **`0.228px / 0.56%`** | `0.230px / 0.56%` | `5.217px / 1.15%` |
| `240°` | `0.025px / 0.05%` | **`0.130px / 0.44%`** | `0.131px / 0.45%` | `1.209px / 1.38%` |
| `300°` | `0.015px / 0.04%` | **`0.083px / 0.36%`** | `0.083px / 0.36%` | `0.340px / 0.96%` |

---

## Section 13: True Arc Matrix (`[MEASURED]`)

- **Script:** [`test_true_arc_matrix.py`](test_true_arc_matrix.py)
- **Method:** Distance-transform-squared weighted Taubin fit (`fit_taubin_weighted`) for center/radius estimation combined with un-eroded foreground-ring angular support and round-cap overhang compensation $\delta\theta = \text{atan2}(\max(0, d_{\max} - 1), R)$.

### 13.1 Part A: Radius $\times$ Sweep ($w=2\text{ px}$, $\theta_{\text{start}}=30^\circ$, 77 Combinations, `[MEASURED]`)

| Sweep (deg) | Mean Ctr Err (px) | Mean Rad Err (%) | Mean Sweep Err (deg) | Mean Endpt Err (px) | Arc Classified ($R \ge 12\text{ px}$) |
|---:|---:|---:|---:|---:|---:|
| `15°` | `40.487` | `72.46%` | `6.14°` | `0.818` | `0/5` (Fail-closed: too shallow) |
| `30°` | `7.367` | `17.34%` | `1.39°` | `0.388` | `2/5` (`R=80,120` only) |
| `45°` | `3.195` | `6.31%` | `0.92°` | `0.354` | `3/5` (`R=40,80,120`, sagitta $\ge 2.2\text{ px}$) |
| `60°` | `0.946` | `2.65%` | `0.62°` | `0.303` | `4/5` (`R=20,40,80,120`) |
| `90°` | `0.343` | `1.20%` | `0.56°` | `0.289` | `5/5 (100%)` |
| `120°` | `0.301` | `0.78%` | `0.54°` | `0.287` | `5/5 (100%)` |
| `180°` | `0.159` | `0.57%` | `0.53°` | `0.193` | `5/5 (100%)` |
| `240°` | `0.106` | `0.54%` | `0.59°` | `0.251` | `5/5 (100%)` |
| `270°` | `0.070` | `0.57%` | `0.52°` | `0.190` | `5/5 (100%)` |
| `300°` | `0.056` | `0.60%` | `0.52°` | `0.192` | `5/5 (100%)` |
| `330°` | `0.068` | `0.53%` | `1.37°` | `0.233` | `5/5 (100%)` |

### 13.2 Part B: Start Angle $\times$ Stroke Width ($R=40\text{ px}$, Sweeps $90^\circ, 180^\circ$, $\theta_{\text{start}} \in \{0^\circ, 30^\circ, 90^\circ, 135^\circ, 225^\circ\}$, `[MEASURED]`)

| Stroke Width (px) | Mean Ctr Err (px) | Mean Rad Err (%) | Mean Sweep Err (deg) | Mean Start Endpt Err (px) | Mean End Endpt Err (px) | Arc Classified |
|---:|---:|---:|---:|---:|---:|---:|
| `1 px` | `0.138` | `0.36%` | `1.32°` | `0.424` | `0.499` | `10/10 (100%)` |
| `2 px` | `0.158` | `0.59%` | `0.44°` | `0.138` | `0.128` | `10/10 (100%)` |
| `3 px` | `0.316` | `0.54%` | `1.12°` | `0.228` | `0.415` | `10/10 (100%)` |
| `5 px` | `0.260` | `0.84%` | `0.55°` | `0.214` | `0.230` | `10/10 (100%)` |
| `8 px` | `0.235` | `0.62%` | `0.47°` | `0.251` | `0.195` | `10/10 (100%)` |

### 13.3 Part C: Anti-Aliased (`LINE_AA`) vs Non-Antialiased (`LINE_8`) Control ($R=40\text{ px}$, $w=2\text{ px}$, `[MEASURED]`)
- `NON_AA (LINE_8)`: `MeanCtrErr = 0.279 px`, `MeanRadErr = 1.01%`, `MeanSweepErr = 0.66°`, `MeanEndptErr = 0.244 px`
- `AA (LINE_AA)`: `MeanCtrErr = 0.185 px`, `MeanRadErr = 1.04%`, `MeanSweepErr = 1.54°`, `MeanEndptErr = 0.592 px`

---

## Section 14: Three Critical Failure Modes (`[MEASURED]`)

### 14A. ARC vs LINE Discrimination ([`test_arc_vs_line_discrimination.py`](test_arc_vs_line_discrimination.py))
- **Gates:**
  - `CURVATURE_INSUFFICIENT_FOR_ARC`: `line_rms <= 0.65 px` OR `sagitta_px < 2.2 px` OR `sweep_deg < 44.0°` OR `circle_rms / line_rms > 0.45`.
  - `PIECEWISE_LINEAR_NOT_ARC`: `approxPolyDP` with $\le 3$ straight segments where `poly_rms < 0.75 * circle_rms`.
  - `RESIDUAL_TOO_HIGH_NOT_ARC`: `circle_rms > max(0.75, 0.04 * r)`.
- **Measured Result (21 Fixtures):**
  - Straight lines ($0^\circ, 23^\circ, 45^\circ, 90^\circ$), shallow arcs ($15^\circ, 30^\circ$), and large-radius shallow arcs ($R=400\text{ px}/14^\circ$, $R=800\text{ px}/7^\circ$, $R=1200\text{ px}/5^\circ$) $\rightarrow$ `CURVATURE_INSUFFICIENT_FOR_ARC`.
  - Two-segment corners ($90^\circ, 120^\circ, 150^\circ$) and three-segment polyline $\rightarrow$ `RESIDUAL_TOO_HIGH_NOT_ARC` / `PIECEWISE_LINEAR_NOT_ARC`.
  - True arcs ($45^\circ, 60^\circ, 90^\circ$ at $R=40, 80\text{ px}$) $\rightarrow$ `TRUE_ARC`.
  - `FALSE_ARC_DETECTIONS_ON_SHALLOW_OR_LINEAR_GEOMETRY = 0`.

### 14B. ARC vs CIRCLE Boundary ([`test_arc_vs_circle_boundary.py`](test_arc_vs_circle_boundary.py))
- Tested $\Delta\theta \in \{300^\circ, 330^\circ, 345^\circ, 350^\circ, 355^\circ, 360^\circ\}$ across $R \in \{25, 50, 90\}\text{ px}$:
  - $300^\circ, 330^\circ \rightarrow$ `ARC` (`MaxGap = 30.1°..61.3°`, `ClosedLoop = False`).
  - $345^\circ, 350^\circ, 355^\circ$ (open loop, $8^\circ < \text{MaxGap} < 22^\circ$) $\rightarrow$ `AMBIGUOUS_NEAR_FULL_CIRCLE` (`ARC=0, CIRCLE=0`, fail-closed).
  - $360^\circ$ (closed loop with `RETR_CCOMP` inner hole and $\text{MaxGap} \le 8^\circ$) $\rightarrow$ `CIRCLE` (`ARC=0, CIRCLE=1`).
  - `DUAL_EMISSION_VIOLATIONS = 0`.

### 14C. Thick-Stroke Arc Duplication ([`test_thick_stroke_arc_duplication.py`](test_thick_stroke_arc_duplication.py))
- Tested across stroke widths $w \in \{1, 2, 3, 5, 8, 10, 15\}\text{ px}$ ($R=60\text{ px}, \Delta\theta=120^\circ$):
  - `M1 (Independent Canny Edge Fits)`: `7/7 (100.0%)` duplicate inner/outer arcs (`MeanRadErr = 3.210 px`, `MaxRadErr = 8.551 px`).
  - `M2 (Outer Contour Boundary Fit)`: `0/7 (0.0%)` duplicates, `MeanRadErr = 0.369 px`.
  - `M3 (Candidate-Local Skeletonization)`: `0/7 (0.0%)` duplicates, `MeanRadErr = 0.276 px`.
  - **`M4 (Candidate-Local Medial Distance Evidence)`**: **`0/7 (0.0%)` duplicates, `MeanRadErr = 0.205 px`**.

---

## Section 15: Short-Span Conditioning (`[MEASURED]` & `[SYNTHETIC_DISCRIMINATOR]`)

- **Script:** [`test_short_span_conditioning.py`](test_short_span_conditioning.py)
- Evaluated under $\pm 0.35\text{ px}$ transverse quantization/scan jitter (25 Monte Carlo trials per configuration) across $\Delta\theta \in \{15^\circ, 30^\circ, 45^\circ, 60^\circ, 90^\circ\}$ and $R \in \{12, 20, 40, 80, 120\}\text{ px}$:
  - `15°`: `0/5` stable (`MeanCleanRadErr = 51.79%`, `MeanJitterRadErr = 62.18%`)
  - `30°`: `2/5` stable (`R=80,120` only; `MeanJitterRadErr = 17.28%`)
  - `45°`: `3/5` stable (`R=40,80,120`; `MeanCleanRadErr = 4.54%`, `MeanJitterRadErr = 6.74%`)
  - `60°`: `4/5` stable (`R=20,40,80,120`; `MeanCleanRadErr = 1.98%`, `MeanJitterRadErr = 3.15%`)
  - `90°`: `5/5` stable (`R=12..120`; `MeanCleanRadErr = 1.01%`, `MeanJitterRadErr = 1.24%`)
- **`MIN_STABLE_ARC_SWEEP = 45.0 deg`** coupled with `sagitta_px >= 2.2 px` and `R >= 12.0 px` (`[SYNTHETIC_DISCRIMINATOR]`).

---

## Section 16: Angular Support and Wrap-Around (`[MEASURED]`)

- **Script:** [`test_angular_wrap_endpoints_and_cad_contract.py`](test_angular_wrap_endpoints_and_cad_contract.py)
- **Method:** Maps support samples to $[0^\circ, 360^\circ)$, sorts occupied angles, locates the largest circular gap (including the wrap gap $\theta_0 + 360^\circ - \theta_{N-1}$), and defines the complementary supported interval $[\theta_{\text{start}}, \theta_{\text{end}}]$ advancing across $0^\circ/360^\circ$ when $\theta_{\text{start}} > \theta_{\text{end}}$.

| Case | `EXPECTED_SWEEP` | `MEASURED_SWEEP` | Sweep Error | `LARGEST_UNSUPPORTED_GAP` | `START_SUPPORT` | `END_SUPPORT` | `WRAP_AROUND_HANDLED` |
|---|---:|---:|---:|---:|---:|---:|---|
| `Wrap 330->30 (60deg)` | `60.0°` | `60.17°` | `0.17°` | `299.83°` | `329.93°` | `30.10°` | `True` |
| `Wrap 350->10 (20deg)` | `20.0°` | `19.38°` | `0.62°` | `340.62°` | `350.31°` | `9.69°` | `True` |
| `Wrap 270->45 (135deg)` | `135.0°` | `134.93°` | `0.07°` | `225.07°` | `269.90°` | `44.83°` | `True` |
| `Wrap 315->135 (180deg)` | `180.0°` | `179.76°` | `0.24°` | `180.24°` | `315.12°` | `134.88°` | `True` |
| `Control 60->120 (60deg)` | `60.0°` | `60.55°` | `0.55°` | `299.45°` | `59.73°` | `120.28°` | `True` |
| `Control 80->100 (20deg)` | `20.0°` | `19.38°` | `0.62°` | `340.62°` | `80.31°` | `99.69°` | `True` |
| `Control 0->135 (135deg)` | `135.0°` | `134.91°` | `0.09°` | `225.09°` | `359.92°` | `134.84°` | `True` |
| `Control 45->225 (180deg)` | `180.0°` | `179.74°` | `0.26°` | `180.26°` | `45.13°` | `224.87°` | `True` |

- `WRAP_AROUND_MEAN_SWEEP_ERR_DEG = 0.273° (max = 0.616°)` vs `NON_WRAP_CTRL_MEAN_SWEEP_ERR_DEG = 0.378° (max = 0.616°)`.

---

## Section 17: Endpoint Recovery (`[MEASURED]`)

- **Script:** [`test_angular_wrap_endpoints_and_cad_contract.py`](test_angular_wrap_endpoints_and_cad_contract.py)
- Evaluated across 15 scenarios covering clean thin strokes ($w=1,2\text{ px}$), thick strokes ($w=5,8\text{ px}$), anti-aliasing (`LINE_AA`), $5^\circ/10^\circ$ missing endpoint erosion, wrap-around ($315^\circ\to 45^\circ$, $270^\circ\to 45^\circ$), and nearby tangent stub contamination:

| Estimator | Mean Start Err (px) | Mean End Err (px) | P95 Start Err (All) | P95 End Err (All) | Clean+Thick+AA+Wrap P95 (px) |
|---|---:|---:|---:|---:|---:|
| `A_EXTREME_ANGLE` | `2.649` | `2.353` | `6.588` | `5.047` | `3.623` |
| `B_SKELETON_PROJ` | `3.172` | `3.330` | `9.986` | `11.156` | `5.959` |
| `C_PERCENTILE_98` | `2.242` | `2.064` | `6.838` | `6.838` | `3.851` |
| **`D_RING_CAP_COMP`** | **`1.481`** | **`1.237`** | **`5.956`** | **`5.956`** | **`0.796`** |
| `E_TANGENT_ORACLE` | `1.221` | `1.237` | `5.956` | `5.956` | `0.760` |

- **`BEST_ENDPOINT_METHOD`**: `D_RING_CAP_COMP` (foreground-ring angular support + round-cap overhang compensation $\delta\theta = \text{atan2}(\max(0, d_{\max}-1), R)$).
- **`START_ENDPOINT_P95_ERROR_PX`**: `0.796 px` on intact strokes (`2.124 px` with unstripped tangent stub; `5.956 px` when $10^\circ$ of physical ink is erased at the endpoints).
- **`END_ENDPOINT_P95_ERROR_PX`**: `0.709 px` on intact strokes (`5.956 px` when $10^\circ$ of physical ink is erased).
- **`ENDPOINT_FAILURE_MODE`**: Physical ink dropout at arc extremities ($5^\circ\text{–}10^\circ$ missing ink) shifts recovered endpoints inward by the exact missing arc length $R \Delta\theta_{\text{missing}}$ unless an adjacent tangent line provides an intersection oracle (`E_TANGENT_ORACLE`). Line topology is NOT required for standard endpoint recovery.

---

## Section 18: Pixel $\rightarrow$ CAD Angle Contract (`[MEASURED]` & `[INFERENCE]`)

- **Script:** [`test_angular_wrap_endpoints_and_cad_contract.py`](test_angular_wrap_endpoints_and_cad_contract.py)
- **Inspected Owners:** `primitive_ir_lib/models.py:241-245` (`Calibration.pixel_to_cad`), `dxf_builder_lib/builder.py:347-356` (`msp.add_arc`), `dxf_builder_lib/reviewer.py:171-199` (`ConstructionArc`).
- **Mathematical Proof (`[INFERENCE]`):**
  1. `PIXEL_ANGLE_CONVENTION`: Origin top-left, $+x$ right, $+y$ down; $\theta_{\text{px}} = \text{atan2}(y_{\text{px}} - c_{y,\text{px}}, x_{\text{px}} - c_{x,\text{px}}) \bmod 360^\circ$ increases **clockwise (CW)**.
  2. `CAD_ANGLE_CONVENTION`: Origin bottom-left (`origin_px`), $+x$ right, $+y$ up; $\theta_{\text{cad}} = \text{atan2}(y_{\text{cad}} - c_{y,\text{cad}}, x_{\text{cad}} - c_{x,\text{cad}}) \bmod 360^\circ$ increases **counter-clockwise (CCW)**.
  3. `ARC_DIRECTION_CONVENTION`: DXF `ARC` (`ezdxf.math.ConstructionArc` and AutoCAD `AcDbArc`) always sweeps **CCW** from `start_angle_deg` to `end_angle_deg`.
  4. `ANGLE_TRANSFORM`: Because `Calibration.pixel_to_cad` reflects across the horizontal axis ($x_{\text{cad}} = s(x_{\text{px}} - x_0)$, $y_{\text{cad}} = s(y_0 - y_{\text{px}})$, Jacobian determinant $\det J = -s^2 < 0$), orientation is reversed: a CW pixel arc from $P_{\text{start,px}}$ to $P_{\text{end,px}}$ becomes a CCW CAD arc starting at $P_2 = \text{pixel\_to\_cad}(P_{\text{end,px}})$ and ending at $P_1 = \text{pixel\_to\_cad}(P_{\text{start,px}})$.
  5. **General Endpoint-Derived CAD Angle Rule:** Calibrate physical points $P_1 = \text{pixel\_to\_cad}(P_{\text{start,px}})$, $P_2 = \text{pixel\_to\_cad}(P_{\text{end,px}})$, and interior arc midpoint $P_m = \text{pixel\_to\_cad}(P_{\text{mid,px}})$. Compute $\alpha_1, \alpha_2, \alpha_m \in [0^\circ, 360^\circ)$ around $C_{\text{cad}}$. If $(\alpha_m - \alpha_1) \bmod 360^\circ \le (\alpha_2 - \alpha_1) \bmod 360^\circ$, set $(\text{start\_angle\_deg}, \text{end\_angle\_deg}) = (\alpha_1, \alpha_2)$; else set $(\alpha_2, \alpha_1)$. Under standard Y-flip, this reduces identically to:
     $$\text{start\_angle\_deg}_{\text{CAD}} = (360^\circ - \theta_{\text{end,px}}) \bmod 360^\circ, \quad \text{end\_angle\_deg}_{\text{CAD}} = (360^\circ - \theta_{\text{start,px}}) \bmod 360^\circ$$
- **Measured Verification across 10 Source Arcs ($0^\circ, 30^\circ, 90^\circ, 135^\circ, 180^\circ, 225^\circ, 270^\circ, 315^\circ$ + wrap cases, $s=0.5\text{ mm/px}$, `[MEASURED]`):**
  - `EXACT_TRANSFORM_LAW_MAX_ERROR_MM = 2.25e-14 mm`
  - `CAD_START_ENDPOINT_ERROR = 0.0887 mm mean (0.2394 mm max)` (`0.177 px` mean)
  - `CAD_END_ENDPOINT_ERROR = 0.0636 mm mean (0.1130 mm max)` (`0.127 px` mean)

---

## Section 19: False-Positive Negative Matrix (`[MEASURED]`)

- **Script:** [`test_negative_matrix_and_ellipse_control.py`](test_negative_matrix_and_ellipse_control.py)
- Evaluated across 51 negative-control fixtures spanning 7 major families (`LINE`, `HATCH`, `CORNER`, `NOISE`, `CIRCLE`, `ELLIPSE`, and `TEXT` glyphs `C, G, O, 0, 8, S, U, J, )` at 3 font scales/stroke widths `(0.9/1px, 1.6/2px, 2.2/3px)`):

| Family | Fixtures Tested | `RAW_CANDIDATE_CHAINS` | `CIRCULAR_FITS` | `ACCEPTED_ARCS` (`FALSE_ARCS`) | Primary Rejection Reasons |
|---|---:|---:|---:|---:|---|
| `TEXT` (`C,G,O,0,8,S,U,J,)`) | `27` | `27` | `18` | **`0`** | `CLOSED_LOOP_TOPOLOGY` (`O,0,8`), `NON_UNIFORM_CURVATURE_OR_ELLIPSE` (`C,U,J,)`), `NEAR_FULL_CIRCLE` / `RADIUS_OUT_OF_BOUNDS` (`G,S`) |
| `HATCH` (grid, cross, dense) | `3` | `25` | `23` | **`0`** | `CLOSED_LOOP_TOPOLOGY`, `FIT_DEGENERATE` |
| `CORNER` (90°, 45°, 25°, arrow, rect, rounded rect, capsule) | `10` | `10` | `7` | **`0`** | `PIECEWISE_LINEAR_NOT_ARC`, `CURVATURE_INSUFFICIENT_FOR_ARC`, `CLOSED_LOOP_TOPOLOGY`, `FIT_DEGENERATE` |
| `LINE` (straight w=1,2,5; parallel 4x) | `4` | `7` | `7` | **`0`** | `FIT_DEGENERATE`, `RADIUS_OUT_OF_BOUNDS` |
| `CIRCLE` (full R=40,70; concentric) | `3` | `4` | `0` | **`0`** | `CLOSED_LOOP_TOPOLOGY` |
| `ELLIPSE` (closed & 180° open 75x40) | `2` | `2` | `1` | **`0`** | `CLOSED_LOOP_TOPOLOGY`, `NON_UNIFORM_CURVATURE_OR_ELLIPSE` |
| `NOISE` (random salt, speckle arc) | `2` | `125` | `10` | **`0`** | `TOO_FEW_PIXELS`, `RADIUS_OUT_OF_BOUNDS` |
| **TOTAL** | **`51`** | **`200`** | **`66`** | **`0`** | **100.0% Negative Rejection** |

- `TEXT_FALSE_ARCS = 0`
- `HATCH_FALSE_ARCS = 0`
- `CORNER_FALSE_ARCS = 0`
- `LINE_FALSE_ARCS = 0`
- `CIRCLE_FALSE_ARCS = 0`
- `TOTAL_FALSE_ARCS = 0`

---

## Section 20: Ellipse Control (`[MEASURED]` & `[SYNTHETIC_DISCRIMINATOR]`)

- **Script:** [`test_negative_matrix_and_ellipse_control.py`](test_negative_matrix_and_ellipse_control.py)
- Tested axis ratios $a/b \in \{1.00, 1.05, 1.10, 1.20, 1.50, 2.00\}$ ($b=50\text{ px}$), partial sweeps $\{45^\circ, 60^\circ, 90^\circ, 120^\circ, 180^\circ, 270^\circ\}$, and orientations $\{0^\circ, 30^\circ, 45^\circ, 90^\circ\}$ (24 configurations per axis ratio):

| Axis Ratio ($a/b$) | Sweeps $\ge 90^\circ$ Accepted | Sweeps $45^\circ\text{–}60^\circ$ Accepted | Total Accepted (All Sweeps) | Mean Radial RMS ($\ge 90^\circ$) | Mean CurvVar ($\ge 90^\circ$) | Mean Radius Drift (%) |
|---:|---:|---:|---:|---:|---:|---:|
| `1.00` (Circle Control) | **`16/16 (100.0%)`** | `6/8 (75.0%)` | `22/24 (91.7%)` | `0.381 px` | `0.043` | `0.39%` |
| `1.05` (Near-Circle) | `11/16 (68.8%)` | `8/8 (100.0%)` | `19/24 (79.2%)` | `0.485 px` | `0.064` | `2.15%` |
| `1.10` (Mild Ellipse) | `6/16 (37.5%)` | `7/8 (87.5%)` | `13/24 (54.2%)` | `0.775 px` | `0.139` | `4.58%` |
| `1.20` (Moderate Ellipse) | **`0/16 (0.0%)`** | `7/8 (87.5%)` | `7/24 (29.2%)` | `1.307 px` | `0.253` | `9.29%` |
| `1.50` (Strong Ellipse) | **`0/16 (0.0%)`** | `8/8 (100.0%)` | `8/24 (33.3%)` | `2.996 px` | `0.570` | `22.51%` |
| `2.00` (High Aspect Ellipse) | **`0/16 (0.0%)`** | `5/8 (62.5%)` | `5/24 (20.8%)` | `5.488 px` | `0.900` | `43.41%` |

- **`ELLIPSE_FALSE_ARC_RATE`**: `0.0% (0/48)` for $a/b \ge 1.20$ and $\Delta\theta \ge 90^\circ$; `32.5% (39/120)` across all non-circular ratios $1.05\text{–}2.00$ when including short $45^\circ\text{–}60^\circ$ osculating segments and near-circular $1.05\text{–}1.10$ ratios.
- **`MIN_AXIS_RATIO_RELIABLY_REJECTED`**: `1.20` for angular extents $\Delta\theta \ge 90^\circ$ (`[SYNTHETIC_DISCRIMINATOR]`).
- **`ELLIPSE_AMBIGUITY_BOUNDARY`**: For short angular extents $\Delta\theta \in [45^\circ, 60^\circ]$ or near-circular ratios $a/b \in [1.05, 1.10]$, an elliptical arc's deviation from its osculating circle over the rasterized span is $0.36\text{–}0.43\text{ px}$ — below the $1\text{ px}$ integer pixel staircase quantization floor ($\approx 0.39\text{ px}$). Pixel evidence alone cannot distinguish a $45^\circ\text{–}60^\circ$ elliptical segment from a circular arc without external semantic/dimension context (`[SYNTHETIC_DISCRIMINATOR]`).

---

## Section 21: Degenerate / Numeric Safety (`[MEASURED]`)

- **Script:** [`test_degenerate_occluded_and_fillet_interactions.py`](test_degenerate_occluded_and_fillet_interactions.py)
- Swept candidate point counts $N \in \{3, 4, 5, 8, 12, 20, 50, 100, 260\}$ across clean arcs, duplicate points, all-identical points, exact collinear points, near-collinear points ($\sigma_\perp = 10^{-5}\text{ px}$), plus 7 extreme numeric cases (`VeryShortChain(L=1.5px)`, `LargeCoordOffset(1e6)`, `TinyRadius(R=0.8px)`, `HugeRadius(R=1e5px)`, `QuantizedPixels(R=40)`, `NearZeroVariance(1e-9)`, `ShortSpanQuantized(5deg)`) — 52 total test cases:
  - `STATE_FIT_OK = 7` (all 7 valid circular point sets with $N \ge 12$, including `LargeCoordOffset(1e6)` thanks to centroid/RMS pre-normalization)
  - `STATE_FIT_DEGENERATE = 24` (identical, duplicate, exact/near collinear, near-zero variance, tiny span)
  - `STATE_FIT_NUMERICALLY_UNSTABLE = 1` (`HugeRadius(R=1e5px)` over $0.05^\circ$ span)
  - `STATE_INSUFFICIENT_POINTS = 20` (all cases with $N \in \{3, 4, 5, 8\} < 12$)
- **`MIN_POINT_COUNT_DISCRIMINATOR = 12`** (`[SYNTHETIC_DISCRIMINATOR]`)
- **`NUMERIC_FAILURE_CASES = 0`** uncontrolled failures (all 45 degenerate/under-determined inputs terminated in controlled rejection states)
- **`NONFINITE_OUTPUT_COUNT = 0`** (`0` `NaN`, `0` `Inf`, `0` negative radii, `0` invalid confidences)

---

## Section 22: Broken / Occluded / Dashed Arc (`[MEASURED]`)

- **Script:** [`test_degenerate_occluded_and_fillet_interactions.py`](test_degenerate_occluded_and_fillet_interactions.py)
- **22A. Broken / Occluded Arcs ($0^\circ\to 180^\circ, R=60\text{ px}$ with missing sector $5^\circ, 10^\circ, 20^\circ, 30^\circ, 45^\circ, 60^\circ$ at `near_start`, `midpoint`, `near_end`):**
  - Connected-component extraction never bridges a physical gap $> 1\text{ px}$ (`Components = 2` in all 18 cases).
  - When the gap is near the midpoint ($5^\circ\text{–}45^\circ$), both remaining sub-arcs exceed $45^\circ$ and are cleanly extracted as `SPLIT_TWO_VALID_ARCS` (`2` independent arcs).
  - When the gap is near an end (`near_start` at $20^\circ$) or reaches $60^\circ$, the short stub ($< 45^\circ$) fails closed while the long branch is extracted (`LONG_BRANCH_ONLY_SHORT_REJECTED`).
  - **`MAX_SAFE_GAP_DEG = NO_FIXED_SAFE_GAP_JUSTIFIED`** (bridging disconnected components across whitespace risks merging unrelated engineering features).
- **22B. Dashed Arcs (`10d/8d`, `15d/10d`, `20d/10d`, `25d/12d`, `35d/10d`):**
  - Individual dashes ($10^\circ\text{–}35^\circ$) fall below `MIN_STABLE_ARC_SWEEP = 45.0°` and are rejected (`AcceptedSubArcs = 0`, `WholeArcRecovered = False`).
  - **`DASHED_ARC_RESULT = DASHED_ARC_UNRESOLVED`** (recovering dashed arcs requires a multi-component co-circular grouping subsystem outside the scope of single-primitive extraction).

---

## Section 23: Line / Tangency / Fillet Interaction (`[MEASURED]`)

- **Script:** [`test_degenerate_occluded_and_fillet_interactions.py`](test_degenerate_occluded_and_fillet_interactions.py)
- Evaluated 8 line+arc interaction configurations ($R=50\text{ px}$), comparing naive unseparated connected-component fitting against **straight-line corridor subtraction** (subtracting accepted straight line corridors of half-width $2\text{ px}$ prior to arc component extraction):

| Interaction Case | Naive Center Drift (px) | Line-Subtracted Center Drift (px) | Line-Subtracted Radius Drift (px) | Endpoint Drift (px) | Radial Residual (px) |
|---|---:|---:|---:|---:|---:|
| `1. Line Tangent at Arc Endpoint` | `84.96` | **`0.217`** | `0.207` | `1.483` | `0.867` |
| `2. Line Tangent at Arc Midpoint` | `63.32` | **`0.169`** | `0.044` | `0.101` | `0.861` |
| `3. Line Crossing Arc` | `27.13` | **`0.035`** | `0.041` | `0.099` | `0.853` |
| `4. Quarter-Circle 90d Fillet + 2 Lines` | `54.67` | **`0.217`** | `0.214` | `2.868` | `0.873` |
| `5. Acute-Angle 60d Fillet (120d sweep)` | `34.20` | **`0.165`** | `0.163` | `2.730` | `0.856` |
| `6. Obtuse-Angle 120d Fillet (60d sweep)` | `75.26` | **`0.196`** | `0.193` | `2.558` | `0.877` |
| `7. T-Junction Near Arc Midpoint` | `70.23` | **`0.088`** | `0.087` | `0.106` | `0.845` |
| `8. Straight Segment Touching Arc End` | `375.19` | **`0.171`** | `0.154` | `1.587` | `0.845` |

- `POINT_CONTAMINATION`: `0.0%` of straight-line shaft pixels remain attached after line-corridor subtraction (vs $35\%\text{–}70\%$ contamination in naive connected components).
- `CENTER_DRIFT`: `0.157 px` mean (`0.035..0.217 px`) vs `98.12 px` mean without line subtraction.
- `RADIUS_DRIFT`: `0.138 px` mean (`0.041..0.214 px`).
- `START_ENDPOINT_DRIFT` / `END_ENDPOINT_DRIFT`: `1.441 px` mean (`0.099..2.868 px` due to the $2\text{ px}$ corridor bite at fillet tangency points; optional projection of $(c_x, c_y)$ onto the adjacent `RawLine` restores tangency endpoints to `< 0.25 px`).

---

## Section 24: Raw Arc Representation (`[FUTURE_PRODUCTION_PROPOSAL]`)

- **`PROPOSED_RAW_ARC_SHAPE`**: **`OPTION_A` with derived endpoint helper (or `OPTION_C` with read-only endpoint properties)** — specifically:
  ```python
  @dataclass
  class RawArc:
      id: str
      center_px: Tuple[float, float]
      radius_px: float
      start_angle_deg: float   # CW pixel polar angle in [0, 360)
      end_angle_deg: float     # CW pixel polar angle in [0, 360)
      confidence: float
      bbox_px: Tuple[int, int, int, int]

      def start_point_px(self) -> Tuple[float, float]:
          rad = math.radians(self.start_angle_deg)
          return (self.center_px[0] + self.radius_px * math.cos(rad),
                  self.center_px[1] + self.radius_px * math.sin(rad))

      def end_point_px(self) -> Tuple[float, float]:
          rad = math.radians(self.end_angle_deg)
          return (self.center_px[0] + self.radius_px * math.cos(rad),
                  self.center_px[1] + self.radius_px * math.sin(rad))

      def mid_point_px(self) -> Tuple[float, float]:
          sweep = (self.end_angle_deg - self.start_angle_deg) % 360.0
          mid_rad = math.radians((self.start_angle_deg + 0.5 * sweep) % 360.0)
          return (self.center_px[0] + self.radius_px * math.cos(mid_rad),
                  self.center_px[1] + self.radius_px * math.sin(mid_rad))
  ```
- **`WHY`**:
  1. Storing canonical `(center_px, radius_px, start_angle_deg, end_angle_deg)` avoids redundant state that could contradict itself (e.g., stored endpoints not lying on the circle `(center_px, radius_px)`).
  2. Providing deterministic `.start_point_px()`, `.end_point_px()`, and `.mid_point_px()` methods on `RawArc` allows `assemble.py:arc_to_primitive()` to calibrate the physical start/end/mid points through `calibration.pixel_to_cad(...)` and derive exact CCW CAD angles without assuming a hardcoded Y-flip formula.
  3. Matches the existing style of `RawLine` (which defines `.length_px()` as a method) and `RawCircle` in `primitive_ir_lib/geometry_extraction.py`.
- **`PUBLIC_SCHEMA_CHANGE_REQUIRED`**: **`NO`**. `primitive_ir.schema.json` (`ArcGeometry` at lines 183–193) and `primitive_ir_lib/models.py` (`ArcGeometry` at lines 77–89) already exist and require zero changes.

---

## Section 25: Circle / Arc / Line Ownership Contract (`[FUTURE_PRODUCTION_PROPOSAL]`)

Integrating findings from `CIRCLE_FALSE_POSITIVE_PERIMETER_VALIDATION_V1` and `THICK_LINE_CENTERLINE_NORMALIZATION_V1`:
- **`CIRCLE_ARC_OWNERSHIP_CONTRACT`**: **`D_WITH_SHARED_TOPOLOGY_PREFILTER`** — `extract_circles()` runs first (with perimeter support validation $\ge 75\%$ and max gap $\le 45^\circ$). Any component with closed-loop hole topology (`RETR_CCOMP` child hole) or matching an admitted `RawCircle` within $\|\mathbf{c}_{\text{arc}} - \mathbf{c}_{\text{circle}}\| \le \max(4.0\text{ px}, 0.15 R)$ and $|R_{\text{arc}} - R_{\text{circle}}| \le \max(4.0\text{ px}, 0.15 R)$ is excluded from `extract_arcs()`.
- **`LINE_ARC_PREPROCESSING_CONTRACT`**: `extract_lines()` runs second. Before extracting connected components for `extract_arcs()`, subtract the pixel corridors of admitted long `RawLine` segments (length $\ge 25\text{ px}$, corridor half-width $\approx \max(2\text{ px}, \hat{w}_{\text{stroke}}/2 + 1)$) from the binary foreground mask. This splits fillet arcs cleanly from straight tangents (`Section 23`) and prevents straight lines from ever being evaluated or emitted as giant-radius arcs.
- **`ADMISSION_ORDER`**:
  $$\text{1. } \texttt{extract\_circles()} \longrightarrow \text{2. } \texttt{extract\_lines()} \longrightarrow \text{3. } \texttt{extract\_arcs()}$$

---

## Section 26: Confidence Model (`[FUTURE_PRODUCTION_PROPOSAL]`)

- **`HARD_REJECTION_GATES`** (must all pass before confidence is computed; confidence never overrides a failed gate):
  1. `MIN_POINT_COUNT`: component pixel count $\ge 12$ and medial skeleton pixel count $\ge 8$.
  2. `OPEN_CURVE_TOPOLOGY`: zero interior holes (`RETR_CCOMP` child contour area $< 9\text{ px}^2$) and maximum angular gap $\Delta\theta_{\text{gap}} \ge 22.0^\circ$ (measured sweep $\le 338.0^\circ$).
  3. `RADIUS_BOUNDS`: $12.0\text{ px} \le R \le 2000.0\text{ px}$.
  4. `CURVATURE_AND_SAGITTA`: `line_rms > 0.65 px`, `sagitta_px >= 2.2 px`, `sweep_deg >= 44.0°`, and `circle_rms / line_rms <= 0.45`.
  5. `NOT_PIECEWISE_LINEAR`: `approxPolyDP` segment count $> 3$ OR `poly_rms >= 0.75 * circle_rms`.
  6. `CIRCULAR_UNIFORMITY`: no S-curve inflection (`cross1 * cross2 >= -4.0`), `circle_rms <= 0.58 px`, and for sweeps $\ge 85.0^\circ$, sub-arc radius drift `rel_r_drift <= 0.16` and center drift `rel_c_drift <= 0.12`.
  7. `CIRCLE_MUTUAL_EXCLUSION`: not within $\max(4.0\text{ px}, 0.15 R)$ in center and radius of any admitted `RawCircle`.
- **`PROPOSED_CONFIDENCE_MODEL`**:
  $$\text{confidence} = \text{round}\!\left(\text{clip}\!\left(0.50 + 0.49 \sum_{k=1}^{5} w_k s_k,\; 0.50,\; 0.99\right),\, 3\right)$$
- **`CONFIDENCE_COMPONENTS`**:
  - $s_{\text{res}} = \text{clip}(1 - \text{circle\_rms} / 0.60,\; 0, 1)$ ($w_1 = 0.30$)
  - $s_{\text{line}} = \text{clip}(1 - (\text{circle\_rms} / \text{line\_rms}) / 0.45,\; 0, 1)$ ($w_2 = 0.25$)
  - $s_{\text{sag}} = \text{clip}((\text{sagitta\_px} - 2.2) / 10.0,\; 0, 1)$ ($w_3 = 0.20$)
  - $s_{\text{curv}} = \text{clip}(1 - \text{rel\_r\_drift} / 0.20,\; 0, 1)$ ($w_4 = 0.15$)
  - $s_{\text{ambig}} = \text{clip}((\Delta\theta_{\text{gap}} - 22.0^\circ) / 38.0^\circ,\; 0, 1)$ ($w_5 = 0.10$)

---

## Section 27: Threshold Classification (`[SYNTHETIC_DISCRIMINATOR]` / `[SAFE_DIMENSIONLESS_BOUND]` / `[NEEDS_REAL_SCAN_CALIBRATION]`)

| `NAME` | `VALUE` | `UNIT` | `PURPOSE` | `SENSITIVITY` | `CLASSIFICATION` |
|---|---:|---|---|---|---|
| `MIN_POINT_COUNT_DISCRIMINATOR` | `12` | `pixels` | Prevent under-determined / noisy micro-component fits | Low ($8\text{–}15\text{ px}$ equivalent) | `SYNTHETIC_DISCRIMINATOR` |
| `MIN_MEDIAL_POINTS` | `8` | `pixels` | Ensure sufficient medial chain length for RMS & polyline checks | Low | `SYNTHETIC_DISCRIMINATOR` |
| `MIN_RADIUS_PX` | `12.0` | `px` | Reject tiny glyph hooks and noise specks | Moderate (depends on scan DPI) | `NEEDS_REAL_SCAN_CALIBRATION` |
| `MAX_RADIUS_PX` | `2000.0` | `px` | Reject near-collinear giant-radius fits | Low | `SYNTHETIC_DISCRIMINATOR` |
| `MIN_STABLE_ARC_SWEEP` | `44.0` (nominal `45.0`) | `deg` | Prevent ill-conditioned short-arc radius/center explosion | Moderate ($40^\circ\text{–}50^\circ$) | `SYNTHETIC_DISCRIMINATOR` |
| `MIN_SAGITTA_PX` | `2.2` | `px` | Ensure arc bulge exceeds $\ge 2\times$ pixel staircase quantization | High ($1.8\text{–}2.5\text{ px}$) | `SYNTHETIC_DISCRIMINATOR` |
| `MIN_LINE_RMS_FOR_ARC` | `0.65` | `px` | Reject straight/near-straight segments before circle comparison | Moderate ($0.55\text{–}0.80\text{ px}$) | `SYNTHETIC_DISCRIMINATOR` |
| `MAX_CIRCLE_OVER_LINE_RMS_RATIO` | `0.45` | `dimensionless` | Require circular fit to improve over linear fit by $> 2.2\times$ | Low ($0.40\text{–}0.55$) | `SAFE_DIMENSIONLESS_BOUND` |
| `MIN_POLYLINE_OVER_CIRCLE_RMS_RATIO` | `0.75` | `dimensionless` | Reject 2/3-segment corners/polylines where polygon fits better than circle | Low ($0.70\text{–}0.85$) | `SAFE_DIMENSIONLESS_BOUND` |
| `MAX_MEDIAL_RADIAL_RMS_PX` | `0.58` | `px` | Reject non-circular curves, rough glyphs, and large ellipses | High on noisy scans ($0.55\text{–}0.85\text{ px}$) | `NEEDS_REAL_SCAN_CALIBRATION` |
| `MAX_SUBARC_RADIUS_DRIFT` | `0.16` | `dimensionless` | Reject ellipses ($a/b \ge 1.20$) and variable-curvature `C/U/J` glyphs for sweeps $\ge 85^\circ$ | Moderate ($0.14\text{–}0.22$) | `SAFE_DIMENSIONLESS_BOUND` |
| `MAX_SUBARC_CENTER_DRIFT` | `0.12` | `dimensionless` | Reject non-circular bends whose local center of curvature shifts | Moderate ($0.10\text{–}0.16$) | `SAFE_DIMENSIONLESS_BOUND` |
| `NEAR_FULL_CIRCLE_MIN_GAP_DEG` | `22.0` | `deg` | Fail closed on $338^\circ\text{–}352^\circ$ near-full circles | Moderate ($15^\circ\text{–}25^\circ$) | `SYNTHETIC_DISCRIMINATOR` |
| `ROUND_CAP_OVERHANG_OFFSET_PX` | `1.0` | `px` | Compensate round stroke cap overhang $\max(0, d_{\max} - 1.0)$ | Low | `SYNTHETIC_DISCRIMINATOR` |

---

## Section 28: Raster Quality / Generalization (`[MEASURED]` & `[UNPROVEN_REAL_SCAN_GENERALIZATION]`)

- **Script:** [`test_degradation_and_performance_benchmark.py`](test_degradation_and_performance_benchmark.py)
- Evaluated across 5 true arcs ($90^\circ, 120^\circ, 180^\circ, 120^\circ\text{ wrap}, 270^\circ$) and 5 negative controls (straight line, $90^\circ$ corner, full circle, $180^\circ$ ellipse, glyph `'C'`) under 7 degradation modes:

| Degradation Mode | `TRUE_ARC_RECALL` | `FALSE_ARC_RATE` | `CENTER_ERROR` | `RADIUS_ERROR` | `SWEEP_ERROR` |
|---|---:|---:|---:|---:|---:|
| `1_CLEAN_BASELINE` | `5/5 (100%)` | `0/5 (0.0%)` | `0.081 px` | `0.16%` | `0.60°` |
| `2_GAUSSIAN_BLUR_3X3` | `5/5 (100%)` | `0/5 (0.0%)` | `0.084 px` | `0.16%` | `0.61°` |
| `3_SALT_PEPPER_NOISE` | `5/5 (100%)` | `0/5 (0.0%)` | `0.077 px` | `0.16%` | `0.63°` |
| `4_ANTI_ALIASED` | `5/5 (100%)` | `0/5 (0.0%)` | `0.098 px` | `0.22%` | `0.64°` |
| `5_ENDPOINT_EROSION_5DEG` | `5/5 (100%)` | `0/5 (0.0%)` | `0.151 px` | `0.22%` | `10.32°` ($5^\circ$ missing each end) |
| `6_JPEG_QUALITY_50` | `5/5 (100%)` | `0/5 (0.0%)` | `0.081 px` | `0.16%` | `0.60°` |
| `7_LOW_CONTRAST` | `5/5 (100%)` | `0/5 (0.0%)` | `0.081 px` | `0.16%` | `0.60°` |

- **`REAL_SCAN_GENERALIZATION = UNPROVEN`** (`[UNPROVEN_REAL_SCAN_GENERALIZATION]` — no private/customer scans used).

---

## Section 29: Sequential Performance Benchmark (`[MEASURED]`)

- **Script:** [`test_degradation_and_performance_benchmark.py`](test_degradation_and_performance_benchmark.py) (`PARALLEL_HEAVY_BENCHMARKS = 1`)

| Canvas Tier | `PREPROCESS_MS` | `COMPONENT_OR_CONTOUR_MS` | `CANDIDATE_FILTER_MS` | `FIT_MS` | `ARBITRATION_MS` | `TOTAL_ARC_STAGE_MS` | `CANDIDATES / FITS / ACCEPTED` |
|---|---:|---:|---:|---:|---:|---:|---:|
| `A. 300x300 Small Isolated ROI` | `0.08 ms` | `0.27 ms` | `0.34 ms` | `5.80 ms` | `1.18 ms` | **`7.67 ms`** | `7 / 4 / 2` (exp `2`) |
| `B. 1000x1000 Mixed Engineering Raster` | `0.95 ms` | `2.26 ms` | `1.89 ms` | `31.04 ms` | `6.04 ms` | **`42.18 ms`** | `63 / 27 / 9` (exp `9`) |
| `C. 2000x2000 Mixed Engineering Raster` | `3.68 ms` | `10.19 ms` | `10.65 ms` | `168.09 ms` | `32.38 ms` | **`225.00 ms`** | `343 / 147 / 49` (exp `49`) |

---

## Section 30: Selected Strategy (`[INFERENCE]` & `[FUTURE_PRODUCTION_PROPOSAL]`)

- **`SELECTED_STRATEGY`**: **`TAUBIN_WITH_CANDIDATE_LOCAL_MEDIAL_EVIDENCE`**
- **`WHY_SELECTED`**:
  1. **Algebraic Fit Accuracy & Speed:** Taubin (`0.744 px` mean center error, `3.13%` mean radius error, `522.5 us/fit`) eliminates Kåsa's short-sweep bias (`6.047 px`, `17.29%`) and outperforms OpenCV `minEnclosingCircle` (`27.332 px`, `28.62%`) while running faster than Pratt (`602.6 us/fit`).
  2. **Zero Thick-Stroke Duplication:** Weighting candidate pixels by squared Euclidean distance transform $w_i = D(x_i, y_i)^2$ (`M4`) with local medial skeleton residual checking yields `0/7 (0.0%)` duplicate arcs across stroke widths $1\text{–}15\text{ px}$ and the lowest radius error (`0.205 px` mean), whereas Canny edge fitting (`M1`) produces `100%` inner/outer duplicates.
  3. **Full Endpoint & Sweep Preservation:** Recovering angular support from the un-eroded foreground ring with round-cap overhang compensation avoids Zhang-Suen endpoint erosion (`0.44°..1.32°` sweep error across widths $1\text{–}8\text{ px}$, `0.796 px` P95 endpoint error).
  4. **Zero False Positives on Negative & Ellipse Controls:** Combining closed-loop topology filtering, line-corridor subtraction, piecewise-linear polyline rejection, and 3-window sub-arc curvature consistency achieves `0/51` false arcs on negative controls and `0/48` false arcs on ellipses with $a/b \ge 1.20, \Delta\theta \ge 90^\circ$.
- **`WHY_ALTERNATIVES_REJECTED`**:
  - `TAUBIN_CONTOUR_CHAIN_FIT`: Raw outer contour chains shift radius outward on thick strokes or split into inner+outer edges under Canny (`100%` duplication).
  - `TAUBIN_WITH_LOCAL_EDGE_PAIR_COLLAPSE`: As proven in `THICK_LINE_CENTERLINE_NORMALIZATION_V1`, post-fit inner/outer edge pairing fails when one edge fragments asymmetrically.
  - `TAUBIN_WITH_BOUNDED_RANSAC_PREFILTER`: $58\times$ slower (`30.5 ms/fit`) and degrades clean thick-stroke accuracy (`2.563 px` center error vs `0.744 px`). Line-corridor subtraction handles connected lines deterministically in `< 2 ms`.
  - `ALTERNATIVE_FIT_OUTPERFORMS_TAUBIN`: Falsified; Kåsa and `minEnclosingCircle` are severely biased on partial arcs, and Pratt offers no accuracy gain over Taubin.

---

## Section 31: Minimum Future Production Writeset (`[FUTURE_PRODUCTION_PROPOSAL]`)

- `PRIMARY_OWNER`: `primitive_ir_lib/geometry_extraction.py`
- `HELPER_OWNER`: `primitive_ir_lib/geometry_extraction.py` (private helpers `_fit_taubin_weighted`, `_compute_circular_support_interval`, `_evaluate_arc_candidate`, `extract_arcs`)
- `RAW_TYPE_OWNER`: `primitive_ir_lib/geometry_extraction.py` (`RawArc` dataclass and `RawGeometry.arcs: List[RawArc] = field(default_factory=list)`)
- `ASSEMBLY_OWNER`: `primitive_ir_lib/assemble.py` (`arc_to_primitive` and optional `raw_arcs: Optional[List[RawArc]] = None` in `build_document`)
- `TEST_OWNER`: `primitive_ir_lib/tests/test_basic.py`
- `SCHEMA_CHANGE_REQUIRED`: `NO` (`ArcGeometry` already exists in `primitive_ir.schema.json:183-193`)
- `ASSEMBLY_CHANGE_REQUIRED`: `YES` (`primitive_ir_lib/assemble.py`)
- `BUILDER_CHANGE_REQUIRED`: `NO` (`dxf_builder_lib/builder.py:347-356` already writes `ArcGeometry` via `msp.add_arc`)
- `NEW_MODULE_REQUIRED`: `NO`
- `NEW_DEPENDENCY_REQUIRED`: `NO`
- `MINIMUM_WRITESET`:
  1. `primitive_ir_lib/geometry_extraction.py`
  2. `primitive_ir_lib/assemble.py`
  3. `primitive_ir_lib/tests/test_basic.py`

---

## Section 32: Future Production GREEN Oracle (`[FUTURE_PRODUCTION_PROPOSAL]`)

1. `PUBLIC_CAUSAL_RED_FLIPS_GREEN`: Deterministic fixture with $90^\circ, 180^\circ, 270^\circ$ arcs, $360^\circ$ circle, and straight line emits `3` `RawArc` / `ArcGeometry` primitives (`TRUE_90_ARC=1`, `TRUE_180_ARC=1`, `TRUE_270_ARC=1`), `1` `CircleGeometry` (`FULL_CIRCLE=1`, `0` duplicate arcs), and `1` normalized `LineGeometry` (`STRAIGHT_LINE=1`, `0` giant-radius arcs).
2. `SHALLOW_AMBIGUOUS_CURVE`: $15^\circ\text{–}30^\circ$ shallow arcs and large-radius shallow curves ($s < 2.2\text{ px}$) fail closed (`0` arcs).
3. `THICK_ARC`: Stroke widths $1\text{–}15\text{ px}$ emit exactly `1` physical `RawArc` with `|R_fit - R_gt| <= 1.0 px` and `0` inner/outer duplicates.
4. `ELLIPSE`: Elliptical arcs with $a/b \ge 1.20$ and sweep $\ge 90^\circ$ are rejected (`0` false arcs).
5. `HATCH_TEXT_CORNER`: Bounded regression fixtures for hatch, text glyphs (`C, G, O, 0, 8, S, U, J, )`), and corners ($90^\circ, 45^\circ, 25^\circ$) emit `0` false arcs.
6. `WRAP_AROUND`: Arcs crossing $0^\circ/360^\circ$ (`330°->30°`, `270°->45°`, `315°->135°`) recover sweep within $\pm 1.5^\circ$ and endpoints within $\le 1.0\text{ px}$.
7. `CALIBRATION`: `arc_to_primitive` reconstructs DXF `ConstructionArc` start/end points matching `calibration.pixel_to_cad` physical endpoints within $\le 0.25\text{ mm}$ at $0.5\text{ mm/px}$.
8. `DEGENERATE`: Under-determined ($N < 12$), collinear, duplicate, and zero-variance point sets fail closed with `0` `NaN`/`Inf` outputs.
9. `BACKWARD_COMPATIBILITY`: `RawGeometry(lines=..., circles=...)` and `build_document(..., raw_lines, raw_circles, raw_texts)` remain 100% backward-compatible via default `arcs=field(default_factory=list)` and `raw_arcs: Optional[List[RawArc]] = None`.

---

## Section 33: Ready-for-Codex Decision

- **`SELECTED_OUTCOME`**: **`TAUBIN_ARC_EXTRACTION_V1_READY_FOR_CODEX`**
- **`READY_FOR_CODEX`**: **`YES`**
- **`BLOCKER`**: **`NONE`** (All 19 readiness gates satisfied with deterministic empirical evidence; `REAL_SCAN_GENERALIZATION=UNPROVEN` is explicitly labeled for future private-data benchmark gating).
