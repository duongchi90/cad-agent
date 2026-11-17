# Marine V1-A Engineering Evidence Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind extracted marine engineering particulars, structural metrics, and native DXF `DIMENSION` measurements to verifiable CAD entity handles, file SHA-256 provenance, and fail-closed verification states (`engineering-fact-1.0`).

**Architecture:** Add `cad_agent/marine_knowledge/evidence_binding.py` and `contracts/marine-knowledge/engineering-fact.schema.json`, reusing `cad_agent.file_integrity.open_bound_file`, `cad_agent.drawing_contracts.canonical_json_sha256`, and `dxf_builder_lib._dxf_snapshot.read_dxf_snapshot`. Extend `observer.py` to collect DXF `DIMENSION` entities, pair two-column table handles, preserve bound `drawing_sha256`/non-fabricated `revision`, and emit `engineering_facts`; extend `skills.py` to surface `bound_facts` traceability and `DIMENSION` override conflicts while preserving `CAD_AGENT_DISABLE_MARINE_PACK=1`.

**Tech Stack:** Python 3.11, `dxf_builder_lib._dxf_snapshot`, `cad_agent.file_integrity`, `cad_agent.drawing_contracts`, `pytest`, `ruff`.

**Spec:** `docs/superpowers/specs/2026-11-18-marine-v1a-evidence-binding-design.md`

## Global Constraints

- Supported environment: Windows, Python 3.11; zero new dependencies outside `requirements/windows-py311.lock`.
- Do not import `ezdxf` outside `dxf_builder_lib/` or `cv2`/`pytesseract` outside `primitive_ir_lib/`.
- Never promote `OCR_ONLY`, `NATIVE_CAD_UNBOUND_TEXT`, `FIXTURE_SUPPLIED`, `INFERRED_UNVERIFIED`, `ABT.` approximate values, or uncalibrated `$INSUNITS=0` geometry to `VERIFIED`.
- Never fabricate `revision`, `sheet_id`, `drawing_path`, or `drawing_sha256` when absent from source data.
- `CAD_AGENT_DISABLE_MARINE_PACK=1` disables all Marine V1-A entrypoints cleanly without side effects.

## Review Focus

- Forged `VERIFIED` state on `OCR_ONLY`, `FIXTURE_SUPPLIED`, `NATIVE_CAD_UNBOUND_TEXT`, or missing `drawing_sha256` -> must raise `MarineKnowledgeError`.
- Native DXF `DIMENSION` with MTEXT formatting override (`{\f.VnArial|...;\C2;1200}` vs `actual_measurement=1241.31`) -> must strip formatting codes, detect mismatch, set `CONFLICTING_OVERRIDE`, and emit `CONFLICT` in gap audit.
- Unitless DXF (`$INSUNITS=0`) `DIMENSION` with `'1.30'` or `'17,50m'` text without verified calibration -> must be `UNVERIFIED_UNITLESS` (not false `VERIFIED` and not false override conflict across 1000x m/mm scale), upgrading to `VERIFIED` (or `CONFLICTING_OVERRIDE` if `>1.5%` off) only when `calibration_verified=True` and `verified_scale_to_mm > 0`.
- Two-column Principal Particulars rows with intermediate tokens (`LENGTH (O.A)` + `ABT.` + `99,95 m`; `DEPTH (MLD)` + `UPPER DECK` + `9,60 m`) -> must bind all contributing handles and mark `ABT.` rows `PROVISIONAL_APPROXIMATE`.
- Symlink / Windows reparse point passed to `observe_dxf_file()` -> must fail closed via `open_bound_file`.

---

### Task 1: Contract, DXF Observation Binding & Traceable Audit (`V1-A`)

**Files:**
- Create: `contracts/marine-knowledge/engineering-fact.schema.json`
- Create: `cad_agent/marine_knowledge/evidence_binding.py`
- Modify: `cad_agent/marine_knowledge/observer.py`
- Modify: `cad_agent/marine_knowledge/skills.py`
- Modify: `cad_agent/marine_knowledge/__init__.py`
- Test: `tests/test_marine_v1a_evidence_binding.py`

**Interfaces:**
- Produces:
  - `ENGINEERING_FACT_SCHEMA_VERSION = "engineering-fact-1.0"`
  - `PROVENANCE_CLASSES: frozenset[str]` (`6` classes)
  - `VERIFICATION_STATES: frozenset[str]` (`8` states)
  - `build_engineering_fact(...) -> dict[str, Any]`
  - `validate_engineering_fact(payload: object) -> dict[str, Any]`
  - `explain_fact_traceability(fact: Mapping[str, object]) -> dict[str, Any]`
  - `audit_engineering_evidence_binding(observations, *, calibration_verified=False, verified_scale_to_mm=None, enabled=None) -> dict[str, Any]`

- [ ] **Step 1: Write causal RED tests in `tests/test_marine_v1a_evidence_binding.py`** covering contract validation, 6 provenance classes, real-style DXF `DIMENSION` + two-column table extraction, non-fabricated `revision`, symlink/tamper refusal, and finding traceability.
- [ ] **Step 2: Run pytest on `tests/test_marine_v1a_evidence_binding.py` and confirm causal RED.**
- [ ] **Step 3: Implement `engineering-fact.schema.json`, `evidence_binding.py`, and wire `observer.py`, `skills.py`, and `__init__.py`.**
- [ ] **Step 4: Run focused pytest (`tests/test_marine_v1a_evidence_binding.py` + `tests/test_marine_knowledge_*.py`), V0 vs V1-A real-DXF comparison, and full repo gates.**
- [ ] **Step 5: Commit cleanly onto `anti/marine-v1a-evidence-binding`, push, open stacked Draft PR, and verify 5/5 hosted CI checks.**
