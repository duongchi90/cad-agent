# EXTERNAL_PRIOR_AND_SPEC_REPORT: Native Dimension Placement Collision Avoidance (REA-023)

- **Document ID:** `REA_DIM_PLACEMENT_EXTERNAL_PRIORS_V1`
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
| **PRIOR-3** | **ezdxf LinearDimension Renderer** | Manfred Moitzi / ezdxf | MIT License | `OPEN_SOURCE_REPO` | `DEPENDENCY_REUSE` | **YES** (Already imported) | **YES** |
| **PRIOR-4** | **PFLP Discrete Candidate Model** | Christensen, Marks & Shieber (1995) | Academic Paper | `ALGORITHM_PAPER` | `ALGORITHM_TRANSFER` | **YES** (Clean-room) | **YES** |
| **PRIOR-5** | **LibreCAD / QCAD RS_DimLinear** | LibreCAD / RibbonSoft | GPL v2 | `OPEN_SOURCE_REPO` | `NOT_REUSABLE` | **NO** (GPL barrier) | **YES** (Inspect only) |
| **PRIOR-6** | **FreeCAD TechDraw Dimensions** | FreeCAD Community | LGPL v2.1+ | `OPEN_SOURCE_REPO` | `NOT_REUSABLE` | **NO** | **YES** (Inspect only) |

---

## 2. Detailed Technical Evidence by Prior

### PRIOR-1: Drafting Standards (ASME Y14.5-2018 / ISO 129-1:2018)
- **SOURCE:** ASME Y14.5-2018 ("Dimensioning and Tolerancing"), Section 4; ISO 129-1:2018 ("Technical product documentation — Presentation of dimensions and tolerances").
- **SOURCE_TYPE:** `SPECIFICATION_ONLY` (Copyrighted Technical Standard).
- **LICENSE:** Copyrighted standard document.
- **DIRECT_CODE_REUSE_ALLOWED:** `NO` (No code exists; standard is English prose conventions).
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
- **SOURCE_TYPE:** `COMMERCIAL_BEHAVIORAL_PRIOR` (Proprietary commercial CAD engine).
- **LICENSE:** Proprietary commercial software.
- **DIRECT_CODE_REUSE_ALLOWED:** `NO`.
- **BEHAVIORAL_PRIOR_ALLOWED:** `YES` (Behavioral contract and system variable semantics).
- **WHAT_IS_ACTUALLY_SUPPORTED:**
  1. `DIMDLI` (Dimension Line Increment): Controls the incremental offset spacing between stacked baseline dimension lines (default is `0.38 in` or `9.5 mm / 3.75 mm`).
  2. `DIMEXO` (Extension Line Origin Offset): Gap between measured point and start of extension line.
  3. `DIMEXE` (Extension Line Extension): Overshoot of extension line beyond dimension line.
  4. When placing chained or stacked dimensions, AutoCAD steps along the normal vector by multiples of `DIMDLI`.
- **WHAT_IS_NOT_SUPPORTED:** AutoCAD's `DIMBASELINE` command requires manual user interaction to specify which side to place dimensions; it does not automatically inspect obstacles or flip sides autonomously.

---

### PRIOR-3: ezdxf LinearDimension Entity Architecture
- **SOURCE:** `ezdxf` (v1.4.4 installed in project virtual environment), `ezdxf.render.dim_linear.LinearDimension`.
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO` (MIT License).
- **EXACT_VERSION_COMMIT:** ezdxf 1.4.4.
- **LICENSE:** MIT License (`https://github.com/mozman/ezdxf/blob/master/LICENSE`).
- **DIRECT_CODE_REUSE_ALLOWED:** `YES` (MIT license, already a core dependency in `requirements/`).
- **BEHAVIORAL_PRIOR_ALLOWED:** `YES`.
- **WHAT_IS_ACTUALLY_SUPPORTED:**
  - `msp.add_linear_dim(base, p1, p2, location, angle, dxfattribs)`:
    - Stores definition points: `defpoint` (base point for dimension line placement), `defpoint2` ($p_1$), `defpoint3` ($p_2$), `defpoint4` (dimension text location).
    - `LinearDimension.render()` automatically constructs dimension lines, extension lines with `dimexo`/`dimexe`, and centers text along the dimension line.
  - **Critical Invariant:** `p1` and `p2` define the physical measurement truth. Moving `base` along the perpendicular normal changes the visual placement offset without altering the measurement value.
- **WHAT_IS_NOT_SUPPORTED:** ezdxf does not provide automatic collision detection or obstacle-avoiding placement search; the caller must supply the desired `base` coordinate.

---

### PRIOR-4: Discrete Candidate Model for Annotation Placement (PFLP)
- **SOURCE:** Christensen, Marks & Shieber (1995), "An Empirical Evaluation of Algorithms for Point-Feature Label Placement"; Hirsch (1982), "An Algorithm for Automated Map Labeling".
- **SOURCE_TYPE:** `ALGORITHM_PAPER`.
- **LICENSE:** Academic public literature (Algorithmic formulation).
- **REUSE_CLASS:** `ALGORITHM_TRANSFER`.
- **DIRECT_CODE_REUSE_ALLOWED:** `YES` (Clean-room reimplementation of the discrete candidate selection pattern).
- **BEHAVIORAL_PRIOR_ALLOWED:** `YES`.
- **WHAT_IS_ACTUALLY_SUPPORTED:**
  - Evaluates a small, finite set of discrete candidate positions ($S \times K$, e.g. 2 sides $\times$ 3 offset lanes).
  - Penalizes collisions using a deterministic scoring function (hard collisions for geometry crossings / text overlap, soft penalties for lane distance and side preference).
  - Selects the minimum penalty candidate via stable lexicographic tie-breaking.
- **BENEFIT FOR CAD AGENT:** Bounded $O(1)$ search per dimension (6 candidates total), completely deterministic, zero graph optimizer overhead, zero machine learning models, zero new dependencies.

---

### PRIOR-5 & PRIOR-6: Open-Source CAD Engines (LibreCAD, QCAD, FreeCAD)
- **SOURCE:** LibreCAD `RS_DimLinear` (GPL v2), FreeCAD `DrawViewDimension` (LGPL v2.1+).
- **SOURCE_TYPE:** `OPEN_SOURCE_REPO`.
- **LICENSE:** GPL v2 / LGPL v2.1+.
- **DIRECT_CODE_REUSE_ALLOWED:** `NO` (Copyleft license barriers).
- **BEHAVIORAL_PRIOR_ALLOWED:** `YES` (Inspection of user-interaction models only).
- **WHAT_IS_ACTUALLY_SUPPORTED:** Both engines require explicit user definition points (`definitionPoint`) clicked in the GUI. Neither engine implements an autonomous obstacle-avoiding multi-lane layout solver for batch dimension generation.

---

## 3. Project Policy and Code Avoidance Conclusion

1. **NO Third-Party Layout Solver:** Commercial layout engines or GPL cartographic packages must not be adopted.
2. **Minimal Clean-Room Algorithm Transfer:** The discrete candidate model (evaluating $\pm \mathbf{n}$ and discrete lanes $d_0 + k \cdot \Delta d$) combined with ezdxf's existing `add_linear_dim` API provides full collision avoidance capability without introducing new dependencies or subsystems.
