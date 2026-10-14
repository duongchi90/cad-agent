# CAD_AGENT_OWNER_MAP: Existing Owners & Anti-Bloat Architecture (REA-022)

- **Document ID:** `REA_CONTOUR_SIMP_OWNER_MAP_V1`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Capability:** `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION`

---

## 1. Mapping to Existing Main Codebase Owners

| Component | What It Currently Contains (Verified on main) | Contour Simplification Role / Gap | Status on Main |
| :--- | :--- | :--- | :---: |
| **`primitive_ir_lib/geometry_comparator.py`** | `_contour_points(mask)` uses `cv2.findContours(..., cv2.CHAIN_APPROX_NONE)` to extract full pixel loops (thousands of points), then resamples them via `_resample_closed(count=128)`. | **EXISTING_OWNER**<br>**GAP:** Direct raw pixel loops contain high-frequency aliasing noise and uneven staircase density, which skews arc-length cumulative distance sampling. A bounded absolute RDP pre-pass ($\epsilon = 1.0\text{ px}$) would eliminate 97%+ of redundant noise before resampling. | **EXISTING_OWNER** (smallest appropriate owner) |
| **`primitive_ir_lib/dimension_geometry.py`** | `_contour_arrow_points()` uses `cv2.approxPolyDP(contour, 0.08 * perimeter, True)` to identify triangular arrowheads near dimension lines. | **EXISTING_CONSUMER**<br>**NOTE:** Uses aggressive relative $\epsilon = 0.08 \times P$ specifically tailored for small arrowheads ($P \approx 30\text{--}50\text{ px}$). This relative formula MUST NOT be copied or applied to full drawing contours. | **EXISTING_OWNER** (specialized consumer) |

---

## 2. Anti-Bloat Principles

1. **NO New Subsystem:** Do **not** create a `contour_processing_service/` or `vectorizer_engine/`. The capability is a 1-line call to existing OpenCV `cv2.approxPolyDP` with safe parameterization ($\epsilon = 1.0\text{ px}$).
2. **NO New Dependencies:** OpenCV (`cv2`) and NumPy are already standard dependencies in `primitive_ir_lib`. Zero new external libraries.
3. **No Unwarranted Production Modification:** Keep this capability as a `RESEARCH_PRIOR`. Do not mutate `geometry_comparator.py` until an active product RED or benchmark demonstrates contour noise failure on real drawing comparisons.
