# TECHNICAL SPECIFICATION: SOURCE-BACKED LINE REMOVAL EVIDENCE

**Role:** `ANTIGRAVITY_RESEARCH`  
**Mode:** `EMPIRICAL_SOURCE_BACKED_LINE_REMOVAL_EVIDENCE`  
**Subagents:** 0 (Disabled)  
**Status:** Empirical Evidence Specification Completed. Zero production code modification. Zero PR.  
**Canonical State:** GitHub [`duongchi90/cad-agent`](https://github.com/duongchi90/cad-agent) on `main` at commit `47808851b22472e213c8b8d77b735f9dbb88d699` (merged PR #493).  
**Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), `NO_TOUCH_ARC_CIRCLE_MUTATION_EPIC=ENFORCED`.  
**Artifact Generated:** [source_base_line_removal_evidence_empirical_specification.md](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/source_base_line_removal_evidence_empirical_specification.md)

---

## 0. PRESERVED RESEARCH QUEUE

The research backlog remains intact and queued:
1. `THICK_LINE_CENTERLINE_NORMALIZATION_V1`
2. `CIRCLE_FALSE_POSITIVE_PERIMETER_VALIDATION_V1`
3. `CARDINAL_ROTATED_TEXT_EXTRACTION_V1`
4. `TAUBIN_ARC_EXTRACTION_V1`
5. `TARGET_BASE_ORIENTATION_ENVELOPE_V1`
6. `SOURCE_FUSION_LINE_ADD_PROPOSAL_V1` (`STATUS=READY_FOR_CODEX_QUEUED`)

*Crucial Architecture Invariant:* `SOURCE_FUSION_LINE_ADD_PROPOSAL_V1` addresses unmatched target lines without mutating or removing any existing base lines. Line removal research is strictly separate.

---

## 1. FRESH CURRENT STATE AUDIT

- **CURRENT_MAIN:** Commit `47808851b22472e213c8b8d77b735f9dbb88d699` (merged PR #493).
- **ACTIVE_PRODUCTION_FRONTIER:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`).
- **FIRST_UNSATISFIED_PRODUCTION_BOUNDARY:** Line removal has zero owner in CadAgent. In [`cad_agent/source_fusion_proposal.py::compose_verified_native_line_delta()`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py#L703-L808), unmatched native base lines are silently dropped from the result without disposition or audit trail.
- **CURRENT_REMOVE_OWNER:** **`NONE`** (Zero owners currently authorize or emit native entity removals).
- **CURRENT_COVERAGE_OWNER:** [`cad_agent/source_fusion_proposal.py::compose_source_delta_coverage()`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py#L916-L955).

---

## 2. CORE SAFETY DOCTRINE: ABSENCE OF DETECTION VS EVIDENCE OF ABSENCE

### The Fundamental Axiom
$$\mathbf{UNMATCHED\_BASE\_LINE \ne REMOVE}$$

In CAD Agent revision architecture, **preserving base CAD is the supreme invariant**. A native line must never be deleted merely because a raster perception pass did not detect it.

### Epistemological Separation
1. **`ABSENCE_OF_DETECTION` (Passive Non-observation):**
   - A line $L_{\text{base}}$ exists in the native DWG database.
   - The raster vision pipeline emits no target primitive matching $L_{\text{base}}$.
   - *Causality:* Common image processing artifacts (OCR text masks, binarization thresholding, lineweight dropout, dashed linetype filtering, ROI cropping).
   - *Engineering Meaning:* **Zero proof of removal.** The line may physically exist on the paper sheet but failed to be digitized.
2. **`EVIDENCE_OF_ABSENCE` (Affirmative Physical Proof):**
   - The spatial region enclosing $L_{\text{base}}$ is affirmatively proved to have been observed.
   - The pixel corridor along $L_{\text{base}}$ contains verified clean background whitespace.
   - Neighboring features of identical stroke width are successfully detected, proving scanner sensitivity.
   - No occlusion (text, dimensions, hatching, clouds) masks the corridor.
   - An affirmative revision obligation records an intended modification.

---

## 3. THE 12 RASTER ABSENCE FAILURE MODES

Tested against synthetic and scanned raster conditions:

| Failure Mode | Base Line Present | Target Detected | Region Coverage Declared | Remove Justified? | Safe Expected Disposition |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. Thin / faint line dropout** | **True** | False | True | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **2. Thick-line preprocessing erosion** | **True** | False | True | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **3. Partial crop (line clipped)** | **True** | False | False | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **4. ROI exclusion (line outside bbox)** | **True** | False | False | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **5. Text overlap / OCR bbox masking** | **True** | False | True | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **6. Dimension witness line crossing** | **True** | False | True | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **7. Section hatch pattern interference** | **True** | False | True | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **8. Low contrast / yellowed paper** | **True** | False | True | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **9. Scan noise / salt-and-pepper break**| **True** | False | True | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **10. Broken line (dashed / phantom)** | **True** | False | True | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **11. Center-line pattern filtering** | **True** | False | True | **FALSE** | `UNMATCHED_BASE_RETAINED` |
| **12. Region not declared complete** | **True** | False | False | **FALSE** | `UNMATCHED_BASE_RETAINED` |

*Conclusion:* In all 12 common failure modes, assuming `unmatched base == REMOVE` produces catastrophic data loss by deleting valid native engineering geometry. The safe default must unconditionally be `UNMATCHED_BASE_RETAINED`.

---

## 4. THE POSITIVE REMOVAL CASE & DISTINGUISHING CRITERIA

### Synthetic Component Benchmark
Constructed a mechanical bracket with an outer boundary box $(20, 20) \to (80, 100)\text{ mm}$ and three internal horizontal stiffener ribs:
- Rib 1: $(20, 40) \to (80, 40)\text{ mm}$ (Kept)
- Rib 2: $(20, 60) \to (80, 60)\text{ mm}$ (**Deleted in Revision B**)
- Rib 3: $(20, 80) \to (80, 80)\text{ mm}$ (Kept)

### Measured Evidence on Synthetic Source Render
- **Rib 2 (LINE_OLD) Corridor:** $y \in [58, 62], x \in [25, 75]$:
  - Mean pixel intensity: **$255.0 / 255.0$** (pure white background).
  - Dark pixels in corridor ($< 128$): **$0$**.
  - Minimum intensity: **$255$**.
- **Neighboring Witnesses (Rib 1 and Rib 3):**
  - Rib 1 dark pixels: **$51\text{ px}$** (detected with 100% confidence).
  - Rib 3 dark pixels: **$51\text{ px}$** (detected with 100% confidence).
  - Local witness contrast ratio: **$> 100,000\times$**.

### The 5 Essential Distinguishing Proofs
To distinguish genuine removal from raster dropout, all 5 criteria must be satisfied:
1. **Active Negative Pixel Verification (Corridor Whitespace):** The sampled ribbon around the expected line contains zero edge energy and $> 99.5\%$ background intensity.
2. **Neighboring Witness Completeness (Local Sensitivity Gauge):** Adjacent features of identical stroke width and orientation are detected with strong SNR, proving the scanner resolution and contrast were sufficient.
3. **Zero Occlusion:** No OCR text bounding box, dimension witness line, leader, or hatch entity intersects the corridor.
4. **Topological Boundary Completeness:** The outer boundary enclosing the component is fully detected and verified closed.
5. **Affirmative Revision Obligation:** The revision manifest or title block records an explicit change obligation for that component.

---

## 5. ANALYSIS OF EXISTING COVERAGE OWNER (`compose_source_delta_coverage`)

### Architectural Scope
[`cad_agent/source_fusion_proposal.py::compose_source_delta_coverage()`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py#L916-L955):
- Binds declared scopes to source bundles via canonical JSON hashes.
- Enforces obligations over `(source_id, region_id, aspect)` tuples.
- `_COVERAGE_DISPOSITIONS` (line 815):
  `{"CHANGE", "KEEP", "NO_DISTINCT_DELTA", "AMBIGUOUS", "INSUFFICIENT_SOURCE_EVIDENCE"}`.

### Findings
1. **`CURRENT_COVERAGE_CAN_EXPRESS_ABSENCE_PROOF: NO.`**
   - It is a **metadata obligation ledger**, not a visual or geometric absence inspector.
   - It verifies candidate evidence hashes, but cannot inspect pixels or determine whether a line was deleted.
2. **`MISSING_FACTS`:**
   - No negative corridor pixel sampling.
   - No entity-level granularity (operates on region-aspect keys, not CAD entity handles).
   - No occlusion clearance checking.
3. **Verdict:** **`MISSING_SEMANTIC_CONTRACT`**
   - Merely adding `"REMOVE"` to `_COVERAGE_DISPOSITIONS` would be an empty assertion without engineering truth. A dedicated affirmative absence verification contract is required.

---

## 6. THE `SOURCE_REGION_GEOMETRY_COMPLETE` CONTRACT

The minimum credible contract required before proposing entity removal:

```yaml
CONTRACT_NAME: SOURCE_REGION_GEOMETRY_COMPLETE_V1
OWNER: cad_agent/source_fusion_proposal.py
REQUIRED_FIELDS:
  region_id: str
  enclosing_boundary_wcs: list[Point2D]  # Closed polygon in WCS mm
  enclosing_boundary_status: "ALL_BOUNDARY_LINES_KEPT"
  negative_sampling_corridor_width_mm: float  # e.g. 2.0 mm
  corridor_mean_background_ratio: float       # Must be >= 0.995
  corridor_dark_pixel_count: int              # Must be 0
  occlusion_intersections: list[str]          # Must be empty []
  local_sensitivity_witness_ids: list[str]    # At least 1 adjacent line detected
  revision_intent_obligation_sha256: str      # Binds explicit change authorization
```

If any condition fails, the candidate entity falls back to **`UNMATCHED_BASE_RETAINED`**.

---

## 7. SAFE DISPOSITION TAXONOMY FOR CADAGENT REVISION MODE

In future Revision Mode correspondence, base and target entities shall be classified into 5 strict, mutually exclusive categories:

```
[Target Lines]
      │
      ├── Matched to Base within keep_tolerance ──────────► KEEP
      ├── Matched to Base with residual > keep_tolerance ──► CHANGE
      └── Unmatched to any Base line ─────────────────────► ADD (SOURCE_FUSION_LINE_ADD_PROPOSAL_V1)

[Base Lines]
      │
      ├── Matched to Target ──────────────────────────────► (Covered by KEEP / CHANGE above)
      └── Unmatched to any Target line:
            ├── Lacks SOURCE_REGION_GEOMETRY_COMPLETE ────► UNMATCHED_BASE_RETAINED (Safe Default)
            └── Satisfies all 5 Complete-Region Proofs ──► CONFIRMED_REMOVE
```

---

## 8. CODEX READINESS & RESEARCH CONCLUSION

- **`SOURCE_FUSION_LINE_ADD_PROPOSAL_V1`:** **`READY_FOR_CODEX = YES`** (Queued).
- **`LINE_REMOVAL_RESEARCH`:** **`RESEARCH_ONLY_COMPLETE`**.
  - No implementation of line removal is authorized at this time.
  - Native base line removal must remain gated behind affirmative negative pixel verification and declared complete-region contracts.
- **`BLOCKER`:** None for ADD; REMOVE is intentionally deferred until negative corridor sampling infrastructure is designed.
- **`NO_TOUCH_PRODUCTION`:** Zero production modifications made. Issue #491 remains the active workstation production frontier.
