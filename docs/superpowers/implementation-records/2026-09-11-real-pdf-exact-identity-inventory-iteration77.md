# Real-PDF Exact-Identity Acceptance Inventory — Iteration 77

Date: 2026-09-11 (Asia/Saigon)
Canonical branch inspected: `origin/main`
Canonical main SHA: `e8fc0092ee46750e50de0ea408fd91811cae10c2`
Issue: `#409` — Phase 4 Real Mechanical source to verified editable CAD acceptance

## Authority and boundary

SOL authorized exactly one read-only identity inventory for the real-PDF lane:

```text
source SHA -> run-pdf manifest/stage -> candidate/build -> DARA/R3/R4
-> setup/readback -> persistence/reopen -> visual -> dimension
```

Each gate is classified only as `PROVEN_CURRENT`,
`PROVEN_OTHER_IDENTITY`, or `NOT_PROVEN`. The inventory stops at the first
unproven current-main gate. No AutoCAD, FileIPC, provider, source/candidate/DXF
mutation, retry, or production-code change was performed.

## Identity evidence

### Source

- Approved private source name: `202607092308.pdf`.
- Current workstation SHA-256:
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.
- This matches the approved source SHA recorded by the repository's canonical
  real-PDF evidence.
- Classification: `PROVEN_CURRENT` for the source identity.

### Historical run-pdf manifest/stage

- Private evidence root:
  `C:/temp/cad-agent-real-p1-20260908-01`.
- Outer manifest:
  `pdf-run-manifest.json`, SHA-256
  `90fc43a14dcd52517de273f98e57bc7c1b860c86257cc406080180176953b261`.
- The manifest binds the same source SHA, approved calibration reference
  `STATUS-e48f3970-144dpi-1to40`, `144` DPI, and
  `7.055555555556` mm/px. It records all 9 pages and 36/36 render, Primitive
  IR, Semantic IR, DXF, and build-evidence stages completed.
- The manifest has no code commit, owner source hash, or current-main identity
  field. The repository status identifies this evidence as historical P1
  evidence around commit `973b6151da34d20adc1d7b399e37eb20920abb7a`, while
  fresh `origin/main` is `e8fc0092ee46750e50de0ea408fd91811cae10c2`.
- Relevant run owners changed between those identities, including
  `cad_agent/cli.py`, `cad_agent/drawing_contracts.py`,
  `cad_agent/drawing_setup.py`, `cad_agent/fidelity.py`,
  `mcp_integration_lib/mcp_dispatch.lsp`, and
  `primitive_ir_lib/dimension_observer.py`.
- Classification: `PROVEN_OTHER_IDENTITY` only.

## First unproven gate and stop condition

```text
FIRST_UNPROVEN_GATE=SOURCE_SHA_BOUND_RUN_PDF_MANIFEST_STAGE_ON_CURRENT_MAIN
CLASSIFICATION=PROVEN_OTHER_IDENTITY
```

The source hash and historical run artifacts are real and internally
consistent, but they do not prove that the same source-to-stage chain was
executed by fresh `origin/main`. The inventory therefore stops here.

The later candidate/build, DARA/R3/R4, setup/readback, persistence/reopen,
visual, and dimension gates are recorded as `NOT_PROVEN` for the current-main
identity; no historical artifact is promoted across this identity boundary.

This is an evidence/currentness finding, not a code defect. A future bounded
action must first create or recover a current-main source-to-run-pdf identity
binding before any later acceptance gate is consumed.
