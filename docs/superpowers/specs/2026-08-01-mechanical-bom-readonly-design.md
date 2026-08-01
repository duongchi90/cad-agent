# Mechanical BOM / Part Reference Read-Only Design

## Goal

Add a bounded `mechanical_bom` IPC operation that extracts direct ModelSpace block inserts and their `ATTRIB` values through the managed AutoCAD .NET API, without modifying the drawing and without referencing AutoCAD Mechanical SDK, COM/ActiveX, ARX, or native code.

## Context

The current AutoCAD .NET plugin uses a read-only drawing gateway, a versioned JSON file IPC contract, and a default `NoOpMechanicalAdapter`. The adapter is not currently reachable through `OperationDispatcher`. This feature makes the smallest useful managed implementation available while preserving the existing Option A boundary.

## Alternatives considered

### A. Managed generic block/attribute extraction — selected

Read `BlockReference` and `AttributeReference` objects from ModelSpace inside a read-only transaction. This is deterministic, testable without AutoCAD, and keeps the main plugin free of Mechanical-specific dependencies. It provides a useful BOM/Part Reference input, but intentionally does not claim Mechanical Structure or Content Library semantics.

### B. AutoCAD Mechanical SDK or ActiveX

This could expose richer Mechanical-specific metadata, but it violates the approved Option A dependency boundary, would require a separate project and installation/runtime contract, and cannot be validated on every Windows machine. It is out of scope for this slice.

### C. Python-side DXF parsing

This would be quick for offline files, but would duplicate drawing semantics outside the plugin and would not implement the requested .NET adapter. It is not selected.

## Scope

Included:

1. A new IPC operation named `mechanical_bom`.
2. A managed `IMechanicalAdapter` implementation that reports the operation as available.
3. A drawing-gateway boundary for reading direct ModelSpace `BlockReference` inserts and their direct `AttributeReference` values.
4. C# contract/dispatcher integration and offline unit tests.
5. Python client support and contract tests.
6. Contract examples and a disposable-DXF live smoke test.

Excluded:

- Any entity mutation, save, balloon creation, Part Reference insertion, or Mechanical command invocation.
- Nested block traversal, exploded geometry, dynamic-block evaluation, Mechanical Structure traversal, Content Library lookup, quantity aggregation, or unit conversion.
- COM/ActiveX, ObjectARX, C++/CLI, native DLLs, or Mechanical SDK references.
- Changes to `scripts/verify.ps1` by the implementation Coder.
- Updates to `docs/STATUS.md` until integration and verification are complete.

## Contract

### Request

The request keeps schema version `1.0`; adding an operation is backward-compatible for clients that do not request it. The request shape remains unchanged:

```json
{
  "request_id": "bom-001",
  "schema_version": "1.0",
  "operation": "mechanical_bom",
  "drawing_full_path": "C:\\temp\\cadagent_bom_fixture.dxf",
  "drawing_sha256": null,
  "parameters": {},
  "approval": null
}
```

Rules:

- `drawing_full_path` is required and must be a full absolute Windows path.
- The path must match the active document after the same normalization used by existing operations.
- `parameters` must be an empty object. Filters are deliberately deferred so the first slice has one unambiguous result set.
- `approval` remains nullable and is not used because the operation is read-only.

### Result

The existing result envelope is used. `changed` is always `false`. `entity_handles` contains the returned component handles in the same order as `payload.components`.

```json
{
  "request_id": "bom-001",
  "success": true,
  "operation": "mechanical_bom",
  "drawing_full_path": "C:\\temp\\cadagent_bom_fixture.dxf",
  "changed": false,
  "entity_handles": ["2F"],
  "warnings": [],
  "errors": [],
  "started_at": "2026-08-01T10:00:00+00:00",
  "completed_at": "2026-08-01T10:00:00+00:00",
  "payload": {
    "component_count": 1,
    "components": [
      {
        "handle": "2F",
        "block_name": "COMP_FRAME",
        "attributes": [
          {"tag": "PART_ID", "value": "FRAME-001"}
        ]
      }
    ]
  }
}
```

Component rules:

- One component is emitted for every direct `BlockReference` found in ModelSpace, including inserts with zero attributes.
- `handle` is the insert handle as an uppercase hexadecimal AutoCAD handle string.
- `block_name` is the managed `BlockReference.Name` value.
- Each direct `AttributeReference` is emitted as one `{tag,value}` item. Duplicate tags are preserved as separate items.
- Attribute tags are trimmed and normalized to uppercase for stable semantic comparison. Attribute values are returned as strings without lossy numeric conversion; null-like API values become an empty string.
- Components are sorted by ordinal handle string. Attributes are sorted by ordinal tag, then ordinal value.
- No nested block references are traversed.

Failure rules:

- A missing active document or a path mismatch returns `success=false`, `changed=false`, and a descriptive error, consistent with `close_disposable`.
- An unavailable adapter returns `success=false` with status `not_supported`; the default fallback remains `NoOpMechanicalAdapter`.
- An unreadable individual insert is skipped with a warning; a transaction-level failure returns `success=false` rather than a partial success.

## Architecture and boundaries

### Managed drawing boundary

Add a focused `IMechanicalDrawingGateway` beside `IDrawingGateway`:

```csharp
public interface IMechanicalDrawingGateway
{
    IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents();
}
```

`AutoCadDrawingGateway` implements both interfaces. Its Mechanical method opens a read-only transaction, enumerates ModelSpace, reads only `BlockReference` objects and direct attributes, and returns immutable snapshots. The existing review read path remains unchanged.

The snapshot types are managed, AutoCAD-independent records:

```csharp
public sealed record MechanicalAttributeSnapshot(string Tag, string Value);

public sealed record MechanicalComponentSnapshot(
    string Handle,
    string BlockName,
    IReadOnlyList<MechanicalAttributeSnapshot> Attributes);
```

### Adapter boundary

Add `ManagedMechanicalAdapter : IMechanicalAdapter`:

- `IsAvailable` is `true`.
- `GetCapabilities()` returns exactly `mechanical_bom`.
- `Execute(new MechanicalOperationRequest("mechanical_bom"))` reads the gateway and returns the snapshots with `Status="success"`.
- Other operation names return `not_supported` without reading the drawing.
- The adapter contains no AutoCAD API calls; AutoCAD access stays behind `IMechanicalDrawingGateway`.

Extend `MechanicalOperationResult` only with the data required by the operation: status, operation name, changed flag, warnings, errors, and component snapshots. Keep `NoOpMechanicalAdapter` behavior valid for fallback tests.

### Command and IPC wiring

`CommandContext` receives an optional mechanical adapter. Existing callers default to `NoOpMechanicalAdapter`; `CreateLive()` constructs `ManagedMechanicalAdapter` over the live gateway. `OperationDispatcher` adds a `mechanical_bom` route, verifies the active drawing path, invokes the adapter, and maps its snapshots to the result payload and `entity_handles`.

Add `mechanical_bom` to the C# and Python supported-operation sets, request validation, JSON contract operation enums, and client helper methods. Do not change the result envelope or schema version.

## Testing and acceptance

### Offline tests

- Adapter capability test: managed adapter is available and advertises only `mechanical_bom`.
- Adapter extraction test: a fake mechanical gateway returns multiple components; the adapter preserves values and operation status.
- Dispatcher success test: matching active path returns sorted components, handles, `changed=false`, and the expected payload.
- Dispatcher safety tests: path mismatch, unavailable adapter, invalid parameters, and non-supported operation names fail without mutation.
- Contract tests: request/result round-trip accepts `mechanical_bom`; unsupported parameters are rejected.
- Python tests: helper emits the exact empty-parameter request, recognizes the operation, validates the result envelope, and preserves payload data.

Every new production behavior must have a failing test observed before its implementation is written.

### Live smoke

Use a newly generated disposable DXF under `C:\temp`, containing at least one block insert with one attribute and one block insert without attributes. Load the plugin in a separate AutoCAD test process, dispatch `mechanical_bom`, and verify:

- result is `PASS` only when the exact component and attribute payload is observed;
- `changed=false`;
- the source DXF is not saved or mutated;
- the live result status is explicitly recorded as `PASS`, `SKIP`, or `NOT RUN`.

No live `PASS` may be inferred from build or unit-test results.

### Verification

The integration task runs focused C# and Python tests, then the repository verifier. Only the integration task may modify `scripts/verify.ps1`, and only the final integration step may update `docs/STATUS.md`.

## Completion criteria

The feature is complete when the contract, managed adapter, dispatcher, Python helper, offline tests, and disposable-DXF live smoke all satisfy the rules above; the diff is reviewed; the verifier passes; the live status is explicitly recorded; and the integrated branch is merged and pushed to `origin/main`.
