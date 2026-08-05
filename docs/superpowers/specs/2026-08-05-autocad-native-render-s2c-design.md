# S2C AutoCAD-Native Layout Capture Design

Status: approved implementation design for Issue #60. Production implementation
has not started.

## 1. Identity and scope

- Issue: #60 — S2C actual read-only AutoCAD-native layout capture.
- Exact implementation base:
  `3d0aa999904f384efa4eb42a81637e4270591859`.
- Branch: `task/s2c-autocad-native-render`.
- Accepted predecessors:
  - S2A closed request/evidence contract;
  - S2B File IPC envelope, validator, client adapter, and fail-closed dispatcher
    seam.

S2C replaces only the deterministic `NATIVE_RENDER_NOT_IMPLEMENTED` dispatcher
path with actual native capture inside AutoCAD Mechanical 2027. It produces one
request-owned PNG or one-page PDF from one named paper-space layout. It does not
add recognition, source fusion, drawing mutation, verdict, approval, repair,
publication, or a new transport.

## 2. Architectural decision

The existing boundary remains authoritative:

```text
DotNetIPCClient.native_render_evidence
  -> existing JSON File IPC
  -> CADAGENT_DISPATCH
  -> existing ContractValidator
  -> existing OperationDispatcher
  -> IDrawingGateway.ReadNativeRenderEvidence
  -> CommandContext.AutoCadDrawingGateway
  -> AutoCadNativeRenderReader
  -> AutoCAD Plot API
  -> NativeRenderArtifactBoundary
```

The live `AutoCadDrawingGateway` is the private nested class already owned by
`Commands/CommandContext.cs`; no second concrete gateway file or capability
interface is created. `OperationDispatcher` does not reference AutoCAD plotting
classes or filesystem artifact mechanics directly.

Rejected alternatives:

- a second gateway or capability cast;
- a second File IPC transport, queue, dispatcher, or protocol;
- calling the native reader directly from `OperationDispatcher`;
- reusing the simulated/preview-oriented visual evidence exporter;
- a production fake, placeholder, or fallback renderer.

## 3. Contract freeze and field semantics

S2A/S2B schema versions, request shape, result payload shape, Python production
validators, and `DotNetIPCClient.native_render_evidence()` are frozen.

- `layout.name` is the actual AutoCAD layout selector.
- `layout.identity` is caller-owned correlation metadata. It is copied unchanged
  into the evidence and remains request/result-bound by the existing validator.
  It is not represented as an AutoCAD ObjectId, handle, or independent proof of
  layout identity.
- `artifact.relative_path` remains a safe POSIX-relative path in the accepted
  result contract and is interpreted relative to the existing IPC root.
- No `artifact_directory`, device name, media name, output path, verdict,
  approval, or publication field is added.

The accepted S2B failure example may be replaced by a closed success example.
That example update does not alter a schema or production validator.

## 4. Initial supported profile

The first S2C production profile is intentionally narrow:

```text
layout: named paper-space layout only
paper_size: A4
background: white
dpi: 300
fit_to_paper: true
plot_style: monochrome.ctb
artifact_kind: PNG or PDF
```

All other option combinations fail closed. This is a production capability
policy, not a schema restriction; later expansion requires a separate task.

Device selection is internal and fixed:

- PDF uses one approved AutoCAD PDF PC3 available on the AutoCAD Mechanical
  2027 acceptance workstation.
- PNG uses one approved raster PNG PC3 available on the same workstation.

The request cannot choose a device. The reader enumerates the selected device's
supported media and requires an exact, unambiguous A4 mapping. For raster output,
its pixel/media capability must be proven by the live gate. Missing device,
missing media, unsupported custom property, incompatible plot style, or an
ambiguous mapping produces a deterministic failure with an empty payload. There
is no nearest-match or alternate-device fallback.

The implementation record must state the exact PC3 identifiers and canonical
media identifiers that passed live acceptance.

## 5. Native plot pipeline

`AutoCadNativeRenderReader` owns the AutoCAD-specific capture sequence.

1. Confirm that the gateway's active document is the requested drawing under
   the existing full-path comparison rules.
2. Hash the on-disk DWG and require equality with `drawing_sha256`.
3. Read DBMOD and require a non-negative value.
4. Snapshot each session variable that will be changed. Foreground plotting may
   require temporarily setting `BACKGROUNDPLOT` to `0`.
5. Open the layout dictionary in a read-only transaction, select exactly one
   layout by `layout.name`, and reject Model space.
6. Create a temporary `PlotSettings` object and copy settings from the selected
   layout. Never write the temporary object into a database dictionary.
7. Apply only the approved profile to the temporary copy through
   `PlotSettingsValidator`.
8. Build `PlotInfo`, set the selected layout ObjectId and temporary overrides,
   validate it with `PlotInfoValidator`, then run one foreground `PlotEngine`
   job to the temporary artifact path.
9. Wait for the plot pipeline to finish before validating output bytes.
10. Dispose all plot objects and restore session state in `finally`-equivalent
    logic.

The reader never changes the current layout and never calls Save, SaveAs,
CloseAndSave, entity/layer/style mutation, or any database write operation.
Transactions used to resolve the layout are read-only.

## 6. Request-owned artifact boundary

The helper is named `NativeRenderArtifactBoundary`. It is a bounded output
boundary, not an artifact registry, manifest owner, transport, or general store.

The only final paths are:

```text
<CAD_AGENT_DOTNET_IPC_DIR>/native-render/<request_id>/artifact.png
<CAD_AGENT_DOTNET_IPC_DIR>/native-render/<request_id>/artifact.pdf
```

The returned paths are exactly:

```text
native-render/<request_id>/artifact.png
native-render/<request_id>/artifact.pdf
```

Boundary rules:

- validate `request_id` again before using it in a path;
- reject path separators, drive prefixes, control characters, empty/dot/
  traversal segments, and canonical containment escapes;
- reject any pre-existing request directory, ownership claim, or final artifact;
- create a race-safe exclusive claim so concurrent duplicate requests cannot
  both publish;
- use a temporary file inside the request directory with the same `.png` or
  `.pdf` suffix required by the native plotter;
- never accept a caller-provided output path;
- publish with a no-overwrite atomic move only after byte validation and all
  read-only/session invariants pass;
- do not clean old request directories in S2C.

A pre-existence check plus an exclusive claim is required: the claim resolves
the race in which two processes observe a missing directory simultaneously.
The losing process fails closed and must not delete a directory or file that may
belong to the winner.

## 7. Artifact validation

Temporary output is not evidence until it passes format validation.

PNG validation requires:

- standard PNG signature;
- an IHDR chunk in the required location;
- positive width and height within the accepted contract limits;
- width multiplied by height no greater than the accepted pixel-count limit;
- complete file bytes, not an empty or truncated header.

PDF validation requires:

- a valid PDF header;
- an EOF trailer near the end of the file;
- a parser-confirmed page count of exactly one;
- complete, non-empty bytes.

SHA-256 is calculated from the validated artifact bytes. The final atomic move
is the last irreversible action. The result is built from the validated
metadata and cannot claim an artifact before the final file exists.

On failure, temporary files are removed when owned safely. A completed final
artifact is never overwritten or silently replaced. Cleanup of orphaned or old
request directories is a separate maintenance concern.

## 8. Read-only and restoration boundary

A successful result requires all of the following:

```text
changed == false
entity_handles == []
dbmod_before >= 0
dbmod_after >= 0
dbmod_before == dbmod_after
drawing_hash_before == drawing_hash_after
session_state_restored == true
```

Every session variable changed by the reader is restored even when plotting,
validation, or publication fails. Restoration failure is itself a failed
operation. The reader re-reads DBMOD and the on-disk DWG hash after plotting and
restoration, before publishing the final artifact.

Failure results use the existing envelope, contain one deterministic error code
or bounded message, retain `changed=false` and an empty entity-handle list, and
have `payload={}`. A failed operation never returns partial evidence metadata.

## 9. Error classes and deterministic failure categories

S2C may return bounded failures for these categories without changing the
contract:

- active drawing mismatch;
- drawing hash mismatch;
- invalid or Model-space layout;
- unsupported render profile;
- approved device unavailable;
- exact media unavailable or ambiguous;
- plot style unavailable or incompatible;
- another plot already in progress;
- duplicate request/artifact ownership collision;
- native plot failure or cancellation;
- invalid/truncated PNG or PDF;
- DBMOD or drawing-hash mutation;
- session restoration failure;
- safe-path or publication failure.

All categories fail closed with an empty payload. No category implies a visual
verdict, engineering approval, repair recommendation, or publication state.

## 10. Testing strategy

### Offline .NET tests

- artifact-path validation, containment, exclusive claim, duplicate collision,
  temporary-file cleanup, and no-overwrite publication;
- PNG header/IHDR/dimension validation;
- PDF header/trailer/page-count validation;
- dispatcher delegation and exact result mapping;
- gateway failure mapping to empty payload;
- success result passes the existing `ContractValidator`;
- read-only boundary rejects DBMOD/hash/session mismatches;
- all existing gateway test doubles compile and preserve previous behavior.

AutoCAD plotting calls should be isolated behind the native reader's smallest
internal seam needed for deterministic tests. That seam must not become a new
public transport or production renderer abstraction.

### Python/contract-adjacent tests

- the result example becomes one closed success envelope;
- existing Python client still validates request/result matching;
- generic unsupported/error results remain surfaced correctly;
- existing operation allowlists and schemas remain unchanged.

### Live AutoCAD Mechanical 2027 tests

- successful A4/white/300-DPI PNG capture;
- successful A4/white/300-DPI one-page PDF capture;
- exact canonical output path and SHA-256;
- PNG dimensions and PDF page count;
- unchanged DBMOD, file hash, current layout, and required session state;
- duplicate request refusal;
- missing layout/device/media and unsupported option refusal;
- no `NATIVE_RENDER_NOT_IMPLEMENTED` on successful requests.

## 11. Allowlist

Exactly the 20 files listed in Issue #60 may change. No schema, Python
production module, dependency, lock, project file, `STATUS.md`, `HANDOFF.md`, or
unrelated test file may change.

If a previously unidentified `IDrawingGateway` implementation or test double
causes a compile error, the worker stops and reports its exact path. The worker
does not silently expand scope.

## 12. Acceptance boundary

Offline tests, Release/x64 build, C# tests, canonical verification, architecture
checks, diff checks, and hosted synthetic-merge CI are necessary but not
sufficient. S2C is accepted only after real AutoCAD Mechanical 2027 live PNG and
PDF gates pass on the exact reviewed head.

Private-data acceptance remains `NOT RUN` unless separately authorized. S3B,
R1C, source fusion, registry, authority, revision, repair, verdict, and
publication remain locked.