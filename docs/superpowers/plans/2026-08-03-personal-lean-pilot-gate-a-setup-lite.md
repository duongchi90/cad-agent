# Personal Lean Pilot Gate A: Setup Lite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a hash-bound `SETUP_VERIFIED` result for one owner-approved DWT and one disposable AutoCAD Mechanical 2027 drawing while preserving the legacy image/PDF path as `DRAFT_REFERENCE`.

**Architecture:** Extend the existing managed .NET/File IPC operation family with one read-only `drawing_setup_audit` operation. Keep `cad_agent` as the thin plan/audit/verify orchestrator, reuse the existing Drawing Setup contracts and atomic manifest writer, and compare one live audit with one approved profile without creating a second dispatcher or setup subsystem.

**Tech Stack:** Windows, Python 3.11, C# `net10.0-windows` x64, AutoCAD Mechanical 2027 managed API, JSON Schema 2020-12, pytest, xUnit, Ruff.

## Global Constraints

- Supported runtime remains Windows, Python 3.11, AutoCAD Mechanical 2027, and Tesseract 5.4.0.20240606.
- The DWT, DWG, raw audit, private annotations, and generated DXF remain outside Git.
- All AutoCAD access in Gate A is read-only and targets a disposable drawing whose normalized full path matches the request.
- No code may call `UpgradeOpen`, save, regen, set a system variable, create/erase an entity, or change `SECURELOAD`.
- Missing .NET, DWT, DWG, AutoCAD, or IPC prerequisites are recorded as `NOT RUN` or `SKIP`, never `PASS`.
- The lean gate audits exactly one owner-approved DWT-derived disposable DWG; the full ten-DWG corpus is deferred.
- Use one writer and TDD for every new behavior. Run `scripts/verify.ps1` once at Gate A closure.
- The existing image/PDF commands remain compatible and cannot emit `SETUP_VERIFIED`, `PERSONAL_VERIFIED`, or `RELEASED`.

---

## File map

- `cad_agent/drawing_setup.py`: create setup plans, normalize IPC audit payloads, compare plan/audit, and enforce verified evidence.
- `cad_agent/cli.py`: expose plan, audit, and verify commands; no AutoCAD algorithms.
- `cad_agent/manifest.py`, `cad_agent/pdf.py`: classify new and historical pixel-first runs as draft/reference.
- `autocad_plugin/CadAgent.AutoCAD2027/DrawingSetup/*`: immutable read-only setup snapshots and deterministic payload projection.
- `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`: collect live setup state through `IDrawingGateway` with read-only database access.
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/*`: validate and dispatch `drawing_setup_audit` under schema version `1.0`.
- `mcp_integration_lib/dotnet_ipc.py`: send the empty-parameter audit request and validate its result.
- `contracts/autocad-ipc/*`: versioned request/result operation contract and examples.
- `tests/test_cad_agent_drawing_setup.py`: Python plan/audit/evidence regression coverage.
- `mcp_integration_lib/tests/test_dotnet_ipc.py`: fake-dispatch transport coverage.
- `mcp_integration_lib/tests/test_dotnet_ipc_live.py`: opt-in disposable AutoCAD read-only gate.

### Task 1: Reuse the verified CLI boundary and classify legacy runs

**Files:**

- Reuse commit: `ea63313977cf369e52d4ac7281fc4944a9133f8a`
- Modify: `cad_agent/manifest.py`
- Modify: `cad_agent/pdf.py`
- Modify: `tests/test_cad_agent_cli.py`
- Modify: `tests/test_cad_agent_pdf.py`
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:** Preserves `main(argv)`, `new_manifest()`, `read_manifest()`, `new_pdf_manifest()`, and `read_pdf_manifest()`. New/historical pixel-first manifests expose `release_profile="DRAFT_REFERENCE"`, `authoritative_release_eligible=False`, and `drawing_setup_evidence=None`.

- [ ] **Step 1: Integrate the already verified T4 commit**

```powershell
git cherry-pick ea63313977cf369e52d4ac7281fc4944a9133f8a
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_drawing_setup.py tests\test_cad_agent_cli.py -q -p no:cacheprovider
```

Expected: `33 passed`; `drawing-setup-plan` works and audit/verify fail explicitly as `unsupported_operation` until Tasks 4 and 5.

- [ ] **Step 2: Write failing image, PDF, and historical compatibility tests**

```python
def test_new_image_manifest_is_draft_reference_only(tmp_path: Path) -> None:
    source = tmp_path / "drawing.png"
    source.write_bytes(b"image")
    manifest = new_manifest(source, 0.5, "ticket-123")
    assert manifest["release_profile"] == "DRAFT_REFERENCE"
    assert manifest["authoritative_release_eligible"] is False
    assert manifest["drawing_setup_evidence"] is None


def test_historical_image_manifest_reads_as_draft_reference(tmp_path: Path) -> None:
    manifest = read_manifest(write_historical_v1_manifest(tmp_path))
    assert manifest["release_profile"] == "DRAFT_REFERENCE"
    assert manifest["authoritative_release_eligible"] is False
    assert manifest["drawing_setup_evidence"] is None
```

Add this PDF case:

```python
def test_new_and_historical_pdf_manifests_are_draft_reference(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    source.write_bytes(b"pdf")
    created = new_pdf_manifest(source, 0.5, "ticket-123", 300)
    for manifest in (created, read_pdf_manifest(write_historical_pdf_manifest(tmp_path))):
        assert manifest["release_profile"] == "DRAFT_REFERENCE"
        assert manifest["authoritative_release_eligible"] is False
        assert manifest["drawing_setup_evidence"] is None
```

`write_historical_pdf_manifest()` writes a valid `pdf-run-1.0` root with an
empty `pages` list and a pending `render` record, without the three new fields.

- [ ] **Step 3: Run the focused tests and verify RED**

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_cli.py tests\test_cad_agent_pdf.py -q -p no:cacheprovider
```

Expected: FAIL because the three classification fields are absent.

- [ ] **Step 4: Add one shared draft-classification helper**

```python
_DRAFT_REFERENCE_FIELDS = {
    "release_profile": "DRAFT_REFERENCE",
    "authoritative_release_eligible": False,
    "drawing_setup_evidence": None,
}


def classify_draft_reference(manifest: dict[str, Any]) -> dict[str, Any]:
    for name, expected in _DRAFT_REFERENCE_FIELDS.items():
        actual = manifest.get(name, expected)
        if actual != expected:
            raise ManifestError(f"Legacy run manifest has unsafe {name}.")
        manifest[name] = expected
    return manifest
```

Call it when creating and after validating image/PDF manifests. Reject an on-disk manifest that explicitly claims another release profile, eligibility `True`, or non-null setup evidence; historical absence alone is compatible.

- [ ] **Step 5: Run GREEN checks and commit**

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_cli.py tests\test_cad_agent_pdf.py -q -p no:cacheprovider
& '.\.venv-py311\Scripts\python.exe' -m ruff check cad_agent\manifest.py cad_agent\pdf.py tests\test_cad_agent_cli.py tests\test_cad_agent_pdf.py
git add cad_agent/manifest.py cad_agent/pdf.py tests/test_cad_agent_cli.py tests/test_cad_agent_pdf.py docs/ARCHITECTURE.md
git commit -m "feat: classify legacy reconstruction as draft reference"
```

### Task 2: Collect one deterministic read-only Drawing Setup snapshot

**Files:**

- Create: `autocad_plugin/CadAgent.AutoCAD2027/DrawingSetup/DrawingSetupModels.cs`
- Create: `autocad_plugin/CadAgent.AutoCAD2027/DrawingSetup/DrawingSetupPayload.cs`
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/DrawingSetup/DrawingSetupFixtures.cs`
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/DrawingSetup/DrawingSetupPayloadTests.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/NullDrawingGateway.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`
- Modify test stubs implementing `IDrawingGateway` under `autocad_plugin/CadAgent.AutoCAD2027.Tests/`

**Interfaces:** Produces `DrawingSetupSnapshot IDrawingGateway.ReadDrawingSetup()`. `DrawingSetupPayload.Create(snapshot)` returns deterministic JSON elements for `dbmod_before`, `dbmod_after`, `changed`, `variables`, `current_layer`, `custom_properties`, `layers`, `styles`, `layouts`, and `font_report`.

- [ ] **Step 1: Write failing payload tests**

```csharp
[Fact]
public void CreateSortsEveryCollectionAndReportsNoMutation()
{
    var payload = DrawingSetupPayload.Create(DrawingSetupFixtures.UnsortedSnapshot());
    Assert.False(payload["changed"].GetBoolean());
    Assert.Equal(0, payload["dbmod_before"].GetInt32());
    Assert.Equal(0, payload["dbmod_after"].GetInt32());
    Assert.Equal(new[] { "0", "NET_CHINH" },
        payload["layers"].EnumerateArray().Select(item => item.GetProperty("name").GetString()));
    Assert.Equal(new[] { "A1-01" },
        payload["layouts"].EnumerateArray().Select(item => item.GetProperty("name").GetString()));
}
```

Also assert that payload creation throws when `DbModBefore != DbModAfter`.

- [ ] **Step 2: Run RED when the .NET SDK is available**

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter FullyQualifiedName~DrawingSetup
```

Expected: build failure because `DrawingSetupSnapshot` is undefined. If `dotnet`/MSBuild is unavailable, record this command as `NOT RUN` and continue only with code inspection and Python gates; do not report C# PASS.

- [ ] **Step 3: Add immutable snapshot records and deterministic projection**

```csharp
public sealed record LayerSetupSnapshot(string Name, string Linetype, bool Plottable);
public sealed record TextStyleSetupSnapshot(string Name, string Font, string BigFont);
public sealed record LayoutSetupSnapshot(
    string Name, IReadOnlyList<double> ViewportScales, bool Locked);
public sealed record DrawingSetupSnapshot(
    string DrawingFullPath,
    int DbModBefore,
    int DbModAfter,
    IReadOnlyDictionary<string, double> Variables,
    string CurrentLayer,
    IReadOnlyDictionary<string, string> CustomProperties,
    IReadOnlyList<LayerSetupSnapshot> Layers,
    IReadOnlyList<TextStyleSetupSnapshot> TextStyles,
    IReadOnlyList<string> DimensionStyles,
    IReadOnlyList<string> MLeaderStyles,
    IReadOnlyList<string> TableStyles,
    IReadOnlyList<LayoutSetupSnapshot> Layouts,
    IReadOnlyList<string> MissingFonts,
    IReadOnlyList<string> SubstitutedFonts);
```

`DrawingSetupPayload.Create()` sorts names ordinally, emits only the fields accepted by `drawing-setup-audit-1.0`, and throws `InvalidOperationException` if DBMOD changed.

- [ ] **Step 4: Implement live read-only collection**

`AutoCadDrawingGateway.ReadDrawingSetup()` must:

```csharp
static double ReadNumber(string name) => Convert.ToDouble(
    AcadApplication.GetSystemVariable(name), CultureInfo.InvariantCulture);

var dbModBefore = Convert.ToInt32(ReadNumber("DBMOD"));
var variables = new Dictionary<string, double>(StringComparer.Ordinal)
{
    ["INSUNITS"] = ReadNumber("INSUNITS"),
    ["MEASUREMENT"] = ReadNumber("MEASUREMENT"),
    ["LTSCALE"] = ReadNumber("LTSCALE"),
    ["CELTSCALE"] = ReadNumber("CELTSCALE"),
    ["PSLTSCALE"] = ReadNumber("PSLTSCALE"),
    ["MSLTSCALE"] = ReadNumber("MSLTSCALE"),
    ["DIMASSOC"] = ReadNumber("DIMASSOC"),
    ["ANNOALLVISIBLE"] = ReadNumber("ANNOALLVISIBLE")
};
using var transaction = _document.TransactionManager.StartOpenCloseTransaction();
var layerTable = (LayerTable)transaction.GetObject(
    _document.Database.LayerTableId, OpenMode.ForRead);
var textStyleTable = (TextStyleTable)transaction.GetObject(
    _document.Database.TextStyleTableId, OpenMode.ForRead);
var dimensionStyleTable = (DimStyleTable)transaction.GetObject(
    _document.Database.DimStyleTableId, OpenMode.ForRead);
var layoutDictionary = (DBDictionary)transaction.GetObject(
    _document.Database.LayoutDictionaryId, OpenMode.ForRead);
var dbModAfter = Convert.ToInt32(ReadNumber("DBMOD"));
if (dbModBefore != dbModAfter)
    throw new InvalidOperationException("Drawing setup audit changed DBMOD.");
```

Open each table/dictionary entry with `OpenMode.ForRead`. Read MLeader and Table
style names from `MLeaderStyleDictionaryId` and `TableStyleDictionaryId`; read
paper-layout viewports from each `Layout.BlockTableRecordId`. Resolve each
declared text-style font with
`HostApplicationServices.Current.FindFile(style.Font, _document.Database,
FindFileHint.Default)`; unresolved names enter `MissingFonts`, and a different
resolved file name enters `SubstitutedFonts`. Sort all outputs ordinally.

- [ ] **Step 5: Run the available checks and commit**

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter FullyQualifiedName~DrawingSetup
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64
git add autocad_plugin/CadAgent.AutoCAD2027/DrawingSetup autocad_plugin/CadAgent.AutoCAD2027.Tests/DrawingSetup autocad_plugin/CadAgent.AutoCAD2027/Drawing autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs autocad_plugin/CadAgent.AutoCAD2027.Tests
git commit -m "feat: read AutoCAD drawing setup without mutation"
```

Both .NET commands must be recorded as `NOT RUN` rather than omitted if the SDK is absent.

### Task 3: Expose the read-only snapshot through IPC schema version 1.0

**Files:**

- Modify: `contracts/autocad-ipc/request.schema.json`
- Modify: `contracts/autocad-ipc/result.schema.json`
- Create: `contracts/autocad-ipc/operations/drawing-setup-audit.schema.json`
- Create: `contracts/autocad-ipc/examples/drawing-setup-audit-request.json`
- Create: `contracts/autocad-ipc/examples/drawing-setup-audit-result.json`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`

**Interfaces:** Adds operation string `drawing_setup_audit`. Request `parameters` is exactly `{}`; result is read-only, `changed=false`, has no entity handles, and carries the deterministic Drawing Setup payload.

- [ ] **Step 1: Write failing contract and dispatcher tests**

```csharp
[Fact]
public void DrawingSetupAuditRequiresExactActivePathAndEmptyParameters()
{
    var gateway = new StubDrawingGateway {
        ActiveDocumentFullPath = @"C:\temp\setup-lite.dwg",
        DrawingSetup = DrawingSetupFixtures.VerifiedSnapshot(@"C:\temp\setup-lite.dwg")
    };
    var result = CreateDispatcher(gateway).Dispatch(Request(
        "drawing_setup_audit", "setup-lite-001", @"C:\temp\setup-lite.dwg", Parameters()));
    Assert.True(result.Success);
    Assert.False(result.Changed);
    Assert.Empty(result.EntityHandles);
    Assert.Equal(1, gateway.ReadDrawingSetupCallCount);
}
```

Add refusals for a non-empty parameter object and a same-name drawing under another directory. The path mismatch must leave `ReadDrawingSetupCallCount == 0`.

- [ ] **Step 2: Run RED or record .NET NOT RUN**

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter "FullyQualifiedName~ContractTests|FullyQualifiedName~OperationDispatcherTests"
```

- [ ] **Step 3: Add the versioned contract and dispatcher branch**

The operation schema is exactly:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "maxProperties": 0
}
```

Add `drawing_setup_audit` to the request/result enums and `ContractConstants.SupportedOperations`. Validate empty parameters. Dispatch only after `TryMatchActiveDocument()` succeeds:

```csharp
var snapshot = _context.DrawingGateway.ReadDrawingSetup();
return CreateResult(
    request.RequestId!, "drawing_setup_audit", activePath,
    success: true, changed: false, entityHandles: Array.Empty<string>(),
    warnings: Array.Empty<string>(), errors: Array.Empty<string>(),
    payload: DrawingSetupPayload.Create(snapshot), startedAt);
```

- [ ] **Step 4: Run schema/C# checks and commit**

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_autocad_plugin_project.py mcp_integration_lib\tests\test_dotnet_ipc.py -q -p no:cacheprovider
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
git add contracts/autocad-ipc autocad_plugin/CadAgent.AutoCAD2027/Ipc autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc
git commit -m "feat: expose read-only drawing setup audit"
```

### Task 4: Capture a hash-stable Python audit artifact

**Files:**

- Modify: `mcp_integration_lib/dotnet_ipc.py`
- Modify: `mcp_integration_lib/tests/test_dotnet_ipc.py`
- Modify: `cad_agent/drawing_setup.py`
- Modify: `cad_agent/cli.py`
- Modify: `tests/test_cad_agent_drawing_setup.py`
- Modify: `tests/drawing_setup_fixtures.py`

**Interfaces:** Produces `DotNetIPCClient.drawing_setup_audit()` and `create_setup_audit(drawing, drawing_sha256, ipc_result)`. Completes `cad_agent drawing-setup-audit`.

- [ ] **Step 1: Write failing transport, normalization, and source-change tests**

```python
def test_drawing_setup_audit_uses_empty_parameters(self) -> None:
    with TemporaryDirectory() as temporary:
        ipc_dir = Path(temporary)
        dispatcher = FakeDispatcher(ipc_dir, {"dbmod_before": 0, "dbmod_after": 0})
        client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=dispatcher)
        result = client.drawing_setup_audit(
            r"C:\temp\setup-lite.dwg", drawing_sha256="a" * 64,
            request_id="setup-lite-001")
        self.assertEqual("drawing_setup_audit", dispatcher.requests[0]["operation"])
        self.assertEqual({}, dispatcher.requests[0]["parameters"])
        self.assertFalse(result["changed"])


def test_audit_cli_refuses_when_drawing_hash_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawing = tmp_path / "setup-lite.dwg"
    drawing.write_bytes(b"before")
    output = tmp_path / "audit.json"

    def mutate_and_return(*args, **kwargs):
        drawing.write_bytes(b"after")
        return matching_setup_ipc_result(approved_setup_plan(), str(drawing.resolve()))

    monkeypatch.setattr(DotNetIPCClient, "drawing_setup_audit", mutate_and_return)
    assert main([
        "drawing-setup-audit", "--drawing", str(drawing), "--hwnd", "123",
        "--ipc-dir", str(tmp_path), "--output", str(output),
    ]) == 2
    assert not output.exists()
```

Add `matching_setup_ipc_result(plan, drawing_full_path)` to
`tests/drawing_setup_fixtures.py`; it wraps `matching_setup_audit(plan)` in a
complete successful IPC result and removes `schema_version`, `drawing_full_path`,
and `drawing_sha256` from the payload.

- [ ] **Step 2: Run RED**

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest mcp_integration_lib\tests\test_dotnet_ipc.py tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider
```

Expected: missing method and the CLI still reports `unsupported_operation`.

- [ ] **Step 3: Add the client method and audit normalizer**

```python
def drawing_setup_audit(
    self,
    drawing_full_path: str | Path,
    *,
    drawing_sha256: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    return self.request(
        "drawing_setup_audit", drawing_full_path,
        drawing_sha256=drawing_sha256, parameters={}, approval=None,
        request_id=request_id)
```

Add the operation to `SUPPORTED_OPERATIONS`; treat its parameters like `health` and `mechanical_bom` (exactly empty). `create_setup_audit()` copies only the strict `drawing-setup-audit-1.0` fields from a successful result and never mutates the result mapping.

- [ ] **Step 4: Implement the CLI with before/after SHA-256 checks**

```python
before = sha256_file(drawing)
result = DotNetIPCClient(
    ipc_dir=args.ipc_dir, timeout_s=args.timeout_s,
    trigger=make_windows_dotnet_dispatch_trigger(args.hwnd),
).drawing_setup_audit(drawing, drawing_sha256=before)
if sha256_file(drawing) != before:
    raise CommandError("source_changed: drawing changed during setup audit")
audit = create_setup_audit(drawing, before, result)
write_manifest(args.output.resolve(), audit)
```

Require an existing regular `.dwg`/`.dxf` path and validate the written artifact with the public Drawing Setup contract reader in tests.

- [ ] **Step 5: Run GREEN checks and commit**

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest mcp_integration_lib\tests\test_dotnet_ipc.py tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider
& '.\.venv-py311\Scripts\python.exe' -m ruff check mcp_integration_lib\dotnet_ipc.py mcp_integration_lib\tests\test_dotnet_ipc.py cad_agent\drawing_setup.py cad_agent\cli.py tests\test_cad_agent_drawing_setup.py
git add mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py cad_agent/drawing_setup.py cad_agent/cli.py tests/test_cad_agent_drawing_setup.py
git commit -m "feat: collect drawing setup audit through dotnet IPC"
```

### Task 5: Compare one audit and enforce `SETUP_VERIFIED`

**Files:**

- Modify: `cad_agent/drawing_setup.py`
- Modify: `cad_agent/cli.py`
- Modify: `tests/test_cad_agent_drawing_setup.py`

**Interfaces:** Produces `evaluate_setup_plan(plan, audit, *, verified_by, approval_reference) -> dict[str, object]` and `require_setup_verified(evidence, *, setup_plan_sha256, drawing_profile_sha256, template_file_sha256) -> None`. Completes `drawing-setup-verify`.

- [ ] **Step 1: Write failing matching, mismatch, immutability, and stale-evidence tests**

```python
def test_matching_audit_becomes_setup_verified() -> None:
    plan = approved_setup_plan()
    audit = matching_setup_audit(plan)
    evidence = evaluate_setup_plan(
        plan, audit, verified_by="OWNER",
        approval_reference="LEAN-SETUP-001")
    assert evidence["status"] == "SETUP_VERIFIED"
    assert evidence["blockers"] == []


@pytest.mark.parametrize("mutation,code", [
    (("variables", "INSUNITS", 0), "setup_incomplete"),
    (("styles", "dimension", "Standard"), "profile_hash_mismatch"),
    (("viewports", "A1-01", False), "viewport_scale_mismatch"),
    (("custom_properties", "CAD_AGENT_SETTINGS_SHA256", "bad"), "template_hash_mismatch"),
])
def test_setup_mismatch_returns_needs_review(mutation, code) -> None:
    plan = approved_setup_plan()
    audit = matching_setup_audit(plan)
    apply_test_mutation(audit, mutation)
    evidence = evaluate_setup_plan(
        plan, audit, verified_by="OWNER",
        approval_reference="LEAN-SETUP-001")
    assert evidence["status"] == "NEEDS_REVIEW"
    assert code in {item["code"] for item in evidence["blockers"]}
```

Assert `plan` and `audit` remain byte-for-byte equal to deep copies. Assert `require_setup_verified()` refuses changed plan/profile/template hashes and any non-empty blocker list.

- [ ] **Step 2: Run RED**

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement exact comparison and stable blockers**

```python
SETUP_BLOCKERS = frozenset({
    "source_changed", "setup_incomplete", "profile_missing",
    "profile_hash_mismatch", "template_hash_mismatch",
    "font_substitution_risk", "viewport_scale_mismatch",
    "drawing_target_mismatch",
})
```

Compare every required variable, current layer, required layer field, required style name, layout viewport scale/lock state, DBMOD/changed state, font report, and `CAD_AGENT_SETTINGS_SHA256`. Sort blockers by `(code, path)` and include exactly `code`, `path`, `expected`, `actual`, and `severity="error"`. Hash the complete plan and audit canonically in the evidence.

- [ ] **Step 4: Complete `drawing-setup-verify`**

Read plan/audit with `read_contract()`, evaluate, and atomically write evidence for both outcomes. Return `0` for `SETUP_VERIFIED`; print a concise blocker summary to stderr and return `2` for `NEEDS_REVIEW`.

- [ ] **Step 5: Run GREEN checks and commit**

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_drawing_setup.py tests\test_cad_agent_cli.py -q -p no:cacheprovider
& '.\.venv-py311\Scripts\python.exe' -m ruff check cad_agent\drawing_setup.py cad_agent\cli.py tests\test_cad_agent_drawing_setup.py
git add cad_agent/drawing_setup.py cad_agent/cli.py tests/test_cad_agent_drawing_setup.py
git commit -m "feat: enforce personal drawing setup gate"
```

### Task 6: Add the single-drawing live gate and close Gate A honestly

**Files:**

- Modify: `mcp_integration_lib/tests/test_dotnet_ipc_live.py`
- Create after a real run: `docs/reviews/2026-08-03-personal-setup-lite-live-review.md`
- Create only from owner-approved, non-sensitive values: `profiles/drawing/PERSONAL_LEAN_V1.json`
- Create only from owner-approved, non-sensitive values: `profiles/domains/PERSONAL_AUTOMOTIVE_V1.json`
- Create only from owner-approved, non-sensitive values: `profiles/templates/PERSONAL_MECHANICAL_2027_TEMPLATE.json`
- Modify: `docs/STATUS.md`

**Interfaces:** Provides one opt-in `autocad_mechanical` setup-audit test and the exact evidence needed to close Gate A. No DWT/DWG/raw audit is committed.

- [ ] **Step 1: Write the opt-in read-only live test**

```python
def _lean_setup_prerequisites_available() -> bool:
    return (
        bool(os.getenv("CAD_AGENT_LEAN_DISPOSABLE_DWG"))
        and bool(os.getenv("CAD_AGENT_AUTOCAD_HWND"))
        and bool(os.getenv("CAD_AGENT_DOTNET_IPC_DIR"))
    )


@unittest.skipUnless(
    _lean_setup_prerequisites_available(),
    "requires CAD_AGENT_LEAN_DISPOSABLE_DWG, CAD_AGENT_AUTOCAD_HWND, and CAD_AGENT_DOTNET_IPC_DIR",
)
@pytest.mark.autocad_mechanical
class PersonalSetupLiveTests(unittest.TestCase):
    def test_live_personal_setup_audit_is_read_only(self) -> None:
        drawing = Path(os.environ["CAD_AGENT_LEAN_DISPOSABLE_DWG"])
        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        before = _sha256(drawing)
        client = DotNetIPCClient(
            ipc_dir=os.environ["CAD_AGENT_DOTNET_IPC_DIR"],
            trigger=make_windows_dotnet_dispatch_trigger(hwnd),
            timeout_s=30.0,
        )
        result = client.drawing_setup_audit(
            normalize_windows_absolute_path(str(drawing)),
            drawing_sha256=before, request_id="lean-setup-live-001")
        self.assertFalse(result["changed"])
        self.assertEqual(
            result["payload"]["dbmod_before"],
            result["payload"]["dbmod_after"],
        )
        self.assertEqual(before, _sha256(drawing))
```

Skip with an explicit prerequisite message unless the drawing path, positive HWND, loaded managed dispatcher, and IPC directory are all present.

- [ ] **Step 2: Run offline/unavailable-state coverage**

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest mcp_integration_lib\tests\test_dotnet_ipc_live.py -q -p no:cacheprovider
```

Expected without a live session: offline cleanup tests pass and the named live test reports `SKIP`; this is not live acceptance.

- [ ] **Step 3: Check the external acceptance prerequisites**

The live gate may run only when all are true:

```powershell
Test-Path -LiteralPath $env:CAD_AGENT_LEAN_DWT
Test-Path -LiteralPath $env:CAD_AGENT_LEAN_DISPOSABLE_DWG
[int64]$env:CAD_AGENT_AUTOCAD_HWND -gt 0
Test-Path -LiteralPath $env:CAD_AGENT_AUTOCAD_PLUGIN_PATH
```

The owner-approved DWT must create the disposable DWG, and AutoCAD's active full path must equal `CAD_AGENT_LEAN_DISPOSABLE_DWG`. If any check is false, record the live/profile gate as `NOT RUN`; do not invent profile values or inspect unrelated drawings.

- [ ] **Step 4: Run the real three-command flow when prerequisites exist**

```powershell
& '.\.venv-py311\Scripts\python.exe' -m cad_agent drawing-setup-plan --run-id LEAN-SETUP-001 --definition $env:CAD_AGENT_LEAN_DEFINITION --profile .\profiles\drawing\PERSONAL_LEAN_V1.json --domain-pack .\profiles\domains\PERSONAL_AUTOMOTIVE_V1.json --template-manifest .\profiles\templates\PERSONAL_MECHANICAL_2027_TEMPLATE.json --template-file $env:CAD_AGENT_LEAN_DWT --output C:\temp\cad-agent-lean\drawing-setup-plan.json
& '.\.venv-py311\Scripts\python.exe' -m cad_agent drawing-setup-audit --drawing $env:CAD_AGENT_LEAN_DISPOSABLE_DWG --hwnd $env:CAD_AGENT_AUTOCAD_HWND --ipc-dir C:\temp --output C:\temp\cad-agent-lean\drawing-setup-audit.json
& '.\.venv-py311\Scripts\python.exe' -m cad_agent drawing-setup-verify --plan C:\temp\cad-agent-lean\drawing-setup-plan.json --audit C:\temp\cad-agent-lean\drawing-setup-audit.json --verified-by OWNER --approval-reference LEAN-SETUP-001 --output C:\temp\cad-agent-lean\drawing-setup-evidence.json
```

Acceptance requires `SETUP_VERIFIED`, no blockers, unchanged drawing SHA-256, unchanged DBMOD, and a recorded AutoCAD Mechanical 2027 session. Otherwise Gate A remains open.

- [ ] **Step 5: Run authoritative verification and record status**

```powershell
& '.\scripts\verify.ps1' -PythonExe 'C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe'
git diff --check
git status --short
```

If the machine lacks .NET build prerequisites, run the verifier only with its explicit `.NET NOT RUN` option and say so in `docs/STATUS.md`; never claim a full Gate A pass. Commit only tests, approved non-sensitive profile metadata, the review record, and accurate status:

```powershell
git add mcp_integration_lib/tests/test_dotnet_ipc_live.py docs/reviews/2026-08-03-personal-setup-lite-live-review.md profiles docs/STATUS.md
git commit -m "test: record personal Setup Lite gate"
```

## Gate A completion checklist

- [ ] T4 plan/CLI behavior is integrated and still passes its focused suite.
- [ ] Legacy image/PDF manifests are explicitly draft/reference and historical files remain resumable.
- [ ] C# snapshot and dispatcher are built/tested, or accurately recorded `NOT RUN`.
- [ ] Python audit and verify commands pass focused offline tests.
- [ ] The one owner-approved disposable drawing produces `SETUP_VERIFIED` with no blockers.
- [ ] Source hash and DBMOD remain unchanged during the live audit.
- [ ] `scripts/verify.ps1` passes on the candidate with every unavailable gate labeled accurately.
- [ ] No DWT, DWG, DXF, raw audit, private data, absolute private path, or secret is staged.
- [ ] `docs/STATUS.md` records only evidence that actually ran.
