# Marine Knowledge Pack V1-A — Engineering Evidence Binding Design

- **Date:** 2026-11-18
- **Status:** CANDIDATE_UNAPPROVED (Stacked on V0 Draft PR `#574` @ `83d4a2a522eeb628558af9f2af0a9db4b1402aee`)
- **Owner:** `cad_agent.marine_knowledge` (reusing `dxf_builder_lib._dxf_snapshot`, `cad_agent.file_integrity`, and `cad_agent.drawing_contracts.canonical_json_sha256`)

## 1. Intent & Problem Statement

Marine V0 (`#574`) recognizes terms, drawing types, and QCVN 72:2025/BGTVT applicability, but stores extracted particulars and structural metrics as flat arrays/scalars without entity-level provenance. On real DXFs (`THLT7000`, `GA7000`), V0:
1. Cannot explain which drawing SHA-256, CAD entity handle(s), entity type (`TEXT`, `MTEXT`, `ATTRIB`, `DIMENSION`), or layer produced a value, nor why it is or isn't trustworthy.
2. Ignores native DXF `DIMENSION` entities (`actual_measurement` vs manual text overrides, unitless `$INSUNITS=0` vs calibrated geometry).
3. Misses two-column Principal Particulars rows (`LENGTH (P.P)` -> `92,40 m`, `LENGTH (O.A)` -> `ABT.` `99,95 m`, `DRAFT (DESIGNED MLD)` -> `7.60 m`).

V1-A introduces a minimal, domain-extensible `engineering-fact-1.0` contract (`domain` = `"marine"` | `"mechanical"` | `"civil"` | ...) without creating any plugin framework or duplicating CAD Core read facades.

## 2. Goals, Non-Goals & Anti-Goals

- **Goals:**
  - Bind every extracted engineering datum to `drawing_id`, `drawing_path` (only when read from a verified file), `drawing_sha256` (when read from raw bytes/file), `sheet_id`, `revision` (`None` unless explicitly present on CAD entities), `entity_handles`, `entity_type`, `layer`, raw/normalized value+unit, `provenance_class`, `verification_state`, and `trust_reason`.
  - Enforce the 6 provenance classes: `NATIVE_CAD_EVIDENCE`, `NATIVE_CAD_UNBOUND_TEXT`, `NATIVE_MEASURED_GEOMETRY`, `OCR_ONLY`, `FIXTURE_SUPPLIED`, `INFERRED_UNVERIFIED`.
  - Extract DXF `DIMENSION` entities via `read_dxf_snapshot`, detecting override-vs-measurement conflicts and `$INSUNITS=0` uncalibrated state fail-closed.
  - Attach `bound_facts` traceability to Skill 2 and Skill 3 findings and provide `audit_engineering_evidence_binding()` + `explain_fact_traceability()`.
- **Non-Goals:** Cross-drawing vessel/revision reconciliation (deferred to V1-B), new statutory rule proliferation (V1-C), multi-view curve geometry (V2-A / PR `#569`), or CAD mutation (V2-D).
- **Anti-Goals:** Never promote `OCR_ONLY`, `NATIVE_CAD_UNBOUND_TEXT`, `FIXTURE_SUPPLIED`, `INFERRED_UNVERIFIED`, approximate (`ABT.`), or uncalibrated `$INSUNITS=0` geometry to `verification_state="VERIFIED"`. Never fabricate `revision` or `drawing_path`.

## 3. Approaches Considered

1. **Selected — Minimal Pure-Python `engineering-fact-1.0` inside `cad_agent/marine_knowledge/evidence_binding.py` + thin `observer.py`/`skills.py` wiring:** Reuses `read_dxf_snapshot`, `open_bound_file`, and `canonical_json_sha256`; adds zero top-level `cad_agent/*` owners, keeps `domain` field generic for future domains, and preserves 100% V0 backward compatibility and `CAD_AGENT_DISABLE_MARINE_PACK=1` toggle.
2. **Rejected — Heavy cross-repo plugin registry / global `EngineeringFactStore`:** Violates anti-expansion rule #9/VII and `check_architecture_boundaries.py` truth-store restrictions.
3. **Rejected — Modifying `cad_agent/cad_read_facade.py`:** `cad_read_facade` is bound to live AutoCAD `CadReadClient` + `R3_CANDIDATE` DARA custody (`#491`); modifying it would risk P0 `#491` interference.

## 4. Contract Summary (`engineering-fact-1.0`)

- **Provenance classes (`6`):** `NATIVE_CAD_EVIDENCE`, `NATIVE_CAD_UNBOUND_TEXT`, `NATIVE_MEASURED_GEOMETRY`, `OCR_ONLY`, `FIXTURE_SUPPLIED`, `INFERRED_UNVERIFIED`.
- **Verification states (`8`):** `VERIFIED`, `PROVISIONAL_APPROXIMATE`, `FIXTURE_UNBOUND_TO_DXF_BYTES`, `UNVERIFIED_UNITLESS`, `CONFLICTING_OVERRIDE`, `UNVERIFIED_UNBOUND_TEXT`, `UNVERIFIED_OCR`, `UNVERIFIED_INFERRED`.
- **Invariant:** `verification_state == "VERIFIED"` requires `provenance_class in {"NATIVE_CAD_EVIDENCE", "NATIVE_MEASURED_GEOMETRY"}`, 64-hex `drawing_sha256`, non-empty `entity_handles`, known/calibrated unit, no `ABT.` approximate qualifier, and no dimension override conflict.
