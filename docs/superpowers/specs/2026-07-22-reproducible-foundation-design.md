# Reproducible Foundation Design

**Status:** Approved by the user on 2026-07-22

**Target:** Windows, Python 3.11, AutoCAD LT

**Program direction:** Incremental hardening; preserve the existing five-package core

## Goal

Create a small, reliable project foundation that every later CAD Agent task can
reuse. A new contributor or agent must be able to identify the current project
state, install the supported environment, run the authoritative offline checks,
and understand the release gates without reconstructing decisions from stale
handoff notes.

This slice changes project guidance, dependency management, test reporting, and
CI only. It does not change CAD recognition, calibration, constraint solving,
DXF generation, or AutoCAD LT behavior.

## Confirmed product decisions

- Preserve the current implementation and improve it incrementally; do not
  rewrite the project from scratch.
- The first product milestone is one real image or PDF running end to end through
  Primitive IR, Semantic IR, DXF, and AutoCAD LT review/repair with reproducible
  evidence.
- Support Windows and AutoCAD LT only. Python 3.11 is the supported runtime for
  this milestone.
- Do not build a GUI, web service, VPS deployment, or cross-platform AutoCAD
  integration.
- Keep a human approval gate for unverified calibration, ambiguous recognition,
  and every mutation of a production DXF in AutoCAD LT.
- Automatic calibration may pass its future production gate only when at least
  two independent dimension candidates agree and their median relative error is
  at most 3 percent.

The calibration rule is recorded here so later slices use the same contract. It
is not enabled or implemented by this foundation slice.

## Current baseline

At design time, `main` and `origin/main` both point to commit `908d016`. The
working tree is clean.

The complete offline pytest selection was executed on Windows with the bundled
Python 3.12 runtime and the installed Tesseract binary added to `PATH`:

```powershell
python -m pytest primitive_ir_lib/tests semantic_ir_lib/tests `
  dxf_builder_lib/tests mcp_integration_lib/tests agent_lib/tests `
  -q -p no:cacheprovider
```

Observed result: `255 passed, 11 skipped, 3 warnings`. This is evidence about the
current code, not the final supported-environment certificate. The foundation
slice must establish and record a fresh baseline using Python 3.11.

The repository already contains five implementation packages:

- `primitive_ir_lib/`
- `semantic_ir_lib/`
- `dxf_builder_lib/`
- `mcp_integration_lib/`
- `agent_lib/`

Their public behavior and JSON schema contracts remain unchanged in this slice.

## Problems this slice addresses

1. There is no repository-level `AGENTS.md` or concise cross-agent working
   agreement.
2. `README.md`, `HANDOFF.md`, and the architecture document contain overlapping
   status statements that have drifted apart.
3. The default `python` on the current workstation resolves to Python 3.7.9,
   while the project requires newer typing and package features.
4. Runtime, optional, CI, and development dependencies are not represented by
   one consistent dependency model or a reproducible Windows/Python 3.11 lock.
5. CI uses floating dependency versions and does not distinguish ordinary
   offline tests from real-data and AutoCAD LT validation gates.
6. A missing private image can make a real-image benchmark print a skip-like
   message and return successfully instead of reporting an actual pytest skip.
7. Historical implementation plans do not record completion metadata, and test
   counts in prose become stale as the suite grows.

## Canonical documentation model

The repository will use small documents with one responsibility each:

- `AGENTS.md` is the durable, tool-neutral working agreement for Codex and other
  repository-aware agents. It contains supported commands, scope boundaries,
  verification requirements, safety rules, and the single-writer rule.
- `CLAUDE.md` is a thin adapter for Claude sessions. It points to the canonical
  documents and does not duplicate project status or architecture prose.
- `README.md` is the human quick start: purpose, supported platform, bootstrap,
  one offline verification command, and links to canonical details.
- `docs/PROJECT.md` defines product goal, supported scope, non-goals, and the
  four-slice modernization roadmap.
- `docs/ARCHITECTURE.md` describes only the current five-phase data flow,
  package boundaries, schemas, and the planned thin orchestrator boundary.
- `docs/STATUS.md` is the only canonical status ledger. Every claim is tagged as
  verified, partially verified, or unverified and includes an evidence date or
  commit where applicable.
- `docs/QUALITY.md` defines offline tests, contract tests, private real-data
  benchmarks, AutoCAD LT live smoke tests, severity levels, and release gates.

`CAD-Agent-Kien-Truc-v1_3.md` and `HANDOFF.md` remain available as historical
evidence. Their first section will state that current status and operating rules
live in the canonical documents above. Historical narrative is not copied into
the new documents unless it still describes current behavior.

No canonical document will hard-code a test count as an evergreen fact. A
status entry may record a count only together with the exact command, date,
runtime, and commit that produced it.

## Repository working agreement

`AGENTS.md` will enforce these rules:

- One writer owns a branch or overlapping file set. Parallel agents are used
  first for read-heavy exploration, tests, and review.
- Production behavior changes require a failing regression test or benchmark
  before implementation.
- Changes to calibration, OCR, geometry, constraints, File IPC, or AutoCAD LT
  require the corresponding specialized gate from `docs/QUALITY.md`.
- Missing real data or AutoCAD LT is reported as `SKIP` or `NOT RUN`, never as a
  pass.
- No secret, API key, customer drawing, private annotation, or unapproved DXF
  artifact is committed.
- A task is complete only after focused tests, the relevant broader suite,
  `git diff --check`, and a clean status review.

For the available AI accounts, Codex is the repository owner and integrator.
Claude Free sessions receive bounded review packets instead of the complete
repository:

- reviewer 1: requirements and architecture;
- reviewer 2: correctness, edge cases, and tests;
- reviewer 3: security, AutoCAD LT operations, rollback, and release.

Small changes require one reviewer, medium-risk changes require two, and
calibration, geometry, File IPC, AutoCAD LT, architecture, and release changes
require all three. First-pass reviews remain independent. Findings are accepted
only with concrete scope, impact, and evidence; numeric quality scores are not
used.

Reusable packet templates will cover task brief, review evidence, reviewer
finding, adjudication, and release checklist. Raw independent reviews stay
outside the repository until all first-pass reviewers have responded; only the
normalized adjudication record is committed when it has lasting value.

The committed templates live under `docs/templates/` as `TASK_BRIEF.md`,
`REVIEW_PACKET.md`, `REVIEW_FINDING.md`, `ADJUDICATION.md`, and
`RELEASE_CHECKLIST.md`.

## Python and dependency model

Python 3.11 is the only supported runtime in this milestone. Other Python
versions may work but are not release evidence.

The project will have:

- `pyproject.toml` declaring the Python requirement and central pytest/Ruff
  settings;
- `requirements/runtime.in` for direct dependencies needed by the ordinary
  five-phase offline runtime;
- `requirements/vision.in` for the optional Anthropic Vision integration;
- `requirements/solver.in` for the optional constraint solver;
- `requirements/dev.in` for pytest, lint, and lock-generation tools;
- `requirements/windows-py311.lock`, a fully resolved environment containing
  everything needed by the authoritative offline CI suite;
- `scripts/bootstrap.ps1`, the single local/CI environment bootstrap entry
  point;
- `scripts/verify.ps1`, the single authoritative offline verification entry
  point.

The lock records exact Python package versions. The bootstrap process validates
the active interpreter before installation and fails with a clear command to
select Python 3.11 when another version is active. Tesseract remains a native
Windows prerequisite. The supported baseline is Tesseract
`5.4.0.20240606`; CI installs that version, while local verification reports a
clear prerequisite failure when the executable is missing or its version does
not match. Its detected executable path and version are printed in verification
evidence.

The dependency model must resolve the current contradiction where the Anthropic
SDK is described as optional but installed unconditionally. Vision, constraint
solver, DXF, test, and lint dependencies must each have an explicit role. The
default CI environment installs everything needed for the offline suite so an
import error cannot be mistaken for an optional skip.

## Test and CI model

The authoritative offline command collects tests from all five packages. CI
runs it on Windows with Python 3.11 and Tesseract `5.4.0.20240606` available.
Both local verification and CI invoke `scripts/verify.ps1`; the test selection
is defined once in that script instead of being copied between documentation
and workflow YAML.

Tests are classified as:

- `offline`: deterministic tests that require no customer data and no running
  AutoCAD LT; these gate every change;
- `real_data`: tests requiring approved images/PDFs stored outside Git;
- `autocad_lt`: tests requiring a running local AutoCAD LT instance and its IPC
  bridge.

Default CI runs and gates `offline`. It still collects the other classes and
reports their absence as explicit skips. Real-data and AutoCAD LT validation are
separate, manually triggered gates until a trusted Windows runner with the
required private data and application is available.

CI will:

- use least-privilege repository permissions;
- use immutable action revisions and the Windows/Python 3.11 dependency lock;
- print Python, Tesseract, and key dependency versions;
- run the full offline pytest suite;
- run repository lint checks configured in one place;
- preserve a machine-readable test report;
- fail on new unexpected warnings while allowing only an explicitly documented
  baseline warning set during migration.

A test that cannot access its private image uses pytest's skip mechanism. It
must not print a message and return as though the benchmark passed.

## Error handling and safety

- Bootstrap and verification stop before tests when the Python version or a
  required offline dependency is wrong.
- Setup messages name the failed prerequisite and the exact supported runtime;
  they do not silently install into whichever `python` happens to be first on
  `PATH`.
- Documentation generation does not infer status from old prose. Status changes
  require fresh command evidence.
- This slice performs no AutoCAD LT mutation and handles no customer drawing.
- Existing CLI/module entry points remain valid; the future `cad_agent/`
  orchestrator is part of the next slice.

## Acceptance criteria

1. A repository-aware agent loads one concise working agreement and can locate
   the authoritative project, architecture, status, and quality documents
   without using historical handoff prose as current truth.
2. On Windows with Python 3.11, one documented bootstrap path installs the
   locked offline environment and one documented command runs the complete
   offline suite.
3. The complete offline suite has zero failures. Every unavailable real-data or
   AutoCAD LT test is an explicit skip or is reported as not run.
4. CI uses the same locked dependency set and the same authoritative offline
   command as local verification.
5. CI has least-privilege permissions and immutable third-party action
   revisions.
6. Runtime, optional, and development dependencies no longer contradict their
   documentation.
7. `README.md`, `docs/STATUS.md`, and `docs/QUALITY.md` agree about supported
   platform, verification commands, and which gates have actually run.
8. Existing package APIs, schemas, recognition results, and DXF behavior are
   unchanged.
9. Running verification leaves no untracked or modified project artifacts.

## Out of scope

- The `cad_agent` orchestration package and `doctor`, `run`, or `resume`
  commands.
- Algorithm changes in calibration, OCR, geometry extraction, pattern
  recognition, constraints, DXF building, review, or repair.
- Creating or committing a real customer benchmark dataset.
- Running or changing AutoCAD LT File IPC behavior.
- GUI, web, VPS, Linux, macOS, or full AutoCAD support.
- Pushing, releasing, or deploying production artifacts.

## Subsequent slices

After this foundation is implemented and verified, later design/plan cycles will
cover, in order:

1. the thin `cad_agent` vertical-slice CLI with run manifests, checkpoints,
   approval gates, and resumability;
2. private real-data benchmark normalization and evidence-driven algorithm
   hardening;
3. the Windows/AutoCAD LT production review-repair loop, backup policy, live
   smoke test, and release checklist.
