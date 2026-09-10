# VIEWPORT-by-handle Read Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one bounded, read-only AutoCAD VIEWPORT-by-handle query so the exact paper-space and model-view fields for handle `126BABE` can be used as registration evidence without redrawing or mutating the source drawing.

**Architecture:** Add a dedicated `viewport_query` operation to the existing AutoCAD .NET/File IPC owner. It opens exactly one known handle `ForRead`, maps the AutoCAD 2027 `Viewport` properties into a closed field-status payload, and preserves the existing path/hash/DBMOD/read-only gates. The existing generic `review`, visual-evidence, mechanical-BOM, and native-render owners remain unchanged; their partial data is not silently repurposed as per-handle viewport data.

**Tech Stack:** Windows; Python 3.11; AutoCAD Mechanical 2027; .NET `net10.0-windows`, x64; JSON File IPC; C# xUnit; Python pytest; `scripts/verify.ps1`.

**Spec:** This document is the design/spec and the implementation plan for the capability.

**Status:** in progress; SOL design review passed; Tasks 1-2 complete, Tasks 3-4 pending bounded checkpoints.

**Approval date:** 2026-09-10; SOL design review passed with `VERDICT=PASS`, `HUMAN_GATE=NO`.

**Supported scope:** one existing AutoCAD drawing, one known hexadecimal entity handle, read-only inspection of a paper-space `Viewport`; no drawing discovery, extraction, copy, redraw, save, Xref creation, FileIPC mutation, or production promotion.

**Base SHA:** `de17ab9bcf9551b9eaf52dca8dd54b059871f8a`.

**Completion Head SHA:** not applicable while status is `planned`.

---

## Design

### Why a dedicated operation

The current `review` owner recognizes the handle but intentionally accepts only `LINE`, `CIRCLE`, `ARC`, `TEXT`, and `DIMENSION`; adding VIEWPORT data to its generic entity union would make a geometry-review response carry a second, different contract. A dedicated operation keeps the new capability narrow, makes the required drawing hash explicit, and reuses the existing gateway, dispatcher, JSON store, and Python IPC client rather than creating a transport.

The existing `AutoCadVisualEvidenceReader` is not the owner for this request: its internal `Viewport` branch only projects a rectangle during model-space region export. The existing `AutoCadNativeRenderReader` exposes active-camera values, not the native fields of a selected viewport entity. `CommandContext.ReadDrawingSetup` exposes only viewport scale/locked state. None is a substitute for this operation.

### Request contract

The operation name is exactly `viewport_query`. The request keeps the existing top-level IPC envelope and uses this closed parameter object:

```json
{
  "request_id": "layout-vp-126babe-20260910",
  "schema_version": "1.0",
  "operation": "viewport_query",
  "drawing_full_path": "C:\\Users\\dkv\\Downloads\\BVTL.dwg",
  "drawing_sha256": "78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8",
  "parameters": {
    "handle": "126BABE"
  },
  "approval": null
}
```

The literal handle is one non-empty hexadecimal AutoCAD handle, case-insensitive for lookup and returned uppercase. The operation rejects a missing hash, a non-absolute path, a non-hex handle, extra parameters, a non-null approval, or more than one handle. The request does not enumerate the drawing to discover a target.

### Response contract

The successful result has `success=true`, `changed=false`, `entity_handles=["126BABE"]`, empty `errors`, and a typed payload:

```json
{
  "schema_version": "viewport-query-result-1.0",
  "handle": "126BABE",
  "type": "VIEWPORT",
  "layer": "0",
  "fields": {
    "center_point": {"status": "OBSERVED", "value": [0.0, 0.0, 0.0]},
    "width": {"status": "OBSERVED", "value": 100.0},
    "height": {"status": "OBSERVED", "value": 50.0},
    "view_center": {"status": "OBSERVED", "value": [10.0, 20.0]},
    "view_height": {"status": "OBSERVED", "value": 200.0},
    "view_target": {"status": "OBSERVED", "value": [0.0, 0.0, 0.0]},
    "twist_angle": {"status": "OBSERVED", "value": 0.0}
  },
  "drawing_sha256_before": "78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8",
  "drawing_sha256_after": "78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8",
  "dbmod_before": 0,
  "dbmod_after": 0
}
```

Every field entry is closed and has one of these exact shapes:

```json
{"status": "OBSERVED", "value": 1.0}
{"status": "UNSUPPORTED", "reason": "PROPERTY_UNAVAILABLE"}
{"status": "ERROR", "reason": "PROPERTY_READ_FAILED"}
```

`OBSERVED` values must be finite; `width`, `height`, and `view_height` must be positive. The operation returns the viewport identity even when an individual property is `UNSUPPORTED` or `ERROR`, so missing API support is explicit and never becomes a guessed zero. The seven field names are fixed: `center_point`, `width`, `height`, `view_center`, `view_height`, `view_target`, and `twist_angle`.

### AutoCAD property mapping

The AutoCAD Mechanical 2027 `acdbmgd.dll` reflection check confirmed these public `Viewport` properties:

| Payload field | AutoCAD property | Value shape |
| --- | --- | --- |
| `center_point` | `Viewport.CenterPoint` | `[x, y, z]` |
| `width` | `Viewport.Width` | finite positive number |
| `height` | `Viewport.Height` | finite positive number |
| `view_center` | `Viewport.ViewCenter` | `[x, y]` |
| `view_height` | `Viewport.ViewHeight` | finite positive number |
| `view_target` | `Viewport.ViewTarget` | `[x, y, z]` |
| `twist_angle` | `Viewport.TwistAngle` | finite number in radians |

The reader must not call `GeometricExtents`, COM `GetBoundingBox`, `ViewTableRecord` camera inference, or any broad ModelSpace/PaperSpace enumeration. It resolves the requested handle through `Database.GetObjectId`, opens that object `ForRead`, verifies `entity is Viewport`, reads only the seven properties, and closes the read transaction.

### Safety and currentness invariants

1. `drawing_full_path` must match the active document exactly after Windows normalization.
2. `drawing_sha256` is required and must match the source hash before reading.
3. `DBMOD` must be captured before and after; the operation fails closed if it changes.
4. The source hash must be captured before and after; the operation fails closed if it changes.
5. The result always reports `changed=false`; no write transaction, save, clone, Xref, FileIPC mutation, or promotion is reachable from this operation.
6. A missing, erased, non-viewport, or unreadable handle produces a typed error/warning and no fabricated field values.
7. The operation is bounded to one handle and never discovers other entities.
8. The existing AutoCAD live session must be left with no changed drawing state; no temporary camera or system-variable mutation is needed.

### Non-goals

- Do not infer raster registration from a missing field.
- Do not change the existing `review` supported entity set.
- Do not add a second AutoCAD transport, COM bridge, or CAD geometry engine.
- Do not extract or copy the source viewport or any other source entity.
- Do not use this capability as permission to modify `BVTL.dwg` or promote the frozen disposable page-1 DXF.

## Implementation tasks

### Task 1: Add the closed viewport result types and contracts

**Files:**
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/ViewportQueryModels.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`
- Create: `contracts/autocad-ipc/operations/viewport-query.schema.json`
- Create: `contracts/autocad-ipc/operations/viewport-query-result.schema.json`
- Modify: `contracts/autocad-ipc/request.schema.json`
- Modify: `contracts/autocad-ipc/result.schema.json`
- Test: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`

**Interfaces:**
- Produce `ViewportQueryRequest(handle, drawingSha256)` with one canonical uppercase handle.
- Produce `ViewportQueryResult` with the seven closed field entries and before/after hash/DBMOD values.
- Produce `ViewportFieldState` with exact statuses `OBSERVED`, `UNSUPPORTED`, and `ERROR`.

- [x] **Step 1: Write the failing contract tests.** Add tests named `ViewportQueryRequiresOneHexHandleAndSourceHash`, `ViewportQueryRejectsExtraParameters`, `ViewportQueryResultRequiresClosedFieldEntries`, and `ViewportQueryResultRejectsNonFiniteObservedValues`.
- [x] **Step 2: Run the focused contract tests and verify failure.** Observed the expected RED run: 4 new tests failed because `viewport_query` was not allowlisted and its result/request rules were absent; the existing 37 contract tests passed.

Run:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj --no-restore --filter "FullyQualifiedName~ContractTests"
```

Expected: FAIL because `viewport_query` and `ViewportQueryResult` are not yet defined.

- [x] **Step 3: Implement only the closed records, JSON schema branches, and validator rules described above.** Keep the top-level IPC envelope at schema version `1.0`; the payload schema version is `viewport-query-result-1.0`.
- [x] **Step 4: Run the same focused tests and verify they pass.** Result: 41 passed, 0 failed, 0 skipped; JSON schema parse check passed.
- [x] **Step 5: Run `git diff --check` and commit only the contract/model files and tests.** Commit: `b88d370d271e7c1c8f8a202d014d1268a52785e9` (`feat(viewport): add query contracts`).

### Task 2: Add the read-only AutoCAD gateway and dispatcher owner

**Files:**
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Review/IDrawingGateway.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`
- Test: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Review/ReviewEngineTests.cs`
- Test: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`

**Interfaces:**
- Consume `ViewportQueryRequest` from Task 1.
- Add `IDrawingGateway.ReadViewportQuery(ViewportQueryRequest request)`.
- Produce a result with `changed=false`, stable hashes/DBMOD, and per-field statuses.

- [x] **Step 1: Write the failing gateway/dispatcher tests.** Add `DispatcherRoutesViewportQueryToTheReadOnlyGateway`, `ViewportQueryPreservesUnsupportedFieldState`, and `ViewportQueryNeverReportsChanged` using the existing stub gateway; configure one synthetic `ViewportQueryResult` with one `UNSUPPORTED` field and assert it is preserved exactly.
- [x] **Step 2: Run the focused tests and verify failure.** Observed the expected RED run: 3 new viewport dispatcher tests failed because the operation branch was absent; the existing 33 selected dispatcher/review tests passed.

Run:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj --no-restore --filter "FullyQualifiedName~OperationDispatcherTests|FullyQualifiedName~ReviewEngineTests"
```

Expected: FAIL because the gateway method and dispatcher branch do not exist.

- [x] **Step 3: Implement `AutoCadDrawingGateway.ReadViewportQuery`.** Uses `Database.GetObjectId(false, new Handle(parsedHandle), 0)`, opens the object `OpenMode.ForRead`, requires `Viewport`, reads only `CenterPoint`, `Width`, `Height`, `ViewCenter`, `ViewHeight`, `ViewTarget`, and `TwistAngle`, and wraps each property read in the explicit field-state mapping. It does not call `GeometricExtents` or enumerate ModelSpace/PaperSpace.
- [x] **Step 4: Implement `DispatchViewportQuery`.** Verifies the active path and requested source hash before calling the gateway, consumes stable source hash/DBMOD before and after from the owner, validates the result, and returns `success=true` only when the read completed with stable identity and currentness. A property-level `UNSUPPORTED`/`ERROR` remains explicit in the successful typed payload; a target identity/read transaction failure is a bounded operation error.
- [x] **Step 5: Run the focused tests and verify they pass.** Result: `dotnet test ... --filter "FullyQualifiedName~OperationDispatcherTests|FullyQualifiedName~ReviewEngineTests"` passed 47 tests, 0 failed, 0 skipped.
- [ ] **Step 6: Run `git diff --check` and commit the owner/dispatcher files and tests.**

### Task 3: Reuse the existing Python IPC client and add offline protocol coverage

**Files:**
- Modify: `mcp_integration_lib/dotnet_ipc.py`
- Test: `mcp_integration_lib/tests/test_dotnet_ipc.py`
- Test: `mcp_integration_lib/tests/test_mcp_dispatch_contract.py`

**Interfaces:**
- Add `DotNetIPCClient.viewport_query(drawing_full_path, *, drawing_sha256, handle, request_id=None)`.
- The method sends `operation="viewport_query"`, `parameters={"handle": handle}`, `approval=None`, and the required source hash through the existing JSON File IPC envelope.
- No new trigger, socket, HTTP endpoint, retry daemon, or direct COM dependency is permitted.

- [ ] **Step 1: Write the failing Python tests.** Add `test_viewport_query_sends_one_handle_and_required_hash`, `test_viewport_query_rejects_missing_hash`, and `test_viewport_query_rejects_extra_parameters` using the existing fake dispatcher/request-file assertions.
- [ ] **Step 2: Run the focused tests and verify failure.**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py mcp_integration_lib/tests/test_mcp_dispatch_contract.py -k viewport_query -q -p no:cacheprovider
```

Expected: FAIL because the client method and operation allowlist are absent.

- [ ] **Step 3: Add the client method and operation allowlist/schema references.** Preserve the existing cleanup behavior and reject a reused request ID result before dispatch.
- [ ] **Step 4: Run the focused Python tests and verify they pass.**
- [ ] **Step 5: Run `git diff --check` and commit the client/protocol files and tests.**

### Task 4: Run the required live disposable-DXF gate and update status

**Files:**
- Test: `mcp_integration_lib/tests/test_dotnet_ipc_live.py`
- Modify: `docs/STATUS.md`
- Review: `docs/QUALITY.md`, `docs/AI_OPERATING_MODEL.md`

**Interfaces:**
- Consume the existing AutoCAD Mechanical 2027 File IPC dispatcher and `CAD_AGENT_AUTOCAD_HWND` prerequisites.
- Produce one live result bound to a disposable DXF, the plugin binary hash, request ID, source hash, DBMOD before/after, and cleanup state.

- [ ] **Step 1: Add an opt-in live test that creates a disposable DXF under `C:\temp`, opens it through the existing owner, queries one known viewport handle, asserts all seven observed values or explicit statuses, asserts `changed=false`, and closes the disposable drawing without saving.** The test must record the candidate hash before and after and must not use `BVTL.dwg`.
- [ ] **Step 2: Run the focused live marker with prerequisites.**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest mcp_integration_lib/tests/test_dotnet_ipc_live.py -m autocad_mechanical -k viewport_query -ra -p no:cacheprovider
```

Expected: `PASS` only when AutoCAD Mechanical 2027, the approved dispatcher, and all declared environment variables are present; otherwise record `SKIP` or `NOT RUN`, never pass.

- [ ] **Step 3: Run the full authoritative verifier.**

Run:

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
.\scripts\bootstrap.ps1 -PythonExe $python311
.\scripts\verify.ps1
```

Record the exact exit code, test counts, live-gate state, plugin identity, and disposable artifact paths in the implementation plan and `docs/STATUS.md`.

- [ ] **Step 4: Request three bounded reviews required for AutoCAD/File IPC/architecture scope:** requirements/architecture, correctness/test, and security/operations. Each reviewer receives the compact packet from `docs/templates/`, the exact contract/schema diff, focused test output, live-gate state, and no private customer drawing.
- [ ] **Step 5: Update `docs/STATUS.md` only with evidence that actually ran.** Keep `BVTL.dwg`, the PDF, and the frozen disposable page-1 DXF outside Git.
- [ ] **Step 6: Run `git diff --check`, confirm no P0/P1 remains, and stop for design/implementation approval before using the new owner against `BVTL.dwg`.**

## Verification and gate record

Until implementation begins, the design checkpoint itself is the only completed action. No production code, AutoCAD source, FileIPC result, or Git history was changed by this plan creation.

When the plan is executed, the required evidence is:

- focused C# contract and dispatcher tests: `PASS` or explicit `NOT RUN`;
- focused Python IPC tests: `PASS` or explicit `NOT RUN`;
- `scripts/verify.ps1`: exact command and exit code;
- `autocad_mechanical` disposable-DXF smoke: `PASS`, `SKIP`, or `NOT RUN` with prerequisite reason;
- source/candidate/plugin hashes and DBMOD before/after;
- `git diff --check` result and final branch/head;
- three independent review reports with scope, impact, evidence, and verification.

The new owner must not be used to approve or promote the current page-1 candidate until a fresh registration oracle consumes its result and SOL returns a new verdict.
