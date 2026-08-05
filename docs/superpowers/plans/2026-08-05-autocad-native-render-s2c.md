# S2C AutoCAD-Native Layout Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the S2B fail-closed seam with one real, read-only AutoCAD Mechanical 2027 native layout capture path that publishes a request-owned PNG or one-page PDF through the existing File IPC contract.

**Architecture:** The existing `OperationDispatcher` delegates to a new `IDrawingGateway.ReadNativeRenderEvidence` method. The nested live gateway in `CommandContext.cs` calls one AutoCAD-specific reader, which uses temporary plot settings and the official Plot API. A request-owned artifact boundary handles safe paths, exclusive ownership, byte validation, and no-overwrite publication under the existing IPC root.

**Tech Stack:** C# / .NET 10 Windows, AutoCAD Mechanical 2027 managed API, Autodesk plotting services, existing JSON File IPC, xUnit, Python 3.11, pytest, pypdf for live PDF verification, Ruff, repository architecture checker and canonical verifier.

## Global Constraints

- Exact implementation base is `3d0aa999904f384efa4eb42a81637e4270591859`.
- Work only on `task/s2c-autocad-native-render` for Issue #60.
- The 20-file Issue #60 allowlist is closed.
- S2A/S2B schemas, schema versions, Python production validators, File IPC transport, and `DotNetIPCClient.native_render_evidence()` do not change.
- The only supported profile is paper-space A4, white background, 300 DPI, fit-to-paper, `monochrome.ctb`, and PNG or PDF.
- No fallback device, media, plot style, renderer, or output path.
- No drawing mutation, Save/SaveAs/CloseAndSave, current-layout switch, verdict, approval, repair, publication, dependency, lock, project-file, `STATUS.md`, or `HANDOFF.md` change.
- Final acceptance requires real AutoCAD Mechanical 2027 live PNG and PDF evidence; offline success is not sufficient.
- Stop and report to the PO if another existing `IDrawingGateway` implementation or test double outside the allowlist must change.

---

## File structure locked by this plan

### Existing files modified

- `contracts/autocad-ipc/examples/native-render-evidence-result.json`
  - replace the obsolete unsupported result example with one closed success result example.
- `mcp_integration_lib/tests/test_autocad_render_evidence_ipc.py`
  - assert the success example while preserving client error-surfacing coverage.
- `tests/test_autocad_render_evidence_ipc_contracts.py`
  - validate the success example against the existing result schema and contract.
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`
  - parse the existing request fields, delegate to the gateway, and map the returned snapshot to the existing result payload.
- `autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs`
  - add the native-render read method.
- `autocad_plugin/CadAgent.AutoCAD2027/Drawing/NullDrawingGateway.cs`
  - fail explicitly when no active drawing exists.
- `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`
  - implement the new gateway method in the existing nested `AutoCadDrawingGateway` and pass the existing IPC root to the reader.
- the four existing .NET test files listed in Issue #60
  - update only the affected gateway test doubles and native-render assertions.
- `mcp_integration_lib/tests/test_dotnet_ipc_live.py`
  - add exact live PNG/PDF and failure probes.

### New production files

- `autocad_plugin/CadAgent.AutoCAD2027/Drawing/NativeRenderModels.cs`
  - closed C# request/options/layout/evidence/artifact records and deterministic conversion helpers.
- `autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadNativeRenderReader.cs`
  - AutoCAD-only read-only layout resolution, approved profile policy, Plot API execution, restoration, and invariant checks.
- `autocad_plugin/CadAgent.AutoCAD2027/Drawing/NativeRenderArtifactBoundary.cs`
  - request-owned path reservation, exclusive claim, temporary path, PNG/PDF byte inspection, SHA-256, and no-overwrite atomic publication.

### New test files

- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/NativeRenderArtifactBoundaryTests.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/NativeRenderBoundaryTests.cs`

---

## Task 1: Convert the accepted result example from unsupported to success

**Files:**
- Modify: `contracts/autocad-ipc/examples/native-render-evidence-result.json`
- Modify: `mcp_integration_lib/tests/test_autocad_render_evidence_ipc.py`
- Modify: `tests/test_autocad_render_evidence_ipc_contracts.py`

**Interfaces:**
- Consumes: the existing `autocad-native-render-evidence-1.0` payload schema.
- Produces: one closed success example with `native-render/render-request-001/artifact.png`.

- [ ] **Step 1: Change Python tests first so the current failure example is rejected**

Update the example assertions to require:

```python
assert result_envelope["success"] is True
assert result_envelope["changed"] is False
assert result_envelope["entity_handles"] == []
assert result_envelope["errors"] == []
assert result_envelope["payload"]["renderer"] == "AUTOCAD_NATIVE"
assert result_envelope["payload"]["artifact"]["relative_path"] == (
    "native-render/render-request-001/artifact.png"
)
```

In `tests/test_autocad_render_evidence_ipc_contracts.py`, validate the payload with the existing schema/validator and assert it contains no verdict, approval, repair, or publication fields.

- [ ] **Step 2: Run the two focused tests and verify RED**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_autocad_render_evidence_ipc.py tests/test_autocad_render_evidence_ipc_contracts.py -q -p no:cacheprovider
```

Expected: failure because the checked-in result example still has `success=false`, `NATIVE_RENDER_NOT_IMPLEMENTED`, and an empty payload.

- [ ] **Step 3: Replace only the result example**

Use a valid PNG payload that exactly matches the existing request example:

```json
{
  "request_id": "render-request-001",
  "success": true,
  "operation": "native_render_evidence",
  "drawing_full_path": "C:\\drawings\\sample.dwg",
  "changed": false,
  "entity_handles": [],
  "warnings": [],
  "errors": [],
  "started_at": "2026-08-05T08:00:00Z",
  "completed_at": "2026-08-05T08:00:03Z",
  "payload": {
    "schema_version": "autocad-native-render-evidence-1.0",
    "request_id": "render-request-001",
    "run_id": "run-001",
    "drawing_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "latest_mutation_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "visual_run_manifest_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "layout": { "identity": "layout-001", "name": "Layout1" },
    "artifact_kind": "PNG",
    "render_options": {
      "background": "white",
      "dpi": 300,
      "fit_to_paper": true,
      "paper_size": "A4",
      "plot_style": "monochrome.ctb"
    },
    "renderer": "AUTOCAD_NATIVE",
    "artifact": {
      "relative_path": "native-render/render-request-001/artifact.png",
      "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      "width": 2480,
      "height": 3508
    },
    "capture_timestamp": "2026-08-05T08:00:03Z",
    "changed": false,
    "dbmod_before": 0,
    "dbmod_after": 0,
    "warnings": []
  }
}
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Expected: both files pass without modifying any schema or Python production module.

- [ ] **Step 5: Commit the example/test transition**

```powershell
git add contracts/autocad-ipc/examples/native-render-evidence-result.json mcp_integration_lib/tests/test_autocad_render_evidence_ipc.py tests/test_autocad_render_evidence_ipc_contracts.py
git commit -m "test: promote native render success example"
```

---

## Task 2: Add closed C# native-render models and gateway method

**Files:**
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/NativeRenderModels.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/NullDrawingGateway.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/CommandGuardTests.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Review/ReviewEngineTests.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`

**Interfaces:**
- Produces:

```csharp
public sealed record NativeRenderLayout(string Identity, string Name);

public sealed record NativeRenderOptions(
    string Background,
    long Dpi,
    bool FitToPaper,
    string PaperSize,
    string PlotStyle);

public sealed record NativeRenderRequest(
    string RequestId,
    string RunId,
    string DrawingFullPath,
    string DrawingSha256,
    string LatestMutationSha256,
    string VisualRunManifestSha256,
    NativeRenderLayout Layout,
    string ArtifactKind,
    NativeRenderOptions RenderOptions);

public sealed record NativeRenderArtifact(
    string RelativePath,
    string Sha256,
    long? Width,
    long? Height,
    long? PageCount);

public sealed record NativeRenderEvidenceSnapshot(
    string RequestId,
    string RunId,
    string DrawingSha256,
    string LatestMutationSha256,
    string VisualRunManifestSha256,
    NativeRenderLayout Layout,
    string ArtifactKind,
    NativeRenderOptions RenderOptions,
    NativeRenderArtifact Artifact,
    DateTimeOffset CaptureTimestamp,
    int DbmodBefore,
    int DbmodAfter,
    IReadOnlyList<string> Warnings);
```

- Extends:

```csharp
NativeRenderEvidenceSnapshot ReadNativeRenderEvidence(NativeRenderRequest request);
```

- [ ] **Step 1: Add compile-time tests that call the new gateway method**

In allowed test doubles, add a deterministic method implementation. The dispatcher test double should track `ReadNativeRenderEvidenceCallCount` and return a supplied snapshot. Other test doubles may throw `InvalidOperationException` because those test paths do not invoke native rendering.

- [ ] **Step 2: Run Release/x64 test compilation and verify RED**

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 -p:AutodeskReferenceDir="$ref" --no-restore
```

Expected: missing model types and interface member.

- [ ] **Step 3: Add the records and interface member**

Keep all records closed and immutable. Add conversion helpers only for deterministic payload generation; do not add filesystem, AutoCAD, or transport logic to the model file.

`NullDrawingGateway.ReadNativeRenderEvidence` must throw:

```csharp
throw new InvalidOperationException(
    "No active drawing is available for native render evidence.");
```

- [ ] **Step 4: Run the .NET test project and verify GREEN**

Expected: all pre-existing tests compile and pass. If an implementation outside the Issue #60 allowlist fails to compile, stop and report its exact path.

- [ ] **Step 5: Commit**

```powershell
git add autocad_plugin/CadAgent.AutoCAD2027/Drawing/NativeRenderModels.cs autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs autocad_plugin/CadAgent.AutoCAD2027/Drawing/NullDrawingGateway.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/CommandGuardTests.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Review/ReviewEngineTests.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs
git commit -m "feat: add native render gateway models"
```

---

## Task 3: Build the request-owned artifact boundary with TDD

**Files:**
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/NativeRenderArtifactBoundary.cs`
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/NativeRenderArtifactBoundaryTests.cs`

**Interfaces:**
- Produces:

```csharp
public sealed class NativeRenderArtifactBoundary
{
    public NativeRenderArtifactReservation Reserve(
        string ipcRoot,
        string requestId,
        string artifactKind);

    public NativeRenderArtifact Publish(
        NativeRenderArtifactReservation reservation);
}

public sealed class NativeRenderArtifactReservation : IDisposable
{
    public string RequestDirectory { get; }
    public string TemporaryPath { get; }
    public string FinalPath { get; }
    public string RelativePath { get; }
    public bool IsPublished { get; }
}
```

The reservation owns a same-directory temporary path and an exclusive claim. `Dispose()` removes only an owned temporary file and releases disposable handles; it never deletes a published final artifact or another request's directory.

- [ ] **Step 1: Write path and ownership tests**

Cover exact rejection of:

```text
../x
x/y
x\y
C:x
C:\x
empty
control characters
pre-existing request directory
pre-existing claim
pre-existing final artifact
```

Cover concurrent reservation attempts for the same `request_id`: exactly one succeeds. Cover distinct request IDs: both succeed.

- [ ] **Step 2: Write PNG validation tests**

Construct minimal valid PNG bytes with a standard signature and IHDR. Assert returned width/height. Reject:

- bad signature;
- missing/truncated IHDR;
- zero dimensions;
- dimensions above 100000;
- pixel count above 100000000;
- empty/truncated files.

- [ ] **Step 3: Write PDF validation tests**

Use a minimal one-page PDF fixture in the test source. Reject missing `%PDF-`, missing terminal `%%EOF`, and empty/truncated files. Production returns `page_count=1` only because S2C executes one layout as one sheet; the live Python gate independently opens the result with `pypdf` and confirms one page.

- [ ] **Step 4: Write publication tests**

Assert:

- validation occurs while output is temporary;
- final move does not overwrite;
- final relative path is exactly `native-render/<request_id>/artifact.<suffix>`;
- SHA-256 matches final bytes;
- failed validation leaves no final artifact;
- disposing an unpublished reservation removes its owned temporary file;
- disposing a published reservation preserves the final file.

- [ ] **Step 5: Run tests and verify RED**

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj -c Release -p:Platform=x64 -p:AutodeskReferenceDir="$ref" --filter NativeRenderArtifactBoundaryTests
```

- [ ] **Step 6: Implement minimal boundary and verify GREEN**

Use canonical `Path.GetFullPath` containment with a trailing separator comparison. Use `FileMode.CreateNew` for the exclusive claim and no-overwrite publication semantics. Do not use a check-then-overwrite sequence.

- [ ] **Step 7: Commit**

```powershell
git add autocad_plugin/CadAgent.AutoCAD2027/Drawing/NativeRenderArtifactBoundary.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/NativeRenderArtifactBoundaryTests.cs
git commit -m "feat: add request-owned render artifact boundary"
```

---

## Task 4: Replace dispatcher unsupported behavior with gateway delegation

**Files:**
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`

**Interfaces:**
- Consumes: existing validated `IpcRequest` fields and `IDrawingGateway.ReadNativeRenderEvidence`.
- Produces: existing `IpcResult` success payload for operation `native_render_evidence`.

- [ ] **Step 1: Replace the existing fail-closed test with delegation tests**

Assert one valid request:

- invokes `ReadNativeRenderEvidence` exactly once;
- maps all request fields exactly;
- returns `success=true`, `changed=false`, empty entity handles/errors;
- emits the exact existing evidence payload shape;
- passes `ContractValidator.ValidateResult`.

Add failure tests where the gateway throws a bounded `InvalidOperationException`: result is `success=false`, `changed=false`, empty handles, empty payload, and one deterministic error.

Keep a test proving unrelated operations retain their behavior.

- [ ] **Step 2: Run dispatcher tests and verify RED**

Expected: current dispatcher returns `NATIVE_RENDER_NOT_IMPLEMENTED` and never calls the gateway.

- [ ] **Step 3: Implement request parsing and delegation**

The dispatcher may parse only fields already accepted by `ContractValidator`. Use exact type checks and fail closed if any required property cannot be converted. Do not duplicate schema-level policy in a new transport validator.

Map `NativeRenderEvidenceSnapshot` to a dictionary containing exactly the accepted payload fields. For PNG include only `relative_path`, `sha256`, `width`, and `height`. For PDF include only `relative_path`, `sha256`, and `page_count`.

- [ ] **Step 4: Run focused tests and verify GREEN**

- [ ] **Step 5: Commit**

```powershell
git add autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs
git commit -m "feat: delegate native render evidence through gateway"
```

---

## Task 5: Implement read-only invariant helpers before Plot API code

**Files:**
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/NativeRenderModels.cs`
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/NativeRenderBoundaryTests.cs`

**Interfaces:**
- Produces pure helpers that validate the supported profile and final invariants without an AutoCAD process.

```csharp
public static class NativeRenderPolicy
{
    public static void EnsureSupported(NativeRenderRequest request);
    public static void EnsureReadOnly(
        int dbmodBefore,
        int dbmodAfter,
        string drawingHashBefore,
        string drawingHashAfter,
        bool sessionStateRestored);
}
```

- [ ] **Step 1: Write supported-profile tests**

Accept exactly:

```text
A4 / white / 300 / fit_to_paper=true / monochrome.ctb / PNG
A4 / white / 300 / fit_to_paper=true / monochrome.ctb / PDF
```

Reject Model layout name, black background, other DPI, `fit_to_paper=false`, other paper size, other style, or other artifact kind.

- [ ] **Step 2: Write read-only invariant tests**

Reject negative DBMOD, unequal DBMOD, unequal hashes, and failed restoration. Accept only the complete invariant set.

- [ ] **Step 3: Implement and verify GREEN**

Use ordinal comparisons for contract values and lowercase SHA-256 strings already validated by the existing contract.

- [ ] **Step 4: Commit**

```powershell
git add autocad_plugin/CadAgent.AutoCAD2027/Drawing/NativeRenderModels.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/NativeRenderBoundaryTests.cs
git commit -m "feat: enforce native render read-only policy"
```

---

## Task 6: Implement the AutoCAD-native reader and Plot API pipeline

**Files:**
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadNativeRenderReader.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/CommandGuardTests.cs`

**Interfaces:**
- Produces:

```csharp
public static class AutoCadNativeRenderReader
{
    public static NativeRenderEvidenceSnapshot Capture(
        Autodesk.AutoCAD.ApplicationServices.Document document,
        NativeRenderRequest request,
        string ipcDirectory,
        DateTimeOffset captureTimestamp);
}
```

The nested `AutoCadDrawingGateway` implementation is:

```csharp
public NativeRenderEvidenceSnapshot ReadNativeRenderEvidence(
    NativeRenderRequest request) =>
    AutoCadNativeRenderReader.Capture(
        _document,
        request,
        _ipcDirectory,
        DateTimeOffset.UtcNow);
```

- [ ] **Step 1: Add command/gateway wiring tests**

Ensure the live gateway continues to receive the existing IPC root and the command path does not create another store or dispatcher. Existing close-without-saving and mechanical paths remain unchanged.

- [ ] **Step 2: Implement preflight**

In order:

1. `NativeRenderPolicy.EnsureSupported(request)`.
2. confirm the document/database exists and filename matches the request path;
3. hash the on-disk DWG with SHA-256 and compare to the request;
4. read DBMOD and reject negative values;
5. reserve the request artifact boundary;
6. snapshot `BACKGROUNDPLOT` and any other session variable the implementation actually changes.

Do not reserve or create a final artifact before path/hash/profile checks pass.

- [ ] **Step 3: Resolve the layout read-only**

Use a read-only transaction over `Database.LayoutDictionaryId`. Match exactly one non-Model `Layout.LayoutName` using ordinal comparison. Set `PlotInfo.Layout` to that layout ObjectId. Do not call `LayoutManager.Current.CurrentLayout = ...`.

- [ ] **Step 4: Configure temporary plot settings**

Create `new PlotSettings(layout.ModelType)` and `CopyFrom(layout)`. Use `PlotSettingsValidator.Current` to:

- set the fixed approved device for PNG or PDF;
- refresh device/media lists;
- select exactly one A4 media mapping;
- set plot type to layout;
- enable standard scale-to-fit and centered plotting;
- set `monochrome.ctb` only when it is available and compatible.

The initial device constants are production policy:

```csharp
private const string PdfDevice = "AutoCAD PDF (General Documentation).pc3";
private const string PngDevice = "PublishToWeb PNG.pc3";
```

If the live AutoCAD Mechanical 2027 installation exposes different approved
identifiers, do not add fallback candidates. Stop and report the exact device
names to the PO so the fixed policy can be amended explicitly before acceptance.

- [ ] **Step 5: Validate and execute one foreground plot**

Set `BACKGROUNDPLOT` to `0` only for the bounded operation. Build `PlotInfo` with `OverrideSettings`, run `PlotInfoValidator`, and refuse to start if `PlotFactory.ProcessPlotState` indicates another plot is active.

Use one `PlotEngine` document/page sequence and target the reservation's temporary path. End page/document/plot synchronously and dispose each plotting object.

- [ ] **Step 6: Restore and verify before publication**

In `finally`, restore `BACKGROUNDPLOT` and every changed session variable. Then read DBMOD and DWG hash again and call `NativeRenderPolicy.EnsureReadOnly(...)`.

Only after successful restoration and invariant checks call `NativeRenderArtifactBoundary.Publish`. Build the evidence snapshot from validated metadata and the original request-bound identity fields.

On any exception before publication, dispose the reservation, return control to the dispatcher, and leave no final artifact.

- [ ] **Step 7: Build and run all .NET tests**

```powershell
dotnet restore autocad_plugin/CadAgent.AutoCAD2027.sln -p:AutodeskReferenceDir="$ref"
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 -p:AutodeskReferenceDir="$ref" --no-restore
dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 -p:AutodeskReferenceDir="$ref" --no-build --no-restore
```

Expected: zero build errors and zero test failures. Record the exact test total.

- [ ] **Step 8: Commit**

```powershell
git add autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadNativeRenderReader.cs autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Commands/CommandGuardTests.cs
git commit -m "feat: capture layouts through AutoCAD Plot API"
```

---

## Task 7: Add real File IPC live acceptance probes

**Files:**
- Modify: `mcp_integration_lib/tests/test_dotnet_ipc_live.py`

**Interfaces:**
- Consumes: existing live-test environment variables and `DotNetIPCClient.native_render_evidence()`.
- Produces: opt-in live PNG/PDF and fail-closed probes.

- [ ] **Step 1: Add an explicit S2C live marker and prerequisites**

Require the existing File IPC variables plus an approved disposable DWG whose on-disk hash is known. Skip truthfully when prerequisites are absent; never relabel a skip as a pass.

- [ ] **Step 2: Add PNG success probe**

Send the approved profile to a real paper-space layout. Assert:

```python
assert result["changed"] is False
assert result["entity_handles"] == []
artifact = result["payload"]["artifact"]
assert artifact["relative_path"] == f"native-render/{request_id}/artifact.png"
assert sha256(final_bytes).hexdigest() == artifact["sha256"]
```

Open the PNG with Pillow and assert its dimensions equal the payload and are positive.

- [ ] **Step 3: Add PDF success probe**

Assert exact `.pdf` relative path and SHA-256. Open with `pypdf.PdfReader` and assert `len(reader.pages) == 1` and payload `page_count == 1`.

- [ ] **Step 4: Add refusal probes**

Use unique request IDs and assert empty payload for:

- duplicate request ID/path;
- missing layout;
- unsupported option profile;
- configured missing device/media probe when the live harness can safely select that controlled condition.

The successful probes must not contain `NATIVE_RENDER_NOT_IMPLEMENTED`.

- [ ] **Step 5: Capture before/after state**

Record the DWG SHA-256, DBMOD, current layout, and relevant session variables before and after each success probe. Assert they are unchanged/restored.

- [ ] **Step 6: Commit**

```powershell
git add mcp_integration_lib/tests/test_dotnet_ipc_live.py
git commit -m "test: add S2C native render live gate"
```

---

## Task 8: Run bounded offline verification before live execution

**Files:** none beyond the allowlist.

- [ ] **Step 1: Verify changed-file allowlist**

```powershell
git diff --name-only 3d0aa999904f384efa4eb42a81637e4270591859...HEAD
```

Expected: only Issue #60 allowlisted files. Stop on any other path.

- [ ] **Step 2: Run focused Python tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_autocad_render_evidence_ipc.py tests/test_autocad_render_evidence_ipc_contracts.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check mcp_integration_lib/tests/test_autocad_render_evidence_ipc.py tests/test_autocad_render_evidence_ipc_contracts.py mcp_integration_lib/tests/test_dotnet_ipc_live.py
```

- [ ] **Step 3: Run mandatory .NET gate**

```powershell
dotnet restore autocad_plugin/CadAgent.AutoCAD2027.sln -p:AutodeskReferenceDir="$ref"
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 -p:AutodeskReferenceDir="$ref" --no-restore
dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 -p:AutodeskReferenceDir="$ref" --no-build --no-restore
```

- [ ] **Step 4: Run architecture and diff checks**

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
```

- [ ] **Step 5: Run canonical verification without skipping AutoCAD .NET**

```powershell
.\scripts\verify.ps1
```

Record PASS/FAIL/SKIP/NOT RUN truthfully for every gate.

---

## Task 9: Execute and record the real AutoCAD Mechanical 2027 live gate

**Files:**
- Modify: `docs/superpowers/implementation-records/2026-08-05-autocad-native-render-s2c.md`

- [ ] **Step 1: Build the exact candidate and load that plugin**

Record:

- exact branch head SHA;
- `.NET SDK` version;
- official Autodesk reference directory;
- plugin assembly SHA-256;
- AutoCAD Mechanical product/version/profile;
- IPC root;
- disposable DWG SHA-256;
- exact layout name;
- exact PDF and PNG PC3 identifiers;
- exact canonical media identifiers.

Do not copy Autodesk DLLs into the repository or plugin output.

- [ ] **Step 2: Run live PNG and PDF probes**

Run the opt-in S2C tests and record the exact pytest command, exit code, test totals, artifact paths, SHA-256 values, PNG dimensions, and PDF page count.

- [ ] **Step 3: Run refusal probes**

Record duplicate, missing-layout, missing-device/media, and unsupported-profile results. Each must have `success=false`, `changed=false`, empty handles, and `payload={}`.

- [ ] **Step 4: Record read-only evidence**

Record DBMOD, DWG hash, current layout, and changed session variables before/after. All must satisfy the design.

- [ ] **Step 5: Write the implementation record**

The record must distinguish:

```text
PASS
FAIL
SKIP
NOT RUN
NOT IMPLEMENTED
```

It must not claim private-data acceptance unless approved private data was actually used. It must state that verdict, approval, repair, and publication remain unimplemented.

- [ ] **Step 6: Commit the evidence record**

```powershell
git add docs/superpowers/implementation-records/2026-08-05-autocad-native-render-s2c.md
git commit -m "docs: record S2C native render evidence"
```

---

## Task 10: Final candidate verification and PR handoff

**Files:** all Issue #60 allowlisted files only.

- [ ] **Step 1: Re-run all mandatory offline and .NET commands on the final head**

The final evidence-record commit changes documentation, so re-run focused tests, Ruff, architecture, `git diff --check`, and the canonical verifier on the exact final head. If the live plugin binary did not change after the live gate, bind live evidence to the exact code commit and clearly identify the final docs-only head.

- [ ] **Step 2: Confirm repository cleanliness**

```powershell
git status --short
git diff --check
git diff --name-only 3d0aa999904f384efa4eb42a81637e4270591859...HEAD
```

Expected: clean worktree and only allowlisted paths.

- [ ] **Step 3: Push branch and open one non-draft PR**

The PR body must include eight Reuse Declaration fields on separate same-line labels, exact base, final head, commit count, changed files, .NET totals, offline totals, live PNG/PDF evidence, refusal evidence, and truthful non-scope states.

- [ ] **Step 4: Stop**

Do not merge, amend scope, start S3B/R1C, or claim acceptance. PO review requires exact diff, synthetic-merge CI, and the live evidence above.