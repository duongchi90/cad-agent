# DISCRIMINATOR_ALGORITHM: Clean-Room Dimension Line & Witness Line Disambiguation

- **Document ID:** `REA_DIM_ASSOC_DISCRIMINATOR_V1`
- **Executor Role:** `CAD_AGENT_REA_GHIDRA_CROSS_MACHINE_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`

---

## 1. Problem Statement: The Witness-Line Misbinding Trap

In Cad Agent's current main implementation (`primitive_ir_lib/cross_validation.py`):
```python
# CURRENT MAIN LOGIC (Vulnerable to misbinding)
line = find_nearest_line(text, raw_lines, max_distance_px=max_distance_px)
measured = line.length_px() * calibration.pixel_to_unit_scale
delta_percent = abs(text.parsed_value - measured) / text.parsed_value * 100.0
status = "confirmed" if delta_percent <= threshold_percent else "conflict"
```

### The Root Cause of #491 Holdout Gaps
1. **Witness Line Misbinding:** If the nearest line to the text bounding box is an extension/witness line (which is perpendicular to the dimension line), its length represents only the extension offset (e.g. $15\text{ mm}$), while the text indicates $100.0\text{ mm}$. The delta is $85\%$, causing `status = "conflict"`.
2. **Contour Line Misbinding:** If an adjacent object contour line is closer to the text than the dimension line, `cross_validation` erroneously evaluates the contour length.
3. **Loss of Native Dimension Semantics:** Because only 1 line ID is bound, `dxf_builder_lib` cannot know the true feature points ($P_1, P_2$) or the dimension line offset ($P_{\text{base}}$).

---

## 2. The 3-Stage Discriminator Algorithm

### Stage 1: Angular Role Partitioning
Given a `RawText` with orientation angle $\theta_{\text{text}}$ and candidate `RawLine` objects within radius $R_{\text{search}}$:
- Compute line angle $\theta_{\text{line}} = \text{atan2}(\Delta y, \Delta x) \pmod{180^\circ}$.
- Angular difference to text:
  $$\Delta\theta = \min(|\theta_{\text{line}} - \theta_{\text{text}}|, 180^\circ - |\theta_{\text{line}} - \theta_{\text{text}}|)$$
- **Role Assignment:**
  - If $\Delta\theta \le 10.0^\circ$: Line is classified as a **`DIMENSION_LINE_CANDIDATE`** (Parallel to text).
  - If $|\Delta\theta - 90.0^\circ| \le 10.0^\circ$: Line is classified as a **`WITNESS_LINE_CANDIDATE`** (Orthogonal to text).
  - Otherwise: Line is an oblique contour or hatch line $\implies$ **`REJECT`**.

### Stage 2: Geometric Dimension Line Verification
For each `DIMENSION_LINE_CANDIDATE`:
- Calculate scaled length: $L_{\text{scaled}} = L_{\text{px}} \times s_{\text{calib}}$.
- Check consistency with text value $V_{\text{text}}$:
  $$\delta_{\text{len}} = \frac{|L_{\text{scaled}} - V_{\text{text}}|}{V_{\text{text}}} \times 100\%$$
- If $\delta_{\text{len}} \le 3.0\%$: Candidate is **`CONFIRMED_DIMENSION_LINE`**.

### Stage 3: Topological Witness-Line Pairing & Feature Point Binding
For the `CONFIRMED_DIMENSION_LINE` with endpoints $A_1, A_2$:
- Search `WITNESS_LINE_CANDIDATE` set for lines passing through or within $\epsilon_{\text{snap}} = 5\text{ px}$ of $A_1$ and $A_2$.
- Pair $W_1$ (passing near $A_1$) and $W_2$ (passing near $A_2$).
- The distal endpoints of $W_1$ and $W_2$ (facing toward the object body) identify the exact physical feature definition points $P_1$ and $P_2$!
- **Output Triple:** $(P_1, P_2, P_{\text{base}} = A_1)$ directly populates DXF Group Codes 13, 14, and 10!
