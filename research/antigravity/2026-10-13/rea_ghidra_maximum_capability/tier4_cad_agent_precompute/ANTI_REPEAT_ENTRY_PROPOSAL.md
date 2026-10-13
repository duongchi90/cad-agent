# ANTI_REPEAT_ENTRY_PROPOSAL: REA-020 Polyline Bulge Reconstruction

### Proposed Entry for REA_CATALOG.md:

```markdown
### REA-020: POLYLINE_BULGE_AND_ARC_RECONSTRUCTION
- **CAPABILITY:** Exact reconstruction of curved polyline segments as DXF/AutoCAD LWPOLYLINE vertex entities with mathematical bulge parameters ($b = \tan(\theta/4)$).
- **EXTERNAL_SOURCE:** Autodesk DXF Specification Group Code 42 & `ezdxf.math.bulge` / LibreCAD `RS_Math`.
- **SOURCE_TYPE:** `SPEC_PUBLIC` / `ALGORITHM_OPEN_SOURCE`.
- **EXACT_VERSION_COMMIT:** `dxf-r14-through-2027-spec` / `ezdxf-1.4.x`.
- **KNOWN_VERSION_FAMILY:** Standard AutoCAD LWPOLYLINE Specification.
- **PROVENANCE:** `SOURCE_CODE_INSPECTED` (`ezdxf/math/bulge.py`) + `DOCUMENTATION_ONLY` (Autodesk DXF Reference) + `TESTS_INSPECTED` (`TRANSFER_ORACLE.md`).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **CURRENT_CAD_AGENT_OWNER:** `dxf_builder_lib/builder.py` and `primitive_ir_lib/geometry_extraction.py`.
- **OWNER_MAPPING_STATUS:** `VALID` (Verified on current main).
- **CURRENT_DISPOSITION:** `READY_TO_TRANSFER`.
- **DO_NOT_REPEAT_REA:** `YES`.
- **RESEARCH_AGAIN_ONLY_IF:** AutoCAD introduces an incompatible non-uniform polyline spline representation replacing LWPOLYLINE Group Code 42.
- **EVIDENCE_TIER:** `VERIFIED_ALGORITHM_AND_ORACLE`.
- **LICENSE:** Public Domain / MIT (ezdxf math).
- **LICENSE_SOURCE:** Autodesk DXF Reference / ezdxf open repository.
- **DIRECT_REUSE_ALLOWED_BY_PROJECT_POLICY:** `YES`.
- **PROJECT_INTEGRATION_DECISION:** `TRANSFER_ALGORITHM_TO_EXISTING_OWNERS` (Transfer clean-room Python math function to `dxf_builder_lib` and `primitive_ir_lib`; do NOT create new subsystems).
- **WHAT_WAS_INSPECTED:** Mathematical relationship between 3-point circular arcs, center coordinates, angular traversal direction, and DXF bulge parameter.
- **VERIFIED_BEHAVIOR_AND_INVARIANTS:**
  - $b = \tan(\theta/4)$ where $\theta$ is the included central angle.
  - $b > 0$ denotes Counter-Clockwise (CCW) traversal; $b < 0$ denotes Clockwise (CW) traversal.
  - Singularity threshold $|b| < 10^{-7}$ must snap to $b = 0.0$ (straight line segment) to prevent radius overflow.
- **FAILURE_MODES_AND_LIMITS:**
  - Collinear 3-point inputs produce zero cross-product determinant, yielding division by zero if unshielded. Protected by determinant guard $|\Delta| < 10^{-9}$.
- **WHAT_NOT_TO_COPY_OR_INVENT:**
  - Do NOT invent custom multi-segment chord approximation when a native bulge can represent the exact curve.
  - Do NOT build an external C++ native curve-fitting module.
- **DURABLE_POINTERS:**
  - `research/antigravity/2026-10-13/rea_ghidra_maximum_capability/tier4_cad_agent_precompute/`
  - `dxf_builder_lib/builder.py`
  - `primitive_ir_lib/geometry_extraction.py`
```
