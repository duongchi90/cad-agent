# N+1 / N+2 Candidate Evaluation Matrix for Cad Agent Research Precompute

## Evaluation Criteria (Scoring: 0 to 5)
- **PR:** `PRODUCT_RELEVANCE` (Direct fit for current Cad Agent roadmap and AutoCAD plugin requirements)
- **LK:** `LIKELIHOOD_OF_FUTURE_NEED` (Probability Luna/production lane will encounter this exact barrier)
- **DC:** `DISCOVERY_COST_FOR_LUNA` (Effort Luna would waste reinventing math/formats without precomputation)
- **RA:** `REA_ADVANTAGE` (Leverage provided by external codebases, specifications, or binary analysis)
- **TR:** `TRANSFERABILITY` (Simplicity of transferring algorithm/data model into Cad Agent without bloat)
- **TE:** `TESTABILITY` (Feasibility of writing deterministic, self-contained unit tests and oracles)
- **LS:** `LICENSE_SAFETY` (Clarity and permissiveness of prior art: MIT, BSD, Apache, Public Domain)
- **OR:** `OWNER_REUSE_POTENTIAL` (Reusability of existing Cad Agent modules: `primitive_ir_lib`, `dxf_builder_lib`)
- **RW:** `RISK_OF_WASTED_RESEARCH` (Risk that findings remain academic or superseded by external platforms)

$$\text{ROI} = (\text{PR} + \text{LK} + \text{DC} + \text{RA} + \text{TR} + \text{TE} + \text{LS} + \text{OR}) - \text{RW}$$

---

## 10 Candidate Matrix

| Rank | Candidate Capability | Primary Candidate Owner | PR | LK | DC | RA | TR | TE | LS | OR | RW | ROI Score | Decision |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1** | **`POLYLINE_BULGE_AND_ARC_RECONSTRUCTION`** | `dxf_builder_lib.builder` & `primitive_ir_lib` | 5 | 5 | 5 | 4 | 5 | 5 | 5 | 5 | 1 | **38 / 40** | **SELECTED (WINNER)** |
| 2 | `DIMENSION_ARROWHEAD_WITNESS_ASSOCIATION` | `cad_agent.mechanical_skills` | 5 | 5 | 4 | 4 | 4 | 4 | 4 | 4 | 1 | **33 / 40** | Candidate |
| 3 | `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION` | `primitive_ir_lib.geometry_extraction` | 4 | 4 | 4 | 4 | 5 | 5 | 5 | 4 | 1 | **34 / 40** | Candidate |
| 4 | `LEADER_MLEADER_RECONSTRUCTION` | `cad_agent.mechanical_skills` | 4 | 4 | 4 | 3 | 4 | 4 | 5 | 4 | 2 | **30 / 40** | Candidate |
| 5 | `HATCH_REGION_BOUNDARY_RECOGNITION` | `primitive_ir_lib.geometry_extraction` | 4 | 4 | 5 | 3 | 3 | 3 | 4 | 4 | 2 | **28 / 40** | Candidate |
| 6 | `REPEATED_COMPONENT_GRAPH_MATCHING` | `cad_agent.block_canonicalization` | 4 | 3 | 5 | 4 | 3 | 3 | 4 | 3 | 2 | **27 / 40** | Candidate |
| 7 | `CAD_TOPOLOGY_WATERTIGHT_REPAIR` | `primitive_ir_lib.line_merging` | 4 | 4 | 4 | 3 | 4 | 4 | 5 | 4 | 2 | **30 / 40** | Candidate |
| 8 | `TABLE_GRID_CELL_STRUCTURE_EXTRACTION` | `cad_agent.drawing_metadata` | 3 | 4 | 4 | 3 | 4 | 4 | 5 | 3 | 2 | **28 / 40** | Candidate |
| 9 | `LAYER_STYLE_METADATA_RECONSTRUCTION` | `dxf_builder_lib.builder` | 4 | 4 | 3 | 3 | 5 | 5 | 5 | 4 | 1 | **32 / 40** | Candidate |
| 10 | `NATIVE_DIMENSION_PERSISTENCE_SEMANTICS` | `autocad_plugin.CadAgent.AutoCAD2027` | 5 | 3 | 5 | 4 | 2 | 3 | 4 | 3 | 3 | **26 / 40** | Adjacent to PR503 |

---

## Detailed Rationale for Candidate 1 Selection

**`POLYLINE_BULGE_AND_ARC_RECONSTRUCTION`** is decisively selected because:
1. **Critical Path Cad Agent Need:** In 2D CAD engineering drawings, composite curves (fillets, rounds, curved boundaries) are represented in DXF and AutoCAD databases as `LWPOLYLINE` entities with vertex bulge parameters ($b = \tan(\theta/4)$). Currently, Cad Agent's extraction either fragments arcs into straight polyline chords or exports detached `ARC` entities that lose topological connectivity.
2. **Immediate Owner Availability:** `dxf_builder_lib/builder.py` and `primitive_ir_lib/geometry_extraction.py` already own polyline construction and curve extraction.
3. **High Mathematical Discovery Cost Avoided:** Developing the bidirectional 3-point-to-bulge and bulge-to-arc center/radius conversion from scratch involves subtle geometric edge cases (collinear points, clockwise vs counter-clockwise signs, inflection points, angles $> \pi$, numerical singularities near zero). Reusing verified algorithms avoids 10+ hours of trial-and-error discovery.
4. **License & Patent Safety:** The DXF bulge mathematical specification is in the public domain and standard in open CAD libraries (LibreCAD, ezdxf, QCAD).
