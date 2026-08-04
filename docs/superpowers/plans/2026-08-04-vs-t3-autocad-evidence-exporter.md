# VS-T3 AutoCAD Evidence Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** planned
**Base SHA:** `2c796f8f2f42b95e838df65b3c197979bf6caa68`
**Specification:** `docs/superpowers/specs/2026-08-04-vs-t3-autocad-evidence-exporter.md`
**Completion Head SHA:** not applicable; this document is a plan-only record

## Goal

Add one read-only `visual_evidence_export` operation to the existing AutoCAD
Mechanical 2027 managed .NET/File IPC boundary. It must export region render,
entity-map, and measurement evidence while proving `changed=false`, stable
`DBMOD`, stable DWG hash, verified full path, restored transient session state,
and freshness against the Visual Run Manifest's exact
`latest_mutation_sha256`.

This plan describes future implementation work. The current documentation PR
must add no runtime code, no schema changes, no tests, no AutoCAD commands, and
no production drawing artifacts.

## Architecture

```text
Visual Run Manifest
  -> exact bytes + latest_mutation_sha256 (only mutation authority)
Python orchestrator
  -> validates existing IPC envelope and VS-T3 parameters
  -> computes visual_run_manifest_sha256 and region_config_sha256
  -> calls existing DotNetIPCClient
AutoCAD .NET visual_evidence_export
  -> verifies active full path
  -> snapshots/restores transient session state
  -> reads entities and measurements
  -> renders fixed Model Space region
  -> writes bounded request-owned artifact files
  -> proves DBMOD/hash/session-state/changed invariants
Python evidence writer
  -> re-reads exact manifest bytes
  -> validates artifact containment, ownership, size, and hashes
  -> atomically promotes evidence/<evidence_id>
```

The implementation extends existing contracts and package boundaries. It does
not add a second dispatcher, mutation executor, CAD solver, visual model
client, Codex bridge, publisher, or mutation-state store.

## Global constraints

- Use the exact field name `latest_mutation_sha256`; do not introduce a
  parallel mutation hash or local mutation counter.
- The Visual Run Manifest is the only mutation-state authority.
- Preserve the existing IPC root envelope:
  `request_id`, `schema_version`, `operation`, `drawing_full_path`,
  `drawing_sha256`, `parameters`, and `approval`.
- Keep VS-T3 request parameters and result payload as separate closed schemas.
- The root `drawing_sha256` is the expected pre-dispatch drawing hash; do not
  create a second root expected-hash field.
- VS-T3 is read-only. It must never save, modify, close-with-save, or create
  entities in a drawing.
- Accepted results require `changed=false` and an empty `entity_handles` list.
- Verify normalized absolute full path and drawing identity.
- Require equal `DBMOD` values and equal before/after drawing SHA-256 values.
- Snapshot and restore active AutoCAD transient session state in `finally` and
  require equal canonical session-state fingerprints before/after.
- Transfer large evidence through request-owned bounded artifact descriptors,
  not inline JSON payloads.
- Bind a stable orchestrator-supplied `evidence_id` end-to-end and refuse an
  existing destination; never auto-increment.
- Snapshot exact Visual Run Manifest bytes in Python and re-read them before
  atomic promotion; mutation-field equality alone is insufficient.
- Reject missing, mismatched, stale, over-limit, or unsafe evidence rather
  than repairing it or guessing.
- Keep private drawings and live artifacts outside Git.
- Keep AutoCAD live tests opt-in and disposable; unavailable prerequisites are
  recorded as `SKIP` or `NOT RUN`, never as a pass.
- Every implementation task uses test-first development and ends with a
  focused verification command and a scoped commit.

## Task 1 - Align the composite operation with the existing IPC envelope

**Files to add/change in the future implementation:**

- `contracts/autocad-ipc/request.schema.json`
- `contracts/autocad-ipc/result.schema.json`
- `contracts/autocad-ipc/operations/visual-evidence-export.schema.json`
- `contracts/autocad-ipc/examples/visual-evidence-export-request.json`
- `contracts/autocad-ipc/examples/visual-evidence-export-result.json`
- focused contract tests under the existing contract-test roots
- Python and managed C# contract-alignment tests

**Steps:**

- [ ] Add failing tests for a valid request using the existing root envelope:
      `request_id`, `schema_version`, `operation`, `drawing_full_path`,
      `drawing_sha256`, `parameters`, and `approval: null`.
- [ ] Add failing tests proving VS-T3-specific fields are rejected at the
      root and accepted only inside `parameters`.
- [ ] Add failing tests for missing/empty/invalid
      `latest_mutation_sha256`, `visual_run_manifest_sha256`, `evidence_id`,
      `artifact_directory`, and region configuration.
- [ ] Extend the supported operation enum with exactly
      `visual_evidence_export`.
- [ ] Define a closed request-parameters schema containing `run_id`,
      `evidence_id`, `region_id`, `latest_mutation_sha256`,
      `visual_run_manifest_sha256`, `artifact_policy_version`,
      `artifact_directory`, `region`, and `measurements`.
- [ ] Define a separate closed result-payload schema containing before/after
      drawing hashes, before/after DBMOD, session-state hashes,
      `transient_state_restored`, `captured_at_utc`, artifact descriptors, and
      the binding IDs.
- [ ] Keep root result fields in the existing result envelope and require
      `changed=false` plus empty `entity_handles` for this operation.
- [ ] Define the artifact descriptor with relative path, artifact ID, kind,
      SHA-256, byte length, MIME type, and optional image dimensions.
- [ ] Add schema-alignment tests that pass through JSON Schema, Python IPC
      validation, and the C# validator.
- [ ] Run the focused contract tests and JSON Schema validator.
- [ ] Commit as `contracts: align VS-T3 with the IPC envelope`.

**Acceptance:** valid fixtures pass through every validator; root/parameters
and root/payload boundaries are enforced; no alternate expected-drawing or
mutation field is introduced.

## Task 2 - Add managed read-only models and transient-state boundary

**Files to add/change in the future implementation:**

- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`
- existing `autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs`
- focused evidence/session-state model files under `.../Drawing/` or
  `.../Evidence/`
- corresponding managed unit tests

**Steps:**

- [ ] Write failing tests proving a full-path mismatch prevents gateway access.
- [ ] Write failing tests proving an accepted result requires `changed=false`,
      equal DBMOD, equal before/after drawing SHA-256, and empty mutation
      handles.
- [ ] Define `VisualEvidenceRequest`, `VisualEvidenceSnapshot`, and a
      read-only gateway method such as:
      `VisualEvidenceSnapshot ReadVisualEvidence(VisualEvidenceRequest request)`.
- [ ] Ensure the managed request model validates and echoes
      `latest_mutation_sha256`, `visual_run_manifest_sha256`, `run_id`, and
      `evidence_id` without claiming it validated a Visual Run Manifest.
- [ ] Define a canonical `SessionStateSnapshot` containing active document
      identity, full path, `CTAB`, model/paper mode, `CVPORT`, current layer,
      current view properties used by the renderer, selection/pickfirst set,
      touched layer states, and a closed allowlist of renderer system variables.
- [ ] Implement a canonical session-state fingerprint and an explicit
      `transient_state_restored` result flag.
- [ ] Require snapshot/restore in `try/finally`; restore failure or a changed
      post-restore fingerprint must fail the operation.
- [ ] Keep the operation context bound to one document identity and one
      request; do not expose a write-capable callback.
- [ ] Run focused managed tests and the Release build.
- [ ] Commit as `feat: add read-only VS-T3 evidence boundary`.

**Acceptance:** the managed boundary can only produce a read-only snapshot;
path identity, manifest-echo behavior, no-change invariants, and transient
session restoration are explicit and testable.

## Task 3 - Implement deterministic projection and secure artifact handoff

**Files to add/change in the future implementation:**

- focused render/evidence projection files under the managed evidence boundary
- existing `OperationDispatcher.cs`
- managed artifact descriptor/cleanup helpers
- managed tests for ordering, projection, limits, containment, and cleanup

**Steps:**

- [ ] Write failing tests for canonical region configuration hashing and stable
      ordering of included layers, entity records, and measurements.
- [ ] Implement fixed Model Space bounding-box rendering with explicit pixel
      size, background, and include/exclude layers.
- [ ] Implement deterministic entity-map projection containing stable IDs,
      type/layer, bounding box, geometry metadata, and handle only as
      read-only identity metadata.
- [ ] Implement measurement projection using approved entity/datum references;
      never create a native dimension entity and never map a pixel directly to
      Model Space.
- [ ] Implement the fixed `vs-t3-artifacts-1` limits: 8 MiB render PNG,
      50,000 entity records, 10,000 measurement records, and 32 MiB total
      request-owned artifact bytes. The existing 1 MiB JSON result bound
      remains unchanged.
- [ ] Create artifacts only below the approved IPC artifact root and the
      request-owned `artifacts/<request_id>/` directory. Reject absolute paths,
      `..`, symlinks, reparse points, existing/non-empty directories, wrong
      request IDs, over-limit files, and hash/size mismatches.
- [ ] Return only closed descriptors for render, entity-map, and measurements;
      do not embed large binary or collection payloads in the result JSON.
- [ ] Keep request-owned artifacts after a successful .NET result; make Python
      the sole owner of success-path cleanup after verify/copy/promote or
      reject. Make .NET clean only when no successful result was produced.
- [ ] Add an exclusive request-owned active lease. On timeout, Python must not
      assume cancellation; cleanup is best-effort only when the lease is free.
      Add a startup scavenger that removes lease-free request directories older
      than a fixed 24-hour TTL, including orphaned successful-result artifacts.
- [ ] Test cleanup ownership, active-lease protection, timeout behavior, and
      bounded stale-request scavenging.
- [ ] Add dispatcher mapping for exactly `visual_evidence_export`.
- [ ] Ensure render failures, unresolved references, DBMOD changes, source hash
      changes, and session-state restore failures produce no accepted evidence.
- [ ] Run focused managed tests, then Release build and test commands.
- [ ] Commit as `feat: implement deterministic VS-T3 evidence projection`.

**Acceptance:** one request yields internally consistent render, entities, and
measurements; large evidence stays outside JSON; all artifact security,
limits, ownership, and cleanup checks are deterministic.

## Task 4 - Extend the Python File IPC adapter

**Files to add/change in the future implementation:**

- `mcp_integration_lib/dotnet_ipc.py`
- focused tests under `mcp_integration_lib/tests/`
- existing Python IPC contract fixture directory

**Steps:**

- [ ] Write failing adapter tests for a valid envelope request, malformed
      result, operation error, `changed=true`, and stale request identity.
- [ ] Add a typed adapter method for `visual_evidence_export` that places all
      VS-T3 fields inside `parameters` and sends the exact root
      `drawing_sha256` expected hash.
- [ ] Validate the returned operation, run ID, evidence ID, region ID,
      mutation hash, manifest snapshot hash, region-config hash, full path,
      session-state fields, `captured_at_utc`, and separate closed payload
      structure.
- [ ] Validate artifact descriptors before any artifact is read: path
      containment, no symlink/reparse point, request ownership, byte limits,
      declared length, MIME type, and SHA-256.
- [ ] Preserve the manifest's exact `latest_mutation_sha256` without deriving
      or updating it in the adapter.
- [ ] Ensure adapter errors, timeout, and cancellation clean the request-owned
      temporary artifact directory and write no final evidence.
- [ ] Do not increase `DEFAULT_MAX_READ_BYTES` to accommodate evidence files.
- [ ] Run focused Python IPC tests and Ruff on affected files.
- [ ] Commit as `feat: add Python VS-T3 IPC adapter`.

**Acceptance:** the adapter uses the existing transport, proves the result is
the requested read-only capture, and safely hands off only verified artifacts.

## Task 5 - Implement exact manifest freshness and atomic evidence writing

**Files to add/change in the future implementation:**

- a focused Python evidence module under `cad_agent/`, for example
  `cad_agent/visual_evidence.py`
- focused tests under `tests/` or the existing `cad_agent` test root

**Required interfaces:**

```python
def snapshot_visual_run_manifest(
    manifest_path: Path,
) -> tuple[bytes, Mapping[str, object], str]: ...

def canonical_region_config_sha256(
    region_config: Mapping[str, object],
) -> str: ...

def validate_visual_evidence_freshness(
    evidence: Mapping[str, object],
    manifest_bytes_sha256: str,
    manifest: Mapping[str, object],
    drawing_sha256_before_dispatch: str,
) -> Mapping[str, object]: ...

def write_visual_evidence(
    evidence_root: Path,
    evidence_result: Mapping[str, object],
    manifest_path: Path,
    evidence_id: str,
) -> Path: ...
```

**Steps:**

- [ ] Write failing tests for missing manifest mutation, invalid manifest,
      request/manifest mismatch, manifest-byte hash mismatch, drawing hash
      mismatch, full-path mismatch, DBMOD change, session-state mismatch,
      `changed=true`, and stale evidence after the manifest advances.
- [ ] Write a race test where any manifest byte changes while
      `latest_mutation_sha256` remains unchanged; require rejection and no
      final evidence folder.
- [ ] Implement exact manifest byte snapshotting and
      `visual_run_manifest_sha256`; validate the JSON contract separately.
- [ ] Implement canonical region-config hashing and exact mutation copying.
- [ ] Implement validation of `run_id`, `evidence_id`, `drawing_path`,
      `drawing_sha256`, `latest_mutation_sha256`,
      `visual_run_manifest_sha256`, `region_id`,
      `region_config_sha256`, and the RFC3339 UTC `captured_at_utc` copied
      exactly from the result payload.
- [ ] Re-read the exact manifest bytes immediately before atomic promotion and
      reject any byte-level change, even when the mutation field is unchanged.
- [ ] Read only verified request-owned descriptors into a temporary sibling
      directory; hash every artifact and write render/entity/measurement,
      render-manifest, and evidence-manifest files.
- [ ] Promote to
      `runs/<run_id>/iterations/<region_id>/evidence-<evidence_id>/` only when
      the destination does not exist and every check succeeds.
- [ ] Make evidence reads repeat the freshness check so a package becomes
      `STALE` after a later mutation.
- [ ] Remove temporary IPC artifacts on success/failure paths according to the
      lease ownership rule; leave active timed-out work for the TTL scavenger.
- [ ] Run focused Python evidence tests, Ruff, and `git diff --check`.
- [ ] Commit as `feat: validate and persist fresh VS-T3 evidence`.

**Acceptance:** stale or inconsistent evidence is never accepted, any
manifest-byte race is rejected, partial output is not promoted, destinations
cannot be overwritten, and the writer never changes mutation state.

## Task 6 - Add the opt-in disposable AutoCAD live gate

**Files to add/change in the future implementation:**

- the existing AutoCAD live-test root, with a focused VS-T3 test module
- test fixtures/harness only when they remain disposable and outside Git
- documentation of the live marker and unavailable-state behavior if required

**Steps:**

- [ ] Write a test explicitly marked `autocad_mechanical` that skips unless
      declared AutoCAD/File IPC prerequisites are present.
- [ ] Use a fresh disposable DWG/DXF below the approved temporary root and a
      manifest snapshot with a stable `evidence_id`.
- [ ] Assert render, entity-map, and measurement descriptors resolve only
      inside the request-owned IPC artifact directory and match hash/size.
- [ ] Assert `changed=false`, equal DBMOD before/after, equal drawing hashes,
      verified full path, exact manifest snapshot hash, exact mutation hash,
      equal session-state fingerprints, `transient_state_restored=true`, and
      a valid result `captured_at_utc`, and empty entity handles.
- [ ] Assert current layout/view, layer visibility/freeze state, selection set,
      and renderer system variables are unchanged after the operation.
- [ ] Change one manifest byte without changing the mutation field and assert
      the exporter rejects the result and leaves no final evidence directory.
- [ ] Assert the disposable drawing closes without save and remains unchanged
      on disk.
- [ ] Record missing prerequisites as `SKIP` or `NOT RUN`, not `PASS`.
- [ ] Run the focused live command only when prerequisites are available;
      otherwise record the unavailable state explicitly.
- [ ] Commit as `test: add VS-T3 disposable AutoCAD evidence gate`.

**Acceptance:** live evidence is honest, disposable, hash-stable,
DBMOD-stable, session-state-stable, and never touches a production drawing.

## Task 7 - Integrate verification and review the authority boundaries

**Files to add/change in the future implementation:**

- `scripts/verify.ps1` only if a new test root must be included through the
  canonical verifier
- relevant contract-test routing files
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
      evidence is consumed, no manifest-byte race is accepted, and no
      mutation/verdict/publish authority leaked into VS-T3.
- [ ] Run `git diff --check` and confirm verification did not alter repository
      status.
- [ ] Commit as `test: verify VS-T3 evidence exporter boundaries`.

**Acceptance:** the authoritative verifier and focused tests pass, unavailable
private/live gates are recorded honestly, and the implementation remains
confined to the approved VS-T3 boundary.

## Task 8 - Close the implementation record

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
| JSON contracts | Existing envelope plus closed request/payload schema tests pass | `NOT RUN` if command not executed |
| Managed .NET | Release build, projection, artifact, and session-state tests pass | `NOT RUN` if .NET unavailable |
| Python IPC/evidence | Adapter, containment, cleanup, race, freshness, Ruff tests pass | `NOT RUN` if not executed |
| Repository gate | `scripts/verify.ps1` exits `0` on final implementation SHA | `NOT RUN` if not executed |
| Private drawing | Approved private gate with source SHA | `NOT RUN` when no approved input exists |
| AutoCAD Mechanical | Disposable live evidence with session identity and state fingerprint | `SKIP`/`NOT RUN` when prerequisites are absent |

## Plan completion criteria

The future VS-T3 implementation may be called complete only when all of the
following are true:

- [ ] The existing IPC envelope remains valid and the one composite operation
      is closed-schema validated end-to-end.
- [ ] Request parameters and result payload are distinct closed schemas.
- [ ] Every accepted evidence package has exact mutation, manifest snapshot,
      region, drawing, and `evidence_id` identity fields.
- [ ] Manifest/drawing changes, stale mutation, manifest-byte races, changed
      DBMOD, changed session state, changed hash, `changed=true`, unsafe
      artifacts, and unverified paths all fail closed.
- [ ] Evidence is transferred through bounded request-owned descriptors and is
      written atomically without overwriting an existing evidence ID.
- [ ] No write transaction, save, entity creation, mutation-state update,
      visual verdict, repair plan, or publication authority is present.
- [ ] Focused tests, canonical verification, and required review gates have
      fresh evidence.
- [ ] Private and AutoCAD live gates are accurately recorded as passed,
      skipped, or not run.
