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
agent advice, DXF build/headless review, and AutoCAD Mechanical 2027 live
review. If review finds a confirmed production defect, the separately approved
repair/rollback loop is available; a passing review is never mutated merely to
exercise repair. The run records input hash, configuration, artifacts,
approvals, and test evidence.

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

## Drawing Initialization Gate

The configurable Drawing Initialization Gate is the required entry boundary for
future authoritative drawing paths. It binds an approved Drawing Definition,
Drawing Profile, Domain Pack, and template provenance to a read-only setup
audit before any geometry is created. The existing image/PDF pipeline remains
`DRAFT_REFERENCE`; it cannot become authoritative until a separate
dimension-first path presents hash-bound `SETUP_VERIFIED` evidence. This gate
does not make a source-specific vehicle or equipment configuration part of the
core product contract.

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
- Approved complete design: `docs/superpowers/specs/2026-08-02-cad-agent-complete-design.md`
- M2 execution plan: `docs/superpowers/plans/2026-08-02-m2-drawing-initialization-gate.md`
