# VS-T3 AutoCAD Evidence Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** planned  
**Base SHA:** `2c796f8f2f42b95e838df65b3c197979bf6caa68`  
**Specification:** `docs/superpowers/specs/2026-08-04-vs-t3-autocad-evidence-exporter.md`  
**Completion Head SHA:** not applicable; this document is a plan-only record

## Goal

Add a single read-only `visual_evidence_export` operation to the existing
AutoCAD Mechanical 2027 managed .NET/File IPC boundary. The operation must
export region render, entity-map, and measurement evidence while proving
`changed=false`, stable `DBMOD`, stable DWG hash, verified full path, and
freshness against the Visual Run Manifest's exact
`latest_mutation_sha256`.

This plan describes future implementation work. The current documentation PR
must add no runtime code, no schema changes, no tests, no AutoCAD commands, and
no production drawing artifacts.

## Architecture

```text
Visual Run Manifest
  └─ latest_mutation_sha256 (only mutation authority)
       ↓ exact copy
Python evidence orchestrator
  ├─ validates manifest and request
  ├─ hashes region configuration
  └─ calls existing DotNetIPCClient
       ↓ one composite operation
AutoCAD .NET visual_evidence_export
  ├─ verifies active full path
  ├─ reads entities and measurements
  ├─ renders fixed Model Space region
  └─ proves DBMOD/hash/changed invariants
       ↓ result
Python evidence writer
  ├─ validates binding and freshness
  ├─ hashes artifacts
  └─ atomically promotes evidence package
```

The implementation extends existing contracts and package boundaries. It does
not add a second dispatcher, mutation executor, CAD solver, visual model
client, Codex bridge, publisher, or mutation-state store.

## Global constraints

- Use the exact field name `latest_mutation_sha256`; do not introduce a
  parallel mutation hash or local mutation counter.
- The Visual Run Manifest is the only mutation-state authority.
- VS-T3 is read-only. It must never save, modify, close-with-save, or create
  entities in a drawing.
- The composite operation must return `changed=false` and an empty
  `entity_handles` list on accepted success.
- Reject missing/mismatched/stale manifest or evidence data rather than
  repairing it or guessing.
- Verify normalized absolute full path and drawing identity.
- Require equal `DBMOD` values and equal before/after drawing SHA-256 values.
- Do not use screen pixels as Model Space coordinates.
- Keep private drawings and live artifacts outside Git.
- Keep AutoCAD live tests opt-in and disposable; unavailable prerequisites are
  recorded as `SKIP` or `NOT RUN`, never as a pass.
- Every implementation task uses test-first development and ends with a
  focused verification command and a scoped commit.

## Task 1 — Lock the composite IPC contract

**Files to add/change in the future implementation:**

- `contracts/autocad-ipc/request.schema.json`
- `contracts/autocad-ipc/result.schema.json`
- `contracts/autocad-ipc/operations/visual-evidence-export.schema.json`
- `contracts/autocad-ipc/examples/visual-evidence-export-request.json`
- `contracts/autocad-ipc/examples/visual-evidence-export-result.json`
- focused contract tests under the existing contract-test roots

**Steps:**

- [ ] Add failing schema tests for a valid composite request and result.
- [ ] Add failing tests for missing/empty/invalid
      `latest_mutation_sha256`.
- [ ] Add failing tests for missing `expected_drawing_sha256`, invalid full
      path, invalid region configuration, and non-closed nested objects.
- [ ] Add the operation schema with closed objects and stable fields:
      `operation`, `request_id`, `drawing_full_path`, `run_id`, `region_id`,
      `latest_mutation_sha256`, `expected_drawing_sha256`, `region`, and
      `measurements`.
- [ ] Add result fields for `success`, `changed`, empty `entity_handles`,
      before/after drawing hashes, before/after DBMOD, mutation hash, region
      config hash, render, entities, measurements, and UTC capture time.
- [ ] Ensure nested render/entity/measurement payloads are deterministic and
      reject unknown properties.
- [ ] Run the focused contract tests and the JSON schema validator.
- [ ] Commit as `contracts: add VS-T3 visual evidence IPC contract`.

**Acceptance:** valid fixtures pass; malformed identity, mutation, region, and
result payloads fail closed; the only mutation field is
`latest_mutation_sha256`.

## Task 2 — Add managed read-only evidence models and gateway boundary

**Files to add/change in the future implementation:**

- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`
- the existing `autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs`
- new focused managed evidence model/gateway files under
  `autocad_plugin/CadAgent.AutoCAD2027/Drawing/` or `.../Evidence/`
- corresponding managed unit tests

**Steps:**

- [ ] Write failing tests proving full-path mismatch prevents gateway access.
- [ ] Write failing tests proving an accepted result requires `changed=false`,
      equal DBMOD, equal before/after drawing SHA-256, and empty mutation
      handles.
- [ ] Define a read-only gateway method with an explicit request/result type,
      for example:
      `VisualEvidenceSnapshot ReadVisualEvidence(VisualEvidenceRequest request)`.
- [ ] Keep the operation context bound to one document identity and one
      request; do not expose a write-capable callback.
- [ ] Model the evidence binding, render metadata, stable entity records, and
      measurement records with deterministic serialization.
- [ ] Reject a missing manifest-authorized mutation value at the contract
      boundary; do not infer it from drawing content.
- [ ] Run the focused .NET tests and Release build.
- [ ] Commit as `feat: add read-only VS-T3 evidence boundary`.

**Acceptance:** the managed boundary can only produce a read-only snapshot;
path identity and all no-change invariants are explicit and testable.

## Task 3 — Implement deterministic render, entity-map, and measurement projection

**Files to add/change in the future implementation:**

- focused render/evidence projection files under the managed evidence boundary
- existing `OperationDispatcher.cs`
- managed tests for ordering, projection, and invariant failures

**Steps:**

- [ ] Write failing tests for canonical region configuration hashing and
      stable ordering of included layers, entity records, and measurements.
- [ ] Implement fixed Model Space bounding-box rendering with explicit pixel
      size, background, and include/exclude layers.
- [ ] Implement deterministic entity-map projection containing stable IDs,
      type/layer, bounding box, geometry metadata, and handle only as
      read-only identity metadata.
- [ ] Implement measurement projection using approved entity/datum references;
      never create a native dimension entity and never map a pixel directly to
      Model Space.
- [ ] Add dispatcher mapping for exactly `visual_evidence_export`.
- [ ] Ensure render failures, unresolved references, DBMOD changes, or source
      hash changes produce a failed result rather than partial evidence.
- [ ] Run focused managed tests, then the Release build and test command.
- [ ] Commit as `feat: implement deterministic VS-T3 evidence projection`.

**Acceptance:** one request yields internally consistent render, entities, and
measurements, with deterministic output and no database mutation path.

## Task 4 — Extend the Python File IPC adapter

**Files to add/change in the future implementation:**

- `mcp_integration_lib/dotnet_ipc.py`
- focused tests under `mcp_integration_lib/tests/`
- any existing Python IPC contract fixture directory

**Steps:**

- [ ] Write failing adapter tests for a valid request, malformed result,
      operation error, and `changed=true` refusal.
- [ ] Add a typed adapter method for `visual_evidence_export` that sends the
      composite request through the existing File IPC transport.
- [ ] Validate the returned operation, run ID, region ID, mutation hash,
      region-config hash, full path, and closed result structure.
- [ ] Preserve the manifest's exact `latest_mutation_sha256` without deriving
      or updating it in the adapter.
- [ ] Ensure adapter errors do not write evidence artifacts.
- [ ] Run focused Python IPC tests and Ruff on affected files.
- [ ] Commit as `feat: add Python VS-T3 IPC adapter`.

**Acceptance:** the adapter uses the existing transport and rejects results
that cannot prove the requested read-only identity.

## Task 5 — Implement manifest freshness and atomic evidence writing

**Files to add/change in the future implementation:**

- a focused Python evidence module under `cad_agent/`, for example
  `cad_agent/visual_evidence.py`
- focused tests under `tests/` or the existing `cad_agent` test root

**Required interfaces:**

```python
def canonical_region_config_sha256(
    region_config: Mapping[str, object],
) -> str: ...

def load_latest_mutation(manifest_path: Path) -> str: ...

def validate_visual_evidence_freshness(
    evidence: Mapping[str, object],
    manifest: Mapping[str, object],
    expected_drawing_sha256: str,
) -> Mapping[str, object]: ...

def write_visual_evidence(
    evidence_root: Path,
    evidence_result: Mapping[str, object],
    manifest_path: Path,
) -> Path: ...
```

**Steps:**

- [ ] Write failing tests for missing manifest mutation, request/manifest
      mismatch, drawing hash mismatch, full-path mismatch, DBMOD change,
      `changed=true`, and stale evidence after the manifest advances.
- [ ] Write a failing race test where the manifest or source drawing changes
      between dispatch and atomic promotion; require no final evidence folder.
- [ ] Implement canonical region-config hashing and exact manifest mutation
      copying.
- [ ] Implement validation of all required binding fields:
      `run_id`, `drawing_path`, `drawing_sha256`,
      `latest_mutation_sha256`, `region_id`, `region_config_sha256`, and
      `captured_at_utc`.
- [ ] Write render, entity-map, measurement, render-manifest, and
      evidence-manifest artifacts to a temporary sibling directory.
- [ ] Hash every artifact and atomically promote only after a final manifest
      and source identity recheck.
- [ ] Make evidence reads repeat the freshness check so a package becomes
      `STALE` after a later mutation.
- [ ] Run focused Python evidence tests, Ruff, and `git diff --check`.
- [ ] Commit as `feat: validate and persist fresh VS-T3 evidence`.

**Acceptance:** stale or inconsistent evidence is never accepted, partial
output is not promoted, and the writer never changes mutation state.

## Task 6 — Add the opt-in disposable AutoCAD live gate

**Files to add/change in the future implementation:**

- the existing AutoCAD live-test root, with a focused VS-T3 test module
- test fixtures/harness only when they remain disposable and outside Git
- documentation of the live marker and unavailable-state behavior if required

**Steps:**

- [ ] Write a test that is explicitly marked `autocad_mechanical` and skips
      unless the declared AutoCAD/File IPC prerequisites are present.
- [ ] Use a fresh disposable DWG/DXF below the approved temporary root.
- [ ] Assert render, entity-map, and measurement artifacts exist and match
      their hashes.
- [ ] Assert `changed=false`, equal DBMOD before/after, equal drawing hashes,
      verified full path, exact manifest mutation hash, and empty entity
      handles.
- [ ] Assert the disposable drawing closes without save and remains unchanged
      on disk.
- [ ] Record missing prerequisites as `SKIP` or `NOT RUN`, not `PASS`.
- [ ] Run the focused live command only when prerequisites are actually
      available; otherwise record the unavailable state explicitly.
- [ ] Commit as `test: add VS-T3 disposable AutoCAD evidence gate`.

**Acceptance:** live evidence is honest, disposable, hash-stable, and
DBMOD-stable; no production drawing is opened or modified.

## Task 7 — Integrate verification and review the authority boundaries

**Files to add/change in the future implementation:**

- `scripts/verify.ps1` only if a new test root must be included through the
  canonical verifier
- the relevant contract-test routing files
- implementation evidence notes outside `docs/STATUS.md` until runtime is
  actually complete

**Steps:**

- [ ] Add the new test root to the canonical verifier only through its existing
      test-selection mechanism; do not duplicate pytest selection elsewhere.
- [ ] Run focused contract, Python, and managed tests.
- [ ] Run `scripts/verify.ps1` on the final implementation commit.
- [ ] Record exact command, exit code, commit SHA, environment versions, and
      live/private gate states in the implementation review packet.
- [ ] Review that no runtime code updates `latest_mutation_sha256`, no stale
      evidence is consumed, and no mutation/verdict/publish authority leaked
      into VS-T3.
- [ ] Run `git diff --check` and confirm verification did not alter repository
      status.
- [ ] Commit as `test: verify VS-T3 evidence exporter boundaries`.

**Acceptance:** the authoritative verifier and focused tests pass, unavailable
private/live gates are recorded honestly, and the implementation remains
confined to the approved VS-T3 boundary.

## Task 8 — Close the implementation record

**Steps:**

- [ ] Obtain bounded requirements/architecture, correctness/test, and
      security/operations reviews because VS-T3 crosses File IPC and AutoCAD
      boundaries.
- [ ] Resolve every P0/P1 finding before merge; record a concrete owner and
      reason for any deferred P2.
- [ ] Update `docs/STATUS.md` only after runtime implementation and fresh
      verification evidence exist. Do not update it for this plan-only PR.
- [ ] Fill the plan's completion head only in the final implementation record,
      not in this documentation commit.
- [ ] Merge only after focused tests, canonical verification,
      `git diff --check`, and required review gates are complete.

**Acceptance:** the final implementation record distinguishes planned,
verified, skipped, and not-run states and does not claim AutoCAD live or
private-drawing acceptance without fresh evidence.

## Verification matrix for the future implementation

| Area | Required evidence | Missing prerequisite state |
|---|---|---|
| JSON contracts | Focused schema/contract tests pass | `NOT RUN` if command not executed |
| Managed .NET | Release build and focused tests pass | `NOT RUN` if .NET unavailable |
| Python IPC/evidence | Focused tests, Ruff, and hash/freshness races pass | `NOT RUN` if not executed |
| Repository gate | `scripts/verify.ps1` exits `0` on final implementation SHA | `NOT RUN` if not executed |
| Private drawing | Approved private gate with source SHA | `NOT RUN` when no approved input exists |
| AutoCAD Mechanical | Disposable live evidence with session identity | `SKIP`/`NOT RUN` when prerequisites are absent |

## Plan completion criteria

The future VS-T3 implementation may be called complete only when all of the
following are true:

- [ ] The one composite operation is closed-schema validated end-to-end.
- [ ] Every accepted evidence package has all required identity fields,
      including exact `latest_mutation_sha256`.
- [ ] Manifest/drawing changes, stale mutation, changed DBMOD, changed hash,
      `changed=true`, and unverified path all fail closed.
- [ ] Evidence is written atomically and is rejected after a later mutation.
- [ ] No write transaction, save, entity creation, mutation-state update,
      visual verdict, repair plan, or publication authority is present.
- [ ] Focused tests, canonical verification, and required review gates have
      fresh evidence.
- [ ] Private and AutoCAD live gates are accurately recorded as passed,
      skipped, or not run.
