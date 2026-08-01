# Mechanical BOM Read-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a safe `mechanical_bom` operation that reads direct ModelSpace block inserts and attributes through managed AutoCAD .NET and returns a deterministic read-only IPC payload.

**Architecture:** Keep the public drawing access behind a small `IMechanicalDrawingGateway`. `ManagedMechanicalAdapter` consumes that boundary and remains AutoCAD-independent. `CommandContext` wires the live AutoCAD gateway and adapter, while `OperationDispatcher` maps the adapter result into the existing IPC envelope. The Python client and JSON schemas remain additive under schema version `1.0`.

**Tech Stack:** C# `net10.0-windows` x64, AutoCAD Managed .NET API, xUnit v3, Python 3.11, pytest, JSON Schema 2020-12, Git worktrees.

## Global Constraints

- Windows-only target; do not add macOS/Linux behavior.
- The operation name is exactly `mechanical_bom`.
- Keep IPC schema version exactly `1.0`; the new operation is additive and does not change the result envelope.
- Read only: `changed` is always `false`; no save, mutation, balloon, Part Reference insertion, or command invocation.
- Read only direct ModelSpace `BlockReference` inserts and direct `AttributeReference` values; no nested traversal, dynamic-block expansion, Mechanical Structure, or Content Library lookup.
- No COM/ActiveX, ObjectARX/C++/CLI, native DLL, or Mechanical SDK references.
- `parameters` for `mechanical_bom` must be exactly `{}`.
- Components sort by ordinal handle; attributes sort by ordinal normalized tag then ordinal value; duplicate attribute tags remain separate entries.
- Every new production behavior must have a failing test observed before its implementation is written.
- No implementation Coder may modify `scripts/verify.ps1` or `docs/STATUS.md`.
- No Coder works on `main`; each task uses an isolated worktree and commits its own branch.
- AutoCAD live evidence is explicitly `PASS`, `SKIP`, or `NOT RUN`; build/unit-test success never implies live `PASS`.

## Dependency graph and task ownership

| Task ID | Goal | Depends on | Branch/worktree | Allowed files | Forbidden files | Parallel with | Required tests | Done when |
|---|---|---|---|---|---|---|---|---|
| T01 | Managed adapter contract and offline implementation | None beyond approved spec | `codex/mechanical-bom-t01-adapter` / agent worktree | `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/IMechanicalDrawingGateway.cs`; `MechanicalModels.cs`; `IMechanicalAdapter.cs`; `ManagedMechanicalAdapter.cs`; `NoOpMechanicalAdapter.cs`; `autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical/ManagedMechanicalAdapterTests.cs`; `NoOpMechanicalAdapterTests.cs` | `Ipc/**`; `Commands/CommandContext.cs`; `OperationDispatcher.cs`; Python; JSON schemas; `scripts/verify.ps1`; `docs/STATUS.md` | None; T02 depends on T01 | `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter FullyQualifiedName~Mechanical` | Failing tests observed first, focused tests pass, no forbidden dependency, self-reviewed commit |
| T02 | Wire live gateway/dispatcher, contracts, Python client, and opt-in live test | T01 commit reviewed and available | `codex/mechanical-bom-t02-ipc` / agent worktree based on T01 | `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`; `Ipc/ContractModels.cs`; `Ipc/ContractValidator.cs`; `Ipc/OperationDispatcher.cs`; `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`; `Ipc/OperationDispatcherTests.cs`; `contracts/autocad-ipc/request.schema.json`; `result.schema.json`; `operations/mechanical-bom.schema.json`; `examples/mechanical-bom-request.json`; `examples/mechanical-bom-result.json`; `mcp_integration_lib/dotnet_ipc.py`; `mcp_integration_lib/tests/test_dotnet_ipc.py`; `test_dotnet_ipc_live.py` | `Mechanical/**` implementation files from T01; `scripts/verify.ps1`; `docs/STATUS.md`; unrelated Python/C# files | None; T03 follows review | `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64`; `.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -q -p no:cacheprovider`; schema/contract tests; opt-in live marker test when session exists | End-to-end offline request/dispatch/client path passes; live test reports only PASS/SKIP/NOT RUN; commit reviewed |
| T03 | Integration, verifier, live smoke, status, merge, push | T01 and T02 review-clean commits | `integration/mechanical-bom-readonly` | `docs/STATUS.md` only after evidence; `scripts/verify.ps1` only if a narrowly justified test root/contract change is required | Production source outside reviewed commits; `main` during integration | None | Focused C#/Python tests; `scripts/verify.ps1`; disposable DXF live smoke | Reviewed commits cherry-picked, verifier clean, status evidence recorded, main pushed |

The tasks are intentionally sequential. T01 and T02 share a conceptual boundary and T02 needs T01 types; splitting them into parallel writers would create avoidable conflicts in contract models and test fixtures.

## Task 1: Managed adapter contract and offline implementation

**Files:**

- Create: `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/IMechanicalDrawingGateway.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/MechanicalModels.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/IMechanicalAdapter.cs`
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/ManagedMechanicalAdapter.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/NoOpMechanicalAdapter.cs`
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical/ManagedMechanicalAdapterTests.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical/NoOpMechanicalAdapterTests.cs`

**Interfaces:**

- `IMechanicalDrawingGateway.ReadMechanicalComponents()` returns `IReadOnlyList<MechanicalComponentSnapshot>`.
- `MechanicalAttributeSnapshot` is `record(string Tag, string Value)`.
- `MechanicalComponentSnapshot` is `record(string Handle, string BlockName, IReadOnlyList<MechanicalAttributeSnapshot> Attributes)`.
- `ManagedMechanicalAdapter(IMechanicalDrawingGateway gateway)` reports `IsAvailable == true`, capabilities exactly `mechanical_bom`, and returns `status == success` for `MechanicalOperationRequest("mechanical_bom")`.
- `MechanicalOperationResult` carries `Status`, `OperationName`, `Changed`, `Warnings`, `Errors`, and `Components` while preserving `NoOpMechanicalAdapter` behavior.

- [ ] **Step 1: Write the failing adapter tests**

Add tests with a real in-memory fake gateway:

```csharp
[Fact]
public void ManagedAdapterAdvertisesOnlyMechanicalBom()
{
    var adapter = new ManagedMechanicalAdapter(new FakeMechanicalGateway());

    Assert.True(adapter.IsAvailable);
    Assert.Equal(new[] { "mechanical_bom" }, adapter.GetCapabilities().SupportedOperations);
}

[Fact]
public void ManagedAdapterReturnsGatewayComponentsWithoutChangingThem()
{
    var expected = new[]
    {
        new MechanicalComponentSnapshot("2F", "COMP_FRAME", new[]
        {
            new MechanicalAttributeSnapshot("PART_ID", "FRAME-001")
        })
    };
    var adapter = new ManagedMechanicalAdapter(new FakeMechanicalGateway(expected));

    var result = adapter.Execute(new MechanicalOperationRequest("mechanical_bom"));

    Assert.Equal("success", result.Status);
    Assert.False(result.Changed);
    Assert.Equal(expected, result.Components);
    Assert.Empty(result.Warnings);
    Assert.Empty(result.Errors);
}
```

- [ ] **Step 2: Run the tests and verify the expected RED state**

Run:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter FullyQualifiedName~Mechanical
```

Expected: FAIL because the managed gateway, snapshots, result fields, and adapter do not yet exist.

- [ ] **Step 3: Implement the smallest managed adapter boundary**

Create the records and interface in the `Mechanical` namespace. Make the result collections immutable/read-only at the public boundary. `ManagedMechanicalAdapter` must reject every operation other than `mechanical_bom` with `not_supported` and must not call the gateway for rejected names. Update `NoOpMechanicalAdapter` to construct the expanded result with empty collections and `Changed == false`.

- [ ] **Step 4: Run focused tests and the full C# test project**

Run the Mechanical filter first, then:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
```

Expected: all tests pass with zero failures and zero errors.

- [ ] **Step 5: Self-review and commit**

Inspect `git diff --check`, search the changed files for `ActiveX`, `COM`, `ObjectARX`, native references, and verify the allowed-file list. Commit:

```powershell
git add autocad_plugin/CadAgent.AutoCAD2027/Mechanical autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical
git commit -m "feat: add managed mechanical BOM adapter"
```

## Task 2: End-to-end IPC and live gateway wiring

**Files:**

- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`
- Modify: `contracts/autocad-ipc/request.schema.json`
- Modify: `contracts/autocad-ipc/result.schema.json`
- Create: `contracts/autocad-ipc/operations/mechanical-bom.schema.json`
- Create: `contracts/autocad-ipc/examples/mechanical-bom-request.json`
- Create: `contracts/autocad-ipc/examples/mechanical-bom-result.json`
- Modify: `mcp_integration_lib/dotnet_ipc.py`
- Modify: `mcp_integration_lib/tests/test_dotnet_ipc.py`
- Modify: `mcp_integration_lib/tests/test_dotnet_ipc_live.py`

**Interfaces:**

- `CommandContext` keeps existing constructor callers source-compatible by accepting an optional `IMechanicalAdapter`; absent adapter means `NoOpMechanicalAdapter`.
- `CreateLive()` makes its existing live gateway implement `IMechanicalDrawingGateway`, reads ModelSpace in a read-only transaction, and wires `ManagedMechanicalAdapter`.
- `OperationDispatcher.Dispatch` routes `mechanical_bom` only after common contract validation and active-document path matching.
- Python exposes `DotNetIPCClient.mechanical_bom(drawing_full_path, *, request_id=None, drawing_sha256=None, approval=None)` and sends `parameters={}`.

- [ ] **Step 1: Add failing dispatcher, contract, and Python tests**

Add assertions for:

```csharp
[Fact]
public void MechanicalBomReturnsSortedReadOnlyComponents()
{
    var gateway = new StubDrawingGateway { ActiveDocumentFullPath = @"C:\\temp\\bom.dxf" };
    var mechanical = new FakeMechanicalAdapter(new[]
    {
        Component("A0", "SECOND", Attribute("QTY", "2")),
        Component("2F", "FIRST", Attribute("PART_ID", "FRAME-001"))
    });

    var result = CreateDispatcher(gateway, mechanical).Dispatch(
        Request("mechanical_bom", "bom-request", @"C:\\temp\\bom.dxf", Parameters()));

    Assert.True(result.Success);
    Assert.False(result.Changed);
    Assert.Equal(new[] { "2F", "A0" }, result.EntityHandles);
    Assert.Equal(2, result.Payload!["component_count"].GetInt32());
}
```

And in `test_dotnet_ipc.py`:

```python
def test_mechanical_bom_sends_empty_parameters_and_preserves_payload(self) -> None:
    with TemporaryDirectory() as temporary:
        dispatcher = FakeDispatcher(Path(temporary), {"component_count": 1})
        client = DotNetIPCClient(ipc_dir=temporary, trigger=dispatcher)

        result = client.mechanical_bom(r"C:\temp\bom.dxf", request_id="bom-001")

        self.assertEqual("mechanical_bom", dispatcher.requests[0]["operation"])
        self.assertEqual({}, dispatcher.requests[0]["parameters"])
        self.assertEqual({"component_count": 1}, result["payload"])
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter FullyQualifiedName~MechanicalBom
& .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -k mechanical_bom -q -p no:cacheprovider
```

Expected: FAIL because the operation is not in the supported set, the dispatcher route is absent, and the Python helper is absent.

- [ ] **Step 3: Update the C# contract and live gateway**

Add `mechanical_bom` to `ContractConstants.SupportedOperations`. Validate its parameters with an exact empty-object rule. Add the operation enum and the operation schema with `type: object`, `additionalProperties: false`, and no properties. Keep schema version `1.0`. Extend `AutoCadDrawingGateway` to enumerate ModelSpace inserts in a read-only transaction; normalize tags, preserve values, sort components/attributes, and skip an unreadable insert with a warning. Wire the live adapter through `CommandContext`.

- [ ] **Step 4: Add dispatcher mapping and Python client support**

Map adapter snapshots into `payload.component_count` and `payload.components`, set `entity_handles` to the sorted component handles, and propagate adapter warnings/errors. Ensure path mismatch happens before gateway reads. Add the Python operation to `SUPPORTED_OPERATIONS`, the empty-parameter validator branch, the `mechanical_bom` helper, and its tests. Add contract examples matching the spec exactly.

- [ ] **Step 5: Add opt-in live smoke and run offline gates**

Extend the existing `autocad_mechanical` live test module to create/use a disposable DXF fixture under `C:\temp`, dispatch `mechanical_bom`, assert the component/attribute payload and `changed == false`, and report `SKIP` when the declared AutoCAD prerequisites are absent. Run:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
& .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -q -p no:cacheprovider
```

- [ ] **Step 6: Self-review and commit**

Run `git diff --check`, inspect the complete allowed-file diff, confirm no `scripts/verify.ps1` or `docs/STATUS.md` changes, then commit:

```powershell
git add autocad_plugin contracts mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc_live.py
git commit -m "feat: expose read-only mechanical BOM over IPC"
```

## Task 3: Integration and evidence (PO-controlled)

**Files:**

- Modify only after evidence: `docs/STATUS.md`
- Modify `scripts/verify.ps1` only if a narrowly scoped new test root is objectively required; otherwise leave it unchanged.

**Review gates:**

- Record the integration base SHA before dispatching each Coder.
- Generate a review package from that base SHA to the Coder commit; require both specification compliance and code-quality approval before cherry-pick.
- If review finds an Important/Critical issue, send the finding back to the Coder for a fix and re-review; the PO does not patch production code directly.

- [ ] **Step 1: Cherry-pick review-clean commits**

Cherry-pick T01, then T02 into `integration/mechanical-bom-readonly` in dependency order. Confirm `git status --short` is clean before each verification gate.

- [ ] **Step 2: Run focused integration tests**

Run the C# test project and the dotnet IPC pytest module. Inspect JSON examples and run `git diff --check`.

- [ ] **Step 3: Run the authoritative verifier**

Run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`. Record the exact commit SHA and pass/fail totals. The verifier must not be changed merely to hide a failure.

- [ ] **Step 4: Run live smoke on a disposable DXF**

When a separate AutoCAD Mechanical 2027 session and File IPC prerequisites are available, run only the `autocad_mechanical` live marker against a DXF under `C:\temp`. Record `PASS` only if the exact component payload and `changed=false` are observed. Otherwise record `SKIP` or `NOT RUN`, never infer success.

- [ ] **Step 5: Update status and commit evidence**

Append a dated entry to `docs/STATUS.md` containing the integrated commit, focused-test results, verifier result, live marker (`PASS`, `SKIP`, or `NOT RUN`), and the explicit scope limitation that no Mechanical SDK/COM/native integration exists. Do not create `PROJECT_STATUS.md`.

- [ ] **Step 6: Merge and push**

After final review, fast-forward or merge the integration branch into `main`, rerun the clean-tree verification appropriate to the final head, and push `origin/main`. Report the final SHA and evidence without claiming live PASS unless it was actually observed.

## Self-review checklist

- Spec coverage: the design's contract, managed boundary, deterministic ordering, failure behavior, offline tests, live smoke, and dependency exclusions are covered by T01–T03.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation step is required; every task has exact files, interfaces, commands, and completion evidence.
- Type consistency: T01 defines `MechanicalComponentSnapshot`, `MechanicalAttributeSnapshot`, `IMechanicalDrawingGateway`, and the expanded `MechanicalOperationResult`; T02 consumes those exact names and maps them to the documented JSON fields.
- Scope check: the plan contains one feature, with sequential C# and IPC integration; it does not include Mechanical SDK, mutation, or unrelated refactoring.
