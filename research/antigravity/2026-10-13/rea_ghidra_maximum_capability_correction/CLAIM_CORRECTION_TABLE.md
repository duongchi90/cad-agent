# CLAIM_CORRECTION_TABLE: Audit & Rectification of Research Assertions

- **Document ID:** `REA_CLAIM_CORRECTION_TABLE_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Basis Research Head:** `8168cf5d74c97a5475eb61c1168d97e49bc51b66`
- **Basis Main:** `86318afc722939d88f355437e55405d012cba356`

---

## Master Claim Correction Inventory

| # | Topic | Old Material Claim | Evidence | Corrected Status | Corrected Claim | Rationale |
| :-: | :--- | :--- | :--- | :---: | :--- | :--- |
| **1** | **Tier 1 Geometry Scope** | "Recovered 3-point circle fitting from Tier 1 binary" | Frozen ground truth in `SOURCE_EXPECTATION_MODEL_FROZEN.md` | `INCORRECT` | Tier 1 binary contained distance, affine transform, bbox expansion, cross product, perpendicular distance, shoelace area, point-in-polygon, Douglas-Peucker, and convex hull. It did **not** contain 3-point circle fitting. | 3-point circle fitting was conceptualized during planning but omitted from compiled `cadgeom_core.c`. Prose summary incorrectly claimed recovery. |
| **2** | **Tier 2 Entity Types** | "Recovered ARC, Polyline, EOF opcodes" | Frozen source & spec in `BLIND_MODULE_MAP.md` | `INCORRECT` | Tier 2 binary defined `ENTITY_LINE` (0x01), `ENTITY_CIRCLE` (0x02), and `ENTITY_POLYLINE_NODE` (0x03). There was no ARC entity and no explicit terminal EOF opcode. | Summary prose introduced ARC and EOF opcode not present in the canonical synthetic source. |
| **3** | **Tier 2 Parser States** | "State transitions: INIT $\rightarrow$ HEADER_PARSED $\rightarrow$ READING_ENTITIES $\rightarrow$ EOF_SEEN" | Frozen spec in `BLIND_BEHAVIORAL_SPEC.md` | `INCORRECT` | Canonical parser states: `STATE_UNINITIALIZED` (0), `STATE_HEADER_PARSED` (1), `STATE_ENTITIES_ACTIVE` (2), `STATE_COMPLETED` (3), `STATE_ERROR` (4). | Prose used informal state labels (`READING_ENTITIES`, `EOF_SEEN`) rather than canonical source names. |
| **4** | **PR 504 State Claim** | "PR #504 state: `d44f6f35b4cebe19e78df796122d2be2f628ff3a`" | GitHub PR #504 API inspection | `STALE` | `SNAPSHOT_AT_TIME_OF_RESEARCH`: PR #504 is OPEN/DRAFT with current head `9b3ced99362586e18989030feb708eff410908bb`. | Research package hardcoded an outdated PR commit as current repo state without snapshot labeling. |
| **5** | **README Basis Identity** | `RESEARCH_PACKAGE_BASIS_HEAD: 4192305...` conflated with commit identity | Git log & commit graph | `STALE` | Separated `RESEARCH_PACKAGE_BASIS_HEAD` (`4192305...`) from `COMMIT_CONTAINING_THIS_REPORT` (`8168cf5...`). | Prevents README from appearing internally contradictory regarding its own containing commit. |
| **6** | **REA-020 Production Readiness** | `CURRENT_DISPOSITION: READY_TO_TRANSFER` | Current main `dxf_builder_lib/builder.py` and `primitive_ir_lib` | `DOWNGRADED` | `CURRENT_DISPOSITION: RESEARCH_PRIOR`. Bulge math is valid external prior, but production generation has no active curved polyline requirement. | `builder.py` emits LINE/CIRCLE/ARC; does not emit LWPOLYLINE. `geometry_extraction.py` has no arc extraction. Over-promoted to READY_TO_TRANSFER without a product RED. |
| **7** | **Bulge Snap Threshold** | "Threshold $|b| < 10^{-7}$ MUST snap to straight line as standard invariant" | Autodesk DXF Spec & ezdxf documentation | `HYPOTHESIS` | `PROJECT_HEURISTIC_UNVALIDATED_FOR_PRODUCTION`. Standard does not specify a normative $10^{-7}$ snap threshold. | Threshold was an empirical guard introduced in our test oracle, not an Autodesk normative contract. |
| **8** | **Autodesk DXF License** | `LICENSE: Public Domain / MIT` | Autodesk copyright notices & DXF Reference | `CORRECTED` | Autodesk DXF Reference is proprietary documentation under copyright of Autodesk, Inc., serving as `SPECIFICATION_PRIOR`. `ezdxf` math is MIT. | Mislabeling third-party specification documentation as public domain is legally incorrect. |
| **9** | **Measured Engineering Hours** | "12–16 engineering hours measured saved; 90% work avoided" | Discovery analysis notes | `HYPOTHESIS` | `HYPOTHESIZED_DISCOVERY_REDUCTION`. No causal empirical baseline was measured for developer time. | Time savings must be stated as hypotheses, not measured empirical metrics. |
| **10** | **Ceiling Capability Scores** | "95%–100% blind reconstruction capability across PE32+ binaries" | Tier 1–3 experimental provenance | `SELF_CONTAMINATED` | `INDEPENDENT_BLIND_CAPABILITY_SCORE = NOT_PROVEN`. Tool operation proven on specific synthetic fixtures only. | Authorship contamination invalidates ceiling accuracy scores. |
