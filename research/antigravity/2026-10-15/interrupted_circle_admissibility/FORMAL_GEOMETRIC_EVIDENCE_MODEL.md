# Formal Geometric Evidence Model for Interrupted Circle Admissibility

**Campaign ID:** `ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015`
**Date:** 2026-10-15
**Author:** Antigravity Research Agent
**Status:** Frozen Formal Model

---

## 1. Mathematical Formulation

### 1.1 Candidate Circle Parameterization
A candidate circle $C$ in image coordinates is defined by:
$$C = (c_x, c_y, r)$$
where $(c_x, c_y) \in \mathbb{R}^2$ is the circle center in pixels, and $r \in \mathbb{R}^+$ is the candidate radius in pixels.

### 1.2 Raster Edge Observations
Let $I: \Omega \to [0, 255]$ be the input grayscale image, where $\Omega \subset \mathbb{Z}^2$.
Let $E = \{e_i = (x_i, y_i) \in \Omega\}$ be the set of edge pixels extracted by a deterministic localizer (e.g., Canny edge detector with thresholds $T_{\text{low}}, T_{\text{high}}$ preceded by Gaussian blur with kernel $\sigma$).

For each edge observation $e_i \in E$:
1. **Radial Residual:**
   $$d_r(e_i; C) = | \|e_i - c\|_2 - r |$$

2. **Polar Angle:**
   $$\theta_i = \text{atan2}(y_i - c_y, x_i - c_x) \in [-\pi, \pi)$$

3. **Candidate Radial Unit Vector:**
   $$\mathbf{u}_r(e_i) = \frac{e_i - c}{\|e_i - c\|_2}$$

4. **Image Gradient Vector:**
   Let $\nabla I(e_i) = \left( \frac{\partial I}{\partial x}(e_i), \frac{\partial I}{\partial y}(e_i) \right)$ be the spatial gradient computed via Sobel convolution with aperture $k=3$.
   The estimated edge normal unit vector is:
   $$\mathbf{n}(e_i) = \frac{\nabla I(e_i)}{\|\nabla I(e_i)\|_2} \quad \text{for } \|\nabla I(e_i)\|_2 > 0$$

5. **Normal Alignment Error (Deviation from Radial Line):**
   For a true circle, the edge normal is parallel to the radius vector. Because gradient polarity may point inward (dark-on-light) or outward (light-on-dark), the unsigned geometric alignment is:
   $$\cos(\Delta \phi_i) = |\mathbf{n}(e_i) \cdot \mathbf{u}_r(e_i)| \in [0, 1]$$
   $$\Delta \phi_i = \arccos\left(\min(1.0, \max(0.0, |\mathbf{n}(e_i) \cdot \mathbf{u}_r(e_i)|))\right) \times \frac{180^\circ}{\pi}$$

---

## 2. Theoretical Uncertainty Budget and Tolerance Envelope

A rasterized circle cannot be evaluated against an arbitrary empirical percentage tolerance without causing false admissions. The tolerance envelope must be derived from physical raster sampling and convolution physics:

$$\epsilon_{\text{position}} = q + \frac{w}{2} + a + b$$

where:
1. **$q$ (Quantization bound):** For discrete pixel grid sampling, a continuous point moves at most $\frac{1}{2}$ pixel per axis. The Euclidean displacement bound is:
   $$q = \frac{\sqrt{2}}{2} \approx 0.7071\text{ px}$$
   (For relative two-point comparison, $q_{\text{rel}} = \sqrt{2} \approx 1.4142\text{ px}$).
2. **$w$ (Stroke width):** Nominal stroke thickness in pixels. A stroke of width $w$ rasterizes with edges at $r \pm \frac{w}{2}$. If the edge detector traces the outer and inner contours of the stroke rather than the stroke centerline, $e_i$ is offset by up to $\frac{w}{2}$ from the nominal centerline.
3. **$a$ (Antialiasing localization uncertainty):** Grayscale transition envelope, typically $\le 0.5\text{ px}$ for standard subpixel rendering.
4. **$b$ (Filter bias):** Gaussian blur ($\sigma=1$, kernel $3\times 3$) and Canny hysteresis displacement, bounded by $\le 0.5\text{ px}$.

### Conservative Position Envelope
For engineering drawings rendered at standard DPI (e.g. 1.5 px/pt, nominal stroke $1.0\text{ pt} \approx 1.5\text{ px}$):
$$\epsilon_{\text{position}} \le 0.7071 + 0.75 + 0.5 + 0.5 = 2.4571\text{ px}$$
A sample $e_i$ is a candidate edge support point if and only if:
$$d_r(e_i; C) \le \epsilon_{\text{position}}$$

### Derived Normal Alignment Envelope
A positional perturbation $\epsilon_{\text{position}}$ on a circle of radius $r$ introduces an angular chord deviation:
$$\Delta \phi_{\text{geom}} \le \arcsin\left(\min\left(1.0, \frac{\epsilon_{\text{position}}}{r}\right)\right)$$
Adding the Sobel gradient discrete angular error bound $g \approx 3.5^\circ$ for $3\times 3$ kernel:
$$\epsilon_{\text{normal}}(r) = \arcsin\left(\min\left(1.0, \frac{\epsilon_{\text{position}}}{r}\right)\right) + g$$

For example:
- At $r = 100\text{ px}$, $\epsilon_{\text{normal}} = \arcsin(2.5/100) + 3.5^\circ \approx 1.43^\circ + 3.5^\circ = 4.93^\circ$.
- At $r = 25\text{ px}$, $\epsilon_{\text{normal}} = \arcsin(2.5/25) + 3.5^\circ \approx 5.74^\circ + 3.5^\circ = 9.24^\circ$.
- At $r < \epsilon_{\text{position}}$, $\epsilon_{\text{position}} \ge r$, candidate is degenerate.

---

## 3. Circumferential Support vs Topological Connectivity

### 3.1 Why Connectedness ($C_{\text{closed}}$) Fails on Engineering Drawings
Topological contour tracing (`cv2.findContours`) forms connected graphs of 8-connected edge pixels.
When a dimension line, witness line, centerline, or hatching intersects a circle at point $P$:
1. $P$ is a junction of degree $\ge 3$ (T-junction or X-crossing).
2. The contour tracer branches along the intersecting line.
3. The resulting contour contains both circle arc segments and intersecting straight line segments.
4. Least-squares circle fitting over this composite contour produces huge residuals ($d_r \gg \epsilon_{\text{position}}$).
5. Even if filtered, the circle is fragmented into disconnected sub-contours $S_1, S_2, \dots, S_k$.
6. Each sub-contour $S_j$ has an angular extent strictly less than $360^\circ$ and exhibits large angular gaps $\Delta \theta_{\text{gap}} \gg \text{pixel spacing}$.
7. Therefore, PR #518's requirement that a single contour must have $\Delta \theta_{\text{gap}} \le 2\arcsin\left(\frac{\text{bound}}{2r}\right)$ mathematically guarantees that **all** intersected engineering circles are rejected.

### 3.2 Definition of Distributed Circumferential Support
Instead of requiring a single connected component, source support is defined over angular bins:
Divide the circle circumference $[0, 2\pi)$ into $M$ equal angular bins:
$$B_m = \left[\frac{2\pi m}{M}, \frac{2\pi (m+1)}{M}\right), \quad m = 0, \dots, M-1$$
A bin $B_m$ is **supported** ($s_m = 1$) if there exists at least one edge pixel $e_i \in E$ such that:
1. $\theta(e_i) \in B_m$;
2. $d_r(e_i; C) \le \epsilon_{\text{position}}$;
3. $\Delta \phi_i \le \epsilon_{\text{normal}}(r)$.

The **Total Angular Support** is:
$$\mathcal{S}(C) = \frac{1}{M} \sum_{m=0}^{M-1} s_m \in [0, 1]$$

The **Largest Unsupported Arc** is:
$$\Theta_{\text{gap}}(C) = \max \text{ contiguous run of bins where } s_m = 0 \times \frac{2\pi}{M}$$

The **Quadrant Occupancy** is:
$$\mathcal{Q}(C) = \prod_{k=0}^3 \mathbf{1}\left( \sum_{m \in Q_k} s_m > 0 \right)$$
where $Q_k = \left[\frac{k\pi}{2}, \frac{(k+1)\pi}{2}\right)$. If any quadrant has zero support, $\mathcal{Q}(C) = 0$.
