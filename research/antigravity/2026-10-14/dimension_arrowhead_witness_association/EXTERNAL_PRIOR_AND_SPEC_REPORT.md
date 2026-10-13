# EXTERNAL_PRIOR_AND_SPEC_REPORT: Dimension Geometry & Witness-Arrowhead Association

- **Document ID:** `REA_DIM_ASSOC_EXTERNAL_PRIOR_V1`
- **Executor Role:** `CAD_AGENT_REA_GHIDRA_CROSS_MACHINE_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Research Topic:** `DIMENSION_ARROWHEAD_WITNESS_ASSOCIATION` (Queue Item #2, Priority P0)
- **Catalog Proposal:** `REA-021`

---

## 1. Technical Drafting Standards Prior (ISO 129-1 & ASME Y14.5)

In formal mechanical engineering drafting, a linear dimension is an assembly of four geometric constituents governed by strict mathematical and topological rules:

### A. The Four Geometric Constituents
1. **Dimension Line (Đường kích thước):**
   - A straight line indicating the direction and extent of the dimension.
   - Parallel to the measured feature baseline ($\vec{u}_{\text{dim}} \parallel \vec{P_2 - P_1}$).
   - Terminated at each end by arrowheads touching the extension lines.
2. **Extension Lines / Witness Lines (Đường gióng):**
   - Two parallel straight lines extending from the feature definition points ($P_1, P_2$) outward to the dimension line.
   - Orthogonal to the dimension line ($\vec{u}_{\text{wit}} \perp \vec{u}_{\text{dim}}$, i.e., $\vec{u}_{\text{wit}} \cdot \vec{u}_{\text{dim}} = 0$).
   - **Extension Origin Gap ($g_{\text{orig}}$):** Distance between feature point and start of extension line (typically $1.0\text{--}2.0\text{ mm}$).
   - **Extension Overhang / Overshoot ($d_{\text{over}}$):** Distance the extension line extends beyond the dimension line (typically $2.0\text{--}3.0\text{ mm}$).
3. **Arrowheads (Mũi tên kích thước):**
   - Terminating symbols placed at the intersection of the dimension line and extension lines.
   - Standard aspect ratio $3:1$ (length $L_{\text{arrow}} \approx 3 \times W_{\text{arrow}}$, included angle $15^\circ\text{--}20^\circ$).
4. **Dimension Text (Con số kích thước):**
   - Numeric measurement string indicating the nominal distance between $P_1$ and $P_2$.
   - Placed near the midpoint of the dimension line, either centered with a gap or positioned above the line.

---

## 2. Open-Source CAD Engine Prior (LibreCAD `RS_DimLinear`)

In LibreCAD (`librecad/src/lib/engine/rs_dimlinear.cpp`, GPLv2 behavioral reference):

### A. Definition Points & Projection Math
- Let $P_1 = (x_1, y_1)$ and $P_2 = (x_2, y_2)$ be the measured feature endpoints.
- Let $P_{\text{base}} = (x_b, y_b)$ be the user-specified point defining the dimension line offset.
- Direction vector $\vec{v} = P_2 - P_1$, unit vector $\vec{u}_{\text{dim}} = \frac{\vec{v}}{\|\vec{v}\|}$.
- Orthogonal unit normal $\vec{u}_{\text{wit}} = (-u_{\text{dim}, y}, u_{\text{dim}, x})$.
- The offset distance $h$ from the feature chord to the dimension line is:
  $$h = (P_{\text{base}} - P_1) \cdot \vec{u}_{\text{wit}}$$
- The dimension line endpoints (arrowhead positions $A_1, A_2$) are:
  $$A_1 = P_1 + h \cdot \vec{u}_{\text{wit}}, \quad A_2 = P_2 + h \cdot \vec{u}_{\text{wit}}$$
- The nominal dimension measurement is exactly:
  $$d_{\text{meas}} = \|A_2 - A_1\| = \|P_2 - P_1\|$$

### B. Arrowhead Inward vs Outward Flip Logic
When the measured distance $d_{\text{meas}}$ is small, standard drawing rules mandate flipping the arrowheads outward so they do not collide with each other or the text:
- Let $L_{\text{arrow}}$ be the arrowhead length and $W_{\text{text}}$ be the bounding width of the dimension text.
- If $d_{\text{meas}} \ge 2 \cdot L_{\text{arrow}} + W_{\text{text}}$:
  - **Inward Arrows:** Arrowhead 1 is at $A_1$ pointing toward $A_2$ ($+\vec{u}_{\text{dim}}$); Arrowhead 2 is at $A_2$ pointing toward $A_1$ ($-\vec{u}_{\text{dim}}$).
- If $d_{\text{meas}} < 2 \cdot L_{\text{arrow}} + W_{\text{text}}$:
  - **Outward Arrows:** Arrowheads flip to the outside of the extension lines, pointing inward toward $A_1$ and $A_2$.

---

## 3. Autodesk DXF Specification Prior (Group Codes for DIMENSION)

In the standard Autodesk DXF Reference:
- Entity name: `DIMENSION`
- **Group 10 ($x, y, z$):** Definition point for dimension line (specifies dimension line baseline coordinate $P_{\text{base}}$).
- **Group 11 ($x, y, z$):** Middle point of dimension text in WCS.
- **Group 13 ($x, y, z$):** First feature definition point ($P_1$).
- **Group 14 ($x, y, z$):** Second feature definition point ($P_2$).
- **Group 50 (double):** Rotation angle of dimension line (in degrees relative to WCS X axis).
- **Group 70 (integer):** Dimension type flag:
  - `0` = Rotated, horizontal, or vertical dimension.
  - `1` = Aligned dimension.
- **Group 1 (string):** Explicit text override. If empty or `<>`, AutoCAD/ezdxf calculates the measurement dynamically from $\|P_2 - P_1\|$.
