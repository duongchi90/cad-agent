# SELECTED_CAPABILITY: Polyline Bulge and Arc Reconstruction

- **CAPABILITY_IDENTIFIER:** `POLYLINE_BULGE_AND_ARC_RECONSTRUCTION`
- **PRIMARY_DOMAIN:** 2D CAD Vector Representation / Numerical Geometry
- **CURRENT_CAD_AGENT_OWNER:** `dxf_builder_lib/builder.py` and `primitive_ir_lib/geometry_extraction.py`
- **OWNER_STATUS:** `VALID` (Both components exist and are actively maintained on `origin/main`)

---

## 1. Problem Statement & Luna Discovery Gap
Cad Agent converts engineering drawings (both raster scans and native CAD DXF/DWG files) into standardized primitive representations. In Autodesk AutoCAD and the DXF standard, curved polyline segments are represented not as thousands of straight chord segments, and not as disconnected `ARC` entities, but as `LWPOLYLINE` vertex pairs with a scalar **Bulge** value ($b$):
$$b = \tan\left(\frac{\theta}{4}\right)$$
where $\theta$ is the included central angle of the arc segment:
- $b > 0$: Counter-Clockwise (CCW) arc from vertex $A$ to vertex $B$.
- $b < 0$: Clockwise (CW) arc from vertex $A$ to vertex $B$.
- $b = 0$: Straight line segment from vertex $A$ to vertex $B$.
- $|b| = 1$: Semicircle ($\theta = \pi$).

### The Hidden Pitfalls Avoided:
1. **Inflection & Near-Zero Singularity:** When arc radius is large or points are nearly collinear, direct circular fitting yields ill-conditioned centers. A robust threshold guard $\epsilon \le 10^{-6}$ is required to fall back to straight line segments ($b = 0$).
2. **Arc-to-Bulge vs Bulge-to-Arc Inversion:** Converting a center, radius, start angle, and end angle into a bulge requires careful angular wrapping ($\Delta\theta = \theta_{\text{end}} - \theta_{\text{start}}$ modulo $2\pi$).
3. **Three-Point Circular Arc Fitting:** Given 3 sequential points $(P_1, P_2, P_3)$ on a curved contour, computing the exact bulge for segment $(P_1, P_3)$ that passes through $P_2$.

---

## 2. Verified Mechanism & Mathematical Oracle
The mathematical transformation between two endpoints $A(x_1, y_1)$ and $B(x_2, y_2)$ and a third point $C(x_3, y_3)$ lying on the arc is:

1. **Determinant / Cross Product Orientation:**
   $$\Delta = (x_2 - x_1)(y_3 - y_1) - (y_2 - y_1)(x_3 - x_1)$$
   If $|\Delta| < 10^{-9}$, points are collinear; bulge is $0.0$.

2. **Perpendicular Bisector Intersection (Center Calculation):**
   $$d = 2 \cdot \Delta$$
   $$x_c = \frac{(x_2^2 - x_1^2 + y_2^2 - y_1^2)(y_3 - y_1) - (x_3^2 - x_1^2 + y_3^2 - y_1^2)(y_2 - y_1)}{d}$$
   $$y_c = \frac{(x_3^2 - x_1^2 + y_3^2 - y_1^2)(x_2 - x_1) - (x_2^2 - x_1^2 + y_2^2 - y_1^2)(x_3 - x_1)}{d}$$
   $$R = \sqrt{(x_1 - x_c)^2 + (y_1 - y_c)^2}$$

3. **Bulge Computation directly from Points:**
   Let chord distance $L = \|B - A\|$. Let sagitta (height of arc above chord) $h$ be:
   $$h = R - \sqrt{\max(0, R^2 - (L/2)^2)}$$
   $$\text{bulge} = \text{sign}(\Delta) \cdot \frac{2h}{L}$$
   Or equivalently using half-angle tangent:
   $$b = \tan\left(\frac{\theta}{4}\right) = \frac{\sqrt{1 + \cot^2(\theta/2)} - 1}{\cot(\theta/2)}$$

This verified formulation guarantees exact representation for DXF Group Code 42.
