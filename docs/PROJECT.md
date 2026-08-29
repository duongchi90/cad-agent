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
- Prefer an existing owner/API or a thin adapter before creating a new
  top-level contract, registry, state machine, transport, executor, or
  publisher.
- New architecture must answer a measured failure or operational bottleneck;
  hypothetical future complexity alone is not implementation authority.

## First product milestone

One approved real image or PDF runs through Primitive IR, Semantic IR, optional
agent advice, DXF build/headless review, and AutoCAD Mechanical 2027 live
review. If review finds a confirmed production defect, the separately approved
repair/rollback loop is available; a passing review is never mutated merely to
exercise repair. The run records input hash, configuration, artifacts,
approvals, and test evidence.

## Active Lean Roadmap

The owner-approved forward roadmap is deliberately product-first. Historical
R*, P*, VS-T*, M*, S* and similar labels remain evidence and traceability, but
they are not an automatic daily execution queue. A historical slice is
reactivated only by a fresh current Issue or valid control authority that ties
it to the active milestone and exact first unsatisfied gate.

1. **M0 — Stabilize the Pipe.** Finish the current control/execution repair,
   make successor-ledger dispatch/ACK/terminal routing dependable on default
   `main`, retain one canonical AutoCAD request/result path, and return hosted
   CI/reuse to a truthful green state without weakening intentional negative
   oracles.
2. **M1 — Golden Path.** Run one approved disposable drawing end to end through
   the existing engine, native editable candidate generation, AutoCAD
   Mechanical review, deterministic verification, and a truthful final
   candidate state. Do not require a generic registry/revision/publisher layer
   unless this path proves one is missing.
3. **M2 — Benchmark.** Exercise a small varied disposable/approved case set and
   measure end-to-end success, wall-clock, Human intervention, unresolved
   engineering inputs, geometry/dimension/visual defects, transport failures,
   and repair demand. Generalize only from measured failures.
4. **M3 — Repair Loop.** Add or integrate bounded repair only for repeatable
   failures demonstrated by M1/M2 evidence. Preserve approval, source
   immutability, fresh post-repair verification, and rollback.
5. **M4 — Production Hardening.** Add private-data, production save/reopen,
   verified promotion/publication, recovery, and stronger audit/security only
   when disposable reliability and production risk justify them.

## Five-SOL responsiveness

The five staggered SOL control roles remain intentionally enabled. Their purpose
is low-latency autonomous governance and SOL↔Luna progression when the Human
Owner is away from the machine. The writer-lease/control-ledger protocol remains
the collision-prevention mechanism; this product simplification does not reduce
SOL cadence or safety.

## Drawing Initialization Gate

The configurable Drawing Initialization Gate remains the required entry
boundary for future authoritative drawing paths. It binds an approved Drawing
Definition, Drawing Profile, Domain Pack, and template provenance to a read-only
setup audit before any geometry is created. The existing image/PDF pipeline
remains `DRAFT_REFERENCE`; it cannot become authoritative until a separate
dimension-first path presents hash-bound `SETUP_VERIFIED` evidence. This gate
does not make a source-specific vehicle or equipment configuration part of the
core product contract.

The Lean Rebaseline does not require future work to create more setup artifacts
when an accepted existing owner can enforce the same invariant safely.

## Non-goals

- No GUI, web service, or VPS.
- No Linux or macOS production support.
- No AutoCAD product/version support beyond AutoCAD Mechanical 2027.
- No rewrite of the five existing implementation packages.
- No automatic production mutation without human approval.
- No second OCR engine, solver, DXF writer, AutoCAD transport/dispatcher,
  repair executor, manifest truth store, visual verdict authority, or
  publication truth store.
- No big-bang migration merely to make accepted evidence structures look
  smaller; freeze/defer is preferred over churn.

## Canonical references

- Current architecture: `docs/ARCHITECTURE.md`
- Verified status/evidence history: `docs/STATUS.md`
- Current operational handoff: `docs/HANDOFF.md`
- AI roles and risk-tiered governance: `docs/AI_OPERATING_MODEL.md`
- Quality and release gates: `docs/QUALITY.md`
- Design/plan record policy: `docs/superpowers/README.md`
- Active Lean Rebaseline design:
  `docs/superpowers/specs/2026-08-29-lean-rebaseline-design.md`
- Active Lean Rebaseline plan:
  `docs/superpowers/plans/2026-08-29-lean-rebaseline.md`
- Earlier approved complete design and execution plans remain historical
  evidence; they do not automatically outrank a fresh current Issue/authority
  under the Lean Rebaseline.
