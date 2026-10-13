# REA020_CORRECTION: Hardening & Scope Calibration for Polyline Bulge

- **Document ID:** `REA020_CORRECTION_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Catalog Entry:** `REA-020`

---

## 1. Executive Summary & Disposition Downgrade

`REA-020` captures valid mathematical and specification knowledge regarding AutoCAD/DXF polyline bulge representation ($b = \tan(\theta/4)$). However, the previous research package over-promoted its production readiness:

```text
OLD_DISPOSITION                 = READY_TO_TRANSFER  (OVERCLAIMED)
CORRECTED_DISPOSITION           = RESEARCH_PRIOR
REUSE_CLASS                     = ALGORITHM_TRANSFER (RETAINED)
OWNER_MAPPING_STATUS            = VALID (Existing owners verified, but no active production path)
```

---

## 2. Verification of Current Main Ownership Boundaries

A fresh inspection of current main (`86318afc722939d88f355437e55405d012cba356`) reveals:

1. **`dxf_builder_lib/builder.py`:**
   - Emits native DXF `LINE`, `CIRCLE`, `ARC`, and `TEXT` entities via `msp.add_line()`, `msp.add_circle()`, `msp.add_arc()`, and `msp.add_text()`.
   - Does **not** contain an active production generation path for `LWPOLYLINE` with bulges. Test utilities may instantiate polyline objects, but production pipeline execution does not depend on them.
2. **`primitive_ir_lib/geometry_extraction.py`:**
   - Detects `RawLine` and `RawCircle` via OpenCV Canny + Hough transforms.
   - Does **not** perform arc detection or produce `ArcGeometry`.
3. **Product Need:**
   - There is currently no active product `RED` test or milestone deliverable demanding curved polyline bulge generation.
   - Promoting `REA-020` to `READY_TO_TRANSFER` created unwarranted pressure to divert Luna from the #491 OCR language-guard frontier.

---

## 3. Rectification of Technical & Numerical Invariants

| Claim | Old Status | Corrected Status | Technical Truth |
| :--- | :---: | :---: | :--- |
| **Bulge Formulation** | `STANDARD_INVARIANT` | `STANDARD_DEFINED_INVARIANT` | $b = \tan(\theta/4)$ is the exact Autodesk DXF Group Code 42 mathematical definition. |
| **Angular Sign Convention** | `STANDARD_INVARIANT` | `STANDARD_DEFINED_INVARIANT` | $b > 0$ denotes Counter-Clockwise (CCW); $b < 0$ denotes Clockwise (CW). |
| **Singularity Threshold** | `STANDARD_INVARIANT` | `PROJECT_HEURISTIC_UNVALIDATED_FOR_PRODUCTION` | The snap $|b| < 10^{-7} \implies b = 0.0$ was introduced in our unit test oracle. It is **not** an Autodesk/ezdxf normative contract. |
| **Radius Overflow Claim** | `PROVEN_FACT` | `REMOVED` | Floating-point radius calculation $\frac{d}{2} \cdot \frac{1 + b^2}{2b}$ approaches infinity as $b \to 0$, but standard CAD engines handle collinear lines without a mandatory $10^{-7}$ snap. |

---

## 4. License and Legal Cleanliness

- **`ezdxf`:** Distributed under the permissive MIT License. Mathematical algorithms in `ezdxf.math.bulge` can be cleanly referenced or adapted.
- **`LibreCAD`:** Distributed under GPLv2. Algorithms in `RS_Math` may serve only as clean-room behavioral reference; direct code ingestion is prohibited by project licensing policy.
- **`Autodesk DXF Reference`:** Copyright Autodesk, Inc. It serves as public `SPECIFICATION_PRIOR`, **not** public domain.

---

## 5. Corrected Anti-Repeat Contract

- **`DO_NOT_REPEAT_BASIC_BULGE_SEMANTICS_RESEARCH`:** `YES`.
  - Future sessions must not re-investigate the fundamental math of DXF Group Code 42 ($b = \tan(\theta/4)$) or sign conventions.
- **`REOPEN_INTEGRATION_RESEARCH_IF`:**
  - A current measured product boundary requires `LWPOLYLINE` bulge generation, conversion, verification, or persistence and current owners do not already satisfy it.
