# CAD_AGENT_OWNER_MAP: Existing Owners & Anti-Bloat Architecture (REA-022)

- **Document ID:** `REA_CONTOUR_SIMP_OWNER_MAP_V1`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Capability:** `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION`

---

## 1. Mapping to Existing Main Codebase Owners

### A. Existing Specialized RDP Reuse (Verified on Main)
- **EXISTING_SPECIALIZED_RDP_REUSE:** `primitive_ir_lib/dimension_geometry.py::_contour_arrow_points`
- **SCOPE:** Small bounded arrowhead contours ($P \approx 30\text{--}50\text{ px}$)
- **IMPLEMENTATION:** `cv2.approxPolyDP(contour, 0.08 * perimeter, True)`
- **STATUS:** **VALID AND NOT DEFECTIVE IN ITS SCOPE**. The `0.08 * perimeter` setting is specifically calibrated for tiny triangular arrowhead polygons where $\epsilon \approx 2.4\text{--}4.0\text{ px}$ correctly extracts 3-4 vertices. It must NOT be called defective based on full-part synthetic benchmarks.

### B. Future Full Contour Candidate Owner
- **FUTURE_FULL_CONTOUR_CANDIDATE_OWNER:** `primitive_ir_lib/geometry_comparator.py::_contour_points`
- **CURRENT_IMPLEMENTATION:** Uses `cv2.findContours(..., cv2.CHAIN_APPROX_NONE)` to extract raw pixel loops, followed by `_resample_closed(count=128)`.
- **CONDITION:** **ONLY AFTER MEASURED PRODUCT RED**. Bounded absolute RDP pre-pass may be introduced as a pre-filtering step only if an active measured product test or real drawing comparison fails due to raw staircase aliasing or resampling skew.
- **PRODUCTION_TRANSFER_AUTHORIZED:** `NO`.

---

## 2. Anti-Bloat Architecture Principles

1. **NO New Subsystem:** Do **not** create a `contour_processing_service/` or `vectorizer_engine/`. If ever adopted, the capability is a 1-line call to existing OpenCV `cv2.approxPolyDP` with bounded parameterization inside `geometry_comparator.py::_contour_points`.
2. **NO New Dependencies:** OpenCV (`cv2`) and NumPy are already standard dependencies in `primitive_ir_lib`. Zero new external libraries.
3. **No Unwarranted Production Modification:** Keep this capability as a `RESEARCH_PRIOR`. Do not mutate `geometry_comparator.py` until an active product RED or benchmark demonstrates contour noise failure on real drawing comparisons.
4. **Preserve Specialized Arrowhead Reuse:** Do not mutate or refactor `dimension_geometry.py::_contour_arrow_points`. Its relative epsilon is specialized and effective for bounded arrowhead contours.
