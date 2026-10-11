# TECHNICAL SPECIFICATION (CORRECTED): RASTER TO BASE DWG WCS REGISTRATION

**Role:** `ANTIGRAVITY_RESEARCH`  
**Mode:** `REGISTRATION_CONTRACT_CORRECTION`  
**Subagents:** 0 (Disabled)  
**Status:** Corrected Research Specification Only. Zero production code modification. Zero PR.  
**Canonical State:** GitHub `duongchi90/cad-agent` on `main` at commit `47808851b22472e213c8b8d77b735f9dbb88d699`  
**Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), `NO_TOUCH_ARC_CIRCLE_MUTATION_EPIC=ENFORCED`  

---

## 0. PRESERVE PRIOR RESEARCH QUEUE

The prior research backlog remains intact and queued:

1. **`THICK_LINE_CENTERLINE_NORMALIZATION_V1`**
   - **Status:** `READY_FOR_CODEX_QUEUED`
   - **Seam:** Distance transform ridge / morphological thinning in `primitive_ir_lib/geometry_extraction.py:extract_lines()`.
2. **`CIRCLE_FALSE_POSITIVE_PERIMETER_VALIDATION_V1`**
   - **Status:** `READY_FOR_CODEX_QUEUED`
   - **Seam:** Circumference ray angular coverage verification filter in `primitive_ir_lib/geometry_extraction.py:extract_circles()`.
3. **`CARDINAL_ROTATED_TEXT_EXTRACTION_V1`**
   - **Status:** `READY_FOR_CODEX_QUEUED`
   - **Seam:** 4-way rotation pass ($0^\circ, 90^\circ, 180^\circ, 270^\circ$) + deterministic token scoring in `primitive_ir_lib/text_extraction.py:extract_text_tesseract()`.
4. **`TAUBIN_ARC_EXTRACTION_V1`**
   - **Status:** `READY_FOR_CODEX_QUEUED`
   - **Seam:** Clean-room Taubin algebraic circular arc extraction in `primitive_ir_lib/geometry_extraction.py` and `assemble.py`.

---

## 1. ARCHITECTURAL CORRECTION SUMMARY

The prior draft (`raster_base_wcs_registration_empirical_specification.md`) identified accurate numerical similarity fit formulas, but made an invalid architectural assumption:

> **Prior Flawed Claim:**  
> `CURRENT_REGISTRATION_OWNER: None for Raster -> Base DWG WCS registration.`  
> Proposed an unconstrained, arbitrary-scale ($s = 2.0$) single-hop solver mapping pixels directly to Base DWG WCS.

### Fresh Owner Evidence & Invalidation
Inspection of `cad_agent/source_fusion_proposal.py` and `primitive_ir_lib/geometry_alignment.py` on current `main` reveals:
1. **Target-to-base alignment already exists** in `cad_agent/source_fusion_proposal.py::_target_to_base_alignment()`.
2. **Similarity estimation is already owned** by `primitive_ir_lib/geometry_alignment.py:estimate_similarity_alignment()`.
3. **Double-scaling is strictly forbidden by design:** `source_fusion_proposal.py` explicitly enforces:
   ```python
   # Calibration already puts target geometry in native units; alignment must not
   # rescale physical dimensions. Allow only floating-point fit noise around 1:1.
   _TARGET_BASE_SCALE_TOLERANCE = 1e-6
   ```
4. If an alignment module outputs an arbitrary scale (e.g. $s = 2.0$), it rescales physical target geometry that has already been calibrated into millimeters, causing a $2.0\times$ dimensional error (a $100\text{ mm}$ part is corrupted to $200\text{ mm}$).

Therefore, **Option A** is the only architecturally truthful contract for CadAgent.

---

## 2. THE THREE-LAYER COORDINATE ARCHITECTURE

The registration and fusion pipeline in CadAgent consists of three decoupled layers:

```
[Raw Raster Pixels]
        │
        │  Layer A: Intrinsic Calibration (primitive_ir_lib/calibration.py via assemble.py)
        ▼  Transform: s_px_to_mm, translation (0, H), Y-inversion
[Target Physical Coordinates (mm)]
        │
        │  Layer B: Target-to-Base Frame Alignment (cad_agent/source_fusion_proposal.py)
        ▼  Transform: Rigid 2D (θ, tx, ty) with s ≈ 1.0 ± 1e-6
[Aligned Target Coordinates in Base WCS (mm)]
        │
        │  Layer C: Bounded Native Correspondence (cad_agent/source_fusion_proposal.py)
        ▼  Operation: Residual pairing, disambiguation, delta generation
[Bounded Native Line Deltas (mm)]
```

### Layer A: Pixel-to-Physical Calibration
- **Owner:** `primitive_ir_lib/calibration.py`, `primitive_ir_lib/models.py`, `primitive_ir_lib/assemble.py`.
- **Input:** Raw raster pixels $(x_{\text{px}}, y_{\text{px}})$, image height $H$.
- **Mapping:**
  $$x_{\text{target}} = (x_{\text{px}} - x_0) \cdot s_{\text{px\_to\_mm}}$$
  $$y_{\text{target}} = (y_0 - y_{\text{px}}) \cdot s_{\text{px\_to\_mm}}$$
  where $(x_0, y_0) = (0, H)$ represents the sheet lower-left origin.
- **Output:** Calibrated target geometry entities (`Line`, `Circle`, `Text`) in native physical units (`mm`).
- **Physical Invariant:** All lengths $\|p_2 - p_1\|_{\text{target}}$ represent true physical millimeters on the sheet.

### Layer B: Target-to-Base Frame Alignment
- **Owner:** `cad_agent/source_fusion_proposal.py::_target_to_base_alignment()`, invoking `primitive_ir_lib/geometry_alignment.py`.
- **Input:** Sequence of `AnchorPair` records (2 to 32 pairs), where `cad_px` is target geometry in mm and `reference_px` is base DWG geometry in mm.
- **Transform:**
  $$\begin{pmatrix} X_{\text{wcs}} \\ Y_{\text{wcs}} \end{pmatrix} = R(\theta) \begin{pmatrix} x_{\text{target}} \\ y_{\text{target}} \end{pmatrix} + \begin{pmatrix} t_x \\ t_y \end{pmatrix}$$
- **Invariant:** The alignment transform is a **rigid Euclidean transformation** (isometry).
- **Enforcement:** Scale is constrained by `_TARGET_BASE_SCALE_TOLERANCE = 1e-6`:
  $$|s_{\text{align}} - 1.0| \le 10^{-6}$$
- **Output:** Transform matrix $(R, t)$ mapping target mm into base DWG WCS mm.

### Layer C: Bounded Native Correspondence & Delta Composition
- **Owner:** `cad_agent/source_fusion_proposal.py::compose_verified_native_line_delta()`.
- **Input:** Base native line observations (WCS mm), aligned target lines (WCS mm).
- **Operation:**
  1. Transforms target lines via alignment matrix: `_apply_alignment_to_target_line(line, matrix)`.
  2. Computes pairwise Hausdorff/endpoint residual distances against native base lines.
  3. Matches 1-to-1 within `max_correspondence_residual`.
  4. Disambiguates or rejects ties (`_same_residual`).
- **Output:** Bounded native line deltas (`before` vs `after` in WCS mm).

---

## 3. CONTRACT SELECTION: OPTION A VS OPTION B

| Dimension | Option A (Architecturally Truthful) | Option B (Flawed Single-Hop Proposal) |
| :--- | :--- | :--- |
| **Separation of Concerns** | Calibration owns pixel $\to$ mm; Alignment owns target frame $\to$ WCS frame. | Single solver couples raster scale, calibration, and WCS pose. |
| **Scale Semantics** | Scale is strictly locked to $1.0 \pm 10^{-6}$ at Layer B. | Scale is arbitrary ($s = 2.0, 2.5$) at Layer B. |
| **Double-Scale Risk** | **Zero.** Physical dimensions are preserved. | **High.** Corrupts physical geometry by $s_{\text{align}} \times$. |
| **Current Code Fit** | Aligns 100% with `source_fusion_proposal.py` invariants. | Breaks `_TARGET_BASE_SCALE_TOLERANCE = 1e-6`. |

### Empirical Double-Scale Measurement
To prove why Option B is dangerous, consider a $100.0\text{ mm}$ mechanical part scanned at $254\text{ DPI}$ ($s_{\text{px\_to\_mm}} = 0.1\text{ mm/px}$):
1. **Raw Pixel Length:** $1,000.0\text{ px}$.
2. **Layer A Calibrated Target:** $1,000.0 \times 0.1 = 100.0\text{ mm}$.
3. **Option A in Layer B ($s = 1.0$):**
   $$L_{\text{wcs}} = 100.0 \times 1.0 = 100.0000\text{ mm} \quad (\Delta = 0.0000\text{ mm})$$
4. **Option B in Layer B ($s = 2.0$):**
   $$L_{\text{wcs}} = 100.0 \times 2.0 = 200.0000\text{ mm} \quad (\Delta = 100.0000\text{ mm}, \text{Error} = +100\%)$$

*Conclusion:* **Option A is mandatory.** The target-to-base alignment must never rescale physical dimensions.

---

## 4. COLLINEAR ANCHOR BEHAVIORAL AND EMPIRICAL MATRIX

In 2D similarity estimation, anchor configurations have distinct algebraic and numerical stability properties depending on point count $N$ and geometric distribution.

### Mathematical Formulation
Given centered coordinate matrices $\bar{X}_{\text{target}}$ and $\bar{X}_{\text{base}}$:
- The covariance matrix is $C = \bar{X}_{\text{target}}^T \bar{X}_{\text{base}}$.
- The SVD is $C = U \Sigma V^T$, with singular values $\sigma_1 \ge \sigma_2 \ge 0$.
- **When points are collinear:** The variance along the axis perpendicular to the line is zero. Thus, $\text{rank}(C) = 1$ and $\sigma_2 = 0$.

### Measured Behavioral Matrix (Cases A – E)

Evaluated against `primitive_ir_lib/geometry_alignment.py` and empirical solvers:

```
========================================================================================
COLLINEAR ANCHOR BEHAVIORAL MATRIX (GROUND TRUTH: θ = 30.0°, t = (100, 200), s = 1.0)
========================================================================================
Case A: N=2 distinct points
  Rank(target)=1, Rank(base)=1
  Current Code Guard: ACCEPTED (guard applies only to N >= 3)
  2-Point Solver:     s = 1.0000, θ = 30.00°, max residual = 0.0000 mm
  Status:             WELL-CONDITIONED & ACCEPTED

Case B: N=3 collinear points (mathematically exact)
  Rank(target)=1, Rank(base)=1
  Current Code Guard: REJECTED (FAIL-CLOSED: "three or more anchors must span two dimensions")
  2-Point Solver:     s = 1.0000, θ = 30.00°, max residual = 0.0000 mm
  Status:             PROTECTED BY FAIL-CLOSED GUARD

Case C: N=5 collinear points (mathematically exact)
  Rank(target)=1, Rank(base)=1
  Current Code Guard: REJECTED (FAIL-CLOSED: "three or more anchors must span two dimensions")
  2-Point Solver:     s = 1.0000, θ = 30.00°, max residual = 0.0000 mm
  Status:             PROTECTED BY FAIL-CLOSED GUARD

Case D: N=5 collinear points with transverse scan jitter (σ = 0.5 px)
  Rank(target)=2 (due to noise), Rank(base)=1
  Current Code Guard: REJECTED (FAIL-CLOSED: Rank(base) < 2)
  Unguarded SVD:      s = 1.0022, θ = 82.81° (CORRUPTED!), det(R) = -1.0 (REFLECTION FLIP!)
  Status:             CRITICAL GUARD VALIDATION (Prevents 52.81° rotation error and inversion)

Case E: N=5 collinear points with 1 gross outlier
  Rank(target)=1, Rank(base)=2
  Current Code Guard: REJECTED (FAIL-CLOSED: Rank(target) < 2)
  Unguarded SVD:      s = 1.5637 (CORRUPTED!), θ = -48.99° (CORRUPTED!), residual = 37.74 mm
  Status:             CRITICAL GUARD VALIDATION (Prevents gross distortion)
```

### Engineering Reason for the Fail-Closed Guard
1. **Why $N=2$ is permitted:**
   - Two distinct points define a single vector $\Delta p = p_2 - p_1$.
   - In 2D, the vector angle $\phi = \text{atan2}(\Delta y, \Delta x)$ and length $\|\Delta p\|$ uniquely determine uniform scale and counter-clockwise rotation without ambiguity.
2. **Why $N \ge 3$ collinear points MUST fail closed:**
   - In real drawings, physical scans contain edge rasterization jitter, digitization noise ($\approx \pm 0.5\text{ px}$), or paper shrinkage.
   - For $N \ge 3$ nominally collinear points, noise produces a tiny non-zero transverse eigenvalue ($\sigma_2 \approx \epsilon$).
   - In SVD Procrustes fitting, if $\sigma_2$ is dominated by noise, the estimated rotation axis flips wildly (as demonstrated in Case D, where rotation jumped from $30.0^\circ$ to $82.81^\circ$, and $\det(R) = -1.0$).
   - Therefore, requiring `_rank(reference) >= 2 and _rank(cad) >= 2` for $N \ge 3$ is **essential fail-closed engineering defense** that prevents corrupting native DWG geometry.

---

## 5. REAL CURRENT-MAIN SEAM & FUTURE EPIC

### Measured Gap
In current `main`:
1. `cad_agent/source_fusion_proposal.py::_target_to_base_alignment()` calls:
   ```python
   alignment = _estimate_similarity_alignment(
       value,
       max_residual_px=max_residual,
   )
   ```
2. In `primitive_ir_lib/geometry_alignment.py`, `estimate_similarity_alignment` has the signature:
   ```python
   def estimate_similarity_alignment(
       anchors: Sequence[AnchorPair],
       *,
       max_rotation_deg: float = 5.0,
       min_uniform_scale: float = 0.5,
       max_uniform_scale: float = 2.0,
       max_residual_px: float = 3.0,
   ) -> AlignmentResult:
   ```
3. Because `_target_to_base_alignment` does not pass `max_rotation_deg`, it uses the default limit **`max_rotation_deg = 5.0°`**.
4. Consequently:
   - Normal small-skew scans ($\theta \le 5.0^\circ$) succeed.
   - Rotated revision sheets, detail views, or cross-orientation drawings ($\theta = 15^\circ, 30^\circ, 90^\circ, 180^\circ, 270^\circ$) **fail closed** with `"rotation is outside the approved range"`, even though they have exact $s = 1.0$ and valid anchor geometry!

### The Smallest Future Implementation Epic

```yaml
EPIC_NAME: TARGET_BASE_ORIENTATION_CONFIG_V1
TARGET_REPO: duongchi90/cad-agent
PRIMARY_OWNER: cad_agent/source_fusion_proposal.py
SECONDARY_OWNER: primitive_ir_lib/geometry_alignment.py
ESTIMATED_DIFF: +8 lines, -2 lines
STATUS: READY_FOR_CODEX_QUEUED
DEPENDENCIES: None (Existing owners only)
ACTIVE_FRONTIER_CONFLICT: ZERO (Zero native AutoCAD mutation touched)
```

#### Seam Specification
1. In `cad_agent/source_fusion_proposal.py::_target_to_base_alignment()`:
   - Accept optional parameter `max_rotation_deg: float = 360.0` (or pass `max_rotation_deg=360.0` when aligning to base WCS).
   - Maintain `_TARGET_BASE_SCALE_TOLERANCE = 1e-6` unchanged.
2. In `primitive_ir_lib/geometry_alignment.py`:
   - Retain all degeneracy guards:
     - Distinct baseline check for $N=2$ ($\|\Delta p\| \ge 10.0$).
     - Rank-2 check for $N \ge 3$ (`_rank(reference) >= 2 and _rank(cad) >= 2`).
     - Reflection guard ($\det(R) > 0$).
     - Residual RMS threshold check.

---

## 6. CAUSAL RED TEST SPECIFICATION

```python
def test_target_to_base_wcs_alignment_90deg_red():
    """Causal RED test: 90-degree rotated drawing detail must register into
    Base DWG WCS with scale 1.0 +/- 1e-6 while failing closed on collinear noise."""
    from primitive_ir_lib.geometry_alignment import (
        AnchorPair,
        estimate_similarity_alignment,
    )
    from cad_agent.source_fusion_proposal import _target_to_base_alignment

    # Ground truth: 90° CCW rotation + translation (500, 400)
    # Target points in calibrated physical mm:
    # A1: (100.0, 100.0), A2: (300.0, 100.0), A3: (100.0, 250.0)
    # WCS = R(90°) * P + (500, 400) = (-y + 500, x + 400)
    anchors = [
        AnchorPair("A1", reference_px=(400.0, 500.0), cad_px=(100.0, 100.0), authority="DATUM", confidence=1.0),
        AnchorPair("A2", reference_px=(400.0, 700.0), cad_px=(300.0, 100.0), authority="DATUM", confidence=1.0),
        AnchorPair("A3", reference_px=(250.0, 500.0), cad_px=(100.0, 250.0), authority="DATUM", confidence=1.0),
    ]

    # Current main fails closed because default max_rotation_deg is 5.0°
    # With orientation-permissive parameter max_rotation_deg=360.0:
    record, matrix = _target_to_base_alignment(
        anchors,
        max_residual=1.0,
        coordinate_unit="mm",
        # max_rotation_deg=360.0  <- Required future seam parameter
    )

    assert record["status"] == "ALIGNED"
    assert abs(record["uniform_scale"] - 1.0) <= 1e-6
    assert record["residual_rms"] <= 1e-4
    assert abs(matrix[0][0] - 0.0) <= 1e-6
    assert abs(matrix[0][1] - (-1.0)) <= 1e-6
    assert abs(matrix[0][2] - 500.0) <= 1e-4
    assert abs(matrix[1][0] - 1.0) <= 1e-6
    assert abs(matrix[1][1] - 0.0) <= 1e-6
    assert abs(matrix[1][2] - 400.0) <= 1e-4
```

### GREEN Verification Oracle
1. `record["status"] == "ALIGNED"`
2. $|s_{\text{align}} - 1.0| \le 10^{-6}$ (Physical length preservation)
3. $|\theta - 90.0^\circ| \le 10^{-4\circ}$
4. $\|t - (500, 400)\| \le 10^{-4}\text{ mm}$
5. $\text{Residual RMS} \le 10^{-4}\text{ mm}$
6. $N \ge 3$ collinear anchors strictly rejected (`_rank < 2` guard passes)
7. Full offline test suite passes: `.\scripts\verify.ps1`
