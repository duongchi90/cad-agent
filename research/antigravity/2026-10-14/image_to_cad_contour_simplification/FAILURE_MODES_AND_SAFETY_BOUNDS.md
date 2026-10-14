# FAILURE_MODES_AND_SAFETY_BOUNDS: Contour Simplification Hazards

- **Document ID:** `REA_CONTOUR_SIMP_FAILURES_V1`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Capability:** `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION` (REA-022)

---

## 1. Overview of Evaluated Hazards

In converting raster engineering drawings into CAD vector boundaries, naive application of polyline simplification algorithms introduces five severe failure modes that corrupt downstream CAD geometry. This document details each failure mode, empirical observations from the 7 synthetic fixtures, and geometric relation models.

---

## 2. Failure Mode 1: Small Feature / Notch Deletion (The Scale-Dependent Epsilon Trap)

### Scope of Existing Reuse vs Full-Part Contours
Current main contains:
- **`EXISTING_SPECIALIZED_RDP_REUSE=dimension_geometry.py::_contour_arrow_points`**
  - Implementation: `cv2.approxPolyDP(contour, 0.08 * perimeter, True)`
  - Scope: Small bounded arrowhead contours ($P \approx 30\text{--}50\text{ px}$, yielding $\epsilon \approx 2.4\text{--}4.0\text{ px}$).
  - Invariants: **Valid and not defective in its scope**. It appropriately simplifies small triangular arrowhead contours down to 3–4 vertices. It must NOT be judged defective based on full-part synthetic benchmarks.

### Mechanism on Full-Part Contours
While perimeter-relative epsilon works for isolated small arrowheads, applying perimeter-proportional epsilon to large whole-part mechanical contours creates a scale-dependent trap when $k \cdot P$ exceeds local feature dimensions:
- In tested synthetic Fixture 4 ($250 \times 150\text{ px}$ block, perimeter $P = 816\text{ px}$):
  - At tested setting $k = 0.02$, $\epsilon = 0.02 \times 816 = 16.32\text{ px}$.
  - At tested setting $k = 0.01$, $\epsilon = 0.01 \times 816 = 8.16\text{ px}$.
  - The tested keyway notch has width $6\text{ px}$ and depth $8\text{ px}$ (perpendicular deviation $8.0\text{ px}$).
  - Because tested $\epsilon \ge 8.0\text{ px}$, the RDP recursive chord test determines that the notch cavity deviates by less than or equal to $\epsilon$, discarding the notch vertices.
  - Result: The keyway notch is bridged over and erased.
- Note: This does **not** prove that all perimeter-relative scaling is universally invalid under all possible formulations; it proves specifically that tested full-part $k \cdot P$ settings ($k \ge 0.01$) erased tested small features when $\epsilon$ exceeded feature deviation.

### Empirical Evidence (Fixture 4 & Fixture 7)
- Fixture 4 ($6 \times 8\text{ px}$ notch on $250 \times 150\text{ px}$ block, $P = 816\text{ px}$):
  - At tested $\epsilon = 0.02 \times P$ ($\epsilon \approx 16.32\text{ px}$), `small_feature_survived = False`, Hausdorff error = $9.00\text{ px}$, corner survival drops from 100% to 50.0%.
  - At tested $\epsilon = 0.005 \times P$ ($\epsilon \approx 4.08\text{ px}$), notch survived with 8 points.
- Fixture 7 (stepped shaft with $8 \times 6\text{ px}$ keyway notch, $P = 1104\text{ px}$):
  - At tested $\epsilon = 0.01 \times P$ ($\epsilon \approx 11.04\text{ px}$), `small_feature_survived = False`, corner survival drops to 50.0%.

### Fixture-Specific Synthetic Observations & Limits
> [!IMPORTANT]
> **UNIVERSAL_EPSILON=NOT_PROVEN.**
> Numerical ranges $\epsilon \in [0.75, 1.5]\text{ px}$ are **fixture-specific synthetic observations** on tested binary raster shapes with 1-pixel steps. They do NOT constitute an all-scale or universal production claim.
>
> - **Scale Generalization:** No assertion is made regarding DPI invariance (e.g. "standard scans >= 300 DPI") or universal preservation of real-world features without explicit calibration. All observations are strictly relative to tested synthetic pixel dimensions ($6 \times 8\text{ px}$ notch, $R = 5\text{ px}$ hole, $R = 15\text{ px}$ fillet).
> - **Production Rule:** `FUTURE_FULL_CONTOUR_CANDIDATE_OWNER=geometry_comparator.py::_contour_points` under condition: **ONLY AFTER MEASURED PRODUCT RED**. `PRODUCTION_TRANSFER_AUTHORIZED=NO`.

---

## 3. Failure Mode 2: Corner Rounding & Apex Clipping

### Mechanism
When a sharp corner (e.g. $30^\circ$ acute apex, $45^\circ$ chamfer) has neighboring edge points that lie within $\epsilon$ of a chord cutting across the corner, RDP will clip the apex vertex if the perpendicular distance from the apex to the chord connecting the flanking edges is $\le \epsilon$.

### Empirical Evidence (Fixture 2)
- In Fixture 2 (Chevron with $30^\circ$ apex):
  - For $\epsilon \le 3.0\text{ px}$, the apex survives with $100\%$ corner retention ($H = 0.72\text{ px}$).
  - At $\epsilon = 0.08 \times P = 80\text{ px}$, the apex is clipped, corner survival drops to $83.3\%$, and Hausdorff error spikes to $50.0\text{ px}$.

### Geometric Relation and Fixture 2 Observation
> [!NOTE]
> **Mathematical model (assuming planar straight flanking edges of length $L_{\text{edge}}$ joining at angle $\alpha$ without raster noise):**
> A chord spanning flanking points at distance $L_{\text{edge}}/2$ deviates from the corner apex by $h = \frac{L_{\text{edge}}}{2} \tan\left(\frac{\alpha}{2}\right)$. For RDP not to clip the apex under this idealized model, $\epsilon < h$.
>
> **Fixture 2 Observation:** On the tested synthetic Chevron profile ($\alpha = 30^\circ$, flanking edges $\ge 200\text{ px}$), tested $\epsilon \le 3.0\text{ px}$ preserved the apex with 100% corner retention, while tested $\epsilon = 0.08 \times P = 80\text{ px}$ clipped the apex.

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

### Analytical Sagitta Model and Fixture 3 Observation
> [!NOTE]
> **Mathematical model (idealized circle of radius $R$):**
> The maximum sagitta between a circular arc of radius $R$ and a chord subtending angle $\theta$ is $h = R \left(1 - \cos\frac{\theta}{2}\right) \le \epsilon$.
>
> **Fixture 3 Observation:** On the tested synthetic circular disk ($R = 75\text{ px}$), tested $\epsilon = 0.75\text{ px}$ yielded 40 chord segments with measured radial error $0.69\text{ px}$ and area error $0.046\%$. At tested $\epsilon = 6.0\text{ px}$, radial error increased to $5.84\text{ px}$ with 8 chord segments.
>
> In Cad Agent's architecture, circular arcs should be extracted as true analytical `ARC` / `CIRCLE` primitives via Taubin SVD (`REA-002`) rather than simplified polylines.

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

### Geometric Collapse Model and Fixture 5 Observation
> [!NOTE]
> **Mathematical model (idealized convex loop of enclosing radius $R$):**
> If $\epsilon \ge R$, diametrically opposed boundary points have chord distance $\le \epsilon$, allowing RDP to reduce the closed loop to a 2-point degenerate line segment ($Area = 0$).
>
> **Fixture 5 Observation:** On tested synthetic circular hole ($R = 5\text{ px}$, $P = 28\text{ px}$), tested $\epsilon \in \{0.75, 1.5\}\text{ px}$ retained 4–8 vertices with preserved closed topology ($Area > 20\text{ px}^2$), whereas tested $\epsilon = 6.0\text{ px} > R$ collapsed the loop into a degenerate 2-point line with 100% area loss.

---

## 6. Failure Mode 5: Clean-Room Direct-Area VW Variant Behavior on Raster Staircase Loops

### Implementation Scope & Qualification
The evaluated implementation is a **`Clean_Room_Direct_Area_VW_Variant`**:
- It recomputes local triangle areas directly without standard monotonic effective-area hierarchy propagation (canonical Visvalingam-Whyatt maintains an ascending ladder where each vertex effective area is bounded below by the previously removed vertex area).
- The findings below report strictly on this direct-area variant on the tested synthetic discretized contours.
- Canonical Visvalingam-Whyatt with monotonic hierarchy was not benchmarked, and no claims of general unsuitability are made regarding canonical VW or algorithms outside this tested variant.

### Mechanism of Direct-Area Variant on Tested Fixtures
The direct-area variant prioritizes vertices by the area of the triangle formed with their immediate active neighbors:
$$A_i = \frac{1}{2} |(x_p - x_n)(y_i - y_p) - (x_i - x_p)(y_p - y_n)|$$
In a raw 1-pixel raster staircase chain (`cv2.CHAIN_APPROX_NONE`), every step has $(\Delta x, \Delta y) \in \{(\pm 1, 0), (0, \pm 1)\}$. The triangle area of any step is at most $0.5\text{ px}^2$.

On the tested pixel grid, a true $90^\circ$ CAD corner also has an initial local triangle area of only $0.5\text{ px}^2$. In this direct-area variant:
1. True discrete corners have the same initial local area ($0.5\text{ px}^2$) as 1-pixel staircase steps on straight edges.
2. Once points on adjacent edges are removed, local triangle areas update directly without monotonic filtering.
3. For tested area thresholds $\tau_{\text{area}} \ge 1.0\text{ px}^2$, this direct-area variant progressively eliminated corner points, stopping at the minimal vertex limit ($N = 3$) on closed loops with $87\%\text{--}99\%$ area error on the tested shapes.

### Benchmark Finding on Tested Variant
> [!NOTE]
> In the tested synthetic discrete raster fixtures, the `Clean_Room_Direct_Area_VW_Variant` (without monotonic hierarchy) collapsed closed raster loops at tested thresholds $\tau \ge 1.0\text{ px}^2$. For Cad Agent's candidate contour filtering, OpenCV's standard Ramer-Douglas-Peucker (`approxPolyDP`) is already present as an existing dependency and achieved 100% corner preservation on tested fixtures. Canonical VW was not tested.
