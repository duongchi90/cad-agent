# INVALIDATED_OR_UNPROVEN_CLAIMS: Formally Retracted Research Claims

- **Document ID:** `REA_INVALIDATED_OR_UNPROVEN_CLAIMS_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`

---

## 1. Inventory of Retracted & Unproven Claims

### 1. General Population Capability Scores (Retracted: `SELF_CONTAMINATED`)
- **Old Claim:** "REA + Ghidra achieves 95%–100% accuracy in blind binary reconstruction and 100% in differential analysis across Windows PE32+ binaries."
- **Ground Truth:** The Tier 1, Tier 2, and Tier 3 benchmark fixtures were authored, compiled, and evaluated within the same agent session.
- **Classification:** `SELF_CONTAMINATED_NOT_VALID_FOR_BLIND_ACCURACY`. Population-level accuracy percentages cannot be inferred from self-authored fixtures.

### 2. Tier 1 Mechanism Inventory (Retracted: `INCORRECT`)
- **Old Claim:** "Recovered 3-point circle fitting algorithm from Tier 1 binary."
- **Ground Truth:** The compiled source of `cadgeom_core.exe` contained distance, affine transformations, bounding box expansion, vector cross product, perpendicular point-line distance, Shoelace polygon area, Point-in-Polygon ray-casting, Douglas-Peucker simplification, and convex hull monotone chain. It did **not** include 3-point circle fitting.
- **Classification:** `INCORRECT`. The claim arose from planning notes and is refuted by the compiled binary and source ground truth.

### 3. Tier 2 Spec Vocabulary (Retracted: `INCORRECT`)
- **Old Claim:** "Recovered ARC entity opcode, EOF opcode, and EOF_SEEN parser state."
- **Ground Truth:** The compiled binary of `cadstream_format.exe` only defined `ENTITY_LINE` (0x01), `ENTITY_CIRCLE` (0x02), and `ENTITY_POLYLINE_NODE` (0x03). The parser state machine ended in `STATE_COMPLETED` (0x03) when byte count reached stream length, with no explicit EOF opcode.
- **Classification:** `INCORRECT`. The claim introduced vocabulary not present in the binary.

### 4. Quantified Engineering Hour Savings (Retracted: `HYPOTHESIS_ONLY`)
- **Old Claim:** "12–16 engineering hours measured saved for Luna; 90% work avoided; remaining implementation under 1 hour."
- **Ground Truth:** No baseline developer time study was conducted. These numbers were speculative estimations.
- **Classification:** `HYPOTHESIS`. All such claims are re-categorized as `HYPOTHESIZED_DISCOVERY_REDUCTION`.

### 5. Normative Bulge Singularity Snap (Retracted: `HYPOTHESIS_ONLY`)
- **Old Claim:** "Autodesk/ezdxf contract mandates that $|b| < 10^{-7}$ MUST snap to $b = 0.0$ to prevent radius overflow."
- **Ground Truth:** The Autodesk DXF specification defines $b = \tan(\theta/4)$ mathematically. It does not dictate a normative $10^{-7}$ cutoff threshold. The cutoff was introduced as an ad-hoc safety guard in our test oracle.
- **Classification:** `PROJECT_HEURISTIC_UNVALIDATED_FOR_PRODUCTION`.

### 6. Legal Domain of Specification Prior (Retracted: `INCORRECT`)
- **Old Claim:** "Autodesk DXF Specification license: Public Domain."
- **Ground Truth:** Autodesk DXF documentation is copyrighted by Autodesk, Inc. It serves as public documentation / specification prior, but is not public domain.
- **Classification:** `INCORRECT`.
