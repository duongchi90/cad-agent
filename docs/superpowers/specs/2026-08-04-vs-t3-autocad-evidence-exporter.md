# VS-T3 AutoCAD Evidence Exporter Specification

**Date:** 2026-08-04  
**Status:** Proposed / Under PO review; implementation not started
**Base SHA:** `2c796f8f2f42b95e838df65b3c197979bf6caa68` (`origin/main`)
**Supported scope:** Windows, Python 3.11, AutoCAD Mechanical 2027, existing
managed .NET/File IPC boundary

## 1. Purpose and boundary

VS-T3 adds one deterministic, read-only AutoCAD evidence operation. It exports
render, entity-map, and measurement evidence for one configured drawing region
while proving that the drawing and the active AutoCAD session were not changed.

This slice is an evidence exporter only. It does not mutate CAD, infer or
advance mutation state, issue visual verdicts, plan repairs, call OpenAI or
Codex, or publish a drawing. It extends the existing AutoCAD .NET/File IPC
boundary; it does not create a second dispatcher, protocol, solver, or CAD
pipeline.

The existing Visual Supervisor contracts remain the orchestration authority.
VS-T3 consumes a validated Visual Run Manifest and returns evidence bound to
that manifest. The manifest and the orchestrator remain the only owners of
mutation state.

## 2. Mutation-state authority

The only source of truth for drawing mutation state is the exact field
`Visual Run Manifest.latest_mutation_sha256`:

```text
Visual Run Manifest.latest_mutation_sha256
        |
        v
VS-T3 request parameters
        |
        v
read-only evidence export
```

VS-T3 must use the field name `latest_mutation_sha256` everywhere. It must not
introduce `current_mutation_hash`, a local mutation counter, an inferred
mutation value, or any parallel mutation-state authority.

The Python orchestrator must read and validate the manifest before dispatch,
snapshot its exact bytes, compute `visual_run_manifest_sha256`, copy the exact
`latest_mutation_sha256` into request parameters, and re-read the exact bytes
before accepting the result. VS-T3 never updates the manifest and never
decides whether a mutation is current.

`visual_run_manifest_sha256` is provenance for the exact manifest snapshot. It
is not a second mutation authority and never replaces
`latest_mutation_sha256`.

## 3. Design decisions

### 3.1 One composite operation

The existing dispatcher gains one operation:

```text
visual_evidence_export
```

Render, entity extraction, and measurement collection run under one request
and one read-only boundary. Separate render/entity/measurement operations are
not used because they could observe different drawing states and produce
inconsistent evidence.

### 3.2 Existing boundaries are extended

The implementation extends the existing request/result contracts,
`OperationDispatcher`, `IDrawingGateway`, and Python `DotNetIPCClient`.
It does not replace the File IPC transport or add a mutation executor.

The read-only gateway may read database state and render a configured view, but
must not open a write transaction, append or erase entities, change persisted
layers, save, close with save, or modify any manifest or mutation record.

### 3.3 Deterministic region and artifact configuration

The request identifies a fixed Model Space bounding box, pixel size,
background, included/excluded layers, and measurement references. The
canonical representation of this region is hashed as
`region_config_sha256`. No free-form viewport state or screen-pixel coordinate
is accepted as Model Space geometry.

Render bytes and large entity/measurement maps are transferred as bounded
request-owned artifacts, not embedded in the JSON result.

### 3.4 Evidence identity is explicit

The orchestrator supplies a stable `evidence_id` for every capture. It is
bound into the request, result, and evidence manifest and is used directly in
the destination path. The writer refuses an existing destination and never
guesses the next iteration number.

## 4. Request contract and existing IPC envelope

VS-T3 must preserve the existing File IPC envelope. The root request remains
closed and contains exactly the established fields:
`request_id`, `schema_version`, `operation`, `drawing_full_path`,
`drawing_sha256`, `parameters`, and `approval`.

The root `drawing_sha256` is the expected drawing hash captured by Python
before dispatch. VS-T3 does not add another root expected-hash field.
All VS-T3-specific fields live inside a separate closed
`visual-evidence-export` request-parameters schema. `approval` is explicitly
`null` because this operation has no mutation authority; its presence keeps
the existing envelope intact.

```json
{
  "request_id": "REQ-VS-T3-001",
  "schema_version": "1.0",
  "operation": "visual_evidence_export",
  "drawing_full_path": "D:\\project\\vehicle.dwg",
  "drawing_sha256": "<64 lowercase hex expected before dispatch>",
  "parameters": {
    "run_id": "RUN-001",
    "evidence_id": "EV-SIDE-CABIN-001",
    "region_id": "SIDE-CABIN",
    "latest_mutation_sha256": "<64 lowercase hex>",
    "visual_run_manifest_sha256": "<64 lowercase hex>",
    "artifact_policy_version": "vs-t3-artifacts-1",
    "artifact_directory": "artifacts/REQ-VS-T3-001",
    "region": {
      "model_bbox_mm": [0, 0, 2400, 2200],
      "pixel_size": [1600, 1200],
      "background": "WHITE",
      "include_layers": ["CABIN", "CENTER"],
      "exclude_layers": ["TEXT", "DIM"]
    },
    "measurements": []
  },
  "approval": null
}
```

Required request rules:

- `drawing_full_path` is an absolute path and is normalized before comparison.
- `run_id`, `evidence_id`, `region_id`, and `request_id` are non-empty stable
  identifiers. `evidence_id` is supplied by the orchestrator; it is not
  inferred or auto-incremented by the writer.
- Root `drawing_sha256`, `latest_mutation_sha256`, and
  `visual_run_manifest_sha256` are valid lowercase SHA-256 values.
- `parameters` is closed and contains no envelope fields. `region` is closed
  and canonicalized before `region_config_sha256` is computed.
- `artifact_directory` is a request-owned relative path below the configured
  IPC artifact root; it may not be absolute, contain `..`, or resolve through
  a symlink or reparse point.
- Measurement requests contain stable IDs and approved entity or datum
  references; they do not create native dimension entities.
- Missing or invalid `latest_mutation_sha256` or
  `visual_run_manifest_sha256` is a hard failure.

## 5. Managed AutoCAD read-only boundary

The managed operation must perform the following sequence:

1. Verify that the active document's normalized full path equals
   `drawing_full_path`.
2. Validate the request identity and mutation hash format, and echo the exact
   request values. The managed process does not receive or own the Visual Run
   Manifest and must not claim that it authorized the mutation value.
3. Capture `DBMOD` and the source drawing SHA-256 before reading.
4. Snapshot the transient active-document session state described below.
5. Read entities with read-only database access in deterministic order.
6. Resolve and collect only the requested measurements.
7. Render the fixed Model Space region with the requested pixel size and
   controlled layer set.
8. Restore and verify the transient AutoCAD session state.
9. Capture `DBMOD` and the source drawing SHA-256 after the operation.
10. Return success only when every read-only invariant is proven.

The operation must not:

- save, autosave, close with save, or change the active document identity;
- open a write transaction or call a write-capable gateway method;
- append, erase, transform, or edit entity data;
- persistently change layers, document metadata, or the Visual Run Manifest;
- create dimension, block, or other CAD entities;
- return mutation handles or a mutation operation plan;
- accept a managed-side claim that a mutation is manifest-authorized.

The result uses `changed=false` as a required assertion, not as an inferred
default. Any inability to prove the invariant produces a failed result that
the orchestrator must reject.

### 5.1 Transient AutoCAD session-state strategy

VS-T3 uses the active-document strategy with an exact snapshot/restore
boundary. `DBMOD` and file SHA-256 are necessary but insufficient because a
render can change transient UI/session state without changing the DWG.

Before any viewport or renderer action, the managed gateway snapshots and
hashes:

- active document normalized full path and document identity;
- current layout/`CTAB`, model/paper mode, `CVPORT`, and current layer;
- current view center, width, height, target, direction, twist, and lens
  properties used by the renderer;
- the selection/pickfirst set, including its ordered entity identity;
- visibility/frozen/thawed state for every layer touched by the render;
- every system variable used by the renderer, from a closed allowlist that
  includes the actual values read by the implementation.

The operation may temporarily apply the requested view/layer state only inside
this boundary. A `try/finally` path must restore the exact snapshot even when
rendering, entity reading, measurement, or artifact writing fails. After
restore, the gateway captures the same state again and requires an identical
`session_state_sha256_before`/`session_state_sha256_after` pair and
`transient_state_restored=true`. Any inability to snapshot, restore, or prove
equality fails the operation and triggers temporary-artifact cleanup.

The session-state hashes are a session safety proof. They are separate from
the drawing hash and are not a mutation authority or a substitute for
`latest_mutation_sha256`.

## 6. Artifact transport over File IPC

The existing JSON File IPC channel remains bounded. Render bytes and large
entity/measurement maps are not embedded in `payload` and must not be handled
by increasing `DEFAULT_MAX_READ_BYTES` without limit.

The managed operation writes artifacts into a request-scoped temporary
directory below the configured approved IPC artifact root, for example:

```text
<ipc-root>/artifacts/REQ-VS-T3-001/
├── cad-render.png
├── entities.json
└── measurements.json
```

The request's `artifact_directory` must resolve to this exact request-owned
directory. The managed side creates it exclusively and refuses an existing,
non-empty, symlinked, or reparse-point directory. The result returns only
closed artifact descriptors:

```json
{
  "artifact_id": "cad-render",
  "kind": "render",
  "relative_path": "artifacts/REQ-VS-T3-001/cad-render.png",
  "sha256": "<64 lowercase hex>",
  "byte_length": 123456,
  "mime_type": "image/png",
  "width": 1600,
  "height": 1200
}
```

Python must verify that every descriptor is relative to the configured IPC
root, remains inside the request-owned directory, contains no symlink or
reparse-point component, has the declared size and hash, and belongs to the
current request ID before reading or promoting it. Python copies verified
artifacts into its atomic evidence staging directory, then removes the
request-owned temporary directory. Failure, timeout, cancellation, or
exception removes that directory as well. The .NET side also cleans it on
operation failure.

The fixed `vs-t3-artifacts-1` policy is:

- render PNG: at most 8 MiB;
- entity records: at most 50,000;
- measurement records: at most 10,000;
- total request-owned artifact bytes: at most 32 MiB;
- IPC result JSON remains within the existing 1 MiB bounded JSON limit.

The policy may be tightened by a caller but may not be raised by request
parameters. Exceeding any limit fails closed and leaves no final evidence
directory.

## 7. Result contract

The result is closed-schema validated and must carry the full evidence binding.
Its `payload` schema is separate from the request-parameters schema:

```json
{
  "request_id": "REQ-VS-T3-001",
  "success": true,
  "operation": "visual_evidence_export",
  "drawing_full_path": "D:\\project\\vehicle.dwg",
  "changed": false,
  "entity_handles": [],
  "warnings": [],
  "errors": [],
  "started_at": "2026-08-04T00:00:00Z",
  "completed_at": "2026-08-04T00:00:02Z",
  "payload": {
    "run_id": "RUN-001",
    "evidence_id": "EV-SIDE-CABIN-001",
    "region_id": "SIDE-CABIN",
    "drawing_sha256_before": "<hash>",
    "drawing_sha256_after": "<same hash>",
    "dbmod_before": 0,
    "dbmod_after": 0,
    "latest_mutation_sha256": "<manifest value>",
    "visual_run_manifest_sha256": "<manifest snapshot hash>",
    "region_config_sha256": "<hash>",
    "session_state_sha256_before": "<hash>",
    "session_state_sha256_after": "<same hash>",
    "transient_state_restored": true,
    "artifacts": []
  }
}
```

The minimum binding in the result/evidence manifest is:

```json
{
  "run_id": "RUN-001",
  "evidence_id": "EV-SIDE-CABIN-001",
  "drawing_path": "D:\\project\\vehicle.dwg",
  "drawing_sha256": "<hash>",
  "latest_mutation_sha256": "<manifest value>",
  "visual_run_manifest_sha256": "<manifest snapshot hash>",
  "region_id": "SIDE-CABIN",
  "region_config_sha256": "<hash>",
  "captured_at_utc": "2026-08-04T00:00:00Z"
}
```

`drawing_sha256` is accepted only when the before and after hashes are equal.
`dbmod_before` and `dbmod_after` must also be equal. `entity_handles` must be
empty because this operation does not grant mutation authority. Entity-map
records may contain stable component IDs and handles as read-only identity
metadata, sorted deterministically.

## 8. Evidence artifact layout

The Python evidence writer stores each package under the run's evidence root:

```text
runs/<run_id>/iterations/<region_id>/evidence-<evidence_id>/
├── cad-render.png
├── entities.json
├── measurements.json
├── render-manifest.json
└── evidence-manifest.json
```

Every artifact is SHA-256 hashed. `render-manifest.json` records the Model
Space bounding box, pixel size, background, included/excluded layers, render
hash, entity-map hash, measurement hash, and session-state hashes.
`evidence-manifest.json` records the request identity, exact manifest snapshot
hash, all required binding fields, and every artifact hash.

The writer uses a temporary sibling directory and an atomic rename. The final
destination must not already exist or be non-empty. The writer never searches
for the next available number and never overwrites a previous `evidence_id`.

## 9. Fail-closed and freshness policy

The exporter/orchestrator must reject the request or result when any of these
conditions holds:

- the Visual Run Manifest is missing, invalid, or changed during export;
- `manifest.latest_mutation_sha256` is missing, invalid, or empty;
- the exact manifest-byte snapshot hash differs before atomic promotion;
- the request mutation hash differs from the manifest value;
- the request manifest snapshot hash differs from the re-read manifest hash;
- the request drawing path differs from the manifest's target path;
- the root pre-dispatch `drawing_sha256` differs from the live drawing;
- the AutoCAD operation returns `changed=true`;
- `DBMOD` changes during export;
- the drawing SHA-256 changes during export;
- transient AutoCAD session state cannot be restored byte-for-byte by its
  canonical fingerprint;
- the returned full path or drawing identity cannot be verified;
- returned run, evidence, mutation, manifest, region, or region-config
  identity differs from the request;
- an artifact descriptor escapes the IPC root/request directory, uses a
  symlink/reparse point, has a wrong size/hash, belongs to another request, or
  exceeds a fixed limit;
- the destination for the requested `evidence_id` already exists;
- the manifest or drawing changes before atomic artifact promotion;
- any required artifact hash is missing or incorrect;
- evidence is read after a later mutation has advanced the manifest.

Evidence created under a previous mutation is `STALE`, never `PASS`, and must
not be consumed by later Visual Supervisor, comparator, repair, or publication
stages. Freshness is checked when evidence is written and whenever it is read.
VS-T3 never repairs stale evidence and never updates
`latest_mutation_sha256`; a new request and a new export are required.

## 10. Ownership and authority

```text
Visual Run Manifest / Orchestrator:
  owns mutation state, exact manifest snapshot, request authorization,
  freshness, and evidence lifecycle

VS-T3:
  reads the requested drawing, echoes request identity, exports evidence, and
  proves managed read-only/session invariants; it does not authorize the
  manifest mutation value

Visual Supervisor:
  evaluates evidence; does not change mutation state

Codex:
  may consume evidence in later slices; may not change latest_mutation_sha256
  or reuse stale evidence
```

This keeps VS-T3 compatible with the project safety rules. It does not weaken
the existing human approval requirement for production mutation and does not
authorize production drawing save or repair.

## 11. Implementation boundaries

The future implementation is limited to the following boundaries:

- the existing IPC envelope plus a closed VS-T3 request-parameters schema;
- a separate closed VS-T3 result-payload schema and operation examples;
- managed evidence models, gateway methods, and dispatcher mapping;
- deterministic render, entity-map, and measurement projection helpers;
- request-owned artifact descriptors, limits, containment, and cleanup;
- transient active-document snapshot/restore and session-state fingerprinting;
- Python `DotNetIPCClient` request/result adapter;
- Python exact-manifest-byte snapshot, evidence freshness validator, and
  atomic artifact writer;
- focused contract, Python, managed .NET, and opt-in disposable live tests.

VS-T3 must not modify VS-T1 dimension-observer behavior, VS-T2 comparator
behavior, Visual Supervisor verdict authority, Codex repair planning,
mutation state, or publication logic.

## 12. Verification and acceptance criteria

VS-T3 is ready for implementation review only when:

1. The existing IPC envelope remains valid and the VS-T3 request parameters
   and result payload are separate closed schemas.
2. Every result/evidence package contains all required binding fields,
   including exact `latest_mutation_sha256`, `visual_run_manifest_sha256`, and
   `evidence_id` fields.
3. Full-path, drawing-identity, `changed=false`, DBMOD, session-state, and
   before/after drawing-hash invariants fail closed.
4. A request/manifest mutation mismatch or any manifest-byte race is rejected.
5. Evidence created before a later manifest mutation is rejected as `STALE`.
6. Large evidence is transferred through request-owned, bounded artifact
   descriptors with containment, hash, size, ownership, and cleanup checks.
7. Artifact promotion is atomic and leaves no accepted output after failure.
8. Focused Python, .NET, IPC, and offline verifier checks pass.
9. The optional AutoCAD Mechanical live gate is recorded honestly as `PASS`,
   `SKIP`, or `NOT RUN`.
10. No mutation, visual verdict, repair, OpenAI/Codex bridge, or publication
    authority is added.

## 13. Explicit non-goals

VS-T3 does not:

- infer, create, or advance mutation state;
- modify, save, close-with-save, or publish a DWG;
- create or repair CAD entities;
- call ChatGPT, OpenAI, or Codex;
- decide visual similarity or issue `PASS`/`FAIL`;
- reuse evidence from an earlier mutation;
- replace the existing File IPC transport or package boundaries.
