# S2B AutoCAD-Native Render Evidence File IPC Seam

Status: bounded S2B seam implemented; actual native capture and live acceptance
remain locked for S2C.

## Identity and bounded scope

- Issue: #52.
- Exact implementation base SHA: `393f318317032096ec5e055ed1c928090f3b7e31`.
- Final head SHA: emitted by the single bounded commit and recorded in the PR
  provenance; a commit cannot contain its own object ID without becoming
  self-referential.
- Branch: `task/s2b-native-render-ipc-seam`.
- Changed files: exactly the 15 Issue #52 allowlisted files.
- No dependencies or `requirements/windows-py311.lock` changed.

The seam adds the `native_render_evidence` File IPC operation, maps the accepted
S2A request fields through the existing envelope, validates successful payloads
with `validate_render_evidence`, and returns the deterministic
`NATIVE_RENDER_NOT_IMPLEMENTED` failure before any drawing gateway access.
No image or PDF artifact is fabricated.

## Reuse Declaration

Existing capability inspected: `mcp_integration_lib.dotnet_ipc`, the existing
`health`, `review`, `drawing_setup_audit`, and `visual_evidence_export` File IPC
operations, `autocad_render_evidence.py`, the closed request/result schemas,
the C# contract validator, and the operation dispatcher.

Existing API reused: `DotNetIPCClient.request`, the existing request/result
envelopes, JSON schema conventions, `ContractModels`, `ContractValidator`,
`OperationDispatcher`, pytest, C# unit tests, Ruff, the architecture checker,
and the canonical verifier.

Adapter required: one operation adapter named `native_render_evidence` that
transports the accepted S2A request fields and validates returned evidence
through `validate_render_evidence`.

New capability genuinely missing: a versioned File IPC envelope and closed
dispatcher registration for native-render evidence, with an explicit
unsupported/fail-closed result until S2C implements the AutoCAD drawing
gateway.

Files allowed to change: `contracts/autocad-ipc/operations/native-render-evidence.schema.json`,
`contracts/autocad-ipc/operations/native-render-evidence-result.schema.json`,
`contracts/autocad-ipc/examples/native-render-evidence-request.json`,
`contracts/autocad-ipc/examples/native-render-evidence-result.json`,
`contracts/autocad-ipc/request.schema.json`, `contracts/autocad-ipc/result.schema.json`,
`mcp_integration_lib/dotnet_ipc.py`,
`mcp_integration_lib/tests/test_autocad_render_evidence_ipc.py`,
`tests/test_autocad_render_evidence_ipc_contracts.py`,
`autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`,
`autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`,
`autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`,
`autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`,
`autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`,
and this implementation record.

Files forbidden to duplicate: File IPC transport, dispatcher, S2A validator,
AutoCAD renderer/plotter, visual verdict, repair executor, manifest/checkpoint/
revision stores, publisher, dependencies, and `requirements/windows-py311.lock`.

Compatibility behavior: all existing operations retain their existing allowlist
entries and request/result behavior. The new operation validates safely but
fails explicitly as `NATIVE_RENDER_NOT_IMPLEMENTED` against the current live
gateway. No `IDrawingGateway`, `CommandContext`, AutoCAD database, plot API,
HWND, or live File IPC implementation was added or changed.

Migration and rollback path: revert the single bounded S2B commit; existing
operations and the S2A offline contract remain unchanged.

## Verification evidence

Focused IPC and S2A contract command:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_autocad_render_evidence.py mcp_integration_lib/tests/test_dotnet_ipc.py mcp_integration_lib/tests/test_autocad_render_evidence_ipc.py tests/test_autocad_render_evidence_ipc_contracts.py tests/test_vs_t3_ipc_contracts.py -q -p no:cacheprovider
```

Observed result: exit `0`; `111 passed, 18 subtests passed`.

Full offline Python command:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests primitive_ir_lib/tests semantic_ir_lib/tests dxf_builder_lib/tests mcp_integration_lib/tests agent_lib/tests -q -m "not real_data and not autocad_mechanical" -p no:cacheprovider
```

Observed result: exit `0`; `869 passed, 11 deselected, 18 subtests passed`.

Ruff command:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_autocad_render_evidence_ipc.py tests/test_autocad_render_evidence_ipc_contracts.py
```

Observed result: exit `0`; all checks passed.

Architecture command:

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Observed result: exit `0`; `Architecture boundaries: PASS`.

Diff command:

```powershell
git diff --check
```

Observed result: exit `0` before the bounded commit.

Canonical verifier command and result are recorded against the clean bounded
candidate in the final PR provenance. The AutoCAD .NET portion is `NOT RUN`
because this workstation has no `dotnet`, `msbuild`, or `csc` executable.

The mandatory commands were attempted exactly:

```powershell
dotnet restore autocad_plugin/CadAgent.AutoCAD2027.sln
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --no-restore
dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --no-build --no-restore
```

Each exited `1` because PowerShell reported that `dotnet` was not recognized.
This is an environment blocker, not a pass.

## Gate states

- Python focused and offline gates: **PASS**.
- Ruff: **PASS**.
- Architecture checker: **PASS**.
- `git diff --check`: **PASS**.
- C# restore/build/test: **NOT RUN**; .NET SDK absent.
- AutoCAD Mechanical live/File IPC smoke: **NOT RUN** and locked.
- Actual AutoCAD-native capture: **NOT RUN** and locked for S2C.
- Private drawing/data gate: **NOT RUN**.
- Image/PDF fabrication: **NOT IMPLEMENTED**.
- Verdict, approval, repair, and publication: **NOT IMPLEMENTED**.
- S2C and S3 tasks: **NOT RUN**.

Unavailable-state skips are not acceptance evidence and are not reported as
passes.
