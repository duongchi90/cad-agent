# TECHNICAL SPECIFICATION: SOURCE-BASE LINE CORRESPONDENCE GAP

**Role:** `ANTIGRAVITY_RESEARCH`  
**Mode:** `EMPIRICAL_SOURCE_BASE_LINE_CORRESPONDENCE_GAP`  
**Subagents:** 0 (Disabled)  
**Status:** Empirical Gap Identification Completed. Zero production code modification. Zero PR.  
**Canonical State:** GitHub [`duongchi90/cad-agent`](https://github.com/duongchi90/cad-agent) on `main` at commit `47808851b22472e213c8b8d77b735f9dbb88d699` (merged PR #493).  
**Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), `NO_TOUCH_ARC_CIRCLE_MUTATION_EPIC=ENFORCED`.  
**Artifact Generated:** [source_base_line_correspondence_gap_empirical_specification.md](file:///C:/Users/duong/.gemini/antigravity/brain/9a64b865-2b13-4f89-ab1e-b0cb2caca8c5/source_base_line_correspondence_gap_empirical_specification.md)

---

## 0. PRESERVE PRIOR RESEARCH QUEUE

The research backlog remains intact and queued:
1. `THICK_LINE_CENTERLINE_NORMALIZATION_V1`
2. `CIRCLE_FALSE_POSITIVE_PERIMETER_VALIDATION_V1`
3. `CARDINAL_ROTATED_TEXT_EXTRACTION_V1`
4. `TAUBIN_ARC_EXTRACTION_V1`
5. `TARGET_BASE_ORIENTATION_ENVELOPE_V1`

---

## 1. FRESH CURRENT STATE AUDIT

- **CURRENT_MAIN:** `47808851b22472e213c8b8d77b735f9dbb88d699` (PR #493).
- **ACTIVE_PRODUCTION_FRONTIER:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`).
- **FIRST_UNSATISFIED_PRODUCTION_BOUNDARY:** Unmatched verified target lines abort the entire correspondence pipeline with `NO_SUPPORTED_DELTA`, completely blocking addition of new geometry in Revision Mode.
- **CURRENT_CORRESPONDENCE_OWNER:** [`cad_agent/source_fusion_proposal.py::compose_verified_native_line_delta()`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py#L703-L808).
- **SUPPORTED_ENTITY_TYPES:** **`LINE` only.**

---

## 2. CURRENT LINE CONTRACT DOCUMENTATION

Tracing [`compose_verified_native_line_delta()`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py#L703-L808):

| Operational Scenario | Internal Condition | Returned `correspondence_status` | Output in `base_target_correspondence` | Output in `bounded_native_line_deltas` |
| :--- | :--- | :---: | :---: | :---: |
| **KEEP** | $\text{residual} \le \text{keep\_limit}$ | `"UNIQUE"` | `[{"disposition": "KEEP", ...}]` | `[]` (omitted from deltas) |
| **CHANGE** | $\text{keep\_limit} < \text{residual} \le \text{max\_residual}$ | `"UNIQUE"` | `[{"disposition": "CHANGE", ...}]` | `[{"before": base, "after": target}]` |
| **Unmatched Target** | $\text{best\_residual} > \text{max\_residual}$ for any target | `"NO_SUPPORTED_DELTA"` | `[]` (**Aborts entire proposal**) | `[]` (**Zero deltas emitted**) |
| **Unmatched Base** | Base line not selected as best candidate by any target | `"UNIQUE"` (if all targets matched) | Completely omitted (silent) | Completely omitted |
| **Equal-Cost Tie** | Target has 2 base lines with equal residual (within 4 ulps) | `"AMBIGUOUS"` | `[]` (Fails closed) | `[]` |
| **Target Collision** | Target 2 selects `best_base` already used by Target 1 | `"AMBIGUOUS"` | `[]` (Fails closed) | `[]` |
| **Reversed Endpoints** | Endpoints ordered oppositely ($p_1 \leftrightarrow q_2, p_2 \leftrightarrow q_1$) | `"UNIQUE"` | Handled seamlessly ($\min(\text{direct}, \text{reverse})$) | Endpoints normalized to base direction |
| **Out-of-Tolerance** | Distance between best candidate endpoints $> \text{max\_residual}$ | `"NO_SUPPORTED_DELTA"` | `[]` | `[]` |

---

## 3. CAUSAL MATRIX EXPERIMENTS (MEASURED ON CURRENT MAIN)

Executed using exact calibrated-mm fixtures ($s = 1.0000$, $\text{max\_residual} = 10.0\text{ mm}$, $\text{keep\_limit} = 0.01\text{ mm}$):

| Case | Fixture Definition | Current Status | Current Correspondence | Current Deltas | Product Expected Disposition | Identified Gap |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **CASE A** | Base $(10, 50)\to(30, 50)$<br>Target $(10, 50)\to(30, 50)$ | `UNIQUE` | 1 item (`KEEP`) | 0 | `KEEP` | None. Passes. |
| **CASE B** | Base $(10, 50)\to(30, 50)$<br>Target $(10, 50)\to(34, 50)$ | `UNIQUE` | 1 item (`CHANGE`) | 1 delta | `CHANGE` | None. Passes. |
| **CASE C** | Base: Line A<br>Target: Line A + Line New | **`NO_SUPPORTED_DELTA`** | **0 items** | **0 deltas** | Line A: `KEEP`<br>Line New: **`ADD`** | **CRITICAL GAP:** Unmatched target line aborts entire run. No support for `ADD`. |
| **CASE D** | Base: Line A + Line Old<br>Target: Line A | `UNIQUE` | 1 item (`base-a` `KEEP`) | 0 deltas | Line A: `KEEP`<br>Line Old: `REMOVE` or `UNMATCHED_BASE` | `base-old` is silently dropped without tracking. |
| **CASE E** | Base: Line A<br>Target: Changed A + Line New | **`NO_SUPPORTED_DELTA`** | **0 items** | **0 deltas** | Line A: `CHANGE`<br>Line New: **`ADD`** | **CRITICAL GAP:** New target line destroys legitimate `CHANGE` delta. |
| **CASE F** | Base: Line A + Line Old<br>Target: Changed A | `UNIQUE` | 1 item (`base-a` `CHANGE`) | 1 delta | Line A: `CHANGE`<br>Line Old: `REMOVE` / Unmatched | `base-old` silently dropped. |
| **CASE G** | Base: Line A<br>Target: Line B (far apart) | `NO_SUPPORTED_DELTA` | 0 items | 0 deltas | Line A: `REMOVE`<br>Line B: `ADD` | Aborts completely. |
| **CASE H** | Reversed endpoints | `UNIQUE` | 1 item (`KEEP`) | 0 deltas | `KEEP` | None. Passes (direct/reverse min). |
| **CASE I** | Two identical base lines | `AMBIGUOUS` | 0 items | 0 deltas | `AMBIGUOUS` | None. Correct fail-closed guard. |
| **CASE J** | Two identical target lines | `AMBIGUOUS` | 0 items | 0 deltas | `AMBIGUOUS` | None. Correct fail-closed guard. |
| **CASE K** | Equidistant target between 2 base | `AMBIGUOUS` | 0 items | 0 deltas | `AMBIGUOUS` | None. Correct fail-closed guard. |
| **CASE L** | Crossing lines ($> \text{max\_residual}$) | `NO_SUPPORTED_DELTA` | 0 items | 0 deltas | Unmatched / Independent | None. Correct tolerance rejection. |

---

## 4. CRITICAL SAFETY ASYMMETRY: SEPARATING ADD FROM REMOVE

### Why `ADD` and `REMOVE` are Fundamentally Asymmetric
1. **The Nature of `ADD` (Source Present, Base Absent):**
   - The line exists on the modified raster/source drawing.
   - It has been binarized, vector-extracted, passed source-support verification (`verify_external_visual_proposal_source_support`), calibrated to physical mm, and aligned into WCS.
   - Proposing `ADD` merely proposes inserting an additional line into the disposable candidate DWG.
   - **Base CAD Safety:** Zero risk to existing base entities. All native base lines remain completely untouched and preserved.
2. **The Danger of `REMOVE` (Base Present, Source Absent):**
   - In real-world scanned raster engineering drawings, a native CAD line may fail to be observed due to:
     - OCR text label masking or dimension callout crossing.
     - Lineweight binarization dropout or scanner illumination falloff.
     - Cropped Region of Interest (ROI) boundaries.
     - Centerline / hidden dashed line filtering.
     - Dense hatching patterns obscuring underlying boundary lines.
   - **Base CAD Danger:** If CadAgent assumes `unmatched base == REMOVE`, it will **silently delete valid native engineering CAD geometry** whenever a scanner experiences a dropout or an OCR box clips an entity!
   - In CadAgent doctrine, **PRESERVING UNCHANGED BASE CAD** is the supreme invariant. Deleting a native line without affirmative proof of removal is an unacceptable data-loss event.
3. **Evidence Requirements:**
   - **`ADD_EVIDENCE_REQUIREMENTS`:** Verified source render support (`SOURCE_SUPPORT_VERIFIED`), valid calibration, non-collinear WCS alignment, and absence of base lines within tolerance. (Ready today).
   - **`REMOVE_EVIDENCE_REQUIREMENTS`:** Full declared ROI coverage scope, multi-pass cross-validation, explicit source-delta coverage obligation proof (`SOURCE_DELTA_COVERAGE_V1`), and affirmative deletion evidence (e.g. revision cloud enclosing deleted region).
   - **`WHICH_IS_SAFER_FIRST`:** **`ADD` is vastly safer and must be implemented first.**

---

## 5. SOURCE-BOUND ADD CONTRACT

- **ADD_OWNER_GAP:** Current [`source_fusion_proposal.py:763`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py#L763) hardcodes `if best_residual > max_residual: return _proposal_without_match("NO_SUPPORTED_DELTA", ...)`. It lacks an unmatched target collection branch.
- **ADD_REQUIRED_FIELDS:**
  1. `target_primitive_id`: str (opaque identifier from verified target document)
  2. `base_observation_id`: `None`
  3. `disposition`: `"ADD"`
  4. `residual`: `None`
  5. `before`: `None`
  6. `after`: `{"start": [x, y], "end": [x, y]}` (aligned WCS mm)
- **ADD_FAIL_CLOSED_CASES:**
  - Ambiguous near-match: If a base line exists near `max_residual` with a tie or collision, it must fail closed as `AMBIGUOUS`, not `ADD`.
  - Duplicate target lines: If two target lines claim the same coordinates, fail closed as `AMBIGUOUS`.
  - Unverified source evidence: If target line lacks source support, rejected before correspondence.

---

## 6. REMOVE CONTRACT & COVERAGE INVESTIGATION

- **EXISTING_COVERAGE_OWNER:** [`cad_agent/source_fusion_proposal.py::compose_source_delta_coverage()`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py#L916-L955).
- **CAN_IT_SUPPORT_REMOVE_PROOF:** **NO.**
  - `_COVERAGE_DISPOSITIONS` in line 815 is strictly:
    `{"CHANGE", "KEEP", "NO_DISTINCT_DELTA", "AMBIGUOUS", "INSUFFICIENT_SOURCE_EVIDENCE"}`.
  - It does NOT include `"REMOVE"`.
- **REMOVE_OWNER_GAP:** Absence from a single raster extraction is legally categorized as `"INSUFFICIENT_SOURCE_EVIDENCE"`, never proof of removal.
- **REMOVE_UNRESOLVED_RISKS:** High risk of deleting native CAD lines due to OCR masking, lineweight dropout, or ROI cropping. Proposing `REMOVE` must be deferred until explicit revision clouds or affirmative multi-source coverage proofs exist.

---

## 7. GLOBAL ASSIGNMENT VS GREEDY MATCHING BENCHMARK

- **Experimental Finding:** When two target lines ($T_1, T_2$) both have the same base line ($B_1$) as their nearest neighbor, current greedy matching rejects the second target via `if base_id in used_base_ids:` and returns:
  `correspondence_status = "AMBIGUOUS"`!
- **Greedy vs Global Comparison:**
  - Even if a globally optimal 1-to-1 matching exists ($T_1 \to B_2, T_2 \to B_1$), the greedy code fails closed as `AMBIGUOUS`.
  - Order dependency exists: processing order can determine whether a collision occurs.
- **Reachability Verdict:** Failing closed as `AMBIGUOUS` is completely safe (no false-positive matches). In engineering CAD, two lines competing for the same base within tolerance are genuine geometric ties. Implementing a complex Hungarian assignment algorithm is **unnecessary for Phase 1**; the greedy fail-closed behavior is safe.

---

## 8. AMBIGUITY CONTROLS (FAIL-CLOSED INTEGRITY)

The existing fail-closed guards in `compose_verified_native_line_delta()` must be preserved:
1. `_same_residual(best_residual, costs[1][0])`: Blocks geometric ties (Cases I, K).
2. `base_id in used_base_ids`: Blocks duplicate targets claiming one base line (Case J).
3. `best_residual > max_residual`: When competing candidates are out-of-tolerance, prevents wild snapping.

---

## 9. BEYOND LINE — INVENTORY AUDIT

| Entity Type | Schema Exists | Verified Source Owner Exists | Base Native Observation Owner Exists | Correspondence Owner Exists | Native Mutation Allowed |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **LINE** | **YES** (`LineGeometry`) | **YES** (`source_verified_geometry.py`) | **YES** (`_native_lines`) | **YES** (`compose_verified_native_line_delta`) | **YES** (Proposal only) |
| **CIRCLE** | **YES** (`CircleGeometry`) | **NO** (Not admitted) | **NO** | **NO** | **NO** (`NO_TOUCH_ARC_CIRCLE`) |
| **ARC** | **YES** (`ArcGeometry`) | **NO** (Not admitted) | **NO** | **NO** | **NO** (`NO_TOUCH_ARC_CIRCLE`) |
| **TEXT** | **YES** (`TextGeometry`) | **NO** (Not in visual adapter) | **NO** | **NO** | **NO** |

*Verdict:* LINE is the sole entity type with complete upstream schema, verified admission, and native observation bindings. All other entity types remain strictly inventory-only.

---

## 10. SELECTED FUTURE EPIC

$$\mathbf{EPIC\_SELECTION: \ SOURCE\_FUSION\_LINE\_ADD\_PROPOSAL\_V1}$$

- **Justification:**
  - **Smallest Owner:** Exactly one file: `cad_agent/source_fusion_proposal.py`.
  - **Zero Breaking Changes:** Preserves all existing `KEEP` and `CHANGE` behaviors.
  - **High Product Value:** Unblocks Revision Mode when a designer adds new lines to a drawing (currently 100% blocked by `NO_SUPPORTED_DELTA`).
  - **Safety:** Proposal-only; zero native CAD mutations; zero risk of base entity deletion.

---

## 11. PUBLIC-PATH CAUSAL RED TEST

Executed on the real public entry point [`compose_verified_native_line_delta()`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py#L703-L808):
- **Base Drawing:** 1 line `base-a`: $(10.0, 50.0) \to (30.0, 50.0)\text{ mm}$.
- **Target Drawing:**
  1. `target-kept`: $(10.0, 50.0) \to (30.0, 50.0)\text{ mm}$ (matches `base-a`).
  2. `target-new`: $(10.0, 30.0) \to (30.0, 30.0)\text{ mm}$ (new revision line, 20mm away).
- **Execution on Current Unmodified Main:**
  ```python
  result = compose_verified_native_line_delta(base_lines=base, verified_target_document=target["document"], ...)
  assert result["correspondence_status"] == "NO_SUPPORTED_DELTA"
  assert result["base_target_correspondence"] == []
  assert result["bounded_native_line_deltas"] == []
  ```
- **Observed Result:** **FAILED TO PROPOSE ADD.** Emits `NO_SUPPORTED_DELTA` and wipes out `target-kept`.

---

## 12. DETERMINISTIC GREEN ORACLE

Future output schema under `SOURCE_FUSION_LINE_ADD_PROPOSAL_V1`:
```python
{
    "status": "PROPOSAL_ONLY",
    "correspondence_status": "UNIQUE_WITH_ADD",
    "base_target_correspondence": [
        {
            "base_observation_id": "base-a",
            "target_primitive_id": "target-kept",
            "disposition": "KEEP",
            "residual": 0.0,
        },
        {
            "base_observation_id": None,
            "target_primitive_id": "target-new",
            "disposition": "ADD",
            "residual": None,
        },
    ],
    "geometry_tolerance": {"unit": "mm", "max_correspondence_residual": 10.0, "keep_tolerance": 0.01},
    "target_to_base_alignment": {...},
    "bounded_native_line_deltas": [
        {
            "base_observation_id": None,
            "target_primitive_id": "target-new",
            "before": None,
            "after": {"start": [10.0, 30.0], "end": [30.0, 30.0]},
        }
    ],
    "semantic_label_authority": "NONE",
    "cad_mutation": False,
}
```

---

## 13. MINIMUM WRITESET REASSESSMENT

- **`PRIMARY_OWNER`:** [`cad_agent/source_fusion_proposal.py`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py)
  - Accumulate unmatched targets instead of immediate abort in `compose_verified_native_line_delta()`.
  - Emit `disposition = "ADD"` in `base_target_correspondence` and delta in `bounded_native_line_deltas`.
  - Set status to `"UNIQUE_WITH_ADD"`.
- **`SECONDARY_OWNER`:** **`NONE`**
- **`TEST_OWNER`:** [`tests/test_external_visual_primitive_ir_admission.py`](file:///C:/Users/duong/ZCodeProject/cad-agent/tests/test_external_visual_primitive_ir_admission.py)
- **`MINIMUM_WRITESET`:** $\approx +22$ lines in `source_fusion_proposal.py`, $+45$ lines in tests.

---

## 14. CURRENT PRODUCTION BLOCKER & GOVERNANCE

- **Issue #491 Status:** OPEN (`NEXT_OWNER=SOLO_CODEX`).
- Workstation native persistence and review lanes remain strictly gated by the licensed AutoCAD Mechanical session requirement.
- Zero production mutation is authorized by this research. Research proceeds in independent offline proposal lanes.

---

## 15. READY FOR CODEX ASSESSMENT

$$\mathbf{READY\_FOR\_CODEX = YES}$$

- All 9 prerequisites satisfied:
  1. Actual current correspondence behavior measured across Cases A–L.
  2. One real gap selected: `SOURCE_FUSION_LINE_ADD_PROPOSAL_V1`.
  3. Public causal RED reproduced on current main.
  4. Deterministic proposal-only GREEN oracle specified.
  5. Ambiguity guards remain fail-closed.
  6. ADD/REMOVE safety asymmetry strictly respected.
  7. Single existing owner reused (`cad_agent/source_fusion_proposal.py`).
  8. Zero native CAD mutation required (`cad_mutation: False`).
  9. Zero conflict with active production governance (Issue #491).
- **REA_NEEDED_NOW:** **`NO`** (Pure Python mathematical correspondence in existing owner).
- **BLOCKER:** **`NONE`** (Self-contained in existing offline unit tests).
