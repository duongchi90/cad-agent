# S2B AutoCAD-Native Render Evidence File IPC Seam

Status: accepted and squash-merged. The File IPC seam is implemented and
fail-closed; actual AutoCAD-native capture and live acceptance remain outside
S2B.

## Identity and bounded scope

- Issue: #52.
- PR: #55.
- Exact implementation base: `393f318317032096ec5e055ed1c928090f3b7e31`.
- Final reviewed head: `0ed4cd3a0c0a23cd9a52626fd24e35626288c9d9`.
- Final synthetic merge candidate: `fd9bb4153837d60483a00b6e3e3fc3a9d80c70e9`.
- Accepted squash merge: `3d0aa999904f384efa4eb42a81637e4270591859`.
- Branch: `task/s2b-native-render-ipc-seam`.
- Changed files: exactly the 15 Issue #52 allowlisted files.
- No dependency or `requirements/windows-py311.lock` change.

The branch contained two bounded commits. The second commit added only the two
validator helper overloads required for successful C# compilation. PO accepted
this narrow compile-completion amendment and squash-merged both commits into one
main commit.

## Implemented behavior

S2B adds the `native_render_evidence` operation to the existing File IPC
request/result envelopes and existing closed .NET dispatcher. The Python
adapter transports the accepted S2A request and validates any successful result
through the accepted native-render evidence contract.

The current .NET dispatcher recognizes the operation but returns the
deterministic `NATIVE_RENDER_NOT_IMPLEMENTED` error before any drawing-gateway
access. It produces no placeholder image or PDF and makes no mutation, approval,
verdict, repair, publication, or production-readiness claim.

The C# validator:

- enforces closed request, layout, render-option, artifact, and result shapes;
- rejects unsafe paths, malformed hashes/timestamps, unsupported artifact kinds,
  approval/verdict fields, mutation claims, entity handles, and negative or
  unequal DBMOD values;
- binds successful result identity and render options back to the request;
- requires read-only results and external artifact metadata only.

## Reuse Declaration

Existing capability inspected: `mcp_integration_lib.dotnet_ipc`, existing File
IPC operations, accepted S2A `autocad_render_evidence.py`, closed schemas,
`ContractModels`, `ContractValidator`, and `OperationDispatcher`.

Existing API reused: `DotNetIPCClient.request`, the existing File IPC envelopes,
S2A validation, schema conventions, C# validator/dispatcher, pytest, C# tests,
Ruff, architecture checker, and canonical verifier.

Adapter required: one `native_render_evidence` adapter through the existing
transport and dispatcher.

New capability genuinely missing: a versioned File IPC seam for native-render
evidence with explicit unsupported behavior before S2C.

Files forbidden to duplicate: File IPC transport, dispatcher, S2A validator,
AutoCAD renderer/plotter, visual verdict, repair executor, manifest/checkpoint/
revision stores, publisher, dependencies, and the Python lock file.

Compatibility behavior: existing File IPC operations retain their prior
allowlist entries and behavior. S2B adds no `IDrawingGateway`, `CommandContext`,
AutoCAD database, plotting, HWND, or live File IPC implementation.

Migration and rollback path: revert accepted squash merge
`3d0aa999904f384efa4eb42a81637e4270591859`; the existing operations and S2A
contract remain otherwise unchanged.

## Verification evidence

### Local mandatory .NET gate

Run on final head `0ed4cd3a0c0a23cd9a52626fd24e35626288c9d9`
with approved external Autodesk 2027 managed references:

```powershell
dotnet restore autocad_plugin/CadAgent.AutoCAD2027.sln
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --no-restore
dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --no-build --no-restore
```

Observed result:

- restore: PASS;
- Release/x64 build: PASS;
- C# tests: `113 passed, 0 failed`.

Autodesk references remain external. The production project declares
`<Private>false</Private>` for `AcCoreMgd`, `AcDbMgd`, and `AcMgd`; no Autodesk
DLL was added to the PR.

### Hosted sequential integration

GitHub Actions checked synthetic merge
`fd9bb4153837d60483a00b6e3e3fc3a9d80c70e9`, combining final head with `main`
at `f66367ab79672cc6fc844a8e393542962bcf7f32`.

Observed result:

- `tests` workflow #346: PASS;
- offline: `1022 passed`, 11 deselected, 18 subtests;
- offline JUnit: `1040/0/0/0`;
- dotnet IPC JUnit: `38/0/0/0`;
- `reuse-declaration` workflow #28: PASS;
- Ruff, architecture, lock/environment, and diff checks: PASS.

## Gate states

- Python focused/offline and schema gates: **PASS**.
- C# restore/build/test: **PASS**.
- GitHub sequential integration CI: **PASS**.
- AutoCAD Mechanical live/File IPC smoke: **NOT RUN**.
- Actual AutoCAD-native capture: **NOT IMPLEMENTED / NOT RUN**.
- Private drawing/data acceptance: **NOT RUN**.
- Placeholder image/PDF fabrication: **NOT IMPLEMENTED**.
- Verdict, approval, repair, and publication: **NOT IMPLEMENTED**.

S2B acceptance does not promote a native-render runtime. S2C requires its own
approved design/task, actual read-only gateway implementation, and live AutoCAD
Mechanical acceptance.
