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
  - `contracts.py`: fail-closed schema + hash validators (`cad_mutation=False`, `regulatory_compliance_proven=False`, non-empty provenance)
  - `manifest.py`: external source metadata & SHA-256 inventory (excluding non-marine road-vehicle docs; no binary source files committed)
  - `text_normalization.py`: idempotent MTEXT control-stripper, TCVN3->Unicode converter, accent-folded search normalization
  - `knowledge_data.py`: 26 bilingual terms and 10 conditional engineering rules with exact clause/page citations
  - `pack.py`: sealed pack loader, bilingual term lookup, conditional rule query, and `CAD_AGENT_DISABLE_MARINE_PACK=1` disable switch
  - `observer.py`: read-only DXF / dictionary normalizer extracting particulars, title blanks, A.P/F.P anchors, and ACAD XDATA `.Vn*` fonts
  - `skills.py`: Skill 1 (`classify_marine_drawing`), Skill 2 (`evaluate_regulation_applicability_and_submittal`), Skill 3 (`detect_drawing_gaps_and_conflicts`), and non-mutating `build_marine_core_proposal`

## Non-Goals and Safety Boundaries

- No vector database, external agent runtime, plugin framework, or duplicate CAD/DXF/OCR package.
- Never promotes OCR-only input or unitless (`$INSUNITS=0`) drawings without verified calibration to `PASS`.
- Never default-applies `QCVN 72:2025/BGTVT` without confirmed inland scope; `OCEAN_GOING` vessels report `NOT_APPLICABLE` referencing `QCVN 21:2015/BGTVT`.
- Never condemns unprovided companion sheets when `partial_package=True`.
