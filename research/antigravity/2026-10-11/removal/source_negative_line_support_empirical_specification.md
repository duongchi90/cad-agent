# TECHNICAL SPECIFICATION: SOURCE NEGATIVE LINE SUPPORT EVIDENCE (CONTRACT CLOSURE)

**Role:** `ANTIGRAVITY_RESEARCH`  
**Mode:** `NEGATIVE_SOURCE_SUPPORT_CONTRACT_CLOSURE_AND_PERSISTENCE`  
**Subagents:** 0 (Disabled)  
**Status:** Contract Closed & Empirically Verified. Research Only. Zero production code modification. Zero PR.  
**Canonical State:** GitHub [`duongchi90/cad-agent`](https://github.com/duongchi90/cad-agent) on `main` at commit `47808851b22472e213c8b8d77b735f9dbb88d699` (merged PR #493).  
**Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), PR #494 (`fix/start-tab-drawing-open-fallback`, DRAFT).  

---

## 0. PRESERVED RESEARCH QUEUE

The research backlog remains intact and queued:
1. `THICK_LINE_CENTERLINE_NORMALIZATION_V1`
2. `CIRCLE_FALSE_POSITIVE_PERIMETER_VALIDATION_V1`
3. `CARDINAL_ROTATED_TEXT_EXTRACTION_V1`
4. `TAUBIN_ARC_EXTRACTION_V1`
5. `TARGET_BASE_ORIENTATION_ENVELOPE_V1`
6. `SOURCE_FUSION_LINE_ADD_PROPOSAL_V1` (`STATUS=READY_FOR_CODEX_QUEUED`)
7. `SOURCE_FUSION_LINE_REMOVE_PROPOSAL_V1` (`STATUS=BLOCKED` — native entity deletion remains blocked behind semantic change authorization)

---

## 1. PRESERVED CORE FINDINGS

- **`UNMATCHED_BASE_LINE != REMOVE`**: An unmatched native entity in base DWG indicates only that no target observation corresponded to it. It does not prove the entity was deleted from the modified source.
- **`NOT_POSITIVELY_SUPPORTED != NEGATIVELY_PROVEN_ABSENT`**: Inverting the positive support verifier causes catastrophic false deletions on faint lines (Control A), dashed lines (Control E), and shifted lines (Control G). Absence requires positive observational proof of whitespace.
- **`LINE ADD IS INDEPENDENT FROM REMOVE`**: `SOURCE_FUSION_LINE_ADD_PROPOSAL_V1` is queued and independent.
- **`NATIVE DELETION REMAINS BLOCKED`**: Observational raster absence evidence does not authorize CAD mutation.

---

## 2. PIXEL-DOMAIN OWNER BOUNDARY

[`cad_agent/source_support_verifier.py`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_support_verifier.py) remains **strictly pixel-domain only**.

### Forbidden Capabilities
`source_support_verifier.py` must **NOT** own:
- Native CAD WCS coordinates or unit conversions (`mm`, `inch`)
- Native entity identity (`entity_handle`, `layer`, `color`)
- Target/base correspondence matching or residuals
- Engineering `REMOVE` classification or CAD mutations
- AutoCAD COM/FileIPC/session interactions
- Source-fusion planning or proposal compilation

### Candidate Capability Interface
The proposed raster absence verifier consumes pre-projected raster pixel geometry:
```python
def verify_projected_line_source_absence(
    *,
    source_render_bytes: bytes,
    expected_render_sha256: str,
    roi_bbox_px: list[int],
    start_px: list[int],
    end_px: list[int],
    darkness_threshold: int = 220,
    max_ink_fraction: float = 0.02,
    min_mean_intensity: float = 245.0,
    dilation_tolerance_px: int = 2,
    max_dilated_ink_fraction: float = 0.05,
) -> dict[str, object]:
    ...
```
Output contract:
```python
{
    "kind": "DETERMINISTIC_SOURCE_ABSENCE_RESULT",
    "status": "VERIFIED" | "INSUFFICIENT",
    "reason": str,
    "metrics": {
        "sample_count": int,
        "corridor_mean_intensity": float,
        "corridor_ink_fraction": float,
        "dilated_ink_fraction": float,
    },
    "parameters": {
        "darkness_threshold": int,
        "max_ink_fraction": float,
        "min_mean_intensity": float,
        "dilation_tolerance_px": int,
        "max_dilated_ink_fraction": float,
    },
    "semantic_label_authority": "NONE",
    "cad_mutation": False,
}
```

---

## 3. PROJECTION OWNER EVALUATION

To map an unmatched base DWG LINE into source pixels:
$$\text{Base WCS (mm)} \xrightarrow{\text{Inv Alignment}} \text{Target Frame (mm)} \xrightarrow{\text{Inv Calibration}} \text{Source Pixels (px)}$$

### Architectural Comparison
- **Option A (Bounded local helper in `cad_agent/source_fusion_proposal.py`):**
  - Implements `_project_base_line_to_source_pixels(base_line, inverse_matrix, calibration)`.
  - Zero external changes. Keeps `Calibration` dataclass immutable.
  - Couples both steps where `alignment_matrix` and `calibration` are already in scope.
- **Option B (Reusable helper in `primitive_ir_lib/geometry_alignment.py`):**
  - Requires passing `Calibration` into `geometry_alignment.py`, introducing cyclic or cross-tier coupling.
- **Option C (`Calibration.cad_to_pixel()` in `primitive_ir_lib/models.py`):**
  - Widens shared model dataclass for exactly 1 caller.
  - Solves only Step 2 (Target mm $\to$ px), leaving Step 1 (WCS $\to$ Target mm) in `source_fusion_proposal.py`.

### Selected Projection Owner
- **`PROJECTION_PRIMARY_OWNER`**: [`cad_agent/source_fusion_proposal.py`](file:///C:/Users/duong/ZCodeProject/cad-agent/cad_agent/source_fusion_proposal.py) (bounded private helper `_project_base_line_to_source_pixels`).
- **`PROJECTION_SECONDARY_OWNER`**: `NONE`
- **`CALIBRATION_API_CHANGE_REQUIRED`**: `NO`
- **`RATIONALE`**: Measured codebase reuse for `cad_to_pixel` across all production files is exactly 0. Adding `cad_to_pixel` to `Calibration` violates YAGNI, expands a shared schema across tiers, and still requires `source_fusion_proposal.py` to own the inverse rigid alignment transform. A 12-line private helper in `source_fusion_proposal.py` achieves end-to-end projection with zero cross-module coupling.

---

## 4. BEHAVIORAL CAUSAL RED REPLACEMENT

The previous symbol-existence check (`AttributeError`) is replaced with an empirical behavioral failure demonstration:

* **Fixture:** Genuine empty white corridor $(20, 50) \to (80, 50)\text{ px}$, valid ROI $[10, 10, 90, 90]$, exact SHA-256 bound render bytes.
* **Current Main Public Behavior:**
  Calling `verify_external_visual_proposal_source_support(...)` crashes with:
  ```python
  ValueError("PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:line_empty_corridor")
  ```
* **Causal Failure:** Current main has no public observational return value for confirmed whitespace. If a caller naively traps `ValueError` and treats it as absence:
  * Evaluating Control A (faint line at intensity 230) produces the exact same error:
    ```python
    ValueError("PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:line_faint_present")
    ```
  * Both empty corridors and faint present lines are indistinguishable under current main, leading to catastrophic false deletion.
* **Verified Script:** [`test_causal_red_negative_support.py`](test_causal_red_negative_support.py).

---

## 5. REQUIRED NEGATIVE CONTROLS (EMPIRICAL MATRIX)

Measured on paired fixtures with base line $(20, 50) \to (80, 50)\text{ px}$ (length $60\text{ px}$, $61\text{ samples}$):

| Scenario | Mean Intensity | Ink Fraction ($\le 220$) | Dilated Ink ($r=2\text{px}$) | Status | Triggered Safety Mechanism |
|---|:---:|:---:|:---:|:---:|---|
| **Case 0: Genuine Deletion** | **255.0** | **0.0000** | **0.0000** | **`VERIFIED`** | All thresholds satisfied (`OBSERVATIONAL_WHITESPACE_PROVEN`) |
| **Control A: Faint Present Line (val=230)** | 230.0 | 0.0000 | 0.0000 | **`INSUFFICIENT`** | `MEAN_INTENSITY_LOW(230.0 < 245.0)` |
| **Control B: Partially Occluded Line** | 125.41 | 0.5082 | 0.5410 | **`INSUFFICIENT`** | `INK_FRACTION_EXCEEDED` & `DILATED_INK_CONTAMINATION` |
| **Control C: ROI-Clipped Line** | N/A | N/A | N/A | **`INSUFFICIENT`** | `PRIMITIVE_OUTSIDE_ROI_OR_RENDER` |
| **Control D: Nearby Parallel Line (dist=2px)**| 255.0 | 0.0000 | 1.0000 | **`INSUFFICIENT`** | `DILATED_INK_CONTAMINATION(1.0000 > 0.05)` |
| **Control E: Dashed Line (5px dash, 5px gap)** | 104.51 | 0.5902 | 0.9508 | **`INSUFFICIENT`** | `INK_FRACTION_EXCEEDED` & `MEAN_INTENSITY_LOW` |
| **Control F: Text-Crossed Line** | 234.10 | 0.0820 | 0.1475 | **`INSUFFICIENT`** | `INK_FRACTION_EXCEEDED(0.0820 > 0.02)` |
| **Control G: Shifted Line (15px away)** | 255.0 | 0.0000 | 0.0000 | **`VERIFIED` (Pixel)** | Whitespace verified at pixel level; downstream correspondence blocks `REMOVE` |
| **Control H: Unparsed Texture / Hatch Noise** | 239.02 | 0.2131 | 0.8689 | **`INSUFFICIENT`** | `INK_FRACTION_EXCEEDED` & `DILATED_INK_CONTAMINATION` |

* **Verified Script:** [`test_negative_support_controls.py`](test_negative_support_controls.py).

---

## 6. THRESHOLD CLOSURE AND CLASSIFICATION

Every candidate threshold is strictly classified into exactly one architectural category:

1. **`darkness_threshold = 220`**
   - **Classification:** **`SAFE_FIXED_PROFILE`**
   - **Rationale:** Already frozen as `_APPROVED_DARKNESS_THRESHOLD = 220` in `source_support_verifier.py`. Reusing this constant maintains optical parity between positive stroke detection and background whitespace verification.

2. **`dilation_contamination_fraction <= 0.05` ($r = 2\text{px}$)**
   - **Classification:** **`SAFE_FIXED_PROFILE`**
   - **Rationale:** Matches `_APPROVED_ENDPOINT_TOLERANCE_PX = 2` (`ImageFilter.MaxFilter(size=5)`). Symmetrically clears a 2px corridor buffer around the line. If adjacent ink encroaches into $>5\%$ of this buffer, nearby parallel geometry or text contaminates the corridor (Control D).

3. **`max_corridor_ink_fraction <= 0.02`**
   - **Classification:** **`SYNTHETIC_DISCRIMINATOR`**
   - **Rationale:** Evaluated on synthetic and anti-aliased renderings to tolerate 1–2 isolated boundary pixels while cleanly rejecting dashed lines (59%) and text crossings (8%). It is a synthetic discriminator until calibrated across scanned print libraries.

4. **`corridor_mean_intensity >= 245.0`**
   - **Classification:** **`NEEDS_REAL_SOURCE_CALIBRATION`**
   - **Rationale:** On pure white synthetic backgrounds (255.0), 245.0 cleanly catches faint gray strokes (230.0). However, scanned engineering drawings on blue/yellowed paper or microfilm have background paper luminance varying between 215.0 and 240.0. A hardcoded 245.0 would cause all real paper corridors to fail closed. In production, this threshold must be dynamically calibrated against local or sheet-level background paper luminance ($I_{\text{corridor}} \ge I_{\text{bg\_sheet}} - \Delta_{\text{tol}}$).

---

## 7. DOWNSTREAM BOUNDARY: CONTROL G & SEMANTIC CHANGE

When a base entity $L_{\text{base}}$ at $y = 50$ is shifted to $y = 65$:
1. `source_support_verifier.py` observes genuine whitespace at $y = 50$ and emits:
   `status: VERIFIED`, `reason: OBSERVATIONAL_WHITESPACE_PROVEN`.
2. Downstream `cad_agent/source_fusion_proposal.py` must **NOT** convert this into `disposition: REMOVE`.
3. When a new candidate line exists in the spatial/functional neighborhood, the system cannot prove whether this represents:
   - A deletion of $L_1$ and addition of $L_2$, OR
   - A modification/move of $L_1$ to new position $L_1'$.
4. Downstream correspondence must fail closed to **`UNRESOLVED`** or keep $L_{\text{base}}$ as **`UNMATCHED_BASE_RETAINED`** unless explicit semantic authorization proves entity lifecycle.

---

## 8. FINAL STATUS

$$\mathbf{SOURCE\_NEGATIVE\_LINE\_SUPPORT\_EVIDENCE\_V1: \ CONTRACT\_CLOSED\_READY\_FOR\_CODEX}$$

* **Pixel Verifier:** Evidence-only whitespace confirmation in `cad_agent/source_support_verifier.py`.
* **Projection:** Private helper in `cad_agent/source_fusion_proposal.py`.
* **Production Code Modifications:** 0 lines (Research Only).
* **Native Entity Deletion:** **`BLOCKED`**.
