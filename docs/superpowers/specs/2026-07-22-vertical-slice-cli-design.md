# Thin Vertical-Slice CLI Design

**Status:** Approved by the user on 2026-07-22

**Target:** Windows, Python 3.11, AutoCAD LT

## Goal

Provide one small `python -m cad_agent` command surface that makes the existing
image-to-DXF path reproducible and resumable.  It owns run metadata, durable
checkpoints, input integrity, and explicit approval recording; it delegates all
recognition, semantic, solving, DXF build, and headless-review work to the
existing packages.

## Scope

- `doctor` reports the supported Python/Tesseract prerequisites and installed
  dependency versions without changing the repository.
- `run` accepts one raster drawing image, a verified manual scale, and a
  non-empty operator calibration approval reference.  It writes Primitive IR,
  Semantic IR, a staged DXF, and a JSON manifest in a selected output folder.
- `resume` verifies the supplied source file SHA-256 against the manifest and
  performs only pending or failed deterministic stages.
- Every completed stage records its relative artifact path and SHA-256.  Each
  manifest update is written atomically.

## Safety decisions

- The command refuses automatic calibration.  The existing auto-calibration
  APIs remain available for investigation, but a production-oriented
  orchestrator must not turn an unverified candidate into staged DXF output.
- `--calibration-approval` is mandatory and is recorded verbatim as the
  operator's approval reference.  The CLI does not infer approval from a scale
  value.
- The slice does not call `agent_lib.apply_agent_report`, File IPC, Reviewer #2,
  Repair #1/#2, or AutoCAD LT.  Its DXF is a staged artifact only; production
  mutation remains behind the documented live-review, backup, and human
  approval gate.
- Input absolute paths are not persisted in the manifest.  The source name and
  SHA-256 are sufficient for resumability while avoiding needless disclosure
  of operator workstation layout.

## Boundary and data flow

```text
image + approved manual scale
  -> primitive_ir_lib.run_image.run
  -> semantic_ir_lib.assemble.build_semantic_document
  -> prune_constraints / solve_constraints
  -> dxf_builder_lib.build_dxf / review_dxf
  -> run-manifest.json checkpoints
```

`cad_agent` contains no geometry, OCR, calibration, constraint, DXF, or
AutoCAD algorithms.  A failed stage is recorded with a concise error and can
be retried through `resume` after the operator corrects the external cause.

## Acceptance criteria

1. A deterministic synthetic drawing can run end to end and produce a manifest
   whose three stages have integrity hashes and completed states.
2. Re-running through `resume` does not redo completed stages.
3. A changed source file is rejected before any resume work starts.
4. The CLI rejects absent approval and never invokes live AutoCAD or agent
   mutation APIs.
5. The focused tests and `scripts/verify.ps1` pass on Windows/Python 3.11.

## Out of scope

- PDF orchestration (the existing `primitive_ir_lib.run_pdf` remains the
  supported page-rendering entry point).
- Private benchmark normalization, AutoCAD LT live execution, production DXF
  repair/mutation, GUI/web service, and changes to the five domain packages.
