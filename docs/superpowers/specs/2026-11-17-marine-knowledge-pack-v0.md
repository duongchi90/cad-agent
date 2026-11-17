# Marine Knowledge Pack V0 Design and Reuse Summary

- Approval / design date: 2026-11-17
- Status: candidate implementation (`CANDIDATE_UNAPPROVED`), read-only advisory plugin layer pending Luna review and merge on Draft PR
- Supported scope: Windows, Python 3.11, offline CAD observation / engineering advisory over Vietnam inland waterway (`QCVN 72:2025/BGTVT`) and general naval shipbuilding drafting conventions (`LINES_PLAN`, `GENERAL_ARRANGEMENT`, `MIDSHIP_STRUCTURAL`, `BASIC_STRUCTURAL`)

## Architecture and Shortest-Path Reuse

1. Reuses `cad_agent.drawing_contracts.canonical_json_sha256` and pure-Python contract validation style without adding `jsonschema` or runtime dependencies.
2. Reuses `contracts/drawing-setup/domain-pack.schema.json` identifier and SHA-256 discipline while keeping `status` restricted to `CANDIDATE_UNAPPROVED` / `DRAFT_REVIEW_ONLY` so unapproved knowledge cannot impersonate an `APPROVED` CAD Core domain pack.
3. Reuses `dxf_builder_lib._dxf_snapshot.read_dxf_snapshot` inside `cad_agent/marine_knowledge/observer.py` so `ezdxf` stays strictly confined to `dxf_builder_lib/`.
4. Zero changes to CAD Core geometry/dimension behavior, `#491` pipelines, `cli.py`, or FileIPC / AutoCAD live runtime.

## Components Added

- Contracts: `contracts/marine-knowledge/{source-manifest,marine-knowledge-pack,marine-check-result}.schema.json`
- Package `cad_agent/marine_knowledge/`:
  - `contracts.py`: fail-closed schema + hash validators (`cad_mutation=False`, `regulatory_compliance_proven=False`, non-empty provenance), proposal structural checks, and `verify_source_citation` returning explicit `verification_states` (`MANIFEST_MATCH` / `SOURCE_BYTES_VERIFIED` / `PAGE_VERIFIED` / `CLAUSE_CONTENT_VERIFIED` vs `METADATA_ONLY`)
  - `manifest.py`: external source metadata & SHA-256 inventory (excluding non-marine road-vehicle docs; no binary source files committed)
  - `text_normalization.py`: idempotent MTEXT control-stripper, TCVN3->Unicode converter, accent-folded search normalization, bounded input guard
  - `knowledge_data.py`: 26 bilingual terms (including QCVN 72 rule length `L` vs `Lpp` distinction) and 10 conditional engineering rules with exact clause/page citations (including QCVN 72 Clause `3.7.21` p.172/188)
  - `pack.py`: sealed pack loader, bilingual term lookup, conditional rule query, and `CAD_AGENT_DISABLE_MARINE_PACK=1` disable switch
  - `observer.py`: read-only DXF / dictionary normalizer extracting separated `L`/`Lpp`/`Lwl`, particulars with unit verification, `metric_provenance`, title blanks, A.P/F.P anchors, negated-scope & lifeboat guards, bound structural plate thickness (`s=`/`t=`), corrupted numeric token detection, non-marine markers, and ACAD XDATA `.Vn*` fonts
  - `skills.py`: Skill 1 (`classify_marine_drawing`), Skill 2 (`evaluate_regulation_applicability_and_submittal`), Skill 3 (`detect_drawing_gaps_and_conflicts`), and hardened non-mutating `build_marine_core_proposal`

## Non-Goals, Adversarial Hardening, and Safety Boundaries

- No vector database, external agent runtime, plugin framework, or duplicate CAD/DXF/OCR package.
- Never promotes OCR-only input, corrupted OCR numerics (`52.O5`), unbound plate text, missing length `L`/`Lpp`, empty geometric shells (`0` CAD primitives), or unitless (`$INSUNITS=0`) drawings without BOTH `calibration_verified=True` and positive finite `verified_scale_to_mm` to `PASS`.
- Enforces `L` vs `Lpp` boundary ambiguity fail-closed behavior near QCVN 72 statutory thresholds (`20m`, `40m`, `60m`, `80m`, `120m`, `140m`) when explicit rule length `L`/`Lwl` is absent, and forbids `PASS` when zero structural checks (`RULE_MK_08`/`09`/`10`) actually executed.
- Separates non-marine domain artifacts (`NOT_APPLICABLE`, `candidate_referred_regulation=None`), bare free-text `OCEAN GOING` labels (`INSUFFICIENT_EVIDENCE`), and verified Clause 1.1.1 statutory exclusions (`NOT_APPLICABLE` mapped accurately to `QCVN 21`/`56`/`84`/`54`).
- Never condemns unprovided companion sheets when `partial_package=True`.
- Verified via Two-Part internal A/B evaluation (`tests/test_marine_knowledge_ab.py` + `tests/test_marine_knowledge_adversarial.py`): Part A functional regression (`DISABLED` vs `ENABLED`) and Part B internal developer-authored regression comparison (`Generic CAD Baseline Inspector` vs `Marine Knowledge Pack V0` over 16 synthetic fixtures — not an independent or blind benchmark).
- Source-correctness hardening:
  - `verify_source_citation()` never promotes caller-supplied `page_texts` without verified SHA-256 source bytes; `SOURCE_CONTENT_VERIFIED` requires SHA-256 match plus page bounds, clause anchor (body text or PDF outline), and `verbatim_excerpt` verified directly against extracted bytes.
  - QCVN 72:2025/BGTVT scope separates Clauses `1.1.1` (design length `L <= 140 m`, QCVN 21/25), `1.1.2` (special replacement regulations `QCVN 50/51/56/84/54/55`), `1.1.4` (non-mandatory defense/security/fishing vessels; `INSUFFICIENT_EVIDENCE` if mixed with inland markers), and Clause `1.4.43-1` regulatory `L` vs bare `Lpp` (never issues `NOT_APPLICABLE` or `PASS` from unproven `Lpp` alone).
