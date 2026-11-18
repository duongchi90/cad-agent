# Marine V1-C Centerline Double-Bottom Minimum Height Rule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver `evaluate_double_bottom_height_rule()` as a single verified conditional rule slice (`RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT`, QCVN 72:2025/BGTVT Phần 2A Chương 2 Clause `2.4.3-2`) backed by native CAD text/DIMENSION evidence binding (V1-A) and multi-sheet comparability verification (V1-B).

**Architecture:** Extend `cad_agent/marine_knowledge/observer.py` with bounded centerline double-bottom height text extraction, non-centerline/unbound disambiguation (`unbound_double_bottom_height_mm`), native `DIMENSION` centerline double-bottom binding (`rebind_double_bottom_dimension_facts`), and single-bottom detection (`single_bottom_evidences`); add `cad_agent/marine_knowledge/conditional_rules.py` implementing `evaluate_double_bottom_height_rule()`; export it from `cad_agent.marine_knowledge`.

**Tech Stack:** Python 3.11, `cad_agent.marine_knowledge.evidence_binding`, `cad_agent.marine_knowledge.particulars_consistency`, `pytest`, `ruff`.

**Spec:** `docs/superpowers/specs/2026-11-18-marine-v1c-double-bottom-rule-design.md`

## Global Constraints

- Do not import `ezdxf` outside `dxf_builder_lib/` (including in `tests/`).
- Do not duplicate `dxf_builder_lib/_dimension_truth.py`; consume V1-A `evaluate_dimension_fact` and `rebind_observation_dimensions`.
- Do not mutate `particulars_consistency.py`, `skills.py`, `contracts.py`, or `evidence_binding.py`.
- Enforce `cad_mutation=False`, `regulatory_compliance_proven=False`, and `CAD_AGENT_DISABLE_MARINE_PACK=1` (`status="DISABLED"`).

## Review Focus

- Native bound text (`750 mm` at `L = 52 m`, `950 mm` at `L = 128 m`) and calibrated native `DIMENSION` (`actual_measurement = 750.0` paired with centerline double-bottom label) -> `PASS` with hash-bound `EngineeringFact`s.
- Negative oracles: `650 mm < 700 mm` at `L = 52 m`, `800 mm < 900 mm` at `L = 128 m`, and `DIMENSION` override `'800'` vs `actual_measurement = 620.0` -> `CONFLICT`.
- Unproven length (`L` missing, bare `Lpp = 52 m`, or `Lwl = 122.0 m` straddling `120.0 m` with `800 mm`) -> `INSUFFICIENT_EVIDENCE`.
- Non-verified provenance (`OCR_ONLY`, bare `'h = 800 mm'`, side/margin `'chieu cao day doi o man = 800 mm'`, `FIXTURE_SUPPLIED` dict without DXF bytes, uncalibrated `$INSUNITS=0`) -> `INSUFFICIENT_EVIDENCE` (never `PASS`).
- Multi-sheet `GA + MCN` -> `PASS` only when `HULL NO` and explicit `REV : 01` match (`COMPARABLE_VERIFIED`); `INSUFFICIENT_EVIDENCE` when `REV` is undeclared or hulls/revisions skew.
- Out-of-scope (`VRH` / `QCVN 21`, `FRP` `QCVN 56`, single-bottom `'tau day don'`) -> `NOT_APPLICABLE`.

---

### Task 1: Single Conditional Rule Slice (`RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT`)

**Files:**
- Create: `docs/superpowers/specs/2026-11-18-marine-v1c-double-bottom-rule-design.md`
- Create: `docs/superpowers/plans/2026-11-18-marine-v1c-double-bottom-rule.md`
- Create: `tests/test_marine_v1c_conditional_rules.py`
- Modify: `cad_agent/marine_knowledge/observer.py`
- Create: `cad_agent/marine_knowledge/conditional_rules.py`
- Modify: `cad_agent/marine_knowledge/__init__.py`

**Interfaces:**
- Produces:
  - `evaluate_double_bottom_height_rule(observations, *, target_regulation="QCVN_72_2025_BGTVT", expected_source_sha256=None, calibration_verified=False, verified_scale_to_mm=None, partial_package=True, enabled=None) -> dict[str, Any]`

- [x] **Step 1: Write executable RED tests in `tests/test_marine_v1c_conditional_rules.py`** covering compliant `L <= 120 m` (text + `DIMENSION`) and `120 < L <= 140 m`, negative conflict oracles (`< 700 mm`, `< 900 mm`, `DIMENSION` override, text-vs-`DIMENSION` discrepancy), unproven `L` / `Lpp`-only / `Lwl` straddle, OCR / unbound / side-margin / fixture / unitless abstentions, multi-sheet comparability gate, statutory/single-bottom `NOT_APPLICABLE`, tampered fact hash & disable toggle, and `@pytest.mark.real_data` `THLT7000 + GA7000` comparison.
- [x] **Step 2: Run pytest on `tests/test_marine_v1c_conditional_rules.py` and capture causal RED log to `D:\Cad agent temp\marine_v1_build_20261118\v1c_red.log`.**
- [x] **Step 3: Implement `observer.py` bounded extraction, `conditional_rules.py`, and `__init__.py` export.**
- [x] **Step 4: Run all `tests/test_marine_*.py` (saving `v1c_green_pre_rebase.log`), `ruff check`, `scripts/check_architecture_boundaries.py`, and LF normalization.**
