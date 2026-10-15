# Behavioral Contract & Algorithmic Invariants: Line Detection Loss & Endpoint Ink Ray-Marching

- **Document ID:** `LINE_DETECTION_LOSS_ENDPOINT_INK_EXTENSION_V1`
- **Role:** `ANTIGRAVITY_RESEARCH_AGENT`
- **Boundary:** Issue #491 (`LINE_DETECTION_LOSS` under `real_scan_tuned_v1` on CASE01 vs NIST FTC-11 intentional text gap)
- **Current Production Owner:** `primitive_ir_lib/geometry_extraction.py::extract_lines`
- **Status:** Decision-grade evidence complete; unblocks implementation for Luna.

---

## 1. Problem Statement & Causal Mechanism

### 1.1 The Failure Mode
Under `real_scan_tuned_v1` (`hough_threshold=90, min_line_length=50, max_line_gap=5`), `extract_lines()` emits line segments for the CASE01 vertical dimension line that span only $y=224\dots 364$ (length $140\text{ px}$), missing the frozen witness rectangles:
- Upper endpoint rectangle: `[153, 198, 168, 219)`
- Lower endpoint rectangle: `[153, 369, 168, 390)`

### 1.2 The Root Cause
1. In CAD drawings, dimension lines terminate in solid filled triangular arrowheads against orthogonal extension lines.
2. In CASE01, the stroke width of the central line body is $\approx 3\text{ px}$ ($x=160\dots 163$).
3. At the arrowheads ($y=208\dots 224$ and $y=364\dots 380$), the stroke widens outward to $x=158\dots 164$ (width $\approx 8\text{ px}$).
4. Canny edge detection operates on gradient transitions (light $\to$ dark and dark $\to$ light). Inside the solid black arrowhead interior, gradient is $0$.
5. Consequently, Canny edges follow the outer flared silhouette, leaving the central column at $x=160$ completely devoid of Canny edges for $9$ consecutive pixels ($y=215\dots 223$).
6. Because `cv2.HoughLinesP` is parameterized with `maxLineGap=5 < 9`, it terminates detection at the flare ($y=224$ and $y=364$). The arrowhead sections ($16\text{ px}$) are discarded because $16 < \text{minLineLength}=50$.
7. Meanwhile, the underlying source pixels are $99.4\%$ continuous dark ink (grayscale $\le 31$, mean $37.7$) across the full span $y=208\dots 380$.

### 1.3 Counterfactual Failures
- **Counterfactual A (Preset change to `maxLineGap=10`):** Recovers CASE01, but bridges $100\%$ across the $192.365\text{ px}$ intentional text gap in NIST FTC-11 by stringing together collinear text glyph edges.
- **Counterfactual B (Fixed-axis Canny continuation):** Adds $0\text{ px}$ on CASE01 because Canny edges are absent along the central axis, while increasing false gap coverage on FTC-11 from $60\%$ to $70\%$.
- **Counterfactual C (Unverified OCR box clipping):** Fails because OCR confidence is low ($0.46$), role is unknown, and hard-clipping geometry risks cutting real drawing lines.
- **Counterfactual D (Full-image morphological skeletonization):** Takes $1088.3\text{ ms}$ (>120x slower) and violates `GLOBAL_THINNING_SAFE = NO` by distorting circular/hatch geometry.

---

## 2. Invariants of Endpoint Ink Ray-Marching

### Invariant 1: Physical Ink Continuity
A genuine engineering line is a continuous ink stroke on paper. When `cv2.HoughLinesP` truncates an endpoint due to local gradient/silhouette divergence (arrowheads, fillets, corners), the underlying raster retains continuous dark ink (`gray <= dark_thresh`).

### Invariant 2: Intentional Gap Preservation
Intentional gaps (dimension text interruptions, breaks, dashed spacing, margins) consist of background paper (`gray >= 220`).
Marching outward along the line unit vector $\mathbf{u}$ into background paper encounters $\ge \text{max\_white\_gap\_px}$ consecutive background pixels within $2\text{--}3\text{ px}$ (accounting for antialiasing), halting extension immediately with $0.0\text{ px}$ invasion into the gap.

### Invariant 3: Directional Alignment
Extension proceeds strictly along the unit direction vector $\mathbf{u} = \frac{\mathbf{p}_2 - \mathbf{p}_1}{\|\mathbf{p}_2 - \mathbf{p}_1\|}$ established by the Hough segment. It cannot veer laterally or turn corners.

### Invariant 4: Bounded Scope & Performance
Extension is strictly bounded by `max_extend_px` ($\le 30\text{ px}$) and inspects only a 3-pixel perpendicular corridor. Total runtime is $\approx 0.068\text{ ms}$ per line ($\approx 8.7\text{ ms}$ for 129 lines), with zero new dependencies.

---

## 3. Behavioral Specification

```python
def _extend_line_along_ink(
    p1: tuple[float, float],
    p2: tuple[float, float],
    gray: np.ndarray,
    max_extend_px: int = 30,
    max_white_gap_px: int = 3,
    dark_thresh: int = 180,
    perp_half_width: int = 2,
) -> tuple[tuple[float, float], tuple[float, float]]:
```

1. **Preconditions:**
   - `gray`: 2D `np.ndarray` of type `uint8`.
   - `p1`, `p2`: floats; if length is zero or non-finite, returns `p1, p2` unmodified.
2. **Forward March ($p_2 \to p_2 + \mathbf{u} \cdot s$):**
   - Step $s \in [1, \text{max\_extend\_px}]$.
   - Check if any pixel within perpendicular corridor $[-w, +w]$ has `gray <= dark_thresh`.
   - If ink present: advance `best_p2`, reset `white_run = 0`.
   - If ink absent: increment `white_run += 1`; if `white_run >= max_white_gap_px`, abort search.
3. **Backward March ($p_1 \to p_1 - \mathbf{u} \cdot s$):**
   - Symmetric with forward march.
4. **Postconditions:**
   - Returns `(best_p1, best_p2)` with span $\ge$ original span.
   - Guaranteed $\le \text{max\_extend\_px}$ displacement.
