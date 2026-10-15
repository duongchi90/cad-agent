# Observational Equivalence and Identifiability Proof

**Campaign ID:** `ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015`
**Phase:** 12 & 13
**Date:** 2026-10-15
**Status:** PROVEN — DECISION-GRADE THEOREM

---

## 1. Theorem: Information-Theoretic Equivalence of Occluded Circles and Open Arcs in the Raster Domain

### Theorem Statement
Let $\Omega \subset \mathbb{Z}^2$ be a discrete raster grid.
Let $\mathcal{C}$ be a complete planar circle and $\mathcal{A}$ be an open circular arc sharing the identical center $(c_x, c_y)$ and radius $r$, where $\mathcal{A}$ spans the angular domain $[0, 2\pi) \setminus \Gamma$, and $\Gamma = (\theta_{\text{start}}, \theta_{\text{end}})$ is an open angular interval of missing curve.

Let $\mathcal{M} \subset \Omega$ be an occlusion region (e.g. an unprinted void, white dimension text box, or margin clip) that covers the spatial footprint of the arc segment over $\Gamma$:
$$\{ (c_x + r\cos\theta, c_y + r\sin\theta) : \theta \in \Gamma \} \subset \mathcal{M}$$

If both geometries are rendered onto the raster grid $\Omega$ and clipped by $\mathcal{M}$:
$$I_{\text{circle}} \circ \mathcal{M} \equiv I_{\text{arc}} \circ \mathcal{M}$$

Then:
$$\forall p \in \Omega: I_{\text{circle}}(p) = I_{\text{arc}}(p)$$
$$\forall p \in \Omega: \nabla I_{\text{circle}}(p) = \nabla I_{\text{arc}}(p)$$
$$\forall p \in \Omega: E_{\text{circle}}(p) = E_{\text{arc}}(p)$$

### Proof
1. Outside $\mathcal{M}$, the continuous locus of $\mathcal{C}$ and $\mathcal{A}$ are identical by construction:
   $$\mathcal{C} \setminus \mathcal{M} = \mathcal{A} \setminus \mathcal{M} = \{ (c_x + r\cos\theta, c_y + r\sin\theta) : \theta \notin \Gamma \}$$
2. Inside $\mathcal{M}$, both images evaluate to the background color $I_{\text{bg}}$ (e.g. white $255$):
   $$\forall p \in \mathcal{M}, \quad I_{\text{circle}}(p) = I_{\text{bg}}, \quad I_{\text{arc}}(p) = I_{\text{bg}}$$
3. Since $I_{\text{circle}}(p) = I_{\text{arc}}(p)$ for all $p \in \Omega \setminus \mathcal{M}$ and all $p \in \mathcal{M}$, $I_{\text{circle}} = I_{\text{arc}}$ everywhere on $\Omega$.
4. Any deterministic functional $f(I)$ (such as convolution, edge detection, Hough accumulator, normal gradient, or least-squares fit) is a single-valued map on the pixel array $I$. Since $I_{\text{circle}} = I_{\text{arc}}$, $f(I_{\text{circle}}) = f(I_{\text{arc}})$.
5. Therefore, no classifier operating purely on the raster matrix $I$ can distinguish $\mathcal{C}$ from $\mathcal{A}$. $\blacksquare$

---

## 2. Empirical Verification

In script `verify_identifiability.py`:
- Fixture Pair 1: Circle with $r=75$ occluded by a white rectangle spanning $40^\circ$ vs Arc of $320^\circ$ with identical white rectangle.
- Result:
  $$\|I_A - I_B\|_1 = 0$$
  $$\|E_A - E_B\|_0 = 0$$
  $$\text{Pixel Difference} = 0.000\text{ px}$$

---

## 3. Corollaries and Invariants for CAD-Agent

### Corollary 1: Impossibility of Unconditioned Raster-Only Interrupted Circle Admission
Any algorithm that admits a candidate circle having an unexplained angular gap $\Delta \theta_{\text{gap}}$ based solely on a coverage threshold $\tau < 1.0$ (e.g., $\tau = 80\%$ or $\tau = 90\%$) **MUST** falsely admit an authentic CAD arc having angular span $2\pi - \Delta \theta_{\text{gap}}$ (e.g. a $300^\circ$ or $330^\circ$ open arc in a retaining ring groove, slot, or cam profile).

### Corollary 2: The Two and Only Two Safe Paths for Interrupted Circle Admission
To admit an interrupted circle without causing false arc admissions, one of two independent witnesses is strictly necessary:
1. **Geometric Occluder Witness (Candidate F):**
   The unsupported angular gap $[\theta_{\text{start}}, \theta_{\text{end}}]$ must be spatially and topologically explained by an intersecting linework (dimension line, witness line, centerline) that physically crosses the circumference locus and continues on both sides (X-crossing) or terminates directly at the boundary.
2. **Semantic / OCR Role Witness (Hybrid Admission):**
   The unsupported angular gap is geometrically spanned by a recognized OCR text bounding box or annotation entity whose role is confirmed as non-part geometry.

### Corollary 3: Fail-Closed Policy on Unexplained Gaps
If an angular gap $\Theta_{\text{gap}} > 2\arcsin\left(\frac{\epsilon_{\text{position}}}{2r}\right)$ is NOT explained by an observed geometric occluder or confirmed annotation witness:
$$\text{ADMISSION\_DISPOSITION} = \text{UNRESOLVED\_OR\_REJECT}$$
Silent promotion to a full circle is mathematically unsafe and forbidden.
