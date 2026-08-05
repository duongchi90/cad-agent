# Visual Supervisor Closed-Loop Rollout Implementation Plan

**Status:** Superseded after VS-T3 by the reuse-first multisource reconstruction rebaseline.

VS-T0 through VS-T3 remain historical accepted slices. Do not execute VS-T4 through VS-T8 unchanged. Their useful requirements must be reissued through the reuse inventory, compatibility spikes, and R1-R8 plans, each with a Reuse Declaration.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Historical plan status at creation:** Planned

**Approval date:** 2026-08-04

**Planning base SHA:** `b1d490d7e03019fcd9356b333e156e0e7e44fa2c`

**Implementation base:** Create each execution branch from the fresh integrated `main` recorded at the start of that plan. Do not assume the planning branch remains the implementation base.

**Completion Head SHA:** Not recorded until all accepted slices and evidence are integrated.

**Verification command:** `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`

**Verification result:** Not recorded until execution completes.

**Goal:** Add an independent multimodal visual-review loop that detects dimensions and shape/layout differences, prevents Codex from self-approving, drives controlled AutoCAD repair, and can publish a verified DWG with backup and rollback.

**Architecture:** Preserve the current `primitive_ir_lib -> semantic_ir_lib -> agent_lib -> dxf_builder_lib -> mcp_integration_lib` pipeline and existing AutoCAD .NET/File IPC dispatcher. Implement the feature as contract, offline analysis, read-only AutoCAD evidence, model-adapter, repair-planning, orchestration, publication, and private-pilot slices, each with a fresh implementation plan written against its actual integration SHA.

**Tech Stack:** Windows, Python 3.11, pytest, JSON Schema draft 2020-12 documents plus strict pure-Python validation, OpenCV-compatible image processing through already-approved project dependencies, AutoCAD Mechanical 2027, .NET 10 (`net10.0-windows`, x64), AutoCAD Managed API, JSON/File IPC, OpenAI multimodal API adapter, existing `scripts/verify.ps1`.

## Global Constraints

- Preserve current package boundaries, verified behavior, and the existing .NET/File IPC dispatcher.
- Keep M2 Drawing Initialization execution uninterrupted. Do not start an authoritative Visual Supervisor generation path before the required predecessor gates are integrated.
- No task may create a second CAD pipeline, solver, dispatcher, mutation protocol, release manifest, or parallel source of truth.
- Source inputs are scanned/photographed drawing images and rendered technical PDF pages.
- Review order is semantic region, complete view, then complete sheet.
- Codex cannot issue visual `PASS`, authorize publication, or convert unverified pixels directly into Model Space coordinates.
- Only confirmed `DRIVING` dimensions with valid attachments may control authoritative geometry. `REFERENCE` and `DERIVED` dimensions verify results. Critical `AMBIGUOUS`, `CONFLICT`, or `UNRESOLVED` dimensions block their affected scope.
- Every affected mutation invalidates previous render, measurement, comparison, and visual-review evidence.
- Final completion requires Visual, Geometry, Dimension/Engineering, Native/Editability, and Save/Reopen gates.
- Automatic publication requires a run-scoped authorization, exact target identity, verified backup, post-save reopen verification, and rollback on failure.
- Private drawings, source images, generated DWG/DXF, run artifacts, absolute workstation paths, customer data, API keys, and secrets remain outside Git.
- Live AutoCAD mutation tests use disposable drawings only.
- Missing private or live prerequisites are `SKIP` or `NOT RUN`, never `PASS`.
- Every code task starts with a failing focused test, implements the smallest passing change, runs focused verification, inspects the diff, and commits a bounded change.

---

## Rollout dependency graph

```text
VS-T0 Contracts
  |---> VS-T1 Dimension Observer ---------+
  |---> VS-T2 Geometry Comparator --------+--> VS-T6 Closed-Loop Orchestrator
  |---> VS-T3 AutoCAD Evidence Exporter --+
  |---> VS-T4 Visual Supervisor Adapter --+
  |                                         |
  +----------------> VS-T5 Repair Planner --+
                                            |
                                            +--> VS-T7 Verified Publisher
                                            |
                                            +--> VS-T8 Private Disposable Pilot
```

The roadmap relationship is:

```text
M2 Setup Gate
  -> M3 Dimension/Datum/Constraint contracts
  -> M4 Operation/Render/Measurement contracts
  -> M6 Source/CAD Region Mapping
  -> Visual Supervisor integrated closed loop
  -> M7/M8 domain repair and authoritative release
```

A disposable MVP can exercise the contracts and loop before M7/M8, but it cannot claim authoritative publication readiness.

## Plan decomposition

| Order | Plan | Deliverable | Required predecessor |
|---:|---|---|---|
| 1 | `2026-08-04-vs-t0-visual-supervisor-contracts.md` | Strict schemas, validators, synthetic examples, cross-contract safety policy, canonical documentation | Approved design at planning SHA |
| 2 | `2026-08-04-vs-t1-dimension-observer.md` | Offline dimension-cluster detection, value/symbol parsing, attachment candidates, role/status classification, coverage and conflict reports | VS-T0 integrated; fresh M3 assumptions reviewed |
| 3 | `2026-08-04-vs-t2-geometry-comparator.md` | Controlled alignment, outlines, overlays, difference masks, deterministic metrics, candidate improvement/regression comparison | VS-T0 integrated |
| 4 | `2026-08-04-vs-t3-autocad-evidence-exporter.md` | Read-only region render, entity-map and measurement operations through existing .NET/File IPC, mutation/render provenance | VS-T0 integrated; M4 evidence contracts reviewed |
| 5 | `2026-08-04-vs-t4-visual-supervisor-adapter.md` | Multimodal request packaging, strict structured-output validation, bounded retry, usage/cost accounting, no self-approval | VS-T0 integrated; current official OpenAI API documentation rechecked at execution time |
| 6 | `2026-08-04-vs-t5-repair-planner.md` | Validated conversion from Visual Review to business-level Repair Plan, protected datums/constraints, affected-region invalidation | VS-T0, stable Visual Review and entity evidence contracts |
| 7 | `2026-08-04-vs-t6-closed-loop-orchestrator.md` | Region/view/sheet state machine, iteration limits, best-candidate selection, stale-evidence enforcement, stop and rollback-to-best behavior | VS-T1 through VS-T5 integrated |
| 8 | `2026-08-04-vs-t7-verified-publisher.md` | Run-scoped authorization, verified backup, candidate save/reopen, atomic replacement, post-save verification, automatic rollback | VS-T6 integrated; M8 release boundary reviewed |
| 9 | `2026-08-04-vs-t8-private-disposable-pilot.md` | One approved image/PDF side-view pilot proving dimension coverage, independent defect detection, measurable repair improvement, and disposable publish flow | VS-T1 through VS-T7 integrated |

Only VS-T0 is detailed now. Every later plan must be written after its predecessor contracts are integrated and must record the actual fresh base SHA, exact existing files, dependencies, test commands, and applicable live/private gates.

## Stable cross-plan interfaces

VS-T0 owns the exact JSON contract names and versions. Later plans consume them without redefining field meanings:

```python
class VisualContractError(ValueError):
    pass


def validate_visual_contract(
    payload: Mapping[str, object],
    *,
    contract: str,
) -> dict[str, object]:
    """Validate one closed Visual Supervisor contract and return a deep copy."""


def read_visual_contract(
    path: Path,
    *,
    contract: str,
) -> dict[str, object]:
    """Read one UTF-8 JSON object and validate its exact closed contract."""
```

Stable contract keys:

```text
dimension_register
geometry_comparison
visual_review
repair_plan
region_verification_register
auto_publish_authorization
visual_run_manifest
```

Stable authority rules:

```text
Visual Review may issue PASS/FAIL/NEEDS_HUMAN.
Repair Plan may never issue PASS or publication authorization.
Only the orchestrator may aggregate verified region/view/sheet state.
Only the publisher may attempt target replacement after all gates pass.
```

## Slice acceptance gates

### VS-T0 — Contracts

- Every schema is closed and versioned.
- Pure-Python validators and schema examples agree.
- Invalid states, hashes, verdicts, roles, authority fields, and unexpected properties fail closed.
- Cross-contract tests prove Codex/Repair Plan cannot self-approve or publish.
- Contract-only gates record private and AutoCAD work as `NOT RUN`.

### VS-T1 — Dimension Observer

- Every detected cluster has a disposition.
- Value, unit/symbol, kind, view, source evidence, attachment candidates, role, confidence, and status are recorded.
- A number without valid attachment remains `UNRESOLVED`.
- Critical unresolved or conflicting dimensions block only their declared scope.
- Coverage is measured, not inferred from model confidence.

### VS-T2 — Geometry Comparator

- Alignment refuses insufficient or contradictory anchors.
- Translation, small rotation, uniform scale, and approved photograph perspective correction are reproducible.
- Free-form deformation is absent.
- Metrics detect missing/extra features, displacement, proportion, contour, and curve-profile differences.
- Candidate regression is deterministic.

### VS-T3 — AutoCAD Evidence Exporter

- Operations are read-only and return `changed=false`.
- `DBMOD` and source hash remain unchanged.
- Render, entity, and measurement evidence are bound to full drawing path, drawing hash, mutation hash, region configuration, and timestamp.
- Evidence older than the last mutation is rejected.
- Live tests use disposable drawings.

### VS-T4 — Visual Supervisor Adapter

- Requests contain the required source/CAD/overlay/difference and technical context for one review scope.
- Responses are validated strictly; free-form acceptance text is rejected.
- Verdicts are only `PASS`, `FAIL`, or `NEEDS_HUMAN`.
- Retries are bounded and limited to transport/schema failures.
- Usage and cost metadata exclude secrets.

### VS-T5 — Repair Planner

- Every operation cites a source review, target drawing hash, stable target, protected anchors/constraints, affected regions, and expected metric direction.
- No pixel-to-Model-Space conversion occurs without a verified mapping.
- Repair Plan has no visual-pass or publication authority.

### VS-T6 — Orchestrator

- Each mutation makes affected evidence stale.
- Region, view, and sheet gates run in the approved order.
- Critical failures cannot be averaged away.
- Technical ambiguity becomes `NEEDS_HUMAN`.
- Visual stagnation restores the best engineering-valid candidate and prevents publication.

### VS-T7 — Publisher

- Authorization is bound to one run, one absolute target path, expected initial hash, backup root, and expiry.
- Backup hash is verified before any replacement.
- Candidate is saved, closed, reopened, rerendered, remeasured, and reverified before target replacement.
- Target is reopened and checked after replacement.
- Any post-replacement failure restores the verified backup.

### VS-T8 — Pilot

- One approved source page and side view are processed outside Git.
- All detected dimension clusters have dispositions and no critical unresolved dimension remains.
- The independent reviewer finds at least one meaningful defect previously accepted by the Codex-only process.
- A repair produces deterministic metric improvement without violating driving dimensions.
- The first complete pilot publishes only to a disposable target.

## Parallel execution windows

After VS-T0 is integrated, VS-T1, VS-T2, VS-T3, and VS-T4 may run in isolated branches/worktrees only when their primary write sets are disjoint.

Recommended ownership:

```text
Worker A: VS-T1 dimension_observer files and tests
Worker B: VS-T2 geometry_comparator files and tests
Worker C: VS-T3 existing .NET/File IPC evidence operation files and tests
Worker D: VS-T4 visual API adapter files and tests
```

VS-T5 begins after Visual Review and entity evidence contracts stabilize. VS-T6 is an integration task and has one owner. VS-T7 is isolated and receives a dedicated security/operations review. One designated reviewer evaluates the integrated candidate; worker self-review is not acceptance evidence.

No parallel workers may edit the same schema, dispatcher file, orchestrator file, canonical status record, or release-policy file.

## Program verification policy

For every slice:

- [ ] Record fresh base SHA and implementation branch/worktree.
- [ ] Inspect current `docs/STATUS.md`, existing code, tests, and predecessor contracts.
- [ ] Classify work as `REUSE_AS_IS`, `EXTEND_WITH_TEST`, or `NEW_MISSING_CAPABILITY`.
- [ ] Write and run a focused failing test before production code.
- [ ] Run focused tests after each bounded change.
- [ ] Inspect `git diff --check` and the task diff.
- [ ] Commit the bounded task.
- [ ] Run `scripts/verify.ps1` from the supported Windows/Python 3.11 environment.
- [ ] Run private and/or AutoCAD gates only when the slice requires them.
- [ ] Record `PASS`, `FAIL`, `SKIP`, or `NOT RUN` honestly in the canonical status record.
- [ ] Perform requirements/architecture, correctness/test, and security/operations reviews when the slice affects geometry, external API use, AutoCAD, publication, or private data.

## Program completion criteria

The rollout is complete only when:

- every requirement in the approved design maps to an integrated slice and fresh evidence;
- Codex cannot self-approve visual fidelity or publication;
- dimension coverage and critical attachment policy are enforced;
- every affected mutation produces fresh render and measurement evidence;
- deterministic comparison and independent multimodal review both participate in acceptance;
- semantic regions, complete views, and complete sheets pass without stale evidence;
- automatic publication is strictly run-authorized, backed up, reopened, reverified, and rollback-capable;
- private data, credentials, and customer artifacts remain outside Git;
- applicable Windows, Python, AutoCAD, private-data, and aggregate verifier gates are recorded honestly.
