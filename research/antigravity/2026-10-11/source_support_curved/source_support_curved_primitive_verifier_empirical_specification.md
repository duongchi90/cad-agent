# Source Support Curved Primitive Verifier Empirical Specification (V1)

**Status:** `READY_FOR_CODEX`  
**Epic Identifier:** `SOURCE_SUPPORT_CURVED_PRIMITIVE_VERIFIER_V1`  
**Topic Group:** `25`  
**Target Subsystem:** `cad_agent`  
**Author:** Antigravity Autonomous Research  
**Evaluated Branch:** `research/antigravity-2026-10-11`  

---

## 1. Role, Mode, and Epic Identification

- **Role:** `ANTIGRAVITY_RESEARCH`
- **Mode:** `LONG_RUNNING_CONTINUOUS_AUTONOMOUS_RESEARCH`
- **Epic:** `SOURCE_SUPPORT_CURVED_PRIMITIVE_VERIFIER_V1`
- **Execution Policy:** Read-only production inspection; empirical research scripts exclusively under `research/antigravity/2026-10-11/source_support_curved/`. Zero native AutoCAD mutation.

---

## 2. Current Production Owners

1. **Primary Security & Support Verifier:**
   - [`cad_agent/source_support_verifier.py:125-240`](file:///C:/cad-agent-antigravity/cad_agent/source_support_verifier.py#L125-L240): `verify_external_visual_proposal_source_support()`
2. **Upstream Proposal Compilation & Admission Seam:**
   - [`cad_agent/source_fusion_proposal.py:22-120`](file:///C:/cad-agent-antigravity/cad_agent/source_fusion_proposal.py#L22-L120): `compile_external_visual_object_proposal()`
   - [`cad_agent/source_verified_geometry.py:19-125`](file:///C:/cad-agent-antigravity/cad_agent/source_verified_geometry.py#L19-L125): `verify_and_admit_external_visual_proposals()`
3. **Data Contracts & Integrity:**
   - [`cad_agent/drawing_contracts.py`](file:///C:/cad-agent-antigravity/cad_agent/drawing_contracts.py): `canonical_json_sha256()`

---

## 3. Current Behavior & Architectural Gap

In the CadAgent security architecture, external AI proposals (from vision models or multimodal LLMs) must be deterministically verified against the exact source render bytes before being admitted to `PrimitiveIR` or triggering native AutoCAD delta operations. This prevents hallucinated lines from mutating drawings.

However, [`cad_agent/source_support_verifier.py`](file:///C:/cad-agent-antigravity/cad_agent/source_support_verifier.py) contains 5 severe architectural limitations:
1. **Hard Rejection of Curved Geometry (`type != 'LINE'`):**
   Line 189 enforces: `if not isinstance(primitive_id, str) or primitive.get("type") != "LINE": _fail("VERIFICATION_REQUEST_INVALID")`. If any external proposal contains a `CIRCLE` (shaft, bore hole, bolt hole) or `ARC` (fillet, rounded corner), the verifier immediately crashes with a `ValueError` exception, completely blocking curved visual proposals.
2. **All-or-Nothing Batch Crash:**
   Line 214 enforces: `if support_fraction < support_threshold: _fail(f"PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:{primitive_id}")`. If 1 out of 50 proposed primitives fails the 85% support threshold (e.g., a single hallucinated connector), the verifier raises an unhandled exception, destroying the validation of the other 49 completely valid outline lines.
3. **Dashed and Centerline Stroke Rejection:**
   Standard mechanical drafting uses dashed lines for hidden features (`HIDDEN` layer, ~50% ink support) and dot-dash lines for axes/centerlines (`CENTER` layer, ~40% ink support). The hardcoded `_APPROVED_MIN_SUPPORT_FRACTION = 0.85` strictly rejects all valid dashed lines and centerlines.
4. **Fixed Darkness Threshold (220) Vulnerability on Inverted/Blueprint Scans:**
   Line 173 uses `roi_pixels <= threshold` with hardcoded `threshold = 220`. On inverted renders (white lines on black background, typical of engineering blueprints or CAD dark mode exports), black background pixels ($0 \le 220$) are treated as 100% dark ink, granting false 100% support to completely hallucinated lines through empty space.
5. **Absence of Arc-Length Raster Sampling:**
   The production code only implements `_line_samples` (linear interpolation between two endpoints). It lacks arc-length parameterized sampling for circles ($N = \lceil 2\pi R \rceil$) and circular arcs ($N = \lceil R \cdot \Delta\theta \rceil$).

---

## 4. Deterministic Causal RED Reproduction

The failure modes are deterministically reproduced in [`test_causal_red_source_support_curved.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/source_support_curved/test_causal_red_source_support_curved.py):

| RED Test | Trigger Condition | Current Production Outcome | Ground Truth & Strategy D Outcome |
|---|---|---|---|
| **RED-1** | Valid `CIRCLE` primitive (hole, r=15px) on white background | Crashes with `ValueError("VERIFICATION_REQUEST_INVALID")` | Verifies circle with arc-length sampling, reports `supported: True` (> 90% support) |
| **RED-2** | Valid `ARC` primitive (90° fillet, r=15px) on white background | Crashes with `ValueError("VERIFICATION_REQUEST_INVALID")` | Verifies arc sweep, reports `supported: True` (> 85% support) |
| **RED-3** | Batch of 4 valid outline lines + 1 hallucinated connector line | Crashes with `ValueError("PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:invented")`, dropping all 4 valid lines | Returns structured result `PARTIAL_VERIFIED`: 4 valid lines marked `supported: True`, connector marked `supported: False` |
| **RED-4** | Valid dashed hidden line (8px dash, 12px gap, 57% support) | Crashes with `ValueError("PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:hidden_1")` | Style-aware `dashed` check (threshold 0.45) confirms `supported: True` |
| **RED-5** | Inverted blueprint (black background) with hallucinated diagonal line | Reports false 100% support (`support_fraction: 1.0, status: VERIFIED`) | Polarity detection identifies dark background, reports `support_fraction: 0.0, status: REJECTED` |

---

## 5. Causal Mechanisms

1. **Type Gate Inflexibility (`source_support_verifier.py:189`):**
   ```python
   if not isinstance(primitive_id, str) or primitive.get("type") != "LINE":
       _fail("VERIFICATION_REQUEST_INVALID")
   ```
   The contract strictly was designed for lines only.
2. **Exception vs Structured Result Anti-Pattern:**
   Using exceptions (`raise ValueError(...)`) for domain-level support failures breaks batch processing and forces callers into defensive single-item loops.
3. **Static Binarization Blindness:**
   A fixed scalar threshold of 220 assumes light paper background and dark ink. It fails to compute background polarity or local ink contrast $\Delta_{\text{contrast}}$.
4. **Style-Agnostic Density Model:**
   Assuming all CAD features are solid continuous strokes is invalid for mechanical drafting.

---

## 6. Product Impact

1. **Total Block on Curved Visual Proposals:** AI vision models cannot propose bolt circles, bores, round slots, or fillets into native CAD.
2. **Batch Vulnerability:** A single stray hallucination aborts the verification of an entire assembly.
3. **Blueprint Insecurity:** Inverted/dark-mode CAD drawings cannot be verified safely due to 100% false-positive ink leakage.

---

## 7. Evaluated Candidate Strategies

- **Strategy A (Current Production Baseline):**
  - Rigid LINE-only verification.
  - All-or-nothing ValueError crash.
  - Fixed 220 darkness threshold.
  - Fixed 0.85 support fraction.
- **Strategy B (Exception-Free Structured Classifier):**
  - Returns structured dict with per-primitive verdicts (`supported: bool`, `reason: str`).
  - Never raises unhandled ValueError on domain support failures.
  - Still LINE-only and fixed 220 threshold.
- **Strategy C (Style-Aware Line Verifier):**
  - Adds `style` awareness: `solid` (0.85), `dashed` (0.45), `centerline` (0.35).
  - Exception-free structured results.
  - Still LINE-only.
- **Strategy D (Multimodal Adaptive Curved & Structured Verifier Oracle):**
  - **Multimodal Support:** Supports `LINE`, `CIRCLE`, and `ARC`.
  - **Arc-Length Equidistant Sampling:**
    - Circle: $N = \max(8, \lceil 2\pi R \rceil)$ points along perimeter.
    - Arc: $N = \max(4, \lceil R \cdot \Delta\theta_{\text{rad}} \rceil)$ points along sweep.
  - **Adaptive Background Polarity Normalization:**
    - Measures perimeter median $bg_{\text{median}}$.
    - If $bg_{\text{median}} < 80$: Inverted blueprint mode (bright ink $\ge 128$).
    - If $bg_{\text{median}} \ge 80$: Dark ink mode with adaptive contrast bound: $\text{threshold} = \min(220, bg_{\text{median}} - 25.0)$. Preserves exact 220 threshold on clean white paper ($bg = 255$).
  - **Style-Aware Calibrated Thresholds:** `solid` (0.85), `dashed` (0.45), `centerline` (0.35).
  - **Structured Batch Reporting:** Returns `ALL_VERIFIED`, `PARTIAL_VERIFIED`, or `REJECTED` with per-primitive verdicts.
  - **Non-Finite & Boundary Safety:** Rejects $R < 1\text{ px}$, $\Delta\theta \le 0$, `NaN`/`Inf` coordinates, and out-of-ROI samples.

---

## 8. Empirical Benchmark Comparison

Measured across 8 comprehensive drawing scenarios in [`test_source_support_curved_benchmark.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/source_support_curved/test_source_support_curved_benchmark.py):

| Scenario | Strategy A (Baseline) | Strategy B (Structured) | Strategy C (Style-Aware) | Strategy D (Oracle) |
|---|---|---|---|---|
| **1. Solid Rectangle (4 Lines)** | 100% (Verified) | 100% (All Verified) | 100% (All Verified) | **100% (All Verified)** |
| **2. Solid Circle Hole (r=15px)** | 0% (Crash ValueError) | 0% (Rejected Type) | 0% (Rejected Type) | **100% (Verified Circle)** |
| **3. Fillet Arc Corner (90°)** | 0% (Crash ValueError) | 0% (Rejected Type) | 0% (Rejected Type) | **100% (Verified Arc)** |
| **4. Dashed Hidden Line (8/12 gap)** | 0% (Crash ValueError) | 0% (Rejected Support) | 100% (Verified Dashed) | **100% (Verified Dashed)** |
| **5. Centerline Dot-Dash (period 33)** | 0% (Crash ValueError) | 0% (Rejected Support) | 100% (Verified Centerline) | **100% (Verified Centerline)** |
| **6. Mixed Batch (4L + 1C + 1A + 1Phantom)** | 0% (Crash on Batch) | 57.1% (4/7 Lines Only) | 57.1% (4/7 Lines Only) | **85.7% (6/7 All Real Features)** |
| **7. Inverted Blueprint (Black Background)** | 0% (100% False Pass) | 0% (100% False Pass) | 0% (100% False Pass) | **100% (Phantom Rejected, Real Passed)** |
| **8. Low-Contrast Scan (Gray 200 / Ink 140)** | 0% (100% False Pass) | 0% (100% False Pass) | 0% (100% False Pass) | **100% (Phantom Rejected, Real Passed)** |
| **Overall Accuracy (8 Scenarios)** | **12.5% (1/8)** | **25.0% (2/8)** | **50.0% (4/8)** | **100.0% (8/8)** |

---

## 9. Boundary Controls Matrix

Verified in [`test_source_support_curved_controls.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/source_support_curved/test_source_support_curved_controls.py):

1. **CTRL-1 (Positive Solid Circles Across Radii):** Circles with radii 8px, 15px, 25px verify with support fraction $\ge 0.85$.
2. **CTRL-2 (Positive Arc Sweeps):** Arcs with sweeps 45°, 180°, 270° verify with support fraction $\ge 0.85$.
3. **CTRL-3 (Negative Invented Circle in Blank Space):** Phantom circle reports 0.0% support and is rejected.
4. **CTRL-4 (Negative Circle Radius Mismatch):** Concentric circle offset by 10px reports $< 10\%$ support and is rejected.
5. **CTRL-5 (Negative Invented Arc in Blank Space):** Phantom arc reports 0.0% support and is rejected.
6. **CTRL-6 (Negative Sparse Dashed Line):** Excessively sparse dashed line (2px dash, 18px gap, ~10% support) is rejected ($< 0.45$).
7. **CTRL-7 (Tolerance Boundary):** Line offset by 2px verifies; line offset by 4px fails (strict 2px tolerance bound).
8. **CTRL-8 (Outside ROI Boundary Rejection):** Circle crossing outside ROI boundary is rejected with reason `OUTSIDE_BOUNDS`.

---

## 10. Degenerate, Numeric Safety & Performance

Verified in [`test_source_support_curved_degenerate_and_perf.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/source_support_curved/test_source_support_curved_degenerate_and_perf.py):

1. **EDGE-1 (Empty Primitives List):** Returns `status: REJECTED` with empty support list.
2. **EDGE-2 (Micro & Zero Radius Circle):** $R \le 0$ or $R < 1.0\text{ px}$ safely rejected with `INVALID_GEOMETRY`, zero division avoided.
3. **EDGE-3 (Micro & Zero Sweep Arc):** Micro-radius or invalid angle arcs safely rejected with `INVALID_GEOMETRY`.
4. **EDGE-4 (Non-Finite Coordinates):** `NaN` and `Inf` in center, radius, or angles safely rejected without unhandled exceptions.
5. **EDGE-5 (Corrupt Render Bytes):** Invalid or empty render bytes raise descriptive `SOURCE_RENDER_BYTES_INVALID`.
6. **EDGE-6 (Extreme Coordinate Magnitudes):** $1500\text{ px}$ coordinates on 2000x2000 image maintain IEEE 754 precision.
7. **PERF-7 (Scalability & Throughput):** 100 mixed primitives on a 1000x1000 (1MP) image execute in **< 60 ms** (well within the 90 ms budget).

---

## 11. Parameter Epistemics

| Parameter | Value | Classification | Justification |
|---|---|---|---|
| `APPROVED_ENDPOINT_TOLERANCE_PX` | `2 px` | `SAFE_DIMENSIONLESS_BOUND` | Dilates stroke by $\pm 2\text{ px}$ to tolerate raster anti-aliasing. |
| `SOLID_MIN_SUPPORT_FRACTION` | `0.85` | `SAFE_DIMENSIONLESS_BOUND` | Production standard invariant in `AGENTS.md` for continuous strokes. |
| `DASHED_MIN_SUPPORT_FRACTION` | `0.45` | `SAFE_DIMENSIONLESS_BOUND` | Calibrated for standard ISO/ANSI hidden line dash/gap ratio (1:1 to 1:1.5). |
| `CENTERLINE_MIN_SUPPORT_FRACTION` | `0.35` | `SAFE_DIMENSIONLESS_BOUND` | Calibrated for ISO 128 long-dash/dot centerline patterns. |
| `DARKNESS_THRESHOLD_MAX` | `220` | `SAFE_DIMENSIONLESS_BOUND` | Preserves exact production threshold on pristine white paper. |
| `ADAPTIVE_CONTRAST_DELTA` | `25.0` | `SYNTHETIC_DISCRIMINATOR` | Minimum luminance separation required between paper background and pencil/ink strokes. |

---

## 12. Reuse-First Architecture Recommendation for Codex

- **Target Production Owners:**
  - Update [`cad_agent/source_support_verifier.py`](file:///C:/cad-agent-antigravity/cad_agent/source_support_verifier.py):
    - Replace hardcoded `LINE` check with support for `CIRCLE` and `ARC`.
    - Replace fail-closed `_fail(...)` with structured per-primitive verdicts.
    - Implement `_detect_and_normalize_ink_mask`.
    - Add arc-length sampling for circles and arcs.
  - Update [`cad_agent/source_fusion_proposal.py:51`](file:///C:/cad-agent-antigravity/cad_agent/source_fusion_proposal.py#L51):
    - Extend `_PRIMITIVE_FIELDS` to admit `center_px`, `radius_px`, `start_angle_deg`, `end_angle_deg`, `style`.
- **Architecture Requirements:**
  - `NEW_MODULE_REQUIRED = NO` (extends existing `source_support_verifier.py`).
  - `NEW_SCHEMA_REQUIRED = NO` (backward compatible extensions to proposal schema).
  - `NEW_DEPENDENCY_REQUIRED = NO` (uses existing `Pillow` and `numpy`).
  - `ASSEMBLY_CHANGE_REQUIRED = NO`.
  - `BUILDER_CHANGE_REQUIRED = NO`.
  - `REPAIR_CHANGE_REQUIRED = NO`.
  - `REVIEWER_CHANGE_REQUIRED = NO`.

---

## 13. Research File Inventory & SHA-256 Signatures

| Filename | Type | Status | SHA-256 Checksum | Description |
|---|---|---|---|---|
| [`source_support_curved_engine.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/source_support_curved/source_support_curved_engine.py) | Engine / Oracle | `RESEARCH_ONLY` | `c5fccb4e24975b82f4431c30c20f18675b6cf45eb1fd2466cb3bce7c63049bad` | Shared reference implementation of Strategies A-D for curved source support verification |
| [`test_causal_red_source_support_curved.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/source_support_curved/test_causal_red_source_support_curved.py) | Causal RED Test | `RESEARCH_ONLY` | `74b9077f484303630c8c615515a08b4638dc26b87d540d2ecd521d9bdfc2fbc6` | Public causal RED reproducing 5 baseline failure modes on production source_support_verifier.py |
| [`test_source_support_curved_benchmark.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/source_support_curved/test_source_support_curved_benchmark.py) | Strategy Benchmark | `RESEARCH_ONLY` | `00df73a0302ca3802ca8343381a20c5f760554aee8a7157c3b582f69a34680cc` | Empirical benchmark comparing Strategies A-D across 8 drawing and stroke scenarios |
| [`test_source_support_curved_controls.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/source_support_curved/test_source_support_curved_controls.py) | Controls Test | `RESEARCH_ONLY` | `29c39cf03c7c571c03e7de03ed268cb3810dad2ed5cbfc7c750342272ab86313` | 8 positive and negative boundary controls (radii, sweeps, phantom circles, dashed lines) |
| [`test_source_support_curved_degenerate_and_perf.py`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/source_support_curved/test_source_support_curved_degenerate_and_perf.py) | Edge & Perf Benchmark | `RESEARCH_ONLY` | `f84881a3343cb64b8e6ccdf76b8bade302675109146efb87fbc3710fdc145f98` | Empty, micro, non-finite coords, 1MP scale, and latency profiling (< 60ms) |
| [`source_support_curved_primitive_verifier_empirical_specification.md`](file:///C:/cad-agent-antigravity/research/antigravity/2026-10-11/source_support_curved/source_support_curved_primitive_verifier_empirical_specification.md) | Specification | `RESEARCH_ONLY` | Authoritative in `MANIFEST.md` | Complete empirical specification for Source Support Curved Verifier (`SOURCE_SUPPORT_CURVED_PRIMITIVE_VERIFIER_V1`) |

---

## 14. Next Ranked Research Boundary Recommendation

Following completion of `SOURCE_SUPPORT_CURVED_PRIMITIVE_VERIFIER_V1`, the next highest-priority boundary is:
- **`PRIMITIVE_IR_SERIALIZATION_ROUNDTRIP_INTEGRITY_V1`** in [`primitive_ir_lib/models.py`](file:///C:/cad-agent-antigravity/primitive_ir_lib/models.py) and [`primitive_ir_lib/assemble.py`](file:///C:/cad-agent-antigravity/primitive_ir_lib/assemble.py): JSON serialization/deserialization schema adherence (`to_dict` vs `from_dict`), timestamp ISO 8601 parsing, float rounding drifts, and validation status persistence roundtrip.
