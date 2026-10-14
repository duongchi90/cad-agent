# EXTERNAL_PRIOR_AND_SPEC_REPORT: Native Dimension Placement Collision Avoidance (REA-023)

- **Document ID:** `REA_DIM_PLACEMENT_EXTERNAL_PRIORS_V2`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Capability:** `NATIVE_DIMENSION_PLACEMENT_COLLISION_AVOIDANCE` (REA-023)
- **Evidence Tier:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`

---

## 1. Prior Inventory and Provenance Summary

| Prior ID | Name / Technology | Originating Entity | License | Source Type | Reuse Class | Direct Code Reuse | Behavioral Prior Allowed |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **PRIOR-1** | **ASME Y14.5 / ISO 129-1** | ASME / ISO Standards Committees | Copyrighted Standard | `SPECIFICATION_ONLY` | `CLEAN_ROOM_BEHAVIORAL_CONTRACT` | **NO** | **YES** |
| **PRIOR-2** | **AutoCAD DIMBASELINE / DIMDLI** | Autodesk, Inc. | Proprietary Commercial | `COMMERCIAL_BEHAVIORAL_PRIOR` | `COMMERCIAL_BEHAVIORAL_PRIOR` | **NO** | **YES** |
| **PRIOR-3** | **ezdxf LinearDimension Renderer** | Manfred Moitzi / ezdxf | MIT License | `DEPENDENCY_API_INSPECTION` | `DEPENDENCY_REUSE` | **YES** (Already imported) | **YES** |
| **PRIOR-4** | **PFLP Discrete Candidate Model** | Christensen, Marks & Shieber (1995) | Academic Paper | `ALGORITHM_PAPER` | `ALGORITHM_TRANSFER` | **NO** (Clean-room transfer) | **YES** |

---

## 2. Detailed Technical Evidence by Prior

### PRIOR-1: Drafting Standards (ASME Y14.5-2018 / ISO 129-1:2018)
- **SOURCE:** ASME Y14.5-2018 ("Dimensioning and Tolerancing"), Section 4; ISO 129-1:2018 ("Technical product documentation — Presentation of dimensions and tolerances").
- **SOURCE_TYPE:** `SPECIFICATION_ONLY` (Copyrighted Technical Specification / Documentation Prior).
- **LICENSE:** Copyrighted standard document (all rights reserved by ASME/ISO).
- **DIRECT_CODE_REUSE_ALLOWED:** `NO` (No code exists in standard; specification is English prose drafting rules).
- **BEHAVIORAL_PRIOR_ALLOWED:** `YES` (Conventions define expected CAD drawing layout principles).
- **WHAT_IS_ACTUALLY_SUPPORTED:**
  1. *Placement outside profile:* Dimensions should be placed outside the outline of the part where practicable.
  2. *Dimension line crossing prohibition:* Dimension lines must not cross other dimension lines.
  3. *Extension line crossing minimization:* Extension lines may cross each other, but should not cross dimension lines if avoidable.
  4. *Nesting / Stacking order:* Smaller intermediate dimensions are placed closer to the measured feature; overall dimensions are placed in outer lanes to avoid extension lines crossing dimension lines.
  5. *Clearance:* A visible gap must separate extension lines from feature vertices (`DIMEXO`), and extension lines overshoot the dimension line (`DIMEXE`).
- **WHAT_IS_NOT_SUPPORTED:** Does NOT specify an automated algorithmic procedure, collision detection routine, or computational geometry optimization function.

---

### PRIOR-2: AutoCAD DIMBASELINE, DIMCONTINUE, and DIMDLI System Contract
- **SOURCE:** Autodesk AutoCAD 2027 Documentation / DXF Reference (AutoCAD Core System Variables).
- **SOURCE_TYPE:** `COMMERCIAL_BEHAVIORAL_PRIOR` (Proprietary commercial CAD engine behavioral contract).
- **LICENSE:** Proprietary commercial software (Autodesk, Inc.).
- **DIRECT_CODE_REUSE_ALLOWED:** `NO`.
- **BEHAVIORAL_PRIOR_ALLOWED:** `YES` (Behavioral contract and system variable semantics).
- **WHAT_IS_ACTUALLY_SUPPORTED:**
  1. `DIMDLI` (Dimension Line Increment): System variable controlling incremental offset spacing between stacked baseline dimension lines. (Numeric defaults vary by template; numeric spacing used in this research is an independent empirical heuristic).
  2. `DIMEXO` (Extension Line Origin Offset): Gap between measured point and start of extension line.
  3. `DIMEXE` (Extension Line Extension): Overshoot of extension line beyond dimension line.
  4. When placing chained or stacked dimensions, AutoCAD steps along the normal vector by multiples of the baseline increment.
- **WHAT_IS_NOT_SUPPORTED:** AutoCAD's `DIMBASELINE` command requires manual user interaction to specify which side to place dimensions; it does not automatically inspect obstacles or flip sides autonomously.

---

### PRIOR-3: ezdxf LinearDimension Entity Architecture
- **SOURCE:** `ezdxf` (v1.4.4 installed in project virtual environment), `ezdxf.render.dim_linear.LinearDimension` API.
- **SOURCE_TYPE:** `DEPENDENCY_API_INSPECTION` (Inspection of installed open-source dependency API).
- **EXACT_VERSION_COMMIT:** `ezdxf==1.4.4` (project environment pinned dependency).
- **LICENSE:** MIT License (`https://github.com/mozman/ezdxf/blob/master/LICENSE`).
- **DIRECT_CODE_REUSE_ALLOWED:** `YES` (MIT license, already a core dependency in `requirements/`).
- **BEHAVIORAL_PRIOR_ALLOWED:** `YES`.
- **WHAT_IS_ACTUALLY_SUPPORTED:**
  - `msp.add_linear_dim(base, p1, p2, location, angle, dxfattribs)`:
    - Stores definition points: `defpoint` (base point for dimension line placement), `defpoint2` ($p_1$), `defpoint3` ($p_2$), `defpoint4` (dimension text location).
    - `LinearDimension.render()` automatically constructs dimension lines, extension lines with `dimexo`/`dimexe`, and centers text along the dimension line.
  - **Geometric Invariant:** `p1` and `p2` define the physical measurement segment. Moving `base` along the perpendicular normal changes visual placement offset without altering definition point coordinates.
- **WHAT_IS_NOT_SUPPORTED:** ezdxf does not provide automatic collision detection or obstacle-avoiding placement search; the caller must supply the desired `base` coordinate.

---

### PRIOR-4: Discrete Candidate Model for Annotation Placement (PFLP)
- **SOURCE:** Jon Christensen, Joe Marks, Stuart M. Shieber (1995), "An Empirical Study of Algorithms for Point-Feature Label Placement", ACM Transactions on Graphics (TOG), 14(3), 1995, pp. 203–232.
- **SOURCE_TYPE:** `ALGORITHM_PAPER` (Academic algorithmic literature).
- **LICENSE:** Academic paper (algorithmic principles; no licensed source code artifact identified or inspected).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER` (Clean-room implementation of discrete candidate evaluation pattern).
- **DIRECT_CODE_REUSE_ALLOWED:** `NO` (Clean-room algorithmic reimplementation only; no third-party code copied).
- **BEHAVIORAL_PRIOR_ALLOWED:** `YES`.
- **WHAT_IS_ACTUALLY_SUPPORTED:**
  - Evaluates a small, finite set of discrete candidate positions ($S \times K$, e.g. 2 sides $\times$ 3 offset lanes).
  - Penalizes collisions using a deterministic scoring function with strict priority: hard collisions for geometry crossings / text overlap, soft penalties for extension crossings, lane distance, and side preference.
  - Selects the minimum penalty candidate via stable lexicographic tie-breaking.
- **BENEFIT FOR CAD AGENT:** Bounded $O(1)$ search per dimension (6 candidates total), completely deterministic, zero graph optimizer overhead, zero machine learning models, zero new dependencies.

---

### Background Reference: Open-Source CAD Engines (LibreCAD, FreeCAD, QCAD)
- **NOTE ON SCOPE:** Open-source CAD engines (FreeCAD, QCAD) were not inspected in this investigation. In REA-021, LibreCAD's `RS_DimLinear` was inspected and verified to position linear dimension entities based on explicit caller-provided definition points without autonomous obstacle-avoidance search. No code from LibreCAD, FreeCAD, or QCAD is reused in REA-023.

---

## 3. Project Policy and Code Avoidance Conclusion

1. **NO Third-Party Layout Solver:** Commercial layout engines or external cartographic packages must not be adopted.
2. **Minimal Clean-Room Algorithm Transfer:** The discrete candidate model (evaluating $\pm \mathbf{n}$ and heuristic discrete lanes $d_0 + k \cdot \Delta d$) combined with ezdxf's existing `add_linear_dim` API provides bounded collision avoidance capability without introducing new dependencies or subsystems.
3. **Research Heuristic Attribution:**
   - **Actual scoring penalties from code:**
     - Hard collisions (out-of-bounds, geometry line/text crossings, obstacle overlaps, placed dimension line/text overlaps) strictly dominate candidate selection ($\text{Primary Key} = \text{hard\_collision\_count}$).
     - Soft penalties: $P_{\text{ext\_geom}} = 150.0$ each, $P_{\text{ext\_dim}} = 300.0$ each, $P_{\text{dim\_ext}} = 300.0$ each, $P_{\text{lane}} = 15.0 \cdot k$, $P_{\text{side}} = 1.0$ (when $s = -1$).
   - **Base floor model change:** The candidate prototype uses base offset floor $\max(\text{length} \cdot 0.08, 6.0\text{ mm})$ and lane step increment $\Delta d = \max(7.5\text{ mm}, 2 \cdot H_{\text{text}})$. The increase from the production baseline floor of $5.0\text{ mm}$ to $6.0\text{ mm}$ is an empirical research heuristic model change, not an external drafting standard.
   - **Input-order independence:** Specs are sorted canonically by $\text{spec\_sort\_key} = (\text{length}, \min(p_1, p_2), \max(p_1, p_2), \text{spec\_id})$.
