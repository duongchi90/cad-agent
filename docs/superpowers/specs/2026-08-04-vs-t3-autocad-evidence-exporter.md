# VS-T3 AutoCAD Evidence Exporter Specification

**Date:** 2026-08-04  
**Status:** Approved for implementation planning; implementation not started  
**Base SHA:** `2c796f8f2f42b95e838df65b3c197979bf6caa68` (`origin/main`)  
**Supported scope:** Windows, Python 3.11, AutoCAD Mechanical 2027, existing
managed .NET/File IPC boundary

## 1. Purpose and boundary

VS-T3 adds one deterministic, read-only AutoCAD evidence operation. It exports
render, entity-map, and measurement evidence for one configured drawing region
while proving that the drawing was not changed.

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

The only source of truth for the drawing state is the exact field
`Visual Run Manifest.latest_mutation_sha256`:

```text
Visual Run Manifest.latest_mutation_sha256
        ↓
VS-T3 request
        ↓
read-only evidence export
```

VS-T3 must use the field name `latest_mutation_sha256` everywhere. It must not
introduce `current_mutation_hash`, a local mutation counter, an inferred
mutation value, or any parallel mutation-state authority.

The orchestrator must read and validate the manifest before dispatch, copy its
exact `latest_mutation_sha256` into the request, and revalidate the manifest
before accepting the result. VS-T3 never updates the manifest and never
decides whether a mutation is current.

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
must not open a write transaction, append or erase entities, change layers,
save, close with save, or modify any manifest or mutation record.

### 3.3 Deterministic region configuration

The request identifies a fixed Model Space bounding box, pixel size,
background, included/excluded layers, and measurement references. The
canonical representation of this configuration is hashed as
`region_config_sha256`. No free-form viewport state or screen-pixel coordinate
is accepted as Model Space geometry.

### 3.4 Evidence is immutable after capture

The Python orchestrator writes evidence to a temporary sibling directory and
atomically promotes it only after all identity, freshness, hash, DBMOD, and
read-only checks pass. An evidence package is never repaired in place.

## 4. Request contract

The request is closed-schema validated and hash-bound. The orchestrator fills
`latest_mutation_sha256` from the manifest; it does not calculate a substitute.

```json
{
  "operation": "visual_evidence_export",
  "request_id": "REQ-VS-T3-001",
  "drawing_full_path": "D:\\project\\vehicle.dwg",
  "run_id": "RUN-001",
  "region_id": "SIDE-CABIN",
  "latest_mutation_sha256": "<64 lowercase hex>",
  "expected_drawing_sha256": "<64 lowercase hex>",
  "region": {
    "model_bbox_mm": [0, 0, 2400, 2200],
    "pixel_size": [1600, 1200],
    "background": "WHITE",
    "include_layers": ["CABIN", "CENTER"],
    "exclude_layers": ["TEXT", "DIM"]
  },
  "measurements": []
}
```

Required request rules:

- `drawing_full_path` is an absolute path and is normalized before comparison.
- `run_id`, `region_id`, and `request_id` are non-empty stable identifiers.
- `latest_mutation_sha256` and `expected_drawing_sha256` are valid lowercase
  SHA-256 values.
- `region` is closed and canonicalized before its hash is computed.
- Measurement requests contain stable IDs and approved entity or datum
  references; they do not create native dimension entities.
- Missing or invalid `latest_mutation_sha256` is a hard failure.

## 5. Managed AutoCAD read-only boundary

The managed operation must perform the following sequence:

1. Verify that the active document's normalized full path equals
   `drawing_full_path`.
2. Verify the request's identity and `latest_mutation_sha256` are the values
   authorized by the validated manifest context.
3. Capture `DBMOD` and the source drawing SHA-256 before reading.
4. Read entities with read-only database access in deterministic order.
5. Resolve and collect only the requested measurements.
6. Render the fixed Model Space region with the requested pixel size and
   controlled layer set.
7. Capture `DBMOD` and the source drawing SHA-256 after the operation.
8. Return success only when every read-only invariant is proven.

The operation must not:

- save, autosave, close with save, or change the active document;
- open a write transaction or call a write-capable gateway method;
- append, erase, transform, or edit entity data;
- change layers, view state persisted to the drawing, or document metadata;
- create dimension, block, or other CAD entities;
- modify the Visual Run Manifest or any mutation state;
- return mutation handles or a mutation operation plan.

The result uses `changed=false` as a required assertion, not as an inferred
default. Any inability to prove the invariant produces a failed result that
the orchestrator must reject.

## 6. Result contract

The result is closed-schema validated and must carry the full evidence binding:

```json
{
  "operation": "visual_evidence_export",
  "success": true,
  "changed": false,
  "entity_handles": [],
  "payload": {
    "run_id": "RUN-001",
    "drawing_path": "D:\\project\\vehicle.dwg",
    "drawing_sha256_before": "<hash>",
    "drawing_sha256_after": "<same hash>",
    "dbmod_before": 0,
    "dbmod_after": 0,
    "latest_mutation_sha256": "<manifest value>",
    "region_id": "SIDE-CABIN",
    "region_config_sha256": "<hash>",
    "render": {},
    "entities": [],
    "measurements": [],
    "captured_at_utc": "2026-08-04T00:00:00Z"
  }
}
```

The minimum binding in the result/evidence manifest is:

```json
{
  "run_id": "RUN-001",
  "drawing_path": "D:\\project\\vehicle.dwg",
  "drawing_sha256": "<hash>",
  "latest_mutation_sha256": "<manifest value>",
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

## 7. Evidence artifact layout

The Python evidence writer stores each package under the run's evidence root:

```text
runs/<run_id>/iterations/<region_id>/evidence-<iteration>/
├── cad-render.png
├── entities.json
├── measurements.json
├── render-manifest.json
└── evidence-manifest.json
```

Every artifact is SHA-256 hashed. `render-manifest.json` records the Model
Space bounding box, pixel size, background, included/excluded layers, render
hash, entity-map hash, and measurement hash. `evidence-manifest.json` records
the request identity, all required binding fields, and every artifact hash.

The writer uses a temporary sibling directory and an atomic rename. It must
not leave a final evidence directory after a rejected export.

## 8. Fail-closed and freshness policy

The exporter/orchestrator must reject the request or result when any of these
conditions holds:

- the Visual Run Manifest is missing, invalid, or changed during export;
- `manifest.latest_mutation_sha256` is missing, invalid, or empty;
- the request mutation hash differs from the manifest value;
- the request drawing path differs from the manifest's target path;
- the expected pre-dispatch drawing SHA-256 does not match the live drawing;
- the AutoCAD operation returns `changed=true`;
- `DBMOD` changes during export;
- the drawing SHA-256 changes during export;
- the returned full path or drawing identity cannot be verified;
- returned run, mutation, region, or region-config identity differs from the
  request;
- the manifest or drawing changes before atomic artifact promotion;
- any required artifact hash is missing or incorrect;
- evidence is read after a later mutation has advanced the manifest.

Evidence created under a previous mutation is `STALE`, never `PASS`, and must
not be consumed by later Visual Supervisor, comparator, repair, or publication
stages. Freshness is checked when evidence is written and whenever it is read.
VS-T3 never repairs stale evidence and never updates
`latest_mutation_sha256`; a new request and a new export are required.

## 9. Ownership and authority

```text
Visual Run Manifest / Orchestrator:
  owns mutation state, request authorization, freshness, and evidence lifecycle

VS-T3:
  reads the authorized drawing, exports evidence, proves read-only invariants

Visual Supervisor:
  evaluates evidence; does not change mutation state

Codex:
  may consume evidence in later slices; may not change latest_mutation_sha256
  or reuse stale evidence
```

This keeps VS-T3 compatible with the project safety rules. It does not weaken
the existing human approval requirement for production mutation and does not
authorize production drawing save or repair.

## 10. Implementation boundaries

The future implementation is limited to the following boundaries:

- closed IPC request/result schemas and operation examples;
- managed evidence models, gateway methods, and dispatcher mapping;
- deterministic render, entity-map, and measurement projection helpers;
- Python `DotNetIPCClient` request/result adapter;
- Python evidence freshness validator and atomic artifact writer;
- focused contract, Python, managed .NET, and opt-in disposable live tests.

VS-T3 must not modify VS-T1 dimension-observer behavior, VS-T2 comparator
behavior, Visual Supervisor verdict authority, Codex repair planning,
mutation state, or publication logic.

## 11. Verification and acceptance criteria

VS-T3 is ready for implementation review only when:

1. The composite operation is closed-schema validated end-to-end.
2. Every result/evidence package contains all required binding fields,
   including the exact `latest_mutation_sha256` field.
3. Full-path, drawing-identity, `changed=false`, DBMOD, and before/after
   drawing-hash invariants fail closed.
4. A request/manifest mutation mismatch is rejected.
5. Evidence created before a later manifest mutation is rejected as `STALE`.
6. Artifact promotion is atomic and leaves no accepted output after failure.
7. Focused Python, .NET, IPC, and offline verifier checks pass.
8. The optional AutoCAD Mechanical live gate is recorded honestly as `PASS`,
   `SKIP`, or `NOT RUN`.
9. No mutation, visual verdict, repair, OpenAI/Codex bridge, or publication
   authority is added.

## 12. Explicit non-goals

VS-T3 does not:

- infer, create, or advance mutation state;
- modify, save, close-with-save, or publish a DWG;
- create or repair CAD entities;
- call ChatGPT, OpenAI, or Codex;
- decide visual similarity or issue `PASS`/`FAIL`;
- reuse evidence from an earlier mutation;
- replace the existing File IPC transport or package boundaries.
