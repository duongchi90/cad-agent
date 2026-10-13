# BEHAVIORAL_CONTRACT_AND_INVARIANTS: Formal Dimension Invariants & Hygiene

- **Document ID:** `REA_DIM_ASSOC_INVARIANTS_V1`
- **Executor Role:** `CAD_AGENT_REA_GHIDRA_CROSS_MACHINE_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`

---

## 1. Classification of Invariants & Heuristics

To maintain strict scientific hygiene (as mandated by PO Decision [`#491 Comment 6151289810`](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6151289810)), we strictly distinguish:
1. `STANDARD_DEFINED_INVARIANT` (Normative standards from ISO 129 / ASME Y14.5 / DXF Reference)
2. `IMPLEMENTATION_HEURISTIC` (Empirical approximations used to handle raster noise or layout collisions)
3. `PROJECT_POLICY` (Cad Agent codebase architectural constraints)

---

## 2. Invariant Specifications

### Invariant 1: Parallelism of Dimension Line to Feature Chord
- **Classification:** `STANDARD_DEFINED_INVARIANT`
- **Definition:** The dimension line vector $\vec{v}_{\text{dim}} = A_2 - A_1$ is strictly parallel to the feature baseline $\vec{v}_{\text{feat}} = P_2 - P_1$:
  $$\frac{\vec{v}_{\text{dim}} \cdot \vec{v}_{\text{feat}}}{\|\vec{v}_{\text{dim}}\| \|\vec{v}_{\text{feat}}\|} = 1.0$$
- **Raster Vectorization Tolerance:** For noisy scanned drawings, $|\cos(\theta)| \ge \cos(5^\circ) \approx 0.9962$ (`IMPLEMENTATION_HEURISTIC`).

### Invariant 2: Orthogonality of Witness Lines
- **Classification:** `STANDARD_DEFINED_INVARIANT`
- **Definition:** Witness lines $W_1$ and $W_2$ project outward from the feature baseline and are strictly orthogonal to the dimension line:
  $$\vec{u}_{\text{wit}} \cdot \vec{u}_{\text{dim}} = 0.0$$
- **Raster Vectorization Tolerance:** $|\vec{u}_{\text{wit}} \cdot \vec{u}_{\text{dim}}| \le \sin(5^\circ) \approx 0.0872$ (`IMPLEMENTATION_HEURISTIC`).

### Invariant 3: Measurement Equivalence
- **Classification:** `STANDARD_DEFINED_INVARIANT`
- **Definition:** The Euclidean distance between the arrowhead termination points equals the distance between feature definition points:
  $$\|A_2 - A_1\| = \|P_2 - P_1\| = \text{Nominal Measurement } M$$

### Invariant 4: Arrowhead Inward/Outward Flip Threshold
- **Classification:** `IMPLEMENTATION_HEURISTIC`
- **Definition:** When the dimension line segment length is insufficient to contain both arrowheads and the text box, arrowheads flip outward:
  $$\text{If } \|A_2 - A_1\| < 2 \cdot L_{\text{arrow}} + W_{\text{text}} \implies \text{Flip Outward}$$
- **Drafting Consequence:** Arrowhead 1 is placed at $A_1 - L_{\text{arrow}} \vec{u}_{\text{dim}}$ pointing $+ \vec{u}_{\text{dim}}$; Arrowhead 2 is placed at $A_2 + L_{\text{arrow}} \vec{u}_{\text{dim}}$ pointing $- \vec{u}_{\text{dim}}$.

### Invariant 5: Extension Overhang & Origin Gap
- **Classification:** `STANDARD_DEFINED_INVARIANT`
- **Definition:**
  - Witness lines do not terminate exactly on the dimension line; they overshoot by $d_{\text{over}} \in [2.0, 3.0]\text{ mm}$.
  - Witness lines do not touch the physical feature contour; they start with an origin gap $g_{\text{orig}} \in [1.0, 2.0]\text{ mm}$.
- **Discriminator Value:** A line that terminates exactly on the contour without an origin gap is an object contour line, not a witness line!

---

## 3. Project Architectural Policies

1. **No New Subsystem:** Transfer logic directly into existing owners `primitive_ir_lib/cross_validation.py` and `dxf_builder_lib/builder.py`.
2. **Fail-Closed on Ambiguity:** If candidate witness lines do not satisfy the orthogonality and parallelism bounds within tolerance, classify as `unverified` rather than guessing or producing corrupted DXF entities.
3. **Deterministic Clean-Room Execution:** Rely only on standard Python `math` operations without external heavy C++ dependencies.
