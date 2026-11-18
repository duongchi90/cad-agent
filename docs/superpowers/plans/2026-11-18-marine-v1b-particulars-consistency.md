# Marine V1-B Engineering Particulars Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver `evaluate_particulars_consistency()` producing a Cross-Drawing Engineering Consistency Report that verifies vessel/revision comparability and separates true cross-sheet conflicts from unit differences, `Loa`/`L`/`Lpp`/`Lwl` concept differences, missing values, approximate/schema-mismatched entries, unbound/OCR notes, and revision skew.

**Architecture:** Add `cad_agent/marine_knowledge/particulars_consistency.py`, enrich `observer.py` with title-block vessel-mission (`tàu hàng - khách` vs `tàu hàng - thực tạp`), issue-date (`MM/YYYY`), and design-variant (`phương án III`) extraction into `drawing_evidence`/`engineering_facts`, and export `evaluate_particulars_consistency` + `parse_structured_main_engine` from `cad_agent.marine_knowledge`. Output conforms strictly to `marine-check-result-1.0`.

**Tech Stack:** Python 3.11, `cad_agent.marine_knowledge.evidence_binding`, `pytest`, `ruff`.

**Spec:** `docs/superpowers/specs/2026-11-18-marine-v1b-particulars-consistency-design.md`

## Global Constraints

- Reuse V1-A `EngineeringFact` validation (`validate_engineering_fact`) fail-closed; reject tampered pre-normalized facts.
- Do not modify `CAD Core`, `#491`, `#569`, `#570`, `#574`, or `#575`.
- Respect `CAD_AGENT_DISABLE_MARINE_PACK=1` (`status="DISABLED"`).
- Never claim `PASS` on a single drawing (`len(obs_list) < 2` -> `INSUFFICIENT_EVIDENCE`), unverified vessel identity (no shared `hull_no` or project code), revision skew, or OCR/unbound inputs.

## Review Focus

- Two different vessels (`HULL NO : YN-101` vs `HULL NO : YN-202`) with different `Lpp` -> comparability gate must block comparison (`DIFFERENT_VESSEL`, `INSUFFICIENT_EVIDENCE` / `F_NOT_COMPARABLE_DIFFERENT_VESSEL`), never emitting false `F_PARTICULAR_CONFLICT_LPP`.
- Same vessel (`HULL NO : YN-101`) with `REV : A` vs `REV : B` and changed `T` -> must report `DIFFERENT_REVISION` (`INSUFFICIENT_EVIDENCE` `F_REVISION_SKEW_NOT_COMPARABLE`), not same-revision `CONFLICT`.
- Unit difference (`52.00 m` on GA vs `52000 mm` on Midship) and compatible distinct length concepts (`Loa = 99.95 m`, `Lpp = 92.40 m`, `L = 94.00 m`) -> must be `CONSISTENT` / `COMPATIBLE_CONCEPTS` (`PASS`), whereas `Lpp = 95.00 m` > `Loa = 90.00 m` or `L = 55.00 m` > `Lwl = 52.00 m` -> `CONFLICT`.
- Main engine model-only (`6 S35MC`) vs power-only (`4040 kW (5500 cv)`) -> must be `AMBIGUOUS_SCHEMA` (`INSUFFICIENT_EVIDENCE`), whereas `4040 kW` vs `1200 kW` or `6 S35MC` vs `8 S50MC` or `1 set` vs `2 sets` -> `CONFLICT`.
- Unbound CAD text note (e.g., stray note mentioning `B = 12.00 m` marked `NATIVE_CAD_UNBOUND_TEXT` or `OCR_ONLY`, or bulkhead count on a `LINES_PLAN`) -> must not trigger false `CONFLICT` or false `PASS`.

---

### Task 1: Cross-Drawing Particulars Consistency Engine (`V1-B`)

**Files:**
- Create: `cad_agent/marine_knowledge/particulars_consistency.py`
- Modify: `cad_agent/marine_knowledge/observer.py`
- Modify: `cad_agent/marine_knowledge/__init__.py`
- Test: `tests/test_marine_v1b_particulars_consistency.py`

**Interfaces:**
- Produces:
  - `parse_structured_main_engine(raw_text: str) -> dict[str, Any]`
  - `verify_package_comparability(obs_list: Sequence[Mapping[str, Any]]) -> dict[str, Any]`
  - `evaluate_particulars_consistency(observations, *, calibration_verified=False, verified_scale_to_mm=None, partial_package=True, enabled=None) -> dict[str, Any]`

- [ ] **Step 1: Write causal RED tests in `tests/test_marine_v1b_particulars_consistency.py`** covering comparability gates, all 6 non-conflict disambiguations, physical length/draft ordering violations, structured engine comparison, adversarial tampering, and real `Marine-7000` DXFs (`THLT7000` + `GA7000`).
- [ ] **Step 2: Run pytest on `tests/test_marine_v1b_particulars_consistency.py` and confirm causal RED.**
- [ ] **Step 3: Implement `particulars_consistency.py` and wire `observer.py` + `__init__.py`.**
- [ ] **Step 4: Run focused pytest, V0 vs V1-A vs V1-B real-DXF comparison, and full repo gates.**
- [ ] **Step 5: Commit onto `anti/marine-v1b-particulars-consistency`, push, open stacked Draft PR targeting `anti/marine-v1a-evidence-binding`, wait for hosted CI, and post review packet.**
