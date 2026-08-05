# S2C AutoCAD-Native Layout Capture Implementation Record

Status: production implementation, offline gates, and AutoCAD Mechanical 2027
live PNG/PDF acceptance are **PASS** on exact live-reviewed head
`8cd75641c3c40032fb2e24b3597f163ccb434265`. This commit is the final
docs-only record update; the PR remains open for PO review and must not be
merged until that review accepts the updated record.

## Identity and bounded scope

- Issue: #60, S2C.
- Exact implementation base: `3d0aa999904f384efa4eb42a81637e4270591859`.
- Implementation branch: `task/s2c-autocad-native-render`.
- Verified source-fix head: `009bc49320e104178f99af4e759d071e616535b8`.
- Verified live-reviewed head: `8cd75641c3c40032fb2e24b3597f163ccb434265`.
- Prior review-fix head: `67f958ed583477df340508ead925cbba0166935b`.
- Source-fix commits: `67f958e` (claim cleanup, refusal evidence, and
  provenance fixes) and `009bc49` (PNG decode validation and post-move
  publication boundary).
- The live acceptance was run against the verified live-reviewed head above.
  This commit changes only this implementation record, so the tested source
  SHA remains unambiguous.
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
Ruff, DLL-output, and diff checks **PASS**. At this source-fix verification
point the canonical AutoCAD live marker was **NOT RUN**; the live gate was
subsequently executed and is recorded below.

### AutoCAD Mechanical 2027 live gate

Live acceptance passed on exact live-reviewed head
`8cd75641c3c40032fb2e24b3597f163ccb434265` using the official File IPC and
AutoCAD .NET drawing gateway. No production source changed during the live
run.

- Positive official command (exit `0`):

  ```powershell
  & 'C:\temp\cad-agent-s2c-py311\Scripts\python.exe' -m pytest mcp_integration_lib/tests/test_dotnet_ipc_live.py -m autocad_mechanical -k 'test_s2c_png_pdf_and_fail_closed_probes_are_read_only' -ra -p no:cacheprovider
  ```

  Result: **1 passed, 10 deselected** in `9.88s`. PNG, PDF, duplicate,
  missing-layout, and unsupported-profile probes passed.
- PNG profile: device `PublishToWeb PNG.pc3`; the approved device exposed
  exactly the canonical raster media
  `UserDefinedRaster (2480.00 x 3508.00Pixels)` with plot units `Pixels`.
  The final PNG passed the artifact-boundary checks and Pillow `verify()` and
  `load()` decoding checks.
- PDF profile: device `AutoCAD PDF (General Documentation).pc3`; canonical
  media `ISO_A4_(210.00_x_297.00_MM)`. The final PDF opened as a valid
  one-page document.
- Missing-device official command (exit `0`) used the isolated
  `CAD_AGENT_S2C_NEGATIVE_PROFILE=missing-device` profile and returned the
  exact `NATIVE_RENDER_DEVICE_UNAVAILABLE` error with no artifact:

  ```powershell
  & 'C:\temp\cad-agent-s2c-py311\Scripts\python.exe' -m pytest mcp_integration_lib/tests/test_dotnet_ipc_live.py -m autocad_mechanical -k 'test_s2c_missing_device_refuses_without_artifact' -ra -p no:cacheprovider
  ```

  Result: **1 passed, 10 deselected** in `5.36s`.
- Missing-media official command (exit `0`) used the isolated
  `CAD_AGENT_S2C_NEGATIVE_PROFILE=missing-media` profile and returned the
  exact `NATIVE_RENDER_MEDIA_UNAVAILABLE` error with no artifact:

  ```powershell
  & 'C:\temp\cad-agent-s2c-py311\Scripts\python.exe' -m pytest mcp_integration_lib/tests/test_dotnet_ipc_live.py -m autocad_mechanical -k 'test_s2c_missing_media_refuses_without_artifact' -ra -p no:cacheprovider
  ```

  Result: **1 passed, 10 deselected** in `6.76s`.
- The official assertions covered request-owned artifact paths and final-byte
  SHA-256, `changed=false`, `entity_handles=[]`, empty failure payloads,
  equal non-negative DBMOD values, unchanged CTAB, unchanged
  BACKGROUNDPLOT, unchanged DWG hash, current-layout preservation, and
  AutoCAD/session restoration. Missing-device and missing-media refusals
  proved final-artifact absence.
- The live run restored the AutoCAD plotting/session state. The follow-up
  record-only commit does not require another live run because its parent is
  exactly the live-reviewed head and its only changed path is this record.

### Other gates and scope

- Private-data/real-drawing gate: **NOT RUN**; no private data was supplied.
- Verdict: **NOT IMPLEMENTED**.
- Approval: **NOT IMPLEMENTED**.
- Repair: **NOT IMPLEMENTED**.
- Publication: **NOT IMPLEMENTED**.
- S3B and R1C: not started by this task.

The AutoCAD Mechanical 2027 live gate is **PASS**. The PR remains open only
for PO review of this final record update; S3B and R1C remain locked.
