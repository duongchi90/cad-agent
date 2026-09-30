# CAD Agent Project

## Product baseline

CAD Agent is a Windows engineering workflow for reading modified source drawings,
reusing the ORIGINAL native CAD BASE, applying only source-supported changes to a
disposable candidate, and proving an editable persisted result in AutoCAD Mechanical
2027. Fresh GitHub wins over cached status, historical plans, and local checkouts.

The product roadmap is [#291](https://github.com/duongchi90/cad-agent/issues/291).
The authorized cumulative BVTL product run is accepted and closed in
[#461](https://github.com/duongchi90/cad-agent/issues/461#issuecomment-5915471764).
This acceptance covers eight modifications on one candidate copied from ORIGINAL
BASE, including native geometry, dimensions/annotations, hatch representation,
protected-state comparison, editability, and save/reopen/readback. Historical target
DXFs and prior candidates are evidence, never generation inputs.

## What is packaged and what is orchestrated

Current main contains source/provenance validators, geometry and dimension
inspection, native CAD query/edit interfaces, FileIPC/.NET dispatch, staged DXF
tools, and regression infrastructure. The accepted cumulative run also uses the
authorized local executor's source reasoning and bounded native COM/AutoLISP
operations. It is not evidence of a single unattended CLI that solves arbitrary
drawings. New drawings require source-specific scope and acceptance evidence.

The image/PDF -> Primitive IR -> Semantic IR -> staged DXF pipeline remains
available for inspection, reconstruction experiments, and regression. Its output
does not acquire the native workflow's acceptance merely by being generated.
Optional provider experiments are separate; PR #340 remains frozen. A completed
BVTL run does not authorize another product phase or provider/billing work.

## Supported environment

- Windows
- Python 3.11
- AutoCAD Mechanical 2027
- Tesseract 5.4.0.20240606

## Product principles

- Incremental hardening: existing owner plus the smallest necessary surface.
- Source and ORIGINAL BASE identity precede candidate mutation.
- Preserve source, BASE, accepted DWGs, manifests, hashes, and audit evidence.
- Geometry/visual evidence precedes applicable dimension/text checks; finish
  editability/readback, save/reopen, and deterministic verification on the same candidate.
- Missing prerequisites, uncertainty, `SKIP`, and `NOT RUN` never become PASS.
- Runtime changes need causal/reachability evidence and the applicable independent
  exact-head Security and Integration review under #305/#392/#429.
- No GUI, web service, or VPS is part of this supported baseline.

## Canonical references and history

- Current owners: `docs/ARCHITECTURE.md`
- Accepted product/evidence routing: `docs/STATUS.md`
- Verification: `docs/QUALITY.md`; `scripts/bootstrap.ps1`; `scripts/verify.ps1`
- Execution authority: latest #305/#429 and `docs/AI_OPERATING_MODEL.md`
- Historical design/plan policy: `docs/superpowers/README.md`
- Prior project snapshot: [historical PROJECT](history/project-before-bvtl-consolidation.md)

The historical Drawing Initialization Gate and M0-M8/R0-R8 plans remain records of
their own contracts and tests. Unchecked tasks and old frontier statements are not
the current product queue. Fresh #291 and accepted #461 define this closure.
