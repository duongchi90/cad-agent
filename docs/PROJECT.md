# CAD Agent Project

## Goal

Convert an approved real CAD image or PDF into a reviewable DXF, validate it
headlessly, open it in AutoCAD Mechanical 2027, and produce reproducible evidence for every
stage.

## Supported environment

- Windows
- Python 3.11
- AutoCAD Mechanical 2027
- Tesseract 5.4.0.20240606

Other operating systems, Python versions, and AutoCAD products are not release
evidence for this project.

## Product principles

- Incremental hardening: preserve verified code and refactor only against a
  failing test, benchmark, or measured integration problem.
- Deterministic rules first; AI supports ambiguous recognition and review.
- Human approval is mandatory for unverified calibration, ambiguous decisions,
  and production DXF mutation.
- Private drawings and annotations remain outside Git.
- A missing private/live gate is reported as skipped or not run, never passed.

## First product milestone

One approved real image or PDF runs through Primitive IR, Semantic IR, optional
agent advice, DXF build/headless review, and AutoCAD Mechanical 2027 live review/repair. The
run records input hash, configuration, artifacts, approvals, and test evidence.

## Modernization slices

1. Reproducible foundation: canonical guidance, locked environment, shared
   verification, explicit gates, and immutable CI.
2. Thin vertical-slice CLI: `doctor`, `run`, and `resume`, with manifests,
   checkpoints, approval gates, and no duplicated domain algorithms.
3. Private real-data benchmark normalization and evidence-driven algorithm
   hardening.
4. Windows/AutoCAD Mechanical 2027 production review-repair loop, backup policy, live smoke,
   and release checklist.

Each slice receives its own approved design, implementation plan, tests, and
review gate.

## Non-goals

- No GUI, web service, or VPS.
- No Linux or macOS production support.
- No AutoCAD product/version support beyond AutoCAD Mechanical 2027.
- No rewrite of the five existing implementation packages.
- No automatic production mutation without human approval.

## Canonical references

- Current architecture: `docs/ARCHITECTURE.md`
- Verified status: `docs/STATUS.md`
- Quality and release gates: `docs/QUALITY.md`
- Design/plan record policy: `docs/superpowers/README.md`
