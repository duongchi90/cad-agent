# S2C AutoCAD-Native Layout Capture Implementation Record

Status: production implementation and offline gates complete; AutoCAD
Mechanical 2027 live PNG/PDF acceptance is **NOT RUN** because this machine
has no configured live File IPC session. S2C is not accepted until that gate
passes.

## Identity and bounded scope

- Issue: #60, S2C.
- Exact implementation base: `3d0aa999904f384efa4eb42a81637e4270591859`.
- Implementation branch: `task/s2c-autocad-native-render`.
- Verified source-fix head: `009bc49320e104178f99af4e759d071e616535b8`.
- Prior review-fix head: `67f958ed583477df340508ead925cbba0166935b`.
- Source-fix commits: `67f958e` (claim cleanup, refusal evidence, and
  provenance fixes) and `009bc49` (PNG decode validation and post-move
  publication boundary).
- This record-only update is kept separate from the source-fix head so the
  tested source SHA remains unambiguous; the final branch head is recorded in
  PR provenance after this commit.
- The branch contains the two approved docs-only commits plus the bounded
  implementation, live-test, review-fix, source-fix, and this evidence-record
  change.
- Changed paths remain inside the exact Issue #60 20-file allowlist. No schema,
  Python production, dependency, project, `STATUS.md`, or `HANDOFF.md` file
  changed.

## Reuse Declaration

Existing capability inspected: existing File IPC request/result store,
`ContractValidator`, `OperationDispatcher`, `IDrawingGateway`, active-document
identity check, `CommandContext.AutoCadDrawingGateway`, Autodesk managed Plot
API references, and the existing `DotNetIPCClient.native_render_evidence()`
contract path.

Existing API reused: existing File IPC root and dispatcher, contract result
envelope, gateway abstraction, AutoCAD `PlotSettings`/
`PlotSettingsValidator`/`PlotInfo`/`PlotInfoValidator`/`PlotEngine` APIs, and
existing live trigger/client helpers.

Adapter required: one `IDrawingGateway.ReadNativeRenderEvidence` adapter and
one AutoCAD-native reader behind the existing gateway; one request-owned
`NativeRenderArtifactBoundary` for safe temporary output and atomic publish.

New capability genuinely missing: read-only AutoCAD paper-space A4 capture to
PNG or one-page PDF, with exact PC3/media selection, DBMOD/DWG/session-state
invariants, and hash-verified request-owned artifact publication.

Files allowed to change: only the 20 paths locked by Issue #60; the exact list
is preserved in the approved plan and issue.

Files forbidden to duplicate: schemas, Python production validators or IPC
transport, a second dispatcher/transport/renderer, Autodesk DLLs in the
repository, verdict/approval/repair/publication owners, dependencies,
`STATUS.md`, and `HANDOFF.md`.

Compatibility behavior: existing operations and S2A/S2B schemas remain
unchanged. Native render accepts only paper-space A4, white, 300 DPI,
fit-to-paper, `monochrome.ctb`, and PNG/PDF. Failures return no artifact
payload; success returns `changed=false`, no entity handles, equal non-negative
DBMOD values, and a relative path below
`IPC_ROOT/native-render/<request_id>/`.

Migration and rollback path: review and merge the single PR only after the
live gate. Roll back the S2C implementation/live-test commits if required;
the pre-existing S2B fail-closed seam remains the safe fallback. No artifact
cleanup or maintenance job is introduced by S2C.

## Implementation boundaries

- The existing File IPC root is reused; no `artifact_directory` is accepted.
- The .NET side owns `native-render/<request_id>/`, uses the validated request
  ID unchanged, rejects traversal/control/drive/path separators, rejects
  reparse points, and uses an exclusive claim.
- Plot output is written to a same-directory temporary file and published with
  no-overwrite atomic rename only after byte validation and SHA-256 hashing.
  After the atomic move, publication only marks the reservation and returns
  metadata/hash already verified from the temporary bytes; it performs no
  final-artifact read or hash operation.
- PNG signature/IHDR/dimension/IEND checks run before publication and accept
  only exact A4 300 DPI pixel dimensions `2480x3508` or `3508x2480`. PNG
  validation also requires legal IHDR combinations, CRC-valid chunks, a
  concatenated zlib IDAT stream, exact non-interlaced scanline length, and
  filter bytes in the PNG-defined range. PDF publication requires a coherent
  catalog, page tree, xref/startxref, trailer, and exactly one page. Failed
  output has no final artifact.
- The artifact claim remains held through final-path publication. If a move
  loses a final-path race, cleanup can delete only a final file proven to
  have been created by that reservation and whose bytes still match.
- `BACKGROUNDPLOT` is snapshotted, set to foreground plotting, and restored in
  all exit paths. Current layout, drawing database, and file bytes are not
  modified or saved.
- Paper-space uses `PlotType.Layout` without plot centering. Device/media
  selection is exact: approved PDF A4 millimeters or approved PNG pixel
  media; missing device/media fails closed.
- The dispatcher binds all five render-option fields, correlation fields,
  read-only DBMOD values, artifact metadata, and the exact
  `native-render/<request_id>/artifact.png|pdf` path before success.
- `layout.identity` is correlation metadata; `layout.name` selects the actual
  paper-space AutoCAD layout. No entity handles, verdict, approval, repair, or
  publication result is produced.

## Verification evidence

### Exact source-fix evidence

- Source-fix head: `009bc49320e104178f99af4e759d071e616535b8`.
- Autodesk reference directory: `C:\Program Files\Autodesk\AutoCAD 2027`,
  with `AcCoreMgd.dll`, `AcDbMgd.dll`, and `AcMgd.dll` resolved from that
  official AutoCAD Mechanical 2027 installation.
- .NET SDK: `10.0.301`.

Release/x64 restore, build, and test were run by the canonical command below;
the .NET sub-gate exited `0` with **163 passed, 0 failed, 0 skipped**.

Focused boundary/policy command (exit `0`):

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj -c Release -p:Platform=x64 --no-restore --no-build --filter "FullyQualifiedName~NativeRenderArtifactBoundaryTests|FullyQualifiedName~NativeRenderBoundaryTests" --verbosity minimal
```

Result: **43 passed, 0 failed, 0 skipped**.

Architecture command (exit `0`):

```powershell
& 'C:\temp\cad-agent-s2c-py311\Scripts\python.exe' scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Result: **Architecture boundaries: PASS**.

Ruff command (exit `0`):

```powershell
& 'C:\temp\cad-agent-s2c-py311\Scripts\python.exe' -m ruff check mcp_integration_lib/tests/test_dotnet_ipc_live.py
```

Result: **All checks passed**. `git diff --check` exited `0`.

Built plugin assembly SHA-256 at the source-fix head:
`49F8E8CB1FED61543079ADAA80CE386ED037EF1269D61E1FEB8D54D0AB265D67`.
No Autodesk managed DLLs were copied into the repository or plugin output.

The canonical verifier was run on the clean source-fix head with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -PythonExe C:\temp\cad-agent-s2c-py311\Scripts\python.exe
```

It exited `0`: dependency lock/environment **PASS**; .NET **163 passed, 0
failed, 0 skipped**; dotnet IPC JUnit `38 tests, 0 failures, 0 errors, 0
skipped`; offline JUnit `1040 tests, 0 failures, 0 errors, 0 skipped` (1022
passed, 14 deselected, 18 subtests); private-data unavailable probe `2
skipped`; AutoCAD Mechanical unavailable probe `12 skipped`; architecture,
Ruff, DLL-output, and diff checks **PASS**. The canonical AutoCAD live marker
was **NOT RUN**.

### AutoCAD Mechanical live gate

- AutoCAD 2027 `acad.exe` is installed at
  `C:\Program Files\Autodesk\AutoCAD 2027\acad.exe`.
- At verification time there was no running AutoCAD process, no
  `CAD_AGENT_AUTOCAD_HWND`, no `CAD_AGENT_AUTOCAD_LISP_PATH`, no
  `CAD_AGENT_DOTNET_IPC_DIR`, no `CAD_AGENT_FILE_IPC=1`, no
  `CAD_AGENT_S2C_LIVE=1`, and no `CAD_AGENT_LEAN_DISPOSABLE_DWG`.
- Command:

  ```powershell
  & 'C:\temp\cad-agent-s2c-py311\Scripts\python.exe' -m pytest mcp_integration_lib/tests/test_dotnet_ipc_live.py -m autocad_mechanical -ra -p no:cacheprovider
  ```

  exited `0`: **12 skipped, 1024 deselected** in the canonical unavailable
  probe; the S2C class's three tests were skipped by their explicit
  prerequisite guards. This is **NOT RUN**, not acceptance.
- Live PNG artifact: **NOT RUN**.
- Live PDF artifact: **NOT RUN**.
- Duplicate, missing-layout, unsupported-profile, missing-device, and
  missing-media refusal probes: **NOT RUN**. The latter two require an
  operator-prepared isolated AutoCAD profile marked with
  `CAD_AGENT_S2C_NEGATIVE_PROFILE`; the harness never changes shared
  AutoCAD configuration.
- Product/profile, disposable DWG hash, exact layout, PC3 output, canonical
  media, DBMOD, current-layout, and restored-session live evidence: **NOT RUN**.
- Approved profile constants are fixed in the reader as:
  `AutoCAD PDF (General Documentation).pc3`, `PublishToWeb PNG.pc3`, and
  `ISO_A4_(210.00_x_297.00_MM)`.

### Other gates and scope

- Private-data/real-drawing gate: **NOT RUN**; no private data was supplied.
- Verdict: **NOT IMPLEMENTED**.
- Approval: **NOT IMPLEMENTED**.
- Repair: **NOT IMPLEMENTED**.
- Publication: **NOT IMPLEMENTED**.
- S3B and R1C: not started by this task.

The PR must remain open for PO review and live AutoCAD Mechanical 2027 PNG/PDF
acceptance. Offline success does not promote this implementation to accepted
S2C status.
