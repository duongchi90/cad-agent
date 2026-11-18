# Marine Knowledge Pack V1-C — Single Conditional Rule Vertical Slice Design (`RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT`)

- **Date:** 2026-11-18
- **Status:** CANDIDATE_UNAPPROVED (Stacked on Marine V1-B `anti/marine-v1b-particulars-consistency`)
- **Owner:** `cad_agent.marine_knowledge` (consuming V1-A `engineering-fact-1.0` records and V1-B `verify_package_comparability`)

## 1. Intent & Problem Statement

Marine V0 (`evaluate_regulation_applicability_and_submittal`) evaluated `RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT` only from caller-supplied `structural_metrics["double_bottom_height_mm"]` scalars without native CAD handle/SHA-256 provenance, without native DXF `DIMENSION` override verification, and without V1-B's cross-sheet comparability gate.

Marine V1-C delivers a **single verified conditional rule vertical slice** (`evaluate_double_bottom_height_rule()`) grounded in **QCVN 72:2025/BGTVT** (`sha256=4ffed2dad51f16d72bff5661a17be4d4793fe547133f999c41ded1ea72696b20`), **Phần 2A, Chương 2, Clause `2.4.3-2`** (`pdf_page=[135]`, `reg_page=[151]`):

- Centerline double-bottom height (`Chiều cao của đáy đôi đo tại mặt phẳng dọc tâm tàu`):
  - `L <= 120.0 m`: minimum `700.0 mm` (`0,7 m`)
  - `120.0 m < L <= 140.0 m`: minimum `900.0 mm` (`0,9 m`)

## 2. Goals, Non-Goals & Fail-Closed Gates

- **Goals:**
  - **Bounded Native CAD Extraction (`observer.py`):**
    - Extract centerline double-bottom height text annotations (`chieu cao day doi ...`, `double bottom height ...`, `h_dd = ...`, `day doi cl h = ...`) into hash-bound `EngineeringFact` records (`fact_key="double_bottom_height_mm"`) with unit conversion (`mm`, `cm`, `m`, or `$INSUNITS in {4, 5, 6}`).
    - Reject bare unbound height notes (`h = 800 mm` without double-bottom context) and explicit non-centerline side/margin callouts (`chieu cao day doi o man = 800 mm`, `margin plate height = 650 mm`) into `fact_key="unbound_double_bottom_height_mm"` (`NATIVE_CAD_UNBOUND_TEXT` / `UNVERIFIED_UNBOUND_TEXT`), never `VERIFIED`.
    - Bind native DXF `DIMENSION` entities (`NATIVE_MEASURED_GEOMETRY`) to `fact_key="double_bottom_height_mm"` when spatially paired (`hypot(dx, dy) <= 3000.0` CAD units) with a centerline double-bottom label (`chieu cao day doi cl`, `double bottom cl`, `h_dd cl`), tagged in `raw_text`, or placed on `DB_CL` / `DAY_DOI_CL`, preserving `CONFLICTING_OVERRIDE` and `UNVERIFIED_UNITLESS` states from V1-A `evaluate_dimension_fact()`.
    - Extract non-negated single-bottom declarations (`tàu đáy đơn`, `đáy đơn`, `single bottom`) into `particulars["single_bottom_evidences"]`.
  - **Fail-Closed Rule Engine (`conditional_rules.py`):**
    - Reuse V1-B `verify_package_comparability()` whenever `len(obs_list) >= 2`; refuse cross-sheet pooling (`INSUFFICIENT_EVIDENCE` / `F_PACKAGE_COMPARABILITY_UNVERIFIED_FOR_RULE`) when revisions are undeclared (`None`), hulls/revisions/variants skew, or identity is unverified.
    - Enforce QCVN 72 scope (`Clause 1.1.1`, `1.1.2`, `1.1.4`), single-bottom exemption (`NOT_APPLICABLE` / `F_SINGLE_BOTTOM_EXEMPT`), eligible `MIDSHIP_STRUCTURAL` / `BASIC_STRUCTURAL` sheet + `geometry_status == "PRESENT"`, native verified provenance (`NATIVE_CAD_EVIDENCE` or `NATIVE_MEASURED_GEOMETRY` + `VERIFIED`), and Clause `1.4.43-1` rule length `L` (`design_length_l_m` or `[0.96 * Lwl, Lwl]`).
    - Catch universal `< 700.0 mm` violations (`CONFLICT`) even when `L` is unproven, catch `< 900.0 mm` violations for `120.0 < L <= 140.0 m` (`CONFLICT`), catch `DIMENSION` text overrides (`CONFLICT`), and abstain (`INSUFFICIENT_EVIDENCE`) on `OCR_ONLY`, unbound text, side/margin height, `FIXTURE_SUPPLIED` without DXF bytes, uncalibrated `$INSUNITS=0`, missing/ambiguous `L` (`Lpp`-only), or `Lwl` intervals straddling `120.0 m` / `140.0 m`.
- **Non-Goals:** Multi-rule expansion (`2.4.3-1` floor spacing, `2.4.3-3` girder spacing, `2.4.3-11/12` section modulus `W`/`J`), V1-D package completeness, or any CAD mutation (`cad_mutation=False`, `regulatory_compliance_proven=False`).

## 3. Selected Architecture

1. **Selected — Dedicated `cad_agent/marine_knowledge/conditional_rules.py` consuming V1-A `EngineeringFact` records and V1-B `verify_package_comparability()`:** Preserves V0 Skill 2 and V1-B boundaries without duplicating `dxf_builder_lib` `DIMENSION` truth logic or importing `ezdxf` outside `dxf_builder_lib/`.
2. **Rejected — Expanding V0 `evaluate_regulation_applicability_and_submittal` in place:** Would entangle V0 backward-compatibility contracts with V1-C native-only provenance and comparability gates.
