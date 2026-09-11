# Current-Main Candidate/Build Identity Binding — Iteration 81

Date: 2026-09-11 (Asia/Saigon)
Canonical main SHA: `e8fc0092ee46750e50de0ea408fd91811cae10c2`
Executor branch: `codex/audit-text-style-compat-20260910`

## Authority and exact scope

SOL's iteration-80 decision was:

```text
VERDICT=CLEAR_CONTINUE
NEXT_SINGLE_BOUNDED_ACTION=Perform exactly one read-only candidate/build
identity-binding oracle on the fresh iteration-80 output using the page-1
staged DXF/build-evidence pair. Recompute SHA256 values and verify binding to
the source, calibration/profile, page, and exact current-main context.
Stop at this gate.
HUMAN_GATE=NO
```

No artifact was edited. The inspected manifest was:

`C:/temp/cad-agent-real-pdf-current-main-iter80-run/staged/pdf-run-manifest.json`

Manifest SHA-256:

`f7c7b1afbd52f8f504dafbcb9b6efb416ee332b88260a01aea2414ab9d650eaf`

The exact page-1 pair was:

- DXF:
  `C:/temp/cad-agent-real-pdf-current-main-iter80-run/staged/dxf/page_01.dxf`;
- build evidence:
  `C:/temp/cad-agent-real-pdf-current-main-iter80-run/staged/build_evidence/page_01.json`.

## Read-only identity checks

All of these checks passed:

- actual page-1 DXF SHA-256:
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`;
- the actual DXF SHA matched both the manifest page-1 stage and the
  build-evidence `dxf.sha256`;
- `build_result.output_path` resolved to the exact staged page-1 DXF;
- actual build-evidence SHA-256:
  `16053d029396a8efc029001991068207c60e4484538eb1f21a765dec2250d659`;
- the actual build-evidence SHA matched the manifest page-1 stage;
- page identity matched `page=1`, `page_01.dxf`, and `page_01.json`;
- the manifest source SHA matched the pre-bound context and the approved source
  bytes:
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`;
- calibration reference, scale `7.055555555556` mm/px, and DPI `144` matched
  the pre-bound context;
- `release_profile=DRAFT_REFERENCE` and
  `authoritative_release_eligible=false` matched the pre-bound context;
- exact current-main context matched: main SHA
  `e8fc0092ee46750e50de0ea408fd91811cae10c2`, clean detached worktree, exact
  output root, and completed iteration-80 oracle context.

The machine-readable check record is outside Git at:

`C:/temp/cad-agent-real-pdf-current-main-iter80-run/candidate-build-identity-binding-iteration81.json`

## Classification and limits

- `CURRENT_MAIN_CANDIDATE_BUILD_EXACT_IDENTITY_BINDING=PROVEN_CURRENT` as a
  composed binding across the exact manifest, page-1 pair, and pre-bound
  current-main oracle context.
- The build-evidence schema itself is `schema_version=1.0` and contains only
  `dxf` and `build_result`; it does not directly repeat source SHA or execution
  context fields. Those identities were verified through the exact manifest
  stage hash and pre-bound context, not inferred from absent fields.
- The release remains draft/non-authoritative. No DARA/R3/R4, AutoCAD/FileIPC,
  setup/readback, persistence/reopen, visual, dimension, provider, M2, source,
  candidate, DXF, or production-code action was performed.
- The source remained unchanged and this read-only oracle performed no mutation.
