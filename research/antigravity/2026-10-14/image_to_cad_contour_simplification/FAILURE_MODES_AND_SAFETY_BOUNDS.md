# FAILURE_MODES_AND_SAFETY_BOUNDS: Contour Simplification Hazards

- **Document ID:** `REA_CONTOUR_SIMP_FAILURES_V1`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Capability:** `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION` (REA-022)

---

## 1. Overview of Evaluated Hazards

In converting raster engineering drawings into CAD vector boundaries, naive application of polyline simplification algorithms introduces five severe failure modes that corrupt downstream CAD geometry. This document details each failure mode, empirical proof from the 7 synthetic fixtures, and established safety bounds.

---

## 2. Failure Mode 1: Small Feature / Notch Deletion (The Scale-Dependent Epsilon Trap)

### Mechanism
In existing codebase implementations (e.g. `primitive_ir_lib/dimension_geometry.py::_contour_arrow_points`), simplification epsilon is computed proportional to contour perimeter:
$$\epsilon = k \cdot P_{\text{contour}}$$
For small arrowheads ($P \approx 40\text{ px}$), $k = 0.08 \implies \epsilon \approx 3.2\text{ px}$, which appropriately collapses triangular arrowheads to 3–4 vertices.

However, when applied to complete mechanical part contours:
- A $250 \times 150\text{ mm}$ plate has perimeter $P = 816\text{ px}$.
- At $k = 0.02$, $\epsilon = 0.02 \times 816 = 16.32\text{ px}$.
- At $k = 0.01$, $\epsilon = 0.01 \times 816 = 8.16\text{ px}$.
- A standard keyway notch of width $6\text{ px}$ and depth $8\text{ px}$ has perpendicular deviation from the outer edge of $8.0\text{ px}$.
- Because $\epsilon \ge 8.0\text{ px}$, the RDP recursive chord test determines that the notch cavity deviates by less than $\epsilon$, and **discards all notch vertices**.
- **Result:** The keyway notch is completely bridged over and erased from the CAD model.

### Empirical Evidence (Fixture 4 & Fixture 7)
- Fixture 4 ($6 \times 8\text{ px}$ notch on $250 \times 150$ block):
  - At $\epsilon = 0.02 \times P$, `small_feature_survived = False`, Hausdorff error = $9.00\text{ px}$, corner survival drops from 100% to 50.0%.
- Fixture 7 (stepped shaft with $8 \times 6\text{ px}$ keyway):
  - At $\epsilon = 0.01 \times P$, `small_feature_survived = False`, corner survival drops to 50.0%.

### Safety Bound & Rule
> [!CAUTION]
> **RULE:** NEVER use global perimeter-relative epsilon ($\epsilon = k \cdot P$) for mechanical part boundary simplification. Epsilon MUST be bounded by an absolute physical tolerance:
> $$\epsilon_{\text{safe}} \le \min\left(1.5\text{ px}, \frac{1}{3} d_{\text{min\_notch}}\right)$$
> For standard scans ($\ge 300\text{ DPI}$), $\epsilon \in [0.75, 1.25]\text{ px}$ eliminates 98%+ of staircase raster noise while strictly preserving features $\ge 4\text{ px}$.

---

## 3. Failure Mode 2: Corner Rounding & Apex Clipping

### Mechanism
When a sharp corner (e.g. $30^\circ$ acute apex, $45^\circ$ chamfer) has neighboring edge points that lie within $\epsilon$ of a chord cutting across the corner, RDP will clip the apex vertex if the perpendicular distance from the apex to the chord connecting the flanking edges is $\le \epsilon$.

### Empirical Evidence (Fixture 2)
- In Fixture 2 (Chevron with $30^\circ$ apex):
  - For $\epsilon \le 3.0\text{ px}$, the apex survives with $100\%$ corner retention ($H = 0.72\text{ px}$).
  - At $\epsilon = 0.08 \times P = 80\text{ px}$, the apex is clipped, corner survival drops to $83.3\%$, and Hausdorff error spikes to $50.0\text{ px}$.

### Safety Bound
> [!IMPORTANT]
> To prevent clipping sharp corners of included angle $\alpha$:
> $$\epsilon < \frac{L_{\text{edge}}}{2} \tan\left(\frac{\alpha}{2}\right)$$
> For acute $30^\circ$ corners, $\epsilon \le 1.5\text{ px}$ guarantees zero apex clipping.

---

## 4. Failure Mode 3: Circular Arc Flattening (Loss of Circularity)

### Mechanism
RDP approximates smooth curves by inscribing secant chords. The maximum radial error (sagitta) between a circular arc of radius $R$ and a chord subtending angle $\theta$ is:
$$h = R \left(1 - \cos\frac{\theta}{2}\right) \le \epsilon$$
When $\epsilon$ is too large relative to radius $R$:
- $\theta = 2 \arccos\left(1 - \frac{\epsilon}{R}\right)$ becomes large.
- For $R = 75\text{ px}$ and $\epsilon = 6.0\text{ px}$, $\theta \approx 46^\circ$, reducing the circle to an 8-sided polygon (octagon) with area error $8.89\%$.
- For $\epsilon = 0.08 \times P = 37.7\text{ px}$, $\theta \approx 120^\circ$, collapsing the circle to a 4-sided diamond with area error $35.54\%$.

### Empirical Evidence (Fixture 3)
- $\epsilon = 0.75\text{ px}$: 40 chords, radial error $0.69\text{ px}$, area error $0.046\%$ (Visually indistinguishable from circle).
- $\epsilon = 1.50\text{ px}$: 20 chords, radial error $1.49\text{ px}$, area error $1.02\%$.
- $\epsilon = 6.00\text{ px}$: 8 chords, radial error $5.84\text{ px}$, area error $8.89\%$.

### Safety Bound
> [!NOTE]
> Polyline simplification is inherently an approximation for curved geometry. In Cad Agent's architecture, circular arcs should be extracted as true analytical `ARC` / `CIRCLE` primitives via Taubin SVD (`REA-002`) rather than simplified polylines. When polylines must represent curves, $\epsilon \le 1.0\text{ px}$ is required to keep chord error $< 1.0\text{ px}$.

---

## 5. Failure Mode 4: Small Hole Boundary Collapse (Topology Degeneration)

### Mechanism
A closed internal contour representing a pin hole or bolt hole (e.g. $R = 5\text{ px}$, diameter $10\text{ px}$) has a maximum bounding diameter of $10\text{ px}$. If $\epsilon \ge R = 5.0\text{ px}$:
- The distance from any point on the hole perimeter to the diametral chord is $\le R \le \epsilon$.
- RDP merges all vertices into a degenerate 2-point line segment ($N = 2$).
- The enclosed polygon area drops to $0.0$, destroying the hole topology and triggering `closed_topology_preserved = False`.

### Empirical Evidence (Fixture 5)
- Hole $R = 5\text{ px}$ (28 raw perimeter points):
  - $\epsilon = 0.75\text{ px}$: 8 vertices, area error $6.06\%$, topology preserved.
  - $\epsilon = 1.50\text{ px}$: 4 vertices, area error $24.2\%$, topology preserved.
  - $\epsilon = 6.00\text{ px}$: 2 vertices, **Area = 0.0 (100% loss), topology destroyed**.

### Safety Bound
> [!CAUTION]
> For any closed hole contour of minimum enclosing radius $R_{\text{hole}}$:
> $$\epsilon < 0.5 \cdot R_{\text{hole}}$$
> Holes with $R \le 3\text{ px}$ must not be simplified with $\epsilon > 1.0\text{ px}$.

---

## 6. Failure Mode 5: Visvalingam-Whyatt Area Collapse on Raster Staircase Loops

### Mechanism
Visvalingam-Whyatt prioritizes vertices by the area of the triangle formed with their immediate neighbors:
$$A_i = \frac{1}{2} |(x_p - x_n)(y_i - y_p) - (x_i - x_p)(y_p - y_n)|$$
In a raw 1-pixel raster staircase chain (`cv2.CHAIN_APPROX_NONE`), every step has $(\Delta x, \Delta y) \in \{(\pm 1, 0), (0, \pm 1)\}$. The triangle area of any step is at most $0.5\text{ px}^2$.

Critically, a true $90^\circ$ CAD corner on a pixel grid also has an initial local triangle area of only $0.5\text{ px}^2$. Because VW uses *area* rather than *distance from chord* as its metric:
1. VW treats true corners as equally "unimportant" as 1-pixel staircase steps on straight edges.
2. Once points on adjacent edges are removed, the area updates dynamically. As the loop shrinks, VW progressively cuts off corners, rounding the shape inward.
3. VW terminates at the hardcoded minimum vertex count ($N = 3$) for almost all area thresholds $\tau \ge 1.0\text{ px}^2$, collapsing full mechanical profiles into arbitrary triangles with $87\%\text{--}99\%$ area error.

### Conclusion on Visvalingam-Whyatt for CAD Contours
> [!WARNING]
> **REJECTION:** Visvalingam-Whyatt is **fundamentally unsuitable** for raw raster engineering contour chains. While effective for geographic cartography (natural coastlines), it fails completely on discretized raster CAD boundaries. **Ramer-Douglas-Peucker (OpenCV approxPolyDP) is strictly superior for CAD geometry.**
