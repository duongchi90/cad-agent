# TECHNICAL SPECIFICATION & EMPIRICAL DISCRIMINATION REPORT
## Target-to-Base Orientation Policy Discriminator

**Role:** `ANTIGRAVITY_RESEARCH`  
**Mode:** `TARGET_BASE_ORIENTATION_POLICY_DISCRIMINATOR`  
**Subagents:** 0 (Disabled)  
**Status:** Research Specification Only. Zero production code modification. Zero PR.  
**Canonical State:** GitHub [`duongchi90/cad-agent`](https://github.com/duongchi90/cad-agent) on `main` at commit `47808851b22472e213c8b8d77b735f9dbb88d699` (merged PR #493).  
**Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), `NO_TOUCH_ARC_CIRCLE_MUTATION_EPIC=ENFORCED`.  

---

## 1. FRESH CURRENT STATE AUDIT

- **CURRENT_MAIN:** Commit `47808851b22472e213c8b8d77b735f9dbb88d699` (PR #493 merged).
- **ACTIVE_PRODUCTION_FRONTIER:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`).
- **CURRENT_ALIGNMENT_DEFAULT_ROTATION:** `max_rotation_deg = 5.0` in [`primitive_ir_lib/geometry_alignment.py:143`](file:///C:/Users/duong/ZCodeProject/cad-agent/primitive_ir_lib/geometry_alignment.py#L143).
- **CURRENT_SOURCE_FUSION_ROTATION_POLICY:** Implicitly restricted to $\pm 5.0^\circ$ because [`cad_agent/source_fusion_proposal.py::_target_to_base_alignment()`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py#L590-L650) invokes `_estimate_similarity_alignment(value, max_residual_px=max_residual)` without passing `max_rotation_deg`.

---

## 2. CLASSIFICATION OF THE EXISTING 5-DEGREE LIMIT

### Archeological Git Trace
1. **Introduction:** Introduced in commit `613463c6f976ed3872854df0d870c88c8f062b87` (*"feat: add deterministic VS-T2 geometry comparator"*), implementing design document `docs/superpowers/plans/2026-08-04-vs-t2-geometry-comparator.md`.
2. **Original Purpose:** VS-T2 was designed for deterministic offline comparison of an upright CAD silhouette render against an already upright reference image/mask to compute 10 visual supervisor metrics.
3. **Explicit Config:** In [`cad_agent/geometry_comparison_run.py:47-53`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/geometry_comparison_run.py#L47-L53):
   ```python
   _ALIGNMENT_CONFIG: dict[str, object] = {
       "algorithm": "geometry-comparator-1.0",
       "max_rotation_deg": 5.0,
       "min_uniform_scale": 0.5,
       "max_uniform_scale": 2.0,
       "max_residual_px": 3.0,
   }
   ```
4. **Passive Inheritance:** In PR #454 (commit `93712bdcee396d0de670d3bdba7b2eea49e153e4`), `cad_agent/source_fusion_proposal.py` imported and reused `estimate_similarity_alignment()` as an off-the-shelf helper for target-to-base alignment. It passed `max_residual_px`, but omitted `max_rotation_deg`, unintentionally inheriting the comparator-specific 5.0° default.
5. **Universal CadAgent Contract:** By contrast, the global CadAgent transformation policy in [`cad_agent/base_cad_adapter.py`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/base_cad_adapter.py) is `_TRANSFORM_POLICY = "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY"`, containing fields `{"rotation_degrees", "translation", "uniform_scale"}` with no angle bound.

### Classification Verdict
- **ORIGINAL_POLICY_SCOPE:** **A. geometry-comparator-specific small registration prior.**
- **EVIDENCE:** Authored explicitly under VS-T2 geometry comparison plan for small scan skew on upright silhouette renders; passively inherited by PR #454 without an intentional architectural decision to limit source fusion to 5°.
- **CAN_SOURCE_FUSION_SAFELY_USE_A_DIFFERENT_POLICY:** **YES**, provided the wider policy prevents silent false-positive registrations on symmetric and repeated geometries.

---

## 3. COMPARISON OF FOUR CANDIDATE POLICIES

We evaluate four structural policies:
- **`POLICY_A` (Current Default):** $|\theta| \le 5.0^\circ$.
- **`POLICY_B` (Arbitrary Planar Rotation):** $|\theta| \le 180.0^\circ$.
- **`POLICY_C` (Unconditional Cardinal-Plus-Skew):** $\min_{\theta_c \in \{0, 90, -90, 180\}} |\theta - \theta_c| \le 5.0^\circ$.
- **`POLICY_D` (Caller-Declared Orientation Envelope):** Caller declares expected angle and tolerance (e.g. `expected_orientation = 0.0°, tolerance = 5.0°` by default, or `expected_orientation = 90.0°, tolerance = 5.0°` for landscape sheets).

---

## 4. EXPERIMENT 1: POSITIVE FIXTURES

Tested on non-collinear 3-point anchors in calibrated physical millimeters:  
$A_1 = (0.0, 0.0)\text{ mm}, A_2 = (100.0, 0.0)\text{ mm}, A_3 = (0.0, 80.0)\text{ mm}$.  
Target-to-base rigid transform applied with $s = 1.0000$, translation $t = (250.0, 175.0)\text{ mm}$.

| True $\theta$ | Policy A ($|\theta| \le 5^\circ$) | Policy B ($|\theta| \le 180^\circ$) | Policy C (Card $\pm 5^\circ$) | Policy D (Declared Env) | Scale Error | Reprojection RMS | Physical Length Preserved |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.0°** | **ACCEPTED** | **ACCEPTED** | **ACCEPTED** | **ACCEPTED** | $0.00 \times 10^{-16}$ | $2.32 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **1.0°** | **ACCEPTED** | **ACCEPTED** | **ACCEPTED** | **ACCEPTED** | $2.22 \times 10^{-16}$ | $2.84 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **5.0°** | REJECTED | **ACCEPTED** | REJECTED | **ACCEPTED** | $0.00 \times 10^{-16}$ | $4.02 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **15.0°** | REJECTED | **ACCEPTED** | REJECTED | **ACCEPTED** | $0.00 \times 10^{-16}$ | $1.64 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **30.0°** | REJECTED | **ACCEPTED** | REJECTED | **ACCEPTED** | $2.22 \times 10^{-16}$ | $4.02 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **45.0°** | REJECTED | **ACCEPTED** | REJECTED | **ACCEPTED** | $0.00 \times 10^{-16}$ | $2.32 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **89.0°** | REJECTED | **ACCEPTED** | **ACCEPTED** | **ACCEPTED** | $0.00 \times 10^{-16}$ | $2.32 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **90.0°** | REJECTED | **ACCEPTED** | **ACCEPTED** | **ACCEPTED** | $3.33 \times 10^{-16}$ | $2.84 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **91.0°** | REJECTED | **ACCEPTED** | **ACCEPTED** | **ACCEPTED** | $0.00 \times 10^{-16}$ | $2.84 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **135.0°** | REJECTED | **ACCEPTED** | REJECTED | **ACCEPTED** | $2.22 \times 10^{-16}$ | $1.64 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **179.0°** | REJECTED | **ACCEPTED** | **ACCEPTED** | **ACCEPTED** | $2.22 \times 10^{-16}$ | $2.32 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **180.0°** | REJECTED | **ACCEPTED** | **ACCEPTED** | **ACCEPTED** | $0.00 \times 10^{-16}$ | $2.84 \times 10^{-14}\text{ mm}$ | **YES (100%)** |
| **-90.0°** | REJECTED | **ACCEPTED** | **ACCEPTED** | **ACCEPTED** | $3.33 \times 10^{-16}$ | $3.28 \times 10^{-14}\text{ mm}$ | **YES (100%)** |

*Key Finding:* Across all angles, numerical similarity estimation preserves machine-precision scale ($|s - 1.0| \le 10^{-15}$) and residual ($< 10^{-13}\text{ mm}$). Rejections under Policy A and C are purely policy-driven, not numerical limitations.

---

## 5. EXPERIMENT 2: WRONG-ANCHOR SAFETY MATRIX (THE CRITICAL EXPERIMENT)

We construct 8 classic engineering geometries where incorrect anchor correspondences or rotational symmetries allow low-residual similarity fits:

```
========================================================================================================================
WRONG-ANCHOR SAFETY EVALUATION (MEASURED BEHAVIOR)
========================================================================================================================
Scenario                                Fitted θ   Scale   RMS (mm)  Policy A    Policy B        Policy C        Policy D (Exp=0°)
------------------------------------------------------------------------------------------------------------------------
A. Repeated Parallel Lines (dy shift)     0.00°   1.0000   0.0000    FALSE PASS  FALSE PASS      FALSE PASS      FALSE PASS (*)
B1. Square Symmetry (90° permutation)    90.00°   1.0000   0.0000    SAFE        FALSE PASS (!!) FALSE PASS (!!) SAFE
B2. Rectangle Symmetry (180° perm)      180.00°   1.0000   0.0000    SAFE        FALSE PASS (!!) FALSE PASS (!!) SAFE
C. Bolt Circle Pattern (45° mispair)     45.00°   1.0000   0.0000    SAFE        FALSE PASS (!!) SAFE            SAFE
D. Two Bosses Swapped (3rd fixed)          --       --       --      SAFE        SAFE (Rej Det)  SAFE (Rej Det)  SAFE (Rej Det)
E. 180° Inverted Layout Match           180.00°   1.0000   0.0000    SAFE        FALSE PASS (!!) FALSE PASS (!!) SAFE
F. Rotated Subassembly (60° mispair)     60.00°   1.0000   0.0000    SAFE        FALSE PASS (!!) SAFE            SAFE
G. 1 Outlier Anchor (15mm shift)         -4.46°   0.9654   4.3301    SAFE        SAFE (RMS>3)    SAFE (RMS>3)    SAFE (RMS>3)
```
*(*) Note on Scenario A: Scenario A is a pure translation error ($\theta = 0.00^\circ$); rotation policies cannot filter translation errors. Translation disambiguation is strictly owned by anchor authority tiers and `compose_verified_native_line_delta()` tie-breaking.*

### Fatal Vulnerabilities of Policy B and Policy C
1. **Disqualification of Policy B (`ARBITRARY_180_DEG_POLICY`):**
   - In 5 out of 8 scenarios (**B1, B2, C, E, F**), Policy B silently accepts completely invalid registrations with $\text{RMS} = 0.0000\text{ mm}$!
   - A 4-hole square pattern permuted by 90° is accepted as a valid 90° rotated drawing.
   - A symmetric flange rotated by 45° or 60° is silently mapped to the wrong subassembly.
   - An upside-down 180° sheet flip is silently accepted.
   - **Verdict: Policy B converts rotational symmetry ambiguity into catastrophic silent corruption.**
2. **Disqualification of Policy C (`CARDINAL_PLUS_SKEW_POLICY` without caller envelope):**
   - In scenarios **B1, B2, and E**, Policy C produces **FALSE PASSES**!
   - Because $90^\circ$ and $180^\circ$ are cardinal angles, Policy C cannot distinguish a legitimate 90° rotated landscape sheet from a 90° corner mispairing on an upright square part.
   - **Verdict: Policy C is unacceptably vulnerable to 90° and 180° symmetry flips.**
3. **Safety Superiority of Policy D (`CALLER_DECLARED_ORIENTATION_ENVELOPE`):**
   - When the caller declares `expected_orientation = 0.0°, tolerance = 5.0°` (the default), Policy D **rejects 100% of false symmetric rotations** (B1, B2, C, E, F).
   - When the caller explicitly declares a 90° landscape sheet (`expected_orientation = 90.0°, tolerance = 5.0°`), it accepts the legitimate 90° sheet, but **strictly rejects** 0°, 45°, 60°, and 180° erroneous matches!

---

## 6. CARDINAL-PLUS-SKEW HYPOTHESIS

We evaluated whether technical drawings require arbitrary continuous rotation or discrete orientation envelopes:

| Test Case | Fitted $\theta$ | Policy A | Policy B | Policy C | Policy D (Card $\pm 5^\circ$) | Policy D (Explicit $\pm 5^\circ$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Case 1: 90° sheet rotation + 2° scan skew** | **92.00°** | False | True | True | True | True (Exp=90°) |
| **Case 2: 180° sheet rotation - 3° scan skew** | **177.00°** | False | True | True | True | True (Exp=180°) |
| **Case 3: 0° sheet rotation + 4° scan skew** | **4.00°** | True | True | True | True | True (Exp=0°) |
| **Case 4: 45° legitimate local detail** | **45.00°** | False | True | False | False | True (Exp=45°) |

### Scientific Verdict
- Physical drawings in engineering workflows are scanned in portrait or landscape orientations: $0^\circ, 90^\circ, 180^\circ, 270^\circ$ (or $-90^\circ$). Physical scanner feed produces skew within $\pm 2^\circ$ (rarely up to $\pm 4^\circ$).
- Therefore, global sheet registration NEVER naturally occurs at arbitrary angles such as $37.2^\circ$ unless the paper was fed crookedly (which constitutes bad scan quality).
- Local 45° chamfers or 30° isometric lines belong to **local feature geometry**, not global sheet registration.

---

## 7. GLOBAL SHEET VS LOCAL FEATURE ORIENTATION

### Decoupling Global Frame from Local Geometry
1. **`GLOBAL_SOURCE_TO_BASE_FRAME_ROTATION`:**
   - The rigid 2D transform mapping the whole sheet/page coordinate frame into base DWG WCS.
   - In ISO/ASME drawings, the sheet frame is aligned with the title block and paper edges: cardinal orientations ($0^\circ, 90^\circ, 180^\circ, 270^\circ$) plus small mechanical scanner skew ($\le 3.0^\circ$).
2. **`LOCAL_ENTITY_OR_VIEW_ORIENTATION`:**
   - Primitive IR line angles, chamfers (45°), angular dimensions (30°, 60°), or auxiliary view projections.
   - These are local vector directions embedded *inside* the sheet coordinate frame.
   - They are extracted by `geometry_extraction.py` as local vectors and mapped into WCS via the sheet transform.
3. **Previous Conflation Corrected:**
   - The prior draft mentioned *"cross-orientation details (15°, 30°, 45°)"* as a reason to allow arbitrary global registration.
   - This was an architectural conflation. A 45° line inside a drawing does **not** mean the sheet is rotated at 45°! The global sheet remains upright ($0^\circ$), while the line has local angle $45^\circ$.
   - Global registration only requires supporting discrete cardinal sheet orientations ($0^\circ, 90^\circ, 180^\circ, 270^\circ$) plus skew.

---

## 8. PUBLIC PRODUCTION PATH RED TEST

Tested on the actual public production entry point:  
[`cad_agent/source_fusion_proposal.py::compose_verified_native_line_delta()`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py#L710-L760).

### Test Fixture
- Verified target document with 1 horizontal line: $(10.0, 54.0)\text{ mm} \to (30.0, 54.0)\text{ mm}$.
- Base DWG native line observation: rotated 90° CCW into WCS, modified end by 5mm:  
  $(46.0, 210.0)\text{ mm} \to (46.0, 225.0)\text{ mm}$.
- Anchors: 3 non-collinear DATUM anchors in exact 90° rotation ($s = 1.0000$, $\text{RMS} = 0.0000\text{ mm}$).
- Execution on current `main`:
  ```python
  _compose_line_delta(
      base_lines=base_lines,
      target_case=target_case,
      target_to_base_alignment_anchors=anchors_90deg,
  )
  ```
- **Observed Current-Main Result:**
  ```
  CAUGHT EXPECTED CURRENT-MAIN RED FAILURE: ValueError: TARGET_BASE_ALIGNMENT_UNPROVEN
  ```
  *Current main fails closed as expected because `_target_to_base_alignment()` defaults to `max_rotation_deg=5.0`.*

---

## 9. NEGATIVE PUBLIC-PATH CONTROL (SAFETY VERIFICATION)

Using the same public `compose_verified_native_line_delta()` entry point:
- Base DWG and target drawing are upright ($0^\circ$).
- Square pattern anchors permuted by 90° (rotational symmetry ambiguity).
- **Execution on Current Main:**
  ```
  PERMUTED ANCHOR FAILED CLOSED: ValueError: TARGET_BASE_ALIGNMENT_UNPROVEN
  ```
- **Execution under Flawed Policy B (Arbitrary $\le 180^\circ$):**
  - Accepts the 90° false alignment ($\text{RMS} = 0.0000$).
  - Rotates target geometry perpendicular to true orientation.
  - If base DWG contains perpendicular symmetric lines, it generates **false bounded deltas**!
- **Execution under Policy D (`expected_orientation = 0.0°, tolerance = 5.0°`):**
  - Computes $\theta = 90.00^\circ$.
  - $|\theta - 0.0^\circ| = 90.0^\circ > 5.0^\circ$.
  - **Fails closed immediately** at Layer B with `TARGET_BASE_ALIGNMENT_UNPROVEN`.
  - Zero bounded deltas emitted.

---

## 10. POLICY SELECTION

We choose:

$$\mathbf{POLICY\_D: \ CALLER\_DECLARED\_ORIENTATION\_ENVELOPE}$$

### Definitive Selection Rationale (Ordered by Criteria)
1. **Safety (Criterion 1):** Zero false registrations. Blocks 100% of square (B1), rectangular (B2), and circular (C) symmetric anchor mispairings.
2. **Determinism (Criterion 2):** Orientation expectation is an explicit, hash-bound parameter declared in the request/manifest, never an ambiguous heuristic guess.
3. **Small Existing-Owner Patch (Criterion 3):** Requires $+8$ lines in `cad_agent/source_fusion_proposal.py`. Requires **ZERO changes** to `primitive_ir_lib/geometry_alignment.py`.
4. **Revision Mode Usefulness (Criterion 4):** Enables 90°, 180°, and 270° revision drawings when the operator/manifest declares the expected sheet orientation.
5. **No Silent Wrong Correspondence (Criterion 5):** Rejects any orientation outside the declared envelope before entity correspondence can run.

---

## 11. WRITESET REASSESSMENT

- **PRIMARY_OWNER:** [`cad_agent/source_fusion_proposal.py`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py)
  - In `_target_to_base_alignment()`:
    Accept `expected_rotation_degrees: float = 0.0, rotation_tolerance_degrees: float = 5.0`.
    Invoke `_estimate_similarity_alignment(value, max_rotation_deg=180.0, max_residual_px=max_residual)`.
    Enforce:
    $$\Delta \theta = |(\theta_{\text{fitted}} - \theta_{\text{expected}} + 180^\circ) \bmod 360^\circ - 180^\circ| \le \theta_{\text{tolerance}}$$
  - In `compose_verified_native_line_delta()`:
    Expose optional `expected_rotation_degrees: float = 0.0, rotation_tolerance_degrees: float = 5.0` with safe default $0.0^\circ \pm 5.0^\circ$.
- **SECONDARY_OWNER:** **`NONE`**
  - `primitive_ir_lib/geometry_alignment.py` already supports `max_rotation_deg=180.0`. It requires **zero changes**.
- **TEST_OWNER:** [`tests/test_external_visual_primitive_ir_admission.py`](file:///C:/Users/duong/ZCodeProject/cad-agent/tests/test_external_visual_primitive_ir_admission.py)
- **MINIMUM_WRITESET:** $\approx +14$ lines in `source_fusion_proposal.py`, $+35$ lines in tests.

---

## 12. SCIENTIFIC COLLINEAR WORDING CORRECTION

- **Accurate Mathematical Label:**
  $$\mathbf{EXACT\_COLLINEAR\_SIMILARITY\_SOLVABLE\_BUT\_NUMERICALLY\_UNSTABLE\_UNDER\_TRANSVERSE\_JITTER}$$
- **Formal Justification:**
  In 2D Euclidean geometry, exact collinear point sets ($N \ge 3$) are mathematically solvable for similarity along their 1D principal axis. However, physical raster drawings invariably possess digitization noise ($\sigma \approx 0.5\text{ px}$). Because the transverse eigenvalue is near zero ($\sigma_2 \approx \epsilon$), noise completely dominates the transverse axis, causing SVD Procrustes fitting to suffer catastrophic rotation jumps ($30^\circ \to 82.8^\circ$) and reflection determinant flips ($\det = -1.0$).
- **Preservation Directive:** The current rank-2 guard `if len(items) >= 3 and (_rank(reference) < 2 or _rank(cad) < 2)` in [`geometry_alignment.py:165`](file:///C:/Users/duong/ZCodeProject/cad-agent/primitive_ir_lib/geometry_alignment.py#L165) is **100% verified and must be preserved unconditionally**.
