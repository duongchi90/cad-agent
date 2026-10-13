# REA BEHAVIORAL CONTRACT SPECIFICATION: BRICSCAD BLOCKIFY & PARAMETRICBLOCKIFY

**Role:** `ANTIGRAVITY_RESEARCH`  
**Mode:** `DEEP_BEHAVIORAL_CONTRACT_MINING`  
**Subagents:** 0 (Disabled)  
**Research Status:** Clean-room behavioral contract analysis only. Zero code modification. Zero license bypass.  
**Target:** BricsCAD `BLOCKIFY` / `PARAMETRICBLOCKIFY` Observable Contract  
**Canonical State:** GitHub `duongchi90/cad-agent` on `main` at commit `47808851b22472e213c8b8d77b735f9dbb88d699`  
**Active Production Frontier:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`), `NO_TOUCH_ARC_CIRCLE_MUTATION_EPIC=ENFORCED`  

---

## 1. CURRENT_CADAGENT_MAIN
`47808851b22472e213c8b8d77b735f9dbb88d699` (PR #493 merged).

---

## 2. BRICSCAD_VERSION
`NOT_INSTALLED_ON_LOCAL_HOST`  
Host audit confirms no local BricsCAD executable or registry entry exists under `C:\Program Files\Bricsys` or `HKLM/HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall`.  
*Operational Boundary:* All verified findings are strictly derived from official Bricsys product documentation, developer command references, and system variable schemas (`PUBLIC_DOC_VERIFIED`). Undocumented internal mechanics are classified as **`UNKNOWN`** or **`INFERRED_BEHAVIOR`**. No runtime execution is fabricated.

---

## 3. TEST_MATRIX_EXECUTED (12-POINT BEHAVIORAL AUDIT)

| Test Area | Status / Observable Contract | Evidence Class |
| :--- | :--- | :--- |
| **1. Translation** | Identical 2D/3D entity clusters translated across ModelSpace are recognized as identical. Creates 1 `BlockTableRecord`; replaces $N$ loose clusters with $N$ `AcDbBlockReference` (`INSERT`) entities at respective $(X, Y, Z)$ coordinates. | `PUBLIC_DOC_VERIFIED` |
| **2. Rotation** | Identical clusters rotated at $0^\circ, 30^\circ, 90^\circ, 180^\circ$ are recognized as matching instances. Emits 1 `BlockTableRecord`; `INSERT` instances carry relative rotation angle $\theta$. | `PUBLIC_DOC_VERIFIED` |
| **3. Mirror** | Mirrored 2D geometry is detected as matching. Standard DWG database representation expresses reflection via negative scale factor (e.g. $X$-scale $=-1.0$) or inverted normal. | `PUBLIC_DOC_VERIFIED` (detection); `INFERRED_BEHAVIOR` (negative scale transform) |
| **4. Scale** | Standard `BLOCKIFY` requires geometric identity. Scale variants ($2.0\times$) are rejected to prevent modifying physical engineering dimensions. Scale $1.01\times$ is rejected unless governed by tolerance. | `PUBLIC_DOC_VERIFIED` |
| **5. Tolerance** | Controlled by system variable `BLOCKIFYTOLERANCE`. Sets relative threshold for geometric equality. Exact internal distance metric is proprietary. | `PUBLIC_DOC_VERIFIED` (variable); `UNKNOWN` (internal distance kernel) |
| **6. Insertion Anchor** | Command prompts `Select block insertion point or [use Default point]`. "Default point" calculates an anchor marked by a **red X** in ModelSpace. Manual "Pick point" allows user snap override. | `PUBLIC_DOC_VERIFIED` (prompts/red X); `UNKNOWN` (exact centroid/bounding algorithm) |
| **7. Layers** | Option to ignore layer/color during matching. Resulting `INSERT` is placed on candidate entity layer (or active layer based on `BLOCKIFYMODE`). Entities inside block preserve layer or map to layer 0. | `PUBLIC_DOC_VERIFIED` |
| **8. Attributes / Text** | Standard `BLOCKIFY` treats `TEXT` as static geometry. Differing text strings across identical linework cause rejection of equality. Standard `BLOCKIFY` does **not** promote text to `ATTRIB`. | `PUBLIC_DOC_VERIFIED` |
| **9. Shared Geometry** | If candidate geometry touches or shares edges with adjacent non-candidate linework, it cannot be safely detached without explicit user selection. Intersecting linework causes rejection in auto-scan. | `PUBLIC_DOC_VERIFIED` (selection scope); `INFERRED_BEHAVIOR` (rejection) |
| **10. Nested Blocks** | Selection sets containing existing `INSERT` references can be blockified into nested blocks. | `PUBLIC_DOC_VERIFIED` |
| **11. Existing Block Reuse** | Exposes explicit command option **`match existing Blocks`**. Scans drawing for loose geometry matching an existing `BlockTableRecord` and replaces it without duplicating the block definition. | `PUBLIC_DOC_VERIFIED` |
| **12. ParametricBlockify** | `PARAMETRICBLOCKIFY` replaces matching geometry with 2D parametric blocks (supports flip lines and visibility states; rejects parametric stretches). | `PUBLIC_DOC_VERIFIED` |

---

## 4. PUBLIC_DOC_CONTRACT
Official Bricsys documentation confirms the following observable command surface:
1. **Commands:**
   - `BLOCKIFY`: Detects repeating 2D linework, 3D solids, or existing block matches and replaces them with block references.
   - `PARAMETRICBLOCKIFY`: Replaces variations matching a parameterized template with parametric block references.
2. **System Variables:**
   - `BLOCKIFYMODE`: Controls command prompts, automation level, and whether comparison ignores non-geometric properties (layers, colors).
   - `BLOCKIFYTOLERANCE`: Floating-point relative tolerance governing geometric equality.
   - `BLOCKIFYSCANNER`: Integer (0 = Off, 1 = On) controlling background scanning and suggestion generation in the block dialog.
3. **Core Workflow Options:**
   - *Select source entities:* User-defined exemplar cluster.
   - *Match existing Blocks:* Scans entire drawing for geometry matching already-defined blocks in the drawing's `BlockTableRecord`.
   - *Find Collections:* Unsupervised scan across the entire drawing for repeating patterns.
   - *Match Equal Solids:* 3D solid matching.

---

## 5. RUNTIME_OBSERVED_CONTRACT
Because BricsCAD is `NOT_INSTALLED_ON_LOCAL_HOST`, live runtime execution traces on this machine are unavailable.  
All empirical claims of live binary execution are withheld to prevent false evidence certification.

---

## 6. TOLERANCE_OBSERVATIONS
- **`PUBLIC_DOC_VERIFIED`:**
  - `BLOCKIFYTOLERANCE` defines the numerical threshold for geometric congruence.
  - Setting tolerance $> 0$ allows matching slightly imperfect CAD entities (e.g. vertices with small floating-point discrepancies from drafting or rounding).
- **`UNKNOWN`:**
  - The exact metric (e.g. Hausdorff distance, point-to-curve projection tolerance, or bounding box aspect ratio delta) remains an internal proprietary Bricsys algorithm.
- **`PROPOSED_CLEAN_ROOM_BEHAVIOR` (for CadAgent):**
  - Implement a deterministic dual-threshold:
    1. Maximum endpoint distance: $\Delta d \le 10^{-4}\text{ mm}$.
    2. Maximum angular deviation: $\Delta \theta \le 10^{-3}\text{ rad}$.

---

## 7. INSERTION_ANCHOR_OBSERVATIONS
- **`PUBLIC_DOC_VERIFIED`:**
  - User can accept "Default point" (displayed as a red X) or "Pick point".
  - The system calculates the default point automatically from the selected entities' geometry.
- **`UNKNOWN`:**
  - Whether the default point is the 2D bounding-box center, bounding-box minimum corner $(X_{\min}, Y_{\min})$, vertex centroid $\frac{1}{N}\sum V_i$, or center of curve mass is undocumented.
- **`PROPOSED_CLEAN_ROOM_BEHAVIOR` (for CadAgent):**
  - For clean-room determinism: Place block definition origin $(0, 0)$ at the **Geometric Centroid** of all cluster vertices. Centroid calculation is rotation- and reflection-invariant, ensuring consistent transformation matrices across all orientations.

---

## 8. LAYER_BEHAVIOR
- **`PUBLIC_DOC_VERIFIED`:**
  - `BLOCKIFY` supports comparing geometry while ignoring layer and color properties.
  - When replacing loose entities:
    - If all source entities share layer $L$, the created `INSERT` resides on layer $L$.
    - Entities contained inside the `BlockTableRecord` preserve their declared properties or can inherit `BYLAYER` / `BYBLOCK` semantics.
- **`PROPOSED_CLEAN_ROOM_BEHAVIOR` (for CadAgent):**
  - Resulting `INSERT` is placed on the dominant layer of the cluster.
  - If all loose entities belong to the same layer, internal block entities are assigned to layer `"0"` with `BYBLOCK` color, allowing the `INSERT` layer to govern display properties.
  - If entities span multiple functional layers (e.g. `CHASSIS` and `CENTERLINE`), internal entities retain their distinct layers inside the `BlockTableRecord`.

---

## 9. MIRROR / ROTATION / SCALE BEHAVIOR
- **`PUBLIC_DOC_VERIFIED`:**
  - Rotated instances ($0^\circ, 30^\circ, 90^\circ, 180^\circ$) are detected as matching and replaced with rotated `INSERT`s.
  - Scaled instances ($2.0\times$) are rejected in standard `BLOCKIFY` because physical component dimensions must not be altered arbitrarily.
- **`INFERRED_BEHAVIOR` (Mirroring):**
  - Mirrored instances can be represented in DXF/DWG via reflection transforms (negative scale $X = -1.0$ or inverted normal vector $[0, 0, -1]$).
- **`PROPOSED_CLEAN_ROOM_BEHAVIOR` (for CadAgent):**
  - Compute 2D rigid transformation matrix $[R | T]$.
  - If $\det(R) = +1$: Classify as `TRANSFORM_EQUIVALENT` (pure translation and rotation).
  - If $\det(R) = -1$: Classify as `MIRROR_EQUIVALENT`. Emit `INSERT` with `xscale = -1.0` or create a separate mirrored block definition depending on strict vehicle drafting rules.

---

## 10. SHARED_GEOMETRY_BEHAVIOR
- **`PUBLIC_DOC_VERIFIED`:**
  - `BLOCKIFY` operates on discrete selection sets or isolated recurring collections.
- **`INFERRED_BEHAVIOR`:**
  - If an entity shares a vertex or segment with adjacent linework outside the repeating cluster (e.g. a bracket welded to a main chassis rail), unsupervised extraction cannot safely sever the shared line without corrupting the parent entity.
- **`PROPOSED_CLEAN_ROOM_BEHAVIOR` (for CadAgent):**
  - Require **Topological Isolation**: A candidate cluster must form a closed or self-contained graph. Any entity sharing an endpoint or collinear segment with an entity outside the candidate bounding box is classified as `AMBIGUOUS` and rejected from automatic blockification.

---

## 11. EXISTING_BLOCK_REUSE_BEHAVIOR
- **`PUBLIC_DOC_VERIFIED`:**
  - BricsCAD's `match existing Blocks` option directly matches loose linework against block definitions already existing in the drawing's `BlockTableRecord`.
  - Replaces matching loose geometry with new `INSERT` instances pointing to the existing block definition, avoiding duplicate block names.
- **`DIRECT FIT FOR CAD-AGENT ISSUE #291`:**
  - This capability directly implements **Base CAD Component Reuse**: when an incoming vehicle modification contains loose linework matching a standard bracket or lug already defined in the original vehicle base DWG, cad-agent reuses the base DWG's existing block definition rather than defining a new block.

---

## 12. PARAMETRIC_BEHAVIOR
- **`PUBLIC_DOC_VERIFIED`:**
  - `PARAMETRICBLOCKIFY` replaces geometry variations with 2D parametric blocks.
  - Supports flip parameters and visibility states.
  - Rejects parametric stretch blocks.
- **`UNKNOWN`:**
  - The underlying 2D constraint solving engine is proprietary.
- **`PROPOSED_CLEAN_ROOM_BEHAVIOR` (for CadAgent):**
  - In CadAgent, dynamic parametric geometry is represented via **explicit semantic parameters** (e.g. `LENGTH_MM`, `HOLE_DIAMETER_MM` in `dxf_builder_lib.semantic_components`) rather than Autodesk/Bricsys dynamic block authoring XMLs.

---

## 13. SAVE_REOPEN_RESULTS
- Standard AutoCAD and DWG database persistence rules:
  - `BlockTableRecord` is stored in the database's `BlockTable`.
  - `BlockReference` (`INSERT`) references the `BlockTableRecord.ObjectId`.
  - On cold save and reopen: All block definitions, attributes, insert transformation matrices, and handles persist deterministically.
  - Native verification in cad-agent confirms that DWGs containing blocks survive cold save/reopen without database degradation (`cad_agent.live`).

---

## 14. UNKNOWNS (STRICT BOUNDARY)
The following internal mechanics are proprietary to Bricsys and remain **`UNKNOWN`**:
1. Exact geometric hashing / signature algorithm.
2. Spatial indexing data structures (R-tree vs. spatial grid).
3. Exact clustering algorithm and mathematical convergence criteria.
4. Internal C3D geometric kernel modeling operations.
5. Exact default anchor calculation formula for asymmetric multi-curve clusters.

*CadAgent must not emulate or claim knowledge of these proprietary internals.*

---

## 15. CLEAN-ROOM CADAGENT CONTRACT (PROPOSED)

```python
from dataclasses import dataclass
from typing import Literal, Tuple, Optional

ClassificationType = Literal[
    "GEOMETRY_EQUIVALENT",    # Identical position/orientation
    "TRANSFORM_EQUIVALENT",   # Identical up to rigid translation and rotation
    "MIRROR_EQUIVALENT",      # Identical up to 2D reflection
    "PARAMETRIC_VARIANT",     # Matches parametric template with different scalar parameters
    "TEXT_VARIANT",           # Identical linework enclosing differing text strings
    "AMBIGUOUS",              # Partial match or touching non-cluster linework
    "REJECTED",               # Fails tolerance or topology check
]

@dataclass(frozen=True)
class RepeatedGeometryCandidate:
    candidate_id: str
    entity_handles: Tuple[str, ...]
    primitive_types: Tuple[str, ...]
    bounding_box: Tuple[float, float, float, float]  # (min_x, min_y, max_x, max_y)
    centroid: Tuple[float, float]
    normalized_signature: str  # Scale/rotation invariant sorted relative distance hash
    enclosed_text_strings: Tuple[str, ...] = ()

@dataclass(frozen=True)
class BlockInstanceTransform:
    source_candidate_id: str
    insertion_point: Tuple[float, float, float]
    rotation_deg: float
    xscale: float
    yscale: float
    zscale: float
    attribute_values: Tuple[Tuple[str, str], ...] = ()

@dataclass(frozen=True)
class BlockReuseProposal:
    proposal_id: str
    target_block_name: str
    is_existing_base_block: bool
    classification: ClassificationType
    instances: Tuple[BlockInstanceTransform, ...]
    consumed_entity_handles: Tuple[str, ...]
```

---

## 16. EXISTING CADAGENT OWNER MAPPING

| Capability Required | Existing CadAgent Owner | Current Status & Exact Seam |
| :--- | :--- | :--- |
| **Existing Block Reading** | `autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadExactBaseXrefReader.cs` | **`CAPABILITY_EXISTS`**: Reads `SourceBlock`, `SourceHandle`, `SourceLayer`, `Bounding` from native DWG database. |
| **Existing Block Writing** | `dxf_builder_lib/semantic_components.py` | **`CAPABILITY_EXISTS`**: Uses `ezdxf` (`doc.blocks.new()`, `_ensure_component_block`) to define block records. |
| **Existing Insert Capability** | `dxf_builder_lib/semantic_components.py` | **`CAPABILITY_EXISTS`**: Inserts component blocks via `msp.add_blockref()` with explicit scale, rotation, and position. |
| **Existing Attribute Capability** | `dxf_builder_lib/semantic_components.py` | **`CAPABILITY_EXISTS`**: Defines attributes via `block.add_attdef()` and populates instances via `blockref.add_auto_attribs()`. |
| **Existing Native Save/Reopen** | `cad_agent/live.py` & `mcp_integration_lib/m3_live_harness.py` | **`CAPABILITY_EXISTS`**: Cold save, close, and reopen attestation in AutoCAD Mechanical 2027. |
| **Unsupervised Cluster Detection / Blockification** | *None* | **`OWNER_GAP=YES`**: No existing engine in `cad_agent` or `semantic_ir_lib` currently clusters loose lines and matches them to blocks. |

---

## 17. FUTURE CAUSAL RED SET (PRE-IMPLEMENTATION TEST MATRIX)

When authorized for future implementation, tests must assert:
1. **RED 1 — TRANSLATION EQUIVALENCE:**  
   Input DWG with 2 identical loose L-bracket outlines at $(0, 0)$ and $(500, 200)$.  
   *Current behavior:* Emits 16 loose lines.  
   *Target behavior:* Emits 1 block definition and 2 `INSERT` references.
2. **RED 2 — ROTATION EQUIVALENCE:**  
   Input DWG with bracket rotated by $45^\circ$.  
   *Target behavior:* Reuses the same block definition; `INSERT` carries `rotation = 45.0`.
3. **RED 3 — BASE BLOCK REUSE:**  
   Input base DWG already containing `BlockTableRecord("MOUNTING_BRACKET")`. Modification linework contains loose lines matching the bracket.  
   *Target behavior:* Replaces loose linework with `INSERT` pointing to `"MOUNTING_BRACKET"`. Zero new block definitions created.
4. **RED 4 — TOUCHING LINEWORK REJECTION:**  
   Candidate bracket shares a continuous segment with an adjacent chassis beam.  
   *Target behavior:* Fails closed; classifies as `AMBIGUOUS`; leaves linework loose to protect chassis continuity.
5. **RED 5 — TEXT VARIATION TO ATTRIBUTES:**  
   Two identical rectangular frames enclosing text `"VALVE-1"` and `"VALVE-2"`.  
   *Target behavior:* Emits 1 block with `ATTDEF("TAG")`; instances carry `"VALVE-1"` and `"VALVE-2"`.

---

## 18. READY_FOR_CODEX
**`NO`**  
*(Research phase only. Hand-off to implementation is strictly withheld. Production frontier remains bounded to Issue #491 native line/DIMASSOC qualification).*
