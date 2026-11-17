# Marine Knowledge Pack V1-B — Engineering Particulars Consistency Design

- **Date:** 2026-11-18
- **Status:** CANDIDATE_UNAPPROVED (Stacked on V1-A Draft PR `#575` @ `67ab1f7afb7e1a5769ae740b57e8a075be7f8ab5`)
- **Owner:** `cad_agent.marine_knowledge` (consuming V1-A `engineering-fact-1.0` records)

## 1. Intent & Problem Statement

Marine V0 (`detect_drawing_gaps_and_conflicts`) compares raw strings and flat scalar buckets across whatever observations are passed in, without verifying whether sheets belong to the same vessel/revision and without distinguishing true conflicts from unit differences, `Loa`/`L`/`Lpp`/`Lwl` concept differences, missing companion entries, approximate/ambiguous schemas (such as engine model `6 S35MC` vs power `4040 kW`), or unbound CAD notes.

V1-B builds `evaluate_particulars_consistency()`, producing a deterministic **Cross-Drawing Engineering Consistency Report** (`marine-check-result-1.0` with structured `consistency_matrix` and `comparability_gate` in `observed_scope`).

## 2. Goals, Non-Goals & Anti-Goals

- **Goals:**
  - **Comparability & False-Conflict Gate:** Verify whether supplied drawings belong to the same vessel and comparable configuration/revision (`COMPARABLE_VERIFIED`, `UNVERIFIED_REVISION_OR_CONFIGURATION`, `DIFFERENT_VESSEL`, `DIFFERENT_REVISION`, `UNVERIFIED_SAME_VESSEL`, `INSUFFICIENT_ELIGIBLE_SHEETS`) before claiming cross-sheet particular conflicts or cross-sheet `PASS`:
    - Explicit matching revisions (`REV : 01` on all eligible sheets) with compatible `design_variants` and vessel identity remain `COMPARABLE_VERIFIED` even when `issue_dates` differ (`1/2005` vs `12/2005` recorded only as informational `ISSUE_DATE_SPREAD`).
    - Undeclared revisions (`revision=None` on all sheets), `design_variants` skew (`PHUONG AN III` vs `[]`), or project-code-only vessel-description divergence yield `UNVERIFIED_REVISION_OR_CONFIGURATION` (`comparable=False`, `advisory_comparison_allowed=True`): cross-sheet matches become `OBSERVED_MATCH_UNVERIFIED_COMPARABILITY` (never false `PASS`) and cross-sheet differences become advisory `INSUFFICIENT_EVIDENCE` findings (`F_ADVISORY_DIFFERENCE_*`, `advisory_only=True`, preserving `bound_facts` and CAD handles with zero mutation proposals), while single-sheet internal contradictions still raise `CONFLICT`.
  - **9 Parameter Groups:** `length_group` (`L`, `Lpp`, `Lwl`, `Loa` + physical invariants `Lpp <= Loa`, `Lwl <= Loa`, `0.96*Lwl <= L <= Lwl`), `breadth_m` (`B`), `depth_m` (`D`), `draft_m` (`T` + `T <= D`), `hull_no`, `ship_type`, `service_and_class`, `watertight_bulkhead_count` (eligible `GA`/`BASIC_STRUCTURAL` sheets only), and structured `main_engine` (`count`, `power_kw`, `model_code`).
  - **7 Non-Conflict Disambiguations:**
    1. Unit difference (`52.00 m` vs `52000 mm` vs `5200 cm`) -> `CONSISTENT` (`UNIT_NORMALIZED_MATCH`) on verified comparable sheets.
    2. Distinct length concepts (`Loa=99.95m` vs `Lpp=92.40m`, or `L=53.5m` vs `Lpp=52.0m`) -> `COMPATIBLE_CONCEPTS` unless physical ordering is violated (`Lpp > Loa` or `L > Lwl` -> `CONFLICT` on comparable sheets, `ADVISORY_DIFFERENCE` when comparability is unverified).
    3. Missing datum on companion sheet -> `SINGLE_SHEET_OBSERVED` / `INCOMPLETE_COVERAGE` (not `CONFLICT`).
    4. Unclear / approximate / non-equivalent table schema (`ABT. 99.95 m`, or engine model `6 S35MC` vs power `4040 kW (5500 cv)`) -> `AMBIGUOUS_OR_APPROXIMATE` (`INSUFFICIENT_EVIDENCE`, not false `CONFLICT` and not `PASS`).
    5. Unbound CAD note / OCR-only / uncalibrated unitless fact / ineligible sheet type -> `EXCLUDED_UNVERIFIED_SOURCE` (`INSUFFICIENT_EVIDENCE`).
    6. Explicit revision skew (`REV A` vs `REV B`, or `REV A` vs `None` on same hull) -> `DIFFERENT_REVISION` (`INSUFFICIENT_EVIDENCE`, not same-revision `CONFLICT`).
    7. Undeclared revisions or variant/configuration skew (`THLT7000` `PHUONG AN III` `TAU HANG - KHACH` vs `GA7000` `TAU HANG - THUC TAP`) -> `UNVERIFIED_REVISION_OR_CONFIGURATION` (`INSUFFICIENT_EVIDENCE` with `F_ADVISORY_DIFFERENCE_SHIP_TYPE`, not false same-revision `CONFLICT` or false `PASS`).
- **Non-Goals & Non-Duplication Boundaries:** Conditional scantling rule expansion (V1-C), full package completeness audit (V1-D), multi-view geometry (V2-A / PR `#569`), single-drawing CAD dimension-truth / rendered-block visibility review owned by `dxf_builder_lib` (PR `#572`), or CAD mutation.
- **Anti-Goals:** Never raise false conflicts between two different ships (`YN-101` vs `YN-202`), across different explicit revisions (`REV A` vs `REV B`), or across unverified revision/variant configurations; never assume issue-date spread alone disproves an explicit shared revision; and never promote single-sheet, undeclared-revision, approximate, OCR, or unbound data to cross-drawing `PASS`.

## 3. Approaches Considered

1. **Selected — Dedicated `cad_agent/marine_knowledge/particulars_consistency.py` consuming V1-A `EngineeringFact` records and returning `marine-check-result-1.0`:** Zero new top-level `cad_agent/*` owners, reuses `validate_check_result`, `validate_engineering_fact`, and `build_marine_core_proposal`, and keeps V0 Skill 3 intact for backward compatibility.
2. **Rejected — Mutating V0 `detect_drawing_gaps_and_conflicts` semantics in place:** Would alter V0 regression contracts and mix CAD drafting checks (text height, bow orientation) with V1-B cross-drawing particulars reconciliation.
